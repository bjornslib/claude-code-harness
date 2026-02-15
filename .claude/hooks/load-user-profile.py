#!/usr/bin/env python3
"""
SessionStart Hook: Load USER.md Operator Profile + IDENTITY.md

Reads .claude/USER.md and .claude/IDENTITY.md, outputs their content wrapped
in <system-reminder> tags so Claude Code receives operator preferences and
system identity at session start.

Gracefully handles either file not existing (silent skip for that file).

Input (stdin): JSON with session info (session_id, source, cwd, etc.)
Output (stdout): File contents wrapped in system-reminder tags
"""

import json
import os
import sys
from pathlib import Path


def find_claude_file(cwd: str, filename: str) -> Path | None:
    """
    Locate a file relative to the project's .claude/ directory.

    Search order:
    1. $CLAUDE_PROJECT_DIR/.claude/<filename> (if env var set)
    2. <cwd>/.claude/<filename>
    3. Walk up from cwd looking for .claude/<filename>
    """
    # Try CLAUDE_PROJECT_DIR first
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidate = Path(project_dir) / ".claude" / filename
        if candidate.is_file():
            return candidate

    # Try cwd
    candidate = Path(cwd) / ".claude" / filename
    if candidate.is_file():
        return candidate

    # Walk up from cwd
    current = Path(cwd).resolve()
    for parent in [current] + list(current.parents):
        candidate = parent / ".claude" / filename
        if candidate.is_file():
            return candidate
        # Stop at filesystem root
        if parent == parent.parent:
            break

    return None


def find_user_profile(cwd: str) -> Path | None:
    """Locate USER.md (backward-compatible wrapper)."""
    return find_claude_file(cwd, "USER.md")


def _load_and_emit(cwd: str, filename: str) -> None:
    """Find a .claude/ file and emit its content as a system-reminder block."""
    file_path = find_claude_file(cwd, filename)
    if file_path is None:
        return

    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        return

    print(f"<system-reminder>\n# {filename}\n\n{content}\n</system-reminder>")


def main():
    """
    Read hook input from stdin, find USER.md and IDENTITY.md, output as system-reminders.
    """
    try:
        raw_input = sys.stdin.read()

        if not raw_input.strip():
            sys.exit(0)

        input_data = json.loads(raw_input)
        cwd = input_data.get("cwd", os.getcwd())

        # Load operator profile
        _load_and_emit(cwd, "USER.md")

        # Load system identity and disposition
        _load_and_emit(cwd, "IDENTITY.md")

    except json.JSONDecodeError:
        # Malformed input — fail silently
        sys.exit(0)
    except Exception as e:
        # Hooks must never crash the session
        print(f"Warning: load-user-profile hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
