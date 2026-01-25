# Worker Delegation

Patterns for delegating implementation to Task subagents.

**Part of**: [Multi-Agent Orchestrator Skill](SKILL.md)

---

## Table of Contents
- [Core Principle](#core-principle)
- [Worker Types](#worker-types)
- [Task Delegation Pattern](#task-delegation-pattern)
- [Worker Assignment Template](#worker-assignment-template)
- [Parallel Worker Pattern](#parallel-worker-pattern)
- [Browser Testing Workers](#browser-testing-workers)

---

## 🚨 3-Tier Hierarchy (CRITICAL)

Understanding the hierarchy prevents delegation violations:

| Tier | Role | Spawns | Implements |
|------|------|--------|------------|
| **TIER 1: System 3** | Meta-orchestrator | Orchestrators via tmux | ❌ Never |
| **TIER 2: Orchestrator** | Coordinator | Workers via Task subagents | ❌ Never |
| **TIER 3: Worker** | Implementer | ❌ Does NOT spawn sub-workers | ✅ Directly |

**The Key Insight**: Workers are the END of the chain. They implement directly using Edit/Write tools. Workers do NOT spawn their own sub-workers or sub-agents for implementation.

```
System 3 ──tmux──► Orchestrator ──Task()──► Worker ──Edit/Write──► Code
                                              │
                                              └──► (Task for validation ONLY, not implementation)
```

**Important Distinction**:
- **System 3 → Orchestrator**: Uses tmux for session isolation (orchestrators need persistent isolated environments in worktrees)
- **Orchestrator → Worker**: Uses Task subagents (workers complete tasks and return results directly)

---

## Core Principle

**Orchestrator = Coordinator. Worker = Implementer.**

Use `Task(subagent_type=specialist)` for all worker delegation.

```python
# ✅ CORRECT - Worker via Task subagent
result = Task(
    subagent_type="frontend-dev-expert",
    description="Implement feature F001",
    prompt="""
    ## Task: [Task title from Beads]

    **Context**: [investigation summary]
    **Requirements**: [list requirements]
    **Acceptance Criteria**: [list criteria]
    **Scope** (ONLY these files): [file list]

    **Report back with**: Files modified, tests written/passed, any blockers
    """
)
# Result returned directly - no monitoring needed
```

**Why Task subagents?**
- Workers receive assignments and return results directly
- No session management or monitoring loops
- No cleanup required (automatic)
- Orchestrator blocks until worker completes (or use `run_in_background=True` for parallel)

---

## Worker Types

| Type | subagent_type | Use For |
|------|---------------|---------|
| Frontend | `frontend-dev-expert` | React, Next.js, UI, TypeScript |
| Backend | `backend-solutions-engineer` | Python, FastAPI, PydanticAI, MCP |
| Browser Testing | `tdd-test-engineer` | E2E validation, browser automation |
| General | `general-purpose` | Scripts, docs, everything else |

### Quick Decision Rule

**Using Beads**: Worker type is stored in bead metadata:
```bash
bd show <bd-id>  # View metadata including worker_type
```

**If worker_type not specified**, determine from scope:
- Scope includes `*-frontend/*` -> `frontend-dev-expert`
- Scope includes `*-agent/*` or `*-backend/*` -> `backend-solutions-engineer`
- Otherwise -> `general-purpose`

---

## Task Delegation Pattern

### Standard Blocking Pattern

Use for single worker delegation where you need the result immediately:

```python
result = Task(
    subagent_type="backend-solutions-engineer",
    description="Implement [feature]",
    prompt="""
    ## Task: Create API endpoint for user authentication

    **Context**: We're building a FastAPI backend with JWT auth
    **Requirements**:
    - POST /api/auth/login endpoint
    - Accept email and password
    - Return JWT token on success

    **Acceptance Criteria**:
    - [ ] Endpoint returns 200 with valid credentials
    - [ ] Endpoint returns 401 with invalid credentials
    - [ ] Token expires in 24 hours

    **Scope**: ONLY these files:
    - agencheck-support-agent/app/routes/auth.py
    - agencheck-support-agent/app/schemas/auth.py

    **Report back with**: Files modified, tests written, any blockers
    """
)
# Orchestrator waits here until worker completes
print(f"Worker result: {result}")
```

### Key Parameters

| Parameter | Purpose | When to Use |
|-----------|---------|-------------|
| `subagent_type` | Worker specialist type | Always required |
| `description` | Short task summary | Always (3-5 words) |
| `prompt` | Full assignment | Always (use template below) |
| `run_in_background` | Return immediately, collect later | Parallel workers |
| `model` | Override model | Rarely needed |

---

## Worker Assignment Template

### Beads Format (RECOMMENDED)

```markdown
## Task Assignment: bd-xxxx

### Mandatory: Serena Mode Activation
Set mode before starting work:
mcp__serena__switch_modes(["editing", "interactive"])

### Checkpoint Protocol (NEVER SKIP)
1. After gathering context (3+ files/symbols):
   `mcp__serena__think_about_collected_information()`

2. Every 5 tool calls during implementation:
   `mcp__serena__think_about_task_adherence()`

3. BEFORE reporting completion (MANDATORY):
   `mcp__serena__think_about_whether_you_are_done()`

---

**Bead ID**: bd-xxxx
**Description**: [Task title from Beads]
**Priority**: P0/P1/P2/P3

**Validation Steps**:
1. [Step 1 from bead metadata]
2. [Step 2 from bead metadata]
3. [Step 3 from bead metadata]

**Scope** (ONLY these files):
- [file1.ts]
- [file2.py]

**Validation Type**: [browser/api/unit]

**Dependencies Verified**: [List parent beads that are closed]

**Your Role**:
- You are TIER 3 in the 3-tier hierarchy (Worker)
- Complete this ONE SMALL TASK - implement it DIRECTLY yourself
- Do NOT spawn sub-agents for implementation - you ARE the implementer
- ONLY modify files in scope list
- Use superpowers:test-driven-development
- Use superpowers:verification-before-completion before claiming done

**Implementation Approach**:
- Write the code yourself using Edit/Write tools
- Write the tests yourself using Edit/Write tools
- You are a specialist agent (frontend-dev-expert, backend-solutions-engineer, etc.)
- Sub-agents are ONLY for validation checks AFTER implementation, not during
- If you need research help, use Task(model="haiku") for quick lookups only

**When Done**:
1. Run all validation steps from above
2. Verify all tests pass
3. MANDATORY CHECKPOINT: `mcp__serena__think_about_whether_you_are_done()`
4. Report: "Task bd-xxxx COMPLETE" or "Task bd-xxxx BLOCKED: [details]"
5. Do NOT run `bd close` - orchestrator handles status updates
6. Commit with message: "feat(bd-xxxx): [description]"

**CRITICAL Constraints**:
- Do NOT modify files outside scope
- Do NOT leave TODO/FIXME comments
- Do NOT use "I think" or "probably" - verify everything
- Do NOT run `bd close` or update bead status
```

### Assignment Checklist

Before launching worker, verify assignment includes:

- [ ] Feature ID and exact description
- [ ] Complete validation steps list
- [ ] Explicit scope (file paths)
- [ ] Validation type specified
- [ ] Dependencies verified as passing
- [ ] Role explanation (TIER 3 = direct implementer)
- [ ] Implementation approach (worker implements directly, not via sub-agents)
- [ ] Completion criteria
- [ ] Critical constraints listed

---

## Parallel Worker Pattern

When delegating multiple workers that can run concurrently:

```python
# Launch workers in parallel using run_in_background=True
frontend_task = Task(
    subagent_type="frontend-dev-expert",
    run_in_background=True,  # Don't block
    description="Frontend feature F001",
    prompt="[Worker assignment...]"
)

backend_task = Task(
    subagent_type="backend-solutions-engineer",
    run_in_background=True,  # Don't block
    description="Backend feature F002",
    prompt="[Worker assignment...]"
)

# Both workers are now running in parallel
# Collect results when needed

frontend_result = TaskOutput(task_id=frontend_task.agent_id, block=True)
backend_result = TaskOutput(task_id=backend_task.agent_id, block=True)

# Process results
if "COMPLETE" in frontend_result and "COMPLETE" in backend_result:
    print("Both workers completed successfully")
```

### When to Use Parallel Workers

| Scenario | Pattern |
|----------|---------|
| Single feature | Blocking: `Task(...)` |
| Frontend + Backend in parallel | Parallel: `run_in_background=True` + `TaskOutput()` |
| Multiple independent features | Parallel: Launch all, collect all |
| Voting consensus (multiple approaches) | Parallel: 3-5 workers, compare results |

### Voting Consensus Pattern

When you need multiple perspectives on a problem:

```python
# Launch multiple workers with different approaches
workers = []
for i, approach in enumerate(["approach_a", "approach_b", "approach_c"]):
    worker = Task(
        subagent_type="general-purpose",
        run_in_background=True,
        description=f"Solution {i+1}",
        prompt=f"Solve using {approach}..."
    )
    workers.append(worker)

# Collect all results
results = [TaskOutput(task_id=w.agent_id, block=True) for w in workers]

# Analyze consensus
consensus = analyze_voting_results(results)
```

---

## Browser Testing Workers

### Overview

Browser testing workers enable actual E2E validation using chrome-devtools MCP tools or Playwright for real browser automation.

**Pattern**: Orchestrator → Task(tdd-test-engineer) → Browser Testing → Results

### When to Use

**Use browser testing workers when**:
- Feature requires validation of actual browser behavior
- Testing UI interactions, animations, scroll behavior
- Validating accessibility (keyboard navigation, ARIA)
- Performance testing (load times, interaction responsiveness)
- Visual regression testing (screenshots, layout)

**Don't use for**:
- Pure logic testing (use unit tests)
- API endpoint testing (use curl/HTTP requests)
- Backend validation (use pytest)

### Browser Testing Pattern

```python
# Direct browser testing via Task subagent
result = Task(
    subagent_type="tdd-test-engineer",
    description="E2E browser testing for F084",
    prompt="""
    MISSION: Validate feature F084 via browser automation

    TARGET: http://localhost:5001/[path]

    TESTING CHECKLIST:
    - [ ] Navigate to page (chrome-devtools: navigate)
    - [ ] Verify UI renders correctly (read_page, screenshot)
    - [ ] Test user interactions (click, form_input)
    - [ ] Verify state changes (read_page after action)
    - [ ] Capture screenshots as evidence

    VALIDATION CRITERIA:
    - Page loads without console errors
    - All interactive elements are accessible
    - User workflow completes successfully

    REPORT FORMAT:
    - Pass/Fail per item
    - Screenshots of key states
    - Console log analysis
    - Overall assessment
    """
)
```

### Test Specification Workflow

```
1. TEST SPECIFICATION (Markdown)
   Location: __tests__/e2e/specs/J{N}-{journey-name}.md
   Format: Given/When/Then with chrome-devtools steps
                                 |
                                 v
2. WORKER EXECUTION (via Task)
   - Worker reads the test spec Markdown file
   - Worker executes tests using chrome-devtools MCP tools
   - Worker captures screenshots as evidence
                                 |
                                 v
3. EXECUTION REPORT
   Location: __tests__/e2e/results/J{N}/J{N}_EXECUTION_REPORT.md
   Contents: Pass/Fail per test, evidence, issues found
                                 |
                                 v
4. ORCHESTRATOR REVIEW
   - Reviews execution report for anomalies
   - Sense-checks results against expected behavior
   - Approves or requests fixes
```

---

## Worker Output Handling

### Interpreting Results

| Signal in Result | Meaning | Action |
|------------------|---------|--------|
| "COMPLETE" | Worker finished successfully | Validate, close bead |
| "BLOCKED" | Worker needs help | Read blocker reason, provide guidance or re-delegate |
| "FAIL" after test run | Tests failed | Review failure, fix or retry |
| "PASS" after test run | Tests passed | Good - proceed to validation |
| Files outside scope | Scope violation | Reject, fresh retry with clearer boundaries |

### Red Flags

| Signal | Action |
|--------|--------|
| Modified files outside scope | Reject - Fresh retry with clearer scope |
| TODO/FIXME in output | Reject - Fresh retry (incomplete work) |
| Validation fails | Reject - Fresh retry |
| Worker reports unclear requirements | Re-decompose task with better spec |

---

## Related Documents

- **[SKILL.md](SKILL.md)** - Main orchestrator skill
- **[WORKFLOWS.md](WORKFLOWS.md)** - Feature decomposition, autonomous mode
- **[VALIDATION.md](VALIDATION.md)** - Service startup, testing infrastructure

---

**Document Version**: 2.0 (Task-Based Delegation)
**Last Updated**: 2026-01-25
**Major Changes**: Replaced tmux worker delegation with Task subagents. Workers now receive assignments via `Task(subagent_type="...")` and return results directly. System 3 → Orchestrator still uses tmux; Orchestrator → Worker now uses Task subagents.
