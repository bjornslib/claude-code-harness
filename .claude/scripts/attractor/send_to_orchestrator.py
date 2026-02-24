"""send_to_orchestrator.py — tmux send-keys wrapper.

Usage:
    python send_to_orchestrator.py --session <session_name> --message <text>

Output (stdout, JSON):
    {"status": "ok", "session": "<name>", "message": "<text sent>"}

On error:
    {"status": "error", "message": "<error>"}
    exits with code 1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="send_to_orchestrator.py",
        description="Send a message to a tmux session via send-keys.",
    )
    parser.add_argument("--session", required=True, help="tmux session name")
    parser.add_argument("--message", required=True, help="Text to send to the session")

    args = parser.parse_args()

    try:
        subprocess.run(
            [
                "tmux", "send-keys",
                "-t", args.session,
                args.message,
                "Enter",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(json.dumps({
            "status": "ok",
            "session": args.session,
            "message": args.message,
        }))
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.strip() if exc.stderr else f"tmux exit code {exc.returncode}"
        print(json.dumps({
            "status": "error",
            "message": f"Failed to send keys to session '{args.session}': {error_msg}",
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


if __name__ == "__main__":
    main()
