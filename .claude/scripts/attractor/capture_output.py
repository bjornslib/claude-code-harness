"""capture_output.py — tmux capture-pane wrapper.

Usage:
    python capture_output.py --session <session_name> [--lines <n>] [--pane <pane_id>]

Output (stdout, JSON):
    {"status": "ok", "session": "<name>", "lines": <n>, "content": "<captured text>"}

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
        prog="capture_output.py",
        description="Capture output from a tmux session pane.",
    )
    parser.add_argument("--session", required=True, help="tmux session name")
    parser.add_argument("--lines", type=int, default=100,
                        help="Number of lines to capture (default: 100)")
    parser.add_argument("--pane", default=None,
                        help="Pane identifier (default: first pane in session)")

    args = parser.parse_args()

    # Build target: session[:window[.pane]]
    target = args.session
    if args.pane:
        target = f"{args.session}:{args.pane}"

    try:
        result = subprocess.run(
            [
                "tmux", "capture-pane",
                "-p",                      # print to stdout
                "-t", target,
                "-S", str(-args.lines),    # start N lines back
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        content = result.stdout
        actual_lines = len(content.splitlines())
        print(json.dumps({
            "status": "ok",
            "session": args.session,
            "lines": actual_lines,
            "content": content,
        }))
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.strip() if exc.stderr else f"tmux exit code {exc.returncode}"
        print(json.dumps({
            "status": "error",
            "message": f"Failed to capture pane for session '{args.session}': {error_msg}",
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
