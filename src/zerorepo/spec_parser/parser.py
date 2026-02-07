"""NLP-based specification parser using the LLM Gateway.

Implements Task 2.4.2 from PRD-RPG-P2-001: Extracts structured data from
natural language repository descriptions using LLM calls via the LLMGateway.
The output conforms to the RepositorySpec schema defined in Task 2.4.1.

The parser uses a two-phase approach:
1. **Extraction**: LLM parses natural language into a structured intermediate
   JSON response matching ParsedSpecResponse.
2. **Assembly**: The intermediate response is assembled into a fully validated
   RepositorySpec instance with proper enums, UUIDs, and timestamps.

Usage::

    from zerorepo.spec_parser.parser import SpecParser, ParserConfig

    parser = SpecParser()
    spec = parser.parse(
        "Build a real-time chat app with React and WebSocket"
    )
    print(spec.core_functionality)
    print(spec.technical_requirements.frameworks)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zerorepo.llm.gateway import LLMGateway
from zerorepo.llm.models import GatewayConfig, ModelTier
from zerorepo.llm.prompt_templates import PromptTemplate
from zerorepo.spec_parser.models import (
    APIEndpointSpec,
    Component,
    Constraint,
    ConstraintPriority,
    DataFlow,
    DataModelSpec,
    DeploymentTarget,
    Epic,
    FileRecommendation,
    FunctionSpec,
    QualityAttributes,
    RepositorySpec,
    ScopeType,
    TechnicalRequirement,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intermediate response schema (what the LLM returns)
# ---------------------------------------------------------------------------

_VALID_DEPLOYMENT_TARGETS = {t.value for t in DeploymentTarget}
_VALID_SCOPES = {s.value for s in ScopeType}
_VALID_PRIORITIES = {p.value for p in ConstraintPriority}


class ParsedConstraint(BaseModel):
    """Intermediate representation of a constraint from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(default="", description="Constraint description")
    priority: str = Field(default="SHOULD_HAVE", description="Priority level")
    category: Optional[str] = Field(default=None, description="Optional category")


class ParsedEpic(BaseModel):
    """Intermediate representation of an epic from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(default="", description="Epic title")
    description: str = Field(default="", description="Epic description")
    priority: str = Field(default="SHOULD_HAVE", description="Priority level")
    estimated_complexity: Optional[str] = Field(default=None, description="Complexity estimate")
    components: list[str] = Field(default_factory=list, description="Component names in this epic")


class ParsedComponent(BaseModel):
    """Intermediate representation of a component from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(default="", description="Component name")
    description: str = Field(default="", description="Component description")
    component_type: Optional[str] = Field(default=None, description="Component type")
    technologies: list[str] = Field(default_factory=list, description="Technologies used")
    suggested_module: Optional[str] = Field(default=None, description="Suggested Python package name")


class ParsedDataFlow(BaseModel):
    """Intermediate representation of a data flow from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(default="", description="Source component")
    target: str = Field(default="", description="Target component")
    description: str = Field(default="", description="Flow description")
    protocol: Optional[str] = Field(default=None, description="Communication protocol")


class ParsedFileRecommendation(BaseModel):
    """Intermediate representation of a file recommendation from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(default="", description="File/directory path")
    purpose: str = Field(default="", description="Purpose of this file")
    component: Optional[str] = Field(default=None, description="Associated component")


class ParsedFunctionSpec(BaseModel):
    """Intermediate representation of a function spec from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(default="", description="Function name")
    signature: str = Field(default="", description="Typed signature")
    description: str = Field(default="", description="What the function does")
    input_types: list[str] = Field(default_factory=list, description="Input parameter types")
    output_type: str = Field(default="", description="Return type")
    belongs_to_component: Optional[str] = Field(default=None, description="Parent component name")


class ParsedDataModelSpec(BaseModel):
    """Intermediate representation of a data model spec from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(default="", description="Model name")
    fields: list[dict[str, str]] = Field(default_factory=list, description="Field definitions")
    relationships: list[str] = Field(default_factory=list, description="Related model names")


