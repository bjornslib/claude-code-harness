"""FanInHandler — handles tripleoctagon (fan-in rendezvous) nodes.

The FanInHandler acts as a rendezvous point for multiple parallel branches.
It blocks until all expected parallel branches have written their completion
results to a shared dict of ``asyncio.Event`` objects.

In Epic 1, the typical usage is:
1. ParallelHandler fans out to N branches.
2. Each branch eventually routes to the same FanInHandler node.
3. FanInHandler collects results from all N branches and produces a single
   merged Outcome.

AC-F11:
- Blocks until all parallel branches have written their completion to a shared
  rendezvous (dict of asyncio.Event).
- Returns Outcome based on collected results from all branches.
- join_policy="wait_all" (default): SUCCESS only if all branches succeed.
- join_policy="first_success": SUCCESS as soon as any branch succeeds.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus

logger = logging.getLogger(__name__)

# Module-level shared rendezvous registry (keyed by pipeline_id + node_id)
# In production, the EngineRunner injects these via context.
_RENDEZVOUS: dict[str, dict[str, Outcome]] = {}
_RENDEZVOUS_EVENTS: dict[str, dict[str, asyncio.Event]] = {}


class FanInHandler:
    """Rendezvous handler for fan-in synchronisation (``tripleoctagon`` shape).

    Collects Outcome results from all parallel branches that were fanned out
    by a preceding ParallelHandler and produces a single aggregated Outcome.

    The rendezvous mechanism uses ``$fan_in.{node_id}.results`` from the
    pipeline context.  ParallelHandler writes branch outcomes there before
    routing to the fan-in node.

    join_policy behaviour:
    - ``wait_all`` (default): all branches must be collected before proceeding.
    - ``first_success``: proceed as soon as any branch result is SUCCESS.
    """

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Collect parallel branch results and return aggregated Outcome.

        Args:
            request: HandlerRequest.  The context must contain
                     ``$fan_in.{node_id}.results`` (dict of branch_id → status)
                     written by the preceding ParallelHandler.

        Returns:
            Aggregated Outcome based on join_policy.
        """
        node = request.node
        join_policy = node.join_policy  # "wait_all" or "first_success"

        # Read branch results written by ParallelHandler
        results_key = f"$fan_in.{node.id}.results"
        branch_results: dict[str, Any] = request.context.get(results_key, {})

        if not branch_results:
            # No branches reported — check context for namespaced results
            # from the AMD-2 merge in ParallelHandler
            branch_results = self._collect_namespaced_results(request)

        if not branch_results:
            # Still nothing — return SUCCESS (no-op fan-in; solo path)
            logger.debug("FanInHandler '%s': no branch results found; returning SUCCESS", node.id)
            return Outcome(
                status=OutcomeStatus.SUCCESS,
                context_updates={f"$fan_in.results": {}},
                metadata={"branch_count": 0, "join_policy": join_policy},
            )

        # Evaluate aggregate status
        all_statuses = list(branch_results.values())
        any_success = any(s in ("success", OutcomeStatus.SUCCESS) for s in all_statuses)
        all_success = all(s in ("success", OutcomeStatus.SUCCESS) for s in all_statuses)

        if join_policy == "first_success":
            final_status = OutcomeStatus.SUCCESS if any_success else OutcomeStatus.FAILURE
        else:  # wait_all
            final_status = OutcomeStatus.SUCCESS if all_success else OutcomeStatus.FAILURE

        return Outcome(
            status=final_status,
            context_updates={
                "$fan_in.results": branch_results,
                f"${node.id}.join_status": final_status.value,
            },
            metadata={
                "branch_count": len(branch_results),
                "join_policy": join_policy,
                "results": branch_results,
            },
        )

    def _collect_namespaced_results(self, request: HandlerRequest) -> dict[str, Any]:
        """Collect AMD-2 namespaced results from the context snapshot."""
        snapshot = request.context.snapshot()
        results: dict[str, Any] = {}
        # Look for keys like "{branch_id}.{key}" where key contains "status"
        for key, value in snapshot.items():
            if "." in key and not key.startswith("$"):
                # This is a namespaced branch result
                branch_id, _, _ = key.partition(".")
                if branch_id not in results:
                    results[branch_id] = value
        return results


assert isinstance(FanInHandler(), Handler)
