---
title: "SD-CASE-DATAFLOW-001-E1: Canonical Type Definitions & Contract"
description: "Solution design for creating a single source of truth type system across the work history verification data flow"
version: "1.0.0"
last-updated: 2026-03-19
status: active
type: sd
grade: authoritative
prd_ref: PRD-CASE-DATAFLOW-001
---

# SD-CASE-DATAFLOW-001-E1: Canonical Type Definitions & Contract

## 1. Overview

This SD addresses Epic 1 of PRD-CASE-DATAFLOW-001: establishing canonical type definitions that serve as the single source of truth for the entire work history verification data flow.

**Target**: `agencheck-support-agent/` (backend, Python/Pydantic)
**Worker Type**: `backend-solutions-engineer`

## 2. Current State Analysis

### 2.1 models/work_history.py — The Canonical Models (Almost)

The file at `agencheck-support-agent/models/work_history.py` is the most mature type definition, but has these gaps:

```python
# Current VerifyFields — uses eligibility_for_rehire
class VerifyFields(BaseModel):
    employment_dates: bool = True
    position_title: bool = True
    supervisor_name: bool = False
    employment_type: bool = False
    eligibility_for_rehire: bool = False  # ← Frontend sends "rehire_eligibility"
    reason_for_leaving: bool = False
    salary: bool = False
```

```python
# Current EmployerInfo — uses hr_contact_name
class EmployerInfo(BaseModel):
    employer_company_name: str
    employer_website_url: str
    employer_phone: Optional[str] = None
    country: str = "Australia"
    hr_email: Optional[str] = None
    hr_contact_name: Optional[str] = None  # ← Frontend sends "contact_name"
    external_reference: Optional[str] = None
    client_type: ClientTypeEnum = ClientTypeEnum.COMPANY
```

### 2.2 voice_agent CandidateInfo — Different Field Names

The PostCallProcessor uses a different CandidateInfo from `voice_agent/helpers/`:
```python
# voice_agent/helpers/post_call_processor.py
CandidateInfo(
    first_name=...,
    last_name=...,
    company=...,
    position=...,
    claimed_start=...,  # ← NOT start_date
    claimed_end=...,    # ← NOT end_date
)
```

### 2.3 was_employed Logic

```python
# process_post_call.py line 358 — INVALID enum value
"was_employed": outcome.employment_status in ("verified", "currently_employed")
#                                              ↑ valid   ↑ NOT a valid EmploymentStatusEnum!
```

## 3. Solution Design

### 3.1 Fix VerifyFields — Add Pydantic Field Aliases

**Strategy**: Add `validation_alias` to accept both the canonical name and the frontend name.

```python
# models/work_history.py — VerifyFields class
from pydantic import AliasChoices

class VerifyFields(BaseModel):
    employment_dates: bool = Field(True)
    position_title: bool = Field(True)
    supervisor_name: bool = Field(False)
    employment_type: bool = Field(False)
    eligibility_for_rehire: bool = Field(
        False,
        validation_alias=AliasChoices('eligibility_for_rehire', 'rehire_eligibility'),
        description="Ask about eligibility for rehire (optional add-on)"
    )
    reason_for_leaving: bool = Field(False)
    salary: bool = Field(False)

    model_config = ConfigDict(populate_by_name=True)
```

**Why AliasChoices**: Accepts both `eligibility_for_rehire` (canonical) and `rehire_eligibility` (frontend compat) during deserialization. Serialization always uses the canonical name.

### 3.2 Fix EmployerInfo — Add Contact Field Aliases

```python
class EmployerInfo(BaseModel):
    employer_company_name: str
    employer_website_url: str
    employer_phone: Optional[str] = None
    country: str = "Australia"
    hr_email: Optional[str] = Field(
        None,
        validation_alias=AliasChoices('hr_email', 'contact_email'),
    )
    hr_contact_name: Optional[str] = Field(
        None,
        validation_alias=AliasChoices('hr_contact_name', 'contact_name'),
    )
    external_reference: Optional[str] = None
    client_type: ClientTypeEnum = ClientTypeEnum.COMPANY

    model_config = ConfigDict(populate_by_name=True)
```

