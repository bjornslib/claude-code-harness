"""Unit tests for the NLP specification parser.

All LLM calls are mocked so tests run without API keys or network access.
Tests cover: parsing, normalization, error handling, config, and edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.llm.models import ModelTier
from zerorepo.spec_parser.models import (
    Component,
    Constraint,
    ConstraintPriority,
    DataFlow,
    DeploymentTarget,
    Epic,
    FileRecommendation,
    QualityAttributes,
    RepositorySpec,
    ScopeType,
    TechnicalRequirement,
)
from zerorepo.spec_parser.parser import (
    ParsedComponent,
    ParsedConstraint,
    ParsedDataFlow,
    ParsedEpic,
    ParsedFileRecommendation,
    ParsedSpecResponse,
    ParserConfig,
    SpecParser,
    SpecParserError,
    _normalize_components,
    _normalize_constraint_priority,
    _normalize_constraints,
    _normalize_data_flows,
    _normalize_deployment_targets,
    _normalize_epics,
    _normalize_file_recommendations,
    _normalize_scope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_response(
    core_functionality: str = "real-time messaging between users",
    languages: list[str] | None = None,
    frameworks: list[str] | None = None,
    platforms: list[str] | None = None,
    deployment_targets: list[str] | None = None,
    scope: str | None = "FULL_STACK",
    performance: str | None = None,
    security: str | None = None,
    scalability: str | None = None,
    reliability: str | None = None,
    maintainability: str | None = None,
    constraints: list[dict[str, Any]] | None = None,
    epics: list[dict[str, Any]] | None = None,
    components: list[dict[str, Any]] | None = None,
    data_flows: list[dict[str, Any]] | None = None,
    file_recommendations: list[dict[str, Any]] | None = None,
) -> str:
    """Build a mock LLM JSON response string."""
    data = {
        "core_functionality": core_functionality,
        "languages": languages or ["TypeScript", "Python"],
        "frameworks": frameworks or ["React", "FastAPI"],
        "platforms": platforms or ["Web"],
        "deployment_targets": deployment_targets or ["CLOUD"],
        "scope": scope,
        "performance": performance,
        "security": security,
        "scalability": scalability,
        "reliability": reliability,
        "maintainability": maintainability,
        "constraints": constraints or [],
        "epics": epics or [],
        "components": components or [],
        "data_flows": data_flows or [],
        "file_recommendations": file_recommendations or [],
    }
    return json.dumps(data)


def _make_parser(llm_response: str | None = None) -> SpecParser:
    """Create a SpecParser with a mocked LLMGateway.

    Args:
        llm_response: The JSON string the mocked LLM should return.
            Defaults to a standard chat app response.

    Returns:
        A SpecParser with mocked gateway.
    """
    if llm_response is None:
        llm_response = _make_llm_response()

    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = llm_response

    parser = SpecParser(
        gateway=mock_gateway,
    )
    return parser


# ---------------------------------------------------------------------------
# ParserConfig tests
# ---------------------------------------------------------------------------


class TestParserConfig:
    """Test ParserConfig model."""

    def test_default_config(self) -> None:
        """Default config uses gpt-5.2 and CHEAP tier."""
        config = ParserConfig()
        assert config.model == "gpt-5.2"
        assert config.tier == ModelTier.CHEAP
        assert config.template_name == "spec_parsing"
        assert config.max_description_length == 50000
        assert config.use_json_mode is True

    def test_custom_config(self) -> None:
        """Custom config values are accepted."""
        config = ParserConfig(
            model="gpt-4o",
            tier=ModelTier.STRONG,
            template_name="custom_template",
            max_description_length=10000,
            use_json_mode=False,
        )
        assert config.model == "gpt-4o"
        assert config.tier == ModelTier.STRONG
        assert config.use_json_mode is False

    def test_max_description_length_must_be_positive(self) -> None:
        """max_description_length must be > 0."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ParserConfig(max_description_length=0)


# ---------------------------------------------------------------------------
# ParsedSpecResponse tests
# ---------------------------------------------------------------------------


