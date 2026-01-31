"""Work Exhaustion Checker - Gathers work state and enforces task completion.

For System 3 sessions (system3-*):
  Pending/in_progress tasks BLOCK the session from stopping. The stop hook
  fires because Claude Code WANTS to stop — a pending task at that point is
  a contradiction. Either execute the task or delete it honestly.

  The only valid exit for System 3 is to have exhausted all productive work
  and presented option questions to the user via AskUserQuestion.

For non-System 3 sessions:
  Pending tasks indicate continuation intent — session is ALLOWED to stop
  (current behavior preserved).

Architecture:
- Step 4 (this checker): Mechanical data gathering + task enforcement
- Step 5 (Haiku judge): LLM-based judgment using transcript + ALL task states
- Output style: Behavioral guidance for System 3's self-assessment
"""

from dataclasses import dataclass, field
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

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

    # Task primitives — unfinished (pending + in_progress)
    pending_task_count: int = 0
    task_subjects: list = field(default_factory=list)

    # Task primitives — completed (for judge context)
    completed_task_count: int = 0
    completed_task_subjects: list = field(default_factory=list)

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

        # Unfinished tasks
        if self.pending_task_count > 0:
            subjects = "; ".join(f'"{s}"' for s in self.task_subjects[:3])
            lines.append(f"Tasks: {self.pending_task_count} pending/in-progress ({subjects})")
        else:
            lines.append("Tasks: none pending")

        # Completed tasks
        if self.completed_task_count > 0:
            subjects = "; ".join(f'"{s}"' for s in self.completed_task_subjects[:3])
            lines.append(f"Completed: {self.completed_task_count} tasks done ({subjects})")

        return lines

    def format_for_judge(self) -> str:
        """Structured summary for the System 3 Haiku Judge (Step 5).

        Includes ALL task states so the judge can evaluate session completeness.
        """
        lines = ["WORK STATE (from Step 4):"]
        lines.extend(f"  {line}" for line in self.format_summary_lines())
        lines.append(f"  Work available: {'YES' if self.has_available_work else 'NO'}")
        lines.append(f"  Unfinished tasks: {'YES' if self.pending_task_count > 0 else 'NO'}")

        # Show ALL task details for the judge
        if self.pending_task_count > 0:
            lines.append("  UNFINISHED task subjects:")
            for subject in self.task_subjects[:5]:
                lines.append(f"    - [pending] \"{subject}\"")

        if self.completed_task_count > 0:
            lines.append("  COMPLETED task subjects:")
            for subject in self.completed_task_subjects[:5]:
                lines.append(f"    - [done] \"{subject}\"")

        if self.beads_summary:
            lines.append(f"  Beads detail: {self.beads_summary[:300]}")

        return "\n".join(lines)


