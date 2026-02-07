"""Specification schema models for the User Specification Parser.

Pydantic models that define the structured representation of natural language
repository specifications. Supports parsing, validation, iterative refinement,
and conflict detection for the downstream feature planning pipeline.

Models:
    - RepositorySpec: Top-level specification container
    - TechnicalRequirement: Languages, frameworks, platforms, deployment targets
    - QualityAttributes: Performance, security, scalability, reliability concerns
    - Constraint: Must-have vs nice-to-have requirements with priority levels
    - ReferenceMaterial: URLs, PDFs, code samples with extracted concepts
    - SpecConflict: Detected conflicts between requirements
    - RefinementEntry: History entry for iterative specification refinement
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ConstraintPriority(str, Enum):
    """Priority level for specification constraints."""

    MUST_HAVE = "MUST_HAVE"
    SHOULD_HAVE = "SHOULD_HAVE"
    NICE_TO_HAVE = "NICE_TO_HAVE"


class ReferenceMaterialType(str, Enum):
    """Type classification for reference materials."""

    API_DOCUMENTATION = "API_DOCUMENTATION"
    CODE_SAMPLE = "CODE_SAMPLE"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    GITHUB_REPO = "GITHUB_REPO"
    OTHER = "OTHER"


class ConflictSeverity(str, Enum):
    """Severity level for detected specification conflicts."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ScopeType(str, Enum):
    """Scope boundaries for the repository specification."""

    BACKEND_ONLY = "BACKEND_ONLY"
    FRONTEND_ONLY = "FRONTEND_ONLY"
    FULL_STACK = "FULL_STACK"
    LIBRARY = "LIBRARY"
    CLI_TOOL = "CLI_TOOL"
    OTHER = "OTHER"


class DeploymentTarget(str, Enum):
    """Deployment target environments."""

    CLOUD = "CLOUD"
    ON_PREMISES = "ON_PREMISES"
    EDGE = "EDGE"
    SERVERLESS = "SERVERLESS"
    HYBRID = "HYBRID"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# Component models
# ---------------------------------------------------------------------------


class TechnicalRequirement(BaseModel):
    """Technical requirements extracted from the specification.

    Captures language preferences, framework choices, platform constraints,
    and deployment target selections.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    languages: list[str] = Field(
        default_factory=list,
        description="Target programming languages (e.g., Python, JavaScript, Rust)",
    )
    frameworks: list[str] = Field(
        default_factory=list,
        description="Framework preferences (e.g., React, Django, FastAPI)",
    )
    platforms: list[str] = Field(
        default_factory=list,
        description="Target platforms (e.g., Linux, macOS, Windows, Web, Mobile)",
    )
    deployment_targets: list[DeploymentTarget] = Field(
        default_factory=list,
        description="Deployment environments",
    )
    scope: Optional[ScopeType] = Field(
        default=None,
        description="Scope boundary for the project",
    )

    @field_validator("languages", "frameworks", "platforms")
    @classmethod
    def validate_non_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure list entries are non-empty after stripping."""
        cleaned = [item.strip() for item in v if item.strip()]
        return cleaned


class QualityAttributes(BaseModel):
    """Quality attributes (non-functional requirements) for the specification.

    Captures performance targets, security requirements, scalability goals,
    reliability expectations, and other quality concerns.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    performance: Optional[str] = Field(
        default=None,
        description="Performance requirements (e.g., '10K concurrent users', '<100ms latency')",
    )
    security: Optional[str] = Field(
        default=None,
        description="Security requirements (e.g., 'OAuth2 authentication', 'OWASP compliance')",
    )
    scalability: Optional[str] = Field(
        default=None,
        description="Scalability requirements (e.g., 'horizontal scaling', '1M daily active users')",
    )
    reliability: Optional[str] = Field(
        default=None,
        description="Reliability requirements (e.g., '99.9% uptime', 'graceful degradation')",
    )
    maintainability: Optional[str] = Field(
        default=None,
        description="Maintainability requirements (e.g., 'modular architecture', '80% test coverage')",
    )
    other: dict[str, str] = Field(
        default_factory=dict,
        description="Additional quality attributes as key-value pairs",
    )

    @property
    def has_any(self) -> bool:
        """Return True if any quality attribute is set."""
        return any([
            self.performance is not None,
            self.security is not None,
            self.scalability is not None,
            self.reliability is not None,
            self.maintainability is not None,
            len(self.other) > 0,
        ])


class Constraint(BaseModel):
    """A specific constraint or requirement with priority classification.

    Supports must-have vs nice-to-have categorization as described
    in the PRD (FR-2.4.2).
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique constraint identifier",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Description of the constraint",
    )
    priority: ConstraintPriority = Field(
        default=ConstraintPriority.SHOULD_HAVE,
        description="Priority level of this constraint",
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional category for grouping constraints (e.g., 'security', 'performance')",
    )


