"""Read state management for Google Chat messages.

Tracks which messages have been read using a local JSON file,
enabling the get_new_messages tool to return only unread messages.

State file location: ~/.claude/state/gchat-read-state.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path.home() / ".claude" / "state" / "gchat-read-state.json"


class SpaceReadState(BaseModel):
    """Read state for a single Google Chat space."""

    space_id: str
    last_read_time: str = Field(
        default="",
        description="ISO 8601 timestamp of last read message",
    )
    last_read_message_name: str = Field(
        default="",
        description="Resource name of the last read message (spaces/X/messages/Y)",
    )
    total_messages_read: int = Field(default=0)


class ReadState(BaseModel):
    """Persisted read state for all tracked Google Chat spaces."""

    spaces: dict[str, SpaceReadState] = Field(default_factory=dict)
    last_updated: str = Field(default="")
    version: int = Field(default=1)

    def get_space_state(self, space_id: str) -> SpaceReadState:
        """Get or create read state for a space."""
        if space_id not in self.spaces:
            self.spaces[space_id] = SpaceReadState(space_id=space_id)
        return self.spaces[space_id]

    def mark_read(
        self,
        space_id: str,
        message_name: str,
        message_time: str,
        count: int = 1,
    ) -> None:
        """Mark messages as read up to a given message."""
        state = self.get_space_state(space_id)
        state.last_read_message_name = message_name
        state.last_read_time = message_time
        state.total_messages_read += count
        self.last_updated = datetime.now(timezone.utc).isoformat()


class ReadStateManager:
    """Manages persistence of read state to a JSON file.

    Thread-safe through atomic write operations (write to temp, then rename).
    """

    def __init__(self, state_path: Path | None = None) -> None:
        self._path = state_path or DEFAULT_STATE_PATH
        self._state: ReadState | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> ReadState:
        """Load read state from disk, creating default if missing."""
        if self._state is not None:
            return self._state

        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._state = ReadState.model_validate(data)
                logger.debug("Loaded read state from %s", self._path)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning(
                    "Failed to load read state from %s: %s. Using defaults.",
                    self._path,
                    exc,
                )
                self._state = ReadState()
        else:
            logger.info("No read state file at %s, using defaults.", self._path)
            self._state = ReadState()

        return self._state

    def save(self) -> None:
        """Persist current read state to disk atomically."""
        if self._state is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        tmp_path = self._path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                self._state.model_dump_json(indent=2),
                encoding="utf-8",
            )
            tmp_path.rename(self._path)
            logger.debug("Saved read state to %s", self._path)
        except OSError as exc:
            logger.error("Failed to save read state: %s", exc)
            # Clean up temp file on failure
            tmp_path.unlink(missing_ok=True)
            raise

    def mark_read(
        self,
        space_id: str,
        message_name: str,
        message_time: str,
        count: int = 1,
    ) -> None:
        """Mark messages as read and persist immediately."""
        state = self.load()
        state.mark_read(space_id, message_name, message_time, count)
        self.save()

    def get_last_read_time(self, space_id: str) -> str:
        """Get the last read timestamp for a space."""
        state = self.load()
        return state.get_space_state(space_id).last_read_time

    def get_stats(self) -> dict[str, Any]:
        """Get read state statistics."""
        state = self.load()
        return {
            "total_spaces_tracked": len(state.spaces),
            "last_updated": state.last_updated or "never",
            "spaces": {
                sid: {
                    "total_messages_read": s.total_messages_read,
                    "last_read_time": s.last_read_time or "never",
                }
                for sid, s in state.spaces.items()
            },
        }
