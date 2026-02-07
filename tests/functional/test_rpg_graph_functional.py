"""Functional tests for RPGGraph container.

These tests simulate real-world usage patterns: building realistic
graph structures, serializing/deserializing, and testing graph
operations in complex scenarios.
"""

import json
from uuid import uuid4

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


pytestmark = pytest.mark.functional


class TestBuildModuleHierarchy:
    """Functional: Build graph with MODULE → COMPONENT → FEATURE hierarchy."""

    def test_build_3_modules_5_components_10_hierarchy_edges(self) -> None:
        """Build graph: 3 MODULE nodes, 5 COMPONENT children, 10 HIERARCHY edges."""
        graph = RPGGraph(metadata={"project": "auth_system", "version": "1.0"})

        # Create 3 modules
        modules = []
        for name in ["authentication", "authorization", "user_management"]:
            mod = RPGNode(
                name=name,
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=f"src/{name}",
            )
            graph.add_node(mod)
            modules.append(mod)

        # Module 0 gets 2 components, module 1 gets 2, module 2 gets 1
        comp_configs = [
            (modules[0], ["login", "registration"]),
            (modules[1], ["roles", "permissions"]),
            (modules[2], ["profile"]),
        ]

        components = []
        for parent, comp_names in comp_configs:
            for name in comp_names:
                comp = RPGNode(
                    name=name,
                    level=NodeLevel.COMPONENT,
                    node_type=NodeType.FOLDER_AUGMENTED,
                    parent_id=parent.id,
                    folder_path=f"{parent.folder_path}/{name}",
                )
                graph.add_node(comp)
                graph.add_edge(RPGEdge(
                    source_id=parent.id,
                    target_id=comp.id,
                    edge_type=EdgeType.HIERARCHY,
                ))
                components.append(comp)

        # Each component gets 2 features = 10 features, 10 more edges
        features = []
        for comp in components:
            for i in range(2):
                feat = RPGNode(
                    name=f"{comp.name}_feature_{i}",
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTION_AUGMENTED,
                    parent_id=comp.id,
                    folder_path=comp.folder_path,
                    file_path=f"{comp.folder_path}/impl_{i}.py",
                    interface_type=InterfaceType.FUNCTION,
                    signature=f"def {comp.name}_feature_{i}() -> None",
                )
                graph.add_node(feat)
                graph.add_edge(RPGEdge(
                    source_id=comp.id,
                    target_id=feat.id,
                    edge_type=EdgeType.HIERARCHY,
                ))
                features.append(feat)

        # 3 modules + 5 components + 10 features = 18 nodes
        assert graph.node_count == 18
        # 5 (mod->comp) + 10 (comp->feat) = 15 hierarchy edges
        assert graph.edge_count == 15

    def test_serialize_deserialize_preserves_counts(self) -> None:
        """Serialize → deserialize → assert node/edge counts match."""
        graph = RPGGraph(metadata={"project": "test"})

        # Build a small hierarchy
        mod = RPGNode(name="mod", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
        graph.add_node(mod)

        for i in range(3):
            comp = RPGNode(
                name=f"comp_{i}",
                level=NodeLevel.COMPONENT,
                node_type=NodeType.FOLDER_AUGMENTED,
                parent_id=mod.id,
            )
            graph.add_node(comp)
            graph.add_edge(RPGEdge(
                source_id=mod.id,
                target_id=comp.id,
                edge_type=EdgeType.HIERARCHY,
            ))

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)

        assert restored.node_count == graph.node_count
        assert restored.edge_count == graph.edge_count
        assert restored.metadata == graph.metadata


