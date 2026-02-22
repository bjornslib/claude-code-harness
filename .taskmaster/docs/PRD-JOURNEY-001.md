---
prd_id: PRD-JOURNEY-001
title: "Business Journey Tests — End-to-End Causal Chain Validation"
product: "Claude Harness Setup"
version: "1.0"
status: draft
created: "2026-02-22"
author: "System 3 Orchestrator"
priority: P1
---

# PRD-JOURNEY-001: Business Journey Tests

## The Problem

The existing acceptance tests validate features **in isolation**. Feature F1.1 passes. Feature F2.3 passes. Every epic closes. And yet the business outcome isn't achieved — because the *chain* broke somewhere.

The scenario the user cares about:
> A form is submitted in the browser → the API writes the record → that write triggers a Prefect workflow → the workflow completes → the downstream state reflects the outcome.

If the trigger never fires, or the workflow silently errors, or the downstream state is wrong — the per-epic tests don't catch it. Each layer passed; the chain failed.

**The gap**: there is no test that follows the full causal chain from user action to business outcome.

---

## What Journey Tests Are

A **Journey Test** is a single Gherkin scenario written from the perspective of a business outcome. It:

1. **Triggers** the initial user or system action (browser click, API call, hook fire)
2. **Traverses** all layers involved: browser → API → DB → downstream process
3. **Asserts** the final business outcome — not just that data exists, but that the *right* thing happened as a result
4. **Polls** for async effects (Prefect runs, queue jobs, cron triggers) with a timeout

Journey tests are named `J{N}` and tagged `@journey @prd-{ID}`. They are generated from the PRD's **business objectives** (the Goals section), not from the feature list.

### Example

For a PRD whose goal is "University contact submitted by employer triggers a validation workflow":

```gherkin
@journey @prd-UEA-001 @J1
Scenario J1: Employer contact submission triggers full validation chain
  Given I am logged in as an employer
  When I submit a university contact with email "hr@university.edu"
  Then the API returns 201 with a contact_id
  And within 10 seconds the database has a contact record with status="queued"
  And within 60 seconds a Prefect flow run exists for that contact_id with state="Completed"
  And the contact record in the database has status="validated"
  And the employer dashboard shows the contact as "Verified"
```

This single scenario crosses: browser session → POST /api/contacts → DB write → Prefect trigger → DB update → UI read.

### What Makes a Good Business Outcome Assertion

| Weak | Strong |
|------|--------|
| `DB row exists` | `DB row has status="validated" AND verified_at IS NOT NULL` |
| `Workflow was created` | `Workflow completed with state="Completed" AND output contains expected fields` |
| `Frontend shows data` | `Frontend shows "Verified" badge for the specific contact_id we submitted` |
| `No error in logs` | `The specific downstream record reflects the correct state change` |

Strong assertions verify **causal completion**: the outcome that the PRD promised is demonstrably achieved.

---

## Architecture

```
acceptance-tests/
└── PRD-UEA-001/
    ├── manifest.yaml          # [existing] per-feature weights
    ├── scenarios.feature      # [existing] per-feature Gherkin (unchanged)
    └── journeys/              # [NEW] business journey tests
        ├── J1-contact-validation-chain.feature
        ├── J2-employer-dashboard-reflects-outcome.feature
        └── runner_config.yaml  # timeouts, polling intervals, service URLs
```

Journey tests live alongside per-feature tests but in a `journeys/` subdirectory. They are a separate, additive layer — the per-feature tests are not modified.

### Two-Layer Validation Model

```
Layer 1 (existing): Per-feature Gherkin
  → Validates: "Does feature X work in isolation?"
  → Scored by: s3-guardian LLM evaluation
  → Generated from: PRD feature list

Layer 2 (new): Journey Tests
  → Validates: "Does the full causal chain produce the business outcome?"
  → Scored by: PASS/FAIL from actual execution
  → Generated from: PRD business objectives
```

Both layers run. A PRD is only considered DONE when Layer 1 passes AND at least one Layer 2 journey test passes for each critical business objective.

---

## Epics

### Epic 1: Journey Test Format and Writer

**Goal**: Define the journey test format and extend `acceptance-test-writer` to generate journey tests from a PRD's business objectives section.

**F1.1 — Journey Test Format Specification**

Define the standard:
- File naming: `journeys/J{N}-{slug}.feature`
- Required tags: `@journey @prd-{ID} @J{N}`
- Optional tags: `@async` (has polling steps), `@browser` (requires Chrome), `@smoke` (fast, no browser)
- `runner_config.yaml` format: `services`, `poll_interval_seconds`, `max_poll_seconds`, `base_url`

**F1.2 — Journey Writer Extension**

Extend `acceptance-test-writer` with a `--mode=journey` flag:
- Read PRD's **Goals** and **Acceptance Criteria** sections (not feature list)
- Each business objective → one `J{N}` scenario
- Identify which layers each objective crosses (browser/API/DB/queue) from context
- Generate step sketches as Gherkin comments where exact URLs/selectors are unknown (to be filled by orchestrator)
- Tag with `@async` if any step involves a background process (Prefect, Celery, cron)

