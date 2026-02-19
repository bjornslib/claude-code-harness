---
name: message-bus
description: Inter-instance messaging system for Claude Code sessions. Use when you need to send messages between System 3 and orchestrators, broadcast announcements, register/unregister orchestrators, or spawn message queue monitors. Triggers on messaging, communication, broadcast, orchestrator registry, inter-instance.
title: "Message Bus"
status: active
---

# Message Bus Skill

Real-time communication between Claude Code instances (System 3, Orchestrators, Workers).

## Quick Reference

| Command | Purpose |
|---------|---------|
| `mb-init` | Initialize message bus database |
| `mb-send` | Send message to orchestrator(s) |
| `mb-recv` | Receive pending messages |
| `mb-register` | Register orchestrator |
| `mb-unregister` | Unregister orchestrator |
| `mb-list` | List active orchestrators |
| `mb-status` | Show queue status |

**Scripts location**: `.claude/scripts/message-bus/`

---

## Initialization

Before first use, initialize the message bus:

```bash
.claude/scripts/message-bus/mb-init
```

This creates:
- SQLite database: `.claude/message-bus/queue.db`
- Signal directory: `.claude/message-bus/signals/`

---

## Sending Messages

### To a Specific Orchestrator

```bash
# Standard message
.claude/scripts/message-bus/mb-send orch-epic4 guidance \
    '{"subject":"Priority shift","body":"Focus on API endpoints first"}'

# Urgent message (triggers tmux injection for immediate attention)
.claude/scripts/message-bus/mb-send orch-epic4 urgent \
    '{"subject":"Stop work","body":"Regression detected"}' --urgent
```

### Broadcast to All Orchestrators

```bash
.claude/scripts/message-bus/mb-send --broadcast announcement \
    '{"subject":"Policy update","body":"All commits require passing tests"}'
```

### Message Types

| Type | Purpose | Default Priority |
|------|---------|------------------|
| `guidance` | Strategic direction from System 3 | 3 |
| `completion` | Task/epic completion report | 5 |
| `broadcast` | Announcements to all | 5 |
| `query` | Status request | 4 |
| `response` | Query response | 4 |
| `urgent` | High-priority, triggers tmux inject | 1 |
| `heartbeat` | Periodic status update | 10 |

### Message Payload Schema

```json
{
    "subject": "Brief subject line",
    "body": "Detailed message content",
    "context": {
        "initiative": "epic-4",
        "beads_ref": "agencheck-042"
    },
    "action_requested": "none|acknowledge|respond|execute"
}
```

---

## Receiving Messages

### Automatic (Recommended)

Messages are automatically detected via:
1. **Background Monitor Agent**: Polls queue, returns message to main agent when found
2. **PostToolUse Hook**: Checks signal file after each tool execution
3. **System3 tmux Injection**: For idle orchestrators, System3 injects `/check-messages` via tmux

### Manual Check

```bash
# Check for messages
.claude/scripts/message-bus/mb-recv

# Peek without marking as read
.claude/scripts/message-bus/mb-recv --peek

# JSON output
.claude/scripts/message-bus/mb-recv --json
```

Or use the slash command:
```
/check-messages
```

---

## Orchestrator Registry

### Register (at session start)

```bash
.claude/scripts/message-bus/mb-register \
    "orch-epic4" \                    # Instance ID
    "orch-epic4" \                    # tmux session name
    "Epic 4 Orchestrator" \           # Description
    --initiative="epic4" \            # Initiative being worked on
    --worktree="/path/to/worktree"    # Worktree path
```

### Unregister (at session end)

```bash
.claude/scripts/message-bus/mb-unregister "orch-epic4"
```

### List Active Orchestrators

```bash
# Active only
.claude/scripts/message-bus/mb-list

# Include stopped
.claude/scripts/message-bus/mb-list --all

# JSON output
.claude/scripts/message-bus/mb-list --json
```

---

## Background Monitor Agent

Each orchestrator should spawn a background monitor at session start.

