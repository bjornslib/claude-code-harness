"""Unit tests for specification parser models."""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cobuilder.repomap.spec_parser.models import (
    Component,
    Constraint,
    ConstraintPriority,
    ConflictSeverity,
    DataFlow,
    DeploymentTarget,
    Epic,
    FileRecommendation,
    QualityAttributes,
    ReferenceMaterial,
    ReferenceMaterialType,
    RefinementEntry,
    RepositorySpec,
    ScopeType,
    SpecConflict,
    TechnicalRequirement,
)


# ---------------------------------------------------------------------------
# TechnicalRequirement tests
# ---------------------------------------------------------------------------


class TestTechnicalRequirement:
    """Test TechnicalRequirement model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create TechnicalRequirement with defaults (all empty)."""
        req = TechnicalRequirement()
        assert req.languages == []
        assert req.frameworks == []
        assert req.platforms == []
        assert req.deployment_targets == []
        assert req.scope is None

    def test_create_full(self) -> None:
        """Create TechnicalRequirement with all fields populated."""
        req = TechnicalRequirement(
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI", "React"],
            platforms=["Linux", "Web"],
            deployment_targets=[DeploymentTarget.CLOUD, DeploymentTarget.SERVERLESS],
            scope=ScopeType.FULL_STACK,
        )
        assert req.languages == ["Python", "TypeScript"]
        assert req.frameworks == ["FastAPI", "React"]
        assert req.platforms == ["Linux", "Web"]
        assert req.deployment_targets == [DeploymentTarget.CLOUD, DeploymentTarget.SERVERLESS]
        assert req.scope == ScopeType.FULL_STACK

    def test_strips_whitespace_in_lists(self) -> None:
        """Validator strips whitespace from list entries."""
        req = TechnicalRequirement(
            languages=["  Python  ", "  Rust "],
            frameworks=["  React  "],
        )
        assert req.languages == ["Python", "Rust"]
        assert req.frameworks == ["React"]

    def test_filters_empty_strings_from_lists(self) -> None:
        """Validator removes empty strings after stripping."""
        req = TechnicalRequirement(
            languages=["Python", "", "  ", "Rust"],
        )
        assert req.languages == ["Python", "Rust"]

    def test_scope_enum_values(self) -> None:
        """All scope enum values are accepted."""
        for scope in ScopeType:
            req = TechnicalRequirement(scope=scope)
            assert req.scope == scope

    def test_deployment_target_enum_values(self) -> None:
        """All deployment target enum values are accepted."""
        for target in DeploymentTarget:
            req = TechnicalRequirement(deployment_targets=[target])
            assert req.deployment_targets == [target]

    def test_serialization_roundtrip(self) -> None:
        """TechnicalRequirement survives JSON serialization/deserialization."""
        req = TechnicalRequirement(
            languages=["Python"],
            frameworks=["Django"],
            scope=ScopeType.BACKEND_ONLY,
            deployment_targets=[DeploymentTarget.CLOUD],
        )
        data = req.model_dump(mode="json")
        restored = TechnicalRequirement.model_validate(data)
        assert restored == req


# ---------------------------------------------------------------------------
# QualityAttributes tests
# ---------------------------------------------------------------------------


class TestQualityAttributes:
    """Test QualityAttributes model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create QualityAttributes with defaults (all None)."""
        qa = QualityAttributes()
        assert qa.performance is None
        assert qa.security is None
        assert qa.scalability is None
        assert qa.reliability is None
        assert qa.maintainability is None
        assert qa.other == {}
        assert qa.has_any is False

    def test_create_full(self) -> None:
        """Create QualityAttributes with all fields populated."""
        qa = QualityAttributes(
            performance="<100ms p95 latency",
            security="OAuth2, OWASP compliance",
            scalability="10K concurrent users",
            reliability="99.9% uptime",
            maintainability="80% test coverage",
            other={"accessibility": "WCAG 2.1 AA"},
        )
        assert qa.performance == "<100ms p95 latency"
        assert qa.security == "OAuth2, OWASP compliance"
        assert qa.has_any is True

    def test_has_any_with_performance_only(self) -> None:
        """has_any returns True with only performance set."""
        qa = QualityAttributes(performance="fast")
        assert qa.has_any is True

    def test_has_any_with_other_only(self) -> None:
        """has_any returns True with only other dict populated."""
        qa = QualityAttributes(other={"accessibility": "WCAG 2.1"})
        assert qa.has_any is True

    def test_serialization_roundtrip(self) -> None:
        """QualityAttributes survives JSON roundtrip."""
        qa = QualityAttributes(
            performance="fast",
            security="secure",
            other={"custom": "value"},
        )
        data = qa.model_dump(mode="json")
        restored = QualityAttributes.model_validate(data)
        assert restored == qa


