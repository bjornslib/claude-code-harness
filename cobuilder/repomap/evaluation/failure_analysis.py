"""Failure analysis for the evaluation pipeline.

Categorizes failures into PLANNING/GENERATION/LOCALIZATION/VALIDATION/EXECUTION
and generates actionable recommendations based on failure patterns.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from cobuilder.repomap.evaluation.models import (
    ABTestResult,
    BenchmarkTask,
    FailureCategory,
    FailureReport,
    StageFailed,
    TaskResult,
)

logger = logging.getLogger(__name__)

# Threshold-based recommendation rules
RECOMMENDATION_RULES = {
    FailureCategory.PLANNING: (
        0.20,
        "High planning failure rate (>{threshold:.0%}): Improve task descriptions and planning prompts.",
    ),
    FailureCategory.GENERATION: (
        0.15,
        "Significant generation failures (>{threshold:.0%}): Review code generation templates.",
    ),
    FailureCategory.LOCALIZATION: (
        0.25,
        "Many localization failures (>{threshold:.0%}): Improve embedding model or add re-ranking.",
    ),
    FailureCategory.VALIDATION: (
        0.20,
        "High validation rejection rate (>{threshold:.0%}): Tune validation prompts or voting threshold.",
    ),
    FailureCategory.EXECUTION: (
        0.15,
        "Frequent execution failures (>{threshold:.0%}): Fix import mapping or sandbox configuration.",
    ),
}


class FailureAnalyzer:
    """Categorizes and analyzes evaluation failures."""

    def __init__(self, max_samples_per_category: int = 10):
        self.max_samples = max_samples_per_category

    def categorize_failure(self, result: TaskResult) -> FailureCategory:
        """Categorize a failed task result into a failure category."""
        if result.passed:
            return FailureCategory.UNKNOWN  # Not actually a failure

        # Use stage_failed if available
        if result.stage_failed:
            stage_map = {
                StageFailed.LOCALIZATION: FailureCategory.LOCALIZATION,
                StageFailed.VALIDATION: FailureCategory.VALIDATION,
                StageFailed.EXECUTION: FailureCategory.EXECUTION,
            }
            return stage_map.get(result.stage_failed, FailureCategory.UNKNOWN)

        # Heuristic: if not localized, likely planning/generation issue
        if not result.localized:
            # Check if the function exists but with different name
            if result.candidate_function and result.candidate_score > 0.3:
                return FailureCategory.LOCALIZATION
            return FailureCategory.GENERATION

        # Localized but not validated
        if not result.validated:
            return FailureCategory.VALIDATION

        # Validated but not passed
        if result.execution_error:
            error = result.execution_error.lower()
            if "import" in error or "module" in error:
                return FailureCategory.EXECUTION
            if "timeout" in error:
                return FailureCategory.EXECUTION
            return FailureCategory.EXECUTION

        return FailureCategory.UNKNOWN

    def analyze_failures(
        self,
        results: list[TaskResult],
        tasks: list[BenchmarkTask] | None = None,
    ) -> FailureReport:
        """Analyze all failed results and generate report with recommendations."""
        failures = [r for r in results if not r.passed]

        if not failures:
            return FailureReport(
                total_failures=0,
                recommendations=["All tasks passed! No failures to analyze."],
            )

        # Categorize
        category_counter: Counter[str] = Counter()
        samples: dict[str, list[TaskResult]] = {}

        for result in failures:
            category = self.categorize_failure(result)
            cat_name = category.value
            category_counter[cat_name] += 1

            if cat_name not in samples:
                samples[cat_name] = []
            if len(samples[cat_name]) < self.max_samples:
                samples[cat_name].append(result)

        # Generate recommendations
        total = len(results)
        recommendations = self._generate_recommendations(category_counter, total)

        return FailureReport(
            total_failures=len(failures),
            category_counts=dict(category_counter),
            samples=samples,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        counts: Counter[str],
        total: int,
    ) -> list[str]:
        """Generate recommendations based on failure category thresholds."""
        recommendations = []

        for category, (threshold, template) in RECOMMENDATION_RULES.items():
            count = counts.get(category.value, 0)
            rate = count / total if total > 0 else 0.0

            if rate > threshold:
                recommendations.append(
                    template.format(threshold=threshold)
                    + f" ({count}/{total} = {rate:.1%})"
                )

        if not recommendations:
            recommendations.append(
                f"Failure distribution is within acceptable thresholds. "
                f"Total failures: {sum(counts.values())}/{total}"
            )

        return recommendations

    def function_exists_different_name(
        self,
        result: TaskResult,
        all_functions: list[str],
    ) -> str | None:
        """Check if a function exists under a different name (fuzzy match)."""
        if not result.candidate_function:
            return None

        target = result.candidate_function.lower().replace("_", "")
        for func_name in all_functions:
            normalized = func_name.lower().replace("_", "")
            if target in normalized or normalized in target:
                if func_name != result.candidate_function:
                    return func_name

        return None


class PromptABTest:
    """Framework for A/B testing prompt variants."""

    def __init__(
        self,
        baseline_prompt: str,
        variant_prompt: str,
    ):
        self.baseline_prompt = baseline_prompt
        self.variant_prompt = variant_prompt

    def run_test(
        self,
        baseline_results: list[bool],
        variant_results: list[bool],
    ) -> ABTestResult:
        """Run A/B test analysis on pre-collected results."""
        n_baseline = len(baseline_results)
        n_variant = len(variant_results)

        baseline_rate = sum(baseline_results) / n_baseline if n_baseline else 0.0
        variant_rate = sum(variant_results) / n_variant if n_variant else 0.0
        delta = variant_rate - baseline_rate

        # Chi-squared test approximation
        p_value = self._chi_squared_p_value(
            sum(baseline_results),
            n_baseline,
            sum(variant_results),
            n_variant,
        )

        significant = p_value < 0.05
        sample_size = n_baseline + n_variant

        if significant and delta > 0:
            recommendation = "USE VARIANT"
        elif significant and delta < 0:
            recommendation = "KEEP BASELINE"
        else:
            recommendation = "NO SIGNIFICANT DIFFERENCE"

        return ABTestResult(
            baseline_pass_rate=baseline_rate,
            variant_pass_rate=variant_rate,
            delta=delta,
            p_value=p_value,
            significant=significant,
            sample_size=sample_size,
            recommendation=recommendation,
        )

    @staticmethod
    def _chi_squared_p_value(
        success_a: int,
        n_a: int,
        success_b: int,
        n_b: int,
    ) -> float:
        """Simplified chi-squared test p-value for two proportions."""
        if n_a == 0 or n_b == 0:
            return 1.0

        p_a = success_a / n_a
        p_b = success_b / n_b
        p_pooled = (success_a + success_b) / (n_a + n_b)

        if p_pooled == 0 or p_pooled == 1:
            return 1.0

        # Z-test statistic
        se = (p_pooled * (1 - p_pooled) * (1 / n_a + 1 / n_b)) ** 0.5
        if se == 0:
            return 1.0

        z = abs(p_a - p_b) / se

        # Approximate p-value using normal distribution approximation
        # For |z| > 3.3, p < 0.001
        # For |z| > 2.58, p < 0.01
        # For |z| > 1.96, p < 0.05
        if z > 3.3:
            return 0.001
        elif z > 2.58:
            return 0.01
        elif z > 1.96:
            return 0.05
        elif z > 1.645:
            return 0.10
        else:
            # Very rough approximation
            return min(1.0, 2 * (1 - 0.5 * (1 + z / (z**2 + 1) ** 0.5)))
