#!/usr/bin/env python3
"""Native Agent Teams Channel Adapter.

Implements ChannelAdapter using the Claude Code Native Agent Teams protocol.
This adapter is used when the Pipeline Runner is spawned as a background
teammate in System 3's live team (e.g., s3-live-workers).

The runner uses SendMessage (via message queue files) to signal System 3
and polls the inbox file for incoming messages.

Message format (JSON):
    {
        "type": "signal" | "approval" | "guidance" | "shutdown",
        "signal_type": "RUNNER_STUCK",   # For type=signal
        "payload": {...},
        "sender": "runner-abc123",
        "timestamp": "2026-02-24T10:30:00Z"
    }

Usage:
    adapter = NativeTeamsAdapter(
        team_name="s3-live-workers",
        recipient="team-lead",
    )
    adapter.register("runner-abc123", "PRD-AUTH-001")
    adapter.send_signal("AWAITING_APPROVAL", payload={"node_id": "validate_backend_biz"})
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from .base import ChannelAdapter, ChannelError, ChannelMessage


class NativeTeamsAdapter(ChannelAdapter):
    """Channel adapter for Claude Code Native Agent Teams.

    Communicates via inbox/outbox JSON files in the team's message directory.
    This is the preferred adapter when the runner is operating as a team member.

    Args:
        team_name: The native team name (e.g., "s3-live-workers").
        recipient: The team member to send signals to (e.g., "team-lead").
        inbox_poll_interval: Seconds between inbox polls (default: 1.0).
        tasks_dir: Override path to the tasks directory.
            Defaults to ~/.claude/tasks/{team_name}/inbox/.
    """

    def __init__(
        self,
        team_name: str = "s3-live-workers",
        recipient: str = "team-lead",
        inbox_poll_interval: float = 1.0,
        tasks_dir: str | None = None,
    ) -> None:
        self._team_name = team_name
        self._recipient = recipient
        self._poll_interval = inbox_poll_interval
        self._runner_id: str | None = None
        self._pipeline_id: str | None = None

        if tasks_dir is not None:
            self._tasks_dir = tasks_dir
        else:
            self._tasks_dir = os.path.expanduser(f"~/.claude/tasks/{team_name}")

        # Outbox: messages FROM this runner TO team-lead
        # Inbox: messages TO this runner FROM team-lead
        self._outbox_dir = os.path.join(self._tasks_dir, "runner-outbox")
        self._inbox_dir = os.path.join(self._tasks_dir, "runner-inbox")

    def register(self, runner_id: str, pipeline_id: str) -> None:
        """Register runner and create inbox/outbox directories."""
        self._runner_id = runner_id
        self._pipeline_id = pipeline_id
        os.makedirs(self._outbox_dir, exist_ok=True)
        os.makedirs(self._inbox_dir, exist_ok=True)

    def unregister(self) -> None:
        """Signal clean shutdown to team-lead."""
        try:
            self.send_signal(
                "RUNNER_UNREGISTERED",
                payload={"runner_id": self._runner_id},
            )
        except ChannelError:
            pass  # Best effort

    def send_signal(
        self,
        signal_type: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: str = "normal",
    ) -> None:
        """Write a signal message to the outbox directory."""
        if not self._runner_id:
            raise ChannelError(
                "Runner not registered. Call register() before send_signal()."
            )

        os.makedirs(self._outbox_dir, exist_ok=True)

        message = {
            "type": "signal",
            "signal_type": signal_type,
            "payload": payload or {},
            "sender": self._runner_id,
            "recipient": self._recipient,
            "pipeline_id": self._pipeline_id,
            "priority": priority,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Write to timestamped file so multiple signals don't clobber each other
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{ts}_{signal_type}.json"
        filepath = os.path.join(self._outbox_dir, filename)

        try:
            with open(filepath, "w") as f:
                json.dump(message, f, indent=2)
        except OSError as exc:
            raise ChannelError(
                f"Failed to write signal to outbox: {exc}"
            ) from exc

    def receive_message(
        self,
        timeout: float = 0.0,
    ) -> ChannelMessage | None:
        """Poll the inbox directory for pending messages."""
        deadline = time.monotonic() + timeout

        while True:
            msg = self._read_oldest_inbox_message()
            if msg is not None:
                return msg

            if time.monotonic() >= deadline:
                return None

            time.sleep(min(self._poll_interval, max(0, deadline - time.monotonic())))

    def _read_oldest_inbox_message(self) -> ChannelMessage | None:
        """Read and consume the oldest message from the inbox."""
        if not os.path.isdir(self._inbox_dir):
            return None

        try:
            files = sorted(
                f for f in os.listdir(self._inbox_dir) if f.endswith(".json")
            )
        except OSError:
            return None

        if not files:
            return None

        oldest = os.path.join(self._inbox_dir, files[0])
        try:
            with open(oldest) as f:
                data = json.load(f)
            # Consume the message by removing it
            os.remove(oldest)
            return self._parse_inbox_message(data)
        except (OSError, json.JSONDecodeError):
            return None

    def _parse_inbox_message(self, data: dict[str, Any]) -> ChannelMessage:
        """Convert a raw inbox JSON dict to a ChannelMessage."""
        msg_type = data.get("type", "guidance")
        # Map known native-teams message types
        if msg_type == "shutdown_request":
            msg_type = "shutdown"
        elif msg_type == "approval_granted":
            msg_type = "approval"
        elif msg_type == "approval_rejected":
            msg_type = "override"

        return ChannelMessage(
            sender=data.get("sender", self._recipient),
            content=data.get("content", ""),
            message_type=msg_type,
            payload=data.get("payload", data),
        )
