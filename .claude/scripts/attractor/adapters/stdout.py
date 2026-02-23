#!/usr/bin/env python3
"""Stdout Channel Adapter.

A simple adapter that prints signals to stdout and reads messages from stdin.
Intended for CLI/POC runs where no real channel infrastructure is needed.

This adapter is automatically selected when running poc_pipeline_runner.py
without the --channel flag.

Usage:
    adapter = StdoutAdapter()
    adapter.register("runner-poc", "PRD-EXAMPLE-001")
    adapter.send_signal("RUNNER_STARTED", payload={"pipeline": "PRD-EXAMPLE-001"})
    # Signals appear on stdout; receive_message() always returns None immediately.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

from .base import ChannelAdapter, ChannelMessage


class StdoutAdapter(ChannelAdapter):
    """Trivial adapter that writes signals to stdout.

    receive_message() always returns None (no upstream in POC mode).
    Useful for local testing and the POC scenario runner.
    """

    def __init__(self, prefix: str = "[RUNNER]") -> None:
        self._prefix = prefix
        self._runner_id: str | None = None

    def register(self, runner_id: str, pipeline_id: str) -> None:
        self._runner_id = runner_id
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(
            f"{self._prefix} {ts} REGISTERED runner={runner_id} pipeline={pipeline_id}",
            flush=True,
        )

    def unregister(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"{self._prefix} {ts} UNREGISTERED runner={self._runner_id}", flush=True)

    def send_signal(
        self,
        signal_type: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: str = "normal",
    ) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        priority_tag = " [URGENT]" if priority == "urgent" else ""
        payload_str = ""
        if payload:
            payload_str = f" {json.dumps(payload, separators=(',', ':'))}"
        print(
            f"{self._prefix} {ts}{priority_tag} {signal_type}{payload_str}",
            flush=True,
        )

    def receive_message(
        self,
        timeout: float = 0.0,
    ) -> ChannelMessage | None:
        # POC mode: no upstream messages
        return None
