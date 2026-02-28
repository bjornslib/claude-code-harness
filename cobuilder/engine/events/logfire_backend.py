"""Logfire backend — manages pipeline and node spans in Logfire.

Maintains a two-level span hierarchy:

    logfire.span("pipeline.{pipeline_id}") → pipeline-level span
        logfire.span("node.{node_id}") → per-node child spans

The pipeline span is opened on ``pipeline.started`` and closed on
``pipeline.completed`` or ``pipeline.failed``.  Each node span is opened on
``node.started`` and closed on ``node.completed`` or ``node.failed``.

All logfire calls are wrapped in try/except.  If logfire is unreachable or
raises on construction, the emitter operates in no-op mode for the rest of
the pipeline run.
"""
from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from cobuilder.engine.events.types import PipelineEvent, SpanConfig

logger = logging.getLogger(__name__)

try:
    import logfire as _logfire
    _LOGFIRE_AVAILABLE = True
except ImportError:
    _logfire = None  # type: ignore[assignment]
    _LOGFIRE_AVAILABLE = False


class LogfireEmitter:
    """Logfire event backend.

    Manages a pipeline-level span and a map of active node-level spans.  All
    logfire operations are guarded by try/except — a logfire failure must
    never propagate to the execution loop.

    State:
        ``_pipeline_span``: The open pipeline-level logfire span, or ``None``.
        ``_node_spans``: Dict mapping ``node_id`` to the open node span.
        ``_span_config``: ``SpanConfig`` controlling span naming and attribute keys.
        ``_failed``: Set to ``True`` after the first logfire failure; subsequent
                     calls become no-ops.
    """

    def __init__(
        self,
        pipeline_id: str,
        span_config: SpanConfig | None = None,
    ) -> None:
        self._pipeline_id = pipeline_id
        self._span_config = span_config or SpanConfig()
        self._pipeline_span: Any = None
        self._node_spans: dict[str, Any] = {}
        self._pipeline_span_ctx: Any = None  # context manager for pipeline span
        self._node_span_ctxs: dict[str, Any] = {}
        self._failed = False
        self._pipeline_closed = False

    def _check_available(self) -> bool:
        """Return True if logfire is importable and not in failed state."""
        return _LOGFIRE_AVAILABLE and not self._failed

    async def emit(self, event: PipelineEvent) -> None:
        """Dispatch event to the appropriate span operation."""
        if not self._check_available():
            return

        event_type = event.type
        try:
            if event_type == "pipeline.started":
                self._handle_pipeline_started(event)
            elif event_type == "pipeline.completed":
                self._handle_pipeline_completed(event)
            elif event_type == "pipeline.failed":
                self._handle_pipeline_failed(event)
            elif event_type == "node.started":
                self._handle_node_started(event)
            elif event_type == "node.completed":
                self._handle_node_completed(event)
            elif event_type == "node.failed":
                self._handle_node_failed(event)
            # All other event types are silently ignored by this backend.
        except Exception as exc:  # noqa: BLE001
            if not self._failed:
                logger.warning(
                    "LogfireEmitter: logfire operation failed for event %s: %s",
                    event_type,
                    exc,
                )
                self._failed = True

    def _handle_pipeline_started(self, event: PipelineEvent) -> None:
        """Open a pipeline-level logfire span."""
        span_name = self._span_config.pipeline_span_name.format(
            pipeline_id=self._pipeline_id
        )
        ctx = _logfire.span(span_name)
        self._pipeline_span_ctx = ctx
        self._pipeline_span = ctx.__enter__()

        data = event.data
        with suppress(Exception):
            self._pipeline_span.set_attribute("pipeline_id", self._pipeline_id)
        with suppress(Exception):
            self._pipeline_span.set_attribute("dot_path", data.get("dot_path", ""))
        with suppress(Exception):
            self._pipeline_span.set_attribute("node_count", data.get("node_count", 0))

    def _handle_pipeline_completed(self, event: PipelineEvent) -> None:
        """Set completion attributes and close the pipeline span."""
        if self._pipeline_span is not None:
            data = event.data
            with suppress(Exception):
                self._pipeline_span.set_attribute("duration_ms", data.get("duration_ms", 0))
            with suppress(Exception):
                self._pipeline_span.set_attribute("total_tokens", data.get("total_tokens", 0))
            with suppress(Exception):
                self._pipeline_span.set_attribute("outcome_status", "completed")
        self._close_pipeline_span(exc=None)

    def _handle_pipeline_failed(self, event: PipelineEvent) -> None:
        """Record exception on the pipeline span and close it."""
        if self._pipeline_span is not None:
            data = event.data
            with suppress(Exception):
                self._pipeline_span.set_attribute("error_type", data.get("error_type", ""))
            with suppress(Exception):
                self._pipeline_span.set_attribute("error_message", data.get("error_message", ""))
            with suppress(Exception):
                self._pipeline_span.set_attribute("outcome_status", "failed")
        self._close_pipeline_span(exc=RuntimeError(event.data.get("error_message", "pipeline failed")))

    def _handle_node_started(self, event: PipelineEvent) -> None:
        """Open a node-level child span under the pipeline span."""
        node_id = event.node_id
        if node_id is None:
            return

        span_name = self._span_config.node_span_name.format(node_id=node_id)
        ctx = _logfire.span(span_name)
        self._node_span_ctxs[node_id] = ctx
        node_span = ctx.__enter__()
        self._node_spans[node_id] = node_span

        data = event.data
        with suppress(Exception):
            node_span.set_attribute("node_id", node_id)
        with suppress(Exception):
            node_span.set_attribute("handler_type", data.get("handler_type", ""))
        with suppress(Exception):
            node_span.set_attribute("visit_count", data.get("visit_count", 0))

    def _handle_node_completed(self, event: PipelineEvent) -> None:
        """Set completion attributes on the node span and close it."""
        node_id = event.node_id
        if node_id is None:
            return

        node_span = self._node_spans.get(node_id)
        if node_span is not None:
            data = event.data
            with suppress(Exception):
                node_span.set_attribute("outcome_status", data.get("outcome_status", ""))
            with suppress(Exception):
                node_span.set_attribute("duration_ms", data.get("duration_ms", 0))
            with suppress(Exception):
                node_span.set_attribute("tokens_used", data.get("tokens_used", 0))

        self._close_node_span(node_id, exc=None)

    def _handle_node_failed(self, event: PipelineEvent) -> None:
        """Record failure on the node span and close it."""
        node_id = event.node_id
        if node_id is None:
            return

        node_span = self._node_spans.get(node_id)
        if node_span is not None:
            data = event.data
            with suppress(Exception):
                node_span.set_attribute("outcome_status", "failed")
            with suppress(Exception):
                node_span.set_attribute("goal_gate", data.get("goal_gate", False))
            with suppress(Exception):
                node_span.set_attribute("error_type", data.get("error_type", ""))

        self._close_node_span(
            node_id,
            exc=RuntimeError(event.data.get("error_type", "node failed")),
        )

    def _close_pipeline_span(self, exc: BaseException | None) -> None:
        """Exit the pipeline span context manager."""
        if self._pipeline_closed or self._pipeline_span_ctx is None:
            return
        self._pipeline_closed = True
        try:
            if exc is not None:
                self._pipeline_span_ctx.__exit__(type(exc), exc, None)
            else:
                self._pipeline_span_ctx.__exit__(None, None, None)
        except Exception as close_exc:  # noqa: BLE001
            logger.warning("LogfireEmitter: error closing pipeline span: %s", close_exc)
        finally:
            self._pipeline_span = None

    def _close_node_span(self, node_id: str, exc: BaseException | None) -> None:
        """Exit the node span context manager for ``node_id``."""
        ctx = self._node_span_ctxs.pop(node_id, None)
        self._node_spans.pop(node_id, None)
        if ctx is None:
            return
        try:
            if exc is not None:
                ctx.__exit__(type(exc), exc, None)
            else:
                ctx.__exit__(None, None, None)
        except Exception as close_exc:  # noqa: BLE001
            logger.warning("LogfireEmitter: error closing node span %s: %s", node_id, close_exc)

    async def aclose(self) -> None:
        """Close any open spans.  Idempotent — safe to call multiple times."""
        if not _LOGFIRE_AVAILABLE:
            return

        # Close any still-open node spans
        for node_id in list(self._node_span_ctxs.keys()):
            with suppress(Exception):
                self._close_node_span(node_id, exc=None)

        # Close pipeline span if still open
        with suppress(Exception):
            self._close_pipeline_span(exc=None)
