"""Tests for IntraModuleOrderEncoder – Epic 3.4 file ordering."""

from __future__ import annotations

import logging
from uuid import UUID

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.file_encoder import FileEncoder
from cobuilder.repomap.rpg_enrichment.folder_encoder import FolderEncoder
from cobuilder.repomap.rpg_enrichment.ordering_encoder import IntraModuleOrderEncoder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    level: NodeLevel = NodeLevel.FEATURE,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    **kwargs,
) -> RPGNode:
    return RPGNode(name=name, level=level, node_type=node_type, **kwargs)


def _h_edge(parent_id: UUID, child_id: UUID) -> RPGEdge:
    return RPGEdge(source_id=parent_id, target_id=child_id, edge_type=EdgeType.HIERARCHY)


def _dep_edge(source_id: UUID, target_id: UUID) -> RPGEdge:
    return RPGEdge(source_id=source_id, target_id=target_id, edge_type=EdgeType.DATA_FLOW)


def _build_module_with_files(
    file_deps: list[tuple[str, str]] | None = None,
) -> tuple[RPGGraph, dict[str, UUID]]:
    """Build a module with 3 files (A, B, C), each containing one leaf.

    Each leaf gets a folder_path matching the module and a distinct file_path.

    Args:
        file_deps: List of (source_leaf, target_leaf) dependency pairs.
    """
    graph = RPGGraph()
    ids: dict[str, UUID] = {}

    mod = RPGNode(name="my_module", level=NodeLevel.MODULE, node_type=NodeType.FOLDER_AUGMENTED)
    graph.add_node(mod)
    ids["module"] = mod.id

    # Create leaves with pre-set folder_path and file_path to avoid
    # validator conflicts (file_path must start with folder_path).
    file_map = {
        "feature_a": "file_a.py",
        "feature_b": "file_b.py",
        "feature_c": "file_c.py",
    }
    for leaf_name, file_name in file_map.items():
        leaf = _make_node(
            leaf_name,
            folder_path="my_module/",
            file_path=f"my_module/{file_name}",
        )
        graph.add_node(leaf)
        ids[leaf_name] = leaf.id
        graph.add_edge(_h_edge(mod.id, leaf.id))

    # Set module folder_path
    mod.folder_path = ""

    # Add dependency edges
    if file_deps:
        for src_name, tgt_name in file_deps:
            graph.add_edge(_dep_edge(ids[src_name], ids[tgt_name]))

    return graph, ids


# ===========================================================================
# Test: Basic ordering
# ===========================================================================


