"""Tests for CompositeEmitter, NullEmitter, EventEmitter protocol, and build_emitter."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from cobuilder.engine.events.emitter import (
    CompositeEmitter,
    EventBusConfig,
    EventEmitter,
    NullEmitter,
    build_emitter,
)
from cobuilder.engine.events.types import EventBuilder, PipelineEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event() -> PipelineEvent:
    return EventBuilder.pipeline_started("test-pipe", "g.dot", 3)


class _RecordingEmitter:
    """Records every emit() call for assertion purposes."""

    def __init__(self) -> None:
        self.received: list[PipelineEvent] = []
        self.closed = False

    async def emit(self, event: PipelineEvent) -> None:
        self.received.append(event)

    async def aclose(self) -> None:
        self.closed = True


class _FailingEmitter:
    """Always raises on emit()."""

    def __init__(self) -> None:
        self.closed = False

    async def emit(self, event: PipelineEvent) -> None:
        raise RuntimeError("intentional backend failure")

    async def aclose(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# EventEmitter Protocol
# ---------------------------------------------------------------------------

class TestEventEmitterProtocol:
    def test_null_emitter_satisfies_protocol(self) -> None:
        emitter = NullEmitter()
        assert isinstance(emitter, EventEmitter)

    def test_recording_emitter_satisfies_protocol(self) -> None:
        emitter = _RecordingEmitter()
        assert isinstance(emitter, EventEmitter)

    def test_failing_emitter_satisfies_protocol(self) -> None:
        assert isinstance(_FailingEmitter(), EventEmitter)


# ---------------------------------------------------------------------------
# NullEmitter
# ---------------------------------------------------------------------------

class TestNullEmitter:
    def test_emit_accepts_all_events(self) -> None:
        emitter = NullEmitter()
        evt = _make_event()
        asyncio.get_event_loop().run_until_complete(emitter.emit(evt))

    def test_aclose_is_idempotent(self) -> None:
        emitter = NullEmitter()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(emitter.aclose())
        loop.run_until_complete(emitter.aclose())  # second call must not raise


# ---------------------------------------------------------------------------
# CompositeEmitter
# ---------------------------------------------------------------------------

class TestCompositeEmitter:

    def _run(self, coro) -> Any:
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_fans_out_to_all_backends(self) -> None:
        backends = [_RecordingEmitter() for _ in range(3)]
        composite = CompositeEmitter(backends)
        evt = _make_event()
        self._run(composite.emit(evt))
        for b in backends:
            assert len(b.received) == 1
            assert b.received[0] is evt

    def test_failure_isolation(self) -> None:
        """One failing backend must not prevent others from receiving the event."""
        good1 = _RecordingEmitter()
        bad = _FailingEmitter()
        good2 = _RecordingEmitter()
        composite = CompositeEmitter([good1, bad, good2])
        evt = _make_event()
        # Should not raise
        self._run(composite.emit(evt))
        assert len(good1.received) == 1
        assert len(good2.received) == 1

    def test_failure_logged_as_warning(self, caplog) -> None:
        import logging
        bad = _FailingEmitter()
        composite = CompositeEmitter([bad])
        evt = _make_event()
        with caplog.at_level(logging.WARNING, logger="cobuilder.engine.events.emitter"):
            self._run(composite.emit(evt))
        assert any("intentional backend failure" in r.message or "_FailingEmitter" in r.message
                   for r in caplog.records)

    def test_aclose_calls_all_backends(self) -> None:
        backends = [_RecordingEmitter() for _ in range(3)]
        composite = CompositeEmitter(backends)
        self._run(composite.aclose())
        for b in backends:
            assert b.closed is True

    def test_aclose_isolates_failures(self) -> None:
        """aclose() with a failing backend must still close the remaining ones."""

        class _FailClose(_RecordingEmitter):
            async def aclose(self) -> None:
                raise OSError("aclose failed")

        good = _RecordingEmitter()
        bad = _FailClose()
        composite = CompositeEmitter([good, bad])
        # Should not raise
        self._run(composite.aclose())
        assert good.closed is True

    def test_empty_backends_no_error(self) -> None:
        composite = CompositeEmitter([])
        evt = _make_event()
        self._run(composite.emit(evt))   # no-op, must not raise
        self._run(composite.aclose())

    def test_multiple_events_in_order(self) -> None:
        backend = _RecordingEmitter()
        composite = CompositeEmitter([backend])
        evts = [EventBuilder.pipeline_started("p", "g.dot", i) for i in range(5)]
        for evt in evts:
            self._run(composite.emit(evt))
        assert len(backend.received) == 5
        for i, (received, expected) in enumerate(zip(backend.received, evts)):
            assert received is expected, f"Event {i} mismatch"


# ---------------------------------------------------------------------------
# build_emitter factory
# ---------------------------------------------------------------------------

class TestBuildEmitter:

    def test_returns_composite_emitter(self, tmp_path) -> None:
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
        )
        result = build_emitter("p", str(tmp_path), config)
        assert isinstance(result, CompositeEmitter)

    def test_jsonl_backend_included_when_run_dir_given(self, tmp_path) -> None:
        from cobuilder.engine.events.jsonl_backend import JSONLEmitter
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
        )
        emitter = build_emitter("p", str(tmp_path), config)
        backend_types = [type(b).__name__ for b in emitter._backends]
        assert "JSONLEmitter" in backend_types

    def test_signal_bridge_included_when_enabled(self, tmp_path) -> None:
        from cobuilder.engine.events.signal_bridge import SignalBridge
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=True,
            signals_dir=str(tmp_path / "signals"),
        )
        emitter = build_emitter("p", str(tmp_path), config)
        backend_types = [type(b).__name__ for b in emitter._backends]
        assert "SignalBridge" in backend_types

    def test_logfire_backend_included_when_enabled(self, tmp_path) -> None:
        from cobuilder.engine.events.logfire_backend import LogfireEmitter
        config = EventBusConfig(
            logfire_enabled=True,
            signal_bridge_enabled=False,
        )
        emitter = build_emitter("p", str(tmp_path), config)
        backend_types = [type(b).__name__ for b in emitter._backends]
        assert "LogfireEmitter" in backend_types

    def test_only_jsonl_when_all_others_disabled(self, tmp_path) -> None:
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
        )
        emitter = build_emitter("p", str(tmp_path), config)
        backend_types = [type(b).__name__ for b in emitter._backends]
        assert "JSONLEmitter" in backend_types
        assert "LogfireEmitter" not in backend_types
        assert "SignalBridge" not in backend_types

    def test_default_config_when_none_given(self, tmp_path) -> None:
        """Default config enables logfire, jsonl, and signal bridge."""
        emitter = build_emitter("p", str(tmp_path), config=None)
        assert isinstance(emitter, CompositeEmitter)
        # At minimum we expect backends to be present
        assert len(emitter._backends) > 0

    def test_custom_jsonl_path(self, tmp_path) -> None:
        custom_path = str(tmp_path / "custom-events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=custom_path,
        )
        emitter = build_emitter("p", str(tmp_path), config)
        from cobuilder.engine.events.jsonl_backend import JSONLEmitter
        jsonl_backends = [b for b in emitter._backends if isinstance(b, JSONLEmitter)]
        assert len(jsonl_backends) == 1
        assert jsonl_backends[0]._path == custom_path
