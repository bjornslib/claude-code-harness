# Evidence Capture Templates

Templates for validation-agent to capture evidence at each validation level.

## Level 1: Unit Tests

**Required Evidence**:
- [ ] Test command output (pytest/jest results)
- [ ] Number of tests passed/failed/skipped
- [ ] Any failure stack traces

**Evidence Format**:
```
==== UNIT TEST EVIDENCE ====
Command: pytest tests/ -v
Timestamp: <ISO 8601>
Results: X passed, Y failed, Z skipped

[Full test output below]
...
```

## Level 2: API Tests

**Required Evidence**:
- [ ] Endpoint(s) tested
- [ ] Request/response payloads
- [ ] HTTP status codes
- [ ] Any error messages

**Evidence Format**:
```
==== API TEST EVIDENCE ====
Endpoint: POST /api/endpoint
Timestamp: <ISO 8601>
Status: 200 OK

Request:
{...}

Response:
{...}
```

## Level 3: E2E Browser Tests

**Required Evidence**:
- [ ] Screenshots of key UI states
- [ ] Browser console logs (errors only)
- [ ] User flow description

**Evidence Format**:
```
==== E2E TEST EVIDENCE ====
Flow: Login → Dashboard → Feature
Timestamp: <ISO 8601>
Screenshots: [list of paths]
Console Errors: None / [list]

Steps Verified:
1. [step description]
2. [step description]
```

## E2E Validation (--mode=e2e --prd=PRD-XXX)

**Required Evidence**:
- [ ] Key Result status (verified/not verified)
- [ ] PRD requirement mappings
- [ ] Completion promise assessment

**Evidence Format**:
```
==== BUSINESS VALIDATION EVIDENCE ====
Epic: <epic-id>
Timestamp: <ISO 8601>
Completion Promise: <original promise>

Key Results:
- KR1: [status] - [evidence]
- KR2: [status] - [evidence]

PRD Requirements Met: X/Y
Verdict: PASS/FAIL
Rationale: <explanation>
```
