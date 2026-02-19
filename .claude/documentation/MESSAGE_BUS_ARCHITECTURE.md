---
title: "Message_Bus_Architecture"
status: active
type: architecture
last_verified: 2026-02-19
grade: reference
---

# Message Bus Architecture

Inter-instance messaging system for communication between Claude Code sessions (System 3, Orchestrators, Workers).

## Overview

The message bus enables real-time coordination in multi-agent Claude Code deployments:
- **System 3** sends strategic guidance and receives completion reports
- **Orchestrators** receive guidance, send status updates, coordinate via broadcasts
- **Workers** receive task assignments, report completion

## System Components

### SQLite Message Queue

| Aspect | Details |
|--------|---------|
| Location | `.claude/message-bus/queue.db` |
| Purpose | Persistent message storage with read/unread tracking |
| Tables | `messages` (queue), `message_log` (audit), `orchestrators` (registry) |

### Signal Directory

| Aspect | Details |
|--------|---------|
| Location | `.claude/message-bus/signals/` |
| Purpose | File-based signal mechanism for PostToolUse hook detection |
| Files | `*.signal` (trigger), `*.msg` (content) |

### CLI Scripts

| Script | Purpose |
|--------|---------|
| `mb-init` | Initialize database and signal directory |
| `mb-send` | Send message to orchestrator(s) |
| `mb-recv` | Receive pending messages |
| `mb-register` | Register instance in orchestrator registry |
| `mb-unregister` | Remove instance from registry |
| `mb-list` | List active orchestrators |
| `mb-status` | Show queue status overview |

**Location**: `.claude/scripts/message-bus/`

## Message Flow

### System 3 → Orchestrator

```
┌──────────────────┐     ┌─────────────────┐     ┌────────────────────────┐
│    System 3      │     │  SQLite Queue   │     │     Orchestrator       │
│                  │     │                 │     │                        │
│  1. mb-send      │────►│  Insert msg     │◄────│  Background Monitor    │
│                  │     │                 │     │  (polls every 3s)      │
│  2. Touch signal │────►│  Signal file    │     │                        │
│     (urgent)     │     │                 │     │  On message found:     │
└──────────────────┘     └─────────────────┘     │  1. Mark read          │
                                                 │  2. Write signal file  │
                                                 │  3. Complete (return)  │
                                                 └───────────┬────────────┘
                                                             │
                              ┌───────────────────────────────┼─────────────┐
                              │                               ▼             │
                              │  Main Agent receives via:                   │
                              │  • Background task output (monitor return)  │
                              │  • PostToolUse hook (signal file trigger)   │
                              │                                             │
                              └─────────────────────────────────────────────┘
```

**Sequence**:
1. System 3 calls `mb-send` with target orchestrator ID
2. Message inserted into SQLite queue
3. For urgent messages: signal file touched for immediate detection
4. Background monitor polls queue, finds message
5. Monitor marks message read, writes signal file, completes
6. Main agent receives message via background task output or PostToolUse hook

### Orchestrator → System 3 (Response/Completion)

```
┌────────────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│     Orchestrator       │     │  SQLite Queue   │     │    System 3      │
│                        │     │                 │     │                  │
│  Task/Epic complete    │     │                 │     │  Receives via:   │
│         │              │     │                 │     │  • mb-recv       │
│         ▼              │     │                 │     │  • Background    │
│  mb-send "system3"     │────►│  Insert msg     │────►│    monitor       │
│  "completion" {...}    │     │  type=completion│     │  • Manual check  │
│                        │     │                 │     │                  │
└────────────────────────┘     └─────────────────┘     └──────────────────┘
```

**Sequence**:
1. Orchestrator completes task/epic
2. Sends completion message targeting "system3"
3. System 3's monitor detects message
4. System 3 updates tracking, may spawn next orchestrator

### Idle Agent Wake-Up (System 3 Responsibility)

```
┌──────────────────┐                              ┌────────────────────────┐
│    System 3      │                              │  Idle Orchestrator     │
│                  │                              │                        │
│  Monitors via    │                              │  Monitor timed out     │
│  mb-list         │                              │  Agent waiting for     │
│       │          │                              │  user input            │
│       ▼          │                              │                        │
│  Detects idle    │──── tmux inject ───────────►│  /check-messages       │
│  orchestrator    │     `/check-messages`        │  forces message check  │
│                  │                              │                        │
└──────────────────┘                              └────────────────────────┘
```

