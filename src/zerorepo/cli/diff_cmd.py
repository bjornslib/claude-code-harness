"""ZeroRepo ``diff`` command — Regression Detection between RPGGraph baselines.

Compares two RPGGraph JSON files (before/after a code change) to detect regressions:
nodes that were EXISTING in the baseline but have become MODIFIED or NEW in the
updated graph.  Optionally filters to only nodes whose ``file_path`` appears inside
an Attractor pipeline ``.dot`` file (the "in-scope" filter).

Output is a simplified DOT graph listing the regressed nodes as red-filled boxes,
suitable for human review and guardian escalation.

Usage::

    zerorepo diff before.json after.json
    zerorepo diff before.json after.json --pipeline codergen.dot
    zerorepo diff before.json after.json --output regression-check.dot
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)

_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------


class RegressionResult:
    """Holds the regression analysis results between two graphs.

    Attributes:
        regressions: Nodes that were EXISTING in ``before`` but are MODIFIED
            or NEW in ``after``.
        unexpected_new: Nodes that appear in ``after`` but have no matching
            name in ``before`` at all (completely new, unexpected components).
        in_scope_filter: If a pipeline was provided, the set of file paths
            that are in-scope for the diff (empty = no filter applied).
    """

    def __init__(
        self,
        regressions: list[RPGNode],
        unexpected_new: list[RPGNode],
        in_scope_filter: set[str],
    ) -> None:
        self.regressions = regressions
        self.unexpected_new = unexpected_new
        self.in_scope_filter = in_scope_filter

    @property
    def has_regressions(self) -> bool:
        """Return True if any regressions or unexpected nodes were found."""
        return bool(self.regressions or self.unexpected_new)

    @property
    def total_count(self) -> int:
        """Total number of problematic nodes."""
        return len(self.regressions) + len(self.unexpected_new)


def _load_graph(path: Path) -> RPGGraph:
    """Load an RPGGraph from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed RPGGraph instance.

    Raises:
        typer.BadParameter: If the file does not exist or is not valid JSON.
    """
    if not path.exists():
        raise typer.BadParameter(f"Baseline file not found: {path}")
    try:
        return RPGGraph.from_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise typer.BadParameter(
            f"Failed to parse baseline '{path}': {exc}"
        ) from exc


def _extract_pipeline_file_paths(dot_path: Path) -> set[str]:
    """Extract ``file_path`` attribute values from codergen nodes in a DOT file.

    Only nodes with ``handler="codergen"`` (i.e., implementation nodes) are
    considered.  This mirrors the in-scope filter described in the PRD.

    Args:
        dot_path: Path to the Attractor ``.dot`` file.

    Returns:
        Set of ``file_path`` strings found in codergen nodes.  Empty set if
        the file does not contain any codergen nodes or if parsing fails.
    """
    if not dot_path.exists():
        logger.warning("Pipeline DOT file not found: %s", dot_path)
        return set()

    content = dot_path.read_text(encoding="utf-8")

    # We look for node blocks that contain handler="codergen" and file_path=...
    # Strategy: find all attribute blocks (sequences of key="value" pairs) that
    # include handler="codergen", then extract file_path from the same block.
    in_scope: set[str] = set()

    # Split into individual node/edge definition lines (between [ ... ])
    node_block_pattern = re.compile(
        r"\[([^\]]*)\]",
        re.DOTALL,
    )
    for block_match in node_block_pattern.finditer(content):
        block = block_match.group(1)
        if 'handler="codergen"' not in block:
            continue
        fp_match = re.search(r'file_path="([^"]+)"', block)
        if fp_match:
            in_scope.add(fp_match.group(1))

    logger.debug(
        "Extracted %d in-scope file paths from pipeline '%s'",
        len(in_scope),
        dot_path,
    )
    return in_scope


def compare_graphs(
    before: RPGGraph,
    after: RPGGraph,
    in_scope_paths: set[str] | None = None,
) -> RegressionResult:
    """Compare two RPGGraphs and return regression information.

    A **regression** is a node whose ``metadata["delta_status"]`` was
    ``"existing"`` in ``before`` and is ``"modified"`` or ``"new"`` in
    ``after``.  This indicates a component that the model previously
    considered stable has now been flagged as changed.

    An **unexpected new** node is one that exists (by name) in ``after``
    but has no corresponding entry in ``before`` at all — suggesting a
    wholly new component was introduced outside the expected plan.

    Args:
        before: The baseline RPGGraph from before the code change.
        after: The updated RPGGraph after the code change.
        in_scope_paths: Optional set of ``file_path`` values to restrict the
            comparison to.  When provided, only nodes whose ``file_path`` is
            in the set are considered.  Pass ``None`` or an empty set to
            disable filtering.

    Returns:
        A :class:`RegressionResult` with the found regressions and metadata.
    """
    # Build name → node maps (use last-seen node if duplicate names exist)
    before_by_name: dict[str, RPGNode] = {
        node.name: node for node in before.nodes.values()
    }
    after_by_name: dict[str, RPGNode] = {
        node.name: node for node in after.nodes.values()
    }

    use_filter = bool(in_scope_paths)
    effective_filter = in_scope_paths or set()

    regressions: list[RPGNode] = []
    unexpected_new: list[RPGNode] = []

    for name, after_node in after_by_name.items():
        # Apply in-scope filter when pipeline was provided
        if use_filter:
            node_fp = after_node.file_path or ""
            if node_fp not in effective_filter:
                continue

        after_status = after_node.metadata.get("delta_status", "")

        if name in before_by_name:
            before_node = before_by_name[name]
            before_status = before_node.metadata.get("delta_status", "")

            # Regression: was stable (existing), now changed (modified/new)
            if before_status == "existing" and after_status in ("modified", "new"):
                regressions.append(after_node)
        else:
            # Completely new in "after" — unexpected component
            if after_status in ("new", "modified"):
                unexpected_new.append(after_node)

    return RegressionResult(
        regressions=regressions,
        unexpected_new=unexpected_new,
        in_scope_filter=effective_filter,
    )


# ---------------------------------------------------------------------------
# DOT output generation
# ---------------------------------------------------------------------------


def _sanitize_dot_id(name: str) -> str:
    """Convert a node name to a valid DOT identifier."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_").lower()
    if not sanitized:
        return "unnamed"
    if sanitized[0].isdigit():
        sanitized = f"n_{sanitized}"
    return sanitized


