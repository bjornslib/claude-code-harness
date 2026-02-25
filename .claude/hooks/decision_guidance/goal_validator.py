"""Goal-aware validation for decision-time guidance.

Compares the orchestrator's reported progress against System3's original
instructions to determine:
1. Is the orchestrator on track?
2. Should it ask for guidance?
3. Can it safely stop?

Uses completion-state as the source of truth:
- session-state.json: Goals, features, completion_promise
- promises/*.json: Promise tracking with ownership
- progress/*.md: Session progress logs (optional)
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GoalProgress:
    """Progress status for a single goal."""
    id: str
    description: str
    status: str  # pending, in_progress, passed, failed
    acceptance_criteria: list[str]
    criteria_met: list[bool]  # Which criteria are verified
    verification: Optional[dict] = None

    @property
    def completion_pct(self) -> float:
        if not self.criteria_met:
            return 0.0 if self.status == "pending" else 50.0
        return (sum(self.criteria_met) / len(self.criteria_met)) * 100

    @property
    def is_complete(self) -> bool:
        return self.status == "passed" and self.completion_pct == 100.0


@dataclass
class FeatureProgress:
    """Progress status for a feature within an epic."""
    id: str
    title: str
    status: str
    acceptance_criteria: list[str]
    verification: Optional[dict] = None

    @property
    def is_complete(self) -> bool:
        return self.status == "passed" and self.verification is not None


@dataclass
class EpicProgress:
    """Progress status for an epic."""
    id: str
    title: str
    status: str
    features: list[FeatureProgress] = field(default_factory=list)

    @property
    def completion_pct(self) -> float:
        if not self.features:
            return 0.0 if self.status == "pending" else 50.0
        completed = sum(1 for f in self.features if f.is_complete)
        return (completed / len(self.features)) * 100

    @property
    def is_complete(self) -> bool:
        return self.status == "passed" or all(f.is_complete for f in self.features)


@dataclass
class CompletionState:
    """Complete state extracted from completion-state files."""
    session_id: str
    raw_prompt: str  # Original System3 instructions
    summary: str
    goals: list[GoalProgress]
    epics: list[EpicProgress]
    progress_log: list[dict]
    iteration: int
    max_iterations: int
    loaded_at: float = field(default_factory=time.time)

    @property
    def overall_completion_pct(self) -> float:
        """Calculate overall completion percentage."""
        if self.goals:
            goal_pct = sum(g.completion_pct for g in self.goals) / len(self.goals)
        else:
            goal_pct = 0.0

        if self.epics:
            epic_pct = sum(e.completion_pct for e in self.epics) / len(self.epics)
        else:
            epic_pct = 0.0

        # Weight goals and epics equally if both exist
        if self.goals and self.epics:
            return (goal_pct + epic_pct) / 2
        return goal_pct or epic_pct

    @property
    def incomplete_goals(self) -> list[GoalProgress]:
        """Get list of incomplete goals."""
        return [g for g in self.goals if not g.is_complete]

    @property
    def incomplete_epics(self) -> list[EpicProgress]:
        """Get list of incomplete epics."""
        return [e for e in self.epics if not e.is_complete]

    @property
    def is_complete(self) -> bool:
        """Check if all goals and epics are complete."""
        goals_complete = all(g.is_complete for g in self.goals) if self.goals else True
        epics_complete = all(e.is_complete for e in self.epics) if self.epics else True
        return goals_complete and epics_complete


@dataclass
class ValidationResult:
    """Result of goal validation."""
    is_on_track: bool
    completion_pct: float
    should_stop: bool
    should_ask_guidance: bool
    reason: str
    incomplete_items: list[str]
    recommendations: list[str]


@dataclass
class TaskMasterTask:
    """A task from Task Master or TodoWrite.

    Handles both formats:
    - Task Master: status = "pending", "in-progress", "done", "blocked"
    - TodoWrite: status = "pending", "in_progress", "completed"
    """
    id: str
    title: str
    status: str  # pending, in-progress/in_progress, done/completed, blocked
    priority: str  # P0, P1, P2, P3
    subtasks: list[dict] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Check if task is complete (handles both TM and TodoWrite status values)."""
        return self.status in ("done", "completed")


