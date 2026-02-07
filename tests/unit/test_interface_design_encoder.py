"""Unit tests for InterfaceDesignEncoder (Epic 3.6).

All tests mock the LLM gateway so no real API calls are made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.interface_design_encoder import (
    InterfaceDesignEncoder,
    _safe_class_name,
    _safe_function_name,
    _validate_signature_syntax,
)
from zerorepo.rpg_enrichment.models import ValidationResult


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _mock_llm(
    signature_response: str = "def load_json(path: str) -> dict:",
    docstring_response: str = "Load JSON data from a file.",
) -> MagicMock:
    """Create a mock LLM gateway that returns predictable outputs."""
    mock = MagicMock()

    def _complete(messages: list[dict[str, Any]], model: str, **kw: Any) -> str:
        prompt = messages[0]["content"]
        if "signature" in prompt.lower() or "def " in prompt.lower():
            return signature_response
        return docstring_response

    mock.complete.side_effect = _complete
    return mock


def _make_feature_node(
    name: str,
    file_path: str = "src/module/utils.py",
    folder_path: str = "src/module/",
) -> RPGNode:
    """Create a FEATURE-level FUNCTIONALITY node with a file_path."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path=folder_path,
        file_path=file_path,
    )


def _make_graph_with_features(
    names: list[str],
    file_path: str = "src/module/utils.py",
    folder_path: str = "src/module/",
) -> tuple[RPGGraph, list[RPGNode]]:
    """Create a graph with several FEATURE nodes in the same file."""
    graph = RPGGraph()
    nodes = []
    for name in names:
        node = _make_feature_node(name, file_path=file_path, folder_path=folder_path)
        graph.add_node(node)
        nodes.append(node)
    return graph, nodes


# ===========================================================================
# Test 1: Empty graph passes through unchanged
# ===========================================================================


