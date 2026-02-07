"""Unit tests for the NLP-based Specification Parser (Task 2.4.2).

Tests cover:
- ParserConfig defaults and custom configuration
- ParsedConstraint and ParsedSpecResponse intermediate models
- SpecParser initialization (defaults, custom config, injected deps)
- parse() input validation (too short, too long, whitespace handling)
- _call_llm with and without JSON mode
- _parse_response with valid JSON, markdown fences, and invalid JSON
- _assemble_spec with various ParsedSpecResponse combinations
- Normalization helpers (deployment targets, scope, constraints, priorities)
- Full parse pipeline with mocked LLMGateway
- SpecParserError exception class
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.llm.models import ModelTier
from zerorepo.spec_parser.models import (
    Constraint,
    ConstraintPriority,
    DeploymentTarget,
    QualityAttributes,
    RepositorySpec,
    ScopeType,
    TechnicalRequirement,
)
from zerorepo.spec_parser.parser import (
    ParsedConstraint,
    ParsedSpecResponse,
    ParserConfig,
    SpecParser,
    SpecParserError,
    _normalize_constraint_priority,
    _normalize_constraints,
    _normalize_deployment_targets,
    _normalize_scope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_gateway(response_json: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock LLMGateway that returns the given JSON dict as a string."""
    if response_json is None:
        response_json = {
            "core_functionality": "A real-time chat application",
            "languages": ["Python", "TypeScript"],
            "frameworks": ["FastAPI", "React"],
            "platforms": ["Web"],
            "deployment_targets": ["CLOUD"],
            "scope": "FULL_STACK",
            "performance": "Must support 10K concurrent users",
            "security": "OAuth2 required",
            "scalability": None,
            "reliability": None,
            "maintainability": None,
            "constraints": [
                {
                    "description": "Must use WebSocket for real-time",
                    "priority": "MUST_HAVE",
                    "category": "architecture",
                },
            ],
        }
    gateway = MagicMock()
    gateway.complete.return_value = json.dumps(response_json)
    return gateway


def _make_mock_templates(rendered_text: str = "rendered prompt") -> MagicMock:
    """Create a mock PromptTemplate."""
    templates = MagicMock()
    templates.render.return_value = rendered_text
    return templates


def _default_description() -> str:
    """Return a valid description for parse() tests."""
    return (
        "Build a real-time chat application with React, WebSocket, "
        "and PostgreSQL. Must support 10K concurrent users."
    )


# ===========================================================================
# ParserConfig Tests
# ===========================================================================


class TestParserConfig:
    """Tests for the ParserConfig Pydantic model."""

    def test_default_values(self) -> None:
        """ParserConfig should have sensible defaults."""
        config = ParserConfig()
        assert config.model == "gpt-5.2"
        assert config.tier == ModelTier.CHEAP
        assert config.template_name == "spec_parsing"
        assert config.max_description_length == 50000
        assert config.use_json_mode is True

    def test_custom_values(self) -> None:
        """ParserConfig should accept custom values."""
        config = ParserConfig(
            model="gpt-4o",
            tier=ModelTier.STRONG,
            template_name="custom_template",
            max_description_length=10000,
            use_json_mode=False,
        )
        assert config.model == "gpt-4o"
        assert config.tier == ModelTier.STRONG
        assert config.template_name == "custom_template"
        assert config.max_description_length == 10000
        assert config.use_json_mode is False

    def test_max_description_length_must_be_positive(self) -> None:
        """max_description_length must be > 0."""
        with pytest.raises(Exception):
            ParserConfig(max_description_length=0)

    def test_mutable_assignment(self) -> None:
        """ParserConfig should allow field reassignment (frozen=False)."""
        config = ParserConfig()
        config.model = "gpt-4o"
        assert config.model == "gpt-4o"

    def test_validate_assignment(self) -> None:
        """Assignment validation should reject invalid values."""
        config = ParserConfig()
        with pytest.raises(Exception):
            config.max_description_length = -1


# ===========================================================================
# ParsedConstraint Tests
# ===========================================================================


class TestParsedConstraint:
    """Tests for the ParsedConstraint intermediate model."""

    def test_default_values(self) -> None:
        """ParsedConstraint defaults: empty description, SHOULD_HAVE priority."""
        pc = ParsedConstraint()
        assert pc.description == ""
        assert pc.priority == "SHOULD_HAVE"
        assert pc.category is None

    def test_custom_values(self) -> None:
        """ParsedConstraint with custom values."""
        pc = ParsedConstraint(
            description="Must use TLS",
            priority="MUST_HAVE",
            category="security",
        )
        assert pc.description == "Must use TLS"
        assert pc.priority == "MUST_HAVE"
        assert pc.category == "security"

    def test_whitespace_stripping(self) -> None:
        """str_strip_whitespace should strip leading/trailing whitespace."""
        pc = ParsedConstraint(description="  padded  ", priority="  MUST_HAVE  ")
        assert pc.description == "padded"
        assert pc.priority == "MUST_HAVE"


