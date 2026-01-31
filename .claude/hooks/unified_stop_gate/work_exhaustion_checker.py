"""Work Exhaustion Checker - Gathers work state and guides System 3 intelligently.

This checker replaces the rigid "does any pending Task exist?" check with one
that ALSO gathers context about available work (promises, beads) and includes
that context in its guidance messages.

The checker does NOT attempt to judge whether tasks are "sensible" — that is
the job of the LLM (either System 3 itself via its output style, or the Haiku
judge in Step 5). This checker is purely mechanical: gather data, check for
tasks, and provide rich context when blocking.

Architecture:
- Step 4 (this checker): Mechanical data gathering + task existence check
- Step 5 (Haiku judge): LLM-based judgment using transcript + work state
- Output style: Behavioral guidance for System 3's self-assessment
"""

from dataclasses import dataclass, field
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from .config import CheckResult, EnvironmentConfig, Priority


@dataclass
class WorkState:
    """Structured representation of available work across all sources.

    Pure data class — no judgment, no heuristics. Just facts about what
    work exists in the system right now.
    """

    # Promises
    has_promises: bool = False
    unmet_promise_count: int = 0
    promise_summaries: list = field(default_factory=list)

    # Beads
    ready_bead_count: int = 0
    high_priority_bead_count: int = 0
    open_business_epic_count: int = 0
    beads_summary: str = ""

    # Task primitives
    pending_task_count: int = 0
    task_subjects: list = field(default_factory=list)

    @property
    def has_available_work(self) -> bool:
        """Whether any source indicates actionable work exists."""
        return (
            self.unmet_promise_count > 0
            or self.ready_bead_count > 0
            or self.high_priority_bead_count > 0
            or self.open_business_epic_count > 0
        )

    def format_summary_lines(self) -> list:
        """Human-readable summary, one line per source. Pure data, no judgment."""
        lines = []

        # Promises
        if self.has_promises:
            if self.unmet_promise_count > 0:
                summaries = "; ".join(self.promise_summaries[:3])
                lines.append(f"Promises: {self.unmet_promise_count} unmet ({summaries})")
            else:
                lines.append("Promises: all verified")
        else:
            lines.append("Promises: none active")

        # Beads
        if self.ready_bead_count > 0 or self.high_priority_bead_count > 0 or self.open_business_epic_count > 0:
            parts = []
            if self.ready_bead_count > 0:
                parts.append(f"{self.ready_bead_count} ready")
            if self.high_priority_bead_count > 0:
                parts.append(f"{self.high_priority_bead_count} high-priority (P0-P2)")
            if self.open_business_epic_count > 0:
                parts.append(f"{self.open_business_epic_count} business epics open")
            lines.append(f"Beads: {', '.join(parts)}")
        else:
            lines.append("Beads: no ready work")

        # Tasks
        if self.pending_task_count > 0:
            subjects = "; ".join(f'"{s}"' for s in self.task_subjects[:3])
            lines.append(f"Tasks: {self.pending_task_count} pending ({subjects})")
        else:
            lines.append("Tasks: none pending")

        return lines

    def format_for_judge(self) -> str:
        """Structured summary for the System 3 Haiku Judge (Step 5).

        Provides factual context — the judge makes the judgment call.
        """
        lines = ["WORK STATE (from Step 4):"]
        lines.extend(f"  {line}" for line in self.format_summary_lines())
        lines.append(f"  Work available: {'YES' if self.has_available_work else 'NO'}")
        lines.append(f"  Has pending tasks: {'YES' if self.pending_task_count > 0 else 'NO'}")

        if self.pending_task_count > 0:
            lines.append("  Pending task subjects:")
            for subject in self.task_subjects[:5]:
                lines.append(f"    - \"{subject}\"")

        if self.beads_summary:
            lines.append(f"  Beads detail: {self.beads_summary[:300]}")

        return "\n".join(lines)


