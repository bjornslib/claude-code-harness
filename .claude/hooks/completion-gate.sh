#!/bin/bash
# completion-gate.sh - Stop hook that gates session completion based on completion promise
#
# This hook integrates with the completion-state tracking system to ensure
# sessions only end when user goals are verifiably achieved.
#
# Exit codes:
#   0 - Allow stop (all criteria met or no constraints)
#   2 - Block stop, inject reason (criteria not met)

# Get project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATE_DIR="$PROJECT_DIR/.claude/completion-state"
CS_VERIFY="$PROJECT_DIR/.claude/scripts/completion-state/cs-verify"

# Check if completion-state is initialized
if [ ! -f "$STATE_DIR/session-state.json" ]; then
    # No completion state = no constraints
    exit 0
fi

# Check if cs-verify script exists
if [ ! -x "$CS_VERIFY" ]; then
    echo "Warning: cs-verify script not found or not executable"
    exit 0
fi

# Run the completion check (using cs-verify --check)
RESULT=$("$CS_VERIFY" --check 2>&1)
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        # All criteria met - allow stop
        echo "Completion criteria satisfied."
        exit 0
        ;;
    2)
        # Criteria not met - block stop with reason
        echo ""
        echo "========================================"
        echo "STOP BLOCKED: COMPLETION PROMISE UNMET"
        echo "========================================"
        echo ""
        echo "$RESULT"
        echo ""
        echo "Continue working to satisfy completion criteria."
        echo "Use 'cs-status' to see full state."
        echo "Use 'cs-verify --iteration' if starting a new iteration."
        echo ""
        exit 2
        ;;
    *)
        # Error - allow stop to avoid infinite loop
        echo "Error checking completion state (code $EXIT_CODE). Allowing stop."
        exit 0
        ;;
esac
