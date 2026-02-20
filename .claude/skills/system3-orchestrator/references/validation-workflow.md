---
title: "Validation Workflow"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Validation Workflow Reference

Comprehensive 3-level validation and validation-test-agent usage for ensuring work quality.

---

## 3-Level Validation Protocol

Every feature must pass ALL THREE levels before marking complete.

| Level | What | How | Purpose |
|-------|------|-----|---------|
| 1 | **Unit Tests** | `pytest` / `jest` | Code logic works |
| 2 | **API Tests** | `curl` endpoints | Services respond correctly |
| 3 | **E2E Browser** | Browser automation | User workflow works |

**Critical Rule**: Tests passing != Feature working. Mocked success is invisible without real-world validation.

---

## Level 1: Unit Tests

### Backend (Python)

```bash
cd agencheck-support-agent && pytest tests/ -v --tb=short
```

### Frontend (React/Next.js)

```bash
cd agencheck-support-frontend && npm run test
```

### What to Check

- All tests pass
- No skipped tests without reason
- Coverage didn't decrease

---

## Level 2: API Tests

### Health Checks

```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:5184/health | jq .
curl -s http://localhost:5185/health | jq .
```

### Feature-Specific Endpoints

```bash
# Test the actual endpoint the feature uses
curl -X POST http://localhost:8000/api/feature \
    -H "Content-Type: application/json" \
    -d '{"test": "data"}' | jq .
```

### What to Check

- Endpoint returns 200/201 for success cases
- Error cases return appropriate status codes
- Response structure matches expectations

---

## Level 3: E2E Browser Tests

### Using chrome-devtools MCP

```python
# Navigate to feature
mcp__chrome-devtools__navigate_page({ url: "http://localhost:5001/feature" })

# Take snapshot for verification
mcp__chrome-devtools__take_snapshot({})

# Interact with elements
mcp__chrome-devtools__click_element({ selector: "button.submit" })

# Verify result
mcp__chrome-devtools__take_snapshot({})
```

### Using Playwright (via tmux worker)

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    prompt="""
    Run Playwright E2E tests for the feature:

    cd agencheck-support-frontend
    npx playwright test tests/e2e/feature.spec.ts

    Report: PASS or FAIL with details
    """
)
```

### What to Check

- User can complete the workflow
- UI displays expected results
- No console errors
- No visual regressions

---

## The Hollow Test Problem

**Problem**: Unit tests pass but feature doesn't work.

**Cause**: Tests mock dependencies, so they test the mock, not the integration.

**Solution**: Always verify with Level 2 (API) and Level 3 (E2E).

### Example

```python
# Unit test passes (mocked)
def test_create_user():
    mock_db.create.return_value = User(id=1)
    result = create_user("test")
    assert result.id == 1  # PASS - but only tests mock

# API test reveals truth
# curl -X POST /api/users -d '{"name":"test"}'
# Returns: 500 Internal Server Error - DB connection failed
```

---

## On-Demand Validation Teammate (F4.1)

### Overview

System 3 spawns `s3-validator` teammates **on-demand** — one per validation request. Validators are short-lived: they receive a request, validate, report results via `SendMessage`, and exit. This replaces the continuous-oversight model for targeted validations.

**Key Principle**: Spawn per-request, validate, report, exit. Do NOT keep validators idle.

### When to Use On-Demand vs Oversight Team

| Scenario | Pattern | Why |
|----------|---------|-----|
| Single task validation after implementation | **On-demand s3-validator** | Cheap, focused, exits quickly |
| Full PRD acceptance testing (multi-feature) | **On-demand s3-validator** | Same pattern, richer prompt |
| Post-orchestrator comprehensive check | **Oversight team** (see oversight-team.md) | Multiple specialists needed |
| Parallel validation of independent tasks | **Multiple on-demand validators** | Each validates independently |

### Spawn Pattern: Single Validation

```python
# Step 1: Spawn s3-validator as a teammate
Task(
    subagent_type="validation-test-agent",
    team_name="s3-live",
    name=f"s3-validator-{task_id}",
    model="sonnet",  # MUST be Sonnet — Haiku lacks exit discipline
    prompt=f"""You are s3-validator-{task_id} in the System 3 oversight team.

    ## Validation Request
    Task ID: {task_id}
    PRD: {prd_id}
    Worktree: {worktree_path}
    Validation Type: {validation_type}  # code | browser | both

    ## Acceptance Criteria to Validate
    {acceptance_criteria_list}

    ## Claimed Evidence from Orchestrator
    {orchestrator_claimed_evidence}

    ## Instructions
    1. Independently verify each acceptance criterion
    2. For code validation: read files, run tests, check implementations
    3. For browser validation: use Claude in Chrome tools for E2E checks
    4. Capture evidence for every criterion (PASS/FAIL with specifics)
    5. Report results via SendMessage to team-lead
    6. Exit after reporting — do NOT wait for more work

    ## Required Output (via SendMessage)
    Include a JSON validation response in your message:
    {{
        "task_id": "{task_id}",
        "verdict": "PASS" | "FAIL",
        "criteria_results": [
            {{"criterion": "...", "status": "PASS|FAIL", "evidence": "..."}}
        ],
        "screenshots": ["path1", "path2"],
        "reasoning": "Overall assessment",
        "confidence": 0.0-1.0
    }}
    """
)
```

### Spawn Pattern: Parallel Validators

For validating multiple independent tasks simultaneously:

```python
# Spawn one validator per task — they run in parallel
for task in tasks_to_validate:
    Task(
        subagent_type="validation-test-agent",
        team_name="s3-live",
        name=f"s3-validator-{task.id}",
        model="sonnet",
        prompt=f"""You are s3-validator-{task.id} in the System 3 oversight team.
        [Same prompt structure as single validation above]
        Task ID: {task.id}
        PRD: {task.prd_id}
        Acceptance Criteria: {task.criteria}
        """
    )

