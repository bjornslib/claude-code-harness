"""Command parsing and management for Google Chat messages.

Parses inbound messages as structured commands with keyword and fuzzy matching.
Commands are stored in a local queue for consumption by System 3.

Command file location: ~/.claude/state/gchat-pending-commands.json

Supported Commands:
    - status: "status", "what's the status?", "any updates?"
    - ready: "bd ready", "what's ready?", "what needs work?"
    - start: "start [initiative]", "begin [task]"
    - approve: "approve", "yes", "ok", "lgtm"
    - reject: "reject", "no", "nope"
    - help: "help", "commands", "?"
    - unknown: Anything else (stored for future processing)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_COMMANDS_PATH = Path.home() / ".claude" / "state" / "gchat-pending-commands.json"


class ParsedCommand(BaseModel):
    """A parsed command from a Google Chat message."""

    type: str = Field(description="Command type (status, ready, start, approve, reject, help, unknown)")
    args: list[str] = Field(default_factory=list, description="Command arguments extracted from text")
    sender: str = Field(description="Sender display name")
    sender_id: str = Field(description="Sender resource name")
    thread_id: str = Field(default="", description="Thread resource name")
    raw_text: str = Field(description="Original message text")
    timestamp: str = Field(description="ISO 8601 message creation time")
    consumed: bool = Field(default=False, description="Whether this command has been consumed")
    consumed_at: str = Field(default="", description="When this command was consumed")
    parsed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When this command was parsed",
    )
    message_id: str = Field(default="", description="Original message ID for deduplication")


class CommandQueue(BaseModel):
    """Persisted command queue state."""

    commands: list[ParsedCommand] = Field(default_factory=list)
    version: int = Field(default=1)
    last_updated: str = Field(default="")
    total_parsed: int = Field(default=0)
    total_consumed: int = Field(default=0)


class CommandParser:
    """Parses Google Chat messages into structured commands.

    Uses keyword matching with fuzzy detection for user-friendly command recognition.
    """

    # Command pattern definitions (case-insensitive)
    _STATUS_PATTERNS = [
        r"\bstatus\b",
        r"what'?s?\s+the\s+status",
        r"any\s+updates?",
        r"update\s+me",
        r"how\s+are\s+things",
    ]

    _READY_PATTERNS = [
        r"\bbd\s+ready\b",
        r"what'?s?\s+ready",
        r"what\s+needs?\s+work",
        r"ready\s+beads?",
        r"show\s+ready",
    ]

    _START_PATTERNS = [
        r"\bstart\s+(.+)",
        r"\bbegin\s+(.+)",
        r"\binitiate\s+(.+)",
        r"\blaunch\s+(.+)",
    ]

    _APPROVE_PATTERNS = [
        r"\bapprove\b",
        r"\byes\b",
        r"\bok\b",
        r"\blgtm\b",
        r"\b\+1\b",
        r"\bsounds?\s+good\b",
        r"\bgo\s+ahead\b",
    ]

    _REJECT_PATTERNS = [
        r"\breject\b",
        r"\bno\b",
        r"\bnope\b",
        r"\b-1\b",
        r"\bcancel\b",
        r"\bdon'?t\b",
        r"\bnegative\b",
    ]

    _HELP_PATTERNS = [
        r"\bhelp\b",
        r"\bcommands?\b",
        r"^\?$",
        r"what\s+can\s+you\s+do",
        r"show\s+commands?",
    ]

    @classmethod
    def parse(
        cls,
        text: str,
        sender: str = "",
        sender_id: str = "",
        thread_id: str = "",
        timestamp: str = "",
        message_id: str = "",
    ) -> ParsedCommand:
        """Parse a message text into a structured command.

        Args:
            text: The message text to parse.
            sender: Sender display name.
            sender_id: Sender resource name.
            thread_id: Thread resource name.
            timestamp: Message creation timestamp (ISO 8601).
            message_id: Original message ID.

        Returns:
            ParsedCommand with recognized type and extracted arguments.
        """
        text_lower = text.strip().lower()

        # Try each command type in priority order
        # Status check
        if cls._match_any(text_lower, cls._STATUS_PATTERNS):
            return ParsedCommand(
                type="status",
                args=[],
                sender=sender,
                sender_id=sender_id,
                thread_id=thread_id,
                raw_text=text,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                message_id=message_id,
            )

        # Ready check
        if cls._match_any(text_lower, cls._READY_PATTERNS):
            return ParsedCommand(
                type="ready",
                args=[],
                sender=sender,
                sender_id=sender_id,
                thread_id=thread_id,
                raw_text=text,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                message_id=message_id,
            )

        # Start command (with argument extraction)
        start_match = cls._match_any_with_groups(text_lower, cls._START_PATTERNS)
        if start_match:
            args = [g.strip() for g in start_match if g]
            return ParsedCommand(
                type="start",
                args=args,
                sender=sender,
                sender_id=sender_id,
                thread_id=thread_id,
                raw_text=text,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                message_id=message_id,
            )

        # Approve
        if cls._match_any(text_lower, cls._APPROVE_PATTERNS):
            return ParsedCommand(
                type="approve",
                args=[],
                sender=sender,
                sender_id=sender_id,
                thread_id=thread_id,
                raw_text=text,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                message_id=message_id,
            )

        # Reject
        if cls._match_any(text_lower, cls._REJECT_PATTERNS):
            return ParsedCommand(
                type="reject",
                args=[],
                sender=sender,
                sender_id=sender_id,
                thread_id=thread_id,
                raw_text=text,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                message_id=message_id,
            )

        # Help
        if cls._match_any(text_lower, cls._HELP_PATTERNS):
            return ParsedCommand(
                type="help",
                args=[],
                sender=sender,
                sender_id=sender_id,
                thread_id=thread_id,
                raw_text=text,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                message_id=message_id,
            )

        # Unknown command
        return ParsedCommand(
            type="unknown",
            args=[],
            sender=sender,
            sender_id=sender_id,
            thread_id=thread_id,
            raw_text=text,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            message_id=message_id,
        )

    @staticmethod
    def _match_any(text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the regex patterns."""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _match_any_with_groups(text: str, patterns: list[str]) -> list[str] | None:
        """Check if text matches any pattern and return captured groups."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return list(match.groups())
        return None


class CommandQueueManager:
    """Manages the pending commands queue with atomic persistence.

    Thread-safe through atomic write operations (write to temp, then rename).
    """

    def __init__(self, queue_path: Path | None = None) -> None:
        self._path = queue_path or DEFAULT_COMMANDS_PATH
        self._queue: CommandQueue | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> CommandQueue:
        """Load command queue from disk, creating default if missing."""
        if self._queue is not None:
            return self._queue

        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._queue = CommandQueue.model_validate(data)
                logger.debug("Loaded command queue from %s", self._path)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning(
                    "Failed to load command queue from %s: %s. Using empty queue.",
                    self._path,
                    exc,
                )
                self._queue = CommandQueue()
        else:
            logger.info("No command queue at %s, using empty queue.", self._path)
            self._queue = CommandQueue()

        return self._queue

    def save(self) -> None:
        """Persist current queue to disk atomically."""
        if self._queue is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                self._queue.model_dump_json(indent=2),
                encoding="utf-8",
            )
            tmp_path.rename(self._path)
            logger.debug("Saved command queue to %s", self._path)
        except OSError as exc:
            logger.error("Failed to save command queue: %s", exc)
            tmp_path.unlink(missing_ok=True)
            raise

    def enqueue(self, command: ParsedCommand) -> bool:
        """Add a parsed command to the queue.

        Returns:
            True if command was added, False if it was a duplicate.
        """
        queue = self.load()

        # Deduplication: check if message_id already exists
        if command.message_id:
            existing_ids = {c.message_id for c in queue.commands if c.message_id}
            if command.message_id in existing_ids:
                logger.debug("Duplicate command from message %s, skipping", command.message_id)
                return False

        queue.commands.append(command)
        queue.total_parsed += 1
        queue.last_updated = datetime.now(timezone.utc).isoformat()

        self.save()
        logger.info("Enqueued command type=%s from sender=%s", command.type, command.sender)
        return True

    def enqueue_batch(self, commands: list[ParsedCommand]) -> int:
        """Add multiple parsed commands to the queue.

        Returns:
            Number of commands actually added (after dedup).
        """
        added = 0
        for cmd in commands:
            if self.enqueue(cmd):
                added += 1
        return added

    def get_unconsumed(
        self,
        command_type: str = "",
        limit: int = 50,
    ) -> list[ParsedCommand]:
        """Get unconsumed commands, optionally filtered by type.

        Args:
            command_type: Optional filter by command type. Empty string = all types.
            limit: Maximum number of commands to return.

        Returns:
            List of unconsumed ParsedCommand objects in FIFO order.
        """
        queue = self.load()
        commands = [
            c for c in queue.commands
            if not c.consumed
            and (not command_type or c.type == command_type)
        ]
        return commands[:limit]

    def consume(self, command_indices: list[int] | None = None) -> int:
        """Mark commands as consumed.

        Args:
            command_indices: List of indices in the queue to mark as consumed.
                            If None, consumes ALL unconsumed commands.

        Returns:
            Number of commands actually marked as consumed.
        """
        queue = self.load()
        now = datetime.now(timezone.utc).isoformat()
        consumed_count = 0

        if command_indices is None:
            # Consume all unconsumed
            for cmd in queue.commands:
                if not cmd.consumed:
                    cmd.consumed = True
                    cmd.consumed_at = now
                    consumed_count += 1
        else:
            # Consume specific indices
            for idx in command_indices:
                if 0 <= idx < len(queue.commands):
                    cmd = queue.commands[idx]
                    if not cmd.consumed:
                        cmd.consumed = True
                        cmd.consumed_at = now
                        consumed_count += 1

        queue.total_consumed += consumed_count
        queue.last_updated = now
        self.save()
        return consumed_count

    def get_stats(self) -> dict[str, Any]:
        """Get command queue statistics."""
        queue = self.load()
        unconsumed = sum(1 for c in queue.commands if not c.consumed)
        consumed = sum(1 for c in queue.commands if c.consumed)

        # Type breakdown
        type_counts: dict[str, int] = {}
        for cmd in queue.commands:
            if not cmd.consumed:
                type_counts[cmd.type] = type_counts.get(cmd.type, 0) + 1

        return {
            "queue_size": len(queue.commands),
            "unconsumed": unconsumed,
            "consumed_in_queue": consumed,
            "total_parsed": queue.total_parsed,
            "total_consumed": queue.total_consumed,
            "unconsumed_by_type": type_counts,
            "last_updated": queue.last_updated or "never",
            "queue_file": str(self._path),
        }

    def purge_consumed(self, keep_recent: int = 50) -> int:
        """Remove consumed commands from the queue to free space.

        Args:
            keep_recent: Keep this many of the most recent consumed commands.

        Returns:
            Number of commands purged.
        """
        queue = self.load()
        consumed = [c for c in queue.commands if c.consumed]
        unconsumed = [c for c in queue.commands if not c.consumed]

        # Sort consumed by consumed_at, keep the most recent
        consumed.sort(key=lambda c: c.consumed_at or c.parsed_at, reverse=True)
        to_keep = consumed[:keep_recent]
        purged = len(consumed) - len(to_keep)

        queue.commands = unconsumed + to_keep
        queue.last_updated = datetime.now(timezone.utc).isoformat()
        self.save()

        logger.info("Purged %d consumed commands from queue", purged)
        return purged
