"""Tests for SignalBridge — signal file translation backend.

Uses tmp_path as signals_dir to avoid filesystem side-effects and to make
signal file inspection easy.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from cobuilder.engine.events.signal_bridge import SignalBridge
from cobuilder.engine.events.types import EventBuilder
from cobuilder.pipeline.signal_protocol import (
    NODE_COMPLETE,
    ORCHESTRATOR_CRASHED,
    ORCHESTRATOR_STUCK,
    VIOLATION,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _read_signals(signals_dir: str) -> list[dict]:
    """Read all signal JSON files from signals_dir (excluding processed/)."""
    results = []
    for fname in sorted(os.listdir(signals_dir)):
        if fname.endswith(".json") and not fname.endswith(".tmp"):
            full_path = os.path.join(signals_dir, fname)
            if os.path.isfile(full_path):
                with open(full_path, encoding="utf-8") as fh:
                    results.append(json.load(fh))
    return results


# ---------------------------------------------------------------------------
# Bridge-eligible event types
# ---------------------------------------------------------------------------

class TestSignalBridgeEligibleEvents:

    def test_pipeline_completed_writes_node_complete_signal(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "signals")
        bridge = SignalBridge(pipeline_id="my-pipe", signals_dir=signals_dir)
        evt = EventBuilder.pipeline_completed("my-pipe", 1234.5, total_tokens=100)
        _run(bridge.emit(evt))

        signals = _read_signals(signals_dir)
        assert len(signals) == 1
        sig = signals[0]
        assert sig["signal_type"] == NODE_COMPLETE
        assert sig["source"] == "engine"
        assert sig["target"] == "guardian"
        assert sig["payload"]["pipeline_id"] == "my-pipe"

    def test_pipeline_failed_writes_orchestrator_crashed_signal(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "signals")
        bridge = SignalBridge(pipeline_id="my-pipe", signals_dir=signals_dir)
        evt = EventBuilder.pipeline_failed("my-pipe", "RuntimeError", "catastrophic failure", "n3")
        _run(bridge.emit(evt))

        signals = _read_signals(signals_dir)
        assert len(signals) == 1
        sig = signals[0]
        assert sig["signal_type"] == ORCHESTRATOR_CRASHED
        assert sig["payload"]["error_type"] == "RuntimeError"

    def test_node_failed_with_goal_gate_writes_violation_signal(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "signals")
        bridge = SignalBridge(pipeline_id="p", signals_dir=signals_dir)
        evt = EventBuilder.node_failed("p", "critical_node", "GoalGateError", goal_gate=True)
        _run(bridge.emit(evt))

        signals = _read_signals(signals_dir)
        assert len(signals) == 1
        sig = signals[0]
        assert sig["signal_type"] == VIOLATION
        assert sig["payload"]["node_id"] == "critical_node"

    def test_loop_detected_writes_orchestrator_stuck_signal(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "signals")
        bridge = SignalBridge(pipeline_id="p", signals_dir=signals_dir)
        evt = EventBuilder.loop_detected("p", "loopy_node", visit_count=10, limit=3)
        _run(bridge.emit(evt))

        signals = _read_signals(signals_dir)
        assert len(signals) == 1
        sig = signals[0]
        assert sig["signal_type"] == ORCHESTRATOR_STUCK
        assert sig["payload"]["node_id"] == "loopy_node"
        assert sig["payload"]["visit_count"] == 10


# ---------------------------------------------------------------------------
# Non-bridge-eligible event types
# ---------------------------------------------------------------------------

class TestSignalBridgeNonEligibleEvents:

    def _bridge(self, tmp_path) -> tuple[SignalBridge, str]:
        signals_dir = str(tmp_path / "signals")
        return SignalBridge(pipeline_id="p", signals_dir=signals_dir), signals_dir

    def test_node_failed_without_goal_gate_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        evt = EventBuilder.node_failed("p", "n1", "ValueError", goal_gate=False)
        _run(bridge.emit(evt))
        # signals_dir might not even exist yet
        if os.path.exists(signals_dir):
            signals = _read_signals(signals_dir)
            assert len(signals) == 0

    def test_edge_selected_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        evt = EventBuilder.edge_selected("p", "n1", "n2", 1)
        _run(bridge.emit(evt))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_node_started_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.node_started("p", "n1", "box", 1)))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_checkpoint_saved_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.checkpoint_saved("p", "n1", "/tmp/chk")))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_retry_triggered_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.retry_triggered("p", "n1", 1, 1000.0, "Err")))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_context_updated_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.context_updated("p", "n1", [], [])))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_pipeline_started_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.pipeline_started("p", "g.dot", 3)))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_pipeline_resumed_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.pipeline_resumed("p", "/chk", 2)))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_validation_started_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.validation_started("p", 5)))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_validation_completed_writes_no_signal(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.validation_completed("p", [], [], True)))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0

    def test_loop_detected_is_distinct_from_node_completed(self, tmp_path) -> None:
        bridge, signals_dir = self._bridge(tmp_path)
        _run(bridge.emit(EventBuilder.node_completed("p", "n1", "SUCCESS", 10.0)))
        if os.path.exists(signals_dir):
            assert len(_read_signals(signals_dir)) == 0


# ---------------------------------------------------------------------------
# aclose() semantics
# ---------------------------------------------------------------------------

class TestSignalBridgeAclose:

    def test_aclose_is_idempotent(self, tmp_path) -> None:
        bridge = SignalBridge(pipeline_id="p", signals_dir=str(tmp_path / "s"))
        _run(bridge.aclose())
        _run(bridge.aclose())  # second call must not raise

    def test_aclose_is_noop(self, tmp_path) -> None:
        """aclose() on a bridge that has emitted signals does nothing extra."""
        signals_dir = str(tmp_path / "signals")
        bridge = SignalBridge(pipeline_id="p", signals_dir=signals_dir)
        _run(bridge.emit(EventBuilder.pipeline_completed("p", 100.0)))
        _run(bridge.aclose())
        # The signals written before aclose() should still be there
        signals = _read_signals(signals_dir)
        assert len(signals) == 1


# ---------------------------------------------------------------------------
# Signal payload correctness
# ---------------------------------------------------------------------------

class TestSignalBridgePayloads:

    def test_pipeline_completed_payload_includes_duration(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "s")
        bridge = SignalBridge("p", signals_dir=signals_dir)
        _run(bridge.emit(EventBuilder.pipeline_completed("p", 2500.0, total_tokens=99)))
        sig = _read_signals(signals_dir)[0]
        assert sig["payload"]["duration_ms"] == 2500.0
        assert sig["payload"]["total_tokens"] == 99

    def test_violation_signal_includes_node_id(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "s")
        bridge = SignalBridge("p", signals_dir=signals_dir)
        _run(bridge.emit(EventBuilder.node_failed("p", "gate_node", "GoalGate", goal_gate=True)))
        sig = _read_signals(signals_dir)[0]
        assert sig["payload"]["node_id"] == "gate_node"

    def test_orchestrator_stuck_includes_visit_count(self, tmp_path) -> None:
        signals_dir = str(tmp_path / "s")
        bridge = SignalBridge("p", signals_dir=signals_dir)
        _run(bridge.emit(EventBuilder.loop_detected("p", "n1", visit_count=7, limit=3)))
        sig = _read_signals(signals_dir)[0]
        assert sig["payload"]["visit_count"] == 7
        assert sig["payload"]["limit"] == 3
