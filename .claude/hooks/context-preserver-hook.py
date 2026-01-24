#!/usr/bin/env python3
"""
PreCompact hook for context preservation.

Captures System3's original instructions and current progress state
before context compression, enabling selective re-injection afterward.

This implements idea #1 from Replit's decision-time guidance:
- Extract key instructions that must survive compaction
- Store in a way that allows selective re-injection
- Only inject what's relevant to current work

Hook type: PreCompact
"""

import json
import os
import sys
import time
from pathlib import Path


def main():
    """Main hook entry point."""
    try:
        # Read hook input
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        # Get paths
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        hooks_dir = Path(project_dir) / ".claude" / "hooks"
        state_dir = Path(project_dir) / ".claude" / "state" / "decision-guidance"
        preserved_file = state_dir / "preserved-context.json"

        # Add hooks dir to path for imports
        sys.path.insert(0, str(hooks_dir))

        from decision_guidance.goal_validator import GoalValidator

        # Initialize validator
        validator = GoalValidator()

        # Load current completion state
        state = validator.load_completion_state()

        if state is None:
            # No state to preserve
            print(json.dumps({"continue": True}))
            return

        # Extract context to preserve
        preserved = validator.should_preserve_context(state)

        # Add session info
        preserved["session_id_env"] = os.environ.get("CLAUDE_SESSION_ID", "")
        preserved["hook_source"] = "PreCompact"
        preserved["preserved_at"] = time.time()

        # Save preserved context
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(preserved_file, "w") as f:
            json.dump(preserved, f, indent=2)

        # Log for debugging
        debug_file = state_dir / "precompact.log"
        with open(debug_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Preserved context: {preserved.get('completion_pct', 0):.0f}% complete\n")

        print(json.dumps({"continue": True}))

    except Exception as e:
        # On any error, don't block
        debug_file = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "state" / "decision-guidance" / "errors.log"
        try:
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_file, "a") as f:
                f.write(f"[PreCompact] Error: {e}\n")
        except Exception:
            pass

        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
