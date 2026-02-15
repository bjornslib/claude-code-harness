"""Inbound message queue for Google Chat messages.

Provides a local JSON-backed queue for buffering inbound messages
from Google Chat. Messages are stored until consumed by System 3
or the heartbeat Communicator.

Queue file location: ~/.claude/state/gchat-message-queue.json

Features:
    - FIFO message ordering with timestamps
    - Thread-based grouping for conversation continuity
    - Message deduplication by Google Chat message name
    - Atomic persistence (write-to-temp-then-rename)
    - Queue size limits to prevent unbounded growth
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_PATH = Path.home() / ".claude" / "state" / "gchat-message-queue.json"
MAX_QUEUE_SIZE = 500  # Maximum messages in queue before oldest are dropped


class NormalizedMessage(BaseModel):
    """Normalized inbound message from Google Chat.

    Standard format for all inbound messages regardless of source,
    enabling consistent processing by System 3.
    """

    message_id: str = Field(description="Unique ID (Google Chat message resource name)")
    sender: str = Field(description="Sender display name")
    sender_id: str = Field(default="", description="Sender resource name")
    text: str = Field(description="Message text content")
    timestamp: str = Field(description="ISO 8601 creation timestamp")
    thread_id: str = Field(default="", description="Thread resource name for grouping")
    space_id: str = Field(default="", description="Space resource name")
    queued_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When this message was added to the queue",
    )
    consumed: bool = Field(default=False, description="Whether this message has been consumed")
    consumed_at: str = Field(default="", description="When this message was consumed")


class ThreadGroup(BaseModel):
    """A group of messages in the same thread."""

    thread_id: str
    message_count: int = 0
    latest_timestamp: str = ""
    messages: list[NormalizedMessage] = Field(default_factory=list)


class MessageQueue(BaseModel):
    """Persisted message queue state."""

    messages: list[NormalizedMessage] = Field(default_factory=list)
    version: int = Field(default=1)
    last_updated: str = Field(default="")
    total_received: int = Field(default=0)
    total_consumed: int = Field(default=0)


class MessageQueueManager:
    """Manages the inbound message queue with thread grouping.

    Thread-safe through atomic write operations.
    """

    def __init__(self, queue_path: Path | None = None) -> None:
        self._path = queue_path or DEFAULT_QUEUE_PATH
        self._queue: MessageQueue | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> MessageQueue:
        """Load queue from disk, creating default if missing."""
        if self._queue is not None:
            return self._queue

        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._queue = MessageQueue.model_validate(data)
                logger.debug("Loaded message queue from %s", self._path)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning(
                    "Failed to load message queue from %s: %s. Using empty queue.",
                    self._path,
                    exc,
                )
                self._queue = MessageQueue()
        else:
            logger.info("No message queue at %s, using empty queue.", self._path)
            self._queue = MessageQueue()

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
            logger.debug("Saved message queue to %s", self._path)
        except OSError as exc:
            logger.error("Failed to save message queue: %s", exc)
            tmp_path.unlink(missing_ok=True)
            raise

    def enqueue(self, message: NormalizedMessage) -> bool:
        """Add a message to the queue.

        Returns:
            True if message was added, False if it was a duplicate.
        """
        queue = self.load()

        # Deduplication: check if message_id already exists
        existing_ids = {m.message_id for m in queue.messages}
        if message.message_id in existing_ids:
            logger.debug("Duplicate message %s, skipping", message.message_id)
            return False

        queue.messages.append(message)
        queue.total_received += 1
        queue.last_updated = datetime.now(timezone.utc).isoformat()

        # Enforce queue size limit (drop oldest consumed first, then oldest unconsumed)
        if len(queue.messages) > MAX_QUEUE_SIZE:
            self._trim_queue(queue)

        self.save()
        logger.info("Enqueued message %s", message.message_id)
        return True

    def enqueue_batch(self, messages: list[NormalizedMessage]) -> int:
        """Add multiple messages to the queue.

        Returns:
            Number of messages actually added (after dedup).
        """
        added = 0
        for msg in messages:
            if self.enqueue(msg):
                added += 1
        return added

    def get_unconsumed(self, limit: int = 50) -> list[NormalizedMessage]:
        """Get unconsumed messages in FIFO order.

        Args:
            limit: Maximum number of messages to return.

        Returns:
            List of unconsumed NormalizedMessage objects.
        """
        queue = self.load()
        return [
            m for m in queue.messages
            if not m.consumed
        ][:limit]

    def consume(self, message_ids: list[str]) -> int:
        """Mark messages as consumed.

        Args:
            message_ids: List of message IDs to mark as consumed.

        Returns:
            Number of messages actually marked as consumed.
        """
        queue = self.load()
        now = datetime.now(timezone.utc).isoformat()
        consumed_count = 0

        for msg in queue.messages:
            if msg.message_id in message_ids and not msg.consumed:
                msg.consumed = True
                msg.consumed_at = now
                consumed_count += 1

        queue.total_consumed += consumed_count
        queue.last_updated = now
        self.save()
        return consumed_count

    def get_thread_groups(self, unconsumed_only: bool = True) -> list[ThreadGroup]:
        """Group messages by thread ID.

        Args:
            unconsumed_only: If True, only include unconsumed messages.

        Returns:
            List of ThreadGroup objects, sorted by latest timestamp descending.
        """
        queue = self.load()
        threads: dict[str, ThreadGroup] = {}

        for msg in queue.messages:
            if unconsumed_only and msg.consumed:
                continue

            tid = msg.thread_id or f"no-thread-{msg.message_id}"
            if tid not in threads:
                threads[tid] = ThreadGroup(thread_id=tid)

            group = threads[tid]
            group.messages.append(msg)
            group.message_count += 1
            if not group.latest_timestamp or msg.timestamp > group.latest_timestamp:
                group.latest_timestamp = msg.timestamp

        # Sort by latest timestamp descending
        groups = sorted(
            threads.values(),
            key=lambda g: g.latest_timestamp,
            reverse=True,
        )
        return groups

    def get_thread_messages(
        self,
        thread_id: str,
        include_consumed: bool = False,
    ) -> list[NormalizedMessage]:
        """Get all messages in a specific thread.

        Args:
            thread_id: Thread resource name to filter by.
            include_consumed: If True, include consumed messages.

        Returns:
            List of messages in the thread, ordered by timestamp.
        """
        queue = self.load()
        messages = [
            m for m in queue.messages
            if m.thread_id == thread_id
            and (include_consumed or not m.consumed)
        ]
        return sorted(messages, key=lambda m: m.timestamp)

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        queue = self.load()
        unconsumed = sum(1 for m in queue.messages if not m.consumed)
        consumed = sum(1 for m in queue.messages if m.consumed)

        # Thread stats
        thread_ids = {m.thread_id for m in queue.messages if not m.consumed and m.thread_id}

        return {
            "queue_size": len(queue.messages),
            "unconsumed": unconsumed,
            "consumed_in_queue": consumed,
            "total_received": queue.total_received,
            "total_consumed": queue.total_consumed,
            "active_threads": len(thread_ids),
            "last_updated": queue.last_updated or "never",
            "queue_file": str(self._path),
        }

    def purge_consumed(self, keep_recent: int = 50) -> int:
        """Remove consumed messages from the queue to free space.

        Args:
            keep_recent: Keep this many of the most recent consumed messages.

        Returns:
            Number of messages purged.
        """
        queue = self.load()
        consumed = [m for m in queue.messages if m.consumed]
        unconsumed = [m for m in queue.messages if not m.consumed]

        # Sort consumed by consumed_at, keep the most recent
        consumed.sort(key=lambda m: m.consumed_at, reverse=True)
        to_keep = consumed[:keep_recent]
        purged = len(consumed) - len(to_keep)

        queue.messages = unconsumed + to_keep
        queue.last_updated = datetime.now(timezone.utc).isoformat()
        self.save()

        logger.info("Purged %d consumed messages from queue", purged)
        return purged

    @staticmethod
    def _trim_queue(queue: MessageQueue) -> None:
        """Trim the queue to MAX_QUEUE_SIZE, removing oldest consumed first."""
        # Separate consumed and unconsumed
        consumed = [m for m in queue.messages if m.consumed]
        unconsumed = [m for m in queue.messages if not m.consumed]

        # Remove oldest consumed first
        excess = len(queue.messages) - MAX_QUEUE_SIZE
        if excess <= len(consumed):
            # Can trim by removing consumed messages
            consumed.sort(key=lambda m: m.consumed_at or m.timestamp)
            consumed = consumed[excess:]
        else:
            # Need to also trim unconsumed (overflow scenario)
            consumed = []
            remaining_excess = excess - len(consumed)
            unconsumed.sort(key=lambda m: m.timestamp)
            unconsumed = unconsumed[remaining_excess:]

        queue.messages = unconsumed + consumed
