---
title: "PRD-CASE-DATAFLOW-001: Work History Check Data Type Consistency"
description: "Enforce consistent data types across the entire case/check data flow from New Case creation through verification outcomes"
version: "1.0.0"
last-updated: 2026-03-19
status: active
type: prd
grade: authoritative
prd_id: PRD-CASE-DATAFLOW-001
---

# PRD-CASE-DATAFLOW-001: Work History Check Data Type Consistency

## 1. Problem Statement

The AgenCheck work history verification system has **9 critical type inconsistencies** across its 4-layer data flow, causing silent data loss, validation bypasses, and field mapping errors between the frontend form, API proxy, backend processing, and outcome storage.

### Root Cause Analysis

Type definitions evolved independently across 4 repositories:
1. **Frontend form** (`new/page.tsx`): Zod schema with local string types
2. **Frontend proxy** (`route.ts`): Ad-hoc `FrontendVerifyFields` interface with manual mapping
3. **Backend models** (`models/work_history.py`): Canonical Pydantic models (most mature)
4. **Voice agent** (`voice_agent/helpers/`): Separate dataclass-based models

No automated type generation or contract testing exists between layers.

## 2. Critical Type Mismatches Identified

### M1: Verify Fields — rehire_eligibility vs eligibility_for_rehire
| Layer | Field Name | Status |
|-------|-----------|--------|
| Frontend form (`VERIFY_FIELDS` array) | `rehire_eligibility` | Used |
| Frontend proxy (`route.ts` line 149) | `rehire_eligibility` | Passed through |
| Backend Pydantic (`VerifyFields` line 349) | `eligibility_for_rehire` | **DIFFERENT** |

**Impact**: The `rehire_eligibility` field sent by the frontend is **silently ignored** by Pydantic's strict model. The backend never receives the user's rehire eligibility preference.

### M2: Employment Type Enum — contract vs contractor
| Layer | Values |
|-------|--------|
| Frontend form (`SelectItem` values) | `full_time`, `part_time`, `contract` |
| Backend Pydantic (`EmploymentTypeEnum`) | `full_time`, `part_time`, `contractor`, `casual` |

**Impact**: Frontend sends `"contract"` which fails Pydantic validation or falls to `None`. Missing `casual` option entirely.

### M3: Contact Info Field Names — contact_name vs hr_contact_name
| Layer | Field Sent | Backend Field |
|-------|-----------|---------------|
| Frontend proxy (`route.ts` line 169) | `contact_name` | — |
| Backend `EmployerInfo` model | — | `hr_contact_name` |

**Impact**: Contact person name is sent as `contact_name` but the Pydantic model expects `hr_contact_name`. The contact person is lost in transit.

### M4: Dual CandidateInfo Models — claimed_start vs start_date
| Model Location | Start Date Field | End Date Field |
|---------------|-----------------|----------------|
| `models/work_history.py` CandidateInfo | `start_date` | `end_date` |
| `voice_agent/helpers/` CandidateInfo | `claimed_start` | `claimed_end` |

**Impact**: `process_post_call.py` passes `start_date` value to `claimed_start` parameter. Works by coincidence but breaks if either side validates field names.

### M5: Dual VerifiedField Models — Pydantic vs Dataclass
| Location | Type | Serialization |
|----------|------|---------------|
| `models/work_history.py` VerifiedField | **Pydantic** BaseModel | `.model_dump()` |
| `voice_agent/helpers/` VerifiedField | **dataclass** | `asdict()` |

**Impact**: `process_post_call.py` must detect whether a VerifiedField is a dataclass or dict via `hasattr(__dataclass_fields__)`. Fragile type detection instead of contract enforcement.

### M6: was_employed Logic Inconsistency
| Location | Logic |
|----------|-------|
| `outcome_builder.py` | Direct boolean from `FormSubmissionRequest.was_employed` |
| `process_post_call.py` line 358 | `outcome.employment_status in ("verified", "currently_employed")` |

**Impact**: `"currently_employed"` is **NOT** a valid `EmploymentStatusEnum` value. The `was_employed` derivation in the PostCallProcessor path can produce incorrect results.

### M7: Date Format — No Frontend Validation
| Layer | Format | Validation |
|-------|--------|-----------|
| Frontend Zod schema | `z.string().min(1)` | **None** — any non-empty string passes |
| Frontend `<Input type="date">` | Browser-dependent | Not enforced by Zod |
| Backend `EmploymentClaim` | `YYYY-MM-DD` or `YYYY-MM` | String field, no regex |

**Impact**: Invalid date strings can flow through the entire pipeline uncaught.

### M8: Frontend Form Missing shadcn Components
| Field | Current Component | Should Be |
|-------|------------------|-----------|
| Start/End Date | `<Input type="date">` | shadcn `DatePicker` or `Calendar` + `Popover` |
| Country | `<Input>` (free text) | shadcn `Combobox` with ISO country list |
| Phone Number | `<Input>` (free text) | Phone input with validation/formatting |
| Employment Arrangement | **Missing** | shadcn `Select` (direct/agency/subcontractor) |

