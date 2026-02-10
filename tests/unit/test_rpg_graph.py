"""Unit tests for RPGGraph container."""

import json
from uuid import UUID, uuid4

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


# --- Helpers ---

def make_node(
    name: str = "test_node",
    level: NodeLevel = NodeLevel.MODULE,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    **kwargs,
) -> RPGNode:
    """Create a node with sensible defaults."""
    return RPGNode(name=name, level=level, node_type=node_type, **kwargs)


def make_edge(
    source_id: UUID,
    target_id: UUID,
    edge_type: EdgeType = EdgeType.HIERARCHY,
    **kwargs,
) -> RPGEdge:
    """Create an edge with sensible defaults."""
    return RPGEdge(source_id=source_id, target_id=target_id, edge_type=edge_type, **kwargs)


class TestRPGGraphCreation:
    """Test RPGGraph creation and initialization."""

    def test_create_empty_graph(self) -> None:
        """Empty graph has no nodes or edges."""
        graph = RPGGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0
        assert graph.metadata == {}

    def test_create_graph_with_metadata(self) -> None:
        """Graph can be created with metadata."""
        graph = RPGGraph(metadata={"project": "zerorepo", "version": "1.0"})
        assert graph.metadata["project"] == "zerorepo"
        assert graph.metadata["version"] == "1.0"

    def test_repr(self) -> None:
        """String representation is informative."""
        graph = RPGGraph(metadata={"project": "test"})
        repr_str = repr(graph)
        assert "RPGGraph" in repr_str
        assert "nodes=0" in repr_str
        assert "edges=0" in repr_str


class TestAddNode:
    """Test RPGGraph.add_node()."""

    def test_add_node_returns_uuid(self) -> None:
        """add_node returns the node's UUID."""
        graph = RPGGraph()
        node = make_node()
        result = graph.add_node(node)
        assert result == node.id
        assert isinstance(result, UUID)

    def test_add_node_in_graph(self) -> None:
        """Added node is in the nodes dict."""
        graph = RPGGraph()
        node = make_node()
        graph.add_node(node)
        assert node.id in graph.nodes
        assert graph.nodes[node.id] == node
        assert graph.node_count == 1

    def test_add_multiple_nodes(self) -> None:
        """Multiple nodes can be added."""
        graph = RPGGraph()
        nodes = [make_node(name=f"node_{i}") for i in range(5)]
        for node in nodes:
            graph.add_node(node)
        assert graph.node_count == 5

    def test_add_duplicate_node_raises(self) -> None:
        """Adding a node with the same ID raises ValueError."""
        graph = RPGGraph()
        node = make_node()
        graph.add_node(node)
        with pytest.raises(ValueError, match="already exists"):
            graph.add_node(node)


class TestAddEdge:
    """Test RPGGraph.add_edge()."""

    def test_add_edge_valid_nodes(self) -> None:
        """Add edge with valid source/target nodes succeeds."""
        graph = RPGGraph()
        n1 = make_node(name="source")
        n2 = make_node(name="target")
        graph.add_node(n1)
        graph.add_node(n2)

        edge = make_edge(n1.id, n2.id)
        result = graph.add_edge(edge)

        assert result == edge.id
        assert edge.id in graph.edges
        assert graph.edge_count == 1

    def test_add_edge_missing_source_raises(self) -> None:
        """Add edge with missing source node raises ValueError."""
        graph = RPGGraph()
        n2 = make_node(name="target")
        graph.add_node(n2)

        edge = make_edge(uuid4(), n2.id)
        with pytest.raises(ValueError, match="Source node.*not found"):
            graph.add_edge(edge)

    def test_add_edge_missing_target_raises(self) -> None:
        """Add edge with missing target node raises ValueError."""
        graph = RPGGraph()
        n1 = make_node(name="source")
        graph.add_node(n1)

        edge = make_edge(n1.id, uuid4())
        with pytest.raises(ValueError, match="Target node.*not found"):
            graph.add_edge(edge)

    def test_add_edge_both_missing_raises(self) -> None:
        """Add edge with both source and target missing raises ValueError."""
        graph = RPGGraph()
        edge = make_edge(uuid4(), uuid4())
        with pytest.raises(ValueError, match="Source node.*not found"):
            graph.add_edge(edge)

    def test_add_duplicate_edge_raises(self) -> None:
        """Adding an edge with the same ID raises ValueError."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = make_edge(n1.id, n2.id)
        graph.add_edge(edge)
        with pytest.raises(ValueError, match="already exists"):
            graph.add_edge(edge)

    def test_add_multiple_edges(self) -> None:
        """Multiple edges between different nodes can be added."""
        graph = RPGGraph()
        nodes = [make_node(name=f"n{i}") for i in range(4)]
        for n in nodes:
            graph.add_node(n)

        edges = [
            make_edge(nodes[0].id, nodes[1].id, EdgeType.HIERARCHY),
            make_edge(nodes[1].id, nodes[2].id, EdgeType.DATA_FLOW, data_id="x"),
            make_edge(nodes[2].id, nodes[3].id, EdgeType.INVOCATION),
        ]
        for e in edges:
            graph.add_edge(e)

        assert graph.edge_count == 3


class TestGetNode:
    """Test RPGGraph.get_node()."""

    def test_get_existing_node(self) -> None:
        """Get an existing node returns the node."""
        graph = RPGGraph()
        node = make_node()
        graph.add_node(node)
        result = graph.get_node(node.id)
        assert result == node

    def test_get_nonexistent_node_returns_none(self) -> None:
        """Get a nonexistent node returns None."""
        graph = RPGGraph()
        result = graph.get_node(uuid4())
        assert result is None


class TestGetEdge:
    """Test RPGGraph.get_edge()."""

    def test_get_existing_edge(self) -> None:
        """Get an existing edge returns the edge."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = make_edge(n1.id, n2.id)
        graph.add_edge(edge)

        result = graph.get_edge(edge.id)
        assert result == edge

    def test_get_nonexistent_edge_returns_none(self) -> None:
        """Get a nonexistent edge returns None."""
        graph = RPGGraph()
        result = graph.get_edge(uuid4())
        assert result is None


