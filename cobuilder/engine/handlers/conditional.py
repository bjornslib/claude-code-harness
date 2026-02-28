"""ConditionalHandler — handles diamond (conditional routing) nodes.

Conditional nodes are pure routing markers.  The handler itself does nothing
beyond returning SUCCESS.  All routing logic is performed by EdgeSelector
evaluating the edge condition expressions.

AC-F7:
- Returns ``Outcome(status=SUCCESS, preferred_label=None, suggested_next=None)``
  with no context updates.
- Does not make LLM calls or spawn processes.
"""
from __future__ import annotations

from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus


class ConditionalHandler:
    """No-op routing handler for conditional nodes (``diamond`` shape).

    The decision of which edge to follow is delegated entirely to
    EdgeSelector.  This handler simply signals that the node has been
    "executed" (i.e., reached) so the runner can proceed to edge selection.
    """

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Return SUCCESS with no side effects — routing is EdgeSelector's job.

        Args:
            request: HandlerRequest (node, context, metadata).

        Returns:
            ``Outcome(status=SUCCESS)`` with no context updates.
        """
        return Outcome(status=OutcomeStatus.SUCCESS)


assert isinstance(ConditionalHandler(), Handler)
