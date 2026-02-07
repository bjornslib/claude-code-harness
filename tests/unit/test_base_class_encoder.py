"""Unit tests for BaseClassEncoder (Epic 3.5).

Tests cover suffix extraction, base class generation, inheritance linking,
abstract method inference, and validation logic.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.baseclass_encoder import (
    BaseClassEncoder,
    _extract_common_suffix,
    _generate_base_class_name,
)
from zerorepo.rpg_enrichment.models import ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(name: str, folder: str) -> RPGNode:
    """Create a MODULE node."""
    return RPGNode(
        name=name,
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path=folder,
    )


def _make_feature(
    name: str,
    folder: str,
    file_path: str | None = None,
) -> RPGNode:
    """Create a FEATURE node."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path=folder,
        file_path=file_path or f"{folder}{name.lower().replace(' ', '_')}.py",
    )


def _module_with_features(
    mod_name: str,
    folder: str,
    feature_names: list[str],
) -> tuple[RPGGraph, RPGNode, list[RPGNode]]:
    """Create a graph with one module and several leaf features.

    Returns (graph, module_node, feature_nodes).
    """
    graph = RPGGraph()
    mod = _make_module(mod_name, folder)
    graph.add_node(mod)

    features = []
    for name in feature_names:
        feat = _make_feature(name, folder)
        graph.add_node(feat)
        graph.add_edge(RPGEdge(
            source_id=mod.id, target_id=feat.id, edge_type=EdgeType.HIERARCHY
        ))
        features.append(feat)

    return graph, mod, features


# ===========================================================================
# Test 1: _extract_common_suffix helper
# ===========================================================================


class TestExtractCommonSuffix:
    def test_regression_suffix(self) -> None:
        names = ["linear_regression", "ridge_regression", "lasso_regression"]
        assert _extract_common_suffix(names) == "regression"

    def test_multi_word_suffix(self) -> None:
        names = ["fast_data_loader", "lazy_data_loader", "batch_data_loader"]
        assert _extract_common_suffix(names) == "data_loader"

    def test_no_common_suffix(self) -> None:
        names = ["alpha", "bravo", "charlie"]
        assert _extract_common_suffix(names) is None

    def test_single_name_returns_none(self) -> None:
        assert _extract_common_suffix(["only_one"]) is None

    def test_empty_list_returns_none(self) -> None:
        assert _extract_common_suffix([]) is None

    def test_hyphen_treated_as_underscore(self) -> None:
        names = ["fast-processor", "slow-processor"]
        assert _extract_common_suffix(names) == "processor"


# ===========================================================================
# Test 2: _generate_base_class_name helper
# ===========================================================================


class TestGenerateBaseClassName:
    def test_simple_suffix(self) -> None:
        assert _generate_base_class_name("regression") == "BaseRegression"

    def test_multi_word_suffix(self) -> None:
        assert _generate_base_class_name("data_loader") == "BaseDataLoader"

    def test_single_char_parts_filtered(self) -> None:
        # Parts that are empty get filtered by the capitalize logic
        assert _generate_base_class_name("x") == "BaseX"


# ===========================================================================
# Test 3: Empty graph passes through
# ===========================================================================


class TestEmptyGraph:
    def test_empty_graph_returns_same_instance(self) -> None:
        encoder = BaseClassEncoder()
        graph = RPGGraph()
        result = encoder.encode(graph)
        assert result is graph
        assert graph.node_count == 0


# ===========================================================================
# Test 4: Not enough features -> no base class created
# ===========================================================================


class TestInsufficientFeatures:
    def test_two_features_no_base_class(self) -> None:
        """Default threshold is 3; 2 features should NOT trigger creation."""
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression"],
        )

        encoder = BaseClassEncoder()
        node_count_before = graph.node_count
        encoder.encode(graph)

        # No new nodes should have been added
        assert graph.node_count == node_count_before

    def test_three_unrelated_features_no_base_class(self) -> None:
        """3 features without a common suffix -> no base class."""
        graph, mod, features = _module_with_features(
            "utils", "utils/",
            ["alpha", "bravo", "charlie"],
        )

        encoder = BaseClassEncoder()
        node_count_before = graph.node_count
        encoder.encode(graph)

        assert graph.node_count == node_count_before


# ===========================================================================
# Test 5: Base class created for 3+ features with common suffix
# ===========================================================================


class TestBaseClassCreation:
    def test_three_regression_features_create_base(self) -> None:
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        # A base class node should have been added
        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) == 1
        bc = base_classes[0]
        assert bc.name == "BaseRegression"
        assert bc.interface_type == InterfaceType.CLASS
        assert bc.signature == "class BaseRegression(ABC):"
        assert bc.metadata.get("derived_count") == 3

    def test_base_class_linked_to_module_via_hierarchy(self) -> None:
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        # Find the base class
        bc = next(
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        )

        # HIERARCHY edge from module to base class
        hierarchy_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.HIERARCHY
            and e.source_id == mod.id
            and e.target_id == bc.id
        ]
        assert len(hierarchy_edges) == 1


# ===========================================================================
# Test 6: Inheritance edges and metadata on derived nodes
# ===========================================================================


