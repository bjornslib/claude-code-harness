"""StartHandler — handles Mdiamond (pipeline start) nodes.

The start node is a no-op sentinel that signals the beginning of pipeline
execution.  It writes no signals, spawns no processes, and makes no LLM calls.
The engine loop transitions immediately to the next node after executing it.

AC-F4:
- Returns ``Outcome(status=SKIPPED, context_updates={})`` for any Mdiamond node.
- Does not write any signals, spawn any processes, or modify any files.
"""
from __future__ import annotations

from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus


class StartHandler:
    """No-op handler for pipeline start nodes (``Mdiamond`` shape).

    Implements the ``Handler`` protocol.  Returns ``SKIPPED`` immediately
    without any side effects.
    """

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Return a SKIPPED outcome — start nodes are no-ops.

        Args:
            request: HandlerRequest (node, context, metadata).

        Returns:
            ``Outcome(status=SKIPPED)`` with no context updates.
        """
        return Outcome(status=OutcomeStatus.SKIPPED)


# Satisfy the Protocol at runtime (not strictly required but documents intent)
assert isinstance(StartHandler(), Handler)
