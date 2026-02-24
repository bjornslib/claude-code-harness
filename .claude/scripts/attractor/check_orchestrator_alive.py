"""check_orchestrator_alive.py — Verify that a tmux session exists.

Usage:
    python check_orchestrator_alive.py --session <session_name>

Output (stdout, JSON):
    {"alive": true/false, "session": "<name>"}

This tool never exits with code 1 for a dead session — the alive field
conveys that. It only exits with code 1 on unexpected errors (e.g., tmux
not installed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def session_exists(session_name: str) -> bool:
    """Return True if the named tmux session exists."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        raise
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="check_orchestrator_alive.py",
        description="Check if a tmux session exists.",
    )
    parser.add_argument("--session", required=True, help="tmux session name to check")

    args = parser.parse_args()

    try:
        alive = session_exists(args.session)
        print(json.dumps({
            "alive": alive,
            "session": args.session,
        }))
    except FileNotFoundError:
        print(json.dumps({
            "status": "error",
            "message": "tmux not found. Please install tmux.",
        }))
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