class TestIntraModuleOrderBasic:
    """Basic tests for file ordering within modules."""

    def test_simple_dependency_chain(self) -> None:
        """A depends on B, B depends on C → order: C, B, A."""
        graph, ids = _build_module_with_files([
            ("feature_a", "feature_b"),  # A depends on B
            ("feature_b", "feature_c"),  # B depends on C
        ])

        IntraModuleOrderEncoder().encode(graph)
        mod = graph.nodes[ids["module"]]
        file_order = mod.metadata.get("file_order", [])

        assert len(file_order) == 3
        assert file_order.index("my_module/file_c.py") < file_order.index("my_module/file_b.py")
        assert file_order.index("my_module/file_b.py") < file_order.index("my_module/file_a.py")

    def test_no_dependencies(self) -> None:
        """Without dependencies, all files appear (order may vary)."""
        graph, ids = _build_module_with_files()

        IntraModuleOrderEncoder().encode(graph)
        mod = graph.nodes[ids["module"]]
        file_order = mod.metadata.get("file_order", [])

        assert len(file_order) == 3
        assert set(file_order) == {
            "my_module/file_a.py",
            "my_module/file_b.py",
            "my_module/file_c.py",
        }

    def test_single_dependency(self) -> None:
        """A depends on C → C before A, B anywhere."""
        graph, ids = _build_module_with_files([
            ("feature_a", "feature_c"),
        ])

        IntraModuleOrderEncoder().encode(graph)
        mod = graph.nodes[ids["module"]]
        file_order = mod.metadata.get("file_order", [])

        assert file_order.index("my_module/file_c.py") < file_order.index("my_module/file_a.py")

    def test_multiple_module_nodes(self) -> None:
        """Each MODULE node gets its own file_order."""
        graph = RPGGraph()
        ids: dict[str, UUID] = {}

        for mod_name, leaf_name in [("mod_x", "feat_x"), ("mod_y", "feat_y")]:
            mod = RPGNode(name=mod_name, level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
            graph.add_node(mod)
            ids[mod_name] = mod.id

            leaf = _make_node(leaf_name)
            leaf.file_path = f"{mod_name}/{leaf_name}.py"
            leaf.folder_path = f"{mod_name}/"
            graph.add_node(leaf)
            ids[leaf_name] = leaf.id
            graph.add_edge(_h_edge(mod.id, leaf.id))

        # Set folder_path on modules
        graph.nodes[ids["mod_x"]].folder_path = "mod_x/"
        graph.nodes[ids["mod_y"]].folder_path = "mod_y/"

        IntraModuleOrderEncoder().encode(graph)

        for mod_name in ["mod_x", "mod_y"]:
            mod = graph.nodes[ids[mod_name]]
            assert "file_order" in mod.metadata
            assert len(mod.metadata["file_order"]) == 1


# ===========================================================================
# Test: Circular dependencies
# ===========================================================================


class TestIntraModuleOrderCircular:
    """Tests for circular dependency handling."""

    def test_circular_dependency_detected(self) -> None:
        """Circular deps should be flagged but not crash."""
        graph, ids = _build_module_with_files([
            ("feature_a", "feature_b"),
            ("feature_b", "feature_a"),  # Circular!
        ])

        enc = IntraModuleOrderEncoder()
        enc.encode(graph)

        mod = graph.nodes[ids["module"]]
        # Should still have file_order (with remaining files appended)
        assert "file_order" in mod.metadata
        assert len(mod.metadata["file_order"]) == 3
        assert mod.metadata.get("file_order_circular") is True

    def test_circular_triggers_validation_warning(self) -> None:
        graph, ids = _build_module_with_files([
            ("feature_a", "feature_b"),
            ("feature_b", "feature_a"),
        ])

        enc = IntraModuleOrderEncoder()
        enc.encode(graph)
        result = enc.validate(graph)

        assert result.passed is True  # Warnings don't fail
        assert any("circular" in w.lower() for w in result.warnings)


# ===========================================================================
# Test: Validation
# ===========================================================================


class TestIntraModuleOrderValidation:
    """Tests for IntraModuleOrderEncoder.validate()."""

    def test_validate_passes_after_encode(self) -> None:
        graph, _ = _build_module_with_files()
        enc = IntraModuleOrderEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_validate_fails_without_encode(self) -> None:
        graph, _ = _build_module_with_files()
        enc = IntraModuleOrderEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert any("missing file_order" in e for e in result.errors)


# ===========================================================================
# Test: Edge cases
# ===========================================================================


class TestIntraModuleOrderEdgeCases:
    """Edge case tests."""

    def test_empty_graph(self) -> None:
        graph = RPGGraph()
        enc = IntraModuleOrderEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_module_with_no_files(self) -> None:
        """A module whose leaves have no file_path gets empty file_order."""
        graph = RPGGraph()
        mod = RPGNode(name="empty_mod", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
        graph.add_node(mod)
        mod.folder_path = "empty_mod/"

        enc = IntraModuleOrderEncoder()
        enc.encode(graph)
        assert mod.metadata["file_order"] == []


# ===========================================================================
# Test: Full pipeline integration
# ===========================================================================


class TestIntraModuleOrderInPipeline:
    """Test the ordering encoder in a full pipeline."""

    def test_folder_file_ordering_pipeline(self) -> None:
        from cobuilder.repomap.rpg_enrichment.pipeline import RPGBuilder

        graph = RPGGraph()
        ids: dict[str, UUID] = {}

        mod = RPGNode(name="pipeline_mod", level=NodeLevel.MODULE, node_type=NodeType.FOLDER_AUGMENTED)
        graph.add_node(mod)
        ids["module"] = mod.id

        for name in ["alpha", "beta"]:
            leaf = _make_node(name)
            graph.add_node(leaf)
            ids[name] = leaf.id
            graph.add_edge(_h_edge(mod.id, leaf.id))

        builder = RPGBuilder()
        builder.add_encoder(FolderEncoder())
        builder.add_encoder(FileEncoder())
        builder.add_encoder(IntraModuleOrderEncoder())
        result = builder.run(graph)

        assert result is graph
        assert len(builder.steps) == 3
        # All steps should validate
        for step in builder.steps:
            assert step.validation is not None
            assert step.validation.passed is True

        # Module should have file_order
        mod_node = graph.nodes[ids["module"]]
        assert "file_order" in mod_node.metadata
