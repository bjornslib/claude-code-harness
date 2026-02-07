"""Tests for FolderEncoder – Epic 3.1 folder-level structural encoding."""

from __future__ import annotations

import logging
from uuid import UUID

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
from zerorepo.rpg_enrichment.folder_encoder import FolderEncoder, _to_package_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    level: NodeLevel = NodeLevel.MODULE,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    **kwargs,
) -> RPGNode:
    return RPGNode(name=name, level=level, node_type=node_type, **kwargs)


def _make_hierarchy_edge(parent_id: UUID, child_id: UUID) -> RPGEdge:
    return RPGEdge(
        source_id=parent_id,
        target_id=child_id,
        edge_type=EdgeType.HIERARCHY,
    )


def _build_tree_graph() -> tuple[RPGGraph, dict[str, UUID]]:
    """Build a 3-level tree: root → (algorithms, evaluation) → leaves.

    Returns the graph and a name→UUID mapping.
    """
    graph = RPGGraph()
    ids: dict[str, UUID] = {}

    # Root
    root = _make_node("project_root", level=NodeLevel.MODULE)
    graph.add_node(root)
    ids["root"] = root.id

    # Level 1 children
    alg = _make_node("algorithms", level=NodeLevel.MODULE)
    graph.add_node(alg)
    ids["algorithms"] = alg.id
    graph.add_edge(_make_hierarchy_edge(root.id, alg.id))

    evl = _make_node("evaluation", level=NodeLevel.MODULE)
    graph.add_node(evl)
    ids["evaluation"] = evl.id
    graph.add_edge(_make_hierarchy_edge(root.id, evl.id))

    # Level 2 leaves under algorithms
    for name in ["linear_models", "tree_models"]:
        leaf = _make_node(
            name,
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
        )
        graph.add_node(leaf)
        ids[name] = leaf.id
        graph.add_edge(_make_hierarchy_edge(alg.id, leaf.id))

    # Leaf under evaluation
    metrics = _make_node(
        "metrics",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FILE_AUGMENTED,
    )
    graph.add_node(metrics)
    ids["metrics"] = metrics.id
    graph.add_edge(_make_hierarchy_edge(evl.id, metrics.id))

    return graph, ids


# ===========================================================================
# Test: _to_package_name utility
# ===========================================================================


class TestToPackageName:
    def test_simple_lowercase(self) -> None:
        assert _to_package_name("algorithms") == "algorithms"

    def test_spaces_to_underscores(self) -> None:
        assert _to_package_name("My Module") == "my_module"

    def test_hyphens_to_underscores(self) -> None:
        assert _to_package_name("data-loading") == "data_loading"

    def test_dots_to_underscores(self) -> None:
        assert _to_package_name("v2.0.module") == "v2_0_module"

    def test_leading_digit(self) -> None:
        result = _to_package_name("3d_models")
        assert result[0] == "_"
        assert result.isidentifier()

    def test_python_keyword(self) -> None:
        result = _to_package_name("class")
        assert result == "class_pkg"

    def test_special_chars_stripped(self) -> None:
        result = _to_package_name("my@module#v2!")
        assert result == "mymodulev2"

    def test_empty_becomes_unnamed(self) -> None:
        assert _to_package_name("") == "unnamed"
        assert _to_package_name("@#$") == "unnamed"


# ===========================================================================
# Test: FolderEncoder on tree graphs
# ===========================================================================


class TestFolderEncoderTreeGraph:
    """Tests for FolderEncoder on well-structured HIERARCHY trees."""

    def test_root_gets_empty_folder_path(self) -> None:
        graph, ids = _build_tree_graph()
        FolderEncoder().encode(graph)
        root = graph.nodes[ids["root"]]
        assert root.folder_path == ""

    def test_namespace_inheritance(self) -> None:
        graph, ids = _build_tree_graph()
        FolderEncoder().encode(graph)

        alg = graph.nodes[ids["algorithms"]]
        assert alg.folder_path == "algorithms/"

        evl = graph.nodes[ids["evaluation"]]
        assert evl.folder_path == "evaluation/"

    def test_leaf_inherits_full_path(self) -> None:
        graph, ids = _build_tree_graph()
        FolderEncoder().encode(graph)

        lm = graph.nodes[ids["linear_models"]]
        assert lm.folder_path == "algorithms/linear_models/"

        tm = graph.nodes[ids["tree_models"]]
        assert tm.folder_path == "algorithms/tree_models/"

        met = graph.nodes[ids["metrics"]]
        assert met.folder_path == "evaluation/metrics/"

    def test_all_nodes_have_folder_path(self) -> None:
        graph, ids = _build_tree_graph()
        FolderEncoder().encode(graph)
        for nid, node in graph.nodes.items():
            assert node.folder_path is not None, f"Node {node.name} missing folder_path"


