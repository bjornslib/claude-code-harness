"""ExitHandler — handles Msquare (pipeline exit) nodes.

The exit handler checks whether all goal-gate nodes have completed
successfully.  If all goal gates are met, it writes a ``pipeline_complete``
signal file and returns SUCCESS.  If any goal gate is missing from
``completed_nodes``, it returns FAILURE.

AC-F5:
- Returns ``Outcome(status=SUCCESS)`` when all ``goal_gate=true`` nodes are
  in ``completed_nodes``.
- Returns ``Outcome(status=FAILURE)`` when any ``goal_gate=true`` node is
  missing from ``completed_nodes``.
- Updates ``context["$pipeline_outcome"]`` to ``"success"`` or ``"failure"``.
- On SUCCESS: writes ``pipeline_complete.signal`` to run_dir signals directory.
"""
from __future__ import annotations

import os
from pathlib import Path

from cobuilder.engine.graph import GOAL_GATE_SHAPES
from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus


class ExitHandler:
    """Handler for pipeline exit nodes (``Msquare`` shape).

    Checks that all ``goal_gate=true`` nodes have completed, then signals
    pipeline completion.

    The ``completed_nodes`` list is read from the pipeline context via
    the built-in key ``$completed_nodes``.  The engine runner populates
    this key before calling any handler.
    """

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Evaluate goal gates and return the pipeline outcome.

        Args:
            request: HandlerRequest.  ``request.context`` must contain
                     ``$completed_nodes`` (list[str]) populated by the runner.
                     ``request.run_dir`` is used for signal file output.

        Returns:
            ``Outcome`` with status ``SUCCESS`` or ``FAILURE`` and
            ``context_updates["$pipeline_outcome"]`` set accordingly.
        """
        graph = request.context.get("$graph")
        completed_nodes: list[str] = request.context.get("$completed_nodes", [])

        # Identify all goal gate nodes in the graph
        if graph is not None:
            goal_gate_nodes = [
                node for node in graph.nodes.values()
                if node.goal_gate and node.shape in GOAL_GATE_SHAPES
            ]
            goal_gate_ids = {n.id for n in goal_gate_nodes}
        else:
            goal_gate_ids = set()

        completed_set = set(completed_nodes)
        missing_gates = goal_gate_ids - completed_set

        if missing_gates:
            # Not all goal gates met — pipeline failure
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={
                    "$pipeline_outcome": "failure",
                    "$missing_goal_gates": sorted(missing_gates),
                },
                metadata={
                    "goal_gate_ids": sorted(goal_gate_ids),
                    "missing_gates": sorted(missing_gates),
                    "completed_nodes": completed_nodes,
                },
            )

        # All goal gates met — write completion signal
        self._write_completion_signal(request.run_dir, request.node.id)

        return Outcome(
            status=OutcomeStatus.SUCCESS,
            context_updates={"$pipeline_outcome": "success"},
            metadata={
                "goal_gate_ids": sorted(goal_gate_ids),
                "completed_nodes": completed_nodes,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write_completion_signal(self, run_dir: str, node_id: str) -> None:
        """Write ``pipeline_complete.signal`` to ``{run_dir}/signals/``.

        Creates the signals directory if it does not exist.  Silently ignores
        write errors (signal files are best-effort; the pipeline outcome is
        already recorded in the checkpoint).
        """
        if not run_dir:
            return
        try:
            signals_dir = Path(run_dir) / "signals"
            signals_dir.mkdir(parents=True, exist_ok=True)
            signal_path = signals_dir / "pipeline_complete.signal"
            signal_path.write_text(
                f'{{"node_id": "{node_id}", "status": "success"}}\n'
            )
        except OSError:
            pass  # Non-fatal — checkpoint already records the outcome


assert isinstance(ExitHandler(), Handler)
