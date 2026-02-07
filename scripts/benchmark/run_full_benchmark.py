"""BenchmarkRunner - End-to-end project evaluation integrating ZeroRepo generation + evaluation.

Usage: python -m scripts.benchmark.run_full_benchmark --projects scikit-learn pandas sympy
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from zerorepo.evaluation.models import (
    BenchmarkResult,
    BenchmarkTask,
    ProfilingData,
    RepositoryResult,
)

logger = logging.getLogger(__name__)


class ZeroRepoPipeline(Protocol):
    """Protocol for the ZeroRepo generation pipeline."""

    def generate(self, project_name: str, paraphrased_name: str) -> str: ...


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""

    projects: list[str] = field(
        default_factory=lambda: ["scikit-learn", "pandas", "sympy"]
    )
    tasks_dir: str = "benchmarks/repocraft/tasks"
    output_dir: str = "benchmarks/results"
    max_tasks_per_project: int = 200
    paraphrase_names: bool = True


class BenchmarkRunner:
    """Runs end-to-end benchmark: load tasks, generate repo, evaluate, profile."""

    def __init__(
        self,
        config: BenchmarkConfig | None = None,
        zerorepo_pipeline: ZeroRepoPipeline | None = None,
        evaluation_pipeline: Any = None,  # EvaluationPipeline
        profiling_collector: Any = None,  # ProfilingCollector
        metrics_calculator: Any = None,  # MetricsCalculator
    ) -> None:
        self.config = config or BenchmarkConfig()
        self.zerorepo = zerorepo_pipeline
        self.evaluator = evaluation_pipeline
        self.profiler = profiling_collector
        self.metrics = metrics_calculator

    def load_tasks(self, project: str) -> list[BenchmarkTask]:
        """Load benchmark tasks for a project from JSON file."""
        tasks_path = Path(self.config.tasks_dir) / f"{project}-tasks.json"

        if not tasks_path.exists():
            logger.warning(f"No tasks found at {tasks_path}")
            return []

        with open(tasks_path) as f:
            data = json.load(f)

        tasks_data = data.get("tasks", data) if isinstance(data, dict) else data
        tasks = [BenchmarkTask.model_validate(t) for t in tasks_data]

        if (
            self.config.max_tasks_per_project
            and len(tasks) > self.config.max_tasks_per_project
        ):
            tasks = tasks[: self.config.max_tasks_per_project]

        logger.info(f"Loaded {len(tasks)} tasks for {project}")
        return tasks

    @staticmethod
    def paraphrase_name(project: str) -> str:
        """Generate paraphrased project name (e.g., scikit-learn -> ml_lib)."""
        mapping = {
            "scikit-learn": "ml_lib",
            "pandas": "data_frames",
            "sympy": "math_engine",
            "statsmodels": "stat_toolkit",
            "requests": "http_client",
            "django": "web_framework",
        }
        return mapping.get(project, project.replace("-", "_"))

    def run_project(self, project: str) -> BenchmarkResult:
        """Run full benchmark for a single project."""
        logger.info(f"=== Starting benchmark for {project} ===")
        start_time = time.monotonic()

        # Load tasks
        tasks = self.load_tasks(project)
        if not tasks:
            return BenchmarkResult(
                project=project,
                evaluation=RepositoryResult(
                    project_name=project,
                    total_tasks=0,
                ),
            )

        # Paraphrase name
        paraphrased = (
            self.paraphrase_name(project)
            if self.config.paraphrase_names
            else project
        )

        # Generate repository (if pipeline available)
        repo_path = ""
        if self.zerorepo:
            if self.profiler:
                self.profiler.start_timer("generation")
            repo_path = self.zerorepo.generate(project, paraphrased)
            if self.profiler:
                self.profiler.stop_timer("generation")

        # Evaluate
        evaluation = RepositoryResult(
            project_name=project,
            total_tasks=len(tasks),
        )

        if self.evaluator and repo_path:
            if self.profiler:
                self.profiler.start_timer("evaluation")
            evaluation = self.evaluator.evaluate_repository(tasks, repo_path)
            if self.profiler:
                self.profiler.stop_timer("evaluation")

        # Collect profiling
        profiling = (
            self.profiler.get_profiling_data() if self.profiler else ProfilingData()
        )

        duration = time.monotonic() - start_time
        logger.info(
            f"=== Completed {project}: {evaluation.passed}/{evaluation.total_tasks} "
            f"passed ({evaluation.pass_rate:.1%}) in {duration:.1f}s ==="
        )

        return BenchmarkResult(
            project=project,
            paraphrased_name=paraphrased,
            evaluation=evaluation,
            profiling=profiling,
            repo_path=repo_path,
        )

    def run_all(self) -> list[BenchmarkResult]:
        """Run benchmark for all configured projects."""
        results = []
        for project in self.config.projects:
            result = self.run_project(project)
            results.append(result)

            # Save intermediate result
            self._save_result(result)

        return results

    def _save_result(self, result: BenchmarkResult) -> None:
        """Save individual project result to disk."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{result.project}-result.json"
        with open(output_path, "w") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"Result saved to {output_path}")


