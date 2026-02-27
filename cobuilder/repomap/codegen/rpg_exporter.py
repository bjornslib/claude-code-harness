"""RPG artifact export for the generated repository.

Exports the final RPG as a human-readable JSON file at docs/rpg.json,
including node statuses, generation metadata, and timestamps.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode


class _UUIDEncoder(json.JSONEncoder):
    """JSON encoder that handles UUID serialization."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def export_rpg_artifact(
    graph: RPGGraph,
    generation_metadata: dict[str, Any] | None = None,
) -> str:
    """Export the RPG as a human-readable JSON artifact.

    Produces an inspectable document at docs/rpg.json containing:
    - All nodes with their current status
    - All edges
    - Graph metadata
    - Generation metadata (timestamp, model, phase versions)

    Args:
        graph: The RPGGraph to export.
        generation_metadata: Optional additional metadata about the
            generation run (LLM model, phase versions, etc).

    Returns:
        A pretty-printed JSON string.
    """
    nodes_data: list[dict[str, Any]] = []
    for node in sorted(graph.nodes.values(), key=lambda n: n.name):
        node_dict = _serialize_node(node)
        nodes_data.append(node_dict)

    edges_data: list[dict[str, Any]] = []
    for edge in graph.edges.values():
        edge_dict = edge.model_dump(mode="json")
        edges_data.append(edge_dict)

    export: dict[str, Any] = {
        "rpg_version": "1.0",
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "node_count": len(nodes_data),
        "edge_count": len(edges_data),
        "nodes": nodes_data,
        "edges": edges_data,
        "metadata": {
            **graph.metadata,
            **(generation_metadata or {}),
        },
    }

    return json.dumps(export, indent=2, cls=_UUIDEncoder)


def _serialize_node(node: RPGNode) -> dict[str, Any]:
    """Serialize a single RPG node for export.

    Includes all relevant fields and the test status.

    Args:
        node: The RPGNode to serialize.

    Returns:
        A JSON-serializable dict.
    """
    data = node.model_dump(mode="json")
    # Ensure test_status is always a string
    if "test_status" in data and hasattr(data["test_status"], "value"):
        data["test_status"] = data["test_status"].value
    return data


def export_rpg_summary(graph: RPGGraph) -> dict[str, Any]:
    """Export a summary of the RPG for quick inspection.

    Lighter than full export - just node names, statuses, and edges.

    Args:
        graph: The RPGGraph to summarize.

    Returns:
        A summary dict.
    """
    node_summary: list[dict[str, str]] = []
    for node in sorted(graph.nodes.values(), key=lambda n: n.name):
        node_summary.append({
            "id": str(node.id),
            "name": node.name,
            "status": node.test_status.value,
            "file_path": node.file_path or "",
        })

    edge_summary: list[dict[str, str]] = []
    for edge in graph.edges.values():
        edge_summary.append({
            "source": str(edge.source_id),
            "target": str(edge.target_id),
            "type": edge.edge_type.value,
        })

    return {
        "total_nodes": len(node_summary),
        "total_edges": len(edge_summary),
        "nodes": node_summary,
        "edges": edge_summary,
    }
