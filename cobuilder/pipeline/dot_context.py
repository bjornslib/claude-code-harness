"""DOT pipeline context extractor for TaskMaster enrichment."""

from pathlib import Path

from cobuilder.pipeline.parser import parse_dot


def get_pipeline_context(dot_pipeline_path: str) -> str:
    """Extract human-readable context from a DOT pipeline file.

    Returns empty string if file does not exist or cannot be parsed.
    Returns a structured markdown/text block describing:
    - Graph metadata (prd_ref, promise_id, label)
    - Node inventory grouped by status (pending/active/validated)
    - Handler type distribution
    - Key pending tasks (the actionable ones for TaskMaster)

    Args:
        dot_pipeline_path: Path to the .dot pipeline file.

    Returns:
        A structured context string, or "" on missing/invalid input.
    """
    path = Path(dot_pipeline_path)
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8")
        data = parse_dot(content)
    except Exception:
        return ""

    graph_attrs = data.get("graph_attrs", {})
    nodes = data.get("nodes", [])

    # --- Graph metadata ---
    prd_ref = graph_attrs.get("prd_ref", "")
    label = graph_attrs.get("label", "")
    promise_id = graph_attrs.get("promise_id", "")

    lines = ["### Pipeline Overview"]
    if prd_ref:
        lines.append(f"- **PRD Reference**: {prd_ref}")
    if label:
        lines.append(f"- **Label**: {label}")
    if promise_id:
        lines.append(f"- **Promise ID**: {promise_id}")
    lines.append(f"- **Total nodes**: {len(nodes)}")
    lines.append("")

    # --- Group nodes by status ---
    by_status: dict[str, list[dict]] = {}
    for node in nodes:
        status = node["attrs"].get("status", "pending")
        by_status.setdefault(status, []).append(node)

    # --- Handler type distribution ---
    handler_counts: dict[str, int] = {}
    for node in nodes:
        handler = node["attrs"].get("handler", "unknown")
        handler_counts[handler] = handler_counts.get(handler, 0) + 1

    if handler_counts:
        lines.append("### Handler Distribution")
        for handler, count in sorted(handler_counts.items()):
            lines.append(f"- {handler}: {count}")
        lines.append("")

    # --- Node inventory by status ---
    lines.append("### Node Inventory by Status")

    for status in ("pending", "active", "impl_complete", "validated", "failed"):
        status_nodes = by_status.get(status, [])
        if not status_nodes:
            continue
        lines.append(f"\n**{status.upper()}** ({len(status_nodes)} nodes):")
        for node in status_nodes:
            node_id = node["id"]
            attrs = node["attrs"]
            node_label = attrs.get("label", node_id)
            bead_id = attrs.get("bead_id", "")
            handler = attrs.get("handler", "")
            parts = [f"  - `{node_id}`: {node_label}"]
            if handler:
                parts.append(f"(handler: {handler})")
            if bead_id:
                parts.append(f"[bead: {bead_id}]")
            lines.append(" ".join(parts))

    # Catch any other statuses not in the predefined list
    for status, status_nodes in sorted(by_status.items()):
        if status in ("pending", "active", "impl_complete", "validated", "failed"):
            continue
        lines.append(f"\n**{status.upper()}** ({len(status_nodes)} nodes):")
        for node in status_nodes:
            node_id = node["id"]
            attrs = node["attrs"]
            node_label = attrs.get("label", node_id)
            bead_id = attrs.get("bead_id", "")
            handler = attrs.get("handler", "")
            parts = [f"  - `{node_id}`: {node_label}"]
            if handler:
                parts.append(f"(handler: {handler})")
            if bead_id:
                parts.append(f"[bead: {bead_id}]")
            lines.append(" ".join(parts))

    lines.append("")

    # --- Key pending tasks for TaskMaster ---
    pending_nodes = by_status.get("pending", [])
    if pending_nodes:
        lines.append("### Key Pending Tasks (Not Yet Started)")
        for node in pending_nodes:
            node_id = node["id"]
            attrs = node["attrs"]
            node_label = attrs.get("label", node_id)
            bead_id = attrs.get("bead_id", "")
            acceptance = attrs.get("acceptance", "")
            worker_type = attrs.get("worker_type", "")
            lines.append(f"\n- **{node_label}** (`{node_id}`)")
            if bead_id:
                lines.append(f"  - Bead: {bead_id}")
            if worker_type:
                lines.append(f"  - Worker type: {worker_type}")
            if acceptance:
                lines.append(f"  - Acceptance: {acceptance}")
        lines.append("")

    return "\n".join(lines)
