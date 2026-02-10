"""End-to-end benchmark runner for the ZeroRepo evaluation pipeline.

Orchestrates the full flow of:
1. Loading benchmark tasks from a project
2. Running the evaluation pipeline (localization + validation + execution)
3. Collecting profiling data (timing, token usage)
4. Aggregating per-project and cross-project results
5. Generating structured reports

Usage::

    runner = BenchmarkRunner(
        evaluation_pipeline=pipeline,
        metrics_calculator=metrics,
    )
    result = runner.run_project("scikit-learn", tasks, "/path/to/generated/repo")

Or for multiple projects::

    results = runner.run_batch(project_configs)
    runner.save_results(results, output_dir)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from zerorepo.evaluation.models import (
    BenchmarkResult,
    BenchmarkTask,
    CodeStats,
    ProfilingData,
    RepositoryResult,
    TaskResult,
    TokenStats,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols for pluggable components
# ---------------------------------------------------------------------------


class EvaluationPipelineProtocol(Protocol):
    """Protocol for the evaluation pipeline."""

    def evaluate_repository(
        self,
        tasks: list[BenchmarkTask],
        repo_path: str,
    ) -> RepositoryResult: ...


class MetricsCalculatorProtocol(Protocol):
    """Protocol for metrics calculation."""

    def calculate_code_stats(self, repo_path: str | Path) -> CodeStats: ...

    def calculate_coverage(
        self,
        tasks: list[BenchmarkTask],
        results: list[TaskResult],
    ) -> float: ...

    def calculate_pass_rate(self, results: list[TaskResult]) -> float: ...


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    """Configuration for a single project benchmark run.

    Attributes:
        project_name: Human-readable name (e.g. ``scikit-learn``).
        paraphrased_name: Optional paraphrased name used during generation.
        repo_path: Path to the generated repository.
        tasks: List of benchmark tasks for this project.
        import_mapping: Optional import rewrites (e.g. ``sklearn`` -> ``ml_lib``).
    """

    project_name: str
    paraphrased_name: str = ""
    repo_path: str = ""
    tasks: list[BenchmarkTask] = field(default_factory=list)
    import_mapping: dict[str, str] = field(default_factory=dict)


@dataclass
class RunnerConfig:
    """Configuration for the benchmark runner.

    Attributes:
        output_dir: Directory for result JSON files.
        save_individual: Whether to save per-project results.
        save_aggregate: Whether to save cross-project aggregation.
        verbose: Enable verbose logging.
    """

    output_dir: str = "./benchmark-results"
    save_individual: bool = True
    save_aggregate: bool = True
    verbose: bool = False


# ---------------------------------------------------------------------------
# Runner result
# ---------------------------------------------------------------------------


@dataclass
class RunSummary:
    """Aggregate summary across all projects in a benchmark run.

    Attributes:
        total_projects: Number of projects evaluated.
        total_tasks: Total tasks across all projects.
        total_passed: Total tasks that passed end-to-end.
        overall_pass_rate: Aggregate pass rate.
        per_project: Mapping of project name to :class:`BenchmarkResult`.
        duration_s: Total wall-clock time for the run.
        timestamp: When the run was initiated.
    """

    total_projects: int = 0
    total_tasks: int = 0
    total_passed: int = 0
    overall_pass_rate: float = 0.0
    per_project: dict[str, BenchmarkResult] = field(default_factory=dict)
    duration_s: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# BenchmarkRunner
# ---------------------------------------------------------------------------


class BenchmarkRunner:
    """Orchestrates end-to-end benchmark evaluation across projects.

    Provides a high-level interface for running the full evaluation
    pipeline on one or more generated repositories, collecting profiling
    data, and producing structured results.

    Args:
        evaluation_pipeline: The 3-stage evaluation pipeline instance.
        metrics_calculator: Optional metrics calculator for code stats.
        config: Runner configuration.
    """

    def __init__(
        self,
        evaluation_pipeline: EvaluationPipelineProtocol,
        metrics_calculator: MetricsCalculatorProtocol | None = None,
        config: RunnerConfig | None = None,
    ) -> None:
        self.pipeline = evaluation_pipeline
        self.metrics = metrics_calculator
        self.config = config or RunnerConfig()

    # ------------------------------------------------------------------
    # Single-project evaluation
    # ------------------------------------------------------------------

    def run_project(
        self,
        project_name: str,
        tasks: list[BenchmarkTask],
        repo_path: str | Path,
        paraphrased_name: str = "",
    ) -> BenchmarkResult:
        """Run full evaluation on a single generated repository.

        Args:
            project_name: Name of the project.
            tasks: Benchmark tasks for this project.
            repo_path: Path to the generated repository.
            paraphrased_name: Optional paraphrased project name.

        Returns:
            A :class:`BenchmarkResult` with evaluation and profiling data.
        """
        repo_path = Path(repo_path)
        logger.info(
            "Starting evaluation of %s (%d tasks) at %s",
            project_name,
            len(tasks),
            repo_path,
        )

        start_time = time.monotonic()

        # Run evaluation pipeline
        eval_result = self.pipeline.evaluate_repository(tasks, str(repo_path))

        eval_duration = time.monotonic() - start_time

        # Collect code stats if metrics calculator available
        code_stats = None
        if self.metrics and repo_path.exists():
            code_stats = self.metrics.calculate_code_stats(repo_path)

        # Build profiling data
        profiling = ProfilingData(
            stage_timings={"evaluation": eval_duration},
            total_duration_s=eval_duration,
        )

        result = BenchmarkResult(
            project=project_name,
            paraphrased_name=paraphrased_name,
            evaluation=eval_result,
            profiling=profiling,
            repo_path=str(repo_path),
            timestamp=datetime.now(),
        )

        logger.info(
            "Completed %s: pass_rate=%.2f, localized=%d/%d, validated=%d/%d, passed=%d/%d (%.1fs)",
            project_name,
            eval_result.pass_rate,
            eval_result.localized,
            eval_result.total_tasks,
            eval_result.validated,
            eval_result.total_tasks,
            eval_result.passed,
            eval_result.total_tasks,
            eval_duration,
        )

        return result

    # ------------------------------------------------------------------
    # Multi-project evaluation
    # ------------------------------------------------------------------

    def run_batch(
        self,
        projects: list[ProjectConfig],
    ) -> RunSummary:
        """Run evaluation across multiple projects.

        Args:
            projects: List of project configurations.

        Returns:
            A :class:`RunSummary` with per-project and aggregate results.
        """
        start_time = time.monotonic()
        results: dict[str, BenchmarkResult] = {}

        for project in projects:
            logger.info("Processing project: %s", project.project_name)
            try:
                result = self.run_project(
                    project_name=project.project_name,
                    tasks=project.tasks,
                    repo_path=project.repo_path,
                    paraphrased_name=project.paraphrased_name,
                )
                results[project.project_name] = result
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to evaluate %s: %s",
                    project.project_name,
                    exc,
                )

        total_duration = time.monotonic() - start_time

        # Aggregate metrics
        total_tasks = sum(
            r.evaluation.total_tasks for r in results.values()
        )
        total_passed = sum(r.evaluation.passed for r in results.values())
        overall_pass_rate = total_passed / total_tasks if total_tasks > 0 else 0.0

        summary = RunSummary(
            total_projects=len(results),
            total_tasks=total_tasks,
            total_passed=total_passed,
            overall_pass_rate=overall_pass_rate,
            per_project=results,
            duration_s=total_duration,
            timestamp=datetime.now(),
        )

        logger.info(
            "Batch complete: %d projects, %d/%d tasks passed (%.1f%%) in %.1fs",
            summary.total_projects,
            summary.total_passed,
            summary.total_tasks,
            summary.overall_pass_rate * 100,
            summary.duration_s,
        )

        return summary

    # ------------------------------------------------------------------
    # Result serialisation
    # ------------------------------------------------------------------

    def save_result(
        self,
        result: BenchmarkResult,
        output_dir: str | Path | None = None,
    ) -> Path:
        """Save a single project result to JSON.

        Args:
            result: The benchmark result to save.
            output_dir: Output directory (defaults to config.output_dir).

        Returns:
            Path to the written JSON file.
        """
        output_dir = Path(output_dir or self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{result.project}-benchmark-result.json"
        output_path = output_dir / filename

        payload = result.model_dump(mode="json")
        output_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

        logger.info("Saved result to %s", output_path)
        return output_path

    def save_summary(
        self,
        summary: RunSummary,
        output_dir: str | Path | None = None,
    ) -> Path:
        """Save aggregate run summary to JSON.

        Args:
            summary: The run summary to save.
            output_dir: Output directory (defaults to config.output_dir).

        Returns:
            Path to the written JSON file.
        """
        output_dir = Path(output_dir or self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "benchmark-summary.json"

        payload = {
            "total_projects": summary.total_projects,
            "total_tasks": summary.total_tasks,
            "total_passed": summary.total_passed,
            "overall_pass_rate": summary.overall_pass_rate,
            "duration_s": summary.duration_s,
            "timestamp": summary.timestamp.isoformat(),
            "projects": {
                name: {
                    "pass_rate": result.evaluation.pass_rate,
                    "localized": result.evaluation.localized,
                    "validated": result.evaluation.validated,
                    "passed": result.evaluation.passed,
                    "total_tasks": result.evaluation.total_tasks,
                    "duration_s": result.profiling.total_duration_s,
                }
                for name, result in summary.per_project.items()
            },
        }

        output_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

        logger.info("Saved summary to %s", output_path)
        return output_path

    def save_results(
        self,
        summary: RunSummary,
        output_dir: str | Path | None = None,
    ) -> list[Path]:
        """Save all results: per-project files and aggregate summary.

        Args:
            summary: The run summary to save.
            output_dir: Output directory (defaults to config.output_dir).

        Returns:
            List of all written file paths.
        """
        output_dir = Path(output_dir or self.config.output_dir)
        paths: list[Path] = []

        if self.config.save_individual:
            for result in summary.per_project.values():
                paths.append(self.save_result(result, output_dir))

        if self.config.save_aggregate:
            paths.append(self.save_summary(summary, output_dir))

        return paths
