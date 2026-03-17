---
title: "nWave TDD Anti-Pattern Catalog"
status: active
type: reference
last_verified: 2026-03-17
grade: authoritative
---

# nWave TDD Anti-Pattern Catalog

Reference catalog of the 7 deadly TDD anti-patterns. Used by the worker stop gate
to validate that workers followed disciplined engineering practices. Each anti-pattern
includes detection heuristics that can be applied against worker activity JSONL streams.

## How This Reference Is Used

1. **Worker stop gate** (`worker-stop-gate.py`) reads this catalog at exit time
2. **Acceptance test runner** injects relevant anti-patterns into validation prompts
3. **Rigor profiles** control which anti-patterns are enforced per pipeline

---

## Anti-Pattern 1: Premature Green (The Wishful Thinker)

**ID**: `AP-001`
**Severity**: critical
**Phase affected**: RED → GREEN transition

### Description

Writing implementation code before a failing test exists. The worker jumps straight
to `src/` edits without first establishing a RED test that defines the expected behavior.

### Detection Heuristics

```yaml
detection:
  activity_stream:
    - pattern: "First edit targets src/ before any test file edit"
    - pattern: "No test file appears in activity before first src/ edit"
  file_ordering:
    - rule: "If phase=green and no prior phase=red_unit entry exists → violation"
  confidence: high
```

### Why It Matters

Without a failing test first, there is no proof that the test actually exercises the
new behavior. The test may pass trivially (tautology) or test the wrong thing entirely.

---

## Anti-Pattern 2: The Giant Leap (Big Bang Implementation)

**ID**: `AP-002`
**Severity**: high
**Phase affected**: GREEN phase

### Description

Writing too much code in a single GREEN phase — implementing multiple behaviors,
features, or edge cases in one pass rather than the smallest increment that makes
the current failing test pass.

### Detection Heuristics

```yaml
detection:
  activity_stream:
    - pattern: "More than 5 src/ file edits in a single GREEN phase without returning to RED"
    - pattern: "GREEN phase duration exceeds 10 minutes without a test run"
  line_count:
    - rule: "If total lines changed in GREEN > 150 without intervening RED → warning"
  confidence: medium
```

### Why It Matters

Large implementations are harder to debug, harder to review, and bypass the
incremental confidence that TDD provides. Each GREEN should be the minimum code
to pass exactly one test.

---

## Anti-Pattern 3: Mock Obsession (The Isolation Fanatic)

**ID**: `AP-003`
**Severity**: high
**Phase affected**: RED_UNIT and RED_INTEGRATION phases

### Description

Over-mocking internal implementation details rather than testing behavior through
public interfaces. Mocking every dependency, including ones owned by the same module,
creating tests that are tightly coupled to implementation.

### Detection Heuristics

```yaml
detection:
  code_analysis:
    - pattern: "mock.patch targeting internal module functions (same package)"
    - pattern: "More than 3 mock.patch decorators on a single test function"
    - pattern: "Mocking return values of functions that could be called directly"
  file_content:
    - rule: "If test file has more mock.patch lines than assertion lines → warning"
  confidence: medium
```

### Why It Matters

Over-mocked tests don't verify real behavior — they verify that the code calls
specific internal functions in a specific order. Refactoring the implementation
(without changing behavior) breaks these tests, creating false negatives.

---

## Anti-Pattern 4: Test-After (The Retroactive Validator)

**ID**: `AP-004`
**Severity**: critical
**Phase affected**: All phases

### Description

Writing all implementation code first, then writing tests afterward to "cover" it.
The tests become confirmation bias — they verify what the code does rather than
what it should do.

### Detection Heuristics

```yaml
detection:
  activity_stream:
    - pattern: "All src/ edits precede all test/ edits in the activity stream"
    - pattern: "No interleaving of test and source file edits"
  temporal:
    - rule: "If >80% of src/ edits occur before the first test/ edit → violation"
  thinking_content:
    - pattern: "Agent mentions 'now let me write tests' or 'add test coverage' after implementation"
  confidence: high
```

### Why It Matters

Test-after code frequently has untestable designs (tight coupling, hidden dependencies)
because testability wasn't a design constraint. Tests written after the fact tend to
test implementation rather than behavior.

---

## Anti-Pattern 5: The Refactor Skip (Good Enough Syndrome)

**ID**: `AP-005`
**Severity**: medium
**Phase affected**: REFACTOR phase

### Description

Skipping the REFACTOR phase entirely after GREEN. The code passes tests but contains
duplication, poor naming, or structural issues that accumulate as technical debt.

### Detection Heuristics

```yaml
detection:
  activity_stream:
    - pattern: "GREEN phase immediately followed by next RED phase (no REFACTOR)"
    - pattern: "No src/ edits between passing tests and next test creation"
  phase_tracking:
    - rule: "If rigor >= standard and zero REFACTOR phases recorded → warning"
    - rule: "If rigor >= thorough and <50% of cycles include REFACTOR → violation"
  confidence: medium
```