class TestParsedSpecResponse:
    """Test the intermediate ParsedSpecResponse model."""

    def test_parse_from_dict(self) -> None:
        """ParsedSpecResponse validates from a dict."""
        data = json.loads(_make_llm_response())
        parsed = ParsedSpecResponse.model_validate(data)
        assert parsed.core_functionality == "real-time messaging between users"
        assert parsed.languages == ["TypeScript", "Python"]
        assert parsed.frameworks == ["React", "FastAPI"]

    def test_minimal_response(self) -> None:
        """ParsedSpecResponse with all defaults."""
        parsed = ParsedSpecResponse()
        assert parsed.core_functionality is None
        assert parsed.languages == []
        assert parsed.constraints == []

    def test_with_constraints(self) -> None:
        """ParsedSpecResponse with constraints."""
        data = {
            "core_functionality": "chat app",
            "constraints": [
                {"description": "Must use WebSocket", "priority": "MUST_HAVE"},
                {"description": "Dark mode", "priority": "NICE_TO_HAVE", "category": "ui"},
            ],
        }
        parsed = ParsedSpecResponse.model_validate(data)
        assert len(parsed.constraints) == 2
        assert parsed.constraints[0].description == "Must use WebSocket"
        assert parsed.constraints[1].category == "ui"


# ---------------------------------------------------------------------------
# Normalization helper tests
# ---------------------------------------------------------------------------


class TestNormalizeDeploymentTargets:
    """Test _normalize_deployment_targets helper."""

    def test_valid_targets(self) -> None:
        """Valid target strings are converted to enum values."""
        result = _normalize_deployment_targets(["CLOUD", "SERVERLESS"])
        assert result == [DeploymentTarget.CLOUD, DeploymentTarget.SERVERLESS]

    def test_case_insensitive(self) -> None:
        """Target matching is case-insensitive."""
        result = _normalize_deployment_targets(["cloud", "Cloud", "CLOUD"])
        assert all(t == DeploymentTarget.CLOUD for t in result)

    def test_hyphenated_targets(self) -> None:
        """Hyphens are converted to underscores."""
        result = _normalize_deployment_targets(["on-premises", "on_premises"])
        assert all(t == DeploymentTarget.ON_PREMISES for t in result)

    def test_unknown_target_maps_to_other(self) -> None:
        """Unknown targets map to OTHER."""
        result = _normalize_deployment_targets(["kubernetes"])
        assert result == [DeploymentTarget.OTHER]

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        result = _normalize_deployment_targets([])
        assert result == []

    def test_whitespace_stripped(self) -> None:
        """Whitespace is stripped from targets."""
        result = _normalize_deployment_targets(["  CLOUD  "])
        assert result == [DeploymentTarget.CLOUD]


class TestNormalizeScope:
    """Test _normalize_scope helper."""

    def test_valid_scopes(self) -> None:
        """Valid scope strings are converted to enum values."""
        assert _normalize_scope("BACKEND_ONLY") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("FULL_STACK") == ScopeType.FULL_STACK
        assert _normalize_scope("LIBRARY") == ScopeType.LIBRARY

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert _normalize_scope(None) is None

    def test_case_insensitive(self) -> None:
        """Scope matching is case-insensitive."""
        assert _normalize_scope("backend_only") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("Backend_Only") == ScopeType.BACKEND_ONLY

    def test_synonyms(self) -> None:
        """Common synonyms are mapped correctly."""
        assert _normalize_scope("BACKEND") == ScopeType.BACKEND_ONLY
        assert _normalize_scope("FRONTEND") == ScopeType.FRONTEND_ONLY
        assert _normalize_scope("FULLSTACK") == ScopeType.FULL_STACK
        assert _normalize_scope("CLI") == ScopeType.CLI_TOOL

    def test_hyphenated_scope(self) -> None:
        """Hyphens are converted to underscores."""
        assert _normalize_scope("full-stack") == ScopeType.FULL_STACK

    def test_unknown_scope_maps_to_other(self) -> None:
        """Unknown scope maps to OTHER."""
        assert _normalize_scope("microservice") == ScopeType.OTHER

    def test_whitespace_stripped(self) -> None:
        """Whitespace is stripped."""
        assert _normalize_scope("  LIBRARY  ") == ScopeType.LIBRARY


