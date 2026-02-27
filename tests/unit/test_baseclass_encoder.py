"""Tests for BaseClassEncoder – Epic 3.5 base class abstraction."""

from __future__ import annotations

from uuid import UUID

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.baseclass_encoder import (
    BaseClassEncoder,
    _extract_common_suffix,
    _generate_base_class_name,
)
from cobuilder.repomap.rpg_enrichment.folder_encoder import FolderEncoder


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


def _build_regression_graph() -> tuple[RPGGraph, dict[str, UUID]]:
    """Build a graph with 4 similar regression features under one module."""
    graph = RPGGraph()
    ids: dict[str, UUID] = {}

    mod = RPGNode(
        name="algorithms",
        level=NodeLevel.MODULE,
        node_type=NodeType.FOLDER_AUGMENTED,
    )
    graph.add_node(mod)
    ids["module"] = mod.id

    for name in [
        "linear_regression",
        "ridge_regression",
        "lasso_regression",
        "elasticnet_regression",
    ]:
        leaf = _make_node(name)
        graph.add_node(leaf)
        ids[name] = leaf.id
        graph.add_edge(_h_edge(mod.id, leaf.id))

    FolderEncoder().encode(graph)
    return graph, ids


# ===========================================================================
# Test: Utility functions
# ===========================================================================


class TestExtractCommonSuffix:
    def test_regression_suffix(self) -> None:
        result = _extract_common_suffix([
            "linear_regression",
            "ridge_regression",
            "lasso_regression",
        ])
        assert result == "regression"

    def test_model_suffix(self) -> None:
        result = _extract_common_suffix(["tree_model", "forest_model"])
        assert result == "model"

    def test_multi_word_suffix(self) -> None:
        result = _extract_common_suffix([
            "fast_data_loader",
            "slow_data_loader",
        ])
        assert result == "data_loader"

    def test_no_common_suffix(self) -> None:
        result = _extract_common_suffix(["alpha", "beta", "gamma"])
        assert result is None

    def test_single_name(self) -> None:
        assert _extract_common_suffix(["only_one"]) is None

    def test_empty_list(self) -> None:
        assert _extract_common_suffix([]) is None


class TestGenerateBaseClassName:
    def test_single_word(self) -> None:
        assert _generate_base_class_name("regression") == "BaseRegression"

    def test_multi_word(self) -> None:
        assert _generate_base_class_name("data_loader") == "BaseDataLoader"

    def test_lowercase(self) -> None:
        assert _generate_base_class_name("model") == "BaseModel"


# ===========================================================================
# Test: BaseClassEncoder basic encoding
# ===========================================================================


class TestBaseClassEncoderBasic:
    def test_creates_base_class_for_similar_features(self) -> None:
        """4 regression features → creates BaseRegression."""
        graph, ids = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        # Find base class nodes
        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) >= 1

        bc = base_classes[0]
        assert "Base" in bc.name
        assert bc.metadata["is_abstract"] is True
        assert isinstance(bc.metadata.get("abstract_methods"), list)

    def test_derived_features_have_inherits_from(self) -> None:
        """Derived features should reference the base class."""
        graph, ids = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        # At least some derived features should have inherits_from
        derived = [
            n for n in graph.nodes.values()
            if n.metadata.get("inherits_from") is not None
        ]
        assert len(derived) >= 3

    def test_inheritance_edges_created(self) -> None:
        """INHERITANCE edges should link base to derived."""
        graph, ids = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        inh_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.INHERITANCE
        ]
        assert len(inh_edges) >= 3

    def test_base_class_has_file_path(self) -> None:
        """Base class should be in module/base.py."""
        graph, ids = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) >= 1
        bc = base_classes[0]
        assert bc.file_path is not None
        assert bc.file_path.endswith("base.py")

    def test_base_class_is_class_type(self) -> None:
        """Base class node should have interface_type=CLASS."""
        graph, ids = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert base_classes[0].interface_type == InterfaceType.CLASS


class TestBaseClassEncoderThreshold:
    def test_no_base_class_below_threshold(self) -> None:
        """If fewer than min_features similar, no base class created."""
        graph = RPGGraph()
        mod = RPGNode(name="mod", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
        graph.add_node(mod)
        # Only 2 similar features (threshold is 3)
        for name in ["linear_regression", "ridge_regression"]:
            leaf = _make_node(name)
            graph.add_node(leaf)
            graph.add_edge(_h_edge(mod.id, leaf.id))

        FolderEncoder().encode(graph)
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) == 0

    def test_high_threshold_skips_small_groups(self) -> None:
        """Raising threshold prevents base class creation."""
        graph, ids = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=10)
        enc.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) == 0


# ===========================================================================
# Test: Validation
# ===========================================================================


class TestBaseClassEncoderValidation:
    def test_validate_passes_after_encode(self) -> None:
        graph, _ = _build_regression_graph()
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_validate_passes_without_encode(self) -> None:
        """No base classes, no errors."""
        graph, _ = _build_regression_graph()
        enc = BaseClassEncoder()
        result = enc.validate(graph)
        assert result.passed is True

    def test_validate_catches_dangling_inherits_from(self) -> None:
        """inherits_from pointing to non-existent node is an error."""
        graph = RPGGraph()
        from uuid import uuid4
        fake_id = uuid4()
        node = _make_node("derived")
        node.metadata["inherits_from"] = fake_id
        graph.add_node(node)

        enc = BaseClassEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert any("not found" in e for e in result.errors)


# ===========================================================================
# Test: Edge cases
# ===========================================================================


class TestBaseClassEncoderEdgeCases:
    def test_empty_graph(self) -> None:
        graph = RPGGraph()
        enc = BaseClassEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_no_similar_features(self) -> None:
        """Completely different feature names produce no base classes."""
        graph = RPGGraph()
        mod = RPGNode(name="mod", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
        graph.add_node(mod)
        for name in ["alpha", "beta", "gamma", "delta"]:
            leaf = _make_node(name)
            graph.add_node(leaf)
            graph.add_edge(_h_edge(mod.id, leaf.id))

        FolderEncoder().encode(graph)
        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) == 0

    def test_features_without_module(self) -> None:
        """Orphan features (no module parent) should not crash."""
        graph = RPGGraph()
        for name in ["orphan_regression", "lost_regression", "stray_regression"]:
            leaf = _make_node(name)
            graph.add_node(leaf)

        enc = BaseClassEncoder(min_features_for_abstraction=3)
        enc.encode(graph)
        # Should still detect pattern and create base class under None module
        result = enc.validate(graph)
        assert result.passed is True