class ReferenceMaterial(BaseModel):
    """Reference material attached to the specification.

    Supports API docs, code samples, research papers, and GitHub repos
    as described in FR-2.4.1 and FR-2.4.4.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique reference material identifier",
    )
    type: ReferenceMaterialType = Field(
        ...,
        description="Type classification of the reference material",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL to the reference material (if web-accessible)",
    )
    title: Optional[str] = Field(
        default=None,
        description="Human-readable title for the reference",
    )
    content: Optional[str] = Field(
        default=None,
        description="Raw text content (for inline snippets or extracted text)",
    )
    extracted_concepts: list[str] = Field(
        default_factory=list,
        description="Key concepts extracted from this material",
    )

    @model_validator(mode="after")
    def validate_reference_material(self) -> ReferenceMaterial:
        """Validate that at least one of url or content is provided."""
        if self.url is None and self.content is None:
            raise ValueError(
                "At least one of 'url' or 'content' must be provided "
                "for a reference material"
            )
        return self

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: Optional[str]) -> Optional[str]:
        """Basic URL format validation."""
        if v is None:
            return v
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://") or v.startswith("file://")):
            raise ValueError(
                f"URL must start with 'http://', 'https://', or 'file://': got '{v}'"
            )
        return v


class SpecConflict(BaseModel):
    """A detected conflict between specification requirements.

    Used by the conflict detector (Task 2.4.4) to flag incompatible
    requirements with severity levels and suggested resolutions.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique conflict identifier",
    )
    severity: ConflictSeverity = Field(
        ...,
        description="Severity level of the conflict",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Description of the detected conflict",
    )
    conflicting_fields: list[str] = Field(
        default_factory=list,
        description="Field paths involved in the conflict",
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggested resolution for the conflict",
    )


