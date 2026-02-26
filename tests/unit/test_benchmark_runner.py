"""Tests for the BenchmarkRunner and full benchmark execution.

Validates the end-to-end benchmark runner including:
- Single project evaluation
- Multi-project batch evaluation
- Result serialisation (JSON export)
- Task loading from harvested JSON files
- Report generation
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from cobuilder.repomap.evaluation.benchmark_runner import (
    BenchmarkRunner,
    ProjectConfig,
    RunnerConfig,
    RunSummary,
)
from cobuilder.repomap.evaluation.models import (
    BenchmarkResult,
    BenchmarkTask,
    CodeStats,
    DifficultyLevel,
    ExecutionResult,
    ProfilingData,
    RepositoryResult,
    TaskResult,
)

# Also test the existing scripts module
try:
    from scripts.benchmark.run_full_benchmark import (
        load_project_tasks,
        build_project_configs,
        generate_report,
    )
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from benchmark.run_full_benchmark import (
        load_project_tasks,
        build_project_configs,
        generate_report,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    id: str = "proj-cat-sub-001",
    project: str = "proj",
    category: str = "cat",
    description: str = "A test",
    test_code: str = "def test_x():\n    assert True",
    loc: int = 20,
) -> BenchmarkTask:
    return BenchmarkTask(
        id=id,
        project=project,
        category=category,
        subcategory="sub",
        description=description,
        test_code=test_code,
        loc=loc,
        difficulty=DifficultyLevel.MEDIUM,
    )


def _make_repo_result(
    project: str = "proj",
    total: int = 10,
    localized: int = 8,
    validated: int = 6,
    passed: int = 4,
) -> RepositoryResult:
    return RepositoryResult(
        project_name=project,
        total_tasks=total,
        localized=localized,
        validated=validated,
        passed=passed,
    )


class FakeEvalPipeline:
    """Fake evaluation pipeline for testing."""

    def __init__(
        self,
        result: RepositoryResult | None = None,
        delay: float = 0.0,
    ) -> None:
        self._result = result or _make_repo_result()
        self._delay = delay
        self.call_count = 0

    def evaluate_repository(
        self,
        tasks: list[BenchmarkTask],
        repo_path: str,
    ) -> RepositoryResult:
        self.call_count += 1
        if self._delay:
            time.sleep(self._delay)
        # Return result with correct task count
        return RepositoryResult(
            project_name=self._result.project_name,
            total_tasks=len(tasks),
            localized=min(self._result.localized, len(tasks)),
            validated=min(self._result.validated, len(tasks)),
            passed=min(self._result.passed, len(tasks)),
        )


class FakeMetrics:
    """Fake metrics calculator for testing."""

    def calculate_code_stats(self, repo_path: str | Path) -> CodeStats:
        return CodeStats(files=5, loc=200, estimated_tokens=800)

    def calculate_coverage(
        self,
        tasks: list[BenchmarkTask],
        results: list[TaskResult],
    ) -> float:
        return 0.75

    def calculate_pass_rate(self, results: list[TaskResult]) -> float:
        return 0.5


# ---------------------------------------------------------------------------
# BenchmarkRunner tests
# ---------------------------------------------------------------------------


class TestBenchmarkRunner:
    """Tests for the BenchmarkRunner class."""

    def test_run_project_basic(self, tmp_path: Path) -> None:
        """Run a single project evaluation."""
        pipeline = FakeEvalPipeline(result=_make_repo_result("sklearn"))
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task(id=f"t{i}", project="sklearn") for i in range(5)]

        result = runner.run_project("sklearn", tasks, tmp_path)

        assert result.project == "sklearn"
        assert result.evaluation.total_tasks == 5
        assert pipeline.call_count == 1

    def test_run_project_with_paraphrased_name(self, tmp_path: Path) -> None:
        """Paraphrased name is stored in result."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task()]

        result = runner.run_project("sklearn", tasks, tmp_path, paraphrased_name="ml_lib")

        assert result.paraphrased_name == "ml_lib"

    def test_run_project_profiling_data(self, tmp_path: Path) -> None:
        """Profiling data includes evaluation timing."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task()]

        result = runner.run_project("test", tasks, tmp_path)

        assert result.profiling.total_duration_s >= 0
        assert "evaluation" in result.profiling.stage_timings

    def test_run_project_with_metrics(self, tmp_path: Path) -> None:
        """Metrics calculator is called when provided."""
        pipeline = FakeEvalPipeline()
        metrics = FakeMetrics()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline, metrics_calculator=metrics)
        tasks = [_make_task()]

        # Create a dummy file so repo_path exists
        (tmp_path / "dummy.py").write_text("x = 1")

        result = runner.run_project("test", tasks, tmp_path)
        assert result.evaluation.total_tasks == 1

    def test_run_project_records_timestamp(self, tmp_path: Path) -> None:
        """Result includes a timestamp."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task()]

        before = datetime.now()
        result = runner.run_project("test", tasks, tmp_path)
        after = datetime.now()

        assert before <= result.timestamp <= after

    def test_run_project_stores_repo_path(self, tmp_path: Path) -> None:
        """Result includes the repo path."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task()]

        result = runner.run_project("test", tasks, tmp_path)
        assert str(tmp_path) in result.repo_path


# ---------------------------------------------------------------------------
# Batch evaluation tests
# ---------------------------------------------------------------------------


class TestBatchEvaluation:
    """Tests for multi-project batch evaluation."""

    def test_run_batch_multiple_projects(self, tmp_path: Path) -> None:
        """Evaluate multiple projects in batch."""
        pipeline = FakeEvalPipeline(result=_make_repo_result(passed=3))
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        projects = [
            ProjectConfig(
                project_name=f"proj{i}",
                repo_path=str(tmp_path),
                tasks=[_make_task(id=f"p{i}-t{j}", project=f"proj{i}") for j in range(5)],
            )
            for i in range(3)
        ]

        summary = runner.run_batch(projects)

        assert summary.total_projects == 3
        assert summary.total_tasks == 15
        assert len(summary.per_project) == 3
        assert pipeline.call_count == 3

    def test_run_batch_empty(self) -> None:
        """Empty project list produces empty summary."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        summary = runner.run_batch([])

        assert summary.total_projects == 0
        assert summary.total_tasks == 0
        assert summary.overall_pass_rate == 0.0

    def test_run_batch_aggregate_pass_rate(self, tmp_path: Path) -> None:
        """Overall pass rate is calculated correctly."""
        pipeline = FakeEvalPipeline(result=_make_repo_result(passed=2))
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        projects = [
            ProjectConfig(
                project_name="p1",
                repo_path=str(tmp_path),
                tasks=[_make_task(id=f"t{i}") for i in range(10)],
            )
        ]

        summary = runner.run_batch(projects)
        # 2 passed out of 10 tasks
        assert summary.overall_pass_rate == pytest.approx(0.2)

    def test_run_batch_handles_error(self, tmp_path: Path) -> None:
        """Batch continues if one project fails."""

        class FailingPipeline:
            def __init__(self):
                self.calls = 0

            def evaluate_repository(self, tasks, repo_path):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("Simulated failure")
                return _make_repo_result("p2", total=len(tasks), passed=1)

        pipeline = FailingPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        projects = [
            ProjectConfig(
                project_name="fail",
                repo_path=str(tmp_path),
                tasks=[_make_task(id="f1")],
            ),
            ProjectConfig(
                project_name="pass",
                repo_path=str(tmp_path),
                tasks=[_make_task(id="p1")],
            ),
        ]

        summary = runner.run_batch(projects)
        # First project failed, second succeeded
        assert summary.total_projects == 1
        assert "pass" in summary.per_project

    def test_run_batch_duration_tracked(self, tmp_path: Path) -> None:
        """Batch records total duration."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        projects = [
            ProjectConfig(
                project_name="p1",
                repo_path=str(tmp_path),
                tasks=[_make_task()],
            )
        ]

        summary = runner.run_batch(projects)
        assert summary.duration_s >= 0


# ---------------------------------------------------------------------------
# Serialisation tests
# ---------------------------------------------------------------------------


class TestResultSerialisation:
    """Tests for result JSON serialisation."""

    def test_save_result_creates_file(self, tmp_path: Path) -> None:
        """save_result writes a JSON file."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task()]

        result = runner.run_project("test", tasks, tmp_path)
        output_dir = tmp_path / "output"
        path = runner.save_result(result, output_dir)

        assert path.exists()
        assert path.name == "test-benchmark-result.json"

    def test_save_result_valid_json(self, tmp_path: Path) -> None:
        """Saved result is valid parseable JSON."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)
        tasks = [_make_task()]

        result = runner.run_project("test", tasks, tmp_path)
        output_dir = tmp_path / "output"
        path = runner.save_result(result, output_dir)

        data = json.loads(path.read_text())
        assert data["project"] == "test"
        assert "evaluation" in data
        assert "profiling" in data

    def test_save_summary_creates_file(self, tmp_path: Path) -> None:
        """save_summary writes a summary JSON file."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        summary = RunSummary(
            total_projects=2,
            total_tasks=20,
            total_passed=10,
            overall_pass_rate=0.5,
        )
        output_dir = tmp_path / "output"
        path = runner.save_summary(summary, output_dir)

        assert path.exists()
        assert path.name == "benchmark-summary.json"

    def test_save_summary_valid_json(self, tmp_path: Path) -> None:
        """Summary JSON has correct structure."""
        pipeline = FakeEvalPipeline()
        runner = BenchmarkRunner(evaluation_pipeline=pipeline)

        summary = RunSummary(
            total_projects=1,
            total_tasks=10,
            total_passed=5,
            overall_pass_rate=0.5,
        )
        output_dir = tmp_path / "output"
        path = runner.save_summary(summary, output_dir)

        data = json.loads(path.read_text())
        assert data["total_projects"] == 1
        assert data["total_tasks"] == 10
        assert data["overall_pass_rate"] == 0.5

    def test_save_results_creates_all_files(self, tmp_path: Path) -> None:
        """save_results creates per-project + summary files."""
        pipeline = FakeEvalPipeline()
        config = RunnerConfig(save_individual=True, save_aggregate=True)
        runner = BenchmarkRunner(evaluation_pipeline=pipeline, config=config)
        tasks = [_make_task()]

        result = runner.run_project("proj1", tasks, tmp_path)
        summary = RunSummary(
            total_projects=1,
            total_tasks=1,
            total_passed=0,
            per_project={"proj1": result},
        )

        output_dir = tmp_path / "output"
        paths = runner.save_results(summary, output_dir)

        assert len(paths) == 2  # 1 project + 1 summary
        names = {p.name for p in paths}
        assert "proj1-benchmark-result.json" in names
        assert "benchmark-summary.json" in names


