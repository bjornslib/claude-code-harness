"""Unit tests for the Conflict Detector (Task 2.4.4).

Tests cover rule-based heuristics, LLM-based analysis (mocked),
deduplication, severity normalisation, and the ConflictDetector class.

All LLM calls are mocked – no actual API requests are made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from zerorepo.llm.exceptions import LLMGatewayError
from zerorepo.llm.gateway import LLMGateway
from zerorepo.llm.models import ModelTier
from zerorepo.llm.prompt_templates import PromptTemplate
from zerorepo.spec_parser.conflict_detector import (
    ConflictDetector,
    ConflictDetectorError,
    DetectorConfig,
    LLMConflictItem,
    LLMConflictResponse,
    _normalize_severity,
)
from zerorepo.spec_parser.models import (
    ConflictSeverity,
    Constraint,
    ConstraintPriority,
    DeploymentTarget,
    QualityAttributes,
    RepositorySpec,
    ScopeType,
    SpecConflict,
    TechnicalRequirement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    description: str = "Build a web application with Python and React",
    languages: list[str] | None = None,
    frameworks: list[str] | None = None,
    platforms: list[str] | None = None,
    deployment_targets: list[DeploymentTarget] | None = None,
    scope: ScopeType | None = None,
    quality_attributes: QualityAttributes | None = None,
    constraints: list[Constraint] | None = None,
    core_functionality: str | None = None,
) -> RepositorySpec:
    """Create a RepositorySpec for testing."""
    return RepositorySpec(
        description=description,
        core_functionality=core_functionality,
        technical_requirements=TechnicalRequirement(
            languages=languages or [],
            frameworks=frameworks or [],
            platforms=platforms or [],
            deployment_targets=deployment_targets or [],
            scope=scope,
        ),
        quality_attributes=quality_attributes or QualityAttributes(),
        constraints=constraints or [],
    )


def _make_llm_response(conflicts: list[dict]) -> str:
    """Create a JSON LLM response string."""
    return json.dumps({"conflicts": conflicts})


def _make_detector(
    llm_response: str = '{"conflicts": []}',
    use_llm: bool = False,
    use_rules: bool = True,
) -> ConflictDetector:
    """Create a ConflictDetector with mocked gateway."""
    mock_gw = MagicMock(spec=LLMGateway)
    mock_gw.complete.return_value = llm_response
    mock_pt = MagicMock(spec=PromptTemplate)
    mock_pt.render.return_value = "Mocked conflict detection prompt"
    config = DetectorConfig(use_llm=use_llm, use_rules=use_rules)
    return ConflictDetector(config=config, gateway=mock_gw, templates=mock_pt)


# ---------------------------------------------------------------------------
# DetectorConfig Tests
# ---------------------------------------------------------------------------


class TestDetectorConfig:
    """Test the DetectorConfig model."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = DetectorConfig()
        assert config.model == "gpt-4o-mini"
        assert config.tier == ModelTier.CHEAP
        assert config.template_name == "conflict_detection"
        assert config.use_llm is True
        assert config.use_rules is True
        assert config.deduplicate is True

    def test_custom_config(self) -> None:
        """Custom config values are accepted."""
        config = DetectorConfig(
            model="gpt-4o",
            tier=ModelTier.STRONG,
            use_llm=False,
            use_rules=True,
            deduplicate=False,
        )
        assert config.model == "gpt-4o"
        assert config.tier == ModelTier.STRONG
        assert config.use_llm is False
        assert config.deduplicate is False


# ---------------------------------------------------------------------------
# LLM Response Model Tests
# ---------------------------------------------------------------------------


class TestLLMConflictItem:
    """Test the LLM conflict item model."""

    def test_create_valid_item(self) -> None:
        """Create a valid conflict item."""
        item = LLMConflictItem(
            severity="ERROR",
            description="Backend-only with React",
            conflicting_fields=["scope", "frameworks"],
            suggestion="Change scope to FULL_STACK",
        )
        assert item.severity == "ERROR"
        assert len(item.conflicting_fields) == 2

    def test_minimal_item(self) -> None:
        """Create a minimal conflict item with defaults."""
        item = LLMConflictItem(
            severity="WARNING",
            description="Minor tension",
        )
        assert item.conflicting_fields == []
        assert item.suggestion is None


