"""Checkers for the unified stop gate hook."""

from dataclasses import dataclass
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from .config import CheckResult, EnvironmentConfig, PathResolver, Priority


@dataclass
class SessionInfo:
    """Information about the current session extracted from hook input.

    Attributes:
        session_id: Unique identifier for the current session.
        current_iteration: The current iteration count in the session.
        transcript_path: Optional path to the session transcript file.
    """

    session_id: str
    current_iteration: int
    transcript_path: Optional[str]

    @classmethod
    def from_hook_input(cls, hook_input: dict) -> 'SessionInfo':
        """Create SessionInfo from Claude hook input dictionary.

        Args:
            hook_input: Dictionary from Claude hook containing session data.

        Returns:
            SessionInfo populated from the hook input with defaults for missing values.
        """
        return cls(
            session_id=hook_input.get('session_id', 'unknown'),
            current_iteration=int(hook_input.get('iteration', 0)),
            transcript_path=hook_input.get('transcript_path'),
        )


class MaxIterationsChecker:
    """P0: Circuit breaker - force ALLOW if iterations exceeded.

    This is the highest priority check (P0). When the iteration count
    reaches or exceeds max_iterations, the circuit breaker triggers
    and forces ALLOW to prevent infinite blocking loops.

    The circuit breaker ensures that even if all other checks would
    block, the session can eventually proceed after sufficient iterations.
    """

    def __init__(self, config: EnvironmentConfig, session: SessionInfo):
        """Initialize the checker.

        Args:
            config: Environment configuration with max_iterations setting.
            session: Session info with current iteration count.
        """
        self.config = config
        self.session = session

    def check(self) -> CheckResult:
        """Check if circuit breaker should trigger.

        Returns:
            CheckResult with:
            - passed=True if iterations >= max_iterations (triggers ALLOW)
            - passed=False if under the limit (circuit breaker not triggered)
        """
        if self.session.current_iteration >= self.config.max_iterations:
            return CheckResult(
                priority=Priority.P0_CIRCUIT_BREAKER,
                passed=True,  # Passed = trigger circuit breaker
                message=f"Circuit breaker: {self.session.current_iteration}/{self.config.max_iterations} iterations reached. Forcing ALLOW.",
                blocking=False,
            )
        return CheckResult(
            priority=Priority.P0_CIRCUIT_BREAKER,
            passed=False,  # Not triggered
            message=f"Iteration {self.session.current_iteration}/{self.config.max_iterations}",
            blocking=False,
        )


