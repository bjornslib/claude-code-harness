"""Tests for FileEncoder – Epic 3.2 file-level structural encoding."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.file_encoder import FileEncoder, _to_file_name
from zerorepo.rpg_enrichment.folder_encoder import FolderEncoder


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


def _make_hierarchy_edge(parent_id: UUID, child_id: UUID) -> RPGEdge:
    return RPGEdge(
        source_id=parent_id,
        target_id=child_id,
        edge_type=EdgeType.HIERARCHY,
    )


def _build_module_with_leaves(
    module_name: str, leaf_names: list[str]
) -> tuple[RPGGraph, dict[str, UUID]]:
    """Build a graph with one MODULE parent and N FEATURE leaves."""
    graph = RPGGraph()
    ids: dict[str, UUID] = {}

    mod = RPGNode(
        name=module_name,
        level=NodeLevel.MODULE,
        node_type=NodeType.FOLDER_AUGMENTED,
    )
    graph.add_node(mod)
    ids["module"] = mod.id

    for name in leaf_names:
        leaf = _make_node(name, level=NodeLevel.FEATURE)
        graph.add_node(leaf)
        ids[name] = leaf.id
        graph.add_edge(_make_hierarchy_edge(mod.id, leaf.id))

    return graph, ids


def _pre_encode_folders(graph: RPGGraph) -> RPGGraph:
    """Run FolderEncoder first (FileEncoder expects folder_path set)."""
    return FolderEncoder().encode(graph)


# ===========================================================================
# Test: _to_file_name utility
# ===========================================================================


class TestToFileName:
    def test_simple_name(self) -> None:
        assert _to_file_name("data_loaders") == "data_loaders.py"

    def test_spaces_to_underscores(self) -> None:
        assert _to_file_name("My Feature") == "my_feature.py"

    def test_hyphens_to_underscores(self) -> None:
        assert _to_file_name("data-loading") == "data_loading.py"

    def test_leading_digit(self) -> None:
        result = _to_file_name("3d_models")
        assert result.startswith("_")
        assert result.endswith(".py")

    def test_special_chars(self) -> None:
        result = _to_file_name("my@module!")
        assert result == "mymodule.py"

    def test_empty_becomes_module(self) -> None:
        assert _to_file_name("") == "module.py"

    def test_already_has_py(self) -> None:
        # Should not double-add .py
        result = _to_file_name("utils")
        assert result == "utils.py"


# ===========================================================================
# Test: FileEncoder basic encoding
# ===========================================================================


class TestFileEncoderBasic:
    """Basic FileEncoder tests."""

    def test_assigns_file_path_to_leaves(self) -> None:
        graph, ids = _build_module_with_leaves(
            "data_loading", ["load_json", "load_csv"]
        )
        _pre_encode_folders(graph)
        FileEncoder().encode(graph)

        for name in ["load_json", "load_csv"]:
            node = graph.nodes[ids[name]]
            assert node.file_path is not None
            assert node.file_path.endswith(".py")

    def test_file_path_under_folder_path(self) -> None:
        graph, ids = _build_module_with_leaves("algorithms", ["linear_reg"])
        _pre_encode_folders(graph)
        FileEncoder().encode(graph)

        leaf = graph.nodes[ids["linear_reg"]]
        assert leaf.folder_path is not None
        assert leaf.file_path.startswith(leaf.folder_path)

    def test_siblings_grouped_by_parent(self) -> None:
        """Siblings under same parent should all get file assignments
        with file names derived from the parent."""
        graph, ids = _build_module_with_leaves(
            "data_loading", ["load_json", "load_csv", "load_parquet"]
        )
        _pre_encode_folders(graph)
        FileEncoder().encode(graph)

        # All leaves should have file_path assigned
        for name in ["load_json", "load_csv", "load_parquet"]:
            node = graph.nodes[ids[name]]
            assert node.file_path is not None
            assert node.file_path.endswith(".py")
            # File should be under the leaf's folder_path
            assert node.file_path.startswith(node.folder_path)

    def test_estimated_loc_metadata(self) -> None:
        graph, ids = _build_module_with_leaves("mod", ["feat_a"])
        _pre_encode_folders(graph)
        FileEncoder().encode(graph)

        node = graph.nodes[ids["feat_a"]]
        assert "estimated_loc" in node.metadata
        assert node.metadata["estimated_loc"] > 0

    def test_file_group_metadata(self) -> None:
        graph, ids = _build_module_with_leaves("mod", ["feat_a"])
        _pre_encode_folders(graph)
        FileEncoder().encode(graph)

        node = graph.nodes[ids["feat_a"]]
        assert "file_group" in node.metadata


class TestFileEncoderValidation:
    """Tests for FileEncoder.validate()."""

    def test_validate_passes_after_encode(self) -> None:
        graph, _ = _build_module_with_leaves("mod", ["feat_a", "feat_b"])
        _pre_encode_folders(graph)
        enc = FileEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_validate_fails_without_encode(self) -> None:
        """Leaf nodes without file_path should cause validation failure."""
        graph, _ = _build_module_with_leaves("mod", ["feat_a"])
        _pre_encode_folders(graph)
        # Don't run encode
        enc = FileEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert any("missing file_path" in e for e in result.errors)

    def test_validate_warns_on_large_file(self) -> None:
        """High complexity nodes should trigger LOC warning."""
        graph, ids = _build_module_with_leaves("mod", ["complex_feat"])
        _pre_encode_folders(graph)
        # Set high complexity
        graph.nodes[ids["complex_feat"]].metadata["complexity_estimate"] = 100

        enc = FileEncoder(max_loc_per_file=500, complexity_loc_ratio=30)
        enc.encode(graph)
        result = enc.validate(graph)
        # The file has 3000 LOC (100 * 30) which exceeds 500
        assert any("estimated" in w and "LOC" in w for w in result.warnings)


class TestFileEncoderEdgeCases:
    """Edge case tests for FileEncoder."""

    def test_empty_graph(self) -> None:
        graph = RPGGraph()
        enc = FileEncoder()
        result = enc.encode(graph)
        assert result is graph
        vr = enc.validate(graph)
        assert vr.passed is True

    def test_module_only_no_leaves(self) -> None:
        """A graph with only MODULE nodes (no leaves) should pass."""
        graph = RPGGraph()
        mod = RPGNode(
            name="standalone",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(mod)
        _pre_encode_folders(graph)

        enc = FileEncoder()
        enc.encode(graph)
        # Module itself is a "leaf" (no children), should get file_path
        assert mod.file_path is not None

    def test_multiple_modules(self) -> None:
        """Leaves in different modules get files in different folders."""
        graph = RPGGraph()
        ids: dict[str, UUID] = {}

        root = RPGNode(name="root", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
        graph.add_node(root)
        ids["root"] = root.id

        for mod_name, leaf_name in [("mod_a", "feat_a"), ("mod_b", "feat_b")]:
            mod = RPGNode(name=mod_name, level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
            graph.add_node(mod)
            ids[mod_name] = mod.id
            graph.add_edge(_make_hierarchy_edge(root.id, mod.id))

            leaf = _make_node(leaf_name)
            graph.add_node(leaf)
            ids[leaf_name] = leaf.id
            graph.add_edge(_make_hierarchy_edge(mod.id, leaf.id))

        _pre_encode_folders(graph)
        FileEncoder().encode(graph)

        fa = graph.nodes[ids["feat_a"]]
        fb = graph.nodes[ids["feat_b"]]
        assert fa.file_path != fb.file_path
        assert "mod_a" in fa.file_path
        assert "mod_b" in fb.file_path


class TestFileEncoderInPipeline:
    """Test FileEncoder in a pipeline with FolderEncoder."""

    def test_folder_then_file_pipeline(self) -> None:
        from zerorepo.rpg_enrichment.pipeline import RPGBuilder

        graph, ids = _build_module_with_leaves(
            "data_loading", ["load_json", "load_csv"]
        )

        builder = RPGBuilder()
        builder.add_encoder(FolderEncoder())
        builder.add_encoder(FileEncoder())
        result = builder.run(graph)

        assert result is graph
        assert len(builder.steps) == 2
        assert all(s.validation.passed for s in builder.steps)

        for name in ["load_json", "load_csv"]:
            node = graph.nodes[ids[name]]
            assert node.folder_path is not None
            assert node.file_path is not None
            assert node.file_path.startswith(node.folder_path)
