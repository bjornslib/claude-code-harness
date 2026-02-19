---
title: "Solution Design Acceptance Testing"
status: active
type: architecture
last_verified: 2026-02-19
grade: reference
---

# Solution Design: Acceptance Testing Framework

**Author**: System 3 + User Collaboration
**Date**: 2026-01-24
**Status**: APPROVED
**PRD Reference**: N/A (Infrastructure improvement)

---

## 1. Problem Statement

### Current State
The validation-test-agent checks whether code **runs** but not whether it does what it was **supposed to do**. This creates a critical gap:

```
Worker implements feature → Validation-agent runs tests → "TECHNICAL_PASS"
                                     ↓
                          But... does it meet the PRD requirements?
                          Does it achieve the business outcomes?

                          ❌ Unknown - validation-test-agent lacks this context
```

### Root Cause
1. Validation-agent has no access to PRD acceptance criteria
2. Tests verify "code executes" not "feature works as specified"
3. No evidence-based reporting linking outcomes to requirements
4. No structured format for acceptance criteria that can be executed

### Impact
- Tasks closed as "done" that don't meet business requirements
- Orchestrators cannot verify worker implementations match PRD
- Feedback loop is broken - workers don't know WHAT failed, only THAT something failed

---

## 2. Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRD LIFECYCLE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌─────────────────────┐    ┌──────────────────────┐   │
│  │     PRD      │───▶│ acceptance-test-    │───▶│ acceptance-tests/    │   │
│  │  (markdown)  │    │ writer skill        │    │ PRD-XXX/             │   │
│  └──────────────┘    └─────────────────────┘    │ ├── manifest.yaml    │   │
│                                                  │ ├── AC-feature-1.yaml│   │
│                                                  │ └── AC-feature-2.yaml│   │
│                                                  └──────────────────────┘   │
│                                                             │               │
│  ┌──────────────────────────────────────────────────────────┼───────────┐  │
│  │                     IMPLEMENTATION PHASE                 │           │  │
│  │                                                          ▼           │  │
│  │  Worker ───▶ Orchestrator ───▶ validation-test-agent ───▶ acceptance-   │  │
│  │  "done"      "validate"        routes to:            test-runner    │  │
│  │                                --mode=unit  ───▶ pytest/jest        │  │
│  │                                --mode=e2e   ───▶ acceptance-test-   │  │
│  │                                                  runner skill       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                             │               │
│                                                             ▼               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      VALIDATION REPORT                               │  │
│  │  acceptance-tests/PRD-XXX/runs/<timestamp>.md                           │  │
│  │  - Per-criterion PASS/FAIL                                           │  │
│  │  - Evidence (screenshots, API responses)                             │  │
│  │  - Gap analysis for failures                                         │  │
│  │  - Actionable feedback                                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Purpose | Type |
|-----------|---------|------|
| `acceptance-test-writer` | Generate executable test scripts from PRD | Skill |
| `acceptance-test-runner` | Execute tests, capture evidence, report results | Skill |
| `validation-test-agent` | Route to appropriate testing mode | Agent (updated) |

### Validation Modes (Simplified)

| Mode | What It Does | Data | When |
|------|--------------|------|------|
| `--mode=unit` | pytest/jest, API unit tests | Mocks OK | Fast feedback during dev |
| `--mode=e2e` | Browser + API tests against acceptance criteria | Real data ONLY | Before closing task |

**Key Insight**: E2E mode tests against acceptance criteria. If acceptance criteria pass, business outcomes are achieved. There is no separate "business" mode.

---

## 3. Directory Structure

```
acceptance-tests/
├── PRD-AUTH-001/                      # Directory named after PRD
│   ├── manifest.yaml                  # PRD metadata + feature list
│   ├── AC-user-login.yaml             # One file per acceptance criterion
│   ├── AC-invalid-credentials.yaml
│   ├── AC-password-reset-request.yaml
│   └── AC-password-reset-complete.yaml
│
├── PRD-BILLING-002/
│   ├── manifest.yaml
│   ├── AC-usage-tracking.yaml
│   ├── AC-overage-detection.yaml
│   └── AC-invoice-generation.yaml
│
├── PRD-DASHBOARD-003/
│   └── ...
│
└── PRD-AUTH-001/                      # Example with run results
    ├── manifest.yaml
    ├── AC-user-login.yaml
    ├── AC-password-reset.yaml
    └── runs/                           # Test execution results
        ├── 2026-01-24T10-30-00Z.md    # Timestamped report
        └── evidence/
            ├── AC-user-login-success.png
            └── AC-user-login-step2.png
```

