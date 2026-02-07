"""Unit tests for DataFlowEncoder (Epic 3.3).

Tests cover type inference, schema annotation, inter-module flow creation,
cycle detection, and validation logic.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.dataflow_encoder import (
    DataFlowEncoder,
    _infer_type_from_name,
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


def _two_module_graph() -> tuple[RPGGraph, RPGNode, RPGNode, RPGNode, RPGNode]:
    """Build a graph with two modules, each with one feature.

    Structure:
        mod_a/ (MODULE)
          |- mod_a/feat_a.py (FEATURE: Feature A)
        mod_b/ (MODULE)
          |- mod_b/feat_b.py (FEATURE: Feature B)

    Returns (graph, mod_a, mod_b, feat_a, feat_b).
    """
    graph = RPGGraph()

    mod_a = _make_module("mod_a", "mod_a/")
    mod_b = _make_module("mod_b", "mod_b/")
    feat_a = _make_feature("Feature A", "mod_a/")
    feat_b = _make_feature("Feature B", "mod_b/")

    for n in [mod_a, mod_b, feat_a, feat_b]:
        graph.add_node(n)

    # HIERARCHY edges
    graph.add_edge(RPGEdge(
        source_id=mod_a.id, target_id=feat_a.id, edge_type=EdgeType.HIERARCHY
    ))
    graph.add_edge(RPGEdge(
        source_id=mod_b.id, target_id=feat_b.id, edge_type=EdgeType.HIERARCHY
    ))

    return graph, mod_a, mod_b, feat_a, feat_b


# ===========================================================================
# Test 1: _infer_type_from_name helper
# ===========================================================================


class TestInferTypeFromName:
    def test_data_keyword(self) -> None:
        assert _infer_type_from_name("training_data") == "pd.DataFrame"

    def test_array_keyword(self) -> None:
        assert _infer_type_from_name("input_array") == "np.ndarray"

    def test_config_keyword(self) -> None:
        assert _infer_type_from_name("app_config") == "dict[str, Any]"

    def test_score_keyword(self) -> None:
        assert _infer_type_from_name("accuracy_score") == "float"

    def test_text_keyword(self) -> None:
        assert _infer_type_from_name("raw_text") == "str"

    def test_path_keyword(self) -> None:
        assert _infer_type_from_name("output_path") == "Path"

    def test_no_match_returns_any(self) -> None:
        assert _infer_type_from_name("xyz_unknown") == "Any"

    def test_case_insensitive(self) -> None:
        assert _infer_type_from_name("MATRIX_Input") == "np.ndarray"

    def test_metric_before_metrics(self) -> None:
        """'metric' matches before 'metrics' due to dict ordering."""
        assert _infer_type_from_name("metric") == "float"


# ===========================================================================
# Test 2: Empty graph passes through
# ===========================================================================


class TestEmptyGraph:
    def test_empty_graph_returns_same_instance(self) -> None:
        encoder = DataFlowEncoder()
        graph = RPGGraph()
        result = encoder.encode(graph)
        assert result is graph
        assert graph.node_count == 0


# ===========================================================================
# Test 3: Existing DATA_FLOW edge gets type inferred
# ===========================================================================


class TestExistingDataFlowEdge:
    def test_type_inferred_on_untyped_edge(self) -> None:
        graph, mod_a, mod_b, feat_a, feat_b = _two_module_graph()
        # Rename feat_a so inference picks up a known keyword
        feat_a.name = "Training Data Loader"

        edge = RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="training_data",
        )
        graph.add_edge(edge)

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        # data_type should have been inferred from "Training Data Loader"
        assert edge.data_type is not None
        assert "DataFrame" in edge.data_type or edge.data_type == "pd.DataFrame"
        assert edge.validated is True

    def test_already_typed_edge_not_overwritten(self) -> None:
        graph, mod_a, mod_b, feat_a, feat_b = _two_module_graph()

        edge = RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="custom",
            data_type="CustomType",
        )
        graph.add_edge(edge)

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        # Should remain unchanged
        assert edge.data_type == "CustomType"

    def test_intra_module_edge_not_annotated(self) -> None:
        """DATA_FLOW edges within the same module are skipped."""
        graph = RPGGraph()
        mod = _make_module("mod", "mod/")
        f1 = _make_feature("Data Source", "mod/")
        f2 = _make_feature("Data Sink", "mod/")
        for n in [mod, f1, f2]:
            graph.add_node(n)
        graph.add_edge(RPGEdge(
            source_id=mod.id, target_id=f1.id, edge_type=EdgeType.HIERARCHY
        ))
        graph.add_edge(RPGEdge(
            source_id=mod.id, target_id=f2.id, edge_type=EdgeType.HIERARCHY
        ))

        edge = RPGEdge(
            source_id=f1.id,
            target_id=f2.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="internal",
        )
        graph.add_edge(edge)

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        # Intra-module => not annotated
        assert edge.data_type is None
        assert edge.validated is False


# ===========================================================================
# Test 4: Schema annotation on source/target nodes
# ===========================================================================


class TestSchemaAnnotation:
    def test_output_schema_set_on_source_node(self) -> None:
        graph, _, _, feat_a, feat_b = _two_module_graph()

        edge = RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="result",
            data_type="dict[str, Any]",
        )
        graph.add_edge(edge)

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        assert "output_schema" in feat_a.metadata
        assert feat_a.metadata["output_schema"]["result"] == "dict[str, Any]"

    def test_input_schema_set_on_target_node(self) -> None:
        graph, _, _, feat_a, feat_b = _two_module_graph()

        edge = RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="result",
            data_type="dict[str, Any]",
        )
        graph.add_edge(edge)

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        assert "input_schema" in feat_b.metadata
        assert feat_b.metadata["input_schema"]["result"] == "dict[str, Any]"


# ===========================================================================
# Test 5: Missing DATA_FLOW edges created from INVOCATION/ORDERING
# ===========================================================================


class TestMissingFlowCreation:
    def test_invocation_edge_creates_data_flow(self) -> None:
        graph, mod_a, mod_b, feat_a, feat_b = _two_module_graph()

        # Add an INVOCATION edge between features in different modules
        graph.add_edge(RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.INVOCATION,
        ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        # A DATA_FLOW edge should have been created
        data_flow_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert len(data_flow_edges) >= 1
        df = data_flow_edges[0]
        assert df.data_type is not None

    def test_ordering_edge_creates_data_flow(self) -> None:
        graph, mod_a, mod_b, feat_a, feat_b = _two_module_graph()

        graph.add_edge(RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.ORDERING,
        ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        data_flow_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert len(data_flow_edges) >= 1

    def test_no_duplicate_data_flow_when_already_exists(self) -> None:
        """If a DATA_FLOW already exists between modules, don't add another."""
        graph, mod_a, mod_b, feat_a, feat_b = _two_module_graph()

        # Existing DATA_FLOW
        graph.add_edge(RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="existing",
            data_type="str",
        ))
        # INVOCATION edge that would also trigger flow creation
        graph.add_edge(RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.INVOCATION,
        ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        data_flow_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        # Should still be only 1 (the original)
        assert len(data_flow_edges) == 1


# ===========================================================================
# Test 6: Validate method
# ===========================================================================


class TestValidateMethod:
    def test_validate_passes_after_encode(self) -> None:
        graph, _, _, feat_a, feat_b = _two_module_graph()
        graph.add_edge(RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="x",
            data_type="str",
        ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)
        result = encoder.validate(graph)
        assert result.passed is True

    def test_validate_warns_on_untyped_data_flow(self) -> None:
        """DATA_FLOW edges missing data_type produce a warning."""
        graph = RPGGraph()
        # Two nodes in different modules without type
        mod_a = _make_module("a", "a/")
        mod_b = _make_module("b", "b/")
        fa = _make_feature("f_a", "a/")
        fb = _make_feature("f_b", "b/")
        for n in [mod_a, mod_b, fa, fb]:
            graph.add_node(n)
        graph.add_edge(RPGEdge(
            source_id=mod_a.id, target_id=fa.id, edge_type=EdgeType.HIERARCHY
        ))
        graph.add_edge(RPGEdge(
            source_id=mod_b.id, target_id=fb.id, edge_type=EdgeType.HIERARCHY
        ))

        # Intra-module DATA_FLOW edge without data_type
        # Actually we need it to NOT be annotated by encode,
        # so just add a DATA_FLOW inside the same module (won't be touched)
        graph.add_edge(RPGEdge(
            source_id=fa.id,
            target_id=fb.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="untyped",
        ))

        encoder = DataFlowEncoder()
        # Don't call encode - just validate the raw state
        result = encoder.validate(graph)

        assert result.passed is True  # warnings don't fail
        assert any("missing data_type" in w for w in result.warnings)

    def test_validate_on_empty_graph(self) -> None:
        encoder = DataFlowEncoder()
        result = encoder.validate(RPGGraph())
        assert result.passed is True


# ===========================================================================
# Test 7: Cycle detection
# ===========================================================================


class TestCycleDetection:
    def test_acyclic_graph_passes(self) -> None:
        graph, _, _, feat_a, feat_b = _two_module_graph()
        graph.add_edge(RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="x",
            data_type="str",
        ))

        encoder = DataFlowEncoder()
        result = encoder.validate(graph)
        assert result.passed is True

    def test_cyclic_graph_fails_validation(self) -> None:
        """A cycle between modules in DATA_FLOW graph causes validation failure."""
        graph = RPGGraph()
        mod_a = _make_module("mod_a", "mod_a/")
        mod_b = _make_module("mod_b", "mod_b/")
        mod_c = _make_module("mod_c", "mod_c/")
        fa = _make_feature("FA", "mod_a/")
        fb = _make_feature("FB", "mod_b/")
        fc = _make_feature("FC", "mod_c/")

        for n in [mod_a, mod_b, mod_c, fa, fb, fc]:
            graph.add_node(n)

        # HIERARCHY
        graph.add_edge(RPGEdge(
            source_id=mod_a.id, target_id=fa.id, edge_type=EdgeType.HIERARCHY
        ))
        graph.add_edge(RPGEdge(
            source_id=mod_b.id, target_id=fb.id, edge_type=EdgeType.HIERARCHY
        ))
        graph.add_edge(RPGEdge(
            source_id=mod_c.id, target_id=fc.id, edge_type=EdgeType.HIERARCHY
        ))

        # DATA_FLOW cycle: A -> B -> C -> A
        graph.add_edge(RPGEdge(
            source_id=fa.id, target_id=fb.id,
            edge_type=EdgeType.DATA_FLOW, data_id="x", data_type="int",
        ))
        graph.add_edge(RPGEdge(
            source_id=fb.id, target_id=fc.id,
            edge_type=EdgeType.DATA_FLOW, data_id="y", data_type="int",
        ))
        graph.add_edge(RPGEdge(
            source_id=fc.id, target_id=fa.id,
            edge_type=EdgeType.DATA_FLOW, data_id="z", data_type="int",
        ))

        encoder = DataFlowEncoder()
        result = encoder.validate(graph)
        assert result.passed is False
        assert any("cycle" in e.lower() for e in result.errors)


