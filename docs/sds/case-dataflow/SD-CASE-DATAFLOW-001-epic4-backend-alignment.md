---
title: "SD-CASE-DATAFLOW-001-E4: Backend Agent & Processor Type Alignment"
description: "Solution design for unifying the PostCallProcessor and Live Form Filler outcome paths to use canonical types"
version: "1.0.0"
last-updated: 2026-03-19
status: active
type: sd
grade: authoritative
prd_ref: PRD-CASE-DATAFLOW-001
---

# SD-CASE-DATAFLOW-001-E4: Backend Agent & Processor Type Alignment

## 1. Overview

This SD addresses Epic 4 of PRD-CASE-DATAFLOW-001: unifying the two outcome production paths (Live Form Filler and PostCallProcessor) to use canonical Pydantic types.

**Target**: `agencheck-support-agent/`
**Worker Type**: `backend-solutions-engineer`
**Depends On**: Epic 1 (canonical types)

## 2. Current State — Two Divergent Paths

### Path A: Live Form Filler → OutcomeBuilder

```
FormSubmissionRequest (Pydantic)
    → outcome_builder.build_verification_outcome()
    → VerificationOutcome (Pydantic, from models/work_history.py)
    → database_writer.write_verification_to_case()
    → cases.verification_results (JSONB, via model_dump(mode="json"))
```

**Status**: Uses canonical types. Mostly correct.

### Path B: PostCallProcessor → process_post_call

```
stream_message (dict)
    → PostCallProcessor (loaded via importlib from voice_agent/)
    → PostCallResult (voice_agent dataclass, NOT Pydantic)
    → Manual dict conversion in process_post_call.py
    → process_call_result (another Prefect task)
    → cases.verification_results (JSONB, via manual dict building)
```

**Status**: Uses non-canonical types with manual conversion. Multiple issues.

### 2.1 Specific Issues in process_post_call.py

**Issue 1: CandidateInfo field name mismatch (lines 300-307)**
```python
candidate = CandidateInfo(
    first_name=candidate_info_data.get("first_name", ""),
    last_name=candidate_info_data.get("last_name", ""),
    company=candidate_info_data.get("company", ""),
    position=candidate_info_data.get("position", ""),
    claimed_start=candidate_info_data.get("start_date", ""),  # ← voice_agent name
    claimed_end=candidate_info_data.get("end_date", "current"),  # ← voice_agent name
)
```

**Issue 2: was_employed invalid enum value (line 358)**
```python
"was_employed": outcome.employment_status in ("verified", "currently_employed"),
# "currently_employed" is NOT a valid EmploymentStatusEnum value
```

**Issue 3: VerifiedField type detection (lines 347-355)**
```python
for field_name, field_val in raw_verified.items():
    if hasattr(field_val, "__dataclass_fields__"):  # ← Fragile type check
        serialized_verified[field_name] = asdict(field_val)
    elif isinstance(field_val, dict):
        serialized_verified[field_name] = field_val
    else:
        serialized_verified[field_name] = str(field_val)
```

**Issue 4: Manual verifier dict building (lines 361-366)**
```python
"verifier": (
    {
        "name": outcome.verifier.name,
        "title": getattr(outcome.verifier, "title", None),  # ← defensive getattr
    }
    if outcome.verifier
    else None
),
```

### 2.2 Issues in outcome_builder.py

**Issue 1: field_name not validated against VerifyFields**
```python
# No validation that field_name matches a known verification field
for field in fields:
    field_name = field["field_name"]  # Could be anything
    verified_value = field["verified_value"]
```

## 3. Solution Design

### 3.1 Create Outcome Conversion Utility

**File**: `agencheck-support-agent/models/outcome_converter.py`

A utility that converts PostCallProcessor output (dataclass-based) into canonical Pydantic `VerificationOutcome`.

```python
"""Convert PostCallProcessor output to canonical VerificationOutcome."""

from typing import Any, Dict, Optional
from models.work_history import (
    VerificationOutcome,
    VerifiedField,
    VerifierInfo,
    EmploymentStatusEnum,
)


# Valid employment statuses that indicate the person WAS employed
_EMPLOYED_STATUSES = {
    EmploymentStatusEnum.VERIFIED.value,
    EmploymentStatusEnum.PARTIAL_VERIFICATION.value,
}


def postcall_result_to_outcome(
    outcome: Any,
    recording_s3_key: str = "",
    transcript_s3_key: Optional[str] = None,
) -> VerificationOutcome:
    """
    Convert a PostCallProcessor PostCallResult.outcome to canonical VerificationOutcome.

    Handles:
    - Dataclass VerifiedField → Pydantic VerifiedField
    - Invalid employment_status values → maps to nearest valid enum
    - was_employed derivation from valid enum values only
    """
    # Convert verified_data
    raw_verified = getattr(outcome, "verified_data", {}) or {}
    canonical_verified: Dict[str, VerifiedField] = {}

    for field_name, field_val in raw_verified.items():
        if hasattr(field_val, "__dataclass_fields__"):
            canonical_verified[field_name] = VerifiedField(
                claimed=getattr(field_val, "claimed", None),
                verified=getattr(field_val, "verified", ""),
                match=getattr(field_val, "match", None),
            )
        elif isinstance(field_val, dict):
            canonical_verified[field_name] = VerifiedField(**field_val)
        else:
            canonical_verified[field_name] = VerifiedField(verified=str(field_val))

    # Map employment_status to valid enum
    raw_status = getattr(outcome, "employment_status", "unable_to_verify")
    employment_status = _normalize_employment_status(raw_status)

    # Derive was_employed from valid enum values
    was_employed = employment_status.value in _EMPLOYED_STATUSES

    # Convert verifier
    raw_verifier = getattr(outcome, "verifier", None)
    verifier = None
    if raw_verifier:
        verifier = VerifierInfo(
            name=getattr(raw_verifier, "name", None),
            title=getattr(raw_verifier, "title", None),
            department=getattr(raw_verifier, "department", None),
        )

    # Build canonical VerificationOutcome
    return VerificationOutcome(
        was_employed=was_employed,
        employment_status=employment_status,
        verified_data=canonical_verified,
        verifier=verifier,
        unable_to_verify_reason=getattr(outcome, "unable_to_verify_reason", None),
        confidence=getattr(outcome, "confidence", 0.0),
        supporting_quotes=getattr(outcome, "supporting_quotes", []),
    )


def _normalize_employment_status(raw: str) -> EmploymentStatusEnum:
    """Map raw status strings (including legacy) to valid EmploymentStatusEnum."""
    # Direct match
    try:
        return EmploymentStatusEnum(raw)
    except ValueError:
        pass

    # Legacy mappings
    LEGACY_MAP = {
        "confirmed": EmploymentStatusEnum.VERIFIED,
        "currently_employed": EmploymentStatusEnum.VERIFIED,  # FIXED: was invalid
        "denied": EmploymentStatusEnum.FAILED_VERIFICATION,
        "partial": EmploymentStatusEnum.PARTIAL_VERIFICATION,
        "unknown": EmploymentStatusEnum.UNABLE_TO_VERIFY,
    }
    return LEGACY_MAP.get(raw, EmploymentStatusEnum.UNABLE_TO_VERIFY)
```

