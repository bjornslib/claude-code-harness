#!/usr/bin/env python3
"""Unified stop gate hook wrapper script.

This wrapper provides the entry point for the Claude Code stop hook,
delegating to the unified_stop_gate package.

Usage in settings.json:
    "Stop": {
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/unified-stop-gate.py"
    }
"""

import sys
from pathlib import Path

# Add the hooks directory to the path for package imports
hooks_dir = Path(__file__).parent
sys.path.insert(0, str(hooks_dir))

from unified_stop_gate.main import main

if __name__ == "__main__":
    main()
