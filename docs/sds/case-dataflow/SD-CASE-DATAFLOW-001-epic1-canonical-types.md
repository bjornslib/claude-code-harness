---
title: "SD-CASE-DATAFLOW-001-E1: Canonical Type Definitions & ISO Standards"
description: "Consolidate all Pydantic models into single source of truth with ISO 3166/4217, TS generation, and contact list alignment"
version: "2.0.0"
last-updated: 2026-03-20
status: active
type: sd
grade: authoritative
prd_ref: PRD-CASE-DATAFLOW-001
---

# SD-CASE-DATAFLOW-001-E1: Canonical Type Definitions & ISO Standards

## 1. Overview

Consolidate all work history verification Pydantic models into `models/work_history.py` as the single source of truth. Add ISO country/currency standards, multiple employer contacts, and TypeScript generation.

**Target**: `agencheck-support-agent/` + generated output to `agencheck-support-frontend/`
**Worker Type**: `backend-solutions-engineer`

## 2. Key Changes

### 2.1 Move Router-Inline Models to Canonical Module

The router at `api/routers/work_history.py` currently defines its own `CandidateInfo` (line 323) and `EmployerInfo` (line 334) inline. These must be moved to `models/work_history.py` and the router must import them.

**Router currently has (lines 323-413):**
```python
# INLINE in router — MUST MOVE to models/work_history.py
class CandidateInfo(BaseModel):  # first_name, last_name, email, phone, job_title...
class EmployerInfo(BaseModel):   # employer_company_name, contact_name, contact_email...
class VerificationRequest(BaseModel):  # candidate, employer, employment, verify_fields...
```

**After**: Router imports from canonical module:
```python
from models.work_history import (
    CandidateInfo, EmployerInfo, EmployerContactPerson,
    EmploymentClaim, VerifyFields, VerificationRequest,
    WorkHistoryVerificationMetadata, CheckType,
)
```

### 2.2 New EmployerContactPerson Model

Aligned with `AdditionalContact` from `models/contacts.py` (line 161):

```python
class EmployerContactPerson(BaseModel):
    """A contact at the employer. Aligned with AdditionalContact schema."""
    contact_name: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    position: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=254)
    phone: Optional[str] = Field(None, max_length=50)
    is_primary: bool = False

    @model_validator(mode='after')
    def validate_has_contact_info(self):
        if not any([self.contact_name, self.department, self.email, self.phone]):
            raise ValueError("Contact must have at least one of: contact_name, department, email, or phone")
        return self
```

### 2.3 Revised EmployerInfo

```python
class EmployerInfo(BaseModel):
    employer_company_name: str = Field(..., min_length=1, max_length=255)
    employer_website_url: Optional[str] = Field(None, max_length=500)  # OPTIONAL now
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    phone_numbers: List[str] = Field(..., min_length=1, max_length=5)
    contacts: List[EmployerContactPerson] = Field(default_factory=list)
    external_reference: Optional[str] = Field(None, max_length=255)
    client_type: ClientTypeEnum = ClientTypeEnum.COMPANY

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        import pycountry
        v = v.upper()
        if not pycountry.countries.get(alpha_2=v):
            raise ValueError(f"Invalid ISO 3166-1 alpha-2 country code: {v}")
        return v

    @field_validator("phone_numbers")
    @classmethod
    def validate_phone_format(cls, v: List[str]) -> List[str]:
        import re
        pattern = re.compile(r'^[+\-()0-9\s]{5,50}$')
        for phone in v:
            if not pattern.match(phone):
                raise ValueError(f"Invalid phone number format: {phone}")
        return v
```

### 2.4 Revised CandidateInfo

```python
class CandidateInfo(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)  # NEW
    last_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=255)
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD or null")
```

### 2.5 Revised EmploymentClaim

```python
class EmploymentClaim(BaseModel):
    """All verifiable fields. /verify-check page displays these."""
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: Optional[str] = None
    position_title: str = Field(...)
    supervisor_name: Optional[str] = None
    employment_type: Optional[EmploymentTypeEnum] = None
    employment_arrangement: Optional[EmploymentArrangementEnum] = EmploymentArrangementEnum.DIRECT
    agency_name: Optional[str] = None
    salary_amount: Optional[str] = None            # numeric string
    salary_currency: Optional[str] = None          # ISO 4217, auto-derived from country_code
    eligibility_for_rehire: Optional[EligibilityForRehireEnum] = None
    reason_for_leaving: Optional[str] = None
```

### 2.6 Revised VerifyFields

```python
class VerifyFields(BaseModel):
    employment_dates: bool = True
    position_title: bool = True
    supervisor_name: bool = False
    employment_type: bool = False
    employment_arrangement: bool = False            # NEW
    eligibility_for_rehire: bool = False
    reason_for_leaving: bool = False
    salary: bool = False                            # checks both amount + currency
```

### 2.7 Remove CustomerAgreement

Delete `CustomerAgreement` class from `models/work_history.py`. Remove from `WorkHistoryVerificationMetadata`. Retry behavior is governed by `check_type_config` + `check_sequences` tables via `CheckSequenceService`.

### 2.8 Simplified WorkHistoryVerificationMetadata

```python
class WorkHistoryVerificationMetadata(BaseModel):
    """cases.verification_metadata — structural pass-through, no field renaming."""
    employer: EmployerInfo
    employment: EmploymentClaim
    verify_fields: VerifyFields
```

### 2.9 Simplify _transform_to_metadata()

