#!/usr/bin/env python3
"""
SessionStart hook for context re-injection after compaction.

Reads preserved System3 context and selectively re-injects it
when the session resumes after context compression.

This works with context-preserver-hook.py:
1. PreCompact: Saves key instructions and progress
2. SessionStart (source=compact): Re-injects relevant context

Hook type: SessionStart
"""

import json
import os
import sys
import time
from pathlib import Path


# Maximum age for preserved context (24 hours)
MAX_CONTEXT_AGE_SECONDS = 24 * 3600


def main():
    """Main hook entry point."""
    try:
        # Read hook input
        try:
            raw_input = sys.stdin.read()
            hook_input = json.loads(raw_input) if raw_input.strip() else {}
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        # Only act on post-compaction
        source = hook_input.get("source", "")
        if source != "compact":
            # Not a compaction event
            sys.exit(0)

        # Get paths
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        hooks_dir = Path(project_dir) / ".claude" / "hooks"
        state_dir = Path(project_dir) / ".claude" / "state" / "decision-guidance"
        preserved_file = state_dir / "preserved-context.json"

        # Check for preserved context
        if not preserved_file.exists():
            sys.exit(0)

        # Load preserved context
        try:
            with open(preserved_file, "r") as f:
                preserved = json.load(f)
        except (json.JSONDecodeError, IOError):
            sys.exit(0)

        # Check age
        preserved_at = preserved.get("preserved_at", 0)
        if time.time() - preserved_at > MAX_CONTEXT_AGE_SECONDS:
            # Too old, remove and skip
            preserved_file.unlink(missing_ok=True)
            sys.exit(0)

        # Check session ID match (only inject if same session)
        current_session = os.environ.get("CLAUDE_SESSION_ID", "")
        preserved_session = preserved.get("session_id_env", "")

        # Allow injection if:
        # 1. Same session ID, OR
        # 2. Both are orchestrator sessions (orch-* prefix), OR
        # 3. No session ID set (default behavior)
        should_inject = (
            current_session == preserved_session or
            (current_session.startswith("orch-") and preserved_session.startswith("orch-")) or
            not current_session
        )

        if not should_inject:
            sys.exit(0)

        # Add hooks dir to path for imports
        sys.path.insert(0, str(hooks_dir))

        from decision_guidance.goal_validator import GoalValidator

        validator = GoalValidator()

        # Format preserved context for injection
        formatted = validator.format_preserved_context(preserved)

        # Print as system reminder for injection
        print(f"""<system-reminder>
{formatted}
</system-reminder>""")

        # Log for debugging
        debug_file = state_dir / "reinjection.log"
        with open(debug_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Re-injected context: {preserved.get('completion_pct', 0):.0f}% complete\n")

        # Clean up preserved file (consumed)
        preserved_file.unlink(missing_ok=True)

    except Exception as e:
        # On any error, don't block
        debug_file = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "state" / "decision-guidance" / "errors.log"
        try:
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_file, "a") as f:
                f.write(f"[SessionStart-Reinjector] Error: {e}\n")
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