class TestEncodeEmptyGraph:
    def test_empty_graph_returns_same_instance(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = RPGGraph()
        result = encoder.encode(graph)
        assert result is graph
        assert graph.node_count == 0
        llm.complete.assert_not_called()


# ===========================================================================
# Test 2: Independent features get FUNCTION interface_type
# ===========================================================================


class TestIndependentFeatures:
    def test_single_feature_gets_function_type(self) -> None:
        llm = _mock_llm(signature_response="def load_json(path: str) -> dict:")
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(["Load JSON"])

        encoder.encode(graph)

        node = nodes[0]
        assert node.interface_type == InterfaceType.FUNCTION
        assert node.node_type == NodeType.FUNCTION_AUGMENTED
        assert node.signature is not None
        assert node.signature.startswith("def ")
        assert node.docstring is not None

    def test_multiple_independent_features_all_functions(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(
            ["Load JSON", "Parse CSV", "Write Output"]
        )

        encoder.encode(graph)

        for node in nodes:
            assert node.interface_type == InterfaceType.FUNCTION
            assert node.node_type == NodeType.FUNCTION_AUGMENTED


# ===========================================================================
# Test 3: Interdependent features in the same file form a class
# ===========================================================================


class TestInterdependentFeatures:
    def test_interdependent_features_become_methods(self) -> None:
        llm = _mock_llm(
            signature_response="def process_data(self, data: list) -> dict:"
        )
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(
            ["Process Data", "Validate Data"], file_path="src/module/processor.py"
        )

        # Add a DATA_FLOW edge between them (same file)
        graph.add_edge(
            RPGEdge(
                source_id=nodes[0].id,
                target_id=nodes[1].id,
                edge_type=EdgeType.DATA_FLOW,
                data_id="processed",
                data_type="dict",
            )
        )

        encoder.encode(graph)

        for node in nodes:
            assert node.interface_type == InterfaceType.METHOD
            assert node.node_type == NodeType.FUNCTION_AUGMENTED


# ===========================================================================
# Test 4: Signature validation with ast.parse
# ===========================================================================


class TestSignatureValidation:
    def test_valid_signature(self) -> None:
        assert _validate_signature_syntax("def foo(x: int) -> str:") is True

    def test_invalid_signature(self) -> None:
        assert _validate_signature_syntax("def invalid(") is False

    def test_class_signature(self) -> None:
        assert _validate_signature_syntax("class MyClass(ABC):") is True

    def test_fallback_on_invalid_llm_signature(self) -> None:
        """When LLM returns invalid syntax, encoder falls back to safe default."""
        llm = _mock_llm(signature_response="not a valid def line at all")
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(["Bad Sig Feature"])

        encoder.encode(graph)

        node = nodes[0]
        # Should have a fallback signature
        assert node.signature is not None
        assert _validate_signature_syntax(node.signature)


# ===========================================================================
# Test 5: INVOCATION edges added between interdependent features
# ===========================================================================


class TestInvocationEdges:
    def test_invocation_edges_added(self) -> None:
        llm = _mock_llm(
            signature_response="def handle(self, x: str) -> None:"
        )
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(
            ["Read Config", "Apply Config"],
            file_path="src/module/config.py",
        )

        # Create a DATA_FLOW edge to make them interdependent
        graph.add_edge(
            RPGEdge(
                source_id=nodes[0].id,
                target_id=nodes[1].id,
                edge_type=EdgeType.DATA_FLOW,
                data_id="config",
                data_type="dict",
            )
        )

        edge_count_before = graph.edge_count
        encoder.encode(graph)

        # Should have added at least one INVOCATION edge
        invocation_edges = [
            e
            for e in graph.edges.values()
            if e.edge_type == EdgeType.INVOCATION
        ]
        assert len(invocation_edges) >= 1

    def test_no_duplicate_invocation_edges(self) -> None:
        """If INVOCATION edge already exists, don't add another."""
        llm = _mock_llm(
            signature_response="def handle(self, x: str) -> None:"
        )
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(
            ["A Feature", "B Feature"],
            file_path="src/module/ab.py",
        )

        # Existing DATA_FLOW edge
        graph.add_edge(
            RPGEdge(
                source_id=nodes[0].id,
                target_id=nodes[1].id,
                edge_type=EdgeType.DATA_FLOW,
                data_id="x",
                data_type="str",
            )
        )
        # Existing INVOCATION edge
        graph.add_edge(
            RPGEdge(
                source_id=nodes[0].id,
                target_id=nodes[1].id,
                edge_type=EdgeType.INVOCATION,
            )
        )

        encoder.encode(graph)

        # Count INVOCATION edges between these specific nodes
        inv_count = sum(
            1
            for e in graph.edges.values()
            if e.edge_type == EdgeType.INVOCATION
            and e.source_id == nodes[0].id
            and e.target_id == nodes[1].id
        )
        assert inv_count == 1  # No duplicates


# ===========================================================================
# Test 6: Validate method
# ===========================================================================


class TestValidateMethod:
    def test_validate_passes_after_encode(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, _ = _make_graph_with_features(["Feature A"])

        encoder.encode(graph)
        result = encoder.validate(graph)

        assert result.passed is True
        assert result.errors == []

    def test_validate_fails_for_unenriched_feature_with_file_path(self) -> None:
        encoder = InterfaceDesignEncoder(llm_gateway=_mock_llm())
        graph, _ = _make_graph_with_features(["Raw Feature"])

        result = encoder.validate(graph)

        assert result.passed is False
        assert any("missing interface_type" in e for e in result.errors)

    def test_validate_on_empty_graph(self) -> None:
        encoder = InterfaceDesignEncoder(llm_gateway=_mock_llm())
        result = encoder.validate(RPGGraph())
        assert result.passed is True


# ===========================================================================
# Test 7: LLM failure graceful degradation
# ===========================================================================


class TestLLMFailure:
    def test_llm_exception_uses_fallback_signature(self) -> None:
        llm = MagicMock()
        llm.complete.side_effect = RuntimeError("LLM unavailable")

        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(["Broken Feature"])

        # Should NOT raise; should use fallback
        encoder.encode(graph)

        node = nodes[0]
        assert node.signature is not None
        assert node.signature.startswith("def ")
        assert node.docstring is not None


# ===========================================================================
# Test 8: Helper functions
# ===========================================================================


class TestHelperFunctions:
    def test_safe_function_name_basic(self) -> None:
        assert _safe_function_name("Load JSON") == "load_json"

    def test_safe_function_name_digits(self) -> None:
        assert _safe_function_name("3D Renderer") == "fn_3d_renderer"

    def test_safe_function_name_special_chars(self) -> None:
        assert _safe_function_name("parse-csv!") == "parse_csv"

    def test_safe_class_name_basic(self) -> None:
        assert _safe_class_name("data_processor") == "DataProcessor"

    def test_safe_class_name_digit_start(self) -> None:
        assert _safe_class_name("3d-model") == "Cls3dModel"


# ===========================================================================
# Test 9: Features without file_path are skipped
# ===========================================================================


class TestFeaturesWithoutFilePath:
    def test_feature_without_file_path_not_enriched(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = RPGGraph()
        node = RPGNode(
            name="Structural Feature",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(node)

        encoder.encode(graph)

        # Should remain un-enriched
        assert node.interface_type is None
        assert node.signature is None
        llm.complete.assert_not_called()


# ===========================================================================
# Test 10: Non-FEATURE nodes are not modified
# ===========================================================================


class TestNonFeatureNodes:
    def test_module_node_not_enriched(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = RPGGraph()
        module = RPGNode(
            name="MyModule",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(module)

        encoder.encode(graph)

        assert module.interface_type is None
        assert module.signature is None

    def test_component_node_not_enriched(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph = RPGGraph()
        component = RPGNode(
            name="MyComponent",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(component)

        encoder.encode(graph)

        assert component.interface_type is None
        assert component.signature is None


# ===========================================================================
# Test 11: Encoder name property
# ===========================================================================


class TestEncoderName:
    def test_name_is_class_name(self) -> None:
        encoder = InterfaceDesignEncoder(llm_gateway=_mock_llm())
        assert encoder.name == "InterfaceDesignEncoder"


# ===========================================================================
# Test 12: metadata flag is set on enriched nodes
# ===========================================================================


class TestMetadataFlag:
    def test_llm_signature_generated_flag(self) -> None:
        llm = _mock_llm()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        graph, nodes = _make_graph_with_features(["Flag Feature"])

        encoder.encode(graph)

        assert nodes[0].metadata.get("llm_signature_generated") is True
