"""Wave 5 tests: Failure Analysis, A/B Testing, Caching, Batch Optimization.

Comprehensive test suite covering FailureAnalyzer, PromptABTest,
EmbeddingCache, LLMResponseCache, and BatchedFunctionGenerator.
"""
from __future__ import annotations

import hashlib

import pytest

from zerorepo.evaluation.caching import (
    BatchedFunctionGenerator,
    EmbeddingCache,
    LLMResponseCache,
)
from zerorepo.evaluation.failure_analysis import (
    FailureAnalyzer,
    PromptABTest,
    RECOMMENDATION_RULES,
)
from zerorepo.evaluation.models import (
    ABTestResult,
    FailureCategory,
    FailureReport,
    StageFailed,
    TaskResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    task_id: str = "task-001",
    passed: bool = False,
    localized: bool = False,
    validated: bool = False,
    stage_failed: StageFailed | None = None,
    candidate_function: str | None = None,
    candidate_score: float = 0.0,
    execution_error: str | None = None,
) -> TaskResult:
    """Helper to create TaskResult instances for testing."""
    return TaskResult(
        task_id=task_id,
        passed=passed,
        localized=localized,
        validated=validated,
        stage_failed=stage_failed,
        candidate_function=candidate_function,
        candidate_score=candidate_score,
        execution_error=execution_error,
    )


# ===========================================================================
# TestFailureAnalyzer
# ===========================================================================


