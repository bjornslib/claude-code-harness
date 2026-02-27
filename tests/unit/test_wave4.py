"""Unit tests for Wave 4: ProfilingCollector, ReportGenerator, BenchmarkRunner.

All external dependencies are mocked.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cobuilder.repomap.evaluation.models import (
    BenchmarkResult,
    BenchmarkTask,
    ProfilingData,
    RepositoryResult,
    TokenStats,
)
from cobuilder.repomap.evaluation.profiling import ProfilingCollector
from cobuilder.repomap.evaluation.report import PAPER_METRICS, ReportGenerator
from scripts.benchmark.run_full_benchmark import (
    BenchmarkConfig,
    BenchmarkRunner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str = "task-001",
    project: str = "test-project",
    category: str = "ml.linear",
    description: str = "Implement ridge regression",
    test_code: str = "def test_ridge(): assert True",
) -> BenchmarkTask:
    return BenchmarkTask(
        id=task_id,
        project=project,
        category=category,
        description=description,
        test_code=test_code,
    )


def _make_benchmark_result(
    project: str = "test-project",
    total_tasks: int = 10,
    localized: int = 8,
    validated: int = 7,
    passed: int = 6,
    coverage: float = 0.8,
    paraphrased_name: str = "test_proj",
    profiling: ProfilingData | None = None,
) -> BenchmarkResult:
    return BenchmarkResult(
        project=project,
        paraphrased_name=paraphrased_name,
        evaluation=RepositoryResult(
            project_name=project,
            total_tasks=total_tasks,
            localized=localized,
            validated=validated,
            passed=passed,
            coverage=coverage,
        ),
        profiling=profiling or ProfilingData(),
    )


# ===========================================================================
# TestProfilingCollector
# ===========================================================================


class TestProfilingCollector:
    """Tests for ProfilingCollector."""

    def test_record_llm_call_new_stage(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("validation", prompt_tokens=100, completion_tokens=50)
        data = pc.get_profiling_data()
        assert "validation" in data.stage_tokens
        assert data.stage_tokens["validation"].prompt_tokens == 100
        assert data.stage_tokens["validation"].completion_tokens == 50
        assert data.stage_tokens["validation"].total_calls == 1

    def test_record_llm_call_accumulates(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("loc", prompt_tokens=100, completion_tokens=50)
        pc.record_llm_call("loc", prompt_tokens=200, completion_tokens=75)
        data = pc.get_profiling_data()
        stats = data.stage_tokens["loc"]
        assert stats.prompt_tokens == 300
        assert stats.completion_tokens == 125
        assert stats.total_calls == 2

    def test_time_stage_context_manager(self) -> None:
        pc = ProfilingCollector()
        with pc.time_stage("build"):
            time.sleep(0.01)
        data = pc.get_profiling_data()
        assert "build" in data.stage_timings
        assert data.stage_timings["build"] >= 0.01
        assert data.total_duration_s >= 0.01

    def test_time_stage_accumulates(self) -> None:
        pc = ProfilingCollector()
        with pc.time_stage("build"):
            time.sleep(0.01)
        with pc.time_stage("build"):
            time.sleep(0.01)
        data = pc.get_profiling_data()
        assert data.stage_timings["build"] >= 0.02

    def test_start_stop_timer(self) -> None:
        pc = ProfilingCollector()
        pc.start_timer("gen")
        time.sleep(0.01)
        elapsed = pc.stop_timer("gen")
        assert elapsed >= 0.01
        data = pc.get_profiling_data()
        assert "gen" in data.stage_timings
        assert data.stage_timings["gen"] >= 0.01

    def test_stop_nonexistent_timer(self) -> None:
        pc = ProfilingCollector()
        elapsed = pc.stop_timer("nonexistent")
        assert elapsed == 0.0

    def test_get_stage_summary_existing(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("val", prompt_tokens=100, completion_tokens=50)
        with pc.time_stage("val"):
            pass
        summary = pc.get_stage_summary("val")
        assert summary["stage"] == "val"
        assert summary["prompt_tokens"] == 100
        assert summary["completion_tokens"] == 50
        assert summary["total_tokens"] == 150
        assert summary["total_calls"] == 1
        assert summary["duration_s"] >= 0.0

    def test_get_stage_summary_nonexistent(self) -> None:
        pc = ProfilingCollector()
        summary = pc.get_stage_summary("missing")
        assert summary["stage"] == "missing"
        assert summary["prompt_tokens"] == 0
        assert summary["total_calls"] == 0
        assert summary["duration_s"] == 0.0

    def test_get_profiling_data_returns_copy(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("a", prompt_tokens=10, completion_tokens=5)
        data1 = pc.get_profiling_data()
        data2 = pc.get_profiling_data()
        assert data1 is not data2
        # Mutating the copy should not affect the original
        data1.stage_tokens["a"].prompt_tokens = 999
        data3 = pc.get_profiling_data()
        assert data3.stage_tokens["a"].prompt_tokens == 10

    def test_reset_clears_data(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("x", prompt_tokens=50, completion_tokens=25)
        pc.start_timer("y")
        pc.reset()
        data = pc.get_profiling_data()
        assert len(data.stage_tokens) == 0
        assert len(data.stage_timings) == 0
        assert data.total_duration_s == 0.0

    def test_total_tokens_aggregation(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("a", prompt_tokens=100, completion_tokens=50)
        pc.record_llm_call("b", prompt_tokens=200, completion_tokens=100)
        data = pc.get_profiling_data()
        assert data.total_tokens == 450  # 150 + 300

    def test_total_cost_calculation(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("a", prompt_tokens=500_000, completion_tokens=500_000)
        data = pc.get_profiling_data()
        # 1M tokens at $10/1M = $10
        assert data.total_cost_usd == pytest.approx(10.0)

    def test_multiple_stages_independent(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("loc", prompt_tokens=100, completion_tokens=50)
        pc.record_llm_call("val", prompt_tokens=200, completion_tokens=75)
        pc.record_llm_call("exec", prompt_tokens=50, completion_tokens=25)
        data = pc.get_profiling_data()
        assert len(data.stage_tokens) == 3
        assert data.stage_tokens["loc"].total_tokens == 150
        assert data.stage_tokens["val"].total_tokens == 275
        assert data.stage_tokens["exec"].total_tokens == 75

    def test_timer_does_not_persist_after_stop(self) -> None:
        pc = ProfilingCollector()
        pc.start_timer("x")
        pc.stop_timer("x")
        # Stopping again should return 0
        assert pc.stop_timer("x") == 0.0


# ===========================================================================
# TestReportGenerator
# ===========================================================================


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def test_empty_results_report(self) -> None:
        rg = ReportGenerator()
        report = rg.generate_comparison_report([])
        assert "# ZeroRepo Benchmark Evaluation Report" in report
        assert "## Metrics vs Paper" in report

    def test_single_project_report(self) -> None:
        result = _make_benchmark_result(project="scikit-learn", total_tasks=10, passed=7)
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        assert "scikit-learn" in report
        assert "## Per-Project Results" in report

    def test_multi_project_report(self) -> None:
        r1 = _make_benchmark_result(project="sklearn", total_tasks=10, passed=7)
        r2 = _make_benchmark_result(project="pandas", total_tasks=20, passed=15)
        rg = ReportGenerator()
        report = rg.generate_comparison_report([r1, r2])
        assert "sklearn" in report
        assert "pandas" in report
        assert "**Projects evaluated**: 2" in report
        assert "**Total tasks**: 30" in report

    def test_comparison_table_has_all_metrics(self) -> None:
        result = _make_benchmark_result()
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        assert "Coverage" in report
        assert "Pass Rate" in report
        assert "Voting Rate" in report

    def test_delta_positive(self) -> None:
        # 100% coverage vs paper 81.5% => positive delta
        result = _make_benchmark_result(coverage=1.0, total_tasks=10, passed=10, validated=10)
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        assert "+" in report  # At least one positive delta

    def test_delta_negative(self) -> None:
        # 0% everything => negative delta
        result = _make_benchmark_result(
            coverage=0.0, total_tasks=10, passed=0, validated=0
        )
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        # Should contain negative deltas (formatted as e.g. "-81.5%")
        assert "-" in report

    def test_per_project_table_rows(self) -> None:
        r1 = _make_benchmark_result(project="A", total_tasks=5, passed=3)
        r2 = _make_benchmark_result(project="B", total_tasks=10, passed=8)
        rg = ReportGenerator()
        report = rg.generate_comparison_report([r1, r2])
        # Should have header + 2 data rows
        assert "| A |" in report
        assert "| B |" in report

    def test_profiling_section_included(self) -> None:
        profiling = ProfilingData(
            stage_tokens={"val": TokenStats(prompt_tokens=1000, completion_tokens=500)},
            total_duration_s=5.0,
        )
        result = _make_benchmark_result(profiling=profiling)
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        assert "## Token Usage" in report
        assert "1,500" in report  # total tokens formatted

    def test_profiling_section_excluded_when_zero(self) -> None:
        result = _make_benchmark_result()
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        assert "## Token Usage" not in report

    def test_generate_json_report_structure(self) -> None:
        result = _make_benchmark_result(project="sklearn", total_tasks=10, passed=7)
        rg = ReportGenerator()
        jr = rg.generate_json_report([result])
        assert jr["num_projects"] == 1
        assert len(jr["projects"]) == 1
        assert jr["projects"][0]["project"] == "sklearn"
        assert jr["projects"][0]["total_tasks"] == 10
        assert jr["projects"][0]["passed"] == 7
        assert "aggregate" in jr

    def test_generate_json_report_empty(self) -> None:
        rg = ReportGenerator()
        jr = rg.generate_json_report([])
        assert jr["num_projects"] == 0
        assert jr["projects"] == []
        assert jr["aggregate"] == {}

    def test_generate_json_report_aggregate(self) -> None:
        r1 = _make_benchmark_result(
            project="A", total_tasks=10, passed=7, coverage=0.8, validated=8
        )
        r2 = _make_benchmark_result(
            project="B", total_tasks=20, passed=15, coverage=0.9, validated=18
        )
        rg = ReportGenerator()
        jr = rg.generate_json_report([r1, r2])
        agg = jr["aggregate"]
        assert agg["total_tasks"] == 30
        assert agg["avg_coverage"] == pytest.approx(0.85)
        assert agg["overall_pass_rate"] == pytest.approx(22 / 30)
        assert agg["overall_voting_rate"] == pytest.approx(26 / 30)

    def test_save_markdown_to_file(self, tmp_path: Path) -> None:
        result = _make_benchmark_result()
        rg = ReportGenerator()
        out = tmp_path / "reports" / "report.md"
        report = rg.generate_comparison_report([result], output_path=out)
        assert out.exists()
        assert out.read_text() == report

    def test_save_json_to_file(self, tmp_path: Path) -> None:
        result = _make_benchmark_result()
        rg = ReportGenerator()
        out = tmp_path / "reports" / "report.json"
        jr = rg.generate_json_report([result], output_path=out)
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["num_projects"] == jr["num_projects"]

    def test_custom_paper_metrics(self) -> None:
        custom = {"coverage": 0.50, "pass_rate": 0.50, "voting_rate": 0.50}
        rg = ReportGenerator(paper_metrics=custom)
        assert rg.paper_metrics == custom
        result = _make_benchmark_result(
            total_tasks=10, passed=10, validated=10, coverage=1.0
        )
        report = rg.generate_comparison_report([result])
        # Should compare against 50% paper metrics
        assert "50.0%" in report

    def test_default_paper_metrics(self) -> None:
        rg = ReportGenerator()
        assert rg.paper_metrics == PAPER_METRICS


# ===========================================================================
# TestBenchmarkRunner
# ===========================================================================


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner."""

    def test_benchmark_config_defaults(self) -> None:
        cfg = BenchmarkConfig()
        assert cfg.projects == ["scikit-learn", "pandas", "sympy"]
        assert cfg.max_tasks_per_project == 200
        assert cfg.paraphrase_names is True

    def test_paraphrase_name_known(self) -> None:
        assert BenchmarkRunner.paraphrase_name("scikit-learn") == "ml_lib"
        assert BenchmarkRunner.paraphrase_name("pandas") == "data_frames"
        assert BenchmarkRunner.paraphrase_name("sympy") == "math_engine"
        assert BenchmarkRunner.paraphrase_name("django") == "web_framework"

    def test_paraphrase_name_unknown(self) -> None:
        assert BenchmarkRunner.paraphrase_name("my-project") == "my_project"
        assert BenchmarkRunner.paraphrase_name("foo") == "foo"

    def test_load_tasks_from_json(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks_data = [
            {
                "id": "t-001",
                "project": "sklearn",
                "category": "ml.linear",
                "description": "Test ridge",
                "test_code": "def test_ridge(): pass",
            },
            {
                "id": "t-002",
                "project": "sklearn",
                "category": "ml.svm",
                "description": "Test svm",
                "test_code": "def test_svm(): pass",
            },
        ]
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(tasks_data))

        cfg = BenchmarkConfig(tasks_dir=str(tasks_dir))
        runner = BenchmarkRunner(config=cfg)
        tasks = runner.load_tasks("sklearn")
        assert len(tasks) == 2
        assert tasks[0].id == "t-001"

    def test_load_tasks_dict_format(self, tmp_path: Path) -> None:
        """Tasks file with {'tasks': [...]} wrapper."""
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        payload = {
            "tasks": [
                {
                    "id": "t-001",
                    "project": "sklearn",
                    "category": "ml",
                    "description": "desc",
                    "test_code": "def test(): pass",
                }
            ]
        }
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(payload))

        cfg = BenchmarkConfig(tasks_dir=str(tasks_dir))
        runner = BenchmarkRunner(config=cfg)
        tasks = runner.load_tasks("sklearn")
        assert len(tasks) == 1

    def test_load_tasks_missing_file(self) -> None:
        cfg = BenchmarkConfig(tasks_dir="/nonexistent/path")
        runner = BenchmarkRunner(config=cfg)
        tasks = runner.load_tasks("sklearn")
        assert tasks == []

    def test_max_tasks_limit(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks_data = [
            {
                "id": f"t-{i:03d}",
                "project": "sklearn",
                "category": "ml",
                "description": f"Task {i}",
                "test_code": f"def test_{i}(): pass",
            }
            for i in range(50)
        ]
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(tasks_data))

        cfg = BenchmarkConfig(tasks_dir=str(tasks_dir), max_tasks_per_project=10)
        runner = BenchmarkRunner(config=cfg)
        tasks = runner.load_tasks("sklearn")
        assert len(tasks) == 10

    def test_run_project_no_tasks(self) -> None:
        cfg = BenchmarkConfig(tasks_dir="/nonexistent/path")
        runner = BenchmarkRunner(config=cfg)
        result = runner.run_project("nonexistent")
        assert result.project == "nonexistent"
        assert result.evaluation.total_tasks == 0

    def test_run_project_with_mocked_pipeline(self, tmp_path: Path) -> None:
        # Setup tasks
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks_data = [
            {
                "id": "t-001",
                "project": "sklearn",
                "category": "ml",
                "description": "Test",
                "test_code": "def test(): pass",
            }
        ]
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(tasks_data))

        # Mock pipeline
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_repository.return_value = RepositoryResult(
            project_name="sklearn",
            total_tasks=1,
            localized=1,
            validated=1,
            passed=1,
            coverage=1.0,
        )

        mock_zerorepo = MagicMock()
        mock_zerorepo.generate.return_value = "/tmp/fake-repo"

        mock_profiler = MagicMock()
        mock_profiler.get_profiling_data.return_value = ProfilingData()

        cfg = BenchmarkConfig(
            projects=["sklearn"],
            tasks_dir=str(tasks_dir),
            output_dir=str(tmp_path / "results"),
        )
        runner = BenchmarkRunner(
            config=cfg,
            zerorepo_pipeline=mock_zerorepo,
            evaluation_pipeline=mock_evaluator,
            profiling_collector=mock_profiler,
        )

        result = runner.run_project("sklearn")
        assert result.project == "sklearn"
        assert result.paraphrased_name == "sklearn"  # "sklearn" not in mapping, so hyphen-replaced
        assert result.evaluation.passed == 1
        mock_zerorepo.generate.assert_called_once()
        mock_evaluator.evaluate_repository.assert_called_once()

    def test_run_project_no_zerorepo(self, tmp_path: Path) -> None:
        """Without zerorepo pipeline, evaluation is skipped."""
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks_data = [
            {
                "id": "t-001",
                "project": "sklearn",
                "category": "ml",
                "description": "Test",
                "test_code": "def test(): pass",
            }
        ]
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(tasks_data))

        cfg = BenchmarkConfig(
            tasks_dir=str(tasks_dir),
            output_dir=str(tmp_path / "results"),
        )
        runner = BenchmarkRunner(config=cfg)
        result = runner.run_project("sklearn")
        # No zerorepo, so evaluation falls back to default
        assert result.evaluation.total_tasks == 1
        assert result.evaluation.passed == 0

    def test_run_all_multiple_projects(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        for proj in ["a", "b"]:
            data = [
                {
                    "id": f"{proj}-001",
                    "project": proj,
                    "category": "cat",
                    "description": "desc",
                    "test_code": "def test(): pass",
                }
            ]
            (tasks_dir / f"{proj}-tasks.json").write_text(json.dumps(data))

        cfg = BenchmarkConfig(
            projects=["a", "b"],
            tasks_dir=str(tasks_dir),
            output_dir=str(tmp_path / "results"),
        )
        runner = BenchmarkRunner(config=cfg)
        results = runner.run_all()
        assert len(results) == 2
        assert results[0].project == "a"
        assert results[1].project == "b"

    def test_save_result(self, tmp_path: Path) -> None:
        result = _make_benchmark_result(project="sklearn")
        cfg = BenchmarkConfig(output_dir=str(tmp_path / "results"))
        runner = BenchmarkRunner(config=cfg)
        runner._save_result(result)
        out_file = tmp_path / "results" / "sklearn-result.json"
        assert out_file.exists()
        loaded = json.loads(out_file.read_text())
        assert loaded["project"] == "sklearn"

    def test_run_project_profiler_timing(self, tmp_path: Path) -> None:
        """Profiler start/stop are called for generation and evaluation."""
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks_data = [
            {
                "id": "t-001",
                "project": "sklearn",
                "category": "ml",
                "description": "Test",
                "test_code": "def test(): pass",
            }
        ]
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(tasks_data))

        mock_zerorepo = MagicMock()
        mock_zerorepo.generate.return_value = "/tmp/repo"

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_repository.return_value = RepositoryResult(
            project_name="sklearn", total_tasks=1
        )

        mock_profiler = MagicMock()
        mock_profiler.get_profiling_data.return_value = ProfilingData()

        cfg = BenchmarkConfig(
            tasks_dir=str(tasks_dir),
            output_dir=str(tmp_path / "results"),
        )
        runner = BenchmarkRunner(
            config=cfg,
            zerorepo_pipeline=mock_zerorepo,
            evaluation_pipeline=mock_evaluator,
            profiling_collector=mock_profiler,
        )
        runner.run_project("sklearn")

        # Profiler should have been called for generation and evaluation
        assert mock_profiler.start_timer.call_count == 2
        assert mock_profiler.stop_timer.call_count == 2
        mock_profiler.start_timer.assert_any_call("generation")
        mock_profiler.start_timer.assert_any_call("evaluation")

    def test_run_project_paraphrase_disabled(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        tasks_data = [
            {
                "id": "t-001",
                "project": "sklearn",
                "category": "ml",
                "description": "Test",
                "test_code": "def test(): pass",
            }
        ]
        (tasks_dir / "sklearn-tasks.json").write_text(json.dumps(tasks_data))

        cfg = BenchmarkConfig(
            tasks_dir=str(tasks_dir),
            output_dir=str(tmp_path / "results"),
            paraphrase_names=False,
        )
        runner = BenchmarkRunner(config=cfg)
        result = runner.run_project("sklearn")
        assert result.paraphrased_name == "sklearn"  # Not paraphrased


# ===========================================================================
# Integration-style tests
# ===========================================================================


class TestProfilingReportIntegration:
    """Tests combining ProfilingCollector output with ReportGenerator."""

    def test_profiling_data_in_report(self) -> None:
        pc = ProfilingCollector()
        pc.record_llm_call("validation", prompt_tokens=5000, completion_tokens=2000)
        with pc.time_stage("validation"):
            time.sleep(0.01)

        profiling = pc.get_profiling_data()
        result = _make_benchmark_result(profiling=profiling)
        rg = ReportGenerator()
        report = rg.generate_comparison_report([result])
        assert "## Token Usage" in report
        assert "7,000" in report  # 5000 + 2000

    def test_json_report_includes_profiling_metadata(self) -> None:
        result = _make_benchmark_result(
            project="sklearn",
            total_tasks=10,
            passed=7,
            validated=8,
            coverage=0.8,
        )
        rg = ReportGenerator()
        jr = rg.generate_json_report([result])
        proj = jr["projects"][0]
        assert proj["pass_rate"] == pytest.approx(0.7)
        assert proj["voting_rate"] == pytest.approx(0.8)
        assert proj["coverage"] == pytest.approx(0.8)

    def test_report_with_zero_tasks(self) -> None:
        result = _make_benchmark_result(
            total_tasks=0, passed=0, validated=0, coverage=0.0
        )
        rg = ReportGenerator()
        # Should not crash on division by zero
        report = rg.generate_comparison_report([result])
        assert "0.0%" in report

    def test_import_from_package(self) -> None:
        """Verify ProfilingCollector and ReportGenerator are importable from package."""
        from cobuilder.repomap.evaluation import ProfilingCollector as PC
        from cobuilder.repomap.evaluation import ReportGenerator as RG

        assert PC is ProfilingCollector
        assert RG is ReportGenerator