class TestNormalizeConstraintPriority:
    """Test _normalize_constraint_priority helper."""

    def test_valid_priorities(self) -> None:
        """Valid priority strings are converted."""
        assert _normalize_constraint_priority("MUST_HAVE") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("SHOULD_HAVE") == ConstraintPriority.SHOULD_HAVE
        assert _normalize_constraint_priority("NICE_TO_HAVE") == ConstraintPriority.NICE_TO_HAVE

    def test_case_insensitive(self) -> None:
        """Priority matching is case-insensitive."""
        assert _normalize_constraint_priority("must_have") == ConstraintPriority.MUST_HAVE

    def test_synonyms(self) -> None:
        """Common synonyms are mapped."""
        assert _normalize_constraint_priority("REQUIRED") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("MANDATORY") == ConstraintPriority.MUST_HAVE
        assert _normalize_constraint_priority("IMPORTANT") == ConstraintPriority.SHOULD_HAVE
        assert _normalize_constraint_priority("OPTIONAL") == ConstraintPriority.NICE_TO_HAVE

    def test_unknown_defaults_to_should_have(self) -> None:
        """Unknown priority defaults to SHOULD_HAVE."""
        assert _normalize_constraint_priority("critical") == ConstraintPriority.SHOULD_HAVE


class TestNormalizeConstraints:
    """Test _normalize_constraints helper."""

    def test_valid_constraints(self) -> None:
        """Valid constraints are normalized."""
        raw = [
            ParsedConstraint(description="Use WebSocket", priority="MUST_HAVE"),
            ParsedConstraint(description="Dark mode", priority="NICE_TO_HAVE", category="ui"),
        ]
        result = _normalize_constraints(raw)
        assert len(result) == 2
        assert result[0].description == "Use WebSocket"
        assert result[0].priority == ConstraintPriority.MUST_HAVE
        assert result[1].category == "ui"

    def test_empty_descriptions_filtered(self) -> None:
        """Constraints with empty descriptions are filtered out."""
        raw = [
            ParsedConstraint(description="Valid", priority="MUST_HAVE"),
            ParsedConstraint(description="", priority="MUST_HAVE"),
            ParsedConstraint(description="   ", priority="MUST_HAVE"),
        ]
        result = _normalize_constraints(raw)
        assert len(result) == 1
        assert result[0].description == "Valid"

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        result = _normalize_constraints([])
        assert result == []


# ---------------------------------------------------------------------------
# SpecParser integration tests (with mocked LLM)
# ---------------------------------------------------------------------------


