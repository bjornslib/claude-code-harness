"""Delta report generation for baseline-aware RPG graphs.

Produces human-readable markdown reports summarizing the delta between
a baseline RPGGraph and a newly generated (enriched) RPGGraph.  Each
node is classified as NEW, EXISTING, or MODIFIED based on the
``delta_status`` metadata field (set by upstream pipeline stages).

The report includes:

1. Delta summary counts (existing / modified / new)
2. Implementation ordering for new and modified nodes
3. Dependency mapping (new nodes → existing nodes they depend on)
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cobuilder.repomap.models.enums import DeltaStatus, EdgeType, NodeLevel
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode

logger = logging.getLogger(__name__)

# Default delta status when metadata is missing
_DEFAULT_DELTA_STATUS = DeltaStatus.NEW


@dataclass(frozen=True)
class DeltaSummary:
    """Aggregated counts for a delta report.

    Attributes:
        existing: Number of nodes unchanged from baseline.
        modified: Number of nodes present in baseline but changed.
        new: Number of nodes not in baseline.
        new_edges: Number of edges in the graph (total).
        by_level: Breakdown of delta counts per :class:`NodeLevel`.
    """

    existing: int = 0
    modified: int = 0
    new: int = 0
    new_edges: int = 0
    by_level: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Total number of nodes across all statuses."""
        return self.existing + self.modified + self.new

    @property
    def actionable(self) -> int:
        """Number of nodes that require implementation (new + modified)."""
        return self.new + self.modified


@dataclass(frozen=True)
class ImplementationItem:
    """A single entry in the implementation order list.

    Attributes:
        node_id: UUID of the node.
        name: Human-readable name.
        level: Hierarchical level (MODULE / COMPONENT / FEATURE).
        delta_status: NEW or MODIFIED.
        depends_on_existing: Names of existing nodes this depends on.
        folder_path: Folder path if available.
        file_path: File path if available.
    """

    node_id: UUID
    name: str
    level: str
    delta_status: str
    depends_on_existing: list[str] = field(default_factory=list)
    folder_path: str | None = None
    file_path: str | None = None


def _get_delta_status(node: RPGNode) -> DeltaStatus:
    """Extract the delta_status from a node's metadata.

    Falls back to :data:`_DEFAULT_DELTA_STATUS` if the field is missing
    or contains an unrecognised value.

    Args:
        node: An RPGNode to inspect.

    Returns:
        The resolved DeltaStatus enum value.
    """
    raw = node.metadata.get("delta_status")
    if raw is None:
        return _DEFAULT_DELTA_STATUS
    try:
        return DeltaStatus(raw)
    except ValueError:
        logger.warning(
            "Node %s has unrecognised delta_status '%s', defaulting to %s",
            node.id,
            raw,
            _DEFAULT_DELTA_STATUS.value,
        )
        return _DEFAULT_DELTA_STATUS


