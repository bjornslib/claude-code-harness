"""Subgraph extraction operations for RPGGraph."""

from __future__ import annotations

from collections import deque
from uuid import UUID

from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph


def extract_subgraph_by_module(graph: RPGGraph, module_id: UUID) -> RPGGraph:
    """Extract a subgraph containing a module and all its HIERARCHY descendants.

    Performs a BFS from the given module node following outgoing HIERARCHY
    edges to collect all descendant nodes. Preserves all edges (of any type)
    between the extracted nodes.

    Args:
        graph: The source RPGGraph.
        module_id: The UUID of the module node to extract.

    Returns:
        A new RPGGraph with the module, its descendants, and edges between them.

    Raises:
        ValueError: If module_id is not found in the graph.
    """
    if module_id not in graph.nodes:
        raise ValueError(f"Node '{module_id}' not found in graph")

    # BFS to find all HIERARCHY descendants
    node_ids: set[UUID] = {module_id}
    queue: deque[UUID] = deque([module_id])

    while queue:
        current = queue.popleft()
        for edge in graph.edges.values():
            if (
                edge.edge_type == EdgeType.HIERARCHY
                and edge.source_id == current
                and edge.target_id not in node_ids
            ):
                node_ids.add(edge.target_id)
                queue.append(edge.target_id)

    return _build_subgraph(graph, node_ids)


def extract_subgraph_by_level(graph: RPGGraph, level: NodeLevel) -> RPGGraph:
    """Extract a subgraph containing all nodes of a specified level.

    Preserves all edges between the extracted nodes.

    Args:
        graph: The source RPGGraph.
        level: The NodeLevel to filter by.

    Returns:
        A new RPGGraph with matching nodes and edges between them.
    """
    node_ids = {
        nid for nid, node in graph.nodes.items() if node.level == level
    }
    return _build_subgraph(graph, node_ids)


def extract_subgraph_by_type(graph: RPGGraph, node_type: NodeType) -> RPGGraph:
    """Extract a subgraph containing all nodes of a specified type.

    Preserves all edges between the extracted nodes.

    Args:
        graph: The source RPGGraph.
        node_type: The NodeType to filter by.

    Returns:
        A new RPGGraph with matching nodes and edges between them.
    """
    node_ids = {
        nid for nid, node in graph.nodes.items() if node.node_type == node_type
    }
    return _build_subgraph(graph, node_ids)


def _build_subgraph(graph: RPGGraph, node_ids: set[UUID]) -> RPGGraph:
    """Build a new RPGGraph from a subset of nodes and their connecting edges.

    Args:
        graph: The source RPGGraph.
        node_ids: The set of node UUIDs to include.

    Returns:
        A new RPGGraph with the specified nodes and edges between them.
    """
    nodes = {nid: graph.nodes[nid] for nid in node_ids if nid in graph.nodes}
    edges = {
        eid: edge
        for eid, edge in graph.edges.items()
        if edge.source_id in node_ids and edge.target_id in node_ids
    }
    return RPGGraph(nodes=nodes, edges=edges, metadata=graph.metadata.copy())
