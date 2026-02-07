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
        """Default config uses gpt-4o-mini and CHEAP tier."""
        config = ParserConfig()
        assert config.model == "gpt-4o-mini"
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
