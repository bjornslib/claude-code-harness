"""spawn_runner.py — Launch Runner as Agent SDK subprocess (placeholder).

Usage:
    python spawn_runner.py --node <node_id> --prd <prd_ref>
        [--solution-design <path>] [--acceptance <text>]
        [--target-dir <path>] [--bead-id <id>]

This is the Runner launch entrypoint. Currently writes runner configuration
to a state file and outputs JSON confirming the configuration. The actual
Agent SDK subprocess invocation will be implemented in a later epic.

Output (stdout, JSON):
    {
        "status": "ok",
        "node": "<node_id>",
        "prd": "<prd_ref>",
        "runner_config": {
            "node_id": ...,
            "prd_ref": ...,
            "solution_design": ...,
            "acceptance_criteria": ...,
            "target_dir": ...,
            "bead_id": ...
        }
    }

On error:
    {"status": "error", "message": "<error>"}
    exits with code 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)


def _find_git_root(start: str):
    """Walk up directory tree to find .git root."""
    current = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _runner_state_dir() -> str:
    """Resolve the runner state directory."""
    git_root = _find_git_root(os.getcwd())
    if git_root:
        return os.path.join(git_root, ".claude", "attractor", "runner-state")
    return os.path.join(os.path.expanduser("~"), ".claude", "attractor", "runner-state")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spawn_runner.py",
        description="Launch a Runner node (placeholder for Agent SDK subprocess).",
    )
    parser.add_argument("--node", required=True, help="Node identifier")
    parser.add_argument("--prd", required=True, help="PRD reference (e.g., PRD-AUTH-001)")
    parser.add_argument("--solution-design", default=None, dest="solution_design",
                        help="Path to solution design document")
    parser.add_argument("--acceptance", default=None,
                        help="Acceptance criteria text")
    parser.add_argument("--target-dir", required=True, dest="target_dir",
                        help="Target working directory for the runner")
    parser.add_argument("--bead-id", default=None, dest="bead_id",
                        help="Beads issue/task identifier")

    args = parser.parse_args()

    runner_config = {
        "node_id": args.node,
        "prd_ref": args.prd,
        "solution_design": args.solution_design,
        "acceptance_criteria": args.acceptance,
        "target_dir": args.target_dir,
        "bead_id": args.bead_id,
    }

    # Write config to state file (placeholder for real runner spawn)
    try:
        state_dir = _runner_state_dir()
        os.makedirs(state_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        state_filename = f"{timestamp}-{args.node}-{args.prd}.json"
        state_path = os.path.join(state_dir, state_filename)

        state_data = {
            "spawned_at": timestamp,
            "status": "pending",
            "runner_config": runner_config,
        }

        tmp_path = state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(state_data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.rename(tmp_path, state_path)

        print(json.dumps({
            "status": "ok",
            "node": args.node,
            "prd": args.prd,
            "runner_config": runner_config,
        }))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
