"""Progress logging and ETA estimation for code generation.

Provides structured progress reporting during the topological
traversal of the RPG, including per-node timing and time-remaining
estimates.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ProgressLogger:
    """Log code-generation progress with ETA estimation.

    Tracks completed node counts and elapsed time to produce periodic
    progress summaries with estimated time remaining.

    Args:
        total_nodes: Total number of nodes to process.
    """

    def __init__(self, total_nodes: int) -> None:
        if total_nodes < 0:
            raise ValueError("total_nodes must be non-negative")
        self._total_nodes = total_nodes
        self._completed = 0
        self._elapsed: float = 0.0
        self._node_log: list[dict[str, object]] = []

    @property
    def eta_seconds(self) -> float:
        """Estimated seconds remaining based on current pace.

        Returns ``0.0`` when no nodes have been completed yet or when
        all nodes are finished.
        """
        if self._completed == 0 or self._completed >= self._total_nodes:
            return 0.0
        avg_time = self._elapsed / self._completed
        remaining = self._total_nodes - self._completed
        return avg_time * remaining

    def log_progress(self, completed: int, elapsed_seconds: float) -> None:
        """Log an overall progress update.

        A summary message is emitted every 10 nodes.

        Args:
            completed: Number of nodes completed so far.
            elapsed_seconds: Wall-clock seconds elapsed since start.
        """
        self._completed = completed
        self._elapsed = elapsed_seconds

        if self._total_nodes == 0:
            return

        pct = (completed / self._total_nodes) * 100
        eta = self.eta_seconds
        eta_min = eta / 60.0

        if completed % 10 == 0 or completed == self._total_nodes:
            logger.info(
                "Completed %d/%d nodes (%.0f%%), ETA: %.1f min",
                completed,
                self._total_nodes,
                pct,
                eta_min,
            )

    def log_node_result(
        self, node_id: str, status: str, duration: float
    ) -> None:
        """Log the result for a single node.

        Args:
            node_id: Identifier of the processed node.
            status: Outcome status (e.g. ``"passed"``, ``"failed"``).
            duration: Processing time in seconds.
        """
        entry = {
            "node_id": node_id,
            "status": status,
            "duration": duration,
        }
        self._node_log.append(entry)
        logger.debug(
            "Node %s: %s (%.2fs)", node_id, status, duration
        )
