# PRD-UEA-001 Implementation Gaps Report

**Date**: 2026-02-22
**Branch**: `feature/ue-a-workflow-config-sla`
**Worktree**: `/Users/theb/Documents/Windsurf/zenagent2/zenagent/agencheck-ue-a-workflow/`
**Validated By**: S3 Guardian (live API + unit test + DB inspection)
**Docker Image Rebuilt**: Yes (app-server from feature branch with manual Dockerfile fix)

---

## Overall Verdict: REJECT (0.285 weighted score)

The implementation has a solid service layer (95/98 unit tests pass) and functioning check-types API, but critical schema-code mismatches prevent the core 3-tier resolution chain from working in production.

---

## Gap #1: Schema-Code Mismatch — `background_check_sequence` Missing Columns

**PRD Scenario**: `database_schema_migration_035` (Epic A1, weight 0.30)
**Severity**: CRITICAL — Blocks the entire 3-tier resolution chain

### What the PRD Requires

From `scenarios.feature` line 22:
> a background_check_sequence table exists with columns (id UUID PK, check_type_id INTEGER FK, **customer_id INTEGER FK**, **client_reference VARCHAR nullable**, **status VARCHAR**, **version INTEGER**, check_steps JSONB, notes TEXT, created_at, updated_at, created_by)

From `scenarios.feature` line 24:
> a partial unique index enforces one active sequence per (check_type_id, customer_id, client_reference) WHERE status='active'

### What Was Implemented

Migration 035 creates `background_check_sequence` with:
```
id            | integer (SERIAL PK)
check_type_id | integer (FK to check_types)
step_order    | integer
step_name     | character varying(100)
description   | text
delay_hours   | numeric(6,2)
max_attempts  | integer
is_active     | boolean
created_at    | timestamp with time zone
```

**Missing columns**: `customer_id`, `client_reference`, `status`, `version`, `check_steps` (JSONB), `notes`, `updated_at`, `created_by`

### What the Service Code Expects

`services/check_sequence_service.py` queries for:
- `customer_id` (used in 3-tier resolution: client > customer default > system fallback)
- `client_reference` (used for client-specific overrides)
- `version` (used for sequence versioning on PUT)
- `status` (used for active/archived state)

### Impact

- `GET /api/v1/check-sequence/resolve` returns **500 Internal Server Error**: `column "customer_id" does not exist`
- The entire 3-tier resolution chain (PRD scenario `sequence_resolution_logic`) is **non-functional**
- Sequence versioning (PRD scenario `sequence_versioning`) is impossible without `version` and `status` columns
- Multi-tenancy isolation (PRD scenario `security_and_multitenancy`) has no `customer_id` scoping

### Evidence

```
2026-02-22 00:31:08,024 - ERROR - resolve_check_sequence('work_history', customer_id=1) failed: column "customer_id" does not exist
```

### Fix Required

Migration 035 must be rewritten to match the PRD schema: add `customer_id INTEGER`, `client_reference VARCHAR`, `status VARCHAR DEFAULT 'active'`, `version INTEGER DEFAULT 1`, `check_steps JSONB`, `notes TEXT`, `updated_at TIMESTAMPTZ`, `created_by VARCHAR`. Add partial unique index `WHERE status='active'`. Restructure from per-step rows to per-sequence rows with JSONB `check_steps`.

---

## Gap #3: Audit Column Names Differ from PRD Specification

**PRD Scenario**: `audit_trail_in_background_tasks` (Epic A2, weight 0.20)
**Severity**: MODERATE — Columns exist but with wrong names; functionality partially works

### What the PRD Requires

From `scenarios.feature` lines 308-311:
> Then it includes **sequence_id** (UUID FK to background_check_sequence)
> And it includes **sequence_version** (integer snapshot)
> And it includes **attempt_timestamp** (TIMESTAMPTZ)

### What Was Implemented

Migration 035 adds to `background_tasks`:
- `check_type_config_id INTEGER` (instead of `sequence_id UUID`)
- `sla_due_at TIMESTAMPTZ` (not in PRD — extra column)
- `current_sequence_step INTEGER` (not in PRD — extra column)

Missing entirely: `sequence_id`, `sequence_version`, `attempt_timestamp`

### Impact

- Audit trail queries expecting `sequence_id` and `sequence_version` will fail
- No FK relationship from `background_tasks` to `background_check_sequence` (the PRD requires `sequence_id UUID FK`)
- Active cases cannot be pinned to a specific sequence version (breaks the versioning invariant: "active cases continue using their original sequence")
- The `check_type_config_id` column works for linking tasks to check types but doesn't provide per-version audit trail

### Evidence

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'background_tasks'
AND column_name IN ('sequence_id', 'sequence_version', 'attempt_timestamp');
-- Returns 0 rows