class TestRemoveModuleNode:
    """Functional: Remove MODULE node and verify edge cleanup."""

    def test_remove_module_removes_parent_edges(self) -> None:
        """Remove MODULE node → assert child COMPONENT nodes remain but parent edges removed."""
        graph = RPGGraph()

        mod = RPGNode(name="auth", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
        comp1 = RPGNode(name="login", level=NodeLevel.COMPONENT, node_type=NodeType.FOLDER_AUGMENTED, parent_id=mod.id)
        comp2 = RPGNode(name="register", level=NodeLevel.COMPONENT, node_type=NodeType.FOLDER_AUGMENTED, parent_id=mod.id)

        graph.add_node(mod)
        graph.add_node(comp1)
        graph.add_node(comp2)

        e1 = RPGEdge(source_id=mod.id, target_id=comp1.id, edge_type=EdgeType.HIERARCHY)
        e2 = RPGEdge(source_id=mod.id, target_id=comp2.id, edge_type=EdgeType.HIERARCHY)
        # Also an edge between components (not involving mod)
        e3 = RPGEdge(source_id=comp1.id, target_id=comp2.id, edge_type=EdgeType.DATA_FLOW, data_id="session")

        graph.add_edge(e1)
        graph.add_edge(e2)
        graph.add_edge(e3)

        assert graph.node_count == 3
        assert graph.edge_count == 3

        # Remove the module
        graph.remove_node(mod.id)

        # Module gone, components remain
        assert graph.node_count == 2
        assert graph.get_node(comp1.id) is not None
        assert graph.get_node(comp2.id) is not None
        assert graph.get_node(mod.id) is None

        # Parent hierarchy edges removed, component-to-component edge remains
        assert graph.edge_count == 1
        assert graph.get_edge(e1.id) is None
        assert graph.get_edge(e2.id) is None
        assert graph.get_edge(e3.id) is not None


class TestComplexGraphRoundTrip:
    """Functional: Build complex graph and verify round-trip fidelity."""

    def _build_complex_graph(self) -> RPGGraph:
        """Build a complex RPG with mixed node types and edge types."""
        graph = RPGGraph(metadata={
            "project": "zerorepo_test",
            "version": "0.1.0",
            "description": "Complex test graph",
        })

        # 3 modules
        modules = []
        for name in ["auth", "payment", "analytics"]:
            mod = RPGNode(
                name=name,
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=f"src/{name}",
                docstring=f"The {name} module",
            )
            graph.add_node(mod)
            modules.append(mod)

        # 10 components (spread across modules)
        components = []
        comp_per_mod = [4, 3, 3]
        for mod_idx, count in enumerate(comp_per_mod):
            for i in range(count):
                comp = RPGNode(
                    name=f"{modules[mod_idx].name}_comp_{i}",
                    level=NodeLevel.COMPONENT,
                    node_type=NodeType.FOLDER_AUGMENTED,
                    parent_id=modules[mod_idx].id,
                    folder_path=f"src/{modules[mod_idx].name}/comp_{i}",
                )
                graph.add_node(comp)
                graph.add_edge(RPGEdge(
                    source_id=modules[mod_idx].id,
                    target_id=comp.id,
                    edge_type=EdgeType.HIERARCHY,
                ))
                components.append(comp)

        # 30 features (3 per component)
        features = []
        for comp in components:
            for i in range(3):
                feat = RPGNode(
                    name=f"{comp.name}_feat_{i}",
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTION_AUGMENTED,
                    parent_id=comp.id,
                    folder_path=comp.folder_path,
                    file_path=f"{comp.folder_path}/feat_{i}.py",
                    interface_type=InterfaceType.FUNCTION,
                    signature=f"def {comp.name}_feat_{i}() -> None",
                    metadata={"index": i},
                )
                graph.add_node(feat)
                graph.add_edge(RPGEdge(
                    source_id=comp.id,
                    target_id=feat.id,
                    edge_type=EdgeType.HIERARCHY,
                ))
                features.append(feat)

        # Add some cross-module DATA_FLOW edges
        if len(features) >= 10:
            graph.add_edge(RPGEdge(
                source_id=features[0].id,
                target_id=features[5].id,
                edge_type=EdgeType.DATA_FLOW,
                data_id="auth_token",
                data_type="str",
                transformation="JWT encode",
            ))
            graph.add_edge(RPGEdge(
                source_id=features[5].id,
                target_id=features[8].id,
                edge_type=EdgeType.INVOCATION,
            ))

        return graph

    def test_complex_graph_counts(self) -> None:
        """Complex graph has expected node/edge counts."""
        graph = self._build_complex_graph()
        # 3 modules + 10 components + 30 features = 43 nodes
        assert graph.node_count == 43
        # 10 (mod->comp) + 30 (comp->feat) + 2 cross-module = 42 edges
        assert graph.edge_count == 42

    def test_complex_graph_round_trip(self) -> None:
        """Complex graph survives full JSON round-trip."""
        graph = self._build_complex_graph()
        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)

        assert restored.node_count == graph.node_count
        assert restored.edge_count == graph.edge_count
        assert restored.metadata == graph.metadata

        # Spot check a few nodes
        for node_id, node in list(graph.nodes.items())[:5]:
            restored_node = restored.get_node(node_id)
            assert restored_node is not None
            assert restored_node.name == node.name
            assert restored_node.level == node.level

    def test_complex_graph_json_size(self) -> None:
        """Complex graph JSON is reasonably sized."""
        graph = self._build_complex_graph()
        json_str = graph.to_json()
        size_kb = len(json_str) / 1024
        # 43 nodes + 42 edges should be well under 1MB
        assert size_kb < 1000  # Less than 1MB

    def test_modify_and_reserialize(self) -> None:
        """Modify deserialized graph → re-serialize → different file."""
        graph = self._build_complex_graph()
        json_str_1 = graph.to_json()
        restored = RPGGraph.from_json(json_str_1)

        # Add a new node
        new_node = RPGNode(
            name="new_feature",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src/new",
            file_path="src/new/impl.py",
        )
        restored.add_node(new_node)
        assert restored.node_count == graph.node_count + 1

        json_str_2 = restored.to_json()
        assert json_str_1 != json_str_2

        # Verify the second serialization is valid
        restored_2 = RPGGraph.from_json(json_str_2)
        assert restored_2.node_count == graph.node_count + 1


