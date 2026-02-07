"""Unit tests for evaluation and benchmarking data models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from zerorepo.evaluation.models import (
    ABTestResult,
    BenchmarkResult,
    BenchmarkTask,
    CodeStats,
    DifficultyLevel,
    ExecutionResult,
    FailureCategory,
    FailureReport,
    FunctionSignature,
    ProfilingData,
    RepositoryResult,
    StageFailed,
    TaskResult,
    Taxonomy,
    TaxonomyNode,
    TokenStats,
    ValidationResult,
    Vote,
    VoteResult,
)


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestDifficultyLevel:
    """Tests for the DifficultyLevel enumeration."""

    def test_difficulty_values(self) -> None:
        """Verify all expected difficulty values exist."""
        assert DifficultyLevel.EASY == "easy"
        assert DifficultyLevel.MEDIUM == "medium"
        assert DifficultyLevel.HARD == "hard"

    def test_difficulty_from_string(self) -> None:
        """Verify difficulties can be constructed from strings."""
        assert DifficultyLevel("easy") is DifficultyLevel.EASY
        assert DifficultyLevel("medium") is DifficultyLevel.MEDIUM
        assert DifficultyLevel("hard") is DifficultyLevel.HARD

    def test_difficulty_invalid_string(self) -> None:
        """Invalid difficulty string raises ValueError."""
        with pytest.raises(ValueError):
            DifficultyLevel("INVALID")

    def test_difficulty_is_string_subclass(self) -> None:
        """DifficultyLevel values are string-compatible."""
        assert isinstance(DifficultyLevel.EASY, str)


class TestVoteResult:
    """Tests for the VoteResult enumeration."""

    def test_vote_result_values(self) -> None:
        """Verify all expected vote result values exist."""
        assert VoteResult.YES == "YES"
        assert VoteResult.NO == "NO"
        assert VoteResult.PARTIAL == "PARTIAL"

    def test_vote_result_from_string(self) -> None:
        """Verify vote results can be constructed from strings."""
        assert VoteResult("YES") is VoteResult.YES

    def test_vote_result_invalid_string(self) -> None:
        """Invalid vote result string raises ValueError."""
        with pytest.raises(ValueError):
            VoteResult("MAYBE")


class TestStageFailed:
    """Tests for the StageFailed enumeration."""

    def test_stage_failed_values(self) -> None:
        """Verify all expected stage failure values exist."""
        assert StageFailed.LOCALIZATION == "localization"
        assert StageFailed.VALIDATION == "validation"
        assert StageFailed.EXECUTION == "execution"


class TestFailureCategory:
    """Tests for the FailureCategory enumeration."""

    def test_failure_category_values(self) -> None:
        """Verify all expected failure category values exist."""
        assert FailureCategory.PLANNING == "planning"
        assert FailureCategory.GENERATION == "generation"
        assert FailureCategory.LOCALIZATION == "localization"
        assert FailureCategory.VALIDATION == "validation"
        assert FailureCategory.EXECUTION == "execution"
        assert FailureCategory.UNKNOWN == "unknown"

    def test_failure_category_count(self) -> None:
        """Verify the total number of failure categories."""
        assert len(FailureCategory) == 6


# ---------------------------------------------------------------------------
# BenchmarkTask Tests
# ---------------------------------------------------------------------------


class TestBenchmarkTask:
    """Tests for the BenchmarkTask model."""

    def test_create_minimal(self) -> None:
        """Create a task with only required fields."""
        task = BenchmarkTask(
            id="sklearn-ridge-001",
            project="scikit-learn",
            category="sklearn.linear_model",
            description="Test ridge regression",
            test_code="def test_ridge(): pass",
        )
        assert task.id == "sklearn-ridge-001"
        assert task.project == "scikit-learn"
        assert task.category == "sklearn.linear_model"
        assert task.subcategory == ""
        assert task.imports == []
        assert task.fixtures == []
        assert task.loc == 0
        assert task.difficulty == DifficultyLevel.MEDIUM

    def test_create_full(self) -> None:
        """Create a task with all fields populated."""
        task = BenchmarkTask(
            id="sklearn-ridge-001",
            project="scikit-learn",
            category="sklearn.linear_model",
            subcategory="ridge",
            description="Test ridge regression fit method",
            test_code="def test_ridge_fit():\n    assert True",
            imports=["import numpy as np"],
            fixtures=["sample_data"],
            auxiliary_code="def helper(): pass",
            loc=5,
            difficulty=DifficultyLevel.HARD,
            metadata={"source": "test_ridge.py"},
        )
        assert task.subcategory == "ridge"
        assert len(task.imports) == 1
        assert task.difficulty == DifficultyLevel.HARD
        assert task.metadata["source"] == "test_ridge.py"

    def test_empty_id_rejected(self) -> None:
        """Empty task ID should be rejected."""
        with pytest.raises(ValidationError):
            BenchmarkTask(
                id="",
                project="scikit-learn",
                category="sklearn.linear_model",
                description="Test ridge",
                test_code="def test(): pass",
            )

    def test_negative_loc_rejected(self) -> None:
        """Negative LOC should be rejected."""
        with pytest.raises(ValidationError):
            BenchmarkTask(
                id="task-001",
                project="proj",
                category="cat",
                description="desc",
                test_code="def test(): pass",
                loc=-1,
            )

    def test_serialization_roundtrip(self) -> None:
        """Verify model_dump and model_validate roundtrip."""
        task = BenchmarkTask(
            id="task-001",
            project="proj",
            category="cat",
            description="desc",
            test_code="def test(): pass",
            difficulty=DifficultyLevel.EASY,
        )
        data = task.model_dump()
        restored = BenchmarkTask.model_validate(data)
        assert restored.id == task.id
        assert restored.difficulty == task.difficulty


# ---------------------------------------------------------------------------
# FunctionSignature Tests
# ---------------------------------------------------------------------------


class TestFunctionSignature:
    """Tests for the FunctionSignature model."""

    def test_create_minimal(self) -> None:
        """Create a function signature with only required fields."""
        sig = FunctionSignature(
            name="ridge_regression",
            module="ml_lib.linear_model",
            signature="def ridge_regression(X, y, alpha=1.0)",
            file_path="ml_lib/linear_model.py",
        )
        assert sig.name == "ridge_regression"
        assert sig.docstring == ""
        assert sig.start_line == 0
        assert sig.body == ""

    def test_empty_name_rejected(self) -> None:
        """Empty function name should be rejected."""
        with pytest.raises(ValidationError):
            FunctionSignature(
                name="",
                module="ml_lib",
                signature="def foo()",
                file_path="ml_lib/foo.py",
            )


# ---------------------------------------------------------------------------
# Vote Tests
# ---------------------------------------------------------------------------


class TestVote:
    """Tests for the Vote model."""

    def test_create_vote(self) -> None:
        """Create a vote with all fields."""
        vote = Vote(
            result=VoteResult.YES,
            justification="Function implements ridge regression correctly",
            model="claude-3-sonnet",
            round_num=2,
        )
        assert vote.result == VoteResult.YES
        assert vote.round_num == 2

    def test_default_round_num(self) -> None:
        """Default round number should be 1."""
        vote = Vote(result=VoteResult.NO)
        assert vote.round_num == 1

    def test_invalid_round_num_rejected(self) -> None:
        """Round number less than 1 should be rejected."""
        with pytest.raises(ValidationError):
            Vote(result=VoteResult.YES, round_num=0)


# ---------------------------------------------------------------------------
# ValidationResult Tests
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Tests for the ValidationResult model."""

    def test_create_passing(self) -> None:
        """Create a passing validation result."""
        result = ValidationResult(
            passed=True,
            confidence="high",
            votes=[Vote(result=VoteResult.YES)],
            candidate_function="ridge_regression",
        )
        assert result.passed is True
        assert result.confidence == "high"
        assert len(result.votes) == 1

    def test_default_confidence(self) -> None:
        """Default confidence should be medium."""
        result = ValidationResult(passed=False)
        assert result.confidence == "medium"