> **Note**: Validation reports are stored in `runs/` within each PRD's acceptance-tests directory, keeping all PRD-related artifacts together.

---

## 4. Data Formats

### 4.1 Manifest Format

```yaml
# acceptance-tests/PRD-AUTH-001/manifest.yaml
prd_id: PRD-AUTH-001
prd_title: "User Authentication System"
prd_source: "docs/prds/auth-system.md"
generated: "2026-01-24T10:00:00Z"
generated_by: "acceptance-test-writer"

features:
  - id: F1
    name: "User Login"
    description: "Allow users to authenticate with email/password"
    acceptance_criteria:
      - AC-user-login
      - AC-invalid-credentials

  - id: F2
    name: "Password Reset"
    description: "Allow users to reset forgotten passwords"
    acceptance_criteria:
      - AC-password-reset-request
      - AC-password-reset-complete

# Optional: Map to task IDs for traceability
task_mapping:
  F1: ["TASK-101", "TASK-102"]
  F2: ["TASK-103"]
```

### 4.2 Acceptance Criterion Format

```yaml
# acceptance-tests/PRD-AUTH-001/AC-user-login.yaml
id: AC-user-login
feature: F1
title: "User can log in with valid credentials"
description: |
  A registered user should be able to log in using their email
  and password, and be redirected to the dashboard.

prd_reference: "PRD-AUTH-001, Section 3.1, Requirement R1"

# Test classification
validation_type: browser    # browser | api | hybrid
priority: critical          # critical | high | medium | low

# What must be true before test runs
preconditions:
  - description: "Test user exists in database"
    details: "Email: test@example.com, Password: TestPass123"
  - description: "User is logged out"
    details: "No active session cookies"

# Executable test steps
steps:
  - id: step-1
    action: navigate
    target: "/login"
    description: "Navigate to login page"

  - id: step-2
    action: assert_visible
    selector: "[data-testid='login-form']"
    description: "Login form is displayed"
    screenshot: true

  - id: step-3
    action: fill
    selector: "[data-testid='email-input']"
    value: "test@example.com"
    description: "Enter email address"

  - id: step-4
    action: fill
    selector: "[data-testid='password-input']"
    value: "TestPass123"
    description: "Enter password"

  - id: step-5
    action: click
    selector: "[data-testid='login-button']"
    description: "Click login button"

  - id: step-6
    action: wait_for_navigation
    timeout_ms: 5000
    description: "Wait for redirect"

  - id: step-7
    action: assert_url
    pattern: "/dashboard"
    description: "Verify redirected to dashboard"

  - id: step-8
    action: assert_visible
    selector: "[data-testid='user-greeting']"
    contains: "Welcome"
    description: "User greeting is visible"
    screenshot: true

# What success looks like
expected_outcome: |
  User is redirected to /dashboard and sees personalized greeting.
  Session is established (auth cookie present).

# How to recognize failure
failure_indicators:
  - "Error message displayed on login form"
  - "Remains on /login page after clicking submit"
  - "401 or 403 HTTP response"
  - "No session cookie created"

# Evidence to capture
evidence:
  - type: screenshot
    when: on_success
    filename: "login-success-dashboard.png"
    description: "Dashboard after successful login"
  - type: screenshot
    when: on_failure
    filename: "login-failure-state.png"
    description: "State of page when login failed"
```

### 4.3 API Test Format (validation_type: api)

```yaml
# acceptance-tests/PRD-AUTH-001/AC-api-authentication.yaml
id: AC-api-authentication
feature: F1
title: "API returns 401 for invalid token"
description: "Protected endpoints reject requests with invalid auth tokens"
prd_reference: "PRD-AUTH-001, Section 4.2"

validation_type: api
priority: critical

preconditions:
  - description: "API server is running"
    details: "Base URL: http://localhost:8000"

steps:
  - id: step-1
    action: api_request
    method: GET
    url: "/api/user/profile"
    headers:
      Authorization: "Bearer invalid-token-12345"
    description: "Request with invalid token"

  - id: step-2
    action: assert_status
    expected: 401
    description: "Should return 401 Unauthorized"

  - id: step-3
    action: assert_json
    path: "$.error"
    expected: "Unauthorized"
    description: "Error message in response body"

expected_outcome: |
  API returns HTTP 401 with JSON body containing error message.

evidence:
  - type: api_response
    filename: "api-401-response.json"
    capture: full  # full | body_only | headers_only
```

### 4.4 Validation Report Format

