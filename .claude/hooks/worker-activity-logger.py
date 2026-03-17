#!/usr/bin/env python3
"""PostToolUse hook — appends worker activity to a per-node JSONL stream.

Captures Edit/Write tool calls and agent thinking pauses as structured events.
The resulting JSONL file is consumed by the worker stop gate at exit time to
validate TDD phase compliance and detect anti-patterns.

Only active when NWAVE_NODE_ID is set (injected by the pipeline runner when
dispatching workers). No-op for non-pipeline sessions.

Output: {NWAVE_SIGNALS_DIR}/{NWAVE_NODE_ID}-activity.jsonl

Event schema:
  {"t": "ISO8601", "type": "edit|think|test_run", "file": "...", "phase": "...", ...}
"""

import json
import os
import sys
from datetime import datetime, timezone

# --- Early exit if not a pipeline worker ---
NODE_ID = os.environ.get("NWAVE_NODE_ID", "")
if not NODE_ID:
    # Not a pipeline worker — approve silently
    sys.exit(0)

SIGNALS_DIR = os.environ.get(
    "NWAVE_SIGNALS_DIR",
    os.environ.get("PIPELINE_SIGNALS_DIR", ""),
)
if not SIGNALS_DIR:
    sys.exit(0)


def _current_phase() -> str:
    """Read the current TDD phase from env (set by worker or inferred)."""
    return os.environ.get("NWAVE_CURRENT_PHASE", "unknown")


def _append_event(event: dict) -> None:
    """Atomically append one JSON line to the activity stream."""
    activity_path = os.path.join(SIGNALS_DIR, f"{NODE_ID}-activity.jsonl")
    os.makedirs(os.path.dirname(activity_path), exist_ok=True)
    try:
        with open(activity_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            fh.flush()
    except OSError:
        pass  # Never crash the worker on logging failure


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    now = datetime.now(timezone.utc).isoformat()

    # Capture Edit/Write tool calls
    if tool_name in ("Edit", "Write", "MultiEdit"):
        file_path = tool_input.get("file_path", "")
        # Infer phase from file path heuristics
        phase = _current_phase()
        if phase == "unknown":
            # Simple heuristic: test files → red, src files → green
            if any(p in file_path for p in ("test_", "_test.", "tests/", "spec.", "__tests__")):
                phase = "red_unit"
            elif any(p in file_path for p in ("src/", "app/", "lib/", "api/")):
                phase = "green"

        event = {
            "t": now,
            "type": "edit",
            "file": file_path,
            "phase": phase,
            "tool": tool_name,
        }
        _append_event(event)

    # Capture Bash tool calls that look like test runs
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if any(kw in command for kw in ("pytest", "jest", "npm test", "npm run test", "vitest", "cargo test")):
            event = {
                "t": now,
                "type": "test_run",
                "command": command[:200],  # Truncate long commands
                "phase": _current_phase(),
            }
            _append_event(event)


if __name__ == "__main__":
    main()
