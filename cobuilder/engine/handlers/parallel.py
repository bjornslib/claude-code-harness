"""ParallelHandler — handles component (fan-out parallel) nodes.

Fans out execution to child nodes concurrently using ``asyncio.TaskGroup``.
Each child node receives a SNAPSHOT copy of the context (not the live
reference) so that branches cannot corrupt each other's state.

AC-F10:
- Uses ``asyncio.TaskGroup`` to fan-out all child nodes concurrently.
- Each child node executes in isolation with a snapshot copy of PipelineContext.
- For ``join_policy=wait_all``: waits for all; SUCCESS only if all succeed.
- For ``join_policy=first_success``: returns as soon as any child succeeds,
  cancelling remaining tasks.
- Merges child context updates back into main PipelineContext after join.

AMD-2 Fan-Out Context Merge Policy:
Child context_updates are namespaced as ``{child_node_id}.{key}`` to
prevent collisions when two branches write the same key.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ParallelHandler:
    """Fan-out handler for parallel execution nodes (``component`` shape).

    Child nodes to execute in parallel are identified via the ``$graph``
    context key.  The graph's outgoing edges from the current node are used
    to identify the immediate children.

    When ``join_policy=wait_all`` (default), all children must succeed for
    the overall outcome to be SUCCESS.  Any failure causes FAILURE.

    When ``join_policy=first_success``, the handler returns SUCCESS as soon
    as the first child succeeds, and cancels the rest.

    In Epic 1 the handler dispatches child handlers directly (in-process).
    In future epics, each child could be a separate orchestrator process.
    """

    def __init__(self, handler_registry: Any = None) -> None:
        """Args:
            handler_registry: Optional HandlerRegistry for dispatching child handlers.
                              If None, children are dispatched with mock outcomes
                              (for testing without the full graph/registry setup).
        """
        self._registry = handler_registry

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Fan-out to child nodes and join results.

        Args:
            request: HandlerRequest with node, context, run_dir.

        Returns:
            Outcome based on join policy and child results.
        """
        node = request.node
        join_policy = node.join_policy  # "wait_all" (default) or "first_success"

        # Identify child nodes via outgoing edges
        graph = request.context.get("$graph")
        child_node_ids: list[str] = []
        if graph is not None:
            edges = graph.edges_from(node.id)
            child_node_ids = [e.target for e in edges]

        if not child_node_ids:
            # No children — trivially SUCCESS
            return Outcome(
                status=OutcomeStatus.SUCCESS,
                context_updates={f"${node.id}.results": {}},
                metadata={"child_count": 0, "join_policy": join_policy},
            )

        # Fan out
        branch_outcomes: list[tuple[str, Outcome]]
        if join_policy == "first_success":
            branch_outcomes = await self._run_first_success(request, child_node_ids, graph)
        else:
            branch_outcomes = await self._run_wait_all(request, child_node_ids, graph)

        # Merge child context updates into main context (AMD-2 namespacing)
        merged = request.context.merge_fan_out_results(branch_outcomes)

        # Determine overall outcome
        all_statuses = [o.status for _, o in branch_outcomes]
        any_failure = any(s == OutcomeStatus.FAILURE for s in all_statuses)
        all_success = all(s == OutcomeStatus.SUCCESS for s in all_statuses)

        if join_policy == "wait_all":
            final_status = OutcomeStatus.SUCCESS if all_success else OutcomeStatus.FAILURE
        else:  # first_success — if we get here, at least one succeeded
            final_status = OutcomeStatus.SUCCESS

        results = {child_id: o.status.value for child_id, o in branch_outcomes}

        return Outcome(
            status=final_status,
            context_updates={
                f"${node.id}.results": results,
                **merged,
            },
            metadata={
                "child_count": len(child_node_ids),
                "join_policy": join_policy,
                "results": results,
            },
        )

    async def _run_wait_all(
        self,
        request: HandlerRequest,
        child_node_ids: list[str],
        graph: Any,
    ) -> list[tuple[str, Outcome]]:
        """Run all children concurrently; collect all results."""
        tasks_results: list[tuple[str, Outcome]] = []

        async with asyncio.TaskGroup() as tg:
            child_tasks: dict[str, asyncio.Task] = {}
            for child_id in child_node_ids:
                task = tg.create_task(
                    self._execute_child(request, child_id, graph),
                    name=f"child-{child_id}",
                )
                child_tasks[child_id] = task

        for child_id, task in child_tasks.items():
            tasks_results.append((child_id, task.result()))

        return tasks_results

    async def _run_first_success(
        self,
        request: HandlerRequest,
        child_node_ids: list[str],
        graph: Any,
    ) -> list[tuple[str, Outcome]]:
        """Return as soon as first child succeeds; cancel the rest."""
        done_results: list[tuple[str, Outcome]] = []

        # Create coroutines for all children
        coro_map = {
            child_id: self._execute_child(request, child_id, graph)
            for child_id in child_node_ids
        }

        pending_tasks = {
            asyncio.ensure_future(coro): child_id
            for child_id, coro in coro_map.items()
        }

        try:
            while pending_tasks:
                done, pending = await asyncio.wait(
                    pending_tasks.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    child_id = pending_tasks.pop(task)
                    outcome = task.result()
                    done_results.append((child_id, outcome))
                    if outcome.status == OutcomeStatus.SUCCESS:
                        # Cancel remaining
                        for remaining_task in list(pending_tasks.keys()):
                            remaining_task.cancel()
                        # Collect cancellation results (ignore CancelledError)
                        for remaining_task in list(pending_tasks.keys()):
                            remaining_id = pending_tasks.pop(remaining_task)
                            try:
                                await remaining_task
                            except (asyncio.CancelledError, Exception):
                                pass
                        return done_results
        except Exception:
            # Cancel all pending on error
            for task in pending_tasks:
                task.cancel()
            raise

        return done_results

    async def _execute_child(
        self,
        parent_request: HandlerRequest,
        child_id: str,
        graph: Any,
    ) -> Outcome:
        """Execute a child node with a snapshot copy of the parent context."""
        # Create isolated snapshot context for this branch
        snapshot_data = parent_request.context.snapshot()
        child_context = PipelineContext(initial=snapshot_data)

        if graph is None or child_id not in graph:
            # No graph or child missing — return mock SUCCESS for testing
            logger.warning("ParallelHandler: child node '%s' not in graph", child_id)
            return Outcome(status=OutcomeStatus.SUCCESS)

        child_node = graph.node(child_id)

        if self._registry is not None:
            child_handler = self._registry.dispatch(child_node)
        else:
            # No registry — return mock outcome
            return Outcome(status=OutcomeStatus.SUCCESS)

        child_request = HandlerRequest(
            node=child_node,
            context=child_context,
            emitter=parent_request.emitter,
            pipeline_id=parent_request.pipeline_id,
            visit_count=1,
            attempt_number=1,
            run_dir=parent_request.run_dir,
        )
        return await child_handler.execute(child_request)


assert isinstance(ParallelHandler(), Handler)
