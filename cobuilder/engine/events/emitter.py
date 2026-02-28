"""EventEmitter protocol, CompositeEmitter, NullEmitter, and build_emitter factory.

The emitter protocol is structural — any class implementing ``emit()`` and
``aclose()`` qualifies without subclassing.  ``CompositeEmitter`` fans out to
all backends concurrently via ``asyncio.gather(return_exceptions=True)`` so
a single failing backend never blocks the pipeline execution loop.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, runtime_checkable

from typing import Protocol

if TYPE_CHECKING:
    from cobuilder.engine.events.types import PipelineEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventEmitter Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class EventEmitter(Protocol):
    """Structural protocol for pipeline event backends.

    Any object implementing ``emit()`` and ``aclose()`` satisfies this
    protocol — no subclassing required.
    """

    async def emit(self, event: PipelineEvent) -> None:
        """Emit one pipeline event.

        Must not raise.  Backend failures should be caught internally and
        logged at WARNING level without propagating to the execution loop.
        """
        ...

    async def aclose(self) -> None:
        """Flush and close any open resources (file handles, spans).

        Called once at pipeline completion or on fatal failure.
        Must be idempotent — calling twice must not raise.
        """
        ...


# ---------------------------------------------------------------------------
# NullEmitter — no-op backend for testing / disabled configs
# ---------------------------------------------------------------------------

class NullEmitter:
    """No-op event emitter.  Accepts all events, stores nothing."""

    async def emit(self, event: PipelineEvent) -> None:
        return

    async def aclose(self) -> None:
        return


# ---------------------------------------------------------------------------
# CompositeEmitter — fans out to all backends concurrently
# ---------------------------------------------------------------------------

class CompositeEmitter:
    """Fan-out emitter that forwards each event to all configured backends.

    Backends are called concurrently via ``asyncio.gather(...,
    return_exceptions=True)`` so that one slow or failed backend does not
    block others.  Exceptions from individual backends are logged at WARNING
    and discarded — they must never propagate to the execution loop.
    """

    def __init__(self, backends: list[EventEmitter]) -> None:
        self._backends = list(backends)

    async def emit(self, event: PipelineEvent) -> None:
        """Emit event to all backends concurrently; swallow per-backend failures."""
        if not self._backends:
            return
        results = await asyncio.gather(
            *[b.emit(event) for b in self._backends],
            return_exceptions=True,
        )
        for backend, result in zip(self._backends, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Emitter backend %s failed on event %s: %s",
                    type(backend).__name__,
                    getattr(event, "type", "<unknown>"),
                    result,
                )

    async def aclose(self) -> None:
        """Close all backends; swallow per-backend failures."""
        if not self._backends:
            return
        await asyncio.gather(
            *[b.aclose() for b in self._backends],
            return_exceptions=True,
        )


# ---------------------------------------------------------------------------
# EventBusConfig — declarative configuration for build_emitter()
# ---------------------------------------------------------------------------

@dataclass
class EventBusConfig:
    """Configuration flags for the event bus backends."""

    logfire_enabled: bool = True
    jsonl_path: str | None = None          # None = auto-derive from run_dir
    signal_bridge_enabled: bool = True
    signals_dir: str | None = None         # None = use signal_protocol default
    sse_enabled: bool = False              # Future; no-op when False


# ---------------------------------------------------------------------------
# build_emitter — factory
# ---------------------------------------------------------------------------

def build_emitter(
    pipeline_id: str,
    run_dir: str,
    config: EventBusConfig | None = None,
) -> CompositeEmitter:
    """Construct and return a CompositeEmitter with configured backends.

    Called once per pipeline run in ``engine/runner.py`` before the execution
    loop begins.  The returned emitter must be closed via ``aclose()`` in a
    ``finally`` block regardless of pipeline outcome.

    Args:
        pipeline_id: The pipeline identifier string.
        run_dir: The run directory for the JSONL log file.
        config: Optional configuration; defaults to ``EventBusConfig()``.

    Returns:
        A ``CompositeEmitter`` wrapping the enabled backends.
    """
    if config is None:
        config = EventBusConfig()

    backends: list[EventEmitter] = []

    # JSONL backend is always constructed when run_dir is non-empty.
    if run_dir:
        import os
        from cobuilder.engine.events.jsonl_backend import JSONLEmitter
        jsonl_path = config.jsonl_path or os.path.join(run_dir, "pipeline-events.jsonl")
        backends.append(JSONLEmitter(jsonl_path))

    if config.logfire_enabled:
        try:
            from cobuilder.engine.events.logfire_backend import LogfireEmitter
            backends.append(LogfireEmitter(pipeline_id=pipeline_id))
        except ImportError:
            logger.warning("logfire not available; LogfireEmitter disabled")

    if config.signal_bridge_enabled:
        from cobuilder.engine.events.signal_bridge import SignalBridge
        backends.append(SignalBridge(
            pipeline_id=pipeline_id,
            signals_dir=config.signals_dir,
        ))

    return CompositeEmitter(backends)
