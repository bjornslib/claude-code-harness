"""spawn_orchestrator.py — Create tmux session with Claude Code orchestrator.

Usage:
    python spawn_orchestrator.py --node <node_id> --prd <prd_ref>
        --worktree <path> [--session-name <name>] [--prompt <text>]
        [--max-respawn <n>]

Creates a tmux session named orch-<node_id> (or --session-name) IN the
worktree directory, boots Claude Code, sets the orchestrator output style
via slash command, then sends the prompt.

Output (stdout, JSON):
    {"status": "ok", "session": "<name>", "tmux_cmd": "<command run>", "respawn_count": 0}

On error:
    {"status": "error", "message": "<error>"}
    exits with code 1
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import os
import time


def _tmux_send(session: str, text: str, pause: float = 2.0) -> None:
    """Send text to tmux with Enter as separate call (Pattern 1 from MEMORY.md)."""
    subprocess.run(
        ["tmux", "send-keys", "-t", session, text],
        check=True, capture_output=True, text=True,
    )
    time.sleep(pause)
    subprocess.run(
        ["tmux", "send-keys", "-t", session, "Enter"],
        check=True, capture_output=True, text=True,
    )


def check_orchestrator_alive(session: str) -> bool:
    """Check if a tmux session exists.

    Args:
        session: tmux session name to check.

    Returns:
        True if the session exists (exit code 0), False otherwise.
    """
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True,
    )
    return result.returncode == 0


def respawn_orchestrator(
    session_name: str,
    work_dir: str,
    prompt: str | None,
    respawn_count: int,
    max_respawn: int,
) -> dict:
    """Attempt to respawn a dead orchestrator tmux session.

    Args:
        session_name: tmux session name to (re)create.
        work_dir: Working directory for the new session.
        prompt: Optional initial prompt to send after launching Claude.
        respawn_count: Current number of respawn attempts made so far.
        max_respawn: Maximum allowed respawn attempts.

    Returns:
        Dict with status:
            - ``{"status": "already_alive", "session": session_name}`` if session exists.
            - ``{"status": "error", "message": "Max respawn limit reached (...)"}`` if limit exceeded.
            - ``{"status": "respawned", "session": session_name, "respawn_count": respawn_count + 1}``
              on successful respawn.
    """
    if check_orchestrator_alive(session_name):
        return {"status": "already_alive", "session": session_name}

    if respawn_count >= max_respawn:
        return {
            "status": "error",
            "message": f"Max respawn limit reached ({respawn_count}/{max_respawn})",
        }

    # Recreate the tmux session using the same config as main()
    tmux_cmd = [
        "tmux", "new-session",
        "-d",
        "-s", session_name,
        "-c", work_dir,
        "-x", "220",
        "-y", "50",
        "exec zsh",
    ]
    subprocess.run(tmux_cmd, check=True, capture_output=True, text=True)

    time.sleep(2)
    _tmux_send(session_name, "unset CLAUDECODE && claude", pause=8.0)
    _tmux_send(session_name, "/output-style orchestrator", pause=3.0)
    if prompt:
        _tmux_send(session_name, prompt, pause=2.0)

    return {
        "status": "respawned",
        "session": session_name,
        "respawn_count": respawn_count + 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spawn_orchestrator.py",
        description="Create a tmux session running Claude Code as orchestrator.",
    )
    parser.add_argument("--node", required=True, help="Node identifier")
    parser.add_argument("--prd", required=True, help="PRD reference (e.g., PRD-AUTH-001)")
    parser.add_argument("--worktree", required=True, help="Working directory (target repo)")
    parser.add_argument("--session-name", default=None, dest="session_name",
                        help="tmux session name (default: orch-<node>)")
    parser.add_argument("--prompt", default=None,
                        help="Initial prompt to send after launching Claude")
    parser.add_argument("--max-respawn", type=int, default=3, dest="max_respawn",
                        help="Maximum respawn attempts if session dies (default: 3)")

    args = parser.parse_args()

    session_name = args.session_name or f"orch-{args.node}"
    work_dir = args.worktree

    # Validate session name: reject reserved s3-live- prefix
    if re.match(r"s3-live-", session_name):
        print(json.dumps({
            "status": "error",
            "message": (
                f"Session name '{session_name}' uses reserved 's3-live-' prefix. "
                "Use 'orch-' or 'runner-' prefix."
            ),
        }))
        sys.exit(1)

    # tmux new-session — start a clean shell IN the target directory via -c.
    # We use "exec zsh" (not "claude" directly) because:
    # 1. CLAUDECODE env var must be unset to avoid nested-session error
    # 2. Shell environment (PATH, etc.) must be properly initialized
    tmux_cmd = [
        "tmux", "new-session",
        "-d",               # detached
        "-s", session_name,
        "-c", work_dir,     # tmux starts IN target dir
        "-x", "220",        # width
        "-y", "50",         # height
        "exec zsh",         # clean shell (ccorch pattern from MEMORY.md)
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

    # Wait for shell to initialize
    time.sleep(2)

    # Alive check: attempt respawn if session died immediately after creation
    respawn_count = 0
    if not check_orchestrator_alive(session_name):
        respawn_result = respawn_orchestrator(
            session_name=session_name,
            work_dir=work_dir,
            prompt=args.prompt,
            respawn_count=respawn_count,
            max_respawn=args.max_respawn,
        )
        if respawn_result["status"] == "error":
            print(json.dumps(respawn_result))
            sys.exit(1)
        respawn_count = respawn_result.get("respawn_count", 0)
        # Session was respawned with Claude and prompt already sent; output and return.
        print(json.dumps({
            "status": "ok",
            "session": session_name,
            "tmux_cmd": " ".join(shlex.quote(c) for c in tmux_cmd),
            "respawn_count": respawn_count,
        }))
        return

    # Unset CLAUDECODE to avoid nested-session error, then launch claude
    try:
        _tmux_send(session_name, "unset CLAUDECODE && claude", pause=8.0)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.strip() if exc.stderr else str(exc)
        print(json.dumps({
            "status": "error",
            "message": f"Session created but failed to launch Claude: {error_msg}",
        }))
        sys.exit(1)

    # Set output style via slash command (not CLI flag)
    try:
        _tmux_send(session_name, "/output-style orchestrator", pause=3.0)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.strip() if exc.stderr else str(exc)
        print(json.dumps({
            "status": "error",
            "message": f"Session created but failed to set output style: {error_msg}",
        }))
        sys.exit(1)

    # Send initial prompt if provided
    if args.prompt:
        try:
            _tmux_send(session_name, args.prompt, pause=2.0)
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
        "respawn_count": respawn_count,
    }))


if __name__ == "__main__":
    main()