```markdown
# Acceptance Test Report: PRD-AUTH-001

**PRD**: User Authentication System
**Executed**: 2026-01-24T10:30:00Z
**Duration**: 47 seconds
**Environment**: Development (localhost)
**Triggered By**: validation-test-agent --mode=e2e --task_id=TASK-101

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ PASS | 4 | 80% |
| ❌ FAIL | 1 | 20% |
| ⏭️ SKIP | 0 | 0% |

**Overall Verdict**: CONDITIONAL PASS - Core functionality works, one criterion failing.

---

## Results by Criterion

### ✅ AC-user-login (PASS)
**Title**: User can log in with valid credentials
**Duration**: 8.2s
**Evidence**: <!-- Evidence: AC-user-login-success.png (login-success-dashboard.png) -->

**Verification**:
- ✓ Login form displayed
- ✓ Credentials accepted
- ✓ Redirected to /dashboard
- ✓ User greeting visible: "Welcome, Test User"

---

### ✅ AC-invalid-credentials (PASS)
**Title**: Invalid credentials show error message
**Duration**: 5.1s
**Evidence**: <!-- Evidence: AC-invalid-credentials.png (login-error.png) -->

**Verification**:
- ✓ Error message displayed: "Invalid email or password"
- ✓ Remained on /login page
- ✓ No session created

---

### ❌ AC-password-reset-complete (FAIL)
**Title**: User can set new password via reset link
**Duration**: 12.3s
**Evidence**: <!-- Evidence: AC-password-reset-complete-fail.png (reset-fail.png) -->

**Expected**:
```
User clicks reset link → enters new password → success message → can login with new password
```

**Actual**:
```
User clicks reset link → 404 Not Found
```

**Failure Analysis**:
- Step 3 failed: navigate to /reset-password/:token returned 404
- Route `/api/auth/reset-password/:token` does not exist or is not deployed

**Root Cause Hypothesis**:
The password reset completion endpoint was not implemented. The reset email sends correctly (AC-password-reset-request passes) but the link destination doesn't exist.

**Recommended Action**:
1. Implement `POST /api/auth/reset-password/:token` endpoint
2. Add route in frontend for `/reset-password/:token`
3. Re-run this acceptance test

---

## What Works
- User login flow (UI + session creation)
- Error handling for invalid credentials
- Password reset email sending
- Session management

## What Doesn't Work
- Password reset completion flow (missing endpoint)

## Blocking Issues
- [ ] AC-password-reset-complete must pass before task can be closed

## Recommendations
1. **Immediate**: Implement password reset endpoint (blocks task closure)
2. **Follow-up**: Add E2E test for session timeout (not in current PRD scope)

---

## Evidence Files
| File | Criterion | Description |
|------|-----------|-------------|
| AC-user-login-success.png | AC-user-login | Dashboard after login |
| AC-invalid-credentials.png | AC-invalid-credentials | Error message display |
| AC-password-reset-complete-fail.png | AC-password-reset-complete | 404 error page |

---

*Report generated by acceptance-test-runner skill*
```

---

## 5. Skill Specifications

### 5.1 acceptance-test-writer

**Purpose**: Generate executable acceptance test scripts from PRD documents.

**Trigger Phrases**:
- "generate acceptance tests"
- "create acceptance criteria tests"
- "write E2E test scripts from PRD"
- "set up acceptance testing for PRD-XXX"

**Input**:
- PRD document (markdown)
- PRD identifier (e.g., PRD-AUTH-001)

**Output**:
- `acceptance-tests/PRD-XXX/manifest.yaml`
- `acceptance-tests/PRD-XXX/AC-*.yaml` (one per criterion)

**Process**:
1. Read and parse PRD document
2. Extract features and acceptance criteria
3. For each acceptance criterion:
   - Determine validation type (browser/api/hybrid)
   - Generate executable steps
   - Define expected outcomes
   - Specify evidence requirements
4. Create manifest linking features to criteria
5. Write all YAML files

### 5.2 acceptance-test-runner

**Purpose**: Execute acceptance tests and generate evidence-based reports.

**Trigger Phrases**:
- "run acceptance tests"
- "validate against PRD"
- "test the outcomes"
- "execute E2E validation for PRD-XXX"

**Input**:
- `--prd=PRD-XXX` (required)
- `--criterion=AC-xxx` (optional, run specific criterion)
- `--task_id=TASK-123` (optional, for traceability)

**Output**:
- `acceptance-tests/PRD-XXX/runs/<timestamp>.md`
- `acceptance-tests/PRD-XXX/runs/evidence/*.png|.json`

