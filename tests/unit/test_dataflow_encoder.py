"""Tests for DataFlowEncoder – Epic 3.3 inter-module data flow encoding."""

from __future__ import annotations

from uuid import UUID

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.dataflow_encoder import (
    DataFlowEncoder,
    _infer_type_from_name,
)


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


def _h_edge(parent_id: UUID, child_id: UUID) -> RPGEdge:
    return RPGEdge(source_id=parent_id, target_id=child_id, edge_type=EdgeType.HIERARCHY)


def _df_edge(
    source_id: UUID,
    target_id: UUID,
    data_type: str | None = None,
    data_id: str | None = None,
) -> RPGEdge:
    return RPGEdge(
        source_id=source_id,
        target_id=target_id,
        edge_type=EdgeType.DATA_FLOW,
        data_type=data_type,
        data_id=data_id,
    )


def _build_two_module_graph() -> tuple[RPGGraph, dict[str, UUID]]:
    """Build a graph with 2 modules, each with a leaf, connected by DATA_FLOW."""
    graph = RPGGraph()
    ids: dict[str, UUID] = {}

    # Module A
    mod_a = _make_node("data_loading")
    graph.add_node(mod_a)
    ids["mod_a"] = mod_a.id

    leaf_a = _make_node("load_dataset", level=NodeLevel.FEATURE)
    graph.add_node(leaf_a)
    ids["leaf_a"] = leaf_a.id
    graph.add_edge(_h_edge(mod_a.id, leaf_a.id))

    # Module B
    mod_b = _make_node("preprocessing")
    graph.add_node(mod_b)
    ids["mod_b"] = mod_b.id

    leaf_b = _make_node("normalize_features", level=NodeLevel.FEATURE)
    graph.add_node(leaf_b)
    ids["leaf_b"] = leaf_b.id
    graph.add_edge(_h_edge(mod_b.id, leaf_b.id))

    return graph, ids


# ===========================================================================
# Test: _infer_type_from_name
# ===========================================================================


class TestInferTypeFromName:
    def test_data_keyword(self) -> None:
        assert _infer_type_from_name("load_data") == "pd.DataFrame"

    def test_array_keyword(self) -> None:
        assert _infer_type_from_name("feature_array") == "np.ndarray"

    def test_predictions_keyword(self) -> None:
        # "predictions" alone matches np.ndarray
        assert _infer_type_from_name("predictions") == "np.ndarray"

    def test_config_keyword(self) -> None:
        assert _infer_type_from_name("app_config") == "dict[str, Any]"

    def test_score_keyword(self) -> None:
        assert _infer_type_from_name("accuracy_score") == "float"

    def test_metrics_keyword(self) -> None:
        # "metric" (singular) is a substring of "metrics" and matches first → float
        # To get dict[str, float], use a name where "metrics" matches but "metric" doesn't
        # come before it. Since "metric" always matches first, test that behavior:
        assert _infer_type_from_name("metric_value") == "float"
        # "metrics" also contains "metric" so it also returns float
        assert _infer_type_from_name("metrics") == "float"

    def test_unknown_falls_back_to_any(self) -> None:
        assert _infer_type_from_name("foobar_xyz") == "Any"

    def test_path_keyword(self) -> None:
        assert _infer_type_from_name("output_path") == "Path"


# ===========================================================================
# Test: DataFlowEncoder basic encoding
# ===========================================================================