Example output:
```gherkin
# Generated from PRD-UEA-001 Goal 1: "Employer contact submission triggers validation"
@journey @prd-UEA-001 @J1 @async @browser
Scenario J1: Complete employer contact validation chain
  # Browser layer
  Given I am logged in as employer with credentials from env
  When I submit a new contact via POST /api/v1/contacts
  # API layer
  Then the API returns HTTP 201
  And the response body contains a contact_id
  # DB layer
  And the contacts table has a row with that contact_id and status="queued"
  # Downstream layer (async — polls with timeout from runner_config.yaml)
  And eventually the Prefect flow for this contact completes successfully
  And the contacts table row has status="validated"
  # Business outcome assertion
  And the employer dashboard API returns this contact as verified
```

**Acceptance Criteria**:
- `Skill("acceptance-test-writer", args="--source=PRD-XXX.md --mode=journey")` produces `journeys/` directory with one `.feature` per business objective
- Each generated scenario has `@journey @prd-{ID} @J{N}` tags
- `runner_config.yaml` is generated with sensible defaults (poll_interval: 5s, max_poll: 120s)

---

### Epic 2: Journey Test Runner

**Goal**: Build a runner that can execute journey tests — orchestrating browser, API, DB, and async downstream assertions in sequence, with polling for async effects.

**F2.1 — Chain Orchestration**

The runner executes steps in order and passes artifacts between them:
- Step output (e.g., `contact_id` from API response) is available to subsequent steps
- Each step names what it extracts: `contact_id = response.json()["id"]`
- Later steps reference it: `poll_until(db_query("SELECT status FROM contacts WHERE id = $contact_id"))`

**F2.2 — Async Polling**

For steps tagged `@async` or steps beginning with "And eventually":
- Poll a specified condition every `poll_interval_seconds`
- Time out after `max_poll_seconds`
- Return PASS if condition met before timeout, FAIL with `"Timed out after {N}s waiting for {condition}"` if not

Polling targets:
- **Prefect**: poll `GET /api/v1/flow_runs?flow_name={name}&state=Completed`
- **Celery**: poll `celery inspect query` or result backend
- **DB column change**: `SELECT {column} FROM {table} WHERE {id} = $artifact` until `{column} = {expected}`
- **API endpoint**: poll until response matches expected

**F2.3 — Evidence Collection**

The runner produces a `journey-evidence.json` per PRD:
```json
{
  "prd_id": "PRD-UEA-001",
  "run_at": "2026-02-22T14:30:00Z",
  "journeys": [
    {
      "id": "J1",
      "title": "Complete employer contact validation chain",
      "status": "PASS",
      "steps": [
        {"step": "API returns 201", "status": "PASS", "artifact": {"contact_id": "uuid-123"}},
        {"step": "DB row status=queued", "status": "PASS", "latency_ms": 45},
        {"step": "Prefect flow Completed", "status": "PASS", "wait_seconds": 34},
        {"step": "DB row status=validated", "status": "PASS"},
        {"step": "Dashboard API returns verified", "status": "PASS"}
      ]
    }
  ],
  "verdict": "PASS",
  "business_objectives_met": 2,
  "business_objectives_total": 2
}
```

**F2.4 — Fallback: Structural-Only Mode**

When services aren't running (e.g., during harness-level validation), run in `--mode=structural`: verify that the journey `.feature` files and `runner_config.yaml` exist and are well-formed. No actual execution. Returns `STRUCTURAL_PASS` instead of `PASS/FAIL`.

**Acceptance Criteria**:
- Runner executes `journeys/J1-*.feature` and returns `journey-evidence.json`
- Async polling steps wait up to `max_poll_seconds` and fail clearly with elapsed time
- Step artifacts (IDs, tokens, etc.) flow correctly from earlier steps to later steps
- Structural-only mode works without any running services

---

### Epic 3: s3-Orchestrator Integration

**Goal**: Wire journey tests into the orchestrator workflow so business outcomes are verified before `impl_complete`, not just per-feature completion.

**F3.1 — Journey Smoke Gate**

After workers complete ALL epics in a PRD (not after each epic individually):
1. Run `Skill("acceptance-test-runner", args="--prd={PRD_ID} --mode=journey")`
2. If any `@J{N}` scenario FAILs: do NOT mark uber-epic `impl_complete`
3. Create a new task targeting the specific failing journey step (not just "fix tests")
4. Failing step artifacts identify which layer broke (API? DB? Prefect trigger?)

**F3.2 — Failure Attribution**

When a journey test fails, the failure step pinpoints the broken layer:
- `"Prefect flow Completed" FAIL after 120s` → worker who owns the Prefect trigger gets the task
- `"DB row status=queued" FAIL` → backend worker gets the task
- `"API returns 201" FAIL` → API worker gets the task