class TestRemoveNode:
    """Test RPGGraph.remove_node()."""

    def test_remove_existing_node(self) -> None:
        """Remove an existing node returns True."""
        graph = RPGGraph()
        node = make_node()
        graph.add_node(node)

        result = graph.remove_node(node.id)
        assert result is True
        assert graph.node_count == 0
        assert graph.get_node(node.id) is None

    def test_remove_nonexistent_node_returns_false(self) -> None:
        """Remove a nonexistent node returns False."""
        graph = RPGGraph()
        result = graph.remove_node(uuid4())
        assert result is False

    def test_remove_node_cascades_to_connected_edges(self) -> None:
        """Removing a node also removes all connected edges."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        n3 = make_node(name="c")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        # n1 -> n2, n2 -> n3
        e1 = make_edge(n1.id, n2.id)
        e2 = make_edge(n2.id, n3.id)
        graph.add_edge(e1)
        graph.add_edge(e2)

        assert graph.edge_count == 2

        # Remove n2 - both edges should be removed
        graph.remove_node(n2.id)
        assert graph.node_count == 2
        assert graph.edge_count == 0
        assert graph.get_edge(e1.id) is None
        assert graph.get_edge(e2.id) is None

    def test_remove_node_only_removes_connected_edges(self) -> None:
        """Removing a node leaves unconnected edges intact."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        n3 = make_node(name="c")
        n4 = make_node(name="d")
        for n in [n1, n2, n3, n4]:
            graph.add_node(n)

        # n1 -> n2 (will be removed), n3 -> n4 (should remain)
        e1 = make_edge(n1.id, n2.id)
        e2 = make_edge(n3.id, n4.id)
        graph.add_edge(e1)
        graph.add_edge(e2)

        graph.remove_node(n1.id)
        assert graph.edge_count == 1
        assert graph.get_edge(e2.id) is not None

    def test_remove_node_source_edges(self) -> None:
        """Removing a source node removes outgoing edges."""
        graph = RPGGraph()
        n1 = make_node(name="source")
        n2 = make_node(name="target")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = make_edge(n1.id, n2.id)
        graph.add_edge(edge)

        graph.remove_node(n1.id)
        assert graph.edge_count == 0

    def test_remove_node_target_edges(self) -> None:
        """Removing a target node removes incoming edges."""
        graph = RPGGraph()
        n1 = make_node(name="source")
        n2 = make_node(name="target")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = make_edge(n1.id, n2.id)
        graph.add_edge(edge)

        graph.remove_node(n2.id)
        assert graph.edge_count == 0


