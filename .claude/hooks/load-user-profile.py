#!/usr/bin/env python3
"""
SessionStart Hook: Load USER.md Operator Profile

Reads .claude/USER.md and outputs its content wrapped in <system-reminder> tags
so Claude Code receives operator preferences at session start.

Gracefully handles USER.md not existing (silent no-op).

Input (stdin): JSON with session info (session_id, source, cwd, etc.)
Output (stdout): USER.md content wrapped in system-reminder tags
"""

import json
import os
import sys
from pathlib import Path


def find_user_profile(cwd: str) -> Path | None:
    """
    Locate USER.md relative to the project's .claude/ directory.

    Search order:
    1. $CLAUDE_PROJECT_DIR/.claude/USER.md (if env var set)
    2. <cwd>/.claude/USER.md
    3. Walk up from cwd looking for .claude/USER.md
    """
    # Try CLAUDE_PROJECT_DIR first
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidate = Path(project_dir) / ".claude" / "USER.md"
        if candidate.is_file():
            return candidate

    # Try cwd
    candidate = Path(cwd) / ".claude" / "USER.md"
    if candidate.is_file():
        return candidate

    # Walk up from cwd
    current = Path(cwd).resolve()
    for parent in [current] + list(current.parents):
        candidate = parent / ".claude" / "USER.md"
        if candidate.is_file():
            return candidate
        # Stop at filesystem root
        if parent == parent.parent:
            break

    return None


def main():
    """
    Read hook input from stdin, find USER.md, and output as system-reminder.
    """
    try:
        raw_input = sys.stdin.read()

        if not raw_input.strip():
            sys.exit(0)

        input_data = json.loads(raw_input)
        cwd = input_data.get("cwd", os.getcwd())

        profile_path = find_user_profile(cwd)

        if profile_path is None:
            # No USER.md found — silent no-op
            sys.exit(0)

        content = profile_path.read_text(encoding="utf-8").strip()

        if not content:
            # Empty file — silent no-op
            sys.exit(0)

        # Output wrapped in system-reminder tags for Claude Code ingestion
        print(f"<system-reminder>\n{content}\n</system-reminder>")

    except json.JSONDecodeError:
        # Malformed input — fail silently
        sys.exit(0)
    except Exception as e:
        # Hooks must never crash the session
        print(f"Warning: load-user-profile hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