# ===========================================================================
# ParsedSpecResponse Tests
# ===========================================================================


class TestParsedSpecResponse:
    """Tests for the ParsedSpecResponse intermediate model."""

    def test_default_values(self) -> None:
        """All fields should have sensible defaults."""
        psr = ParsedSpecResponse()
        assert psr.core_functionality is None
        assert psr.languages == []
        assert psr.frameworks == []
        assert psr.platforms == []
        assert psr.deployment_targets == []
        assert psr.scope is None
        assert psr.performance is None
        assert psr.security is None
        assert psr.scalability is None
        assert psr.reliability is None
        assert psr.maintainability is None
        assert psr.constraints == []

    def test_full_population(self) -> None:
        """ParsedSpecResponse with all fields populated."""
        psr = ParsedSpecResponse(
            core_functionality="Chat app",
            languages=["Python"],
            frameworks=["FastAPI"],
            platforms=["Linux"],
            deployment_targets=["CLOUD"],
            scope="BACKEND_ONLY",
            performance="< 100ms",
            security="OAuth2",
            scalability="horizontal",
            reliability="99.9%",
            maintainability="modular",
            constraints=[
                ParsedConstraint(description="test", priority="MUST_HAVE"),
            ],
        )
        assert psr.core_functionality == "Chat app"
        assert len(psr.languages) == 1
        assert len(psr.constraints) == 1

    def test_model_validate_from_dict(self) -> None:
        """ParsedSpecResponse should validate from a raw dict."""
        data = {
            "core_functionality": "API server",
            "languages": ["Go", "Python"],
            "frameworks": [],
            "constraints": [{"description": "Must be fast", "priority": "MUST_HAVE"}],
        }
        psr = ParsedSpecResponse.model_validate(data)
        assert psr.core_functionality == "API server"
        assert len(psr.languages) == 2
        assert psr.constraints[0].description == "Must be fast"

    def test_extra_fields_ignored(self) -> None:
        """Extra fields from LLM output should not cause errors."""
        data = {
            "core_functionality": "Test",
            "extra_field": "should be fine",
        }
        # ParsedSpecResponse uses default ConfigDict which allows extra by default
        # or ignores gracefully - verify it doesn't raise
        psr = ParsedSpecResponse.model_validate(data)
        assert psr.core_functionality == "Test"


# ===========================================================================
# SpecParser Initialization Tests
# ===========================================================================


class TestSpecParserInit:
    """Tests for SpecParser initialization."""

    def test_default_initialization(self) -> None:
        """SpecParser with no args should use defaults."""
        # We need to mock LLMGateway since it requires litellm
        mock_gw = MagicMock()
        mock_tpl = MagicMock()
        parser = SpecParser(gateway=mock_gw, templates=mock_tpl)
        assert isinstance(parser.config, ParserConfig)
        assert parser.gateway is mock_gw
        assert parser.templates is mock_tpl

    def test_custom_config(self) -> None:
        """SpecParser with custom config."""
        config = ParserConfig(model="gpt-4o", tier=ModelTier.STRONG)
        parser = SpecParser(
            config=config,
            gateway=MagicMock(),
            templates=MagicMock(),
        )
        assert parser.config.model == "gpt-4o"
        assert parser.config.tier == ModelTier.STRONG

    def test_injected_gateway(self) -> None:
        """SpecParser should use injected gateway."""
        gw = MagicMock()
        parser = SpecParser(gateway=gw, templates=MagicMock())
        assert parser.gateway is gw

    def test_injected_templates(self) -> None:
        """SpecParser should use injected PromptTemplate."""
        tpl = MagicMock()
        parser = SpecParser(gateway=MagicMock(), templates=tpl)
        assert parser.templates is tpl


# ===========================================================================
# parse() Input Validation Tests
# ===========================================================================