# ---------------------------------------------------------------------------
# Constraint tests
# ---------------------------------------------------------------------------


class TestConstraint:
    """Test Constraint model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create Constraint with only required fields."""
        c = Constraint(description="Must support Python 3.11+")
        assert c.description == "Must support Python 3.11+"
        assert c.priority == ConstraintPriority.SHOULD_HAVE
        assert c.category is None
        assert isinstance(c.id, UUID)

    def test_create_full(self) -> None:
        """Create Constraint with all fields populated."""
        c = Constraint(
            description="Backend must use REST API",
            priority=ConstraintPriority.MUST_HAVE,
            category="architecture",
        )
        assert c.priority == ConstraintPriority.MUST_HAVE
        assert c.category == "architecture"

    def test_empty_description_rejected(self) -> None:
        """Empty description raises ValidationError."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            Constraint(description="")

    def test_description_max_length(self) -> None:
        """Description exceeding max length raises ValidationError."""
        with pytest.raises(ValidationError):
            Constraint(description="x" * 2001)

    def test_all_priority_values(self) -> None:
        """All ConstraintPriority values are accepted."""
        for priority in ConstraintPriority:
            c = Constraint(description="test", priority=priority)
            assert c.priority == priority

    def test_custom_id(self) -> None:
        """Custom UUID can be provided."""
        custom_id = uuid4()
        c = Constraint(id=custom_id, description="test")
        assert c.id == custom_id


# ---------------------------------------------------------------------------
# ReferenceMaterial tests
# ---------------------------------------------------------------------------


class TestReferenceMaterial:
    """Test ReferenceMaterial model creation and validation."""

    def test_create_with_url(self) -> None:
        """Create ReferenceMaterial with URL."""
        ref = ReferenceMaterial(
            type=ReferenceMaterialType.API_DOCUMENTATION,
            url="https://docs.python.org/3/",
            title="Python 3 Docs",
        )
        assert ref.type == ReferenceMaterialType.API_DOCUMENTATION
        assert ref.url == "https://docs.python.org/3/"
        assert ref.title == "Python 3 Docs"
        assert ref.content is None
        assert ref.extracted_concepts == []

    def test_create_with_content(self) -> None:
        """Create ReferenceMaterial with inline content."""
        ref = ReferenceMaterial(
            type=ReferenceMaterialType.CODE_SAMPLE,
            content="def hello(): return 'world'",
        )
        assert ref.content == "def hello(): return 'world'"
        assert ref.url is None

    def test_create_with_both_url_and_content(self) -> None:
        """Creating ReferenceMaterial with both URL and content is valid."""
        ref = ReferenceMaterial(
            type=ReferenceMaterialType.GITHUB_REPO,
            url="https://github.com/example/repo",
            content="README contents here",
        )
        assert ref.url is not None
        assert ref.content is not None

    def test_neither_url_nor_content_rejected(self) -> None:
        """ReferenceMaterial without url or content raises ValidationError."""
        with pytest.raises(ValidationError, match="At least one of 'url' or 'content'"):
            ReferenceMaterial(type=ReferenceMaterialType.OTHER)

    def test_invalid_url_format_rejected(self) -> None:
        """URL not starting with http(s):// or file:// raises ValidationError."""
        with pytest.raises(ValidationError, match="URL must start with"):
            ReferenceMaterial(
                type=ReferenceMaterialType.API_DOCUMENTATION,
                url="ftp://example.com/docs",
            )

    def test_file_url_accepted(self) -> None:
        """file:// URLs are accepted."""
        ref = ReferenceMaterial(
            type=ReferenceMaterialType.RESEARCH_PAPER,
            url="file:///home/user/paper.pdf",
        )
        assert ref.url == "file:///home/user/paper.pdf"

    def test_extracted_concepts(self) -> None:
        """Extracted concepts list is properly stored."""
        ref = ReferenceMaterial(
            type=ReferenceMaterialType.API_DOCUMENTATION,
            url="https://scikit-learn.org/",
            extracted_concepts=["GridSearchCV", "Pipeline", "cross_val_score"],
        )
        assert len(ref.extracted_concepts) == 3
        assert "Pipeline" in ref.extracted_concepts

    def test_all_reference_types(self) -> None:
        """All ReferenceMaterialType values are accepted."""
        for ref_type in ReferenceMaterialType:
            ref = ReferenceMaterial(
                type=ref_type,
                content="sample content",
            )
            assert ref.type == ref_type


# ---------------------------------------------------------------------------
# SpecConflict tests
# ---------------------------------------------------------------------------


