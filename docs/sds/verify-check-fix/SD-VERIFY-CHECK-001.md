---
title: "Fix /verify-check Status Query Bug"
description: "Investigation of /verify-check status handling - research confirms current implementation is correct but identifies defensive improvements"
version: "1.1.0"
last-updated: 2026-03-21
status: active
type: sd
grade: authoritative
prd_ref: PRD-VERIFY-CHECK-001
research_ref: documentation/evidence/PRD-VERIFY-CHECK-001/status_mapping_research.md
---

# SD-VERIFY-CHECK-001: Fix /verify-check Status Query Bug

## Problem Statement

The `/verify-check/[taskId]` page was suspected to incorrectly use `background_tasks.status` to determine completion instead of `cases.status`. This assumption was based on observed behavior where newly submitted cases showed "already completed" despite `cases.status = 'pending'`.

## Research Findings

### Implementation Verification (2026-03-21)

Code analysis reveals the current implementation is **already correct**:

**Frontend** (`agencheck-support-frontend/app/verify-check/[task_id]/page.tsx` lines 153-158):
```typescript
const TERMINAL_CASE_STATUSES = ['completed', 'verified', 'cancelled', 'requires_review', 'on_hold'];
if (TERMINAL_CASE_STATUSES.includes(data.case_status)) {
    setIsAlreadyCompleted(true);
    setIsConnecting(false);
    return;
}
```

**Backend** (`agencheck-support-agent/api/routers/live_form.py` lines 311, 420):
```python
case_row = await conn.fetchrow(
    """
    SELECT
        c.id                    AS case_id,
        c.status                AS case_status,
        ...
    FROM cases c
    ...
    """
)
# Response includes case_status
case_status=case_row["case_status"],
```

### Data Flow Confirmed

```
1. Frontend calls GET /api/live-form-filler/init/{task_id}
2. Backend queries:
   a. background_tasks (to get task info and case_id)
   b. cases (to get case_status and verification_metadata)
3. Backend returns response with:
   - task_status (from background_tasks.status)
   - case_status (from cases.status)  ← This is what frontend uses
4. Frontend checks case_status against TERMINAL_CASE_STATUSES
```

### Conclusion

The frontend correctly uses `case_status` (from `cases.status`) to determine if a verification is complete. The `TERMINAL_CASE_STATUSES` constant correctly identifies terminal states.

## Status Mapping

### background_tasks.status Values

**Source**: `database/schema/01_foundation_schema_v1.4.1.sql` + Migration 029

| Status | Meaning | Terminal? |
|--------|---------|-----------|
| `pending` | Task created, awaiting scheduler pickup | No |
| `started` | Task dispatched, Prefect flow initiated | No |
| `processing` | Flow actively running | No |
| `completed` | Task action completed (email sent, call made) | Yes |
| `failed` | Task action failed | Yes |
| `timeout` | Task exceeded SLA | Yes |
| `cancelled` | Task manually cancelled | Yes |

**Key Insight**: `background_tasks.status = 'completed'` means the **task** completed successfully (e.g., an email was sent). It does NOT mean the **case** verification is complete.

### cases.status Values

**Source**: `database/schema/01_foundation_schema_v1.4.1.sql` line 158

| Status | Meaning | Terminal? |
|--------|---------|-----------|
| `pending` | Case created, awaiting verification | No |
| `in_progress` | Verification process active | No |
| `completed` | Verification finished with outcome | Yes |
| `cancelled` | Manually cancelled | Yes |
| `on_hold` | Paused for external reason | Yes |
| `requires_review` | Needs human review | Yes |

**Note**: `verified` is mentioned in SD but not in the database constraint. This may be an outcome stored in `verification_results.employment_status` rather than `cases.status`.

## Potential Root Causes (If Issue Persists)

If the "already completed" behavior still occurs despite correct code:

1. **Data Inconsistency**: The `case_status` may not be returned correctly from the API for specific cases
2. **Caching**: Browser or CDN caching could return stale status values
3. **Different Code Path**: There may be another route or component that bypasses the init endpoint
4. **API Route Mismatch**: The frontend may be calling a different endpoint than expected

## Required Investigation

### 1. Database Verification

Query case 90 to confirm actual status values:

```sql
SELECT
    c.id AS case_id,
    c.status AS case_status,
    bt.id AS task_id,
    bt.status AS task_status,
    bt.task_id AS task_uuid
FROM cases c
LEFT JOIN background_tasks bt ON bt.case_id = c.id
WHERE c.id = 90;
```

