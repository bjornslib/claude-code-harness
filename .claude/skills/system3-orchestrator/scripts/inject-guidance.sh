#!/bin/bash
# Send guidance message to a running orchestrator
#
# Usage: ./inject-guidance.sh <initiative-name> "<message>"
#    or: ./inject-guidance.sh <initiative-name> --file <message-file>

set -euo pipefail

INITIATIVE="${1:?Usage: $0 <initiative-name> <message> OR $0 <initiative-name> --file <file>}"
SESSION_NAME="orch-${INITIATIVE}"

shift

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check if session exists
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${RED}[ERROR]${NC} Session not found: $SESSION_NAME"
    exit 1
fi

# Get message
if [ "${1:-}" = "--file" ] || [ "${1:-}" = "-f" ]; then
    FILE="${2:?--file requires a filename}"
    if [ ! -f "$FILE" ]; then
        echo -e "${RED}[ERROR]${NC} File not found: $FILE"
        exit 1
    fi
    MESSAGE=$(cat "$FILE")
else
    MESSAGE="${1:?Message required}"
fi

# Send message (text and Enter MUST be separate - Pattern 1)
echo -e "${GREEN}[INFO]${NC} Sending guidance to: $SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "$MESSAGE"
sleep 1  # Allow bracketed paste processing for large messages
tmux send-keys -t "$SESSION_NAME" Enter

echo -e "${GREEN}[INFO]${NC} Guidance sent successfully"
echo -e "${GREEN}[INFO]${NC} View response: tmux capture-pane -t $SESSION_NAME -p | tail -30"
