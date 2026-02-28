"""Tests for TokenCountingMiddleware (F8).

Coverage:
- Tokens accumulate into $node_tokens and $total_tokens when raw_messages present.
- Empty raw_messages: context unchanged, no-op.
- Cumulative: 3 nodes each with 100 tokens → $total_tokens == 300.
- context.updated event emitted when tokens change.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.events.types import PipelineEvent
from cobuilder.engine.graph import Node
from cobuilder.engine.middleware.chain import HandlerRequest
from cobuilder.engine.middleware.token_counter import TokenCountingMiddleware
from cobuilder.engine.outcome import Outcome, OutcomeStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingEmitter:
    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []

    async def emit(self, event: PipelineEvent) -> None:
        self.events.append(event)

    async def aclose(self) -> None:
        return

    def types(self) -> list[str]:
        return [e.type for e in self.events]


def _mock_usage(input_tokens: int, output_tokens: int) -> Any:
    """Build a mock SDK usage object."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    return usage


def _mock_message(input_tokens: int = 50, output_tokens: int = 50) -> Any:
    """Build a mock SDK ResultMessage with usage."""
    msg = MagicMock()
    msg.usage = _mock_usage(input_tokens, output_tokens)
    return msg


def make_node(id: str = "n1") -> Node:
    return Node(id=id, shape="box", label=id)


def make_outcome(raw_messages: list[Any] | None = None) -> Outcome:
    return Outcome(status=OutcomeStatus.SUCCESS, raw_messages=raw_messages or [])


def make_request(
    context: PipelineContext | None = None,
    emitter: Any = None,
) -> HandlerRequest:
    return HandlerRequest(
        node=make_node(),
        context=context if context is not None else PipelineContext(),
        emitter=emitter,
        pipeline_id="pipe",
        visit_count=1,
        attempt_number=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tokens_accumulated_from_raw_messages() -> None:
    """$node_tokens and $total_tokens updated when raw_messages contain usage."""
    context = PipelineContext()
    msg = _mock_message(input_tokens=60, output_tokens=40)
    outcome = make_outcome(raw_messages=[msg])

    async def _next(request: HandlerRequest) -> Outcome:
        return outcome

    mw = TokenCountingMiddleware()
    result = await mw(make_request(context=context), _next)

    assert result.status == OutcomeStatus.SUCCESS
    assert context.get("$node_tokens") == 100  # 60 + 40
    assert context.get("$total_tokens") == 100


@pytest.mark.asyncio
async def test_empty_raw_messages_is_noop() -> None:
    """Context unchanged when Outcome.raw_messages is empty."""
    context = PipelineContext()
    outcome = make_outcome(raw_messages=[])

    async def _next(request: HandlerRequest) -> Outcome:
        return outcome

    mw = TokenCountingMiddleware()
    await mw(make_request(context=context), _next)

    assert context.get("$node_tokens") is None
    assert context.get("$total_tokens") is None


@pytest.mark.asyncio
async def test_cumulative_total_tokens() -> None:
    """Three consecutive nodes with 100 tokens each → $total_tokens == 300."""
    context = PipelineContext()
    mw = TokenCountingMiddleware()

    for _ in range(3):
        msg = _mock_message(input_tokens=50, output_tokens=50)
        outcome = make_outcome(raw_messages=[msg])

        async def _next(request: HandlerRequest, _o: Outcome = outcome) -> Outcome:
            return _o

        await mw(make_request(context=context), _next)

    assert context.get("$total_tokens") == 300


@pytest.mark.asyncio
async def test_context_updated_event_emitted_when_tokens_change() -> None:
    """context.updated event should be emitted when token counts change."""
    context = PipelineContext()
    emitter = _RecordingEmitter()
    msg = _mock_message(input_tokens=30, output_tokens=20)
    outcome = make_outcome(raw_messages=[msg])

    async def _next(request: HandlerRequest) -> Outcome:
        return outcome

    mw = TokenCountingMiddleware()
    await mw(make_request(context=context, emitter=emitter), _next)

    assert "context.updated" in emitter.types()


@pytest.mark.asyncio
async def test_no_context_updated_when_no_tokens() -> None:
    """No context.updated event when raw_messages is empty."""
    context = PipelineContext()
    emitter = _RecordingEmitter()
    outcome = make_outcome(raw_messages=[])

    async def _next(request: HandlerRequest) -> Outcome:
        return outcome

    mw = TokenCountingMiddleware()
    await mw(make_request(context=context, emitter=emitter), _next)

    assert "context.updated" not in emitter.types()


@pytest.mark.asyncio
async def test_message_without_usage_attribute_skipped() -> None:
    """Messages without a 'usage' attribute should be silently skipped."""
    context = PipelineContext()
    msg_no_usage = MagicMock(spec=[])  # No attributes at all
    msg_with_usage = _mock_message(input_tokens=10, output_tokens=10)
    outcome = make_outcome(raw_messages=[msg_no_usage, msg_with_usage])

    async def _next(request: HandlerRequest) -> Outcome:
        return outcome

    mw = TokenCountingMiddleware()
    await mw(make_request(context=context), _next)

    assert context.get("$node_tokens") == 20  # Only the message with usage counted
