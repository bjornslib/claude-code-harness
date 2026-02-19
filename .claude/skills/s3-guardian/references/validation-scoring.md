# Validation Scoring Methodology

Detailed methodology for independently scoring implementation work against blind acceptance tests using gradient confidence scoring (0.0-1.0).

---

## 1. Weighted Scoring Formula

The overall validation score is computed as a weighted average across all features:

```
Overall Score = SUM( feature_weight[i] * feature_score[i] )  for i in all features
```

Where:

```
feature_score[i] = AVERAGE( scenario_score[j] )  for j in scenarios of feature i
```

### Worked Example

```
Feature 1 (weight 0.30): 2 scenarios scored 0.8 and 0.7 → feature_score = 0.75
Feature 2 (weight 0.25): 1 scenario scored 0.6 → feature_score = 0.60
Feature 3 (weight 0.20): 2 scenarios scored 0.9 and 0.8 → feature_score = 0.85
Feature 4 (weight 0.15): 1 scenario scored 0.5 → feature_score = 0.50
Feature 5 (weight 0.10): 1 scenario scored 0.7 → feature_score = 0.70

Overall = (0.30 * 0.75) + (0.25 * 0.60) + (0.20 * 0.85) + (0.15 * 0.50) + (0.10 * 0.70)
        = 0.225 + 0.150 + 0.170 + 0.075 + 0.070
        = 0.690

Decision: 0.690 >= 0.60 ACCEPT threshold → ACCEPT
```

---

## 2. Decision Thresholds

### Standard Thresholds

| Range | Decision | Meaning |
|-------|----------|---------|
| >= 0.60 | ACCEPT | Implementation meets business requirements. Proceed to merge. |
| 0.40 - 0.59 | INVESTIGATE | Partial implementation. Gaps must be identified and addressed. |
| < 0.40 | REJECT | Implementation fundamentally incomplete. Restart cycle. |

### Customizing Thresholds

Thresholds are configurable per initiative in `manifest.yaml`. Adjust based on:

| Factor | Lower Thresholds | Higher Thresholds |
|--------|-----------------|-------------------|
| Initiative criticality | Prototype, exploration | Production, customer-facing |
| Time pressure | Tight deadline, MVP | No deadline pressure |
| Iteration plan | Will have follow-up sessions | This is the final session |
| Scope complexity | Small, well-defined PRD | Large, ambiguous PRD |

**Example**: A prototype pipeline might use `accept: 0.50` while a production auth system might use `accept: 0.75`.

### Threshold Configuration in Manifest

```yaml
thresholds:
  accept: 0.60      # Score >= this → ACCEPT
  investigate: 0.40  # Score >= this but < accept → INVESTIGATE
  reject: 0.40      # Score < this → REJECT (always equals investigate threshold)
```

The `reject` threshold always equals `investigate` to ensure no scoring gap exists.

---

## 3. Mapping Code Evidence to Confidence Scores

The core of independent validation is reading actual code and mapping observations to the scenario's scoring guide.

### Evidence Gathering Workflow

For each scenario in the acceptance test suite:

**Step 1: Identify what to check**

Read the scenario's "Evidence to Check" section. Translate each item into a concrete action:

```
Evidence item: "src/pipeline.py for @flow decorator"
Action: cat /path/to/impl-repo/src/pipeline.py | grep "@flow"

Evidence item: "Tests that verify retry behavior"
Action: grep -r "retry\|retries" /path/to/impl-repo/tests/

Evidence item: "Configuration loaded from external source"
Action: grep -r "os.getenv\|BaseSettings\|load_config" /path/to/impl-repo/src/
```

**Step 2: Execute evidence gathering**

```bash
# Git diff for the implementation period
git -C /path/to/impl-repo log --oneline --since="4 hours ago"
git -C /path/to/impl-repo diff HEAD~20..HEAD --stat

# Specific file examination
cat /path/to/impl-repo/src/{file}

# Function body examination
grep -A 30 "def {function_name}" /path/to/impl-repo/src/{file}

# Import verification (is the module actually used?)
grep -r "from {module} import\|import {module}" /path/to/impl-repo/src/

# Test examination
cat /path/to/impl-repo/tests/test_{module}.py

# Test execution (if available and safe)
cd /path/to/impl-repo && python -m pytest tests/test_{module}.py -v --tb=short 2>&1
```

**Step 3: Map observations to scoring guide**

Read the scenario's "Confidence Scoring Guide" and find the closest match:

```
Observation: pipeline.py exists, has @flow decorator on main(),
             orchestrates 4 @task functions, parameters are typed,
             but no docstring on the flow function.

Scoring guide reference:
  0.8 — @flow orchestrates 3+ tasks with proper parameter passing
  1.0 — @flow is well-structured, typed parameters, docstring, 3+ tasks with dependencies

Score: 0.85 (between 0.8 and 1.0 — typed parameters push above 0.8, missing docstring prevents 1.0)
```

**Step 4: Check for red flags**

Read the scenario's "Red Flags" section. For each red flag, check whether it applies:

```
Red flag: "@flow decorator on an empty function"
Check: cat /path/to/impl-repo/src/pipeline.py | grep -A 5 "@flow"
Result: Function body has 40+ lines of real logic → Red flag NOT triggered

Red flag: "Tasks defined but never called from the flow"
Check: grep "@task" src/pipeline.py, then check if task names appear in the flow body
Result: All 4 tasks are called within the flow → Red flag NOT triggered
```

If a red flag IS triggered, apply the severity penalty from the gherkin-test-patterns reference:
- Minor red flag: -0.05 to -0.10
- Moderate red flag: -0.10 to -0.20
- Major red flag: -0.20 to -0.40
- Critical red flag: cap score at 0.3

---

## 4. Cross-Referencing Claims vs Actual Git Diff

Operators may claim completion of features that are only partially implemented. Cross-referencing is essential.

### Claim Sources

| Source | Reliability | Use For |
|--------|------------|---------|
| Git diff (actual code changes) | High | Ground truth of what was modified |
| Git commit messages | Medium | Intent, but may be optimistic |
| Orchestrator progress log | Low | Self-reported, often inflated |
| Worker completion messages | Low | Worker scope may not match feature scope |
| Test results (if run independently) | High | Objective pass/fail |
| `cs-promise --meet` evidence | Medium | Claimed evidence, verify independently |

### Cross-Reference Protocol

1. **Read the git diff**: What files actually changed? What was added vs modified?

```bash
# Summary of all changes
git -C /path/to/impl-repo diff HEAD~N..HEAD --stat

# Detailed changes in specific files
git -C /path/to/impl-repo diff HEAD~N..HEAD -- src/pipeline.py

# Show each commit individually
git -C /path/to/impl-repo log --oneline HEAD~N..HEAD
```

2. **Compare claims to reality**:

```
Claim: "Implemented retry logic with exponential backoff"
Git diff: Added `retries=3` to @task decorator, no custom retry handler
Reality: Basic retry, NOT exponential backoff
Score adjustment: Reduce from claimed 0.8 to actual 0.5
```

3. **Look for phantom features**: Features mentioned in commit messages or logs that do not appear in the actual diff.

```bash
# Check commit messages for feature claims
git -C /path/to/impl-repo log --oneline HEAD~N..HEAD | grep -iE "implement|add|feature"

# Cross-reference: do the claimed files actually exist and contain real code?
for file in $(git -C /path/to/impl-repo diff HEAD~N..HEAD --name-only); do
    wc -l /path/to/impl-repo/$file
done
```

---

## 5. What Constitutes "Independent" Validation

The guardian pattern's value comes from independence. Validation is only independent if:

### Independent Means

- Reading source code files directly (not orchestrator summaries)
- Running tests independently (not trusting "all tests pass" claims)
- Checking git diff for actual changes (not commit message descriptions)
- Evaluating against a rubric the operator never saw (blind testing)
- Scoring based on evidence, not on effort or time spent

### Independent Does NOT Mean

- Asking the operator if the feature is done
- Reading the operator's progress log and taking it at face value
- Trusting `cs-promise --meet` evidence without verifying the evidence itself
- Counting commit messages as proof of implementation
- Assuming tests pass because the operator said they do

### The Independence Test

Before recording a score, ask: "Could I arrive at this score WITHOUT any information from the operator?" If the answer is no, the validation is not independent. Gather more direct evidence.

---

## 6. Scoring Worksheet Template

Use this template for each validation session:

```markdown
# Validation Worksheet: PRD-{ID}

## Session Metadata
- Guardian session started: {timestamp}
- Operator session: s3-{initiative}
- Implementation repo: {path}
- Monitoring duration: {hours}
- Interventions performed: {count}

## Feature Scoring

### Feature: {F1 Name} (weight: {0.XX})

**Scenario: {scenario_name}**
- Evidence gathered:
  - {file}: {what was observed}
  - {test}: {results}
- Red flags:
  - {flag}: {triggered/not triggered}
- Score: {0.X}
- Rationale: {why this score}

**Feature Score**: {average of scenario scores}
**Weighted Contribution**: {feature_score * weight}

### Feature: {F2 Name} (weight: {0.XX})
...

## Summary

| Feature | Weight | Score | Weighted |
|---------|--------|-------|----------|
| F1 | {w} | {s} | {w*s} |
| F2 | {w} | {s} | {w*s} |
| ... | ... | ... | ... |
| **Total** | **1.00** | - | **{sum}** |

## Decision

- Overall Score: {X.XX}
- ACCEPT threshold: {from manifest}
- **Decision: {ACCEPT | INVESTIGATE | REJECT}**

## Gaps Identified
1. {gap}
2. {gap}

## Red Flags Triggered
1. {flag} — severity: {minor/moderate/major/critical} — impact: -{0.XX}

## Recommendations
- {next steps}
```