class TestRemoveEdge:
    """Test RPGGraph.remove_edge()."""

    def test_remove_existing_edge(self) -> None:
        """Remove an existing edge returns True."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = make_edge(n1.id, n2.id)
        graph.add_edge(edge)

        result = graph.remove_edge(edge.id)
        assert result is True
        assert graph.edge_count == 0

    def test_remove_nonexistent_edge_returns_false(self) -> None:
        """Remove a nonexistent edge returns False."""
        graph = RPGGraph()
        result = graph.remove_edge(uuid4())
        assert result is False

    def test_remove_edge_preserves_nodes(self) -> None:
        """Removing an edge does not remove its endpoint nodes."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        graph.add_node(n1)
        graph.add_node(n2)
        edge = make_edge(n1.id, n2.id)
        graph.add_edge(edge)

        graph.remove_edge(edge.id)
        assert graph.node_count == 2
        assert graph.get_node(n1.id) is not None
        assert graph.get_node(n2.id) is not None


class TestJsonSerialization:
    """Test RPGGraph JSON serialization round-trip."""

    def test_empty_graph_round_trip(self) -> None:
        """Empty graph survives JSON round-trip."""
        graph = RPGGraph()
        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)
        assert restored.node_count == 0
        assert restored.edge_count == 0

    def test_empty_graph_valid_json(self) -> None:
        """Empty graph serializes to valid JSON."""
        graph = RPGGraph()
        json_str = graph.to_json()
        parsed = json.loads(json_str)
        assert "nodes" in parsed
        assert "edges" in parsed
        assert "metadata" in parsed

    def test_graph_with_10_nodes_round_trip(self) -> None:
        """Graph with 10 nodes survives JSON round-trip."""
        graph = RPGGraph(metadata={"project": "test"})
        nodes = [make_node(name=f"node_{i}") for i in range(10)]
        for n in nodes:
            graph.add_node(n)

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)

        assert restored.node_count == 10
        for n in nodes:
            restored_node = restored.get_node(n.id)
            assert restored_node is not None
            assert restored_node.name == n.name

    def test_graph_with_nodes_and_edges_round_trip(self) -> None:
        """Graph with nodes and edges survives JSON round-trip."""
        graph = RPGGraph()
        n1 = make_node(name="module_a")
        n2 = make_node(name="component_b", level=NodeLevel.COMPONENT, parent_id=n1.id)
        graph.add_node(n1)
        graph.add_node(n2)

        edge = make_edge(n1.id, n2.id, EdgeType.HIERARCHY)
        graph.add_edge(edge)

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)

        assert restored.node_count == 2
        assert restored.edge_count == 1
        restored_edge = restored.get_edge(edge.id)
        assert restored_edge is not None
        assert restored_edge.edge_type == EdgeType.HIERARCHY

    def test_graph_with_all_edge_types_round_trip(self) -> None:
        """Graph with all edge types survives round-trip."""
        graph = RPGGraph()
        nodes = [make_node(name=f"n{i}") for i in range(6)]
        for n in nodes:
            graph.add_node(n)

        edges = [
            make_edge(nodes[0].id, nodes[1].id, EdgeType.HIERARCHY),
            make_edge(nodes[1].id, nodes[2].id, EdgeType.DATA_FLOW, data_id="x", data_type="str"),
            make_edge(nodes[2].id, nodes[3].id, EdgeType.ORDERING),
            make_edge(nodes[3].id, nodes[4].id, EdgeType.INHERITANCE),
            make_edge(nodes[4].id, nodes[5].id, EdgeType.INVOCATION),
        ]
        for e in edges:
            graph.add_edge(e)

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)

        assert restored.edge_count == 5
        for orig_edge in edges:
            restored_edge = restored.get_edge(orig_edge.id)
            assert restored_edge is not None
            assert restored_edge.edge_type == orig_edge.edge_type

    def test_graph_with_metadata_round_trip(self) -> None:
        """Graph metadata survives JSON round-trip."""
        graph = RPGGraph(metadata={
            "project": "zerorepo",
            "version": "0.1.0",
            "timestamp": "2026-02-07T10:00:00Z",
            "nested": {"key": "value"},
        })
        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)
        assert restored.metadata == graph.metadata

    def test_large_graph_round_trip(self) -> None:
        """Graph with 10 nodes and 15 edges survives round-trip with equality."""
        graph = RPGGraph(metadata={"test": "large"})

        # Create 10 nodes
        nodes = [make_node(name=f"node_{i}") for i in range(10)]
        for n in nodes:
            graph.add_node(n)

        # Create 15 edges (connect each node to the next, then some extra)
        edges_added = 0
        for i in range(9):
            e = make_edge(nodes[i].id, nodes[i + 1].id)
            graph.add_edge(e)
            edges_added += 1

        # Add 6 more edges for cross-connections
        extra_pairs = [(0, 2), (0, 5), (1, 4), (3, 7), (5, 9), (6, 8)]
        for src, tgt in extra_pairs:
            e = make_edge(nodes[src].id, nodes[tgt].id)
            graph.add_edge(e)
            edges_added += 1

        assert edges_added == 15
        assert graph.node_count == 10
        assert graph.edge_count == 15

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)

        assert restored.node_count == 10
        assert restored.edge_count == 15

    def test_invalid_json_raises(self) -> None:
        """Invalid JSON string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            RPGGraph.from_json("not valid json {{{")

    def test_to_json_produces_pretty_format(self) -> None:
        """to_json uses indentation for readability."""
        graph = RPGGraph(metadata={"project": "test"})
        json_str = graph.to_json(indent=2)
        # Pretty printed JSON has newlines
        assert "\n" in json_str
        # Can be parsed back
        json.loads(json_str)


class TestGraphEquality:
    """Test RPGGraph equality comparison."""

    def test_empty_graphs_equal(self) -> None:
        """Two empty graphs are equal."""
        g1 = RPGGraph()
        g2 = RPGGraph()
        assert g1 == g2

    def test_graphs_with_same_nodes_equal(self) -> None:
        """Graphs with identical nodes are equal."""
        node_id = uuid4()
        node_data = {
            "id": node_id,
            "name": "test",
            "level": NodeLevel.MODULE,
            "node_type": NodeType.FUNCTIONALITY,
        }
        g1 = RPGGraph()
        g1.add_node(RPGNode(**node_data))
        g2 = RPGGraph()
        g2.add_node(RPGNode(**node_data))
        assert g1 == g2

    def test_graphs_different_nodes_not_equal(self) -> None:
        """Graphs with different nodes are not equal."""
        g1 = RPGGraph()
        g1.add_node(make_node(name="a"))
        g2 = RPGGraph()
        g2.add_node(make_node(name="b"))
        assert g1 != g2

    def test_not_equal_to_non_graph(self) -> None:
        """Graph is not equal to non-RPGGraph object."""
        g = RPGGraph()
        assert g != "not a graph"
        assert g != 42


class TestGraphEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_remove_node_with_many_edges(self) -> None:
        """Remove a hub node connected to many edges."""
        graph = RPGGraph()
        hub = make_node(name="hub")
        graph.add_node(hub)

        spokes = [make_node(name=f"spoke_{i}") for i in range(10)]
        for s in spokes:
            graph.add_node(s)
            graph.add_edge(make_edge(hub.id, s.id))

        assert graph.edge_count == 10
        graph.remove_node(hub.id)
        assert graph.edge_count == 0
        assert graph.node_count == 10  # Spokes still exist

    def test_add_edge_after_node_removal_fails(self) -> None:
        """Cannot add edge to a removed node."""
        graph = RPGGraph()
        n1 = make_node(name="a")
        n2 = make_node(name="b")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.remove_node(n1.id)

        with pytest.raises(ValueError, match="Source node.*not found"):
            graph.add_edge(make_edge(n1.id, n2.id))

    def test_graph_with_complex_node_types(self) -> None:
        """Graph handles FUNCTION_AUGMENTED nodes with full metadata."""
        graph = RPGGraph()
        node = RPGNode(
            name="process_payment",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/payment",
            file_path="src/payment/processor.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def process_payment(amount: float) -> bool",
            docstring="Process a payment",
            implementation="def process_payment(amount: float) -> bool:\n    return True",
            test_status=TestStatus.PASSED,
            serena_validated=True,
            actual_dependencies=[uuid4()],
            metadata={"complexity": "high"},
        )
        graph.add_node(node)

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)
        restored_node = restored.get_node(node.id)
        assert restored_node is not None
        assert restored_node.interface_type == InterfaceType.FUNCTION
        assert restored_node.test_status == TestStatus.PASSED
        assert restored_node.metadata["complexity"] == "high"

    def test_properties(self) -> None:
        """node_count and edge_count properties work correctly."""
        graph = RPGGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0

        n1 = make_node(name="a")
        n2 = make_node(name="b")
        graph.add_node(n1)
        assert graph.node_count == 1

        graph.add_node(n2)
        assert graph.node_count == 2

        graph.add_edge(make_edge(n1.id, n2.id))
        assert graph.edge_count == 1