SELECT column_name FROM information_schema.columns
WHERE table_name = 'background_tasks'
AND column_name IN ('check_type_config_id', 'sla_due_at', 'current_sequence_step');
-- Returns 3 rows
```

### Fix Required

Add three columns to `background_tasks`: `sequence_id UUID REFERENCES background_check_sequence(id)`, `sequence_version INTEGER`, `attempt_timestamp TIMESTAMPTZ DEFAULT NOW()`. The existing `check_type_config_id`, `sla_due_at`, `current_sequence_step` can remain as supplementary operational columns.

---

## Gap #4: POST /verify Does Not Create a Case Record

**PRD Scenario**: `prefect_reads_db_config` (Epic A2, weight 0.20)
**Severity**: HIGH — Breaks the verification pipeline traceability

### What the PRD Requires

From `scenarios.feature` lines 256-257:
> When a new verification case is created
> Then resolve_check_sequence() is called with customer_id, check_type, and optional client_ref

The PRD flow is: `/verify` -> create case -> resolve sequence -> dispatch Prefect flow

### What Was Implemented

`POST /api/v1/verify` returns 201 with a `task_id` and creates a `background_tasks` row, but does NOT create a `cases` table entry.

### Evidence

```sql
-- After POST /verify returned 201 with task_id=16bcb3d4-f0dc-4230-9d50-cd5023e51847
SELECT id, customer_id, status FROM cases ORDER BY id DESC LIMIT 3;
-- Returns only pre-seeded test data (IDs 100-102), NO new case

SELECT id, task_type, status FROM background_tasks WHERE id = 23;
-- Returns: work_history | pending | check_type_config_id=1
```

### Impact

- No parent case entity linking multiple verification attempts together
- Cannot track the lifecycle of a verification request from submission to completion
- Dashboard/reporting cannot show "cases" — only individual background tasks
- The `cases` table exists (with pre-seeded data) but `/verify` never writes to it

### Fix Required

The `/verify` endpoint handler (`api/routers/work_history.py`) must create a `cases` record BEFORE creating the `background_tasks` entry. The case should link the customer, candidate, employer, and check type. The background_task should reference the case_id.

---

## Gap #5: POST /verify Does Not Trigger a Prefect Flow

**PRD Scenario**: `prefect_reads_db_config` (Epic A2, weight 0.20)
**Severity**: HIGH — The core async orchestration pipeline is disconnected

### What the PRD Requires

From `scenarios.feature` lines 253-258:
> Given a Prefect parent flow exists for check_work_history
> When a new verification case is created
> Then resolve_check_sequence() is called
> And the resolved sequence is used to determine subflow order

The expected flow: `/verify` -> create case -> resolve sequence -> **dispatch Prefect parent flow** -> subflows execute per sequence steps

### What Was Implemented

`POST /api/v1/verify` creates a `background_tasks` row with:
- `status = 'pending'`
- `check_type_config_id = 1` (links to check_types table)
- `sla_due_at` = NOW() + 48h (correctly computed)
- `current_sequence_step = 1`
- `prefect_flow_run_id = NULL` (no Prefect flow triggered)

Even with `PREFECT_DISPATCH_MODE=local_mock`, no flow run is created.

### Evidence

```sql
SELECT prefect_flow_run_id FROM background_tasks WHERE id = 23;
-- Returns: NULL

