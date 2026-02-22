"""Attractor DOT Pipeline Exporter for RPGGraph Delta Reports.

Transforms an :class:`~zerorepo.models.graph.RPGGraph`'s delta-annotated nodes
into an Attractor-compatible pipeline ``.dot`` graph.  Only nodes whose
``metadata["delta_status"]`` is ``"new"`` or ``"modified"`` are included;
``"existing"`` nodes are silently skipped.

Spec: PRD-S3-DOT-LIFECYCLE-001, Epic 1

Delta → DOT mapping
-------------------
+---------------------+------------------+------------+-----------+
| Delta Classification| DOT Node         | Shape      | Handler   |
+=====================+==================+============+===========+
| EXISTING            | (skipped)        | —          | —         |
| MODIFIED            | Implementation   | box        | codergen  |
| NEW                 | Implementation   | box        | codergen  |
| (auto)              | Tech validation  | hexagon    | wait.human|
| (auto)              | Biz validation   | hexagon    | wait.human|
| (auto)              | Decision         | diamond    | conditional|
+---------------------+------------------+------------+-----------+

Graph structure (for N MODIFIED/NEW nodes)
------------------------------------------
If the nodes have no RPG dependency edges between them (independent):

    start (Mdiamond)
      └─► parallel_start (parallelogram)
            ├─► impl_A (box/codergen) → val_A_tech → val_A_biz → decision_A
            │                                                    ├─pass──► join_validation
            │                                                    └─fail──► impl_A (retry)
            └─► impl_B (box/codergen) → val_B_tech → val_B_biz → decision_B
                                                                 ├─pass──► join_validation
                                                                 └─fail──► impl_B (retry)
          join_validation (parallelogram)
            └─► finalize (Msquare)

If there ARE dependency edges (topological order respected):

    start → impl_A → val_A_tech → val_A_biz → decision_A
                                               ├─pass──► impl_B
                                               └─fail──► impl_A
              impl_B → val_B_tech → val_B_biz → decision_B
                                               ├─pass──► finalize
                                               └─fail──► impl_B

Usage::

    from zerorepo.graph_construction.attractor_exporter import AttractorExporter
    from zerorepo.models.graph import RPGGraph

    exporter = AttractorExporter(prd_ref="PRD-S3-DOT-LIFECYCLE-001")
    dot_str = exporter.export(rpg_graph)
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any
from uuid import UUID

from zerorepo.models.enums import DeltaStatus, EdgeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Attractor worker types inferred from file/folder paths (PRD R1.7).
_WORKER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(components?/|pages?/|\.tsx?$|\.jsx?$|\.vue$)"),
        "frontend-dev-expert",
    ),
    (
        re.compile(r"(tests?/|test_|_test\.py|\.test\.|\.spec\.)"),
        "tdd-test-engineer",
    ),
    (
        re.compile(r"(api/|models?/|schemas?/|routes?/|\.py$)"),
        "backend-solutions-engineer",
    ),
]

_STATUS_COLORS: dict[str, str] = {
    "pending": "lightyellow",
    "active": "lightblue",
    "impl_complete": "lightsalmon",
    "validated": "lightgreen",
    "failed": "lightcoral",
}

#: Delta status values that map to actionable pipeline nodes.
_ACTIONABLE_STATUSES = frozenset(
    {
        DeltaStatus.MODIFIED.value,
        DeltaStatus.NEW.value,
        "modified",  # plain strings, just in case
        "new",
    }
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def infer_worker_type(node: RPGNode) -> str:
    """Infer Attractor ``worker_type`` from an :class:`RPGNode`'s paths.

    Priority order (PRD-S3-DOT-LIFECYCLE-001 R1.7):

    1. ``frontend-dev-expert``  — components/, pages/, .tsx, .jsx, .vue
    2. ``tdd-test-engineer``    — tests/, .test., .spec., test_*
    3. ``backend-solutions-engineer`` — api/, models/, .py (non-test)
    4. ``backend-solutions-engineer`` — default (mixed or unclear)

    Args:
        node: The RPGNode to inspect.

    Returns:
        One of the four valid Attractor worker type strings.
    """
    path = " ".join(
        filter(None, [node.file_path, node.folder_path, node.name])
    ).lower()
    for pattern, worker_type in _WORKER_PATTERNS:
        if pattern.search(path):
            return worker_type
    return "backend-solutions-engineer"


def _sanitize_id(text: str) -> str:
    """Convert arbitrary text into a valid DOT node identifier.

    Replaces non-alphanumeric characters with underscores, collapses
    consecutive underscores, strips leading/trailing underscores, and
    prepends ``n_`` if the result begins with a digit.
    """
    text = re.sub(r"[^a-zA-Z0-9_]", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    if text and text[0].isdigit():
        text = "n_" + text
    return text.lower() if text else "unnamed"


def _esc(text: str) -> str:
    """Escape a string for use in a DOT double-quoted attribute value."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _wrap(text: str, width: int = 35, max_lines: int = 3) -> str:
    """Word-wrap *text* for a DOT node label (``\\n``-separated lines)."""
    text = text.replace('"', '\\"')
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            if current:
                lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return "\\n".join(lines[:max_lines])


