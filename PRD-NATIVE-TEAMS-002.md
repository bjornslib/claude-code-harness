# PRD-NATIVE-TEAMS-002: Migration of Orchestration Infrastructure to Native Agent Teams

**Status**: DRAFT
**Author**: System 3 Meta-Orchestrator
**Date**: 2026-02-06
**Version**: 1.0
**Depends on**: PRD-NATIVE-TEAMS-001 (compatibility confirmed)

---

## 1. Problem Statement

Our harness has two output styles and two skills that define the 3-tier agent hierarchy. Every worker delegation currently uses `Task(subagent_type=...)` — an ephemeral subagent pattern where workers spawn, execute, and return results synchronously. Epic 1 and Epic 3 PoC from PRD-NATIVE-TEAMS-001 confirmed that Claude Code's native Agent Teams provide:

- **Teammate spawning** via `Task(..., team_name="X", name="Y")`
- **Peer messaging** via `SendMessage` with file-based inboxes
- **Shared task list** via the same `TaskCreate/TaskUpdate/TaskList` tools
- **Idle agent wake-up** via incoming peer messages
- **Graceful shutdown** via `SendMessage(type="shutdown_request")`

**What PRD-001 did NOT address**: The actual migration of our output styles, skills, templates, and scripts to USE these native features. Our orchestrator still says `Task(subagent_type=...)` on line 13. Our system3 skill still spawns orchestrators without `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Our worker skill still assumes assignments arrive via prompt parameter.

This PRD defines the concrete file changes needed to migrate from Task-subagent worker delegation to native team teammate coordination.

---

## 2. Architecture: Before vs After

### Before (Current)

```
System 3 (ccsystem3)
    │
    ├── tmux spawn ───► Orchestrator (ccorch in worktree)
    │                       │
    │   SQLite message      ├── Task(subagent_type="frontend-dev-expert") → returns result
    │   bus for comms       ├── Task(subagent_type="backend-solutions-engineer") → returns result
    │                       ├── Task(subagent_type="tdd-test-engineer") → returns result
    │                       └── Task(subagent_type="validation-agent") → returns result
    │
    └── tmux capture-pane for monitoring
```

**Characteristics**:
- Workers are ephemeral (spawn, execute, die)
- No worker-to-worker communication
- Orchestrator blocks waiting for Task() result
- System 3 monitors via tmux + background Haiku agents
- SQLite message bus for System 3 ↔ Orchestrator

### After (Migration Target)

```
System 3 (ccsystem3, OUTSIDE teams)
    │
    ├── tmux spawn ───► Orchestrator AS TEAM LEAD (with AGENT_TEAMS=1)
    │                       │
    │   SQLite message      ├── Teammate: worker-frontend (frontend-dev-expert)
    │   bus for S3↔Orch     ├── Teammate: worker-backend (backend-solutions-engineer)
    │                       ├── Teammate: worker-test (tdd-test-engineer)
    │                       └── Task(subagent_type="validation-agent") ← UNCHANGED
    │
    │   Native inboxes for Orch↔Workers and Worker↔Worker
    │
    └── tmux + TaskList monitoring (native task system)
