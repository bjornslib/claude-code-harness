"""Environment configuration for unified stop gate hook."""

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional
import os


@dataclass(frozen=True)
class EnvironmentConfig:
    """Centralized environment configuration for unified stop gate.

    Attributes:
        project_dir: The Claude project directory (CLAUDE_PROJECT_DIR)
        session_dir: Optional session-specific directory for isolation (CLAUDE_SESSION_DIR)
        session_id: The Claude session ID (CLAUDE_SESSION_ID)
        max_iterations: Maximum allowed iterations before requiring justification (CLAUDE_MAX_ITERATIONS)
        enforce_promise: Whether to enforce completion promise checking (CLAUDE_ENFORCE_PROMISE)
        enforce_bo: Whether to enforce business objectives checking (CLAUDE_ENFORCE_BO)
    """

    project_dir: str
    session_dir: Optional[str]
    session_id: Optional[str]
    max_iterations: int
    enforce_promise: bool
    enforce_bo: bool

    @property
    def is_orchestrator(self) -> bool:
        """Check if this is an orchestrator session (session ID starts with 'orch-')."""
        return bool(self.session_id and self.session_id.startswith("orch-"))

    @property
    def is_system3(self) -> bool:
        """Check if this is a System 3 meta-orchestrator session (session ID starts with 'system3-')."""
        return bool(self.session_id and self.session_id.startswith("system3-"))

    @classmethod
    def from_env(cls) -> 'EnvironmentConfig':
        """Create configuration from environment variables.

        Environment Variables:
            CLAUDE_PROJECT_DIR: Project directory path (default: '.')
            CLAUDE_SESSION_DIR: Session directory for isolation (default: None)
            CLAUDE_SESSION_ID: Session identifier, 'orch-*' prefix indicates orchestrator
            CLAUDE_MAX_ITERATIONS: Max iterations before justification (default: 25)
            CLAUDE_ENFORCE_PROMISE: Enforce completion promises (default: false)
            CLAUDE_ENFORCE_BO: Enforce business objectives (default: false)

        Returns:
            EnvironmentConfig with values from environment or defaults.
        """
        return cls(
            project_dir=os.environ.get('CLAUDE_PROJECT_DIR', '.'),
            session_dir=os.environ.get('CLAUDE_SESSION_DIR'),
            session_id=os.environ.get('CLAUDE_SESSION_ID'),
            max_iterations=int(os.environ.get('CLAUDE_MAX_ITERATIONS', '25')),
            enforce_promise=os.environ.get('CLAUDE_ENFORCE_PROMISE', '').lower() in ('true', '1', 'yes'),
            enforce_bo=os.environ.get('CLAUDE_ENFORCE_BO', '').lower() in ('true', '1', 'yes'),
        )

    @property
    def completion_state_dir(self) -> str:
        """Get the completion state directory, supporting session isolation.

        Returns:
            Path to completion state directory. If session_dir is set,
            returns a session-specific subdirectory for isolation.
        """
        base = f"{self.project_dir}/.claude/completion-state"
        if self.session_dir:
            return f"{base}/{self.session_dir}"
        return base


class Priority(IntEnum):
    """Priority levels for stop gate checks (P0 = highest).

    Lower numbers = higher priority. Checks are evaluated in priority order.
    """

    P0_CIRCUIT_BREAKER = 0      # max_iterations - force ALLOW
    P1_COMPLETION_PROMISE = 1   # user goals - BLOCK if unmet
    P2_BEADS_SYNC = 2           # data integrity - BLOCK if dirty
    P2_5_ORCHESTRATOR_GUIDANCE = 25  # orchestrator blocker escalation - BLOCK
    P3_TODO_CONTINUATION = 3    # momentum - BLOCK if missing
    P3_5_SYSTEM3_JUDGE = 35     # System 3 continuation evaluation - BLOCK if premature
    P4_GIT_STATUS = 4           # advisory - WARN only
    P5_BUSINESS_OUTCOMES = 5    # focused mode - BLOCK if enforced


@dataclass(frozen=True)
class CheckResult:
    """Result from a priority checker.

    Attributes:
        priority: The priority level of this check.
        passed: Whether the check passed (True) or failed (False).
        message: Human-readable description of the result.
        blocking: Whether a failed check should block (True) or just warn (False).
    """

    priority: Priority
    passed: bool
    message: str
    blocking: bool = True  # P4 (git status) is non-blocking

    @property
    def action(self) -> str:
        """Determine the action based on check result.

        Returns:
            'ALLOW' - Circuit breaker passed, force allow
            'BLOCK' - Check failed and is blocking
            'WARN' - Check failed but non-blocking
            'PASS' - Check passed normally
        """
        if self.priority == Priority.P0_CIRCUIT_BREAKER and self.passed:
            return 'ALLOW'  # Circuit breaker forces allow
        if not self.passed:
            return 'BLOCK' if self.blocking else 'WARN'
        return 'PASS'


@dataclass
class PathResolver:
    """Resolves paths for completion state, supporting session isolation.

    Provides centralized path resolution for all completion state files,
    with support for System3 parallel initiative isolation via CLAUDE_SESSION_DIR.

    Attributes:
        config: The environment configuration containing project and session dirs.
    """

    config: EnvironmentConfig

    @property
    def completion_state_dir(self) -> Path:
        """Get completion state directory with session isolation.

        Returns:
            Path to completion state directory. If session_dir is configured,
            returns a session-specific subdirectory for parallel initiative isolation.
        """
        base = Path(self.config.project_dir) / '.claude' / 'completion-state'
        if self.config.session_dir:
            return base / self.config.session_dir
        return base

    @property
    def promises_dir(self) -> Path:
        """Path to the promises directory (active promises)."""
        return self.completion_state_dir / 'promises'

    @property
    def history_dir(self) -> Path:
        """Path to the history directory (verified/cancelled promises)."""
        return self.completion_state_dir / 'history'

    @property
    def promise_file(self) -> Path:
        """Path to the completion promise file (legacy, use promises_dir)."""
        return self.completion_state_dir / 'promise.txt'

    @property
    def session_state_file(self) -> Path:
        """Path to the session state JSON file (legacy, use promises_dir)."""
        return self.completion_state_dir / 'session-state.json'

    @property
    def features_file(self) -> Path:
        """Path to the features tracking JSON file."""
        return self.completion_state_dir / 'features.json'

    @property
    def verification_log(self) -> Path:
        """Path to the verification log file."""
        return self.completion_state_dir / 'verification.log'

    def ensure_dirs_exist(self) -> None:
        """Create completion state directories if needed.

        Creates promises and history directories as necessary.
        """
        self.promises_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
