# Quick Reference

Essential commands and patterns for orchestrator sessions.

## Table of Contents
- [Beads Commands](#beads-commands)
- [Epic Hierarchy](#epic-hierarchy)
- [Key Directories](#key-directories)
- [Service Ports](#service-ports)
- [Environment Variables](#environment-variables)
- [Session Start Template](#session-start-template)

---

## Beads Commands

### Finding Work

```bash
bd ready                          # Get unblocked tasks (MOST IMPORTANT)
bd list                           # All tasks
bd list --status=open             # Open tasks only
bd list --status=closed           # Closed tasks only
bd show <bd-id>                   # Task details with dependencies
bd stats                          # Project statistics
bd blocked                        # Show blocked issues and why
```

### Status Updates

```bash
bd update <bd-id> --status in_progress   # Mark as started
bd close <bd-id>                          # Mark complete
bd close <bd-id> --reason "Validated"     # Close with reason
bd reopen <bd-id>                         # Reopen if regression found
```

### Creating Tasks

```bash
bd create "Task title" -p 0              # Priority 0 (highest)
bd create "Task title" -p 1              # Priority 1 (normal)
bd create --title="..." --type=epic      # Create epic
bd create --title="..." --type=task      # Create task
```

### Dependencies

```bash
bd dep add <child> <parent>              # Add dependency
bd dep add <id> <id> --type=parent-child # Organizational grouping
bd dep add <id> <id> --type=blocks       # Sequential requirement
bd dep list <bd-id>                      # Show dependencies
bd dep remove <child> <parent>           # Remove dependency
```

### Sync & Commit

```bash
bd sync                                  # Sync with git remote
git add .beads/ && git commit -m "feat(<bd-id>): [description]"
```

---

## Epic Hierarchy

Every initiative requires this structure:

```
UBER-EPIC: Initiative Name
├── EPIC: Feature A ─────────────────────┐
│   ├── TASK: Implementation 1           │ [parent-child]
│   ├── TASK: Implementation 2           │ Concurrent work OK
│   └── TASK 3 → TASK 4 [blocks]         │
│                                        │
├── EPIC: AT-Feature A ──────────────────┤ [blocks]
│   └── TASK: E2E Tests                  │ AT blocks functional epic
│                                        │
├── EPIC: Feature B ─────────────────────┤
│   └── TASK: Implementation             │ [parent-child]
│                                        │
└── EPIC: AT-Feature B ──────────────────┘ [blocks]
    └── TASK: Validation tests
```

### Dependency Types

| Type | Blocks `bd ready`? | Use For |
|------|-------------------|---------|
| `parent-child` | No | Uber-epic→Epic, Epic→Task (organizational) |
| `blocks` | Yes | AT-epic→Functional-epic, Task→Task (sequential) |
| `related` | No | Cross-reference (soft link) |
| `discovered-from` | No | Bugs found during work |

### Quick Setup Example

```bash
# 1. Create uber-epic (ALWAYS FIRST)
bd create --title="Q1 Authentication" --type=epic --priority=1
# Returns: agencheck-001

# 2. Create functional + AT epic pair
bd create --title="User Login Flow" --type=epic --priority=2      # agencheck-002
bd create --title="AT-User Login Flow" --type=epic --priority=2   # agencheck-003
bd dep add agencheck-002 agencheck-001 --type=parent-child        # Under uber-epic
bd dep add agencheck-003 agencheck-001 --type=parent-child        # Under uber-epic
bd dep add agencheck-002 agencheck-003 --type=blocks              # AT blocks functional

# 3. Create tasks
bd create --title="Implement login API" --type=task --priority=2  # agencheck-004
bd dep add agencheck-004 agencheck-002 --type=parent-child        # Under epic
```

### Closure Order (MUST follow)

```
AT tasks → AT epic → Functional epic → Uber-epic
```

---

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `.beads/` | Task state (managed by `bd` commands) |
| `.claude/progress/` | Session summaries and logs |
| `.claude/learnings/` | Accumulated patterns |
| `.claude/state/` | Mappings and state files |
| `.taskmaster/` | Task Master tasks and PRDs |

---

## Service Ports

| Port | Service |
|------|---------|
| 5001 | Frontend (Next.js) |
| 8000 | Backend (FastAPI) |
| 5184 | eddy_validate MCP |
| 5185 | user_chat MCP |

### Service Commands

```bash
# Start services
cd agencheck-support-agent && ./start_services.sh
cd agencheck-support-frontend && npm run dev

# Verify running
lsof -i :5001 -i :8000 -i :5184 -i :5185 | grep LISTEN
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_SESSION_ID` | Session isolation for message bus |
| `CLAUDE_OUTPUT_STYLE` | Active output style |

---

## Session Start Template

### PREFLIGHT Checklist

Run this at the start of every orchestrator session:

```markdown
### Phase 1: Tool Activation
- [ ] Serena: `mcp__serena__activate_project("agencheck")`
- [ ] Serena: `mcp__serena__check_onboarding_performed`

### Phase 2: Memory Check
- [ ] Hindsight: `mcp__hindsight__recall("What should I remember about [current task]?")`
- [ ] Serena: `mcp__serena__list_memories` (if relevant)

### Phase 3: Beads Status
- [ ] `bd ready` - Find unblocked tasks
- [ ] `bd stats` - Overall progress

### Phase 4: Service Health (if executing)
- [ ] Frontend: `curl -s http://localhost:5001 > /dev/null && echo "OK"`
- [ ] Backend: `curl -s http://localhost:8000/health`

### Phase 5: Regression Check (pick 1-2 closed tasks)
- [ ] `bd list --status=closed` - Select tasks
- [ ] Run validation (Unit + API + E2E)
- [ ] If fail: `bd reopen <id>` and fix BEFORE new work
```

### Message Bus Registration

```bash
# Register with message bus
.claude/scripts/message-bus/mb-register \
    "${CLAUDE_SESSION_ID:-orch-$(basename $(pwd))}" \
    "$(tmux display-message -p '#S' 2>/dev/null || echo 'unknown')" \
    "[Initiative description]" \
    --initiative="[epic-name]" \
    --worktree="$(pwd)"
```

### Session End Checklist

```markdown
- [ ] Feature complete or cleanly stopped
- [ ] `bd sync` - Sync beads state
- [ ] Update `.claude/progress/` with summary
- [ ] `git status` clean, changes committed and pushed
- [ ] `mb-unregister "${CLAUDE_SESSION_ID}"` - Unregister from message bus
- [ ] Hindsight: Store learnings with `mcp__hindsight__retain(...)`
```

---

## Worker Types (via Task Subagents)

| Type | subagent_type | Use For |
|------|---------------|---------|
| Frontend | `frontend-dev-expert` | React, Next.js, UI |
| Backend | `backend-solutions-engineer` | Python, FastAPI, APIs |
| Browser Testing | `tdd-test-engineer` | E2E validation |
| General | `general-purpose` | Everything else |

### Task Delegation Pattern

```python
# Standard blocking delegation
result = Task(
    subagent_type="frontend-dev-expert",
    description="Implement feature",
    prompt="[Worker assignment...]"
)
# Result returned directly - no monitoring needed

# Parallel workers
task1 = Task(subagent_type="...", run_in_background=True, ...)
task2 = Task(subagent_type="...", run_in_background=True, ...)
result1 = TaskOutput(task_id=task1.agent_id, block=True)
result2 = TaskOutput(task_id=task2.agent_id, block=True)
```

---

## Task Lifecycle

```
created (open) → in-progress → closed
     ↑                            │
     └────── reopen ──────────────┘
```

---

**Related Files**:
- [SKILL.md](SKILL.md) - Main orchestrator documentation
- [PREFLIGHT.md](PREFLIGHT.md) - Full pre-flight checklist
- [WORKFLOWS.md](WORKFLOWS.md) - Detailed workflow patterns
- [WORKERS.md](WORKERS.md) - Worker delegation details
- [VALIDATION.md](VALIDATION.md) - Testing and troubleshooting