class TestParseInputValidation:
    """Tests for parse() description validation."""

    def _make_parser(self, **config_kwargs: Any) -> SpecParser:
        """Helper to create a parser with mocked dependencies."""
        config = ParserConfig(**config_kwargs) if config_kwargs else None
        return SpecParser(
            config=config,
            gateway=_make_mock_gateway(),
            templates=_make_mock_templates(),
        )

    def test_description_too_short(self) -> None:
        """parse() should reject descriptions < 10 chars."""
        parser = self._make_parser()
        with pytest.raises(ValueError, match="at least 10 characters"):
            parser.parse("short")

    def test_description_exactly_10_chars(self) -> None:
        """A 10-character description should not raise ValueError for length."""
        parser = self._make_parser()
        # "1234567890" is exactly 10 chars; the RepositorySpec validator requires
        # at least 3 words, so use a 10+ char string with multiple words
        desc = "build app now"  # 13 chars, 3 words
        result = parser.parse(desc)
        assert isinstance(result, RepositorySpec)

    def test_description_too_long(self) -> None:
        """parse() should reject descriptions exceeding max_description_length."""
        parser = self._make_parser(max_description_length=50)
        long_desc = "Build a real-time chat with React and WebSocket features " * 5
        with pytest.raises(ValueError, match="exceeds maximum length"):
            parser.parse(long_desc)

    def test_description_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be stripped before length check."""
        parser = self._make_parser()
        # Whitespace-padded but content is < 10 chars after strip
        with pytest.raises(ValueError, match="at least 10 characters"):
            parser.parse("   tiny    ")

    def test_valid_description_passes(self) -> None:
        """A valid description should proceed through the full pipeline."""
        parser = self._make_parser()
        result = parser.parse(_default_description())
        assert isinstance(result, RepositorySpec)

    def test_description_at_max_length(self) -> None:
        """Description exactly at max_description_length should be accepted."""
        # Create a description that is exactly at the limit
        words = "a " * 25  # 50 chars
        parser = self._make_parser(max_description_length=50)
        result = parser.parse(words.strip())
        assert isinstance(result, RepositorySpec)


# ===========================================================================
# _call_llm Tests
# ===========================================================================


class TestCallLLM:
    """Tests for SpecParser._call_llm method."""

    def test_json_mode_enabled(self) -> None:
        """When use_json_mode=True, response_format should be passed to gateway."""
        gw = MagicMock()
        gw.complete.return_value = '{"core_functionality": null}'
        config = ParserConfig(use_json_mode=True)
        parser = SpecParser(config=config, gateway=gw, templates=MagicMock())

        messages = [{"role": "user", "content": "test"}]
        parser._call_llm(messages)

        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args
        assert call_kwargs.kwargs.get("response_format") == {"type": "json_object"}

    def test_json_mode_disabled(self) -> None:
        """When use_json_mode=False, response_format should NOT be passed."""
        gw = MagicMock()
        gw.complete.return_value = '{"core_functionality": null}'
        config = ParserConfig(use_json_mode=False)
        parser = SpecParser(config=config, gateway=gw, templates=MagicMock())

        messages = [{"role": "user", "content": "test"}]
        parser._call_llm(messages)

        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args
        assert "response_format" not in call_kwargs.kwargs

    def test_model_and_tier_passed(self) -> None:
        """_call_llm should pass config.model and config.tier to gateway."""
        gw = MagicMock()
        gw.complete.return_value = "{}"
        config = ParserConfig(model="gpt-4o", tier=ModelTier.STRONG)
        parser = SpecParser(config=config, gateway=gw, templates=MagicMock())

        parser._call_llm([{"role": "user", "content": "test"}])

        gw.complete.assert_called_once_with(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o",
            tier=ModelTier.STRONG,
            temperature=0,
            response_format={"type": "json_object"},
        )


# ===========================================================================
# _parse_response Tests
# ===========================================================================


class TestParseResponse:
    """Tests for SpecParser._parse_response method."""

    def _parser(self) -> SpecParser:
        return SpecParser(gateway=MagicMock(), templates=MagicMock())

    def test_valid_json(self) -> None:
        """Clean JSON should be parsed into ParsedSpecResponse."""
        parser = self._parser()
        raw = json.dumps({
            "core_functionality": "Chat app",
            "languages": ["Python"],
        })
        result = parser._parse_response(raw)
        assert isinstance(result, ParsedSpecResponse)
        assert result.core_functionality == "Chat app"
        assert result.languages == ["Python"]

    def test_json_with_markdown_fences(self) -> None:
        """JSON wrapped in ```json ... ``` should be parsed."""
        parser = self._parser()
        inner = json.dumps({"core_functionality": "API server", "languages": ["Go"]})
        raw = f"```json\n{inner}\n```"
        result = parser._parse_response(raw)
        assert result.core_functionality == "API server"
        assert result.languages == ["Go"]

    def test_json_with_plain_fences(self) -> None:
        """JSON wrapped in ``` ... ``` (no language tag) should be parsed."""
        parser = self._parser()
        inner = json.dumps({"core_functionality": "CLI tool"})
        raw = f"```\n{inner}\n```"
        result = parser._parse_response(raw)
        assert result.core_functionality == "CLI tool"

    def test_invalid_json_raises_spec_parser_error(self) -> None:
        """Non-JSON text should raise SpecParserError."""
        parser = self._parser()
        with pytest.raises(SpecParserError, match="not valid JSON"):
            parser._parse_response("This is not JSON at all")

    def test_invalid_schema_raises_spec_parser_error(self) -> None:
        """JSON that doesn't match ParsedSpecResponse should raise SpecParserError."""
        parser = self._parser()
        # constraints expects a list of objects, not a string
        raw = json.dumps({"constraints": "not a list"})
        with pytest.raises(SpecParserError, match="does not match expected schema"):
            parser._parse_response(raw)

    def test_empty_json_object(self) -> None:
        """Empty JSON object {} should parse to defaults."""
        parser = self._parser()
        result = parser._parse_response("{}")
        assert result.core_functionality is None
        assert result.languages == []
        assert result.constraints == []

    def test_whitespace_padded_json(self) -> None:
        """JSON with leading/trailing whitespace should be handled."""
        parser = self._parser()
        raw = "   \n  {\"core_functionality\": \"padded\"}  \n  "
        result = parser._parse_response(raw)
        assert result.core_functionality == "padded"

    def test_response_preview_in_error(self) -> None:
        """SpecParserError should include a preview of the bad response."""
        parser = self._parser()
        bad_response = "x" * 300  # Longer than 200 char preview
        with pytest.raises(SpecParserError, match="Response preview"):
            parser._parse_response(bad_response)


