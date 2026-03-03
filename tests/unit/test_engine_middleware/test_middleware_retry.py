"""Tests for RetryMiddleware (F9).

Coverage:
- next() fails twice then succeeds: retry.triggered emitted twice, final outcome SUCCESS.
- next() fails 3 times (exhausting retries): final FAILURE returned after 4 total calls.
- Backoff timing: asyncio.sleep called with 1.0, 2.0, 4.0 seconds.
- max_retries=0: no retry, first FAILURE returned immediately (no sleep).
- No emitter: middleware runs without raising.
- attempt_number on HandlerRequest is incremented on each retry.
- Exception from next() propagates when retry_on_exception=False (default).
- Exception from next() is retried when retry_on_exception=True.
- node.attrs["max_retries"] overrides default_max_retries.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.events.types import PipelineEvent
from cobuilder.engine.graph import Node
from cobuilder.engine.middleware.chain import HandlerRequest
from cobuilder.engine.middleware.retry import RetryMiddleware
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

    def retry_events(self) -> list[PipelineEvent]:
        return [e for e in self.events if e.type == "retry.triggered"]


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


def _counter_next(fail_count: int, *, then_status: OutcomeStatus = OutcomeStatus.SUCCESS):
    """Return a next() callable that fails `fail_count` times then returns `then_status`."""
    calls: list[int] = [0]

    async def _next(request: HandlerRequest) -> Outcome:
        calls[0] += 1
        if calls[0] <= fail_count:
            return make_outcome(OutcomeStatus.FAILURE)
        return make_outcome(then_status)

    _next.calls = calls  # type: ignore[attr-defined]
    return _next


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fails_twice_then_succeeds_emits_retry_triggered_twice() -> None:
    """next() fails twice then succeeds: retry.triggered emitted exactly twice; outcome SUCCESS."""
    emitter = _RecordingEmitter()
    next_fn = _counter_next(fail_count=2)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        result = await mw(make_request(emitter=emitter), next_fn)

    assert result.status == OutcomeStatus.SUCCESS
    assert len(emitter.retry_events()) == 2, (
        f"Expected 2 retry.triggered events, got {len(emitter.retry_events())}"
    )


@pytest.mark.asyncio
async def test_fails_twice_then_succeeds_total_calls() -> None:
    """next() is called exactly 3 times when failing twice then succeeding."""
    next_fn = _counter_next(fail_count=2)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        await mw(make_request(), next_fn)

    assert next_fn.calls[0] == 3  # 2 failures + 1 success


@pytest.mark.asyncio
async def test_exhausts_all_retries_returns_failure() -> None:
    """next() always fails: FAILURE returned after exhausting max_retries (default 3)."""
    emitter = _RecordingEmitter()
    next_fn = _counter_next(fail_count=100)  # Always fails

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        result = await mw(make_request(emitter=emitter), next_fn)

    assert result.status == OutcomeStatus.FAILURE
    # With max_retries=3: 1 original + 3 retries = 4 total calls
    assert next_fn.calls[0] == 4
    # retry.triggered emitted 3 times (before each of the 3 retries)
    assert len(emitter.retry_events()) == 3


@pytest.mark.asyncio
async def test_backoff_timing_exponential() -> None:
    """asyncio.sleep called with 1.0, 2.0, 4.0 seconds on successive failures."""
    sleep_calls: list[float] = []

    async def _recording_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    next_fn = _counter_next(fail_count=100)  # Always fails

    with patch("asyncio.sleep", side_effect=_recording_sleep):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        await mw(make_request(), next_fn)

    assert sleep_calls == [1.0, 2.0, 4.0], (
        f"Expected backoff [1.0, 2.0, 4.0], got {sleep_calls}"
    )


@pytest.mark.asyncio
async def test_backoff_timing_custom_base_delay() -> None:
    """Exponential back-off respects a custom base_delay_s."""
    sleep_calls: list[float] = []

    async def _recording_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    next_fn = _counter_next(fail_count=100)

    with patch("asyncio.sleep", side_effect=_recording_sleep):
        mw = RetryMiddleware(default_max_retries=2, base_delay_s=0.5)
        await mw(make_request(), next_fn)

    # attempt 0: 0.5 * 2^0 = 0.5; attempt 1: 0.5 * 2^1 = 1.0
    assert sleep_calls == [0.5, 1.0]


@pytest.mark.asyncio
async def test_max_retries_zero_no_retry_no_sleep() -> None:
    """max_retries=0: first FAILURE returned immediately; no sleep, no retry event."""
    emitter = _RecordingEmitter()
    next_fn = _counter_next(fail_count=100)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mw = RetryMiddleware(default_max_retries=0, base_delay_s=1.0)
        result = await mw(make_request(emitter=emitter), next_fn)

    assert result.status == OutcomeStatus.FAILURE
    assert next_fn.calls[0] == 1, "With max_retries=0, next() called exactly once"
    mock_sleep.assert_not_called()
    assert len(emitter.retry_events()) == 0


@pytest.mark.asyncio
async def test_node_attr_max_retries_overrides_default() -> None:
    """node.attrs['max_retries'] takes precedence over RetryMiddleware.default_max_retries."""
    next_fn = _counter_next(fail_count=100)

    # Node says max_retries=1; middleware default is 3 — node wins
    node = make_node(max_retries=1)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        result = await mw(make_request(node=node), next_fn)

    assert result.status == OutcomeStatus.FAILURE
    # 1 original + 1 retry = 2 total calls
    assert next_fn.calls[0] == 2


@pytest.mark.asyncio
async def test_no_emitter_does_not_raise() -> None:
    """With emitter=None, RetryMiddleware retries normally without crashing."""
    next_fn = _counter_next(fail_count=1)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        result = await mw(make_request(emitter=None), next_fn)

    assert result.status == OutcomeStatus.SUCCESS


@pytest.mark.asyncio
async def test_attempt_number_increments_per_retry() -> None:
    """HandlerRequest.attempt_number is incremented on each retry."""
    attempt_numbers: list[int] = []

    async def _recording_next(request: HandlerRequest) -> Outcome:
        attempt_numbers.append(request.attempt_number)
        return make_outcome(OutcomeStatus.FAILURE)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=2, base_delay_s=1.0)
        await mw(make_request(), _recording_next)

    # 1st call: attempt_number=0; 2nd: 1; 3rd: 2
    assert attempt_numbers == [0, 1, 2]


@pytest.mark.asyncio
async def test_success_on_first_call_no_retry() -> None:
    """If next() succeeds on the first call, no retry.triggered event and no sleep."""
    emitter = _RecordingEmitter()

    async def _always_success(request: HandlerRequest) -> Outcome:
        return make_outcome(OutcomeStatus.SUCCESS)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        result = await mw(make_request(emitter=emitter), _always_success)

    assert result.status == OutcomeStatus.SUCCESS
    mock_sleep.assert_not_called()
    assert len(emitter.retry_events()) == 0


@pytest.mark.asyncio
async def test_exception_propagates_when_retry_on_exception_false() -> None:
    """Exception from next() propagates immediately when retry_on_exception=False."""

    async def _raising_next(request: HandlerRequest) -> Outcome:
        raise RuntimeError("boom")

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mw = RetryMiddleware(default_max_retries=3, retry_on_exception=False)
        with pytest.raises(RuntimeError, match="boom"):
            await mw(make_request(), _raising_next)

    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_exception_retried_when_retry_on_exception_true() -> None:
    """Exception from next() is retried when retry_on_exception=True."""
    calls: list[int] = [0]

    async def _raise_then_succeed(request: HandlerRequest) -> Outcome:
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("transient")
        return make_outcome(OutcomeStatus.SUCCESS)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(
            default_max_retries=3,
            base_delay_s=1.0,
            retry_on_exception=True,
        )
        result = await mw(make_request(), _raise_then_succeed)

    assert result.status == OutcomeStatus.SUCCESS
    assert calls[0] == 2


@pytest.mark.asyncio
async def test_retry_triggered_event_contains_correct_fields() -> None:
    """retry.triggered events contain attempt_number, backoff_ms, and error_type."""
    emitter = _RecordingEmitter()
    next_fn = _counter_next(fail_count=2)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        mw = RetryMiddleware(default_max_retries=3, base_delay_s=1.0)
        await mw(make_request(emitter=emitter, pipeline_id="test-pipe"), next_fn)

    retry_events = emitter.retry_events()
    assert len(retry_events) == 2

    first = retry_events[0]
    assert first.type == "retry.triggered"
    assert "attempt_number" in first.data
    assert "backoff_ms" in first.data
    assert "error_type" in first.data
    assert first.data["attempt_number"] == 1  # Human-readable: 1st retry
    assert first.data["backoff_ms"] == pytest.approx(1000.0)  # 1.0s * 1000

    second = retry_events[1]
    assert second.data["attempt_number"] == 2
    assert second.data["backoff_ms"] == pytest.approx(2000.0)  # 2.0s * 1000
