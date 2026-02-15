"""Inbound message routing with rate limiting and normalization.

Handles the flow of inbound messages from Google Chat:
1. Fetch new messages from Google Chat API (via ChatClient)
2. Normalize into standard NormalizedMessage format
3. Apply rate limiting per sender
4. Queue for consumption by System 3 or heartbeat

Rate Limiting:
    - Per-sender sliding window (default: 10 messages per 60 seconds)
    - Configurable via environment variables:
        GCHAT_RATE_LIMIT_MAX: Maximum messages per window (default: 10)
        GCHAT_RATE_LIMIT_WINDOW: Window size in seconds (default: 60)
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from google_chat_bridge.chat_client import ChatClient, ChatMessage
from google_chat_bridge.message_queue import MessageQueueManager, NormalizedMessage

logger = logging.getLogger(__name__)

# Rate limit defaults
DEFAULT_RATE_LIMIT_MAX = 10  # messages per window
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds


class RateLimiter:
    """Sliding window rate limiter per sender.

    Tracks message timestamps per sender and rejects messages
    that exceed the configured rate.
    """

    def __init__(
        self,
        max_messages: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self._max = max_messages or int(
            os.environ.get("GCHAT_RATE_LIMIT_MAX", str(DEFAULT_RATE_LIMIT_MAX))
        )
        self._window = window_seconds or int(
            os.environ.get("GCHAT_RATE_LIMIT_WINDOW", str(DEFAULT_RATE_LIMIT_WINDOW))
        )
        # sender_id -> list of timestamps
        self._windows: dict[str, list[float]] = defaultdict(list)

    @property
    def max_messages(self) -> int:
        return self._max

    @property
    def window_seconds(self) -> int:
        return self._window

    def check(self, sender_id: str) -> bool:
        """Check if a sender is within rate limits.

        Args:
            sender_id: Sender identifier to check.

        Returns:
            True if the message is allowed, False if rate limited.
        """
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - self._window

        # Clean old entries
        self._windows[sender_id] = [
            ts for ts in self._windows[sender_id]
            if ts > window_start
        ]

        # Check limit
        if len(self._windows[sender_id]) >= self._max:
            logger.warning(
                "Rate limit exceeded for sender %s: %d/%d in %ds window",
                sender_id,
                len(self._windows[sender_id]),
                self._max,
                self._window,
            )
            return False

        # Record this message
        self._windows[sender_id].append(now)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - self._window

        active_senders = {}
        for sender_id, timestamps in self._windows.items():
            recent = [ts for ts in timestamps if ts > window_start]
            if recent:
                active_senders[sender_id] = {
                    "messages_in_window": len(recent),
                    "remaining": max(0, self._max - len(recent)),
                }

        return {
            "max_per_window": self._max,
            "window_seconds": self._window,
            "active_senders": active_senders,
            "total_tracked_senders": len(self._windows),
        }


class MessageRouter:
    """Routes inbound messages through normalization, rate limiting, and queuing.

    Orchestrates the full inbound message pipeline:
    1. Fetch new messages from Google Chat API
    2. Normalize into standard format
    3. Apply rate limiting
    4. Enqueue for consumption
    """

    def __init__(
        self,
        client: ChatClient,
        queue_manager: MessageQueueManager,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._client = client
        self._queue = queue_manager
        self._rate_limiter = rate_limiter or RateLimiter()

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    def poll_and_route(
        self,
        space_id: str | None = None,
        max_messages: int = 50,
    ) -> dict[str, Any]:
        """Fetch new messages from Google Chat, normalize, and queue them.

        This is the main entry point for inbound message processing.
        It fetches messages from the Google Chat API that are newer
        than the last read watermark, normalizes them, applies rate
        limiting, and adds them to the local queue.

        Args:
            space_id: Google Chat space ID. If None, uses default.
            max_messages: Maximum messages to fetch per poll.

        Returns:
            Dict with polling results (fetched, queued, rate_limited, duplicates).
        """
        resolved_space = self._client._resolve_space(space_id)

        # Get the last read time from the read state (managed externally)
        # For routing, we fetch recent messages and let dedup handle repeats
        messages = self._client.list_messages(
            space_id=resolved_space,
            page_size=min(max_messages, 100),
        )

        fetched = len(messages)
        queued = 0
        rate_limited = 0
        duplicates = 0

        for msg in messages:
            normalized = self._normalize_message(msg, resolved_space)

            # Rate limit check
            if not self._rate_limiter.check(normalized.sender_id):
                rate_limited += 1
                continue

            # Enqueue (dedup handled internally)
            if self._queue.enqueue(normalized):
                queued += 1
            else:
                duplicates += 1

        return {
            "space_id": resolved_space,
            "fetched": fetched,
            "queued": queued,
            "rate_limited": rate_limited,
            "duplicates": duplicates,
        }

    def route_messages(
        self,
        messages: list[ChatMessage],
        space_id: str = "",
    ) -> dict[str, Any]:
        """Route a batch of pre-fetched messages through normalization and queuing.

        Use this when messages have already been fetched (e.g., from get_new_messages)
        and need to be processed through the routing pipeline.

        Args:
            messages: List of ChatMessage objects to route.
            space_id: Space ID to associate with the messages.

        Returns:
            Dict with routing results.
        """
        queued = 0
        rate_limited = 0
        duplicates = 0

        for msg in messages:
            normalized = self._normalize_message(msg, space_id)

            if not self._rate_limiter.check(normalized.sender_id):
                rate_limited += 1
                continue

            if self._queue.enqueue(normalized):
                queued += 1
            else:
                duplicates += 1

        return {
            "total": len(messages),
            "queued": queued,
            "rate_limited": rate_limited,
            "duplicates": duplicates,
        }

    @staticmethod
    def _normalize_message(
        msg: ChatMessage,
        space_id: str = "",
    ) -> NormalizedMessage:
        """Normalize a Google Chat message to standard format.

        Args:
            msg: Raw ChatMessage from the Google Chat API.
            space_id: Space resource name to associate.

        Returns:
            NormalizedMessage in standard format.
        """
        return NormalizedMessage(
            message_id=msg.name,
            sender=msg.sender_display_name,
            sender_id=msg.sender_name,
            text=msg.text,
            timestamp=msg.create_time,
            thread_id=msg.thread_name,
            space_id=space_id or msg.space_name,
        )
