"""Coverage report generation for the code generation run.

Compares planned vs generated nodes and produces a Markdown report
with breakdown by subgraph, failure details, and recommendations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from cobuilder.repomap.codegen.models import (
    CoverageReport,
    GenerationStatus,
    NodeCoverageEntry,
    SubgraphCoverage,
)
from cobuilder.repomap.models.enums import TestStatus
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode


# Map RPGNode TestStatus to our GenerationStatus
_STATUS_MAP: dict[TestStatus, GenerationStatus] = {
    TestStatus.PENDING: GenerationStatus.PENDING,
    TestStatus.PASSED: GenerationStatus.PASSED,
    TestStatus.FAILED: GenerationStatus.FAILED,
    TestStatus.SKIPPED: GenerationStatus.SKIPPED,
}


def build_coverage_report(
    graph: RPGGraph,
    generation_time_seconds: float | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> CoverageReport:
    """Build a comprehensive coverage report from the RPG graph.

    Analyzes all nodes in the graph and their test statuses
    to produce per-node and per-subgraph coverage breakdowns.

    Args:
        graph: The RPGGraph with generation status on nodes.
        generation_time_seconds: Optional wall time for the generation run.
        extra_metadata: Optional additional metadata.

    Returns:
        A CoverageReport with full breakdown.
    """
    node_details: list[NodeCoverageEntry] = []
    subgraph_data: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    )

    passed = 0
    failed = 0
    skipped = 0
    total = 0

    for node in sorted(graph.nodes.values(), key=lambda n: n.name):
        total += 1
        status = _STATUS_MAP.get(node.test_status, GenerationStatus.PENDING)

        if status == GenerationStatus.PASSED:
            passed += 1
        elif status == GenerationStatus.FAILED:
            failed += 1
        elif status == GenerationStatus.SKIPPED:
            skipped += 1

        # Determine subgraph from metadata or folder path
        subgraph_id = _get_subgraph_id(node)

        entry = NodeCoverageEntry(
            node_id=node.id,
            node_name=node.name,
            status=status,
            retry_count=node.metadata.get("retry_count", 0),
            failure_reason=node.metadata.get("failure_reason"),
            subgraph_id=subgraph_id,
        )
        node_details.append(entry)

        # Update subgraph counters
        sg = subgraph_data[subgraph_id]
        sg["total"] += 1
        if status == GenerationStatus.PASSED:
            sg["passed"] += 1
        elif status == GenerationStatus.FAILED:
            sg["failed"] += 1
        elif status == GenerationStatus.SKIPPED:
            sg["skipped"] += 1

    # Build subgraph breakdown
    subgraph_breakdown = [
        SubgraphCoverage(
            subgraph_id=sg_id,
            total=data["total"],
            passed=data["passed"],
            failed=data["failed"],
            skipped=data["skipped"],
        )
        for sg_id, data in sorted(subgraph_data.items())
    ]

    return CoverageReport(
        timestamp=datetime.now(timezone.utc),
        total_nodes=total,
        passed_nodes=passed,
        failed_nodes=failed,
        skipped_nodes=skipped,
        node_details=node_details,
        subgraph_breakdown=subgraph_breakdown,
        generation_time_seconds=generation_time_seconds,
        metadata=extra_metadata or {},
    )


def _get_subgraph_id(node: RPGNode) -> str:
    """Extract the subgraph ID for a node.

    Tries metadata 'subgraph_id', then derives from folder_path,
    then defaults to 'default'.

    Args:
        node: The RPGNode.

    Returns:
        The subgraph identifier string.
    """
    if "subgraph_id" in node.metadata:
        return str(node.metadata["subgraph_id"])
    if node.folder_path:
        parts = node.folder_path.replace("\\", "/").split("/")
        # Use second component after 'src/' if available
        if len(parts) >= 2 and parts[0] == "src":
            return parts[1]
        return parts[-1]
    if node.file_path:
        parts = node.file_path.replace("\\", "/").split("/")
        if len(parts) >= 2:
            return parts[-2]
    return "default"


def render_coverage_markdown(report: CoverageReport) -> str:
    """Render a coverage report as a Markdown document.

    Follows the template from PRD Appendix C.

    Args:
        report: The CoverageReport to render.

    Returns:
        The Markdown content string.
    """
    lines: list[str] = []

    # Header
    lines.append("# Code Generation Report")
    lines.append("")
    lines.append(f"**Generated**: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("**Phase**: 4 (Graph-Guided Code Generation)")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Nodes Planned**: {report.total_nodes}")
    lines.append(
        f"- **Nodes Passed**: {report.passed_nodes} "
        f"({report.pass_rate:.1f}%)"
    )
    lines.append(
        f"- **Nodes Failed**: {report.failed_nodes} "
        f"({(report.failed_nodes / max(report.total_nodes, 1)) * 100:.1f}%)"
    )
    lines.append(
        f"- **Nodes Skipped**: {report.skipped_nodes} "
        f"({(report.skipped_nodes / max(report.total_nodes, 1)) * 100:.1f}%)"
    )
    lines.append("")

    # Subgraph breakdown table
    if report.subgraph_breakdown:
        lines.append("## Breakdown by Subgraph")
        lines.append("")
        lines.append("| Subgraph | Nodes | Passed | Failed | Skipped | Pass Rate |")
        lines.append("|----------|-------|--------|--------|---------|-----------|")
        for sg in report.subgraph_breakdown:
            pass_rate = f"{sg.pass_rate:.0f}%" if sg.total > 0 else "N/A"
            lines.append(
                f"| {sg.subgraph_id} | {sg.total} | {sg.passed} "
                f"| {sg.failed} | {sg.skipped} | {pass_rate} |"
            )
        lines.append("")

    # Failed nodes detail
    failed_nodes = [
        n for n in report.node_details
        if n.status == GenerationStatus.FAILED
    ]
    if failed_nodes:
        lines.append("## Failed Nodes (detail)")
        lines.append("")
        for node in failed_nodes:
            lines.append(f"### {node.node_name}")
            lines.append(f"- **Node ID**: `{node.node_id}`")
            lines.append(f"- **Subgraph**: {node.subgraph_id or 'unknown'}")
            lines.append(f"- **Retry Count**: {node.retry_count}")
            if node.failure_reason:
                lines.append(f"- **Failure Reason**: {node.failure_reason}")
            lines.append("")

    # Performance
    if report.generation_time_seconds is not None:
        lines.append("## Performance")
        lines.append("")
        minutes = report.generation_time_seconds / 60
        avg = report.generation_time_seconds / max(report.total_nodes, 1)
        lines.append(f"- **Generation Time**: {minutes:.1f} minutes")
        lines.append(f"- **Average Time per Node**: {avg:.1f} seconds")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if failed_nodes:
        lines.append(
            f"1. **Manual Fix Required**: {len(failed_nodes)} node(s) need review"
        )
    if report.skipped_nodes > 0:
        lines.append(
            f"2. **Dependency Fixes**: {report.skipped_nodes} node(s) skipped "
            f"due to upstream failures"
        )
    if report.pass_rate >= 60:
        lines.append(
            f"3. **Proceed to Phase 5**: Pass rate ({report.pass_rate:.1f}%) "
            f"meets threshold"
        )
    else:
        lines.append(
            f"3. **Re-run Generation**: Pass rate ({report.pass_rate:.1f}%) "
            f"below 60% threshold"
        )
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by ZeroRepo Phase 4: Graph-Guided Code Generation.*")
    lines.append("")

    return "\n".join(lines)