---

## 7. Storing Validation Results

After completing the scoring worksheet, store results in two locations.

### Hindsight — Private Bank (Guardian Learnings)

```python
mcp__hindsight__retain(
    content=f"""
    ## Guardian Validation: PRD-{prd_id}

    ### Result
    - Decision: {verdict}
    - Overall Score: {score}
    - Date: {timestamp}
    - Duration: {monitoring_duration}

    ### Feature Breakdown
    {feature_score_table}

    ### Key Gaps
    {gaps_list}

    ### Red Flags Triggered
    {red_flags_list}

    ### Lessons for Future Guardians
    - {lesson_1}
    - {lesson_2}

    ### Scoring Calibration Notes
    - {any adjustments to scoring guides for future use}
    """,
    context="s3-guardian-validations",
    bank_id="system3-orchestrator"
)
```

### Hindsight — Project Bank (Team Awareness)

```python
mcp__hindsight__retain(
    content=f"""
    PRD-{prd_id} Guardian Validation: {verdict} (score: {score})

    Features validated: {feature_count}
    Gaps found: {gap_count}
    Recommendations: {summary}
    """,
    context="project-validations",
    bank_id="claude-code-{project}"
)
```

### When to Store

- **ACCEPT**: Store immediately. Include positive patterns for future reference.
- **INVESTIGATE**: Store gaps and the investigation plan. Update after gaps are addressed.
- **REJECT**: Store failure analysis. Include anti-patterns to avoid.

---

## 8. Handling Edge Cases

### Feature Not Attempted

If a feature shows zero evidence of implementation (score 0.0), it receives its full weight as a penalty. A PRD with one critical feature (weight 0.30) completely missing will score at most 0.70.

### Feature Over-Implemented

If a feature exceeds PRD requirements, score it at 1.0 (the maximum). Do not award bonus points. The purpose of validation is to verify PRD compliance, not to reward over-engineering.

### Ambiguous Evidence

If evidence is unclear — the implementation exists but its correctness is uncertain without running it:

1. Default to the lower score in the ambiguous range
2. Note the ambiguity in the rationale
3. If the ambiguity affects the overall decision (score is near a threshold), attempt to resolve it by running the code or tests

### Operator Claims Not In PRD

If the operator implemented features not in the PRD, ignore them for scoring purposes. They do not increase or decrease the score. Note them in the validation report as "out of scope additions" for the oversight team's awareness.

### Tests Exist But Fail

If tests exist but fail when run independently:

- The test file existing is evidence of intent (worth 0.1-0.2)
- Failing tests indicate incomplete implementation (cap at 0.4 for the scenario)
- The failure reason matters: import error (0.2), assertion error (0.3), timeout (0.3)

### No Test Suite Available

If the implementation has no tests:

- This is NOT automatic failure — the scoring guide for each scenario defines what constitutes each score level
- Absence of tests typically limits a scenario to 0.5-0.6 maximum (functional but unverified)
- Exception: if the scoring guide explicitly requires tests for scores above 0.5, honor that

---

## 9. Calibration Over Time

Scoring calibration improves with experience. After each validation session:

1. **Review scoring decisions**: Were any scores surprisingly high or low in retrospect?
2. **Compare with operator claims**: Where did the guardian and operator most disagree?
3. **Adjust scoring guides**: If a scoring level description was misleading, update it for future use
4. **Update thresholds**: If the standard thresholds consistently produce wrong decisions, adjust per-domain

### Calibration Signals

| Signal | Meaning | Action |
|--------|---------|--------|
| ACCEPT but implementation has obvious bugs | Thresholds too low or scoring too generous | Raise ACCEPT threshold or recalibrate scoring guides |
| REJECT but implementation is actually solid | Scoring too strict or evidence gathering incomplete | Lower thresholds or expand evidence sources |
| INVESTIGATE frequently with no resolution | Threshold range too wide | Narrow the investigate band |
| All features score 0.7-0.8 | Scoring guides may be too coarse | Add more granularity to the 0.6-1.0 range |

Store calibration notes in Hindsight for future guardian sessions to reference.

---

**Reference Version**: 0.1.0
**Parent Skill**: s3-guardian
