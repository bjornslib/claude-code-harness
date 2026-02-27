"""Unit tests for delta-aware graph construction (Wave 2A).

Tests cover:
- DeltaStatus enum values
- Baseline-aware spec parsing (context building)
- Delta graph construction (node matching, delta_status tagging)
- Converter behaviour with and without baseline
- CLI integration of baseline threading
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cobuilder.repomap.graph_construction.builder import FunctionalityGraph
from cobuilder.repomap.graph_construction.converter import FunctionalityGraphConverter
from cobuilder.repomap.graph_construction.dependencies import DependencyEdge
from cobuilder.repomap.graph_construction.partitioner import ModuleSpec
from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import (
    DeltaStatus,
    EdgeType,
    NodeLevel,
    NodeType,
)
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.spec_parser.parser import SpecParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    level: NodeLevel = NodeLevel.FEATURE,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    parent_id=None,
    folder_path=None,
    file_path=None,
    signature=None,
    docstring=None,
    metadata=None,
) -> RPGNode:
    """Helper to create an RPGNode for testing."""
    return RPGNode(
        name=name,
        level=level,
        node_type=node_type,
        parent_id=parent_id,
        folder_path=folder_path,
        file_path=file_path,
        signature=signature,
        docstring=docstring,
        metadata=metadata or {},
    )


def _make_baseline() -> RPGGraph:
    """Create a baseline RPGGraph with known structure.

    Structure:
      MODULE: auth_service (folder: src/auth)
        COMPONENT: authentication
          FEATURE: login_handler (signature: def login(...))
          FEATURE: token_validator
        FEATURE: password_reset
      MODULE: api_gateway
        FEATURE: route_dispatcher
    """
    graph = RPGGraph(metadata={"source": "test_baseline"})

    # auth_service module
    auth_mod = _make_node(
        "auth_service",
        level=NodeLevel.MODULE,
        folder_path="src/auth",
        docstring="Authentication service module",
    )
    graph.add_node(auth_mod)

    # authentication component
    auth_comp = _make_node(
        "authentication",
        level=NodeLevel.COMPONENT,
        parent_id=auth_mod.id,
        docstring="Handles user authentication flows",
    )
    graph.add_node(auth_comp)

    # HIERARCHY: auth_service -> authentication
    graph.add_edge(RPGEdge(
        source_id=auth_mod.id,
        target_id=auth_comp.id,
        edge_type=EdgeType.HIERARCHY,
    ))

    # login_handler feature
    login_feat = _make_node(
        "login handler",
        level=NodeLevel.FEATURE,
        parent_id=auth_comp.id,
        signature="def login(username: str, password: str) -> AuthResult",
        file_path="src/auth/login.py",
        folder_path="src/auth",
    )
    graph.add_node(login_feat)
    graph.add_edge(RPGEdge(
        source_id=auth_comp.id,
        target_id=login_feat.id,
        edge_type=EdgeType.HIERARCHY,
    ))

    # token_validator feature
    token_feat = _make_node(
        "token validator",
        level=NodeLevel.FEATURE,
        parent_id=auth_comp.id,
        signature="def validate_token(token: str) -> bool",
    )
    graph.add_node(token_feat)
    graph.add_edge(RPGEdge(
        source_id=auth_comp.id,
        target_id=token_feat.id,
        edge_type=EdgeType.HIERARCHY,
    ))

    # password_reset feature (directly under module)
    pw_feat = _make_node(
        "password reset",
        level=NodeLevel.FEATURE,
        parent_id=auth_mod.id,
    )
    graph.add_node(pw_feat)
    graph.add_edge(RPGEdge(
        source_id=auth_mod.id,
        target_id=pw_feat.id,
        edge_type=EdgeType.HIERARCHY,
    ))

    # api_gateway module
    api_mod = _make_node(
        "api_gateway",
        level=NodeLevel.MODULE,
        folder_path="src/api",
    )
    graph.add_node(api_mod)

    # route_dispatcher feature
    route_feat = _make_node(
        "route dispatcher",
        level=NodeLevel.FEATURE,
        parent_id=api_mod.id,
    )
    graph.add_node(route_feat)
    graph.add_edge(RPGEdge(
        source_id=api_mod.id,
        target_id=route_feat.id,
        edge_type=EdgeType.HIERARCHY,
    ))

    return graph


def _make_func_graph(module_names: list[str]) -> FunctionalityGraph:
    """Create a minimal FunctionalityGraph with given module names.

    Each module has one feature named the same as the module.
    """
    modules = [
        ModuleSpec(
            name=name,
            description=f"Module for {name}",
            feature_ids=[f"{name}_feature"],
            public_interface=[f"{name}_feature"],
            rationale=f"Test module {name}",
        )
        for name in module_names
    ]
    return FunctionalityGraph(
        modules=modules,
        dependencies=[],
        is_acyclic=True,
        metadata={"source": "test"},
    )


# ---------------------------------------------------------------------------
# DeltaStatus enum tests
# ---------------------------------------------------------------------------


class TestDeltaStatus:
    """Tests for the DeltaStatus enumeration."""

    def test_enum_values(self):
        """DeltaStatus has new, existing, and modified values."""
        assert DeltaStatus.NEW == "new"
        assert DeltaStatus.EXISTING == "existing"
        assert DeltaStatus.MODIFIED == "modified"

    def test_enum_is_string(self):
        """DeltaStatus values are strings (str, Enum)."""
        assert isinstance(DeltaStatus.NEW, str)
        assert isinstance(DeltaStatus.EXISTING, str)
        assert isinstance(DeltaStatus.MODIFIED, str)

    def test_enum_membership(self):
        """All three statuses are members of DeltaStatus."""
        assert len(DeltaStatus) == 3
        assert "new" in [s.value for s in DeltaStatus]
        assert "existing" in [s.value for s in DeltaStatus]
        assert "modified" in [s.value for s in DeltaStatus]

    def test_enum_from_value(self):
        """Can create DeltaStatus from string value."""
        assert DeltaStatus("new") == DeltaStatus.NEW
        assert DeltaStatus("existing") == DeltaStatus.EXISTING
        assert DeltaStatus("modified") == DeltaStatus.MODIFIED


# ---------------------------------------------------------------------------
# Baseline node matching tests
# ---------------------------------------------------------------------------


class TestBaselineNodeMatching:
    """Tests for _find_matching_baseline_node."""

    def test_exact_name_match(self):
        """Exact name match finds the baseline node."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        result = conv._find_matching_baseline_node(
            "auth_service", baseline, level=NodeLevel.MODULE
        )
        assert result is not None
        assert result.name == "auth_service"

    def test_normalized_name_match(self):
        """Case-insensitive, underscore-normalized match works."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        result = conv._find_matching_baseline_node(
            "Auth Service", baseline, level=NodeLevel.MODULE
        )
        assert result is not None
        assert result.name == "auth_service"

    def test_normalized_name_with_hyphens(self):
        """Hyphens are normalized to underscores for matching."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        result = conv._find_matching_baseline_node(
            "auth-service", baseline, level=NodeLevel.MODULE
        )
        assert result is not None
        assert result.name == "auth_service"

    def test_no_match_returns_none(self):
        """Non-existent name returns None."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        result = conv._find_matching_baseline_node(
            "nonexistent_module", baseline, level=NodeLevel.MODULE
        )
        assert result is None

    def test_level_filter(self):
        """Level filter restricts matching to specific level."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        # "authentication" exists as COMPONENT, not MODULE
        result = conv._find_matching_baseline_node(
            "authentication", baseline, level=NodeLevel.MODULE
        )
        assert result is None

        result = conv._find_matching_baseline_node(
            "authentication", baseline, level=NodeLevel.COMPONENT
        )
        assert result is not None
        assert result.name == "authentication"

    def test_no_level_filter_matches_any(self):
        """Without level filter, any level matches."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        result = conv._find_matching_baseline_node(
            "authentication", baseline
        )
        assert result is not None

    def test_feature_matching(self):
        """Feature-level nodes can be matched."""
        baseline = _make_baseline()
        conv = FunctionalityGraphConverter()
        result = conv._find_matching_baseline_node(
            "login handler", baseline, level=NodeLevel.FEATURE
        )
        assert result is not None
        assert result.name == "login handler"


# ---------------------------------------------------------------------------
# Delta status tagging tests
# ---------------------------------------------------------------------------


class TestDeltaStatusTagging:
    """Tests for _tag_delta_status."""

    def test_new_node_tagged(self):
        """Node without baseline match is tagged as NEW."""
        node = _make_node("brand_new_feature")
        FunctionalityGraphConverter._tag_delta_status(node, None)
        assert node.metadata["delta_status"] == DeltaStatus.NEW.value

    def test_existing_node_tagged(self):
        """Node with baseline match is tagged as EXISTING."""
        node = _make_node("login handler", level=NodeLevel.FEATURE)
        baseline_node = _make_node(
            "login handler",
            level=NodeLevel.FEATURE,
            signature="def login(username: str, password: str) -> AuthResult",
            file_path="src/auth/login.py",
            folder_path="src/auth",
        )
        FunctionalityGraphConverter._tag_delta_status(node, baseline_node)
        assert node.metadata["delta_status"] == DeltaStatus.EXISTING.value
        assert node.metadata["baseline_node_id"] == str(baseline_node.id)

    def test_existing_node_preserves_signature(self):
        """Existing node copies signature from baseline."""
        node = _make_node("login handler", level=NodeLevel.FEATURE)
        assert node.signature is None

        baseline_node = _make_node(
            "login handler",
            level=NodeLevel.FEATURE,
            signature="def login(u: str, p: str) -> AuthResult",
        )
        FunctionalityGraphConverter._tag_delta_status(node, baseline_node)
        assert node.signature == "def login(u: str, p: str) -> AuthResult"

    def test_existing_node_preserves_file_path(self):
        """Existing node copies file_path from baseline."""
        node = _make_node("login handler", level=NodeLevel.FEATURE)
        baseline_node = _make_node(
            "login handler",
            level=NodeLevel.FEATURE,
            file_path="src/auth/login.py",
            folder_path="src/auth",
        )
        FunctionalityGraphConverter._tag_delta_status(node, baseline_node)
        assert node.file_path == "src/auth/login.py"
        assert node.folder_path == "src/auth"

    def test_existing_node_preserves_docstring(self):
        """Existing node copies docstring from baseline."""
        node = _make_node("login handler", level=NodeLevel.FEATURE)
        baseline_node = _make_node(
            "login handler",
            level=NodeLevel.FEATURE,
            docstring="Handles user login requests.",
        )
        FunctionalityGraphConverter._tag_delta_status(node, baseline_node)
        assert node.docstring == "Handles user login requests."

    def test_existing_node_does_not_overwrite_own_data(self):
        """When the new node already has data, baseline does not overwrite."""
        node = _make_node(
            "login handler",
            level=NodeLevel.FEATURE,
            signature="def login_v2(u: str) -> Result",
        )
        baseline_node = _make_node(
            "login handler",
            level=NodeLevel.FEATURE,
            signature="def login(u: str, p: str) -> AuthResult",
        )
        FunctionalityGraphConverter._tag_delta_status(node, baseline_node)
        # Own signature is preserved
        assert node.signature == "def login_v2(u: str) -> Result"


# ---------------------------------------------------------------------------
# Converter delta integration tests
# ---------------------------------------------------------------------------


class TestConverterDeltaIntegration:
    """Tests for FunctionalityGraphConverter.convert() with baseline."""

    def test_convert_without_baseline_no_delta_status(self):
        """Without baseline, nodes have no delta_status metadata."""
        func_graph = _make_func_graph(["auth_service"])
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph)

        for node in rpg.nodes.values():
            assert "delta_status" not in node.metadata

    def test_convert_without_baseline_identical_output(self):
        """Without baseline, output is structurally identical."""
        func_graph = _make_func_graph(["auth_service", "api_gateway"])
        converter = FunctionalityGraphConverter()

        rpg_no_baseline = converter.convert(func_graph)
        rpg_with_none = converter.convert(func_graph, baseline=None)

        assert rpg_no_baseline.node_count == rpg_with_none.node_count
        assert rpg_no_baseline.edge_count == rpg_with_none.edge_count

    def test_convert_with_baseline_tags_all_nodes(self):
        """With baseline, all nodes get delta_status metadata."""
        baseline = _make_baseline()
        func_graph = _make_func_graph(["auth_service", "new_module"])
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph, baseline=baseline)

        for node in rpg.nodes.values():
            assert "delta_status" in node.metadata
            assert node.metadata["delta_status"] in [
                DeltaStatus.NEW.value,
                DeltaStatus.EXISTING.value,
                DeltaStatus.MODIFIED.value,
            ]

    def test_existing_module_tagged_correctly(self):
        """Module existing in baseline is tagged as EXISTING."""
        baseline = _make_baseline()
        func_graph = _make_func_graph(["auth_service"])
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph, baseline=baseline)

        module_nodes = [
            n for n in rpg.nodes.values()
            if n.level == NodeLevel.MODULE
        ]
        assert len(module_nodes) == 1
        assert module_nodes[0].metadata["delta_status"] == DeltaStatus.EXISTING.value

    def test_new_module_tagged_correctly(self):
        """Module not in baseline is tagged as NEW."""
        baseline = _make_baseline()
        func_graph = _make_func_graph(["brand_new_module"])
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph, baseline=baseline)

        module_nodes = [
            n for n in rpg.nodes.values()
            if n.level == NodeLevel.MODULE
        ]
        assert len(module_nodes) == 1
        assert module_nodes[0].metadata["delta_status"] == DeltaStatus.NEW.value

    def test_has_baseline_metadata(self):
        """RPGGraph metadata includes has_baseline flag."""
        baseline = _make_baseline()
        func_graph = _make_func_graph(["auth_service"])
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph, baseline=baseline)
        assert rpg.metadata.get("has_baseline") is True

    def test_no_baseline_no_metadata_flag(self):
        """RPGGraph metadata does not include has_baseline when no baseline."""
        func_graph = _make_func_graph(["auth_service"])
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph)
        assert "has_baseline" not in rpg.metadata

    def test_mixed_new_and_existing(self):
        """Graph with both new and existing modules tags correctly."""
        baseline = _make_baseline()
        func_graph = _make_func_graph(
            ["auth_service", "api_gateway", "payment_service"]
        )
        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph, baseline=baseline)

        module_statuses = {}
        for node in rpg.nodes.values():
            if node.level == NodeLevel.MODULE:
                module_statuses[node.name] = node.metadata["delta_status"]

        assert module_statuses["auth_service"] == DeltaStatus.EXISTING.value
        assert module_statuses["api_gateway"] == DeltaStatus.EXISTING.value
        assert module_statuses["payment_service"] == DeltaStatus.NEW.value


# ---------------------------------------------------------------------------
# Spec parser baseline context tests
# ---------------------------------------------------------------------------


class TestSpecParserBaselineContext:
    """Tests for SpecParser._build_baseline_context."""

    def test_empty_baseline(self):
        """Empty baseline produces minimal context."""
        baseline = RPGGraph()
        context = SpecParser._build_baseline_context(baseline)
        assert "Existing Codebase Structure" in context
        assert "No modules found in baseline" in context

    def test_baseline_with_modules(self):
        """Baseline with modules includes module names."""
        baseline = _make_baseline()
        context = SpecParser._build_baseline_context(baseline)
        assert "auth_service" in context
        assert "api_gateway" in context

    def test_baseline_includes_features(self):
        """Baseline context includes feature names under modules."""
        baseline = _make_baseline()
        context = SpecParser._build_baseline_context(baseline)
        assert "login handler" in context
        assert "token validator" in context

    def test_baseline_includes_components(self):
        """Baseline context includes component names."""
        baseline = _make_baseline()
        context = SpecParser._build_baseline_context(baseline)
        assert "authentication" in context

    def test_baseline_includes_signatures(self):
        """Baseline context includes function signatures when available."""
        baseline = _make_baseline()
        context = SpecParser._build_baseline_context(baseline)
        assert "def login(" in context or "login(" in context

    def test_baseline_includes_folder_paths(self):
        """Baseline context includes folder paths for modules."""
        baseline = _make_baseline()
        context = SpecParser._build_baseline_context(baseline)
        assert "src/auth" in context

    def test_baseline_context_mentions_delta_instructions(self):
        """Baseline context instructs LLM about existing/modified/new."""
        baseline = _make_baseline()
        context = SpecParser._build_baseline_context(baseline)
        assert "existing" in context.lower()
        assert "modified" in context.lower()
        assert "new" in context.lower()


# ---------------------------------------------------------------------------
# Spec parser parse() baseline parameter tests
# ---------------------------------------------------------------------------


class TestSpecParserBaselineParam:
    """Tests for SpecParser.parse() baseline parameter passthrough."""

    def test_parse_accepts_baseline_none(self):
        """parse() works with baseline=None (default)."""
        # This just tests the signature doesn't raise
        import inspect
        sig = inspect.signature(SpecParser.parse)
        params = sig.parameters
        assert "baseline" in params
        assert params["baseline"].default is None

    def test_parse_signature_has_baseline(self):
        """parse() method signature includes baseline parameter."""
        import inspect
        sig = inspect.signature(SpecParser.parse)
        assert "baseline" in sig.parameters