### 3.3 TypeScript Type Generation

Create a script that exports Pydantic models to TypeScript interfaces.

**File**: `agencheck-support-agent/scripts/generate_ts_types.py`

```python
#!/usr/bin/env python3
"""Generate TypeScript interfaces from canonical Pydantic models."""

import json
import sys
sys.path.insert(0, '.')
from models.work_history import (
    VerifyFields, EmployerInfo, EmploymentClaim,
    VerificationOutcome, VerifiedField, VerifierInfo,
    EmploymentTypeEnum, EmploymentStatusEnum,
    EmploymentArrangementEnum, EligibilityForRehireEnum,
)

OUTPUT_PATH = "../agencheck-support-frontend/lib/types/work-history.generated.ts"

def pydantic_to_ts():
    """Generate TypeScript from Pydantic JSON schemas."""
    models = [
        VerifyFields, EmployerInfo, EmploymentClaim,
        VerificationOutcome, VerifiedField, VerifierInfo,
    ]
    enums = [
        EmploymentTypeEnum, EmploymentStatusEnum,
        EmploymentArrangementEnum, EligibilityForRehireEnum,
    ]

    lines = [
        "// AUTO-GENERATED from agencheck-support-agent/models/work_history.py",
        "// Do not edit manually. Run: python scripts/generate_ts_types.py",
        "",
    ]

    # Generate enum types
    for enum_cls in enums:
        values = " | ".join(f'"{e.value}"' for e in enum_cls)
        lines.append(f"export type {enum_cls.__name__} = {values};")
    lines.append("")

    # Generate interface from JSON schema
    for model in models:
        schema = model.model_json_schema()
        lines.append(f"export interface {model.__name__} {{")
        for prop_name, prop_def in schema.get("properties", {}).items():
            required = prop_name in schema.get("required", [])
            ts_type = json_schema_to_ts(prop_def)
            opt = "" if required else "?"
            lines.append(f"  {prop_name}{opt}: {ts_type};")
        lines.append("}")
        lines.append("")

    with open(OUTPUT_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"Generated {OUTPUT_PATH}")


def json_schema_to_ts(prop: dict) -> str:
    """Convert JSON Schema property to TypeScript type."""
    if "anyOf" in prop:
        types = [json_schema_to_ts(t) for t in prop["anyOf"] if t.get("type") != "null"]
        return " | ".join(types) + " | null" if any(t.get("type") == "null" for t in prop["anyOf"]) else " | ".join(types)
    t = prop.get("type", "any")
    if t == "string": return "string"
    if t == "integer" or t == "number": return "number"
    if t == "boolean": return "boolean"
    if t == "array": return f"{json_schema_to_ts(prop.get('items', {}))}[]"
    if t == "object":
        if "additionalProperties" in prop:
            return f"Record<string, {json_schema_to_ts(prop['additionalProperties'])}>"
        return "Record<string, unknown>"
    return "unknown"


if __name__ == "__main__":
    pydantic_to_ts()
```

**Output location**: `agencheck-support-frontend/lib/types/work-history.generated.ts`

### 3.4 Fix process_post_call.py — Canonical CandidateInfo

