# Tmux Commands Reference

All tmux commands for orchestrator management.

---

## Session Management

### Create Session

```bash
# Create detached session
tmux new-session -d -s "orch-[name]"

# Create and attach
tmux new-session -s "orch-[name]"
```

### List Sessions

```bash
# All sessions
tmux list-sessions

# Orchestrator sessions only
tmux list-sessions -F "#{session_name}" | grep "^orch-"

# With creation time
tmux list-sessions -F "#{session_name}: #{session_created}"
```

### Check Session Exists

```bash
# Returns 0 if exists, 1 if not
tmux has-session -t "orch-[name]"

# With conditional
if tmux has-session -t "orch-[name]" 2>/dev/null; then
    echo "Session exists"
fi
```

### Attach to Session

```bash
# Simple attach
tmux attach -t "orch-[name]"

# Attach read-only (for monitoring)
tmux attach -t "orch-[name]" -r
```

### Detach from Session

```
# From within tmux
Ctrl+b d

# From command line (detach other clients)
tmux detach -s "orch-[name]"
```

---

## Sending Commands

### Send Keys

```bash
# Send text and Enter
tmux send-keys -t "orch-[name]" "command here" Enter

# Send text without Enter (for partial input)
tmux send-keys -t "orch-[name]" "partial text"

# Send special keys
tmux send-keys -t "orch-[name]" C-c     # Ctrl+C
tmux send-keys -t "orch-[name]" C-d     # Ctrl+D
tmux send-keys -t "orch-[name]" C-l     # Clear screen
tmux send-keys -t "orch-[name]" Escape  # Escape key
```

### Send Multi-line Content

```bash
# Using heredoc
tmux send-keys -t "orch-[name]" "$(cat << 'EOF'
Multi-line
content
here
EOF
)" Enter

# From file
tmux send-keys -t "orch-[name]" "$(cat message.md)" Enter
```

---

## Capturing Output

### Capture Current Pane

```bash
# Print to stdout
tmux capture-pane -t "orch-[name]" -p

# Last N lines
tmux capture-pane -t "orch-[name]" -p | tail -20

# Save to file
tmux capture-pane -t "orch-[name]" -p > output.txt
```

### Capture with History

```bash
# Capture including scrollback (last 1000 lines)
tmux capture-pane -t "orch-[name]" -p -S -1000

# Full history
tmux capture-pane -t "orch-[name]" -p -S -
```

### Capture Range

```bash
# Specific line range (0 = current, negative = scrollback)
tmux capture-pane -t "orch-[name]" -p -S -50 -E -1
```

---

## Session Termination

### Graceful Exit

```bash
# Send /exit command (for Claude Code)
tmux send-keys -t "orch-[name]" "/exit" Enter

# Wait and verify
sleep 10
tmux has-session -t "orch-[name]" 2>/dev/null || echo "Exited cleanly"
```

### Force Kill

```bash
# Kill specific session
tmux kill-session -t "orch-[name]"

# Kill all orchestrator sessions
tmux list-sessions -F "#{session_name}" | grep "^orch-" | xargs -I {} tmux kill-session -t {}
```

### Interrupt and Kill

```bash
# Send Ctrl+C first
tmux send-keys -t "orch-[name]" C-c
sleep 2
tmux kill-session -t "orch-[name]"
```

---

## Window Management

### Multiple Windows in Session

```bash
# Create new window
tmux new-window -t "orch-[name]"

# Create named window
tmux new-window -t "orch-[name]" -n "logs"

# Switch windows
tmux select-window -t "orch-[name]:0"  # First window
tmux select-window -t "orch-[name]:1"  # Second window
```

---

## Pane Splitting

### Split Current Window

```bash
# Horizontal split
tmux split-window -h -t "orch-[name]"

# Vertical split
tmux split-window -v -t "orch-[name]"

# Target specific pane
tmux send-keys -t "orch-[name].0" "command" Enter  # First pane
tmux send-keys -t "orch-[name].1" "command" Enter  # Second pane
```

---

## Monitoring Scripts

### Watch Session Output

```bash
# Continuous monitoring
watch -n 5 'tmux capture-pane -t orch-[name] -p | tail -10'
```

### Check All Orchestrators

```bash
#!/bin/bash
for session in $(tmux list-sessions -F "#{session_name}" | grep "^orch-"); do
    echo "=== $session ==="
    tmux capture-pane -t "$session" -p | tail -5
    echo ""
done
```

### Wait for Pattern

```bash
# Wait until Claude responds
while ! tmux capture-pane -t "orch-[name]" -p | grep -q "pattern"; do
    sleep 5
done
echo "Pattern found!"
```

---

## Useful Aliases

Add to your `.bashrc`:

```bash
# Orchestrator aliases
alias orch-list='tmux list-sessions | grep orch-'
alias orch-status='./scripts/status-orchestrators.sh'

# Quick attach function
orch() {
    tmux attach -t "orch-$1"
}

# Quick peek function
orch-peek() {
    tmux capture-pane -t "orch-$1" -p | tail -${2:-20}
}

# Quick guidance function
orch-say() {
    tmux send-keys -t "orch-$1" "$2" Enter
}
```

---

## Common Patterns

### Spawn and Inject

```bash
tmux new-session -d -s "orch-[name]"
tmux send-keys -t "orch-[name]" "cd trees/[name]/agencheck && launchcc" Enter
sleep 5
tmux send-keys -t "orch-[name]" "$(cat wisdom.md)" Enter
```

### Poll Until Complete

```bash
while tmux has-session -t "orch-[name]" 2>/dev/null; do
    if tmux capture-pane -t "orch-[name]" -p | grep -q "COMPLETE"; then
        echo "Orchestrator finished!"
        break
    fi
    sleep 60
done
```

### Emergency Recovery

```bash
# If stuck, interrupt and restart
tmux send-keys -t "orch-[name]" C-c
sleep 2
tmux send-keys -t "orch-[name]" "Continue from where you left off" Enter
```
