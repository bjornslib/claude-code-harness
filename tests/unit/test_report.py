"""Unit tests for the ReportGenerator class.

Tests cover:
- Markdown report generation with metrics vs paper targets
- Per-project results table generation
- Token usage / profiling section
- JSON report generation
- Empty results handling
- File output for both report types
- Custom paper metrics
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cobuilder.repomap.evaluation.models import (
    BenchmarkResult,
    ProfilingData,
    RepositoryResult,
    TokenStats,
)
from cobuilder.repomap.evaluation.report import PAPER_METRICS, ReportGenerator


def _make_evaluation(
    project_name: str = "test-project",
    total_tasks: int = 10,
    localized: int = 8,
    validated: int = 7,
    passed: int = 6,
    coverage: float = 0.80,
) -> RepositoryResult:
    """Create RepositoryResult with configurable values."""
    return RepositoryResult(
        project_name=project_name,
        total_tasks=total_tasks,
        localized=localized,
        validated=validated,
        passed=passed,
        coverage=coverage,
    )


def _make_profiling(
    total_tokens: int = 0,
    total_cost_usd: float = 0.0,
    total_duration_s: float = 0.0,
) -> ProfilingData:
    """Create ProfilingData with configurable values."""
    data = ProfilingData(total_duration_s=total_duration_s)
    if total_tokens > 0:
        data.stage_tokens["test"] = TokenStats(
            prompt_tokens=total_tokens // 2,
            completion_tokens=total_tokens // 2,
        )
    return data


def _make_benchmark_result(
    project: str = "test-project",
    total_tasks: int = 10,
    passed: int = 6,
    coverage: float = 0.80,
    total_tokens: int = 0,
    total_cost_usd: float = 0.0,
    total_duration_s: float = 0.0,
) -> BenchmarkResult:
    """Create a BenchmarkResult with configurable fields."""
    return BenchmarkResult(
        project=project,
        paraphrased_name=f"{project}-paraphrased",
        evaluation=_make_evaluation(
            project_name=project,
            total_tasks=total_tasks,
            passed=passed,
            coverage=coverage,
        ),
        profiling=_make_profiling(
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            total_duration_s=total_duration_s,
        ),
    )


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


class TestGenerateComparisonReport:
    """Tests for generate_comparison_report()."""

    def test_header_present(self) -> None:
        """Report should contain the title header."""
        gen = ReportGenerator()
        report = gen.generate_comparison_report([_make_benchmark_result()])
        assert "# ZeroRepo Benchmark Evaluation Report" in report

    def test_summary_section(self) -> None:
        """Report should include summary with project count and pass rate."""
        gen = ReportGenerator()
        result = _make_benchmark_result(total_tasks=10, passed=7)
        report = gen.generate_comparison_report([result])
        assert "Projects evaluated" in report
        assert "Total tasks" in report
        assert "Tasks passed" in report

    def test_metrics_vs_paper_table(self) -> None:
        """Report should include metrics comparison table."""
        gen = ReportGenerator()
        report = gen.generate_comparison_report([_make_benchmark_result()])
        assert "Metrics vs Paper" in report
        assert "Coverage" in report
        assert "Pass Rate" in report
        assert "Voting Rate" in report

    def test_per_project_table(self) -> None:
        """Report should include per-project results table."""
        gen = ReportGenerator()
        results = [
            _make_benchmark_result(project="alpha"),
            _make_benchmark_result(project="beta"),
        ]
        report = gen.generate_comparison_report(results)
        assert "Per-Project Results" in report
        assert "alpha" in report
        assert "beta" in report

    def test_empty_results(self) -> None:
        """Empty results should still generate a valid report."""
        gen = ReportGenerator()
        report = gen.generate_comparison_report([])
        assert "# ZeroRepo Benchmark Evaluation Report" in report
        assert "Metrics vs Paper" in report

    def test_profiling_section_when_tokens(self) -> None:
        """Report should include token usage section when profiling data exists."""
        gen = ReportGenerator()
        result = _make_benchmark_result(total_tokens=10000, total_duration_s=60.0)
        report = gen.generate_comparison_report([result])
        assert "Token Usage" in report

    def test_no_profiling_section_when_no_tokens(self) -> None:
        """Report should NOT include token section when no tokens recorded."""
        gen = ReportGenerator()
        result = _make_benchmark_result(total_tokens=0)
        report = gen.generate_comparison_report([result])
        assert "Token Usage" not in report

    def test_writes_to_file(self, tmp_path: Path) -> None:
        """Report should be written to file when output_path provided."""
        gen = ReportGenerator()
        output = tmp_path / "report.md"
        gen.generate_comparison_report([_make_benchmark_result()], output_path=output)
        assert output.exists()
        content = output.read_text()
        assert "ZeroRepo" in content

    def test_custom_paper_metrics(self) -> None:
        """Custom paper metrics should be used in comparison."""
        custom = {"coverage": 0.90, "pass_rate": 0.80, "voting_rate": 0.85}
        gen = ReportGenerator(paper_metrics=custom)
        report = gen.generate_comparison_report([_make_benchmark_result()])
        assert "90.0%" in report  # Paper coverage should show 90%

    def test_delta_signs(self) -> None:
        """Delta should show + for positive and no + for negative."""
        gen = ReportGenerator(paper_metrics={"coverage": 0.50, "pass_rate": 0.99, "voting_rate": 0.50})
        result = _make_benchmark_result(coverage=0.80, passed=6)
        report = gen.generate_comparison_report([result])
        # Coverage 80% vs 50% = +30% should have +
        assert "+30.0%" in report


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


class TestGenerateJsonReport:
    """Tests for generate_json_report()."""

    def test_structure(self) -> None:
        """JSON report should have expected top-level keys."""
        gen = ReportGenerator()
        report = gen.generate_json_report([_make_benchmark_result()])
        assert "generated_at" in report
        assert "num_projects" in report
        assert "projects" in report
        assert "aggregate" in report

    def test_project_data(self) -> None:
        """Project entries should include evaluation metrics."""
        gen = ReportGenerator()
        result = _make_benchmark_result(project="test-proj", total_tasks=10, passed=7)
        report = gen.generate_json_report([result])

        assert len(report["projects"]) == 1
        proj = report["projects"][0]
        assert proj["project"] == "test-proj"
        assert proj["total_tasks"] == 10
        assert proj["passed"] == 7

    def test_aggregate_metrics(self) -> None:
        """Aggregate should compute totals across projects."""
        gen = ReportGenerator()
        results = [
            _make_benchmark_result(total_tasks=10, passed=7, coverage=0.80),
            _make_benchmark_result(total_tasks=20, passed=15, coverage=0.90),
        ]
        report = gen.generate_json_report(results)
        agg = report["aggregate"]
        assert agg["total_tasks"] == 30
        assert pytest.approx(agg["overall_pass_rate"], rel=0.01) == 22 / 30

    def test_empty_results(self) -> None:
        """Empty results should return valid structure."""
        gen = ReportGenerator()
        report = gen.generate_json_report([])
        assert report["num_projects"] == 0
        assert report["projects"] == []
        assert report["aggregate"] == {}

    def test_writes_to_file(self, tmp_path: Path) -> None:
        """JSON report should be written to file when output_path provided."""
        gen = ReportGenerator()
        output = tmp_path / "report.json"
        gen.generate_json_report([_make_benchmark_result()], output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert "generated_at" in data

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Should create parent directories if they don't exist."""
        gen = ReportGenerator()
        output = tmp_path / "nested" / "dir" / "report.json"
        gen.generate_json_report([_make_benchmark_result()], output_path=output)
        assert output.exists()


# ---------------------------------------------------------------------------
# Paper metrics defaults
# ---------------------------------------------------------------------------


class TestPaperMetrics:
    """Tests for paper metrics constants."""

    def test_default_paper_metrics(self) -> None:
        """Default paper metrics should match expected values."""
        assert PAPER_METRICS["coverage"] == 0.815
        assert PAPER_METRICS["pass_rate"] == 0.697
        assert PAPER_METRICS["voting_rate"] == 0.750

    def test_generator_uses_defaults(self) -> None:
        """Generator without custom metrics should use defaults."""
        gen = ReportGenerator()
        assert gen.paper_metrics == PAPER_METRICS
