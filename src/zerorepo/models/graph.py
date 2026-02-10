"""RPGGraph container for the Repository Planning Graph."""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from zerorepo.models.edge import RPGEdge
from zerorepo.models.node import RPGNode


class RPGGraph(BaseModel):
    """Container managing nodes and edges in the Repository Planning Graph.

    Provides methods for adding, removing, querying, and serializing
    graph elements. Maintains referential integrity by validating that
    edge endpoints reference existing nodes, and cascading node removal
    to connected edges.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    nodes: dict[UUID, RPGNode] = Field(
        default_factory=dict,
        description="Nodes indexed by their UUID",
    )
    edges: dict[UUID, RPGEdge] = Field(
        default_factory=dict,
        description="Edges indexed by their UUID",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Graph-level metadata (project name, version, timestamp, etc.)",
    )

    def add_node(self, node: RPGNode) -> UUID:
        """Add a node to the graph.

        Args:
            node: The RPGNode to add.

        Returns:
            The UUID of the added node.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.id in self.nodes:
            raise ValueError(f"Node with id '{node.id}' already exists in the graph")
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, edge: RPGEdge) -> UUID:
        """Add an edge to the graph.

        Validates that both source and target nodes exist in the graph
        before adding the edge.

        Args:
            edge: The RPGEdge to add.

        Returns:
            The UUID of the added edge.

        Raises:
            ValueError: If source_id or target_id not in nodes, or if
                an edge with the same ID already exists.
        """
        if edge.source_id not in self.nodes:
            raise ValueError(
                f"Source node '{edge.source_id}' not found in graph. "
                f"Add the source node before adding this edge."
            )
        if edge.target_id not in self.nodes:
            raise ValueError(
                f"Target node '{edge.target_id}' not found in graph. "
                f"Add the target node before adding this edge."
            )
        if edge.id in self.edges:
            raise ValueError(f"Edge with id '{edge.id}' already exists in the graph")
        self.edges[edge.id] = edge
        return edge.id

    def get_node(self, node_id: UUID) -> Optional[RPGNode]:
        """Get a node by its UUID.

        Args:
            node_id: The UUID of the node to retrieve.

        Returns:
            The RPGNode if found, None otherwise.
        """
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: UUID) -> Optional[RPGEdge]:
        """Get an edge by its UUID.

        Args:
            edge_id: The UUID of the edge to retrieve.

        Returns:
            The RPGEdge if found, None otherwise.
        """
        return self.edges.get(edge_id)

    def remove_node(self, node_id: UUID) -> bool:
        """Remove a node and all connected edges from the graph.

        Any edge where this node is either the source or target will
        also be removed to maintain referential integrity.

        Args:
            node_id: The UUID of the node to remove.

        Returns:
            True if the node was found and removed, False otherwise.
        """
        if node_id not in self.nodes:
            return False

        # Find and remove all edges connected to this node
        edges_to_remove = [
            edge_id
            for edge_id, edge in self.edges.items()
            if edge.source_id == node_id or edge.target_id == node_id
        ]
        for edge_id in edges_to_remove:
            del self.edges[edge_id]

        del self.nodes[node_id]
        return True

    def remove_edge(self, edge_id: UUID) -> bool:
        """Remove an edge from the graph.

        Args:
            edge_id: The UUID of the edge to remove.

        Returns:
            True if the edge was found and removed, False otherwise.
        """
        if edge_id not in self.edges:
            return False
        del self.edges[edge_id]
        return True

    def to_json(self, indent: int = 2) -> str:
        """Serialize the graph to a JSON string.

        Args:
            indent: JSON indentation level for pretty formatting.

        Returns:
            A JSON string representation of the graph.
        """
        data = {
            "nodes": {
                str(node_id): node.model_dump(mode="json")
                for node_id, node in self.nodes.items()
            },
            "edges": {
                str(edge_id): edge.model_dump(mode="json")
                for edge_id, edge in self.edges.items()
            },
            "metadata": self.metadata,
        }
        return json.dumps(data, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> RPGGraph:
        """Deserialize a graph from a JSON string.

        Args:
            json_str: A JSON string previously produced by to_json().

        Returns:
            A new RPGGraph instance populated from the JSON data.

        Raises:
            ValueError: If the JSON is invalid or contains invalid data.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        nodes: dict[UUID, RPGNode] = {}
        for node_id_str, node_data in data.get("nodes", {}).items():
            node = RPGNode.model_validate(node_data)
            nodes[node.id] = node

        edges: dict[UUID, RPGEdge] = {}
        for edge_id_str, edge_data in data.get("edges", {}).items():
            edge = RPGEdge.model_validate(edge_data)
            edges[edge.id] = edge

        metadata = data.get("metadata", {})

        return cls(nodes=nodes, edges=edges, metadata=metadata)

    @property
    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self.edges)

    def __eq__(self, other: object) -> bool:
        """Check equality based on nodes, edges, and metadata."""
        if not isinstance(other, RPGGraph):
            return NotImplemented
        return (
            self.nodes == other.nodes
            and self.edges == other.edges
            and self.metadata == other.metadata
        )

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"RPGGraph(nodes={self.node_count}, edges={self.edge_count}, "
            f"metadata_keys={list(self.metadata.keys())})"
        )
