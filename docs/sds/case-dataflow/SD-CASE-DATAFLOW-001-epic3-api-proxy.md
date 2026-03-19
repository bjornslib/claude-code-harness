---
title: "SD-CASE-DATAFLOW-001-E3: API Proxy Contract Alignment"
description: "Solution design for fixing field mapping in the frontend API proxy to match canonical backend types"
version: "1.0.0"
last-updated: 2026-03-19
status: active
type: sd
grade: authoritative
prd_ref: PRD-CASE-DATAFLOW-001
---

# SD-CASE-DATAFLOW-001-E3: API Proxy Contract Alignment

## 1. Overview

This SD addresses Epic 3 of PRD-CASE-DATAFLOW-001: fixing all field mapping in `app/api/verify/route.ts` to match the canonical backend Pydantic models.

**Target**: `agencheck-support-frontend/app/api/verify/route.ts`
**Worker Type**: `frontend-dev-expert`
**Depends On**: Epic 1 (TypeScript types), Epic 2 (form field additions)

## 2. Current State — route.ts (256 lines)

### 2.1 Field Mapping Issues

```typescript
// Line 142-152: verify_fields mapping
const backendVerifyFields = verifyFields
  ? {
      employment_dates: true,
      position_title: true,
      salary: verifyFields.salary ?? false,
      supervisor_name: verifyFields.supervisor ?? false,
      employment_type: verifyFields.employment_type ?? false,
      rehire_eligibility: verifyFields.rehire_eligibility ?? false,  // ← WRONG: backend uses eligibility_for_rehire
      reason_for_leaving: verifyFields.reason_for_leaving ?? false,
    }
  : undefined;
```

```typescript
// Line 167-171: employer mapping
employer: {
    employer_company_name: employerName,
    employer_website_url: employerWebsite,
    ...(contactPersonName ? { contact_name: contactPersonName } : {}),  // ← WRONG: backend uses hr_contact_name
    ...(employerPhone ? { employer_phone: employerPhone } : {}),
    ...(contactEmail ? { contact_email: contactEmail } : {}),  // ← backend EmployerInfo has no contact_email (only hr_email)
    country,
},
```

### 2.2 Missing Fields

- `employment_arrangement` not passed through
- `agency_name` not passed through
- No date format validation before sending

## 3. Solution Design

### 3.1 Import Canonical Types

```typescript
// Replace inline FrontendVerifyFields interface with canonical import
import type {
  VerifyFields,
  EmployerInfo,
  EmploymentClaim,
  EmploymentTypeEnum,
  EmploymentArrangementEnum,
} from "@/lib/types/work-history.generated";
```

### 3.2 Fix verify_fields Mapping

```typescript
// Map frontend field names → canonical backend field names
const backendVerifyFields: VerifyFields | undefined = verifyFields
  ? {
      employment_dates: true,
      position_title: true,
      salary: verifyFields.salary ?? false,
      supervisor_name: verifyFields.supervisor ?? false,
      employment_type: verifyFields.employment_type ?? false,
      eligibility_for_rehire: verifyFields.rehire_eligibility ?? false,  // FIXED: canonical name
      reason_for_leaving: verifyFields.reason_for_leaving ?? false,
    }
  : undefined;
```

### 3.3 Fix employer Mapping

```typescript
employer: {
    employer_company_name: employerName,
    employer_website_url: employerWebsite,
    ...(contactPersonName ? { hr_contact_name: contactPersonName } : {}),  // FIXED
    ...(employerPhone ? { employer_phone: employerPhone } : {}),
    ...(contactEmail ? { hr_email: contactEmail } : {}),  // FIXED: hr_email not contact_email
    country,
},
```

### 3.4 Add employment_arrangement and agency_name

Destructure from body:

```typescript
const {
  // ... existing fields ...
  employmentArrangement,  // NEW
  agencyName,             // NEW
} = body as {
  // ... existing types ...
  employmentArrangement?: string;
  agencyName?: string;
};
```

Pass through to employment object:

```typescript
employment: {
    start_date: normalizedStart ?? '1970-01-01',
    ...(normalizedEnd ? { end_date: normalizedEnd } : {}),
    ...(position ? { position_title: position } : {}),
    ...(verifyFields?.supervisor && supervisorName
      ? { supervisor_name: supervisorName }
      : {}),
    ...(verifyFields?.employment_type && employmentType
      ? { employment_type: employmentType }
      : {}),
    ...(verifyFields?.salary && salaryAmount
      ? { salary: salaryAmount }
      : {}),
    // NEW: employment arrangement
    ...(employmentArrangement
      ? { employment_arrangement: employmentArrangement }
      : {}),
    ...(agencyName ? { agency_name: agencyName } : {}),
},
```

### 3.5 Add Date Format Validation

```typescript
// After parsing body, before building payload
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

function validateDateFormat(date: string | undefined, fieldName: string): void {
  if (date && !DATE_REGEX.test(date) && !/^\d{4}-\d{2}$/.test(date)) {
    throw new Error(`Invalid date format for ${fieldName}: ${date}. Expected YYYY-MM-DD or YYYY-MM`);
  }
}

validateDateFormat(startDate, 'startDate');
validateDateFormat(endDate, 'endDate');
```

### 3.6 Complete Updated route.ts Structure

The key changes summarized:

| Line | Before | After |
|------|--------|-------|
| 19-25 | `FrontendVerifyFields` inline interface | Import from canonical types |
| 149 | `rehire_eligibility: verifyFields.rehire_eligibility` | `eligibility_for_rehire: verifyFields.rehire_eligibility` |
| 169 | `contact_name: contactPersonName` | `hr_contact_name: contactPersonName` |
| 171 | `contact_email: contactEmail` | `hr_email: contactEmail` |
| N/A | Missing | `employment_arrangement` and `agency_name` pass-through |
| N/A | Missing | Date format validation |

## 4. Files to Modify

| File | Changes |
|------|---------|
| `app/api/verify/route.ts` | Fix field mappings, add new fields, import canonical types |

## 5. Test Strategy

1. Submit form with rehire_eligibility enabled → verify backend receives `eligibility_for_rehire: true`
2. Submit form with contact person → verify backend receives `hr_contact_name`
3. Submit form with agency arrangement → verify `employment_arrangement` and `agency_name` arrive
4. Submit invalid date format → verify 400 error returned
5. Regression: standard work history submission still works

## Implementation Status

| Task | Status | Date | Commit |
|------|--------|------|--------|
| Fix verify_fields mapping | Remaining | - | - |
| Fix employer field names | Remaining | - | - |
| Add arrangement pass-through | Remaining | - | - |
| Add date validation | Remaining | - | - |
| Import canonical types | Remaining | - | - |