class WorkExhaustionChecker:
    """P3: Work-state-aware task continuation checker.

    Mechanical responsibilities:
    1. Gather work state from three sources (promises, beads, task primitives)
    2. Check whether any pending/in_progress Task primitive exists
    3. When blocking, include the gathered work state as rich guidance
    4. Produce a work_state_summary for Step 5 (Haiku judge) to reason over

    What this checker does NOT do:
    - Judge whether a task is "sensible" (that's the LLM's job)
    - Use regex or keyword heuristics (that's anti-LLM-first)
    - Make decisions about protocol compliance (that's Step 5)
    """

    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self._work_state: Optional[WorkState] = None

    def check(self) -> CheckResult:
        """Check for pending tasks and gather work-state context.

        Returns:
            CheckResult with:
            - passed=True if a pending/in_progress task exists (continuation present)
            - passed=False if no pending task (blocks with work-state-enriched guidance)
        """
        task_list_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "")

        # Skip check if no task list configured
        if not task_list_id:
            return CheckResult(
                priority=Priority.P3_TODO_CONTINUATION,
                passed=True,
                message="No CLAUDE_CODE_TASK_LIST_ID set - work exhaustion check skipped",
                blocking=True,
            )

        # Gather work state from all sources (for context, not for blocking decisions)
        try:
            work_state = self._gather_work_state(task_list_id)
            self._work_state = work_state
        except Exception as e:
            # Fail open on gathering errors — still check for tasks below
            self._work_state = WorkState()
            work_state = self._work_state

        # Core check: does a pending/in_progress task exist?
        has_continuation = work_state.pending_task_count > 0

        if has_continuation:
            # Task exists — pass, but include work state context for Step 5
            return CheckResult(
                priority=Priority.P3_TODO_CONTINUATION,
                passed=True,
                message=self._format_pass_message(work_state),
                blocking=True,
            )
        else:
            # No task — block with rich guidance including work state
            return CheckResult(
                priority=Priority.P3_TODO_CONTINUATION,
                passed=False,
                message=self._format_block_message(work_state),
                blocking=True,
            )

    @property
    def work_state_summary(self) -> str:
        """Structured work-state summary for Step 5 (System 3 Judge).

        Returns empty string if check() hasn't been called yet.
        """
        if self._work_state is None:
            return ""
        return self._work_state.format_for_judge()

    # --- Data Gathering (mechanical, no judgment) ---

    def _gather_work_state(self, task_list_id: str) -> WorkState:
        """Gather work state from all three sources."""
        state = WorkState()
        self._gather_promise_summary(state)
        self._gather_beads_state(state)
        self._gather_task_state(state, task_list_id)
        return state

    def _gather_promise_summary(self, state: WorkState) -> None:
        """Quick scan of promise files for context summary."""
        promises_dir = Path(self.config.project_dir) / ".claude" / "completion-state" / "promises"

        if not promises_dir.exists():
            return

        try:
            for promise_file in promises_dir.glob("*.json"):
                if promise_file.name == ".gitkeep":
                    continue
                try:
                    with open(promise_file, "r") as f:
                        promise = json.load(f)

                    state.has_promises = True
                    status = promise.get("status", "unknown")

                    if status in ("pending", "in_progress"):
                        state.unmet_promise_count += 1
                        summary = promise.get("summary", "")[:60]
                        if summary:
                            state.promise_summaries.append(summary)
                except (json.JSONDecodeError, OSError):
                    continue
        except OSError:
            pass

    def _gather_beads_state(self, state: WorkState) -> None:
        """Check beads for ready work and open business epics."""
        if not Path(self.config.project_dir, ".beads").exists():
            return

        try:
            # Get ready work
            result = subprocess.run(
                ["bd", "ready"],
                cwd=self.config.project_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            ready_output = result.stdout.strip()

            if ready_output and "No open issues" not in ready_output and "No issues" not in ready_output:
                # Count lines that look like bead entries
                bead_lines = [
                    line for line in ready_output.split("\n")
                    if line.strip() and re.search(r"(beads-[a-z0-9]+|bd-[a-z0-9]+|\[P\d\])", line)
                ]
                state.ready_bead_count = len(bead_lines)
                state.high_priority_bead_count = len([
                    line for line in bead_lines
                    if re.search(r"\[P[012]\]", line)
                ])
                state.beads_summary = ready_output[:500]

            # Check for open business epics
            result2 = subprocess.run(
                ["bd", "list", "--tag=bo", "--status=open"],
                cwd=self.config.project_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            bo_output = result2.stdout.strip()
            if bo_output and "No" not in bo_output and "error" not in bo_output.lower():
                bo_lines = [
                    line for line in bo_output.split("\n")
                    if line.strip() and re.search(r"(beads-|bd-)", line)
                ]
                state.open_business_epic_count = len(bo_lines)

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    def _gather_task_state(self, state: WorkState, task_list_id: str) -> None:
        """Read Task primitive JSON files for pending/in_progress tasks."""
        tasks_dir = Path.home() / ".claude" / "tasks" / task_list_id

        if not tasks_dir.exists():
            return

        try:
            for task_file in sorted(tasks_dir.glob("*.json")):
                try:
                    with open(task_file, "r") as f:
                        task = json.load(f)

                    task_status = task.get("status", "")
                    if task_status in ("pending", "in_progress"):
                        state.pending_task_count += 1
                        subject = task.get("subject", task.get("title", "untitled"))
                        state.task_subjects.append(subject)
                except (json.JSONDecodeError, OSError):
                    continue
        except OSError:
            pass

    # --- Message Formatting ---

    def _format_pass_message(self, state: WorkState) -> str:
        """Pass message with work-state context (for Step 5 and system message)."""
        lines = state.format_summary_lines()
        summary = "\n".join(f"  {line}" for line in lines)
        return f"Work exhaustion check: continuation task exists\n{summary}"

    def _format_block_message(self, state: WorkState) -> str:
        """Block message with rich work-state guidance.

        The intelligence here is in WHAT CONTEXT we provide, not in making
        judgment calls. We show System 3 the full picture and let it decide.
        """
        lines = state.format_summary_lines()
        work_summary = "\n".join(f"  {line}" for line in lines)

        if state.has_available_work:
            return f"""NO CONTINUATION TASK - WORK IS AVAILABLE

Current work state:
{work_summary}

There is available work but no pending continuation task. Before stopping,
ask yourself: "Have I exhausted what I can conservatively continue productive
work on without user input?"

Three-layer self-assessment (in priority order):
1. SESSION PROMISES: Are all promises verified? If not, that is your next task.
2. HIGH-PRIORITY BEADS: Are there P0-P2 beads or open business epics above?
   If yes, your next task should advance one of them.
3. SELF-ASSESSMENT: Did you follow protocols? Did you achieve session goals?
   Are you being honest with yourself about what remains?

If you CAN continue productively:
  Add a specific continuation task that advances the available work.

If you GENUINELY need user input to decide direction:
  Use AskUserQuestion to present 2-4 concrete options to the user.
  This is a valid and sensible action — not a cop-out.

To proceed: Add a continuation task, then try stopping again."""
        else:
            return f"""NO CONTINUATION TASK - NO AVAILABLE WORK

Current work state:
{work_summary}

No promises, no ready beads, no open business epics. Before stopping,
ask yourself: "Have I genuinely completed my session goals and followed
all protocols?"

Before stopping, either:
1. PRESENT OPTIONS to the user via AskUserQuestion:
   - What should the next session focus on?
   - Are there improvement areas to explore?
   - Should we start a new initiative?
   This counts as a valid continuation task.

2. CONFIRM GENUINE COMPLETION by adding a brief completion task:
   - Post-session reflection stored to Hindsight?
   - All protocols followed?
   - Session goals achieved?

To proceed: Add a continuation task (even an AskUserQuestion-based one),
then try stopping again."""
