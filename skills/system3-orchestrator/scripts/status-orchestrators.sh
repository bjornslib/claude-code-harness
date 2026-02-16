#!/bin/bash
# Check status of all orchestrator sessions
#
# Usage: ./status-orchestrators.sh [--verbose]

set -euo pipefail

VERBOSE="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== Orchestrator Status ===${NC}"
echo ""

# Get all orchestrator sessions
SESSIONS=$(tmux list-sessions -F "#{session_name}" 2>/dev/null | grep "^orch-" || true)

if [ -z "$SESSIONS" ]; then
    echo -e "${YELLOW}No active orchestrator sessions found.${NC}"
    exit 0
fi

for session in $SESSIONS; do
    echo -e "${GREEN}[$session]${NC}"

    # Extract initiative name
    INITIATIVE=${session#orch-}
    WORKTREE="trees/${INITIATIVE}/agencheck"

    # Check worktree exists
    if [ -d "$WORKTREE" ]; then
        echo "  Worktree: $WORKTREE"
    else
        echo -e "  Worktree: ${RED}NOT FOUND${NC}"
    fi

    # Check progress log
    PROGRESS_LOG="$WORKTREE/.claude/progress/orch-${INITIATIVE}-log.md"
    if [ -f "$PROGRESS_LOG" ]; then
        LAST_UPDATE=$(stat -c %Y "$PROGRESS_LOG" 2>/dev/null || stat -f %m "$PROGRESS_LOG" 2>/dev/null || echo "0")
        NOW=$(date +%s)
        AGE=$((NOW - LAST_UPDATE))

        if [ $AGE -lt 300 ]; then
            echo -e "  Progress: ${GREEN}Updated ${AGE}s ago${NC}"
        elif [ $AGE -lt 1800 ]; then
            echo -e "  Progress: ${YELLOW}Updated $((AGE / 60))m ago${NC}"
        else
            echo -e "  Progress: ${RED}Stale ($((AGE / 3600))h ago)${NC}"
        fi
    else
        echo -e "  Progress: ${YELLOW}No log file${NC}"
    fi

    # Show recent output if verbose
    if [ "$VERBOSE" = "--verbose" ] || [ "$VERBOSE" = "-v" ]; then
        echo "  Recent output:"
        tmux capture-pane -t "$session" -p 2>/dev/null | tail -5 | sed 's/^/    /'
    fi

    echo ""
done

# Summary
COUNT=$(echo "$SESSIONS" | wc -l | tr -d ' ')
echo -e "${CYAN}Total: $COUNT active orchestrator(s)${NC}"
