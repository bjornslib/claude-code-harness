"""Proactive notification dispatcher for Google Chat.

Maps event types to formatting tools, handles deduplication and quiet hours,
and logs all notification activity.

Notification log location: ~/.claude/state/gchat-notification-log.json

Event Types:
    - heartbeat_finding: System 3 heartbeat findings (uses send_heartbeat_finding pattern)
    - task_completion: Task status updates (uses send_task_completion pattern)
    - blocked_alert: Blocked work requiring user input (uses send_blocked_alert pattern)
    - morning_briefing: Morning daily briefing (uses send_daily_briefing pattern)
    - eod_summary: End-of-day summary (uses send_daily_briefing EOD variant)
    - orchestrator_status: Orchestrator progress updates (uses send_progress_update pattern)

Deduplication:
    - Prevents sending duplicate notifications within 5 minutes
    - Dedup key based on event_type + hash of core event data fields

Quiet Hours:
    - Default: 22:00-07:00 local time
    - Configurable via GCHAT_QUIET_START and GCHAT_QUIET_END environment variables
    - Format: "HH:MM" (24-hour)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path.home() / ".claude" / "state" / "gchat-notification-log.json"
DEDUP_WINDOW_SECONDS = 300  # 5 minutes
DEFAULT_QUIET_START = "22:00"
DEFAULT_QUIET_END = "07:00"


class NotificationLogEntry(BaseModel):
    """A single notification log entry."""

    timestamp: str = Field(description="ISO 8601 timestamp when notification was dispatched")
    event_type: str = Field(description="Type of event that triggered the notification")
    space_id: str = Field(default="", description="Target Google Chat space ID")
    thread_key: str = Field(default="", description="Thread key used for grouping")
    message_name: str = Field(default="", description="Google Chat message resource name (if sent)")
    dedup_key: str = Field(description="Deduplication key for this notification")
    status: str = Field(description="Dispatch status (sent, skipped_dedup, skipped_quiet_hours, error)")
    error: str = Field(default="", description="Error message if status=error")


class NotificationLog(BaseModel):
    """Persisted notification log state."""

    entries: list[NotificationLogEntry] = Field(default_factory=list)
    version: int = Field(default=1)
    total_sent: int = Field(default=0)
    total_skipped_dedup: int = Field(default=0)
    total_skipped_quiet: int = Field(default=0)
    total_errors: int = Field(default=0)


class NotificationDispatcher:
    """Dispatches proactive notifications with deduplication and quiet hours.

    Thread-safe through atomic write operations.
    """

    def __init__(
        self,
        log_path: Path | None = None,
        quiet_start: str | None = None,
        quiet_end: str | None = None,
    ) -> None:
        self._log_path = log_path or DEFAULT_LOG_PATH
        self._log: NotificationLog | None = None
        self._quiet_start = quiet_start or os.environ.get("GCHAT_QUIET_START", DEFAULT_QUIET_START)
        self._quiet_end = quiet_end or os.environ.get("GCHAT_QUIET_END", DEFAULT_QUIET_END)

    @property
    def log_path(self) -> Path:
        return self._log_path

    def load_log(self) -> NotificationLog:
        """Load notification log from disk, creating default if missing."""
        if self._log is not None:
            return self._log

        if self._log_path.exists():
            try:
                data = json.loads(self._log_path.read_text(encoding="utf-8"))
                self._log = NotificationLog.model_validate(data)
                logger.debug("Loaded notification log from %s", self._log_path)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning(
                    "Failed to load notification log from %s: %s. Using empty log.",
                    self._log_path,
                    exc,
                )
                self._log = NotificationLog()
        else:
            logger.info("No notification log at %s, using empty log.", self._log_path)
            self._log = NotificationLog()

        return self._log

    def save_log(self) -> None:
        """Persist current log to disk atomically."""
        if self._log is None:
            return

        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._log_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                self._log.model_dump_json(indent=2),
                encoding="utf-8",
            )
            tmp_path.rename(self._log_path)
            logger.debug("Saved notification log to %s", self._log_path)
        except OSError as exc:
            logger.error("Failed to save notification log: %s", exc)
            tmp_path.unlink(missing_ok=True)
            raise

    def should_send(self, dedup_key: str) -> tuple[bool, str]:
        """Check if a notification should be sent (dedup + quiet hours).

        Args:
            dedup_key: Deduplication key for the notification.

        Returns:
            Tuple of (should_send: bool, reason: str).
        """
        # Check deduplication
        log = self.load_log()
        now = datetime.now(timezone.utc)
        cutoff_time = now.timestamp() - DEDUP_WINDOW_SECONDS

        # Find recent entries with same dedup_key
        for entry in reversed(log.entries):
            entry_time = datetime.fromisoformat(entry.timestamp).timestamp()
            if entry_time < cutoff_time:
                break  # Older than dedup window

            if entry.dedup_key == dedup_key and entry.status == "sent":
                return False, "skipped_dedup"

        # Check quiet hours
        if self._is_quiet_hours():
            return False, "skipped_quiet_hours"

        return True, "ok"

    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours.

        Quiet hours are defined as local time between quiet_start and quiet_end.
        Handles overnight ranges (e.g., 22:00-07:00).
        """
        try:
            now = datetime.now()
            current_time = now.time()

            # Parse quiet hours
            start = time.fromisoformat(self._quiet_start)
            end = time.fromisoformat(self._quiet_end)

            # Handle overnight range (e.g., 22:00-07:00)
            if start <= end:
                # Same-day range (e.g., 09:00-17:00)
                return start <= current_time <= end
            else:
                # Overnight range (e.g., 22:00-07:00)
                return current_time >= start or current_time <= end

        except ValueError:
            logger.warning(
                "Invalid quiet hours format: %s-%s. Using defaults.",
                self._quiet_start,
                self._quiet_end,
            )
            return False

    def log_notification(
        self,
        event_type: str,
        dedup_key: str,
        space_id: str = "",
        thread_key: str = "",
        message_name: str = "",
        status: str = "sent",
        error: str = "",
    ) -> None:
        """Log a notification dispatch attempt.

        Args:
            event_type: Type of event that triggered the notification.
            dedup_key: Deduplication key for this notification.
            space_id: Target Google Chat space ID.
            thread_key: Thread key used for grouping.
            message_name: Google Chat message resource name (if sent).
            status: Dispatch status (sent, skipped_dedup, skipped_quiet_hours, error).
            error: Error message if status=error.
        """
        log = self.load_log()
        entry = NotificationLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            space_id=space_id,
            thread_key=thread_key,
            message_name=message_name,
            dedup_key=dedup_key,
            status=status,
            error=error,
        )

        log.entries.append(entry)

        # Update counters
        if status == "sent":
            log.total_sent += 1
        elif status == "skipped_dedup":
            log.total_skipped_dedup += 1
        elif status == "skipped_quiet_hours":
            log.total_skipped_quiet += 1
        elif status == "error":
            log.total_errors += 1

        self.save_log()
        logger.info(
            "Logged notification: event_type=%s, status=%s, dedup_key=%s",
            event_type,
            status,
            dedup_key,
        )

    def get_history(
        self,
        space_id: str = "",
        limit: int = 20,
    ) -> list[NotificationLogEntry]:
        """Get recent notification log entries.

        Args:
            space_id: Optional filter by space ID. Empty string = all spaces.
            limit: Maximum number of entries to return (most recent first).

        Returns:
            List of NotificationLogEntry objects.
        """
        log = self.load_log()
        entries = log.entries

        if space_id:
            entries = [e for e in entries if e.space_id == space_id]

        # Return most recent first
        return list(reversed(entries[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        """Get notification dispatcher statistics."""
        log = self.load_log()
        return {
            "total_entries": len(log.entries),
            "total_sent": log.total_sent,
            "total_skipped_dedup": log.total_skipped_dedup,
            "total_skipped_quiet_hours": log.total_skipped_quiet,
            "total_errors": log.total_errors,
            "quiet_hours": {
                "start": self._quiet_start,
                "end": self._quiet_end,
                "currently_active": self._is_quiet_hours(),
            },
            "dedup_window_seconds": DEDUP_WINDOW_SECONDS,
            "log_file": str(self._log_path),
        }

    @staticmethod
    def compute_dedup_key(event_type: str, event_data: dict[str, Any]) -> str:
        """Compute a deduplication key for an event.

        Args:
            event_type: Type of event.
            event_data: Event data dictionary. Core fields are hashed for dedup.

        Returns:
            Deduplication key string.
        """
        # Extract core fields for dedup based on event type
        core_fields: dict[str, Any] = {}

        if event_type == "heartbeat_finding":
            core_fields = {
                "finding_type": event_data.get("finding_type", ""),
                "summary": event_data.get("summary", ""),
            }
        elif event_type == "task_completion":
            core_fields = {
                "task_title": event_data.get("task_title", ""),
                "status": event_data.get("status", ""),
            }
        elif event_type == "blocked_alert":
            core_fields = {
                "task_title": event_data.get("task_title", ""),
                "blocker_description": event_data.get("blocker_description", ""),
            }
        elif event_type in ["morning_briefing", "eod_summary"]:
            core_fields = {
                "date": event_data.get("date", ""),
            }
        elif event_type == "orchestrator_status":
            core_fields = {
                "orchestrator_name": event_data.get("orchestrator_name", ""),
                "status": event_data.get("status", ""),
            }
        else:
            # Generic fallback: hash entire event_data
            core_fields = event_data

        # Compute hash of core fields
        core_json = json.dumps(core_fields, sort_keys=True)
        hash_hex = hashlib.md5(core_json.encode("utf-8")).hexdigest()[:16]

        return f"{event_type}:{hash_hex}"


def map_event_to_formatter(
    event_type: str,
    event_data: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Map event type to the appropriate formatter function parameters.

    Args:
        event_type: Type of event to dispatch.
        event_data: Event data dictionary with fields specific to the event type.

    Returns:
        Tuple of (formatter_name, formatter_kwargs).

    Raises:
        ValueError: If event_type is not recognized.
    """
    if event_type == "heartbeat_finding":
        return "send_heartbeat_finding", {
            "finding_type": event_data.get("finding_type", ""),
            "summary": event_data.get("summary", ""),
            "details": event_data.get("details", ""),
            "action_needed": event_data.get("action_needed", True),
            "thread_key": event_data.get("thread_key", "system3-heartbeat"),
        }

    elif event_type == "task_completion":
        return "send_task_completion", {
            "task_title": event_data.get("task_title", ""),
            "task_id": event_data.get("task_id", ""),
            "status": event_data.get("status", "completed"),
            "summary": event_data.get("summary", ""),
            "details": event_data.get("details", ""),
            "thread_key": event_data.get("thread_key", "system3-tasks"),
        }

    elif event_type == "blocked_alert":
        return "send_blocked_alert", {
            "task_title": event_data.get("task_title", ""),
            "task_id": event_data.get("task_id", ""),
            "blocker_description": event_data.get("blocker_description", ""),
            "options": event_data.get("options", "[]"),
            "urgency": event_data.get("urgency", "medium"),
            "thread_key": event_data.get("thread_key", "system3-alerts"),
        }

    elif event_type == "morning_briefing":
        return "send_daily_briefing", {
            "briefing_type": "morning",
            "date": event_data.get("date", ""),
            "beads_summary": event_data.get("beads_summary", ""),
            "orchestrator_summary": event_data.get("orchestrator_summary", ""),
            "git_summary": event_data.get("git_summary", ""),
            "priorities": event_data.get("priorities", "[]"),
            "blockers": event_data.get("blockers", "[]"),
            "use_card": event_data.get("use_card", True),
            "thread_key": event_data.get("thread_key", "system3-briefings"),
        }

    elif event_type == "eod_summary":
        return "send_daily_briefing", {
            "briefing_type": "eod",
            "date": event_data.get("date", ""),
            "beads_summary": event_data.get("beads_summary", ""),
            "orchestrator_summary": event_data.get("orchestrator_summary", ""),
            "git_summary": event_data.get("git_summary", ""),
            "accomplishments": event_data.get("accomplishments", "[]"),
            "blockers": event_data.get("blockers", "[]"),
            "use_card": event_data.get("use_card", True),
            "thread_key": event_data.get("thread_key", "system3-briefings"),
        }

    elif event_type == "orchestrator_status":
        return "send_progress_update", {
            "orchestrator_name": event_data.get("orchestrator_name", ""),
            "status": event_data.get("status", "running"),
            "tasks_completed": event_data.get("tasks_completed", 0),
            "tasks_total": event_data.get("tasks_total", 0),
            "current_task": event_data.get("current_task", ""),
            "elapsed_time": event_data.get("elapsed_time", ""),
            "details": event_data.get("details", ""),
            "thread_key": event_data.get("thread_key", "system3-progress"),
        }

    else:
        raise ValueError(f"Unknown event type: {event_type}")