class ParsedAPIEndpointSpec(BaseModel):
    """Intermediate representation of an API endpoint spec from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    method: str = Field(default="GET", description="HTTP method")
    path: str = Field(default="", description="URL path")
    request_schema: str = Field(default="", description="Request body description")
    response_schema: str = Field(default="", description="Response body description")
    belongs_to_component: Optional[str] = Field(default=None, description="Parent component name")


class ParsedSpecResponse(BaseModel):
    """Intermediate JSON schema for the LLM's parsed specification output.

    This schema is intentionally lenient (all strings, no strict enums)
    because LLM output may contain slight variations. The assembly phase
    handles normalization and validation.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    core_functionality: Optional[str] = Field(
        default=None,
        description="Core functionality summary",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Programming languages",
    )
    frameworks: list[str] = Field(
        default_factory=list,
        description="Frameworks and libraries",
    )
    platforms: list[str] = Field(
        default_factory=list,
        description="Target platforms",
    )
    deployment_targets: list[str] = Field(
        default_factory=list,
        description="Deployment environments",
    )
    scope: Optional[str] = Field(
        default=None,
        description="Project scope type",
    )
    performance: Optional[str] = Field(
        default=None,
        description="Performance requirements",
    )
    security: Optional[str] = Field(
        default=None,
        description="Security requirements",
    )
    scalability: Optional[str] = Field(
        default=None,
        description="Scalability requirements",
    )
    reliability: Optional[str] = Field(
        default=None,
        description="Reliability requirements",
    )
    maintainability: Optional[str] = Field(
        default=None,
        description="Maintainability requirements",
    )
    constraints: list[ParsedConstraint] = Field(
        default_factory=list,
        description="Extracted constraints",
    )
    epics: list[ParsedEpic] = Field(
        default_factory=list,
        description="High-level feature groupings",
    )
    components: list[ParsedComponent] = Field(
        default_factory=list,
        description="Architectural components",
    )
    data_flows: list[ParsedDataFlow] = Field(
        default_factory=list,
        description="Data flow relationships",
    )
    file_recommendations: list[ParsedFileRecommendation] = Field(
        default_factory=list,
        description="Recommended file structure",
    )
    functions: list[ParsedFunctionSpec] = Field(
        default_factory=list,
        description="Function/method specifications",
    )
    data_models: list[ParsedDataModelSpec] = Field(
        default_factory=list,
        description="Data model specifications",
    )
    api_endpoints: list[ParsedAPIEndpointSpec] = Field(
        default_factory=list,
        description="API endpoint specifications",
    )


# ---------------------------------------------------------------------------
# Parser configuration
# ---------------------------------------------------------------------------