# ===========================================================================
# _assemble_spec Tests
# ===========================================================================


class TestAssembleSpec:
    """Tests for SpecParser._assemble_spec method."""

    def _parser(self) -> SpecParser:
        return SpecParser(gateway=MagicMock(), templates=MagicMock())

    def test_minimal_parsed_response(self) -> None:
        """Minimal ParsedSpecResponse should produce a valid RepositorySpec."""
        parser = self._parser()
        parsed = ParsedSpecResponse()
        desc = "Build a minimal test application"
        spec = parser._assemble_spec(desc, parsed)
        assert isinstance(spec, RepositorySpec)
        assert spec.description == desc
        assert spec.core_functionality is None
        assert spec.technical_requirements.languages == []
        assert spec.constraints == []

    def test_full_parsed_response(self) -> None:
        """Fully populated ParsedSpecResponse should assemble correctly."""
        parser = self._parser()
        parsed = ParsedSpecResponse(
            core_functionality="Real-time messaging platform",
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI", "React"],
            platforms=["Web", "Linux"],
            deployment_targets=["CLOUD", "SERVERLESS"],
            scope="FULL_STACK",
            performance="< 100ms p95 latency",
            security="OAuth2 with RBAC",
            scalability="horizontal auto-scaling",
            reliability="99.9% uptime SLA",
            maintainability="modular microservices",
            constraints=[
                ParsedConstraint(
                    description="Must use WebSocket",
                    priority="MUST_HAVE",
                    category="architecture",
                ),
                ParsedConstraint(
                    description="Should support dark mode",
                    priority="NICE_TO_HAVE",
                    category="ui",
                ),
            ],
        )
        desc = "Build a real-time messaging platform with FastAPI and React"
        spec = parser._assemble_spec(desc, parsed)

        assert spec.core_functionality == "Real-time messaging platform"
        assert spec.technical_requirements.languages == ["Python", "TypeScript"]
        assert spec.technical_requirements.frameworks == ["FastAPI", "React"]
        assert spec.technical_requirements.platforms == ["Web", "Linux"]
        assert len(spec.technical_requirements.deployment_targets) == 2
        assert DeploymentTarget.CLOUD in spec.technical_requirements.deployment_targets
        assert DeploymentTarget.SERVERLESS in spec.technical_requirements.deployment_targets
        assert spec.technical_requirements.scope == ScopeType.FULL_STACK
        assert spec.quality_attributes.performance == "< 100ms p95 latency"
        assert spec.quality_attributes.security == "OAuth2 with RBAC"
        assert spec.quality_attributes.scalability == "horizontal auto-scaling"
        assert spec.quality_attributes.reliability == "99.9% uptime SLA"
        assert spec.quality_attributes.maintainability == "modular microservices"
        assert len(spec.constraints) == 2
        assert spec.constraints[0].description == "Must use WebSocket"
        assert spec.constraints[0].priority == ConstraintPriority.MUST_HAVE
        assert spec.constraints[0].category == "architecture"
        assert spec.constraints[1].priority == ConstraintPriority.NICE_TO_HAVE

    def test_unknown_deployment_target_maps_to_other(self) -> None:
        """Unknown deployment target strings should map to OTHER."""
        parser = self._parser()
        parsed = ParsedSpecResponse(deployment_targets=["QUANTUM_CLOUD", "CLOUD"])
        spec = parser._assemble_spec("Build a futuristic test application", parsed)
        assert spec.technical_requirements.deployment_targets[0] == DeploymentTarget.OTHER
        assert spec.technical_requirements.deployment_targets[1] == DeploymentTarget.CLOUD

    def test_scope_synonym_mapping(self) -> None:
        """Scope synonyms like 'backend' should map correctly."""
        parser = self._parser()
        parsed = ParsedSpecResponse(scope="backend")
        spec = parser._assemble_spec("Build a backend test application", parsed)
        assert spec.technical_requirements.scope == ScopeType.BACKEND_ONLY

    def test_scope_none(self) -> None:
        """None scope should remain None."""
        parser = self._parser()
        parsed = ParsedSpecResponse(scope=None)
        spec = parser._assemble_spec("Build a test application here", parsed)
        assert spec.technical_requirements.scope is None

    def test_empty_constraints_filtered(self) -> None:
        """Constraints with empty descriptions should be filtered out."""
        parser = self._parser()
        parsed = ParsedSpecResponse(
            constraints=[
                ParsedConstraint(description="Valid constraint", priority="MUST_HAVE"),
                ParsedConstraint(description="", priority="SHOULD_HAVE"),
                ParsedConstraint(description="   ", priority="NICE_TO_HAVE"),
            ]
        )
        spec = parser._assemble_spec("Build a test application here", parsed)
        assert len(spec.constraints) == 1
        assert spec.constraints[0].description == "Valid constraint"

    def test_quality_attributes_none_fields(self) -> None:
        """None quality attributes should pass through."""
        parser = self._parser()
        parsed = ParsedSpecResponse(
            performance=None,
            security=None,
            scalability=None,
            reliability=None,
            maintainability=None,
        )
        spec = parser._assemble_spec("Build a simple test application", parsed)
        assert spec.quality_attributes.performance is None
        assert spec.quality_attributes.security is None
        assert not spec.quality_attributes.has_any