class DeltaReportGenerator:
    """Generate delta reports from an RPGGraph with delta metadata.

    The generator reads ``delta_status`` from each node's metadata dict
    and produces a :class:`DeltaSummary` and a markdown report.

    Usage::

        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        report_md = gen.generate(graph)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(self, graph: RPGGraph) -> DeltaSummary:
        """Compute aggregated delta summary from graph nodes.

        Args:
            graph: The enriched RPGGraph (nodes must have
                ``metadata["delta_status"]``).

        Returns:
            A :class:`DeltaSummary` with overall and per-level counts.
        """
        counts: Counter[DeltaStatus] = Counter()
        level_counts: dict[str, Counter[DeltaStatus]] = {}

        for node in graph.nodes.values():
            status = _get_delta_status(node)
            counts[status] += 1

            level_name = node.level.value
            if level_name not in level_counts:
                level_counts[level_name] = Counter()
            level_counts[level_name][status] += 1

        by_level: dict[str, dict[str, int]] = {}
        for level_name, counter in sorted(level_counts.items()):
            by_level[level_name] = {
                "existing": counter.get(DeltaStatus.EXISTING, 0),
                "modified": counter.get(DeltaStatus.MODIFIED, 0),
                "new": counter.get(DeltaStatus.NEW, 0),
            }

        return DeltaSummary(
            existing=counts.get(DeltaStatus.EXISTING, 0),
            modified=counts.get(DeltaStatus.MODIFIED, 0),
            new=counts.get(DeltaStatus.NEW, 0),
            new_edges=graph.edge_count,
            by_level=by_level,
        )

    def implementation_order(
        self, graph: RPGGraph
    ) -> list[ImplementationItem]:
        """Compute an implementation order for new and modified nodes.

        Orders by:
        1. NODE level priority: MODULE > COMPONENT > FEATURE
        2. Modified before new (updates before creation)
        3. Alphabetical by name within each group

        For each actionable node, traces its HIERARCHY and DATA_FLOW
        edges to identify dependencies on existing nodes.

        Args:
            graph: The enriched RPGGraph.

        Returns:
            Ordered list of :class:`ImplementationItem` instances.
        """
        level_priority = {
            NodeLevel.MODULE: 0,
            NodeLevel.COMPONENT: 1,
            NodeLevel.FEATURE: 2,
        }
        status_priority = {
            DeltaStatus.MODIFIED: 0,
            DeltaStatus.NEW: 1,
        }

        # Build lookup: node_id → list of existing node names it depends on
        existing_deps = self._find_existing_dependencies(graph)

        items: list[ImplementationItem] = []
        for node in graph.nodes.values():
            status = _get_delta_status(node)
            if status == DeltaStatus.EXISTING:
                continue

            deps = existing_deps.get(node.id, [])
            items.append(
                ImplementationItem(
                    node_id=node.id,
                    name=node.name,
                    level=node.level.value,
                    delta_status=status.value,
                    depends_on_existing=deps,
                    folder_path=node.folder_path,
                    file_path=node.file_path,
                )
            )

        # Sort
        items.sort(
            key=lambda item: (
                level_priority.get(NodeLevel(item.level), 99),
                status_priority.get(DeltaStatus(item.delta_status), 99),
                item.name,
            )
        )

        return items

    def generate(
        self,
        graph: RPGGraph,
        *,
        title: str = "Delta Report",
        include_implementation_order: bool = True,
    ) -> str:
        """Generate a complete markdown delta report.

        Args:
            graph: The enriched RPGGraph with delta metadata.
            title: Report heading (default: "Delta Report").
            include_implementation_order: Whether to include the
                implementation order section.

        Returns:
            A markdown string suitable for writing to a file.
        """
        summary = self.summarize(graph)
        lines: list[str] = []

        # Header
        lines.append(f"# {title}")
        lines.append("")

        # Delta summary
        lines.append("## Delta Summary")
        lines.append("")
        lines.append(f"- **Existing (unchanged)**: {summary.existing} nodes")
        lines.append(f"- **Modified**: {summary.modified} nodes")
        lines.append(f"- **New**: {summary.new} nodes")
        lines.append(f"- **Total edges**: {summary.new_edges}")
        lines.append("")

        # Per-level breakdown
        if summary.by_level:
            lines.append("### By Level")
            lines.append("")
            lines.append("| Level | Existing | Modified | New |")
            lines.append("|-------|----------|----------|-----|")
            for level_name, counts in sorted(summary.by_level.items()):
                lines.append(
                    f"| {level_name} | {counts['existing']} "
                    f"| {counts['modified']} | {counts['new']} |"
                )
            lines.append("")

        # Implementation order
        if include_implementation_order:
            order = self.implementation_order(graph)
            if order:
                lines.append("## Implementation Order (new + modified only)")
                lines.append("")
                for i, item in enumerate(order, 1):
                    tag = item.delta_status.upper()
                    dep_str = ""
                    if item.depends_on_existing:
                        existing_names = ", ".join(
                            f"[EXISTING] {d}" for d in item.depends_on_existing
                        )
                        dep_str = f" -> depends on {existing_names}"
                    path_hint = ""
                    if item.file_path:
                        path_hint = f" ({item.file_path})"
                    elif item.folder_path:
                        path_hint = f" ({item.folder_path})"
                    lines.append(
                        f"{i}. [{tag}] {item.name}{path_hint}{dep_str}"
                    )
                lines.append("")
            else:
                lines.append("## Implementation Order")
                lines.append("")
                lines.append("_No new or modified nodes — baseline is up to date._")
                lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*Generated by ZeroRepo DeltaReportGenerator*")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_existing_dependencies(
        self, graph: RPGGraph
    ) -> dict[UUID, list[str]]:
        """For each non-existing node, find names of existing nodes it depends on.

        Traverses HIERARCHY (parent), DATA_FLOW, and INVOCATION edges.

        Args:
            graph: The RPGGraph to inspect.

        Returns:
            Mapping from node UUID to list of existing dependency names.
        """
        # Pre-compute existing node IDs
        existing_ids: set[UUID] = set()
        for node in graph.nodes.values():
            if _get_delta_status(node) == DeltaStatus.EXISTING:
                existing_ids.add(node.id)

        # Pre-compute: for each node, which existing nodes does it
        # connect to via edges where it is the source
        deps: dict[UUID, list[str]] = {}
        for edge in graph.edges.values():
            if edge.edge_type in (
                EdgeType.DATA_FLOW,
                EdgeType.INVOCATION,
                EdgeType.HIERARCHY,
            ):
                source = graph.get_node(edge.source_id)
                target = graph.get_node(edge.target_id)
                if source is None or target is None:
                    continue

                # If source is actionable and target is existing
                if (
                    edge.source_id not in existing_ids
                    and edge.target_id in existing_ids
                ):
                    deps.setdefault(edge.source_id, [])
                    if target.name not in deps[edge.source_id]:
                        deps[edge.source_id].append(target.name)

                # Also check reverse: if target is actionable and source
                # is existing (e.g. existing node invokes this new one
                # via HIERARCHY parent)
                if (
                    edge.target_id not in existing_ids
                    and edge.source_id in existing_ids
                    and edge.edge_type == EdgeType.HIERARCHY
                ):
                    deps.setdefault(edge.target_id, [])
                    if source.name not in deps[edge.target_id]:
                        deps[edge.target_id].append(source.name)

        return deps