class ParserConfig(BaseModel):
    """Configuration for the specification parser."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    model: str = Field(
        default="gpt-5.2",
        description="Model identifier for LLM calls",
    )
    tier: ModelTier = Field(
        default=ModelTier.CHEAP,
        description="Model tier for cost/quality selection",
    )
    template_name: str = Field(
        default="spec_parsing",
        description="Name of the prompt template to use",
    )
    max_description_length: int = Field(
        default=50000,
        gt=0,
        description="Maximum description length in characters",
    )
    use_json_mode: bool = Field(
        default=True,
        description="Whether to request JSON response format from the LLM",
    )


# ---------------------------------------------------------------------------
# Main parser class
# ---------------------------------------------------------------------------


class SpecParser:
    """LLM-based natural language specification parser.

    Parses free-form repository descriptions into structured RepositorySpec
    instances using the LLMGateway for LLM calls and Jinja2 templates for
    prompt construction.

    Example::

        parser = SpecParser()
        spec = parser.parse(
            "Build a real-time chat application with React, WebSocket, "
            "and PostgreSQL. Must support 10K concurrent users."
        )
        assert "React" in spec.technical_requirements.frameworks
        assert spec.quality_attributes.scalability is not None

    Attributes:
        config: Parser configuration (model, template, etc.)
        gateway: LLMGateway instance for making LLM calls
        templates: PromptTemplate instance for rendering prompts
    """

    def __init__(
        self,
        config: ParserConfig | None = None,
        gateway: LLMGateway | None = None,
        templates: PromptTemplate | None = None,
    ) -> None:
        """Initialise the parser.

        Args:
            config: Parser configuration. Defaults to ParserConfig().
            gateway: Pre-configured LLMGateway. If None, creates a new one.
            templates: Pre-configured PromptTemplate. If None, creates one
                using the default template directory.
        """
        self.config = config or ParserConfig()
        self.gateway = gateway or LLMGateway()
        self.templates = templates or PromptTemplate()

    def parse(
        self,
        description: str,
        context: str | None = None,
    ) -> RepositorySpec:
        """Parse a natural language description into a RepositorySpec.

        This is the main entry point. It:
        1. Renders the prompt template with the description
        2. Calls the LLM via complete_json or complete
        3. Parses the intermediate response
        4. Assembles the final RepositorySpec

        Args:
            description: Natural language repository description (10-50000 chars).
            context: Optional additional context to include in the prompt.

        Returns:
            A validated RepositorySpec instance.

        Raises:
            ValueError: If the description is empty or too long.
            zerorepo.llm.exceptions.ConfigurationError: If LLM is misconfigured.
            zerorepo.llm.exceptions.RetryExhaustedError: If LLM calls fail.
            SpecParserError: If the LLM response cannot be parsed.
        """
        # Validate input
        description = description.strip()
        if len(description) < 10:
            raise ValueError(
                f"Description must be at least 10 characters, got {len(description)}"
            )
        if len(description) > self.config.max_description_length:
            raise ValueError(
                f"Description exceeds maximum length of "
                f"{self.config.max_description_length} characters"
            )

        # Render prompt
        prompt = self.templates.render(
            self.config.template_name,
            description=description,
            context=context or "",
        )
        logger.debug("Rendered spec parsing prompt (%d chars)", len(prompt))

        # Call LLM
        messages = [{"role": "user", "content": prompt}]

        raw_response = self._call_llm(messages)
        logger.debug("LLM response received (%d chars)", len(raw_response))

        # Parse intermediate response
        parsed = self._parse_response(raw_response)

        # Assemble final RepositorySpec
        spec = self._assemble_spec(description, parsed)

        logger.info(
            "Parsed specification: %d languages, %d frameworks, %d constraints",
            len(spec.technical_requirements.languages),
            len(spec.technical_requirements.frameworks),
            len(spec.constraints),
        )

        return spec

    def _call_llm(self, messages: list[dict[str, Any]]) -> str:
        """Call the LLM and return the raw response text.

        Uses temperature=0 for deterministic, reproducible spec extraction.

        Args:
            messages: Chat messages for the LLM.

        Returns:
            Raw response text from the LLM.
        """
        kwargs: dict[str, Any] = {"temperature": 0}
        if self.config.use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        return self.gateway.complete(
            messages=messages,
            model=self.config.model,
            tier=self.config.tier,
            **kwargs,
        )

    def _parse_response(self, raw_response: str) -> ParsedSpecResponse:
        """Parse the raw LLM response into a ParsedSpecResponse.

        Handles common LLM output quirks like markdown code blocks and
        trailing text after JSON.

        Args:
            raw_response: Raw text from the LLM.

        Returns:
            A ParsedSpecResponse instance.

        Raises:
            SpecParserError: If the response cannot be parsed as valid JSON.
        """
        text = raw_response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            # Remove opening fence (e.g. ```json)
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3].rstrip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise SpecParserError(
                f"LLM response is not valid JSON: {e}\n"
                f"Response preview: {text[:200]}"
            ) from e

        try:
            return ParsedSpecResponse.model_validate(data)
        except Exception as e:
            raise SpecParserError(
                f"LLM response does not match expected schema: {e}"
            ) from e

    def _assemble_spec(
        self,
        description: str,
        parsed: ParsedSpecResponse,
    ) -> RepositorySpec:
        """Assemble a RepositorySpec from the parsed intermediate response.

        Handles normalization of enum values, filtering of invalid entries,
        and construction of properly typed Pydantic models. Includes a
        validation pass that logs warnings for missing critical fields.

        Args:
            description: The original user description.
            parsed: The intermediate parsed response from the LLM.

        Returns:
            A validated RepositorySpec instance.
        """
        # Build TechnicalRequirement
        deployment_targets = _normalize_deployment_targets(parsed.deployment_targets)
        scope = _normalize_scope(parsed.scope)

        technical_requirements = TechnicalRequirement(
            languages=parsed.languages,
            frameworks=parsed.frameworks,
            platforms=parsed.platforms,
            deployment_targets=deployment_targets,
            scope=scope,
        )

        # Build QualityAttributes
        quality_attributes = QualityAttributes(
            performance=parsed.performance,
            security=parsed.security,
            scalability=parsed.scalability,
            reliability=parsed.reliability,
            maintainability=parsed.maintainability,
        )

        # Build Constraints
        constraints = _normalize_constraints(parsed.constraints)

        # Build Epics
        epics = _normalize_epics(parsed.epics)

        # Build Components
        components = _normalize_components(parsed.components)

        # Build DataFlows
        data_flows = _normalize_data_flows(parsed.data_flows)

        # Build FileRecommendations
        file_recommendations = _normalize_file_recommendations(
            parsed.file_recommendations
        )

        # Build FunctionSpecs
        functions = _normalize_functions(parsed.functions)

        # Build DataModelSpecs
        data_models = _normalize_data_models(parsed.data_models)

        # Build APIEndpointSpecs
        api_endpoints = _normalize_api_endpoints(parsed.api_endpoints)

        # Assemble RepositorySpec
        spec = RepositorySpec(
            description=description,
            core_functionality=parsed.core_functionality,
            technical_requirements=technical_requirements,
            quality_attributes=quality_attributes,
            constraints=constraints,
            epics=epics,
            components=components,
            data_flows=data_flows,
            functions=functions,
            data_models=data_models,
            api_endpoints=api_endpoints,
            file_recommendations=file_recommendations,
        )

        # Validation pass: warn about missing critical fields
        _validation_pass(spec)

        return spec


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class SpecParserError(Exception):
    """Raised when the specification parser encounters an unrecoverable error.

    Examples: LLM response is not valid JSON, response doesn't match schema,
    or required fields are missing from the parsed output.
    """


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize_deployment_targets(
    raw_targets: list[str],
) -> list[DeploymentTarget]:
    """Normalize deployment target strings to DeploymentTarget enum values.

    Handles case variations and unknown values (mapped to OTHER).

    Args:
        raw_targets: List of deployment target strings from LLM.

    Returns:
        List of DeploymentTarget enum values.
    """
    result: list[DeploymentTarget] = []
    for target in raw_targets:
        normalized = target.strip().upper().replace(" ", "_").replace("-", "_")
        if normalized in _VALID_DEPLOYMENT_TARGETS:
            result.append(DeploymentTarget(normalized))
        else:
            logger.warning(
                "Unknown deployment target '%s', mapping to OTHER", target
            )
            result.append(DeploymentTarget.OTHER)
    return result


def _normalize_scope(raw_scope: str | None) -> ScopeType | None:
    """Normalize a scope string to a ScopeType enum value.

    Handles case variations and common synonyms.

    Args:
        raw_scope: Scope string from LLM, or None.

    Returns:
        ScopeType enum value, or None if input is None.
    """
    if raw_scope is None:
        return None

    normalized = raw_scope.strip().upper().replace(" ", "_").replace("-", "_")

    # Handle common synonyms
    synonyms: dict[str, str] = {
        "BACKEND": "BACKEND_ONLY",
        "FRONTEND": "FRONTEND_ONLY",
        "FULLSTACK": "FULL_STACK",
        "FULL-STACK": "FULL_STACK",
        "LIB": "LIBRARY",
        "CLI": "CLI_TOOL",
        "COMMAND_LINE": "CLI_TOOL",
    }

    normalized = synonyms.get(normalized, normalized)

    if normalized in _VALID_SCOPES:
        return ScopeType(normalized)

    logger.warning("Unknown scope '%s', mapping to OTHER", raw_scope)
    return ScopeType.OTHER


def _normalize_constraint_priority(
    raw_priority: str,
) -> ConstraintPriority:
    """Normalize a priority string to a ConstraintPriority enum value.

    Args:
        raw_priority: Priority string from LLM.

    Returns:
        ConstraintPriority enum value.
    """
    normalized = raw_priority.strip().upper().replace(" ", "_").replace("-", "_")

    # Handle common synonyms
    synonyms: dict[str, str] = {
        "REQUIRED": "MUST_HAVE",
        "MANDATORY": "MUST_HAVE",
        "IMPORTANT": "SHOULD_HAVE",
        "OPTIONAL": "NICE_TO_HAVE",
    }

    normalized = synonyms.get(normalized, normalized)

    if normalized in _VALID_PRIORITIES:
        return ConstraintPriority(normalized)

    return ConstraintPriority.SHOULD_HAVE


def _normalize_constraints(
    raw_constraints: list[ParsedConstraint],
) -> list[Constraint]:
    """Normalize parsed constraints into proper Constraint instances.

    Filters out empty descriptions and normalizes priority values.

    Args:
        raw_constraints: List of ParsedConstraint from LLM.

    Returns:
        List of validated Constraint instances.
    """
    result: list[Constraint] = []
    for raw in raw_constraints:
        desc = raw.description.strip()
        if not desc:
            continue

        priority = _normalize_constraint_priority(raw.priority)

        result.append(
            Constraint(
                description=desc,
                priority=priority,
                category=raw.category,
            )
        )
    return result


def _normalize_epics(
    raw_epics: list[ParsedEpic],
) -> list[Epic]:
    """Normalize parsed epics into proper Epic instances.

    Filters out entries with empty titles.

    Args:
        raw_epics: List of ParsedEpic from LLM.

    Returns:
        List of validated Epic instances.
    """
    result: list[Epic] = []
    for raw in raw_epics:
        title = raw.title.strip()
        if not title:
            continue

        priority = _normalize_constraint_priority(raw.priority)

        result.append(
            Epic(
                title=title,
                description=raw.description.strip(),
                priority=priority,
                estimated_complexity=raw.estimated_complexity,
                components=[c.strip() for c in raw.components if c.strip()],
            )
        )
    return result


def _normalize_components(
    raw_components: list[ParsedComponent],
) -> list[Component]:
    """Normalize parsed components into proper Component instances.

    Filters out entries with empty names.

    Args:
        raw_components: List of ParsedComponent from LLM.

    Returns:
        List of validated Component instances.
    """
    result: list[Component] = []
    for raw in raw_components:
        name = raw.name.strip()
        if not name:
            continue

        result.append(
            Component(
                name=name,
                description=raw.description.strip(),
                component_type=raw.component_type,
                technologies=[t.strip() for t in raw.technologies if t.strip()],
                suggested_module=raw.suggested_module.strip() if raw.suggested_module else None,
            )
        )
    return result


def _normalize_data_flows(
    raw_flows: list[ParsedDataFlow],
) -> list[DataFlow]:
    """Normalize parsed data flows into proper DataFlow instances.

    Filters out entries with empty source or target.

    Args:
        raw_flows: List of ParsedDataFlow from LLM.

    Returns:
        List of validated DataFlow instances.
    """
    result: list[DataFlow] = []
    for raw in raw_flows:
        source = raw.source.strip()
        target = raw.target.strip()
        if not source or not target:
            continue

        result.append(
            DataFlow(
                source=source,
                target=target,
                description=raw.description.strip(),
                protocol=raw.protocol,
            )
        )
    return result


def _normalize_file_recommendations(
    raw_recs: list[ParsedFileRecommendation],
) -> list[FileRecommendation]:
    """Normalize parsed file recommendations into proper FileRecommendation instances.

    Filters out entries with empty paths.

    Args:
        raw_recs: List of ParsedFileRecommendation from LLM.

    Returns:
        List of validated FileRecommendation instances.
    """
    result: list[FileRecommendation] = []
    for raw in raw_recs:
        path = raw.path.strip()
        if not path:
            continue

        result.append(
            FileRecommendation(
                path=path,
                purpose=raw.purpose.strip(),
                component=raw.component,
            )
        )
    return result


def _normalize_functions(
    raw_functions: list[ParsedFunctionSpec],
) -> list[FunctionSpec]:
    """Normalize parsed function specs into proper FunctionSpec instances.

    Filters out entries with empty names.

    Args:
        raw_functions: List of ParsedFunctionSpec from LLM.

    Returns:
        List of validated FunctionSpec instances.
    """
    result: list[FunctionSpec] = []
    for raw in raw_functions:
        name = raw.name.strip()
        if not name:
            continue

        result.append(
            FunctionSpec(
                name=name,
                signature=raw.signature.strip(),
                description=raw.description.strip(),
                input_types=[t.strip() for t in raw.input_types if t.strip()],
                output_type=raw.output_type.strip(),
                belongs_to_component=(
                    raw.belongs_to_component.strip()
                    if raw.belongs_to_component
                    else None
                ),
            )
        )
    return result


def _normalize_data_models(
    raw_models: list[ParsedDataModelSpec],
) -> list[DataModelSpec]:
    """Normalize parsed data model specs into proper DataModelSpec instances.

    Filters out entries with empty names.

    Args:
        raw_models: List of ParsedDataModelSpec from LLM.

    Returns:
        List of validated DataModelSpec instances.
    """
    result: list[DataModelSpec] = []
    for raw in raw_models:
        name = raw.name.strip()
        if not name:
            continue

        result.append(
            DataModelSpec(
                name=name,
                fields=raw.fields,
                relationships=[r.strip() for r in raw.relationships if r.strip()],
            )
        )
    return result


def _normalize_api_endpoints(
    raw_endpoints: list[ParsedAPIEndpointSpec],
) -> list[APIEndpointSpec]:
    """Normalize parsed API endpoint specs into proper APIEndpointSpec instances.

    Filters out entries with empty path.

    Args:
        raw_endpoints: List of ParsedAPIEndpointSpec from LLM.

    Returns:
        List of validated APIEndpointSpec instances.
    """
    result: list[APIEndpointSpec] = []
    for raw in raw_endpoints:
        path = raw.path.strip()
        if not path:
            continue

        result.append(
            APIEndpointSpec(
                method=raw.method.strip().upper() or "GET",
                path=path,
                request_schema=raw.request_schema.strip(),
                response_schema=raw.response_schema.strip(),
                belongs_to_component=(
                    raw.belongs_to_component.strip()
                    if raw.belongs_to_component
                    else None
                ),
            )
        )
    return result


def _validation_pass(spec: RepositorySpec) -> None:
    """Run a validation pass on the assembled RepositorySpec.

    Logs warnings for missing critical fields that downstream
    pipeline stages depend on. This does not raise exceptions;
    it provides observability for parse quality.

    Args:
        spec: The assembled RepositorySpec to validate.
    """
    if not spec.core_functionality:
        logger.warning(
            "Validation: core_functionality is empty — downstream planning "
            "may produce lower-quality results"
        )

    if not spec.technical_requirements.languages:
        logger.warning(
            "Validation: no programming languages extracted — "
            "file recommendations may be generic"
        )

    if not spec.technical_requirements.frameworks:
        logger.warning(
            "Validation: no frameworks extracted — "
            "component identification may be incomplete"
        )

    if not spec.epics:
        logger.warning(
            "Validation: no epics extracted — "
            "consider providing a more detailed specification"
        )

    if not spec.components:
        logger.warning(
            "Validation: no components extracted — "
            "architecture analysis may be incomplete"
        )
