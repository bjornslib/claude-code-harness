"""Dependency diff operations for RPGGraph."""

from __future__ import annotations

from uuid import UUID

from zerorepo.models.enums import EdgeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


def diff_dependencies(node: RPGNode, graph: RPGGraph) -> dict[str, list[UUID]]:
    """Compare planned vs actual dependencies for a node.

    Planned dependencies are determined by outgoing DATA_FLOW and INVOCATION
    edges from this node. Actual dependencies come from node.actual_dependencies.

    Args:
        node: The RPGNode to analyze.
        graph: The RPGGraph containing edges for the node.

    Returns:
        A dict with keys:
            - "planned": All targets from DATA_FLOW/INVOCATION edges
            - "actual": node.actual_dependencies
            - "missing": planned but not actual (planned - actual)
            - "extra": actual but not planned (actual - planned)
    """
    dep_types = {EdgeType.DATA_FLOW, EdgeType.INVOCATION}

    planned_list = [
        edge.target_id
        for edge in graph.edges.values()
        if edge.source_id == node.id and edge.edge_type in dep_types
    ]

    planned_set = set(planned_list)
    actual_set = set(node.actual_dependencies)

    missing = sorted(planned_set - actual_set, key=str)
    extra = sorted(actual_set - planned_set, key=str)

    return {
        "planned": planned_list,
        "actual": list(node.actual_dependencies),
        "missing": missing,
        "extra": extra,
    }
