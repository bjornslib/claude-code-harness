"""Unit tests for LLM-based delta classification (Waves 1-2).

Tests cover:
1. Model tests: DeltaClassification enum, Component with delta fields
2. Parser tests: ParsedComponent delta fields, _normalize_components passthrough
3. Converter tests: _tag_delta_status_from_llm() with various scenarios
4. Template tests: Conditional baseline classification section rendering
"""

from __future__ import annotations

import pytest

from cobuilder.repomap.graph_construction.converter import FunctionalityGraphConverter
from cobuilder.repomap.llm.prompt_templates import PromptTemplate
from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import (
    DeltaStatus,
    EdgeType,
    NodeLevel,
    NodeType,
)
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.spec_parser.models import (
    Component,
    DeltaClassification,
)
from cobuilder.repomap.spec_parser.parser import (
    ParsedComponent,
    _normalize_components,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    level: NodeLevel = NodeLevel.COMPONENT,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    folder_path: str | None = None,
    file_path: str | None = None,
    signature: str | None = None,
    docstring: str | None = None,
    metadata: dict | None = None,
) -> RPGNode:
    """Create an RPGNode for testing."""
    return RPGNode(
        name=name,
        level=level,
        node_type=node_type,
        folder_path=folder_path,
        file_path=file_path,
        signature=signature,
        docstring=docstring,
        metadata=metadata or {},
    )


def _make_baseline_with_component(
    name: str = "auth_service",
    level: NodeLevel = NodeLevel.COMPONENT,
    folder_path: str = "src/auth",
    file_path: str = "src/auth/service.py",
    signature: str = "class AuthService",
    docstring: str = "Auth service module",
) -> RPGGraph:
    """Create a baseline RPGGraph with a known component."""
    graph = RPGGraph()
    node = _make_node(
        name=name,
        level=level,
        folder_path=folder_path,
        file_path=file_path,
        signature=signature,
        docstring=docstring,
    )
    graph.add_node(node)
    return graph


# ---------------------------------------------------------------------------
# 1. Model Tests: DeltaClassification enum
# ---------------------------------------------------------------------------


class TestDeltaClassificationEnum:
    """Tests for the DeltaClassification enum."""

    def test_enum_values(self):
        """DeltaClassification has existing, modified, and new values."""
        assert DeltaClassification.EXISTING == "existing"
        assert DeltaClassification.MODIFIED == "modified"
        assert DeltaClassification.NEW == "new"

    def test_enum_is_string(self):
        """DeltaClassification values are strings (str, Enum)."""
        assert isinstance(DeltaClassification.EXISTING, str)
        assert isinstance(DeltaClassification.MODIFIED, str)
        assert isinstance(DeltaClassification.NEW, str)

    def test_enum_membership(self):
        """All three statuses are members of DeltaClassification."""
        assert len(DeltaClassification) == 3

    def test_enum_from_value(self):
        """Can create DeltaClassification from string value."""
        assert DeltaClassification("existing") == DeltaClassification.EXISTING
        assert DeltaClassification("modified") == DeltaClassification.MODIFIED
        assert DeltaClassification("new") == DeltaClassification.NEW

    def test_enum_invalid_value_raises(self):
        """Invalid value raises ValueError."""
        with pytest.raises(ValueError):
            DeltaClassification("unknown")


# ---------------------------------------------------------------------------
# 1b. Model Tests: Component with delta fields
# ---------------------------------------------------------------------------


class TestComponentDeltaFields:
    """Tests for Component model with delta classification fields."""

    def test_component_delta_fields_default_none(self):
        """Delta fields default to None for backward compatibility."""
        comp = Component(name="test_component")
        assert comp.delta_status is None
        assert comp.baseline_match_name is None
        assert comp.change_summary is None

    def test_component_with_delta_fields_set(self):
        """Component accepts delta classification fields."""
        comp = Component(
            name="Auth Service",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="auth_service",
            change_summary=None,
        )
        assert comp.delta_status == DeltaClassification.EXISTING
        assert comp.baseline_match_name == "auth_service"
        assert comp.change_summary is None

    def test_component_modified_with_change_summary(self):
        """Modified component carries a change summary."""
        comp = Component(
            name="API Gateway",
            delta_status=DeltaClassification.MODIFIED,
            baseline_match_name="api_gateway",
            change_summary="Added rate limiting and caching",
        )
        assert comp.delta_status == DeltaClassification.MODIFIED
        assert comp.change_summary == "Added rate limiting and caching"

    def test_component_new_with_summary(self):
        """New component can describe new functionality."""
        comp = Component(
            name="Payment Service",
            delta_status=DeltaClassification.NEW,
            baseline_match_name=None,
            change_summary="Stripe payment processing integration",
        )
        assert comp.delta_status == DeltaClassification.NEW
        assert comp.baseline_match_name is None

    def test_component_serialization_with_delta_fields(self):
        """Component with delta fields serializes and deserializes correctly."""
        comp = Component(
            name="Auth Service",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="auth_service",
            change_summary=None,
        )
        data = comp.model_dump(mode="json")
        assert data["delta_status"] == "existing"
        assert data["baseline_match_name"] == "auth_service"
        assert data["change_summary"] is None

        # Roundtrip
        comp2 = Component.model_validate(data)
        assert comp2.delta_status == DeltaClassification.EXISTING
        assert comp2.baseline_match_name == "auth_service"

    def test_component_deserialization_without_delta_fields(self):
        """Component deserializes correctly when delta fields are absent."""
        data = {"name": "legacy_component", "description": "old component"}
        comp = Component.model_validate(data)
        assert comp.delta_status is None
        assert comp.baseline_match_name is None
        assert comp.change_summary is None


