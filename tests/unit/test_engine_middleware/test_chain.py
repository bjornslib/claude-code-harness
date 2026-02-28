"""Tests for compose_middleware() and HandlerRequest (F6).

Coverage:
- Call-order verification: middlewares execute in declared order.
- Exception propagation through the chain.
- Empty chain invokes handler directly.
"""
from __future__ import annotations

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.graph import Node
from cobuilder.engine.middleware.chain import HandlerRequest, compose_middleware
from cobuilder.engine.outcome import Outcome, OutcomeStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_node(id: str = "n1", shape: str = "box") -> Node:
    return Node(id=id, shape=shape, label=id)


def make_request(node: Node | None = None) -> HandlerRequest:
    if node is None:
        node = make_node()
    return HandlerRequest(
        node=node,
        context=PipelineContext(),
        emitter=None,
        pipeline_id="test-pipeline",
        visit_count=1,
        attempt_number=0,
        run_dir="",
    )


def make_outcome(status: OutcomeStatus = OutcomeStatus.SUCCESS) -> Outcome:
    return Outcome(status=status)


class _MockHandler:
    """Handler stub that returns a fixed outcome."""

    def __init__(self, outcome: Outcome | None = None) -> None:
        self._outcome = outcome or make_outcome()

    async def execute(self, request: HandlerRequest) -> Outcome:
        return self._outcome


# ---------------------------------------------------------------------------
# Tests: call order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_order_three_middlewares() -> None:
    """Three middlewares must be called in declared order (outermost first)."""
    order: list[str] = []

    class _MW:
        def __init__(self, name: str) -> None:
            self._name = name

        async def __call__(self, request, next):
            order.append(f"{self._name}:pre")
            result = await next(request)
            order.append(f"{self._name}:post")
            return result

    handler = _MockHandler()
    chain = compose_middleware([_MW("A"), _MW("B"), _MW("C")], handler)
    await chain(make_request())

    assert order == [
        "A:pre", "B:pre", "C:pre",
        "C:post", "B:post", "A:post",
    ], f"Unexpected order: {order}"


@pytest.mark.asyncio
async def test_empty_chain_calls_handler_directly() -> None:
    """An empty middleware list should call handler.execute() directly."""
    expected = make_outcome(OutcomeStatus.SUCCESS)
    handler = _MockHandler(expected)
    chain = compose_middleware([], handler)
    result = await chain(make_request())
    assert result is expected


# ---------------------------------------------------------------------------
# Tests: exception propagation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_propagates_through_chain() -> None:
    """An exception raised in the handler propagates through all middlewares."""
    class _BangHandler:
        async def execute(self, request: HandlerRequest) -> Outcome:
            raise ValueError("boom")

    class _PassthroughMW:
        async def __call__(self, request, next):
            return await next(request)

    chain = compose_middleware([_PassthroughMW(), _PassthroughMW()], _BangHandler())
    with pytest.raises(ValueError, match="boom"):
        await chain(make_request())


@pytest.mark.asyncio
async def test_outer_middleware_can_catch_inner_exception() -> None:
    """Outer middleware can wrap next() in try/except and handle exceptions."""
    class _CatchingMW:
        async def __call__(self, request, next):
            try:
                return await next(request)
            except ValueError:
                return make_outcome(OutcomeStatus.FAILURE)

    class _BangHandler:
        async def execute(self, request: HandlerRequest) -> Outcome:
            raise ValueError("inner boom")

    chain = compose_middleware([_CatchingMW()], _BangHandler())
    result = await chain(make_request())
    assert result.status == OutcomeStatus.FAILURE


@pytest.mark.asyncio
async def test_each_middleware_receives_fresh_next() -> None:
    """Each middleware must receive a next callable bound to the rest of the chain."""
    calls: list[str] = []

    class _RecordingMW:
        def __init__(self, name: str) -> None:
            self._name = name

        async def __call__(self, request, next):
            calls.append(self._name)
            return await next(request)

    chain = compose_middleware(
        [_RecordingMW("first"), _RecordingMW("second")],
        _MockHandler(),
    )
    await chain(make_request())
    assert calls == ["first", "second"]


# ---------------------------------------------------------------------------
# Tests: HandlerRequest fields
# ---------------------------------------------------------------------------

def test_handler_request_defaults() -> None:
    """HandlerRequest should have sensible defaults for all optional fields."""
    req = HandlerRequest(node=make_node(), context=PipelineContext())
    assert req.emitter is None
    assert req.pipeline_id == ""
    assert req.visit_count == 1
    assert req.attempt_number == 0
    assert req.run_dir == ""
