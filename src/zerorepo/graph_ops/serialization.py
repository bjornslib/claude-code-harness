"""File-based JSON serialization for RPGGraph."""

from __future__ import annotations

from pathlib import Path

from zerorepo.models.graph import RPGGraph


def serialize_graph(graph: RPGGraph, filepath: Path) -> None:
    """Write graph to a JSON file with pretty formatting.

    Creates parent directories if they don't exist.

    Args:
        graph: The RPGGraph to serialize.
        filepath: The file path to write to.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    json_str = graph.to_json(indent=2)
    filepath.write_text(json_str, encoding="utf-8")


def deserialize_graph(filepath: Path) -> RPGGraph:
    """Load a graph from a JSON file.

    Round-trip equality must hold: deserialize(serialize(graph)) == graph.

    Args:
        filepath: The file path to read from.

    Returns:
        A new RPGGraph instance populated from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file contains invalid JSON or graph data.
    """
    json_str = filepath.read_text(encoding="utf-8")
    return RPGGraph.from_json(json_str)
