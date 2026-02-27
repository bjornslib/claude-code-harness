"""Node filtering operations for RPGGraph."""

from __future__ import annotations

from typing import Callable

from cobuilder.repomap.models.enums import NodeLevel, TestStatus
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode


def filter_nodes(
    graph: RPGGraph, predicate: Callable[[RPGNode], bool]
) -> list[RPGNode]:
    """Return all nodes matching the given predicate.

    Args:
        graph: The RPGGraph to filter.
        predicate: A callable that takes an RPGNode and returns True
            if the node should be included.

    Returns:
        A list of RPGNode instances matching the predicate.
    """
    return [node for node in graph.nodes.values() if predicate(node)]


def filter_by_status(graph: RPGGraph, status: TestStatus) -> list[RPGNode]:
    """Return all nodes with the specified test status.

    Args:
        graph: The RPGGraph to filter.
        status: The TestStatus to filter by.

    Returns:
        A list of RPGNode instances with the matching test status.
    """
    return filter_nodes(graph, lambda node: node.test_status == status)


def filter_by_validation(graph: RPGGraph, validated: bool) -> list[RPGNode]:
    """Return all nodes matching the specified validation state.

    Args:
        graph: The RPGGraph to filter.
        validated: True to get validated nodes, False for unvalidated.

    Returns:
        A list of RPGNode instances matching the validation state.
    """
    return filter_nodes(graph, lambda node: node.serena_validated == validated)


def filter_by_level(graph: RPGGraph, level: NodeLevel) -> list[RPGNode]:
    """Return all nodes at the specified hierarchical level.

    Args:
        graph: The RPGGraph to filter.
        level: The NodeLevel to filter by.

    Returns:
        A list of RPGNode instances at the specified level.
    """
    return filter_nodes(graph, lambda node: node.level == level)
