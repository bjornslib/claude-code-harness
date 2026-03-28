"""CLI event stream — real-time formatted tail of pipeline-events.jsonl.

Usage::

    python3 cobuilder/engine/cli.py watch <path.jsonl|path.dot> [--filter node.*] [--since 5]

Reads the JSONL file produced by ``JSONLEmitter``, formats each event with
ANSI colors, and follows the file for new events (like ``tail -f``).
Pure stdlib — no external dependencies.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

# ---------------------------------------------------------------------------
# ANSI escape codes
# ---------------------------------------------------------------------------

_ANSI = {
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "reset": "\033[0m",
    "magenta": "\033[35m",
}

# Map event type patterns to colors
_COLOR_RULES: list[tuple[str, str]] = [
    ("*.completed", "green"),
    ("*.failed", "red"),
    ("pipeline.failed", "red"),
    ("retry.*", "yellow"),
    ("retry.triggered", "yellow"),
    ("loop.detected", "yellow"),
    ("*.started", "cyan"),
    ("pipeline.started", "cyan"),
    ("pipeline.resumed", "cyan"),
    ("checkpoint.saved", "dim"),
    ("context.updated", "dim"),
    ("validation.started", "magenta"),
    ("validation.completed", "green"),
]


def _color_for_event(event_type: str) -> str:
    """Return the ANSI color code for an event type."""
    for pattern, color in _COLOR_RULES:
        if fnmatch.fnmatch(event_type, pattern):
            return _ANSI[color]
    return ""


# ---------------------------------------------------------------------------
# Event formatting
# ---------------------------------------------------------------------------

def _data_summary(event_type: str, data: dict) -> str:
    """Extract the most informative fields from event data as a short string."""
    parts: list[str] = []

    if event_type == "pipeline.started":
        parts.append(f"nodes={data.get('node_count', '?')}")
        dot = data.get("dot_path", "")
        if dot:
            parts.append(f"dot={os.path.basename(dot)}")

    elif event_type == "pipeline.completed":
        ms = data.get("duration_ms")
        if ms is not None:
            parts.append(f"{ms:.0f}ms")
        tok = data.get("total_tokens", 0)
        if tok:
            parts.append(f"{tok}tok")

    elif event_type == "pipeline.failed":
        parts.append(data.get("error_type", ""))
        msg = data.get("error_message", "")
        if msg:
            parts.append(msg[:80])

    elif event_type == "pipeline.resumed":
        parts.append(f"completed={data.get('completed_node_count', '?')}")

    elif event_type == "node.started":
        parts.append(f"handler={data.get('handler_type', '?')}")
        visit = data.get("visit_count", 1)
        if visit > 1:
            parts.append(f"visit={visit}")

    elif event_type == "node.completed":
        parts.append(f"status={data.get('outcome_status', '?')}")
        ms = data.get("duration_ms")
        if ms is not None:
            parts.append(f"{ms:.0f}ms")
        tok = data.get("tokens_used", 0)
        if tok:
            parts.append(f"{tok}tok")

    elif event_type == "node.failed":
        parts.append(data.get("error_type", ""))
        if data.get("goal_gate"):
            parts.append("GOAL_GATE")
        rt = data.get("retry_target")
        if rt:
            parts.append(f"retry->{rt}")

    elif event_type == "edge.selected":
        fr = data.get("from_node_id", "?")
        to = data.get("to_node_id", "?")
        parts.append(f"{fr} -> {to}")
        cond = data.get("condition")
        if cond:
            parts.append(f"({cond})")

    elif event_type == "checkpoint.saved":
        cp = data.get("checkpoint_path", "")
        if cp:
            parts.append(os.path.basename(cp))

    elif event_type == "context.updated":
        added = data.get("keys_added", [])
        modified = data.get("keys_modified", [])
        if added:
            parts.append(f"+{len(added)} keys")
        if modified:
            parts.append(f"~{len(modified)} keys")

    elif event_type == "retry.triggered":
        parts.append(f"attempt={data.get('attempt_number', '?')}")
        backoff = data.get("backoff_ms")
        if backoff:
            parts.append(f"backoff={backoff:.0f}ms")
        parts.append(data.get("error_type", ""))

    elif event_type == "loop.detected":
        parts.append(f"visits={data.get('visit_count', '?')}/{data.get('limit', '?')}")
        pat = data.get("pattern")
        if pat:
            parts.append(pat[:40])

    elif event_type == "validation.started":
        parts.append(f"rules={data.get('rule_count', '?')}")

    elif event_type == "validation.completed":
        passed = data.get("passed")
        errors = data.get("errors", [])
        warnings = data.get("warnings", [])
        parts.append("PASS" if passed else "FAIL")
        if errors:
            parts.append(f"{len(errors)} errors")
        if warnings:
            parts.append(f"{len(warnings)} warnings")

    return "  ".join(parts)


def format_event(record: dict, use_color: bool = True) -> str:
    """Format a single JSONL record as a human-readable line.

    Format: ``HH:MM:SS.fff  event.type(padded)  [node_id]  data_summary``
    """
    # Parse timestamp
    ts_raw = record.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_raw)
        # Convert to local time for display
        ts_local = ts.astimezone()
        ts_str = ts_local.strftime("%H:%M:%S.") + f"{ts_local.microsecond // 1000:03d}"
    except (ValueError, TypeError):
        ts_str = ts_raw[:12] if ts_raw else "??:??:??.???"

    event_type = record.get("type", "unknown")
    node_id = record.get("node_id")
    data = record.get("data", {})

    # Type string, padded for alignment
    type_str = event_type.ljust(22)

    # Node indicator
    if node_id:
        node_str = f"[{node_id}]"
    else:
        node_str = " --"

    # Data summary
    summary = _data_summary(event_type, data)

    # Compose
    if use_color:
        color = _color_for_event(event_type)
        reset = _ANSI["reset"]
        dim = _ANSI["dim"]
        line = f"{dim}{ts_str}{reset}  {color}{type_str}{reset}  {node_str}  {summary}"
    else:
        line = f"{ts_str}  {type_str}  {node_str}  {summary}"

    return line


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_PIPELINE_SEARCH_DIRS = [
    ".pipelines/pipelines",
    ".claude/attractor/pipelines",
]


def resolve_jsonl_path(input_path: str) -> str:
    """Resolve a .jsonl or .dot path to the actual pipeline-events.jsonl file.

    - ``.jsonl`` paths are returned as-is (after existence check).
    - ``.dot`` paths trigger a scan of standard pipeline run directories
      to find the most recent ``pipeline-events.jsonl``.

    Raises:
        FileNotFoundError: If the JSONL file cannot be located.
        ValueError: If the input has an unexpected extension.
    """
    p = Path(input_path)

    if p.suffix == ".jsonl":
        if not p.exists():
            raise FileNotFoundError(f"JSONL file not found: {input_path}")
        return str(p)

    if p.suffix == ".dot":
        # The DOT file itself contains a pipeline_id; also try the stem
        pipeline_id = p.stem
        cwd = Path.cwd()

        # Also check if the JSONL is next to the DOT file
        sibling = p.parent / "pipeline-events.jsonl"
        if sibling.exists():
            return str(sibling)

        # Scan standard directories for run dirs
        for search_dir in _PIPELINE_SEARCH_DIRS:
            base = cwd / search_dir
            # Check for pipeline-events.jsonl directly in the pipeline dir
            direct = base / pipeline_id / "pipeline-events.jsonl"
            if direct.exists():
                return str(direct)

            # Check for timestamped run subdirectories
            pipeline_dir = base / pipeline_id
            if pipeline_dir.is_dir():
                run_dirs = sorted(
                    [d for d in pipeline_dir.iterdir() if d.is_dir()],
                    key=lambda d: d.name,
                    reverse=True,
                )
                for rd in run_dirs:
                    candidate = rd / "pipeline-events.jsonl"
                    if candidate.exists():
                        return str(candidate)

        # Also try using the full path parent as the base
        if p.parent.is_dir():
            parent_jsonl = p.parent / "pipeline-events.jsonl"
            if parent_jsonl.exists():
                return str(parent_jsonl)

        raise FileNotFoundError(
            f"No pipeline-events.jsonl found for pipeline '{pipeline_id}'.\n"
            f"Searched: {', '.join(_PIPELINE_SEARCH_DIRS)}\n"
            f"Provide the .jsonl path directly instead."
        )

    raise ValueError(f"Expected .jsonl or .dot file, got: '{p.suffix}'")


# ---------------------------------------------------------------------------
# Tail / follow loop
# ---------------------------------------------------------------------------

def tail_events(
    path: str,
    follow: bool = True,
    filter_pattern: str | None = None,
    since_minutes: float | None = None,
    use_color: bool = True,
    output: TextIO | None = None,
) -> dict[str, int]:
    """Read and format pipeline events from a JSONL file.

    Args:
        path: Path to the ``pipeline-events.jsonl`` file.
        follow: If True, keep tailing for new events (like ``tail -f``).
        filter_pattern: Glob pattern to match event types (e.g. ``node.*``).
        since_minutes: Skip events older than this many minutes.
        use_color: Enable ANSI color output.
        output: Output stream (defaults to ``sys.stdout``).

    Returns:
        Dict mapping event type to count of displayed events.
    """
    if output is None:
        output = sys.stdout

    since_cutoff = None
    if since_minutes is not None:
        since_cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

    counts: dict[str, int] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if not line:
                    if not follow:
                        break
                    time.sleep(0.15)
                    continue

                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = record.get("type", "")

                # --since filter
                if since_cutoff is not None:
                    ts_raw = record.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_raw)
                        if ts < since_cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass  # show events with unparseable timestamps

                # --filter glob
                if filter_pattern and not fnmatch.fnmatch(event_type, filter_pattern):
                    continue

                counts[event_type] = counts.get(event_type, 0) + 1
                formatted = format_event(record, use_color=use_color)
                output.write(formatted + "\n")
                output.flush()

    except KeyboardInterrupt:
        output.write("\n")

    return counts


def print_summary(counts: dict[str, int], use_color: bool = True, output: TextIO | None = None) -> None:
    """Print a summary of event counts by type."""
    if output is None:
        output = sys.stdout

    if not counts:
        return

    total = sum(counts.values())
    output.write("\n")

    if use_color:
        output.write(f"{_ANSI['bold']}--- Event Summary ---{_ANSI['reset']}\n")
    else:
        output.write("--- Event Summary ---\n")

    for event_type in sorted(counts.keys()):
        count = counts[event_type]
        if use_color:
            color = _color_for_event(event_type)
            reset = _ANSI["reset"]
            output.write(f"  {color}{event_type.ljust(22)}{reset}  {count}\n")
        else:
            output.write(f"  {event_type.ljust(22)}  {count}\n")

    if use_color:
        output.write(f"{_ANSI['dim']}  total: {total}{_ANSI['reset']}\n")
    else:
        output.write(f"  total: {total}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """``cli.py watch`` subcommand entry point."""
    parser = argparse.ArgumentParser(
        prog="cli.py watch",
        description="Stream pipeline events in real-time (tail -f for pipelines).",
    )
    parser.add_argument(
        "path",
        help="Path to pipeline-events.jsonl or a .dot pipeline file",
    )
    parser.add_argument(
        "--filter",
        dest="filter_pattern",
        default=None,
        help="Glob pattern to match event types (e.g. 'node.*', '*.failed')",
    )
    parser.add_argument(
        "--since",
        type=float,
        default=None,
        metavar="MINUTES",
        help="Only show events from the last N minutes",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Print existing events and exit (don't follow)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output",
    )

    args = parser.parse_args()

    # Resolve path
    try:
        jsonl_path = resolve_jsonl_path(args.path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    use_color = not args.no_color and sys.stdout.isatty()
    follow = not args.no_follow

    # Header
    if use_color:
        print(f"{_ANSI['bold']}Watching:{_ANSI['reset']} {jsonl_path}")
        if follow:
            print(f"{_ANSI['dim']}Press Ctrl+C to stop{_ANSI['reset']}")
    else:
        print(f"Watching: {jsonl_path}")
        if follow:
            print("Press Ctrl+C to stop")
    print()

    # Stream events
    counts = tail_events(
        path=jsonl_path,
        follow=follow,
        filter_pattern=args.filter_pattern,
        since_minutes=args.since,
        use_color=use_color,
    )

    print_summary(counts, use_color=use_color)


if __name__ == "__main__":
    main()
