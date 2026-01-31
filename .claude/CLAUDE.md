# .claude Configuration Directory

This directory contains Claude Code configuration for the agencheck project.

## Agent Hierarchy

This project uses a 3-level agent hierarchy for complex multi-feature development:

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEVEL 1: SYSTEM 3 (Meta-Orchestrator)                              │
│  Output Style: system3-meta-orchestrator.md                         │
│  Skills: system3-orchestrator/, completion-promise                  │
│  Role: Strategic planning, OKR tracking, business validation        │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 2: ORCHESTRATOR                                              │
│  Output Style: orchestrator.md                                      │
│  Skills: orchestrator-multiagent/                                   │
│  Role: Feature coordination, worker delegation via Task subagents   │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 3: WORKERS (via Task subagents)                              │
│  Specialists: frontend-dev-expert, backend-solutions-engineer,      │
│               tdd-test-engineer, solution-architect                 │
│  Role: Implementation, testing, focused execution                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Launch Commands

| Level | Command | Purpose |
|-------|---------|---------|
| System 3 | `ccsystem3` | Launch meta-orchestrator with completion promises |
| Orchestrator | `launchorchestrator [epic-name]` | Launch in isolated worktree (via tmux) |
| Worker | `Task(subagent_type="...")` | Spawned by orchestrator as Task subagent |

### Key Principle

**Higher levels coordinate; lower levels implement.**
- System 3 sets goals and validates business outcomes
- Orchestrators break down work and delegate to workers
- Workers execute focused tasks and report completion

## Directory Structure

| Path | Purpose |
|------|---------|
| `output-styles/` | Output style definitions (system3-meta-orchestrator.md, orchestrator.md) |
| `skills/` | Skill implementations (system3-orchestrator/, orchestrator-multiagent/) |
| `hooks/` | Pre/post tool hooks for automation |
| `documentation/` | Architecture docs, changelogs |
| `completion-state/` | Session completion tracking |
| `scripts/` | CLI utilities (message-bus, completion state) |

## System3 Monitoring Architecture (2026-01-25)

### Critical Discovery: Wake-Up Mechanism

**Only completing subagents can wake the main thread.** External scripts, file changes, and task list updates do NOT trigger notifications to idle Claude sessions.

This shapes the entire monitoring design: **monitors must be subagents that COMPLETE when attention is needed.**

### Validation-Agent Monitor Mode

System3 uses `validation-agent --mode=monitor` for continuous oversight of orchestrators:

```python
Task(
    subagent_type="validation-agent",
    model="sonnet",  # ⚠️ MUST be Sonnet - Haiku lacks exit discipline
    run_in_background=True,
    prompt="--mode=monitor --session-id=orch-{name} --task-list-id=PRD-{prd}"
)
```

**Monitor Outputs:**
| Status | Meaning | System3 Action |
|--------|---------|----------------|
| `MONITOR_COMPLETE` | All tasks validated ✅ | Run final e2e, close uber-epic |
| `MONITOR_STUCK` | Orchestrator blocked ⚠️ | Send guidance, re-launch monitor |
| `MONITOR_VALIDATION_FAILED` | Work invalid ❌ | Alert orchestrator, re-launch |
| `MONITOR_HEALTHY` | Still working 🔄 | Re-launch monitor (heartbeat) |

### Cyclic Wake-Up Pattern

```
System3                    Monitor (Sonnet)                Orchestrator
   │                            │                              │
   │  Launch monitor ──────────►│                              │
   │                            │◄── Poll task-list-monitor.py │
   │                            │    Detect task completed     │
   │                            │    Validate work...          │
   │◄───── COMPLETE ────────────│                              │
   │  Handle result             │                              │
   │  RE-LAUNCH monitor ───────►│  (cycle repeats)             │
```

### Model Requirements

| Role | Model | Reason |
|------|-------|--------|
| System3 | Opus | Complex strategic reasoning |
| Orchestrator | Sonnet/Opus | Coordination, delegation |
| Worker | Haiku/Sonnet | Simple implementation |
| **Validation Monitor** | **Sonnet** | Exit discipline required |

**Why not Haiku for monitors?** Testing (2026-01-25) showed:
- ✅ Haiku validated correctly (5 tests passed)
- ❌ Haiku failed to EXIT - kept writing documentation
- ✅ Sonnet returned promptly: "MONITOR_COMPLETE: Task #15 validated"

### Task List Monitor Script

`scripts/task-list-monitor.py` provides efficient change detection using MD5 checksums:

```bash
# Detect changes since last poll
python ~/.claude/scripts/task-list-monitor.py --list-id shared-tasks --changes --json

# Output: {"has_changes": true, "changes": [{"task_id": "7", "old_status": "pending", "new_status": "completed"}]}
```

### Task List ID Convention

```
CLAUDE_CODE_TASK_LIST_ID = PRD-{category}-{number}

Examples:
- PRD-AUTH-001 → Authentication feature
- PRD-DASH-002 → Dashboard feature
```

Tasks stored at: `~/.claude/tasks/{CLAUDE_CODE_TASK_LIST_ID}/`

### Key Files

| File | Purpose |
|------|---------|
| `documentation/SYSTEM3_MONITORING_ARCHITECTURE.md` | Full design document |
| `agents/validation-agent.md` | Monitor mode workflow & exit discipline |
| `scripts/task-list-monitor.py` | Efficient change detection |
| `hooks/decision_guidance/goal_validator.py` | Task validation logic |

## Related Documentation

- Main CLAUDE.md: `/agencheck/CLAUDE.md` (project instructions)
- Output Styles: `.claude/output-styles/`
- Skills: `.claude/skills/`
- Architecture: `.claude/documentation/`