class CompletionPromiseChecker:
    """P1: Check if completion promises have been fulfilled.

    Multi-session aware promise checker. Each session owns a set of promises
    identified by CLAUDE_SESSION_ID. The session cannot end until all owned
    promises are verified or cancelled.

    Promise lifecycle: pending → in_progress → verified | cancelled

    Architecture:
        - Promises are stored in .claude/completion-state/promises/{uuid}.json
        - Each promise has an owned_by field tracking the current owner
        - All sessions can see all promises but only own their own
        - Orphaned promises (owned_by=null) generate warnings but don't block
    """

    def __init__(self, config: EnvironmentConfig, paths: PathResolver):
        """Initialize the checker.

        Args:
            config: Environment configuration.
            paths: Path resolver for locating promise files.
        """
        self.config = config
        self.paths = paths
        self.session_id = os.environ.get('CLAUDE_SESSION_ID', '')

    def check(self) -> CheckResult:
        """Check if all owned completion promises are fulfilled.

        Scans the promises directory for promises owned by the current session.
        Blocks if any owned promises have 'pending' or 'in_progress' status.
        Warns about orphaned in_progress promises but doesn't block on them.

        Returns:
            CheckResult with:
            - passed=True if no owned promises or all owned promises are verified/cancelled
            - passed=False if owned promises have pending/in_progress status (BLOCK)
        """
        promises_dir = self.paths.promises_dir

        # No promises directory = no promises exist
        if not promises_dir.exists():
            return CheckResult(
                priority=Priority.P1_COMPLETION_PROMISE,
                passed=True,
                message="No completion promises defined",
                blocking=True,
            )

        # Scan all promise files FIRST to detect in_progress promises
        my_promises = []
        orphaned_in_progress = []
        all_in_progress = []

        try:
            for promise_file in promises_dir.glob('*.json'):
                with open(promise_file, 'r') as f:
                    promise = json.load(f)

                promise_id = promise.get('id', 'unknown')
                status = promise.get('status', 'unknown')
                owner = promise.get('ownership', {}).get('owned_by')
                summary = promise.get('summary', '')[:50]

                # Track ALL in_progress promises for no-session-id check
                if status == 'in_progress':
                    all_in_progress.append({
                        'id': promise_id,
                        'owner': owner,
                        'summary': summary,
                    })

                # Track promises owned by this session (if session ID set)
                if self.session_id and owner == self.session_id:
                    my_promises.append({
                        'id': promise_id,
                        'status': status,
                        'summary': summary,
                    })
                # Track orphaned in_progress promises (warning only)
                elif owner is None and status == 'in_progress':
                    orphaned_in_progress.append({
                        'id': promise_id,
                        'summary': summary,
                    })

        except (json.JSONDecodeError, OSError) as e:
            return CheckResult(
                priority=Priority.P1_COMPLETION_PROMISE,
                passed=False,
                message=f"Error reading promises: {e}",
                blocking=True,
            )

        # If no session ID: WARN about other sessions' promises but allow stop
        # Only BLOCK if THIS session owns incomplete promises (checked below)
        if not self.session_id:
            if all_in_progress:
                promise_list = "\n".join([f"  - {p['id']}: {p['summary']} (owner: {p['owner']})" for p in all_in_progress[:5]])
                return CheckResult(
                    priority=Priority.P1_COMPLETION_PROMISE,
                    passed=True,  # Allow stop - these belong to OTHER sessions
                    message=f"[INFO] {len(all_in_progress)} in_progress promise(s) from other sessions:\n{promise_list}",
                    blocking=False,  # Non-blocking warning
                )
            return CheckResult(
                priority=Priority.P1_COMPLETION_PROMISE,
                passed=True,
                message="No CLAUDE_SESSION_ID set and no in_progress promises - OK to stop",
                blocking=True,
            )

        # From here, we have a session ID - use the data already collected above
        # my_promises was populated during the initial scan when self.session_id matched

        # Track OTHER sessions' in_progress promises (not orphaned, not mine)
        other_sessions_in_progress = [
            p for p in all_in_progress
            if p['owner'] is not None and p['owner'] != self.session_id
        ]

        # No owned promises = can end
        if not my_promises:
            warnings = []
            if orphaned_in_progress:
                warnings.append(f"{len(orphaned_in_progress)} orphaned in_progress promise(s)")
            if other_sessions_in_progress:
                warnings.append(f"{len(other_sessions_in_progress)} in_progress promise(s) from other sessions")
            warning = f" [WARNING: {', '.join(warnings)}]" if warnings else ""
            return CheckResult(
                priority=Priority.P1_COMPLETION_PROMISE,
                passed=True,
                message=f"No promises owned by this session{warning}",
                blocking=True,
            )

        # Check for incomplete promises
        incomplete = [p for p in my_promises if p['status'] in ('pending', 'in_progress')]

        if not incomplete:
            return CheckResult(
                priority=Priority.P1_COMPLETION_PROMISE,
                passed=True,
                message=f"All {len(my_promises)} owned promise(s) completed",
                blocking=True,
            )

        # Build blocking message
        in_progress = [p for p in incomplete if p['status'] == 'in_progress']
        pending = [p for p in incomplete if p['status'] == 'pending']

        msg_parts = []
        if in_progress:
            first = in_progress[0]
            msg_parts.append(f"{len(in_progress)} in_progress (e.g., {first['id']}: \"{first['summary']}...\")")
        if pending:
            first = pending[0]
            msg_parts.append(f"{len(pending)} pending (e.g., {first['id']}: \"{first['summary']}...\")")

        warning = ""
        if orphaned_in_progress:
            warning = f" [WARNING: {len(orphaned_in_progress)} orphaned in_progress promise(s)]"

        return CheckResult(
            priority=Priority.P1_COMPLETION_PROMISE,
            passed=False,
            message=f"Incomplete promises: {', '.join(msg_parts)}{warning}",
            blocking=True,
        )


