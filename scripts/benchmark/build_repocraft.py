"""End-to-end RepoCraft benchmark construction pipeline.

Integrates the full workflow:

1. **Harvest** -- extract test functions from Python repositories via AST
2. **Categorize** -- build hierarchical taxonomy from dotted categories
3. **Filter** -- remove trivial, flaky, and skipped tests
4. **Sample** -- stratified sampling to produce a balanced benchmark subset

Usage::

    python -m scripts.benchmark.build_repocraft \\
        --repo-path /path/to/repo \\
        --project-name scikit-learn \\
        --output-dir ./benchmark-tasks \\
        --sample-size 200 \\
        --seed 42

Or programmatically::

    from scripts.benchmark.build_repocraft import BenchmarkPipeline, PipelineConfig
    pipeline = BenchmarkPipeline(PipelineConfig(project_name="sklearn"))
    result = pipeline.run("/path/to/sklearn-repo")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerorepo.evaluation.categorizer import Categorizer
from zerorepo.evaluation.models import BenchmarkTask, Taxonomy
from zerorepo.evaluation.test_filter import TestFilter

from scripts.benchmark.harvest_tests import TestHarvester

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """Configuration for the benchmark construction pipeline.

    Attributes:
        project_name: Human-readable project name (e.g. ``scikit-learn``).
        sample_size: Target number of tasks after stratified sampling.
            Set to ``0`` to disable sampling (keep all filtered tasks).
        seed: RNG seed for reproducible sampling.
        min_loc: Minimum lines of code for a test to survive filtering.
        require_assertions: Whether to drop tests without assertions.
        filter_flaky: Whether to drop tests with external IO patterns.
        filter_skipped: Whether to drop tests with skip decorators.
    """

    project_name: str = ""
    sample_size: int = 200
    seed: int = 42
    min_loc: int = 10
    require_assertions: bool = True
    filter_flaky: bool = True
    filter_skipped: bool = True


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Output of a single pipeline run.

    Attributes:
        project_name: Name of the project that was processed.
        harvested_count: Total test functions extracted by the harvester.
        filtered_count: Tasks remaining after quality filtering.
        sampled_count: Tasks in the final sample.
        tasks: The final list of :class:`BenchmarkTask` instances.
        taxonomy: Hierarchical taxonomy built from the tasks.
    """

    project_name: str = ""
    harvested_count: int = 0
    filtered_count: int = 0
    sampled_count: int = 0
    tasks: list[BenchmarkTask] = field(default_factory=list)
    taxonomy: Taxonomy | None = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class BenchmarkPipeline:
    """Orchestrates the full harvest -> categorize -> filter -> sample flow.

    Args:
        config: Pipeline configuration.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self._harvester = TestHarvester(project_name=self.config.project_name)
        self._categorizer = Categorizer()
        self._filter = TestFilter(
            min_loc=self.config.min_loc,
            require_assertions=self.config.require_assertions,
            filter_flaky=self.config.filter_flaky,
            filter_skipped=self.config.filter_skipped,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, repo_path: str | Path) -> PipelineResult:
        """Execute the full pipeline on *repo_path*.

        Args:
            repo_path: Root directory of the Python repository.

        Returns:
            A :class:`PipelineResult` with the final tasks and stats.
        """
        repo_path = Path(repo_path)
        logger.info(
            "Starting benchmark pipeline for %s at %s",
            self.config.project_name,
            repo_path,
        )

        # 1. Harvest
        raw_tasks = self._harvester.extract_tests(repo_path)
        harvested_count = len(raw_tasks)
        logger.info("Harvested %d tests", harvested_count)

        # 2. Filter
        filtered_tasks = self._filter.filter_tasks(raw_tasks)
        filtered_count = len(filtered_tasks)
        logger.info("Filtered to %d tests", filtered_count)

        # 3. Categorize (build taxonomy from filtered tasks)
        taxonomy = self._categorizer.build_taxonomy(filtered_tasks)
        logger.info(
            "Taxonomy: %d categories, %d tasks",
            taxonomy.total_categories,
            taxonomy.total_tasks,
        )

        # 4. Sample (if enabled)
        if self.config.sample_size > 0 and filtered_count > self.config.sample_size:
            final_tasks = self._categorizer.stratified_sample(
                filtered_tasks,
                n=self.config.sample_size,
                seed=self.config.seed,
            )
        else:
            final_tasks = filtered_tasks

        sampled_count = len(final_tasks)
        logger.info("Final sample: %d tasks", sampled_count)

        return PipelineResult(
            project_name=self.config.project_name,
            harvested_count=harvested_count,
            filtered_count=filtered_count,
            sampled_count=sampled_count,
            tasks=final_tasks,
            taxonomy=taxonomy,
        )

    def save_tasks(
        self,
        result: PipelineResult,
        output_dir: str | Path,
    ) -> Path:
        """Serialize pipeline result to a JSON file.

        Creates ``{output_dir}/{project_name}-tasks.json`` containing
        both the task list and summary metadata.

        Args:
            result: Pipeline result to serialise.
            output_dir: Directory to write the output file.

        Returns:
            Path to the written JSON file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{result.project_name or 'benchmark'}-tasks.json"
        output_path = output_dir / filename

        payload = {
            "project": result.project_name,
            "summary": {
                "harvested": result.harvested_count,
                "filtered": result.filtered_count,
                "sampled": result.sampled_count,
            },
            "tasks": [task.model_dump(mode="json") for task in result.tasks],
        }

        output_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Saved %d tasks to %s", result.sampled_count, output_path)
        return output_path


