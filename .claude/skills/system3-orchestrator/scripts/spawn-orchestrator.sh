#!/bin/bash
# Spawn a new orchestrator in a worktree
#
# Usage: ./spawn-orchestrator.sh <initiative-name> [wisdom-injection-file]
#
# Prerequisites:
#   - Worktree must exist: /create_worktree <initiative-name>
#   - tmux must be installed

set -euo pipefail

INITIATIVE="${1:?Usage: $0 <initiative-name> [wisdom-file]}"
WISDOM_FILE="${2:-}"
SESSION_NAME="orch-${INITIATIVE}"
WORKTREE_PATH="trees/${INITIATIVE}/agencheck"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
if ! command -v tmux &> /dev/null; then
    log_error "tmux is not installed"
    exit 1
fi

if [ ! -d "$WORKTREE_PATH" ]; then
    log_error "Worktree not found: $WORKTREE_PATH"
    log_info "Create it first: /create_worktree $INITIATIVE"
    exit 1
fi

# CRITICAL: Ensure .claude symlink exists for skills/hooks/output-styles
CLAUDE_DIR="$WORKTREE_PATH/.claude"
MAIN_CLAUDE_DIR="$(pwd)/.claude"

if [ ! -e "$CLAUDE_DIR" ]; then
    if [ -d "$MAIN_CLAUDE_DIR" ]; then
        log_info "Creating .claude symlink for worktree..."
        ln -s "$MAIN_CLAUDE_DIR" "$CLAUDE_DIR"
        log_info "Symlinked: $CLAUDE_DIR -> $MAIN_CLAUDE_DIR"
    else
        log_warn ".claude directory not found in main repo: $MAIN_CLAUDE_DIR"
    fi
elif [ -L "$CLAUDE_DIR" ]; then
    log_info ".claude symlink already exists"
else
    log_warn ".claude exists but is not a symlink - skills may not work correctly"
fi

# CRITICAL: Ensure .beads symlink exists for issue tracking
# Note: .beads is at the zenagent level, not agencheck level
WORKTREE_PARENT="$(dirname "$WORKTREE_PATH")"
BEADS_DIR="$WORKTREE_PARENT/.beads"
MAIN_BEADS_DIR="$(dirname "$(pwd)")/.beads"

if [ ! -e "$BEADS_DIR" ]; then
    if [ -d "$MAIN_BEADS_DIR" ]; then
        log_info "Creating .beads symlink for worktree..."
        ln -s "$MAIN_BEADS_DIR" "$BEADS_DIR"
        log_info "Symlinked: $BEADS_DIR -> $MAIN_BEADS_DIR"
    else
        log_warn ".beads directory not found in main repo: $MAIN_BEADS_DIR"
    fi
elif [ -L "$BEADS_DIR" ]; then
    log_info ".beads symlink already exists"
else
    log_warn ".beads exists but is not a symlink - issue tracking may not work correctly"
fi

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log_warn "Session $SESSION_NAME already exists"
    log_info "Attach with: tmux attach -t $SESSION_NAME"
    exit 1
fi

# Create tmux session
log_info "Creating tmux session: $SESSION_NAME"
tmux new-session -d -s "$SESSION_NAME"

# Navigate to worktree
log_info "Navigating to worktree: $WORKTREE_PATH"
tmux send-keys -t "$SESSION_NAME" "cd $WORKTREE_PATH"
tmux send-keys -t "$SESSION_NAME" Enter

# CRITICAL: Set environment variables BEFORE launching Claude Code
# CLAUDE_SESSION_DIR enables session isolation for completion state tracking
# CLAUDE_SESSION_ID enables message bus detection
SESSION_DATE=$(date +%Y%m%d)
log_info "Setting CLAUDE_SESSION_DIR=${INITIATIVE}-${SESSION_DATE}"
tmux send-keys -t "$SESSION_NAME" "export CLAUDE_SESSION_DIR=${INITIATIVE}-${SESSION_DATE}"
tmux send-keys -t "$SESSION_NAME" Enter

log_info "Setting CLAUDE_SESSION_ID=$SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "export CLAUDE_SESSION_ID=$SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" Enter

# Launch Claude Code (Enter must be separate - critical tmux pattern)
log_info "Launching Claude Code..."
tmux send-keys -t "$SESSION_NAME" "launchcc"
tmux send-keys -t "$SESSION_NAME" Enter

# Wait for initialization
log_info "Waiting for Claude Code to initialize (5 seconds)..."
sleep 5

# Send initialization prompt if wisdom file provided
if [ -n "$WISDOM_FILE" ] && [ -f "$WISDOM_FILE" ]; then
    log_info "Injecting wisdom from: $WISDOM_FILE"
    WISDOM_CONTENT=$(cat "$WISDOM_FILE")
    tmux send-keys -t "$SESSION_NAME" "$WISDOM_CONTENT"
    tmux send-keys -t "$SESSION_NAME" Enter
else
    log_info "No wisdom file provided, sending default initialization"
    DEFAULT_PROMPT="You are an orchestrator for initiative: $INITIATIVE

## FIRST ACTIONS (Do Not Skip)

### 1. Invoke Skill (MANDATORY)
Before ANYTHING else: Skill(\"orchestrator-multiagent\")

### 2. Register with Message Bus
.claude/scripts/message-bus/mb-register \"\${CLAUDE_SESSION_ID}\" \"$SESSION_NAME\" \"$INITIATIVE orchestrator\" --initiative=\"$INITIATIVE\"

### 3. Check for Messages from System 3
.claude/scripts/message-bus/mb-recv --peek

## Starting Point
1. Follow PREFLIGHT checklist from the skill
2. Use \`bd ready\` to find your first task
3. Report progress to \`.claude/progress/orch-${INITIATIVE}-log.md\`
4. Send completion messages to System 3 via mb-send

Begin work now."
    tmux send-keys -t "$SESSION_NAME" "$DEFAULT_PROMPT"
    tmux send-keys -t "$SESSION_NAME" Enter
fi

# Update registry
REGISTRY_FILE=".claude/state/active-orchestrators.json"
mkdir -p "$(dirname "$REGISTRY_FILE")"

if [ -f "$REGISTRY_FILE" ]; then
    # Add to existing registry
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    jq --arg name "$SESSION_NAME" \
       --arg init "$INITIATIVE" \
       --arg wt "$WORKTREE_PATH" \
       --arg ts "$TIMESTAMP" \
       '.orchestrators += [{name: $name, initiative: $init, worktree: $wt, status: "active", started_at: $ts}]' \
       "$REGISTRY_FILE" > "${REGISTRY_FILE}.tmp" && mv "${REGISTRY_FILE}.tmp" "$REGISTRY_FILE"
else
    # Create new registry
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    cat > "$REGISTRY_FILE" <<EOF
{
  "orchestrators": [{
    "name": "$SESSION_NAME",
    "initiative": "$INITIATIVE",
    "worktree": "$WORKTREE_PATH",
    "status": "active",
    "started_at": "$TIMESTAMP"
  }]
}
EOF
fi

log_info "Orchestrator spawned successfully!"
log_info "Session: $SESSION_NAME"
log_info "Worktree: $WORKTREE_PATH"
log_info ""
log_info "Commands:"
log_info "  Attach:    tmux attach -t $SESSION_NAME"
log_info "  Monitor:   tmux capture-pane -t $SESSION_NAME -p | tail -20"
log_info "  Terminate: ./scripts/terminate-orchestrator.sh $INITIATIVE"