### Why It Matters

Skipping refactoring in early cycles means structural issues compound. Later tests
become harder to write because the code wasn't cleaned up when the context was fresh.

---

## Anti-Pattern 6: Assertion-Free Tests (The Silent Witness)

**ID**: `AP-006`
**Severity**: critical
**Phase affected**: RED_UNIT phase

### Description

Tests that execute code but don't assert anything meaningful. Tests that only check
"no exception was raised" or assert trivially true conditions.

### Detection Heuristics

```yaml
detection:
  code_analysis:
    - pattern: "Test function body has no assert statements"
    - pattern: "Only assertion is `assert True` or `assert result is not None`"
    - pattern: "Test uses `try/except` that catches and ignores all exceptions"
  file_content:
    - rule: "If test function has >5 lines of setup but <=1 assertion → warning"
    - rule: "If assertion only checks type/existence, not value/behavior → warning"
  confidence: high
```

### Why It Matters

Assertion-free tests provide false confidence. They show up in coverage reports
as "covered" but don't actually verify correct behavior. A test without meaningful
assertions is worse than no test — it creates a false sense of security.

---

## Anti-Pattern 7: Snapshot Dependence (The Brittle Record)

**ID**: `AP-007`
**Severity**: medium
**Phase affected**: RED_UNIT and RED_INTEGRATION phases

### Description

Over-reliance on snapshot testing for logic verification. Snapshots are appropriate
for UI rendering but not for business logic, data transformations, or API contracts
where explicit assertions document intent.

### Detection Heuristics

```yaml
detection:
  code_analysis:
    - pattern: "toMatchSnapshot() or assert_match_snapshot() used for non-UI code"
    - pattern: "Snapshot files larger than 100 lines for a single test"
  file_content:
    - rule: "If >50% of test assertions are snapshot-based → warning"
    - rule: "If snapshot is used for JSON API response validation → warning"
  confidence: medium
```

### Why It Matters

Snapshot tests fail on any change, including intentional ones. Developers learn to
blindly update snapshots (`-u`) without reviewing diffs, defeating the purpose of
testing. Explicit assertions document expected behavior clearly.

---

## Rigor-Based Enforcement Matrix

Which anti-patterns are enforced at each rigor level:

| Anti-Pattern | lean | standard | thorough | exhaustive |
|-------------|------|----------|----------|------------|
| AP-001: Premature Green | - | BLOCK | BLOCK | BLOCK |
| AP-002: Giant Leap | - | warn | BLOCK | BLOCK |
| AP-003: Mock Obsession | - | - | warn | BLOCK |
| AP-004: Test-After | - | BLOCK | BLOCK | BLOCK |
| AP-005: Refactor Skip | - | - | warn | BLOCK |
| AP-006: Assertion-Free | - | warn | BLOCK | BLOCK |
| AP-007: Snapshot Dependence | - | - | warn | BLOCK |

- **lean**: No anti-pattern enforcement (speed over rigor)
- **standard**: Critical anti-patterns block, others are informational
- **thorough**: Most anti-patterns enforced, some as warnings
- **exhaustive**: All anti-patterns are blocking

---

## Activity Stream Schema

The worker stop gate reads activity from `{signals_dir}/{node_id}-activity.jsonl`.
Each line is a JSON object:

```jsonl
{"t":"2026-03-17T10:00:01Z","type":"edit","file":"tests/test_auth.py","phase":"red_unit","lines_changed":12}
{"t":"2026-03-17T10:00:05Z","type":"think","summary":"Test fails as expected. Now implementing minimum code to pass."}
{"t":"2026-03-17T10:00:08Z","type":"edit","file":"src/auth.py","phase":"green","lines_changed":8}
{"t":"2026-03-17T10:00:12Z","type":"edit","file":"src/auth.py","phase":"refactor","lines_changed":4}
{"t":"2026-03-17T10:00:15Z","type":"test_run","passed":true,"phase":"refactor"}
```

### Event Types

| Type | Fields | Description |
|------|--------|-------------|
| `edit` | file, phase, lines_changed | File was modified via Edit/Write tool |
| `think` | summary | Agent reasoning between tool calls |
| `test_run` | passed, phase, test_count | Test execution result |
| `phase_transition` | from_phase, to_phase | Explicit phase change |

### Phase Values

| Phase | Meaning |
|-------|---------|
| `red_unit` | Writing a failing unit test |
| `red_integration` | Writing a failing integration test |
| `green` | Writing minimum code to pass the test |
| `refactor` | Improving code structure without changing behavior |
| `review` | Self-review and cleanup |
| `unknown` | Phase not determinable from context |
