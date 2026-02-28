"""Middleware chain — compose_middleware() and HandlerRequest.

The middleware chain pattern wraps every handler.execute() call through a
composable async chain.  Right-to-left composition means the first middleware
in the list is the outermost wrapper:

    request → LogfireMiddleware → TokenCountingMiddleware → RetryMiddleware → Handler
    response ←─────────────────────────────────────────────────────────────────────

Each middleware is an async callable that receives:
    (request: HandlerRequest, next: Callable[[HandlerRequest], Awaitable[Outcome]])
and returns an Outcome.

HandlerRequest carries all context a middleware needs — the node, context,
emitter, pipeline_id, and visit_count — so that middlewares can emit events
and access context without additional injection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Protocol

from cobuilder.engine.graph import Node

if TYPE_CHECKING:
    from cobuilder.engine.context import PipelineContext
    from cobuilder.engine.outcome import Outcome


# ---------------------------------------------------------------------------
# HandlerRequest — unified request object for handler invocation
# ---------------------------------------------------------------------------

@dataclass
class HandlerRequest:
    """Carries everything a middleware or handler needs for one invocation.

    This is the middleware-layer equivalent of the base.HandlerRequest (which
    is also named HandlerRequest for historical reasons and is imported by the
    runner).  Both share the same field layout — the middleware package defines
    its own copy so it has no circular dependency on handlers.base.

    Attributes:
        node:           The DOT node being executed.
        context:        Current pipeline context.
        emitter:        EventEmitter for the Epic 4 event bus (Any to avoid
                        circular import; treat as EventEmitter protocol).
        pipeline_id:    Pipeline identifier (DOT file base name).
        visit_count:    Current visit count for this node.
        attempt_number: Current retry attempt (0 = first attempt).
        run_dir:        Absolute path to the pipeline run directory.
    """

    node: Node
    context: "PipelineContext"
    emitter: Any = None          # EventEmitter; Any avoids circular import
    pipeline_id: str = ""
    visit_count: int = 1
    attempt_number: int = 0
    run_dir: str = ""


# ---------------------------------------------------------------------------
# Middleware Protocol
# ---------------------------------------------------------------------------

class Middleware(Protocol):
    """Protocol that every middleware must satisfy.

    A middleware is an async callable accepting (request, next) and returning
    an Outcome.  It must call next(request) exactly once (unless implementing
    retry logic that calls it multiple times).  It must not swallow exceptions
    from next() unless retry logic dictates returning a FAILURE Outcome instead.
    """

    async def __call__(
        self,
        request: HandlerRequest,
        next: Callable[[HandlerRequest], Awaitable["Outcome"]],
    ) -> "Outcome":
        """Process a handler request.

        Args:
            request: Unified request object carrying node, context, emitter.
            next:    Callable that invokes the next middleware or the handler.

        Returns:
            Outcome from the handler (possibly transformed by this middleware).
        """
        ...


# ---------------------------------------------------------------------------
# compose_middleware — right-to-left composition
# ---------------------------------------------------------------------------

def compose_middleware(
    middlewares: list[Middleware],
    handler: Any,
) -> Callable[[HandlerRequest], Awaitable["Outcome"]]:
    """Compose a list of middlewares around a handler into a single callable.

    Composition is right-to-left: the first element in *middlewares* is the
    outermost wrapper (called first, returned from last).  An empty list
    returns a callable that invokes handler.execute(request) directly.

    The returned callable has signature::

        async (request: HandlerRequest) -> Outcome

    which is identical to the handler protocol.

    Args:
        middlewares: Ordered list of middleware callables.  May be empty.
        handler:     The innermost Handler instance (must implement execute()).

    Returns:
        A composed async callable.

    Example::

        chain = compose_middleware(
            [LogfireMiddleware(), RetryMiddleware()],
            my_handler,
        )
        outcome = await chain(request)
    """
    async def execute(request: HandlerRequest) -> "Outcome":
        return await handler.execute(request)

    for mw in reversed(middlewares):
        inner = execute

        async def execute(  # noqa: E731
            request: HandlerRequest,
            _mw: Middleware = mw,
            _inner: Callable[[HandlerRequest], Awaitable["Outcome"]] = inner,
        ) -> "Outcome":
            return await _mw(request, _inner)

    return execute
