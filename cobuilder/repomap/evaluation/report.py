"""Report generation for benchmark evaluation results.

Generates markdown comparison reports with metrics vs paper targets.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from cobuilder.repomap.evaluation.models import (
    BenchmarkResult,
    ProfilingData,
    RepositoryResult,
)

logger = logging.getLogger(__name__)

# Paper reference metrics
PAPER_METRICS = {
    "coverage": 0.815,
    "pass_rate": 0.697,
    "voting_rate": 0.750,
}


class ReportGenerator:
    """Generates markdown and JSON reports from benchmark results."""

    def __init__(self, paper_metrics: dict[str, float] | None = None) -> None:
        self.paper_metrics = paper_metrics or PAPER_METRICS

    def generate_comparison_report(
        self,
        results: list[BenchmarkResult],
        output_path: str | Path | None = None,
    ) -> str:
        """Generate markdown report comparing results vs paper metrics."""
        lines = [
            "# ZeroRepo Benchmark Evaluation Report",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Summary",
            "",
        ]

        # Overall aggregates
        if results:
            all_tasks = sum(r.evaluation.total_tasks for r in results)
            all_passed = sum(r.evaluation.passed for r in results)
            all_validated = sum(r.evaluation.validated for r in results)
            all_localized = sum(r.evaluation.localized for r in results)

            avg_coverage = sum(r.evaluation.coverage for r in results) / len(results)
            avg_pass_rate = all_passed / all_tasks if all_tasks else 0.0
            avg_voting_rate = all_validated / all_tasks if all_tasks else 0.0

            lines.extend([
                f"- **Projects evaluated**: {len(results)}",
                f"- **Total tasks**: {all_tasks}",
                f"- **Tasks passed**: {all_passed}",
                f"- **Overall pass rate**: {avg_pass_rate:.1%}",
                "",
            ])
        else:
            avg_coverage = 0.0
            avg_pass_rate = 0.0
            avg_voting_rate = 0.0

        # Comparison table
        lines.extend([
            "## Metrics vs Paper",
            "",
            "| Metric | Ours | Paper | Delta |",
            "|--------|------|-------|-------|",
        ])

        our_metrics = {
            "coverage": avg_coverage,
            "pass_rate": avg_pass_rate,
            "voting_rate": avg_voting_rate,
        }

        for metric, ours in our_metrics.items():
            paper = self.paper_metrics.get(metric, 0.0)
            delta = ours - paper
            sign = "+" if delta >= 0 else ""
            lines.append(
                f"| {metric.replace('_', ' ').title()} "
                f"| {ours:.1%} | {paper:.1%} | {sign}{delta:.1%} |"
            )

        lines.append("")

        # Per-project table
        if results:
            lines.extend([
                "## Per-Project Results",
                "",
                "| Project | Tasks | Localized | Validated | Passed | Coverage | Pass Rate |",
                "|---------|-------|-----------|-----------|--------|----------|-----------|",
            ])

            for r in results:
                ev = r.evaluation
                lines.append(
                    f"| {r.project} | {ev.total_tasks} | {ev.localized} | "
                    f"{ev.validated} | {ev.passed} | {ev.coverage:.1%} | "
                    f"{ev.pass_rate:.1%} |"
                )

            lines.append("")

        # Profiling section
        has_profiling = (
            any(r.profiling.total_tokens > 0 for r in results) if results else False
        )
        if has_profiling:
            lines.extend([
                "## Token Usage",
                "",
                "| Project | Total Tokens | Est. Cost | Duration |",
                "|---------|-------------|-----------|----------|",
            ])
            for r in results:
                p = r.profiling
                lines.append(
                    f"| {r.project} | {p.total_tokens:,} | "
                    f"${p.total_cost_usd:.2f} | {p.total_duration_s:.1f}s |"
                )
            lines.append("")

        report = "\n".join(lines)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report)
            logger.info(f"Report saved to {output_path}")

        return report

    def generate_json_report(
        self,
        results: list[BenchmarkResult],
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Generate JSON report for programmatic consumption."""
        report: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "num_projects": len(results),
            "projects": [],
            "aggregate": {},
        }

        for r in results:
            report["projects"].append({
                "project": r.project,
                "paraphrased_name": r.paraphrased_name,
                "total_tasks": r.evaluation.total_tasks,
                "localized": r.evaluation.localized,
                "validated": r.evaluation.validated,
                "passed": r.evaluation.passed,
                "coverage": r.evaluation.coverage,
                "pass_rate": r.evaluation.pass_rate,
                "voting_rate": r.evaluation.voting_rate,
            })

        if results:
            all_tasks = sum(r.evaluation.total_tasks for r in results)
            report["aggregate"] = {
                "total_tasks": all_tasks,
                "avg_coverage": (
                    sum(r.evaluation.coverage for r in results) / len(results)
                ),
                "overall_pass_rate": (
                    sum(r.evaluation.passed for r in results) / all_tasks
                    if all_tasks
                    else 0.0
                ),
                "overall_voting_rate": (
                    sum(r.evaluation.validated for r in results) / all_tasks
                    if all_tasks
                    else 0.0
                ),
            }

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, indent=2))
            logger.info(f"JSON report saved to {output_path}")

        return report