### 2. API Testing

Test the init endpoint directly:

```bash
curl -X GET "http://localhost:8001/api/live-form-filler/init/{task_id}" \
  -H "Authorization: Bearer {token}"
```

Verify the response includes `case_status` and that it matches the database.

### 3. Frontend Debugging

Add logging to verify the `case_status` value received:

```typescript
console.log('[verify-check] case_status:', data.case_status);
console.log('[verify-check] task_status:', data.task_status);
console.log('[verify-check] is terminal?', TERMINAL_CASE_STATUSES.includes(data.case_status));
```

## Defensive Improvements

Regardless of whether the issue is confirmed, these improvements should be implemented:

### 1. API Documentation Fix

**File**: `agencheck-support-agent/api/routers/live_form.py` line 73-76

The `case_status` description mentions "open" which is not a valid status:

```python
case_status: Optional[str] = Field(
    None,
    description="Current status of the verification case (pending|in_progress|completed|cancelled|on_hold|requires_review)"
)
```

### 2. Add Debug Logging

**File**: `agencheck-support-frontend/app/verify-check/[task_id]/page.tsx`

Add explicit logging for troubleshooting:

```typescript
useEffect(() => {
    if (data) {
        console.log('[verify-check] Status received:', {
            case_status: data.case_status,
            task_status: data.task_status,
            isTerminal: TERMINAL_CASE_STATUSES.includes(data.case_status)
        });
    }
}, [data]);
```

### 3. Add Unit Tests

Create unit tests for the terminal status check logic to prevent regression:

```typescript
// __tests__/verify-check/status-logic.test.ts
describe('Terminal Status Check', () => {
    const TERMINAL_CASE_STATUSES = ['completed', 'verified', 'cancelled', 'requires_review', 'on_hold'];

    it('should identify pending as non-terminal', () => {
        expect(TERMINAL_CASE_STATUSES.includes('pending')).toBe(false);
    });

    it('should identify in_progress as non-terminal', () => {
        expect(TERMINAL_CASE_STATUSES.includes('in_progress')).toBe(false);
    });

    it('should identify completed as terminal', () => {
        expect(TERMINAL_CASE_STATUSES.includes('completed')).toBe(true);
    });

    it('should identify cancelled as terminal', () => {
        expect(TERMINAL_CASE_STATUSES.includes('cancelled')).toBe(true);
    });
});
```

## Acceptance Criteria

1. ✅ Research confirms current implementation correctly uses `case_status` from `cases.status`
2. ✅ Research confirms `TERMINAL_CASE_STATUSES` constant correctly identifies terminal states
3. ⬜ Database query confirms case 90 has `cases.status = 'pending'`
4. ⬜ API test confirms `/api/live-form-filler/init/{task_id}` returns correct `case_status`
5. ⬜ Debug logging added to frontend to track status values
6. ⬜ Unit tests added for terminal status check logic
7. ⬜ API documentation updated to remove invalid "open" status

## Implementation Priority

**P1 — High**: While the code appears correct, defensive improvements and verification are needed to ensure reliability. This supports E2E testing of PRD-CASE-DATAFLOW-001.

## Testing

### Database Verification

```bash
# Connect to local database
psql -h localhost -p 5434 -U agencheck -d agencheck

# Query case 90 status
SELECT c.id, c.status, bt.status AS task_status
FROM cases c
LEFT JOIN background_tasks bt ON bt.case_id = c.id
WHERE c.id = 90;
```

### API Testing

```bash
# Test init endpoint with task_id from case 90
curl -X GET "http://localhost:8001/api/live-form-filler/init/{task_id}"
```

### Frontend Testing

1. Navigate to `/verify-check/{task_id}` for a case with `status='pending'` and `background_tasks.status='completed'`
2. Verify the verification form is displayed (not "already completed")
3. Check browser console for debug logs showing status values

## Files Analyzed

| File | Purpose |
|------|---------|
| `agencheck-support-frontend/app/verify-check/[task_id]/page.tsx` | Frontend verification page |
| `agencheck-support-agent/api/routers/live_form.py` | Backend init API endpoint |
| `agencheck-support-agent/models/cases.py` | Case status enum definition |
| `database/schema/01_foundation_schema_v1.4.1.sql` | Database schema definitions |
| `database/migrations/029_add_pending_to_task_status.sql` | Migration adding 'pending' to task status |
