#!/usr/bin/env python3
"""
PostToolUse hook for decision-time guidance injection.

Implements Replit's decision-time guidance approach:
- Tracks errors in a rolling 5-minute window
- Detects doom loops (same file edited 3+ times)
- Injects short, situational guidance when patterns are detected

Fast path: No-op if no signals detected (<5ms).

Hook type: PostToolUse
"""

import json
import os
import sys
from pathlib import Path


def main():
    """Main hook entry point."""
    try:
        # Read hook input
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        # Fast path: Skip if no tool result
        if "tool_result" not in hook_input and "tool_name" not in hook_input:
            print(json.dumps({"continue": True}))
            return

        # Import classifier (deferred to avoid import overhead when not needed)
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        hooks_dir = Path(project_dir) / ".claude" / "hooks"

        # Add hooks dir to path for imports
        sys.path.insert(0, str(hooks_dir))

        from decision_guidance.classifier import SignalClassifier

        # Initialize classifier
        classifier = SignalClassifier()

        # Analyze tool result
        guidance = classifier.get_guidance_to_inject(hook_input)

        if guidance:
            # Inject guidance into context
            print(json.dumps({
                "continue": True,
                "systemMessage": guidance
            }))
        else:
            # No guidance needed
            print(json.dumps({"continue": True}))

    except Exception as e:
        # On any error, don't block - just continue
        # Log error for debugging but don't inject it
        debug_file = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".claude" / "state" / "decision-guidance" / "errors.log"
        try:
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_file, "a") as f:
                f.write(f"Error: {e}\n")
        except Exception:
            pass

        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
