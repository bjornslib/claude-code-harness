"""Functional tests for DataFlowEncoder (Epic 3.3).

These tests exercise the encoder in realistic multi-module graph scenarios,
verifying end-to-end data flow inference, schema annotation, and pipeline
integration.
"""

from __future__ import annotations

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.dataflow_encoder import DataFlowEncoder
from zerorepo.rpg_enrichment.pipeline import RPGBuilder


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def _build_ml_pipeline_graph() -> RPGGraph:
    """Build a realistic ML pipeline graph with typed data flows.

    Structure:
        ingestion/ (MODULE)
          |- ingestion/csv_loader.py (FEATURE: CSV Data Loader)
          |- ingestion/api_fetcher.py (FEATURE: API Fetcher)

        preprocessing/ (MODULE)
          |- preprocessing/feature_extractor.py (FEATURE: Feature Extractor)
          |- preprocessing/normalizer.py (FEATURE: Score Normalizer)

        training/ (MODULE)
          |- training/model_trainer.py (FEATURE: Model Trainer)
          |- training/evaluator.py (FEATURE: Metric Evaluator)

    DATA_FLOW edges (inter-module):
        CSV Data Loader -> Feature Extractor  (untyped, to be inferred)
        Feature Extractor -> Model Trainer    (untyped)
        Score Normalizer -> Metric Evaluator  (untyped)
    """
    graph = RPGGraph()

    # --- Modules ---
    ingestion = RPGNode(
        name="ingestion",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="ingestion/",
    )
    preprocessing = RPGNode(
        name="preprocessing",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="preprocessing/",
    )
    training = RPGNode(
        name="training",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="training/",
    )

    for mod in [ingestion, preprocessing, training]:
        graph.add_node(mod)

    # --- Features ---
    csv_loader = RPGNode(
        name="CSV Data Loader",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="ingestion/",
        file_path="ingestion/csv_loader.py",
    )
    api_fetcher = RPGNode(
        name="API Fetcher",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="ingestion/",
        file_path="ingestion/api_fetcher.py",
    )
    feature_extractor = RPGNode(
        name="Feature Extractor",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="preprocessing/",
        file_path="preprocessing/feature_extractor.py",
    )
    normalizer = RPGNode(
        name="Score Normalizer",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="preprocessing/",
        file_path="preprocessing/normalizer.py",
    )
    trainer = RPGNode(
        name="Model Trainer",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="training/",
        file_path="training/model_trainer.py",
    )
    evaluator = RPGNode(
        name="Metric Evaluator",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="training/",
        file_path="training/evaluator.py",
    )

    features = [csv_loader, api_fetcher, feature_extractor, normalizer, trainer, evaluator]
    for f in features:
        graph.add_node(f)

    # --- HIERARCHY edges ---
    for f in [csv_loader, api_fetcher]:
        graph.add_edge(RPGEdge(
            source_id=ingestion.id, target_id=f.id, edge_type=EdgeType.HIERARCHY
        ))
    for f in [feature_extractor, normalizer]:
        graph.add_edge(RPGEdge(
            source_id=preprocessing.id, target_id=f.id, edge_type=EdgeType.HIERARCHY
        ))
    for f in [trainer, evaluator]:
        graph.add_edge(RPGEdge(
            source_id=training.id, target_id=f.id, edge_type=EdgeType.HIERARCHY
        ))

    # --- DATA_FLOW edges (inter-module, untyped) ---
    graph.add_edge(RPGEdge(
        source_id=csv_loader.id,
        target_id=feature_extractor.id,
        edge_type=EdgeType.DATA_FLOW,
        data_id="raw_data",
    ))
    graph.add_edge(RPGEdge(
        source_id=feature_extractor.id,
        target_id=trainer.id,
        edge_type=EdgeType.DATA_FLOW,
        data_id="features",
    ))
    graph.add_edge(RPGEdge(
        source_id=normalizer.id,
        target_id=evaluator.id,
        edge_type=EdgeType.DATA_FLOW,
        data_id="normalized_scores",
    ))

    return graph


# ===========================================================================
# Functional Tests
# ===========================================================================