### 3.2 Update process_post_call.py

Replace the manual dict conversion with the converter:

```python
# BEFORE (lines 344-374):
outcome = result.outcome
raw_verified = getattr(outcome, "verified_data", {}) or {}
serialized_verified = {}
# ... 20+ lines of manual conversion ...
return {
    "was_employed": outcome.employment_status in ("verified", "currently_employed"),
    # ...
}

# AFTER:
from models.outcome_converter import postcall_result_to_outcome

outcome = result.outcome
canonical_outcome = postcall_result_to_outcome(
    outcome,
    recording_s3_key=recording_s3_key,
    transcript_s3_key=transcript_s3_key,
)

# Return serialized canonical VerificationOutcome
return {
    **canonical_outcome.model_dump(mode="json"),
    "recording_s3_key": recording_s3_key,
    "transcript_s3_key": transcript_s3_key,
}
```

### 3.3 Add field_name Validation to outcome_builder.py

```python
# Known verification field names (from VerifyFields + base fields)
VALID_FIELD_NAMES = {
    "employment_dates", "start_date", "end_date",
    "position_title",
    "supervisor_name",
    "employment_type",
    "eligibility_for_rehire",
    "reason_for_leaving",
    "salary",
}

async def build_verification_outcome(
    fields: List[Dict[str, Any]],
    ...
) -> VerificationOutcome:
    claimed = claimed_data or {}
    verified_data: Dict[str, VerifiedField] = {}

    for field in fields:
        field_name = field["field_name"]

        # Warn on unknown field names but don't reject (extensible)
        if field_name not in VALID_FIELD_NAMES:
            logger.warning(f"Unknown verification field: {field_name}")

        # ... rest unchanged ...
```

### 3.4 Update database_writer.py Type Hints

No logic changes needed — it already accepts `VerificationOutcome`. Just ensure imports are clean:

```python
from models.work_history import VerificationOutcome, EmploymentStatusEnum
```

## 4. Files to Modify/Create

| File | Action |
|------|--------|
| `models/outcome_converter.py` | **CREATE** — PostCallResult → VerificationOutcome converter |
| `prefect_flows/flows/tasks/process_post_call.py` | **MODIFY** — Use outcome_converter instead of manual dict |
| `live_form_filler/services/outcome_builder.py` | **MODIFY** — Add field_name validation |
| `live_form_filler/services/database_writer.py` | **VERIFY** — Type hints correct |

## 5. Test Strategy

### 5.1 Unit Tests for outcome_converter.py

```python
def test_normalize_employment_status_currently_employed():
    """Verify 'currently_employed' maps to VERIFIED (was causing bugs)."""
    assert _normalize_employment_status("currently_employed") == EmploymentStatusEnum.VERIFIED

def test_was_employed_derived_correctly():
    """Verify was_employed uses only valid enum values."""
    outcome = postcall_result_to_outcome(mock_outcome_verified)
    assert outcome.was_employed is True

    outcome = postcall_result_to_outcome(mock_outcome_failed)
    assert outcome.was_employed is False

def test_dataclass_verified_field_converted():
    """Verify dataclass VerifiedField → Pydantic VerifiedField."""
    outcome = postcall_result_to_outcome(mock_outcome_with_dataclass_fields)
    for field in outcome.verified_data.values():
        assert isinstance(field, VerifiedField)  # Pydantic, not dataclass
```

### 5.2 Integration Tests

1. Send FormSubmissionRequest through Live Form Filler path → verify VerificationOutcome in DB
2. Send stream_message through PostCallProcessor path → verify identical VerificationOutcome structure in DB
3. Compare JSON schemas of outcomes from both paths — must be identical

## Implementation Status

| Task | Status | Date | Commit |
|------|--------|------|--------|
| Create outcome_converter.py | Remaining | - | - |
| Update process_post_call.py | Remaining | - | - |
| Add field validation to outcome_builder | Remaining | - | - |
| Write unit tests | Remaining | - | - |
| Write integration tests | Remaining | - | - |
