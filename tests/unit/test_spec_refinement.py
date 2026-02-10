"""Unit tests for the Iterative Spec Refinement module (Task 2.4.5).

Tests cover:
- RefinerConfig validation and defaults
- Suggestion and SuggestionResponse models
- RefinementError exception
- SpecRefiner initialization
- add_requirement with mocked LLM
- remove_requirement (local, no LLM)
- clarify with mocked LLM
- suggest_improvements with mocked LLM
- get_history
- _parse_json_response edge cases
- _spec_to_template_vars conversion
- _apply_parsed_updates with various inputs
- Full pipeline: multiple sequential refinements
- Error handling (empty inputs, invalid IDs, bad LLM responses)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from zerorepo.llm.models import ModelTier
from zerorepo.spec_parser.models import (
    Constraint,
    ConstraintPriority,
    DeploymentTarget,
    QualityAttributes,
    RefinementEntry,
    RepositorySpec,
    ScopeType,
    TechnicalRequirement,
)
from zerorepo.spec_parser.refinement import (
    RefinerConfig,
    RefinementError,
    SpecRefiner,
    Suggestion,
    SuggestionResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_gateway(response_json: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock LLMGateway returning the given JSON as a string."""
    if response_json is None:
        response_json = {
            "core_functionality": "Real-time chat with offline support",
            "languages": ["Python", "TypeScript"],
            "frameworks": ["FastAPI", "React"],
            "platforms": ["Web"],
            "deployment_targets": ["CLOUD"],
            "scope": "FULL_STACK",
            "performance": "10K concurrent users",
            "security": "OAuth2",
            "scalability": None,
            "reliability": None,
            "maintainability": None,
            "constraints": [
                {
                    "description": "Must use WebSocket",
                    "priority": "MUST_HAVE",
                    "category": "architecture",
                },
                {
                    "description": "Support offline mode",
                    "priority": "SHOULD_HAVE",
                    "category": "feature",
                },
            ],
            "changes_summary": "Added offline support requirement",
        }
    gateway = MagicMock()
    gateway.complete.return_value = json.dumps(response_json)
    return gateway


def _make_mock_templates() -> MagicMock:
    """Create a mock PromptTemplate."""
    templates = MagicMock()
    templates.render.return_value = "rendered refinement prompt"
    return templates


def _make_spec(
    description: str = "Build a real-time chat application with React and WebSocket",
    constraints: list[Constraint] | None = None,
    **kwargs: Any,
) -> RepositorySpec:
    """Create a test RepositorySpec."""
    if constraints is None:
        constraints = [
            Constraint(
                description="Must use WebSocket for real-time",
                priority=ConstraintPriority.MUST_HAVE,
                category="architecture",
            ),
        ]
    return RepositorySpec(
        description=description,
        core_functionality="A real-time chat application",
        technical_requirements=TechnicalRequirement(
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI", "React"],
            platforms=["Web"],
            deployment_targets=[DeploymentTarget.CLOUD],
            scope=ScopeType.FULL_STACK,
        ),
        quality_attributes=QualityAttributes(
            performance="10K concurrent users",
            security="OAuth2",
        ),
        constraints=constraints,
        **kwargs,
    )


def _make_refiner(
    response_json: dict[str, Any] | None = None,
    config: RefinerConfig | None = None,
) -> SpecRefiner:
    """Create a SpecRefiner with mocked dependencies."""
    return SpecRefiner(
        config=config,
        gateway=_make_mock_gateway(response_json),
        templates=_make_mock_templates(),
    )


# ===========================================================================
# RefinerConfig Tests
# ===========================================================================


