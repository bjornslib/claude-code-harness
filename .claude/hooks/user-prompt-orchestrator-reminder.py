#!/usr/bin/env python3
"""
UserPromptSubmit Hook: Orchestrator Skill Reminder Injector

This hook runs when the user submits a prompt. It checks for a flag file set by
the SessionStart hook indicating the orchestrator skill was active before compaction.

If the flag exists, it injects a reminder to reinvoke the orchestrator skill and
removes the flag so the reminder only appears once.

stdout is injected as context when exit code is 0.

DISTRIBUTION NOTE: This hook should be placed in .claude/hooks/ at the project level
for projects using the orchestrator-multiagent skill.
"""

import json
import sys
from pathlib import Path


SKILL_NAME = "orchestrator-multiagent"
FLAG_FILE = Path.home() / ".claude" / "state" / "orchestrator-reminder-pending"


def main():
    """
    Main entry point for the UserPromptSubmit hook.

    Input JSON:
    {
        "session_id": "...",
        "transcript_path": "...",
        "prompt": "user's prompt",
        ...
    }

    Output: Plain text stdout is injected as context.
    """
    try:
        # Read stdin (required even if we don't use it)
        _ = json.load(sys.stdin)

        # Check if reminder flag exists
        if FLAG_FILE.exists():
            skill_name = FLAG_FILE.read_text().strip()

            # Remove the flag so reminder only shows once
            FLAG_FILE.unlink()

            # Inject reminder as context with delegation checklist
            reminder = f"""<system-reminder>
🔄 POST-COMPACTION ORCHESTRATOR CHECKLIST

The '{skill_name}' skill was active before context compression.

## MANDATORY ACTIONS:
1. ☐ Re-invoke skill: Skill("{skill_name}")
2. ☐ Check work queue: `bd ready`
3. ☐ Review in-progress tasks: `bd list --status=in_progress`

## CRITICAL DELEGATION RULE:
Before using Edit/Write/MultiEdit tools, STOP and ask:
- "Is this INVESTIGATION or IMPLEMENTATION?"
- Investigation → Use Read/Grep/Glob directly ✅
- Implementation → Delegate via tmux worker ⚠️

## IF IMPLEMENTATION IS NEEDED:
```bash
# Create worker session
tmux new-session -d -s worker-<task-id>
tmux send-keys -t worker-<task-id> "cd $(pwd) && claude"
tmux send-keys -t worker-<task-id> Enter
# Send task assignment...
```

## ANTI-PATTERN ALERT:
❌ "It's just a small change" → STILL DELEGATE
❌ "I'm continuing previous work" → STILL DELEGATE
❌ Task(subagent_type="backend-solutions-engineer") → WRONG, use tmux

Orchestrator = Coordinator. Worker = Implementer. No exceptions.
</system-reminder>"""
            print(reminder)

    except Exception as e:
        # Hooks should fail gracefully - don't block user prompts
        print(f"Warning: UserPromptSubmit hook error: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
