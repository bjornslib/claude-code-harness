"""Tests for cobuilder.engine.events.types — PipelineEvent, EventType, EventBuilder."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cobuilder.engine.events.types import (
    _ALL_EVENT_TYPES,
    EventBuilder,
    EventType,
    PipelineEvent,
    SpanConfig,
)


# ---------------------------------------------------------------------------
# EventType literal tests
# ---------------------------------------------------------------------------

class TestEventTypeLiterals:
    """All 14 EventType string constants must be present."""

    EXPECTED_TYPES = {
        "pipeline.started",
        "pipeline.completed",
        "pipeline.failed",
        "pipeline.resumed",
        "node.started",
        "node.completed",
        "node.failed",
        "edge.selected",
        "checkpoint.saved",
        "context.updated",
        "retry.triggered",
        "loop.detected",
        "validation.started",
        "validation.completed",
    }

    def test_all_14_types_present_in_frozenset(self) -> None:
        assert _ALL_EVENT_TYPES == self.EXPECTED_TYPES

    def test_count_is_exactly_14(self) -> None:
        assert len(_ALL_EVENT_TYPES) == 14

    def test_no_extra_types(self) -> None:
        """The frozenset contains exactly the expected set — no extras."""
        assert not (_ALL_EVENT_TYPES - self.EXPECTED_TYPES)


# ---------------------------------------------------------------------------
# PipelineEvent dataclass tests
# ---------------------------------------------------------------------------

class TestPipelineEvent:
    """PipelineEvent must be frozen and slot-based."""

    def _make_event(self, **kwargs) -> PipelineEvent:
        defaults = dict(
            type="pipeline.started",
            timestamp=datetime.now(timezone.utc),
            pipeline_id="test-pipe",
            node_id=None,
            data={"dot_path": "a.dot", "node_count": 3},
        )
        defaults.update(kwargs)
        return PipelineEvent(**defaults)

    def test_construction_succeeds(self) -> None:
        evt = self._make_event()
        assert evt.pipeline_id == "test-pipe"
        assert evt.node_id is None

    def test_frozen_raises_on_mutation(self) -> None:
        evt = self._make_event()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            evt.node_id = "x"  # type: ignore[misc]

    def test_slots_true(self) -> None:
        """Slotted dataclasses do not have a __dict__ instance attribute."""
        evt = self._make_event()
        assert not hasattr(evt, "__dict__"), "PipelineEvent should use __slots__"

    def test_timestamp_is_timezone_aware(self) -> None:
        evt = self._make_event()
        assert evt.timestamp.tzinfo is not None

    def test_default_span_id_is_none(self) -> None:
        evt = self._make_event()
        assert evt.span_id is None

    def test_default_sequence_is_zero(self) -> None:
        """When constructed directly (not via EventBuilder) sequence defaults to 0."""
        evt = self._make_event()
        assert evt.sequence == 0

    def test_node_id_accepts_none_for_pipeline_events(self) -> None:
        evt = self._make_event(type="pipeline.started", node_id=None)
        assert evt.node_id is None

    def test_node_id_accepts_string_for_node_events(self) -> None:
        evt = self._make_event(type="node.started", node_id="box_1", data={"handler_type": "box", "visit_count": 1})
        assert evt.node_id == "box_1"


# ---------------------------------------------------------------------------
# EventBuilder factory method tests
# ---------------------------------------------------------------------------

class TestEventBuilder:
    """EventBuilder factory methods must produce correct PipelineEvent instances."""

    def setup_method(self) -> None:
        # Reset counter between test methods to avoid ordering-dependency issues.
        # We capture the current value and verify it only increases.
        self._counter_before = EventBuilder._counter

    def test_pipeline_started(self) -> None:
        evt = EventBuilder.pipeline_started("my-pipe", "/tmp/graph.dot", 5)
        assert evt.type == "pipeline.started"
        assert evt.pipeline_id == "my-pipe"
        assert evt.node_id is None
        assert evt.data["dot_path"] == "/tmp/graph.dot"
        assert evt.data["node_count"] == 5

    def test_pipeline_completed(self) -> None:
        evt = EventBuilder.pipeline_completed("p", 1234.5, total_tokens=42)
        assert evt.type == "pipeline.completed"
        assert evt.data["duration_ms"] == 1234.5
        assert evt.data["total_tokens"] == 42

    def test_pipeline_failed(self) -> None:
        evt = EventBuilder.pipeline_failed("p", "RuntimeError", "boom", last_node_id="n1")
        assert evt.type == "pipeline.failed"
        assert evt.data["error_type"] == "RuntimeError"
        assert evt.data["last_node_id"] == "n1"

    def test_pipeline_resumed(self) -> None:
        evt = EventBuilder.pipeline_resumed("p", "/tmp/chk.json", 3)
        assert evt.type == "pipeline.resumed"
        assert evt.data["completed_node_count"] == 3

    def test_node_started(self) -> None:
        evt = EventBuilder.node_started("p", "n1", "box", 2)
        assert evt.type == "node.started"
        assert evt.node_id == "n1"
        assert evt.data["handler_type"] == "box"
        assert evt.data["visit_count"] == 2

    def test_node_completed(self) -> None:
        evt = EventBuilder.node_completed("p", "n1", "SUCCESS", 100.0, tokens_used=50, span_id="abc")
        assert evt.type == "node.completed"
        assert evt.data["outcome_status"] == "SUCCESS"
        assert evt.data["duration_ms"] == 100.0
        assert evt.data["tokens_used"] == 50
        assert evt.span_id == "abc"

    def test_node_failed(self) -> None:
        evt = EventBuilder.node_failed("p", "n1", "ValueError", goal_gate=True)
        assert evt.type == "node.failed"
        assert evt.data["goal_gate"] is True
        assert evt.data["error_type"] == "ValueError"

    def test_edge_selected(self) -> None:
        evt = EventBuilder.edge_selected("p", "n1", "n2", 1, condition="SUCCESS")
        assert evt.type == "edge.selected"
        assert evt.data["to_node_id"] == "n2"
        assert evt.data["condition"] == "SUCCESS"

    def test_checkpoint_saved(self) -> None:
        evt = EventBuilder.checkpoint_saved("p", "n1", "/tmp/chk.json")
        assert evt.type == "checkpoint.saved"
        assert evt.data["checkpoint_path"] == "/tmp/chk.json"

    def test_context_updated(self) -> None:
        evt = EventBuilder.context_updated("p", "n1", ["k1"], ["k2"])
        assert evt.type == "context.updated"
        assert evt.data["keys_added"] == ["k1"]
        assert evt.data["keys_modified"] == ["k2"]

    def test_retry_triggered(self) -> None:
        evt = EventBuilder.retry_triggered("p", "n1", 2, 2000.0, "TimeoutError")
        assert evt.type == "retry.triggered"
        assert evt.data["attempt_number"] == 2
        assert evt.data["backoff_ms"] == 2000.0

    def test_loop_detected(self) -> None:
        evt = EventBuilder.loop_detected("p", "n1", 5, 3, "A→B→A")
        assert evt.type == "loop.detected"
        assert evt.data["visit_count"] == 5
        assert evt.data["limit"] == 3

    def test_validation_started(self) -> None:
        evt = EventBuilder.validation_started("p", 7)
        assert evt.type == "validation.started"
        assert evt.data["rule_count"] == 7

    def test_validation_completed(self) -> None:
        evt = EventBuilder.validation_completed("p", ["err1"], ["warn1"], passed=False)
        assert evt.type == "validation.completed"
        assert evt.data["passed"] is False
        assert "err1" in evt.data["errors"]

    def test_timestamp_is_utc_aware(self) -> None:
        evt = EventBuilder.pipeline_started("p", "g.dot", 1)
        assert evt.timestamp.tzinfo is not None
        assert evt.timestamp.tzinfo == timezone.utc or evt.timestamp.utcoffset().total_seconds() == 0

    def test_sequence_is_monotonically_increasing(self) -> None:
        """Calling _build() multiple times produces strictly increasing sequence values."""
        seq_values = [
            EventBuilder.pipeline_started("p", "g.dot", 1).sequence
            for _ in range(10)
        ]
        for a, b in zip(seq_values, seq_values[1:]):
            assert b > a, f"sequence not monotonically increasing: {seq_values}"

    def test_sequence_counter_increments_across_different_event_types(self) -> None:
        """The counter is shared across all factory methods."""
        e1 = EventBuilder.pipeline_started("p", "g.dot", 1)
        e2 = EventBuilder.node_started("p", "n1", "box", 1)
        e3 = EventBuilder.pipeline_completed("p", 100.0)
        assert e2.sequence > e1.sequence
        assert e3.sequence > e2.sequence

    def test_all_14_factory_methods_exist(self) -> None:
        """Every event type in _ALL_EVENT_TYPES has a corresponding factory method."""
        method_map = {
            "pipeline.started": lambda: EventBuilder.pipeline_started("p", "g.dot", 1),
            "pipeline.completed": lambda: EventBuilder.pipeline_completed("p", 100.0),
            "pipeline.failed": lambda: EventBuilder.pipeline_failed("p", "Error", "msg"),
            "pipeline.resumed": lambda: EventBuilder.pipeline_resumed("p", "/chk", 2),
            "node.started": lambda: EventBuilder.node_started("p", "n", "box", 1),
            "node.completed": lambda: EventBuilder.node_completed("p", "n", "SUCCESS", 10.0),
            "node.failed": lambda: EventBuilder.node_failed("p", "n", "ValueError"),
            "edge.selected": lambda: EventBuilder.edge_selected("p", "n1", "n2", 1),
            "checkpoint.saved": lambda: EventBuilder.checkpoint_saved("p", "n", "/chk"),
            "context.updated": lambda: EventBuilder.context_updated("p", "n", [], []),
            "retry.triggered": lambda: EventBuilder.retry_triggered("p", "n", 1, 1000.0, "Err"),
            "loop.detected": lambda: EventBuilder.loop_detected("p", "n", 5, 3),
            "validation.started": lambda: EventBuilder.validation_started("p", 3),
            "validation.completed": lambda: EventBuilder.validation_completed("p", [], [], True),
        }
        assert set(method_map.keys()) == _ALL_EVENT_TYPES
        for event_type, factory in method_map.items():
            evt = factory()
            assert evt.type == event_type, f"Expected type {event_type!r}, got {evt.type!r}"


# ---------------------------------------------------------------------------
# SpanConfig tests
# ---------------------------------------------------------------------------

class TestSpanConfig:
    def test_defaults(self) -> None:
        cfg = SpanConfig()
        assert "pipeline_id" in cfg.pipeline_span_name
        assert "node_id" in cfg.node_span_name
        assert "pipeline_id" in cfg.pipeline_attrs
        assert "outcome_status" in cfg.node_attrs
