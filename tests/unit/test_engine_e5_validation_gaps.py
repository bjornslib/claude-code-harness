"""Tests for E5 validation gap fixes: v5lm, ca1b, uqrs.

Gap v5lm: ORCHESTRATOR_STUCK signal written when LoopDetectedError is raised.
Gap ca1b: EventBuilder.loop_detected uses "pattern" field name (not "pattern_detected").
Gap uqrs: _handle_loop_detected emits loop.detected event via emitter.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cobuilder.engine.exceptions import LoopDetectedError
from cobuilder.engine.events.types import EventBuilder, PipelineEvent
from cobuilder.engine.handlers import HandlerRegistry
from cobuilder.engine.outcome import Outcome, OutcomeStatus
from cobuilder.engine.runner import EngineRunner


# ---------------------------------------------------------------------------
# Helpers (shared with existing integration tests)
# ---------------------------------------------------------------------------


def _make_handler(status: OutcomeStatus = OutcomeStatus.SUCCESS, **kw) -> Any:
    outcome = Outcome(status=status, **kw)
    h = MagicMock()
    h.execute = AsyncMock(return_value=outcome)
    return h


def _build_registry(*shape_pairs: tuple[str, Any]) -> HandlerRegistry:
    reg = HandlerRegistry()
    for shape, handler in shape_pairs:
        reg.register(shape, handler)
    return reg


def _write_dot(tmp_path: Path, content: str, name: str = "pipeline") -> Path:
    p = tmp_path / f"{name}.dot"
    p.write_text(content, encoding="utf-8")
    return p


def _make_runner(tmp_path: Path, dot_content: str, registry: HandlerRegistry, **kwargs) -> tuple[Path, EngineRunner]:
    dot_file = _write_dot(tmp_path, dot_content)
    runner = EngineRunner(
        dot_path=dot_file,
        pipelines_dir=tmp_path / "runs",
        handler_registry=registry,
        skip_validation=True,
        **kwargs,
    )
    return dot_file, runner


# Self-loop DOT for triggering LoopDetectedError
_DOT_SELF_LOOP = """
digraph pipeline {
    s    [shape=Mdiamond];
    body [shape=box];
    done [shape=Msquare];
    s    -> body;
    body -> body;
    body -> done [condition="$body_done = true"];
}
"""


# ---------------------------------------------------------------------------
# Gap v5lm: ORCHESTRATOR_STUCK signal for LoopDetectedError
# ---------------------------------------------------------------------------


class TestOrchestratorStuckSignal:
    """Verify that LoopDetectedError triggers an ORCHESTRATOR_STUCK signal write."""

    @pytest.mark.asyncio
    async def test_loop_detected_error_writes_stuck_signal(self, tmp_path):
        """v5lm: When LoopDetectedError is raised, write_signal is called
        with signal_type=ORCHESTRATOR_STUCK."""
        registry = _build_registry(
            ("Mdiamond", _make_handler(OutcomeStatus.SKIPPED)),
            ("box", _make_handler(OutcomeStatus.SUCCESS)),
            ("Msquare", _make_handler(OutcomeStatus.SUCCESS)),
        )
        _, runner = _make_runner(tmp_path, _DOT_SELF_LOOP, registry, max_node_visits=2)

        with patch("cobuilder.engine.runner.write_signal") as mock_write:
            with pytest.raises(LoopDetectedError):
                await runner.run()

            # Find the ORCHESTRATOR_STUCK call
            stuck_calls = [
                c for c in mock_write.call_args_list
                if c.kwargs.get("signal_type") == "ORCHESTRATOR_STUCK"
                or (len(c.args) > 2 and c.args[2] == "ORCHESTRATOR_STUCK")
            ]
            assert len(stuck_calls) == 1, (
                f"Expected exactly 1 ORCHESTRATOR_STUCK signal, got {len(stuck_calls)}. "
                f"All calls: {mock_write.call_args_list}"
            )

            call = stuck_calls[0]
            payload = call.kwargs.get("payload", {})
            assert payload["node_id"] == "body"
            assert "visit_count" in payload
            assert "max_retries" in payload

    @pytest.mark.asyncio
    async def test_stuck_signal_not_written_on_handler_error(self, tmp_path):
        """v5lm negative: HandlerError should NOT write ORCHESTRATOR_STUCK."""
        from cobuilder.engine.exceptions import HandlerError

        async def failing_handler(req):
            raise HandlerError("boom", node_id="body")

        h = MagicMock()
        h.execute = failing_handler

        dot = """
