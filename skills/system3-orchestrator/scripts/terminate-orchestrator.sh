#!/bin/bash
# Gracefully terminate an orchestrator session
#
# Usage: ./terminate-orchestrator.sh <initiative-name> [--force]

set -euo pipefail

INITIATIVE="${1:?Usage: $0 <initiative-name> [--force]}"
FORCE="${2:-}"
SESSION_NAME="orch-${INITIATIVE}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if session exists
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log_error "Session not found: $SESSION_NAME"
    exit 1
fi

if [ "$FORCE" = "--force" ] || [ "$FORCE" = "-f" ]; then
    # Force kill
    log_warn "Force terminating: $SESSION_NAME"
    tmux kill-session -t "$SESSION_NAME"
else
    # Graceful shutdown
    log_info "Sending graceful shutdown to: $SESSION_NAME"

    # Send /exit command
    tmux send-keys -t "$SESSION_NAME" "/exit" Enter

    log_info "Waiting for graceful shutdown (10 seconds)..."
    sleep 10

    # Check if still running
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        log_warn "Session still active, sending Ctrl+C..."
        tmux send-keys -t "$SESSION_NAME" C-c
        sleep 2

        if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
            log_warn "Session still active, force killing..."
            tmux kill-session -t "$SESSION_NAME"
        fi
    fi
fi

# Update registry
REGISTRY_FILE=".claude/state/active-orchestrators.json"
if [ -f "$REGISTRY_FILE" ]; then
    jq --arg name "$SESSION_NAME" \
       '.orchestrators = [.orchestrators[] | select(.name != $name)]' \
       "$REGISTRY_FILE" > "${REGISTRY_FILE}.tmp" && mv "${REGISTRY_FILE}.tmp" "$REGISTRY_FILE"
    log_info "Removed from registry"
fi

log_info "Orchestrator terminated: $SESSION_NAME"
log_info ""
log_info "Next steps:"
log_info "  1. Review progress: cat trees/$INITIATIVE/agencheck/.claude/progress/orch-${INITIATIVE}-log.md"
log_info "  2. Merge work: cd trees/$INITIATIVE/agencheck && git push"
log_info "  3. Clean up worktree: /remove_worktree $INITIATIVE"