class WorkExhaustionChecker:
    """P3: Work-state-aware task enforcement checker.

    Mechanical responsibilities:
    1. Gather work state from three sources (promises, beads, task primitives)
    2. For System 3 sessions: BLOCK if unfinished tasks exist (must execute or delete)
    3. For non-System 3: PASS if unfinished tasks exist (continuation signal)
    4. Produce a work_state_summary for Step 5 (Haiku judge) with ALL task states

    What this checker does NOT do:
    - Judge whether a task is "sensible" (that's the LLM's job)
    - Use regex or keyword heuristics (that's anti-LLM-first)
    - Make decisions about protocol compliance (that's Step 5)
    """

    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self._work_state: Optional[WorkState] = None

    def check(self) -> CheckResult:
        """Check task state and gather work-state context.

        For System 3 sessions (system3-*):
            pending/in_progress tasks → BLOCK (the stop hook fires because
            Claude Code wants to stop — pending tasks are a contradiction)

        For non-System 3 sessions:
            pending/in_progress tasks → PASS (continuation signal, current behavior)

        Returns:
            CheckResult with work-state-enriched messages in all cases.
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

        # Gather work state from all sources
        try:
            work_state = self._gather_work_state(task_list_id)
            self._work_state = work_state
        except Exception as e:
            # Fail open on gathering errors — still check for tasks below
            self._work_state = WorkState()
            work_state = self._work_state

        has_unfinished_tasks = work_state.pending_task_count > 0

        # System 3 sessions: pending tasks BLOCK (must execute or delete)
        if self.config.is_system3:
            if has_unfinished_tasks:
                return CheckResult(
                    priority=Priority.P3_TODO_CONTINUATION,
                    passed=False,
                    message=self._format_system3_unfinished_block(work_state),
                    blocking=True,
                )
            else:
                # No unfinished tasks — pass with context for Step 5 (judge)
                return CheckResult(
                    priority=Priority.P3_TODO_CONTINUATION,
                    passed=True,
                    message=self._format_pass_message(work_state),
                    blocking=True,
                )

        # Non-System 3 sessions: original behavior
        if has_unfinished_tasks:
            return CheckResult(
                priority=Priority.P3_TODO_CONTINUATION,
                passed=True,
                message=self._format_pass_message(work_state),
                blocking=True,
            )
        else:
            return CheckResult(
                priority=Priority.P3_TODO_CONTINUATION,
                passed=False,
                message=self._format_non_system3_block(work_state),
                blocking=True,
            )

    @property
    def work_state_summary(self) -> str:
        """Structured work-state summary for Step 5 (System 3 Judge).

        Includes ALL task states (pending, completed) for judge evaluation.
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
        """Read ALL Task primitive JSON files — both unfinished and completed.

        Unfinished tasks (pending/in_progress) drive the blocking decision.
        Completed tasks are included for the Haiku judge to evaluate session
        completeness.
        """
        tasks_dir = Path.home() / ".claude" / "tasks" / task_list_id

        if not tasks_dir.exists():
            return

        try:
            for task_file in sorted(tasks_dir.glob("*.json")):
                try:
                    with open(task_file, "r") as f:
                        task = json.load(f)

                    task_status = task.get("status", "")
                    subject = task.get("subject", task.get("title", "untitled"))

                    if task_status in ("pending", "in_progress"):
                        state.pending_task_count += 1
                        state.task_subjects.append(subject)
                    elif task_status == "completed":
                        state.completed_task_count += 1
                        state.completed_task_subjects.append(subject)
                    # deleted tasks are ignored entirely
                except (json.JSONDecodeError, OSError):
                    continue
        except OSError:
            pass

    # --- Message Formatting ---

    def _format_pass_message(self, state: WorkState) -> str:
        """Pass message with work-state context (for Step 5 and system message)."""
        lines = state.format_summary_lines()
        summary = "\n".join(f"  {line}" for line in lines)
        return f"Work exhaustion check: all tasks completed or none pending\n{summary}"

    def _format_system3_unfinished_block(self, state: WorkState) -> str:
        """Block message for System 3 sessions with unfinished tasks.

        The stop hook fires because Claude Code WANTS to stop. Pending tasks
        at that point are a contradiction — either execute them or delete them.
        """
        task_list = "\n".join(f'  - "{s}"' for s in state.task_subjects[:5])
        lines = state.format_summary_lines()
        work_summary = "\n".join(f"  {line}" for line in lines)

        return f"""UNFINISHED TASKS - SESSION CANNOT STOP

You have {state.pending_task_count} pending/in-progress task(s):
{task_list}

The stop hook fires because you want to end the session. But you have
unfinished tasks — work you committed to doing.

Current work state:
{work_summary}

REQUIRED ACTIONS (choose one):

1. EXECUTE your pending tasks — they represent work you committed to.
   Consider all viable options to continue productive work independently.

2. DELETE tasks that are no longer relevant:
   TaskUpdate(taskId="<id>", status="deleted")

3. If you genuinely have no more productive work to do:
   - Delete your pending tasks
   - Use AskUserQuestion to present 2-4 next-step options to the user
   - The session can stop after the user responds or you await their input

Do NOT create placeholder tasks to satisfy this check.
Tasks represent real commitments — execute them or be honest about deleting them."""

    def _format_non_system3_block(self, state: WorkState) -> str:
        """Block message for non-System 3 sessions with no tasks.

        Original behavior: no pending task means no continuation intent.
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

To proceed: Add a continuation task, then try stopping again."""
        else:
            return f"""NO CONTINUATION TASK - NO AVAILABLE WORK

Current work state:
{work_summary}

No promises, no ready beads, no open business epics.

To proceed: Add a continuation task or confirm completion, then try stopping again."""