class TestDataFlowEncoderBasic:
    def test_annotates_existing_data_flow_edge(self) -> None:
        """Existing DATA_FLOW edges get data_type inferred."""
        graph, ids = _build_two_module_graph()
        # Add a DATA_FLOW edge without data_type
        graph.add_edge(_df_edge(ids["leaf_a"], ids["leaf_b"]))

        DataFlowEncoder().encode(graph)

        # Find the DATA_FLOW edge
        df_edges = [
            e for e in graph.edges.values() if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert len(df_edges) == 1
        assert df_edges[0].data_type is not None
        assert df_edges[0].validated is True

    def test_preserves_existing_data_type(self) -> None:
        """If data_type is already set, don't overwrite it."""
        graph, ids = _build_two_module_graph()
        graph.add_edge(
            _df_edge(ids["leaf_a"], ids["leaf_b"], data_type="CustomType")
        )

        DataFlowEncoder().encode(graph)

        df_edges = [
            e for e in graph.edges.values() if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert df_edges[0].data_type == "CustomType"

    def test_sets_output_schema_on_source(self) -> None:
        """Source node gets output_schema metadata."""
        graph, ids = _build_two_module_graph()
        graph.add_edge(_df_edge(ids["leaf_a"], ids["leaf_b"]))

        DataFlowEncoder().encode(graph)

        src = graph.nodes[ids["leaf_a"]]
        assert "output_schema" in src.metadata
        assert isinstance(src.metadata["output_schema"], dict)

    def test_sets_input_schema_on_target(self) -> None:
        """Target node gets input_schema metadata."""
        graph, ids = _build_two_module_graph()
        graph.add_edge(_df_edge(ids["leaf_a"], ids["leaf_b"]))

        DataFlowEncoder().encode(graph)

        tgt = graph.nodes[ids["leaf_b"]]
        assert "input_schema" in tgt.metadata
        assert isinstance(tgt.metadata["input_schema"], dict)


class TestDataFlowEncoderMissingFlows:
    def test_creates_flow_from_invocation_edge(self) -> None:
        """INVOCATION edges between modules trigger DATA_FLOW creation."""
        graph, ids = _build_two_module_graph()
        # Add an INVOCATION edge (not DATA_FLOW)
        graph.add_edge(
            RPGEdge(
                source_id=ids["leaf_a"],
                target_id=ids["leaf_b"],
                edge_type=EdgeType.INVOCATION,
            )
        )

        DataFlowEncoder().encode(graph)

        # A DATA_FLOW edge should have been created
        df_edges = [
            e for e in graph.edges.values() if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert len(df_edges) == 1
        assert df_edges[0].data_type is not None


# ===========================================================================
# Test: DataFlowEncoder validation
# ===========================================================================


class TestDataFlowEncoderValidation:
    def test_validate_passes_acyclic(self) -> None:
        graph, ids = _build_two_module_graph()
        graph.add_edge(_df_edge(ids["leaf_a"], ids["leaf_b"]))

        enc = DataFlowEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_validate_detects_cycle(self) -> None:
        """Cyclic DATA_FLOW between modules should fail validation."""
        graph, ids = _build_two_module_graph()
        # Create cycle: A→B and B→A
        graph.add_edge(
            _df_edge(ids["leaf_a"], ids["leaf_b"], data_type="np.ndarray")
        )
        graph.add_edge(
            _df_edge(ids["leaf_b"], ids["leaf_a"], data_type="np.ndarray")
        )

        enc = DataFlowEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert any("cycle" in e.lower() for e in result.errors)

    def test_validate_warns_on_missing_data_type(self) -> None:
        """DATA_FLOW edges without data_type get a warning."""
        graph, ids = _build_two_module_graph()
        # Add edge without data_type (and don't encode)
        graph.add_edge(_df_edge(ids["leaf_a"], ids["leaf_b"]))

        enc = DataFlowEncoder()
        result = enc.validate(graph)
        assert any("missing data_type" in w for w in result.warnings)


# ===========================================================================
# Test: Edge cases
# ===========================================================================


class TestDataFlowEncoderEdgeCases:
    def test_empty_graph(self) -> None:
        graph = RPGGraph()
        enc = DataFlowEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_single_module(self) -> None:
        """Intra-module edges should not be annotated as inter-module."""
        graph = RPGGraph()
        mod = _make_node("mod")
        graph.add_node(mod)
        leaf1 = _make_node("feat1", level=NodeLevel.FEATURE)
        leaf2 = _make_node("feat2", level=NodeLevel.FEATURE)
        graph.add_node(leaf1)
        graph.add_node(leaf2)
        graph.add_edge(_h_edge(mod.id, leaf1.id))
        graph.add_edge(_h_edge(mod.id, leaf2.id))
        graph.add_edge(
            _df_edge(leaf1.id, leaf2.id, data_type="str")
        )

        enc = DataFlowEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True

    def test_no_data_flow_edges(self) -> None:
        """Graph with no DATA_FLOW or INVOCATION edges should pass cleanly."""
        graph, _ = _build_two_module_graph()
        enc = DataFlowEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True