# ---------------------------------------------------------------------------
# 2. Parser Tests: ParsedComponent
# ---------------------------------------------------------------------------


class TestParsedComponentDeltaFields:
    """Tests for ParsedComponent accepting delta fields."""

    def test_parsed_component_accepts_delta_fields(self):
        """ParsedComponent accepts delta_status, baseline_match_name, change_summary."""
        pc = ParsedComponent(
            name="Auth Service",
            delta_status="existing",
            baseline_match_name="auth_service",
            change_summary=None,
        )
        assert pc.delta_status == "existing"
        assert pc.baseline_match_name == "auth_service"
        assert pc.change_summary is None

    def test_parsed_component_delta_fields_default_none(self):
        """ParsedComponent delta fields default to None."""
        pc = ParsedComponent(name="Test")
        assert pc.delta_status is None
        assert pc.baseline_match_name is None
        assert pc.change_summary is None

    def test_parsed_component_all_delta_values(self):
        """ParsedComponent accepts all three delta_status values."""
        for status in ["existing", "modified", "new"]:
            pc = ParsedComponent(name="Test", delta_status=status)
            assert pc.delta_status == status


# ---------------------------------------------------------------------------
# 2b. Parser Tests: _normalize_components passthrough
# ---------------------------------------------------------------------------


class TestNormalizeComponentsPassthrough:
    """Tests for _normalize_components() passing delta fields through."""

    def test_passthrough_existing(self):
        """_normalize_components passes through existing delta classification."""
        parsed = [
            ParsedComponent(
                name="Auth Service",
                delta_status="existing",
                baseline_match_name="auth_service",
                change_summary=None,
            )
        ]
        result = _normalize_components(parsed)
        assert len(result) == 1
        assert result[0].delta_status == DeltaClassification.EXISTING
        assert result[0].baseline_match_name == "auth_service"
        assert result[0].change_summary is None

    def test_passthrough_modified(self):
        """_normalize_components passes through modified delta classification."""
        parsed = [
            ParsedComponent(
                name="API Gateway",
                delta_status="modified",
                baseline_match_name="api_gateway",
                change_summary="Added rate limiting",
            )
        ]
        result = _normalize_components(parsed)
        assert len(result) == 1
        assert result[0].delta_status == DeltaClassification.MODIFIED
        assert result[0].baseline_match_name == "api_gateway"
        assert result[0].change_summary == "Added rate limiting"

    def test_passthrough_new(self):
        """_normalize_components passes through new delta classification."""
        parsed = [
            ParsedComponent(
                name="Payment Service",
                delta_status="new",
                baseline_match_name=None,
                change_summary="New payment integration",
            )
        ]
        result = _normalize_components(parsed)
        assert len(result) == 1
        assert result[0].delta_status == DeltaClassification.NEW
        assert result[0].baseline_match_name is None
        assert result[0].change_summary == "New payment integration"

    def test_passthrough_none_delta(self):
        """_normalize_components preserves None delta fields."""
        parsed = [ParsedComponent(name="Legacy Component")]
        result = _normalize_components(parsed)
        assert len(result) == 1
        assert result[0].delta_status is None
        assert result[0].baseline_match_name is None
        assert result[0].change_summary is None

    def test_passthrough_invalid_delta_status(self):
        """Invalid delta_status is ignored (set to None) with warning."""
        parsed = [
            ParsedComponent(
                name="Bad Component",
                delta_status="unknown_status",
            )
        ]
        result = _normalize_components(parsed)
        assert len(result) == 1
        assert result[0].delta_status is None

    def test_passthrough_strips_whitespace(self):
        """Delta fields are stripped of whitespace."""
        parsed = [
            ParsedComponent(
                name="Test",
                delta_status="  existing  ",
                baseline_match_name="  auth_service  ",
                change_summary="  some changes  ",
            )
        ]
        result = _normalize_components(parsed)
        assert result[0].delta_status == DeltaClassification.EXISTING
        assert result[0].baseline_match_name == "auth_service"
        assert result[0].change_summary == "some changes"