# ---------------------------------------------------------------------------
# ExecutionResult Tests
# ---------------------------------------------------------------------------


class TestExecutionResult:
    """Tests for the ExecutionResult model."""

    def test_create_passing(self) -> None:
        """Create a passing execution result."""
        result = ExecutionResult(
            passed=True,
            exit_code=0,
            stdout="1 passed",
            duration_ms=150.5,
        )
        assert result.passed is True
        assert result.exit_code == 0
        assert result.duration_ms == 150.5

    def test_create_failing(self) -> None:
        """Create a failing execution result."""
        result = ExecutionResult(
            passed=False,
            exit_code=1,
            stderr="AssertionError",
            error="Test failed",
        )
        assert result.passed is False
        assert result.error == "Test failed"

    def test_negative_duration_rejected(self) -> None:
        """Negative duration should be rejected."""
        with pytest.raises(ValidationError):
            ExecutionResult(passed=True, duration_ms=-1.0)


# ---------------------------------------------------------------------------
# TaskResult Tests
# ---------------------------------------------------------------------------


class TestTaskResult:
    """Tests for the TaskResult model."""

    def test_create_fully_passed(self) -> None:
        """Create a task result that passed all stages."""
        result = TaskResult(
            task_id="task-001",
            localized=True,
            validated=True,
            passed=True,
            candidate_function="ridge_regression",
            candidate_score=0.95,
        )
        assert result.localized is True
        assert result.passed is True
        assert result.stage_failed is None

    def test_create_failed_at_validation(self) -> None:
        """Create a task result that failed at validation."""
        result = TaskResult(
            task_id="task-002",
            localized=True,
            validated=False,
            stage_failed=StageFailed.VALIDATION,
        )
        assert result.stage_failed == StageFailed.VALIDATION

    def test_candidate_score_range(self) -> None:
        """Candidate score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TaskResult(task_id="task-001", candidate_score=1.5)

    def test_empty_task_id_rejected(self) -> None:
        """Empty task ID should be rejected."""
        with pytest.raises(ValidationError):
            TaskResult(task_id="")


# ---------------------------------------------------------------------------
# RepositoryResult Tests
# ---------------------------------------------------------------------------


class TestRepositoryResult:
    """Tests for the RepositoryResult model."""

    def test_pass_rate_with_tasks(self) -> None:
        """Pass rate computed correctly with tasks."""
        result = RepositoryResult(
            project_name="test-project",
            total_tasks=10,
            localized=8,
            validated=6,
            passed=4,
        )
        assert result.pass_rate == pytest.approx(0.4)
        assert result.voting_rate == pytest.approx(0.6)
        assert result.localization_rate == pytest.approx(0.8)

    def test_pass_rate_zero_tasks(self) -> None:
        """Pass rate is 0.0 when total_tasks is zero."""
        result = RepositoryResult(
            project_name="empty-project",
            total_tasks=0,
        )
        assert result.pass_rate == 0.0
        assert result.voting_rate == 0.0
        assert result.localization_rate == 0.0

    def test_coverage_bounds(self) -> None:
        """Coverage must be between 0 and 1."""
        with pytest.raises(ValidationError):
            RepositoryResult(
                project_name="proj",
                total_tasks=10,
                coverage=1.5,
            )

    def test_serialization_with_task_results(self) -> None:
        """Serialization roundtrip with nested task results."""
        task_result = TaskResult(task_id="task-001", passed=True)
        result = RepositoryResult(
            project_name="proj",
            total_tasks=1,
            passed=1,
            task_results=[task_result],
        )
        data = result.model_dump()
        restored = RepositoryResult.model_validate(data)
        assert len(restored.task_results) == 1
        assert restored.task_results[0].task_id == "task-001"


# ---------------------------------------------------------------------------
# CodeStats Tests
# ---------------------------------------------------------------------------


class TestCodeStats:
    """Tests for the CodeStats model."""

    def test_default_values(self) -> None:
        """All fields default to zero."""
        stats = CodeStats()
        assert stats.files == 0
        assert stats.loc == 0
        assert stats.estimated_tokens == 0

    def test_negative_files_rejected(self) -> None:
        """Negative file count should be rejected."""
        with pytest.raises(ValidationError):
            CodeStats(files=-1)


# ---------------------------------------------------------------------------
# TokenStats Tests
# ---------------------------------------------------------------------------


class TestTokenStats:
    """Tests for the TokenStats model."""

    def test_total_tokens_computed(self) -> None:
        """Total tokens is sum of prompt and completion tokens."""
        stats = TokenStats(prompt_tokens=100, completion_tokens=50, total_calls=3)
        assert stats.total_tokens == 150

    def test_total_tokens_zero_default(self) -> None:
        """Default total tokens is zero."""
        stats = TokenStats()
        assert stats.total_tokens == 0

    def test_negative_tokens_rejected(self) -> None:
        """Negative token counts should be rejected."""
        with pytest.raises(ValidationError):
            TokenStats(prompt_tokens=-10)


# ---------------------------------------------------------------------------
# ProfilingData Tests
# ---------------------------------------------------------------------------


class TestProfilingData:
    """Tests for the ProfilingData model."""

    def test_total_tokens_across_stages(self) -> None:
        """Total tokens sums across all stages."""
        profiling = ProfilingData(
            stage_tokens={
                "localization": TokenStats(prompt_tokens=100, completion_tokens=50),
                "validation": TokenStats(prompt_tokens=200, completion_tokens=100),
            },
        )
        assert profiling.total_tokens == 450

    def test_total_cost_calculation(self) -> None:
        """Cost estimated at $10 per million tokens."""
        profiling = ProfilingData(
            stage_tokens={
                "stage1": TokenStats(prompt_tokens=500_000, completion_tokens=500_000),
            },
        )
        assert profiling.total_cost_usd == pytest.approx(10.0)

    def test_empty_profiling(self) -> None:
        """Empty profiling has zero tokens and cost."""
        profiling = ProfilingData()
        assert profiling.total_tokens == 0
        assert profiling.total_cost_usd == 0.0


# ---------------------------------------------------------------------------
# BenchmarkResult Tests
# ---------------------------------------------------------------------------


class TestBenchmarkResult:
    """Tests for the BenchmarkResult model."""

    def test_create_with_evaluation(self) -> None:
        """Create a benchmark result with evaluation data."""
        eval_result = RepositoryResult(
            project_name="scikit-learn",
            total_tasks=50,
            passed=30,
        )
        result = BenchmarkResult(
            project="scikit-learn",
            evaluation=eval_result,
        )
        assert result.project == "scikit-learn"
        assert result.evaluation.total_tasks == 50
        assert result.paraphrased_name == ""
        assert isinstance(result.timestamp, datetime)

    def test_timestamp_default(self) -> None:
        """Timestamp defaults to approximately now."""
        before = datetime.now()
        result = BenchmarkResult(
            project="proj",
            evaluation=RepositoryResult(project_name="proj", total_tasks=0),
        )
        after = datetime.now()
        assert before <= result.timestamp <= after


# ---------------------------------------------------------------------------
# Taxonomy Tests
# ---------------------------------------------------------------------------


class TestTaxonomyNode:
    """Tests for the TaxonomyNode model."""

    def test_create_leaf(self) -> None:
        """Create a leaf taxonomy node."""
        node = TaxonomyNode(name="ridge", count=5)
        assert node.name == "ridge"
        assert node.count == 5
        assert node.children == {}

    def test_create_nested(self) -> None:
        """Create a nested taxonomy tree."""
        child = TaxonomyNode(name="ridge", count=3)
        parent = TaxonomyNode(
            name="linear_model",
            count=10,
            children={"ridge": child},
        )
        assert "ridge" in parent.children
        assert parent.children["ridge"].count == 3

    def test_deep_nesting(self) -> None:
        """Create a deeply nested taxonomy tree."""
        leaf = TaxonomyNode(name="fit", count=1)
        mid = TaxonomyNode(name="ridge", count=2, children={"fit": leaf})
        root = TaxonomyNode(name="linear_model", count=5, children={"ridge": mid})
        assert root.children["ridge"].children["fit"].count == 1

    def test_empty_name_rejected(self) -> None:
        """Empty taxonomy node name should be rejected."""
        with pytest.raises(ValidationError):
            TaxonomyNode(name="")


class TestTaxonomy:
    """Tests for the Taxonomy model."""

    def test_create_empty(self) -> None:
        """Create an empty taxonomy."""
        taxonomy = Taxonomy()
        assert taxonomy.roots == {}
        assert taxonomy.total_tasks == 0
        assert taxonomy.total_categories == 0

    def test_create_with_roots(self) -> None:
        """Create a taxonomy with root nodes."""
        root = TaxonomyNode(name="sklearn", count=50)
        taxonomy = Taxonomy(
            roots={"sklearn": root},
            total_tasks=50,
            total_categories=10,
        )
        assert "sklearn" in taxonomy.roots
        assert taxonomy.total_tasks == 50


# ---------------------------------------------------------------------------
# FailureReport Tests
# ---------------------------------------------------------------------------


class TestFailureReport:
    """Tests for the FailureReport model."""

    def test_create_report(self) -> None:
        """Create a failure report with samples."""
        failed_task = TaskResult(
            task_id="task-fail",
            stage_failed=StageFailed.EXECUTION,
        )
        report = FailureReport(
            total_failures=1,
            category_counts={"execution": 1},
            samples={"execution": [failed_task]},
            recommendations=["Improve test assembly"],
        )
        assert report.total_failures == 1
        assert len(report.samples["execution"]) == 1
        assert len(report.recommendations) == 1

    def test_create_empty_report(self) -> None:
        """Create an empty failure report."""
        report = FailureReport(total_failures=0)
        assert report.category_counts == {}
        assert report.samples == {}
        assert report.recommendations == []


# ---------------------------------------------------------------------------
# ABTestResult Tests
# ---------------------------------------------------------------------------


class TestABTestResult:
    """Tests for the ABTestResult model."""

    def test_create_insignificant(self) -> None:
        """Create a non-significant A/B test result."""
        result = ABTestResult(
            baseline_pass_rate=0.5,
            variant_pass_rate=0.52,
            delta=0.02,
            p_value=0.35,
            significant=False,
            sample_size=100,
        )
        assert result.recommendation == "KEEP BASELINE"
        assert result.significant is False

    def test_create_significant(self) -> None:
        """Create a significant A/B test result."""
        result = ABTestResult(
            baseline_pass_rate=0.5,
            variant_pass_rate=0.7,
            delta=0.2,
            p_value=0.01,
            significant=True,
            sample_size=200,
            recommendation="ADOPT VARIANT",
        )
        assert result.significant is True
        assert result.recommendation == "ADOPT VARIANT"

    def test_pass_rate_bounds(self) -> None:
        """Pass rates must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ABTestResult(
                baseline_pass_rate=1.5,
                variant_pass_rate=0.5,
            )

    def test_p_value_bounds(self) -> None:
        """P-value must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ABTestResult(
                baseline_pass_rate=0.5,
                variant_pass_rate=0.6,
                p_value=1.5,
            )

    def test_serialization_roundtrip(self) -> None:
        """Verify model_dump and model_validate roundtrip."""
        result = ABTestResult(
            baseline_pass_rate=0.5,
            variant_pass_rate=0.6,
            delta=0.1,
            significant=True,
            sample_size=50,
        )
        data = result.model_dump()
        restored = ABTestResult.model_validate(data)
        assert restored.baseline_pass_rate == result.baseline_pass_rate
        assert restored.significant == result.significant
