"""Tests for LogfireEmitter — Logfire span management backend.

Uses logfire.testing.TestExporter to capture spans without a real Logfire
API connection.  If logfire.testing is unavailable the tests are skipped.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from cobuilder.engine.events.types import EventBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Availability guard
# ---------------------------------------------------------------------------

try:
    import logfire
    import logfire.testing
    _LOGFIRE_TESTING_AVAILABLE = True
except ImportError:
    _LOGFIRE_TESTING_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not _LOGFIRE_TESTING_AVAILABLE,
    reason="logfire.testing not available",
)


# ---------------------------------------------------------------------------
# Helper to build a LogfireEmitter with fresh state
# ---------------------------------------------------------------------------

def _make_emitter(pipeline_id: str = "test-pipe"):
    from cobuilder.engine.events.logfire_backend import LogfireEmitter
    return LogfireEmitter(pipeline_id=pipeline_id)


# ---------------------------------------------------------------------------
# Pipeline span lifecycle
# ---------------------------------------------------------------------------

class TestLogfireEmitterPipelineSpan:

    def test_pipeline_started_opens_span(self, capfire) -> None:
        """pipeline.started should create a span named pipeline.{pipeline_id}."""
        emitter = _make_emitter("my-pipe")
        evt = EventBuilder.pipeline_started("my-pipe", "/path/graph.dot", 5)
        _run(emitter.emit(evt))
        # Pipeline span should be open (stored in emitter state)
        assert emitter._pipeline_span is not None
        _run(emitter.aclose())

    def test_pipeline_completed_closes_span(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        assert emitter._pipeline_span is not None
        _run(emitter.emit(EventBuilder.pipeline_completed("p", 500.0, total_tokens=42)))
        # After completion the span reference is cleared
        assert emitter._pipeline_span is None

    def test_pipeline_failed_closes_span(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.pipeline_failed("p", "RuntimeError", "boom")))
        assert emitter._pipeline_span is None

    def test_aclose_closes_pipeline_span(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.aclose())
        assert emitter._pipeline_span is None

    def test_aclose_is_idempotent(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.aclose())
        _run(emitter.aclose())  # second call must not raise


# ---------------------------------------------------------------------------
# Node span lifecycle
# ---------------------------------------------------------------------------

class TestLogfireEmitterNodeSpan:

    def test_node_started_opens_node_span(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.node_started("p", "n1", "box", 1)))
        assert "n1" in emitter._node_spans
        _run(emitter.aclose())

    def test_node_completed_closes_node_span(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.node_started("p", "n1", "box", 1)))
        assert "n1" in emitter._node_spans
        _run(emitter.emit(EventBuilder.node_completed("p", "n1", "SUCCESS", 100.0)))
        assert "n1" not in emitter._node_spans
        _run(emitter.aclose())

    def test_node_failed_closes_node_span(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.node_started("p", "n1", "box", 1)))
        _run(emitter.emit(EventBuilder.node_failed("p", "n1", "ValueError")))
        assert "n1" not in emitter._node_spans
        _run(emitter.aclose())

    def test_parallel_nodes_get_independent_spans(self, capfire) -> None:
        """Multiple nodes open simultaneously each get their own span."""
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 5)))
        _run(emitter.emit(EventBuilder.node_started("p", "n1", "box", 1)))
        _run(emitter.emit(EventBuilder.node_started("p", "n2", "box", 1)))
        assert "n1" in emitter._node_spans
        assert "n2" in emitter._node_spans
        # Close them independently
        _run(emitter.emit(EventBuilder.node_completed("p", "n1", "SUCCESS", 50.0)))
        assert "n1" not in emitter._node_spans
        assert "n2" in emitter._node_spans
        _run(emitter.aclose())

    def test_node_completed_without_started_does_not_raise(self, capfire) -> None:
        """Calling node.completed for a node that was never started must not crash."""
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        # No node.started for "ghost_node"
        _run(emitter.emit(EventBuilder.node_completed("p", "ghost_node", "SUCCESS", 10.0)))
        _run(emitter.aclose())


# ---------------------------------------------------------------------------
# Non-span events are silently ignored
# ---------------------------------------------------------------------------

class TestLogfireEmitterNonSpanEvents:

    def test_edge_selected_is_ignored(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.edge_selected("p", "n1", "n2", 1)))
        # No error; state unchanged (no new node spans)
        assert len(emitter._node_spans) == 0
        _run(emitter.aclose())

    def test_checkpoint_saved_is_ignored(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.checkpoint_saved("p", "n1", "/tmp/chk.json")))
        _run(emitter.aclose())

    def test_retry_triggered_is_ignored(self, capfire) -> None:
        emitter = _make_emitter("p")
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        _run(emitter.emit(EventBuilder.retry_triggered("p", "n1", 1, 1000.0, "TimeoutError")))
        _run(emitter.aclose())


# ---------------------------------------------------------------------------
# Failure resilience
# ---------------------------------------------------------------------------

class TestLogfireEmitterFailureResilience:

    def test_failed_flag_set_on_logfire_error(self, capfire) -> None:
        """If logfire operations raise, _failed is set and no more ops happen."""
        from cobuilder.engine.events.logfire_backend import LogfireEmitter
        emitter = LogfireEmitter(pipeline_id="p")

        # Simulate logfire.span raising
        with patch("cobuilder.engine.events.logfire_backend._logfire") as mock_lf:
            mock_lf.span.side_effect = RuntimeError("logfire unavailable")
            evt = EventBuilder.pipeline_started("p", "g.dot", 3)
            _run(emitter.emit(evt))  # Should not propagate
            assert emitter._failed is True

    def test_no_op_after_failure(self, capfire) -> None:
        """After _failed is True, emit() does nothing."""
        from cobuilder.engine.events.logfire_backend import LogfireEmitter
        emitter = LogfireEmitter(pipeline_id="p")
        emitter._failed = True  # Pre-set failure state

        # Should be a no-op, not raise
        _run(emitter.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        assert emitter._pipeline_span is None
