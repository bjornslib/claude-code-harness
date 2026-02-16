"""State management for decision-time guidance.

Tracks errors, edits, and other signals in rolling windows.
State is persisted to JSON files for cross-hook communication.
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class ErrorEvent:
    """A recorded error event."""
    timestamp: float
    tool_name: str
    error_type: str
    message: str
    session_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorEvent":
        return cls(**data)


@dataclass
class EditEvent:
    """A recorded file edit event."""
    timestamp: float
    file_path: str
    tool_name: str
    success: bool
    session_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EditEvent":
        return cls(**data)


class ErrorTracker:
    """Track errors in a rolling time window.

    Errors older than the window are automatically pruned on each operation.
    """

    DEFAULT_WINDOW_SECONDS = 300  # 5 minutes
    DEFAULT_THRESHOLD = 4

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        threshold: int = DEFAULT_THRESHOLD,
    ):
        self.window_seconds = window_seconds
        self.threshold = threshold

        if state_dir is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            state_dir = Path(project_dir) / ".claude" / "state" / "decision-guidance"

        self.state_file = state_dir / "error-tracker.json"
        self.state_dir = state_dir
        self._errors: list[ErrorEvent] = []
        self._load_state()

    def _load_state(self) -> None:
        """Load error state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self._errors = [ErrorEvent.from_dict(e) for e in data.get("errors", [])]
            except (json.JSONDecodeError, IOError, KeyError):
                self._errors = []
        self._prune_old_errors()

    def _save_state(self) -> None:
        """Save error state to disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({"errors": [e.to_dict() for e in self._errors]}, f, indent=2)

    def _prune_old_errors(self) -> None:
        """Remove errors outside the rolling window."""
        cutoff = time.time() - self.window_seconds
        self._errors = [e for e in self._errors if e.timestamp > cutoff]

    def record_error(
        self,
        tool_name: str,
        error_type: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Record a new error event."""
        self._prune_old_errors()

        event = ErrorEvent(
            timestamp=time.time(),
            tool_name=tool_name,
            error_type=error_type,
            message=message[:500],  # Truncate long messages
            session_id=session_id or os.environ.get("CLAUDE_SESSION_ID"),
        )
        self._errors.append(event)
        self._save_state()

    def get_recent_errors(self) -> list[ErrorEvent]:
        """Get all errors in the current window."""
        self._prune_old_errors()
        return self._errors.copy()

    def is_threshold_reached(self) -> bool:
        """Check if error threshold is reached."""
        return len(self.get_recent_errors()) >= self.threshold

    def get_error_summary(self) -> dict:
        """Get summary of recent errors for guidance injection."""
        errors = self.get_recent_errors()
        if not errors:
            return {"count": 0, "tools": [], "types": [], "messages": []}

        from collections import Counter

        tool_counts = Counter(e.tool_name for e in errors)
        type_counts = Counter(e.error_type for e in errors)

        return {
            "count": len(errors),
            "window_seconds": self.window_seconds,
            "threshold": self.threshold,
            "tools": dict(tool_counts.most_common(5)),
            "types": dict(type_counts.most_common(5)),
            "messages": [e.message for e in errors[-3:]],  # Last 3 error messages
        }

    def clear(self) -> None:
        """Clear all tracked errors."""
        self._errors = []
        self._save_state()


class EditHistory:
    """Track file edits to detect doom loops.

    A doom loop is when the same file is edited 3+ times in a short window
    without apparent progress (tests still failing, errors recurring).
    """

    DEFAULT_WINDOW_SECONDS = 600  # 10 minutes
    DEFAULT_REPEAT_THRESHOLD = 3

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        repeat_threshold: int = DEFAULT_REPEAT_THRESHOLD,
    ):
        self.window_seconds = window_seconds
        self.repeat_threshold = repeat_threshold

        if state_dir is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            state_dir = Path(project_dir) / ".claude" / "state" / "decision-guidance"

        self.state_file = state_dir / "edit-history.json"
        self.state_dir = state_dir
        self._edits: list[EditEvent] = []
        self._load_state()

    def _load_state(self) -> None:
        """Load edit state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self._edits = [EditEvent.from_dict(e) for e in data.get("edits", [])]
            except (json.JSONDecodeError, IOError, KeyError):
                self._edits = []
        self._prune_old_edits()

    def _save_state(self) -> None:
        """Save edit state to disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({"edits": [e.to_dict() for e in self._edits]}, f, indent=2)

    def _prune_old_edits(self) -> None:
        """Remove edits outside the rolling window."""
        cutoff = time.time() - self.window_seconds
        self._edits = [e for e in self._edits if e.timestamp > cutoff]

    def record_edit(
        self,
        file_path: str,
        tool_name: str,
        success: bool,
        session_id: Optional[str] = None,
    ) -> None:
        """Record a file edit event."""
        self._prune_old_edits()

        event = EditEvent(
            timestamp=time.time(),
            file_path=file_path,
            tool_name=tool_name,
            success=success,
            session_id=session_id or os.environ.get("CLAUDE_SESSION_ID"),
        )
        self._edits.append(event)
        self._save_state()

    def detect_doom_loop(self) -> Optional[dict]:
        """Detect if a doom loop is occurring.

        Returns dict with details if doom loop detected, None otherwise.
        """
        self._prune_old_edits()

        from collections import Counter

        file_counts = Counter(e.file_path for e in self._edits)
        repeated_files = [
            (f, count) for f, count in file_counts.items()
            if count >= self.repeat_threshold
        ]

        if not repeated_files:
            return None

        # Check if recent edits to repeated files are failing
        repeated_file_paths = {f for f, _ in repeated_files}
        recent_repeated_edits = [
            e for e in self._edits[-10:]
            if e.file_path in repeated_file_paths
        ]

        failed_edits = [e for e in recent_repeated_edits if not e.success]

        if len(failed_edits) >= 2 or len(repeated_files) > 0:
            return {
                "files": dict(repeated_files),
                "recent_failures": len(failed_edits),
                "total_edits": len(self._edits),
                "window_seconds": self.window_seconds,
            }

        return None

    def clear(self) -> None:
        """Clear edit history."""
        self._edits = []
        self._save_state()