# ---------------------------------------------------------------------------
# AttractorExporter
# ---------------------------------------------------------------------------


class AttractorExporter:
    """Converts an RPGGraph delta into an Attractor-compatible DOT pipeline.

    Each MODIFIED/NEW node generates a *triplet*::

        codergen (box)
            → tech-validation (hexagon, wait.human, gate=technical)
            → biz-validation  (hexagon, wait.human, gate=business)
            → decision (diamond, conditional)
                ──pass──► next stage / finalize
                ──fail──► codergen (allowed retry loop)

    Pipeline bookends are always emitted:

    * ``start`` — ``Mdiamond``, handler=start, status=validated
    * ``finalize`` — ``Msquare``, handler=exit, status=pending

    When nodes share RPG dependency edges the layout is *sequential* (topo
    order preserved).  When nodes are mutually independent a *parallel*
    fan-out/fan-in is used.

    Args:
        prd_ref: PRD reference string (e.g. ``"PRD-S3-DOT-LIFECYCLE-001"``).
        promise_id: Optional completion-promise ID (populated later by
            ``attractor init-promise``).
        label: Human-readable graph title (defaults to ``"Initiative: {prd_ref}"``).
    """

    def __init__(
        self,
        prd_ref: str = "",
        promise_id: str = "",
        label: str = "",
    ) -> None:
        self._prd_ref = prd_ref or "PRD-UNKNOWN"
        self._promise_id = promise_id
        self._label = label or f"Initiative: {self._prd_ref}"

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def export(self, rpg: RPGGraph) -> str:
        """Generate an Attractor-compatible DOT string from *rpg*.

        Args:
            rpg: An :class:`~zerorepo.models.graph.RPGGraph` whose nodes carry
                ``metadata["delta_status"]`` values (``"new"`` / ``"modified"``
                / ``"existing"``).

        Returns:
            A valid Attractor DOT string ready for ``attractor validate``.
        """
        # 1. Collect actionable nodes
        actionable = self._collect_actionable(rpg)
        if not actionable:
            logger.warning(
                "AttractorExporter: no MODIFIED or NEW nodes found in RPGGraph; "
                "generating minimal placeholder pipeline for prd_ref=%s",
                self._prd_ref,
            )

        # 2. Build dependency adjacency between actionable nodes only
        dep_adj = self._build_dep_adj(rpg, actionable)

        # 3. Topological sort for stable output
        ordered = self._topo_sort(actionable, dep_adj)

        # 4. Use parallel layout when all nodes are mutually independent
        use_parallel = bool(ordered) and len(ordered) > 1 and not dep_adj

        # 5. Render
        return self._render(ordered, use_parallel)

    # -------------------------------------------------------------------
    # Collection
    # -------------------------------------------------------------------

    def _collect_actionable(self, rpg: RPGGraph) -> list[RPGNode]:
        """Return only MODIFIED and NEW nodes; silently skip EXISTING."""
        result: list[RPGNode] = []
        for node in rpg.nodes.values():
            ds = node.metadata.get("delta_status", "")
            if ds in _ACTIONABLE_STATUSES:
                result.append(node)
        return result

    def _build_dep_adj(
        self,
        rpg: RPGGraph,
        actionable: list[RPGNode],
    ) -> dict[UUID, list[UUID]]:
        """Build a dependency adjacency list limited to *actionable* nodes.

        Only DATA_FLOW, ORDERING, and INVOCATION edge types are included
        (HIERARCHY edges represent parent–child containment, not execution
        ordering).

        Returns:
            ``{source_uuid: [target_uuid, ...]}``
        """
        ids = {n.id for n in actionable}
        dep_types = {EdgeType.DATA_FLOW, EdgeType.ORDERING, EdgeType.INVOCATION}
        adj: dict[UUID, list[UUID]] = defaultdict(list)
        for edge in rpg.edges.values():
            if (
                edge.edge_type in dep_types
                and edge.source_id in ids
                and edge.target_id in ids
            ):
                adj[edge.source_id].append(edge.target_id)
        return dict(adj)

    def _topo_sort(
        self,
        nodes: list[RPGNode],
        adj: dict[UUID, list[UUID]],
    ) -> list[RPGNode]:
        """Topological sort via Kahn's algorithm.

        Any nodes involved in a cycle (shouldn't happen in acyclic RPGs) are
        appended at the end to guarantee all nodes appear in output.
        """
        if not nodes:
            return []
        node_map = {n.id: n for n in nodes}
        in_deg: dict[UUID, int] = {n.id: 0 for n in nodes}
        for targets in adj.values():
            for t in targets:
                if t in in_deg:
                    in_deg[t] += 1

        queue = [nid for nid, d in in_deg.items() if d == 0]
        result: list[RPGNode] = []
        while queue:
            nid = queue.pop(0)
            result.append(node_map[nid])
            for t in adj.get(nid, []):
                in_deg[t] -= 1
                if in_deg[t] == 0:
                    queue.append(t)

        # Append cycle survivors (defensive)
        seen = {n.id for n in result}
        for n in nodes:
            if n.id not in seen:
                result.append(n)
        return result

    # -------------------------------------------------------------------
    # DOT rendering
    # -------------------------------------------------------------------

    def _render(self, nodes: list[RPGNode], use_parallel: bool) -> str:
        L: list[str] = []  # lines accumulator

        # ── Graph envelope ──────────────────────────────────────────────
        L.append(f'digraph "{_esc(self._prd_ref)}" {{')
        L.append("    graph [")
        L.append(f'        label="{_esc(self._label)}"')
        L.append('        labelloc="t"')
        L.append("        fontsize=16")
        L.append('        rankdir="TB"')
        L.append(f'        prd_ref="{_esc(self._prd_ref)}"')
        L.append(f'        promise_id="{_esc(self._promise_id)}"')
        L.append("    ];")
        L.append("")
        L.append('    node [fontname="Helvetica" fontsize=11];')
        L.append('    edge [fontname="Helvetica" fontsize=9];')
        L.append("")

        # ── Start node (Mdiamond) ───────────────────────────────────────
        L.append("    // ===== START =====")
        L.append("")
        L.append("    start [")
        L.append("        shape=Mdiamond")
        L.append(f'        label="START\\n{_esc(self._prd_ref)}"')
        L.append('        handler="start"')
        L.append('        status="validated"')
        L.append("        style=filled")
        L.append("        fillcolor=lightgreen")
        L.append("    ];")
        L.append("")

        if not nodes:
            # ── Minimal placeholder pipeline ────────────────────────────
            L.append("    // No MODIFIED/NEW nodes — placeholder pipeline")
            L.append("")
            self._emit_placeholder(L)
        else:
            # ── Real implementation nodes ───────────────────────────────
            L.append("    // ===== EXECUTE =====")
            L.append("")

            # Build per-task metadata
            tasks = self._build_task_meta(nodes)

            if use_parallel:
                self._emit_parallel_fanout(L, tasks)
            else:
                # Sequential: first impl connects directly from start
                pass

            # Emit node triplets
            for i, task in enumerate(tasks):
                self._emit_triplet(L, task, i, use_parallel, is_first=(i == 0))

            # Wire pass edges
            if use_parallel:
                self._emit_parallel_fanin(L, tasks)
            else:
                self._emit_sequential_pass_edges(L, tasks)

        # ── Finalize node (Msquare) ─────────────────────────────────────
        L.append("")
        L.append("    // ===== FINALIZE =====")
        L.append("")
        L.append("    finalize [")
        L.append("        shape=Msquare")
        L.append(f'        label="FINALIZE\\n{_esc(self._prd_ref)}\\ncs-verify"')
        L.append('        handler="exit"')
        L.append(f'        promise_id="{_esc(self._promise_id)}"')
        if nodes:
            L.append(f'        promise_ac="AC-{len(nodes)}"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append("}")
        L.append("")

        return "\n".join(L)

    # -------------------------------------------------------------------
    # Task metadata construction
    # -------------------------------------------------------------------

    def _build_task_meta(self, nodes: list[RPGNode]) -> list[dict[str, Any]]:
        """Build a metadata dict for each node (used during rendering)."""
        tasks: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for i, node in enumerate(nodes):
            base_id = f"impl_{_sanitize_id(node.name)}"
            node_id = base_id
            # Guarantee uniqueness
            if node_id in seen_ids:
                node_id = f"{base_id}_{_sanitize_id(str(node.id))[:8]}"
            seen_ids.add(node_id)

            delta = node.metadata.get("delta_status", "new")
            bead_id = node.metadata.get("bead_id", "UNASSIGNED")
            acceptance = (
                node.metadata.get("acceptance", "")
                or node.docstring
                or ""
            )
            file_path = node.file_path or node.folder_path or ""
            worker_type = infer_worker_type(node)

            tasks.append(
                {
                    "node_id": node_id,
                    "name": node.name,
                    "worker_type": worker_type,
                    "bead_id": str(bead_id),
                    "acceptance": acceptance,
                    "file_path": file_path,
                    "promise_ac": f"AC-{i + 1}",
                    "delta": str(delta).lower(),
                    "rpg_id": str(node.id),
                    # Filled in during emit
                    "val_tech_id": f"val_{_sanitize_id(node.name)}_tech",
                    "val_biz_id": f"val_{_sanitize_id(node.name)}_biz",
                    "decision_id": f"decision_{_sanitize_id(node.name)}",
                }
            )
        return tasks

    # -------------------------------------------------------------------
    # Parallel fan-out / fan-in
    # -------------------------------------------------------------------

    def _emit_parallel_fanout(
        self, L: list[str], tasks: list[dict[str, Any]]
    ) -> None:
        """Emit the ``parallel_start`` parallelogram and its edge from start."""
        task_labels = [_wrap(t["name"], 20) for t in tasks[:3]]
        par_label = "Parallel:\\n" + " + ".join(task_labels)
        if len(tasks) > 3:
            par_label += f" +{len(tasks) - 3} more"

        L.append("    // --- Parallel fan-out ---")
        L.append("")
        L.append("    parallel_start [")
        L.append("        shape=parallelogram")
        L.append(f'        label="{par_label}"')
        L.append('        handler="parallel"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append('    start -> parallel_start [label="begin"];')
        L.append("")

    def _emit_parallel_fanin(
        self, L: list[str], tasks: list[dict[str, Any]]
    ) -> None:
        """Emit ``join_validation`` and its edge to finalize."""
        L.append("    // --- Parallel fan-in ---")
        L.append("")
        L.append("    join_validation [")
        L.append("        shape=parallelogram")
        L.append('        label="Join:\\nAll Streams\\nValidated"')
        L.append('        handler="parallel"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append('    join_validation -> finalize [label="all pass" style=bold];')
        L.append("")

    # -------------------------------------------------------------------
    # Sequential pass-edge wiring
    # -------------------------------------------------------------------

    def _emit_sequential_pass_edges(
        self, L: list[str], tasks: list[dict[str, Any]]
    ) -> None:
        """Wire sequential pass edges: decision_i → impl_{i+1} or finalize."""
        for i, task in enumerate(tasks):
            dec_id = task["decision_id"]
            if i < len(tasks) - 1:
                dst = tasks[i + 1]["node_id"]
            else:
                dst = "finalize"
            L.append(f"    {dec_id} -> {dst} [")
            L.append('        label="pass"')
            L.append('        condition="pass"')
            L.append("        color=green")
            L.append("    ];")
            L.append("")

    # -------------------------------------------------------------------
    # Node triplet: codergen → tech_hex → biz_hex → diamond
    # -------------------------------------------------------------------

    def _emit_triplet(
        self,
        L: list[str],
        task: dict[str, Any],
        index: int,
        use_parallel: bool,
        is_first: bool,
    ) -> None:
        """Emit the codergen→hexagon×2→diamond triplet for one task."""
        nid = task["node_id"]
        name = task["name"]
        worker = task["worker_type"]
        bead_id = task["bead_id"]
        acceptance = task["acceptance"]
        file_path = task["file_path"]
        promise_ac = task["promise_ac"]
        delta = task["delta"]
        rpg_id = task["rpg_id"]
        val_tech_id = task["val_tech_id"]
        val_biz_id = task["val_biz_id"]
        dec_id = task["decision_id"]

        label = _wrap(name)
        short = _wrap(name, 15)

        # ── codergen (implementation node) ─────────────────────────────
        L.append(f"    // --- [{delta.upper()}] {name[:60]} ---")
        L.append("")
        L.append(f"    {nid} [")
        L.append("        shape=box")
        L.append(f'        label="{label}"')
        L.append('        handler="codergen"')
        L.append(f'        bead_id="{_esc(bead_id)}"')
        L.append(f'        worker_type="{worker}"')
        if acceptance:
            L.append(f'        acceptance="{_esc(acceptance[:120])}"')
        if file_path:
            L.append(f'        file_path="{_esc(file_path)}"')
        L.append(f'        promise_ac="{promise_ac}"')
        L.append(f'        prd_ref="{_esc(self._prd_ref)}"')
        L.append(f'        rpg_node_id="{rpg_id}"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")

        # Incoming edge
        if use_parallel:
            L.append(f"    parallel_start -> {nid} [color=blue style=bold];")
        elif is_first:
            L.append(f'    start -> {nid} [label="begin"];')
        # non-first sequential nodes receive their incoming edge via
        # _emit_sequential_pass_edges (decision_prev → nid)
        L.append("")

        # ── Technical validation hexagon ────────────────────────────────
        L.append(f"    {val_tech_id} [")
        L.append("        shape=hexagon")
        L.append(f'        label="{short}\\nTechnical\\nValidation"')
        L.append('        handler="wait.human"')
        L.append('        gate="technical"')
        L.append('        mode="technical"')
        L.append(f'        bead_id="AT-{_sanitize_id(bead_id)}-TECH"')
        L.append(f'        promise_ac="{promise_ac}"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append(f'    {nid} -> {val_tech_id} [label="impl_complete"];')
        L.append("")

        # ── Business validation hexagon ─────────────────────────────────
        L.append(f"    {val_biz_id} [")
        L.append("        shape=hexagon")
        L.append(f'        label="{short}\\nBusiness\\nValidation"')
        L.append('        handler="wait.human"')
        L.append('        gate="business"')
        L.append('        mode="business"')
        L.append(f'        bead_id="AT-{_sanitize_id(bead_id)}-BIZ"')
        L.append(f'        promise_ac="{promise_ac}"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append(f'    {val_tech_id} -> {val_biz_id} [label="tech pass"];')
        L.append("")

        # ── Conditional diamond ─────────────────────────────────────────
        L.append(f"    {dec_id} [")
        L.append("        shape=diamond")
        L.append(f'        label="{short}\\nResult?"')
        L.append('        handler="conditional"')
        L.append("    ];")
        L.append("")
        L.append(f"    {val_biz_id} -> {dec_id};")
        L.append("")

        # Pass edge (parallel only — sequential wired by _emit_sequential_pass_edges)
        if use_parallel:
            L.append(f"    {dec_id} -> join_validation [")
            L.append('        label="pass"')
            L.append('        condition="pass"')
            L.append("        color=green")
            L.append("    ];")
            L.append("")

        # Fail edge (always → retry; allowed cycle per validator rule 9)
        L.append(f"    {dec_id} -> {nid} [")
        L.append('        label="fail\\nretry"')
        L.append('        condition="fail"')
        L.append("        color=red")
        L.append("        style=dashed")
        L.append("    ];")
        L.append("")

    # -------------------------------------------------------------------
    # Placeholder helpers (when no actionable nodes)
    # -------------------------------------------------------------------

    def _emit_placeholder(self, L: list[str]) -> None:
        """Emit a minimal valid placeholder pipeline (1 codergen triplet)."""
        L.append("    impl_placeholder [")
        L.append("        shape=box")
        L.append('        label="Placeholder\\nTask"')
        L.append('        handler="codergen"')
        L.append('        bead_id="UNASSIGNED"')
        L.append('        worker_type="backend-solutions-engineer"')
        L.append(f'        prd_ref="{_esc(self._prd_ref)}"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append("    val_placeholder_tech [")
        L.append("        shape=hexagon")
        L.append('        label="Placeholder\\nTechnical\\nValidation"')
        L.append('        handler="wait.human"')
        L.append('        gate="technical"')
        L.append('        mode="technical"')
        L.append('        bead_id="AT-PLACEHOLDER-TECH"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append("    val_placeholder_biz [")
        L.append("        shape=hexagon")
        L.append('        label="Placeholder\\nBusiness\\nValidation"')
        L.append('        handler="wait.human"')
        L.append('        gate="business"')
        L.append('        mode="business"')
        L.append('        bead_id="AT-PLACEHOLDER-BIZ"')
        L.append('        status="pending"')
        L.append("        style=filled")
        L.append("        fillcolor=lightyellow")
        L.append("    ];")
        L.append("")
        L.append("    decision_placeholder [")
        L.append("        shape=diamond")
        L.append('        label="Placeholder\\nResult?"')
        L.append('        handler="conditional"')
        L.append("    ];")
        L.append("")
        L.append('    start -> impl_placeholder [label="begin"];')
        L.append(
            '    impl_placeholder -> val_placeholder_tech [label="impl_complete"];'
        )
        L.append(
            '    val_placeholder_tech -> val_placeholder_biz [label="tech pass"];'
        )
        L.append("    val_placeholder_biz -> decision_placeholder;")
        L.append("    decision_placeholder -> finalize [")
        L.append('        label="pass"')
        L.append('        condition="pass"')
        L.append("        color=green")
        L.append("    ];")
        L.append("    decision_placeholder -> impl_placeholder [")
        L.append('        label="fail\\nretry"')
        L.append('        condition="fail"')
        L.append("        color=red")
        L.append("        style=dashed")
        L.append("    ];")
        L.append("")