# ---------------------------------------------------------------------------
# 3. Converter Tests: _tag_delta_status_from_llm
# ---------------------------------------------------------------------------


class TestTagDeltaStatusFromLLM:
    """Tests for FunctionalityGraphConverter._tag_delta_status_from_llm()."""

    def test_llm_existing_classification(self):
        """LLM classification of EXISTING is used directly."""
        comp = Component(
            name="Auth",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="auth_service",
        )
        baseline = _make_baseline_with_component("auth_service")
        node = _make_node("Auth")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline
        )
        assert node.metadata["delta_status"] == "existing"
        assert node.metadata["delta_source"] == "llm"

    def test_llm_modified_classification(self):
        """LLM classification of MODIFIED is used directly."""
        comp = Component(
            name="API",
            delta_status=DeltaClassification.MODIFIED,
            baseline_match_name="api_gateway",
            change_summary="Added caching",
        )
        node = _make_node("API")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, RPGGraph()
        )
        assert node.metadata["delta_status"] == "modified"
        assert node.metadata["delta_source"] == "llm"
        assert node.metadata["change_summary"] == "Added caching"

    def test_llm_new_classification(self):
        """LLM classification of NEW is used directly."""
        comp = Component(
            name="Payment",
            delta_status=DeltaClassification.NEW,
            change_summary="New payment module",
        )
        node = _make_node("Payment")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, RPGGraph()
        )
        assert node.metadata["delta_status"] == "new"
        assert node.metadata["delta_source"] == "llm"
        assert node.metadata["change_summary"] == "New payment module"

    def test_delta_source_is_llm(self):
        """metadata['delta_source'] is 'llm' when LLM classification used."""
        comp = Component(
            name="Test",
            delta_status=DeltaClassification.NEW,
        )
        node = _make_node("Test")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, RPGGraph()
        )
        assert node.metadata["delta_source"] == "llm"

    def test_no_delta_source_on_fallback(self):
        """metadata has no 'delta_source' when falling back to name matching."""
        comp = Component(name="Brand New")
        node = _make_node("Brand New")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, RPGGraph()
        )
        assert "delta_source" not in node.metadata
        # Falls back to name match -> not found -> NEW
        assert node.metadata["delta_status"] == "new"

    def test_fallback_no_llm_classification(self):
        """Without LLM delta_status, falls back to name matching."""
        comp = Component(name="auth_service")
        baseline = _make_baseline_with_component("auth_service")
        node = _make_node("auth_service")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline
        )
        assert node.metadata["delta_status"] == "existing"
        assert "delta_source" not in node.metadata

    def test_llm_classification_no_baseline(self):
        """LLM classification is applied even without baseline."""
        comp = Component(
            name="Service",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="some_service",
        )
        node = _make_node("Service")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline=None
        )
        assert node.metadata["delta_status"] == "existing"
        assert node.metadata["delta_source"] == "llm"
        # baseline_match_name not stored because baseline is None
        assert "baseline_match_name" not in node.metadata

    def test_baseline_data_enrichment(self):
        """Baseline data is copied when baseline_match_name resolves."""
        comp = Component(
            name="Auth",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="auth_service",
        )
        baseline = _make_baseline_with_component(
            name="auth_service",
            folder_path="src/auth",
            file_path="src/auth/service.py",
            signature="class AuthService",
            docstring="Auth service module",
        )
        node = _make_node("Auth")
        assert node.folder_path is None
        assert node.file_path is None

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline
        )
        assert node.folder_path == "src/auth"
        assert node.file_path == "src/auth/service.py"
        assert node.signature == "class AuthService"
        assert node.docstring == "Auth service module"
        assert "baseline_node_id" in node.metadata

    def test_baseline_data_not_overwritten(self):
        """Existing node data is not overwritten by baseline data."""
        comp = Component(
            name="Auth",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="auth_service",
        )
        baseline = _make_baseline_with_component(
            name="auth_service",
            folder_path="src/auth",
            signature="class AuthService",
        )
        node = _make_node(
            "Auth",
            folder_path="src/new_auth",
            file_path="src/new_auth/main.py",
            signature="class NewAuth",
        )

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline
        )
        # Node's own data preserved
        assert node.folder_path == "src/new_auth"
        assert node.file_path == "src/new_auth/main.py"
        assert node.signature == "class NewAuth"

    def test_no_baseline_no_delta_no_metadata(self):
        """No baseline + no delta_status -> no delta metadata set."""
        comp = Component(name="test")
        node = _make_node("test")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline=None
        )
        assert "delta_status" not in node.metadata
        assert "delta_source" not in node.metadata

    def test_backward_compat_plain_object(self):
        """Works with plain objects without delta attributes."""

        class PlainComp:
            name = "test"
            description = "desc"

        node = _make_node("test")
        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, PlainComp(), RPGGraph()
        )
        # Falls back to name matching -> not found -> NEW
        assert node.metadata["delta_status"] == "new"
        assert "delta_source" not in node.metadata

    def test_baseline_match_name_stored_in_metadata(self):
        """baseline_match_name is stored in node metadata."""
        comp = Component(
            name="Auth",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="auth_service",
        )
        baseline = _make_baseline_with_component("auth_service")
        node = _make_node("Auth")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline
        )
        assert node.metadata["baseline_match_name"] == "auth_service"

    def test_change_summary_not_stored_when_none(self):
        """change_summary is not stored when it is None."""
        comp = Component(
            name="Auth",
            delta_status=DeltaClassification.EXISTING,
            change_summary=None,
        )
        node = _make_node("Auth")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, RPGGraph()
        )
        assert "change_summary" not in node.metadata

    def test_unresolved_baseline_match_name(self):
        """When baseline_match_name doesn't resolve, no enrichment happens."""
        comp = Component(
            name="Auth",
            delta_status=DeltaClassification.EXISTING,
            baseline_match_name="nonexistent_service",
        )
        baseline = _make_baseline_with_component("auth_service")
        node = _make_node("Auth")

        FunctionalityGraphConverter._tag_delta_status_from_llm(
            node, comp, baseline
        )
        assert node.metadata["delta_status"] == "existing"
        assert node.metadata["baseline_match_name"] == "nonexistent_service"
        assert "baseline_node_id" not in node.metadata
        assert node.folder_path is None  # No enrichment


