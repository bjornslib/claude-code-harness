#!/usr/bin/env python3
"""Message Bus Channel Adapter.

Implements ChannelAdapter using the mb-* CLI scripts for cross-session
communication. This adapter is used when the Pipeline Runner operates in
a separate tmux session from System 3.

The message bus uses a SQLite queue at .claude/message-bus/queue.db and
signal files at .claude/message-bus/signals/*.signal.

Usage:
    adapter = MessageBusAdapter(
        target="system3",
        session_id="runner-abc123",
    )
    adapter.register("runner-abc123", "PRD-AUTH-001")
    adapter.send_signal("RUNNER_STARTED", payload={"pipeline": "PRD-AUTH-001"})
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from .base import ChannelAdapter, ChannelError, ChannelMessage


class MessageBusAdapter(ChannelAdapter):
    """Channel adapter backed by the .claude message-bus SQLite queue.

    Uses mb-send to deliver signals and mb-recv to poll for incoming messages.
    Requires the message bus to be initialized (mb-init) before use.

    Args:
        target: The message bus instance ID to send signals to (e.g., "system3").
        session_id: This runner's session identifier (used as sender ID in mb-send).
        scripts_dir: Override path to the mb-* CLI scripts directory.
            Defaults to ~/.claude/scripts/message-bus.
    """

    def __init__(
        self,
        target: str = "system3",
        session_id: str = "pipeline-runner",
        scripts_dir: str | None = None,
    ) -> None:
        self._target = target
        self._session_id = session_id
        self._runner_id: str | None = None
        self._pipeline_id: str | None = None

        # Resolve scripts dir
        if scripts_dir is not None:
            self._scripts_dir = scripts_dir
        else:
            self._scripts_dir = os.path.expanduser("~/.claude/scripts/message-bus")

    def _mb(self, command: str, *args: str) -> subprocess.CompletedProcess:
        """Run an mb-* command."""
        script = os.path.join(self._scripts_dir, f"mb-{command}")
        cmd = [script] + list(args)
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError as exc:
            raise ChannelError(
                f"Message bus script not found: {script}. "
                "Ensure the message bus is initialized (mb-init)."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ChannelError(
                f"Message bus command timed out: mb-{command}"
            ) from exc

    def register(self, runner_id: str, pipeline_id: str) -> None:
        """Register this runner with the message bus."""
        self._runner_id = runner_id
        self._pipeline_id = pipeline_id
        result = self._mb("register", runner_id, "pipeline-runner")
        if result.returncode != 0:
            # Non-fatal: mb-register may fail if already registered
            pass  # Silently ignore

    def unregister(self) -> None:
        """Unregister from the message bus (no-op for mb — sessions expire naturally)."""
        pass

    def send_signal(
        self,
        signal_type: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: str = "normal",
    ) -> None:
        """Send a signal via mb-send."""
        message_parts = [f"SIGNAL:{signal_type}"]
        if payload:
            message_parts.append(json.dumps(payload))
        if priority == "urgent":
            message_parts.insert(0, "URGENT")
        message = " ".join(message_parts)

        result = self._mb("send", self._target, message)
        if result.returncode != 0:
            raise ChannelError(
                f"Failed to send signal {signal_type}: {result.stderr}"
            )

    def receive_message(
        self,
        timeout: float = 0.0,
    ) -> ChannelMessage | None:
        """Poll for pending messages via mb-recv."""
        deadline = time.monotonic() + timeout
        while True:
            result = self._mb("recv")
            if result.returncode == 0 and result.stdout.strip():
                raw = result.stdout.strip()
                return self._parse_message(raw)

            if time.monotonic() >= deadline:
                return None

            time.sleep(0.5)

    def _parse_message(self, raw: str) -> ChannelMessage:
        """Parse a raw mb-recv message into a ChannelMessage."""
        # Format: "SENDER: CONTENT" or just "CONTENT"
        sender = "system3"
        content = raw

        if ": " in raw:
            parts = raw.split(": ", 1)
            if len(parts) == 2:
                sender = parts[0]
                content = parts[1]

        # Try to extract type from structured messages
        message_type = "guidance"
        payload: dict[str, Any] = {}

        if content.startswith("{"):
            try:
                data = json.loads(content)
                message_type = data.get("type", "guidance")
                payload = data
                content = data.get("content", content)
            except json.JSONDecodeError:
                pass
        elif "APPROVAL_GRANTED" in content:
            message_type = "approval"
        elif "APPROVAL_REJECTED" in content:
            message_type = "override"
        elif "SHUTDOWN" in content:
            message_type = "shutdown"

        return ChannelMessage(
            sender=sender,
            content=content,
            message_type=message_type,
            payload=payload,
        )