### Spawn the Monitor

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description="Message queue monitor",
    prompt=open(".claude/skills/message-bus/monitor-prompt-template.md").read().format(
        instance_id=instance_id
    )
)
```

### Monitor Behavior

1. Polls SQLite queue every 3 seconds
2. When message found:
   - Marks message as read
   - Writes signal file for PostToolUse hook
   - Completes with message content (returns to main agent)
3. Updates heartbeat every iteration
4. Times out after 10 minutes (should be respawned)

**Note**: The monitor does NOT handle tmux injection. System3 monitors orchestrators and injects `/check-messages` for idle agents as needed.

---

## Session Integration

### For System 3

At session start:
```bash
# Initialize (if needed)
.claude/scripts/message-bus/mb-init

# Register System 3
.claude/scripts/message-bus/mb-register "system3" "main" "System 3 Meta-Orchestrator"

# Check status
.claude/scripts/message-bus/mb-status
```

When spawning orchestrators:
```bash
# After orchestrator launches, it should register itself
# Include in wisdom injection:
# "Register with message bus: mb-register orch-[name] ..."
```

### For Orchestrators

**⚠️ CRITICAL**: Before launching Claude Code, set `CLAUDE_SESSION_ID` environment variable:

```bash
# In the tmux session, BEFORE running launchcc:
export CLAUDE_SESSION_ID=orch-[name]
launchcc
```

Without this, the PostToolUse hook cannot detect incoming messages!

At session start (after Claude Code is running):
```bash
# Register
.claude/scripts/message-bus/mb-register \
    "${CLAUDE_SESSION_ID}" \
    "$(tmux display-message -p '#S')" \
    "[Initiative description]" \
    --initiative="[epic-name]"

# Spawn background monitor (see above)
```

When completing work:
```bash
# Send completion report
.claude/scripts/message-bus/mb-send "system3" "completion" '{
    "subject": "Epic 4 Complete",
    "body": "All tasks closed, tests passing",
    "context": {"initiative": "epic-4", "test_results": "42 passed"}
}'
```

At session end:
```bash
.claude/scripts/message-bus/mb-unregister "${CLAUDE_SESSION_ID}"
```

---

## Status and Debugging

```bash
# Full status overview
.claude/scripts/message-bus/mb-status

# Check specific orchestrator's pending messages
.claude/scripts/message-bus/mb-recv --instance=orch-epic4 --peek

# View message log
sqlite3 .claude/message-bus/queue.db "SELECT * FROM message_log ORDER BY timestamp DESC LIMIT 20"
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        MESSAGE FLOW                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SENDER                           RECEIVER                       │
│  ┌─────────────────┐              ┌─────────────────────────┐   │
│  │ mb-send         │              │ Background Monitor      │   │
│  │                 │   SQLite     │ (Haiku sub-agent)       │   │
│  │ 1. Insert msg   │ ──────────► │                         │   │
│  │ 2. Touch signal │              │ Polls every 3s          │   │
│  └─────────────────┘              │                         │   │
│                                   │ On message:             │   │
│                                   │ 1. Mark read            │   │
│                                   │ 2. Write signal file    │   │
│                                   │ 3. Complete (return)    │   │
│                                   └───────────┬─────────────┘   │
│                                               │                  │
│        ┌──────────────────────────────────────┼──────────────┐  │
│        │                                      ▼              │  │
│        │  Main Agent checks:                                 │  │
│        │  • Background task output (monitor completed)       │  │
│        │  • PostToolUse hook (signal file triggered)         │  │
│        │                                                     │  │
│        └─────────────────────────────────────────────────────┘  │
│                                                                  │
│  IDLE AGENT WAKE-UP (System3 responsibility):                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ System3 monitors orchestrators → detects idle state →    │   │
│  │ tmux inject `/check-messages` → orchestrator wakes up    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files

| File | Purpose |
|------|---------|
| `.claude/message-bus/queue.db` | SQLite database |
| `.claude/message-bus/signals/*.signal` | Signal files |
| `.claude/message-bus/signals/*.msg` | Message content |
| `.claude/scripts/message-bus/mb-*` | CLI scripts |
| `.claude/hooks/message-bus-signal-check.py` | PostToolUse hook |
| `.claude/commands/check-messages.md` | Slash command |

---

**Version**: 1.0.1
**Dependencies**: SQLite3, tmux (for System3 idle wake-up only)
**Integration**: system3-meta-orchestrator, orchestrator-multiagent
