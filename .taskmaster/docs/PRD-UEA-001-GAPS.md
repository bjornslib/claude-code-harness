# PRD-UEA-001-GAPS: SLA Frontend Fix & Backend Wiring

**Parent PRD**: PRD-UEA-001 (Uber-Epic A: Workflow Config & SLA Engine)
**Type**: Gap Fix PRD — addresses Guardian-identified frontend failures
**Priority**: P0 — blocks PRD-UEA-001 acceptance (J1 journey FAIL)
**Implementation Repo**: `/Users/theb/Documents/Windsurf/zenagent2/zenagent/agencheck-ue-a-workflow/agencheck/`

---

## Problem Statement

Guardian validation of PRD-UEA-001 scored 0.735 per-epic weighted, but **J1 journey test FAILED** due to 3 critical frontend issues. The backend is solid (J2 PASS, 0.90 average across 12 scenarios). The frontend renders but cannot complete any user workflow because:

1. API endpoint paths in the frontend do not match the backend routes
2. The fallback URL port is wrong (8000 vs 8001)
3. When API calls fail, the frontend silently falls back to localStorage cache/mock data
4. Users cannot edit SLA steps (overlay click handler may be broken due to data shape mismatch)
5. Drag-and-drop channel reordering is not visually accessible

---

## Root Cause Analysis

### The Data Flow Problem

```
Frontend expects:  GET /api/v1/check-types/by-name/:name/sequence
Backend provides:  GET /api/v1/check-sequence/resolve?customer_id=X&check_type=Y

Frontend expects:  PATCH /api/v1/check-steps/:step_id
Backend provides:  (needs verification — may not exist)

Frontend fallback: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
Actual backend:    http://localhost:8001
```

When the frontend's `fetchResolvedSequences()` call fails (wrong endpoint), it falls back to mock data via `resolvedSequencesToSLAConfigurationV32()` error handler. This mock data populates localStorage (`agencheck-sla-draft-v32`) and Zustand store. The page renders from cached data, showing "Cached data" badge.

Because the data comes from mock/cache rather than a live API response, the `backendMeta` object (which stores real check_type IDs and step IDs) is empty. Without `backendMeta`, the EditStepModal's save function `saveToBackendV32()` has no real step IDs to PATCH.

---

## Acceptance Criteria

### Epic G1: API Endpoint Alignment (Weight: 0.40)

**G1.1**: Update `lib/api/check-sequence.ts` to use correct backend endpoint paths:
- `fetchResolvedSequences()` must call `GET /api/v1/check-sequence/resolve?customer_id={id}&check_type={name}` (not `/check-types/by-name/:name/sequence`)
- Fallback URL must be `http://localhost:8001` (not 8000)
- Use `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'` consistently

**G1.2**: Verify and align write endpoints:
- If backend has `PATCH /api/v1/check-steps/{step_id}` → use it
- If backend has `PUT /api/v1/check-sequences/{sequence_id}` → use it
- If endpoints are missing → create them in the backend router

**G1.3**: Adapter function `resolvedSequencesToSLAConfigurationV32()` must correctly map the backend's actual response schema to the frontend's V3.2 data shape. The backend returns:
```json
{
  "check_type": "work_history",
  "sequence_id": 1,
  "resolution_chain": "customer_default",
  "steps": [
    {"step_order": 1, "step_name": "initial_outreach", "channel": "voice", ...},
    {"step_order": 2, "step_name": "follow_up_1", "channel": "email", ...}
  ]
}
```

**G1.4**: `backendMeta` must be populated with real IDs from API response so write operations work.

### Epic G2: EditStepModal Overlay Fix (Weight: 0.30)

**G2.1**: Clicking a SequenceCard (e.g., "Voice Call (Primary)") MUST open the EditStepModal overlay.
- The `onClick` handler exists in `SequenceCard.tsx:194` — verify it fires
- If data shape mismatch prevents rendering, fix the adapter to produce correct step objects

**G2.2**: EditStepModal save MUST persist to backend:
- `saveToBackendV32()` must use real `step_id` from `backendMeta`
- Success toast must show after save
- Modal must close after successful save
- Verify the saved value is reflected in the next GET call

**G2.3**: Channel dropdown must show all 5 options: Voice, Email, SMS, WhatsApp, Manual Review.

### Epic G3: Drag-and-Drop Reordering (Weight: 0.20)

**G3.1**: Sequence cards within a check type section must be draggable to reorder.
- @dnd-kit is already installed and wired (`SequenceCardRow.tsx`)
- Grip icon must be visible on hover
- Drop must update step_order in both Zustand store and backend

**G3.2**: Reordering must persist:
- After drag-drop, call backend to update step_order
- Reload page → order must match what was set

### Epic G4: Data Source Integrity (Weight: 0.10)

**G4.1**: Remove or disable localStorage fallback for production reads. The page MUST show data from the live backend API.
- If API is unreachable, show an error state (not cached data)
- localStorage should only be used for unsaved draft state (isDirty=true edits not yet saved)

**G4.2**: The "Cached data" badge should NOT appear when the API is healthy.

---

## Technical Context

### Frontend Files to Modify

| File | Purpose |
|------|---------|
| `lib/api/check-sequence.ts` | API client — fix endpoints, fallback URL |
| `lib/adapters/checkSequenceToSLA.ts` | Adapter — map backend response to V3.2 |
| `stores/slices/slaConfigurationSliceV32.ts` | Zustand slice — fix loadFromAPIV32, backendMeta |
| `app/check-sla-configuration/_components/SequenceCard.tsx` | Click handler for overlay |
| `app/check-sla-configuration/_components/EditStepModal.tsx` | Modal save logic |
| `app/check-sla-configuration/_components/SequenceCardRow.tsx` | DnD rendering |
| `stores/slaConfigurationStoreV32.ts` | Store — localStorage persistence config |

### Backend Files (if write endpoints needed)

| File | Purpose |
|------|---------|
| `api/routers/check_sequences.py` | Check sequence CRUD routes |
| `api/routers/check_steps.py` | Check step CRUD routes (may need creation) |
| `services/check_sequence_service.py` | Service layer for DB operations |

### Environment

- Frontend dev server: `http://localhost:5002` (Next.js on port 5002)
- Backend API: `http://localhost:8001` (FastAPI via Docker)
- Database: PostgreSQL on port 5434
- Auth: DEV_AUTH_BYPASS=true in .env.local

### How to Verify

```bash
# 1. Confirm backend is running
curl http://localhost:8001/api/v1/check-types

# 2. Confirm resolve endpoint works
curl "http://localhost:8001/api/v1/check-sequence/resolve?customer_id=1&check_type=work_history"

# 3. Start frontend dev server
cd agencheck-support-frontend && npm run dev -- -p 5002

# 4. Browser test: navigate to http://localhost:5002/check-sla-configuration
# - Page should load data from API (no "Cached data" badge)
# - Click "Voice Call (Primary)" → EditStepModal opens
# - Change retry interval → Save → verify PATCH call in Network tab
# - Drag cards to reorder → verify new order persists on reload
```

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Fix frontend endpoints, not change backend | Backend API is validated working (J2 PASS). Frontend must adapt. |
| Keep localStorage for drafts only | Drafts are useful UX, but reads must come from live API |
| Keep @dnd-kit (already installed) | Code exists, just needs the data flow to work |
| Use NEXT_PUBLIC_API_URL with fallback | Standard Next.js pattern for environment-based config |