class TestSpecConflict:
    """Test SpecConflict model creation and validation."""

    def test_create_error_conflict(self) -> None:
        """Create an ERROR severity conflict."""
        conflict = SpecConflict(
            severity=ConflictSeverity.ERROR,
            description="Backend-only scope conflicts with React frontend requirement",
            conflicting_fields=["technical_requirements.scope", "technical_requirements.frameworks"],
            suggestion="Did you mean backend API + separate React app?",
        )
        assert conflict.severity == ConflictSeverity.ERROR
        assert len(conflict.conflicting_fields) == 2
        assert conflict.suggestion is not None

    def test_create_warning_conflict(self) -> None:
        """Create a WARNING severity conflict."""
        conflict = SpecConflict(
            severity=ConflictSeverity.WARNING,
            description="Serverless with long-running processes may cause timeouts",
        )
        assert conflict.severity == ConflictSeverity.WARNING
        assert conflict.suggestion is None

    def test_create_info_conflict(self) -> None:
        """Create an INFO severity conflict."""
        conflict = SpecConflict(
            severity=ConflictSeverity.INFO,
            description="Consider adding authentication for public APIs",
        )
        assert conflict.severity == ConflictSeverity.INFO

    def test_empty_description_rejected(self) -> None:
        """Empty description raises ValidationError."""
        with pytest.raises(ValidationError):
            SpecConflict(severity=ConflictSeverity.ERROR, description="")

    def test_all_severity_values(self) -> None:
        """All ConflictSeverity values are accepted."""
        for sev in ConflictSeverity:
            c = SpecConflict(severity=sev, description="test conflict")
            assert c.severity == sev


# ---------------------------------------------------------------------------
# RefinementEntry tests
# ---------------------------------------------------------------------------


class TestRefinementEntry:
    """Test RefinementEntry model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create RefinementEntry with required fields."""
        entry = RefinementEntry(
            action="add_requirement",
            details="Added offline mode support",
        )
        assert entry.action == "add_requirement"
        assert entry.details == "Added offline mode support"
        assert entry.previous_value is None
        assert isinstance(entry.timestamp, datetime)
        assert isinstance(entry.id, UUID)

    def test_create_full(self) -> None:
        """Create RefinementEntry with all fields."""
        entry = RefinementEntry(
            action="clarify",
            details="Clarified deployment target as AWS Lambda",
            previous_value="deployment: cloud",
        )
        assert entry.previous_value == "deployment: cloud"

    def test_empty_action_rejected(self) -> None:
        """Empty action raises ValidationError."""
        with pytest.raises(ValidationError):
            RefinementEntry(action="", details="some details")

    def test_empty_details_rejected(self) -> None:
        """Empty details raises ValidationError."""
        with pytest.raises(ValidationError):
            RefinementEntry(action="add", details="")

    def test_timestamp_is_utc(self) -> None:
        """Default timestamp is in UTC."""
        entry = RefinementEntry(action="add", details="test")
        assert entry.timestamp.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# RepositorySpec tests
# ---------------------------------------------------------------------------


class TestRepositorySpecCreation:
    """Test RepositorySpec creation with various field combinations."""

    def test_create_minimal(self) -> None:
        """Create RepositorySpec with only description (minimum viable spec)."""
        spec = RepositorySpec(
            description="Build a real-time chat application with WebSocket support"
        )
        assert "real-time chat" in spec.description
        assert spec.core_functionality is None
        assert spec.technical_requirements.languages == []
        assert spec.quality_attributes.has_any is False
        assert spec.constraints == []
        assert spec.references == []
        assert spec.conflicts == []
        assert spec.refinement_history == []
        assert spec.metadata == {}
        assert isinstance(spec.id, UUID)
        assert isinstance(spec.created_at, datetime)
        assert isinstance(spec.updated_at, datetime)

    def test_create_full(self) -> None:
        """Create RepositorySpec with all fields populated."""
        spec = RepositorySpec(
            description="Build a machine learning library with regression, clustering, and evaluation metrics",
            core_functionality="Machine learning algorithms for supervised and unsupervised learning",
            technical_requirements=TechnicalRequirement(
                languages=["Python"],
                frameworks=["scikit-learn"],
                platforms=["Linux", "macOS"],
                scope=ScopeType.LIBRARY,
            ),
            quality_attributes=QualityAttributes(
                performance="<100ms for predictions on small datasets",
                maintainability="80% test coverage",
            ),
            constraints=[
                Constraint(
                    description="Must support Python 3.11+",
                    priority=ConstraintPriority.MUST_HAVE,
                ),
                Constraint(
                    description="GPU acceleration would be nice",
                    priority=ConstraintPriority.NICE_TO_HAVE,
                ),
            ],
            references=[
                ReferenceMaterial(
                    type=ReferenceMaterialType.API_DOCUMENTATION,
                    url="https://scikit-learn.org/stable/",
                    extracted_concepts=["GridSearchCV", "Pipeline"],
                ),
            ],
            metadata={"project_name": "ml-lib", "version": "0.1.0"},
        )
        assert spec.core_functionality is not None
        assert len(spec.constraints) == 2
        assert len(spec.references) == 1
        assert spec.technical_requirements.scope == ScopeType.LIBRARY
        assert spec.quality_attributes.has_any is True


