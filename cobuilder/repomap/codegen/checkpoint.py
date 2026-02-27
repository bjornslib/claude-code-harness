"""Checkpoint management for graph-guided code generation.

Provides save/load/resume functionality for generation checkpoints,
enabling reliable restart from the last known good state.
"""

from __future__ import annotations

from uuid import UUID

from cobuilder.repomap.codegen.state import GenerationState, GenerationStatus
from cobuilder.repomap.graph_ops.traversal import get_ancestors
from cobuilder.repomap.models.enums import EdgeType
from cobuilder.repomap.models.graph import RPGGraph


class CheckpointManager:
    """Manages checkpoint persistence and resume logic for code generation.

    Coordinates with GenerationState and RPGGraph to determine which nodes
    need (re)generation after a checkpoint resume.

    Args:
        state: The GenerationState to manage.
        graph: The RPGGraph providing dependency information.
    """

    def __init__(self, state: GenerationState, graph: RPGGraph) -> None:
        self._state = state
        self._graph = graph

    @property
    def state(self) -> GenerationState:
        """The managed generation state."""
        return self._state

    @property
    def graph(self) -> RPGGraph:
        """The associated RPGGraph."""
        return self._graph

    def save_checkpoint(self, path: str | None = None) -> str:
        """Save the current generation state to a checkpoint file.

        Args:
            path: Optional override path. Defaults to state's checkpoint_path.

        Returns:
            The path the checkpoint was saved to.
        """
        return self._state.save(path)

    @classmethod
    def load_checkpoint(cls, path: str, graph: RPGGraph) -> CheckpointManager:
        """Load a checkpoint and create a new CheckpointManager.

        Args:
            path: Path to the checkpoint JSON file.
            graph: The RPGGraph to associate with the loaded state.

        Returns:
            A new CheckpointManager instance with the loaded state.

        Raises:
            FileNotFoundError: If the checkpoint file doesn't exist.
            ValueError: If the checkpoint data is malformed.
        """
        state = GenerationState.load(path)
        return cls(state=state, graph=graph)

    def get_nodes_to_process(self) -> list[UUID]:
        """Determine which nodes need processing based on current state.

        Nodes are processed if they are:
        - PENDING: never started
        - FAILED: will be retried (if retry count < max_retries)
        - IN_PROGRESS: interrupted, treated as needing retry

        Nodes that are PASSED or SKIPPED are not reprocessed.

        Returns:
            A list of node UUIDs that need processing.
        """
        to_process: list[UUID] = []
        for node_id in self._graph.nodes:
            node_state = self._state.get_node_state(node_id)
            if node_state.status == GenerationStatus.PASSED:
                continue
            if node_state.status == GenerationStatus.SKIPPED:
                continue
            if (
                node_state.status == GenerationStatus.FAILED
                and node_state.retry_count >= self._state.max_retries
            ):
                continue
            to_process.append(node_id)
        return to_process

    def validate_start_from(self, node_id: UUID) -> list[UUID]:
        """Validate that all dependencies of a start-from node are passed.

        Checks that all ancestors (via HIERARCHY and DATA_FLOW edges)
        of the specified node have a PASSED status in the generation state.

        Args:
            node_id: The UUID of the node to start from.

        Returns:
            A list of ancestor UUIDs that are NOT passed (i.e., blockers).

        Raises:
            ValueError: If node_id is not in the graph.
        """
        if node_id not in self._graph.nodes:
            raise ValueError(f"Node '{node_id}' not found in graph")

        ancestors = get_ancestors(
            self._graph,
            node_id,
            [EdgeType.HIERARCHY, EdgeType.DATA_FLOW],
        )

        blockers: list[UUID] = []
        for ancestor_id in ancestors:
            ancestor_state = self._state.get_node_state(ancestor_id)
            if ancestor_state.status != GenerationStatus.PASSED:
                blockers.append(ancestor_id)

        return sorted(blockers, key=lambda uid: str(uid))

    def resume_from_node(self, node_id: UUID) -> list[UUID]:
        """Set up state to resume generation from a specific node.

        Validates all dependencies are passed, then resets the target
        node and all downstream nodes to PENDING so they can be
        reprocessed.

        Args:
            node_id: The UUID of the node to resume from.

        Returns:
            A list of node UUIDs that were reset to PENDING.

        Raises:
            ValueError: If node_id is not in the graph or if
                dependencies are not satisfied.
        """
        blockers = self.validate_start_from(node_id)
        if blockers:
            blocker_strs = ", ".join(str(b) for b in blockers)
            raise ValueError(
                f"Cannot resume from node '{node_id}': "
                f"dependencies not passed: {blocker_strs}"
            )

        # Reset the target node and all nodes that haven't been processed yet
        # but would come after this node in topological order
        reset_nodes: list[UUID] = [node_id]

        # Also reset any nodes that depend on this one
        from cobuilder.repomap.graph_ops.traversal import get_descendants

        descendants = get_descendants(
            self._graph,
            node_id,
            [EdgeType.HIERARCHY, EdgeType.DATA_FLOW],
        )
        reset_nodes.extend(sorted(descendants, key=lambda uid: str(uid)))

        for nid in reset_nodes:
            self._state.set_status(nid, GenerationStatus.PENDING)
            node_state = self._state.get_node_state(nid)
            node_state.retry_count = 0
            node_state.failure_reason = None

        return reset_nodes

    def is_idempotent_safe(self, node_id: UUID) -> bool:
        """Check if running generation for a node is idempotent-safe.

        A node is idempotent-safe if it's already PASSED (running again
        would produce the same result) or if it's PENDING (fresh start).

        Args:
            node_id: The UUID of the node to check.

        Returns:
            True if running generation on this node is safe.
        """
        state = self._state.get_node_state(node_id)
        return state.status in {
            GenerationStatus.PASSED,
            GenerationStatus.PENDING,
            GenerationStatus.SKIPPED,
        }