class GoalValidator:
    """Validates orchestrator progress against System3 instructions."""

    # Thresholds for decision making
    GUIDANCE_THRESHOLD_PCT = 30  # Ask guidance if < 30% complete and stuck
    STOP_THRESHOLD_PCT = 100  # Only allow stop at 100% (or explicit override)
    STUCK_ERROR_COUNT = 3  # Consider stuck if 3+ errors

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            state_dir = Path(project_dir) / ".claude" / "completion-state"

        self.state_dir = state_dir
        self.project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        self.session_dir = os.environ.get("CLAUDE_SESSION_DIR")
        self.session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    def _get_state_path(self) -> Path:
        """Get path to session-state.json, respecting session isolation."""
        if self.session_dir:
            return self.state_dir / self.session_dir / "session-state.json"
        return self.state_dir / "session-state.json"

    def _get_promises_dir(self) -> Path:
        """Get path to promises directory."""
        return self.state_dir / "promises"

    def _get_tasks_dir(self) -> Path:
        """Get path to .claude/tasks directory (TodoWrite storage)."""
        return self.project_dir / ".claude" / "tasks"

    def _get_task_list_id(self) -> Optional[str]:
        """Get the task list ID from environment."""
        return os.environ.get("CLAUDE_CODE_TASK_LIST_ID")

    def _get_task_list_path(self) -> Optional[Path]:
        """Get path to the specific task list file.

        Uses CLAUDE_CODE_TASK_LIST_ID to find the task list:
        - .claude/tasks/{TASK_LIST_ID}
        - .claude/tasks/{TASK_LIST_ID}.json

        Returns None if no task list ID is set.
        """
        task_list_id = self._get_task_list_id()
        if not task_list_id:
            return None

        tasks_dir = self._get_tasks_dir()

        # Try exact path first
        exact_path = tasks_dir / task_list_id
        if exact_path.exists():
            return exact_path

        # Try with .json extension
        json_path = tasks_dir / f"{task_list_id}.json"
        if json_path.exists():
            return json_path

        return None

    def _get_taskmaster_path(self) -> Path:
        """Get path to Task Master tasks.json."""
        return self.project_dir / ".taskmaster" / "tasks" / "tasks.json"

    def load_tasks(self) -> list[TaskMasterTask]:
        """Load tasks from .claude/tasks/ or .taskmaster/tasks/tasks.json.

        Priority order:
        1. .claude/tasks/{CLAUDE_CODE_TASK_LIST_ID} (if env var set)
        2. .claude/tasks/*.json (all JSON files)
        3. .taskmaster/tasks/tasks.json (Task Master)

        Returns list of tasks found.
        """
        tasks = []

        # Priority 1: Specific task list from CLAUDE_CODE_TASK_LIST_ID
        task_list_path = self._get_task_list_path()
        if task_list_path:
            try:
                with open(task_list_path, "r") as fp:
                    data = json.load(fp)
                    tasks.extend(self._parse_task_data(data))
                    # If we found a specific task list, return it
                    if tasks:
                        return tasks
            except (json.JSONDecodeError, IOError):
                pass

        # Source 2: .claude/tasks/ directory (all JSON files)
        tasks_dir = self._get_tasks_dir()
        if tasks_dir.exists():
            for f in tasks_dir.glob("*.json"):
                try:
                    with open(f, "r") as fp:
                        data = json.load(fp)
                        tasks.extend(self._parse_task_data(data))
                except (json.JSONDecodeError, IOError, KeyError):
                    continue

        # Source 3: .taskmaster/tasks/tasks.json
        tm_path = self._get_taskmaster_path()
        if tm_path.exists():
            try:
                with open(tm_path, "r") as f:
                    data = json.load(f)
                    tasks.extend(self._parse_task_data(data))
            except (json.JSONDecodeError, IOError, KeyError):
                pass

        return tasks

    def _parse_task_data(self, data) -> list[TaskMasterTask]:
        """Parse task data from various formats.

        Handles:
        - Array of tasks: [{"id": 1, ...}, {"id": 2, ...}]
        - Object with tasks key: {"tasks": [...]}
        - Single task object: {"id": 1, ...}
        - TodoWrite format: {"todos": [{"content": "...", "status": "..."}]}
        """
        tasks = []

        if isinstance(data, list):
            for t in data:
                if isinstance(t, dict):
                    tasks.append(self._parse_task(t))
        elif isinstance(data, dict):
            # Check for various container keys
            if "tasks" in data:
                for t in data["tasks"]:
                    tasks.append(self._parse_task(t))
            elif "todos" in data:
                # TodoWrite format
                for t in data["todos"]:
                    tasks.append(self._parse_task(t))
            elif "id" in data or "content" in data or "title" in data:
                # Single task
                tasks.append(self._parse_task(data))

        return tasks

    def _parse_task(self, data: dict) -> TaskMasterTask:
        """Parse a task from JSON data."""
        return TaskMasterTask(
            id=str(data.get("id", "")),
            title=data.get("title", data.get("content", data.get("description", ""))),
            status=data.get("status", "pending"),
            priority=data.get("priority", "P2"),
            subtasks=data.get("subtasks", []),
        )

    def get_task_completion_pct(self) -> tuple[float, list[TaskMasterTask]]:
        """Get task completion percentage and incomplete tasks."""
        tasks = self.load_tasks()
        if not tasks:
            return 0.0, []

        completed = [t for t in tasks if t.is_complete]
        incomplete = [t for t in tasks if not t.is_complete]

        pct = (len(completed) / len(tasks)) * 100 if tasks else 0.0
        return pct, incomplete

    def load_completion_state(self) -> Optional[CompletionState]:
        """Load completion state from files.

        Returns None if no state file exists.
        """
        state_path = self._get_state_path()

        if not state_path.exists():
            return None

        try:
            with open(state_path, "r") as f:
                data = json.load(f)

            # Parse goals
            goals = []
            for g in data.get("goals", []):
                criteria = g.get("acceptance_criteria", [])
                # Infer criteria_met from status and verification
                if g.get("status") == "passed":
                    criteria_met = [True] * len(criteria)
                elif g.get("status") == "in_progress":
                    # Assume 50% if in progress
                    criteria_met = [True] * (len(criteria) // 2) + [False] * (len(criteria) - len(criteria) // 2)
                else:
                    criteria_met = [False] * len(criteria)

                goals.append(GoalProgress(
                    id=g.get("id", ""),
                    description=g.get("description", ""),
                    status=g.get("status", "pending"),
                    acceptance_criteria=criteria,
                    criteria_met=criteria_met,
                    verification=g.get("verification"),
                ))

            # Parse epics and features
            epics = []
            prd = data.get("prd", {})
            for e in prd.get("epics", []):
                features = []
                for f in e.get("features", []):
                    features.append(FeatureProgress(
                        id=f.get("id", ""),
                        title=f.get("title", ""),
                        status=f.get("status", "pending"),
                        acceptance_criteria=f.get("acceptance_criteria", []),
                        verification=f.get("verification"),
                    ))

                epics.append(EpicProgress(
                    id=e.get("id", ""),
                    title=e.get("title", ""),
                    status=e.get("status", "pending"),
                    features=features,
                ))

            # Extract completion promise
            promise = data.get("completion_promise", {})

            return CompletionState(
                session_id=data.get("session_id", ""),
                raw_prompt=promise.get("raw_prompt", ""),
                summary=promise.get("summary", ""),
                goals=goals,
                epics=epics,
                progress_log=data.get("progress_log", []),
                iteration=data.get("iteration", 0),
                max_iterations=data.get("max_iterations", 25),
            )

        except (json.JSONDecodeError, IOError, KeyError) as e:
            return None

    def load_promises(self) -> list[dict]:
        """Load all promises from promises directory."""
        promises_dir = self._get_promises_dir()
        if not promises_dir.exists():
            return []

        promises = []
        for f in promises_dir.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    promises.append(json.load(fp))
            except (json.JSONDecodeError, IOError):
                continue

        return promises

    def validate(
        self,
        error_count: int = 0,
        stop_attempt: bool = False,
    ) -> ValidationResult:
        """Validate current progress and determine next action.

        Args:
            error_count: Number of recent errors (from error tracker)
            stop_attempt: Whether this is being called from a stop attempt

        Returns:
            ValidationResult with recommendations.
        """
        state = self.load_completion_state()

        # Also load tasks from .claude/tasks/ or .taskmaster/
        task_pct, incomplete_tasks = self.get_task_completion_pct()

        # No state and no tasks = no validation possible
        if state is None and not incomplete_tasks:
            return ValidationResult(
                is_on_track=True,
                completion_pct=task_pct,
                should_stop=True,  # Allow stop if no tracking
                should_ask_guidance=False,
                reason="No completion state found - tracking disabled",
                incomplete_items=[],
                recommendations=["Consider setting up completion-state tracking"],
            )

        # Calculate combined completion
        if state is not None:
            state_pct = state.overall_completion_pct
            incomplete_goals = state.incomplete_goals
            incomplete_epics = state.incomplete_epics
            # Combine state and task completion
            if task_pct > 0:
                completion_pct = (state_pct + task_pct) / 2
            else:
                completion_pct = state_pct
        else:
            completion_pct = task_pct
            incomplete_goals = []
            incomplete_epics = []

        # Build incomplete items list
        incomplete_items = []
        for g in incomplete_goals:
            incomplete_items.append(f"Goal {g.id}: {g.description} ({g.completion_pct:.0f}%)")
        for e in incomplete_epics:
            incomplete_items.append(f"Epic {e.id}: {e.title} ({e.completion_pct:.0f}%)")
        for t in incomplete_tasks[:5]:  # Limit to 5 tasks
            incomplete_items.append(f"Task {t.id}: {t.title} [{t.status}]")

        # Determine if stuck (errors + low progress)
        is_stuck = error_count >= self.STUCK_ERROR_COUNT and completion_pct < 50

        # Determine recommendations
        recommendations = []

        if state.is_complete:
            # All done!
            return ValidationResult(
                is_on_track=True,
                completion_pct=100,
                should_stop=True,
                should_ask_guidance=False,
                reason="All goals and epics are complete",
                incomplete_items=[],
                recommendations=["Ready to stop - all work verified"],
            )

        # Not complete - determine next action
        if is_stuck:
            recommendations.append("Multiple errors detected with low progress - consider asking System3 for guidance")
            recommendations.append(f"bd update <id> --status=impl_complete  # stuck: completion={completion_pct:.0f}%, errors={error_count}")
            return ValidationResult(
                is_on_track=False,
                completion_pct=completion_pct,
                should_stop=False,
                should_ask_guidance=True,
                reason=f"Stuck: {error_count} errors with only {completion_pct:.0f}% complete",
                incomplete_items=incomplete_items,
                recommendations=recommendations,
            )

        if completion_pct < self.GUIDANCE_THRESHOLD_PCT and stop_attempt:
            recommendations.append("Very early in progress - consider continuing or asking System3 for guidance")
            return ValidationResult(
                is_on_track=True,  # Not necessarily off track, just early
                completion_pct=completion_pct,
                should_stop=False,
                should_ask_guidance=True,
                reason=f"Only {completion_pct:.0f}% complete - stopping not recommended",
                incomplete_items=incomplete_items,
                recommendations=recommendations,
            )

        if stop_attempt and not state.is_complete:
            # Trying to stop with incomplete work
            recommendations.append("Complete remaining work before stopping")
            recommendations.append("Use cs-status to see detailed progress")
            recommendations.append("If blocked, ask System3 for guidance")
            return ValidationResult(
                is_on_track=True,
                completion_pct=completion_pct,
                should_stop=False,
                should_ask_guidance=False,
                reason=f"{completion_pct:.0f}% complete - {len(incomplete_items)} items remaining",
                incomplete_items=incomplete_items,
                recommendations=recommendations,
            )

        # Normal progress - continue working
        return ValidationResult(
            is_on_track=True,
            completion_pct=completion_pct,
            should_stop=False,
            should_ask_guidance=False,
            reason=f"On track: {completion_pct:.0f}% complete",
            incomplete_items=incomplete_items,
            recommendations=[f"Continue working on: {incomplete_items[0]}" if incomplete_items else "Continue"],
        )

    def format_for_guidance(self, result: ValidationResult, state: Optional[CompletionState] = None) -> str:
        """Format validation result for guidance injection."""
        if state is None:
            state = self.load_completion_state()

        lines = [
            f"## Goal Validation: {result.completion_pct:.0f}% Complete",
            "",
        ]

        if state and state.summary:
            lines.extend([
                f"**Original Goal**: {state.summary}",
                "",
            ])

        if not result.is_on_track:
            lines.append("**Status**: NOT ON TRACK")
        elif result.should_ask_guidance:
            lines.append("**Status**: Consider guidance")
        else:
            lines.append("**Status**: On track")

        lines.append(f"\n**Reason**: {result.reason}\n")

        if result.incomplete_items:
            lines.append("**Incomplete Items**:")
            for item in result.incomplete_items[:5]:  # Limit to 5
                lines.append(f"- {item}")
            if len(result.incomplete_items) > 5:
                lines.append(f"- ... and {len(result.incomplete_items) - 5} more")
            lines.append("")

        if result.recommendations:
            lines.append("**Recommendations**:")
            for rec in result.recommendations[:3]:  # Limit to 3
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def should_preserve_context(self, state: CompletionState) -> dict:
        """Determine what context to preserve before compaction.

        Called by PreCompact hook to extract key instructions for re-injection.
        """
        return {
            "session_id": state.session_id,
            "original_prompt": state.raw_prompt,
            "summary": state.summary,
            "completion_pct": state.overall_completion_pct,
            "incomplete_goals": [
                {"id": g.id, "description": g.description, "pct": g.completion_pct}
                for g in state.incomplete_goals
            ],
            "incomplete_epics": [
                {"id": e.id, "title": e.title, "pct": e.completion_pct}
                for e in state.incomplete_epics
            ],
            "recent_progress": state.progress_log[-3:] if state.progress_log else [],
            "preserved_at": time.time(),
        }

    def format_preserved_context(self, preserved: dict) -> str:
        """Format preserved context for post-compaction injection."""
        lines = [
            "## Preserved System3 Context (Post-Compaction)",
            "",
            f"**Original Goal**: {preserved.get('summary', 'Unknown')}",
            f"**Progress**: {preserved.get('completion_pct', 0):.0f}% complete",
            "",
        ]

        incomplete_goals = preserved.get("incomplete_goals", [])
        if incomplete_goals:
            lines.append("**Incomplete Goals**:")
            for g in incomplete_goals[:3]:
                lines.append(f"- {g['id']}: {g['description']} ({g['pct']:.0f}%)")
            lines.append("")

        incomplete_epics = preserved.get("incomplete_epics", [])
        if incomplete_epics:
            lines.append("**Incomplete Epics**:")
            for e in incomplete_epics[:3]:
                lines.append(f"- {e['id']}: {e['title']} ({e['pct']:.0f}%)")
            lines.append("")

        recent = preserved.get("recent_progress", [])
        if recent:
            lines.append("**Recent Progress**:")
            for p in recent:
                lines.append(f"- {p.get('action', 'Unknown')}: {p.get('outcome', 'Unknown')}")
            lines.append("")

        lines.append("*Continue working toward the original goal.*")

        return "\n".join(lines)