# Results arrive via SendMessage — correlate by task_id in the response JSON
# Each validator exits independently after reporting
```

### Spawn Pattern: Browser Validation

When acceptance criteria require browser/E2E verification:

```python
Task(
    subagent_type="validation-test-agent",
    team_name="s3-live",
    name=f"s3-validator-{task_id}",
    model="sonnet",
    prompt=f"""You are s3-validator-{task_id} in the System 3 oversight team.

    ## Validation Request (Browser Required)
    Task ID: {task_id}
    Validation Type: browser

    ## Browser Validation Steps
    1. Navigate to {app_url}
    2. Verify: {ui_acceptance_criteria}
    3. Take screenshots of key states
    4. Check browser console for errors
    5. Report via SendMessage with screenshot paths

    ## Tools Available
    - Claude in Chrome (mcp__claude-in-chrome__*) for browser automation
    - File system tools for reading test specs
    - Bash for running CLI tests

    ## Exit Protocol
    After validation: SendMessage results to team-lead, then exit.
    """
)
```

### Result Handling

After validators report back:

```python
# Validators send results via SendMessage — auto-delivered to System 3
# Parse the JSON validation response from the message content

if verdict == "PASS":
    # Gate 3: Run cs-verify programmatic check (triple-gate)
    Bash(f"cs-verify --promise {promise_id} --type api --proof '{evidence_summary}'")
    Bash(f"bd close {task_id} --reason 'S3 validated: all criteria pass'")
elif verdict == "FAIL":
    # Do NOT close — spawn orchestrator to fix
    Bash(f"bd update {task_id} --status=in_progress")
    # Send failure details to orchestrator via message bus
    Bash(f"mb-send orch-{{name}} s3_rejected '{{\"task_id\": \"{task_id}\", \"failures\": \"{failure_list}\"}}'")
```

### Model Requirements

| Role | Model | Why |
|------|-------|-----|
| s3-validator | **Sonnet 4.5** | Exit discipline — Haiku keeps running after reporting |
| Multiple validators | **Sonnet 4.5 each** | Same reason; each must exit independently |

**Tested finding (2026-01-25)**: Haiku validates correctly (5/5 tests passed) but fails to EXIT, continuing to write documentation. Sonnet returns promptly with structured results.

### Lifecycle

```
System 3                    s3-validator
   │                            │
   │  Task(team_name=...) ─────►│
   │                            │── Read PRD & criteria
   │                            │── Run tests / browser
   │                            │── Capture evidence
   │◄── SendMessage(verdict) ───│
   │                            │── EXIT (graceful)
   │  Handle result             ✕
   │  [spawn next if needed]
```

---

## Validation Agent Integration

### Three Modes

| Mode | Flag | Used By | Purpose |
|------|------|---------|---------|
| **Unit** | `--mode=unit` | Orchestrators | Fast technical checks (mocks OK) |
| **E2E** | `--mode=e2e --prd=PRD-XXX` | Orchestrators & System 3 | Full acceptance validation against PRD criteria |
| **Monitor** | `--mode=monitor` | System 3 | Continuous task completion monitoring |

**CRITICAL**: `--prd` parameter is MANDATORY for E2E mode. The validation-test-agent will invoke `acceptance-test-runner` internally.

### Orchestrator Usage (Unit/E2E Mode)

**Orchestrators delegate ALL task closure to validation-test-agent.**

```python
# Fast unit check
Task(
    subagent_type="validation-test-agent",
    prompt="""
    Validate task <task-id> with unit tests:
    --mode=unit
    --task_id=<task-id>

    Run fast technical checks (mocks OK).

    If pass: Close task with evidence
    If fail: Report failure, do NOT close
    """
)