The current method (router line 646) renames fields. After consolidation, it becomes a structural pass-through:

```python
def _transform_to_metadata(self, request: VerificationRequest) -> WorkHistoryVerificationMetadata:
    employment = request.employment or EmploymentClaim(
        start_date=request.candidate.start_date or "1970-01-01",
        end_date=request.candidate.end_date,
        position_title=request.candidate.job_title or "Unknown Position",
    )
    # Auto-derive salary_currency from country if not provided
    if employment.salary_amount and not employment.salary_currency:
        employment.salary_currency = get_default_currency(request.employer.country_code)

    return WorkHistoryVerificationMetadata(
        employer=request.employer,      # same model, no rename
        employment=employment,
        verify_fields=request.verify_fields or VerifyFields(),
    )
```

### 2.10 ISO Currency Derivation

```python
def get_default_currency(country_code: str) -> str:
    """Derive default ISO 4217 currency from ISO 3166-1 alpha-2 country code."""
    from babel.numbers import get_territory_currencies
    currencies = get_territory_currencies(country_code)
    return currencies[0] if currencies else "USD"
```

### 2.11 Contacts Write Path (Aligned with contacts table)

When writing to the contacts table (university_contacts / future contacts):
- `contacts[0]` → table-level columns (`contact_name`, `email`, `phone`, `department`)
- `contacts[1:]` → `additional_contacts` JSONB column, using `AdditionalContact` model format from `models/contacts.py`

```python
# In work_history_case.py or equivalent
async def write_employer_contact(conn, employer: EmployerInfo):
    primary = employer.contacts[0] if employer.contacts else None
    additional = [
        AdditionalContact(
            contact_name=c.contact_name,
            department=c.department,
            email=c.email,
            phone=c.phone,
            position=c.position,
        ).model_dump(mode="json")
        for c in employer.contacts[1:]
    ]
    # primary → table columns, additional → JSONB
```

### 2.12 DB Migration: Remove default_sla from check_types

```sql
-- Migration: XXX_remove_default_sla_from_check_types.sql
ALTER TABLE check_types DROP COLUMN IF EXISTS default_sla;
```

### 2.13 TypeScript Generation + Pre-Push Hook

**Script**: `agencheck-support-agent/scripts/generate_ts_types.py`

Generates `agencheck-support-frontend/lib/types/work-history.generated.ts` from Pydantic model JSON schemas.

**Pre-push hook** (added to `agencheck-support-frontend/.husky/pre-push` or equivalent):
```bash
#!/bin/bash
cd ../agencheck-support-agent
python scripts/generate_ts_types.py --check  # exits 1 if generated file differs from committed
```

### 2.14 outcome_converter.py

```python
"""Convert PostCheckProcessor output to canonical VerificationOutcome."""

_EMPLOYED_STATUSES = {
    EmploymentStatusEnum.VERIFIED.value,
    EmploymentStatusEnum.PARTIAL_VERIFICATION.value,
}

_LEGACY_STATUS_MAP = {
    "confirmed": EmploymentStatusEnum.VERIFIED,
    "currently_employed": EmploymentStatusEnum.VERIFIED,
    "denied": EmploymentStatusEnum.FAILED_VERIFICATION,
    "partial": EmploymentStatusEnum.PARTIAL_VERIFICATION,
    "unknown": EmploymentStatusEnum.UNABLE_TO_VERIFY,
}

def postcall_result_to_outcome(outcome: Any) -> VerificationOutcome:
    """Convert PostCheckProcessor result to canonical VerificationOutcome.

    Handles: dataclass → Pydantic VerifiedField, legacy status values,
    was_employed derivation from valid enum values only,
    salary split into amount + currency VerifiedField entries.
    """
    # ... (implementation as previously designed)
```

## 3. Files to Modify/Create

| File | Action | Changes |
|------|--------|---------|
| `models/work_history.py` | **MAJOR REWRITE** | Consolidate all models, add ISO validation, remove CustomerAgreement |
| `api/routers/work_history.py` | **MODIFY** | Remove inline model definitions, import from models/ |
| `helpers/work_history_case.py` | **MODIFY** | Update _transform_to_metadata(), contacts write path |
| `models/outcome_converter.py` | **CREATE** | PostCheckProcessor → VerificationOutcome converter |
| `scripts/generate_ts_types.py` | **CREATE** | Pydantic → TypeScript generation |
| `database/migrations/XXX_remove_default_sla.sql` | **CREATE** | Drop default_sla from check_types |
| `requirements.txt` | **MODIFY** | Add `pycountry`, `babel` |

## 4. Test Strategy

1. Unit: `VerifyFields` accepts `eligibility_for_rehire`
2. Unit: `EmployerInfo.country_code` validates via `pycountry`
3. Unit: `get_default_currency("AU")` returns `"AUD"`
4. Unit: `contacts[0]` maps to primary, `contacts[1:]` to additional
5. Integration: Full round-trip VerificationRequest → JSONB → model_validate()
6. TS: Generated file compiles without errors

## Implementation Status

| Task | Status | Date | Commit |
|------|--------|------|--------|
| Consolidate models | Remaining | - | - |
| ISO country/currency | Remaining | - | - |
| EmployerContactPerson | Remaining | - | - |
| Remove CustomerAgreement | Remaining | - | - |
| DB migration | Remaining | - | - |
| TS generation script | Remaining | - | - |
| outcome_converter.py | Remaining | - | - |