# ===========================================================================
# Normalization Helper Tests
# ===========================================================================


class TestNormalizeDeploymentTargets:
    """Tests for _normalize_deployment_targets helper."""

    def test_exact_match(self) -> None:
        """Exact enum values should map directly."""
        result = _normalize_deployment_targets(["CLOUD", "SERVERLESS", "EDGE"])
        assert result == [
            DeploymentTarget.CLOUD,
            DeploymentTarget.SERVERLESS,
            DeploymentTarget.EDGE,
        ]

    def test_case_insensitive(self) -> None:
        """Lowercase and mixed case should normalize correctly."""
        result = _normalize_deployment_targets(["cloud", "Cloud", "CLOUD"])
        assert all(t == DeploymentTarget.CLOUD for t in result)

    def test_space_and_dash_normalization(self) -> None:
        """Spaces and dashes should be converted to underscores."""
        result = _normalize_deployment_targets(["on premises", "on-premises"])
        assert all(t == DeploymentTarget.ON_PREMISES for t in result)

    def test_unknown_targets_map_to_other(self) -> None:
        """Unknown strings should map to DeploymentTarget.OTHER."""
        result = _normalize_deployment_targets(["QUANTUM", "MARS_COLONY"])
        assert all(t == DeploymentTarget.OTHER for t in result)

    def test_empty_list(self) -> None:
        """Empty input should return empty output."""
        assert _normalize_deployment_targets([]) == []

    def test_whitespace_padded(self) -> None:
        """Whitespace-padded strings should normalize correctly."""
        result = _normalize_deployment_targets(["  CLOUD  ", "  EDGE  "])
        assert result == [DeploymentTarget.CLOUD, DeploymentTarget.EDGE]

    def test_hybrid(self) -> None:
        """HYBRID should be a valid deployment target."""
        result = _normalize_deployment_targets(["hybrid"])
        assert result == [DeploymentTarget.HYBRID]


class TestNormalizeScope:
    """Tests for _normalize_scope helper."""

    def test_none_returns_none(self) -> None:
        """None input should return None."""
        assert _normalize_scope(None) is None

    def test_exact_match(self) -> None:
        """Exact enum values should map directly."""
        assert _normalize_scope("BACKEND_ONLY") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("FULL_STACK") == ScopeType.FULL_STACK
        assert _normalize_scope("LIBRARY") == ScopeType.LIBRARY
        assert _normalize_scope("CLI_TOOL") == ScopeType.CLI_TOOL

    def test_case_insensitive(self) -> None:
        """Lowercase scope should normalize correctly."""
        assert _normalize_scope("backend_only") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("Full_Stack") == ScopeType.FULL_STACK

    def test_synonym_backend(self) -> None:
        """'backend' synonym should map to BACKEND_ONLY."""
        assert _normalize_scope("backend") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("BACKEND") == ScopeType.BACKEND_ONLY

    def test_synonym_frontend(self) -> None:
        """'frontend' synonym should map to FRONTEND_ONLY."""
        assert _normalize_scope("frontend") == ScopeType.FRONTEND_ONLY

    def test_synonym_fullstack(self) -> None:
        """'fullstack' and 'full-stack' synonyms should map to FULL_STACK."""
        assert _normalize_scope("fullstack") == ScopeType.FULL_STACK
        assert _normalize_scope("full-stack") == ScopeType.FULL_STACK

    def test_synonym_lib(self) -> None:
        """'lib' synonym should map to LIBRARY."""
        assert _normalize_scope("lib") == ScopeType.LIBRARY

    def test_synonym_cli(self) -> None:
        """'cli' and 'command_line' synonyms should map to CLI_TOOL."""
        assert _normalize_scope("cli") == ScopeType.CLI_TOOL
        assert _normalize_scope("command_line") == ScopeType.CLI_TOOL

    def test_unknown_scope_maps_to_other(self) -> None:
        """Unknown scope strings should map to OTHER."""
        assert _normalize_scope("microkernel") == ScopeType.OTHER
        assert _normalize_scope("embedded") == ScopeType.OTHER

    def test_whitespace_padded(self) -> None:
        """Whitespace-padded scope should normalize correctly."""
        assert _normalize_scope("  LIBRARY  ") == ScopeType.LIBRARY