class TestFailureAnalyzer:
    """Tests for FailureAnalyzer categorization and analysis."""

    def test_categorize_localization_failure(self):
        analyzer = FailureAnalyzer()
        result = _make_result(stage_failed=StageFailed.LOCALIZATION)
        assert analyzer.categorize_failure(result) == FailureCategory.LOCALIZATION

    def test_categorize_validation_failure(self):
        analyzer = FailureAnalyzer()
        result = _make_result(stage_failed=StageFailed.VALIDATION)
        assert analyzer.categorize_failure(result) == FailureCategory.VALIDATION

    def test_categorize_execution_failure(self):
        analyzer = FailureAnalyzer()
        result = _make_result(stage_failed=StageFailed.EXECUTION)
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_categorize_generation_failure_not_localized_low_score(self):
        analyzer = FailureAnalyzer()
        result = _make_result(localized=False, candidate_score=0.1)
        assert analyzer.categorize_failure(result) == FailureCategory.GENERATION

    def test_categorize_generation_failure_no_candidate(self):
        analyzer = FailureAnalyzer()
        result = _make_result(localized=False, candidate_function=None)
        assert analyzer.categorize_failure(result) == FailureCategory.GENERATION

    def test_categorize_localization_heuristic_high_score(self):
        """Not localized but candidate exists with score > 0.3 => LOCALIZATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=False,
            candidate_function="some_func",
            candidate_score=0.5,
        )
        assert analyzer.categorize_failure(result) == FailureCategory.LOCALIZATION

    def test_categorize_passed_task(self):
        analyzer = FailureAnalyzer()
        result = _make_result(passed=True)
        assert analyzer.categorize_failure(result) == FailureCategory.UNKNOWN

    def test_categorize_import_error(self):
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=True,
            validated=True,
            execution_error="ModuleNotFoundError: No module named 'foo'",
        )
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_categorize_timeout_error(self):
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=True,
            validated=True,
            execution_error="TimeoutError: execution timeout exceeded",
        )
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_categorize_generic_execution_error(self):
        analyzer = FailureAnalyzer()
        result = _make_result(
            localized=True,
            validated=True,
            execution_error="AssertionError: values differ",
        )
        assert analyzer.categorize_failure(result) == FailureCategory.EXECUTION

    def test_categorize_unknown_no_stage_no_error(self):
        analyzer = FailureAnalyzer()
        result = _make_result(localized=True, validated=True)
        assert analyzer.categorize_failure(result) == FailureCategory.UNKNOWN

    def test_categorize_validation_heuristic(self):
        """Localized but not validated => VALIDATION."""
        analyzer = FailureAnalyzer()
        result = _make_result(localized=True, validated=False)
        assert analyzer.categorize_failure(result) == FailureCategory.VALIDATION

    def test_analyze_no_failures(self):
        analyzer = FailureAnalyzer()
        results = [_make_result(passed=True) for _ in range(5)]
        report = analyzer.analyze_failures(results)
        assert report.total_failures == 0
        assert "All tasks passed" in report.recommendations[0]

    def test_analyze_mixed_failures(self):
        analyzer = FailureAnalyzer()
        results = [
            _make_result(passed=True),
            _make_result(stage_failed=StageFailed.LOCALIZATION),
            _make_result(stage_failed=StageFailed.VALIDATION),
            _make_result(stage_failed=StageFailed.EXECUTION),
        ]
        report = analyzer.analyze_failures(results)
        assert report.total_failures == 3
        assert "localization" in report.category_counts
        assert "validation" in report.category_counts
        assert "execution" in report.category_counts

    def test_analyze_all_localization(self):
        analyzer = FailureAnalyzer()
        results = [
            _make_result(
                task_id=f"task-{i}",
                stage_failed=StageFailed.LOCALIZATION,
            )
            for i in range(10)
        ]
        report = analyzer.analyze_failures(results)
        assert report.total_failures == 10
        assert report.category_counts.get("localization") == 10

    def test_recommendations_above_threshold(self):
        """When execution failures are >15%, recommendation is generated."""
        analyzer = FailureAnalyzer()
        # 3 out of 10 = 30% execution failures (threshold is 15%)
        results = [_make_result(passed=True) for _ in range(7)]
        results += [
            _make_result(
                task_id=f"exec-{i}",
                stage_failed=StageFailed.EXECUTION,
            )
            for i in range(3)
        ]
        report = analyzer.analyze_failures(results)
        assert any("execution" in r.lower() for r in report.recommendations)

    def test_recommendations_below_threshold(self):
        """When all failure rates are below thresholds, generic message."""
        analyzer = FailureAnalyzer()
        # 1 out of 100 = 1% (below all thresholds)
        results = [_make_result(passed=True, task_id=f"ok-{i}") for i in range(99)]
        results.append(
            _make_result(task_id="fail-1", stage_failed=StageFailed.EXECUTION)
        )
        report = analyzer.analyze_failures(results)
        assert any("within acceptable" in r for r in report.recommendations)

    def test_function_exists_different_name_match(self):
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function="ridge_regression")
        match = analyzer.function_exists_different_name(
            result, ["linear_ridge_regression", "lasso_regression"]
        )
        assert match == "linear_ridge_regression"

    def test_function_exists_different_name_no_match(self):
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function="ridge_regression")
        match = analyzer.function_exists_different_name(
            result, ["lasso_regression", "svm_classify"]
        )
        assert match is None

    def test_function_exists_different_name_no_candidate(self):
        analyzer = FailureAnalyzer()
        result = _make_result(candidate_function=None)
        match = analyzer.function_exists_different_name(
            result, ["ridge_regression"]
        )
        assert match is None

    def test_max_samples_limit(self):
        analyzer = FailureAnalyzer(max_samples_per_category=3)
        results = [
            _make_result(
                task_id=f"loc-{i}",
                stage_failed=StageFailed.LOCALIZATION,
            )
            for i in range(10)
        ]
        report = analyzer.analyze_failures(results)
        assert len(report.samples.get("localization", [])) == 3

    def test_default_max_samples(self):
        analyzer = FailureAnalyzer()
        assert analyzer.max_samples == 10

    def test_custom_max_samples(self):
        analyzer = FailureAnalyzer(max_samples_per_category=5)
        assert analyzer.max_samples == 5

    def test_analyze_empty_results(self):
        analyzer = FailureAnalyzer()
        report = analyzer.analyze_failures([])
        assert report.total_failures == 0

    def test_recommendation_rules_coverage(self):
        """All FailureCategory values in RECOMMENDATION_RULES except UNKNOWN."""
        for cat in [
            FailureCategory.PLANNING,
            FailureCategory.GENERATION,
            FailureCategory.LOCALIZATION,
            FailureCategory.VALIDATION,
            FailureCategory.EXECUTION,
        ]:
            assert cat in RECOMMENDATION_RULES


# ===========================================================================
# TestEmbeddingCache
# ===========================================================================


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    def test_get_miss(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.get("hello world") is None

    def test_put_and_get(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        embedding = [0.1, 0.2, 0.3]
        cache.put("hello world", embedding)
        result = cache.get("hello world")
        assert result == [0.1, 0.2, 0.3]

    def test_hit_rate_calculation(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.get("a")  # hit
        cache.get("b")  # miss
        assert cache.hit_rate == pytest.approx(0.5)

    def test_hit_rate_zero_total(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.hit_rate == 0.0

    def test_clear_cache(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        removed = cache.clear()
        assert removed == 2
        assert cache.get("a") is None

    def test_stats(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("x", [1.0])
        cache.get("x")  # hit
        cache.get("y")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["cache_files"] == 1
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_consistent_key_for_same_text(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        key1 = cache._key("identical text")
        key2 = cache._key("identical text")
        assert key1 == key2

    def test_different_key_for_different_text(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        key1 = cache._key("text a")
        key2 = cache._key("text b")
        assert key1 != key2

    def test_clear_resets_counters(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.get("a")  # hit
        cache.clear()
        assert cache._hits == 0
        assert cache._misses == 0

    def test_overwrite_existing(self, tmp_path):
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("key", [1.0])
        cache.put("key", [2.0])
        assert cache.get("key") == [2.0]


# ===========================================================================
# TestLLMResponseCache
# ===========================================================================


class TestLLMResponseCache:
    """Tests for LLMResponseCache."""

    def test_get_miss(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.get("gpt-4", "hello") is None

    def test_put_and_get(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("gpt-4", "What is 2+2?", "4")
        assert cache.get("gpt-4", "What is 2+2?") == "4"

    def test_different_models_different_keys(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("gpt-4", "prompt", "response_a")
        cache.put("claude", "prompt", "response_b")
        assert cache.get("gpt-4", "prompt") == "response_a"
        assert cache.get("claude", "prompt") == "response_b"

    def test_hit_rate(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "r")
        cache.get("m", "p")  # hit
        cache.get("m", "other")  # miss
        assert cache.hit_rate == pytest.approx(0.5)

    def test_hit_rate_zero(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.hit_rate == 0.0

    def test_clear(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p1", "r1")
        cache.put("m", "p2", "r2")
        removed = cache.clear()
        assert removed == 2
        assert cache.get("m", "p1") is None

    def test_stats(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "r")
        cache.get("m", "p")  # hit
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["cache_files"] == 1

    def test_clear_resets_counters(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "r")
        cache.get("m", "p")
        cache.clear()
        assert cache._hits == 0
        assert cache._misses == 0

    def test_overwrite_existing(self, tmp_path):
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "old")
        cache.put("m", "p", "new")
        assert cache.get("m", "p") == "new"


# ===========================================================================
# TestBatchedFunctionGenerator
# ===========================================================================


class TestBatchedFunctionGenerator:
    """Tests for BatchedFunctionGenerator."""

    def test_create_batch_prompt(self):
        gen = BatchedFunctionGenerator(max_batch_size=5)
        reqs = [
            {"name": "add", "description": "Add two numbers", "signature": "def add(a, b)"},
            {"name": "sub", "description": "Subtract", "signature": "def sub(a, b)"},
        ]
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1: add" in prompt
        assert "Function 2: sub" in prompt
        assert "---FUNCTION---" in prompt

    def test_parse_batch_response(self):
        gen = BatchedFunctionGenerator()
        response = "def add(a, b):\n    return a + b\n---FUNCTION---\ndef sub(a, b):\n    return a - b"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 2
        assert "def add" in parts[0]
        assert "def sub" in parts[1]

    def test_parse_batch_response_trailing_separator(self):
        gen = BatchedFunctionGenerator()
        response = "def foo(): pass\n---FUNCTION---\n"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 1

    def test_create_batches_exact(self):
        gen = BatchedFunctionGenerator(max_batch_size=3)
        reqs = [{"name": f"f{i}"} for i in range(6)]
        batches = gen.create_batches(reqs)
        assert len(batches) == 2
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3

    def test_create_batches_remainder(self):
        gen = BatchedFunctionGenerator(max_batch_size=3)
        reqs = [{"name": f"f{i}"} for i in range(7)]
        batches = gen.create_batches(reqs)
        assert len(batches) == 3
        assert len(batches[2]) == 1

    def test_max_batch_size_limit(self):
        gen = BatchedFunctionGenerator(max_batch_size=2)
        reqs = [
            {"name": f"f{i}", "description": f"desc {i}", "signature": f"def f{i}()"}
            for i in range(5)
        ]
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1:" in prompt
        assert "Function 2:" in prompt
        assert "Function 3:" not in prompt

    def test_empty_requirements(self):
        gen = BatchedFunctionGenerator()
        batches = gen.create_batches([])
        assert batches == []

    def test_single_requirement(self):
        gen = BatchedFunctionGenerator(max_batch_size=5)
        reqs = [{"name": "only", "description": "one", "signature": "def only()"}]
        batches = gen.create_batches(reqs)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_custom_separator(self):
        gen = BatchedFunctionGenerator(separator="===SPLIT===")
        response = "part1===SPLIT===part2"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 2

    def test_missing_keys_in_requirements(self):
        gen = BatchedFunctionGenerator()
        reqs = [{"name": "test"}]  # missing description and signature
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1: test" in prompt
        # Should use defaults for missing keys
        assert "Description:" in prompt


# ===========================================================================
# TestPromptABTest
# ===========================================================================


class TestPromptABTest:
    """Tests for PromptABTest A/B testing framework."""

    def test_run_test_variant_better(self):
        ab = PromptABTest("baseline prompt", "variant prompt")
        # Variant clearly better: 90% vs 50%
        baseline = [True] * 50 + [False] * 50
        variant = [True] * 90 + [False] * 10
        result = ab.run_test(baseline, variant)
        assert result.variant_pass_rate > result.baseline_pass_rate
        assert result.delta > 0
        assert result.significant is True
        assert result.recommendation == "USE VARIANT"

    def test_run_test_baseline_better(self):
        ab = PromptABTest("baseline prompt", "variant prompt")
        # Baseline clearly better: 90% vs 50%
        baseline = [True] * 90 + [False] * 10
        variant = [True] * 50 + [False] * 50
        result = ab.run_test(baseline, variant)
        assert result.delta < 0
        assert result.significant is True
        assert result.recommendation == "KEEP BASELINE"

    def test_significance_calculation(self):
        ab = PromptABTest("base", "var")
        # Large difference, large sample => significant
        baseline = [True] * 30 + [False] * 70
        variant = [True] * 70 + [False] * 30
        result = ab.run_test(baseline, variant)
        assert result.p_value < 0.05
        assert result.significant is True

    def test_small_sample_not_significant(self):
        ab = PromptABTest("base", "var")
        # Small sample, small difference => not significant
        baseline = [True, False, True]
        variant = [True, True, False]
        result = ab.run_test(baseline, variant)
        assert result.significant is False
        assert result.recommendation == "NO SIGNIFICANT DIFFERENCE"

    def test_recommendation_messages(self):
        ab = PromptABTest("base", "var")
        # Equal performance
        baseline = [True] * 50 + [False] * 50
        variant = [True] * 50 + [False] * 50
        result = ab.run_test(baseline, variant)
        assert result.recommendation == "NO SIGNIFICANT DIFFERENCE"
        assert result.delta == pytest.approx(0.0)

    def test_sample_size(self):
        ab = PromptABTest("base", "var")
        baseline = [True] * 20
        variant = [False] * 30
        result = ab.run_test(baseline, variant)
        assert result.sample_size == 50

    def test_pass_rates(self):
        ab = PromptABTest("base", "var")
        baseline = [True, True, False, False]  # 50%
        variant = [True, True, True, False]  # 75%
        result = ab.run_test(baseline, variant)
        assert result.baseline_pass_rate == pytest.approx(0.5)
        assert result.variant_pass_rate == pytest.approx(0.75)

    def test_p_value_identical_results(self):
        """Identical results => p_pooled difference is 0 => high p-value."""
        ab = PromptABTest("base", "var")
        baseline = [True] * 10
        variant = [True] * 10
        result = ab.run_test(baseline, variant)
        # All pass => p_pooled = 1.0 => returns 1.0
        assert result.p_value == 1.0

    def test_all_false_results(self):
        """All false => p_pooled = 0 => returns 1.0."""
        ab = PromptABTest("base", "var")
        baseline = [False] * 10
        variant = [False] * 10
        result = ab.run_test(baseline, variant)
        assert result.p_value == 1.0

    def test_return_type(self):
        ab = PromptABTest("base", "var")
        result = ab.run_test([True, False], [True, False])
        assert isinstance(result, ABTestResult)

    def test_prompts_stored(self):
        ab = PromptABTest("my baseline", "my variant")
        assert ab.baseline_prompt == "my baseline"
        assert ab.variant_prompt == "my variant"
