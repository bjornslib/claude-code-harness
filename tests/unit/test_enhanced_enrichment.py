"""Tests for enhanced enrichment with baseline support (Wave 3).

Tests that InterfaceDesignEncoder, DataFlowEncoder, and FolderEncoder
correctly use baseline RPGGraph data when available, while maintaining
backward compatibility when no baseline is provided.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.dataflow_encoder import DataFlowEncoder
from zerorepo.rpg_enrichment.folder_encoder import FolderEncoder
from zerorepo.rpg_enrichment.interface_design_encoder import (
    InterfaceDesignEncoder,
)


# ---------------------------------------------------------------------------
# Mock LLM Gateway
# ---------------------------------------------------------------------------


class MockLLMGateway:
    """Mock LLM gateway that returns deterministic signatures and docstrings."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str:
        self.call_count += 1
        prompt = messages[0]["content"]
        if "docstring" in prompt.lower():
            return "Auto-generated docstring from LLM."
        # Return a simple signature
        return "def mock_function(self) -> None:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_node(
    name: str,
    file_path: str | None = None,
    folder_path: str | None = None,
    node_id: UUID | None = None,
) -> RPGNode:
    """Create a FEATURE-level FUNCTIONALITY node."""
    return RPGNode(
        id=node_id or uuid4(),
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        file_path=file_path,
        folder_path=folder_path,
    )


def _make_module_node(
    name: str,
    folder_path: str | None = None,
    node_id: UUID | None = None,
) -> RPGNode:
    """Create a MODULE-level FUNCTIONALITY node."""
    return RPGNode(
        id=node_id or uuid4(),
        name=name,
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path=folder_path,
    )


def _make_component_node(
    name: str,
    folder_path: str | None = None,
    node_id: UUID | None = None,
) -> RPGNode:
    """Create a COMPONENT-level FUNCTIONALITY node."""
    return RPGNode(
        id=node_id or uuid4(),
        name=name,
        level=NodeLevel.COMPONENT,
        node_type=NodeType.FUNCTIONALITY,
        folder_path=folder_path,
    )


