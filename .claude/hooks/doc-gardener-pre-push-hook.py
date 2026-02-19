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

Bypass methods (any one is sufficient):
  1. Environment variable : DOC_GARDENER_SKIP=1 (set in parent process)
  2. Command-string env   : DOC_GARDENER_SKIP=1 git push  (inline in the command)
  3. --no-verify flag     : git push --no-verify  (git convention)
  4. --skip-lint flag      : git push --skip-lint  (explicit opt-out)
  5. Signal file          : .claude/.doc-gardener-skip  (project-level temporary bypass;
                            create the file to skip, remove when done)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Regex that matches `git push` as a real command (possibly preceded by
# shell operators or inline env-var assignments) but NOT inside quoted
# strings such as `gh pr create --body "... git push ..."`.
#
# Strategy: split the command on common shell operators (&&, ||, ;, |) and
# check whether any resulting segment, after stripping leading whitespace
# and env-var assignments (FOO=bar), starts with `git push`.
_SHELL_SPLIT = re.compile(r"\s*(?:&&|\|\|?|;)\s*")
_LEADING_ENV = re.compile(r'^(?:(?:export\s+)?\w+=(?:"[^"]*"|\S*)\s+)*')


def _has_real_git_push(command: str) -> bool:
    """Return True if *command* contains a standalone `git push` invocation.

    Ignores occurrences inside quoted strings (e.g. in ``gh pr create --body``
    arguments) by only inspecting shell-operator–delimited segments.
    """
    segments = _SHELL_SPLIT.split(command)
    for seg in segments:
        stripped = seg.strip()
        # Skip segments that are clearly inside a quoted argument.
        # A simple heuristic: if the segment starts with a quote or
        # dash (flag value), it's not a standalone command.
        if stripped.startswith(("'", '"')):
            continue
        # Strip leading env-var assignments (VAR=val ...)
        core = _LEADING_ENV.sub("", stripped)
        if re.match(r"git\s+push\b", core):
            return True
    return False


def _approve(msg: str | None = None) -> None:
    """Print an approve decision and exit."""
    out: dict = {"decision": "approve"}
    if msg:
        out["systemMessage"] = msg
    print(json.dumps(out))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    # Fast path: only act on Bash tool calls that look like git push
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    if not _has_real_git_push(command):
        # Not a push — approve immediately (< 1 ms)
        _approve()
        return

    # --- Bypass checks (any one is sufficient) ---

    # 1. Environment variable set in the parent process
    if os.environ.get("DOC_GARDENER_SKIP") == "1":
        _approve("[doc-gardener] Skipped (DOC_GARDENER_SKIP env).")
        return

    # 2. DOC_GARDENER_SKIP appears anywhere in the command string
    #    (covers `DOC_GARDENER_SKIP=1 git push` inline usage that doesn't
    #    propagate to the hook subprocess)
    if "DOC_GARDENER_SKIP" in command:
        _approve("[doc-gardener] Skipped (DOC_GARDENER_SKIP in command).")
        return

    # 3. --no-verify flag (respects git convention)
    if "--no-verify" in command:
        _approve("[doc-gardener] Skipped (--no-verify).")
        return

    # 4. --skip-lint flag (explicit opt-out)
    if "--skip-lint" in command:
        _approve("[doc-gardener] Skipped (--skip-lint).")
        return

    # 5. Signal file bypass (.claude/.doc-gardener-skip)
    hook_dir = Path(__file__).resolve().parent
    claude_dir = hook_dir.parent
    signal_file = claude_dir / ".doc-gardener-skip"
    if signal_file.exists():
        _approve("[doc-gardener] Skipped (.doc-gardener-skip signal file).")
        return

    # Locate gardener.py relative to this hook
    gardener = claude_dir / "scripts" / "doc-gardener" / "gardener.py"

    if not gardener.is_file():
        # gardener.py not present — don't block
        _approve()
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
        _approve("[doc-gardener] Lint timed out (60 s), allowing push.")
        return
    except Exception as exc:
        _approve(f"[doc-gardener] Lint error ({exc}), allowing push.")
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
            "",
            "Bypass options:",
            "  - git push --no-verify",
            "  - DOC_GARDENER_SKIP=1 git push",
            "  - touch .claude/.doc-gardener-skip",
        ]
        print(json.dumps({
            "decision": "block",
            "reason": "\n".join(reason_lines),
        }))
        return

    # Clean — approve with informational note
    _approve("[doc-gardener] Documentation lint passed.")


if __name__ == "__main__":
    main()