# ---------------------------------------------------------------------------
# 4. Template Tests: Conditional baseline section
# ---------------------------------------------------------------------------


class TestTemplateBaselineSection:
    """Tests for spec_parsing.jinja2 baseline classification section."""

    def test_renders_baseline_section_when_true(self):
        """Template renders baseline classification section when has_baseline=True."""
        pt = PromptTemplate()
        prompt = pt.render(
            "spec_parsing",
            description="Build a chat app",
            context="",
            has_baseline=True,
        )
        assert "Baseline-Aware Delta Classification" in prompt
        assert "delta_status" in prompt
        assert "baseline_match_name" in prompt
        assert "change_summary" in prompt
        assert "Classification Rules" in prompt

    def test_no_baseline_section_when_false(self):
        """Template does NOT render baseline section when has_baseline=False."""
        pt = PromptTemplate()
        prompt = pt.render(
            "spec_parsing",
            description="Build a chat app",
            context="",
            has_baseline=False,
        )
        assert "Baseline-Aware Delta Classification" not in prompt

    def test_no_baseline_section_when_undefined(self):
        """Template does NOT render baseline section when has_baseline is not passed."""
        pt = PromptTemplate()
        prompt = pt.render(
            "spec_parsing",
            description="Build a chat app",
            context="",
        )
        assert "Baseline-Aware Delta Classification" not in prompt

    def test_baseline_section_contains_classification_rules(self):
        """Baseline section includes all 5 classification rules."""
        pt = PromptTemplate()
        prompt = pt.render(
            "spec_parsing",
            description="Build a chat app",
            context="",
            has_baseline=True,
        )
        assert "Copy baseline node names EXACTLY" in prompt
        assert "Prefer mapping to existing components" in prompt
        assert 'Only classify as "new"' in prompt

    def test_component_schema_includes_delta_fields(self):
        """Component schema in template documents the delta fields."""
        pt = PromptTemplate()
        prompt = pt.render(
            "spec_parsing",
            description="Build a chat app",
            context="",
            has_baseline=False,
        )
        # These appear in the schema docs regardless of has_baseline
        assert '"delta_status"' in prompt
        assert '"baseline_match_name"' in prompt
        assert '"change_summary"' in prompt
        assert "(only when baseline provided)" in prompt

    def test_respond_only_line_preserved(self):
        """The 'Respond ONLY with valid JSON' line is still present."""
        pt = PromptTemplate()
        prompt = pt.render(
            "spec_parsing",
            description="Build a chat app",
            context="",
            has_baseline=True,
        )
        assert "Respond ONLY with valid JSON" in prompt
