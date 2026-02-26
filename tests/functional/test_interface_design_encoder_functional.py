"""Functional tests for InterfaceDesignEncoder (Epic 3.6).

These tests exercise the encoder in a realistic multi-node graph scenario,
verifying end-to-end enrichment with the RPGBuilder pipeline.
All tests mock the LLM gateway.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.interface_design_encoder import (
    InterfaceDesignEncoder,
    _validate_signature_syntax,
)
from cobuilder.repomap.rpg_enrichment.pipeline import RPGBuilder


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_llm() -> MagicMock:
    """LLM mock returning valid signatures and docstrings."""
    mock = MagicMock()

    call_count = {"n": 0}

    def _complete(messages: list[dict[str, Any]], model: str, **kw: Any) -> str:
        call_count["n"] += 1
        prompt = messages[0]["content"]
        if "signature" in prompt.lower() or "def " in prompt.lower():
            # Generate a unique but valid signature
            return f"def func_{call_count['n']}(data: Any) -> None:"
        return f"Auto-generated docstring for call {call_count['n']}."

    mock.complete.side_effect = _complete
    return mock


def _build_realistic_graph() -> RPGGraph:
    """Build a realistic graph with MODULE -> COMPONENT -> FEATURE hierarchy.

    Structure:
        data_processing (MODULE)
        |- io_component (COMPONENT)
        |  |- Load CSV (FEATURE) -- file: src/data_processing/io.py
        |  |- Write Output (FEATURE) -- file: src/data_processing/io.py
        |- transform_component (COMPONENT)
           |- Normalize Data (FEATURE) -- file: src/data_processing/transform.py
           |- Scale Features (FEATURE) -- file: src/data_processing/transform.py
           |- Validate Schema (FEATURE) -- file: src/data_processing/validate.py
    """
    graph = RPGGraph()

    # MODULE
    module = RPGNode(
        name="data_processing",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
    )
    graph.add_node(module)

    # COMPONENTs
    io_comp = RPGNode(
        name="io_component",
        level=NodeLevel.COMPONENT,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
    )
    transform_comp = RPGNode(
        name="transform_component",
        level=NodeLevel.COMPONENT,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
    )
    graph.add_node(io_comp)
    graph.add_node(transform_comp)

    # HIERARCHY: module -> components
    graph.add_edge(RPGEdge(source_id=module.id, target_id=io_comp.id, edge_type=EdgeType.HIERARCHY))
    graph.add_edge(RPGEdge(source_id=module.id, target_id=transform_comp.id, edge_type=EdgeType.HIERARCHY))

    # FEATURES - io group (same file, with inter-dependency)
    load_csv = RPGNode(
        name="Load CSV",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
        file_path="src/data_processing/io.py",
    )
    write_output = RPGNode(
        name="Write Output",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
        file_path="src/data_processing/io.py",
    )
    graph.add_node(load_csv)
    graph.add_node(write_output)

    # FEATURES - transform group (same file, interdependent)
    normalize = RPGNode(
        name="Normalize Data",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
        file_path="src/data_processing/transform.py",
    )
    scale = RPGNode(
        name="Scale Features",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
        file_path="src/data_processing/transform.py",
    )
    graph.add_node(normalize)
    graph.add_node(scale)

    # FEATURE - standalone in its own file
    validate_schema = RPGNode(
        name="Validate Schema",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="src/data_processing/",
        file_path="src/data_processing/validate.py",
    )
    graph.add_node(validate_schema)

    # HIERARCHY: components -> features
    graph.add_edge(RPGEdge(source_id=io_comp.id, target_id=load_csv.id, edge_type=EdgeType.HIERARCHY))
    graph.add_edge(RPGEdge(source_id=io_comp.id, target_id=write_output.id, edge_type=EdgeType.HIERARCHY))
    graph.add_edge(RPGEdge(source_id=transform_comp.id, target_id=normalize.id, edge_type=EdgeType.HIERARCHY))
    graph.add_edge(RPGEdge(source_id=transform_comp.id, target_id=scale.id, edge_type=EdgeType.HIERARCHY))
    graph.add_edge(RPGEdge(source_id=transform_comp.id, target_id=validate_schema.id, edge_type=EdgeType.HIERARCHY))

    # DATA_FLOW: normalize -> scale (same file, making them interdependent)
    graph.add_edge(
        RPGEdge(
            source_id=normalize.id,
            target_id=scale.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="normalized",
            data_type="np.ndarray",
        )
    )

    # DATA_FLOW: load_csv -> write_output (same file, interdependent)
    graph.add_edge(
        RPGEdge(
            source_id=load_csv.id,
            target_id=write_output.id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="csv_data",
            data_type="pd.DataFrame",
        )
    )

    return graph


# ===========================================================================
# Functional Test: Full pipeline with InterfaceDesignEncoder
# ===========================================================================


class TestInterfaceDesignEncoderFunctional:
    """End-to-end functional tests for InterfaceDesignEncoder."""

    def test_full_encode_enriches_all_features(self) -> None:
        """All FEATURE nodes with file_path get enriched."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        encoder.encode(graph)

        feature_nodes = [
            n for n in graph.nodes.values()
            if n.level == NodeLevel.FEATURE and n.file_path
        ]
        assert len(feature_nodes) == 5

        for node in feature_nodes:
            assert node.interface_type is not None
            assert node.node_type == NodeType.FUNCTION_AUGMENTED
            assert node.signature is not None
            assert node.docstring is not None
            assert node.metadata.get("llm_signature_generated") is True

    def test_interdependent_features_become_methods(self) -> None:
        """Features connected by same-file DATA_FLOW become METHODs."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        encoder.encode(graph)

        # Find transform.py features
        transform_features = [
            n for n in graph.nodes.values()
            if n.file_path == "src/data_processing/transform.py"
            and n.level == NodeLevel.FEATURE
        ]
        assert len(transform_features) == 2
        for node in transform_features:
            assert node.interface_type == InterfaceType.METHOD

    def test_standalone_feature_is_function(self) -> None:
        """Feature alone in its file gets FUNCTION type."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        encoder.encode(graph)

        validate_node = next(
            n for n in graph.nodes.values()
            if n.name == "Validate Schema"
        )
        assert validate_node.interface_type == InterfaceType.FUNCTION

    def test_validate_passes_after_full_encode(self) -> None:
        """Validation succeeds after encoding."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is True
        assert result.errors == []

    def test_pipeline_integration(self) -> None:
        """InterfaceDesignEncoder works correctly in an RPGBuilder pipeline."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        builder = RPGBuilder(validate_after_each=True)
        builder.add_encoder(encoder)

        graph = _build_realistic_graph()
        result = builder.run(graph)

        assert result is graph

        # Check the pipeline step recorded
        assert len(builder.steps) == 1
        step = builder.steps[0]
        assert step.encoder_name == "InterfaceDesignEncoder"
        assert step.validation is not None
        assert step.validation.passed is True

    def test_all_generated_signatures_are_valid_python(self) -> None:
        """Every signature generated by the encoder parses with ast."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        encoder.encode(graph)

        for node in graph.nodes.values():
            if node.signature:
                assert _validate_signature_syntax(node.signature), (
                    f"Invalid signature for {node.name}: {node.signature}"
                )

    def test_invocation_edges_added_for_interdependent_features(self) -> None:
        """INVOCATION edges are added between interdependent features."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        encoder.encode(graph)

        invocation_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.INVOCATION
        ]
        # At least some invocation edges should exist
        assert len(invocation_edges) >= 1

    def test_non_feature_nodes_unchanged(self) -> None:
        """MODULE and COMPONENT nodes are not modified by the encoder."""
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = _build_realistic_graph()

        # Record original state
        non_features = {
            nid: (n.interface_type, n.signature, n.docstring)
            for nid, n in graph.nodes.items()
            if n.level != NodeLevel.FEATURE
        }

        encoder.encode(graph)

        for nid, (orig_itype, orig_sig, orig_doc) in non_features.items():
            node = graph.nodes[nid]
            assert node.interface_type == orig_itype
            assert node.signature == orig_sig
            assert node.docstring == orig_doc