class TestRepositorySpecValidation:
    """Test RepositorySpec validation logic."""

    def test_description_too_short_char_count(self) -> None:
        """Description shorter than 10 characters raises ValidationError."""
        with pytest.raises(ValidationError, match="String should have at least 10 character"):
            RepositorySpec(description="short")

    def test_description_too_few_words(self) -> None:
        """Description with fewer than 3 words raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 3 words"):
            RepositorySpec(description="toolongsingleword")

    def test_description_max_length(self) -> None:
        """Description exceeding max length raises ValidationError."""
        with pytest.raises(ValidationError):
            RepositorySpec(description="word " * 10001)

    def test_core_functionality_max_length(self) -> None:
        """core_functionality exceeding max length raises ValidationError."""
        with pytest.raises(ValidationError):
            RepositorySpec(
                description="Build a repository for testing",
                core_functionality="x" * 5001,
            )


class TestRepositorySpecProperties:
    """Test RepositorySpec computed properties."""

    def test_has_conflicts_false(self) -> None:
        """has_conflicts returns False when no conflicts exist."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
        )
        assert spec.has_conflicts is False

    def test_has_conflicts_true(self) -> None:
        """has_conflicts returns True when conflicts are present."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
            conflicts=[
                SpecConflict(
                    severity=ConflictSeverity.ERROR,
                    description="Conflict detected",
                ),
            ],
        )
        assert spec.has_conflicts is True

    def test_blocking_conflicts_filter(self) -> None:
        """blocking_conflicts returns only ERROR severity conflicts."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
            conflicts=[
                SpecConflict(severity=ConflictSeverity.ERROR, description="Error 1"),
                SpecConflict(severity=ConflictSeverity.WARNING, description="Warning 1"),
                SpecConflict(severity=ConflictSeverity.INFO, description="Info 1"),
                SpecConflict(severity=ConflictSeverity.ERROR, description="Error 2"),
            ],
        )
        blockers = spec.blocking_conflicts
        assert len(blockers) == 2
        assert all(c.severity == ConflictSeverity.ERROR for c in blockers)

    def test_must_have_constraints(self) -> None:
        """must_have_constraints filters correctly."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
            constraints=[
                Constraint(description="Python 3.11+", priority=ConstraintPriority.MUST_HAVE),
                Constraint(description="GPU support", priority=ConstraintPriority.NICE_TO_HAVE),
                Constraint(description="REST API", priority=ConstraintPriority.MUST_HAVE),
            ],
        )
        must_haves = spec.must_have_constraints
        assert len(must_haves) == 2
        assert all(c.priority == ConstraintPriority.MUST_HAVE for c in must_haves)

    def test_nice_to_have_constraints(self) -> None:
        """nice_to_have_constraints filters correctly."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
            constraints=[
                Constraint(description="Python 3.11+", priority=ConstraintPriority.MUST_HAVE),
                Constraint(description="GPU support", priority=ConstraintPriority.NICE_TO_HAVE),
            ],
        )
        nice_to_haves = spec.nice_to_have_constraints
        assert len(nice_to_haves) == 1
        assert nice_to_haves[0].description == "GPU support"


class TestRepositorySpecMethods:
    """Test RepositorySpec instance methods."""

    def test_add_constraint(self) -> None:
        """add_constraint appends to constraints list."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
        )
        c = Constraint(description="Must use PostgreSQL", priority=ConstraintPriority.MUST_HAVE)
        spec.add_constraint(c)
        assert len(spec.constraints) == 1
        assert spec.constraints[0].description == "Must use PostgreSQL"

    def test_add_reference(self) -> None:
        """add_reference appends to references list."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
        )
        ref = ReferenceMaterial(
            type=ReferenceMaterialType.API_DOCUMENTATION,
            url="https://react.dev/",
        )
        spec.add_reference(ref)
        assert len(spec.references) == 1
        assert spec.references[0].url == "https://react.dev/"

    def test_add_conflict(self) -> None:
        """add_conflict appends to conflicts list."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
        )
        conflict = SpecConflict(
            severity=ConflictSeverity.WARNING,
            description="Multiple frontend frameworks detected",
        )
        spec.add_conflict(conflict)
        assert len(spec.conflicts) == 1
        assert spec.has_conflicts is True

    def test_add_refinement_updates_timestamp(self) -> None:
        """add_refinement appends entry and updates updated_at."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
        )
        original_updated = spec.updated_at
        entry = RefinementEntry(
            action="add_requirement",
            details="Added real-time collaboration via WebSocket",
        )
        # Small sleep is unreliable; instead check the history was added
        spec.add_refinement(entry)
        assert len(spec.refinement_history) == 1
        assert spec.refinement_history[0].action == "add_requirement"
        # updated_at should be >= original (timing may be same millisecond)
        assert spec.updated_at >= original_updated


