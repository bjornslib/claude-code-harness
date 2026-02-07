"""Unit tests for FailureAnalyzer and PromptABTest classes.

Tests cover:
- Failure categorization from TaskResult fields
- Stage-based categorization (stage_failed field)
- Heuristic-based categorization
- Failure report generation and recommendations
- Threshold-based recommendation rules
- Function name fuzzy matching
- A/B test statistical analysis
- Chi-squared p-value approximation
"""

from __future__ import annotations

from typing import Any

import pytest

from zerorepo.evaluation.failure_analysis import (
    FailureAnalyzer,
    PromptABTest,
    RECOMMENDATION_RULES,
)
from zerorepo.evaluation.models import (
    ABTestResult,
    BenchmarkTask,
    FailureCategory,
    FailureReport,
    StageFailed,
    TaskResult,
)


def _make_result(
    passed: bool = False,
    stage_failed: StageFailed | None = None,
    localized: bool = False,
    validated: bool = False,
    execution_error: str | None = None,
    candidate_function: str | None = None,
    candidate_score: float = 0.0,
) -> TaskResult:
    """Create a TaskResult with configurable fields."""
    return TaskResult(
        task_id="task-001",
        passed=passed,
        localized=localized,
        validated=validated,
        stage_failed=stage_failed,
        execution_error=execution_error,
        candidate_function=candidate_function,
        candidate_score=candidate_score,
    )


def _make_task() -> BenchmarkTask:
    """Create a minimal BenchmarkTask."""
    return BenchmarkTask(
        id="task-001",
        project="test",
        category="test.cat",
        description="A test task",
        test_code="def test_x(): pass",
    )


# ---------------------------------------------------------------------------
# FailureAnalyzer.categorize_failure
# ---------------------------------------------------------------------------


