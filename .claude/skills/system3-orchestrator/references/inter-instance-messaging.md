# Inter-Instance Messaging Reference

> Extracted from `system3-meta-orchestrator.md` to reduce output style context size.
> This is lookup/reference material for the message bus system.

---

### Initialization

At session start, initialize and register:

```bash
# Initialize message bus (if needed)
.claude/scripts/message-bus/mb-init

# Register System 3
.claude/scripts/message-bus/mb-register "system3" "main" "System 3 Meta-Orchestrator"

# Check current status
.claude/scripts/message-bus/mb-status
```

### Sending Messages to Orchestrators

```bash
# Guidance to specific orchestrator
.claude/scripts/message-bus/mb-send "orch-epic4" "guidance" \
    '{"subject":"Priority shift","body":"Focus on API endpoints first"}'

# Broadcast to ALL active orchestrators
.claude/scripts/message-bus/mb-send --broadcast "announcement" \
    '{"subject":"Policy update","body":"All commits require passing tests"}'

# Urgent message (triggers immediate tmux injection)
.claude/scripts/message-bus/mb-send "orch-epic4" "urgent" \
    '{"subject":"Stop work","body":"Regression detected in main branch"}' --urgent
```

### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `guidance` | System 3 -> Orch | Strategic direction, pattern reminders |
| `completion` | Orch -> System 3 | Task/epic completion report |
| `broadcast` | System 3 -> All | Announcements, policy changes |
| `query` | Any -> Any | Status request |
| `urgent` | Any -> Any | High-priority, triggers tmux inject |

### Receiving Messages

Messages are automatically injected via PostToolUse hook. For manual check:

```bash
/check-messages
```

### Orchestrator Registry

View active orchestrators:

```bash
.claude/scripts/message-bus/mb-list
```

When spawning orchestrators, ensure they register:

```bash
# Include in orchestrator's initialization:
.claude/scripts/message-bus/mb-register "orch-[name]" "orch-[name]" "[description]" \
    --initiative="[epic]" --worktree="$(pwd)"
```

### Spawn Background Monitor (Recommended)

For each active session, spawn a background monitor for real-time message detection:

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description="Message queue monitor",
    prompt="""[Monitor prompt from .claude/skills/message-bus/monitor-prompt-template.md]"""
)
```

### Message Flow Architecture

```
System 3 --mb-send--> SQLite Queue <--polls-- Background Monitor (Haiku)
                           |                          |
                           |                          v
                           |                   Signal File
                           |                          |
                           v                          v
                    Orchestrator <----------- PostToolUse Hook
                                              (injects message)
```

### Session End

**MANDATORY cleanup before stopping:**

```bash
# 1. Kill ALL orchestrator tmux sessions spawned during this session
echo "Cleaning up orchestrator sessions..."
for session in $(tmux list-sessions 2>/dev/null | grep "^orch-" | awk -F: '{print $1}'); do
    tmux kill-session -t "$session" 2>/dev/null && echo "Killed: $session"
done

# 2. Verify cleanup
remaining=$(tmux list-sessions 2>/dev/null | grep -c "^orch-" || echo "0")
echo "Remaining orchestrator sessions: $remaining"

# 3. Unregister from message bus
.claude/scripts/message-bus/mb-unregister "system3"
```

**Note**: Workers are now native teammates managed by the team lead (orchestrator). Shut down workers via `SendMessage(type="shutdown_request")` and clean up teams via `Teammate(operation="cleanup")` before killing the orchestrator tmux session.

**When orchestrator completes (before session end):**

After a monitor reports completion, **always review the final report first** (see "Review Final Report Before Cleanup" in the monitoring section), then kill the session:

```bash
# 1. Review final output FIRST
tmux capture-pane -t orch-[initiative] -p -S -200 2>/dev/null | tail -150

# 2. THEN kill the session
tmux kill-session -t orch-[initiative] 2>/dev/null && echo "Cleaned up: orch-[initiative]"
```

**Why review first**: Killing the tmux session destroys the orchestrator's output permanently.