class TestSpecParserParse:
    """Test SpecParser.parse() with mocked LLM gateway."""

    def test_parse_basic_description(self) -> None:
        """Parse a basic description into a RepositorySpec."""
        parser = _make_parser()
        spec = parser.parse(
            "Build a real-time chat application with React and WebSocket"
        )

        assert isinstance(spec, RepositorySpec)
        assert "real-time chat" in spec.description
        assert spec.core_functionality == "real-time messaging between users"
        assert "TypeScript" in spec.technical_requirements.languages
        assert "React" in spec.technical_requirements.frameworks
        assert spec.technical_requirements.scope == ScopeType.FULL_STACK

    def test_parse_with_context(self) -> None:
        """Parse with additional context."""
        parser = _make_parser()
        spec = parser.parse(
            "Build a web application for project management",
            context="Must integrate with Jira and GitHub APIs",
        )
        assert isinstance(spec, RepositorySpec)
        # Verify context was passed to template
        call_kwargs = parser.gateway.complete.call_args.kwargs
        messages = call_kwargs["messages"]
        prompt = messages[0]["content"]
        assert "Jira" in prompt or "project management" in prompt

    def test_parse_with_quality_attributes(self) -> None:
        """Parse extracts quality attributes."""
        llm_response = _make_llm_response(
            performance="<100ms message delivery",
            security="OAuth2 authentication",
            scalability="10K concurrent users",
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a real-time chat app with React and WebSocket support"
        )

        assert spec.quality_attributes.performance == "<100ms message delivery"
        assert spec.quality_attributes.security == "OAuth2 authentication"
        assert spec.quality_attributes.scalability == "10K concurrent users"
        assert spec.quality_attributes.has_any is True

    def test_parse_with_constraints(self) -> None:
        """Parse extracts constraints with priorities."""
        llm_response = _make_llm_response(
            constraints=[
                {"description": "Must support WebSocket", "priority": "MUST_HAVE", "category": "protocol"},
                {"description": "Dark mode would be nice", "priority": "NICE_TO_HAVE", "category": "ui"},
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a real-time chat application with WebSocket support"
        )

        assert len(spec.constraints) == 2
        assert spec.constraints[0].priority == ConstraintPriority.MUST_HAVE
        assert spec.constraints[0].category == "protocol"
        assert spec.constraints[1].priority == ConstraintPriority.NICE_TO_HAVE

    def test_parse_with_deployment_targets(self) -> None:
        """Parse extracts deployment targets."""
        llm_response = _make_llm_response(
            deployment_targets=["CLOUD", "SERVERLESS"],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a serverless API deployed to AWS Lambda in the cloud"
        )

        assert DeploymentTarget.CLOUD in spec.technical_requirements.deployment_targets
        assert DeploymentTarget.SERVERLESS in spec.technical_requirements.deployment_targets

    def test_parse_json_mode_enabled(self) -> None:
        """Parser uses JSON mode by default."""
        parser = _make_parser()
        parser.parse(
            "Build a real-time chat application with React support"
        )

        call_kwargs = parser.gateway.complete.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    def test_parse_json_mode_disabled(self) -> None:
        """Parser can disable JSON mode."""
        config = ParserConfig(use_json_mode=False)
        parser = _make_parser()
        parser.config = config
        parser.parse(
            "Build a real-time chat application with React support"
        )

        call_kwargs = parser.gateway.complete.call_args.kwargs
        assert "response_format" not in call_kwargs

    def test_parse_uses_temperature_zero(self) -> None:
        """Parser calls LLM with temperature=0 for deterministic output."""
        parser = _make_parser()
        parser.parse(
            "Build a real-time chat application with React support"
        )

        call_kwargs = parser.gateway.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0

    def test_parse_preserves_original_description(self) -> None:
        """The original description is preserved in the output."""
        parser = _make_parser()
        original = "Build a machine learning library with regression and clustering"
        spec = parser.parse(original)
        assert spec.description == original

    def test_parse_minimal_llm_response(self) -> None:
        """Parse handles minimal LLM response with mostly defaults."""
        llm_response = json.dumps({
            "core_functionality": "simple tool",
            "languages": [],
            "frameworks": [],
            "platforms": [],
            "deployment_targets": [],
            "scope": None,
            "performance": None,
            "security": None,
            "scalability": None,
            "reliability": None,
            "maintainability": None,
            "constraints": [],
        })
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a simple command-line tool for file conversion"
        )

        assert spec.core_functionality == "simple tool"
        assert spec.technical_requirements.languages == []
        assert spec.technical_requirements.scope is None
        assert spec.quality_attributes.has_any is False
        assert spec.constraints == []


class TestSpecParserValidation:
    """Test SpecParser input validation."""

    def test_description_too_short(self) -> None:
        """Description shorter than 10 chars raises ValueError."""
        parser = _make_parser()
        with pytest.raises(ValueError, match="at least 10 characters"):
            parser.parse("short")

    def test_description_whitespace_only(self) -> None:
        """Whitespace-only description raises ValueError."""
        parser = _make_parser()
        with pytest.raises(ValueError, match="at least 10 characters"):
            parser.parse("         ")

    def test_description_too_long(self) -> None:
        """Description exceeding max length raises ValueError."""
        config = ParserConfig(max_description_length=100)
        parser = _make_parser()
        parser.config = config
        with pytest.raises(ValueError, match="exceeds maximum length"):
            parser.parse("x " * 100)

    def test_description_stripped(self) -> None:
        """Description whitespace is stripped before processing."""
        parser = _make_parser()
        spec = parser.parse(
            "   Build a real-time chat application with React support   "
        )
        assert spec.description == "Build a real-time chat application with React support"


