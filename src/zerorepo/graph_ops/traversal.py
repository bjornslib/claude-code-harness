"""Dependency traversal operations for RPGGraph."""

from __future__ import annotations

from collections import deque
from uuid import UUID

from zerorepo.models.enums import EdgeType
from zerorepo.models.graph import RPGGraph


def get_ancestors(
    graph: RPGGraph, node_id: UUID, edge_types: list[EdgeType]
) -> set[UUID]:
    """Return all ancestors reachable via specified edge types (transitive closure).

    Traverses edges in reverse: follows edges where node is a target back to
    their sources, recursively.

    Args:
        graph: The RPGGraph to traverse.
        node_id: The starting node UUID.
        edge_types: The edge types to follow.

    Returns:
        A set of all ancestor node UUIDs (not including node_id itself).

    Raises:
        ValueError: If node_id is not found in the graph.
    """
    if node_id not in graph.nodes:
        raise ValueError(f"Node '{node_id}' not found in graph")

    edge_type_set = set(edge_types)
    ancestors: set[UUID] = set()
    queue: deque[UUID] = deque([node_id])

    while queue:
        current = queue.popleft()
        for edge in graph.edges.values():
            if (
                edge.edge_type in edge_type_set
                and edge.target_id == current
                and edge.source_id not in ancestors
                and edge.source_id != node_id
            ):
                ancestors.add(edge.source_id)
                queue.append(edge.source_id)

    return ancestors


def get_descendants(
    graph: RPGGraph, node_id: UUID, edge_types: list[EdgeType]
) -> set[UUID]:
    """Return all descendants reachable via specified edge types (transitive closure).

    Traverses edges forward: follows edges where node is a source to their
    targets, recursively.

    Args:
        graph: The RPGGraph to traverse.
        node_id: The starting node UUID.
        edge_types: The edge types to follow.

    Returns:
        A set of all descendant node UUIDs (not including node_id itself).

    Raises:
        ValueError: If node_id is not found in the graph.
    """
    if node_id not in graph.nodes:
        raise ValueError(f"Node '{node_id}' not found in graph")

    edge_type_set = set(edge_types)
    descendants: set[UUID] = set()
    queue: deque[UUID] = deque([node_id])

    while queue:
        current = queue.popleft()
        for edge in graph.edges.values():
            if (
                edge.edge_type in edge_type_set
                and edge.source_id == current
                and edge.target_id not in descendants
                and edge.target_id != node_id
            ):
                descendants.add(edge.target_id)
                queue.append(edge.target_id)

    return descendants


def get_direct_dependencies(graph: RPGGraph, node_id: UUID) -> list[UUID]:
    """Return immediate dependencies of a node.

    Dependencies are nodes targeted by outgoing DATA_FLOW or INVOCATION edges.

    Args:
        graph: The RPGGraph to query.
        node_id: The node UUID to get dependencies for.

    Returns:
        A list of node UUIDs that this node directly depends on.

    Raises:
        ValueError: If node_id is not found in the graph.
    """
    if node_id not in graph.nodes:
        raise ValueError(f"Node '{node_id}' not found in graph")

    dep_types = {EdgeType.DATA_FLOW, EdgeType.INVOCATION}
    return [
        edge.target_id
        for edge in graph.edges.values()
        if edge.source_id == node_id and edge.edge_type in dep_types
    ]