class TestInheritanceLinks:
    def test_derived_nodes_get_inherits_from(self) -> None:
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        bc = next(
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        )

        for feat in features:
            assert feat.metadata.get("inherits_from") == bc.id

    def test_inheritance_edges_created(self) -> None:
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        bc = next(
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        )

        inheritance_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.INHERITANCE
            and e.source_id == bc.id
        ]
        assert len(inheritance_edges) == 3
        derived_ids = {e.target_id for e in inheritance_edges}
        assert derived_ids == {f.id for f in features}


# ===========================================================================
# Test 7: Abstract method inference
# ===========================================================================


class TestAbstractMethodInference:
    def test_common_words_become_methods(self) -> None:
        """Words common to most derived feature names become abstract methods."""
        graph, mod, features = _module_with_features(
            "models", "models/",
            [
                "train_linear_model",
                "train_ridge_model",
                "train_lasso_model",
            ],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        bc = next(
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        )
        methods = bc.metadata.get("abstract_methods", [])
        # "train" and "model" are common to all three
        assert "train" in methods or "model" in methods

    def test_common_suffix_word_as_method(self) -> None:
        """When 'processor' is common to all, it appears in abstract_methods."""
        graph, mod, features = _module_with_features(
            "x", "x/",
            ["a_processor", "b_processor", "c_processor"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        bc = next(
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        )
        methods = bc.metadata.get("abstract_methods", [])
        assert "processor" in methods


# ===========================================================================
# Test 8: Validate method
# ===========================================================================


class TestValidateMethod:
    def test_validate_passes_after_encode(self) -> None:
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is True

    def test_validate_on_empty_graph(self) -> None:
        encoder = BaseClassEncoder()
        result = encoder.validate(RPGGraph())
        assert result.passed is True

    def test_validate_warns_missing_abstract_methods(self) -> None:
        """A base class with no abstract_methods gets a warning."""
        graph = RPGGraph()
        bc = RPGNode(
            name="EmptyBase",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.CLASS,
            signature="class EmptyBase(ABC):",
            folder_path="x/",
            file_path="x/base.py",
            metadata={"is_abstract": True, "abstract_methods": []},
        )
        graph.add_node(bc)

        encoder = BaseClassEncoder()
        result = encoder.validate(graph)

        assert result.passed is True  # warnings don't fail
        assert any("no abstract_methods" in w for w in result.warnings)

    def test_validate_warns_no_derived_nodes(self) -> None:
        """A base class with no derived nodes gets a warning."""
        graph = RPGGraph()
        bc = RPGNode(
            name="LonelyBase",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.CLASS,
            signature="class LonelyBase(ABC):",
            folder_path="y/",
            file_path="y/base.py",
            metadata={"is_abstract": True, "abstract_methods": ["run"]},
        )
        graph.add_node(bc)

        encoder = BaseClassEncoder()
        result = encoder.validate(graph)

        assert any("no derived nodes" in w for w in result.warnings)

    def test_validate_fails_invalid_inherits_from(self) -> None:
        """A node referencing a non-existent base class causes failure."""
        from uuid import uuid4

        graph = RPGGraph()
        node = RPGNode(
            name="Orphan",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="z/",
            file_path="z/orphan.py",
            metadata={"inherits_from": uuid4()},  # non-existent
        )
        graph.add_node(node)

        encoder = BaseClassEncoder()
        result = encoder.validate(graph)

        assert result.passed is False
        assert any("not found in graph" in e for e in result.errors)


# ===========================================================================
# Test 9: Custom min_features_for_abstraction threshold
# ===========================================================================


class TestCustomThreshold:
    def test_lower_threshold_creates_base(self) -> None:
        """With min_features=2, a pair of features triggers base class creation."""
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression"],
        )

        encoder = BaseClassEncoder(min_features_for_abstraction=2)
        encoder.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        assert len(base_classes) == 1

    def test_higher_threshold_prevents_creation(self) -> None:
        """With min_features=5, 3 features don't trigger base class creation."""
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder(min_features_for_abstraction=5)
        node_count_before = graph.node_count
        encoder.encode(graph)

        assert graph.node_count == node_count_before


# ===========================================================================
# Test 10: Encoder name property
# ===========================================================================


class TestEncoderName:
    def test_name_is_class_name(self) -> None:
        encoder = BaseClassEncoder()
        assert encoder.name == "BaseClassEncoder"


# ===========================================================================
# Test 11: Base class file path
# ===========================================================================


class TestBaseClassFilePath:
    def test_file_path_under_module_folder(self) -> None:
        graph, mod, features = _module_with_features(
            "models", "models/",
            ["linear_regression", "ridge_regression", "lasso_regression"],
        )

        encoder = BaseClassEncoder()
        encoder.encode(graph)

        bc = next(
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        )
        assert bc.file_path == "models/base.py"
        assert bc.folder_path == "models/"


# ===========================================================================
# Test 12: group_by_suffix static method
# ===========================================================================


class TestGroupBySuffix:
    def test_groups_by_common_suffix(self) -> None:
        from uuid import uuid4

        id1, id2, id3, id4 = uuid4(), uuid4(), uuid4(), uuid4()
        leaf_names = {
            id1: "linear_regression",
            id2: "ridge_regression",
            id3: "lasso_regression",
            id4: "random_forest",
        }

        groups = BaseClassEncoder._group_by_suffix(leaf_names)

        assert "regression" in groups
        assert set(groups["regression"]) == {id1, id2, id3}