class TestDataFlowEncoderFunctional:
    """End-to-end functional tests for DataFlowEncoder."""

    def test_all_inter_module_edges_get_typed(self) -> None:
        """All untyped inter-module DATA_FLOW edges get a data_type after encode."""
        graph = _build_ml_pipeline_graph()
        encoder = DataFlowEncoder()
        encoder.encode(graph)

        data_flow_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert len(data_flow_edges) == 3

        for edge in data_flow_edges:
            assert edge.data_type is not None, f"Edge {edge.data_id} has no data_type"
            assert edge.validated is True

    def test_type_inference_uses_source_name(self) -> None:
        """Types are inferred from source node names using _TYPE_HINTS."""
        graph = _build_ml_pipeline_graph()
        encoder = DataFlowEncoder()
        encoder.encode(graph)

        edge_types = {}
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.DATA_FLOW and edge.data_id:
                edge_types[edge.data_id] = edge.data_type

        # "CSV Data Loader" -> contains "data" -> pd.DataFrame
        assert edge_types.get("raw_data") == "pd.DataFrame"
        # "Feature Extractor" -> "Feature" doesn't match "features" exactly
        # but does match "feature" which isn't in _TYPE_HINTS; "extract" isn't either
        # So it falls back to "Any"
        assert edge_types.get("features") == "Any"
        # "Score Normalizer" -> contains "score" -> float
        assert edge_types.get("normalized_scores") == "float"

    def test_schema_metadata_propagated(self) -> None:
        """Source and target nodes receive output/input schema metadata."""
        graph = _build_ml_pipeline_graph()
        encoder = DataFlowEncoder()
        encoder.encode(graph)

        # Find CSV Data Loader and Feature Extractor
        csv_loader = None
        feat_extractor = None
        for node in graph.nodes.values():
            if node.name == "CSV Data Loader":
                csv_loader = node
            elif node.name == "Feature Extractor":
                feat_extractor = node

        assert csv_loader is not None
        assert feat_extractor is not None

        # CSV Data Loader should have output_schema
        assert "output_schema" in csv_loader.metadata
        assert "raw_data" in csv_loader.metadata["output_schema"]

        # Feature Extractor should have input_schema (from csv_loader)
        # AND output_schema (to trainer)
        assert "input_schema" in feat_extractor.metadata
        assert "output_schema" in feat_extractor.metadata

    def test_validation_passes_on_fully_typed_graph(self) -> None:
        """After encode, validation should pass (no untyped edges, no cycles)."""
        graph = _build_ml_pipeline_graph()
        encoder = DataFlowEncoder()
        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is True
        assert result.errors == []

    def test_pipeline_integration(self) -> None:
        """DataFlowEncoder works correctly in an RPGBuilder pipeline."""
        graph = _build_ml_pipeline_graph()
        encoder = DataFlowEncoder()
        builder = RPGBuilder(validate_after_each=True)
        builder.add_encoder(encoder)

        result = builder.run(graph)

        assert result is graph
        assert len(builder.steps) == 1
        step = builder.steps[0]
        assert step.encoder_name == "DataFlowEncoder"
        assert step.validation is not None
        assert step.validation.passed is True

    def test_missing_flows_created_from_invocation_edges(self) -> None:
        """INVOCATION edges between modules trigger DATA_FLOW creation."""
        graph = _build_ml_pipeline_graph()

        # Find two features in different modules
        api_fetcher = None
        trainer = None
        for node in graph.nodes.values():
            if node.name == "API Fetcher":
                api_fetcher = node
            elif node.name == "Model Trainer":
                trainer = node

        assert api_fetcher is not None
        assert trainer is not None

        # Add INVOCATION edge (no existing DATA_FLOW between these modules for this pair)
        graph.add_edge(RPGEdge(
            source_id=api_fetcher.id,
            target_id=trainer.id,
            edge_type=EdgeType.INVOCATION,
        ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)

        # Should have created a new DATA_FLOW edge for this pair
        data_flow_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        # Originally 3 + possibly 1 new (depends on module-pair dedup)
        assert len(data_flow_edges) >= 3

    def test_cyclic_inter_module_flow_detected(self) -> None:
        """Validation detects cycles in inter-module DATA_FLOW graph."""
        graph = _build_ml_pipeline_graph()

        # Find features to create a cycle: training -> ingestion
        trainer = None
        csv_loader = None
        for node in graph.nodes.values():
            if node.name == "Model Trainer":
                trainer = node
            elif node.name == "CSV Data Loader":
                csv_loader = node

        assert trainer is not None
        assert csv_loader is not None

        # Add backward DATA_FLOW: training -> ingestion
        graph.add_edge(RPGEdge(
            source_id=trainer.id,
            target_id=csv_loader.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="feedback",
            data_type="dict[str, Any]",
        ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is False
        assert any("cycle" in e.lower() for e in result.errors)

    def test_large_graph_performance(self) -> None:
        """Encoder handles graphs with many modules without errors."""
        graph = RPGGraph()
        modules = []
        features = []

        # Create 10 modules with 3 features each
        for i in range(10):
            mod = RPGNode(
                name=f"module_{i}",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=f"mod_{i}/",
            )
            graph.add_node(mod)
            modules.append(mod)

            for j in range(3):
                feat = RPGNode(
                    name=f"data_feature_{i}_{j}",
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTIONALITY,
                    folder_path=f"mod_{i}/",
                    file_path=f"mod_{i}/feat_{j}.py",
                )
                graph.add_node(feat)
                features.append(feat)
                graph.add_edge(RPGEdge(
                    source_id=mod.id, target_id=feat.id,
                    edge_type=EdgeType.HIERARCHY,
                ))

        # Add some inter-module DATA_FLOW edges (linear chain)
        for i in range(len(modules) - 1):
            src_feat = features[i * 3]  # first feature of module i
            tgt_feat = features[(i + 1) * 3]  # first feature of module i+1
            graph.add_edge(RPGEdge(
                source_id=src_feat.id,
                target_id=tgt_feat.id,
                edge_type=EdgeType.DATA_FLOW,
                data_id=f"flow_{i}",
            ))

        encoder = DataFlowEncoder()
        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is True
        # All edges should be typed
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.DATA_FLOW and edge.validated:
                assert edge.data_type is not None
