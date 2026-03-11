# Research: Backend SD case_reference vs case_id

**Node ID**: `research_backend_sd`
**PRD**: PRD-DASHBOARD-AUDIT-001
**Date**: 2026-03-11
**Status**: Research Complete

---

## Executive Summary

The PRD-DASHBOARD-AUDIT-001 solution design initially proposed adding a `case_reference` column (e.g., "AC-YYYYMM-NNNNN") to the `cases` table as a human-readable display alias. **This feature was later removed from the PRD** (version 0.5.0, 2026-03-09) in favor of using `cases.id` directly — the same stable reference already used in Prefect email templates.

**Key Finding**: The `case_reference` column is NOT implemented in the current codebase. The frontend incorrectly uses `task_id` (per-attempt UUID) instead of `case_id` (integer PK) for navigation.

---

## Current Database Schema State

### `cases` Table - Existing Columns

The `cases` table has these relevant columns (no `case_reference`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key — stable case identity |
| `customer_id` | INTEGER | Customer scope |
| `client_id` | INTEGER | Client scope (nullable) |
| `case_type` | VARCHAR | Classification (work_history, work_history_scheduling) |
| `status` | VARCHAR | Case lifecycle status |
| `title` | VARCHAR | Case title |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update |

**No `case_reference` column exists.** The previous solution design arbitrary was modified to use `cases.id` directly.

### `background_tasks` Table - Existing Columns

The `background_tasks` table has columns added by migrations 035/036/037:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `case_id` | INTEGER | FK to cases.id — links all retries to same case |
| `task_id` | UUID | Per-attempt UUID unique identifier |
| `action_type` | VARCHAR | Task type (call_attempt, email_outreach, etc.) |
| `status` | VARCHAR | Task status |
| `result_status` | VARCHAR | Result status (CallResultStatus enum) |
| `check_type_config_id` | INTEGER | FK to check_types for SLA config |
| `current_sequence_step` | INTEGER | 1-indexed step order |
| `sequence_id` | INTEGER | FK to background_check_sequence |
| `sequence_version` | INTEGER | Denormalized sequence version |
| `sla_due_at` | TIMESTAMPTZ | SLA deadline |
| `prefect_flow_run_id` | UUID/VARCHAR | Prefect flow correlation |
| `created_at` | TIMESTAMPTZ | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update |

**Key relationship**: `background_tasks.case_id` → `cases.id` links all task attempts to the same case.

---

## Database Migrations Referenced in SD

| Migration | Status | What it Added |
|-----------|--------|---------------|
| 035 (`check_sequence_sla.sql`) | Complete | `check_types`, `background_check_sequence` tables; `check_type_config_id`, `sla_due_at`, `current_sequence_step` on background_tasks |
| 036 (`customer_sla_resolution.sql`) | Complete | `customer_id`, `version`, `status` on background_check_sequence (3-tier resolution) |
| 037 (`background_tasks_audit_columns.sql`) | Complete | `sequence_id`, `sequence_version`, `attempt_timestamp` on background_tasks |
| 038 (`0XX_add_case_reference.sql`) | **DOES NOT EXIST** | Proposed `case_reference` column — **not implemented** |

**Clarification**: The PRD v0.4.0 and SD v0.4.0 referenced a migration `0XX_add_case_reference.sql`. This migration was **never created** — the PRD was updated to version 0.5.0 on 2026-03-09, explicitly removing `case_reference` in favor of using `cases.id` directly.

---

## Current Case Reference Pattern

### What Exists

| Component | Value | Use Case |
|-----------|-------|----------|
| `cases.id` | INTEGER | Stable internal identity (PK) |
| `background_tasks.case_id` | INTEGER | FK to cases.id |
| `background_tasks.task_id` | UUID | Per-attempt unique identifier |
| `cases.id` in Prefect email templates | Integer | External reference in emails |

### What the Frontend Currently Uses

**File**: `lib/api/work-history.ts` (line 368)

```typescript
// FROM (incorrect):
case_id: v.task_id  // Uses per-attempt UUID instead of stable case ID

// SHOULD BE:
case_id: v.case_id  // Uses stable cases.id
```

**The ` VerificationCaseSummary` interface is currently type-incorrect**:
```typescript
interface VerificationCaseSummary {
  case_id: string;        // Should be number (cases.id is INTEGER PK)
  candidate_name: string;
  employer: string;
  case_type: CaseType;
  status: CaseStatus;
  employment_status?: EmploymentStatus;
  created_at: string;
  completed_at?: string;
}
```

The frontend incorrectly maps `task_id` (UUID string) to `case_id` (should be integer).

---

## Solution Design Status

### PRD v0.5.0 (Current) - Changes from v0.4.0

**Removed Features**:
- `case_reference` column (TEXT, with PostgreSQL sequence)
- `next_case_reference()` PostgreSQL function
- CI script for reference generation

**Revised Approach**:
- Use `cases.id` directly for all case navigation
- `cases.id` is already used in Prefect email templates — frontend should match
- `background_tasks.case_id` FK already links retries to cases

**Critical Dependency Discovered**:
> **Sequence step progression is implemented (PRD-SEQ-PROGRESSION-001, merged)**. However, **the Prefect verification orchestrator does NOT create `background_tasks` rows per step**. Steps are resolved in-memory via `asyncio.sleep()`. A `background_tasks` row is only written on retryable call results or all-steps-exhausted.

**Without per-step task creation, there is NO audit trail data to display.** The timeline requires one `background_tasks` entry per sequence step.

---

## Current Database State Analysis

### Sequence Configuration

The `check_types` and `background_check_sequence` tables have been seeded:

| Check Type | Display Name | Default SLA Hours |
|------------|--------------|-------------------|
| work_history | Work History Verification | 48h |
| work_history_scheduling | Scheduled Work History Verification | 72h |

**Work History Sequence** (4 steps):
1. `initial_call` — First call attempt (0h delay, 1 max attempt)
2. `first_retry` — Second call after 2h (2h delay, 1 max attempt)
3. `second_retry` — Third call after 4h (4h delay, 1 max attempt)
4. `final_attempt` — Final call escalate to voicemail (24h delay, 1 max attempt)

### Current Task State

Based on migration 037 audit trail columns:
- `current_sequence_step` = 1 for all tasks (no retries triggered yet)
- `sequence_id` populated only for tasks created after ~March 1 (migration 037)
- Older tasks have `sequence_id = NULL`

---

## Fixes Required

### 1. Backend - API Response Fix

Update `api/routers/work_history.py` to return `case_id` correctly:

```python
# Current (incorrect):
{"case_id": str(task["task_id"]), ...}  # UUID

# Required:
{"case_id": case["id"], ...}  # Integer
```

### 2. Frontend - API Client Fix

**File**: `lib/api/work-history.ts:368`

```typescript
// FROM:
case_id: v.task_id

// TO:
case_id: v.case_id
```

### 3. Timeline Display Requirements

**Critical**: The Prefect verification orchestrator must be modified to INSERT a `background_tasks` row at the START of each sequence step (before dispatching voice/email/SMS). Without this, the timeline has no data to display.

---

## Research Validation

| Question | Research Status | Finding |
|----------|-----------------|---------|
| PostgreSQL sequence for case_reference | Resolved in PRD v0.5.0 | Not needed — use cases.id |
| Frontend timeline component | Resolved | Custom Tailwind vertical timeline (shadcn has none) |
| React Query polling pattern | Resolved | Use callback pattern: `refetchInterval: (q) => isTerminal(q.state.data?.status) ? false : 5000` |
| Denormalized step_order on background_tasks | Resolved | Already exists (`current_sequence_step`) |
| 3-tier SLA resolution | Resolved | Implemented (migration 036: client → customer → system) |

---

## Conclusion

### What Was Found

1. **`case_reference` is NOT implemented** — PRD v0.5.0 (2026-03-09) removed this requirement in favor of using `cases.id` directly.

2. **The correct stable reference already exists** — `cases.id` (INTEGER PK) with `background_tasks.case_id` (FK) forming the one-to-many relationship for retry chains.

3. **The frontend has two bugs**:
   - `work-history.ts` line 368 maps `task_id` (UUID) to `case_id` (should be integer)
   - The `VerificationCaseSummary` interface has incorrect type (`string` instead of `number`)

4. **Timeline data is missing** — Prefect orchestrator doesn't create per-step `background_tasks` rows, only writes on retry or completion. This is the PREREQUISITE for displaying the audit trail.

### What Was NOT Found

- `database/migrations/0XX_add_case_reference.sql` — This file does not exist (PRD v0.5.0 removed the requirement)
- `cases.case_reference` column — Does not exist in current schema

### Next Steps

1. Fix frontend to use `cases.id` instead of `task_id`
2. Update API response to include correct `case_id`
3. **Critical**: Modify Prefect orchestrator to create per-step `background_tasks` rows for timeline data

---

## Signal File Path

**Signal**: `/Users/theb/Documents/Windsurf/claude-harness-setup/.claude/attractor/pipelines/signals/PRD-DASHBOARD-AUDIT-001-impl-research/research_backend_sd.json`
**Document**: `/Users/theb/Documents/Windsurf/claude-harness-setup/.claude/attractor/pipelines/evidence/PRD-DASHBOARD-AUDIT-001-impl-research/research_backend_sd.md`
