"""Iterative specification refinement using the LLM Gateway.

Implements Task 2.4.5 from PRD-RPG-P2-001: Provides an interface for
users to iteratively refine parsed specifications through natural language
commands.  Each refinement is tracked in the specification's history,
enabling review and undo.

Supported operations:
- **add_requirement**: Add a new requirement via LLM re-parsing
- **remove_requirement**: Remove a constraint by ID
- **clarify**: Answer an ambiguous question to update the spec
- **suggest_improvements**: Ask the LLM for specification improvements
- **get_history**: Retrieve the full refinement history

Usage::

    from zerorepo.spec_parser.refinement import SpecRefiner, RefinerConfig

    refiner = SpecRefiner()
    updated_spec = refiner.add_requirement(
        spec, "Support offline mode with IndexedDB"
    )
    suggestions = refiner.suggest_improvements(spec)
    history = refiner.get_history(spec)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zerorepo.llm.gateway import LLMGateway
from zerorepo.llm.models import ModelTier
from zerorepo.llm.prompt_templates import PromptTemplate
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
from zerorepo.spec_parser.parser import (
    SpecParserError,
    _normalize_constraint_priority,
    _normalize_constraints,
    _normalize_deployment_targets,
    _normalize_scope,
    ParsedConstraint,
    ParsedSpecResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class RefinerConfig(BaseModel):
    """Configuration for the specification refiner."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    model: str = Field(
        default="gpt-4o-mini",
        description="Model identifier for LLM calls",
    )
    tier: ModelTier = Field(
        default=ModelTier.CHEAP,
        description="Model tier for cost/quality selection",
    )
    refinement_template: str = Field(
        default="spec_refinement",
        description="Template name for refinement prompts",
    )
    suggestion_template: str = Field(
        default="spec_suggestions",
        description="Template name for suggestion prompts",
    )
    use_json_mode: bool = Field(
        default=True,
        description="Whether to request JSON response format from the LLM",
    )
    max_suggestions: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of suggestions to return",
    )


# ---------------------------------------------------------------------------
# Suggestion model
# ---------------------------------------------------------------------------