class TestRefinerConfig:
    """Tests for the RefinerConfig model."""

    def test_default_values(self) -> None:
        config = RefinerConfig()
        assert config.model == "gpt-4o-mini"
        assert config.tier == ModelTier.CHEAP
        assert config.refinement_template == "spec_refinement"
        assert config.suggestion_template == "spec_suggestions"
        assert config.use_json_mode is True
        assert config.max_suggestions == 10

    def test_custom_values(self) -> None:
        config = RefinerConfig(
            model="gpt-4o",
            tier=ModelTier.STRONG,
            refinement_template="custom_refine",
            suggestion_template="custom_suggest",
            use_json_mode=False,
            max_suggestions=5,
        )
        assert config.model == "gpt-4o"
        assert config.tier == ModelTier.STRONG
        assert config.refinement_template == "custom_refine"
        assert config.use_json_mode is False
        assert config.max_suggestions == 5

    def test_max_suggestions_bounds(self) -> None:
        with pytest.raises(Exception):
            RefinerConfig(max_suggestions=0)
        with pytest.raises(Exception):
            RefinerConfig(max_suggestions=51)

    def test_mutable_assignment(self) -> None:
        config = RefinerConfig()
        config.model = "gpt-4o"
        assert config.model == "gpt-4o"


# ===========================================================================
# Suggestion / SuggestionResponse Model Tests
# ===========================================================================


class TestSuggestion:
    """Tests for the Suggestion model."""

    def test_defaults(self) -> None:
        s = Suggestion()
        assert s.category == "general"
        assert s.title == ""
        assert s.description == ""
        assert s.priority == "SHOULD_HAVE"

    def test_custom(self) -> None:
        s = Suggestion(
            category="missing_requirement",
            title="Add authentication",
            description="No auth mechanism specified",
            priority="MUST_HAVE",
        )
        assert s.category == "missing_requirement"
        assert s.title == "Add authentication"

    def test_whitespace_stripping(self) -> None:
        s = Suggestion(title="  padded  ", description="  also padded  ")
        assert s.title == "padded"
        assert s.description == "also padded"


class TestSuggestionResponse:
    """Tests for the SuggestionResponse model."""

    def test_defaults(self) -> None:
        sr = SuggestionResponse()
        assert sr.suggestions == []
        assert sr.completeness_score == 0.0
        assert sr.summary == ""

    def test_full_population(self) -> None:
        sr = SuggestionResponse(
            suggestions=[
                Suggestion(title="Add auth", category="missing_requirement"),
                Suggestion(title="Add tests", category="best_practice"),
            ],
            completeness_score=0.65,
            summary="Good spec but missing security",
        )
        assert len(sr.suggestions) == 2
        assert sr.completeness_score == 0.65
        assert "missing security" in sr.summary

    def test_completeness_score_bounds(self) -> None:
        with pytest.raises(Exception):
            SuggestionResponse(completeness_score=-0.1)
        with pytest.raises(Exception):
            SuggestionResponse(completeness_score=1.1)


# ===========================================================================
# RefinementError Tests
# ===========================================================================


class TestRefinementError:
    """Tests for the RefinementError exception."""

    def test_is_exception(self) -> None:
        assert issubclass(RefinementError, Exception)

    def test_message(self) -> None:
        err = RefinementError("something broke")
        assert str(err) == "something broke"

    def test_raised_and_caught(self) -> None:
        with pytest.raises(RefinementError):
            raise RefinementError("test")


# ===========================================================================
# SpecRefiner Initialization Tests
# ===========================================================================


class TestSpecRefinerInit:
    """Tests for SpecRefiner initialization."""

    def test_default_config(self) -> None:
        refiner = SpecRefiner(gateway=MagicMock(), templates=MagicMock())
        assert isinstance(refiner.config, RefinerConfig)

    def test_custom_config(self) -> None:
        config = RefinerConfig(model="gpt-4o", tier=ModelTier.STRONG)
        refiner = SpecRefiner(config=config, gateway=MagicMock(), templates=MagicMock())
        assert refiner.config.model == "gpt-4o"

    def test_injected_gateway(self) -> None:
        gw = MagicMock()
        refiner = SpecRefiner(gateway=gw, templates=MagicMock())
        assert refiner.gateway is gw

    def test_injected_templates(self) -> None:
        tpl = MagicMock()
        refiner = SpecRefiner(gateway=MagicMock(), templates=tpl)
        assert refiner.templates is tpl


# ===========================================================================
# add_requirement Tests
# ===========================================================================


