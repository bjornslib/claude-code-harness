---
name: orchestrator-multiagent
description: Multi-agent orchestration for building software incrementally. Use when coordinating workers via native Agent Teams (Teammate + TaskCreate + SendMessage), managing task state with Beads, delegating features to specialized workers (frontend-dev-expert, backend-solutions-engineer, etc.), tracking progress across sessions, or implementing the four-phase pattern (ideation → planning → execution → validation). Triggers on orchestration, coordination, multi-agent, beads, worker delegation, session handoff, progress tracking, agent teams, teammates.
---

# Multi-Agent Orchestrator Skill

## 🚀 SESSION START (Do This First)

| Step | Action | Reference |
|------|--------|-----------|
| 1 | **Pre-Flight Checklist** | Complete [PREFLIGHT.md](PREFLIGHT.md) |
| 2 | **Find Work** | `bd ready` |
| 3 | **Multi-feature?** | See [WORKFLOWS.md](WORKFLOWS.md#autonomous-mode-protocol) |

**Everything below is reference material.**

---

## Core Rule: Delegate, Don't Implement

**Orchestrator = Coordinator. Worker = Implementer.**

```python
# ✅ CORRECT - Worker via native team teammate
# Step 1: Create team (once per session, in PREFLIGHT)
Teammate(
    operation="spawnTeam",
    team_name="{initiative}-workers",
    description="Workers for {initiative}"
)

# Step 2: Create work item
TaskCreate(
    subject="Implement feature F001",
    description="""
    ## Task: [Task title from Beads]

    **Context**: [investigation summary]
    **Requirements**: [list requirements]
    **Acceptance Criteria**: [list criteria]
    **Scope** (ONLY these files): [file list]

    **Report back with**: Files modified, tests written/passed, any blockers
    """,
    activeForm="Implementing F001"
)

# Step 3: Spawn specialist worker into team
Task(
    subagent_type="frontend-dev-expert",
    team_name="{initiative}-workers",
    name="worker-frontend",
    prompt="You are worker-frontend in team {initiative}-workers. Check TaskList for available work. Claim tasks, implement, report completion via SendMessage to team-lead."
)

# Step 4: Worker results arrive via SendMessage (auto-delivered to you)
# Worker sends: SendMessage(type="message", recipient="team-lead", content="Task #X complete: ...")
```

**Why native teams?** Workers are persistent teammates that can claim tasks, communicate with each other, and handle multiple assignments within a single session. The orchestrator creates tasks and workers pick them up -- no blocking, no single-assignment limitation.

**Parallel workers**: Spawn multiple teammates into the same team. Each claims different tasks from the shared TaskList. Workers coordinate peer-to-peer via SendMessage.

---

## BLOCKED COMMANDS (HARD ENFORCEMENT)

**The following commands are BLOCKED for orchestrators:**

| Command | Why Blocked | Alternative |
|---------|-------------|-------------|
| `bd close <id>` | Bypasses validation evidence | Assign to validator teammate via TaskCreate + SendMessage |
| `bd close <id> --reason "..."` | Same - reason doesn't replace evidence | Validator teammate collects actual evidence |
| `Skill("acceptance-test-runner")` | Bypasses validation-test-agent routing | Use validation-test-agent --mode=e2e |
| `Skill("acceptance-test-writer")` | Bypasses validation-test-agent routing | Use validation-test-agent --mode=e2e |

**If you attempt `bd close`**: STOP. Ask yourself:
1. Did I run validation-test-agent --mode=unit or --mode=e2e?
2. Did validation-test-agent produce passing evidence?
3. Did validation-test-agent close the task for me?

If NO to any: You're violating the validation gate. Delegate to validation-test-agent first.

**Correct vs Incorrect Patterns:**

```python
# ---- WRONG: Direct bd close ----
bd close agencheck-042 --reason "Tests passing"

# ---- WRONG: Direct skill invocation ----
Skill("acceptance-test-runner", args="--prd=PRD-001")

# ---- CORRECT: Assign validation to validator teammate ----
# (Validator teammate spawned once per session -- see "Validation Agent" section below)

# Fast unit check
TaskCreate(
    subject="Validate agencheck-042 (unit)",
    description="--mode=unit --task_id=agencheck-042",
    activeForm="Validating agencheck-042"
)
SendMessage(type="message", recipient="validator", content="Unit validation task available for agencheck-042", summary="Validation request")

# Full E2E with PRD acceptance tests
TaskCreate(
    subject="Validate agencheck-042 (e2e)",
    description="--mode=e2e --task_id=agencheck-042 --prd=PRD-AUTH-001\nValidate against acceptance criteria. Close with evidence if passing.",
    activeForm="Validating agencheck-042"
)
SendMessage(type="message", recipient="validator", content="E2E validation task available for agencheck-042", summary="E2E validation request")
# Validator teammate invokes acceptance-test-runner internally and closes with evidence
```

**Exception**: Only the validator teammate is authorized to run `bd close` after verification passes.

---

## Quick Reference

### State Management (Beads - Recommended)

**Primary**: `.beads/` directory managed by `bd` commands

```bash
# Essential Beads commands
bd ready                          # Get unblocked tasks (MOST IMPORTANT)
bd list                           # All tasks
bd show <bd-id>                   # Task details
bd reopen <bd-id>                 # Reopen if regression found
bd dep list <bd-id>               # Show dependencies
```

**Quick Reference**: [REFERENCE.md](REFERENCE.md#beads-commands)

### Worker Types (Spawned as Teammates)

These types are used as `subagent_type` when spawning teammates via `Task(..., team_name=..., name=...)`:

| Type | subagent_type | Teammate Name | Use For |
|------|---------------|---------------|---------|
| Frontend | `frontend-dev-expert` | `worker-frontend` | React, Next.js, UI, TypeScript |
| Backend | `backend-solutions-engineer` | `worker-backend` | Python, FastAPI, PydanticAI, MCP |
| **Browser Testing** | `tdd-test-engineer` | `worker-tester` | **E2E UI validation, automated browser testing** |
| Architecture | `solution-design-architect` | `worker-architect` | Design docs, PRDs |
| General | `Explore` | `worker-explore` | Investigation, code search |
| **Validator** | `validation-test-agent` | `validator` | **Task closure with evidence** |

**Pattern**: Use `Task(subagent_type="...", team_name="...", name="...")` to spawn teammates. Workers claim tasks from the shared TaskList and report via SendMessage.

### Key Directories
- `.beads/` - Task state (managed by `bd` commands)
- `.claude/progress/` - Session summaries and logs
- `.claude/learnings/` - Accumulated patterns

### Service Ports
- Frontend: 5001 | Backend: 8000 | eddy_validate: 5184 | user_chat: 5185

### Essential Commands

```bash
# Services (see VALIDATION.md for details)
./agencheck-support-agent/start_services.sh
cd agencheck-support-frontend && npm run dev

# Task status (Beads - RECOMMENDED)
bd ready                                    # Get unblocked tasks
bd list                                     # All tasks
bd show <bd-id>                             # Task details

# Update task status (Beads)
bd update <bd-id> --status in-progress      # Mark as started
bd close <bd-id> --reason "Validated"       # Mark complete

# Commit (Beads)
git add .beads/ && git commit -m "feat(<bd-id>): [description]"
```

---

## Workflow Triage (MANDATORY FIRST STEP)

**Before any orchestration, determine which workflow applies:**

```
1. Check Beads status: bd list
   ↓
2. If NO TASKS exist → IDEATION + PLANNING MODE (Phase 0 + Phase 1)

   🚨 STOP HERE - Before planning:
   □ Read WORKFLOWS.md Feature Decomposition section (MANDATORY)
   □ Complete Phase 0: Ideation (brainstorming + research)
   □ Create TodoWrite checklist for Phase 1 steps
   ↓
3. If TASKS exist → Check task status: bd stats
   ↓
4. Determine execution workflow type:

   ALL tasks open → EXECUTION MODE (Phase 2)
   SOME tasks closed, some open → CONTINUATION MODE (Phase 2)
   All impl done, AT pending → VALIDATION MODE (Phase 3)
   ALL tasks closed → MAINTENANCE MODE (delegate single hotfix)
```

### Session Start Memory Check (CRITICAL CIRCUIT BREAKER)

**🚨 MANDATORY: Run [PREFLIGHT.md](PREFLIGHT.md) checklist before ANY investigation.**

The preflight includes:
- ✅ Serena activation (code navigation only)
- ✅ Hindsight memory recall (patterns, lessons learned)
- ✅ Service health verification
- ✅ Regression validation (1-2 closed tasks)
- ✅ Session goal determination

**Why This Matters**: Memory check prevents repeating mistakes. Missing memories costs hours of repeated investigation (Session F087-F092 evidence).

### Workflow Decision Matrix

| Scenario | Signs | Workflow |
|----------|-------|----------|
| **Ideation** | No tasks exist, new initiative | Phase 0: Ideation (brainstorming + research) |
| **Planning** | Ideation done, no Beads tasks | Phase 1: Planning (uber-epic + task decomposition + acceptance test generation) |
| **Execution** | Tasks exist, all open | Phase 2: Execution (incremental implementation) |
| **Continuation** | Some tasks closed, some open | Phase 2: Execution (continue from where left off) |
| **Validation** | All impl done, AT pending | Phase 3: Validation (AT epic closure) |
| **Maintenance** | All tasks closed, minor fix needed | Direct Fix (delegate single task) |

---

## The Four-Phase Pattern

### Phase 0: Ideation (Brainstorming + Research)

**Every new project MUST begin with structured ideation.** This is not optional.

**Why Ideation is Mandatory**:
- Explores multiple solution approaches before committing
- Prevents tunnel vision on first idea
- Surfaces hidden requirements and edge cases
- Produces validated design before task decomposition

**Ideation Workflow**:
```
1. Extensive Research
   └─ Use research-tools skill (Perplexity, Brave Search, context7)
   └─ Query: "What are best practices for [your domain]?"
   └─ Document findings in scratch pad
   ↓
2. Brainstorming (MANDATORY)
   └─ Skill("superpowers:brainstorming")
   └─ Refine rough ideas into clear problem statement
   └─ Explore 2-3 alternative approaches with trade-offs
   └─ Output: Validated design document
   ↓
3. Complex Architectures: Parallel-Solutioning (Recommended)
   └─ /parallel-solutioning "Your architectural challenge"
   └─ Deploys 7 solution-architects with diverse reasoning strategies
   └─ Produces consensus architecture from multiple perspectives
   └─ Use for: major features, system integrations, high-risk decisions
   ↓
4. Design Validation
   └─ Skill("superpowers:writing-plan") to convert design into implementation steps
   └─ Review: Is each step small enough for a worker to complete?
   └─ If not: iterate on decomposition
```

**When to Use Parallel-Solutioning**:
| ✅ Use For | ❌ Skip When |
|-----------|-------------|
| New system architecture | Simple bug fixes |
| Multi-service integration | Single-file changes |
| Technology migration | Clear, mechanical processes |
| High business impact decisions | Well-established patterns |

**Ideation Outputs**:
1. **Design Document** → `docs/plans/YYYY-MM-DD-<topic>-design.md`
2. **Implementation Plan** → Ready for Task Master parsing
3. **Research Notes** → Stored in Hindsight via `mcp__hindsight__retain()`

---

### Epic Hierarchy Patterns (MANDATORY)

**Every initiative requires this hierarchy. No exceptions.**

```
UBER-EPIC: "Q1 Authentication System"
│
├── EPIC: User Login Flow ─────────────────┐
│   ├── TASK: Implement login API          │ [parent-child]
│   ├── TASK: Create login form            │ Concurrent work OK
│   └── TASK: Add validation               │
│                                          │
├── EPIC: AT-User Login Flow ──────────────┤ [blocks]
│   ├── TASK: Unit tests for login API     │ AT blocks functional epic
│   ├── TASK: E2E test login flow          │
│   └── TASK: API integration tests        │
│                                          │
├── EPIC: Session Management ──────────────┤
│   ├── TASK: Implement session store      │ [parent-child]
│   └── TASK: Add session timeout          │
│                                          │
└── EPIC: AT-Session Management ───────────┘ [blocks]
    └── TASK: Session validation tests
```

**Quick Setup**:
```bash
# 1. Create uber-epic (ALWAYS FIRST)
bd create --title="Q1 Authentication System" --type=epic --priority=1
# Returns: agencheck-001

# 2. Create functional epic + paired AT epic
bd create --title="User Login Flow" --type=epic --priority=2           # agencheck-002
bd create --title="AT-User Login Flow" --type=epic --priority=2        # agencheck-003
bd dep add agencheck-002 agencheck-003 --type=blocks                   # AT blocks functional

# 3. Create tasks under each epic
bd create --title="Implement login API" --type=task --priority=2
bd dep add agencheck-004 agencheck-002 --type=parent-child             # Task under epic
```

**Dependency Types**:
| Type | Purpose | Blocks `bd ready`? | Use For |
|------|---------|-------------------|---------|
| `parent-child` | Organizational grouping | ❌ No | Uber-epic→Epic, Epic→Task |
| `blocks` | Sequential requirement | ✅ Yes | AT-epic→Functional-epic, Task→Task |

**Key Rules**:
- **Uber-Epic First**: Create before any planning work
- **AT Pairing**: Every functional epic MUST have a paired AT epic
- **Closure Order**: AT tasks → AT epic → Functional epic → Uber-epic
- **Concurrent Development**: `parent-child` allows ALL epics to progress simultaneously

**Validation**: Each AT task must pass 3-level validation (Unit + API + E2E). See [WORKFLOWS.md](WORKFLOWS.md#validation-protocol-31-level).

**Quick Reference**: [REFERENCE.md](REFERENCE.md#epic-hierarchy)

---

### Phase 1: Planning (Uber-Epic + Task Decomposition)

**Prerequisites**:
1. ✅ Phase 0 complete (ideation, brainstorming, research done)
2. ✅ Design document exists (from ideation)
3. ✅ Read [WORKFLOWS.md](WORKFLOWS.md#feature-decomposition-maker) for MAKER decomposition principles

**Planning Workflow**:
```bash
# 1. Create uber-epic in zenagent/ (from validated design)
cd /Users/theb/Documents/Windsurf/zenagent
bd create --title="[Initiative from Ideation]" --type=epic --priority=1
# Note the returned ID (e.g., agencheck-001)

# 2. Create PRD from design document (if not exists)
# Location: agencheck/.taskmaster/docs/[project]-prd.md

# 3. Note current highest task ID before parsing
cd agencheck && task-master list | tail -5  # e.g., last task is ID 170

# 4. Parse PRD with Task Master (--append if tasks exist)
task-master parse-prd .taskmaster/docs/prd.md --research --append
task-master analyze-complexity --research
task-master expand --all --research
# Note the new ID range (e.g., 171-210)

# 5. Sync ONLY new tasks to Beads (run from zenagent/ root!)
cd /Users/theb/Documents/Windsurf/zenagent
node agencheck/.claude/skills/orchestrator-multiagent/scripts/sync-taskmaster-to-beads.js \
    --uber-epic=agencheck-001 \
    --from-id=171 --to-id=210 \
    --tasks-path=agencheck/.taskmaster/tasks/tasks.json
# This also closes Task Master tasks 171-210 (status=done)

# 6. Generate acceptance tests from PRD (IMMEDIATELY after sync)
cd /Users/theb/Documents/Windsurf/zenagent/agencheck
Skill("acceptance-test-writer", args="--prd=PRD-AUTH-001 --source=.taskmaster/docs/prd.md")
# This generates:
# acceptance-tests/PRD-AUTH-001/
# ├── manifest.yaml          # PRD metadata + feature list
# ├── AC-user-login.yaml     # Acceptance criteria
# ├── AC-invalid-credentials.yaml
# └── ...

# 7. Commit acceptance tests
git add acceptance-tests/ && git commit -m "test(PRD-AUTH-001): add acceptance test suite"

# 8. Review hierarchy (filter by uber-epic)
bd list --parent=agencheck-001   # See only tasks under this initiative
bd ready --parent=agencheck-001  # Ready tasks for this initiative only

# 9. Commit planning artifacts (completes Phase 1)
git add .beads/ && git commit -m "plan: initialize [initiative] hierarchy"
# Write progress summary to .claude/progress/
```

### Acceptance Test Generation (Phase 1 Part 2)

**Prerequisites**:
- ✅ Beads hierarchy synced (from sync step above)
- ✅ PRD document exists at `.taskmaster/docs/`

**Workflow**:

```bash
# 6. Generate acceptance tests from PRD (IMMEDIATELY after sync)
Skill("acceptance-test-writer", args="--prd=PRD-AUTH-001 --source=.taskmaster/docs/prd.md")

# This generates:
# acceptance-tests/PRD-AUTH-001/
# ├── manifest.yaml          # PRD metadata + feature list
# ├── AC-user-login.yaml     # Acceptance criteria
# ├── AC-invalid-credentials.yaml
# └── ...

# 7. Commit acceptance tests
git add acceptance-tests/ && git commit -m "test(PRD-AUTH-001): add acceptance test suite"
```

**Why This Timing**:
- Tests generated from fresh PRD → accurate representation
- Tests committed BEFORE Phase 2 → workers can reference them
- Enables early detection of ambiguous acceptance criteria
- Phase 3 validation has tests ready to execute

**Important**:
- acceptance-test-writer is a **Skill** (invoked explicitly)
- Tests are **NOT executed** in Phase 1 (only generated)
- Tests become part of **version control**
- Workers reference tests during Phase 2
- validation-test-agent executes tests during Phase 3 closure

---

**Manual Planning** (Hotfixes only - already have clear scope):
```bash
bd create --title="[Hotfix Description]" --type=epic --priority=1
# Create tasks directly: bd create --title="[Task]" --type=task
# Skip Phase 0 only for emergency fixes with <3 file changes
```

**Warning: Ignore plan skill's "execute with superpowers:executing-plans"** -- we use native Agent Teams teammates.

---

### Sync Script Reference (Task Master → Beads)

The sync script bridges Task Master's flat task structure with Beads' hierarchical filtering.

**🚨 IMPORTANT**: Run from `zenagent/` root (not `agencheck/`) to use the correct `.beads` database.

```bash
# From zenagent/ root:
cd /Users/theb/Documents/Windsurf/zenagent
node agencheck/.claude/skills/orchestrator-multiagent/scripts/sync-taskmaster-to-beads.js [options]
```

**Options**:

| Flag | Purpose |
|------|---------|
| `--uber-epic=<id>` | Link synced tasks to uber-epic via parent-child |
| `--from-id=<id>` | Only sync tasks with ID >= this value |
| `--to-id=<id>` | Only sync tasks with ID <= this value |
| `--tasks-path=<path>` | Path to tasks.json (default: `.taskmaster/tasks/tasks.json`) |
| `--dry-run` | Show what would be done without making changes |

**Auto-mapped Fields** (always passed):
- `description` → Brief task summary (1000 char limit)
- `details` → Implementation details as `design` (5000 char limit)
- `testStrategy` → Validation criteria as `acceptance` (2000 char limit)

**After Sync**:
- ✅ Creates beads with rich field mapping
- ✅ Links all beads to uber-epic via parent-child
- ✅ Sets up task dependencies in beads
- ✅ **Closes synced Task Master tasks** (status=done)

**ID Range Filtering** (IMPORTANT):
When parsing multiple PRDs, use `--from-id` and `--to-id` to sync only tasks from a specific PRD:
```bash
# PRD adds tasks 171-210, sync only those to their uber-epic
node agencheck/.claude/skills/orchestrator-multiagent/scripts/sync-taskmaster-to-beads.js \
    --uber-epic=agencheck-001 --from-id=171 --to-id=210 \
    --tasks-path=agencheck/.taskmaster/tasks/tasks.json
```

**Hierarchical Filtering**:

Once synced with `--uber-epic`, you can filter tasks by initiative:

```bash
# See all tasks under an initiative
bd list --parent=agencheck-001

# See ready tasks for specific initiative only
bd ready --parent=agencheck-001

# Useful for multi-initiative projects where you want to focus on one epic
```

**Why This Matters**:
- Task Master maintains flat structure (good for parsing/complexity analysis)
- Beads provides hierarchical organization (good for orchestration/filtering)
- The sync script bridges both: parse with Task Master, orchestrate with Beads

### Phase 2: Execution (Incremental Implementation)

**🚨 For multi-feature autonomous operation, see [WORKFLOWS.md](WORKFLOWS.md#autonomous-mode-protocol)**

The autonomous mode protocol provides:
- ✅ Continuation criteria (when to proceed automatically)
- ✅ Stop conditions (when to pause and report)
- ✅ Comprehensive validation (Unit + API + E2E for backend and frontend)
- ✅ Session handoff procedures

**Quick Reference (Single Feature)**:
```
1. Run PREFLIGHT.md checklist (includes team creation)
   ↓
2. `bd ready` -> Select next task
   ↓
3. `bd update <bd-id> --status in-progress`
   ↓
4. DELEGATE TO WORKER TEAMMATE
   TaskCreate(subject="Implement ...", description="...", activeForm="...")
   SendMessage(type="message", recipient="worker-backend", content="Task available", summary="New task")
   ↓
5. Worker sends results via SendMessage (auto-delivered to you)
   ↓
6. DELEGATE VALIDATION TO VALIDATOR TEAMMATE
   TaskCreate(subject="Validate <bd-id>", description="--mode=e2e --task_id=... --prd=PRD-XXX")
   SendMessage(type="message", recipient="validator", content="Validation ready", summary="Validate request")
   ↓
7. Validator closes task with evidence (via bd close internally)
   ↓
8. `git add . && git commit -m "feat(<bd-id>): [description]"`
```

**Critical Rules**:
- One feature at a time. Leave clean state. Commit progress.
- **Use TaskCreate + SendMessage for all worker delegation** - Workers claim tasks from shared TaskList
- **NEVER use `bd close` directly** - Route through validator teammate
- Orchestrator coordinates; Workers implement

**Legacy feature_list.json**: See [LEGACY_FEATURE_LIST.md](archive/LEGACY_FEATURE_LIST.md) for legacy workflow.

### Phase 3: Validation (AT Epic Closure)

**When**: All functional epic tasks are complete, AT epic tasks ready for final validation.

**Validation Workflow**:
```
1. Verify ALL tasks in functional epic are closed
   -- `bd list` - check status
   |
2. Assign AT epic tasks to validator teammate (--mode=unit first, then --mode=e2e)
   -- TaskCreate + SendMessage to validator
   -- Validator runs fast unit checks, then PRD-based acceptance tests
   -- Validator closes tasks that pass (via bd close internally)
   |
3. Assign AT epic closure to validator teammate
   -- TaskCreate: "--mode=e2e --task_id=<at-epic-id> --prd=PRD-XXX"
   -- SendMessage to validator
   |
4. Assign functional epic closure to validator teammate (now unblocked)
   -- TaskCreate: "--mode=e2e --task_id=<epic-id> --prd=PRD-XXX"
   -- SendMessage to validator
   |
5. When all epics closed -> System 3 closes uber-epic
   -- System 3 uses validation-test-agent --mode=e2e --prd=PRD-XXX for uber-epic
   |
6. Final commit and summary
   -- `git add . && git commit -m "feat: complete [initiative]"`
   -- Update `.claude/progress/` with final summary
```

**Closure Order** (MUST follow):
```
AT tasks -> AT epic -> Functional epic -> Uber-epic
(All closures via validator teammate, NOT direct bd close)
```

**Full Validation Protocol**: See [WORKFLOWS.md](WORKFLOWS.md#validation-protocol-31-level)

---

## State Integrity Principles

**State = What can be independently verified** (tests, browser, git status).

**Immutability Rules**:
| ✅ Allowed | ❌ Never |
|-----------|---------|
| Change status (open → closed) | Remove tasks |
| Add timestamps/evidence | Edit task definitions after creation |
| Add discovered subtasks | Reorder task hierarchy |

**MAKER-Inspired Decomposition**: Tasks must be small enough for a Haiku model to complete reliably. See [WORKFLOWS.md](WORKFLOWS.md#feature-decomposition-maker) for the four questions and decision tree.

---

## Memory-Driven Decision Making (Hindsight Integration)

The orchestrator uses Hindsight as extended memory to learn from experience and avoid repeating mistakes.

**Architecture Context**: For Hindsight's role in System 3's memory-driven philosophy and dual-bank architecture, see `system3-meta-orchestrator.md` → "Dual-Bank Startup Protocol" section.

### Core Principle

**Before deciding, recall. After learning, retain. When stuck, reflect + validate.**

### Integration Points

| Decision Point | Action | Purpose |
|----------------|--------|---------|
| **Task start** | `recall` | Check for pertinent memories before beginning |
| **User feedback received** | `retain` → `reflect` → `retain` | Capture feedback, extract lesson, store pattern |
| **Rejected 2 times** (feature OR regression) | `recall` → `reflect` → Perplexity → `retain` | Full analysis with external validation |
| **Regression detected** (first time) | `recall` | Check for similar past situations |
| **Hollow test detected** | `reflect` → Perplexity → `retain` | Analyze gap, validate fix, store prevention |
| **AT epic/session closure** | `reflect` → `retain` | Synthesize patterns and store insights |

### Task Start Memory Check

**Before starting ANY task:**

```python
# Check for pertinent memories about this task type/context
mcp__hindsight__recall("What should I remember about [task type/domain]?")
```

This surfaces patterns like:
- "Always launch Haiku sub-agent to monitor workers"
- "This component has fragile dependencies on X"
- "Previous attempts failed because of Y"

### User Feedback Loop

**When the user provides feedback** (corrections, reminders, guidance):

```
USER FEEDBACK DETECTED
    │
    ▼
1. RETAIN immediately
   mcp__hindsight__retain(
       content="User reminded me to [X] when [context]",
       context="patterns"
   )
    │
    ▼
2. REFLECT on the lesson
   mcp__hindsight__reflect(
       query="Why did I forget this? What pattern should I follow?",
       budget="mid"
   )
    │
    ▼
3. RETAIN the extracted pattern
   mcp__hindsight__retain(
       content="Lesson: [extracted pattern from reflection]",
       context="patterns"
   )
```

**Example**: User keeps reminding to launch Haiku sub-agent for monitoring:
- Retain: "User reminded me to launch Haiku sub-agent to monitor worker progress"
- Reflect: "Why did I miss this? What's the pattern?"
- Retain: "Lesson: Always use run_in_background=True for parallel workers"

### Rejected 2 Times (Feature or Regression)

**When a feature is rejected twice OR regression occurs twice:**

```python
# 1. Recall similar situations
mcp__hindsight__recall("What happened when [similar feature/regression] was rejected?")

# 2. Reflect on patterns
mcp__hindsight__reflect(
    query="Why has [feature/regression] failed twice? What pattern is emerging?",
    budget="high"
)

# 3. Validate with Perplexity (MANDATORY)
mcp__perplexity-ask__perplexity_ask(
    messages=[{
        "role": "user",
        "content": "I'm seeing repeated failures with [issue]. My hypothesis is [reflection output]. Is this assessment correct? What approaches should I consider?"
    }]
)

# 4. Retain the validated lesson
mcp__hindsight__retain(
    content="Double rejection: [feature]. Root cause: [X]. Validated approach: [Y]",
    context="bugs"
)
```

### Regression Detected (First Time)

**On first regression detection:**

```python
# Recall only - check for similar past situations
mcp__hindsight__recall("What do I know about regressions in [component/area]?")
```

If recall surfaces relevant patterns, apply them. If not, proceed with standard fix.

### Hollow Test Analysis

**When tests pass but feature doesn't work:**

```python
# 1. Reflect on the gap
mcp__hindsight__reflect(
    query="Why did tests pass but feature fail? What's the mock/reality gap?",
    budget="high"
)

# 2. Validate prevention approach with Perplexity
mcp__perplexity-ask__perplexity_ask(
    messages=[{
        "role": "user",
        "content": "My tests passed but feature failed because [gap]. How should I improve my testing approach to catch this?"
    }]
)

# 3. Retain prevention pattern
mcp__hindsight__retain(
    content="Hollow test: [scenario]. Gap: [X]. Prevention: [Y]",
    context="patterns"
)
```

### AT Epic/Session Closure

**When closing an AT epic or ending a session:**

```python
# 1. Reflect on patterns that emerged
mcp__hindsight__reflect(
    query="What patterns emerged from this [epic/session]? What worked well? What should be done differently?",
    budget="high"
)

# 2. Retain the insights
mcp__hindsight__retain(
    content="[Epic/Session] insights: [key patterns and learnings]",
    context="patterns"
)
```

### The Learning Loop

```
Experience → Retain → Reflect → Retain Pattern → Recall Next Time → Apply
     ↑                                                              │
     └──────────────────────────────────────────────────────────────┘
```

This creates a continuous improvement cycle where each task benefits from all previous experience.

---

## Worker Delegation (Native Teams)

**Orchestrators use native Agent Teams for all worker delegation.**

### Team Lifecycle

```python
# 1. Create team (once per session, during PREFLIGHT)
Teammate(
    operation="spawnTeam",
    team_name="{initiative}-workers",
    description="Workers for {initiative}"
)

# 2. Spawn specialist workers as persistent teammates
Task(
    subagent_type="backend-solutions-engineer",
    team_name="{initiative}-workers",
    name="worker-backend",
    prompt="You are worker-backend in team {initiative}-workers. Check TaskList for available work. Claim tasks, implement, report completion via SendMessage to team-lead."
)

# 3. Spawn validator teammate (once per session)
Task(
    subagent_type="validation-test-agent",
    team_name="{initiative}-workers",
    name="validator",
    prompt="You are the validator in team {initiative}-workers. When tasks are ready for validation, check TaskList for tasks needing review. Run validation (--mode=unit or --mode=e2e --prd=PRD-XXX). Close tasks with evidence via bd close. Report results via SendMessage to team-lead."
)

# 4. Create work items and notify workers
TaskCreate(
    subject="Implement {feature}",
    description="[task details, requirements, acceptance criteria, file scope]",
    activeForm="Implementing {feature}"
)
SendMessage(type="message", recipient="worker-backend", content="Task available: {feature}", summary="New task assignment")

# 5. Worker results arrive via SendMessage (auto-delivered)
# 6. Assign validation to validator teammate
TaskCreate(
    subject="Validate {feature}",
    description="--mode=e2e --task_id={bead_id} --prd=PRD-XXX",
    activeForm="Validating {feature}"
)
SendMessage(type="message", recipient="validator", content="Validation task available", summary="Validation request")
```

### Quick Worker Selection

| Feature Type | subagent_type | Teammate Name |
|--------------|---------------|---------------|
| React, UI | `frontend-dev-expert` | `worker-frontend` |
| API, Python | `backend-solutions-engineer` | `worker-backend` |
| **E2E Browser Tests** | **`tdd-test-engineer`** | **`worker-tester`** |
| Architecture | `solution-design-architect` | `worker-architect` |
| Investigation | `Explore` | `worker-explore` |
| **Task Closure** | **`validation-test-agent`** | **`validator`** |

**Parallel workers**: Spawn multiple teammates into the same team. Each claims different tasks from the shared TaskList. Workers coordinate peer-to-peer via SendMessage.

### Browser Testing Worker Pattern

**When to use**: Features requiring actual browser automation (not just unit tests)

**Pattern**: Orchestrator creates task, persistent tdd-test-engineer teammate picks it up. Because the tester is a persistent teammate, it can maintain browser sessions across multiple test tasks.

```python
# Create browser testing task
TaskCreate(
    subject="E2E browser testing for F084",
    description="""
    MISSION: Validate feature F084 via browser automation

    TARGET: http://localhost:5001/[path]

    TESTING CHECKLIST:
    - [ ] Navigate to page
    - [ ] Verify UI renders correctly
    - [ ] Test user interactions
    - [ ] Capture screenshots as evidence

    Report: Pass/Fail per item, screenshots, overall assessment
    """,
    activeForm="Browser testing F084"
)
SendMessage(type="message", recipient="worker-tester", content="Browser test task available for F084", summary="Browser test request")
# Worker-tester picks up task, maintains browser session, reports results via SendMessage
```

### Fallback: Task Subagent Mode

**When AGENT_TEAMS is not enabled**, fall back to the original Task subagent pattern:

```python
result = Task(
    subagent_type="frontend-dev-expert",
    description="Implement [feature]",
    prompt="""
    ## Task: [Task title from Beads]

    **Context**: [investigation summary]
    **Requirements**: [list requirements]
    **Acceptance Criteria**: [list criteria]
    **Scope** (ONLY these files): [file list]

    **Report back with**: Files modified, tests written/passed, any blockers
    """
)
# Result returned directly - no monitoring, no cleanup needed
```

In fallback mode, validation also uses Task subagents:
```python
Task(
    subagent_type="validation-test-agent",
    prompt="--mode=e2e --task_id=agencheck-042 --prd=PRD-AUTH-001"
)
```

**How to detect**: Check for `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in environment. If absent, use fallback.

**Full Guide**: [WORKERS.md](WORKERS.md)
- Worker Assignment Template
- Parallel Worker Pattern
- Browser Testing Workers (E2E validation)

---

## Service Management

**BEFORE starting Phase 2:**

```bash
# Start services (see VALIDATION.md for details)
cd agencheck-support-agent && ./start_services.sh
cd agencheck-support-frontend && npm run dev

# Verify services running
lsof -i :5001 -i :8000 -i :5184 -i :5185 | grep LISTEN
```

**Full Guide**: [VALIDATION.md](VALIDATION.md#service-management)
- Service Setup and Health Checks
- Starting from Clean State
- Worker Dependency Verification
- Troubleshooting Service Issues

---

## Testing & Validation

### Validation Agent (Teammate -- Task Closure Authority)

**Orchestrators delegate task closure to the validator teammate, NOT direct `bd close`.**

The validator is a persistent teammate spawned once per session during PREFLIGHT:

```python
# Spawn validator teammate (once per session, after team creation)
Task(
    subagent_type="validation-test-agent",
    team_name="{initiative}-workers",
    name="validator",
    prompt="You are the validator in team {initiative}-workers. When tasks are ready for validation, check TaskList for tasks needing review. Run validation (--mode=unit or --mode=e2e --prd=PRD-XXX). Close tasks with evidence via bd close. Report results via SendMessage to team-lead."
)
```

The validator operates in two modes:

| Mode | Flag | Used By | Purpose |
|------|------|---------|---------|
| **Unit** | `--mode=unit` | Orchestrators | Fast technical checks (mocks OK) |
| **E2E** | `--mode=e2e --prd=PRD-XXX` | Orchestrators & System 3 | Full acceptance validation (real data, PRD criteria) |

**Two-Stage Validation Workflow:**

```python
# Stage 1: Fast unit check (runs first)
TaskCreate(
    subject="Validate agencheck-042 (unit)",
    description="--mode=unit --task_id=agencheck-042",
    activeForm="Unit validation agencheck-042"
)
SendMessage(type="message", recipient="validator", content="Unit validation task for agencheck-042", summary="Unit validation request")
# Quick validation with mocks, catches obvious breakage

# Stage 2: Full E2E with PRD acceptance tests (if unit passes)
TaskCreate(
    subject="Validate agencheck-042 (e2e)",
    description="--mode=e2e --task_id=agencheck-042 --prd=PRD-AUTH-001\nValidate against acceptance criteria. Close with evidence if passing.",
    activeForm="E2E validation agencheck-042"
)
SendMessage(type="message", recipient="validator", content="E2E validation task for agencheck-042", summary="E2E validation request")
# Validator teammate invokes acceptance-test-runner internally
# Runs PRD-defined acceptance criteria with real data
# Closes task with evidence if all criteria pass
```

**Key Rules:**
- Orchestrators NEVER run `bd close` directly
- Validator teammate handles closure AFTER validation passes
- NEVER invoke acceptance-test-runner or acceptance-test-writer directly
- Always include `--prd=PRD-XXX` for e2e mode
- System 3 uses `--mode=e2e --prd=X` for business outcome validation
- Validator is a **persistent teammate** -- spawned once, handles multiple validation tasks

### Validation Types

| Type | When | How |
|------|------|-----|
| `browser` | UI features | chrome-devtools automation |
| `api` | Backend endpoints | curl/HTTP requests |
| `unit` | Pure logic | pytest/jest |

### MANDATORY: Post-Test Validation

**After ANY test suite passes:**

```python
# Create exploration task and assign to explorer teammate (or validator)
TaskCreate(
    subject="Post-test validation for <bd-id>",
    description="""Validate <bd-id> works as designed:
    - Test actual user workflow (not mocked)
    - Verify API endpoints return real data
    - Check UI displays expected results
    - Compare against Beads task acceptance criteria""",
    activeForm="Post-test validation <bd-id>"
)
SendMessage(type="message", recipient="validator", content="Post-test validation needed for <bd-id>", summary="Post-test validation")
```

**Why**: Unit tests can pass with mocks while feature doesn't work (hollow tests).

**Level 4 (Deploy Health)**: After deployment, orchestrators query Logfire for new exceptions, latency regressions, and error rate changes. See [VALIDATION.md](VALIDATION.md#level-4-deploy-health-logfire-observability).

**Full Guide**: [VALIDATION.md](VALIDATION.md)
- 3+1 Level Validation Protocol
- Testing Infrastructure
- Hollow Test Problem explanation

---

## Mandatory Regression Check (CIRCUIT BREAKER)

**🚨 This is covered in [PREFLIGHT.md](PREFLIGHT.md) Phase 3.**

**Quick Summary**: Before ANY new feature work:
1. Pick 1-2 closed tasks (`bd list --status=closed`)
2. Run 3-level validation (Unit + API + E2E)
3. If ANY fail: `bd reopen <id>` and fix BEFORE new work

**Why It Matters**: Hidden regressions multiply across features. Session F089-F090 evidence shows regression checks prevented 3+ hour blockages.

**Full Validation Protocol**: See [WORKFLOWS.md](WORKFLOWS.md#validation-protocol-31-level)

**Failure Recovery**: [VALIDATION.md](VALIDATION.md#recovery-patterns)

---

## Progress Tracking

### Session Handoff Checklist

**Before Ending:**
1. ✅ Current feature complete or cleanly stopped
2. ✅ Beads state synced (`bd sync`)
3. ✅ Progress summary updated (`.claude/progress/`)
4. ✅ Git status clean, changes committed and pushed
5. ✅ Learnings stored in Hindsight (`mcp__hindsight__retain()`)

**Starting New:**
1. Run PREFLIGHT.md checklist (includes memory check)
2. `bd ready` to find next available work
3. Review task details with `bd show <id>`
4. Continue with Phase 2 workflow

**Full Guide**: [WORKFLOWS.md](WORKFLOWS.md#progress-tracking)
- Session Summary template
- Progress Log template
- Learnings Accumulation
- Handoff procedures

---

## Quick Troubleshooting

### Worker Red Flags

| Signal | Action |
|--------|--------|
| Modified files outside scope | Reject - Fresh retry |
| TODO/FIXME in output | Reject - Fresh retry |
| Validation fails | Reject - Fresh retry |
| Exceeds 2 hours | Stop - Re-decompose |

### Orchestrator Self-Check

**Before Starting Phase 1 (Planning):**
- ✅ Completed Phase 0 (Ideation)?
- ✅ Read WORKFLOWS.md Feature Decomposition section?
- ✅ Created TodoWrite checklist for Phase 1?
- ✅ Used MAKER checklist to evaluate approach?
- ✅ Chose correct workflow (Task Master vs Manual)?

**After each feature:**
- Did I use **TaskCreate + SendMessage** for worker delegation (or Task subagent fallback)?
- Ran regression check first?
- Worker stayed within scope?
- Validated feature works (not just tests pass)?
- **Delegated closure to validator teammate (--mode=unit or --mode=e2e --prd=X)?**
- Committed with message?
- Git status clean?

**Pattern**: All worker delegation uses native Agent Teams (TaskCreate + SendMessage to teammates). When AGENT_TEAMS is not enabled, fall back to `Task(subagent_type="...")`.

**Full Guide**: [VALIDATION.md](VALIDATION.md#troubleshooting)
- Worker Red Flags & Recovery
- Orchestrator Anti-Patterns
- Hollow Test Problem
- Voting Protocol (when consensus needed)
- Recovery Patterns

---

## Reference Guides

### When to Consult Each Guide

**Quick Lookup:**
- **[REFERENCE.md](REFERENCE.md)** - Commands, ports, directories, session templates

**Session Start (MANDATORY):**
- **[PREFLIGHT.md](PREFLIGHT.md)** - 🚨 MANDATORY - Unified pre-flight checklist consolidating all circuit breakers (Serena, services, memory, regression)

**During Ideation + Planning (Phase 0-1):**
- **[WORKFLOWS.md](WORKFLOWS.md#feature-decomposition-maker)** - 🚨 MANDATORY READ before Phase 1 - Contains MAKER checklist, decision tree, red flags

**During Execution (Phase 2):**
- **[WORKFLOWS.md](WORKFLOWS.md)** - 4-Phase Pattern, Autonomous Mode Protocol, Validation (Unit + API + E2E), Progress Tracking, Session Handoffs
- **[WORKERS.md](WORKERS.md)** - Launching workers, monitoring, feedback, browser testing
- **[VALIDATION.md](VALIDATION.md)** - Service startup, health checks, testing infrastructure, troubleshooting, recovery patterns

**Session Boundaries:**
- **[WORKFLOWS.md](WORKFLOWS.md#session-handoffs)** - Handoff checklists, summaries, learning documentation

**Legacy Support:**
- **[LEGACY_FEATURE_LIST.md](archive/LEGACY_FEATURE_LIST.md)** - Archived feature_list.json documentation for migration

---

**Skill Version**: 5.0 (Native Agent Teams Worker Delegation)
**Progressive Disclosure**: 5 reference files for detailed information
**Last Updated**: 2026-02-06
**Latest Enhancements**:
- v5.0: **Native Agent Teams** - Replaced Task subagent worker delegation with native Agent Teams (Teammate + TaskCreate + SendMessage). Workers are now persistent teammates that claim tasks from a shared TaskList, communicate peer-to-peer, and maintain session state across multiple assignments. Validator is a team role (not a separate Task subagent). Worker communication uses native team inboxes. Fallback to Task subagent mode when AGENT_TEAMS is not enabled.
- v4.0: **Task-Based Worker Delegation** - Replaced tmux worker delegation with Task subagents. Workers now receive assignments via `Task(subagent_type="...")` and return results directly. No session management, monitoring loops, or cleanup required. Parallel workers use `run_in_background=True` with `TaskOutput()` collection. System 3 -> Orchestrator still uses tmux for session isolation; Orchestrator -> Worker now uses Task subagents.
- v3.13: 🆕 **Sync Script Finalization** - Sync script now auto-closes Task Master tasks after sync (status=done). Removed mapping file (redundant with beads hierarchy). **IMPORTANT**: Must run from `zenagent/` root to use correct `.beads` database. Updated all docs with correct paths and `--tasks-path` usage.
- v3.12: **ID Range Filtering** - `--from-id=<id>` and `--to-id=<id>` to filter which Task Master tasks to sync. Essential for multi-PRD projects.
- v3.11: **Enhanced Sync Script** - `--uber-epic=<id>` for parent-child linking. Auto-maps description, details→design, testStrategy→acceptance.
- v3.10: **Reference Consolidation** - Created REFERENCE.md as quick reference card. Merged BEADS_INTEGRATION.md, README.md, and ORCHESTRATOR_INITIALIZATION_TEMPLATE.md into REFERENCE.md. Reduced reference files from 6 to 5. Essential commands, patterns, and session templates now in single quick-lookup location.
- v3.9: **Validation Consolidation** - Merged TESTING_INFRASTRUCTURE.md, TROUBLESHOOTING.md, and SERVICE_MANAGEMENT.md into unified VALIDATION.md. Reduced reference files from 8 to 6. All testing, troubleshooting, and service management now in single location.
- v3.8: **Workflow Consolidation** - Merged AUTONOMOUS_MODE.md, ORCHESTRATOR_PROCESS_FLOW.md, FEATURE_DECOMPOSITION.md, and PROGRESS_TRACKING.md into unified WORKFLOWS.md. Reduced reference files from 11 to 8. All workflow documentation now in single location.
- v3.7: 🆕 **Inter-Instance Coordination** - Background monitor agent pattern for task completion detection. Session start/end protocol. Completion reports to System 3 via `bd update`.
- v3.6: **Memory-Driven Decision Making** - Integrated Hindsight for continuous learning. Task start recall, user feedback loop (retain → reflect → retain), double-rejection analysis with Perplexity validation, hollow test prevention, session closure reflection. Creates learning loop where each task benefits from all previous experience.
- v3.5: Clear four-phase pattern (Phase 0: Ideation → Phase 1: Planning → Phase 2: Execution → Phase 3: Validation). Consolidated Uber-Epic and AT-Epic patterns into unified "Epic Hierarchy Patterns" section with cleaner visual. Updated all phase references for consistency.
- v3.4: Beads-only workflow - Removed ALL feature_list.json references (now in LEGACY_FEATURE_LIST.md). Added MANDATORY Ideation Phase with brainstorming + parallel-solutioning.
- v3.3: Major streamlining - Created PREFLIGHT.md (unified session checklist), AUTONOMOUS_MODE.md (multi-feature protocol with 3-level validation), LEGACY_FEATURE_LIST.md (archived legacy docs).
- v3.2: Added Mandatory Acceptance Test Epic Pattern - every functional epic requires a paired AT epic with blocking dependency.
- v3.1: Added Uber-Epic First Pattern - mandatory hierarchy (uber-epic → epic → task) for all initiatives.
- v3.0: Added Beads task management integration as recommended state tracking method.
