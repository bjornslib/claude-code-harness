"""Unit tests for Wave 5: FailureAnalyzer, EmbeddingCache, LLMResponseCache,
BatchedFunctionGenerator, and PromptABTest.

All external dependencies are mocked.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from cobuilder.repomap.evaluation.caching import (
    BatchedFunctionGenerator,
    EmbeddingCache,
    LLMResponseCache,
)
from cobuilder.repomap.evaluation.failure_analysis import (
    FailureAnalyzer,
    PromptABTest,
    RECOMMENDATION_RULES,
)
from cobuilder.repomap.evaluation.models import (
    ABTestResult,
    BenchmarkTask,
    ExecutionResult,
    FailureCategory,
    FailureReport,
    StageFailed,
    TaskResult,
    ValidationResult,
    Vote,
    VoteResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_result(
    task_id: str = "task-001",
    localized: bool = False,
    validated: bool = False,
    passed: bool = False,
    stage_failed: StageFailed | None = None,
    candidate_function: str | None = None,
    candidate_score: float = 0.0,
    execution_error: str | None = None,
) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        localized=localized,
        validated=validated,
        passed=passed,
        stage_failed=stage_failed,
        candidate_function=candidate_function,
        candidate_score=candidate_score,
        execution_error=execution_error,
    )


# ===========================================================================
# TestFailureAnalyzer
# ===========================================================================


class TestFailureAnalyzerCategorize:
    """Tests for FailureAnalyzer.categorize_failure()."""

    def test_passed_task_returns_unknown(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(passed=True)
        assert fa.categorize_failure(result) == FailureCategory.UNKNOWN

    def test_stage_failed_localization(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(stage_failed=StageFailed.LOCALIZATION)
        assert fa.categorize_failure(result) == FailureCategory.LOCALIZATION

    def test_stage_failed_validation(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(stage_failed=StageFailed.VALIDATION)
        assert fa.categorize_failure(result) == FailureCategory.VALIDATION

    def test_stage_failed_execution(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(stage_failed=StageFailed.EXECUTION)
        assert fa.categorize_failure(result) == FailureCategory.EXECUTION

    def test_not_localized_no_candidate_returns_generation(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(localized=False)
        assert fa.categorize_failure(result) == FailureCategory.GENERATION

    def test_not_localized_with_low_score_candidate_returns_generation(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(
            localized=False, candidate_function="ridge", candidate_score=0.2
        )
        assert fa.categorize_failure(result) == FailureCategory.GENERATION

    def test_not_localized_with_high_score_candidate_returns_localization(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(
            localized=False, candidate_function="ridge_regression", candidate_score=0.5
        )
        assert fa.categorize_failure(result) == FailureCategory.LOCALIZATION

    def test_localized_not_validated_returns_validation(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(localized=True, validated=False)
        assert fa.categorize_failure(result) == FailureCategory.VALIDATION

    def test_execution_error_import(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(
            localized=True, validated=True,
            execution_error="ModuleNotFoundError: No module named 'sklearn'",
        )
        assert fa.categorize_failure(result) == FailureCategory.EXECUTION

    def test_execution_error_timeout(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(
            localized=True, validated=True,
            execution_error="Execution timeout after 30s",
        )
        assert fa.categorize_failure(result) == FailureCategory.EXECUTION

    def test_execution_error_generic(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(
            localized=True, validated=True,
            execution_error="AssertionError: values differ",
        )
        assert fa.categorize_failure(result) == FailureCategory.EXECUTION

    def test_no_stage_failed_no_error_returns_unknown(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(localized=True, validated=True)
        assert fa.categorize_failure(result) == FailureCategory.UNKNOWN


class TestFailureAnalyzerAnalyze:
    """Tests for FailureAnalyzer.analyze_failures()."""

    def test_all_passed_returns_no_failures(self) -> None:
        fa = FailureAnalyzer()
        results = [_make_task_result(task_id=f"t-{i}", passed=True) for i in range(5)]
        report = fa.analyze_failures(results)
        assert report.total_failures == 0
        assert "All tasks passed" in report.recommendations[0]

    def test_mixed_failures_categorized(self) -> None:
        fa = FailureAnalyzer()
        results = [
            _make_task_result(task_id="t-1", stage_failed=StageFailed.LOCALIZATION),
            _make_task_result(task_id="t-2", stage_failed=StageFailed.LOCALIZATION),
            _make_task_result(task_id="t-3", stage_failed=StageFailed.VALIDATION),
            _make_task_result(task_id="t-4", passed=True),
        ]
        report = fa.analyze_failures(results)
        assert report.total_failures == 3
        assert report.category_counts.get("localization") == 2
        assert report.category_counts.get("validation") == 1

    def test_samples_limited(self) -> None:
        fa = FailureAnalyzer(max_samples_per_category=2)
        results = [
            _make_task_result(task_id=f"t-{i}", stage_failed=StageFailed.LOCALIZATION)
            for i in range(10)
        ]
        report = fa.analyze_failures(results)
        assert len(report.samples.get("localization", [])) == 2

    def test_recommendations_triggered_above_threshold(self) -> None:
        fa = FailureAnalyzer()
        # 4 localization failures out of 5 tasks = 80% > 25% threshold
        results = [
            _make_task_result(task_id=f"t-{i}", stage_failed=StageFailed.LOCALIZATION)
            for i in range(4)
        ] + [_make_task_result(task_id="t-5", passed=True)]
        report = fa.analyze_failures(results)
        assert any("localization" in r.lower() for r in report.recommendations)

    def test_no_recommendations_when_below_threshold(self) -> None:
        fa = FailureAnalyzer()
        # 1 localization failure out of 100 = 1% < 25% threshold
        results = [_make_task_result(task_id="t-1", stage_failed=StageFailed.LOCALIZATION)]
        results += [_make_task_result(task_id=f"t-{i}", passed=True) for i in range(2, 100)]
        report = fa.analyze_failures(results)
        # Should get the "within acceptable thresholds" message
        assert any("acceptable" in r.lower() for r in report.recommendations)

    def test_multiple_recommendation_types(self) -> None:
        fa = FailureAnalyzer()
        # Many failures across multiple categories
        results = [
            _make_task_result(task_id=f"loc-{i}", stage_failed=StageFailed.LOCALIZATION)
            for i in range(5)
        ] + [
            _make_task_result(task_id=f"exec-{i}", stage_failed=StageFailed.EXECUTION)
            for i in range(5)
        ]
        report = fa.analyze_failures(results)
        assert report.total_failures == 10
        assert len(report.recommendations) >= 2


class TestFailureAnalyzerFuzzyMatch:
    """Tests for FailureAnalyzer.function_exists_different_name()."""

    def test_finds_similar_name(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(candidate_function="ridge_regression")
        match = fa.function_exists_different_name(
            result, ["RidgeRegression", "linear_model", "svm_fit"]
        )
        assert match == "RidgeRegression"

    def test_no_candidate_returns_none(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(candidate_function=None)
        match = fa.function_exists_different_name(result, ["foo", "bar"])
        assert match is None

    def test_exact_match_ignored(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(candidate_function="ridge")
        match = fa.function_exists_different_name(result, ["ridge", "svm"])
        assert match is None  # Same name doesn't count

    def test_no_match_returns_none(self) -> None:
        fa = FailureAnalyzer()
        result = _make_task_result(candidate_function="ridge")
        match = fa.function_exists_different_name(result, ["svm", "knn"])
        assert match is None


# ===========================================================================
# TestEmbeddingCache
# ===========================================================================


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    def test_get_miss_returns_none(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.get("hello world") is None
        assert cache._misses == 1

    def test_put_and_get(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        embedding = [0.1, 0.2, 0.3]
        cache.put("hello", embedding)
        result = cache.get("hello")
        assert result == embedding
        assert cache._hits == 1

    def test_hit_rate(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.get("a")  # hit
        cache.get("b")  # miss
        assert cache.hit_rate == pytest.approx(0.5)

    def test_stats(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.get("a")
        cache.get("b")
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["cache_files"] == 1

    def test_clear(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        count = cache.clear()
        assert count == 2
        assert cache.get("a") is None
        assert cache._hits == 0
        assert cache._misses == 1  # The get after clear

    def test_different_texts_different_keys(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("text_a", [1.0])
        cache.put("text_b", [2.0])
        assert cache.get("text_a") == [1.0]
        assert cache.get("text_b") == [2.0]

    def test_overwrite_existing(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1.0])
        cache.put("a", [9.9])
        assert cache.get("a") == [9.9]

    def test_creates_directory(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "nested" / "emb"
        cache = EmbeddingCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_hit_rate_no_operations(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.hit_rate == 0.0


# ===========================================================================
# TestLLMResponseCache
# ===========================================================================


class TestLLMResponseCache:
    """Tests for LLMResponseCache."""

    def test_get_miss_returns_none(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.get("gpt-4", "some prompt") is None
        assert cache._misses == 1

    def test_put_and_get(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("gpt-4", "prompt1", "response1")
        assert cache.get("gpt-4", "prompt1") == "response1"
        assert cache._hits == 1

    def test_different_models_different_keys(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("gpt-4", "prompt", "response_gpt4")
        cache.put("claude", "prompt", "response_claude")
        assert cache.get("gpt-4", "prompt") == "response_gpt4"
        assert cache.get("claude", "prompt") == "response_claude"

    def test_hit_rate(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "r")
        cache.get("m", "p")  # hit
        cache.get("m", "other")  # miss
        assert cache.hit_rate == pytest.approx(0.5)

    def test_stats(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "r")
        cache.get("m", "p")
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["cache_files"] == 1

    def test_clear(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m1", "p1", "r1")
        cache.put("m2", "p2", "r2")
        count = cache.clear()
        assert count == 2
        assert cache.get("m1", "p1") is None

    def test_overwrite(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "old")
        cache.put("m", "p", "new")
        assert cache.get("m", "p") == "new"

    def test_hit_rate_no_operations(self, tmp_path: Path) -> None:
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.hit_rate == 0.0


# ===========================================================================
# TestBatchedFunctionGenerator
# ===========================================================================


class TestBatchedFunctionGenerator:
    """Tests for BatchedFunctionGenerator."""

    def test_create_batch_prompt_single(self) -> None:
        gen = BatchedFunctionGenerator()
        reqs = [{"name": "ridge", "description": "Ridge regression", "signature": "def ridge(X, y)"}]
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1: ridge" in prompt
        assert "Ridge regression" in prompt
        assert "def ridge(X, y)" in prompt

    def test_create_batch_prompt_multiple(self) -> None:
        gen = BatchedFunctionGenerator(max_batch_size=3)
        reqs = [
            {"name": f"func_{i}", "description": f"Desc {i}", "signature": f"def func_{i}()"}
            for i in range(5)
        ]
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1:" in prompt
        assert "Function 2:" in prompt
        assert "Function 3:" in prompt
        # Should NOT include 4 and 5 (batch size 3)
        assert "Function 4:" not in prompt

    def test_create_batch_prompt_missing_keys(self) -> None:
        gen = BatchedFunctionGenerator()
        reqs = [{"name": "test"}]  # Missing description and signature
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1: test" in prompt

    def test_parse_batch_response(self) -> None:
        gen = BatchedFunctionGenerator()
        response = "def ridge(): pass\n---FUNCTION---\ndef svm(): pass"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 2
        assert "def ridge(): pass" in parts[0]
        assert "def svm(): pass" in parts[1]

    def test_parse_batch_response_empty(self) -> None:
        gen = BatchedFunctionGenerator()
        parts = gen.parse_batch_response("")
        assert parts == []

    def test_parse_batch_response_custom_separator(self) -> None:
        gen = BatchedFunctionGenerator(separator="###SPLIT###")
        response = "func_a###SPLIT###func_b"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 2

    def test_create_batches(self) -> None:
        gen = BatchedFunctionGenerator(max_batch_size=3)
        reqs = [{"name": f"f{i}"} for i in range(7)]
        batches = gen.create_batches(reqs)
        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 1

    def test_create_batches_exact_fit(self) -> None:
        gen = BatchedFunctionGenerator(max_batch_size=5)
        reqs = [{"name": f"f{i}"} for i in range(10)]
        batches = gen.create_batches(reqs)
        assert len(batches) == 2
        assert all(len(b) == 5 for b in batches)

    def test_create_batches_single_item(self) -> None:
        gen = BatchedFunctionGenerator(max_batch_size=5)
        reqs = [{"name": "solo"}]
        batches = gen.create_batches(reqs)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_create_batches_empty(self) -> None:
        gen = BatchedFunctionGenerator()
        batches = gen.create_batches([])
        assert batches == []

    def test_default_config(self) -> None:
        gen = BatchedFunctionGenerator()
        assert gen.max_batch_size == 5
        assert gen.separator == "---FUNCTION---"


# ===========================================================================
# TestPromptABTest
# ===========================================================================


class TestPromptABTest:
    """Tests for PromptABTest."""

    def test_variant_clearly_better(self) -> None:
        ab = PromptABTest("baseline", "variant")
        # Large sample, clear difference
        baseline = [True] * 30 + [False] * 70  # 30%
        variant = [True] * 80 + [False] * 20  # 80%
        result = ab.run_test(baseline, variant)
        assert result.baseline_pass_rate == pytest.approx(0.3)
        assert result.variant_pass_rate == pytest.approx(0.8)
        assert result.delta == pytest.approx(0.5)
        assert result.significant is True
        assert result.recommendation == "USE VARIANT"

    def test_baseline_clearly_better(self) -> None:
        ab = PromptABTest("baseline", "variant")
        baseline = [True] * 80 + [False] * 20
        variant = [True] * 20 + [False] * 80
        result = ab.run_test(baseline, variant)
        assert result.significant is True
        assert result.recommendation == "KEEP BASELINE"

    def test_no_significant_difference(self) -> None:
        ab = PromptABTest("baseline", "variant")
        baseline = [True] * 50 + [False] * 50
        variant = [True] * 52 + [False] * 48
        result = ab.run_test(baseline, variant)
        assert result.recommendation == "NO SIGNIFICANT DIFFERENCE"

    def test_empty_baseline(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([], [True, False])
        assert result.baseline_pass_rate == 0.0
        assert result.p_value == 1.0

    def test_empty_variant(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True, False], [])
        assert result.variant_pass_rate == 0.0
        assert result.p_value == 1.0

    def test_all_pass_both(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True] * 50, [True] * 50)
        assert result.delta == pytest.approx(0.0)
        assert result.p_value == 1.0  # No difference possible

    def test_all_fail_both(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([False] * 50, [False] * 50)
        assert result.delta == pytest.approx(0.0)
        assert result.p_value == 1.0

    def test_sample_size_correct(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True] * 30, [True] * 20)
        assert result.sample_size == 50

    def test_result_is_ab_test_result(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True], [False])
        assert isinstance(result, ABTestResult)

    def test_small_sample_weak_difference(self) -> None:
        ab = PromptABTest("baseline", "variant")
        result = ab.run_test([True, False], [True, True])
        # Too small sample to be significant
        assert result.p_value > 0.05 or result.recommendation in (
            "USE VARIANT", "NO SIGNIFICANT DIFFERENCE"
        )


# ===========================================================================
# Integration: imports from package
# ===========================================================================


class TestPackageImports:
    """Verify all classes are importable from cobuilder.repomap.evaluation package."""

    def test_import_failure_analyzer(self) -> None:
        from cobuilder.repomap.evaluation import FailureAnalyzer as FA
        assert FA is FailureAnalyzer

    def test_import_prompt_ab_test(self) -> None:
        from cobuilder.repomap.evaluation import PromptABTest as PAB
        assert PAB is PromptABTest

    def test_import_embedding_cache(self) -> None:
        from cobuilder.repomap.evaluation import EmbeddingCache as EC
        assert EC is EmbeddingCache

    def test_import_llm_response_cache(self) -> None:
        from cobuilder.repomap.evaluation import LLMResponseCache as LRC
        assert LRC is LLMResponseCache

    def test_import_batched_function_generator(self) -> None:
        from cobuilder.repomap.evaluation import BatchedFunctionGenerator as BFG
        assert BFG is BatchedFunctionGenerator