# Full E2E validation with PRD acceptance tests
Task(
    subagent_type="validation-test-agent",
    prompt="""
    Validate task <task-id> with E2E validation:
    --mode=e2e
    --prd=PRD-AUTH-001
    --task_id=<task-id>

    validation-test-agent will invoke acceptance-test-runner internally.
    Validation against PRD acceptance criteria.

    If ALL criteria pass: Close task with evidence
    If ANY fail: Report failure, do NOT close
    """
)
```

### System 3 Usage (E2E Mode)

**System 3 validates Business Epics and Key Results via E2E mode.**

```python
Task(
    subagent_type="validation-test-agent",
    prompt="""
    Validate business outcome for <bo-id> with E2E validation:
    --mode=e2e
    --prd=PRD-WORK-HISTORY-001
    --task_id=<bo-id>

    Validate against Key Results from PRD:
    - KR1: [description] - verify with evidence
    - KR2: [description] - verify with evidence

    If ALL Key Results verified: Close Business Epic
    If ANY fail: Report gap, do NOT close
    """
)
```

---

## PRD Validation Gate (MANDATORY)

System 3 NEVER validates PRD implementations directly. Follow this context collation
→ delegation pattern.

### Step 1: Context Collation (System 3 does this)

Gather information validation-test-agent needs:
- Read the PRD to understand scope and acceptance criteria
- Identify the worktree/branch where implementation lives
- Note specific areas of concern or focus
- Identify the PRD ID for the `--prd` parameter

**BOUNDARY**: The moment the thought arises "let me read the implementation files
to check if they match the PRD" — STOP. That is validation work.

### Step 2: Delegation (one tool call)

```python
Task(
    subagent_type="validation-test-agent",
    prompt=f"""
    --mode=e2e
    --prd=PRD-{prd_id}

    ## Validation Request
    Validate PRD implementation completeness.

    ## PRD Location
    {prd_path}

    ## Implementation Location
    Worktree: {worktree_path}
    Branch: {branch_name}

    ## Acceptance Criteria to Validate
    {extracted_criteria_from_prd}

    ## Focus Areas (if any)
    {specific_concerns}

    ## Required Output
    For each acceptance criterion:
    1. PASS/FAIL with file-level evidence
    2. If FAIL: specific gap description and remediation steps
    3. Confidence level (high/medium/low)

    Produce a structured gap analysis report.
    """
)
```

### Step 3: Review Report (System 3 reviews the REPORT, not the code)

After validation-test-agent returns:
1. Read the structured gap analysis report
2. If all PASS → proceed to next phase (close epic, advance Key Result)
3. If any FAIL → spawn orchestrator to fix gaps, then re-validate
4. Store validation outcome to Hindsight for pattern tracking

---

## The Gate Function

**Every claim needs proof.** Follow this pattern:

1. **IDENTIFY**: What command proves this claim?
2. **RUN**: Execute the FULL command (fresh, complete)
3. **READ**: Full output, check exit code, count failures
4. **VERIFY**: Does output confirm the claim?
5. **ONLY THEN**: Make the claim

### Before Validation

Always invoke the verification skill first:

```python
Skill("verification-before-completion")
```

This loads the Iron Law: "No completion claims without fresh verification evidence from THIS session."

---

## Mandatory Regression Check

**Before ANY new feature work:**

1. Pick 1-2 recently closed tasks (`bd list --status=closed`)
2. Run 3-level validation on them
3. If ANY fail: `bd reopen <id>` and fix BEFORE new work

**Why**: Hidden regressions multiply across features. This is a circuit breaker.

---

## Validation Evidence Format

When recording verification proof:

```bash
.claude/scripts/completion-state/cs-verify \
    --feature F1.1 \
    --type test \
    --command "pytest tests/test_feature.py -v" \
    --proof "5 passed, 0 failed in 2.3s"
```

### Good Evidence Examples

- "All 12 tests passed (exit code 0)"
- "API returned 200 with expected fields: id, name, status"
- "Browser screenshot shows success message after form submission"

### Bad Evidence Examples

- "I checked and it works" (no proof)
- "Tests passed" (no specifics)
- "Should be fine now" (no verification)

---

## Quick Reference

### Validation Commands

```bash
# Level 1: Unit
cd agencheck-support-agent && pytest tests/ -v

# Level 2: API
curl -s localhost:8000/health | jq .

# Level 3: E2E
# Use chrome-devtools MCP or Playwright
```

### Validation Agent (Subagent — Orchestrator Use)

```python
# For tasks - fast unit check (orchestrator)
Task(subagent_type="validation-test-agent", prompt="--mode=unit --task_id=<id>")

# For tasks - full E2E validation (orchestrator)
Task(subagent_type="validation-test-agent", prompt="--mode=e2e --prd=PRD-XXX --task_id=<id>")
```

### On-Demand Validator (Teammate — System 3 Use)

```python
# Spawn validator as teammate for independent verification
Task(
    subagent_type="validation-test-agent",
    team_name="s3-live",
    name=f"s3-validator-{task_id}",
    model="sonnet",
    prompt="[validation request with criteria, evidence, worktree path]"
)
# Results arrive via SendMessage — correlate by task_id
```

### Triple-Gate Validation (Full Chain)

```
Gate 1: Session self-reports completion (cs-promise)
Gate 2: s3-validator teammate independently verifies (on-demand spawn)
Gate 3: cs-verify calls Sonnet 4.5 as programmatic judge (Anthropic SDK)
```

---

**Version**: 2.0.0
**Source**: System 3 Output Style, PRD-S3-AUTONOMY-001 Epic 4 (F4.1, F4.2, F4.3)
