"""Functional tests for BaseClassEncoder (Epic 3.5).

These tests exercise the encoder in realistic multi-module graph scenarios,
verifying end-to-end base class detection, inheritance linking, and pipeline
integration.
"""

from __future__ import annotations

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.baseclass_encoder import BaseClassEncoder
from cobuilder.repomap.rpg_enrichment.pipeline import RPGBuilder


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def _build_ml_models_graph() -> RPGGraph:
    """Build a realistic ML models graph with repeated patterns.

    Structure:
        models/ (MODULE)
          |- models/linear_regression.py (FEATURE)
          |- models/ridge_regression.py  (FEATURE)
          |- models/lasso_regression.py  (FEATURE)
          |- models/random_forest.py     (FEATURE)
          |- models/gradient_boost.py    (FEATURE)

        evaluators/ (MODULE)
          |- evaluators/accuracy_evaluator.py  (FEATURE)
          |- evaluators/f1_evaluator.py        (FEATURE)
          |- evaluators/precision_evaluator.py (FEATURE)
          |- evaluators/recall_evaluator.py    (FEATURE)

        utils/ (MODULE)
          |- utils/config.py   (FEATURE)
          |- utils/logging.py  (FEATURE)
    """
    graph = RPGGraph()

    # --- Modules ---
    models = RPGNode(
        name="models",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="models/",
    )
    evaluators = RPGNode(
        name="evaluators",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="evaluators/",
    )
    utils = RPGNode(
        name="utils",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="utils/",
    )

    for mod in [models, evaluators, utils]:
        graph.add_node(mod)

    # --- Models features (3 regressions + 2 tree-based) ---
    model_names = [
        "linear_regression",
        "ridge_regression",
        "lasso_regression",
        "random_forest",
        "gradient_boost",
    ]
    for name in model_names:
        feat = RPGNode(
            name=name,
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="models/",
            file_path=f"models/{name}.py",
        )
        graph.add_node(feat)
        graph.add_edge(RPGEdge(
            source_id=models.id, target_id=feat.id,
            edge_type=EdgeType.HIERARCHY,
        ))

    # --- Evaluator features (4 evaluators) ---
    eval_names = [
        "accuracy_evaluator",
        "f1_evaluator",
        "precision_evaluator",
        "recall_evaluator",
    ]
    for name in eval_names:
        feat = RPGNode(
            name=name,
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="evaluators/",
            file_path=f"evaluators/{name}.py",
        )
        graph.add_node(feat)
        graph.add_edge(RPGEdge(
            source_id=evaluators.id, target_id=feat.id,
            edge_type=EdgeType.HIERARCHY,
        ))

    # --- Utils features (no pattern) ---
    for name in ["config", "logging"]:
        feat = RPGNode(
            name=name,
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="utils/",
            file_path=f"utils/{name}.py",
        )
        graph.add_node(feat)
        graph.add_edge(RPGEdge(
            source_id=utils.id, target_id=feat.id,
            edge_type=EdgeType.HIERARCHY,
        ))

    return graph


# ===========================================================================
# Functional Tests
# ===========================================================================


class TestBaseClassEncoderFunctional:
    """End-to-end functional tests for BaseClassEncoder."""

    def test_regression_base_class_created(self) -> None:
        """3+ regression features should produce a BaseRegression class."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        base_names = {bc.name for bc in base_classes}
        assert "BaseRegression" in base_names

    def test_evaluator_base_class_created(self) -> None:
        """4 evaluator features should produce a BaseEvaluator class."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        base_names = {bc.name for bc in base_classes}
        assert "BaseEvaluator" in base_names

    def test_utils_module_no_base_class(self) -> None:
        """Utils module with only 2 features should NOT produce a base class."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]
        # All base classes should be from models/ or evaluators/, not utils/
        for bc in base_classes:
            assert bc.folder_path != "utils/"

    def test_inheritance_edges_count(self) -> None:
        """Correct number of INHERITANCE edges created."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        inheritance_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.INHERITANCE
        ]
        # 3 regression + 4 evaluator = 7 inheritance edges minimum
        assert len(inheritance_edges) >= 7

    def test_derived_nodes_have_inherits_from(self) -> None:
        """All derived regression nodes reference the base class."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        regression_features = [
            n for n in graph.nodes.values()
            if "regression" in n.name.lower() and not n.metadata.get("is_abstract")
        ]
        assert len(regression_features) == 3

        for feat in regression_features:
            base_id = feat.metadata.get("inherits_from")
            assert base_id is not None
            bc = graph.nodes[base_id]
            assert bc.name == "BaseRegression"

    def test_validation_passes_on_realistic_graph(self) -> None:
        """After encode, validation should pass with no errors."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is True
        assert result.errors == []

    def test_pipeline_integration(self) -> None:
        """BaseClassEncoder works correctly in an RPGBuilder pipeline."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        builder = RPGBuilder(validate_after_each=True)
        builder.add_encoder(encoder)

        result = builder.run(graph)

        assert result is graph
        assert len(builder.steps) == 1
        step = builder.steps[0]
        assert step.encoder_name == "BaseClassEncoder"
        assert step.validation is not None
        assert step.validation.passed is True

    def test_base_class_has_correct_properties(self) -> None:
        """Base class nodes have proper CLASS interface type and ABC signature."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        for node in graph.nodes.values():
            if node.metadata.get("is_abstract") is True:
                assert node.interface_type == InterfaceType.CLASS
                assert node.node_type == NodeType.FUNCTION_AUGMENTED
                assert "ABC" in (node.signature or "")
                assert node.metadata.get("abstract_methods") is not None
                assert node.metadata.get("derived_count", 0) >= 3

    def test_multiple_modules_independent_bases(self) -> None:
        """Base classes in different modules are independent."""
        graph = _build_ml_models_graph()
        encoder = BaseClassEncoder()
        encoder.encode(graph)

        base_classes = [
            n for n in graph.nodes.values()
            if n.metadata.get("is_abstract") is True
        ]

        # Each base class should be in a different folder or have different suffix
        base_folders = {bc.folder_path for bc in base_classes}
        # models/ and evaluators/ should both have bases
        assert "models/" in base_folders
        assert "evaluators/" in base_folders