### M9: EmployerInfo Fields — Frontend Proxy vs Backend Model

The frontend proxy (`route.ts`) sends field names that don't match the backend Pydantic model:

| Frontend Sends | Backend Expects | Status |
|---------------|----------------|--------|
| `contact_name` | `hr_contact_name` | **MISMATCH** |
| `contact_email` | `hr_email`? No — backend has no `contact_email` | **MISMATCH** |
| `employer_phone` | `employer_phone` | OK |
| `country` | `country` | OK |

## 3. Business Goals

1. **Zero silent data loss**: Every field value entered by the user must arrive at the backend with the correct field name
2. **Type-safe data flow**: Shared type definitions between frontend and backend prevent drift
3. **Complete form experience**: All work history check types represented with proper shadcn UI components
4. **Unified outcome models**: Single VerificationOutcome path regardless of whether data comes from Live Form Filler or PostCallProcessor

## 4. User Stories

**US-1**: As a verification operator, I want all my form selections (including rehire eligibility) to actually reach the backend, so that the voice agent asks the right questions.

**US-2**: As a verification operator, I want to select from ALL valid employment types (including casual and contractor), so that the verification accurately reflects the candidate's employment.

**US-3**: As a verification operator, I want date pickers that enforce valid formats, so that verification calls aren't delayed by data formatting issues.

**US-4**: As a platform engineer, I want a single canonical set of type definitions that both frontend and backend share, so that field name mismatches are caught at build time rather than silently failing at runtime.

**US-5**: As a platform engineer, I want both the Live Form Filler and PostCallProcessor paths to produce identical VerificationOutcome objects, so that downstream consumers don't need path-specific handling.

## 5. Target Repository

**Codebase**: `zenagent2/zenagent/agencheck`
- Frontend: `agencheck-support-frontend/` (Next.js, TypeScript, shadcn/ui)
- Backend: `agencheck-support-agent/` (FastAPI, Pydantic, Python)

## 6. Scope

### In Scope
- Fix all 9 type mismatches (M1-M9)
- Create shared TypeScript type definitions generated from Pydantic models
- Upgrade frontend form to use proper shadcn components
- Unify VerificationOutcome production paths
- Add employment_arrangement field to frontend form
- Add date format validation

### Out of Scope
- Database schema changes (types flow as JSONB; schema is flexible)
- New check types beyond work_history (schedule_work_history stays "coming soon")
- Prefect flow restructuring
- Voice agent internal refactoring (only the interface contract)
- LiveKit integration changes

## 7. Success Criteria

1. All verify_fields from frontend reach backend with matching field names
2. EmploymentTypeEnum values match between frontend Select options and backend enum
3. Frontend form uses shadcn DatePicker, Combobox (country), and proper Select components
4. TypeScript types are generated from or aligned with Pydantic models
5. Both outcome paths (Live Form Filler + PostCallProcessor) produce the same VerificationOutcome type
6. `was_employed` logic uses only valid EmploymentStatusEnum values
7. Zero Pydantic validation errors from field name mismatches in production logs

## 8. Epics

### Epic 1: Canonical Type Definitions & Contract (Backend)
**Priority**: P0 — All other epics depend on this
**Scope**: `agencheck-support-agent/`

Create a single source of truth for all work history verification types.

**Deliverables**:
- Fix `VerifyFields.eligibility_for_rehire` → add alias `rehire_eligibility` for backward compat
- Fix `EmployerInfo` to accept both `contact_name` and `hr_contact_name` via Field aliases
- Add `contact_email` field to `EmployerInfo` model
- Create TypeScript type export script that generates `.d.ts` from Pydantic models
- Unify voice_agent CandidateInfo fields: `claimed_start`/`claimed_end` → `start_date`/`end_date`
- Fix `was_employed` derivation to use only valid `EmploymentStatusEnum` values
- Converge `VerifiedField` to single Pydantic model (eliminate dataclass version)

**Acceptance Criteria**:
- [ ] `VerifyFields` model accepts both `rehire_eligibility` and `eligibility_for_rehire`
- [ ] `EmployerInfo` accepts both `contact_name`/`hr_contact_name` and `contact_email`
- [ ] TypeScript type file generated and matches Pydantic models
- [ ] Single `VerifiedField` type used across both outcome paths
- [ ] `was_employed` uses only valid enum values
- [ ] All existing tests pass with changes

### Epic 2: Frontend Form — shadcn Component Upgrade
**Priority**: P1 — Depends on Epic 1 types
**Scope**: `agencheck-support-frontend/`

Replace raw HTML inputs with proper shadcn components and wire to canonical types.

**Deliverables**:
- Replace `<Input type="date">` with shadcn `DatePicker` (Popover + Calendar)
- Replace Country `<Input>` with shadcn `Combobox` (autocomplete, ISO countries)
- Fix Employment Type `<Select>` options: add `contractor` (not `contract`), add `casual`
- Add Employment Arrangement `<Select>`: direct, agency, subcontractor
- Add conditional Agency Name `<Input>` when arrangement is agency/subcontractor
- Wire form to use generated TypeScript types from Epic 1
- Update Zod schema to use proper date validation (YYYY-MM-DD regex)