class TestNormalizeConstraintPriority:
    """Tests for _normalize_constraint_priority helper."""

    def test_exact_match(self) -> None:
        """Exact enum values should map directly."""
        assert _normalize_constraint_priority("MUST_HAVE") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("SHOULD_HAVE") == ConstraintPriority.SHOULD_HAVE
        assert _normalize_constraint_priority("NICE_TO_HAVE") == ConstraintPriority.NICE_TO_HAVE

    def test_case_insensitive(self) -> None:
        """Lowercase priorities should normalize."""
        assert _normalize_constraint_priority("must_have") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("nice_to_have") == ConstraintPriority.NICE_TO_HAVE

    def test_synonym_required(self) -> None:
        """'required' and 'mandatory' should map to MUST_HAVE."""
        assert _normalize_constraint_priority("required") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("mandatory") == ConstraintPriority.MUST_HAVE

    def test_synonym_important(self) -> None:
        """'important' should map to SHOULD_HAVE."""
        assert _normalize_constraint_priority("important") == ConstraintPriority.SHOULD_HAVE

    def test_synonym_optional(self) -> None:
        """'optional' should map to NICE_TO_HAVE."""
        assert _normalize_constraint_priority("optional") == ConstraintPriority.NICE_TO_HAVE

    def test_unknown_defaults_to_should_have(self) -> None:
        """Unknown priority strings should default to SHOULD_HAVE."""
        assert _normalize_constraint_priority("critical") == ConstraintPriority.SHOULD_HAVE
        assert _normalize_constraint_priority("low") == ConstraintPriority.SHOULD_HAVE

    def test_whitespace_padded(self) -> None:
        """Whitespace-padded priorities should normalize."""
        assert _normalize_constraint_priority("  MUST_HAVE  ") == ConstraintPriority.MUST_HAVE

    def test_space_and_dash_normalization(self) -> None:
        """Spaces and dashes in priority strings should be normalized."""
        assert _normalize_constraint_priority("must have") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("nice-to-have") == ConstraintPriority.NICE_TO_HAVE
        assert _normalize_constraint_priority("should have") == ConstraintPriority.SHOULD_HAVE


class TestNormalizeConstraints:
    """Tests for _normalize_constraints helper."""

    def test_valid_constraints(self) -> None:
        """Valid constraints should be normalized."""
        raw = [
            ParsedConstraint(
                description="Use TLS",
                priority="MUST_HAVE",
                category="security",
            ),
            ParsedConstraint(
                description="Support dark mode",
                priority="optional",
                category="ui",
            ),
        ]
        result = _normalize_constraints(raw)
        assert len(result) == 2
        assert isinstance(result[0], Constraint)
        assert result[0].description == "Use TLS"
        assert result[0].priority == ConstraintPriority.MUST_HAVE
        assert result[0].category == "security"
        assert result[1].priority == ConstraintPriority.NICE_TO_HAVE

    def test_empty_descriptions_filtered(self) -> None:
        """Constraints with empty/whitespace-only descriptions should be skipped."""
        raw = [
            ParsedConstraint(description="Valid", priority="MUST_HAVE"),
            ParsedConstraint(description="", priority="MUST_HAVE"),
            ParsedConstraint(description="   ", priority="MUST_HAVE"),
        ]
        result = _normalize_constraints(raw)
        assert len(result) == 1
        assert result[0].description == "Valid"

    def test_empty_list(self) -> None:
        """Empty input should return empty output."""
        assert _normalize_constraints([]) == []

    def test_category_preserved(self) -> None:
        """Category from ParsedConstraint should be preserved."""
        raw = [
            ParsedConstraint(
                description="Test",
                priority="SHOULD_HAVE",
                category="testing",
            ),
        ]
        result = _normalize_constraints(raw)
        assert result[0].category == "testing"

    def test_none_category(self) -> None:
        """None category should be preserved."""
        raw = [ParsedConstraint(description="Test", priority="SHOULD_HAVE")]
        result = _normalize_constraints(raw)
        assert result[0].category is None


# ===========================================================================
# Full Pipeline Tests (parse with mocked LLM)
# ===========================================================================


