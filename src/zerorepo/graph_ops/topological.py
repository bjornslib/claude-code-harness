"""Topological sort and cycle detection for RPGGraph."""

from __future__ import annotations

from collections import defaultdict, deque
from uuid import UUID

from zerorepo.models.enums import EdgeType
from zerorepo.models.graph import RPGGraph

from zerorepo.graph_ops.exceptions import CycleDetectedError


def topological_sort(graph: RPGGraph) -> list[UUID]:
    """Return nodes in topological order using Kahn's algorithm.

    Considers HIERARCHY and DATA_FLOW edges for ordering. A node appears
    before any node that depends on it (i.e., sources before targets).

    Args:
        graph: The RPGGraph to sort.

    Returns:
        A list of node UUIDs in topological order.

    Raises:
        CycleDetectedError: If the graph contains a cycle among the
            considered edge types.
    """
    relevant_types = {EdgeType.HIERARCHY, EdgeType.DATA_FLOW}

    # Build adjacency list and in-degree map
    in_degree: dict[UUID, int] = {nid: 0 for nid in graph.nodes}
    adjacency: dict[UUID, list[UUID]] = defaultdict(list)

    for edge in graph.edges.values():
        if edge.edge_type in relevant_types:
            adjacency[edge.source_id].append(edge.target_id)
            in_degree[edge.target_id] = in_degree.get(edge.target_id, 0) + 1

    # Start with nodes that have no incoming relevant edges
    queue: deque[UUID] = deque(
        nid for nid, deg in in_degree.items() if deg == 0
    )
    result: list[UUID] = []

    while queue:
        node_id = queue.popleft()
        result.append(node_id)
        for neighbor in adjacency.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(graph.nodes):
        # Cycle exists – find it for the error message
        cycles = detect_cycles(graph)
        cycle = cycles[0] if cycles else []
        raise CycleDetectedError(cycle)

    return result


def detect_cycles(graph: RPGGraph) -> list[list[UUID]]:
    """Detect all cycles in the graph considering HIERARCHY and DATA_FLOW edges.

    Uses DFS-based cycle detection. Returns all elementary cycles found.

    Args:
        graph: The RPGGraph to check.

    Returns:
        A list of cycles, where each cycle is a list of node UUIDs
        forming the cycle path. Empty list if the graph is acyclic.
    """
    relevant_types = {EdgeType.HIERARCHY, EdgeType.DATA_FLOW}

    adjacency: dict[UUID, list[UUID]] = defaultdict(list)
    for edge in graph.edges.values():
        if edge.edge_type in relevant_types:
            adjacency[edge.source_id].append(edge.target_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[UUID, int] = {nid: WHITE for nid in graph.nodes}
    parent: dict[UUID, UUID | None] = {}
    cycles: list[list[UUID]] = []

    def _dfs(node: UUID) -> None:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if color[neighbor] == GRAY:
                # Found a cycle – reconstruct it
                cycle: list[UUID] = [neighbor, node]
                current = node
                while current != neighbor:
                    current = parent.get(current)  # type: ignore[assignment]
                    if current is None or current == neighbor:
                        break
                    cycle.append(current)
                cycle.reverse()
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                parent[neighbor] = node
                _dfs(neighbor)
        color[node] = BLACK

    for node_id in graph.nodes:
        if color[node_id] == WHITE:
            parent[node_id] = None
            _dfs(node_id)

    return cycles