class TestGraphIntegrity:
    """Functional: Verify graph maintains integrity through operations."""

    def test_add_remove_cycle(self) -> None:
        """Add nodes/edges, remove some, verify integrity."""
        graph = RPGGraph()

        # Add 5 nodes in a chain
        nodes = [RPGNode(name=f"n{i}", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY) for i in range(5)]
        for n in nodes:
            graph.add_node(n)

        edges = []
        for i in range(4):
            e = RPGEdge(source_id=nodes[i].id, target_id=nodes[i + 1].id, edge_type=EdgeType.HIERARCHY)
            graph.add_edge(e)
            edges.append(e)

        assert graph.node_count == 5
        assert graph.edge_count == 4

        # Remove middle node (n2)
        graph.remove_node(nodes[2].id)
        assert graph.node_count == 4
        # Edges n1->n2 and n2->n3 should be removed
        assert graph.edge_count == 2  # n0->n1 and n3->n4 remain

        # Can still add new edges between remaining nodes
        new_edge = RPGEdge(
            source_id=nodes[1].id,
            target_id=nodes[3].id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="bypass",
        )
        graph.add_edge(new_edge)
        assert graph.edge_count == 3

    def test_empty_graph_operations(self) -> None:
        """Operations on empty graph work correctly."""
        graph = RPGGraph()

        assert graph.get_node(uuid4()) is None
        assert graph.get_edge(uuid4()) is None
        assert graph.remove_node(uuid4()) is False
        assert graph.remove_edge(uuid4()) is False

        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)
        assert restored.node_count == 0
        assert restored.edge_count == 0

    def test_batch_operations(self) -> None:
        """Build large graph with batch operations."""
        graph = RPGGraph(metadata={"batch_test": True})

        # Add 100 nodes
        nodes = [
            RPGNode(name=f"node_{i}", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
            for i in range(100)
        ]
        for n in nodes:
            graph.add_node(n)

        # Add 99 chain edges
        for i in range(99):
            graph.add_edge(RPGEdge(
                source_id=nodes[i].id,
                target_id=nodes[i + 1].id,
                edge_type=EdgeType.HIERARCHY,
            ))

        assert graph.node_count == 100
        assert graph.edge_count == 99

        # Round trip
        json_str = graph.to_json()
        restored = RPGGraph.from_json(json_str)
        assert restored.node_count == 100
        assert restored.edge_count == 99
