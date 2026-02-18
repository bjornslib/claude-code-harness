#!/usr/bin/env python3
"""Attractor DOT Pipeline Status Display.

Displays the status of all nodes in a pipeline DOT file as a formatted table.

Usage:
    python3 status.py <file.dot> [--json] [--filter=active]
    python3 status.py --help
"""

import argparse
import json
import sys

from parser import parse_file


def get_status_table(data: dict, filter_status: str = "") -> list[dict]:
    """Build a status table from parsed DOT data.

    Returns a list of dicts with keys:
        node_id, handler, status, bead_id, worker_type, label
    """
    rows = []
    for node in data.get("nodes", []):
        attrs = node["attrs"]
        row = {
            "node_id": node["id"],
            "handler": attrs.get("handler", ""),
            "status": attrs.get("status", "pending"),
            "bead_id": attrs.get("bead_id", ""),
            "worker_type": attrs.get("worker_type", ""),
            "label": attrs.get("label", "").replace("\\n", " ").replace("\n", " "),
        }
        if filter_status and row["status"] != filter_status:
            continue
        rows.append(row)
    return rows


def format_table(rows: list[dict]) -> str:
    """Format rows into an aligned text table."""
    if not rows:
        return "(no nodes match filter)"

    headers = {
        "node_id": "Node ID",
        "handler": "Handler",
        "status": "Status",
        "bead_id": "Bead ID",
        "worker_type": "Worker Type",
        "label": "Label",
    }
    cols = ["node_id", "handler", "status", "bead_id", "worker_type", "label"]

    # Calculate column widths
    widths: dict[str, int] = {}
    for col in cols:
        widths[col] = max(
            len(headers[col]),
            max((len(str(row.get(col, ""))) for row in rows), default=0),
        )

    # Build header line
    header_line = "  ".join(
        headers[col].ljust(widths[col]) for col in cols
    )
    sep_line = "  ".join("-" * widths[col] for col in cols)

    # Build data lines
    data_lines = []
    for row in rows:
        line = "  ".join(
            str(row.get(col, "")).ljust(widths[col]) for col in cols
        )
        data_lines.append(line)

    return "\n".join([header_line, sep_line] + data_lines)


def status_summary(rows: list[dict]) -> dict[str, int]:
    """Count nodes by status."""
    counts: dict[str, int] = {}
    for row in rows:
        s = row["status"]
        counts[s] = counts.get(s, 0) + 1
    return counts


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Display status of all nodes in an Attractor DOT pipeline."
    )
    ap.add_argument("file", help="Path to .dot file")
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )
    ap.add_argument(
        "--filter",
        default="",
        help="Filter by status (e.g., --filter=active)",
    )
    ap.add_argument(
        "--summary",
        action="store_true",
        help="Show only status summary counts",
    )
    args = ap.parse_args()

    try:
        data = parse_file(args.file)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Get all rows (unfiltered) for summary, filtered for display
    all_rows = get_status_table(data)
    display_rows = get_status_table(data, filter_status=args.filter)
    summary = status_summary(all_rows)

    if args.json_output:
        result = {
            "graph_name": data.get("graph_name", ""),
            "prd_ref": data.get("graph_attrs", {}).get("prd_ref", ""),
            "total_nodes": len(all_rows),
            "summary": summary,
        }
        if args.summary:
            print(json.dumps(result, indent=2))
        else:
            result["nodes"] = display_rows
            print(json.dumps(result, indent=2))
    else:
        graph_name = data.get("graph_name", "unknown")
        prd = data.get("graph_attrs", {}).get("prd_ref", "")
        print(f"Pipeline: {graph_name}")
        if prd:
            print(f"PRD: {prd}")
        print(f"Total nodes: {len(all_rows)}")
        print()

        if args.summary:
            print("Status summary:")
            for status, count in sorted(summary.items()):
                print(f"  {status:20s}  {count}")
        else:
            if args.filter:
                print(f"Filter: status={args.filter}")
                print()
            print(format_table(display_rows))
            print()
            print("Summary:", ", ".join(
                f"{s}={c}" for s, c in sorted(summary.items())
            ))


if __name__ == "__main__":
    main()
