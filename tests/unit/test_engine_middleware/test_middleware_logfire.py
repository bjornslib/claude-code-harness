"""Tests for LogfireMiddleware (F7).

Coverage:
- node.started emitted BEFORE next() is called.
- node.completed emitted with outcome_status = "success" when next() returns SUCCESS.
- node.failed emitted when next() returns FAILURE.
- duration_ms > 0 in emitted events.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.events.types import PipelineEvent
from cobuilder.engine.graph import Node
from cobuilder.engine.middleware.chain import HandlerRequest
from cobuilder.engine.middleware.logfire import LogfireMiddleware
from cobuilder.engine.outcome import Outcome, OutcomeStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingEmitter:
    """Emitter that records every event emitted."""

    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []

    async def emit(self, event: PipelineEvent) -> None:
        self.events.append(event)

    async def aclose(self) -> None:
        return

    def types(self) -> list[str]:
        return [e.type for e in self.events]


def make_node(id: str = "n1", shape: str = "box", **attrs: Any) -> Node:
    return Node(id=id, shape=shape, label=id, attrs=attrs)


def make_request(
    node: Node | None = None,
    emitter: Any = None,
    pipeline_id: str = "pipe",
) -> HandlerRequest:
    if node is None:
        node = make_node()
    return HandlerRequest(
        node=node,
        context=PipelineContext(),
        emitter=emitter,
        pipeline_id=pipeline_id,
        visit_count=1,
        attempt_number=0,
    )


def make_outcome(status: OutcomeStatus = OutcomeStatus.SUCCESS) -> Outcome:
    return Outcome(status=status)


async def _next_success(request: HandlerRequest) -> Outcome:
    return make_outcome(OutcomeStatus.SUCCESS)


async def _next_failure(request: HandlerRequest) -> Outcome:
    return make_outcome(OutcomeStatus.FAILURE)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_node_started_emitted_before_next() -> None:
    """node.started must be emitted before next() is called."""
    emitter = _RecordingEmitter()
    call_order: list[str] = []

    async def _recording_next(request: HandlerRequest) -> Outcome:
        # Capture events already emitted BEFORE marking next() was called.
        call_order.extend(emitter.types())
        call_order.append("next")
        return make_outcome()

    mw = LogfireMiddleware()
    await mw(make_request(emitter=emitter), _recording_next)

    assert "node.started" in call_order, "node.started must appear before 'next'"
    assert call_order.index("node.started") < call_order.index("next")


@pytest.mark.asyncio
async def test_node_completed_on_success() -> None:
    """node.completed should be emitted with outcome_status='success' on SUCCESS."""
    emitter = _RecordingEmitter()
    mw = LogfireMiddleware()
    await mw(make_request(emitter=emitter), _next_success)

    assert "node.completed" in emitter.types()
    completed_events = [e for e in emitter.events if e.type == "node.completed"]
    assert len(completed_events) == 1
    assert completed_events[0].data["outcome_status"] == "success"


@pytest.mark.asyncio
async def test_node_failed_on_failure() -> None:
    """node.failed should be emitted when next() returns FAILURE."""
    emitter = _RecordingEmitter()
    mw = LogfireMiddleware()
    await mw(make_request(emitter=emitter), _next_failure)

    assert "node.failed" in emitter.types()
    assert "node.completed" not in emitter.types()


@pytest.mark.asyncio
async def test_duration_ms_positive() -> None:
    """duration_ms in node.completed must be > 0."""
    emitter = _RecordingEmitter()
    mw = LogfireMiddleware()

    async def _slow_next(request: HandlerRequest) -> Outcome:
        await asyncio.sleep(0.01)
        return make_outcome()

    await mw(make_request(emitter=emitter), _slow_next)

    completed = [e for e in emitter.events if e.type == "node.completed"]
    assert len(completed) == 1
    assert completed[0].data["duration_ms"] > 0


@pytest.mark.asyncio
async def test_node_started_and_completed_both_emitted() -> None:
    """Both node.started and node.completed should be emitted for a successful run."""
    emitter = _RecordingEmitter()
    mw = LogfireMiddleware()
    await mw(make_request(emitter=emitter), _next_success)

    event_types = emitter.types()
    assert "node.started" in event_types
    assert "node.completed" in event_types
    # started must come before completed
    assert event_types.index("node.started") < event_types.index("node.completed")


@pytest.mark.asyncio
async def test_no_emitter_does_not_raise() -> None:
    """When emitter is None, the middleware should not raise."""
    mw = LogfireMiddleware()
    result = await mw(make_request(emitter=None), _next_success)
    assert result.status == OutcomeStatus.SUCCESS


@pytest.mark.asyncio
async def test_exception_from_next_reraises_and_emits_failed() -> None:
    """Exception from next() should be re-raised; node.failed should be emitted."""
    emitter = _RecordingEmitter()
    mw = LogfireMiddleware()

    async def _raising_next(request: HandlerRequest) -> Outcome:
        raise RuntimeError("crash")

    with pytest.raises(RuntimeError, match="crash"):
        await mw(make_request(emitter=emitter), _raising_next)

    assert "node.failed" in emitter.types()