# ===========================================================================
# Test 8: Encoder name property
# ===========================================================================


class TestEncoderName:
    def test_name_is_class_name(self) -> None:
        encoder = DataFlowEncoder()
        assert encoder.name == "DataFlowEncoder"


# ===========================================================================
# Test 9: Module map building
# ===========================================================================


class TestBuildModuleMap:
    def test_features_mapped_to_modules(self) -> None:
        graph, mod_a, mod_b, feat_a, feat_b = _two_module_graph()
        encoder = DataFlowEncoder()
        module_map = encoder._build_module_map(graph)

        assert module_map[feat_a.id] == mod_a.id
        assert module_map[feat_b.id] == mod_b.id
        assert module_map[mod_a.id] == mod_a.id
        assert module_map[mod_b.id] == mod_b.id

    def test_orphan_feature_not_mapped(self) -> None:
        """A feature without a MODULE ancestor has no module mapping."""
        graph = RPGGraph()
        orphan = _make_feature("Orphan", "orphan/")
        graph.add_node(orphan)

        encoder = DataFlowEncoder()
        module_map = encoder._build_module_map(graph)
        assert orphan.id not in module_map


# ===========================================================================
# Test 10: has_cycle static method
# ===========================================================================


class TestHasCycle:
    def test_empty_graph_no_cycle(self) -> None:
        assert DataFlowEncoder._has_cycle({}) is False

    def test_single_edge_no_cycle(self) -> None:
        from uuid import uuid4
        a, b = uuid4(), uuid4()
        assert DataFlowEncoder._has_cycle({a: {b}}) is False

    def test_two_node_cycle(self) -> None:
        from uuid import uuid4
        a, b = uuid4(), uuid4()
        assert DataFlowEncoder._has_cycle({a: {b}, b: {a}}) is True

    def test_three_node_cycle(self) -> None:
        from uuid import uuid4
        a, b, c = uuid4(), uuid4(), uuid4()
        assert DataFlowEncoder._has_cycle({a: {b}, b: {c}, c: {a}}) is True