The orchestrator uses the `step.status = FAIL` entry in `journey-evidence.json` to route the fix task to the correct worker.

**F3.3 — Orchestrator Skill Documentation**

Update `orchestrator-multiagent/SKILL.md` and `WORKFLOWS.md`:
- Add Phase 2 step: "After all epics complete → run journey smoke gate"
- Add "Journey Test Failure Attribution" section

**Acceptance Criteria**:
- Orchestrator workflow in `SKILL.md` includes journey smoke gate after all-epic completion
- Uber-epic `impl_complete` is only set when all `@journey` scenarios pass (or `STRUCTURAL_PASS` for non-executable PRDs)
- Failure attribution correctly routes fix tasks to the worker owning the broken layer

---

### Epic 4: s3-Guardian Integration

**Goal**: Enable the guardian to independently run journey tests as the authoritative business outcome validation — the final gate before a PRD is considered done.

**F4.1 — Guardian Journey Execution**

The guardian runs journey tests as part of Phase 2 validation, AFTER per-feature scoring:
1. Per-feature Gherkin scoring (existing) → gradient score per feature
2. Journey test execution (new) → `PASS/FAIL` per business objective
3. Final verdict: weighted combination of feature score AND journey outcomes

**F4.2 — Journey Override Rule**

If ANY journey test FAILs, the PRD is `REJECT` regardless of feature scores:
- Feature score: 0.92 → normally `ACCEPT`
- Journey J1 FAILs (Prefect never triggered) → `REJECT` with reason
- Rationale: a PRD cannot be done if the business outcome isn't achieved, even if all individual features scored well

**F4.3 — Journey Tests Remain Blind**

Journey test `.feature` files live in `acceptance-tests/PRD-XXX/journeys/` in the harness repo. Operators never see them. The guardian writes them from the PRD's business objectives before any implementation starts — same blind guarantee as per-feature tests.

**F4.4 — Guardian Skill Documentation**

Update `s3-guardian/SKILL.md`:
- Phase 1: "Create journey tests from PRD business objectives" (add as Step 2 after feature scenarios)
- Phase 2: "Execute journey tests → J-verdicts" (add after per-feature scoring)
- Final verdict: "Feature score AND J-verdicts must both pass for ACCEPT"

**Acceptance Criteria**:
- Guardian `SKILL.md` explicitly generates journey tests in Phase 1
- Guardian executes journey tests in Phase 2
- A failing J-verdict results in `REJECT` regardless of feature score
- Journey `.feature` files are generated before implementation starts (not retroactively)
- `journey-evidence.json` is included in the guardian's closure evidence package

---

## What Changes vs. Current System

| Aspect | Current | After This PRD |
|--------|---------|----------------|
| Test scope | Per-feature (isolated) | Per-feature + full causal chain |
| What passes PRD | All features score above threshold | All features + all J-scenarios pass |
| When generated | Per-feature, before implementation | J-tests also generated, from business objectives |
| What guardian validates | Feature completeness | Feature completeness + business outcomes |
| Orchestrator gate | Per-epic impl_complete | All-epic journey smoke before uber-epic impl_complete |
| Async effects | Not tested | Polled until complete or timeout |

---

## Implementation Dependencies

```
E1 (Format + Writer) ────────────────────────┐
                                               ▼
                                          E2 (Runner)
                                          /          \
                                    E3 (Orch)    E4 (Guardian)
```

---

## Acceptance Criteria (PRD Level)

**AC1 — Journey Generation**: `Skill("acceptance-test-writer", args="--source=PRD-XXX.md --mode=journey")` produces a `journeys/` directory with one scenario per business objective.

**AC2 — Journey Execution**: `Skill("acceptance-test-runner", args="--prd=PRD-XXX --mode=journey")` runs the chain and emits `journey-evidence.json` with per-step status and artifacts.

**AC3 — Async Polling**: Journey tests with `@async` scenarios correctly poll downstream systems (Prefect, DB, etc.) up to configured timeout, with clear FAIL messages when timed out.

**AC4 — Override Rule**: A failing journey verdict results in PRD `REJECT` even if all per-feature scores exceed threshold.

**AC5 — Orchestrator Gate**: Journey smoke gate runs after all-epic completion, before uber-epic `impl_complete`. Failure attribution routes fix tasks to the correct worker by layer.

**AC6 — Guardian Blind**: Journey `.feature` files are created before implementation and stored only in the harness repo. Operators never have access to them.

**AC7 — Layer Coverage**: For a PRD with `@browser`, `@async`, and DB assertions, the runner can execute all three layers in sequence with artifact passing between steps.

---

## Estimated Scope

| Epic | Complexity | Estimated Sessions |
|------|-----------|-------------------|
| E1: Format + Writer | Medium | 1 (1 worker) |
| E2: Runner | High | 2 (1 backend worker, 1 tester) |
| E3: Orchestrator Integration | Small | 1 (1 worker) |
| E4: Guardian Integration | Small | 1 (1 worker) |
| **Total** | | **5 orchestrator sessions** |