class TestFolderEncoderValidation:
    """Tests for FolderEncoder.validate()."""

    def test_validate_passes_after_encode(self) -> None:
        graph, _ = _build_tree_graph()
        enc = FolderEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True
        assert result.errors == []

    def test_validate_fails_without_encode(self) -> None:
        graph, _ = _build_tree_graph()
        enc = FolderEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert len(result.errors) > 0

    def test_validate_warns_on_oversized_folder(self) -> None:
        """Create a MODULE with many leaf descendants to trigger oversized warning."""
        graph = RPGGraph()
        mod = _make_node("big_module", level=NodeLevel.MODULE)
        graph.add_node(mod)

        # Add 50 leaf descendants → estimated_files = 50/3 ≈ 16 > 15
        for i in range(50):
            leaf = _make_node(
                f"feature_{i}",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTIONALITY,
            )
            graph.add_node(leaf)
            graph.add_edge(_make_hierarchy_edge(mod.id, leaf.id))

        enc = FolderEncoder(max_files_per_folder=15)
        enc.encode(graph)

        result = enc.validate(graph)
        # Should pass (oversized is a warning, not an error)
        assert result.passed is True
        assert any("consider submodule split" in w for w in result.warnings)


class TestFolderEncoderEdgeCases:
    """Edge case tests for FolderEncoder."""

    def test_empty_graph(self) -> None:
        graph = RPGGraph()
        enc = FolderEncoder()
        result = enc.encode(graph)
        assert result is graph
        vr = enc.validate(graph)
        assert vr.passed is True

    def test_single_node(self) -> None:
        graph = RPGGraph()
        node = _make_node("solo")
        graph.add_node(node)

        FolderEncoder().encode(graph)
        assert node.folder_path == ""

    def test_no_hierarchy_edges(self) -> None:
        """Nodes without HIERARCHY edges should still get folder_path."""
        graph = RPGGraph()
        n1 = _make_node("mod_a", level=NodeLevel.MODULE)
        n2 = _make_node("mod_b", level=NodeLevel.MODULE)
        graph.add_node(n1)
        graph.add_node(n2)

        FolderEncoder().encode(graph)
        assert n1.folder_path is not None
        assert n2.folder_path is not None

    def test_disconnected_nodes(self) -> None:
        """Disconnected non-module nodes get root folder."""
        graph = RPGGraph()
        mod = _make_node("main", level=NodeLevel.MODULE)
        orphan = _make_node("orphan", level=NodeLevel.COMPONENT)
        graph.add_node(mod)
        graph.add_node(orphan)

        FolderEncoder().encode(graph)
        assert orphan.folder_path is not None

    def test_folder_path_python_identifier(self) -> None:
        """All folder path components must be valid Python identifiers."""
        graph = RPGGraph()
        root = _make_node("root")
        child = _make_node("Data Loading v2.0")
        graph.add_node(root)
        graph.add_node(child)
        graph.add_edge(_make_hierarchy_edge(root.id, child.id))

        enc = FolderEncoder()
        enc.encode(graph)

        # Validate that the folder name is a valid identifier
        result = enc.validate(graph)
        assert result.passed is True

    def test_estimated_files_metadata(self) -> None:
        """MODULE nodes should have estimated_files in metadata."""
        graph, ids = _build_tree_graph()
        FolderEncoder().encode(graph)

        root = graph.nodes[ids["root"]]
        if root.level == NodeLevel.MODULE:
            assert "estimated_files" in root.metadata


class TestFolderEncoderInPipeline:
    """Test FolderEncoder works correctly in RPGBuilder pipeline."""

    def test_encode_then_validate_in_pipeline(self) -> None:
        from zerorepo.rpg_enrichment.pipeline import RPGBuilder

        graph, _ = _build_tree_graph()
        builder = RPGBuilder()
        builder.add_encoder(FolderEncoder())
        result = builder.run(graph)

        assert result is graph
        assert builder.steps[0].validation is not None
        assert builder.steps[0].validation.passed is True
