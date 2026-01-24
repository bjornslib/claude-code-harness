# Orchestrator Workflows

Execution workflows for multi-feature development.

## Table of Contents
- [4-Phase Pattern](#4-phase-pattern)
- [Autonomous Mode Protocol](#autonomous-mode-protocol)
- [Acceptance Test Generation (After PRD Parse)](#acceptance-test-generation-after-prd-parse)
- [Feature Decomposition (MAKER)](#feature-decomposition-maker)
- [Progress Tracking](#progress-tracking)
- [Session Handoffs](#session-handoffs)

---

## 4-Phase Pattern

The orchestrator follows a complete cycle for each feature:

```
1. PREPARATION
   ├── Read feature_list.json / bd ready
   ├── Run regression check (1-2 passing features)
   └── Select next ready feature

2. ASSIGNMENT
   ├── Determine worker type
   ├── Prepare worker context
   ├── Launch worker (tmux session)
   └── Set expectations

3. MONITORING
   ├── Check-ins (every 30-45 min)
   ├── Watch for red flags
   ├── Provide guidance if needed
   └── Detect completion signals

4. VALIDATION
   ├── Run feature validation command
   ├── Post-test verification (Explore agent)
   ├── Check scope compliance
   └── Decision: Accept / Reject / Escalate

5. PROGRESSION
   ├── Update feature_list.json (passes: true) / bd close
   ├── Commit to git
   ├── Update progress tracking
   └── Loop back to step 1
```

### Phase Details

**Preparation**: Ensure clean state and identify next actionable feature.
- Read state to understand current status
- Run regression check on 1-2 previously passing features
- Select first feature where dependencies are satisfied

**Assignment**: Delegate feature to appropriate worker with complete context.
- Match feature to specialist (frontend/backend/general)
- Provide context package with acceptance criteria, files, validation command
- Launch tmux session with clear expectations

**Monitoring**: Track progress, detect problems early.
- Periodic check-ins every 30-45 minutes
- Use Haiku sub-agent with `run_in_background=True` for context-efficient monitoring
- Watch for scope creep, TODO/FIXME, time exceeded

**Validation**: Verify feature works as designed, not just that tests pass.
- Pre-validation: git clean, scope compliance, no incomplete markers
- Run validation command (tests)
- Post-test validation via Explore agent (hollow test detection)

**Progression**: Record success, commit, prepare for next feature.
- Update state file (only the `passes` field)
- Commit with descriptive message
- Update progress tracking, document learnings
- Clean up worker session

---

## Autonomous Mode Protocol

Enable independent monitoring and completion of multiple features without user intervention.

### Autonomous Continuation Criteria

**Continue to next feature automatically when ALL conditions met:**

1. Current feature validation PASSED (all three levels)
2. validation-agent closed task with evidence
3. Git commit successful with `feat(<id>)` message
4. `bd ready` returns next available task
5. No regressions detected in spot checks
6. Services remain healthy

### Stop Conditions (Report to User)

**Stop autonomous operation and report when ANY condition met:**

1. **3+ consecutive features blocked** - Indicates systemic issue
2. **Regression discovered** - Previously closed work now failing
3. **Service crash not auto-recoverable** - Infrastructure problem
4. **Uber-epic complete** - All epics closed, initiative done
5. **User explicitly requested checkpoint** - Honor user requests
6. **Circular dependency detected** - Beads graph issue
7. **Worker exceeds 2 hours on single task** - Decomposition needed

### Multi-Feature Session Loop

```
LOOP:
  1. PRE-FLIGHT CHECK
     - If not done this session: Run full PREFLIGHT.md checklist
     - If already done: Quick service health check only
     - If new PRD: Generate acceptance tests (see Acceptance Test Generation)

  2. SELECT NEXT TASK
     bd ready → Pick highest priority unblocked task
     bd update <id> --status in_progress

  3. DELEGATE TO WORKER
     - Create tmux session: worker-<id>
     - Launch Claude Code interactively (no -p flag)
     - Paste worker assignment template
     - Launch Haiku monitor with run_in_background=True

  4. AWAIT COMPLETION
     TaskOutput(task_id=monitor_agent_id, block=True)

  5. VALIDATE (THREE LEVELS - ALL MANDATORY)
     See Validation Protocol below

  6. CLOSE OR REMEDIATE
     IF all validation passed:
       # Delegate closure to validation-agent
       Task(
         subagent_type="validation-agent",
         prompt="--mode=e2e --task_id=<id> --prd=PRD-XXX"
       )
       # validation-agent closes with evidence if all criteria pass
       git add . && git commit -m "feat(<id>): [description]"
       → CONTINUE LOOP

     IF validation failed:
       Document failure in scratch pad
       IF first failure: Provide worker feedback, retry
       IF second failure: Decompose task, create sub-beads
       IF third failure: STOP, report to user

  7. REGRESSION SPOT CHECK (every 3rd feature)
     Pick 1 recently closed bead
     Run its validation
     IF regression: bd reopen → STOP, report to user

  8. CHECK STOP CONDITIONS
     IF any stop condition met: Exit loop, report to user
     ELSE: → CONTINUE LOOP
```

### Validation Protocol (3-Level)

**All three levels are MANDATORY before closing any feature.**

#### Level 1: Unit Tests

**Backend (Python/pytest)**:
```bash
cd agencheck-support-agent
pytest tests/ -v --tb=short
```

**Frontend (TypeScript/Jest)**:
```bash
cd agencheck-support-frontend
npm run test -- --coverage
```

**Pass Criteria**: Zero test failures, no uncaught exceptions, coverage maintained.

#### Level 2: Integration/API Tests

**API Endpoint Validation**:
```bash
# Health checks
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:5184/health | jq .
curl -s http://localhost:5185/health | jq .

# Feature-specific endpoints
curl -X POST http://localhost:8000/agencheck \
  -H "Content-Type: application/json" \
  -d '{"query": "test message", "session_id": "test-123"}'
```

**Pass Criteria**: All endpoints return 200, response structures match schemas, data persists.

#### Level 3: E2E Browser Tests

Use Markdown-based test specifications:

1. **Test Specification** → Read from `__tests__/e2e/specs/J{N}-*.md`
2. **Worker Execution** → Execute via chrome-devtools MCP tools
3. **Execution Report** → Write to `__tests__/e2e/results/J{N}/J{N}_EXECUTION_REPORT.md`
4. **Orchestrator Review** → Sense-check results, re-execute if anomalies

**Pass Criteria**: UI renders correctly, workflows complete, no JS console errors, 100% pass rate.

---

## Acceptance Test Generation (After PRD Parse)

**When**: Immediately after Task Master parse-prd and beads sync completes

**Purpose**: Generate executable test scripts from PRD before implementation begins

**Workflow**:

1. **Generate tests from PRD**:
   ```python
   # Orchestrator invokes skill (NOT worker, NOT validation-agent)
   Skill("acceptance-test-writer", args="--prd=PRD-XXX --source=.taskmaster/docs/prd.md")
   ```

2. **Review generated tests**:
   - Check `acceptance-tests/PRD-XXX/manifest.yaml` for completeness
   - Review each `AC-*.yaml` file for clarity
   - Adjust selectors/assertions if needed

3. **Commit tests**:
   ```bash
   git add acceptance-tests/ && git commit -m "test(PRD-XXX): add acceptance test suite"
   ```

**Output Directory**:
```
acceptance-tests/PRD-XXX/
├── manifest.yaml           # PRD metadata + feature list
├── AC-user-login.yaml     # Browser acceptance test
├── AC-api-auth.yaml       # API acceptance test
└── AC-session-timeout.yaml # Hybrid test
```

**Key Rules**:
- Generate tests in Phase 1 (Planning), NOT Phase 2 (Execution)
- Orchestrator generates tests, NOT workers
- validation-agent executes tests in Phase 3 (NOT orchestrator)
- Tests are committed to git with the beads hierarchy

**Integration with Validation Gate**:
```
Phase 1: PRD → acceptance-test-writer → acceptance-tests/PRD-XXX/
Phase 2: Workers implement (reference tests for guidance)
Phase 3: validation-agent --mode=e2e --prd=PRD-XXX → runs tests → closes tasks
```

---

## Feature Decomposition (MAKER)

**Reference:** "SOLVING A MILLION-STEP LLM TASK WITH ZERO ERRORS" paper

**Core Principle:** Decompose until each step is simple enough for a Haiku model to execute with high reliability.

### MAKER Checklist

Before adding ANY feature, ask these four questions:

| Question | If YES | If NO |
|----------|--------|-------|
| Can this be broken into smaller steps? | Decompose further | Proceed |
| Does each step modify multiple files? | Too broad, decompose | Proceed |
| Could a Haiku model complete each step? | Proceed | Too complex, decompose |
| Is there more than ONE decision per step? | Too complex, decompose | Proceed |

### Decision Tree

```
START: Evaluate feature candidate
    ↓
Is feature completable in ONE worker session?
    NO → Split into multiple features
    YES ↓
Does feature have 10+ validation steps?
    YES → Too large, split into smaller features
    NO ↓
Do validation steps include "and" or "then"?
    YES → Multiple tasks, split steps
    NO ↓
Does scope include 5+ files?
    YES → Too broad, reduce scope or split feature
    NO ↓
Is each step specific and verifiable?
    NO → Refine steps to be concrete
    YES ↓
✅ APPROVED: Add to feature list
```

### Red Flags

| Red Flag | Meaning | Action |
|----------|---------|--------|
| Feature has 10+ steps | Too large | Split into multiple features |
| Step says "and" | Multiple tasks | Split into separate steps |
| Step is vague ("make it work") | Undefined | Specify exact outcome |
| Scope has 5+ files | Too broad | Reduce scope per feature |
| Description includes "how" details | Implementation details leaking | Focus on "what" behavior |
| Dependencies form circular chain | Logic error | Redesign feature order |

### Warning Signs During Execution

If you observe these during Phase 2, the decomposition needs improvement:

- Workers consistently exceed 2 hours per feature
- Workers modify files outside scope repeatedly
- Features fail validation 3+ times
- Workers spawn 10+ sub-agents for one feature
- Workers report "unclear requirements"

**Action:** Stop, return to Phase 1, refine decomposition.

### Good vs Bad Steps

**Good Steps:**
- "Add email input field to login form"
- "Create POST /api/auth endpoint"
- "Verify token returned in response body"
- "Display error message when email invalid"

**Bad Steps:**
- "Implement authentication" (too vague)
- "Build login form and connect to backend" (multiple tasks)
- "Make it work" (undefined outcome)
- "Fix any bugs" (open-ended)

---

## Progress Tracking

### Files to Maintain

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `.claude/progress/{project}-summary.md` | Current state & next steps | End of every session |
| `.claude/progress/{project}-log.md` | Chronological history | End of every session |
| `.claude/learnings/decomposition.md` | Task breakdown patterns | After discovering patterns |
| `.claude/learnings/coordination.md` | Orchestration patterns | After successful coordination |
| `.claude/learnings/failures.md` | Anti-patterns & red flags | After recovering from failure |

### Session Summary Template

**Location:** `.claude/progress/{project}-summary.md`

```markdown
# Progress Summary

**Last Updated**: [YYYY-MM-DD HH:MM]
**Last Feature Completed**: F00X - [description]
**Next Feature Ready**: F00Y - [description]

## Current State

**Features Status:**
- Total features: X
- Passed: Y (YY%)
- Remaining: Z

**Recent Activity:**
- [Date]: Completed F00X (description)
- [Date]: Fixed regression in F00W

**Current Blocker (if any):**
- [None | Description of blocker]

## Technical Context

**Active Services:**
- Frontend: [Running on :5001 | Not started | Crashed]
- Backend: [Running on :8000 | Not started | Crashed]

## Notes for Next Session

**Quick Wins Available:**
- F00Y ready to implement (no blockers)

**Known Issues:**
- [List any gotchas discovered]

## Next Steps

1. Run regression check on [F001, F002]
2. Implement F00Y
3. If F00Y passes, proceed to F00Z
```

### Progress Log Template

**Location:** `.claude/progress/{project}-log.md`

```markdown
## [YYYY-MM-DD] Session [N]

**Duration:** ~[X] minutes
**Features Attempted:** F00X, F00Y
**Features Completed:** F00X

### What Was Done
- Started session at [time]
- Ran regression check - all passed
- Assigned F00X to frontend worker
- Worker completed in 45 minutes
- Validated via browser testing - passed
- Committed: "feat(F00X): [description]"

### What Worked Well
- MAKER decomposition was effective
- Worker completed without blockers

### Challenges / Issues
- Initial scope included too many files

### Time Breakdown
- Regression check: 5 min
- Worker execution: 45 min
- Validation: 10 min

### Next Session Should
- Continue with F00Y (ready, no blockers)
```

### Learnings Accumulation

**Three learning categories:**

1. **Decomposition Patterns** (`.claude/learnings/decomposition.md`)
   - Feature sizes that work well
   - Effective validation step patterns

2. **Coordination Patterns** (`.claude/learnings/coordination.md`)
   - Effective worker delegation strategies
   - When to intervene vs let worker continue

3. **Failure Patterns** (`.claude/learnings/failures.md`)
   - Anti-patterns that caused problems
   - Recovery strategies that worked

---

## Session Handoffs

### Before Ending Checklist

**Before ending ANY orchestration session:**

1. **Feature State Clean**
   - [ ] Current feature either complete OR cleanly stopped
   - [ ] No uncommitted code changes
   - [ ] No active worker sessions

2. **Feature List Updated**
   - [ ] State file updated with latest passes status
   - [ ] State file committed to git
   - [ ] Commit message describes what passed

3. **Progress Documentation Updated**
   - [ ] `summary.md` updated with current counts, blockers, context
   - [ ] `log.md` entry added for this session
   - [ ] Progress files committed

4. **Git State Clean**
   - [ ] `git status` shows clean working tree
   - [ ] All progress committed
   - [ ] Current branch noted in summary.md

5. **Learnings Captured**
   - [ ] Any new patterns documented in `.claude/learnings/`
   - [ ] Learning files committed to git

6. **Services State Noted**
   - [ ] Service status documented in summary.md

**Quick handoff command sequence:**
```bash
# 1. Ensure workers terminated
tmux list-sessions | grep worker && echo "Kill worker sessions first"

# 2. Update state and commit
git add .claude/state/
git commit -m "feat(F00X): [description] - marked complete"

# 3. Update progress files
git add .claude/progress/
git commit -m "docs: update progress after F00X completion"

# 4. Verify clean state
git status
```

### Starting New Session

**When resuming orchestration work:**

1. **Load Context**
   ```bash
   cat .claude/progress/{project}-summary.md
   tail -100 .claude/progress/{project}-log.md
   ```

2. **Verify Environment**
   - [ ] Services status matches summary.md expectation
   - [ ] Git status clean, on correct branch

3. **Mandatory Regression Check**
   - Pick 1-2 features marked `passes: true`
   - Run their validation steps
   - If ANY fail → mark as `passes: false` and fix BEFORE proceeding

4. **Identify Next Feature**
   - Find next ready feature (passes == false, dependencies satisfied)
   - Check all dependencies have passes == true

5. **Begin Work**
   - Proceed to Phase 2 workflow

---

**Version**: 1.0
**Created**: 2026-01-07
**Consolidated from**: AUTONOMOUS_MODE.md, ORCHESTRATOR_PROCESS_FLOW.md, FEATURE_DECOMPOSITION.md, PROGRESS_TRACKING.md