class TestAddRequirement:
    """Tests for SpecRefiner.add_requirement."""

    def test_adds_requirement(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        updated = refiner.add_requirement(spec, "Support offline mode")

        assert isinstance(updated, RepositorySpec)
        # Should have refinement history
        assert len(updated.refinement_history) == 1
        entry = updated.refinement_history[0]
        assert entry.action == "add_requirement"
        assert "Support offline mode" in entry.details

    def test_does_not_mutate_original(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        original_history_len = len(spec.refinement_history)

        updated = refiner.add_requirement(spec, "Support offline mode")

        assert len(spec.refinement_history) == original_history_len
        assert len(updated.refinement_history) == original_history_len + 1

    def test_empty_requirement_raises(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        with pytest.raises(ValueError, match="must not be empty"):
            refiner.add_requirement(spec, "")

    def test_whitespace_only_raises(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        with pytest.raises(ValueError, match="must not be empty"):
            refiner.add_requirement(spec, "   ")

    def test_llm_called_with_correct_params(self) -> None:
        gw = _make_mock_gateway()
        tpl = _make_mock_templates()
        refiner = SpecRefiner(gateway=gw, templates=tpl)
        spec = _make_spec()

        refiner.add_requirement(spec, "Add dark mode")

        # Template should be rendered with refinement template
        tpl.render.assert_called_once()
        render_kwargs = tpl.render.call_args.kwargs
        assert render_kwargs["action"] == "add_requirement"
        assert render_kwargs["details"] == "Add dark mode"

    def test_with_context(self) -> None:
        gw = _make_mock_gateway()
        tpl = _make_mock_templates()
        refiner = SpecRefiner(gateway=gw, templates=tpl)
        spec = _make_spec()

        refiner.add_requirement(spec, "Add dark mode", context="For mobile users")

        render_kwargs = tpl.render.call_args.kwargs
        assert render_kwargs["context"] == "For mobile users"

    def test_llm_response_updates_spec(self) -> None:
        response = {
            "core_functionality": "Chat with dark mode",
            "languages": ["Python", "TypeScript"],
            "frameworks": ["FastAPI", "React"],
            "platforms": ["Web", "Mobile"],
            "deployment_targets": ["CLOUD"],
            "scope": "FULL_STACK",
            "performance": "10K concurrent users",
            "security": "OAuth2",
            "scalability": None,
            "reliability": None,
            "maintainability": None,
            "constraints": [
                {"description": "Must use WebSocket", "priority": "MUST_HAVE"},
                {"description": "Must support dark mode", "priority": "MUST_HAVE"},
            ],
            "changes_summary": "Added dark mode requirement",
        }
        refiner = _make_refiner(response_json=response)
        spec = _make_spec()
        updated = refiner.add_requirement(spec, "Add dark mode")

        assert "Mobile" in updated.technical_requirements.platforms
        assert len(updated.constraints) == 2


# ===========================================================================
# remove_requirement Tests
# ===========================================================================


class TestRemoveRequirement:
    """Tests for SpecRefiner.remove_requirement."""

    def test_removes_constraint(self) -> None:
        refiner = _make_refiner()
        constraint = Constraint(
            description="Must use WebSocket",
            priority=ConstraintPriority.MUST_HAVE,
            category="architecture",
        )
        spec = _make_spec(constraints=[constraint])

        updated = refiner.remove_requirement(spec, constraint.id)

        assert len(updated.constraints) == 0
        assert len(updated.refinement_history) == 1
        entry = updated.refinement_history[0]
        assert entry.action == "remove_requirement"
        assert "Must use WebSocket" in entry.details
        assert entry.previous_value == "Must use WebSocket"

    def test_does_not_mutate_original(self) -> None:
        refiner = _make_refiner()
        constraint = Constraint(
            description="Test constraint",
            priority=ConstraintPriority.SHOULD_HAVE,
        )
        spec = _make_spec(constraints=[constraint])

        updated = refiner.remove_requirement(spec, constraint.id)

        assert len(spec.constraints) == 1
        assert len(updated.constraints) == 0

    def test_nonexistent_id_raises(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        with pytest.raises(RefinementError, match="No constraint found"):
            refiner.remove_requirement(spec, uuid4())

    def test_removes_correct_constraint(self) -> None:
        refiner = _make_refiner()
        c1 = Constraint(description="Keep this", priority=ConstraintPriority.MUST_HAVE)
        c2 = Constraint(description="Remove this", priority=ConstraintPriority.NICE_TO_HAVE)
        c3 = Constraint(description="Also keep", priority=ConstraintPriority.SHOULD_HAVE)
        spec = _make_spec(constraints=[c1, c2, c3])

        updated = refiner.remove_requirement(spec, c2.id)

        assert len(updated.constraints) == 2
        remaining_descs = [c.description for c in updated.constraints]
        assert "Keep this" in remaining_descs
        assert "Also keep" in remaining_descs
        assert "Remove this" not in remaining_descs

    def test_no_llm_call(self) -> None:
        """remove_requirement should NOT call the LLM."""
        gw = MagicMock()
        refiner = SpecRefiner(gateway=gw, templates=MagicMock())
        constraint = Constraint(description="Test", priority=ConstraintPriority.MUST_HAVE)
        spec = _make_spec(constraints=[constraint])

        refiner.remove_requirement(spec, constraint.id)

        gw.complete.assert_not_called()


# ===========================================================================
# clarify Tests
# ===========================================================================


class TestClarify:
    """Tests for SpecRefiner.clarify."""

    def test_clarifies_spec(self) -> None:
        response = {
            "core_functionality": "Chat with PostgreSQL",
            "languages": ["Python", "TypeScript"],
            "frameworks": ["FastAPI", "React", "PostgreSQL"],
            "platforms": ["Web"],
            "deployment_targets": ["CLOUD"],
            "scope": "FULL_STACK",
            "performance": "10K concurrent users",
            "security": "OAuth2",
            "scalability": None,
            "reliability": None,
            "maintainability": None,
            "constraints": [
                {"description": "Must use WebSocket", "priority": "MUST_HAVE"},
            ],
            "changes_summary": "Added PostgreSQL as database",
        }
        refiner = _make_refiner(response_json=response)
        spec = _make_spec()

        updated = refiner.clarify(
            spec,
            question="What database?",
            answer="PostgreSQL",
        )

        assert isinstance(updated, RepositorySpec)
        assert len(updated.refinement_history) == 1
        entry = updated.refinement_history[0]
        assert entry.action == "clarify"
        assert "What database?" in entry.details
        assert "PostgreSQL" in entry.details

    def test_empty_question_raises(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        with pytest.raises(ValueError, match="Question must not be empty"):
            refiner.clarify(spec, question="", answer="Something")

    def test_empty_answer_raises(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        with pytest.raises(ValueError, match="Answer must not be empty"):
            refiner.clarify(spec, question="What?", answer="")

    def test_whitespace_stripped(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        with pytest.raises(ValueError, match="Question must not be empty"):
            refiner.clarify(spec, question="   ", answer="Fine")

    def test_llm_called_with_clarify_action(self) -> None:
        gw = _make_mock_gateway()
        tpl = _make_mock_templates()
        refiner = SpecRefiner(gateway=gw, templates=tpl)
        spec = _make_spec()

        refiner.clarify(spec, question="What DB?", answer="Postgres")

        render_kwargs = tpl.render.call_args.kwargs
        assert render_kwargs["action"] == "clarify"
        assert "What DB?" in render_kwargs["details"]
        assert "Postgres" in render_kwargs["details"]

    def test_does_not_mutate_original(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        original_history = len(spec.refinement_history)

        updated = refiner.clarify(spec, "Q?", "A.")
        assert len(spec.refinement_history) == original_history
        assert len(updated.refinement_history) == original_history + 1


# ===========================================================================
# suggest_improvements Tests
# ===========================================================================


class TestSuggestImprovements:
    """Tests for SpecRefiner.suggest_improvements."""

    def _suggestion_response(self) -> dict[str, Any]:
        return {
            "suggestions": [
                {
                    "category": "missing_requirement",
                    "title": "Add authentication",
                    "description": "No authentication mechanism specified",
                    "priority": "MUST_HAVE",
                },
                {
                    "category": "quality_concern",
                    "title": "Add reliability requirements",
                    "description": "No uptime or failover requirements",
                    "priority": "SHOULD_HAVE",
                },
                {
                    "category": "best_practice",
                    "title": "Consider CI/CD",
                    "description": "Add continuous integration pipeline",
                    "priority": "NICE_TO_HAVE",
                },
            ],
            "completeness_score": 0.6,
            "summary": "Good foundation but missing security and reliability",
        }

    def test_returns_suggestions(self) -> None:
        gw = MagicMock()
        gw.complete.return_value = json.dumps(self._suggestion_response())
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        result = refiner.suggest_improvements(spec)

        assert isinstance(result, SuggestionResponse)
        assert len(result.suggestions) == 3
        assert result.completeness_score == 0.6
        assert "missing security" in result.summary

    def test_suggestion_categories(self) -> None:
        gw = MagicMock()
        gw.complete.return_value = json.dumps(self._suggestion_response())
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        result = refiner.suggest_improvements(spec)

        categories = [s.category for s in result.suggestions]
        assert "missing_requirement" in categories
        assert "quality_concern" in categories
        assert "best_practice" in categories

    def test_does_not_modify_spec(self) -> None:
        """suggest_improvements is read-only."""
        gw = MagicMock()
        gw.complete.return_value = json.dumps(self._suggestion_response())
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()
        original_data = spec.model_dump()

        refiner.suggest_improvements(spec)

        assert spec.model_dump() == original_data

    def test_uses_suggestion_template(self) -> None:
        gw = MagicMock()
        gw.complete.return_value = json.dumps(self._suggestion_response())
        tpl = _make_mock_templates()
        config = RefinerConfig(suggestion_template="my_suggest")
        refiner = SpecRefiner(config=config, gateway=gw, templates=tpl)
        spec = _make_spec()

        refiner.suggest_improvements(spec)

        tpl.render.assert_called_once()
        assert tpl.render.call_args.args[0] == "my_suggest"

    def test_max_suggestions_limit(self) -> None:
        """Only max_suggestions should be returned even if LLM gives more."""
        many_suggestions = {
            "suggestions": [
                {"title": f"Suggestion {i}", "description": f"Desc {i}"}
                for i in range(20)
            ],
            "completeness_score": 0.3,
            "summary": "Many suggestions",
        }
        gw = MagicMock()
        gw.complete.return_value = json.dumps(many_suggestions)
        config = RefinerConfig(max_suggestions=5)
        refiner = SpecRefiner(config=config, gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        result = refiner.suggest_improvements(spec)
        assert len(result.suggestions) <= 5

    def test_malformed_suggestions_skipped(self) -> None:
        """Malformed suggestion entries should be skipped gracefully."""
        response = {
            "suggestions": [
                {"title": "Valid", "description": "This is valid"},
                "not a dict",
                42,
                {"title": "Also valid", "description": "Also fine"},
            ],
            "completeness_score": 0.5,
            "summary": "Mixed",
        }
        gw = MagicMock()
        gw.complete.return_value = json.dumps(response)
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        result = refiner.suggest_improvements(spec)
        assert len(result.suggestions) == 2

    def test_invalid_completeness_score_clamped(self) -> None:
        """Non-numeric completeness scores should default to 0.0."""
        response = {
            "suggestions": [],
            "completeness_score": "high",
            "summary": "Test",
        }
        gw = MagicMock()
        gw.complete.return_value = json.dumps(response)
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        result = refiner.suggest_improvements(spec)
        assert result.completeness_score == 0.0

    def test_empty_suggestions_response(self) -> None:
        """Empty suggestions list should be handled gracefully."""
        response = {
            "suggestions": [],
            "completeness_score": 0.95,
            "summary": "Excellent spec!",
        }
        gw = MagicMock()
        gw.complete.return_value = json.dumps(response)
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        result = refiner.suggest_improvements(spec)
        assert len(result.suggestions) == 0
        assert result.completeness_score == 0.95


# ===========================================================================
# get_history Tests
# ===========================================================================


class TestGetHistory:
    """Tests for SpecRefiner.get_history."""

    def test_empty_history(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()
        history = refiner.get_history(spec)
        assert history == []

    def test_returns_entries(self) -> None:
        refiner = _make_refiner()
        spec = _make_spec()

        # Perform two refinements
        spec = refiner.add_requirement(spec, "Add offline mode")
        spec = refiner.add_requirement(spec, "Add push notifications")

        history = refiner.get_history(spec)
        assert len(history) == 2
        assert all(isinstance(e, RefinementEntry) for e in history)
        assert history[0].action == "add_requirement"
        assert "offline mode" in history[0].details
        assert "push notifications" in history[1].details

    def test_returns_copy(self) -> None:
        """get_history should return a new list, not the original."""
        refiner = _make_refiner()
        spec = _make_spec()
        spec = refiner.add_requirement(spec, "Add feature")

        history1 = refiner.get_history(spec)
        history2 = refiner.get_history(spec)

        assert history1 is not history2
        assert len(history1) == len(history2)


# ===========================================================================
# _parse_json_response Tests
# ===========================================================================


class TestParseJsonResponse:
    """Tests for SpecRefiner._parse_json_response."""

    def _refiner(self) -> SpecRefiner:
        return SpecRefiner(gateway=MagicMock(), templates=MagicMock())

    def test_valid_json(self) -> None:
        refiner = self._refiner()
        result = refiner._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fences(self) -> None:
        refiner = self._refiner()
        result = refiner._parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_plain_fences(self) -> None:
        refiner = self._refiner()
        result = refiner._parse_json_response('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_whitespace_padded(self) -> None:
        refiner = self._refiner()
        result = refiner._parse_json_response('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_invalid_json_raises(self) -> None:
        refiner = self._refiner()
        with pytest.raises(RefinementError, match="not valid JSON"):
            refiner._parse_json_response("not json at all")

    def test_non_object_raises(self) -> None:
        refiner = self._refiner()
        with pytest.raises(RefinementError, match="not a JSON object"):
            refiner._parse_json_response("[1, 2, 3]")

    def test_error_includes_preview(self) -> None:
        refiner = self._refiner()
        bad = "x" * 300
        with pytest.raises(RefinementError, match="Response preview"):
            refiner._parse_json_response(bad)


# ===========================================================================
# _spec_to_template_vars Tests
# ===========================================================================


class TestSpecToTemplateVars:
    """Tests for SpecRefiner._spec_to_template_vars."""

    def test_basic_conversion(self) -> None:
        refiner = SpecRefiner(gateway=MagicMock(), templates=MagicMock())
        spec = _make_spec()

        vars_ = refiner._spec_to_template_vars(spec)

        assert vars_["description"] == spec.description
        assert vars_["core_functionality"] == "A real-time chat application"
        assert vars_["languages"] == ["Python", "TypeScript"]
        assert vars_["frameworks"] == ["FastAPI", "React"]
        assert vars_["platforms"] == ["Web"]
        assert vars_["scope"] == "FULL_STACK"
        assert vars_["performance"] == "10K concurrent users"
        assert vars_["security"] == "OAuth2"
        assert vars_["scalability"] is None

    def test_constraints_conversion(self) -> None:
        refiner = SpecRefiner(gateway=MagicMock(), templates=MagicMock())
        spec = _make_spec()

        vars_ = refiner._spec_to_template_vars(spec)

        assert len(vars_["constraints"]) == 1
        c = vars_["constraints"][0]
        assert c["description"] == "Must use WebSocket for real-time"
        assert c["priority"] == "MUST_HAVE"
        assert c["category"] == "architecture"

    def test_none_scope(self) -> None:
        refiner = SpecRefiner(gateway=MagicMock(), templates=MagicMock())
        spec = _make_spec()
        spec.technical_requirements.scope = None

        vars_ = refiner._spec_to_template_vars(spec)
        assert vars_["scope"] is None

    def test_empty_spec(self) -> None:
        refiner = SpecRefiner(gateway=MagicMock(), templates=MagicMock())
        spec = RepositorySpec(description="Minimal test specification here")

        vars_ = refiner._spec_to_template_vars(spec)
        assert vars_["languages"] == []
        assert vars_["frameworks"] == []
        assert vars_["constraints"] == []
        assert vars_["core_functionality"] is None


# ===========================================================================
# _apply_parsed_updates Tests
# ===========================================================================


class TestApplyParsedUpdates:
    """Tests for SpecRefiner._apply_parsed_updates."""

    def _refiner(self) -> SpecRefiner:
        return SpecRefiner(gateway=MagicMock(), templates=MagicMock())

    def test_updates_languages(self) -> None:
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {"languages": ["Python", "Go"]}

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert updated.technical_requirements.languages == ["Python", "Go"]

    def test_updates_frameworks(self) -> None:
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {"frameworks": ["Django", "Vue"]}

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert updated.technical_requirements.frameworks == ["Django", "Vue"]

    def test_updates_deployment_targets(self) -> None:
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {"deployment_targets": ["SERVERLESS", "EDGE"]}

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert DeploymentTarget.SERVERLESS in updated.technical_requirements.deployment_targets
        assert DeploymentTarget.EDGE in updated.technical_requirements.deployment_targets

    def test_updates_scope(self) -> None:
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {"scope": "BACKEND_ONLY"}

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert updated.technical_requirements.scope == ScopeType.BACKEND_ONLY

    def test_updates_quality_attributes(self) -> None:
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {
            "performance": "sub-second",
            "scalability": "auto-scaling",
            "reliability": "99.99% uptime",
        }

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert updated.quality_attributes.performance == "sub-second"
        assert updated.quality_attributes.scalability == "auto-scaling"
        assert updated.quality_attributes.reliability == "99.99% uptime"

    def test_updates_constraints(self) -> None:
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {
            "constraints": [
                {"description": "New constraint", "priority": "MUST_HAVE"},
            ],
        }

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert len(updated.constraints) == 1
        assert updated.constraints[0].description == "New constraint"

    def test_preserves_unchanged_fields(self) -> None:
        """Fields not in parsed dict should be preserved from original."""
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {"core_functionality": "Updated functionality"}

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert updated.core_functionality == "Updated functionality"
        # Everything else preserved
        assert updated.technical_requirements.languages == ["Python", "TypeScript"]
        assert updated.quality_attributes.performance == "10K concurrent users"

    def test_preserves_id_and_description(self) -> None:
        """Spec ID and description should never change via updates."""
        refiner = self._refiner()
        spec = _make_spec()
        original_id = spec.id
        parsed = {"core_functionality": "New"}

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert updated.id == original_id
        assert updated.description == spec.description

    def test_empty_parsed_preserves_all(self) -> None:
        """Empty parsed dict should return a spec identical to original."""
        refiner = self._refiner()
        spec = _make_spec()
        updated = refiner._apply_parsed_updates(spec, {})

        assert updated.core_functionality == spec.core_functionality
        assert updated.technical_requirements.languages == spec.technical_requirements.languages

    def test_malformed_constraints_skipped(self) -> None:
        """Malformed constraint dicts in parsed should be skipped."""
        refiner = self._refiner()
        spec = _make_spec()
        parsed = {
            "constraints": [
                {"description": "Valid", "priority": "MUST_HAVE"},
                "not a dict",
                {"description": "Also valid", "priority": "SHOULD_HAVE"},
            ],
        }

        updated = refiner._apply_parsed_updates(spec, parsed)
        assert len(updated.constraints) == 2


# ===========================================================================
# Full Pipeline Tests
# ===========================================================================


class TestFullPipeline:
    """Integration-like tests for sequential refinement operations."""

    def test_add_then_remove(self) -> None:
        """Add a requirement then remove a constraint."""
        refiner = _make_refiner()
        spec = _make_spec()

        # Add requirement
        spec = refiner.add_requirement(spec, "Support offline mode")
        assert len(spec.refinement_history) == 1

        # Remove a constraint (get first one's ID)
        if spec.constraints:
            cid = spec.constraints[0].id
            spec = refiner.remove_requirement(spec, cid)
            assert len(spec.refinement_history) == 2
            assert spec.refinement_history[1].action == "remove_requirement"

    def test_multiple_adds(self) -> None:
        """Multiple sequential add_requirements."""
        refiner = _make_refiner()
        spec = _make_spec()

        spec = refiner.add_requirement(spec, "Add offline mode")
        spec = refiner.add_requirement(spec, "Add push notifications")
        spec = refiner.add_requirement(spec, "Add analytics")

        assert len(spec.refinement_history) == 3
        actions = [e.action for e in spec.refinement_history]
        assert all(a == "add_requirement" for a in actions)

    def test_add_clarify_suggest(self) -> None:
        """Full pipeline: add requirement, clarify, then get suggestions."""
        suggestion_response = {
            "suggestions": [
                {"title": "Add caching", "description": "Consider Redis"},
            ],
            "completeness_score": 0.8,
            "summary": "Good spec",
        }
        gw = MagicMock()
        # First two calls return refinement JSON, third returns suggestions
        gw.complete.side_effect = [
            json.dumps({
                "core_functionality": "Chat app",
                "languages": ["Python"],
                "frameworks": ["FastAPI"],
                "platforms": ["Web"],
                "constraints": [],
                "changes_summary": "Added feature",
            }),
            json.dumps({
                "core_functionality": "Chat with Redis",
                "languages": ["Python"],
                "frameworks": ["FastAPI", "Redis"],
                "platforms": ["Web"],
                "constraints": [],
                "changes_summary": "Clarified storage",
            }),
            json.dumps(suggestion_response),
        ]
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        spec = refiner.add_requirement(spec, "Add caching")
        spec = refiner.clarify(spec, "What cache?", "Redis")
        suggestions = refiner.suggest_improvements(spec)

        assert len(spec.refinement_history) == 2
        assert isinstance(suggestions, SuggestionResponse)
        assert len(suggestions.suggestions) == 1

    def test_history_preserves_order(self) -> None:
        """History entries should be in chronological order."""
        refiner = _make_refiner()
        spec = _make_spec()

        spec = refiner.add_requirement(spec, "First change")
        spec = refiner.add_requirement(spec, "Second change")

        history = refiner.get_history(spec)
        assert len(history) == 2
        # Timestamps should be ordered
        assert history[0].timestamp <= history[1].timestamp
        assert "First change" in history[0].details
        assert "Second change" in history[1].details


# ===========================================================================
# Error Handling Tests
# ===========================================================================


class TestErrorHandling:
    """Tests for error conditions."""

    def test_invalid_json_from_llm(self) -> None:
        """Invalid JSON from LLM should raise RefinementError."""
        gw = MagicMock()
        gw.complete.return_value = "This is not JSON"
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        with pytest.raises(RefinementError, match="not valid JSON"):
            refiner.add_requirement(spec, "Add feature")

    def test_gateway_error_propagates(self) -> None:
        """Gateway errors should propagate through."""
        gw = MagicMock()
        gw.complete.side_effect = RuntimeError("API down")
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        with pytest.raises(RuntimeError, match="API down"):
            refiner.add_requirement(spec, "Add feature")

    def test_suggestion_invalid_json(self) -> None:
        """Invalid JSON in suggest_improvements should raise RefinementError."""
        gw = MagicMock()
        gw.complete.return_value = "not json"
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        with pytest.raises(RefinementError, match="not valid JSON"):
            refiner.suggest_improvements(spec)

    def test_clarify_invalid_json(self) -> None:
        """Invalid JSON in clarify should raise RefinementError."""
        gw = MagicMock()
        gw.complete.return_value = "[]"  # Valid JSON but not a dict
        refiner = SpecRefiner(gateway=gw, templates=_make_mock_templates())
        spec = _make_spec()

        with pytest.raises(RefinementError, match="not a JSON object"):
            refiner.clarify(spec, "Question?", "Answer.")


# ===========================================================================
# Package Import Tests
# ===========================================================================


class TestPackageImports:
    """Tests for spec_parser package exports."""

    def test_import_refiner(self) -> None:
        from zerorepo.spec_parser import SpecRefiner
        assert SpecRefiner is not None

    def test_import_config(self) -> None:
        from zerorepo.spec_parser import RefinerConfig
        assert RefinerConfig is not None

    def test_import_error(self) -> None:
        from zerorepo.spec_parser import RefinementError
        assert issubclass(RefinementError, Exception)

    def test_import_suggestion(self) -> None:
        from zerorepo.spec_parser import Suggestion, SuggestionResponse
        assert Suggestion is not None
        assert SuggestionResponse is not None
