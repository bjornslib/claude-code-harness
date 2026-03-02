"""Full benchmark execution runner for RepoCraft.

Provides:
- :func:`load_project_tasks`: load harvested tasks from JSON files.
- :func:`build_project_configs`: build project configs for batch evaluation.
- :func:`generate_report`: produce a Markdown summary report.
- :class:`BenchmarkConfig`: configuration for the wave-4 runner.
- :class:`BenchmarkRunner`: wave-4 benchmark runner that wraps zerorepo and
  evaluation pipelines.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cobuilder.repomap.evaluation.models import (
    BenchmarkResult,
    BenchmarkTask,
    ProfilingData,
    RepositoryResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known project name → paraphrase mappings
# ---------------------------------------------------------------------------

_PARAPHRASE_MAP: dict[str, str] = {
    "scikit-learn": "ml_lib",
    "pandas": "data_frames",
    "sympy": "math_engine",
    "django": "web_framework",
}


# ---------------------------------------------------------------------------
# Helper functions used by test_benchmark_runner.py
# ---------------------------------------------------------------------------


def load_project_tasks(directory: Path, project_name: str) -> list[BenchmarkTask]:
    """Load tasks from ``{directory}/{project_name}-tasks.json``.

    The JSON file may be either:
    - A dict with a ``"tasks"`` key whose value is a list of task dicts.
    - A plain list of task dicts.

    Invalid task entries are skipped with a warning.  Returns an empty list
    if the file does not exist.

    Args:
        directory: Directory containing the tasks JSON file.
        project_name: Name of the project (used to build the filename).

    Returns:
        List of validated :class:`BenchmarkTask` objects.
    """
    tasks_file = directory / f"{project_name}-tasks.json"
    if not tasks_file.exists():
        logger.warning("Tasks file not found: %s", tasks_file)
        return []

    try:
        data = json.loads(tasks_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read tasks file %s: %s", tasks_file, exc)
        return []

    raw_tasks: list[dict[str, Any]] = []
    if isinstance(data, list):
        raw_tasks = data
    elif isinstance(data, dict):
        raw_tasks = data.get("tasks", [])
    else:
        logger.error("Unexpected tasks file format in %s", tasks_file)
        return []

    tasks: list[BenchmarkTask] = []
    for raw in raw_tasks:
        try:
            tasks.append(BenchmarkTask(**raw))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping invalid task %s: %s", raw.get("id", "?"), exc)

    return tasks


def build_project_configs(
    project_names: list[str],
    tasks_dir: Path,
    repos_dir: Path,
) -> list[dict[str, Any]]:
    """Build project configs for batch evaluation.

    For each project in *project_names*, attempts to load tasks from
    ``{tasks_dir}/{project_name}-tasks.json``.  Projects with no tasks are
    silently skipped.

    Args:
        project_names: Names of projects to configure.
        tasks_dir: Directory containing per-project task JSON files.
        repos_dir: Root directory containing per-project repository folders.

    Returns:
        A list of dicts each with ``"project_name"`` and ``"tasks"`` keys.
    """
    configs: list[dict[str, Any]] = []
    for name in project_names:
        tasks = load_project_tasks(tasks_dir, name)
        if not tasks:
            logger.info("No tasks found for project %s, skipping", name)
            continue
        configs.append({
            "project_name": name,
            "tasks": tasks,
            "repo_path": str(repos_dir / name),
        })
    return configs


def generate_report(summary: Any) -> str:
    """Generate a Markdown report from a :class:`RunSummary`.

    The report contains:
    - A heading ``# RepoCraft Benchmark Report``
    - Per-project table rows with pass rates formatted as ``75.0%``
    - Summary statistics

    Args:
        summary: A :class:`RunSummary` (or compatible object with
            ``total_projects``, ``total_tasks``, ``overall_pass_rate``,
            ``per_project``, and optionally ``duration_s``).

    Returns:
        Markdown-formatted report string.
    """
    lines: list[str] = [
        "# RepoCraft Benchmark Report",
        "",
        f"**Projects evaluated**: {summary.total_projects}",
        f"**Total tasks**: {summary.total_tasks}",
        f"**Overall pass rate**: {summary.overall_pass_rate * 100:.1f}%",
        "",
        "## Per-Project Results",
        "",
        "| Project | Tasks | Passed | Pass Rate |",
        "| ------- | ----- | ------ | --------- |",
    ]

    per_project = getattr(summary, "per_project", {}) or {}
    for project_name, result in per_project.items():
        evaluation = result.evaluation
        total = evaluation.total_tasks
        passed = evaluation.passed
        rate = (passed / total * 100) if total else 0.0
        lines.append(f"| {project_name} | {total} | {passed} | {rate:.1f}% |")

    duration_s = getattr(summary, "duration_s", None)
    if duration_s is not None:
        lines.extend([
            "",
            f"**Total duration**: {duration_s:.1f}s",
        ])

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Wave-4 runner (used by test_wave4.py)
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkConfig:
    """Configuration for the wave-4 :class:`BenchmarkRunner`.

    Attributes:
        projects: List of project names to evaluate.
        max_tasks_per_project: Maximum number of tasks to load per project.
        paraphrase_names: If ``True``, replace project names using
            :meth:`BenchmarkRunner.paraphrase_name` during generation.
        tasks_dir: Directory containing per-project task JSON files.
        output_dir: Directory to write per-project result JSON files.
    """

    projects: list[str] = field(
        default_factory=lambda: ["scikit-learn", "pandas", "sympy"]
    )
    max_tasks_per_project: int = 200
    paraphrase_names: bool = True
    tasks_dir: str = "./benchmark-tasks"
    output_dir: str = "./benchmark-results"


class BenchmarkRunner:
    """Wave-4 benchmark runner that wraps zerorepo and evaluation pipelines.

    This is a *different* class from
    :class:`cobuilder.repomap.evaluation.benchmark_runner.BenchmarkRunner`.

    Args:
        config: :class:`BenchmarkConfig` instance.  A default config is used
            when ``None`` is passed.
        zerorepo_pipeline: Optional pipeline with a ``generate(...)`` method.
        evaluation_pipeline: Optional pipeline with an
            ``evaluate_repository(...)`` method.
        profiling_collector: Optional profiler with ``start_timer`` /
            ``stop_timer`` / ``get_profiling_data`` methods.
    """

    def __init__(
        self,
        config: BenchmarkConfig | None = None,
        zerorepo_pipeline: Any = None,
        evaluation_pipeline: Any = None,
        profiling_collector: Any = None,
    ) -> None:
        self.config = config or BenchmarkConfig()
        self.zerorepo_pipeline = zerorepo_pipeline
        self.evaluation_pipeline = evaluation_pipeline
        self.profiling_collector = profiling_collector

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def paraphrase_name(name: str) -> str:
        """Return the paraphrased name for *name*.

        Known mappings are applied first; unknown names have hyphens replaced
        with underscores.

        Args:
            name: Original project name (e.g. ``"scikit-learn"``).

        Returns:
            Paraphrased name (e.g. ``"ml_lib"``).
        """
        if name in _PARAPHRASE_MAP:
            return _PARAPHRASE_MAP[name]
        return name.replace("-", "_")

    # ------------------------------------------------------------------
    # Task loading
    # ------------------------------------------------------------------

    def load_tasks(self, project_name: str) -> list[BenchmarkTask]:
        """Load tasks for *project_name* from the configured tasks directory.

        Applies the :attr:`~BenchmarkConfig.max_tasks_per_project` limit.

        Args:
            project_name: Name of the project.

        Returns:
            List of :class:`BenchmarkTask` objects (possibly empty).
        """
        tasks_dir = Path(self.config.tasks_dir)
        tasks_file = tasks_dir / f"{project_name}-tasks.json"

        if not tasks_file.exists():
            logger.warning("Tasks file not found: %s", tasks_file)
            return []

        try:
            data = json.loads(tasks_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read tasks file %s: %s", tasks_file, exc)
            return []

        raw_tasks: list[dict[str, Any]] = []
        if isinstance(data, list):
            raw_tasks = data
        elif isinstance(data, dict):
            raw_tasks = data.get("tasks", [])

        tasks: list[BenchmarkTask] = []
        for raw in raw_tasks:
            try:
                tasks.append(BenchmarkTask(**raw))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping invalid task: %s", exc)

        # Apply max limit.
        if self.config.max_tasks_per_project > 0:
            tasks = tasks[: self.config.max_tasks_per_project]

        return tasks

    # ------------------------------------------------------------------
    # Project evaluation
    # ------------------------------------------------------------------

    def run_project(self, project_name: str) -> BenchmarkResult:
        """Evaluate a single project.

        Workflow:
        1. Load tasks via :meth:`load_tasks`.
        2. If ``zerorepo_pipeline`` is set, call
           ``profiling_collector.start_timer("generation")``, then
           ``zerorepo_pipeline.generate(...)``, then stop the timer.
        3. If ``evaluation_pipeline`` is set, call
           ``profiling_collector.start_timer("evaluation")``, then
           ``evaluation_pipeline.evaluate_repository(...)``, then stop
           the timer.
        4. Build and save a :class:`BenchmarkResult`.

        Args:
            project_name: Name of the project to evaluate.

        Returns:
            A :class:`BenchmarkResult` for the project.
        """
        tasks = self.load_tasks(project_name)

        # Determine paraphrased name.
        if self.config.paraphrase_names:
            paraphrased = self.paraphrase_name(project_name)
        else:
            paraphrased = project_name

        repo_path: str = ""
        profiling = ProfilingData()

        # Generation stage.
        if self.zerorepo_pipeline is not None:
            if self.profiling_collector is not None:
                self.profiling_collector.start_timer("generation")
            repo_path = self.zerorepo_pipeline.generate(
                project_name=paraphrased,
                tasks=tasks,
            )
            if self.profiling_collector is not None:
                self.profiling_collector.stop_timer("generation")

        # Evaluation stage.
        if self.evaluation_pipeline is not None and tasks:
            if self.profiling_collector is not None:
                self.profiling_collector.start_timer("evaluation")
            evaluation = self.evaluation_pipeline.evaluate_repository(
                tasks,
                repo_path,
            )
            if self.profiling_collector is not None:
                self.profiling_collector.stop_timer("evaluation")

            if self.profiling_collector is not None:
                profiling = self.profiling_collector.get_profiling_data()
        else:
            # No evaluation pipeline or no tasks — return a default result.
            evaluation = RepositoryResult(
                project_name=project_name,
                total_tasks=len(tasks),
                passed=0,
            )

        result = BenchmarkResult(
            project=project_name,
            paraphrased_name=paraphrased,
            evaluation=evaluation,
            profiling=profiling,
            repo_path=repo_path,
        )

        self._save_result(result)
        return result

    def run_all(self) -> list[BenchmarkResult]:
        """Evaluate all projects listed in :attr:`config.projects`.

        Returns:
            List of :class:`BenchmarkResult`, one per project, in the
            same order as ``config.projects``.
        """
        return [self.run_project(name) for name in self.config.projects]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_result(self, result: BenchmarkResult) -> None:
        """Persist *result* to ``{config.output_dir}/{project}-result.json``.

        The output directory is created if it does not exist.

        Args:
            result: The benchmark result to save.
        """
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        out_file = output_dir / f"{result.project}-result.json"

        payload: dict[str, Any] = {
            "project": result.project,
            "paraphrased_name": result.paraphrased_name,
            "repo_path": result.repo_path,
            "evaluation": {
                "project_name": result.evaluation.project_name,
                "total_tasks": result.evaluation.total_tasks,
                "localized": result.evaluation.localized,
                "validated": result.evaluation.validated,
                "passed": result.evaluation.passed,
                "coverage": result.evaluation.coverage,
                "novelty": result.evaluation.novelty,
            },
        }

        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved result for %s to %s", result.project, out_file)