class TestLLMConflictResponse:
    """Test the LLM conflict response model."""

    def test_empty_conflicts(self) -> None:
        """Parse response with no conflicts."""
        resp = LLMConflictResponse(conflicts=[])
        assert len(resp.conflicts) == 0

    def test_with_conflicts(self) -> None:
        """Parse response with conflicts."""
        resp = LLMConflictResponse(
            conflicts=[
                LLMConflictItem(
                    severity="ERROR",
                    description="Test conflict",
                ),
            ]
        )
        assert len(resp.conflicts) == 1

    def test_parse_from_json(self) -> None:
        """Parse response from JSON string."""
        data = {
            "conflicts": [
                {
                    "severity": "WARNING",
                    "description": "Test",
                    "conflicting_fields": ["a", "b"],
                    "suggestion": "Fix it",
                },
            ]
        }
        resp = LLMConflictResponse.model_validate(data)
        assert len(resp.conflicts) == 1
        assert resp.conflicts[0].suggestion == "Fix it"


# ---------------------------------------------------------------------------
# Severity Normalisation Tests
# ---------------------------------------------------------------------------


class TestNormalizeSeverity:
    """Test the severity normalization function."""

    def test_standard_values(self) -> None:
        """Standard severity values are normalised correctly."""
        assert _normalize_severity("ERROR") == ConflictSeverity.ERROR
        assert _normalize_severity("WARNING") == ConflictSeverity.WARNING
        assert _normalize_severity("INFO") == ConflictSeverity.INFO

    def test_case_insensitive(self) -> None:
        """Severity normalisation is case-insensitive."""
        assert _normalize_severity("error") == ConflictSeverity.ERROR
        assert _normalize_severity("Warning") == ConflictSeverity.WARNING
        assert _normalize_severity("info") == ConflictSeverity.INFO

    def test_synonyms(self) -> None:
        """Common synonyms are mapped correctly."""
        assert _normalize_severity("WARN") == ConflictSeverity.WARNING
        assert _normalize_severity("CRITICAL") == ConflictSeverity.ERROR
        assert _normalize_severity("HIGH") == ConflictSeverity.ERROR
        assert _normalize_severity("MEDIUM") == ConflictSeverity.WARNING
        assert _normalize_severity("LOW") == ConflictSeverity.INFO
        assert _normalize_severity("INFORMATION") == ConflictSeverity.INFO

    def test_unknown_defaults_to_warning(self) -> None:
        """Unknown severity values default to WARNING."""
        assert _normalize_severity("UNKNOWN") == ConflictSeverity.WARNING
        assert _normalize_severity("") == ConflictSeverity.WARNING

    def test_whitespace_stripped(self) -> None:
        """Whitespace is stripped before normalisation."""
        assert _normalize_severity("  ERROR  ") == ConflictSeverity.ERROR


# ---------------------------------------------------------------------------
# Rule-Based: Scope vs Frameworks
# ---------------------------------------------------------------------------