**Acceptance Criteria**:
- [ ] Date fields use shadcn DatePicker with YYYY-MM-DD output
- [ ] Country field uses shadcn Combobox with ISO country list
- [ ] Employment Type options match backend `EmploymentTypeEnum` exactly
- [ ] Employment Arrangement field present with correct options
- [ ] Agency Name appears conditionally for agency/subcontractor
- [ ] Zod schema validates date format
- [ ] Form compiles against canonical TypeScript types

### Epic 3: API Proxy Contract Alignment (Frontend)
**Priority**: P1 — Depends on Epic 1 types
**Scope**: `agencheck-support-frontend/app/api/verify/route.ts`

Fix all field mapping in the frontend proxy to match canonical backend types.

**Deliverables**:
- Fix verify_fields mapping: `rehire_eligibility` → `eligibility_for_rehire`
- Fix employer field mapping: `contact_name` → `hr_contact_name`
- Add `contact_email` → pass through to backend
- Add employment_arrangement pass-through
- Replace inline `FrontendVerifyFields` interface with imported canonical type
- Add agency_name conditional pass-through
- Add date format validation (YYYY-MM-DD regex) before sending

**Acceptance Criteria**:
- [ ] All verify_fields names match backend `VerifyFields` model
- [ ] All employer fields match backend `EmployerInfo` model
- [ ] Employment arrangement passed through correctly
- [ ] Date format validated as YYYY-MM-DD before backend call
- [ ] TypeScript types imported from canonical definition file

### Epic 4: Backend Agent & Processor Type Alignment
**Priority**: P1 — Depends on Epic 1 types
**Scope**: `agencheck-support-agent/` + interface to `agencheck-communication-agent/`

Unify the two outcome production paths to use canonical types.

**Deliverables**:
- Update `process_post_call.py` to use canonical `CandidateInfo` from `models/work_history.py`
- Fix field mapping: `claimed_start` → `start_date`, `claimed_end` → `end_date`
- Fix `was_employed` logic: remove `"currently_employed"`, use only `EmploymentStatusEnum` values
- Update `outcome_builder.py` to validate field_names against `VerifyFields.get_active_fields()`
- Ensure both paths produce identical `VerificationOutcome` objects
- Update `database_writer.py` type hints to use canonical models

**Acceptance Criteria**:
- [ ] `process_post_call.py` uses `CandidateInfo` from `models/work_history.py`
- [ ] No reference to `claimed_start`/`claimed_end` in PostCallProcessor integration
- [ ] `was_employed` derived from `EmploymentStatusEnum` values only
- [ ] Both outcome paths produce `VerificationOutcome` via `.model_dump(mode="json")`
- [ ] Database writer receives canonical `VerificationOutcome` from both paths
- [ ] Integration tests verify outcome equivalence across both paths

## 9. Dependency Graph

```
Epic 1 (Canonical Types)
  ├──→ Epic 2 (Frontend Form — shadcn)
  ├──→ Epic 3 (API Proxy Contract)
  └──→ Epic 4 (Backend Agent Alignment)
```

Epic 1 is the foundation. Epics 2, 3, and 4 can proceed in parallel after Epic 1 completes.

## 10. Key File Map

| Layer | File | Purpose |
|-------|------|---------|
| Frontend Form | `agencheck-support-frontend/app/checks-dashboard/new/page.tsx` | New Case form with Zod schema |
| Frontend Proxy | `agencheck-support-frontend/app/api/verify/route.ts` | Field mapping to backend |
| Backend Models | `agencheck-support-agent/models/work_history.py` | Canonical Pydantic models |
| Backend Router | `agencheck-support-agent/api/routers/work_history.py` | /api/v1/verify endpoint |
| Form Filler Models | `agencheck-support-agent/live_form_filler/models.py` | FormSubmissionRequest |
| Outcome Builder | `agencheck-support-agent/live_form_filler/services/outcome_builder.py` | VerificationOutcome from form filler |
| Database Writer | `agencheck-support-agent/live_form_filler/services/database_writer.py` | Write outcomes to cases table |
| PostCallProcessor | `agencheck-support-agent/prefect_flows/flows/tasks/process_post_call.py` | PostCallProcessor integration |
| Case Service | `agencheck-support-agent/helpers/work_history_case.py` | Case creation in DB |
| DB Migration | `database/migrations/027_work_history_case_support.sql` | Schema definition |

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Voice agent CandidateInfo break | Medium | High | Add backward-compat aliases |
| Pydantic model alias conflicts | Low | Medium | Test with both old and new field names |
| shadcn DatePicker timezone issues | Medium | Medium | Always produce UTC-naive YYYY-MM-DD strings |
| Breaking existing API consumers | Low | High | Use Field aliases for backward compat, not renames |

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| E1: Canonical Types | Remaining | - | - |
| E2: Frontend Form shadcn | Remaining | - | - |
| E3: API Proxy Contract | Remaining | - | - |
| E4: Backend Agent Alignment | Remaining | - | - |