-- Server log shows no Prefect-related activity after /verify call
```

### Impact

- Verification requests are submitted but never processed
- The background task sits in `pending` status indefinitely
- No voice call is initiated, no employer is contacted
- The entire async pipeline (Prefect parent flow -> subflows -> retries) is disconnected from the API
- SLA tracking is set up (sla_due_at computed) but never acted upon

### Fix Required

The `/verify` endpoint must dispatch a Prefect flow run after creating the case and background task. The flow dispatch should:
1. Call `resolve_check_sequence()` to get the DB-backed config
2. Create a Prefect flow run with the resolved sequence as parameters
3. Store the `flow_run_id` in `background_tasks.prefect_flow_run_id`
4. Support `PREFECT_DISPATCH_MODE=local_mock` for testing (create a mock flow run)

---

## Bonus Finding: Dockerfile.app-server Missing `services/` COPY

**Severity**: CRITICAL for deployment — Container won't start without manual fix

The feature branch adds a new `services/` directory (`check_sequence_service.py`, `template_service.py`) but the Dockerfile does not include `COPY services/ ./services/`. The container crashes with:
```
ModuleNotFoundError: No module named 'services'
```

**Fix**: Add `COPY services/ ./services/` to `Dockerfile.app-server` after line 64.

**Note**: This was manually patched during validation to proceed with testing.

---

## Summary Table

| Gap | PRD Scenario | Severity | Pre-Fix Score | Post-Fix Score | Status |
|-----|-------------|----------|---------------|----------------|--------|
| #1 Schema-Code Mismatch | database_schema_migration_035 | CRITICAL | 0.4 | **0.75** | CLOSED (migration 036 added columns, resolve works) |
| #3 Audit Column Names | audit_trail_in_background_tasks | MODERATE | 0.3 | **0.50** | PARTIAL (columns exist via mig 037, but not populated — see Bug #1) |
| #4 No Case Creation | prefect_reads_db_config | HIGH | 0.4 | **0.90** | CLOSED (was already fixed on branch — case count increases) |
| #5 No Prefect Flow Trigger | prefect_reads_db_config | HIGH | 0.2 | **0.30** | PARTIAL (code written, blocked by Bug #1 in prefect_bridge.py) |
| Bonus: Dockerfile | (deployment) | CRITICAL | 0.0 | **1.00** | CLOSED (COPY services/ present, Docker rebuilds cleanly) |

---

## Post-Fix Validation (2026-02-22, commit e56e019d)

**Operator Work**: S3 operator spawned in tmux `s3-uea-gaps`, deployed 2 backend-solutions-engineer workers.
**Changes**: Migration 037 (audit columns), work_history.py (flow_run_id storage), Dockerfile fix confirmed.
**Docker Rebuilt**: Yes — `docker build -f Dockerfile.app-server` from UEA worktree, container restarted.

### E2E Test Results (Post-Rebuild)

| Test | Result | Evidence |
|------|--------|----------|
| GET /check-types | 200 OK | 2 types with metadata |
| GET /check-sequence/resolve?customer_id=1&check_type=work_history | 200 OK | resolution_chain: customer_default, 4 steps |
| POST /verify | 201 Created | case_id increments (28→30), flow_run_id field present but null |
| Migration 037 columns | Present | sequence_id, sequence_version, attempt_timestamp in background_tasks |
| Docker rebuild | Success | Container running from feature branch code |

### Bugs Found During Validation

**Bug #1: `sequence_id` type mismatch in prefect_bridge.py:477**
- Code: `sequence_id = str(customer_id) + "-" + check_type` → produces `"1-work_history"` (string)
- Column type: `background_tasks.sequence_id INTEGER` (FK to background_check_sequence)
- Error: `invalid input for query argument $4: '1-work_history' ('str' object cannot be interpreted as an integer)`
- Impact: Entire Prefect flow creation fails → flow_run_id always NULL → audit columns never populated
- Fix: Replace concatenation with actual `background_check_sequence.id` lookup from resolution result

### Guardian Weighted Score

| Feature | Weight | Score | Notes |
|---------|--------|-------|-------|
| A1 Config Backend | 0.30 | 0.75 | Schema works, resolve works, 3-tier resolution functional |
| A4 Frontend | 0.25 | 0.00 | Not tested (frontend not running) |
| A2 Prefect Integration | 0.20 | 0.35 | Case creation works, audit columns exist, but Bug #1 blocks Prefect |
| A3 Reminders | 0.15 | 0.40 | Templates exist, sla_due_at computed correctly |
| Cross-Cutting | 0.10 | 0.60 | Docker works, 95/98 tests pass, versioning partially works |

**Weighted Total: 0.415 — INVESTIGATE**

### Remaining Work

1. Fix Bug #1 (`prefect_bridge.py:477` sequence_id type) → unblocks Gap #5 + Gap #3
2. Launch frontend from feature branch → unblocks A4 scoring (0.25 weight)
3. Re-validate E2E after both fixes

## What Works Well

- **Check Types API** (GET /api/v1/check-types): 200 OK, returns 2 types with full metadata
- **Service Layer Code**: 48/48 unit tests pass — well-structured 3-tier resolution logic
- **SLA Computation**: `sla_due_at` correctly computed (48h for work_history)
- **Background Task Creation**: /verify creates tasks with config linking and SLA
- **Template Service**: `services/template_service.py` exists with load/render functions
- **3-Tier Resolution**: resolve endpoint returns correct chain with customer_default precedence
- **Case Creation**: POST /verify creates cases correctly (confirmed via DB count)
- **Audit Migration**: Migration 037 idempotent with proper FK constraints and partial index

## Recommended Next Steps

1. **Fix Bug #1** (prefect_bridge.py:477) — ~10 lines, unblocks Prefect pipeline
2. **Launch frontend** from feature branch — validate SLA config UI (A4, 0.25 weight)
3. **Re-run full E2E battery** after both fixes
4. **Target score**: 0.60+ (ACCEPT threshold)