# ---------------------------------------------------------------------------
# Task loading helpers
# ---------------------------------------------------------------------------


def load_project_tasks(
    tasks_dir: str | Path,
    project_name: str,
) -> list[BenchmarkTask]:
    """Load benchmark tasks from a previously-harvested JSON file.

    Expects a file at ``{tasks_dir}/{project_name}-tasks.json`` produced
    by :mod:`scripts.benchmark.build_repocraft`.

    Args:
        tasks_dir: Directory containing ``*-tasks.json`` files.
        project_name: Name of the project to load.

    Returns:
        List of :class:`BenchmarkTask` instances.
    """
    tasks_dir = Path(tasks_dir)
    tasks_file = tasks_dir / f"{project_name}-tasks.json"

    if not tasks_file.exists():
        logger.warning("Tasks file not found: %s", tasks_file)
        return []

    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    tasks_data = data.get("tasks", [])

    tasks: list[BenchmarkTask] = []
    for task_dict in tasks_data:
        try:
            tasks.append(BenchmarkTask(**task_dict))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping invalid task: %s", exc)

    logger.info(
        "Loaded %d tasks for %s from %s",
        len(tasks),
        project_name,
        tasks_file,
    )
    return tasks


def build_project_configs(
    projects: list[str],
    tasks_dir: str | Path,
    repos_dir: str | Path,
    import_mappings: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Build project configuration dicts for a list of projects.

    Args:
        projects: List of project names.
        tasks_dir: Directory containing ``*-tasks.json`` files.
        repos_dir: Directory containing generated repos (one per project).
        import_mappings: Optional per-project import rewrites.

    Returns:
        List of project config dicts with tasks loaded.
    """
    repos_dir = Path(repos_dir)
    import_mappings = import_mappings or {}
    configs: list[dict[str, Any]] = []

    for name in projects:
        tasks = load_project_tasks(tasks_dir, name)
        if not tasks:
            logger.warning("Skipping %s: no tasks found", name)
            continue

        repo_path = repos_dir / name

        configs.append({
            "project_name": name,
            "repo_path": str(repo_path),
            "tasks": tasks,
            "import_mapping": import_mappings.get(name, {}),
        })

    return configs


def generate_report(summary: Any) -> str:
    """Generate a human-readable Markdown report from a run summary.

    Args:
        summary: A RunSummary-like object with per_project results.

    Returns:
        Markdown-formatted string.
    """
    lines: list[str] = []
    lines.append("# RepoCraft Benchmark Report")
    lines.append("")
    lines.append(f"**Date**: {summary.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Duration**: {summary.duration_s:.1f}s")
    lines.append(f"**Projects**: {summary.total_projects}")
    lines.append(f"**Total Tasks**: {summary.total_tasks}")
    lines.append(f"**Overall Pass Rate**: {summary.overall_pass_rate:.1%}")
    lines.append("")
    lines.append("## Per-Project Results")
    lines.append("")
    lines.append("| Project | Tasks | Localized | Validated | Passed | Pass Rate | Duration |")
    lines.append("|---------|-------|-----------|-----------|--------|-----------|----------|")

    for name, result in summary.per_project.items():
        ev = result.evaluation
        dur = result.profiling.total_duration_s
        lines.append(
            f"| {name} | {ev.total_tasks} | {ev.localized} | "
            f"{ev.validated} | {ev.passed} | "
            f"{ev.pass_rate:.1%} | {dur:.1f}s |"
        )

    lines.append("")
    return "\n".join(lines)
