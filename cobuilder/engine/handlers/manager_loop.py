"""ManagerLoopHandler — handles house (manager loop) nodes.

**STATUS: DEFERRED — AMD-10**

The ``house`` shape represents a recursive sub-pipeline manager loop.  This
handler is a stub that raises ``NotImplementedError`` when invoked.

The shape is fully parsed, registered in the HandlerRegistry, and accepted
by the validator (Validation Rule 10 emits a WARNING, not an error, when a
``house`` node is encountered).  The stub is clearly documented here with a
reference to AMD-10 so that future implementers have context.

AC-F13:
- ``ManagerLoopHandler.execute()`` raises
  ``NotImplementedError("ManagerLoopHandler is deferred to a future epic — see AMD-10")``.
- The validator emits a WARNING (not error) for ``house`` nodes.

**AMD-10 Design Notes** (for future implementation):

The ManagerLoopHandler should spawn a sub-engine process (not a recursive
in-process call) to avoid stack overflows on deeply nested pipelines.  The
sub-engine is a separate ``cobuilder pipeline run`` invocation with:
- The sub-pipeline DOT file derived from ``node.attrs["sub_pipeline"]``
- A fresh run directory under the parent run's ``nodes/<node_id>/sub-run/``
- The parent context serialised as ``--context`` flags or a context JSON file

The handler polls for the sub-engine's ``pipeline_complete.signal`` using the
same signal-polling protocol as CodergenHandler.

Depth is bounded by process memory (not call stack) because each level spawns
a new process.  A configurable ``ATTRACTOR_MAX_MANAGER_DEPTH`` env var (default
5) prevents runaway nesting.
"""
from __future__ import annotations

from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome


class ManagerLoopHandler:
    """Stub handler for manager loop nodes (``house`` shape).

    See module docstring and AMD-10 for deferred implementation context.
    """

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Raise NotImplementedError — ManagerLoopHandler is deferred.

        Args:
            request: HandlerRequest (ignored).

        Raises:
            NotImplementedError: Always.  This handler is a stub pending
                                 AMD-10 implementation.
        """
        raise NotImplementedError(
            "ManagerLoopHandler is deferred to a future epic — see AMD-10 in "
            "docs/sds/SD-PIPELINE-ENGINE-001-epic1-core-engine.md. "
            f"Node '{request.node.id}' uses the 'house' shape which requires "
            "recursive sub-pipeline management. This feature is not yet implemented."
        )


# TODO (AMD-10): Implement ManagerLoopHandler as a subprocess-based sub-engine
# that spawns a new 'cobuilder pipeline run' process for the sub-pipeline DOT
# file specified in node.attrs["sub_pipeline"].

assert isinstance(ManagerLoopHandler(), Handler)