```

**Characteristics**:
- Workers persist as teammates (can receive multiple tasks)
- Worker-to-worker peer messaging for collaboration
- Orchestrator delegates via TaskCreate + SendMessage
- Workers claim and complete via TaskUpdate
- validation-agent REMAINS a Task subagent (special authority pattern)

### What Does NOT Change

| Component | Why Unchanged |
|-----------|--------------|
| System 3 stays outside teams | Autonomous steering, completion promises, stop gate |
| System 3 → Orchestrator via tmux | Session isolation with env vars, worktree management |
| SQLite message bus (S3 ↔ Orch) | System 3 is not a team member, can't use SendMessage |
| validation-agent via Task subagent | Must maintain single-authority closure pattern |
| Beads integration (bd commands) | Orchestrator-beads relationship unchanged |
| Hook system | Per PRD-001 finding: no changes needed |
| Serena checkpoint protocol | Worker-level code quality, independent of coordination |

---

## 3. Artifact Inventory: Files to Migrate

### Tier 1: Output Styles (100% load guarantee, most critical)

| File | Lines | Current Pattern | Migration Required |
|------|-------|----------------|-------------------|
| `output-styles/orchestrator.md` | 135 | `Task(subagent_type=...)` throughout | **REWRITE** delegation section |
| `output-styles/system3-meta-orchestrator.md` | 2197 | References Task subagents for monitoring | **UPDATE** spawn + monitor sections |

### Tier 2: Skills (loaded on-demand, detailed patterns)

| File | Size | Current Pattern | Migration Required |
|------|------|----------------|-------------------|
| `skills/orchestrator-multiagent/SKILL.md` | ~45KB | Core orchestration with Task delegation | **MAJOR REWRITE** |
| `skills/orchestrator-multiagent/WORKERS.md` | ~15KB | Task subagent spawning, templates | **MAJOR REWRITE** |
| `skills/orchestrator-multiagent/WORKFLOWS.md` | ~12KB | Multi-feature loops with Task() | **UPDATE** delegation patterns |
| `skills/orchestrator-multiagent/VALIDATION.md` | ~8KB | Validation via Task subagent | **MINOR UPDATE** (stays Task-based) |
| `skills/orchestrator-multiagent/REFERENCE.md` | ~10KB | Worker types, message bus | **UPDATE** worker types + messaging |
| `skills/orchestrator-multiagent/ORCHESTRATOR_INITIALIZATION_TEMPLATE.md` | ~4KB | Message bus registration | **UPDATE** add team creation |
| `skills/orchestrator-multiagent/PREFLIGHT.md` | ~3KB | Session start checklist | **UPDATE** add team init step |
| `skills/system3-orchestrator/SKILL.md` | ~18KB | Spawn workflow, monitoring | **UPDATE** env var + wisdom injection |
| `skills/system3-orchestrator/scripts/spawn-orchestrator.sh` | ~150 lines | tmux spawn sequence | **UPDATE** add env var |
| `skills/system3-orchestrator/examples/wisdom-injection-template.md` | ~2KB | Task-based starting point | **UPDATE** add team coordination |
| `skills/worker-focused-execution/SKILL.md` | ~12KB | Assignment via prompt parameter | **UPDATE** assignment via TaskGet |

### Tier 3: Supporting Infrastructure

| File | Current Pattern | Migration Required |
|------|----------------|-------------------|
| `scripts/message-bus/mb-*` | S3↔Orch communication | **KEEP** (still needed) |
| `hooks/unified_stop_gate/*` | Session identity checks | **NO CHANGE** |
| `documentation/NATIVE-TEAMS-EPIC1-FINDINGS.md` | Testing findings | **REFERENCE ONLY** |

---

## 4. Epic Breakdown

### Epic M1: Orchestrator Output Style Migration

**Priority**: P0 (highest — loaded in every orchestrator session at 100%)
**Scope**: `output-styles/orchestrator.md` (135 lines → ~180 lines)
**Risk**: HIGH — incorrect output style breaks ALL orchestrator sessions

#### Changes Required

**Line 2** — Core principle #2:
```
BEFORE: Workers via Task agents — Use Task(subagent_type=specialist) for structured delegation
AFTER:  Workers via native teammates — Use Teammate + TaskCreate + SendMessage for team coordination
```

**Line 13** — 3-Tier Hierarchy diagram:
```
BEFORE: ──Task──► TIER 3: Worker
AFTER:  ──Team──► TIER 3: Worker (native teammate)
```

**Lines 25-29** — Worker chain description:
```
BEFORE: Worker returns structured results directly to you
AFTER:  Worker marks tasks completed via TaskUpdate and sends results via SendMessage
```

**Lines 31-60** — Worker Delegation Pattern (complete rewrite):
```python
# BEFORE: Task subagent (ephemeral, blocking)
result = Task(
    subagent_type="backend-solutions-engineer",
    prompt="...",
    description="Implement feature"
)

# AFTER: Native teammate (persistent, async)
# Step 1: Create the task
TaskCreate(
    subject="Implement {feature_name}",
    description="**Context**: ...\n**Requirements**: ...\n**Acceptance Criteria**: ...",
    activeForm="Implementing {feature_name}"
)

# Step 2: Spawn or message the worker
Task(
    subagent_type="backend-solutions-engineer",
    team_name="my-team",
    name="worker-backend",
    prompt="You are worker-backend. Check TaskList, claim available tasks, implement, report via SendMessage."
)

# Step 3: Results arrive via SendMessage (auto-delivered)
# Worker sends: SendMessage(type="message", recipient="team-lead", content="Task #X complete: ...")
```

**Lines 62-70** — Available Worker Types table:
```
BEFORE: | Type | subagent_type | Use For |
AFTER:  | Type | subagent_type (used in Task spawn) | Use For |
```
(Table content stays the same — subagent_type is still the parameter name)

**Lines 96-99** — Environment section:
```
ADD: - `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — Native team coordination enabled
```

**Lines 100-135** — TASK CLOSURE GATE:
```
UNCHANGED: validation-agent REMAINS a Task subagent.
Rationale: validation-agent has special authority (sole task closer).
Using it as a teammate would allow other teammates to also close tasks.
Keeping it as a Task subagent preserves the single-authority pattern.
```

#### Acceptance Criteria
- [ ] orchestrator.md shows native team delegation as the PRIMARY pattern
- [ ] Task subagent pattern documented as FALLBACK (when AGENT_TEAMS not enabled)
- [ ] validation-agent explicitly documented as remaining Task-based
- [ ] No Edit/Write enforcement language unchanged (still soft)
- [ ] FIRST ACTION still invokes `Skill("orchestrator-multiagent")`

---

### Epic M2: Orchestrator Skill Migration (orchestrator-multiagent)

**Priority**: P0 (loaded by every orchestrator as first action)
**Scope**: 6 files in `skills/orchestrator-multiagent/`
**Risk**: HIGH — skill guides all worker coordination

#### M2.1: SKILL.md Core Delegation Section

**Current**: Worker delegation via `Task(subagent_type=...)` with blocking results
**Target**: Team-based delegation via `Teammate.spawnTeam` + `TaskCreate` + `SendMessage`

Key sections to rewrite:
- Worker Delegation (currently ~40 lines of Task examples)
- Message Bus Integration (currently ~100 lines → simplify with native messaging)
- Validation Agent section (keep Task-based but clarify WHY)

#### M2.2: WORKERS.md Complete Rewrite

**Current**: 3-tier hierarchy with Task spawning, assignment templates via prompt parameter
**Target**: 3-tier hierarchy with native team spawning, assignment via TaskCreate

| Section | Current Content | New Content |
|---------|----------------|-------------|
| 3-Tier Hierarchy | `──Task()──► Worker` | `──Team──► Worker (native teammate)` |
| Task Delegation Pattern | `Task(subagent_type=..., prompt=...)` | `TaskCreate + Task(..., team_name=..., name=...)` |
| Worker Assignment Template | Full assignment in `prompt` parameter | Assignment in TaskCreate description + SendMessage |
| Parallel Workers | `run_in_background=True` + `TaskOutput()` | Multiple teammates + TaskList polling |
| Worker Types | Same types, different spawn mechanism | Same types via `subagent_type` in `Task(..., team_name=...)` |
| Voting/Consensus | Via parallel Task subagents | Via parallel teammates + SendMessage results |

#### M2.3: WORKFLOWS.md Update

**Current**: Multi-feature loop with `Task()` calls
**Target**: Multi-feature loop with team coordination

Key change: The autonomous execution loop currently does:
```python
for feature in features:
    result = Task(subagent_type=..., prompt=...)  # blocks
    validate(result)
```
Must become:
```python
# Create team at start
Teammate(operation="spawnTeam", team_name="epic-workers")
# Spawn workers
Task(subagent_type=..., team_name="epic-workers", name="worker-1")

for feature in features:
    TaskCreate(subject=feature, description=...)  # non-blocking
    SendMessage(recipient="worker-1", content="New task available")
    # Worker claims, implements, reports via SendMessage
```

#### M2.4: ORCHESTRATOR_INITIALIZATION_TEMPLATE.md Update

**Current**: Steps 1-5 include message bus registration, background monitor
**Target**: Add Step 0: Create team. Simplify message bus (keep for S3 only).

```markdown
## Step 0: Create Worker Team (NEW)
Teammate(operation="spawnTeam", team_name="{initiative}-workers", description="...")
```

#### M2.5: REFERENCE.md Update

**Current**: Worker types table, message bus commands, session templates
**Target**: Update worker types spawn syntax, add SendMessage patterns

#### M2.6: PREFLIGHT.md Update

**Current**: Session start checklist
**Target**: Add team creation as step after skill invocation

#### Acceptance Criteria
- [ ] All 6 files updated with native team patterns
- [ ] Task subagent examples replaced with Teammate/SendMessage equivalents
- [ ] Validation-agent explicitly marked as remaining Task-based
- [ ] Worker assignment template uses TaskCreate description field
- [ ] Parallel worker pattern uses multiple teammates + TaskList
- [ ] Message bus section simplified (S3↔Orch only)

---

### Epic M3: System 3 Output Style Updates

**Priority**: P1 (affects how S3 instructs orchestrators)
**Scope**: `output-styles/system3-meta-orchestrator.md` (~2197 lines)
**Risk**: MEDIUM — changes are additive, not replacements

#### Changes Required

**Spawning Orchestrators section** (~line 578):
Add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` to the environment variables list:
```bash
# EXISTING env vars:
export CLAUDE_SESSION_DIR=[initiative]-$(date +%Y%m%d)
export CLAUDE_SESSION_ID=orch-[name]
export CLAUDE_CODE_TASK_LIST_ID=PRD-[prd-name]

# NEW env var:
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

**Initialization Template section** (~line 626):
Update the wisdom injection instructions to tell orchestrators about team coordination:
```markdown
## FIRST ACTIONS (Do Not Skip)
1. Invoke Skill: Skill("orchestrator-multiagent")
2. Create Worker Team: Teammate(operation="spawnTeam", ...)  ← NEW
3. Register with Message Bus (for System 3 communication)
4. Spawn Background Monitor
```

**Multi-Orchestrator Monitoring section** (~line 748):
Update the blocking watcher to also check native team task status:
```python
# In addition to tmux capture-pane, check team task list:
TaskList  # Shows worker task completion status
```

**Worker Delegation references** (scattered):
Update any references to "orchestrators delegate to workers via Task subagents" → "orchestrators delegate to workers as native teammates"

#### Acceptance Criteria
- [ ] `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in spawn env vars
- [ ] Initialization template includes team creation step
- [ ] Monitoring section updated for team-aware checking
- [ ] References to Task subagent worker delegation updated

---

### Epic M4: System 3 Orchestrator Skill Updates

**Priority**: P1 (spawn workflow must include feature flag)
**Scope**: `skills/system3-orchestrator/` (SKILL.md, scripts, templates)

#### M4.1: spawn-orchestrator.sh

**Add between existing env var exports and `launchcc` command**:
```bash
# Enable native agent teams for orchestrator
tmux send-keys -t "$SESSION_NAME" "export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"
tmux send-keys -t "$SESSION_NAME" Enter
```

#### M4.2: SKILL.md Spawn Workflow

Update the Manual tmux Commands section to include the new env var:
```bash
# 4. CRITICAL: Set env vars BEFORE launching Claude
tmux send-keys -t "orch-[name]" "export CLAUDE_SESSION_DIR=..."
tmux send-keys -t "orch-[name]" "export CLAUDE_SESSION_ID=orch-[name]"
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_TASK_LIST_ID=PRD-[prd-name]"
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"  # NEW
```

#### M4.3: wisdom-injection-template.md

Add team coordination to the "Starting Point" section:
```markdown
## Starting Point
1. **Invoke skill**: Skill("orchestrator-multiagent")
2. **Create worker team**: Teammate(operation="spawnTeam", team_name="{initiative}-workers")  ← NEW
3. **Run PREFLIGHT checklist**
4. **Find first task**: bd ready
```

#### M4.4: Monitoring Section Updates

Update the monitoring patterns to account for native team tasks:
- Blocking watcher can poll `TaskList` (native team task system) in addition to tmux
- Background monitors can check inbox messages for worker completion
- Cleanup section: add `Teammate(operation="cleanup")` after tmux session kill

#### Acceptance Criteria
- [ ] spawn-orchestrator.sh exports AGENT_TEAMS env var
- [ ] SKILL.md spawn workflow includes 4th env var
- [ ] Wisdom injection template includes team creation
- [ ] Monitoring patterns updated for team-aware checking
- [ ] Cleanup includes team teardown

---

### Epic M5: Worker Skill Migration (worker-focused-execution)

**Priority**: P1 (workers must understand new assignment model)
**Scope**: `skills/worker-focused-execution/SKILL.md` (~12KB)

#### Changes Required

**Assignment Reception** (how workers get their work):
```
BEFORE: Assignment arrives via Task() prompt parameter — full context in one message
AFTER:  Assignment arrives via TaskList — worker checks TaskList, claims with TaskUpdate(owner=name)
```

**Completion Reporting**:
```
BEFORE: Worker returns structured markdown as Task() return value
AFTER:  Worker marks TaskUpdate(status="completed") AND sends SendMessage to orchestrator
```

**Task Claiming**:
```
BEFORE: Implicit (Task() call assigns work directly)
AFTER:  Explicit (worker checks TaskList, claims unowned tasks via TaskUpdate)
```

**Status Updates**:
```
BEFORE: No intermediate updates (orchestrator blocks until completion)
AFTER:  Worker can send progress via SendMessage during long tasks
```

**Blocker Reporting**:
```
BEFORE: Blocker returned as Task() result
AFTER:  Blocker sent via SendMessage(type="message") with BLOCKED status
```

**Unchanged**:
- Serena checkpoint protocol (still 3 checkpoints)
- Scope enforcement (still scope array in task description)
- TDD/verification workflow
- Voting mechanism (same independence rule, different result delivery)

#### Acceptance Criteria
- [ ] Worker skill describes TaskList-based assignment claiming
- [ ] Completion reporting uses TaskUpdate + SendMessage
- [ ] Intermediate progress updates documented
- [ ] Blocker reporting via SendMessage documented
- [ ] Serena checkpoints unchanged
- [ ] Voting mechanism updated for teammate delivery

---

### Epic M6: Documentation and ADR

**Priority**: P2
**Scope**: Documentation files

#### M6.1: ADR-002: Native Agent Teams Migration

Create `documentation/ADR-002-native-teams-migration.md`:
- Decision: Migrate worker delegation from Task subagents to native teammates
- Context: Epic 1+3 PoC confirmed compatibility
- Consequences: Peer messaging enabled, async coordination, validation-agent stays Task-based
- Tradeoffs: Higher token cost per worker, but better coordination quality

#### M6.2: Update CLAUDE.md Files

Both `CLAUDE.md` and `.claude/CLAUDE.md`:
- Update 3-Tier Hierarchy diagram to show native teams
- Update "Workers via Task subagents" → "Workers via native teammates"
- Add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` to environment variables table

#### M6.3: Migration Guide

Create `documentation/NATIVE-TEAMS-MIGRATION-GUIDE.md`:
- Step-by-step migration from old to new patterns
- Common pitfalls and solutions
- Rollback procedure (remove env var to disable)

#### Acceptance Criteria
- [ ] ADR-002 documents the decision with rationale
- [ ] Both CLAUDE.md files reflect new architecture
- [ ] Migration guide covers rollback

---

## 5. Migration Strategy

### Phase 1: Foundation (Epics M1, M4)
**Duration**: 1 session
**Why first**: Output style is loaded at 100% — must be correct before orchestrators launch

1. Update `orchestrator.md` with native team patterns
2. Update `spawn-orchestrator.sh` with env var
3. Update system3 wisdom injection template

### Phase 2: Skill Details (Epics M2, M3, M5)
**Duration**: 1-2 sessions
**Why second**: Skills provide detailed patterns that build on the output style foundation

1. Rewrite `WORKERS.md` with native team patterns
2. Update `SKILL.md` core delegation section
3. Update `WORKFLOWS.md` execution loops
4. Update `worker-focused-execution/SKILL.md` assignment model
5. Update system3 output style spawn references

### Phase 3: Documentation (Epic M6)
**Duration**: 1 session
**Why last**: Documents the completed migration

1. Create ADR-002
2. Update CLAUDE.md files
3. Write migration guide

### Rollback Strategy

**Instant rollback**: Remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` from:
- `.claude/settings.json` (global)
- `spawn-orchestrator.sh` (per-orchestrator)

**Output style rollback**: Output style should document BOTH patterns (native team as primary, Task subagent as fallback). If agent teams feature is disabled or broken, orchestrators fall back to Task pattern automatically.

---

## 6. Design Decisions

### D1: validation-agent Remains Task-Based

**Decision**: validation-agent is NOT migrated to a native teammate.

**Rationale**:
- validation-agent has **special authority** — it is the ONLY agent allowed to close tasks via `bd close`
- Making it a teammate would place it at the same level as implementation workers
- The single-authority closure pattern is a critical safety mechanism
- Task subagent pattern provides natural isolation: spawn, validate, return result, exit

### D2: System 3 Stays Outside Teams

**Decision**: System 3 does NOT become a team member.

**Rationale**:
- System 3 needs autonomous steering (completion promises, stop gate, Hindsight)
- Team leads can be shut down by team members (shutdown_request)
- System 3 must persist beyond any single orchestrator's lifecycle
- tmux provides necessary session isolation with env var control

### D3: Both Patterns in Output Style

**Decision**: Output style documents BOTH native team AND Task subagent patterns.

**Rationale**:
- Agent teams is experimental — may change or break
- Graceful degradation if feature flag is not set
- Orchestrators can choose pattern based on env var availability
- ADR-001 principle: output styles must be reliable

### D4: Message Bus Coexistence

**Decision**: Keep SQLite message bus for System 3 ↔ Orchestrator communication.

**Rationale**:
- System 3 is outside native teams — cannot use SendMessage to orchestrators
- Message bus provides persistence across session boundaries
- Native inbox is ephemeral (lost on team cleanup)
- Future: May deprecate message bus if System 3 adopts native teams (unlikely per D2)

### D5: Worker Assignment via TaskCreate Description

**Decision**: Worker assignments use the `description` field of TaskCreate, not separate prompt files.

**Rationale**:
- TaskCreate description is the natural place for task details
- Workers use TaskGet to read full assignment
- No need for external file-based assignment delivery
- Consistent with how native teams already work (as proven in Epic 3 PoC)

---

## 7. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Worker-to-worker messaging | Enabled | Workers can peer-message without orchestrator relay |
| Orchestrator delegation clarity | Improved | No ambiguity about Task vs Teammate in output style |
| Worker persistence | Enabled | Same worker handles multiple sequential tasks |
| Rollback time | < 1 minute | Remove env var, restart |
| Output style size | < 200 lines | Keep thin, reference skill for details |
| Skill file sizes | ≤ current | No bloat from dual-pattern documentation |

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Experimental feature changes API | Medium | High | Dual-pattern documentation, rollback strategy |
| Workers don't claim tasks autonomously | Low | Medium | Clear assignment via SendMessage after TaskCreate |
| Higher token cost per worker | High | Low | Accept per PRD-001 Q6 decision |
| Teammate spawn failures | Low | Medium | Fallback to Task subagent pattern |
| validation-agent confused by team context | Low | High | Keep validation-agent as Task subagent (D1) |

---

## 9. Non-Goals

- Migrating System 3 into native teams
- Deprecating the SQLite message bus entirely
- Migrating validation-agent to native teammate
- Changing the 3-tier hierarchy itself (only the delegation mechanism changes)
- Hook system modifications (confirmed unnecessary in PRD-001)
- Changing beads integration patterns
