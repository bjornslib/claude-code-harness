---
name: orchestrator-multiagent
description: Multi-agent orchestration for building software incrementally. Use when coordinating workers via tmux sessions, managing task state with Beads, delegating features to specialized workers (NOT direct sub-agents), tracking progress across sessions, or implementing the four-phase pattern (ideation → planning → execution → validation). Triggers on orchestration, coordination, multi-agent, beads, worker delegation, session handoff, progress tracking.
---

# Multi-Agent Orchestrator Skill

## 🚨 CRITICAL: tmux Enter Pattern (READ THIS FIRST)

**EVERY orchestrator using tmux worker delegation MUST know this:**

When sending commands via tmux, **Enter must be a separate `send-keys` command** or it will be **silently ignored** (no error, just doesn't work).

```bash
# ❌ WRONG - Enter gets silently ignored
tmux send-keys -t worker "command" Enter

# ✅ CORRECT - Enter as separate command
tmux send-keys -t worker "command"
tmux send-keys -t worker Enter
```

**This affects 100% of worker delegation workflows.** See [WORKERS.md](WORKERS.md#critical-tmux-enter-pattern) for detailed explanation.

---

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

```bash
# ❌ WRONG - Direct sub-agent usage
Task(subagent_type="frontend-dev-expert", prompt="Implement...")

# ✅ RIGHT - Worker via tmux
tmux new-session -d -s worker-F001
tmux send-keys -t worker-F001 "launchcc"  # launchcc = claude --chrome --dangerously-skip-permissions
tmux send-keys -t worker-F001 Enter
```

**Why `launchcc` not `claude`?** The alias includes `--dangerously-skip-permissions` so workers can edit files autonomously without requiring manual approval for each change. Using plain `claude` means you'll have to approve every edit manually.

**Allowed exceptions**: `Task(subagent_type="Explore")` for investigation, `Task(model="haiku")` for monitoring.

---

## BLOCKED COMMANDS (HARD ENFORCEMENT)

**The following commands are BLOCKED for orchestrators:**

| Command | Why Blocked | Alternative |
|---------|-------------|-------------|
| `bd close <id>` | Bypasses validation evidence | `Task(subagent_type="validation-agent", ...)` |
| `bd close <id> --reason "..."` | Same - reason doesn't replace evidence | validation-agent collects actual evidence |

**If you attempt `bd close`**: STOP. Ask yourself:
1. Did I run validation-agent --mode=implementation?
2. Did validation-agent produce passing evidence?
3. Did validation-agent close the task for me?

If NO to any: You're violating the validation gate. Delegate to validation-agent first.

**Exception**: Only validation-agent is authorized to run `bd close` after verification passes.

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

### Worker Types (via tmux ONLY)
| Type | Worker Via tmux | Use For |
|------|-----------------|---------|
| Frontend | `frontend-dev-expert` in tmux | React, Next.js, UI |
| Backend | `backend-solutions-engineer` in tmux | Python, FastAPI, PydanticAI |
| **Browser Testing** | `haiku` in tmux with chrome-devtools | **E2E UI validation, automated browser testing** |
| General | `general-purpose` in tmux | Everything else |

**CRITICAL:** Never use Task tool with these worker types. Always launch via tmux.

**⚠️ IMPORTANT tmux Command Pattern**: See critical banner at top of this file for Enter pattern details.

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
| **Planning** | Ideation done, no Beads tasks | Phase 1: Planning (uber-epic + task decomposition) |
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

**Validation**: Each AT task must pass 3-level validation (Unit + API + E2E). See [WORKFLOWS.md](WORKFLOWS.md#validation-protocol-3-level).

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

# 6. Review hierarchy (filter by uber-epic)
bd list --parent=agencheck-001   # See only tasks under this initiative
bd ready --parent=agencheck-001  # Ready tasks for this initiative only

# 7. Commit and document (completes Phase 1)
git add .beads/ && git commit -m "plan: initialize [initiative] hierarchy"
# Write progress summary to .claude/progress/
```

**Manual Planning** (Hotfixes only - already have clear scope):
```bash
bd create --title="[Hotfix Description]" --type=epic --priority=1
# Create tasks directly: bd create --title="[Task]" --type=task
# Skip Phase 0 only for emergency fixes with <3 file changes
```

**⚠️ Ignore plan skill's "execute with superpowers:executing-plans"** - we use tmux workers.

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
1. Run PREFLIGHT.md checklist
   ↓
2. `bd ready` → Select next task
   ↓
3. `bd update <bd-id> --status in-progress`
   ↓
4. 🚨 DELEGATE TO WORKER VIA TMUX (MANDATORY - INTERACTIVE MODE)
   See WORKERS.md for template
   ↓
5. Monitor via Haiku sub-agent
   ↓
6. Validate completion (3 LEVELS - see WORKFLOWS.md)
   - Level 1: Unit Tests (pytest + Jest)
   - Level 2: API Tests (curl endpoints)
   - Level 3: E2E Browser Tests (chrome-devtools/Playwright)
   ↓
7. `bd close <bd-id> --reason "PASS: Unit ✓ API ✓ E2E ✓"`
   ↓
7. `git add . && git commit -m "feat(<bd-id>): [description]"`
```

**Critical Rules**:
- One feature at a time. Leave clean state. Commit progress.
- **NEVER use Task tool with implementation sub-agents - ALWAYS delegate via tmux**
- **INTERACTIVE MODE IS MANDATORY** - Workers must be able to receive feedback
- Orchestrator coordinates; Workers implement

**Legacy feature_list.json**: See [LEGACY_FEATURE_LIST.md](archive/LEGACY_FEATURE_LIST.md) for legacy workflow.

### Phase 3: Validation (AT Epic Closure)

**When**: All functional epic tasks are complete, AT epic tasks ready for final validation.

**Validation Workflow**:
```
1. Verify ALL tasks in functional epic are closed
   └─ `bd list` - check status
   ↓
2. Execute AT epic tasks via validation-agent (--mode=implementation)
   └─ Validation-agent runs 3-level validation for each task
   └─ Validation-agent closes tasks that pass
   ↓
3. Close AT epic via validation-agent
   └─ Delegate: validation-agent --mode=implementation --task_id=<at-epic-id>
   ↓
4. Close functional epic via validation-agent (now unblocked)
   └─ Delegate: validation-agent --mode=implementation --task_id=<epic-id>
   ↓
5. When all epics closed → System 3 closes uber-epic
   └─ System 3 uses validation-agent --mode=business for uber-epic
   ↓
6. Final commit and summary
   └─ `git add . && git commit -m "feat: complete [initiative]"`
   └─ Update `.claude/progress/` with final summary
```

**Closure Order** (MUST follow):
```
AT tasks → AT epic → Functional epic → Uber-epic
(All closures via validation-agent, NOT direct bd close)
```

**Full Validation Protocol**: See [WORKFLOWS.md](WORKFLOWS.md#validation-protocol-3-level)

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
- Retain: "Lesson: Always launch Haiku sub-agent after delegating to tmux worker"

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

## Worker Delegation

**🚨 CRITICAL REMINDER:** Orchestrators NEVER use Task tool with worker types directly.

### Quick Worker Selection (Launch via tmux)

| Feature Type | Worker (via tmux) |
|--------------|-------------------|
| React, UI | `frontend-dev-expert` in tmux |
| API, Python | `backend-solutions-engineer` in tmux |
| **E2E Browser Tests** | **`haiku` in tmux with chrome-devtools** |
| Scripts, docs | `general-purpose` in tmux |

**Delegation Pattern (MANDATORY):**
1. Create tmux session
2. Launch Claude Code in session
3. Provide worker assignment
4. Monitor via Haiku sub-agent

**❌ ANTI-PATTERN:** Using `Task(subagent_type="frontend-dev-expert")` directly

### Browser Testing Worker Pattern (NEW)

**When to use**: Features requiring actual browser automation (not just unit tests)

**Pattern**: Orchestrator → Haiku Sub-Agent → Browser Testing Worker

```typescript
// Orchestrator delegates to Haiku for browser testing setup
Task({
    subagent_type: "general-purpose",
    model: "haiku",
    description: "Launch browser-testing worker for F084",
    prompt: `MISSION: Set up E2E testing worker with chrome-devtools

STEPS:
1. Create tmux session: e2e-worker-f084
2. Launch Claude Code (Haiku model)
3. Validate chrome-devtools connected
4. Send testing assignment to worker
5. Monitor progress and report results

See: .claude/skills/orchestrator-multiagent/WORKERS.md#browser-testing-workers for details`
})
```

**Full Guide**: [WORKERS.md](WORKERS.md)
- tmux Delegation Pattern (critical Enter pattern)
- Worker Assignment Template
- Monitoring with Haiku Sub-Agent
- Browser Testing Workers (E2E validation)
- Worker Feedback and Intervention

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
- Service Session Setup (tmux)
- Health Checks
- Starting from Clean State
- Worker Dependency Verification
- Troubleshooting Service Issues

---

## Testing & Validation

### Validation Agent (NEW - Task Closure Authority)

**🚨 Orchestrators delegate task closure to validation-agent, NOT direct `bd close`.**

The validation-agent operates in two modes:

| Mode | Flag | Used By | Purpose |
|------|------|---------|---------|
| **Implementation** | `--mode=implementation` | Orchestrators | Technical validation against task acceptance criteria |
| **Business** | `--mode=business` | System 3 | Business validation against completion promise |

**Orchestrator Workflow (Implementation Mode):**

```bash
# 1. Worker completes implementation
# 2. Orchestrator spawns validation-agent in implementation mode
Task(
    subagent_type="validation-agent",
    prompt="""
    Validate task <bd-id> in implementation mode:
    --mode=implementation
    --task_id=<bd-id>

    Run 3-level validation:
    - Level 1: Unit Tests
    - Level 2: API Tests
    - Level 3: E2E Browser Tests

    If ALL pass: Close task with evidence
    If ANY fail: Report failure, do NOT close
    """
)
```

**Key Rules:**
- Orchestrators NEVER run `bd close` directly
- Validation-agent handles closure AFTER validation passes
- Use `--mode=implementation` for technical validation
- System 3 uses `--mode=business` for business outcome validation

### Validation Types

| Type | When | How |
|------|------|-----|
| `browser` | UI features | chrome-devtools automation |
| `api` | Backend endpoints | curl/HTTP requests |
| `unit` | Pure logic | pytest/jest |

### MANDATORY: Post-Test Validation

**After ANY test suite passes:**

```
Task(subagent_type="Explore", prompt="Validate <bd-id> works as designed:
- Test actual user workflow (not mocked)
- Verify API endpoints return real data
- Check UI displays expected results
- Compare against Beads task acceptance criteria")
```

**Why**: Unit tests can pass with mocks while feature doesn't work (hollow tests).

**Full Guide**: [VALIDATION.md](VALIDATION.md)
- 3-Level Validation Protocol
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

**Full Validation Protocol**: See [WORKFLOWS.md](WORKFLOWS.md#validation-protocol-3-level)

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
- ✅ **Used tmux worker (NOT Task tool with implementation sub-agents)?**
- ✅ Ran regression check first?
- ✅ Worker stayed within scope?
- ✅ Validated feature works (not just tests pass)?
- ✅ **Delegated closure to validation-agent (--mode=implementation)?**
- ✅ Committed with message?
- ✅ Git status clean?

**CRITICAL:** If you used `Task(subagent_type="frontend-dev-expert"|"backend-solutions-engineer"|"general-purpose")` for implementation, you violated the orchestrator pattern. Next time, delegate via tmux.

**Full Guide**: [VALIDATION.md](VALIDATION.md#troubleshooting)
- Worker Red Flags & Recovery
- Orchestrator Anti-Patterns
- Hollow Test Problem
- Voting Protocol (when consensus needed)
- Recovery Patterns

---

## Message Bus Integration

Real-time communication with System 3 and other orchestrators.

**Architecture Reference**: See [MESSAGE_BUS_ARCHITECTURE.md](../../documentation/MESSAGE_BUS_ARCHITECTURE.md) for the complete architecture overview.

### Session Start: Register + Spawn Monitor

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

```python
# 2. Spawn background monitor for real-time message detection
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description="Message queue monitor",
    prompt="""[Load from .claude/skills/message-bus/monitor-prompt-template.md]"""
)
```

### Receiving Messages

Messages from System 3 are automatically injected via PostToolUse hook.

For manual check:
```bash
/check-messages
```

### Responding to System 3 Guidance

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

### Sending Completion Reports

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

### Session End: Unregister

Before session ends:

```bash
.claude/scripts/message-bus/mb-unregister "${CLAUDE_SESSION_ID}"
```

### Updated Session Handoff Checklist

Add to your session start/end routines:

**Session Start:**
- [ ] Register with message bus (`mb-register`)
- [ ] Spawn background monitor (Haiku, run_in_background)

**Session End:**
- [ ] Send completion report to System 3 (`mb-send`)
- [ ] Unregister from message bus (`mb-unregister`)

### Message Types You May Receive

| Type | From | Action |
|------|------|--------|
| `guidance` | System 3 | Adjust approach, acknowledge |
| `broadcast` | System 3 | Note policy/announcement |
| `query` | System 3 | Respond with status |
| `urgent` | System 3 | Handle immediately |

### CLI Commands Quick Reference

| Command | Purpose |
|---------|---------|
| `mb-recv` | Check for pending messages |
| `mb-send` | Send message to System 3 or other orchestrator |
| `mb-register` | Register this session |
| `mb-unregister` | Unregister this session |
| `mb-list` | List active orchestrators |
| `mb-status` | Queue status overview |

**Full Guide**: See [message-bus skill](../message-bus/SKILL.md)

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

**Skill Version**: 3.13 (Sync Script Finalization)
**Progressive Disclosure**: 5 reference files for detailed information
**Last Updated**: 2026-01-07
**Latest Enhancements**:
- v3.13: 🆕 **Sync Script Finalization** - Sync script now auto-closes Task Master tasks after sync (status=done). Removed mapping file (redundant with beads hierarchy). **IMPORTANT**: Must run from `zenagent/` root to use correct `.beads` database. Updated all docs with correct paths and `--tasks-path` usage.
- v3.12: **ID Range Filtering** - `--from-id=<id>` and `--to-id=<id>` to filter which Task Master tasks to sync. Essential for multi-PRD projects.
- v3.11: **Enhanced Sync Script** - `--uber-epic=<id>` for parent-child linking. Auto-maps description, details→design, testStrategy→acceptance.
- v3.10: **Reference Consolidation** - Created REFERENCE.md as quick reference card. Merged BEADS_INTEGRATION.md, README.md, and ORCHESTRATOR_INITIALIZATION_TEMPLATE.md into REFERENCE.md. Reduced reference files from 6 to 5. Essential commands, patterns, and session templates now in single quick-lookup location.
- v3.9: **Validation Consolidation** - Merged TESTING_INFRASTRUCTURE.md, TROUBLESHOOTING.md, and SERVICE_MANAGEMENT.md into unified VALIDATION.md. Reduced reference files from 8 to 6. All testing, troubleshooting, and service management now in single location.
- v3.8: **Workflow Consolidation** - Merged AUTONOMOUS_MODE.md, ORCHESTRATOR_PROCESS_FLOW.md, FEATURE_DECOMPOSITION.md, and PROGRESS_TRACKING.md into unified WORKFLOWS.md. Reduced reference files from 11 to 8. All workflow documentation now in single location.
- v3.7: 🆕 **Inter-Instance Messaging** - Real-time communication with System 3 and other orchestrators. SQLite message queue with orchestrator registry. Background monitor agent pattern for message detection. Session start/end registration protocol. Completion reports to System 3.
- v3.6: **Memory-Driven Decision Making** - Integrated Hindsight for continuous learning. Task start recall, user feedback loop (retain → reflect → retain), double-rejection analysis with Perplexity validation, hollow test prevention, session closure reflection. Creates learning loop where each task benefits from all previous experience.
- v3.5: Clear four-phase pattern (Phase 0: Ideation → Phase 1: Planning → Phase 2: Execution → Phase 3: Validation). Consolidated Uber-Epic and AT-Epic patterns into unified "Epic Hierarchy Patterns" section with cleaner visual. Updated all phase references for consistency.
- v3.4: Beads-only workflow - Removed ALL feature_list.json references (now in LEGACY_FEATURE_LIST.md). Added MANDATORY Ideation Phase with brainstorming + parallel-solutioning.
- v3.3: Major streamlining - Created PREFLIGHT.md (unified session checklist), AUTONOMOUS_MODE.md (multi-feature protocol with 3-level validation), LEGACY_FEATURE_LIST.md (archived legacy docs).
- v3.2: Added Mandatory Acceptance Test Epic Pattern - every functional epic requires a paired AT epic with blocking dependency.
- v3.1: Added Uber-Epic First Pattern - mandatory hierarchy (uber-epic → epic → task) for all initiatives.
- v3.0: Added Beads task management integration as recommended state tracking method.
