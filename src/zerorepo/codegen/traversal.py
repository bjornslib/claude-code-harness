"""Topological order traversal engine for graph-guided code generation.

Wraps the existing graph_ops.topological_sort to provide a higher-level
traversal engine suitable for code generation workflows, including
failure propagation, leaf-node filtering, and deterministic ordering.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.graph_ops.topological import topological_sort
from zerorepo.graph_ops.traversal import get_descendants
from zerorepo.models.enums import EdgeType, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


@dataclass
class TraversalReport:
    """Summary report of a traversal engine run.

    Attributes:
        total: Total number of nodes processed.
        passed: Number of nodes that passed generation.
        failed: Number of nodes that failed generation.
        skipped: Number of nodes skipped (downstream of failures).
        pending: Number of nodes still pending.
        subgraph_reports: Per-subgraph breakdown keyed by root node UUID.
    """

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    pending: int = 0
    subgraph_reports: dict[str, dict[str, int]] = field(default_factory=dict)


class TraversalEngine:
    """Computes and manages topological traversal order for code generation.

    Uses the existing topological_sort from graph_ops to compute valid
    generation order, with deterministic tie-breaking, leaf-node filtering,
    and failure propagation.

    Args:
        graph: The RPGGraph to traverse.
        state: The GenerationState tracking per-node progress.
        max_retries: Maximum retries per node before marking failed.
            Defaults to 8.
    """

    def __init__(
        self,
        graph: RPGGraph,
        state: GenerationState | None = None,
        *,
        max_retries: int = 8,
    ) -> None:
        self._graph = graph
        self._state = state or GenerationState(max_retries=max_retries)
        self._state.max_retries = max_retries

    @property
    def graph(self) -> RPGGraph:
        """The RPGGraph being traversed."""
        return self._graph

    @property
    def state(self) -> GenerationState:
        """The generation state tracker."""
        return self._state

    def compute_order(self) -> list[RPGNode]:
        """Compute the full topological order of all nodes.

        Returns nodes in topological order with deterministic tie-breaking
        by UUID string (alphabetical). Parent nodes appear before their
        children within the hierarchy.

        Returns:
            A list of RPGNode instances in topological order.

        Raises:
            CycleDetectedError: If the graph contains cycles.
        """
        sorted_ids = topological_sort(self._graph)
        # topological_sort already handles HIERARCHY and DATA_FLOW edges
        # Apply deterministic tie-breaking: stable sort by UUID string
        # preserves topological order while breaking ties alphabetically
        sorted_ids = self._apply_deterministic_tiebreak(sorted_ids)
        return [self._graph.nodes[nid] for nid in sorted_ids]

    def compute_generation_order(self) -> list[RPGNode]:
        """Compute the generation order for leaf nodes only.

        Returns only FUNCTION_AUGMENTED nodes (leaf nodes for code
        generation) in topological order with deterministic tie-breaking.

        Returns:
            A list of FUNCTION_AUGMENTED RPGNode instances in topological order.

        Raises:
            CycleDetectedError: If the graph contains cycles.
        """
        all_ordered = self.compute_order()
        return [
            node
            for node in all_ordered
            if node.node_type == NodeType.FUNCTION_AUGMENTED
        ]

    def _apply_deterministic_tiebreak(self, sorted_ids: list[UUID]) -> list[UUID]:
        """Apply deterministic tie-breaking to a topologically sorted list.

        Nodes at the same topological level (same set of predecessors)
        are sorted by UUID string for deterministic ordering.

        The approach: group nodes by their topological position
        (computed from in-degree layers in Kahn's algorithm). Within
        each layer, sort by UUID string.

        Args:
            sorted_ids: A valid topological ordering.

        Returns:
            A topological ordering with deterministic tie-breaking.
        """
        if len(sorted_ids) <= 1:
            return sorted_ids

        relevant_types = {EdgeType.HIERARCHY, EdgeType.DATA_FLOW}

        # Build adjacency and reverse adjacency for layer computation
        predecessors: dict[UUID, set[UUID]] = defaultdict(set)
        for edge in self._graph.edges.values():
            if edge.edge_type in relevant_types:
                predecessors[edge.target_id].add(edge.source_id)

        # Compute the topological layer for each node
        # Layer 0 = nodes with no predecessors
        # Layer N = max(layer of predecessors) + 1
        layer: dict[UUID, int] = {}
        for nid in sorted_ids:
            pred_layers = [
                layer[p] for p in predecessors.get(nid, set()) if p in layer
            ]
            layer[nid] = (max(pred_layers) + 1) if pred_layers else 0

        # Group by layer, sort within each layer by UUID string
        layers: dict[int, list[UUID]] = defaultdict(list)
        for nid in sorted_ids:
            layers[layer[nid]].append(nid)

        result: list[UUID] = []
        for layer_idx in sorted(layers.keys()):
            layer_nodes = layers[layer_idx]
            layer_nodes.sort(key=lambda uid: str(uid))
            result.extend(layer_nodes)

        return result

    def mark_passed(self, node_id: UUID) -> None:
        """Mark a node as having passed generation.

        Args:
            node_id: The UUID of the node.
        """
        self._state.set_status(node_id, GenerationStatus.PASSED)

    def mark_failed(
        self, node_id: UUID, reason: str = "Generation failed"
    ) -> list[UUID]:
        """Mark a node as failed and propagate to downstream dependents.

        If the node's retry count has reached max_retries, marks it as
        FAILED and skips all downstream nodes (using get_descendants).

        Args:
            node_id: The UUID of the failed node.
            reason: The failure reason string.

        Returns:
            A list of downstream node UUIDs that were marked as SKIPPED.
        """
        retry_count = self._state.increment_retry(node_id)

        if retry_count < self._state.max_retries:
            # Still has retries left - mark as pending for retry
            self._state.set_status(
                node_id,
                GenerationStatus.PENDING,
                failure_reason=reason,
            )
            return []

        # Max retries exceeded - mark as permanently failed
        self._state.set_status(
            node_id,
            GenerationStatus.FAILED,
            failure_reason=reason,
        )

        # Propagate: skip all downstream nodes
        skipped: list[UUID] = []
        descendants = get_descendants(
            self._graph,
            node_id,
            [EdgeType.HIERARCHY, EdgeType.DATA_FLOW],
        )

        for desc_id in descendants:
            desc_state = self._state.get_node_state(desc_id)
            if desc_state.status not in {
                GenerationStatus.PASSED,
                GenerationStatus.FAILED,
            }:
                self._state.set_status(
                    desc_id,
                    GenerationStatus.SKIPPED,
                    failure_reason=f"Skipped: upstream node {node_id} failed",
                )
                skipped.append(desc_id)

        return sorted(skipped, key=lambda uid: str(uid))

    def should_process(self, node_id: UUID) -> bool:
        """Check if a node should be processed in the current run.

        A node should be processed if:
        - Its status is PENDING (fresh or retry)
        - Its status is IN_PROGRESS (interrupted previous run)

        A node should NOT be processed if:
        - Its status is PASSED (already done)
        - Its status is FAILED (max retries exceeded)
        - Its status is SKIPPED (upstream failure)

        Args:
            node_id: The UUID of the node to check.

        Returns:
            True if the node should be processed.
        """
        state = self._state.get_node_state(node_id)
        return state.status in {
            GenerationStatus.PENDING,
            GenerationStatus.IN_PROGRESS,
        }

    def generate_report(self) -> TraversalReport:
        """Generate a summary report of the current traversal state.

        Returns:
            A TraversalReport with per-status counts and per-subgraph breakdown.
        """
        summary = self._state.get_summary()
        report = TraversalReport(
            total=sum(summary.values()),
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            skipped=summary.get("skipped", 0),
            pending=summary.get("pending", 0) + summary.get("in_progress", 0),
        )

        # Generate per-root-node subgraph reports
        # Find root nodes (nodes with no incoming HIERARCHY edges)
        has_parent: set[UUID] = set()
        for edge in self._graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                has_parent.add(edge.target_id)

        root_nodes = [
            nid for nid in self._graph.nodes if nid not in has_parent
        ]

        for root_id in root_nodes:
            descendants = get_descendants(
                self._graph,
                root_id,
                [EdgeType.HIERARCHY],
            )
            subgraph_nodes = {root_id} | descendants
            sub_summary: dict[str, int] = {s.value: 0 for s in GenerationStatus}

            for nid in subgraph_nodes:
                node_state = self._state.get_node_state(nid)
                sub_summary[node_state.status.value] += 1

            report.subgraph_reports[str(root_id)] = sub_summary

        return report