class TestCategorizeFailure:
    """Tests for categorize_failure()."""

    def test_passed_returns_unknown(self) -> None:
        """Passed results should return UNKNOWN (not a failure)."""
        analyzer = FailureAnalyzer()
        result = _make_result(passed=True)
        assert analyzer.categorize_failure(result) == FailureCategory.UNKNOWN

    def test_stage_failed_localization(self) -> None:
        """stage_failed=LOCALIZATION should map to FailureCategory.LOCALIZATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(stage_failed=StageFailed.LOCALIZATION)
        assert analyzer.categorize_failure(result) == FailureCategory.LOCALIZATION

    def test_stage_failed_validation(self) -> None:
        """stage_failed=VALIDATION should map to FailureCategory.VALIDATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(stage_failed=StageFailed.VALIDATION)
        assert analyzer.categorize_failure(result) == FailureCategory.VALIDATION

    def test_stage_failed_execution(self) -> None:
        """stage_failed=EXECUTION should map to FailureCategory.EXECUTION."""
        analyzer = FailureAnalyzer()
        result = _make_result(stage_failed=StageFailed.EXECUTION)
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_not_localized_no_candidate(self) -> None:
        """Not localized with no good candidate should be GENERATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(localized=False, candidate_score=0.1)
        assert analyzer.categorize_failure(result) == FailureCategory.GENERATION

    def test_not_localized_with_candidate(self) -> None:
        """Not localized but good candidate score should be LOCALIZATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=False,
            candidate_function="ridge_regression",
            candidate_score=0.5,
        )
        assert analyzer.categorize_failure(result) == FailureCategory.LOCALIZATION

    def test_localized_not_validated(self) -> None:
        """Localized but not validated should be VALIDATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(localized=True, validated=False)
        assert analyzer.categorize_failure(result) == FailureCategory.VALIDATION

    def test_execution_error_import(self) -> None:
        """Execution error with 'import' keyword should be EXECUTION."""
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=True, validated=True, execution_error="ImportError: no module named foo"
        )
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_execution_error_timeout(self) -> None:
        """Execution error with 'timeout' keyword should be EXECUTION."""
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=True, validated=True, execution_error="Timeout after 30s"
        )
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_execution_error_generic(self) -> None:
        """Generic execution error should be EXECUTION."""
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=True, validated=True, execution_error="AssertionError: wrong value"
        )
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_unknown_fallthrough(self) -> None:
        """Result with no clear signals should return UNKNOWN."""
        analyzer = FailureAnalyzer()
        result = _make_result(localized=True, validated=True)
        assert analyzer.categorize_failure(result) == FailureCategory.UNKNOWN


# ---------------------------------------------------------------------------
# FailureAnalyzer.analyze_failures
# ---------------------------------------------------------------------------


class TestAnalyzeFailures:
    """Tests for analyze_failures()."""

    def test_no_failures(self) -> None:
        """No failures should return empty report with success message."""
        analyzer = FailureAnalyzer()
        results = [_make_result(passed=True)]
        report = analyzer.analyze_failures(results)

        assert isinstance(report, FailureReport)
        assert report.total_failures == 0
        assert "All tasks passed" in report.recommendations[0]

    def test_categorizes_failures(self) -> None:
        """Should categorize and count failures."""
        analyzer = FailureAnalyzer()
        results = [
            _make_result(stage_failed=StageFailed.LOCALIZATION),
            _make_result(stage_failed=StageFailed.LOCALIZATION),
            _make_result(stage_failed=StageFailed.VALIDATION),
        ]
        report = analyzer.analyze_failures(results)

        assert report.total_failures == 3
        assert report.category_counts["localization"] == 2
        assert report.category_counts["validation"] == 1

    def test_samples_limited(self) -> None:
        """Samples per category should be limited by max_samples."""
        analyzer = FailureAnalyzer(max_samples_per_category=2)
        results = [
            _make_result(stage_failed=StageFailed.EXECUTION) for _ in range(10)
        ]
        report = analyzer.analyze_failures(results)

        assert len(report.samples["execution"]) == 2

    def test_mixed_passed_and_failed(self) -> None:
        """Should only analyze failed results."""
        analyzer = FailureAnalyzer()
        results = [
            _make_result(passed=True),
            _make_result(passed=True),
            _make_result(stage_failed=StageFailed.EXECUTION),
        ]
        report = analyzer.analyze_failures(results)
        assert report.total_failures == 1


# ---------------------------------------------------------------------------
# FailureAnalyzer._generate_recommendations
# ---------------------------------------------------------------------------


class TestGenerateRecommendations:
    """Tests for _generate_recommendations()."""

    def test_high_rate_triggers_recommendation(self) -> None:
        """Failure rate above threshold should trigger recommendation."""
        analyzer = FailureAnalyzer()
        # EXECUTION threshold is 0.15 → 5/10 = 50% should trigger
        results = [_make_result(stage_failed=StageFailed.EXECUTION) for _ in range(5)]
        results += [_make_result(passed=True) for _ in range(5)]
        report = analyzer.analyze_failures(results)

        assert any("execution" in r.lower() for r in report.recommendations)

    def test_below_threshold_no_recommendation(self) -> None:
        """Failure rate below all thresholds should give 'within threshold' message."""
        analyzer = FailureAnalyzer()
        # 1 failure out of 100 = 1% → below all thresholds
        results = [_make_result(stage_failed=StageFailed.EXECUTION)]
        results += [_make_result(passed=True) for _ in range(99)]
        report = analyzer.analyze_failures(results)

        assert any("within acceptable thresholds" in r for r in report.recommendations)


# ---------------------------------------------------------------------------
# FailureAnalyzer.function_exists_different_name
# ---------------------------------------------------------------------------


class TestFunctionExistsDifferentName:
    """Tests for function_exists_different_name()."""

    def test_finds_similar_name(self) -> None:
        """Should find a function with similar name (normalized)."""
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function="ridge_regression")
        all_funcs = ["RidgeRegression", "linear_fit", "predict"]

        match = analyzer.function_exists_different_name(result, all_funcs)
        assert match == "RidgeRegression"

    def test_no_match(self) -> None:
        """Should return None when no similar name exists."""
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function="ridge_regression")
        all_funcs = ["linear_fit", "predict", "optimize"]

        match = analyzer.function_exists_different_name(result, all_funcs)
        assert match is None

    def test_no_candidate_function(self) -> None:
        """Should return None when no candidate function."""
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function=None)

        match = analyzer.function_exists_different_name(result, ["foo", "bar"])
        assert match is None

    def test_exact_match_excluded(self) -> None:
        """Exact same name should not be returned."""
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function="ridge_regression")
        all_funcs = ["ridge_regression", "linear_fit"]

        match = analyzer.function_exists_different_name(result, all_funcs)
        assert match is None


# ---------------------------------------------------------------------------
# PromptABTest
# ---------------------------------------------------------------------------


class TestPromptABTest:
    """Tests for PromptABTest A/B testing framework."""

    def test_variant_better(self) -> None:
        """Clear variant improvement should recommend USE VARIANT."""
        ab = PromptABTest("baseline prompt", "variant prompt")
        baseline = [True] * 30 + [False] * 70  # 30% pass
        variant = [True] * 70 + [False] * 30    # 70% pass
        result = ab.run_test(baseline, variant)

        assert isinstance(result, ABTestResult)
        assert result.variant_pass_rate > result.baseline_pass_rate
        assert result.delta > 0
        assert result.recommendation == "USE VARIANT"

    def test_baseline_better(self) -> None:
        """Clear baseline superiority should recommend KEEP BASELINE."""
        ab = PromptABTest("baseline prompt", "variant prompt")
        baseline = [True] * 70 + [False] * 30   # 70% pass
        variant = [True] * 30 + [False] * 70     # 30% pass
        result = ab.run_test(baseline, variant)

        assert result.delta < 0
        assert result.recommendation == "KEEP BASELINE"

    def test_no_difference(self) -> None:
        """Equal results should give NO SIGNIFICANT DIFFERENCE."""
        ab = PromptABTest("baseline prompt", "variant prompt")
        baseline = [True] * 50 + [False] * 50
        variant = [True] * 50 + [False] * 50
        result = ab.run_test(baseline, variant)

        assert result.recommendation == "NO SIGNIFICANT DIFFERENCE"

    def test_sample_size(self) -> None:
        """sample_size should be total of both groups."""
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True] * 20, [True] * 30)
        assert result.sample_size == 50

    def test_empty_baseline(self) -> None:
        """Empty baseline should give 0 rate and p=1.0."""
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([], [True, False])
        assert result.baseline_pass_rate == 0.0
        assert result.p_value == 1.0

    def test_empty_variant(self) -> None:
        """Empty variant should give 0 rate and p=1.0."""
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True, False], [])
        assert result.variant_pass_rate == 0.0
        assert result.p_value == 1.0


# ---------------------------------------------------------------------------
# Chi-squared p-value
# ---------------------------------------------------------------------------


class TestChiSquaredPValue:
    """Tests for the _chi_squared_p_value static method."""

    def test_identical_proportions(self) -> None:
        """Same proportions should give p=1.0 (or at least > 0.05)."""
        p = PromptABTest._chi_squared_p_value(50, 100, 50, 100)
        assert p >= 0.05

    def test_very_different_proportions(self) -> None:
        """Very different proportions with large n should give small p."""
        p = PromptABTest._chi_squared_p_value(10, 100, 90, 100)
        assert p < 0.05

    def test_zero_n_a(self) -> None:
        """n_a=0 should return 1.0."""
        p = PromptABTest._chi_squared_p_value(0, 0, 50, 100)
        assert p == 1.0

    def test_zero_n_b(self) -> None:
        """n_b=0 should return 1.0."""
        p = PromptABTest._chi_squared_p_value(50, 100, 0, 0)
        assert p == 1.0

    def test_all_success(self) -> None:
        """All success in both groups: p_pooled=1.0 → return 1.0."""
        p = PromptABTest._chi_squared_p_value(100, 100, 100, 100)
        assert p == 1.0

    def test_all_failure(self) -> None:
        """All failure in both groups: p_pooled=0.0 → return 1.0."""
        p = PromptABTest._chi_squared_p_value(0, 100, 0, 100)
        assert p == 1.0
