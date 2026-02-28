"""Engine events package — public re-exports.

Exports the canonical types and emitter protocol so call sites can import
from one stable namespace::

    from cobuilder.engine.events import (
        PipelineEvent, EventBuilder, EventEmitter,
        CompositeEmitter, NullEmitter, build_emitter,
    )
"""
from __future__ import annotations

from cobuilder.engine.events.types import (
    EventBuilder,
    EventType,
    PipelineEvent,
    SpanConfig,
)
from cobuilder.engine.events.emitter import (
    CompositeEmitter,
    EventBusConfig,
    EventEmitter,
    NullEmitter,
    build_emitter,
)

__all__ = [
    # types
    "PipelineEvent",
    "EventType",
    "EventBuilder",
    "SpanConfig",
    # emitter
    "EventEmitter",
    "CompositeEmitter",
    "NullEmitter",
    "EventBusConfig",
    "build_emitter",
]
