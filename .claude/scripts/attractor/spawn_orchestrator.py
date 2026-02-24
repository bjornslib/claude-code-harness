"""spawn_orchestrator.py — Create tmux session with Claude Code orchestrator.

Usage:
    python spawn_orchestrator.py --node <node_id> --prd <prd_ref>
        [--worktree <path>] [--session-name <name>] [--prompt <text>]

Creates a tmux session named orch-<node_id> (or --session-name) and runs:
    cd <worktree or current dir> && claude --output-style orchestrator
Then sends the prompt via tmux send-keys.

Output (stdout, JSON):
    {"status": "ok", "session": "<name>", "tmux_cmd": "<command run>"}

On error:
    {"status": "error", "message": "<error>"}
    exits with code 1
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spawn_orchestrator.py",
        description="Create a tmux session running Claude Code as orchestrator.",
    )
    parser.add_argument("--node", required=True, help="Node identifier")
    parser.add_argument("--prd", required=True, help="PRD reference (e.g., PRD-AUTH-001)")
    parser.add_argument("--worktree", default=None, help="Working directory path")
    parser.add_argument("--session-name", default=None, dest="session_name",
                        help="tmux session name (default: orch-<node>)")
    parser.add_argument("--prompt", default=None,
                        help="Initial prompt to send after launching Claude")

    args = parser.parse_args()

    session_name = args.session_name or f"orch-{args.node}"
    work_dir = args.worktree or os.getcwd()

    # Build the shell command to run inside tmux
    shell_cmd = f"cd {shlex.quote(work_dir)} && claude --output-style orchestrator"

    # tmux new-session command
    tmux_cmd = [
        "tmux", "new-session",
        "-d",               # detached
        "-s", session_name,
        "-x", "220",        # width
        "-y", "50",         # height
        shell_cmd,
    ]

    try:
        subprocess.run(
            tmux_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.strip() if exc.stderr else str(exc)
        print(json.dumps({
            "status": "error",
            "message": f"Failed to create tmux session: {error_msg}",
        }))
        sys.exit(1)
    except FileNotFoundError:
        print(json.dumps({
            "status": "error",
            "message": "tmux not found. Please install tmux.",
        }))
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)

    # Optionally send initial prompt
    if args.prompt:
        try:
            send_cmd = [
                "tmux", "send-keys",
                "-t", session_name,
                args.prompt,
                "Enter",
            ]
            subprocess.run(send_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            error_msg = exc.stderr.strip() if exc.stderr else str(exc)
            print(json.dumps({
                "status": "error",
                "message": f"Session created but failed to send prompt: {error_msg}",
            }))
            sys.exit(1)

    print(json.dumps({
        "status": "ok",
        "session": session_name,
        "tmux_cmd": " ".join(shlex.quote(c) for c in tmux_cmd),
    }))


if __name__ == "__main__":
    main()