class TestSpecParserErrorHandling:
    """Test SpecParser error handling for bad LLM responses."""

    def test_invalid_json_response(self) -> None:
        """Non-JSON LLM response raises SpecParserError."""
        parser = _make_parser("This is not JSON at all")
        with pytest.raises(SpecParserError, match="not valid JSON"):
            parser.parse(
                "Build a real-time chat application with React support"
            )

    def test_markdown_wrapped_json(self) -> None:
        """Parser strips markdown code fences from JSON response."""
        raw_json = _make_llm_response()
        wrapped = f"```json\n{raw_json}\n```"
        parser = _make_parser(wrapped)
        spec = parser.parse(
            "Build a real-time chat application with React support"
        )
        assert isinstance(spec, RepositorySpec)
        assert spec.core_functionality is not None

    def test_markdown_wrapped_no_language(self) -> None:
        """Parser strips generic code fences (no language tag)."""
        raw_json = _make_llm_response()
        wrapped = f"```\n{raw_json}\n```"
        parser = _make_parser(wrapped)
        spec = parser.parse(
            "Build a real-time chat application with React support"
        )
        assert isinstance(spec, RepositorySpec)

    def test_partial_json_response(self) -> None:
        """Truncated JSON response raises SpecParserError."""
        parser = _make_parser('{"core_functionality": "test"')
        with pytest.raises(SpecParserError, match="not valid JSON"):
            parser.parse(
                "Build a real-time chat application with React support"
            )

    def test_wrong_schema_response(self) -> None:
        """JSON with unexpected structure is handled gracefully."""
        # ParsedSpecResponse has all-optional fields, so even wrong keys will
        # just produce defaults. However, if the value types are wrong...
        parser = _make_parser('{"languages": "not a list"}')
        with pytest.raises(SpecParserError, match="does not match expected schema"):
            parser.parse(
                "Build a real-time chat application with React support"
            )


class TestSpecParserLLMInteraction:
    """Test how SpecParser interacts with the LLM Gateway."""

    def test_uses_configured_model(self) -> None:
        """Parser passes configured model to gateway."""
        config = ParserConfig(model="gpt-4o")
        mock_gateway = MagicMock()
        mock_gateway.complete.return_value = _make_llm_response()
        parser = SpecParser(config=config, gateway=mock_gateway)

        parser.parse("Build a web application for task management")

        call_kwargs = mock_gateway.complete.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"

    def test_uses_configured_tier(self) -> None:
        """Parser passes configured tier to gateway."""
        config = ParserConfig(tier=ModelTier.STRONG)
        mock_gateway = MagicMock()
        mock_gateway.complete.return_value = _make_llm_response()
        parser = SpecParser(config=config, gateway=mock_gateway)

        parser.parse("Build a web application for task management")

        call_kwargs = mock_gateway.complete.call_args.kwargs
        assert call_kwargs["tier"] == ModelTier.STRONG

    def test_gateway_called_once(self) -> None:
        """Parser makes exactly one LLM call per parse."""
        parser = _make_parser()
        parser.parse("Build a web application for task management")
        assert parser.gateway.complete.call_count == 1

    def test_prompt_contains_description(self) -> None:
        """The rendered prompt contains the user's description."""
        parser = _make_parser()
        description = "Build a machine learning library with regression and clustering"
        parser.parse(description)

        call_kwargs = parser.gateway.complete.call_args.kwargs
        messages = call_kwargs["messages"]
        prompt = messages[0]["content"]
        assert description in prompt


