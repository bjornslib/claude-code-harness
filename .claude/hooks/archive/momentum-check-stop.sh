#!/bin/bash
# momentum-check-stop.sh
# StopHook that reminds System 3 to verify productive work is exhausted
#
# Part of the Momentum Maintenance Protocol:
# - Always maintain at least one continuation todo item
# - This hook reminds (but doesn't block) on every stop attempt
# - Uses dual-bank Hindsight for informed priority decisions

# Read input from stdin (Claude Code passes context as JSON)
INPUT=$(cat)

# Output a system message reminder
cat << 'EOF'
{
  "decision": "approve",
  "systemMessage": "## Momentum Check\n\nBefore stopping, complete this protocol:\n\n### 1. Memory-Guided Priority Check\n```python\n# Recall shared priorities from project bank\nmcp__hindsight__recall(\"What are current priorities? What work has highest Signal?\", bank_id=\"claude-code-agencheck\")\n\n# Reflect in private bank to synthesize decision\nmcp__hindsight__reflect(\"Given current priorities and beads state, should I continue working or is stopping appropriate?\", budget=\"mid\", bank_id=\"claude-code-system3\")\n```\n\n### 2. Work Discovery\n- Run `bd ready` to see unblocked P0-P2 work\n- Check active tmux orchestrator sessions\n- Look for **Signal** (business-advancing work) over Noise\n\n### 3. Continuation Protocol\nIf work exists with clear path:\n- **Don't defer** - proceed autonomously\n- Add specific todo items for the work\n- Continue without asking permission\n\nIf genuinely complete:\n- Retain session learnings to shared bank\n- Reflect on meta-patterns to private bank\n- Add continuation todo: \"Check bd ready for next session\"\n- Proceed to stop\n\n### 4. Decision Framework\n- **Continue** if: P0-P2 beads ready, clear implementation path, no user input needed\n- **Stop** if: Only P3-P4 work, blocked on external factors, user feedback required"
}
EOF

exit 0