digraph pipeline {
    s    [shape=Mdiamond];
    body [shape=box];
    done [shape=Msquare];
    s    -> body;
    body -> done;
}
"""
        registry = _build_registry(
            ("Mdiamond", _make_handler(OutcomeStatus.SKIPPED)),
            ("box", h),
            ("Msquare", _make_handler(OutcomeStatus.SUCCESS)),
        )
        _, runner = _make_runner(tmp_path, dot, registry)

        with patch("cobuilder.engine.runner.write_signal") as mock_write:
            with pytest.raises(HandlerError):
                await runner.run()

            stuck_calls = [
                c for c in mock_write.call_args_list
                if c.kwargs.get("signal_type") == "ORCHESTRATOR_STUCK"
                or (len(c.args) > 2 and c.args[2] == "ORCHESTRATOR_STUCK")
            ]
            assert len(stuck_calls) == 0, "HandlerError should not produce ORCHESTRATOR_STUCK"


# ---------------------------------------------------------------------------
# Gap ca1b: LoopDetectionResult field naming alignment
# ---------------------------------------------------------------------------


class TestLoopDetectedFieldNaming:
    """Verify that EventBuilder.loop_detected uses 'pattern' field name."""

    def test_loop_detected_event_uses_pattern_field(self):
        """ca1b: Event data key must be 'pattern', not 'pattern_detected'."""
        event = EventBuilder.loop_detected(
            pipeline_id="test-pipe",
            node_id="body",
            visit_count=5,
            limit=3,
            pattern="A,B,A",
        )
        assert isinstance(event, PipelineEvent)
        assert event.type == "loop.detected"
        assert "pattern" in event.data
        assert "pattern_detected" not in event.data
        assert event.data["pattern"] == "A,B,A"
        assert event.data["visit_count"] == 5
        assert event.data["limit"] == 3

    def test_loop_detected_event_pattern_none_by_default(self):
        """ca1b: pattern field defaults to None."""
        event = EventBuilder.loop_detected(
            pipeline_id="p1",
            node_id="n1",
            visit_count=3,
            limit=2,
        )
        assert event.data["pattern"] is None

    def test_loop_detected_event_node_id_set(self):
        """ca1b: node_id is set on the PipelineEvent."""
        event = EventBuilder.loop_detected(
            pipeline_id="p1",
            node_id="my_node",
            visit_count=3,
            limit=2,
        )
        assert event.node_id == "my_node"


# ---------------------------------------------------------------------------
# Gap uqrs: loop.detected event emission (no longer a stub)
# ---------------------------------------------------------------------------


class TestLoopDetectedEventEmission:
    """Verify that _handle_loop_detected emits a loop.detected event."""

    @pytest.mark.asyncio
    async def test_loop_detected_emits_event_before_raising(self, tmp_path):
        """uqrs: When LoopDetectedError is about to be raised, a loop.detected
        event is emitted via the emitter BEFORE the exception propagates."""
        emitted_events: list[PipelineEvent] = []

        class CapturingEmitter:
            async def emit(self, event: PipelineEvent) -> None:
                emitted_events.append(event)
            async def aclose(self) -> None:
                pass

        registry = _build_registry(
            ("Mdiamond", _make_handler(OutcomeStatus.SKIPPED)),
            ("box", _make_handler(OutcomeStatus.SUCCESS)),
            ("Msquare", _make_handler(OutcomeStatus.SUCCESS)),
        )
        _, runner = _make_runner(tmp_path, _DOT_SELF_LOOP, registry, max_node_visits=2)

        # Patch build_emitter to return our capturing emitter
        with patch("cobuilder.engine.runner.build_emitter", return_value=CapturingEmitter()):
            with pytest.raises(LoopDetectedError):
                await runner.run()

        # Find the loop.detected event
        loop_events = [e for e in emitted_events if e.type == "loop.detected"]
        assert len(loop_events) == 1, (
            f"Expected exactly 1 loop.detected event, got {len(loop_events)}. "
            f"All event types: {[e.type for e in emitted_events]}"
        )

        loop_event = loop_events[0]
        assert loop_event.node_id == "body"
        assert loop_event.data["visit_count"] > 0
        assert loop_event.data["limit"] > 0
        # Field must be "pattern" (not "pattern_detected") — validates ca1b + uqrs together
        assert "pattern" in loop_event.data

    @pytest.mark.asyncio
    async def test_loop_detected_event_emitted_before_pipeline_failed(self, tmp_path):
        """uqrs: loop.detected event is emitted BEFORE pipeline.failed event."""
        emitted_types: list[str] = []

        class OrderCapturingEmitter:
            async def emit(self, event: PipelineEvent) -> None:
                emitted_types.append(event.type)
            async def aclose(self) -> None:
                pass

        registry = _build_registry(
            ("Mdiamond", _make_handler(OutcomeStatus.SKIPPED)),
            ("box", _make_handler(OutcomeStatus.SUCCESS)),
            ("Msquare", _make_handler(OutcomeStatus.SUCCESS)),
        )
        _, runner = _make_runner(tmp_path, _DOT_SELF_LOOP, registry, max_node_visits=2)

        with patch("cobuilder.engine.runner.build_emitter", return_value=OrderCapturingEmitter()):
            with pytest.raises(LoopDetectedError):
                await runner.run()

        # loop.detected should appear before pipeline.failed
        assert "loop.detected" in emitted_types, (
            f"loop.detected not in emitted events: {emitted_types}"
        )
        assert "pipeline.failed" in emitted_types, (
            f"pipeline.failed not in emitted events: {emitted_types}"
        )
        loop_idx = emitted_types.index("loop.detected")
        failed_idx = emitted_types.index("pipeline.failed")
        assert loop_idx < failed_idx, (
            f"loop.detected (idx={loop_idx}) should come before "
            f"pipeline.failed (idx={failed_idx})"
        )

    @pytest.mark.asyncio
    async def test_emit_failure_does_not_prevent_loop_detected_error(self, tmp_path):
        """uqrs: If event emission fails, LoopDetectedError is still raised."""
        class FailingEmitter:
            async def emit(self, event: PipelineEvent) -> None:
                if event.type == "loop.detected":
                    raise RuntimeError("emit failed")
            async def aclose(self) -> None:
                pass

        registry = _build_registry(
            ("Mdiamond", _make_handler(OutcomeStatus.SKIPPED)),
            ("box", _make_handler(OutcomeStatus.SUCCESS)),
            ("Msquare", _make_handler(OutcomeStatus.SUCCESS)),
        )
        _, runner = _make_runner(tmp_path, _DOT_SELF_LOOP, registry, max_node_visits=2)

        with patch("cobuilder.engine.runner.build_emitter", return_value=FailingEmitter()):
            with pytest.raises(LoopDetectedError):
                await runner.run()
        # If we get here, the emit failure was swallowed and the error still raised
