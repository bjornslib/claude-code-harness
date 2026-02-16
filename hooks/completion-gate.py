#!/usr/bin/env python3
"""
completion-gate.py - Stop hook that gates session completion based on completion promise.

This hook integrates with the completion-state tracking system to ensure
sessions only end when user goals are verifiably achieved.

Hook type: Stop
Input: JSON with stop_reason on stdin
Output: JSON with decision

Returns:
  {"decision": "allow"} - All criteria met or no constraints
  {"decision": "block", "reason": "..."} - Criteria not met
"""

import json
import subprocess
import sys
from pathlib import Path


def main():
    # Read hook input
    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        hook_input = {}

    # Get project directory
    project_dir = Path.cwd()
    state_file = project_dir / ".claude" / "completion-state" / "session-state.json"
    cs_verify = project_dir / ".claude" / "scripts" / "completion-state" / "cs-verify"

    # No completion state = no constraints
    if not state_file.exists():
        print(json.dumps({"decision": "allow"}))
        return

    # Check if cs-verify exists
    if not cs_verify.exists():
        print(json.dumps({"decision": "allow"}))
        return

    # Run cs-verify --check
    try:
        result = subprocess.run(
            [str(cs_verify), "--check"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_dir)
        )

        if result.returncode == 0:
            # All criteria met
            print(json.dumps({
                "decision": "allow",
                "reason": "Completion criteria satisfied."
            }))
        elif result.returncode == 2:
            # Criteria not met - block with reason
            output = result.stdout.strip()

            # Format for Claude's context
            message = f"""
## STOP BLOCKED: COMPLETION PROMISE UNMET

{output}

Continue working to satisfy the completion criteria. Use `cs-status` for full state.
"""
            print(json.dumps({
                "decision": "block",
                "reason": message
            }))
        else:
            # Error - allow to avoid infinite loop
            print(json.dumps({
                "decision": "allow",
                "reason": f"Error checking completion state (code {result.returncode})"
            }))

    except subprocess.TimeoutExpired:
        print(json.dumps({
            "decision": "allow",
            "reason": "Completion check timed out"
        }))
    except Exception as e:
        print(json.dumps({
            "decision": "allow",
            "reason": f"Error: {str(e)}"
        }))


if __name__ == "__main__":
    main()
