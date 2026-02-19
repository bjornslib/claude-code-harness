#!/usr/bin/env python3
"""Attractor DOT Pipeline State Transition.

Advance a node's status through the defined lifecycle:
    pending -> active -> impl_complete -> validated
                                       -> failed -> active (retry)

Usage:
    python3 transition.py <file.dot> <node_id> <new_status> [--dry-run]
    python3 transition.py --help
"""

import argparse
import datetime
import json
import re
import sys

from parser import parse_file


# --- Valid transitions ---
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"active"},
    "active": {"impl_complete"},
    "impl_complete": {"validated", "failed"},
    "failed": {"active"},
    "validated": set(),  # terminal
}

# Status -> fillcolor mapping from schema
STATUS_COLORS: dict[str, str] = {
    "pending": "lightyellow",
    "active": "lightblue",
    "impl_complete": "lightsalmon",
    "validated": "lightgreen",
    "failed": "lightcoral",
}


def check_transition(current: str, target: str) -> tuple[bool, str]:
    """Check if a status transition is valid.

    Returns (is_valid, reason).
    """
    if current not in VALID_TRANSITIONS:
        return False, f"Unknown current status '{current}'"
    if target not in VALID_TRANSITIONS and target not in {
        s for ss in VALID_TRANSITIONS.values() for s in ss
    }:
        return False, f"Unknown target status '{target}'"
    if target in VALID_TRANSITIONS.get(current, set()):
        return True, f"{current} -> {target}"
    return False, (
        f"Illegal transition: {current} -> {target}. "
        f"Valid transitions from '{current}': {sorted(VALID_TRANSITIONS.get(current, set()))}"
    )


def apply_transition(
    dot_content: str, node_id: str, new_status: str
) -> tuple[str, str]:
    """Apply a status transition to a DOT file string.

    Finds the node definition and updates its status attribute.
    Also updates fillcolor to match the new status.

    Returns (updated_content, log_message).
    """
    # First parse to validate the node exists and get current status
    from parser import parse_dot

    data = parse_dot(dot_content)
    node = None
    for n in data["nodes"]:
        if n["id"] == node_id:
            node = n
            break

    if node is None:
        raise ValueError(f"Node '{node_id}' not found in pipeline")

    current_status = node["attrs"].get("status", "pending")
    valid, reason = check_transition(current_status, new_status)
    if not valid:
        raise ValueError(reason)

    # Update the status attribute in the DOT content
    updated = _update_node_attr(dot_content, node_id, "status", new_status)

    # Update fillcolor to match new status
    new_color = STATUS_COLORS.get(new_status, "")
    if new_color:
        updated = _update_node_attr(updated, node_id, "fillcolor", new_color)
        # Ensure style=filled is present
        if "style" not in node["attrs"]:
            updated = _add_node_attr(updated, node_id, "style", "filled")

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_msg = f"[{timestamp}] {node_id}: {current_status} -> {new_status}"

    return updated, log_msg


def _find_node_block(content: str, node_id: str) -> tuple[int, int]:
    """Find the start and end positions of a node's definition block.

    Returns (start, end) positions, or (-1, -1) if not found.
    """
    # Look for patterns like: node_id [ ... ] or node_id [...];
    # Must handle multiline blocks
    pattern = re.compile(
        r"(?<!\w)(" + re.escape(node_id) + r")\s*\[",
        re.MULTILINE,
    )

    for m in pattern.finditer(content):
        # Verify this isn't an edge (no -> before it)
        before = content[: m.start()].rstrip()
        if before.endswith("->"):
            continue

        # Find matching ]
        bracket_start = content.index("[", m.start())
        depth = 0
        pos = bracket_start
        while pos < len(content):
            if content[pos] == "[":
                depth += 1
            elif content[pos] == "]":
                depth -= 1
                if depth == 0:
                    # Include trailing semicolon if present
                    end = pos + 1
                    if end < len(content) and content[end] == ";":
                        end += 1
                    return m.start(), end
            elif content[pos] == '"':
                pos += 1
                while pos < len(content) and content[pos] != '"':
                    if content[pos] == "\\":
                        pos += 1
                    pos += 1
            pos += 1

    return -1, -1


def _update_node_attr(content: str, node_id: str, attr: str, value: str) -> str:
    """Update a single attribute within a node's block."""
    start, end = _find_node_block(content, node_id)
    if start == -1:
        raise ValueError(f"Cannot find node block for '{node_id}'")

    block = content[start:end]

    # Try to replace existing attribute
    # Match: attr="old_value" or attr=old_value
    attr_pattern = re.compile(
        r'(' + re.escape(attr) + r')\s*=\s*"[^"]*"'
    )
    m = attr_pattern.search(block)
    if m:
        new_block = block[: m.start()] + f'{attr}="{value}"' + block[m.end() :]
        return content[:start] + new_block + content[end:]

    # Try unquoted: attr=value
    attr_pattern_unquoted = re.compile(
        r'(' + re.escape(attr) + r')\s*=\s*(\S+)'
    )
    m = attr_pattern_unquoted.search(block)
    if m:
        new_block = block[: m.start()] + f'{attr}="{value}"' + block[m.end() :]
        return content[:start] + new_block + content[end:]

    # Attribute not found — add it
    return _add_node_attr(content, node_id, attr, value)


def _add_node_attr(content: str, node_id: str, attr: str, value: str) -> str:
    """Add a new attribute to a node's block."""
    start, end = _find_node_block(content, node_id)
    if start == -1:
        raise ValueError(f"Cannot find node block for '{node_id}'")

    block = content[start:end]

    # Find the closing bracket and insert before it
    bracket_pos = block.rfind("]")
    if bracket_pos == -1:
        raise ValueError(f"Malformed node block for '{node_id}'")

    # Determine indentation from existing attributes
    new_attr = f'\n        {attr}="{value}"'
    new_block = block[:bracket_pos] + new_attr + "\n    " + block[bracket_pos:]
    return content[:start] + new_block + content[end:]


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Transition a node's status in an Attractor DOT pipeline."
    )
    ap.add_argument("file", help="Path to .dot file")
    ap.add_argument("node_id", help="Node ID to transition")
    ap.add_argument(
        "new_status",
        choices=["pending", "active", "impl_complete", "validated", "failed"],
        help="Target status",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )
    ap.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    args = ap.parse_args()

    try:
        with open(args.file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        updated, log_msg = apply_transition(content, args.node_id, args.new_status)
    except ValueError as e:
        if args.output == "json":
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        if args.output == "json":
            print(
                json.dumps(
                    {"success": True, "dry_run": True, "log": log_msg},
                    indent=2,
                )
            )
        else:
            print(f"DRY RUN: {log_msg}")
            print("(no changes written)")
    else:
        with open(args.file, "w") as f:
            f.write(updated)
        if args.output == "json":
            print(
                json.dumps(
                    {"success": True, "log": log_msg, "file": args.file},
                    indent=2,
                )
            )
        else:
            print(f"Transition applied: {log_msg}")
            print(f"Updated: {args.file}")


if __name__ == "__main__":
    main()
