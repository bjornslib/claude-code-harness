"""End-to-end benchmark construction pipeline for RepoCraft.

Orchestrates test harvesting, filtering, taxonomy construction, stratified
sampling and JSON serialisation in a single cohesive pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cobuilder.repomap.evaluation.categorizer import Categorizer
from cobuilder.repomap.evaluation.models import BenchmarkTask, Taxonomy
from cobuilder.repomap.evaluation.test_filter import TestFilter
from scripts.benchmark.harvest_tests import TestHarvester

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration and result types
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """Configuration for a single benchmark construction run.

    Attributes:
        project_name: Name of the source project.
        sample_size: Target sample size after filtering (0 = no sampling).
        seed: Random seed for reproducible stratified sampling.
        min_loc: Minimum LOC threshold for the :class:`TestFilter`.
        require_assertions: Whether to drop tests lacking assertions.
        filter_flaky: Whether to drop tests with IO/network patterns.
        filter_skipped: Whether to drop tests carrying skip decorators.
    """

    project_name: str = ""
    sample_size: int = 200
    seed: int = 42
    min_loc: int = 10
    require_assertions: bool = True
    filter_flaky: bool = True
    filter_skipped: bool = True


@dataclass
class PipelineResult:
    """Result produced by :meth:`BenchmarkPipeline.run`.

    Attributes:
        project_name: Name of the source project.
        harvested_count: Raw number of test functions found.
        filtered_count: Tasks remaining after quality filtering.
        sampled_count: Tasks remaining after stratified sampling.
        tasks: Final list of tasks.
        taxonomy: Hierarchical task taxonomy (``None`` when no tasks).
    """

    project_name: str = ""
    harvested_count: int = 0
    filtered_count: int = 0
    sampled_count: int = 0
    tasks: list[BenchmarkTask] = field(default_factory=list)
    taxonomy: Taxonomy | None = None


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


class BenchmarkPipeline:
    """Orchestrates the full benchmark construction workflow.

    Usage::

        config = PipelineConfig(project_name="scikit-learn")
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(Path("/path/to/sklearn"))
        pipeline.save_tasks(result, Path("./benchmark-tasks"))
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(self, repo_path: Path) -> PipelineResult:
        """Execute the full harvest → filter → categorize → sample pipeline.

        Args:
            repo_path: Root of the repository to process.

        Returns:
            A :class:`PipelineResult` with counts and the final task list.
        """
        cfg = self.config

        # 1. Harvest.
        harvested: list[BenchmarkTask] = TestHarvester(
            project_name=cfg.project_name
        ).extract_tests(repo_path)
        harvested_count = len(harvested)

        # 2. Filter.
        filtered: list[BenchmarkTask] = TestFilter(
            min_loc=cfg.min_loc,
            require_assertions=cfg.require_assertions,
            filter_flaky=cfg.filter_flaky,
            filter_skipped=cfg.filter_skipped,
        ).filter_tasks(harvested)
        filtered_count = len(filtered)

        # 3. Taxonomy.
        taxonomy: Taxonomy | None = None
        if filtered:
            taxonomy = Categorizer().build_taxonomy(filtered)

        # 4. Sample.
        if cfg.sample_size > 0 and len(filtered) > cfg.sample_size:
            sampled = Categorizer().stratified_sample(
                filtered, n=cfg.sample_size, seed=cfg.seed
            )
        else:
            sampled = list(filtered)

        sampled_count = len(sampled)

        return PipelineResult(
            project_name=cfg.project_name,
            harvested_count=harvested_count,
            filtered_count=filtered_count,
            sampled_count=sampled_count,
            tasks=sampled,
            taxonomy=taxonomy,
        )

    def save_tasks(self, result: PipelineResult, output_dir: Path) -> Path:
        """Serialise *result* to a JSON file in *output_dir*.

        Args:
            result: Pipeline result to serialise.
            output_dir: Directory to write the output file into
                (created if it does not exist).

        Returns:
            The :class:`Path` of the written JSON file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        project_name = result.project_name or ""
        filename = f"{project_name}-tasks.json" if project_name else "benchmark-tasks.json"
        output_path = output_dir / filename

        tasks_data: list[dict[str, Any]] = []
        for task in result.tasks:
            tasks_data.append({
                "id": task.id,
                "project": task.project,
                "category": task.category,
                "subcategory": task.subcategory,
                "description": task.description,
                "test_code": task.test_code,
                "imports": task.imports,
                "fixtures": task.fixtures,
                "auxiliary_code": task.auxiliary_code,
                "loc": task.loc,
                "difficulty": task.difficulty.value if hasattr(task.difficulty, "value") else str(task.difficulty),
                "metadata": task.metadata,
            })

        payload: dict[str, Any] = {
            "project": project_name,
            "summary": {
                "harvested": result.harvested_count,
                "filtered": result.filtered_count,
                "sampled": result.sampled_count,
            },
            "tasks": tasks_data,
        }

        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved %d tasks to %s", len(tasks_data), output_path)
        return output_path


# ---------------------------------------------------------------------------
# Multi-project runner
# ---------------------------------------------------------------------------


def run_multiple(
    projects: dict[str, Path],
    output_dir: Path,
    sample_size: int = 200,
    seed: int = 42,
) -> dict[str, PipelineResult]:
    """Run the benchmark pipeline for multiple projects.

    Args:
        projects: Mapping of project name → repository root path.
        output_dir: Directory where task JSON files will be saved.
        sample_size: Target sample size per project (0 = no sampling).
        seed: Random seed for reproducible stratified sampling.

    Returns:
        A dict mapping project name → :class:`PipelineResult`.
    """
    results: dict[str, PipelineResult] = {}

    for project_name, repo_path in projects.items():
        config = PipelineConfig(
            project_name=project_name,
            sample_size=sample_size,
            seed=seed,
        )
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(repo_path)
        pipeline.save_tasks(result, output_dir)
        results[project_name] = result
        logger.info(
            "Project %s: harvested=%d filtered=%d sampled=%d",
            project_name,
            result.harvested_count,
            result.filtered_count,
            result.sampled_count,
        )

    return results
