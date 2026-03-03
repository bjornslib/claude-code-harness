"""End-to-end integration tests for the E4 event bus and middleware subsystems.

Tests cover:
1. build_emitter() backend assembly from EventBusConfig flags
2. JSONL round-trip: emit events, read back, verify all present
3. CompositeEmitter fan-out to multiple recording backends
4. Full middleware chain (all 4 E4 middlewares) composition and execution
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.events.emitter import (
    CompositeEmitter,
    EventBusConfig,
    NullEmitter,
    build_emitter,
)
from cobuilder.engine.events.jsonl_backend import JSONLEmitter
from cobuilder.engine.events.types import EventBuilder, PipelineEvent
from cobuilder.engine.graph import Node
from cobuilder.engine.middleware.audit import AuditMiddleware
from cobuilder.engine.middleware.chain import HandlerRequest, compose_middleware
from cobuilder.engine.middleware.logfire import LogfireMiddleware
from cobuilder.engine.middleware.retry import RetryMiddleware
from cobuilder.engine.middleware.token_counter import TokenCountingMiddleware
from cobuilder.engine.outcome import Outcome, OutcomeStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine synchronously — matches pattern used across unit tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


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
    """Always raises on emit() — used for isolation tests."""

    async def emit(self, event: PipelineEvent) -> None:
        raise RuntimeError("intentional backend failure")

    async def aclose(self) -> None:
        pass


def _make_node(id: str = "test-node") -> Node:
    """Create a minimal Node for HandlerRequest construction."""
    return Node(id=id, shape="box", label=id)


def _make_request(
    node: Node | None = None,
    pipeline_id: str = "test-pipeline",
    emitter: Any = None,
) -> HandlerRequest:
    """Build a HandlerRequest with minimal required fields."""
    if node is None:
        node = _make_node()
    return HandlerRequest(
        node=node,
        context=PipelineContext(initial={}),
        emitter=emitter if emitter is not None else NullEmitter(),
        pipeline_id=pipeline_id,
        visit_count=1,
        attempt_number=0,
    )


class _SuccessHandler:
    """Minimal handler that always returns SUCCESS Outcome."""

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, request: HandlerRequest) -> Outcome:
        self.call_count += 1
        return Outcome(status=OutcomeStatus.SUCCESS)


class _MetadataHandler:
    """Handler that returns an Outcome with custom metadata."""

    async def execute(self, request: HandlerRequest) -> Outcome:
        return Outcome(
            status=OutcomeStatus.SUCCESS,
            metadata={"custom_key": "custom_value", "score": 42},
        )


# ---------------------------------------------------------------------------
# 1. build_emitter() with various EventBusConfig flags
# ---------------------------------------------------------------------------

class TestBuildEmitterConfigs:
    """Integration tests for build_emitter() backend assembly from config flags."""

    def test_returns_composite_emitter_type(self, tmp_path: Path) -> None:
        """build_emitter() always returns a CompositeEmitter."""
        config = EventBusConfig(logfire_enabled=False, signal_bridge_enabled=False)
        emitter = build_emitter("pipe", str(tmp_path), config)
        assert isinstance(emitter, CompositeEmitter)
        _run(emitter.aclose())

    def test_default_config_includes_jsonl_backend(self, tmp_path: Path) -> None:
        """Default config (None) always includes JSONLEmitter."""
        emitter = build_emitter("pipe", str(tmp_path), config=None)
        types = [type(b).__name__ for b in emitter._backends]
        assert "JSONLEmitter" in types
        _run(emitter.aclose())

    def test_logfire_disabled_excludes_logfire_emitter(self, tmp_path: Path) -> None:
        """logfire_enabled=False must produce no LogfireEmitter backend."""
        config = EventBusConfig(logfire_enabled=False, signal_bridge_enabled=False)
        emitter = build_emitter("pipe", str(tmp_path), config)
        types = [type(b).__name__ for b in emitter._backends]
        assert "LogfireEmitter" not in types
        _run(emitter.aclose())

    def test_signal_bridge_disabled_excludes_signal_bridge(self, tmp_path: Path) -> None:
        """signal_bridge_enabled=False must produce no SignalBridge backend."""
        config = EventBusConfig(logfire_enabled=False, signal_bridge_enabled=False)
        emitter = build_emitter("pipe", str(tmp_path), config)
        types = [type(b).__name__ for b in emitter._backends]
        assert "SignalBridge" not in types
        _run(emitter.aclose())

    def test_signal_bridge_enabled_includes_signal_bridge(self, tmp_path: Path) -> None:
        """signal_bridge_enabled=True must include SignalBridge backend."""
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=True,
            signals_dir=str(tmp_path / "signals"),
        )
        emitter = build_emitter("pipe", str(tmp_path), config)
        types = [type(b).__name__ for b in emitter._backends]
        assert "SignalBridge" in types
        _run(emitter.aclose())

    def test_custom_jsonl_path_is_used(self, tmp_path: Path) -> None:
        """Custom jsonl_path in config is passed through to JSONLEmitter."""
        custom_path = str(tmp_path / "subdir" / "custom-events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=custom_path,
        )
        emitter = build_emitter("pipe", str(tmp_path), config)
        jsonl_backends = [b for b in emitter._backends if isinstance(b, JSONLEmitter)]
        assert len(jsonl_backends) == 1
        assert jsonl_backends[0]._path == custom_path
        _run(emitter.aclose())

    def test_only_jsonl_when_optional_backends_disabled(self, tmp_path: Path) -> None:
        """When logfire and signal bridge are off, only JSONLEmitter is present."""
        config = EventBusConfig(logfire_enabled=False, signal_bridge_enabled=False)
        emitter = build_emitter("pipe", str(tmp_path), config)
        types = [type(b).__name__ for b in emitter._backends]
        assert "JSONLEmitter" in types
        assert "LogfireEmitter" not in types
        assert "SignalBridge" not in types
        _run(emitter.aclose())

    def test_multiple_backends_all_receive_events(self, tmp_path: Path) -> None:
        """build_emitter() fan-out works when signal bridge is also enabled."""
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=True,
            signals_dir=str(tmp_path / "signals"),
        )
        emitter = build_emitter("multi-backend-pipe", str(tmp_path), config)
        # Should have at least JSONLEmitter + SignalBridge
        assert len(emitter._backends) >= 2
        _run(emitter.aclose())


# ---------------------------------------------------------------------------
# 2. JSONL round-trip
# ---------------------------------------------------------------------------

class TestJSONLRoundTrip:
    """Test that events emitted via build_emitter() appear correctly in JSONL."""

    def _emit_and_close(self, emitter: CompositeEmitter, events: list) -> None:
        """Helper: emit all events then aclose."""
        async def _run_async():
            for evt in events:
                await emitter.emit(evt)
            await emitter.aclose()

        _run(_run_async())

    def test_five_event_pipeline_sequence(self, tmp_path: Path) -> None:
        """Emit 5-event pipeline sequence; all must appear in JSONL in order."""
        jsonl_path = str(tmp_path / "events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=jsonl_path,
        )
        emitter = build_emitter("round-trip-pipe", str(tmp_path), config)

        events = [
            EventBuilder.pipeline_started("round-trip-pipe", "pipeline.dot", 3),
            EventBuilder.node_started("round-trip-pipe", "node_a", "box", 1),
            EventBuilder.node_completed(
                "round-trip-pipe", "node_a", "success", 42.0, tokens_used=100
            ),
            EventBuilder.edge_selected(
                "round-trip-pipe", "node_a", "node_b", selection_step=1
            ),
            EventBuilder.pipeline_completed(
                "round-trip-pipe", 500.0, total_tokens=100
            ),
        ]

        self._emit_and_close(emitter, events)

        lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 5, f"Expected 5 JSONL lines, got {len(lines)}"

        records = [json.loads(line) for line in lines]
        expected_types = [
            "pipeline.started",
            "node.started",
            "node.completed",
            "edge.selected",
            "pipeline.completed",
        ]
        actual_types = [r["type"] for r in records]
        assert actual_types == expected_types, (
            f"Event types mismatch.\nExpected: {expected_types}\nActual:   {actual_types}"
        )

    def test_pipeline_id_preserved_in_jsonl(self, tmp_path: Path) -> None:
        """pipeline_id field is preserved correctly in JSONL output."""
        pipeline_id = "my-unique-pipe-id-xyz"
        jsonl_path = str(tmp_path / "events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=jsonl_path,
        )
        emitter = build_emitter(pipeline_id, str(tmp_path), config)

        event = EventBuilder.pipeline_started(pipeline_id, "g.dot", 2)
        self._emit_and_close(emitter, [event])

        lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["pipeline_id"] == pipeline_id

    def test_timestamps_are_iso8601_and_timezone_aware(self, tmp_path: Path) -> None:
        """All JSONL records include a valid, timezone-aware ISO-8601 timestamp."""
        jsonl_path = str(tmp_path / "events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=jsonl_path,
        )
        emitter = build_emitter("ts-pipe", str(tmp_path), config)

        events = [
            EventBuilder.pipeline_started("ts-pipe", "g.dot", 2),
            EventBuilder.pipeline_completed("ts-pipe", 100.0),
        ]
        self._emit_and_close(emitter, events)

        lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            record = json.loads(line)
            assert "timestamp" in record, "timestamp field missing from JSONL record"
            ts = datetime.fromisoformat(record["timestamp"])
            assert ts.tzinfo is not None, "timestamp must be timezone-aware"

    def test_sequence_numbers_strictly_increasing(self, tmp_path: Path) -> None:
        """sequence field in JSONL records is strictly monotonically increasing."""
        jsonl_path = str(tmp_path / "events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=jsonl_path,
        )
        emitter = build_emitter("seq-pipe", str(tmp_path), config)

        events = [
            EventBuilder.pipeline_started("seq-pipe", "g.dot", 3),
            EventBuilder.node_started("seq-pipe", "n1", "box", 1),
            EventBuilder.node_completed("seq-pipe", "n1", "success", 10.0),
        ]
        self._emit_and_close(emitter, events)

        lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
        sequences = [json.loads(line)["sequence"] for line in lines]
        for i in range(1, len(sequences)):
            assert sequences[i] > sequences[i - 1], (
                f"Sequence not strictly increasing: "
                f"{sequences[i - 1]} -> {sequences[i]} at index {i}"
            )

    def test_node_id_in_node_level_events(self, tmp_path: Path) -> None:
        """node_id is correctly set for node-level events and None for pipeline-level."""
        jsonl_path = str(tmp_path / "events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=jsonl_path,
        )
        emitter = build_emitter("node-id-pipe", str(tmp_path), config)

        events = [
            EventBuilder.pipeline_started("node-id-pipe", "g.dot", 2),
            EventBuilder.node_started("node-id-pipe", "my_node", "box", 1),
        ]
        self._emit_and_close(emitter, events)

        lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(line) for line in lines]

        # pipeline.started has no node_id
        assert records[0]["node_id"] is None
        # node.started carries the node_id
        assert records[1]["node_id"] == "my_node"

    def test_data_payload_preserved(self, tmp_path: Path) -> None:
        """Event data payloads are round-tripped through JSONL without data loss."""
        jsonl_path = str(tmp_path / "events.jsonl")
        config = EventBusConfig(
            logfire_enabled=False,
            signal_bridge_enabled=False,
            jsonl_path=jsonl_path,
        )
        emitter = build_emitter("payload-pipe", str(tmp_path), config)

        event = EventBuilder.pipeline_started("payload-pipe", "my/path/g.dot", 7)
        self._emit_and_close(emitter, [event])

        lines = Path(jsonl_path).read_text(encoding="utf-8").strip().splitlines()
        record = json.loads(lines[0])
        assert record["data"]["dot_path"] == "my/path/g.dot"
        assert record["data"]["node_count"] == 7


# ---------------------------------------------------------------------------
# 3. CompositeEmitter fan-out verification
# ---------------------------------------------------------------------------

class TestCompositeEmitterFanOut:
    """Verify fan-out behaviour: all backends receive all events."""

    def test_three_backends_all_receive_five_events(self) -> None:
        """All 3 backends must receive all 5 emitted events in order."""
        backends = [_RecordingEmitter() for _ in range(3)]
        composite = CompositeEmitter(backends)

        events = [
            EventBuilder.pipeline_started("fan-pipe", "g.dot", 5),
            EventBuilder.node_started("fan-pipe", "n1", "box", 1),
            EventBuilder.node_completed("fan-pipe", "n1", "success", 10.0),
            EventBuilder.edge_selected("fan-pipe", "n1", "n2", 1),
            EventBuilder.pipeline_completed("fan-pipe", 200.0),
        ]

        async def emit_all():
            for evt in events:
                await composite.emit(evt)

        _run(emit_all())

        for i, backend in enumerate(backends):
            assert len(backend.received) == 5, (
                f"Backend {i} received {len(backend.received)} events, expected 5"
            )
            for j, expected_evt in enumerate(events):
                assert backend.received[j] is expected_evt, (
                    f"Backend {i} event {j}: got {backend.received[j].type!r}, "
                    f"expected {expected_evt.type!r}"
                )

    def test_fan_out_preserves_event_order_per_backend(self) -> None:
        """Events arrive at each backend in the same order they were emitted."""
        backends = [_RecordingEmitter() for _ in range(2)]
        composite = CompositeEmitter(backends)

        events = [
            EventBuilder.pipeline_started("order-pipe", "g.dot", 10),
            EventBuilder.node_started("order-pipe", "n1", "box", 1),
            EventBuilder.node_started("order-pipe", "n2", "box", 1),
            EventBuilder.pipeline_completed("order-pipe", 1000.0),
        ]

        async def emit_all():
            for evt in events:
                await composite.emit(evt)

        _run(emit_all())

        expected_type_sequence = [e.type for e in events]
        for backend in backends:
            actual = [e.type for e in backend.received]
            assert actual == expected_type_sequence

    def test_single_failing_backend_does_not_block_others(self) -> None:
        """A backend that raises must not prevent healthy backends from receiving events."""
        good1 = _RecordingEmitter()
        bad = _FailingEmitter()
        good2 = _RecordingEmitter()
        composite = CompositeEmitter([good1, bad, good2])  # type: ignore[list-item]

        evt = EventBuilder.pipeline_started("iso-pipe", "g.dot", 1)
        _run(composite.emit(evt))  # Must not raise

        assert len(good1.received) == 1
        assert len(good2.received) == 1

    def test_aclose_flushes_all_backends(self) -> None:
        """aclose() must be propagated to every backend."""
        backends = [_RecordingEmitter() for _ in range(4)]
        composite = CompositeEmitter(backends)
        _run(composite.aclose())
        for b in backends:
            assert b.closed is True

    def test_single_backend_receives_all_events(self) -> None:
        """Single-backend CompositeEmitter still delivers all events."""
        backend = _RecordingEmitter()
        composite = CompositeEmitter([backend])

        events = [
            EventBuilder.pipeline_started("solo-pipe", "g.dot", 2),
            EventBuilder.node_started("solo-pipe", "n1", "box", 1),
        ]

        async def emit_all():
            for evt in events:
                await composite.emit(evt)

        _run(emit_all())

        assert len(backend.received) == 2
        assert backend.received[0].type == "pipeline.started"
        assert backend.received[1].type == "node.started"

    def test_empty_composite_emitter_no_error(self) -> None:
        """CompositeEmitter with zero backends must not raise on emit or aclose."""
        composite = CompositeEmitter([])
        evt = EventBuilder.pipeline_started("empty-pipe", "g.dot", 0)
        _run(composite.emit(evt))
        _run(composite.aclose())


# ---------------------------------------------------------------------------
# 4. Full middleware chain composition
# ---------------------------------------------------------------------------

class TestFullMiddlewareChain:
    """Test that all 4 E4 middlewares compose and execute without error."""

    _ALL_MIDDLEWARES: list = [
        # Listed in the runner's chain order (outermost first)
        LogfireMiddleware(),
        TokenCountingMiddleware(),
        RetryMiddleware(default_max_retries=3, base_delay_s=0.0),
        AuditMiddleware(),
    ]

    def test_chain_calls_handler_exactly_once_on_success(self) -> None:
        """A SUCCESS outcome passes through all 4 middlewares; handler called once."""
        handler = _SuccessHandler()
        chain = compose_middleware(list(self._ALL_MIDDLEWARES), handler)
        request = _make_request()

        outcome = _run(chain(request))

        assert outcome.status == OutcomeStatus.SUCCESS
        assert handler.call_count == 1

    def test_chain_does_not_raise_for_success_handler(self) -> None:
        """compose_middleware chain must not raise for a SUCCESS-returning handler."""
        handler = _SuccessHandler()
        chain = compose_middleware(
            [
                LogfireMiddleware(),
                TokenCountingMiddleware(),
                RetryMiddleware(base_delay_s=0.0),
                AuditMiddleware(),
            ],
            handler,
        )
        outcome = _run(chain(_make_request()))
        assert outcome is not None

    def test_chain_with_recording_emitter_emits_node_events(self) -> None:
        """Middlewares that emit events work correctly when a real emitter is provided."""
        recording = _RecordingEmitter()
        handler = _SuccessHandler()
        chain = compose_middleware(
            [
                LogfireMiddleware(),
                TokenCountingMiddleware(),
                RetryMiddleware(base_delay_s=0.0),
                AuditMiddleware(),
            ],
            handler,
        )
        request = _make_request(emitter=recording)

        outcome = _run(chain(request))

        assert outcome.status == OutcomeStatus.SUCCESS
        # LogfireMiddleware emits node.started and node.completed
        event_types = {e.type for e in recording.received}
        assert "node.started" in event_types, (
            f"node.started missing from emitted events: {event_types}"
        )
        assert "node.completed" in event_types, (
            f"node.completed missing from emitted events: {event_types}"
        )

    def test_chain_empty_middlewares_calls_handler_directly(self) -> None:
        """compose_middleware([]) invokes the handler directly with no wrapping."""
        handler = _SuccessHandler()
        chain = compose_middleware([], handler)
        request = _make_request()

        outcome = _run(chain(request))

        assert outcome.status == OutcomeStatus.SUCCESS
        assert handler.call_count == 1

    def test_chain_preserves_outcome_metadata_through_all_middlewares(self) -> None:
        """Middleware chain must not strip or overwrite handler Outcome.metadata."""
        chain = compose_middleware(
            [LogfireMiddleware(), AuditMiddleware()],
            _MetadataHandler(),
        )
        outcome = _run(chain(_make_request()))

        assert outcome.metadata.get("custom_key") == "custom_value"
        assert outcome.metadata.get("score") == 42

    def test_chain_outcome_status_propagated_correctly(self) -> None:
        """All OutcomeStatus values pass through the chain unchanged."""
        for status in (OutcomeStatus.SUCCESS, OutcomeStatus.PARTIAL_SUCCESS):

            class _StatusHandler:
                def __init__(self, s: OutcomeStatus) -> None:
                    self._s = s

                async def execute(self, req: HandlerRequest) -> Outcome:
                    return Outcome(status=self._s)

            chain = compose_middleware(
                [LogfireMiddleware(), AuditMiddleware()],
                _StatusHandler(status),
            )
            outcome = _run(chain(_make_request()))
            assert outcome.status == status, (
                f"Expected {status}, got {outcome.status}"
            )

    def test_logfire_middleware_alone_emits_node_started(self) -> None:
        """LogfireMiddleware in isolation emits node.started and node.completed."""
        recording = _RecordingEmitter()
        handler = _SuccessHandler()
        chain = compose_middleware([LogfireMiddleware()], handler)
        request = _make_request(emitter=recording)

        _run(chain(request))

        event_types = [e.type for e in recording.received]
        assert "node.started" in event_types
        assert "node.completed" in event_types

    def test_retry_middleware_does_not_retry_on_success(self) -> None:
        """RetryMiddleware must not retry when handler returns SUCCESS."""
        handler = _SuccessHandler()
        chain = compose_middleware(
            [RetryMiddleware(default_max_retries=5, base_delay_s=0.0)],
            handler,
        )
        outcome = _run(chain(_make_request()))

        assert outcome.status == OutcomeStatus.SUCCESS
        assert handler.call_count == 1  # No retries

    def test_audit_middleware_does_not_break_chain(self) -> None:
        """AuditMiddleware with default stub writer must not raise."""
        handler = _SuccessHandler()
        chain = compose_middleware([AuditMiddleware()], handler)
        outcome = _run(chain(_make_request()))
        assert outcome.status == OutcomeStatus.SUCCESS
        assert handler.call_count == 1