class BeadsSyncChecker:
    """P2: Check if .beads/ has uncommitted changes.

    Ensures data integrity by blocking if the beads database has
    uncommitted changes that could be lost.
    """

    def __init__(self, config: EnvironmentConfig):
        """Initialize the checker.

        Args:
            config: Environment configuration with project_dir.
        """
        self.config = config

    def check(self) -> CheckResult:
        """Check if .beads/ directory has uncommitted changes.

        Returns:
            CheckResult with:
            - passed=True if .beads/ is clean or doesn't exist
            - passed=False if .beads/ has uncommitted changes (BLOCK)
        """
        try:
            # Check git status for .beads/ directory
            result = subprocess.run(
                ["git", "status", "--porcelain", ".beads/"],
                cwd=self.config.project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            # If there's output, there are uncommitted changes
            if result.stdout.strip():
                dirty_files = result.stdout.strip().split('\n')
                return CheckResult(
                    priority=Priority.P2_BEADS_SYNC,
                    passed=False,
                    message=f"Beads has uncommitted changes ({len(dirty_files)} files). Run 'bd sync' before completing.",
                    blocking=True,
                )

            return CheckResult(
                priority=Priority.P2_BEADS_SYNC,
                passed=True,
                message="Beads directory is clean",
                blocking=True,
            )

        except subprocess.TimeoutExpired:
            return CheckResult(
                priority=Priority.P2_BEADS_SYNC,
                passed=False,
                message="Git status timed out - unable to verify beads sync",
                blocking=True,
            )
        except FileNotFoundError:
            # Git not installed or not a git repo
            return CheckResult(
                priority=Priority.P2_BEADS_SYNC,
                passed=True,
                message="Not a git repository or git not available",
                blocking=True,
            )
        except Exception as e:
            return CheckResult(
                priority=Priority.P2_BEADS_SYNC,
                passed=False,
                message=f"Error checking beads sync: {e}",
                blocking=True,
            )


class TodoContinuationChecker:
    """P3: Check if session has pending todos requiring continuation.

    Placeholder implementation - future versions will read from
    session transcript to detect incomplete todos.
    """

    def __init__(self, config: EnvironmentConfig, session: SessionInfo):
        """Initialize the checker.

        Args:
            config: Environment configuration.
            session: Session info (for future transcript analysis).
        """
        self.config = config
        self.session = session

    def check(self) -> CheckResult:
        """Check if there are pending todos requiring continuation.

        Returns:
            CheckResult - currently always passes (placeholder).
            Future: Will analyze session transcript for incomplete todos.
        """
        # Placeholder: Always pass for now
        # Future implementation will read from session transcript
        # to detect incomplete TodoWrite items
        return CheckResult(
            priority=Priority.P3_TODO_CONTINUATION,
            passed=True,
            message="Todo continuation check: placeholder (always pass)",
            blocking=True,
        )


class GitStatusChecker:
    """P4: Advisory check for uncommitted git changes.

    Non-blocking check that warns about uncommitted changes.
    Unlike BeadsSyncChecker (P2), this checks ALL uncommitted changes
    and is advisory only (blocking=False).
    """

    def __init__(self, config: EnvironmentConfig):
        """Initialize the checker.

        Args:
            config: Environment configuration with project_dir.
        """
        self.config = config

    def check(self) -> CheckResult:
        """Check for any uncommitted git changes.

        Returns:
            CheckResult with:
            - passed=True if working directory is clean
            - passed=False if uncommitted changes exist (WARN, non-blocking)
        """
        try:
            # Check git status for ALL uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.config.project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            # If there's output, there are uncommitted changes
            if result.stdout.strip():
                dirty_files = [
                    line for line in result.stdout.strip().split('\n')
                    if line.strip()
                ]
                return CheckResult(
                    priority=Priority.P4_GIT_STATUS,
                    passed=False,
                    message=f"Uncommitted changes ({len(dirty_files)} files). Consider committing before completing.",
                    blocking=False,  # Advisory only
                )

            return CheckResult(
                priority=Priority.P4_GIT_STATUS,
                passed=True,
                message="Working directory is clean",
                blocking=False,
            )

        except subprocess.TimeoutExpired:
            return CheckResult(
                priority=Priority.P4_GIT_STATUS,
                passed=True,  # Don't block on timeout for advisory check
                message="Git status timed out",
                blocking=False,
            )
        except FileNotFoundError:
            # Git not installed or not a git repo
            return CheckResult(
                priority=Priority.P4_GIT_STATUS,
                passed=True,
                message="Not a git repository or git not available",
                blocking=False,
            )
        except Exception as e:
            return CheckResult(
                priority=Priority.P4_GIT_STATUS,
                passed=True,  # Don't block on errors for advisory check
                message=f"Error checking git status: {e}",
                blocking=False,
            )


class BusinessOutcomeChecker:
    """P5: Check business outcomes (focused mode).

    Only active when enforce_bo is True. Placeholder implementation
    that will check business outcomes in the future.
    """

    def __init__(self, config: EnvironmentConfig):
        """Initialize the checker.

        Args:
            config: Environment configuration with enforce_bo setting.
        """
        self.config = config

    def check(self) -> CheckResult:
        """Check if business outcomes are met.

        Returns:
            CheckResult with:
            - passed=True if enforce_bo=False (skip check)
            - passed=True/False based on business outcome verification (future)
        """
        # If not enforcing business outcomes, skip the check
        if not self.config.enforce_bo:
            return CheckResult(
                priority=Priority.P5_BUSINESS_OUTCOMES,
                passed=True,
                message="Business outcomes check: disabled (enforce_bo=False)",
                blocking=True,
            )

        # Placeholder: When enforced, currently always passes
        # Future implementation will verify business outcomes
        return CheckResult(
            priority=Priority.P5_BUSINESS_OUTCOMES,
            passed=True,
            message="Business outcomes check: placeholder (always pass when enforced)",
            blocking=True,
        )


class OrchestratorGuidanceChecker:
    """P2.5: Check if orchestrator has unescalated blockers.

    Only active for orchestrator sessions (session ID starts with 'orch-').
    Encourages orchestrators to consult System3 before stopping when blocked.

    This implements decision-time guidance for orchestrators:
    - Detects unescalated blockers from error patterns or worker failures
    - Suggests consulting System3 for guidance
    - Can be bypassed after 2 blocked attempts (like momentum check)
    """

    def __init__(self, config: EnvironmentConfig, paths: PathResolver):
        """Initialize the checker.

        Args:
            config: Environment configuration.
            paths: Path resolver for state files.
        """
        self.config = config
        self.paths = paths

    def _get_guidance_state_file(self) -> Path:
        """Get path to orchestrator guidance state file."""
        project_dir = Path(self.config.project_dir)
        state_dir = project_dir / ".claude" / "state" / "decision-guidance"
        return state_dir / "orchestrator-guidance-state.json"

    def _load_guidance_state(self) -> dict:
        """Load orchestrator guidance state."""
        state_file = self._get_guidance_state_file()
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"stop_attempts": 0, "last_attempt": 0, "escalated": False}

    def _save_guidance_state(self, state: dict) -> None:
        """Save orchestrator guidance state."""
        state_file = self._get_guidance_state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _detect_unescalated_blockers(self) -> list[dict]:
        """Detect blockers that should be escalated to System3.

        Checks:
        1. Recent error patterns from decision-guidance state
        2. Worker failure records
        3. Todo items marked as blocked
        """
        blockers = []
        project_dir = Path(self.config.project_dir)
        state_dir = project_dir / ".claude" / "state" / "decision-guidance"

        # Check for recent error patterns
        error_file = state_dir / "error-tracker.json"
        if error_file.exists():
            try:
                with open(error_file, "r") as f:
                    error_data = json.load(f)
                    errors = error_data.get("errors", [])
                    # Count errors in last 10 minutes
                    cutoff = time.time() - 600
                    recent_errors = [e for e in errors if e.get("timestamp", 0) > cutoff]
                    if len(recent_errors) >= 3:
                        blockers.append({
                            "type": "error_pattern",
                            "count": len(recent_errors),
                            "description": f"{len(recent_errors)} errors in last 10 minutes",
                        })
            except (json.JSONDecodeError, IOError):
                pass

        # Check for worker failures
        worker_file = state_dir / "worker-status.json"
        if worker_file.exists():
            try:
                with open(worker_file, "r") as f:
                    worker_data = json.load(f)
                    failures = worker_data.get("failures", [])
                    # Recent failures (last 30 minutes)
                    cutoff = time.time() - 1800
                    recent_failures = [f for f in failures if f.get("timestamp", 0) > cutoff]
                    if recent_failures:
                        blockers.append({
                            "type": "worker_failure",
                            "count": len(recent_failures),
                            "description": f"{len(recent_failures)} worker failure(s)",
                        })
            except (json.JSONDecodeError, IOError):
                pass

        return blockers

    def _format_blocker_list(self, blockers: list[dict]) -> str:
        """Format blockers for display."""
        lines = []
        for b in blockers:
            lines.append(f"- **{b['type']}**: {b['description']}")
        return "\n".join(lines)

    def check(self) -> CheckResult:
        """Check if orchestrator should escalate blockers before stopping.

        Returns:
            CheckResult with:
            - passed=True if not orchestrator, no blockers, or already escalated
            - passed=False if unescalated blockers exist (BLOCK with guidance)
        """
        # Only applies to orchestrator sessions
        if not self.config.is_orchestrator:
            return CheckResult(
                priority=Priority.P2_5_ORCHESTRATOR_GUIDANCE,
                passed=True,
                message="Not an orchestrator session - guidance check skipped",
                blocking=False,
            )

        # Load state
        state = self._load_guidance_state()

        # Check if within cooldown window (bypass after 2 attempts in 5 minutes)
        now = time.time()
        if state["last_attempt"] > 0 and (now - state["last_attempt"]) < 300:
            if state["stop_attempts"] >= 2:
                # Allow through after 2 blocked attempts
                return CheckResult(
                    priority=Priority.P2_5_ORCHESTRATOR_GUIDANCE,
                    passed=True,
                    message="Guidance check bypassed (2 blocked attempts in 5 minutes)",
                    blocking=True,
                )
        else:
            # Reset counter if outside window
            state["stop_attempts"] = 0

        # Detect unescalated blockers
        blockers = self._detect_unescalated_blockers()

        if not blockers:
            return CheckResult(
                priority=Priority.P2_5_ORCHESTRATOR_GUIDANCE,
                passed=True,
                message="No unescalated blockers detected",
                blocking=True,
            )

        # Blockers found - increment counter and block
        state["stop_attempts"] += 1
        state["last_attempt"] = now
        self._save_guidance_state(state)

        remaining = 2 - state["stop_attempts"] + 1
        bypass_hint = f"\n\n*Attempt {state['stop_attempts']}/2. Stop {remaining} more time(s) to bypass.*" if remaining > 0 else ""

        session_id = self.config.session_id or "unknown"

        return CheckResult(
            priority=Priority.P2_5_ORCHESTRATOR_GUIDANCE,
            passed=False,
            message=f"""## Orchestrator Guidance: Unescalated Blockers

You have {len(blockers)} blocker(s) that should be escalated to System3:

{self._format_blocker_list(blockers)}

**Recommended Action - Send guidance request to System3:**
```bash
mb-send system3 '{{"type": "guidance_request", "blockers": {json.dumps([b["description"] for b in blockers])}, "session_id": "{session_id}"}}'
```

**Why escalate?**
- A fresh perspective often recognizes solutions the stuck agent cannot
- System3 can provide strategic guidance without failed attempts polluting context

**Alternative**: If blockers are external dependencies, document them and proceed.
{bypass_hint}""",
            blocking=True,
        )