def generate_regression_dot(result: RegressionResult, label: str = "") -> str:
    """Generate a simple DOT digraph listing regression nodes.

    Uses red-filled box nodes — one per regression, one per unexpected new
    node.  No edges are emitted; this is a list-style visualization.

    Args:
        result: The regression comparison result.
        label: Optional graph label (e.g. PRD reference).

    Returns:
        DOT string ready to write to a ``.dot`` file.
    """
    lines: list[str] = []
    graph_label = label or "ZeroRepo Regression Check"
    lines.append(f'digraph "regression_check" {{')
    lines.append(f'    label="{graph_label}";')
    lines.append('    rankdir="TB";')
    lines.append('    node [shape=box, style=filled, fillcolor=red, fontcolor=white];')
    lines.append("")

    if not result.has_regressions:
        lines.append(
            '    no_regressions [label="No regressions detected", '
            'fillcolor=lightgreen, fontcolor=black];'
        )
        lines.append("}")
        return "\n".join(lines)

    # Regression nodes (were existing, now changed)
    if result.regressions:
        lines.append("    // Regressions: were EXISTING, now MODIFIED or NEW")
        for node in result.regressions:
            node_id = _sanitize_dot_id(node.name)
            status = node.metadata.get("delta_status", "unknown")
            fp = node.file_path or ""
            label_text = f"{node.name}\\n[was: existing → now: {status}]"
            if fp:
                label_text += f"\\n{fp}"
            lines.append(
                f'    {node_id} ['
                f'label="{label_text}", '
                f'regression_type="status_change", '
                f'delta_status="{status}", '
                f'file_path="{fp}"'
                f"];"
            )
        lines.append("")

    # Unexpected new nodes (not present in before at all)
    if result.unexpected_new:
        lines.append(
            "    // Unexpected new nodes: present in after but not in before"
        )
        for node in result.unexpected_new:
            node_id = _sanitize_dot_id(node.name)
            fp = node.file_path or ""
            label_text = f"{node.name}\\n[unexpected new component]"
            if fp:
                label_text += f"\\n{fp}"
            lines.append(
                f'    {node_id} ['
                f'label="{label_text}", '
                f'regression_type="unexpected_new", '
                f'delta_status="new", '
                f'file_path="{fp}"'
                f"];"
            )

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def run_diff(
    before_path: Path,
    after_path: Path,
    pipeline_path: Optional[Path],
    output_path: Optional[Path],
    console: Console,
) -> RegressionResult:
    """Execute the diff workflow and write output.

    Args:
        before_path: Path to the "before" RPGGraph JSON.
        after_path: Path to the "after" RPGGraph JSON.
        pipeline_path: Optional path to an Attractor ``.dot`` pipeline for
            in-scope filtering.
        output_path: Optional path to write the regression DOT output.
        console: Rich console for status messages.

    Returns:
        The :class:`RegressionResult` from the comparison.
    """
    console.print(f"[bold]Loading baseline:[/bold] {before_path}")
    before_graph = _load_graph(before_path)
    console.print(
        f"  [dim]{before_graph.node_count} nodes, {before_graph.edge_count} edges[/dim]"
    )

    console.print(f"[bold]Loading updated graph:[/bold] {after_path}")
    after_graph = _load_graph(after_path)
    console.print(
        f"  [dim]{after_graph.node_count} nodes, {after_graph.edge_count} edges[/dim]"
    )

    # Pipeline in-scope filter
    in_scope: set[str] | None = None
    if pipeline_path is not None:
        console.print(f"[bold]Extracting in-scope paths from pipeline:[/bold] {pipeline_path}")
        in_scope = _extract_pipeline_file_paths(pipeline_path)
        if in_scope:
            console.print(f"  [dim]{len(in_scope)} file paths in scope[/dim]")
        else:
            console.print(
                "  [yellow]No codergen nodes with file_path found in pipeline; "
                "no scope filter applied.[/yellow]"
            )
            in_scope = None

    # Run comparison
    console.print("[bold]Comparing graphs...[/bold]")
    result = compare_graphs(before_graph, after_graph, in_scope_paths=in_scope)

    # Report
    if result.has_regressions:
        console.print(
            f"\n[bold red]Regressions detected: {result.total_count} node(s)[/bold red]"
        )
        if result.regressions:
            console.print(
                f"  Status-change regressions: {len(result.regressions)}"
            )
            for node in result.regressions:
                fp = f" ({node.file_path})" if node.file_path else ""
                console.print(
                    f"    • [red]{node.name}[/red]{fp}: "
                    f"existing → {node.metadata.get('delta_status', '?')}"
                )
        if result.unexpected_new:
            console.print(
                f"  Unexpected new nodes: {len(result.unexpected_new)}"
            )
            for node in result.unexpected_new:
                fp = f" ({node.file_path})" if node.file_path else ""
                console.print(f"    • [yellow]{node.name}[/yellow]{fp}")
    else:
        console.print("\n[bold green]No regressions detected.[/bold green]")

    # Generate DOT output
    dot_content = generate_regression_dot(result)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dot_content, encoding="utf-8")
        console.print(f"\n[green]Regression DOT written to:[/green] {output_path}")
    else:
        # Print to stdout
        from rich.console import Console as RichConsole

        out = RichConsole()
        out.print(dot_content)

    return result
