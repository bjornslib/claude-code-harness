"""Handler protocol and unified request object.

**Handler Protocol** (AMD-8):

Every node handler must implement ``async def execute(request: HandlerRequest)
→ Outcome``.  The protocol is ``runtime_checkable`` so that the registry can
validate handler objects at registration time using ``isinstance(obj, Handler)``.

**HandlerRequest** (AMD-8):

The ``EngineRunner`` ALWAYS wraps handler calls in ``HandlerRequest``, even
when no middlewares are configured.  This eliminates the signature mismatch
between direct handler calls and middleware-wrapped calls.  The middleware
chain's callable signature is identical to a raw handler call::

    async (request: HandlerRequest) -> Outcome

Handlers are stateless — all state is passed in via ``request.node`` and
``request.context``.  Handlers must not hold instance state that persists
between ``execute()`` calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from cobuilder.engine.graph import Node

if TYPE_CHECKING:
    from cobuilder.engine.context import PipelineContext
    from cobuilder.engine.outcome import Outcome


@dataclass(frozen=True)
class HandlerRequest:
    """AMD-8: Unified request object for handler invocation.

    Attributes:
        node:           The DOT node being executed.
        context:        Current pipeline context (live reference for sequential
                        handlers; snapshot copy for fan-out branches).
        emitter:        EventEmitter for the Epic 4 event bus.  ``None`` in
                        Epic 1 — handlers must treat this as optional.
        pipeline_id:    Pipeline identifier (DOT file base name).
        visit_count:    Number of times this node has been visited in this run.
        attempt_number: Retry attempt number (1-indexed; 1 = first attempt).
        run_dir:        Absolute path to the pipeline run directory.
    """

    node: Node
    context: "PipelineContext"
    emitter: Any = None           # EventEmitter (Epic 4); None in Epic 1
    pipeline_id: str = ""
    visit_count: int = 1
    attempt_number: int = 1
    run_dir: str = ""


@runtime_checkable
class Handler(Protocol):
    """Protocol that all node handlers must satisfy.

    Handlers are stateless; all state lives in ``PipelineContext``.
    The method must be ``async`` to support ``ParallelHandler``
    (``asyncio.TaskGroup``).  Sequential handlers simply contain their
    logic inside a coroutine body.

    AMD-8: The signature uses ``HandlerRequest`` rather than
    ``(Node, PipelineContext)`` so that the runner can call handlers
    identically with or without middleware wrapping.
    """

    async def execute(self, request: HandlerRequest) -> "Outcome":
        """Execute the handler's logic for the request.

        Args:
            request: ``HandlerRequest`` wrapping node, context, and metadata.

        Returns:
            ``Outcome`` with status, context_updates, preferred_label,
            suggested_next, and optional metadata.

        Raises:
            HandlerError: If the handler encounters an unrecoverable error.
                          The runner catches this and writes a VIOLATION signal.
        """
        ...
