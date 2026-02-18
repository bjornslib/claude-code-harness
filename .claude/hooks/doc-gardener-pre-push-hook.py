#!/usr/bin/env python3
"""
PreToolUse hook — intercepts `git push` commands to run doc-gardener lint.

When Claude Code invokes a Bash tool whose command contains `git push`,
this hook runs the doc-gardener linter first.  If violations remain after
auto-fix, the push is blocked with a helpful message.

Hook type : PreToolUse (matcher: "Bash")
Input     : JSON on stdin with {"tool_name": "Bash", "tool_input": {"command": "..."}}
Output    : JSON on stdout — {"decision": "approve"} or {"decision": "block", "reason": "..."}

Fast path : ~1 ms when the command is not `git push`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    # Fast path: only act on Bash tool calls that look like git push
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    if "git push" not in command and "git  push" not in command:
        # Not a push — approve immediately (< 1 ms)
        print(json.dumps({"decision": "approve"}))
        return

    # Emergency bypass via environment variable
    if os.environ.get("DOC_GARDENER_SKIP") == "1":
        print(json.dumps({"decision": "approve"}))
        return

    # Locate gardener.py relative to this hook
    hook_dir = Path(__file__).resolve().parent
    claude_dir = hook_dir.parent
    gardener = claude_dir / "scripts" / "doc-gardener" / "gardener.py"

    if not gardener.is_file():
        # gardener.py not present — don't block
        print(json.dumps({"decision": "approve"}))
        return

    # Run the gardener in execute mode (auto-fix + re-scan)
    try:
        result = subprocess.run(
            [sys.executable, str(gardener), "--execute"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        # Timeout — fail open, let the push through
        print(json.dumps({
            "decision": "approve",
            "systemMessage": "[doc-gardener] Lint timed out (60 s), allowing push.",
        }))
        return
    except Exception as exc:
        print(json.dumps({
            "decision": "approve",
            "systemMessage": f"[doc-gardener] Lint error ({exc}), allowing push.",
        }))
        return

    if result.returncode != 0:
        # Manual-fix items remain — block the push
        reason_lines = [
            "[doc-gardener] Documentation violations found — push blocked.",
            "",
            result.stdout.strip() if result.stdout.strip() else "(no output)",
            "",
            "Fix remaining violations, then retry the push.",
            "Run: python3 .claude/scripts/doc-gardener/gardener.py --report",
        ]
        print(json.dumps({
            "decision": "block",
            "reason": "\n".join(reason_lines),
        }))
        return

    # Clean — approve with informational note
    print(json.dumps({
        "decision": "approve",
        "systemMessage": "[doc-gardener] Documentation lint passed.",
    }))


if __name__ == "__main__":
    main()
