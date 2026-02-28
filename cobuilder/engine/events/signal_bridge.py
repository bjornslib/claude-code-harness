"""SignalBridge backend — translates a subset of pipeline events to signal files.

Only 4 event types are translated; all others are silently ignored.  The
mapping follows SD Section 2.6:

    pipeline.completed  → NODE_COMPLETE
    pipeline.failed     → ORCHESTRATOR_CRASHED
    node.failed (goal_gate=True) → VIOLATION
    loop.detected       → ORCHESTRATOR_STUCK

Signal file I/O is delegated to ``signal_protocol.write_signal()`` which
uses an atomic write-then-rename pattern.  ``SignalBridge`` itself holds no
open file handles or span state — it is fully reentrant.
"""
from __future__ import annotations

import logging

from cobuilder.engine.events.types import PipelineEvent
from cobuilder.pipeline.signal_protocol import (
    NODE_COMPLETE,
    ORCHESTRATOR_CRASHED,
    ORCHESTRATOR_STUCK,
    VIOLATION,
    write_signal,
)

logger = logging.getLogger(__name__)

# Source identifier written into every signal payload
_SOURCE = "engine"
_TARGET = "guardian"


class SignalBridge:
    """Translates critical pipeline events to guardian signal files.

    The bridge is stateless beyond ``pipeline_id`` and ``signals_dir``.
    ``aclose()`` is a no-op — the bridge holds no open resources.
    """

    def __init__(
        self,
        pipeline_id: str,
        signals_dir: str | None = None,
    ) -> None:
        """Initialise the bridge.

        Args:
            pipeline_id: The pipeline identifier, included in every signal
                         payload.
            signals_dir: Override the default signals directory.  Passed
                         through to ``write_signal()``; ``None`` uses the
                         signal_protocol default resolution.
        """
        self._pipeline_id = pipeline_id
        self._signals_dir = signals_dir

    async def emit(self, event: PipelineEvent) -> None:
        """Translate eligible event types to signal files; ignore all others.

        Eligible types: ``pipeline.completed``, ``pipeline.failed``,
        ``node.failed`` (only when ``data["goal_gate"] is True``),
        ``loop.detected``.

        All other event types produce no signal file and return silently.
        """
        event_type = event.type

        try:
            if event_type == "pipeline.completed":
                write_signal(
                    source=_SOURCE,
                    target=_TARGET,
                    signal_type=NODE_COMPLETE,
                    payload={
                        "pipeline_id": self._pipeline_id,
                        "node_id": event.node_id,
                        "duration_ms": event.data.get("duration_ms"),
                        "total_tokens": event.data.get("total_tokens"),
                    },
                    signals_dir=self._signals_dir,
                )

            elif event_type == "pipeline.failed":
                write_signal(
                    source=_SOURCE,
                    target=_TARGET,
                    signal_type=ORCHESTRATOR_CRASHED,
                    payload={
                        "pipeline_id": self._pipeline_id,
                        "node_id": event.data.get("last_node_id"),
                        "error_type": event.data.get("error_type"),
                        "error_message": event.data.get("error_message"),
                    },
                    signals_dir=self._signals_dir,
                )

            elif event_type == "node.failed" and event.data.get("goal_gate"):
                write_signal(
                    source=_SOURCE,
                    target=_TARGET,
                    signal_type=VIOLATION,
                    payload={
                        "pipeline_id": self._pipeline_id,
                        "node_id": event.node_id,
                        "error_type": event.data.get("error_type"),
                        "reason": event.data.get("error_type", "goal_gate violation"),
                    },
                    signals_dir=self._signals_dir,
                )

            elif event_type == "loop.detected":
                write_signal(
                    source=_SOURCE,
                    target=_TARGET,
                    signal_type=ORCHESTRATOR_STUCK,
                    payload={
                        "pipeline_id": self._pipeline_id,
                        "node_id": event.node_id,
                        "visit_count": event.data.get("visit_count"),
                        "limit": event.data.get("limit"),
                        "duration": None,
                        "last_output": event.data.get("pattern_detected"),
                    },
                    signals_dir=self._signals_dir,
                )

            # All other event types are silently ignored.

        except Exception as exc:
            logger.warning(
                "SignalBridge: failed to write signal for event %s: %s",
                event_type,
                exc,
            )

    async def aclose(self) -> None:
        """No-op.  SignalBridge holds no open resources."""
        return
