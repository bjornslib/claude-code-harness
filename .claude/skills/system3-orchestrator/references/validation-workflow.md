# Validation Workflow Reference

Comprehensive 3-level validation and validation-agent usage for ensuring work quality.

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

## Validation Agent Integration

### Two Modes

| Mode | Flag | Used By | Purpose |
|------|------|---------|---------|
| **Unit** | `--mode=unit` | Orchestrators | Fast technical checks (mocks OK) |
| **E2E** | `--mode=e2e --prd=PRD-XXX` | Orchestrators & System 3 | Full acceptance validation against PRD criteria |

**CRITICAL**: `--prd` parameter is MANDATORY for E2E mode. The validation-agent will invoke `acceptance-test-runner` internally.

### Orchestrator Usage (Unit/E2E Mode)

**Orchestrators delegate ALL task closure to validation-agent.**

```python
# Fast unit check
Task(
    subagent_type="validation-agent",
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
    subagent_type="validation-agent",
    prompt="""
    Validate task <task-id> with E2E validation:
    --mode=e2e
    --prd=PRD-AUTH-001
    --task_id=<task-id>

    validation-agent will invoke acceptance-test-runner internally.
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
    subagent_type="validation-agent",
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

Gather information validation-agent needs:
- Read the PRD to understand scope and acceptance criteria
- Identify the worktree/branch where implementation lives
- Note specific areas of concern or focus
- Identify the PRD ID for the `--prd` parameter

**BOUNDARY**: The moment the thought arises "let me read the implementation files
to check if they match the PRD" — STOP. That is validation work.

### Step 2: Delegation (one tool call)

```python
Task(
    subagent_type="validation-agent",
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

After validation-agent returns:
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

### Validation Agent

```python
# For tasks - fast unit check (orchestrator)
Task(subagent_type="validation-agent", prompt="--mode=unit --task_id=<id>")

# For tasks - full E2E validation (orchestrator)
Task(subagent_type="validation-agent", prompt="--mode=e2e --prd=PRD-XXX --task_id=<id>")

# For business outcomes (System 3)
Task(subagent_type="validation-agent", prompt="--mode=e2e --prd=PRD-XXX --task_id=<id>")
```

---

**Version**: 1.0.0
**Source**: System 3 Output Style - Enforcing 3-Level Validation, Validation Agent Integration