class TestFullParsePipeline:
    """Integration-like tests for the full parse() pipeline with mocked LLM."""

    def _make_parser(
        self,
        response_json: dict[str, Any] | None = None,
        config: ParserConfig | None = None,
    ) -> SpecParser:
        """Create a parser with mocked gateway and templates."""
        return SpecParser(
            config=config,
            gateway=_make_mock_gateway(response_json),
            templates=_make_mock_templates(),
        )

    def test_basic_parse(self) -> None:
        """Full pipeline: description -> RepositorySpec."""
        parser = self._make_parser()
        spec = parser.parse(_default_description())

        assert isinstance(spec, RepositorySpec)
        assert spec.description == _default_description()
        assert spec.core_functionality == "A real-time chat application"
        assert "Python" in spec.technical_requirements.languages
        assert "TypeScript" in spec.technical_requirements.languages
        assert "FastAPI" in spec.technical_requirements.frameworks
        assert "React" in spec.technical_requirements.frameworks
        assert DeploymentTarget.CLOUD in spec.technical_requirements.deployment_targets
        assert spec.technical_requirements.scope == ScopeType.FULL_STACK
        assert spec.quality_attributes.performance is not None
        assert spec.quality_attributes.security is not None
        assert len(spec.constraints) == 1
        assert spec.constraints[0].priority == ConstraintPriority.MUST_HAVE

    def test_template_rendering_called(self) -> None:
        """parse() should render the template with description and context."""
        tpl = _make_mock_templates()
        gw = _make_mock_gateway()
        parser = SpecParser(gateway=gw, templates=tpl)

        parser.parse(_default_description(), context="Extra context here")

        tpl.render.assert_called_once_with(
            "spec_parsing",
            description=_default_description(),
            context="Extra context here",
            has_baseline=False,
        )

    def test_context_defaults_to_empty_string(self) -> None:
        """When context is None, empty string should be passed to template."""
        tpl = _make_mock_templates()
        gw = _make_mock_gateway()
        parser = SpecParser(gateway=gw, templates=tpl)

        parser.parse(_default_description())

        tpl.render.assert_called_once_with(
            "spec_parsing",
            description=_default_description(),
            context="",
            has_baseline=False,
        )

    def test_gateway_complete_called(self) -> None:
        """parse() should call gateway.complete with rendered prompt."""
        gw = _make_mock_gateway()
        tpl = _make_mock_templates("Hello LLM prompt")
        parser = SpecParser(gateway=gw, templates=tpl)

        parser.parse(_default_description())

        gw.complete.assert_called_once()
        call_args = gw.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello LLM prompt"

    def test_minimal_llm_response(self) -> None:
        """Minimal LLM response (empty JSON) should produce valid spec."""
        parser = self._make_parser(response_json={})
        spec = parser.parse(_default_description())
        assert isinstance(spec, RepositorySpec)
        assert spec.core_functionality is None
        assert spec.technical_requirements.languages == []
        assert spec.constraints == []

    def test_rich_llm_response(self) -> None:
        """Rich LLM response with all fields populated."""
        response = {
            "core_functionality": "E-commerce platform",
            "languages": ["Python", "JavaScript", "SQL"],
            "frameworks": ["Django", "React", "PostgreSQL"],
            "platforms": ["Web", "Mobile"],
            "deployment_targets": ["CLOUD", "SERVERLESS"],
            "scope": "FULL_STACK",
            "performance": "Sub-second page loads",
            "security": "PCI-DSS compliant",
            "scalability": "Auto-scaling to 1M users",
            "reliability": "99.99% uptime",
            "maintainability": "Microservice architecture",
            "constraints": [
                {
                    "description": "Must support Stripe payments",
                    "priority": "MUST_HAVE",
                    "category": "payments",
                },
                {
                    "description": "Should have dark mode",
                    "priority": "NICE_TO_HAVE",
                    "category": "ui",
                },
                {
                    "description": "Must be GDPR compliant",
                    "priority": "required",
                    "category": "legal",
                },
            ],
        }
        parser = self._make_parser(response_json=response)
        spec = parser.parse("Build a comprehensive e-commerce platform with payments")

        assert spec.core_functionality == "E-commerce platform"
        assert len(spec.technical_requirements.languages) == 3
        assert len(spec.technical_requirements.frameworks) == 3
        assert spec.technical_requirements.scope == ScopeType.FULL_STACK
        assert len(spec.constraints) == 3
        assert spec.constraints[0].priority == ConstraintPriority.MUST_HAVE
        assert spec.constraints[1].priority == ConstraintPriority.NICE_TO_HAVE
        # "required" synonym -> MUST_HAVE
        assert spec.constraints[2].priority == ConstraintPriority.MUST_HAVE
        assert spec.quality_attributes.has_any is True

    def test_llm_returns_markdown_fences(self) -> None:
        """LLM returning JSON in markdown fences should still parse correctly."""
        gw = MagicMock()
        inner = json.dumps({"core_functionality": "Fenced response", "languages": ["Rust"]})
        gw.complete.return_value = f"```json\n{inner}\n```"
        parser = SpecParser(gateway=gw, templates=_make_mock_templates())

        spec = parser.parse(_default_description())
        assert spec.core_functionality == "Fenced response"
        assert "Rust" in spec.technical_requirements.languages

    def test_llm_error_propagates(self) -> None:
        """Gateway errors should propagate through parse()."""
        gw = MagicMock()
        gw.complete.side_effect = RuntimeError("API down")
        parser = SpecParser(gateway=gw, templates=_make_mock_templates())

        with pytest.raises(RuntimeError, match="API down"):
            parser.parse(_default_description())

    def test_invalid_json_from_llm(self) -> None:
        """Invalid JSON from LLM should raise SpecParserError."""
        gw = MagicMock()
        gw.complete.return_value = "This is plain text, not JSON"
        parser = SpecParser(gateway=gw, templates=_make_mock_templates())

        with pytest.raises(SpecParserError, match="not valid JSON"):
            parser.parse(_default_description())

    def test_custom_template_name(self) -> None:
        """Custom template_name should be passed to templates.render."""
        tpl = _make_mock_templates()
        gw = _make_mock_gateway()
        config = ParserConfig(template_name="my_custom_template")
        parser = SpecParser(config=config, gateway=gw, templates=tpl)

        parser.parse(_default_description())

        tpl.render.assert_called_once()
        assert tpl.render.call_args.args[0] == "my_custom_template"