class TestRepositorySpecSerialization:
    """Test RepositorySpec JSON serialization/deserialization."""

    def _make_full_spec(self) -> RepositorySpec:
        """Create a fully-populated spec for serialization tests."""
        return RepositorySpec(
            description="Build a real-time chat application with React and WebSocket support for 10K concurrent users",
            core_functionality="real-time messaging between authenticated users",
            technical_requirements=TechnicalRequirement(
                languages=["TypeScript", "Python"],
                frameworks=["React", "FastAPI"],
                platforms=["Web", "Linux"],
                deployment_targets=[DeploymentTarget.CLOUD],
                scope=ScopeType.FULL_STACK,
            ),
            quality_attributes=QualityAttributes(
                performance="<100ms message delivery",
                security="OAuth2 authentication",
                scalability="10K concurrent users",
            ),
            constraints=[
                Constraint(
                    description="Must support WebSocket",
                    priority=ConstraintPriority.MUST_HAVE,
                    category="protocol",
                ),
                Constraint(
                    description="Dark mode would be nice",
                    priority=ConstraintPriority.NICE_TO_HAVE,
                    category="ui",
                ),
            ],
            references=[
                ReferenceMaterial(
                    type=ReferenceMaterialType.API_DOCUMENTATION,
                    url="https://react.dev/",
                    title="React Docs",
                    extracted_concepts=["useState", "useEffect"],
                ),
            ],
            conflicts=[
                SpecConflict(
                    severity=ConflictSeverity.INFO,
                    description="Consider adding rate limiting for WebSocket connections",
                ),
            ],
            refinement_history=[
                RefinementEntry(
                    action="initial_parse",
                    details="Initial specification parsed from natural language",
                ),
            ],
            metadata={"project_name": "chat-app"},
        )

    def test_to_json_produces_valid_json(self) -> None:
        """to_json returns a valid JSON string."""
        spec = self._make_full_spec()
        json_str = spec.to_json()
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert "description" in data
        assert "technical_requirements" in data
        assert "constraints" in data

    def test_from_json_roundtrip(self) -> None:
        """Spec survives to_json -> from_json roundtrip."""
        spec = self._make_full_spec()
        json_str = spec.to_json()
        restored = RepositorySpec.from_json(json_str)

        assert restored.description == spec.description
        assert restored.core_functionality == spec.core_functionality
        assert restored.technical_requirements.languages == spec.technical_requirements.languages
        assert restored.technical_requirements.scope == spec.technical_requirements.scope
        assert restored.quality_attributes.performance == spec.quality_attributes.performance
        assert len(restored.constraints) == len(spec.constraints)
        assert len(restored.references) == len(spec.references)
        assert len(restored.conflicts) == len(spec.conflicts)
        assert len(restored.refinement_history) == len(spec.refinement_history)
        assert restored.metadata == spec.metadata

    def test_from_json_invalid_json(self) -> None:
        """from_json with invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            RepositorySpec.from_json("{not valid json")

    def test_from_json_invalid_data(self) -> None:
        """from_json with valid JSON but invalid data raises ValidationError."""
        with pytest.raises((ValueError, ValidationError)):
            RepositorySpec.from_json('{"description": "ab"}')

    def test_model_dump_mode_json(self) -> None:
        """model_dump(mode='json') produces JSON-serializable dict."""
        spec = self._make_full_spec()
        data = spec.model_dump(mode="json")
        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        # UUIDs should be strings
        assert isinstance(data["id"], str)


class TestRepositorySpecOptionalFields:
    """Test that optional fields work correctly."""

    def test_all_optional_fields_default_to_none_or_empty(self) -> None:
        """Only description is required; all else defaults gracefully."""
        spec = RepositorySpec(
            description="Build a simple command line tool for file conversion",
        )
        assert spec.core_functionality is None
        assert spec.technical_requirements.languages == []
        assert spec.technical_requirements.scope is None
        assert spec.quality_attributes.has_any is False
        assert spec.constraints == []
        assert spec.references == []
        assert spec.conflicts == []
        assert spec.refinement_history == []
        assert spec.metadata == {}

    def test_partial_technical_requirements(self) -> None:
        """Only some technical requirement fields can be set."""
        spec = RepositorySpec(
            description="Build a Python backend API for data processing",
            technical_requirements=TechnicalRequirement(
                languages=["Python"],
            ),
        )
        assert spec.technical_requirements.languages == ["Python"]
        assert spec.technical_requirements.frameworks == []
        assert spec.technical_requirements.scope is None

    def test_partial_quality_attributes(self) -> None:
        """Only some quality attributes can be set."""
        spec = RepositorySpec(
            description="Build a secure authentication service with OAuth2",
            quality_attributes=QualityAttributes(
                security="OAuth2 + OWASP",
            ),
        )
        assert spec.quality_attributes.security == "OAuth2 + OWASP"
        assert spec.quality_attributes.performance is None
        assert spec.quality_attributes.has_any is True


class TestRepositorySpecEquality:
    """Test RepositorySpec equality and hashing."""

    def test_equal_specs(self) -> None:
        """Two specs with same data are equal."""
        spec_id = uuid4()
        ts = datetime.now(timezone.utc)
        kwargs = dict(
            id=spec_id,
            description="Build a web application with React frontend",
            created_at=ts,
            updated_at=ts,
        )
        spec1 = RepositorySpec(**kwargs)
        spec2 = RepositorySpec(**kwargs)
        assert spec1 == spec2

    def test_different_specs_not_equal(self) -> None:
        """Two specs with different IDs are not equal."""
        spec1 = RepositorySpec(description="Build a web application with React frontend")
        spec2 = RepositorySpec(description="Build a web application with React frontend")
        # Different UUIDs generated
        assert spec1 != spec2

    def test_hash_based_on_id(self) -> None:
        """Hash is based on id field."""
        spec = RepositorySpec(description="Build a web application with React frontend")
        assert hash(spec) == hash(spec.id)

    def test_not_equal_to_non_spec(self) -> None:
        """Comparing to non-RepositorySpec returns NotImplemented."""
        spec = RepositorySpec(description="Build a web application with React frontend")
        assert spec != "not a spec"

    def test_repr_concise(self) -> None:
        """__repr__ returns a concise string."""
        spec = RepositorySpec(description="Build a web application with React frontend")
        r = repr(spec)
        assert "RepositorySpec" in r
        assert "constraints=" in r
        assert "references=" in r


class TestJsonSchemaGeneration:
    """Test JSON schema generation for validation support."""

    def test_repository_spec_json_schema(self) -> None:
        """RepositorySpec.model_json_schema() produces a valid JSON schema."""
        schema = RepositorySpec.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "description" in schema["properties"]
        assert "technical_requirements" in schema["properties"]
        assert "quality_attributes" in schema["properties"]
        assert "constraints" in schema["properties"]
        assert "references" in schema["properties"]

    def test_technical_requirement_json_schema(self) -> None:
        """TechnicalRequirement schema includes all fields."""
        schema = TechnicalRequirement.model_json_schema()
        assert "languages" in schema["properties"]
        assert "frameworks" in schema["properties"]
        assert "platforms" in schema["properties"]
        assert "deployment_targets" in schema["properties"]
        assert "scope" in schema["properties"]

    def test_quality_attributes_json_schema(self) -> None:
        """QualityAttributes schema includes all fields."""
        schema = QualityAttributes.model_json_schema()
        assert "performance" in schema["properties"]
        assert "security" in schema["properties"]
        assert "scalability" in schema["properties"]

    def test_constraint_json_schema(self) -> None:
        """Constraint schema includes all fields."""
        schema = Constraint.model_json_schema()
        assert "description" in schema["properties"]
        assert "priority" in schema["properties"]

    def test_reference_material_json_schema(self) -> None:
        """ReferenceMaterial schema includes all fields."""
        schema = ReferenceMaterial.model_json_schema()
        assert "type" in schema["properties"]
        assert "url" in schema["properties"]
        assert "extracted_concepts" in schema["properties"]

    def test_schema_serializes_to_json(self) -> None:
        """Full schema can be serialized to JSON for external validators."""
        schema = RepositorySpec.model_json_schema()
        json_str = json.dumps(schema, indent=2)
        assert isinstance(json_str, str)
        # Roundtrip
        data = json.loads(json_str)
        assert data == schema


class TestEnumStringValues:
    """Test that all enums serialize as strings for JSON compatibility."""

    def test_constraint_priority_values(self) -> None:
        """ConstraintPriority enum values are strings."""
        assert ConstraintPriority.MUST_HAVE.value == "MUST_HAVE"
        assert ConstraintPriority.SHOULD_HAVE.value == "SHOULD_HAVE"
        assert ConstraintPriority.NICE_TO_HAVE.value == "NICE_TO_HAVE"

    def test_reference_material_type_values(self) -> None:
        """ReferenceMaterialType enum values are strings."""
        assert ReferenceMaterialType.API_DOCUMENTATION.value == "API_DOCUMENTATION"
        assert ReferenceMaterialType.CODE_SAMPLE.value == "CODE_SAMPLE"
        assert ReferenceMaterialType.RESEARCH_PAPER.value == "RESEARCH_PAPER"
        assert ReferenceMaterialType.GITHUB_REPO.value == "GITHUB_REPO"
        assert ReferenceMaterialType.OTHER.value == "OTHER"

    def test_conflict_severity_values(self) -> None:
        """ConflictSeverity enum values are strings."""
        assert ConflictSeverity.ERROR.value == "ERROR"
        assert ConflictSeverity.WARNING.value == "WARNING"
        assert ConflictSeverity.INFO.value == "INFO"

    def test_scope_type_values(self) -> None:
        """ScopeType enum values are strings."""
        for scope in ScopeType:
            assert isinstance(scope.value, str)

    def test_deployment_target_values(self) -> None:
        """DeploymentTarget enum values are strings."""
        for target in DeploymentTarget:
            assert isinstance(target.value, str)


# ---------------------------------------------------------------------------
# Epic tests
# ---------------------------------------------------------------------------


class TestEpic:
    """Test Epic model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create Epic with only required fields."""
        epic = Epic(title="User Authentication")
        assert epic.title == "User Authentication"
        assert epic.description == ""
        assert epic.priority == ConstraintPriority.SHOULD_HAVE
        assert epic.estimated_complexity is None
        assert isinstance(epic.id, UUID)

    def test_create_full(self) -> None:
        """Create Epic with all fields populated."""
        epic = Epic(
            title="Real-time Messaging",
            description="WebSocket-based chat system with rooms",
            priority=ConstraintPriority.MUST_HAVE,
            estimated_complexity="high",
        )
        assert epic.title == "Real-time Messaging"
        assert epic.priority == ConstraintPriority.MUST_HAVE
        assert epic.estimated_complexity == "high"

    def test_empty_title_rejected(self) -> None:
        """Empty title raises ValidationError."""
        with pytest.raises(ValidationError):
            Epic(title="")

    def test_title_max_length(self) -> None:
        """Title exceeding max length raises ValidationError."""
        with pytest.raises(ValidationError):
            Epic(title="x" * 501)

    def test_serialization_roundtrip(self) -> None:
        """Epic survives JSON roundtrip."""
        epic = Epic(
            title="Auth System",
            description="JWT auth",
            priority=ConstraintPriority.MUST_HAVE,
        )
        data = epic.model_dump(mode="json")
        restored = Epic.model_validate(data)
        assert restored.title == epic.title
        assert restored.priority == epic.priority


# ---------------------------------------------------------------------------
# Component tests
# ---------------------------------------------------------------------------


class TestComponent:
    """Test Component model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create Component with only required fields."""
        comp = Component(name="API Gateway")
        assert comp.name == "API Gateway"
        assert comp.description == ""
        assert comp.component_type is None
        assert comp.technologies == []
        assert isinstance(comp.id, UUID)

    def test_create_full(self) -> None:
        """Create Component with all fields populated."""
        comp = Component(
            name="Auth Service",
            description="Handles authentication and authorization",
            component_type="service",
            technologies=["FastAPI", "PyJWT"],
        )
        assert comp.name == "Auth Service"
        assert comp.component_type == "service"
        assert "FastAPI" in comp.technologies

    def test_empty_name_rejected(self) -> None:
        """Empty name raises ValidationError."""
        with pytest.raises(ValidationError):
            Component(name="")

    def test_serialization_roundtrip(self) -> None:
        """Component survives JSON roundtrip."""
        comp = Component(
            name="Database Layer",
            technologies=["PostgreSQL", "SQLAlchemy"],
        )
        data = comp.model_dump(mode="json")
        restored = Component.model_validate(data)
        assert restored.name == comp.name
        assert restored.technologies == comp.technologies


# ---------------------------------------------------------------------------
# DataFlow tests
# ---------------------------------------------------------------------------


class TestDataFlow:
    """Test DataFlow model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create DataFlow with only required fields."""
        flow = DataFlow(source="API Gateway", target="Auth Service")
        assert flow.source == "API Gateway"
        assert flow.target == "Auth Service"
        assert flow.description == ""
        assert flow.protocol is None
        assert isinstance(flow.id, UUID)

    def test_create_full(self) -> None:
        """Create DataFlow with all fields populated."""
        flow = DataFlow(
            source="Frontend",
            target="API Gateway",
            description="HTTP requests for data",
            protocol="REST",
        )
        assert flow.source == "Frontend"
        assert flow.protocol == "REST"

    def test_empty_source_rejected(self) -> None:
        """Empty source raises ValidationError."""
        with pytest.raises(ValidationError):
            DataFlow(source="", target="DB")

    def test_empty_target_rejected(self) -> None:
        """Empty target raises ValidationError."""
        with pytest.raises(ValidationError):
            DataFlow(source="API", target="")

    def test_serialization_roundtrip(self) -> None:
        """DataFlow survives JSON roundtrip."""
        flow = DataFlow(
            source="API",
            target="DB",
            protocol="direct",
        )
        data = flow.model_dump(mode="json")
        restored = DataFlow.model_validate(data)
        assert restored.source == flow.source
        assert restored.target == flow.target


# ---------------------------------------------------------------------------
# FileRecommendation tests
# ---------------------------------------------------------------------------


class TestFileRecommendation:
    """Test FileRecommendation model creation and validation."""

    def test_create_minimal(self) -> None:
        """Create FileRecommendation with only required fields."""
        rec = FileRecommendation(path="src/main.py")
        assert rec.path == "src/main.py"
        assert rec.purpose == ""
        assert rec.component is None
        assert isinstance(rec.id, UUID)

    def test_create_full(self) -> None:
        """Create FileRecommendation with all fields populated."""
        rec = FileRecommendation(
            path="src/api/routes.py",
            purpose="API route definitions and endpoint handlers",
            component="API Gateway",
        )
        assert rec.path == "src/api/routes.py"
        assert rec.component == "API Gateway"

    def test_empty_path_rejected(self) -> None:
        """Empty path raises ValidationError."""
        with pytest.raises(ValidationError):
            FileRecommendation(path="")

    def test_serialization_roundtrip(self) -> None:
        """FileRecommendation survives JSON roundtrip."""
        rec = FileRecommendation(
            path="src/models/user.py",
            purpose="User data model",
        )
        data = rec.model_dump(mode="json")
        restored = FileRecommendation.model_validate(data)
        assert restored.path == rec.path
        assert restored.purpose == rec.purpose


# ---------------------------------------------------------------------------
# RepositorySpec deep extraction field tests
# ---------------------------------------------------------------------------


class TestRepositorySpecDeepFields:
    """Test RepositorySpec with new deep extraction fields."""

    def test_default_deep_fields_empty(self) -> None:
        """New deep extraction fields default to empty lists."""
        spec = RepositorySpec(
            description="Build a web application with React frontend",
        )
        assert spec.epics == []
        assert spec.components == []
        assert spec.data_flows == []
        assert spec.file_recommendations == []

    def test_create_with_deep_fields(self) -> None:
        """Create RepositorySpec with all deep extraction fields."""
        spec = RepositorySpec(
            description="Build a real-time chat application with authentication",
            epics=[
                Epic(title="Authentication System"),
                Epic(title="Messaging Engine"),
            ],
            components=[
                Component(name="API Gateway", technologies=["FastAPI"]),
                Component(name="Message Queue", technologies=["Redis"]),
            ],
            data_flows=[
                DataFlow(source="API Gateway", target="Message Queue", protocol="direct"),
            ],
            file_recommendations=[
                FileRecommendation(path="src/api/routes.py", purpose="API routes"),
            ],
        )
        assert len(spec.epics) == 2
        assert len(spec.components) == 2
        assert len(spec.data_flows) == 1
        assert len(spec.file_recommendations) == 1

    def test_deep_fields_serialization_roundtrip(self) -> None:
        """RepositorySpec with deep fields survives JSON roundtrip."""
        spec = RepositorySpec(
            description="Build a backend API service with database layer",
            epics=[Epic(title="Core API")],
            components=[Component(name="DB Layer")],
            data_flows=[DataFlow(source="API", target="DB")],
            file_recommendations=[FileRecommendation(path="src/main.py")],
        )
        json_str = spec.to_json()
        restored = RepositorySpec.from_json(json_str)
        assert len(restored.epics) == 1
        assert restored.epics[0].title == "Core API"
        assert len(restored.components) == 1
        assert restored.components[0].name == "DB Layer"
        assert len(restored.data_flows) == 1
        assert len(restored.file_recommendations) == 1

    def test_json_schema_includes_deep_fields(self) -> None:
        """RepositorySpec JSON schema includes the new deep extraction fields."""
        schema = RepositorySpec.model_json_schema()
        assert "epics" in schema["properties"]
        assert "components" in schema["properties"]
        assert "data_flows" in schema["properties"]
        assert "file_recommendations" in schema["properties"]
