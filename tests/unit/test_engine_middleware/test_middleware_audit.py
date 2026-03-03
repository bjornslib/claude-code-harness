"""Tests for AuditMiddleware (F10).

Coverage:
- Two AuditEntry records written per handler invocation (pre + post).
- Pre-entry: from_status="pending", to_status="active".
- Post-entry: from_status="active", to_status=<outcome.status.value>.
- agent_id resolved from context["$session_id"].
- Missing $session_id defaults to "unknown".
- OSError from writer is caught — handler outcome still returned.
- Generic Exception from writer is caught — handler outcome still returned.
- No writer injected: _StubAuditWriter is used (no-op, no error).
"""
from __future__ import annotations

from typing import Any

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.graph import Node
from cobuilder.engine.middleware.audit import AuditMiddleware, _StubAuditWriter
from cobuilder.engine.middleware.chain import HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingWriter:
    """Audit writer that records every entry passed to write()."""

    def __init__(self) -> None:
        self.entries: list[Any] = []

    def write(self, entry: Any) -> None:
        self.entries.append(entry)


class _RaisingWriter:
    """Audit writer that raises a configurable exception on write()."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.call_count = int(0)

    def write(self, entry: Any) -> None:
        self.call_count += 1
        raise self._exc


class _RaisingAfterFirstWriter:
    """Writer that succeeds on first write and raises on subsequent writes."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.entries: list[Any] = []

    def write(self, entry: Any) -> None:
        if self.entries:
            raise self._exc
        self.entries.append(entry)


def make_node(id: str = "node1") -> Node:
    return Node(id=id, shape="box", label=id)


def make_request(
    node: Node | None = None,
    session_id: str | None = "session-abc",
) -> HandlerRequest:
    if node is None:
        node = make_node()
    context: dict[str, Any] = {}
    if session_id is not None:
        context["$session_id"] = session_id
    return HandlerRequest(
        node=node,
        context=PipelineContext(initial=context),
        emitter=None,
        pipeline_id="pipe",
        visit_count=1,
        attempt_number=0,
    )


def make_outcome(status: OutcomeStatus = OutcomeStatus.SUCCESS) -> Outcome:
    return Outcome(status=status)


async def _next_success(request: HandlerRequest) -> Outcome:
    return make_outcome(OutcomeStatus.SUCCESS)


async def _next_failure(request: HandlerRequest) -> Outcome:
    return make_outcome(OutcomeStatus.FAILURE)