class Suggestion(BaseModel):
    """A single improvement suggestion for the specification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(
        default="general",
        description=(
            "Suggestion category: missing_requirement, ambiguous, "
            "technical_gap, quality_concern, or best_practice"
        ),
    )
    title: str = Field(
        default="",
        description="Short title for the suggestion",
    )
    description: str = Field(
        default="",
        description="Detailed explanation of the suggestion",
    )
    priority: str = Field(
        default="SHOULD_HAVE",
        description="Suggested priority level",
    )


class SuggestionResponse(BaseModel):
    """Response model for suggest_improvements, including parsed suggestions."""

    model_config = ConfigDict(str_strip_whitespace=True)

    suggestions: list[Suggestion] = Field(
        default_factory=list,
        description="List of improvement suggestions",
    )
    completeness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall completeness score (0.0-1.0)",
    )
    summary: str = Field(
        default="",
        description="Brief overall assessment of the specification",
    )


# ---------------------------------------------------------------------------
# Refinement error
# ---------------------------------------------------------------------------


class RefinementError(Exception):
    """Raised when a refinement operation fails.

    Examples: invalid constraint ID, LLM response cannot be parsed,
    or the refinement produces an invalid specification.
    """


# ---------------------------------------------------------------------------
# Main refiner class
# ---------------------------------------------------------------------------


class SpecRefiner:
    """Iterative specification refiner using LLM-assisted updates.

    Provides methods to incrementally modify a RepositorySpec through
    natural language commands, with full history tracking.

    Example::

        refiner = SpecRefiner()
        spec = parser.parse("Build a chat app with React")

        # Add a new requirement
        spec = refiner.add_requirement(spec, "Support offline mode")

        # Clarify an ambiguity
        spec = refiner.clarify(
            spec,
            question="What type of database?",
            answer="PostgreSQL for primary storage"
        )

        # Get improvement suggestions
        suggestions = refiner.suggest_improvements(spec)

        # Review history
        history = refiner.get_history(spec)

    Attributes:
        config: Refiner configuration (model, templates, etc.)
        gateway: LLMGateway instance for making LLM calls
        templates: PromptTemplate instance for rendering prompts
    """

    def __init__(
        self,
        config: RefinerConfig | None = None,
        gateway: LLMGateway | None = None,
        templates: PromptTemplate | None = None,
    ) -> None:
        """Initialise the refiner.

        Args:
            config: Refiner configuration. Defaults to RefinerConfig().
            gateway: Pre-configured LLMGateway. If None, creates a new one.
            templates: Pre-configured PromptTemplate. If None, creates one
                using the default template directory.
        """
        self.config = config or RefinerConfig()
        self.gateway = gateway or LLMGateway()
        self.templates = templates or PromptTemplate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_requirement(
        self,
        spec: RepositorySpec,
        requirement_text: str,
        context: str | None = None,
    ) -> RepositorySpec:
        """Add a new requirement to the specification via LLM re-parsing.

        The LLM analyzes the existing spec and the new requirement text,
        then produces an updated specification.  A RefinementEntry is
        recorded in the spec's history.

        Args:
            spec: The current specification to refine.
            requirement_text: Natural language description of the new
                requirement (e.g., "Support offline mode with IndexedDB").
            context: Optional additional context for the LLM.

        Returns:
            A *new* RepositorySpec with the requirement added and history
            entry recorded.  The original spec is not modified.

        Raises:
            ValueError: If requirement_text is empty.
            RefinementError: If the LLM response cannot be parsed.
        """
        requirement_text = requirement_text.strip()
        if not requirement_text:
            raise ValueError("Requirement text must not be empty")

        # Call LLM to re-parse with the new requirement
        parsed = self._call_refinement_llm(
            spec=spec,
            action="add_requirement",
            details=requirement_text,
            context=context,
        )

        # Apply the parsed updates to produce a new spec
        updated = self._apply_parsed_updates(spec, parsed)

        # Record history
        changes_summary = parsed.get("changes_summary", f"Added: {requirement_text}")
        entry = RefinementEntry(
            action="add_requirement",
            details=requirement_text,
            previous_value=None,
        )
        updated.add_refinement(entry)

        logger.info(
            "Added requirement to spec %s: %s",
            spec.id,
            requirement_text[:80],
        )
        return updated

    def remove_requirement(
        self,
        spec: RepositorySpec,
        constraint_id: UUID,
    ) -> RepositorySpec:
        """Remove a constraint from the specification by ID.

        This is a local operation (no LLM call needed). The constraint is
        removed and a RefinementEntry is recorded.

        Args:
            spec: The current specification.
            constraint_id: UUID of the constraint to remove.

        Returns:
            A *new* RepositorySpec with the constraint removed.

        Raises:
            RefinementError: If no constraint with the given ID exists.
        """
        # Find the constraint
        target = None
        for constraint in spec.constraints:
            if constraint.id == constraint_id:
                target = constraint
                break

        if target is None:
            raise RefinementError(
                f"No constraint found with ID {constraint_id}"
            )

        # Create a new spec with the constraint removed
        new_constraints = [c for c in spec.constraints if c.id != constraint_id]

        updated = spec.model_copy(
            update={
                "constraints": new_constraints,
                "refinement_history": list(spec.refinement_history),
                "references": list(spec.references),
                "conflicts": list(spec.conflicts),
            },
        )

        # Record history
        entry = RefinementEntry(
            action="remove_requirement",
            details=f"Removed constraint: {target.description}",
            previous_value=target.description,
        )
        updated.add_refinement(entry)

        logger.info(
            "Removed constraint %s from spec %s: %s",
            constraint_id,
            spec.id,
            target.description[:80],
        )
        return updated

    def clarify(
        self,
        spec: RepositorySpec,
        question: str,
        answer: str,
        context: str | None = None,
    ) -> RepositorySpec:
        """Clarify an ambiguous part of the specification.

        The LLM uses the question-answer pair to update the spec
        with more precise requirements.

        Args:
            spec: The current specification.
            question: The clarifying question (e.g., "What type of database?").
            answer: The user's answer (e.g., "PostgreSQL for primary storage").
            context: Optional additional context.

        Returns:
            A *new* RepositorySpec with the clarification applied.

        Raises:
            ValueError: If question or answer is empty.
            RefinementError: If the LLM response cannot be parsed.
        """
        question = question.strip()
        answer = answer.strip()
        if not question:
            raise ValueError("Question must not be empty")
        if not answer:
            raise ValueError("Answer must not be empty")

        details = f"Q: {question}\nA: {answer}"

        parsed = self._call_refinement_llm(
            spec=spec,
            action="clarify",
            details=details,
            context=context,
        )

        updated = self._apply_parsed_updates(spec, parsed)

        entry = RefinementEntry(
            action="clarify",
            details=details,
            previous_value=None,
        )
        updated.add_refinement(entry)

        logger.info(
            "Clarified spec %s: Q=%s A=%s",
            spec.id,
            question[:40],
            answer[:40],
        )
        return updated

    def suggest_improvements(
        self,
        spec: RepositorySpec,
    ) -> SuggestionResponse:
        """Ask the LLM for improvement suggestions for the specification.

        This is a read-only operation that does not modify the spec.

        Args:
            spec: The specification to analyze.

        Returns:
            A SuggestionResponse with a list of suggestions, completeness
            score, and summary.

        Raises:
            RefinementError: If the LLM response cannot be parsed.
        """
        # Build template variables
        template_vars = self._spec_to_template_vars(spec)

        prompt = self.templates.render(
            self.config.suggestion_template,
            **template_vars,
        )

        messages = [{"role": "user", "content": prompt}]
        raw_response = self._call_llm(messages)

        # Parse response
        try:
            data = self._parse_json_response(raw_response)
        except RefinementError:
            raise

        # Build SuggestionResponse
        raw_suggestions = data.get("suggestions", [])
        suggestions: list[Suggestion] = []
        for raw in raw_suggestions[:self.config.max_suggestions]:
            if isinstance(raw, dict):
                try:
                    suggestions.append(Suggestion.model_validate(raw))
                except Exception:
                    # Skip malformed suggestions
                    logger.warning("Skipping malformed suggestion: %s", raw)
                    continue

        completeness_score = data.get("completeness_score", 0.0)
        if not isinstance(completeness_score, (int, float)):
            completeness_score = 0.0
        completeness_score = max(0.0, min(1.0, float(completeness_score)))

        summary = data.get("summary", "")
        if not isinstance(summary, str):
            summary = ""

        response = SuggestionResponse(
            suggestions=suggestions,
            completeness_score=completeness_score,
            summary=summary,
        )

        logger.info(
            "Generated %d suggestions for spec %s (score: %.2f)",
            len(suggestions),
            spec.id,
            completeness_score,
        )
        return response

    def get_history(
        self,
        spec: RepositorySpec,
    ) -> list[RefinementEntry]:
        """Retrieve the refinement history for a specification.

        Args:
            spec: The specification.

        Returns:
            A list of RefinementEntry instances, ordered by timestamp
            (oldest first).
        """
        return list(spec.refinement_history)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict[str, Any]]) -> str:
        """Call the LLM and return the raw response text.

        Args:
            messages: Chat messages for the LLM.

        Returns:
            Raw response text from the LLM.
        """
        kwargs: dict[str, Any] = {}
        if self.config.use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        return self.gateway.complete(
            messages=messages,
            model=self.config.model,
            tier=self.config.tier,
            **kwargs,
        )

    def _parse_json_response(self, raw_response: str) -> dict[str, Any]:
        """Parse a raw LLM response into a JSON dict.

        Handles markdown code fences and whitespace.

        Args:
            raw_response: Raw text from the LLM.

        Returns:
            Parsed JSON dictionary.

        Raises:
            RefinementError: If the response is not valid JSON.
        """
        text = raw_response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3].rstrip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RefinementError(
                f"LLM response is not valid JSON: {e}\n"
                f"Response preview: {text[:200]}"
            ) from e

        if not isinstance(data, dict):
            raise RefinementError(
                f"LLM response is not a JSON object, got {type(data).__name__}"
            )

        return data

    def _spec_to_template_vars(self, spec: RepositorySpec) -> dict[str, Any]:
        """Convert a RepositorySpec into template variables.

        Args:
            spec: The specification to convert.

        Returns:
            A dict of template variables suitable for Jinja2 rendering.
        """
        constraints_data = []
        for c in spec.constraints:
            constraints_data.append({
                "description": c.description,
                "priority": c.priority.value,
                "category": c.category,
            })

        return {
            "description": spec.description,
            "core_functionality": spec.core_functionality,
            "languages": spec.technical_requirements.languages,
            "frameworks": spec.technical_requirements.frameworks,
            "platforms": spec.technical_requirements.platforms,
            "scope": (
                spec.technical_requirements.scope.value
                if spec.technical_requirements.scope
                else None
            ),
            "performance": spec.quality_attributes.performance,
            "security": spec.quality_attributes.security,
            "scalability": spec.quality_attributes.scalability,
            "reliability": spec.quality_attributes.reliability,
            "maintainability": spec.quality_attributes.maintainability,
            "constraints": constraints_data,
        }

    def _call_refinement_llm(
        self,
        spec: RepositorySpec,
        action: str,
        details: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Call the LLM with the refinement template and return parsed JSON.

        Args:
            spec: The current specification.
            action: The refinement action (e.g., "add_requirement", "clarify").
            details: Details of the refinement request.
            context: Optional additional context.

        Returns:
            Parsed JSON dictionary from the LLM response.

        Raises:
            RefinementError: If the LLM response cannot be parsed.
        """
        template_vars = self._spec_to_template_vars(spec)
        template_vars["action"] = action
        template_vars["details"] = details
        template_vars["context"] = context or ""

        prompt = self.templates.render(
            self.config.refinement_template,
            **template_vars,
        )

        messages = [{"role": "user", "content": prompt}]
        raw_response = self._call_llm(messages)

        return self._parse_json_response(raw_response)

    def _apply_parsed_updates(
        self,
        spec: RepositorySpec,
        parsed: dict[str, Any],
    ) -> RepositorySpec:
        """Apply LLM-parsed updates to a specification.

        Creates a new RepositorySpec by merging the parsed updates into the
        existing spec. Only fields present in the parsed dict are updated.

        Args:
            spec: The original specification.
            parsed: Parsed JSON dict from the LLM refinement response.

        Returns:
            A new RepositorySpec with updates applied.
        """
        # Build updated technical requirements
        languages = parsed.get("languages", spec.technical_requirements.languages)
        frameworks = parsed.get("frameworks", spec.technical_requirements.frameworks)
        platforms = parsed.get("platforms", spec.technical_requirements.platforms)

        raw_targets = parsed.get("deployment_targets")
        if raw_targets is not None and isinstance(raw_targets, list):
            deployment_targets = _normalize_deployment_targets(raw_targets)
        else:
            deployment_targets = list(spec.technical_requirements.deployment_targets)

        raw_scope = parsed.get("scope")
        if raw_scope is not None:
            scope = _normalize_scope(raw_scope) if isinstance(raw_scope, str) else spec.technical_requirements.scope
        else:
            scope = spec.technical_requirements.scope

        technical_requirements = TechnicalRequirement(
            languages=languages if isinstance(languages, list) else spec.technical_requirements.languages,
            frameworks=frameworks if isinstance(frameworks, list) else spec.technical_requirements.frameworks,
            platforms=platforms if isinstance(platforms, list) else spec.technical_requirements.platforms,
            deployment_targets=deployment_targets,
            scope=scope,
        )

        # Build updated quality attributes
        quality_attributes = QualityAttributes(
            performance=parsed.get("performance", spec.quality_attributes.performance),
            security=parsed.get("security", spec.quality_attributes.security),
            scalability=parsed.get("scalability", spec.quality_attributes.scalability),
            reliability=parsed.get("reliability", spec.quality_attributes.reliability),
            maintainability=parsed.get("maintainability", spec.quality_attributes.maintainability),
        )

        # Build updated constraints
        raw_constraints = parsed.get("constraints")
        if raw_constraints is not None and isinstance(raw_constraints, list):
            parsed_constraints = []
            for raw_c in raw_constraints:
                if isinstance(raw_c, dict):
                    try:
                        parsed_constraints.append(
                            ParsedConstraint.model_validate(raw_c)
                        )
                    except Exception:
                        logger.warning("Skipping malformed constraint: %s", raw_c)
                        continue
            constraints = _normalize_constraints(parsed_constraints)
        else:
            constraints = list(spec.constraints)

        # Core functionality
        core_func = parsed.get("core_functionality", spec.core_functionality)

        # Build new spec (preserving id, description, references, conflicts,
        # metadata, and timestamps from original).
        # Deep-copy mutable lists to avoid shared-state mutation between
        # the original and the updated spec.
        updated = spec.model_copy(
            update={
                "core_functionality": core_func,
                "technical_requirements": technical_requirements,
                "quality_attributes": quality_attributes,
                "constraints": constraints,
                "refinement_history": list(spec.refinement_history),
                "references": list(spec.references),
                "conflicts": list(spec.conflicts),
            },
        )

        return updated