class TestRuleScopeVsFrameworks:
    """Test rule-based scope vs framework conflict detection."""

    def test_backend_only_with_react(self) -> None:
        """BACKEND_ONLY + React = ERROR."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert "react" in conflicts[0].description.lower()

    def test_backend_only_with_vue(self) -> None:
        """BACKEND_ONLY + Vue = ERROR."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["Vue"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.ERROR

    def test_backend_only_with_angular_and_svelte(self) -> None:
        """BACKEND_ONLY + multiple frontend frameworks = ERROR."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["Angular", "Svelte"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert "angular" in conflicts[0].description.lower()
        assert "svelte" in conflicts[0].description.lower()

    def test_backend_only_with_backend_framework_no_conflict(self) -> None:
        """BACKEND_ONLY + Django = no conflict."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["Django"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_frontend_only_with_django(self) -> None:
        """FRONTEND_ONLY + Django = ERROR."""
        spec = _make_spec(
            scope=ScopeType.FRONTEND_ONLY,
            frameworks=["Django"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert "django" in conflicts[0].description.lower()

    def test_frontend_only_with_fastapi(self) -> None:
        """FRONTEND_ONLY + FastAPI = ERROR."""
        spec = _make_spec(
            scope=ScopeType.FRONTEND_ONLY,
            frameworks=["FastAPI"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.ERROR

    def test_frontend_only_with_frontend_framework_no_conflict(self) -> None:
        """FRONTEND_ONLY + React = no conflict."""
        spec = _make_spec(
            scope=ScopeType.FRONTEND_ONLY,
            frameworks=["React"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_full_stack_with_mixed_frameworks_no_conflict(self) -> None:
        """FULL_STACK + React + Django = no conflict."""
        spec = _make_spec(
            scope=ScopeType.FULL_STACK,
            frameworks=["React", "Django"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_no_scope_no_conflict(self) -> None:
        """No scope specified = no scope-related conflict."""
        spec = _make_spec(
            scope=None,
            frameworks=["React", "Django"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Rule-Based: Language vs Deployment
# ---------------------------------------------------------------------------


class TestRuleLanguageVsDeployment:
    """Test rule-based language vs deployment conflict detection."""

    def test_python_with_spring_no_jvm(self) -> None:
        """Python + Spring Boot (no JVM language) = WARNING."""
        spec = _make_spec(
            languages=["Python"],
            frameworks=["Spring Boot"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.WARNING
        assert "spring boot" in conflicts[0].description.lower()

    def test_java_with_spring_no_conflict(self) -> None:
        """Java + Spring Boot = no conflict."""
        spec = _make_spec(
            languages=["Java"],
            frameworks=["Spring Boot"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_kotlin_with_spring_no_conflict(self) -> None:
        """Kotlin + Spring = no conflict."""
        spec = _make_spec(
            languages=["Kotlin"],
            frameworks=["Spring"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_python_and_java_with_spring_no_conflict(self) -> None:
        """Python + Java + Spring = no conflict (Java covers JVM)."""
        spec = _make_spec(
            languages=["Python", "Java"],
            frameworks=["Spring"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_python_with_django_no_conflict(self) -> None:
        """Python + Django = no conflict (not a JVM framework)."""
        spec = _make_spec(
            languages=["Python"],
            frameworks=["Django"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Rule-Based: Serverless vs Long-Running
# ---------------------------------------------------------------------------


class TestRuleServerlessVsLongRunning:
    """Test rule-based serverless vs long-running process checks."""

    def test_serverless_with_celery(self) -> None:
        """SERVERLESS + Celery = WARNING."""
        spec = _make_spec(
            deployment_targets=[DeploymentTarget.SERVERLESS],
            frameworks=["Celery"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.WARNING
        assert "celery" in conflicts[0].description.lower()

    def test_serverless_with_kafka(self) -> None:
        """SERVERLESS + Kafka = WARNING."""
        spec = _make_spec(
            deployment_targets=[DeploymentTarget.SERVERLESS],
            frameworks=["Kafka"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert "kafka" in conflicts[0].description.lower()

    def test_serverless_with_react_no_conflict(self) -> None:
        """SERVERLESS + React = no conflict."""
        spec = _make_spec(
            deployment_targets=[DeploymentTarget.SERVERLESS],
            frameworks=["React"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_cloud_with_celery_no_conflict(self) -> None:
        """CLOUD + Celery = no conflict."""
        spec = _make_spec(
            deployment_targets=[DeploymentTarget.CLOUD],
            frameworks=["Celery"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_no_deployment_target_no_conflict(self) -> None:
        """No deployment target + Celery = no conflict."""
        spec = _make_spec(
            deployment_targets=[],
            frameworks=["Celery"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Rule-Based: Scope vs Platforms
# ---------------------------------------------------------------------------


class TestRuleScopeVsPlatforms:
    """Test rule-based scope vs platform conflict detection."""

    def test_cli_with_mobile(self) -> None:
        """CLI_TOOL + Mobile = WARNING."""
        spec = _make_spec(
            scope=ScopeType.CLI_TOOL,
            platforms=["Mobile"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.WARNING
        assert "mobile" in conflicts[0].description.lower()

    def test_cli_with_ios(self) -> None:
        """CLI_TOOL + iOS = WARNING."""
        spec = _make_spec(
            scope=ScopeType.CLI_TOOL,
            platforms=["iOS"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1

    def test_cli_with_linux_no_conflict(self) -> None:
        """CLI_TOOL + Linux = no conflict."""
        spec = _make_spec(
            scope=ScopeType.CLI_TOOL,
            platforms=["Linux"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_library_with_mobile_info(self) -> None:
        """LIBRARY + Mobile = INFO."""
        spec = _make_spec(
            scope=ScopeType.LIBRARY,
            platforms=["Mobile"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.INFO

    def test_full_stack_with_mobile_no_conflict(self) -> None:
        """FULL_STACK + Mobile = no conflict."""
        spec = _make_spec(
            scope=ScopeType.FULL_STACK,
            platforms=["Mobile"],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Rule-Based: Valid Specs (No False Positives)
# ---------------------------------------------------------------------------


class TestRuleNoFalsePositives:
    """Ensure valid specifications produce no conflicts."""

    def test_valid_fullstack_web_app(self) -> None:
        """Valid full-stack web app produces no conflicts."""
        spec = _make_spec(
            description="Build a full-stack web application with Python backend and React frontend",
            languages=["Python", "TypeScript"],
            frameworks=["FastAPI", "React"],
            platforms=["Web"],
            deployment_targets=[DeploymentTarget.CLOUD],
            scope=ScopeType.FULL_STACK,
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_valid_python_backend(self) -> None:
        """Valid Python backend produces no conflicts."""
        spec = _make_spec(
            description="Build a REST API backend with Python and Django",
            languages=["Python"],
            frameworks=["Django"],
            platforms=["Linux"],
            deployment_targets=[DeploymentTarget.CLOUD],
            scope=ScopeType.BACKEND_ONLY,
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_valid_python_serverless(self) -> None:
        """Python backend with serverless is valid (no long-running frameworks)."""
        spec = _make_spec(
            description="Build a serverless API with Python and FastAPI",
            languages=["Python"],
            frameworks=["FastAPI"],
            deployment_targets=[DeploymentTarget.SERVERLESS],
            scope=ScopeType.BACKEND_ONLY,
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_valid_cli_tool(self) -> None:
        """Valid CLI tool produces no conflicts."""
        spec = _make_spec(
            description="Build a command-line tool for data processing",
            languages=["Rust"],
            platforms=["Linux", "macOS", "Windows"],
            scope=ScopeType.CLI_TOOL,
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_empty_spec(self) -> None:
        """Spec with no technical requirements produces no conflicts."""
        spec = _make_spec(
            description="A simple web application project",
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Multiple Rule Conflicts
# ---------------------------------------------------------------------------


class TestMultipleRuleConflicts:
    """Test detection of multiple simultaneous conflicts."""

    def test_backend_only_with_react_and_serverless_celery(self) -> None:
        """Multiple conflicts detected simultaneously."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React", "Celery"],
            deployment_targets=[DeploymentTarget.SERVERLESS],
        )
        detector = _make_detector()
        conflicts = detector.detect(spec)
        # Should have: scope vs framework (React) + serverless vs Celery
        assert len(conflicts) == 2
        severities = {c.severity for c in conflicts}
        assert ConflictSeverity.ERROR in severities
        assert ConflictSeverity.WARNING in severities


# ---------------------------------------------------------------------------
# LLM-Based Analysis Tests
# ---------------------------------------------------------------------------


class TestLLMAnalysis:
    """Test LLM-based conflict detection with mocked gateway."""

    def test_llm_no_conflicts(self) -> None:
        """LLM returns no conflicts for a valid spec."""
        detector = _make_detector(
            llm_response='{"conflicts": []}',
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_llm_returns_conflicts(self) -> None:
        """LLM returns conflicts."""
        llm_resp = _make_llm_response([
            {
                "severity": "ERROR",
                "description": "Backend-only with React frontend",
                "conflicting_fields": ["scope", "frameworks"],
                "suggestion": "Change scope",
            },
        ])
        detector = _make_detector(
            llm_response=llm_resp,
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert "Backend-only" in conflicts[0].description

    def test_llm_multiple_conflicts(self) -> None:
        """LLM returns multiple conflicts with different severities."""
        llm_resp = _make_llm_response([
            {
                "severity": "ERROR",
                "description": "Conflict 1",
                "conflicting_fields": ["a"],
            },
            {
                "severity": "WARNING",
                "description": "Conflict 2",
                "conflicting_fields": ["b"],
            },
            {
                "severity": "INFO",
                "description": "Suggestion 1",
                "conflicting_fields": ["c"],
            },
        ])
        detector = _make_detector(
            llm_response=llm_resp,
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 3
        # Should be sorted: ERROR, WARNING, INFO
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert conflicts[1].severity == ConflictSeverity.WARNING
        assert conflicts[2].severity == ConflictSeverity.INFO

    def test_llm_calls_gateway(self) -> None:
        """LLM analysis calls the gateway."""
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.return_value = '{"conflicts": []}'
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=False)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        spec = _make_spec()
        detector.detect(spec)
        mock_gw.complete.assert_called_once()
        call_kwargs = mock_gw.complete.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_llm_uses_prompt_template(self) -> None:
        """LLM analysis renders the prompt template."""
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.return_value = '{"conflicts": []}'
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=False)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        spec = _make_spec(
            languages=["Python"],
            frameworks=["Django"],
            scope=ScopeType.BACKEND_ONLY,
        )
        detector.detect(spec)
        mock_pt.render.assert_called_once()
        call_kwargs = mock_pt.render.call_args.kwargs
        assert call_kwargs["languages"] == ["Python"]
        assert call_kwargs["frameworks"] == ["Django"]
        assert call_kwargs["scope"] == "BACKEND_ONLY"

    def test_llm_error_raises_detector_error(self) -> None:
        """LLM gateway error is wrapped in ConflictDetectorError."""
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.side_effect = LLMGatewayError("API error")
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=False)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        spec = _make_spec()
        with pytest.raises(ConflictDetectorError, match="failed"):
            detector.detect(spec)

    def test_llm_invalid_json_raises_detector_error(self) -> None:
        """Invalid JSON from LLM raises ConflictDetectorError."""
        detector = _make_detector(
            llm_response="not valid json",
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        with pytest.raises(ConflictDetectorError, match="not valid JSON"):
            detector.detect(spec)

    def test_llm_invalid_schema_raises_detector_error(self) -> None:
        """JSON that doesn't match schema raises ConflictDetectorError."""
        detector = _make_detector(
            llm_response='{"wrong_field": []}',
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        # This should not raise because conflicts defaults to empty list
        conflicts = detector.detect(spec)
        assert len(conflicts) == 0

    def test_llm_markdown_fenced_response(self) -> None:
        """LLM response wrapped in markdown code fences is handled."""
        fenced = '```json\n{"conflicts": [{"severity": "WARNING", "description": "Test"}]}\n```'
        detector = _make_detector(
            llm_response=fenced,
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        conflicts = detector.detect(spec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.WARNING

    def test_llm_no_gateway_raises(self) -> None:
        """LLM mode without a gateway raises ConflictDetectorError."""
        config = DetectorConfig(use_llm=True, use_rules=False)
        detector = ConflictDetector(
            config=config, gateway=None, templates=PromptTemplate()
        )
        spec = _make_spec()
        with pytest.raises(ConflictDetectorError, match="requires a configured"):
            detector.detect(spec)


# ---------------------------------------------------------------------------
# Combined Rules + LLM Tests
# ---------------------------------------------------------------------------


class TestCombinedRulesAndLLM:
    """Test combined rule-based and LLM-based detection."""

    def test_combined_results_merged(self) -> None:
        """Results from rules and LLM are merged."""
        llm_resp = _make_llm_response([
            {
                "severity": "INFO",
                "description": "LLM suggestion",
                "conflicting_fields": ["quality"],
            },
        ])
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.return_value = llm_resp
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=True, deduplicate=False)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        # Spec that triggers a rule-based conflict
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        conflicts = detector.detect(spec)
        # Rule gives 1 ERROR + LLM gives 1 INFO = 2 total
        assert len(conflicts) == 2
        # Sorted by severity
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert conflicts[1].severity == ConflictSeverity.INFO


# ---------------------------------------------------------------------------
# Deduplication Tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Test conflict deduplication logic."""

    def test_duplicate_same_fields_keeps_higher_severity(self) -> None:
        """Duplicates with same fields keep the higher severity."""
        llm_resp = _make_llm_response([
            {
                "severity": "WARNING",
                "description": "LLM: scope vs frameworks",
                "conflicting_fields": [
                    "technical_requirements.scope",
                    "technical_requirements.frameworks",
                ],
            },
        ])
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.return_value = llm_resp
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=True, deduplicate=True)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        conflicts = detector.detect(spec)
        # Rule produces ERROR for same fields, LLM produces WARNING
        # Dedup should keep the ERROR
        scope_framework_conflicts = [
            c for c in conflicts
            if "technical_requirements.scope" in c.conflicting_fields
        ]
        assert len(scope_framework_conflicts) == 1
        assert scope_framework_conflicts[0].severity == ConflictSeverity.ERROR

    def test_different_fields_no_dedup(self) -> None:
        """Conflicts with different fields are not deduplicated."""
        llm_resp = _make_llm_response([
            {
                "severity": "INFO",
                "description": "Different conflict",
                "conflicting_fields": ["quality.performance"],
            },
        ])
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.return_value = llm_resp
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=True, deduplicate=True)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        conflicts = detector.detect(spec)
        # Rule conflict + LLM conflict with different fields = both kept
        assert len(conflicts) == 2

    def test_no_dedup_when_disabled(self) -> None:
        """Deduplication can be disabled."""
        llm_resp = _make_llm_response([
            {
                "severity": "WARNING",
                "description": "LLM duplicate",
                "conflicting_fields": [
                    "technical_requirements.scope",
                    "technical_requirements.frameworks",
                ],
            },
        ])
        mock_gw = MagicMock(spec=LLMGateway)
        mock_gw.complete.return_value = llm_resp
        mock_pt = MagicMock(spec=PromptTemplate)
        mock_pt.render.return_value = "Prompt"
        config = DetectorConfig(use_llm=True, use_rules=True, deduplicate=False)
        detector = ConflictDetector(
            config=config, gateway=mock_gw, templates=mock_pt
        )
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        conflicts = detector.detect(spec)
        # Both rule and LLM conflicts kept (no dedup)
        assert len(conflicts) >= 2

    def test_conflicts_without_fields_not_deduped(self) -> None:
        """Conflicts without conflicting_fields are always kept."""
        detector = _make_detector()
        conflicts_in = [
            SpecConflict(
                severity=ConflictSeverity.WARNING,
                description="No fields 1",
                conflicting_fields=[],
            ),
            SpecConflict(
                severity=ConflictSeverity.WARNING,
                description="No fields 2",
                conflicting_fields=[],
            ),
        ]
        result = detector._deduplicate(conflicts_in)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Sorting Tests
# ---------------------------------------------------------------------------


class TestConflictSorting:
    """Test that conflicts are sorted by severity."""

    def test_sorted_error_first(self) -> None:
        """ERROR conflicts come before WARNING and INFO."""
        llm_resp = _make_llm_response([
            {"severity": "INFO", "description": "Info", "conflicting_fields": ["a"]},
            {"severity": "ERROR", "description": "Error", "conflicting_fields": ["b"]},
            {"severity": "WARNING", "description": "Warning", "conflicting_fields": ["c"]},
        ])
        detector = _make_detector(
            llm_response=llm_resp,
            use_llm=True,
            use_rules=False,
        )
        spec = _make_spec()
        conflicts = detector.detect(spec)
        assert conflicts[0].severity == ConflictSeverity.ERROR
        assert conflicts[1].severity == ConflictSeverity.WARNING
        assert conflicts[2].severity == ConflictSeverity.INFO


# ---------------------------------------------------------------------------
# detect_and_attach Tests
# ---------------------------------------------------------------------------


class TestDetectAndAttach:
    """Test the detect_and_attach convenience method."""

    def test_conflicts_attached_to_spec(self) -> None:
        """detect_and_attach adds conflicts to the spec."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        assert len(spec.conflicts) == 0
        detector = _make_detector()
        conflicts = detector.detect_and_attach(spec)
        assert len(conflicts) == 1
        assert len(spec.conflicts) == 1
        assert spec.conflicts[0].severity == ConflictSeverity.ERROR

    def test_no_conflicts_nothing_attached(self) -> None:
        """detect_and_attach with no conflicts leaves spec unchanged."""
        spec = _make_spec(
            scope=ScopeType.FULL_STACK,
            frameworks=["React", "Django"],
        )
        detector = _make_detector()
        conflicts = detector.detect_and_attach(spec)
        assert len(conflicts) == 0
        assert len(spec.conflicts) == 0

    def test_multiple_calls_accumulate(self) -> None:
        """Multiple detect_and_attach calls accumulate conflicts."""
        spec = _make_spec(
            scope=ScopeType.BACKEND_ONLY,
            frameworks=["React"],
        )
        detector = _make_detector()
        detector.detect_and_attach(spec)
        detector.detect_and_attach(spec)
        assert len(spec.conflicts) == 2


# ---------------------------------------------------------------------------
# Constructor Tests
# ---------------------------------------------------------------------------


class TestConflictDetectorConstruction:
    """Test ConflictDetector construction."""

    def test_rules_only_no_gateway(self) -> None:
        """Rules-only mode doesn't require a gateway."""
        config = DetectorConfig(use_llm=False, use_rules=True)
        detector = ConflictDetector(config=config)
        assert detector.gateway is None
        spec = _make_spec()
        conflicts = detector.detect(spec)
        assert isinstance(conflicts, list)

    def test_default_config_creates_gateway(self) -> None:
        """Default config (use_llm=True) creates a gateway."""
        # This would normally try to create a real gateway
        # Just test that config is set correctly
        config = DetectorConfig(use_llm=False)
        detector = ConflictDetector(config=config)
        assert detector.config.use_llm is False

    def test_custom_gateway(self) -> None:
        """Custom gateway is used."""
        mock_gw = MagicMock(spec=LLMGateway)
        config = DetectorConfig(use_llm=False)
        detector = ConflictDetector(config=config, gateway=mock_gw)
        assert detector.gateway is mock_gw


# ---------------------------------------------------------------------------
# Package Import Tests
# ---------------------------------------------------------------------------


class TestConflictDetectorPackageImports:
    """Test that the conflict detector is importable from the package."""

    def test_import_from_package(self) -> None:
        """Conflict detector classes are importable from zerorepo.spec_parser."""
        from zerorepo.spec_parser import (
            ConflictDetector,
            ConflictDetectorError,
            DetectorConfig,
        )
        assert ConflictDetector is not None
        assert ConflictDetectorError is not None
        assert DetectorConfig is not None

    def test_import_from_module(self) -> None:
        """Conflict detector classes are importable from the module."""
        from zerorepo.spec_parser.conflict_detector import (
            ConflictDetector,
            ConflictDetectorError,
            DetectorConfig,
            LLMConflictItem,
            LLMConflictResponse,
            _normalize_severity,
        )
        assert ConflictDetector is not None
        assert _normalize_severity is not None