class TestSpecParserEndToEnd:
    """End-to-end tests with realistic LLM responses."""

    def test_chat_app_spec(self) -> None:
        """Parse a chat app specification."""
        llm_response = _make_llm_response(
            core_functionality="Real-time messaging application with user presence tracking",
            languages=["TypeScript", "Python"],
            frameworks=["React", "FastAPI", "Socket.IO"],
            platforms=["Web"],
            deployment_targets=["CLOUD"],
            scope="FULL_STACK",
            performance="<100ms message delivery",
            security="JWT authentication, end-to-end encryption",
            scalability="10K concurrent users",
            constraints=[
                {"description": "Must support WebSocket protocol", "priority": "MUST_HAVE", "category": "protocol"},
                {"description": "Support file sharing up to 10MB", "priority": "SHOULD_HAVE", "category": "feature"},
                {"description": "Dark mode theme", "priority": "NICE_TO_HAVE", "category": "ui"},
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a real-time chat application with React, WebSocket, "
            "and PostgreSQL. Must support 10K concurrent users."
        )

        # Core functionality
        assert "messaging" in spec.core_functionality.lower()

        # Technical requirements
        assert "TypeScript" in spec.technical_requirements.languages
        assert "React" in spec.technical_requirements.frameworks
        assert spec.technical_requirements.scope == ScopeType.FULL_STACK

        # Quality attributes
        assert spec.quality_attributes.performance is not None
        assert spec.quality_attributes.security is not None
        assert spec.quality_attributes.scalability is not None
        assert spec.quality_attributes.has_any is True

        # Constraints
        assert len(spec.constraints) == 3
        must_haves = spec.must_have_constraints
        assert len(must_haves) == 1
        assert "WebSocket" in must_haves[0].description

        nice_to_haves = spec.nice_to_have_constraints
        assert len(nice_to_haves) == 1
        assert "Dark mode" in nice_to_haves[0].description

    def test_ml_library_spec(self) -> None:
        """Parse a machine learning library specification."""
        llm_response = _make_llm_response(
            core_functionality="Machine learning library with supervised and unsupervised learning algorithms",
            languages=["Python"],
            frameworks=["NumPy", "scikit-learn"],
            platforms=["Linux", "macOS", "Windows"],
            deployment_targets=[],
            scope="LIBRARY",
            performance="Sub-second predictions on small datasets",
            maintainability="80% test coverage, comprehensive documentation",
            constraints=[
                {"description": "Must support Python 3.11+", "priority": "MUST_HAVE"},
                {"description": "GPU acceleration", "priority": "NICE_TO_HAVE"},
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a machine learning library with regression, clustering, "
            "and evaluation metrics. Support Python 3.11+."
        )

        assert spec.technical_requirements.scope == ScopeType.LIBRARY
        assert "Python" in spec.technical_requirements.languages
        assert spec.quality_attributes.maintainability is not None
        assert len(spec.constraints) == 2

    def test_backend_api_spec(self) -> None:
        """Parse a backend API specification."""
        llm_response = _make_llm_response(
            core_functionality="RESTful API for e-commerce operations",
            languages=["Python"],
            frameworks=["FastAPI", "SQLAlchemy"],
            platforms=["Linux"],
            deployment_targets=["CLOUD", "SERVERLESS"],
            scope="BACKEND_ONLY",
            security="OAuth2, rate limiting, input validation",
            scalability="Handle 1000 requests/second",
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a backend API for an e-commerce platform with "
            "user management, product catalog, and order processing."
        )

        assert spec.technical_requirements.scope == ScopeType.BACKEND_ONLY
        assert DeploymentTarget.SERVERLESS in spec.technical_requirements.deployment_targets
        assert spec.quality_attributes.security is not None

    def test_spec_serialization_after_parse(self) -> None:
        """Parsed spec can be serialized and deserialized."""
        parser = _make_parser()
        spec = parser.parse(
            "Build a real-time chat application with React and WebSocket"
        )

        json_str = spec.to_json()
        restored = RepositorySpec.from_json(json_str)

        assert restored.description == spec.description
        assert restored.core_functionality == spec.core_functionality
        assert restored.technical_requirements.languages == spec.technical_requirements.languages

    def test_llm_response_with_unknown_enums(self) -> None:
        """Parser handles unknown enum values gracefully."""
        llm_response = _make_llm_response(
            deployment_targets=["CLOUD", "kubernetes", "docker-compose"],
            scope="microservice-architecture",
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a microservice-based system with Kubernetes deployment"
        )

        # Unknown targets mapped to OTHER
        assert DeploymentTarget.CLOUD in spec.technical_requirements.deployment_targets
        assert spec.technical_requirements.deployment_targets.count(DeploymentTarget.OTHER) == 2
        # Unknown scope mapped to OTHER
        assert spec.technical_requirements.scope == ScopeType.OTHER

    def test_llm_response_with_synonym_priorities(self) -> None:
        """Parser normalizes priority synonyms."""
        llm_response = _make_llm_response(
            constraints=[
                {"description": "Required feature", "priority": "REQUIRED"},
                {"description": "Mandatory feature", "priority": "MANDATORY"},
                {"description": "Optional feature", "priority": "OPTIONAL"},
                {"description": "Important feature", "priority": "IMPORTANT"},
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a web application with various requirements"
        )

        assert spec.constraints[0].priority == ConstraintPriority.MUST_HAVE
        assert spec.constraints[1].priority == ConstraintPriority.MUST_HAVE
        assert spec.constraints[2].priority == ConstraintPriority.NICE_TO_HAVE
        assert spec.constraints[3].priority == ConstraintPriority.SHOULD_HAVE


# ---------------------------------------------------------------------------
# Deep extraction tests (epics, components, data flows, file recommendations)
# ---------------------------------------------------------------------------


class TestDeepExtractionParsing:
    """Test parsing of deep extraction fields."""

    def test_parse_with_epics(self) -> None:
        """Parse extracts epics from LLM response."""
        llm_response = _make_llm_response(
            epics=[
                {
                    "title": "User Authentication",
                    "description": "JWT-based auth with OAuth2",
                    "priority": "MUST_HAVE",
                    "estimated_complexity": "high",
                },
                {
                    "title": "Real-time Messaging",
                    "description": "WebSocket-based chat system",
                    "priority": "MUST_HAVE",
                    "estimated_complexity": "high",
                },
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a chat application with authentication and messaging"
        )

        assert len(spec.epics) == 2
        assert spec.epics[0].title == "User Authentication"
        assert spec.epics[0].priority == ConstraintPriority.MUST_HAVE
        assert spec.epics[0].estimated_complexity == "high"
        assert spec.epics[1].title == "Real-time Messaging"

    def test_parse_with_components(self) -> None:
        """Parse extracts components from LLM response."""
        llm_response = _make_llm_response(
            components=[
                {
                    "name": "API Gateway",
                    "description": "Central entry point for all API requests",
                    "component_type": "service",
                    "technologies": ["FastAPI", "uvicorn"],
                },
                {
                    "name": "Database Layer",
                    "description": "PostgreSQL with SQLAlchemy ORM",
                    "component_type": "database",
                    "technologies": ["PostgreSQL", "SQLAlchemy"],
                },
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a backend API with PostgreSQL database"
        )

        assert len(spec.components) == 2
        assert spec.components[0].name == "API Gateway"
        assert spec.components[0].component_type == "service"
        assert "FastAPI" in spec.components[0].technologies
        assert spec.components[1].name == "Database Layer"

    def test_parse_with_data_flows(self) -> None:
        """Parse extracts data flows from LLM response."""
        llm_response = _make_llm_response(
            data_flows=[
                {
                    "source": "API Gateway",
                    "target": "Auth Service",
                    "description": "JWT token validation",
                    "protocol": "REST",
                },
                {
                    "source": "API Gateway",
                    "target": "Database Layer",
                    "description": "CRUD operations via ORM",
                    "protocol": "direct",
                },
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a system with API gateway and authentication"
        )

        assert len(spec.data_flows) == 2
        assert spec.data_flows[0].source == "API Gateway"
        assert spec.data_flows[0].target == "Auth Service"
        assert spec.data_flows[0].protocol == "REST"

    def test_parse_with_file_recommendations(self) -> None:
        """Parse extracts file recommendations from LLM response."""
        llm_response = _make_llm_response(
            file_recommendations=[
                {
                    "path": "src/api/routes.py",
                    "purpose": "API route definitions",
                    "component": "API Gateway",
                },
                {
                    "path": "src/models/user.py",
                    "purpose": "User data model",
                    "component": "Database Layer",
                },
            ],
        )
        parser = _make_parser(llm_response)
        spec = parser.parse(
            "Build a backend API with user management"
        )

        assert len(spec.file_recommendations) == 2
        assert spec.file_recommendations[0].path == "src/api/routes.py"
        assert spec.file_recommendations[0].component == "API Gateway"

    def test_parse_empty_deep_extraction_fields(self) -> None:
        """Parse handles empty deep extraction fields gracefully."""
        parser = _make_parser()
        spec = parser.parse(
            "Build a simple command line tool for file conversion"
        )

        assert spec.epics == []
        assert spec.components == []
        assert spec.data_flows == []
        assert spec.file_recommendations == []


class TestNormalizeEpics:
    """Test _normalize_epics helper."""

    def test_valid_epics(self) -> None:
        """Valid epics are normalized."""
        raw = [
            ParsedEpic(title="Auth System", description="Authentication", priority="MUST_HAVE"),
            ParsedEpic(title="Messaging", description="Chat features", priority="SHOULD_HAVE"),
        ]
        result = _normalize_epics(raw)
        assert len(result) == 2
        assert result[0].title == "Auth System"
        assert result[0].priority == ConstraintPriority.MUST_HAVE
        assert result[1].title == "Messaging"

    def test_empty_titles_filtered(self) -> None:
        """Epics with empty titles are filtered out."""
        raw = [
            ParsedEpic(title="Valid Epic", description="has a title"),
            ParsedEpic(title="", description="no title"),
            ParsedEpic(title="   ", description="whitespace title"),
        ]
        result = _normalize_epics(raw)
        assert len(result) == 1

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        assert _normalize_epics([]) == []


class TestNormalizeComponents:
    """Test _normalize_components helper."""

    def test_valid_components(self) -> None:
        """Valid components are normalized."""
        raw = [
            ParsedComponent(
                name="API Gateway",
                description="Entry point",
                component_type="service",
                technologies=["FastAPI"],
            ),
        ]
        result = _normalize_components(raw)
        assert len(result) == 1
        assert result[0].name == "API Gateway"
        assert result[0].technologies == ["FastAPI"]

    def test_empty_names_filtered(self) -> None:
        """Components with empty names are filtered out."""
        raw = [
            ParsedComponent(name="Valid", description="ok"),
            ParsedComponent(name="", description="no name"),
        ]
        result = _normalize_components(raw)
        assert len(result) == 1

    def test_whitespace_technologies_cleaned(self) -> None:
        """Whitespace-only technologies are removed."""
        raw = [
            ParsedComponent(name="Test", technologies=["FastAPI", "", "  ", "Redis"]),
        ]
        result = _normalize_components(raw)
        assert result[0].technologies == ["FastAPI", "Redis"]


class TestNormalizeDataFlows:
    """Test _normalize_data_flows helper."""

    def test_valid_flows(self) -> None:
        """Valid data flows are normalized."""
        raw = [
            ParsedDataFlow(
                source="API",
                target="DB",
                description="CRUD ops",
                protocol="REST",
            ),
        ]
        result = _normalize_data_flows(raw)
        assert len(result) == 1
        assert result[0].source == "API"
        assert result[0].target == "DB"

    def test_empty_source_or_target_filtered(self) -> None:
        """Flows with empty source or target are filtered."""
        raw = [
            ParsedDataFlow(source="API", target="DB"),
            ParsedDataFlow(source="", target="DB"),
            ParsedDataFlow(source="API", target=""),
        ]
        result = _normalize_data_flows(raw)
        assert len(result) == 1


class TestNormalizeFileRecommendations:
    """Test _normalize_file_recommendations helper."""

    def test_valid_recommendations(self) -> None:
        """Valid file recommendations are normalized."""
        raw = [
            ParsedFileRecommendation(
                path="src/api/routes.py",
                purpose="API routes",
                component="API Gateway",
            ),
        ]
        result = _normalize_file_recommendations(raw)
        assert len(result) == 1
        assert result[0].path == "src/api/routes.py"

    def test_empty_paths_filtered(self) -> None:
        """Recommendations with empty paths are filtered."""
        raw = [
            ParsedFileRecommendation(path="src/main.py", purpose="entry point"),
            ParsedFileRecommendation(path="", purpose="no path"),
        ]
        result = _normalize_file_recommendations(raw)
        assert len(result) == 1