**Process**:
1. Load manifest from `acceptance-tests/PRD-XXX/`
2. For each acceptance criterion:
   - Spawn Sonnet sub-agent with criterion YAML
   - Sub-agent executes steps using chrome-devtools MCP or curl
   - Sub-agent captures evidence
   - Sub-agent returns PASS/FAIL + evidence path + details
3. Aggregate all results
4. Generate comprehensive report
5. Return summary to caller

**Sub-Agent Model**: Sonnet (per criterion) - chosen for capability over speed.

---

## 6. Validation Agent Updates

The validation-test-agent becomes a router that invokes the appropriate skill based on mode:

```python
# Pseudo-code for validation-test-agent routing logic

def validate(mode: str, task_id: str, prd: str = None):
    if mode == "unit":
        # Run pytest/jest
        run_unit_tests(task_id)

    elif mode == "e2e":
        # Check if acceptance tests exist for this PRD
        if prd and Path(f"acceptance-tests/{prd}").exists():
            # Invoke acceptance-test-runner skill
            Skill("acceptance-test-runner", args=f"--prd={prd} --task_id={task_id}")
        else:
            # Fall back to generic E2E (browser loads, no crashes)
            # But WARN: "No acceptance tests found - running generic E2E only"
            run_generic_e2e(task_id)

    elif mode == "full":
        # Run both unit and e2e
        validate("unit", task_id, prd)
        validate("e2e", task_id, prd)
```

**Changes Required to validation-test-agent**:
1. Add `--prd` parameter to specify which PRD's acceptance tests to run
2. Add routing logic to invoke `acceptance-test-runner` skill
3. Update report aggregation to include acceptance test results
4. Add warning when no acceptance tests found for PRD

---

## 7. Workflow Integration

### 7.1 PRD Creation Phase

```
1. User creates PRD document
2. User runs: Skill("acceptance-test-writer", args="--prd=PRD-XXX --source=docs/prd.md")
3. Skill generates: acceptance-tests/PRD-XXX/
4. User reviews generated tests, adjusts if needed
5. Tests are committed to repo alongside PRD
```

### 7.2 Implementation Phase

```
1. Orchestrator assigns task to worker
2. Worker implements feature
3. Worker reports "done"
4. Orchestrator invokes validation-test-agent:

   Task(
       subagent_type="validation-test-agent",
       prompt="--mode=e2e --task_id=TASK-123 --prd=PRD-AUTH-001"
   )

5. Validation-agent routes to acceptance-test-runner
6. acceptance-test-runner executes all criteria
7. Report generated with PASS/FAIL + evidence
8. Orchestrator reviews report:
   - All PASS → close task
   - Any FAIL → feedback to worker with specific gaps
```

### 7.3 Failure Feedback Loop

When acceptance tests fail:

```
1. Validation report identifies:
   - Which criterion failed
   - What was expected
   - What actually happened
   - Root cause hypothesis
   - Recommended action

2. Orchestrator creates follow-up task:

   bd create --title="Fix: AC-password-reset-complete failing" \
             --description="Reset endpoint returns 404. See acceptance-tests/PRD-AUTH-001/runs/..." \
             --deps=TASK-123

3. Worker receives specific, actionable feedback
4. Worker fixes issue
5. Re-run validation
```

---

## 8. Success Criteria for This Solution

| Criterion | Measurement |
|-----------|-------------|
| Acceptance tests generated from PRD | Given a PRD, skill produces valid YAML test definitions |
| Tests are executable | Runner skill can execute generated tests without manual modification |
| Evidence captured | Screenshots/responses saved for each criterion |
| Reports are actionable | Failed tests include specific gap analysis and recommended actions |
| Integration with validation-test-agent | `--mode=e2e --prd=X` routes to acceptance-test-runner |
| Feedback loop works | Failed criteria result in new tasks with specific fix instructions |

---

## 9. Implementation Plan

| Phase | Task | Owner |
|-------|------|-------|
| 1 | Create `acceptance-test-writer` skill | skill-development |
| 2 | Create `acceptance-test-runner` skill | skill-development |
| 3 | Update validation-test-agent to route to skills | backend-solutions-engineer |
| 4 | Test with sample PRD | tdd-test-engineer |
| 5 | Document in CLAUDE.md | orchestrator |

---

## 10. Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Naming convention | `acceptance-test-writer`, `acceptance-test-runner` |
| Test format | YAML (easier for LLMs to parse) |
| Sub-agent model | Sonnet per criterion (capability over speed) |
| Skill vs agent | Skills, invoked by validation-test-agent |
| Modes | `--mode=unit` (mocks OK), `--mode=e2e` (real data, tests against acceptance criteria) |

---

**Document Status**: Ready for implementation
**Next Step**: Invoke skill-development to create both skills