```python
# BEFORE (line 300-307):
candidate = CandidateInfo(
    first_name=candidate_info_data.get("first_name", ""),
    last_name=candidate_info_data.get("last_name", ""),
    company=candidate_info_data.get("company", ""),
    position=candidate_info_data.get("position", ""),
    claimed_start=candidate_info_data.get("start_date", ""),
    claimed_end=candidate_info_data.get("end_date", "current"),
)

# AFTER: Use canonical CandidateInfo from models/work_history.py
from models.work_history import CandidateInfo as CanonicalCandidateInfo

# Map voice_agent fields to canonical names
candidate_for_processor = CandidateInfo(
    first_name=candidate_info_data.get("first_name", ""),
    last_name=candidate_info_data.get("last_name", ""),
    company=candidate_info_data.get("company", ""),
    position=candidate_info_data.get("position", ""),
    claimed_start=candidate_info_data.get("start_date", ""),  # Must map
    claimed_end=candidate_info_data.get("end_date", "current"),
)
```

**Note**: The voice_agent's internal CandidateInfo uses `claimed_start`/`claimed_end` which is its domain-specific naming. We do NOT change the voice agent's internal models (out of scope). Instead, we ensure the `process_post_call.py` correctly maps FROM canonical field names TO the voice_agent's expected names.

### 3.5 Fix was_employed Logic

```python
# BEFORE (process_post_call.py line 358):
"was_employed": outcome.employment_status in ("verified", "currently_employed"),

# AFTER: Use only valid EmploymentStatusEnum values
"was_employed": outcome.employment_status in (
    EmploymentStatusEnum.VERIFIED.value,
    EmploymentStatusEnum.PARTIAL_VERIFICATION.value,
),
```

### 3.6 Converge VerifiedField to Pydantic Only

The `outcome_builder.py` already uses the Pydantic `VerifiedField`. The `process_post_call.py` handles dataclass `VerifiedField` from the voice agent.

**Strategy**: Keep the Pydantic `VerifiedField` as canonical. In `process_post_call.py`, convert dataclass VerifiedField to Pydantic VerifiedField immediately after PostCallProcessor returns:

```python
from models.work_history import VerifiedField as CanonicalVerifiedField

# After PostCallProcessor.process():
raw_verified = getattr(outcome, "verified_data", {}) or {}
canonical_verified = {}
for field_name, field_val in raw_verified.items():
    if hasattr(field_val, "__dataclass_fields__"):
        canonical_verified[field_name] = CanonicalVerifiedField(
            claimed=getattr(field_val, "claimed", None),
            verified=getattr(field_val, "verified", ""),
            match=getattr(field_val, "match", None),
        )
    elif isinstance(field_val, dict):
        canonical_verified[field_name] = CanonicalVerifiedField(**field_val)
    else:
        canonical_verified[field_name] = CanonicalVerifiedField(verified=str(field_val))
```

## 4. Files to Modify

| File | Changes |
|------|---------|
| `agencheck-support-agent/models/work_history.py` | Add `AliasChoices` to VerifyFields and EmployerInfo; add `populate_by_name=True` |
| `agencheck-support-agent/scripts/generate_ts_types.py` | **NEW** — TypeScript generation script |
| `agencheck-support-agent/prefect_flows/flows/tasks/process_post_call.py` | Fix was_employed logic; convert VerifiedField to Pydantic |
| `agencheck-support-frontend/lib/types/work-history.generated.ts` | **NEW** — Auto-generated TypeScript types |

## 5. Test Strategy

1. **Unit tests**: Verify `VerifyFields` accepts both `rehire_eligibility` and `eligibility_for_rehire`
2. **Unit tests**: Verify `EmployerInfo` accepts both `contact_name` and `hr_contact_name`
3. **Unit tests**: Verify `was_employed` derivation with all EmploymentStatusEnum values
4. **Integration test**: Round-trip serialize→deserialize with both old and new field names
5. **TypeScript compilation**: Ensure generated `.ts` file compiles without errors

## Implementation Status

| Task | Status | Date | Commit |
|------|--------|------|--------|
| VerifyFields alias fix | Remaining | - | - |
| EmployerInfo alias fix | Remaining | - | - |
| TS type generation script | Remaining | - | - |
| was_employed fix | Remaining | - | - |
| VerifiedField convergence | Remaining | - | - |