# ---------------------------------------------------------------------------
# Multi-project runner
# ---------------------------------------------------------------------------


def run_multiple(
    projects: dict[str, str | Path],
    output_dir: str | Path,
    sample_size: int = 200,
    seed: int = 42,
) -> dict[str, PipelineResult]:
    """Run the pipeline on multiple projects.

    Args:
        projects: Mapping of project_name -> repo_path.
        output_dir: Directory to write all output JSON files.
        sample_size: Per-project sample size.
        seed: RNG seed for reproducibility.

    Returns:
        Mapping of project_name -> :class:`PipelineResult`.
    """
    results: dict[str, PipelineResult] = {}

    for name, repo_path in projects.items():
        logger.info("Processing project: %s", name)
        config = PipelineConfig(
            project_name=name,
            sample_size=sample_size,
            seed=seed,
        )
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(repo_path)
        pipeline.save_tasks(result, output_dir)
        results[name] = result

    logger.info(
        "Completed %d projects. Total tasks: %d",
        len(results),
        sum(r.sampled_count for r in results.values()),
    )
    return results


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for single-project benchmark construction."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build RepoCraft benchmark tasks from a Python repository."
    )
    parser.add_argument(
        "--repo-path",
        type=str,
        required=True,
        help="Path to the Python repository to harvest tests from.",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="project",
        help="Human-readable project name (default: 'project').",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./benchmark-tasks",
        help="Directory to write output JSON (default: ./benchmark-tasks).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=200,
        help="Number of tasks to sample per project (0 = no sampling).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducible sampling (default: 42).",
    )
    parser.add_argument(
        "--min-loc",
        type=int,
        default=10,
        help="Minimum LOC threshold for test filtering (default: 10).",
    )
    parser.add_argument(
        "--no-filter-flaky",
        action="store_true",
        help="Disable flaky test detection.",
    )
    parser.add_argument(
        "--no-filter-skipped",
        action="store_true",
        help="Disable skip decorator detection.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = PipelineConfig(
        project_name=args.project_name,
        sample_size=args.sample_size,
        seed=args.seed,
        min_loc=args.min_loc,
        filter_flaky=not args.no_filter_flaky,
        filter_skipped=not args.no_filter_skipped,
    )

    pipeline = BenchmarkPipeline(config)
    result = pipeline.run(args.repo_path)
    output_path = pipeline.save_tasks(result, args.output_dir)

    print(f"\nBenchmark construction complete for {args.project_name}:")
    print(f"  Harvested: {result.harvested_count}")
    print(f"  Filtered:  {result.filtered_count}")
    print(f"  Sampled:   {result.sampled_count}")
    print(f"  Output:    {output_path}")


if __name__ == "__main__":
    main()
