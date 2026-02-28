"""LogfireMiddleware — emits node.started/completed/failed events and manages spans.

This middleware is the primary source of node lifecycle events.  It:
1. Emits node.started via request.emitter before calling next.
2. Opens a logfire.span for the node handler execution.
3. Calls next(request) inside the span context.
4. Emits node.completed or node.failed after next returns.
5. Sets span attributes: outcome_status, duration_ms, handler_type.
6. On exception: closes the span with record_exception=True and re-raises.

If logfire is not installed or is unavailable, the middleware operates in
no-op span mode (still emits events, just without Logfire spans).
"""
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable, TYPE_CHECKING

from cobuilder.engine.middleware.chain import HandlerRequest

if TYPE_CHECKING:
    from cobuilder.engine.outcome import Outcome

logger = logging.getLogger(__name__)

# Attempt to import logfire; degrade gracefully if unavailable.
try:
    import logfire as _logfire
    _LOGFIRE_AVAILABLE = True
except ImportError:
    _logfire = None  # type: ignore[assignment]
    _LOGFIRE_AVAILABLE = False
    logger.warning("logfire not available; LogfireMiddleware will run in no-op span mode")


class _NullSpan:
    """Context manager that does nothing — used when logfire is unavailable."""

    def __enter__(self) -> "_NullSpan":
        return self

    def __exit__(self, *args: object) -> None:
        return

    def set_attribute(self, key: str, value: object) -> None:
        return

    def record_exception(self, exc: BaseException) -> None:
        return


class LogfireMiddleware:
    """Emits node lifecycle events and manages per-node Logfire spans.

    Designed to be the outermost middleware in the chain so that the span
    covers the full duration of the handler invocation including all inner
    middleware.

    Args:
        span_name_template: f-string template for span names.
                            Defaults to ``"handler.{node_id}"``.
    """

    def __init__(self, span_name_template: str = "handler.{node_id}") -> None:
        self._span_name_template = span_name_template

    async def __call__(
        self,
        request: HandlerRequest,
        next: Callable[[HandlerRequest], Awaitable["Outcome"]],
    ) -> "Outcome":
        """Emit events and manage span around the handler execution."""
        from cobuilder.engine.events.types import EventBuilder
        from cobuilder.engine.outcome import OutcomeStatus

        node_id = request.node.id
        pipeline_id = request.pipeline_id
        handler_type = request.node.handler_type
        visit_count = request.visit_count
        emitter = request.emitter

        # Emit node.started BEFORE calling next.
        if emitter is not None:
            try:
                await emitter.emit(EventBuilder.node_started(
                    pipeline_id=pipeline_id,
                    node_id=node_id,
                    handler_type=handler_type,
                    visit_count=visit_count,
                ))
            except Exception as exc:
                logger.warning("Failed to emit node.started for %s: %s", node_id, exc)

        span_name = self._span_name_template.format(node_id=node_id)
        start_time = time.monotonic()

        # Open span (or null span if logfire unavailable).
        if _LOGFIRE_AVAILABLE and _logfire is not None:
            span_ctx = _logfire.span(span_name)
        else:
            span_ctx = _NullSpan()

        with span_ctx as span:
            try:
                outcome = await next(request)
            except Exception as exc:
                duration_ms = (time.monotonic() - start_time) * 1000.0
                # Record exception on span.
                if hasattr(span, "record_exception"):
                    try:
                        span.record_exception(exc)
                    except Exception:
                        pass
                # Emit node.failed
                if emitter is not None:
                    try:
                        await emitter.emit(EventBuilder.node_failed(
                            pipeline_id=pipeline_id,
                            node_id=node_id,
                            error_type=type(exc).__name__,
                            goal_gate=request.node.goal_gate,
                            retry_target=request.node.retry_target,
                        ))
                    except Exception as emit_exc:
                        logger.warning(
                            "Failed to emit node.failed for %s: %s", node_id, emit_exc
                        )
                raise

            duration_ms = (time.monotonic() - start_time) * 1000.0

            # Set span attributes.
            if hasattr(span, "set_attribute"):
                try:
                    span.set_attribute("node_id", node_id)
                    span.set_attribute("handler_type", handler_type)
                    span.set_attribute("visit_count", visit_count)
                    span.set_attribute("outcome_status", outcome.status.value)
                    span.set_attribute("duration_ms", duration_ms)
                    tokens_used = int(outcome.metadata.get("tokens_used", 0))
                    span.set_attribute("tokens_used", tokens_used)
                    span.set_attribute("goal_gate", request.node.goal_gate)
                except Exception:
                    pass

        # Get active span ID for correlation (best-effort).
        span_id: str | None = None
        if _LOGFIRE_AVAILABLE and _logfire is not None:
            try:
                active = _logfire.get_current_span()
                if active is not None and hasattr(active, "context") and active.context is not None:
                    span_id = str(active.context.span_id)
            except Exception:
                pass

        # Emit node.completed or node.failed based on outcome status.
        if emitter is not None:
            try:
                if outcome.status == OutcomeStatus.FAILURE:
                    await emitter.emit(EventBuilder.node_failed(
                        pipeline_id=pipeline_id,
                        node_id=node_id,
                        error_type="FAILURE",
                        goal_gate=request.node.goal_gate,
                        retry_target=request.node.retry_target,
                    ))
                else:
                    tokens_used = int(outcome.metadata.get("tokens_used", 0))
                    await emitter.emit(EventBuilder.node_completed(
                        pipeline_id=pipeline_id,
                        node_id=node_id,
                        outcome_status=outcome.status.value,
                        duration_ms=duration_ms,
                        tokens_used=tokens_used,
                        span_id=span_id,
                    ))
            except Exception as emit_exc:
                logger.warning(
                    "Failed to emit node completion event for %s: %s", node_id, emit_exc
                )

        return outcome