# ===========================================================================
# SpecParserError Tests
# ===========================================================================


class TestSpecParserError:
    """Tests for the SpecParserError exception class."""

    def test_is_exception(self) -> None:
        """SpecParserError should be a subclass of Exception."""
        assert issubclass(SpecParserError, Exception)

    def test_message(self) -> None:
        """SpecParserError should carry a message."""
        err = SpecParserError("Something went wrong")
        assert str(err) == "Something went wrong"

    def test_raised_and_caught(self) -> None:
        """SpecParserError should be catchable."""
        with pytest.raises(SpecParserError):
            raise SpecParserError("test error")

    def test_chained_exception(self) -> None:
        """SpecParserError should support exception chaining."""
        try:
            try:
                raise ValueError("original")
            except ValueError as e:
                raise SpecParserError("wrapped") from e
        except SpecParserError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)


# ===========================================================================
# Edge Case Tests
# ===========================================================================


class TestEdgeCases:
    """Edge case tests for the parser module."""

    def test_constraint_with_all_synonyms(self) -> None:
        """Test all constraint priority synonyms in one batch."""
        raw = [
            ParsedConstraint(description="A", priority="required"),
            ParsedConstraint(description="B", priority="mandatory"),
            ParsedConstraint(description="C", priority="important"),
            ParsedConstraint(description="D", priority="optional"),
            ParsedConstraint(description="E", priority="MUST_HAVE"),
            ParsedConstraint(description="F", priority="unknown_priority"),
        ]
        result = _normalize_constraints(raw)
        assert result[0].priority == ConstraintPriority.MUST_HAVE   # required
        assert result[1].priority == ConstraintPriority.MUST_HAVE   # mandatory
        assert result[2].priority == ConstraintPriority.SHOULD_HAVE  # important
        assert result[3].priority == ConstraintPriority.NICE_TO_HAVE  # optional
        assert result[4].priority == ConstraintPriority.MUST_HAVE   # exact
        assert result[5].priority == ConstraintPriority.SHOULD_HAVE  # unknown default

    def test_all_deployment_target_variants(self) -> None:
        """All valid DeploymentTarget enum values should normalize."""
        targets = ["cloud", "on_premises", "edge", "serverless", "hybrid", "other"]
        result = _normalize_deployment_targets(targets)
        assert result == [
            DeploymentTarget.CLOUD,
            DeploymentTarget.ON_PREMISES,
            DeploymentTarget.EDGE,
            DeploymentTarget.SERVERLESS,
            DeploymentTarget.HYBRID,
            DeploymentTarget.OTHER,
        ]

    def test_all_scope_variants(self) -> None:
        """All valid ScopeType enum values should normalize."""
        assert _normalize_scope("BACKEND_ONLY") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("FRONTEND_ONLY") == ScopeType.FRONTEND_ONLY
        assert _normalize_scope("FULL_STACK") == ScopeType.FULL_STACK
        assert _normalize_scope("LIBRARY") == ScopeType.LIBRARY
        assert _normalize_scope("CLI_TOOL") == ScopeType.CLI_TOOL
        assert _normalize_scope("OTHER") == ScopeType.OTHER

    def test_parsed_spec_response_with_nested_constraints(self) -> None:
        """ParsedSpecResponse with multiple nested constraints."""
        data = {
            "constraints": [
                {"description": f"Constraint {i}", "priority": "MUST_HAVE"}
                for i in range(20)
            ],
        }
        psr = ParsedSpecResponse.model_validate(data)
        assert len(psr.constraints) == 20

    def test_description_preserved_exactly(self) -> None:
        """The description in the RepositorySpec should match the stripped input."""
        gw = _make_mock_gateway()
        tpl = _make_mock_templates()
        parser = SpecParser(gateway=gw, templates=tpl)

        desc = "   Build a chat app with many features and requirements   "
        spec = parser.parse(desc)
        # parse() strips the description before passing it through
        assert spec.description == desc.strip()

    def test_parse_response_preserves_all_quality_attributes(self) -> None:
        """All quality attributes should flow through from parsed to assembled."""
        parser = SpecParser(gateway=MagicMock(), templates=MagicMock())
        parsed = ParsedSpecResponse(
            performance="fast",
            security="secure",
            scalability="scalable",
            reliability="reliable",
            maintainability="maintainable",
        )
        spec = parser._assemble_spec("Test quality attributes preserved well", parsed)
        assert spec.quality_attributes.performance == "fast"
        assert spec.quality_attributes.security == "secure"
        assert spec.quality_attributes.scalability == "scalable"
        assert spec.quality_attributes.reliability == "reliable"
        assert spec.quality_attributes.maintainability == "maintainable"
