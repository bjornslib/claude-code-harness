"""PipelineContext — thread-safe key-value accumulator for pipeline state.

All mutable pipeline state lives here; the parsed Graph and Outcome are
immutable.  PipelineContext is passed by reference to sequential handlers.
Fan-out handlers receive a ``snapshot()`` copy so that parallel branches
cannot corrupt each other's state.

Built-in keys maintained by the engine runner (all prefixed with ``$``):
    $last_status           OutcomeStatus value of the most recently completed node
    $retry_count           int, number of times the current node has been retried
    $pipeline_duration_s   float, seconds elapsed since pipeline start
    $node_visits.<node_id> int, number of times node_id has been visited

Custom keys set by handler context_updates must not start with ``$``.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cobuilder.engine.outcome import Outcome


class PipelineContext:
    """Thread-safe key-value store for accumulated pipeline state.

    Fan-out handlers (ParallelHandler) receive a snapshot (shallow copy) of
    the context at fan-out time.  Their context_updates are namespaced by
    branch node ID via ``merge_fan_out_results()`` to prevent silent
    data corruption when two branches write the same key (AMD-2).

    Thread safety: all public methods acquire a reentrant lock before
    accessing ``_data``.  This is sufficient for the fan-out scenario where
    branches hold *copies*, not shared references.
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial or {})
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core accessors
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if not present."""
        with self._lock:
            return self._data.get(key, default)

    def update(self, updates: dict[str, Any]) -> None:
        """Merge *updates* into the context, overwriting existing keys."""
        with self._lock:
            self._data.update(updates)

    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of the current context state.

        Used by fan-out handlers and EdgeSelector to prevent mutations from
        affecting routing decisions or parallel branches.
        """
        with self._lock:
            return dict(self._data)

    # ------------------------------------------------------------------
    # Fan-out merge (AMD-2)
    # ------------------------------------------------------------------

    def merge_fan_out_results(
        self,
        branch_outcomes: list[tuple[str, "Outcome"]],
    ) -> dict[str, Any]:
        """Merge results from parallel fan-out branches into the main context.

        **AMD-2 Fan-Out Context Merge Policy**:

        - Parallel branches receive a READ-ONLY snapshot of the context.
        - Each branch's ``context_updates`` are namespaced by branch node ID:
          the key ``'<branch_node_id>.<original_key>'`` is stored in the
          main context.
        - This prevents silent data corruption when branches write the same key.
        - ``FanInHandler`` receives the list of ``(branch_id, Outcome)``
          tuples and can inspect individual branch results.

        Args:
            branch_outcomes: List of (branch_node_id, outcome) tuples from
                             all completed parallel branches.

        Returns:
            Dict of all namespaced keys that were merged into the main context.
        """
        merged_keys: dict[str, Any] = {}
        with self._lock:
            for branch_id, outcome in branch_outcomes:
                for key, value in outcome.context_updates.items():
                    namespaced_key = f"{branch_id}.{key}"
                    self._data[namespaced_key] = value
                    merged_keys[namespaced_key] = value
        return merged_keys

    # ------------------------------------------------------------------
    # Visit counter helpers
    # ------------------------------------------------------------------

    def increment_visit(self, node_id: str) -> int:
        """Increment and return the visit count for *node_id*.

        The count is stored as ``$node_visits.<node_id>`` so that it is
        visible to condition evaluators via the context snapshot.
        """
        key = f"$node_visits.{node_id}"
        with self._lock:
            count = self._data.get(key, 0) + 1
            self._data[key] = count
            return count

    def get_visit_count(self, node_id: str) -> int:
        """Return the current visit count for *node_id* (0 if never visited)."""
        key = f"$node_visits.{node_id}"
        with self._lock:
            return self._data.get(key, 0)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        with self._lock:
            return f"PipelineContext({self._data!r})"

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