def _make_baseline_feature(
    name: str,
    signature: str,
    file_path: str | None = None,
    folder_path: str | None = None,
    interface_type: InterfaceType = InterfaceType.FUNCTION,
    docstring: str | None = None,
) -> RPGNode:
    """Create a FEATURE node as it would appear in a baseline RPGGraph."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=interface_type,
        signature=signature,
        docstring=docstring or f"{name}: real docstring from baseline.",
        file_path=file_path,
        folder_path=folder_path,
        serena_validated=True,
        metadata={
            "baseline": True,
            "signature": signature,
        },
    )


def _build_hierarchy(
    graph: RPGGraph,
    parent_id: UUID,
    child_id: UUID,
) -> None:
    """Add a HIERARCHY edge between parent and child nodes."""
    graph.add_edge(
        RPGEdge(
            source_id=parent_id,
            target_id=child_id,
            edge_type=EdgeType.HIERARCHY,
        )
    )


# ===========================================================================
# InterfaceDesignEncoder + Baseline Tests
# ===========================================================================


class TestInterfaceDesignEncoderBaseline:
    """Tests for InterfaceDesignEncoder with baseline support."""

    def test_uses_baseline_signature_skips_llm(self) -> None:
        """When baseline has a matching node with signature, use it and skip LLM."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        # Current graph with a feature node
        graph = RPGGraph()
        node = _make_feature_node("validate_email", file_path="auth/validators.py")
        graph.add_node(node)

        # Baseline with matching node with real signature
        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "validate_email",
            signature="def validate_email(email: str) -> bool:",
            file_path="auth/validators.py",
        )
        baseline.add_node(b_node)

        encoder.encode(graph, baseline=baseline)

        assert node.signature == "def validate_email(email: str) -> bool:"
        assert node.serena_validated is True
        assert node.metadata.get("baseline_signature_used") is True
        assert node.metadata.get("llm_signature_generated") is False
        assert llm.call_count == 0  # No LLM calls for signature or docstring

    def test_falls_through_to_llm_for_new_nodes(self) -> None:
        """Nodes not in baseline still use LLM for signature generation."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        node = _make_feature_node("new_feature", file_path="new/module.py")
        graph.add_node(node)

        # Baseline with a different node
        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "existing_feature",
            signature="def existing_feature() -> None:",
            file_path="old/module.py",
        )
        baseline.add_node(b_node)

        encoder.encode(graph, baseline=baseline)

        # LLM should have been called (signature + docstring = 2 calls)
        assert llm.call_count == 2
        assert node.serena_validated is False
        assert node.metadata.get("baseline_signature_used") is None

    def test_no_baseline_works_identically(self) -> None:
        """Without baseline, encoder works exactly as before."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        node = _make_feature_node("process_data", file_path="core/processor.py")
        graph.add_node(node)

        encoder.encode(graph, baseline=None)

        assert llm.call_count == 2  # signature + docstring
        assert node.node_type == NodeType.FUNCTION_AUGMENTED
        assert node.interface_type is not None
        assert node.signature is not None

    def test_baseline_match_is_case_insensitive(self) -> None:
        """Baseline matching uses case-insensitive name comparison."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        node = _make_feature_node("Process Data", file_path="core/proc.py")
        graph.add_node(node)

        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "process data",
            signature="def process_data(df: pd.DataFrame) -> pd.DataFrame:",
            file_path="core/proc.py",
        )
        baseline.add_node(b_node)

        encoder.encode(graph, baseline=baseline)

        assert node.signature == "def process_data(df: pd.DataFrame) -> pd.DataFrame:"
        assert node.serena_validated is True
        assert llm.call_count == 0

    def test_baseline_preserves_interface_type(self) -> None:
        """Baseline node's interface_type is preserved on the matched node."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        node = _make_feature_node("handle_request", file_path="api/handler.py")
        graph.add_node(node)

        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "handle_request",
            signature="def handle_request(self, request: Request) -> Response:",
            interface_type=InterfaceType.METHOD,
            file_path="api/handler.py",
        )
        baseline.add_node(b_node)

        encoder.encode(graph, baseline=baseline)

        assert node.interface_type == InterfaceType.METHOD
        assert node.node_type == NodeType.FUNCTION_AUGMENTED

    def test_mixed_baseline_and_new_nodes(self) -> None:
        """Graph with both baseline-matched and new nodes handles both correctly."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        existing = _make_feature_node("existing_fn", file_path="mod/file.py")
        new_node = _make_feature_node("brand_new_fn", file_path="mod/file.py")
        graph.add_node(existing)
        graph.add_node(new_node)

        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "existing_fn",
            signature="def existing_fn(x: int) -> str:",
            file_path="mod/file.py",
        )
        baseline.add_node(b_node)

        encoder.encode(graph, baseline=baseline)

        # Existing node uses baseline
        assert existing.signature == "def existing_fn(x: int) -> str:"
        assert existing.serena_validated is True
        assert existing.metadata.get("baseline_signature_used") is True

        # New node uses LLM
        assert new_node.signature is not None
        assert new_node.serena_validated is False
        assert llm.call_count == 2  # Only for new_node (sig + docstring)

    def test_empty_graph_with_baseline(self) -> None:
        """Empty graph returns immediately even with baseline."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "some_fn",
            signature="def some_fn() -> None:",
        )
        baseline.add_node(b_node)

        result = encoder.encode(graph, baseline=baseline)
        assert result.node_count == 0
        assert llm.call_count == 0

    def test_baseline_node_without_signature_falls_through(self) -> None:
        """Baseline node without a signature does not bypass LLM."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        node = _make_feature_node("partial_fn", file_path="mod/partial.py")
        graph.add_node(node)

        baseline = RPGGraph()
        # Baseline feature WITHOUT signature (FUNCTIONALITY type can't have one)
        b_node = RPGNode(
            name="partial_fn",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            file_path="mod/partial.py",
            metadata={"baseline": True},
        )
        baseline.add_node(b_node)

        encoder.encode(graph, baseline=baseline)

        # Should fall through to LLM since baseline has no signature
        assert llm.call_count == 2
        assert node.metadata.get("baseline_signature_used") is None


# ===========================================================================
# DataFlowEncoder + Baseline Tests
# ===========================================================================


class TestDataFlowEncoderBaseline:
    """Tests for DataFlowEncoder with baseline support."""

    def test_merges_baseline_dataflow_edges(self) -> None:
        """Baseline DATA_FLOW edges are merged into the current graph."""
        encoder = DataFlowEncoder()

        # Current graph: two modules with no DATA_FLOW between them
        graph = RPGGraph()
        mod_a = _make_module_node("ModuleA")
        mod_b = _make_module_node("ModuleB")
        feat_a = _make_feature_node("feature_a", file_path="a/feat.py")
        feat_b = _make_feature_node("feature_b", file_path="b/feat.py")
        graph.add_node(mod_a)
        graph.add_node(mod_b)
        graph.add_node(feat_a)
        graph.add_node(feat_b)
        _build_hierarchy(graph, mod_a.id, feat_a.id)
        _build_hierarchy(graph, mod_b.id, feat_b.id)

        # Baseline: has a DATA_FLOW edge between matching nodes
        baseline = RPGGraph()
        b_feat_a = _make_feature_node("feature_a", file_path="a/feat.py")
        b_feat_b = _make_feature_node("feature_b", file_path="b/feat.py")
        baseline.add_node(b_feat_a)
        baseline.add_node(b_feat_b)
        baseline.add_edge(
            RPGEdge(
                source_id=b_feat_a.id,
                target_id=b_feat_b.id,
                edge_type=EdgeType.DATA_FLOW,
                data_id="processed_data",
                data_type="pd.DataFrame",
            )
        )

        initial_edge_count = graph.edge_count
        encoder.encode(graph, baseline=baseline)

        # Should have more edges now (baseline edge merged)
        dataflow_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        assert len(dataflow_edges) >= 1

        # Check that at least one edge has the baseline type
        types = [e.data_type for e in dataflow_edges]
        assert "pd.DataFrame" in types

        # Check metadata markers
        assert feat_a.metadata.get("baseline_dataflow_source") is True
        assert feat_b.metadata.get("baseline_dataflow_target") is True

    def test_upgrades_any_type_from_baseline(self) -> None:
        """Existing edges with 'Any' type get upgraded from baseline."""
        encoder = DataFlowEncoder()

        graph = RPGGraph()
        mod_a = _make_module_node("ModA")
        mod_b = _make_module_node("ModB")
        feat_a = _make_feature_node("alpha_feature", file_path="a/feat.py")
        feat_b = _make_feature_node("beta_feature", file_path="b/feat.py")
        graph.add_node(mod_a)
        graph.add_node(mod_b)
        graph.add_node(feat_a)
        graph.add_node(feat_b)
        _build_hierarchy(graph, mod_a.id, feat_a.id)
        _build_hierarchy(graph, mod_b.id, feat_b.id)

        # Pre-existing edge with generic type
        existing_edge = RPGEdge(
            source_id=feat_a.id,
            target_id=feat_b.id,
            edge_type=EdgeType.DATA_FLOW,
            data_type="Any",
        )
        graph.add_edge(existing_edge)

        # Baseline has specific type
        baseline = RPGGraph()
        b_a = _make_feature_node("alpha_feature")
        b_b = _make_feature_node("beta_feature")
        baseline.add_node(b_a)
        baseline.add_node(b_b)
        baseline.add_edge(
            RPGEdge(
                source_id=b_a.id,
                target_id=b_b.id,
                edge_type=EdgeType.DATA_FLOW,
                data_type="UserModel",
                data_id="user_data",
            )
        )

        encoder.encode(graph, baseline=baseline)

        # Edge type should be upgraded
        assert existing_edge.data_type == "UserModel"

    def test_no_baseline_works_identically(self) -> None:
        """Without baseline, DataFlowEncoder works exactly as before."""
        encoder = DataFlowEncoder()

        graph = RPGGraph()
        mod = _make_module_node("TestMod")
        feat = _make_feature_node("data_processor", file_path="mod/proc.py")
        graph.add_node(mod)
        graph.add_node(feat)
        _build_hierarchy(graph, mod.id, feat.id)

        encoder.encode(graph, baseline=None)

        # Should still work, just no baseline merge
        assert feat.metadata.get("baseline_dataflow_source") is None

    def test_no_duplicate_edges_from_baseline(self) -> None:
        """Baseline edges that already exist in the graph are not duplicated."""
        encoder = DataFlowEncoder()

        graph = RPGGraph()
        mod_a = _make_module_node("ModX")
        mod_b = _make_module_node("ModY")
        feat_a = _make_feature_node("feat_x", file_path="x/feat.py")
        feat_b = _make_feature_node("feat_y", file_path="y/feat.py")
        graph.add_node(mod_a)
        graph.add_node(mod_b)
        graph.add_node(feat_a)
        graph.add_node(feat_b)
        _build_hierarchy(graph, mod_a.id, feat_a.id)
        _build_hierarchy(graph, mod_b.id, feat_b.id)

        # Pre-existing DATA_FLOW edge with a good type
        graph.add_edge(
            RPGEdge(
                source_id=feat_a.id,
                target_id=feat_b.id,
                edge_type=EdgeType.DATA_FLOW,
                data_type="SpecificModel",
            )
        )
        initial_count = graph.edge_count

        # Baseline with same named edge
        baseline = RPGGraph()
        b_a = _make_feature_node("feat_x")
        b_b = _make_feature_node("feat_y")
        baseline.add_node(b_a)
        baseline.add_node(b_b)
        baseline.add_edge(
            RPGEdge(
                source_id=b_a.id,
                target_id=b_b.id,
                edge_type=EdgeType.DATA_FLOW,
                data_type="OtherModel",
            )
        )

        encoder.encode(graph, baseline=baseline)

        # Count DATA_FLOW edges between feat_x and feat_y
        df_edges = [
            e for e in graph.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
            and e.source_id == feat_a.id
            and e.target_id == feat_b.id
        ]
        assert len(df_edges) == 1  # No duplicate
        # Existing edge with SpecificModel should NOT be overwritten (it's not "Any")
        assert df_edges[0].data_type == "SpecificModel"


# ===========================================================================
# FolderEncoder + Baseline Tests
# ===========================================================================


class TestFolderEncoderBaseline:
    """Tests for FolderEncoder with baseline support."""

    def test_uses_baseline_folder_paths(self) -> None:
        """Existing nodes retain their real folder_path from baseline."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        mod = _make_module_node("AuthModule")
        comp = _make_component_node("Validators")
        feat = _make_feature_node("validate_email")
        graph.add_node(mod)
        graph.add_node(comp)
        graph.add_node(feat)
        _build_hierarchy(graph, mod.id, comp.id)
        _build_hierarchy(graph, comp.id, feat.id)

        # Baseline with real paths
        baseline = RPGGraph()
        b_mod = _make_module_node("AuthModule", folder_path="auth/")
        b_comp = _make_component_node("Validators", folder_path="auth/validators/")
        b_feat = _make_feature_node(
            "validate_email",
            folder_path="auth/validators/",
            file_path="auth/validators/email.py",
        )
        baseline.add_node(b_mod)
        baseline.add_node(b_comp)
        baseline.add_node(b_feat)

        encoder.encode(graph, baseline=baseline)

        assert mod.folder_path == "auth/"
        assert comp.folder_path == "auth/validators/"
        assert feat.folder_path == "auth/validators/"
        assert mod.metadata.get("baseline_folder_used") is True
        assert comp.metadata.get("baseline_folder_used") is True
        assert feat.metadata.get("baseline_folder_used") is True

    def test_new_nodes_get_generated_paths(self) -> None:
        """New nodes not in baseline get generated folder paths as usual."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        mod = _make_module_node("NewModule")
        graph.add_node(mod)

        # Baseline with a different module
        baseline = RPGGraph()
        b_mod = _make_module_node("OldModule", folder_path="old_module/")
        baseline.add_node(b_mod)

        encoder.encode(graph, baseline=baseline)

        # New module gets a generated path (not from baseline)
        assert mod.folder_path is not None
        assert mod.metadata.get("baseline_folder_used") is None

    def test_no_baseline_works_identically(self) -> None:
        """Without baseline, FolderEncoder works exactly as before."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        mod = _make_module_node("TestModule")
        comp = _make_component_node("TestComp")
        graph.add_node(mod)
        graph.add_node(comp)
        _build_hierarchy(graph, mod.id, comp.id)

        encoder.encode(graph, baseline=None)

        assert mod.folder_path == ""
        assert comp.folder_path is not None
        assert "testcomp" in comp.folder_path.lower()

    def test_baseline_file_path_applied_to_matching_node(self) -> None:
        """Baseline file_path is applied to matching nodes without file_path."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        feat = _make_feature_node("process_csv")
        graph.add_node(feat)

        baseline = RPGGraph()
        b_feat = _make_feature_node(
            "process_csv",
            folder_path="data/",
            file_path="data/csv_processor.py",
        )
        baseline.add_node(b_feat)

        encoder.encode(graph, baseline=baseline)

        assert feat.folder_path == "data/"
        assert feat.file_path == "data/csv_processor.py"
        assert feat.metadata.get("baseline_folder_used") is True
        assert feat.metadata.get("baseline_file_path_used") is True

    def test_mixed_baseline_and_new_nodes_folder(self) -> None:
        """Graph with both baseline-matched and new nodes handles both correctly."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        existing_mod = _make_module_node("ExistingMod")
        new_mod = _make_module_node("NewMod")
        graph.add_node(existing_mod)
        graph.add_node(new_mod)

        baseline = RPGGraph()
        b_mod = _make_module_node("ExistingMod", folder_path="existing/")
        baseline.add_node(b_mod)

        encoder.encode(graph, baseline=baseline)

        assert existing_mod.folder_path == "existing/"
        assert existing_mod.metadata.get("baseline_folder_used") is True
        # New mod gets default assignment (empty string since it's root)
        assert new_mod.folder_path is not None

    def test_empty_graph_with_baseline(self) -> None:
        """Empty graph returns immediately even with baseline."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        baseline = RPGGraph()
        b_mod = _make_module_node("SomeMod", folder_path="some/")
        baseline.add_node(b_mod)

        result = encoder.encode(graph, baseline=baseline)
        assert result.node_count == 0


# ===========================================================================
# Cross-encoder backward compatibility
# ===========================================================================


class TestBackwardCompatibility:
    """Ensure all three encoders work identically without baseline."""

    def test_interface_encoder_no_baseline(self) -> None:
        """InterfaceDesignEncoder without baseline produces valid output."""
        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        for i in range(3):
            node = _make_feature_node(f"fn_{i}", file_path=f"mod/file_{i}.py")
            graph.add_node(node)

        encoder.encode(graph)

        for node in graph.nodes.values():
            assert node.signature is not None
            assert node.interface_type is not None
            assert node.node_type == NodeType.FUNCTION_AUGMENTED

    def test_dataflow_encoder_no_baseline(self) -> None:
        """DataFlowEncoder without baseline produces valid output."""
        encoder = DataFlowEncoder()

        graph = RPGGraph()
        mod = _make_module_node("Mod")
        graph.add_node(mod)

        result = encoder.encode(graph)
        assert result is graph

    def test_folder_encoder_no_baseline(self) -> None:
        """FolderEncoder without baseline produces valid output."""
        encoder = FolderEncoder()

        graph = RPGGraph()
        mod = _make_module_node("TestMod")
        child = _make_component_node("Child")
        graph.add_node(mod)
        graph.add_node(child)
        _build_hierarchy(graph, mod.id, child.id)

        encoder.encode(graph)

        assert mod.folder_path is not None
        assert child.folder_path is not None

    def test_validate_passes_with_baseline_enriched_nodes(self) -> None:
        """Validation passes for nodes enriched via baseline."""
        llm = MockLLMGateway()
        ide_encoder = InterfaceDesignEncoder(llm_gateway=llm)

        graph = RPGGraph()
        node = _make_feature_node("check_auth", file_path="auth/check.py")
        graph.add_node(node)

        baseline = RPGGraph()
        b_node = _make_baseline_feature(
            "check_auth",
            signature="def check_auth(token: str) -> bool:",
            file_path="auth/check.py",
        )
        baseline.add_node(b_node)

        ide_encoder.encode(graph, baseline=baseline)

        result = ide_encoder.validate(graph)
        assert result.passed is True
        assert len(result.errors) == 0