class RefinementEntry(BaseModel):
    """A single refinement history entry for iterative spec updates.

    Tracks the history of changes made during iterative refinement
    (FR-2.4.3) so users can review and revert modifications.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique refinement entry identifier",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this refinement was applied",
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Description of the refinement action (e.g., 'add_requirement', 'remove_requirement', 'clarify')",
    )
    details: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Detailed description of what was changed",
    )
    previous_value: Optional[str] = Field(
        default=None,
        description="The previous value before this refinement (for undo support)",
    )


# ---------------------------------------------------------------------------
# Top-level specification model
# ---------------------------------------------------------------------------


class RepositorySpec(BaseModel):
    """Top-level repository specification container.

    Structures a natural language repository description into validated
    components for consumption by the feature planning pipeline (Epics 2.1-2.3).

    Supports:
    - Natural language description (50-5000 words as per FR-2.4.1)
    - Technical requirements (languages, frameworks, platforms)
    - Quality attributes (performance, security, scalability)
    - Constraints with priority classification (must-have vs nice-to-have)
    - Reference materials (API docs, code samples, papers)
    - Conflict detection results
    - Refinement history for iterative updates

    Example:
        >>> spec = RepositorySpec(
        ...     description="Build a real-time chat app with React and WebSocket",
        ...     core_functionality="real-time messaging between users",
        ...     technical_requirements=TechnicalRequirement(
        ...         languages=["TypeScript", "Python"],
        ...         frameworks=["React", "FastAPI"],
        ...         scope=ScopeType.FULL_STACK,
        ...     ),
        ... )
        >>> spec.description
        'Build a real-time chat app with React and WebSocket'
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique specification identifier",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description=(
            "Natural language repository description (50-5000 words recommended). "
            "This is the raw input from the user."
        ),
    )
    core_functionality: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Extracted core functionality summary (what the repository does)",
    )
    technical_requirements: TechnicalRequirement = Field(
        default_factory=TechnicalRequirement,
        description="Technical requirements (languages, frameworks, platforms)",
    )
    quality_attributes: QualityAttributes = Field(
        default_factory=QualityAttributes,
        description="Quality attributes (performance, security, scalability)",
    )
    constraints: list[Constraint] = Field(
        default_factory=list,
        description="Explicit constraints with priority classification",
    )
    references: list[ReferenceMaterial] = Field(
        default_factory=list,
        description="Reference materials (API docs, code samples, papers)",
    )
    conflicts: list[SpecConflict] = Field(
        default_factory=list,
        description="Detected conflicts between requirements",
    )
    refinement_history: list[RefinementEntry] = Field(
        default_factory=list,
        description="History of iterative refinement changes",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata for this specification",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this specification was first created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this specification was last updated",
    )

    @field_validator("description")
    @classmethod
    def validate_description_not_trivial(cls, v: str) -> str:
        """Validate that description has meaningful content beyond minimum length."""
        words = v.split()
        if len(words) < 3:
            raise ValueError(
                f"Description must contain at least 3 words, got {len(words)}"
            )
        return v

    @property
    def has_conflicts(self) -> bool:
        """Return True if any conflicts have been detected."""
        return len(self.conflicts) > 0

    @property
    def blocking_conflicts(self) -> list[SpecConflict]:
        """Return only ERROR-severity conflicts that block processing."""
        return [c for c in self.conflicts if c.severity == ConflictSeverity.ERROR]

    @property
    def must_have_constraints(self) -> list[Constraint]:
        """Return only MUST_HAVE priority constraints."""
        return [c for c in self.constraints if c.priority == ConstraintPriority.MUST_HAVE]

    @property
    def nice_to_have_constraints(self) -> list[Constraint]:
        """Return only NICE_TO_HAVE priority constraints."""
        return [c for c in self.constraints if c.priority == ConstraintPriority.NICE_TO_HAVE]

    def add_constraint(self, constraint: Constraint) -> None:
        """Add a constraint to the specification."""
        self.constraints.append(constraint)

    def add_reference(self, reference: ReferenceMaterial) -> None:
        """Add a reference material to the specification."""
        self.references.append(reference)

    def add_conflict(self, conflict: SpecConflict) -> None:
        """Add a detected conflict to the specification."""
        self.conflicts.append(conflict)

    def add_refinement(self, entry: RefinementEntry) -> None:
        """Record a refinement history entry and update the timestamp."""
        self.refinement_history.append(entry)
        self.updated_at = datetime.now(timezone.utc)

    def to_json(self, indent: int = 2) -> str:
        """Serialize the specification to a JSON string.

        Args:
            indent: JSON indentation level for pretty formatting.

        Returns:
            A JSON string representation of the specification.
        """
        import json

        return json.dumps(
            self.model_dump(mode="json"),
            indent=indent,
            default=str,
        )

    @classmethod
    def from_json(cls, json_str: str) -> RepositorySpec:
        """Deserialize a specification from a JSON string.

        Args:
            json_str: A JSON string previously produced by to_json().

        Returns:
            A new RepositorySpec instance populated from the JSON data.

        Raises:
            ValueError: If the JSON is invalid or contains invalid data.
        """
        import json

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        return cls.model_validate(data)

    def __eq__(self, other: object) -> bool:
        """Check equality based on all fields."""
        if not isinstance(other, RepositorySpec):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    def __hash__(self) -> int:
        """Hash based on the immutable id field."""
        return hash(self.id)

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"RepositorySpec(id={self.id!s:.8}, "
            f"description={self.description[:50]!r}..., "
            f"constraints={len(self.constraints)}, "
            f"references={len(self.references)})"
        )
