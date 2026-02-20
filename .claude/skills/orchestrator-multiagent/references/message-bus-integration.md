---
title: "Message Bus Integration"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Message Bus Integration

**Scope**: The message bus handles communication between **System 3 and Orchestrators** only. Worker communication within a team uses native Agent Teams (SendMessage/TaskCreate) -- NOT the message bus.

| Communication Path | Mechanism |
|--------------------|-----------|
| System 3 <-> Orchestrator | Message Bus (mb-* commands) |
| Orchestrator <-> Worker | Native Teams (SendMessage, TaskCreate, TaskList) |
| Worker <-> Worker (peers) | Native Teams (SendMessage) |

**Architecture Reference**: See [MESSAGE_BUS_ARCHITECTURE.md](../../../documentation/MESSAGE_BUS_ARCHITECTURE.md) for the complete architecture overview.

## Session Start: Register with Message Bus

At the START of every orchestrator session:

```bash
# 1. Register with message bus
.claude/scripts/message-bus/mb-register \
    "${CLAUDE_SESSION_ID:-orch-$(basename $(pwd))}" \
    "$(tmux display-message -p '#S' 2>/dev/null || echo 'unknown')" \
    "[Your initiative description]" \
    --initiative="[epic-name]" \
    --worktree="$(pwd)"
```

## Receiving Messages from System 3

Messages from System 3 are automatically injected via PostToolUse hook.

For manual check:
```bash
/check-messages
```

## Responding to System 3 Guidance

When you receive a `guidance` message:
1. Acknowledge receipt
2. Adjust priorities if needed
3. Continue execution

```bash
.claude/scripts/message-bus/mb-send "system3" "response" '{
    "subject": "Guidance acknowledged",
    "body": "Shifting focus to API endpoints as requested",
    "context": {"original_type": "guidance"}
}'
```

## Sending Completion Reports

When completing a task or epic:

```bash
.claude/scripts/message-bus/mb-send "system3" "completion" '{
    "subject": "Epic 4 Complete",
    "body": "All tasks closed, tests passing",
    "context": {
        "initiative": "epic-4",
        "beads_closed": ["agencheck-041", "agencheck-042"],
        "test_results": "42 passed, 0 failed"
    }
}'
```

## Session End: Cleanup

Before session ends:

```bash
# 1. Shutdown team (sends shutdown_request to all teammates)
# Use SendMessage(type="shutdown_request", recipient="worker-backend") for each teammate
# Wait for shutdown confirmations, then:
Teammate(operation="cleanup")

# 2. Unregister from message bus
.claude/scripts/message-bus/mb-unregister "${CLAUDE_SESSION_ID}"
```

**Note**: Native team teammates are shut down via `SendMessage(type="shutdown_request")`. Team cleanup via `Teammate(operation="cleanup")` removes team directories.

## Updated Session Handoff Checklist

Add to your session start/end routines:

**Session Start:**
- [ ] Register with message bus (`mb-register`)
- [ ] Create worker team (`Teammate(operation="spawnTeam")`)
- [ ] Spawn specialist workers and validator as teammates

**Session End:**
- [ ] Send completion report to System 3 (`mb-send`)
- [ ] Shutdown teammates (`SendMessage(type="shutdown_request")`)
- [ ] Clean up team (`Teammate(operation="cleanup")`)
- [ ] Unregister from message bus (`mb-unregister`)

## Message Types You May Receive (from System 3)

| Type | From | Action |
|------|------|--------|
| `guidance` | System 3 | Adjust approach, acknowledge |
| `broadcast` | System 3 | Note policy/announcement |
| `query` | System 3 | Respond with status |
| `urgent` | System 3 | Handle immediately |

## CLI Commands Quick Reference

| Command | Purpose |
|---------|---------|
| `mb-recv` | Check for pending messages from System 3 |
| `mb-send` | Send message to System 3 or other orchestrator |
| `mb-register` | Register this session |
| `mb-unregister` | Unregister this session |
| `mb-list` | List active orchestrators |
| `mb-status` | Queue status overview |

**Full Guide**: See [message-bus skill](../../message-bus/SKILL.md)
