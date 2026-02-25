#!/usr/bin/env python3
"""
PostToolUse hook (async) — gentle advisory to use Serena for code navigation.

Fires after Read/Grep calls that were approved (e.g., non-code files or when Serena
is not active). Provides a systemMessage reminder on the next conversation turn.

This is a non-blocking advisory layer. It does NOT prevent any operations.

Hook type : PostToolUse (matcher: "Read|Grep", async: true)
Input     : JSON on stdin with {"tool_name": "Read"|"Grep", "tool_input": {...}}
Output    : JSON on stdout — {} (no-op) or {"systemMessage": "..."}

PRD: PRD-SERENA-ENFORCE-001
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# Source code extensions worth advising about
SOURCE_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".jsx", ".js",
    ".vue", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".swift", ".c", ".cpp",
})

# Directories where we don't advise (already whitelisted in pretool)
WHITELISTED_DIRS = frozenset({
    ".claude", ".taskmaster", "acceptance-tests", "docs", "documentation",
    ".beads", ".serena", ".zerorepo", ".github", ".vscode",
    "node_modules", "__pycache__", ".git",
})


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print("{}")
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Skip if Serena not active
    serena_config = Path(project_dir) / ".serena" / "project.yml"
    if not serena_config.exists():
        print("{}")
        sys.exit(0)

    # Skip if bypass active
    if os.environ.get("SERENA_ENFORCE_SKIP", "").strip() in ("1", "true", "yes"):
        print("{}")
        sys.exit(0)

    # Extract target path
    if tool_name == "Read":
        target_path = tool_input.get("file_path", "")
    elif tool_name == "Grep":
        target_path = tool_input.get("path", "")
    else:
        print("{}")
        sys.exit(0)

    if not target_path:
        print("{}")
        sys.exit(0)

    # Skip whitelisted directories
    try:
        rel = Path(target_path).relative_to(project_dir)
        if rel.parts and rel.parts[0] in WHITELISTED_DIRS:
            print("{}")
            sys.exit(0)
    except ValueError:
        pass

    # Check if this was a source code file that somehow got through
    ext = Path(target_path).suffix.lower()
    if ext in SOURCE_CODE_EXTENSIONS:
        print(json.dumps({
            "systemMessage": (
                "[serena-advisory] Serena is active for this project. "
                "For future code exploration, prefer: "
                "find_symbol (read functions/classes), "
                "search_for_pattern (search code), "
                "get_symbols_overview (file structure). "
                "These provide targeted extraction with 70-95% token savings vs Read/Grep."
            )
        }))
        sys.exit(0)

    # Non-code file — no advisory needed
    print("{}")
    sys.exit(0)


if __name__ == "__main__":
    main()