## Message Types

| Type | Direction | Priority | Purpose |
|------|-----------|----------|---------|
| `guidance` | System 3 → Orch | 3 | Strategic direction, pattern reminders |
| `completion` | Orch → System 3 | 5 | Task/epic completion report |
| `broadcast` | System 3 → All | 5 | Announcements, policy changes |
| `query` | Any → Any | 4 | Status request |
| `response` | Any → Any | 4 | Query response |
| `urgent` | Any → Any | 1 | High-priority, triggers tmux inject |
| `heartbeat` | Any → Any | 10 | Periodic status update |

**Message Payload Schema**:
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

## Session Integration

### System 3 Session Lifecycle

| Phase | Actions |
|-------|---------|
| **Start** | `mb-init` (if needed) → `mb-register "system3" "main" "System 3 Meta-Orchestrator"` → `mb-status` |
| **Running** | `mb-send` to orchestrators → `mb-list` to monitor registry → tmux inject for idle agents |
| **End** | Ensure all orchestrators completed → `mb-unregister "system3"` |

### Orchestrator Session Lifecycle

| Phase | Actions |
|-------|---------|
| **Start** | Set `CLAUDE_SESSION_ID` env var → `mb-register` with initiative → Spawn background monitor |
| **Running** | Receive guidance via hook → Acknowledge messages → Execute work |
| **End** | Send `completion` message → `mb-unregister` |

**Critical Requirement**: `CLAUDE_SESSION_ID` must be set BEFORE launching Claude Code:
```bash
export CLAUDE_SESSION_ID=orch-[name]
launchcc
```

Without this, the PostToolUse hook cannot detect incoming messages.

## Detection Mechanisms

### 1. Background Monitor Agent (Primary)

A Haiku sub-agent runs in background:
- Polls SQLite queue every 3 seconds
- On message: marks read, writes signal file, completes
- Times out after 10 minutes (should be respawned)
- Returns message content to main agent

### 2. PostToolUse Hook (Secondary)

After each tool execution:
- Checks for signal files in `.claude/message-bus/signals/`
- If found, injects message into conversation
- Works even without background monitor

### 3. tmux Injection (Fallback for Idle Agents)

System 3 monitors orchestrator activity:
- Detects idle/waiting orchestrators via heartbeat
- Injects `/check-messages` command via tmux
- Forces message check without background monitor

## Failure Modes and Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Monitor timeout | No heartbeat update | Respawn monitor agent |
| Queue corruption | `mb-status` errors | Delete `.claude/message-bus/queue.db`, run `mb-init` |
| Signal file issues | Messages not detected | Check permissions, use manual `/check-messages` |
| Orphaned registration | `mb-list` shows stale entries | Run `mb-unregister` for stale instances |
| PostToolUse hook not firing | Messages delayed | Verify `CLAUDE_SESSION_ID` set, check hook installation |

## Files Reference

| File | Purpose |
|------|---------|
| `.claude/message-bus/queue.db` | SQLite database |
| `.claude/message-bus/signals/*.signal` | Signal trigger files |
| `.claude/message-bus/signals/*.msg` | Message content files |
| `.claude/scripts/message-bus/mb-*` | CLI scripts |
| `.claude/hooks/message-bus-signal-check.py` | PostToolUse hook |
| `.claude/commands/check-messages.md` | Slash command |
| `.claude/skills/message-bus/monitor-prompt-template.md` | Monitor agent prompt |

## References

- **Operational Details**: [`Skill("message-bus")`](.claude/skills/message-bus/SKILL.md) - Full CLI usage, examples
- **System 3 Integration**: [system3-meta-orchestrator.md](.claude/output-styles/system3-meta-orchestrator.md) - Inter-Instance Messaging section
- **Orchestrator Integration**: [`Skill("orchestrator-multiagent")`](.claude/skills/orchestrator-multiagent/SKILL.md) - Message Bus Integration section

---

**Version**: 1.0.0
**Dependencies**: SQLite3, tmux (for idle wake-up)
