#!/usr/bin/env python3
"""Channel Adapter Abstract Base Class.

Defines the interface for all communication channels the Pipeline Runner
can use to signal System 3 and receive instructions.

The runner is agnostic about HOW it communicates — the adapter handles the
channel-specific details. This enables the runner to work in different
deployment contexts:
  - Native Agent Teams (SendMessage, via teammate protocol)
  - Stdout-only (for CLI/POC runs, prints to stdout)

Usage:
    from adapters.base import ChannelAdapter
    from adapters.stdout import StdoutAdapter

    adapter = StdoutAdapter()
    adapter.send_signal("RUNNER_STUCK", payload={"node_id": "impl_backend"})
    msg = adapter.receive_message(timeout=30)
"""

from __future__ import annotations

import abc
import dataclasses
from typing import Any


@dataclasses.dataclass
class ChannelMessage:
    """A message received from the channel."""

    sender: str
    content: str
    message_type: str  # e.g., "approval", "guidance", "override", "shutdown"
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)


class ChannelAdapter(abc.ABC):
    """Abstract base class for all Pipeline Runner communication channels.

    Subclasses implement the specific transport (message bus, native teams,
    stdout, etc.) while the runner uses the common interface.

    Design principles:
    - send_signal() is fire-and-forget: no return value, raises on hard error.
    - receive_message() returns None on timeout (non-blocking by default).
    - All methods are synchronous; async variants are for Phase 3.
    """

    @abc.abstractmethod
    def send_signal(
        self,
        signal_type: str,
        payload: dict[str, Any] | None = None,
        *,
        priority: str = "normal",
    ) -> None:
        """Send a signal to the upstream controller (System 3).

        Args:
            signal_type: Semantic signal name. Convention: UPPER_SNAKE_CASE.
                Examples:
                    "RUNNER_STARTED"       - Runner has loaded pipeline and begun
                    "NODE_SPAWNED"         - Orchestrator spawned for a codergen node
                    "NODE_IMPL_COMPLETE"   - Implementation finished; dispatching validation
                    "NODE_VALIDATED"       - Node has been validated; advancing
                    "NODE_FAILED"          - Node failed; retrying or escalating
                    "RUNNER_STUCK"         - No progress possible; needs S3 guidance
                    "AWAITING_APPROVAL"    - Business gate reached; S3 approval required
                    "RUNNER_COMPLETE"      - Exit node reached; pipeline done
                    "RUNNER_ERROR"         - Unexpected error; runner cannot continue

            payload: Optional structured data accompanying the signal. Keys vary by
                signal_type; common keys: node_id, pipeline_id, reason, retry_count,
                worker_type, evidence, error.

            priority: "normal" (default) or "urgent". Urgent signals bypass queuing
                where the transport supports it.

        Raises:
            ChannelError: If the transport cannot deliver the signal (hard failure).
        """

    @abc.abstractmethod
    def receive_message(
        self,
        timeout: float = 0.0,
    ) -> ChannelMessage | None:
        """Receive the next pending message from the upstream controller.

        Args:
            timeout: Seconds to wait for a message. 0.0 (default) = non-blocking.
                     Use float("inf") to block indefinitely (not recommended).

        Returns:
            A ChannelMessage if one is available, or None if timeout elapsed.

        Raises:
            ChannelError: If the transport is in an unrecoverable error state.
        """

    @abc.abstractmethod
    def register(self, runner_id: str, pipeline_id: str) -> None:
        """Register this runner instance with the channel.

        Called once at startup. Allows the channel to route messages to this
        specific runner instance when multiple runners are active.

        Args:
            runner_id: Unique identifier for this runner instance (e.g., "runner-abc123").
            pipeline_id: The pipeline this runner manages (e.g., "PRD-AUTH-001").
        """

    @abc.abstractmethod
    def unregister(self) -> None:
        """Unregister this runner from the channel.

        Called at clean shutdown. Frees channel resources and notifies
        upstream that this runner is no longer active.
        """

    # --- Optional convenience methods (default implementations) ---

    def send_heartbeat(self, status: str, current_node: str | None = None) -> None:
        """Send a periodic heartbeat to indicate the runner is alive.

        Default implementation sends a RUNNER_HEARTBEAT signal. Subclasses
        may override with a lighter-weight mechanism.

        Args:
            status: Human-readable status (e.g., "executing node impl_backend").
            current_node: Node ID currently being processed, if any.
        """
        payload: dict[str, Any] = {"status": status}
        if current_node:
            payload["current_node"] = current_node
        self.send_signal("RUNNER_HEARTBEAT", payload=payload)

    def request_approval(
        self,
        node_id: str,
        gate_type: str,
        acceptance_criteria: str,
        evidence_summary: str,
    ) -> None:
        """Signal that a business gate requires System 3 approval.

        Wraps send_signal with the structured payload expected for approval requests.

        Args:
            node_id: The validation gate node requiring approval.
            gate_type: "technical", "business", or "e2e".
            acceptance_criteria: The criteria that must be met.
            evidence_summary: Summary of evidence produced so far.
        """
        self.send_signal(
            "AWAITING_APPROVAL",
            payload={
                "node_id": node_id,
                "gate_type": gate_type,
                "acceptance_criteria": acceptance_criteria,
                "evidence_summary": evidence_summary,
            },
            priority="urgent",
        )


class ChannelError(Exception):
    """Raised when the channel transport encounters an unrecoverable error."""