# ---------------------------------------------------------------------------
# Task loading tests
# ---------------------------------------------------------------------------


class TestTaskLoading:
    """Tests for loading tasks from JSON files."""

    def test_load_project_tasks(self, tmp_path: Path) -> None:
        """Load tasks from a valid JSON file."""
        tasks_data = {
            "project": "test",
            "summary": {"harvested": 5, "filtered": 3, "sampled": 3},
            "tasks": [
                {
                    "id": f"test-cat-sub-{i:03d}",
                    "project": "test",
                    "category": "cat",
                    "subcategory": "sub",
                    "description": f"Test {i}",
                    "test_code": f"def test_{i}():\n    assert True",
                    "loc": 20,
                }
                for i in range(3)
            ],
        }
        tasks_file = tmp_path / "test-tasks.json"
        tasks_file.write_text(json.dumps(tasks_data))

        tasks = load_project_tasks(tmp_path, "test")
        assert len(tasks) == 3
        assert all(isinstance(t, BenchmarkTask) for t in tasks)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns empty list."""
        tasks = load_project_tasks(tmp_path, "nonexistent")
        assert tasks == []

    def test_load_invalid_task_skipped(self, tmp_path: Path) -> None:
        """Invalid tasks are skipped with warning."""
        tasks_data = {
            "tasks": [
                {"id": "valid-1", "project": "p", "category": "c", "description": "d", "test_code": "code"},
                {"bad_field": "invalid"},  # Missing required fields
            ],
        }
        tasks_file = tmp_path / "mixed-tasks.json"
        tasks_file.write_text(json.dumps(tasks_data))

        tasks = load_project_tasks(tmp_path, "mixed")
        assert len(tasks) == 1


# ---------------------------------------------------------------------------
# build_project_configs tests
# ---------------------------------------------------------------------------


class TestBuildProjectConfigs:
    """Tests for building project configurations."""

    def test_build_configs(self, tmp_path: Path) -> None:
        """Build configs from tasks directory."""
        # Create tasks file
        tasks_data = {
            "tasks": [
                {"id": "p1-1", "project": "p1", "category": "c", "description": "d", "test_code": "code"},
            ],
        }
        (tmp_path / "tasks").mkdir()
        (tmp_path / "tasks" / "p1-tasks.json").write_text(json.dumps(tasks_data))
        (tmp_path / "repos" / "p1").mkdir(parents=True)

        configs = build_project_configs(
            ["p1"],
            tmp_path / "tasks",
            tmp_path / "repos",
        )

        assert len(configs) == 1
        assert configs[0]["project_name"] == "p1"
        assert len(configs[0]["tasks"]) == 1

    def test_build_configs_missing_tasks(self, tmp_path: Path) -> None:
        """Projects with no tasks are skipped."""
        configs = build_project_configs(
            ["missing"],
            tmp_path,
            tmp_path,
        )
        assert len(configs) == 0


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------


class TestReportGeneration:
    """Tests for Markdown report generation."""

    def test_generate_report_basic(self) -> None:
        """Generate a basic report from summary."""
        result = BenchmarkResult(
            project="sklearn",
            evaluation=_make_repo_result("sklearn", total=100, passed=75),
            profiling=ProfilingData(total_duration_s=60.0),
        )
        summary = RunSummary(
            total_projects=1,
            total_tasks=100,
            total_passed=75,
            overall_pass_rate=0.75,
            per_project={"sklearn": result},
            duration_s=60.0,
        )

        report = generate_report(summary)

        assert "# RepoCraft Benchmark Report" in report
        assert "sklearn" in report
        assert "75.0%" in report
        assert "100" in report

    def test_generate_report_multiple_projects(self) -> None:
        """Report includes all projects."""
        results = {}
        for name in ("sklearn", "pandas"):
            results[name] = BenchmarkResult(
                project=name,
                evaluation=_make_repo_result(name, total=50, passed=25),
                profiling=ProfilingData(total_duration_s=30.0),
            )

        summary = RunSummary(
            total_projects=2,
            total_tasks=100,
            total_passed=50,
            overall_pass_rate=0.5,
            per_project=results,
            duration_s=60.0,
        )

        report = generate_report(summary)
        assert "sklearn" in report
        assert "pandas" in report
        assert "50.0%" in report


# ---------------------------------------------------------------------------
# RunnerConfig tests
# ---------------------------------------------------------------------------


class TestRunnerConfig:
    """Tests for RunnerConfig defaults."""

    def test_default_config(self) -> None:
        cfg = RunnerConfig()
        assert cfg.output_dir == "./benchmark-results"
        assert cfg.save_individual is True
        assert cfg.save_aggregate is True

    def test_custom_config(self) -> None:
        cfg = RunnerConfig(output_dir="/tmp/out", save_individual=False)
        assert cfg.output_dir == "/tmp/out"
        assert cfg.save_individual is False


# ---------------------------------------------------------------------------
# ProjectConfig tests
# ---------------------------------------------------------------------------


class TestProjectConfig:
    """Tests for ProjectConfig."""

    def test_defaults(self) -> None:
        cfg = ProjectConfig(project_name="test")
        assert cfg.project_name == "test"
        assert cfg.paraphrased_name == ""
        assert cfg.tasks == []
        assert cfg.import_mapping == {}

    def test_with_tasks(self) -> None:
        tasks = [_make_task()]
        cfg = ProjectConfig(project_name="test", tasks=tasks)
        assert len(cfg.tasks) == 1


# ---------------------------------------------------------------------------
# RunSummary tests
# ---------------------------------------------------------------------------


class TestRunSummary:
    """Tests for RunSummary dataclass."""

    def test_defaults(self) -> None:
        s = RunSummary()
        assert s.total_projects == 0
        assert s.total_tasks == 0
        assert s.overall_pass_rate == 0.0
        assert s.per_project == {}

    def test_with_values(self) -> None:
        s = RunSummary(total_projects=3, total_tasks=300, total_passed=150, overall_pass_rate=0.5)
        assert s.total_projects == 3
        assert s.overall_pass_rate == 0.5