async def _next_partial(request: HandlerRequest) -> Outcome:
    return make_outcome(OutcomeStatus.PARTIAL_SUCCESS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_entries_written_per_invocation() -> None:
    """Exactly two AuditEntry records must be written per handler invocation."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    await mw(make_request(), _next_success)

    assert len(writer.entries) == 2, (
        f"Expected 2 entries, got {len(writer.entries)}"
    )


@pytest.mark.asyncio
async def test_pre_entry_status_pair() -> None:
    """First entry must have from_status='pending' and to_status='active'."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    await mw(make_request(), _next_success)

    pre = writer.entries[0]
    assert pre.from_status == "pending"
    assert pre.to_status == "active"


@pytest.mark.asyncio
async def test_post_entry_status_reflects_success_outcome() -> None:
    """Post-entry must have from_status='active' and to_status='success'."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    await mw(make_request(), _next_success)

    post = writer.entries[1]
    assert post.from_status == "active"
    assert post.to_status == OutcomeStatus.SUCCESS.value  # "success"


@pytest.mark.asyncio
async def test_post_entry_status_reflects_failure_outcome() -> None:
    """Post-entry to_status must match outcome.status.value for FAILURE."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    await mw(make_request(), _next_failure)

    post = writer.entries[1]
    assert post.to_status == OutcomeStatus.FAILURE.value  # "failure"


@pytest.mark.asyncio
async def test_post_entry_status_reflects_partial_success_outcome() -> None:
    """Post-entry to_status must match outcome.status.value for PARTIAL_SUCCESS."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    await mw(make_request(), _next_partial)

    post = writer.entries[1]
    assert post.to_status == OutcomeStatus.PARTIAL_SUCCESS.value  # "partial_success"


@pytest.mark.asyncio
async def test_agent_id_from_session_id_context() -> None:
    """agent_id in both entries must match context['$session_id']."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    await mw(make_request(session_id="user-session-xyz"), _next_success)

    assert writer.entries[0].agent_id == "user-session-xyz"
    assert writer.entries[1].agent_id == "user-session-xyz"


@pytest.mark.asyncio
async def test_missing_session_id_defaults_to_unknown() -> None:
    """When $session_id is absent, agent_id must default to 'unknown'."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)

    # make_request with session_id=None omits the key from context
    await mw(make_request(session_id=None), _next_success)

    assert writer.entries[0].agent_id == "unknown"
    assert writer.entries[1].agent_id == "unknown"


@pytest.mark.asyncio
async def test_oserror_on_pre_write_does_not_propagate() -> None:
    """OSError raised by writer.write() during pre-execution must be caught.

    The handler must still be invoked and its outcome returned.
    """
    writer = _RaisingWriter(OSError("disk full"))
    mw = AuditMiddleware(writer=writer)

    result = await mw(make_request(), _next_success)

    assert result.status == OutcomeStatus.SUCCESS
    # Both writes were attempted (and both raised, but outcome was still returned)
    assert writer.call_count >= 1


@pytest.mark.asyncio
async def test_oserror_on_post_write_does_not_propagate() -> None:
    """OSError raised on the post-execution write must be caught.

    The handler outcome must still be returned to the caller.
    """
    writer = _RaisingAfterFirstWriter(OSError("disk full on post"))
    mw = AuditMiddleware(writer=writer)

    result = await mw(make_request(), _next_failure)

    assert result.status == OutcomeStatus.FAILURE
    # Pre-entry was recorded, post-entry raised but was caught.
    assert len(writer.entries) == 1
    assert writer.entries[0].from_status == "pending"


@pytest.mark.asyncio
async def test_generic_exception_on_pre_write_does_not_propagate() -> None:
    """Non-OSError exceptions from pre-write must also be caught."""
    writer = _RaisingWriter(ValueError("bad data"))
    mw = AuditMiddleware(writer=writer)

    result = await mw(make_request(), _next_success)

    assert result.status == OutcomeStatus.SUCCESS


@pytest.mark.asyncio
async def test_no_writer_stub_is_noop_and_does_not_raise() -> None:
    """When no writer is provided, _StubAuditWriter is used — no error raised."""
    mw = AuditMiddleware(writer=None)
    result = await mw(make_request(), _next_success)
    assert result.status == OutcomeStatus.SUCCESS


@pytest.mark.asyncio
async def test_stub_audit_writer_write_is_noop() -> None:
    """_StubAuditWriter.write() accepts any argument and does nothing."""
    stub = _StubAuditWriter()
    stub.write("anything")
    stub.write(None)
    stub.write({"key": "value"})
    # No assertion needed — just checking no exception is raised.


@pytest.mark.asyncio
async def test_node_id_in_entries_matches_request_node() -> None:
    """Both entries must carry the node_id from the request node."""
    writer = _RecordingWriter()
    mw = AuditMiddleware(writer=writer)
    node = make_node(id="my-special-node")
    request = HandlerRequest(
        node=node,
        context=PipelineContext(),
        emitter=None,
        pipeline_id="pipe",
        visit_count=1,
        attempt_number=0,
    )
    await mw(request, _next_success)

    assert writer.entries[0].node_id == "my-special-node"
    assert writer.entries[1].node_id == "my-special-node"


@pytest.mark.asyncio
async def test_outcome_returned_even_when_both_writes_raise() -> None:
    """Handler outcome is returned regardless of writer failures on both writes."""
    writer = _RaisingWriter(OSError("catastrophic"))
    mw = AuditMiddleware(writer=writer)

    result = await mw(make_request(), _next_failure)

    assert result.status == OutcomeStatus.FAILURE
