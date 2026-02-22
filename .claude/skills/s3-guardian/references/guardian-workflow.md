---
title: "Guardian Workflow"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Guardian Workflow — End-to-End Reference

Complete workflow for the S3 Guardian pattern, from pre-flight checks through post-validation actions.

---

## 1. Pre-Flight Checks

Before beginning a guardian session, verify all prerequisites are met.

### 1.1 Environment Verification

```bash
# Verify config repo (where acceptance tests will live)
ls -la acceptance-tests/ 2>/dev/null || echo "Directory will be created"

# Verify implementation repo is accessible
ls -la /path/to/impl-repo/.taskmaster/docs/ 2>/dev/null || echo "ERROR: impl repo not found"

# Verify tmux is available
tmux -V

# Verify cs-promise CLI is available
cs-status 2>/dev/null || echo "ERROR: completion-state scripts not found"

# Verify ccsystem3 function is available
which ccsystem3 2>/dev/null || type ccsystem3 2>/dev/null
```

### 1.2 PRD Verification

```bash
# Check PRD exists
cat /path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md | head -50

# Extract PRD metadata
grep -E "^#|^##|acceptance|criteria|epic|feature" /path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md
```

### 1.3 Conflict Checks

```bash
# No existing tmux session with same name
tmux has-session -t "s3-{initiative}" 2>/dev/null && echo "WARNING: session exists" || echo "OK: no conflict"

# No existing acceptance tests (or confirm overwrite intent)
ls acceptance-tests/PRD-{ID}/ 2>/dev/null && echo "WARNING: tests exist, will be overwritten" || echo "OK: fresh"

# No stale completion state
cs-status 2>/dev/null | grep -i "pending\|in_progress"
```

### 1.4 Hindsight Context Gathering

Before creating acceptance tests, gather institutional knowledge about the initiative:

```python
# Check for previous guardian sessions on this PRD
previous = mcp__hindsight__reflect(
    f"Previous guardian validations for PRD-{prd_id} or similar initiatives",
    budget="mid",
    bank_id="system3-orchestrator"
)

# Check for known patterns in the implementation domain
domain_patterns = mcp__hindsight__reflect(
    f"Development patterns and anti-patterns for {domain}",
    budget="mid",
    bank_id="claude-code-{project}"
)
```

Use findings to calibrate acceptance test expectations and thresholds.

---

## 2. Acceptance Test Generation

### 2.1 Read and Analyze PRD

Read the entire PRD document. Extract a structured feature list:

```
Feature Extraction Template:
---
PRD: PRD-{ID}
Title: {PRD title}
Epics: {number of epics}

Features:
  - F1: {name} — {description} — Weight: {0.XX}
  - F2: {name} — {description} — Weight: {0.XX}
  ...

Total Weight Check: {sum} (must equal 1.00)
```

### 2.2 Determine Feature Weights

Weight assignment follows business criticality, not implementation complexity:

**Weight Calibration Process**:

1. Rank all features by "what breaks if this is missing?"
2. Assign the top feature 0.25-0.35 weight
3. Distribute remaining weight proportionally
4. Verify sum equals 1.00
5. Sanity check: would a product owner agree with this ranking?

**Common Mistakes**:
- Giving infrastructure features (logging, config) high weight — these rarely fail business validation
- Equal weights across all features — this dilutes the signal from core features
- Forgetting to account for cross-cutting concerns (error handling touches many features)

### 2.3 Write Gherkin Scenarios

For each feature, write 1-3 Gherkin scenarios. The number of scenarios depends on feature complexity:

| Feature Complexity | Scenarios |
|-------------------|-----------|
| Simple (single behavior) | 1 scenario |
| Medium (2-3 behaviors) | 2 scenarios |
| Complex (multiple states/paths) | 3 scenarios |

Each scenario follows this template:

```gherkin
  Scenario: {Descriptive name}
    Given {precondition — what must exist before testing}
    When {action — what the implementation should do}
    Then {outcome — what should be verifiable}

    # Confidence Scoring Guide:
    # 0.0 — {what total absence looks like}
    # 0.3 — {what partial/broken implementation looks like}
    # 0.5 — {what basic but incomplete implementation looks like}
    # 0.7 — {what solid implementation with minor gaps looks like}
    # 1.0 — {what complete, production-quality implementation looks like}
    #
    # Evidence to Check:
    #   - {specific file or function to examine}
    #   - {specific test to look for}
    #   - {specific behavior to verify}
    #
    # Red Flags:
    #   - {indicator of false or inflated claims}
    #   - {common shortcut that appears complete but isn't}
```

### 2.4 Create Manifest

Generate the manifest using the template script:

```bash
.claude/skills/s3-guardian/scripts/generate-manifest.sh PRD-{ID} "PRD Title"
```

Then populate the generated `manifest.yaml` with:
- Feature names, descriptions, and weights
- Scoring thresholds (ACCEPT, INVESTIGATE, REJECT)
- Validation protocol (which evidence sources to use)
- Implementation repo path

### 2.5 Verification of Test Quality

Before proceeding to meta-orchestrator spawning, verify acceptance test quality:

1. **Coverage check**: Every PRD feature has at least one scenario
2. **Weight sum**: Exactly 1.00
3. **Scoring guides**: Every scenario has a 0.0-1.0 calibration guide
4. **Evidence specificity**: Each scenario references concrete files or behaviors, not vague descriptions
5. **Red flag inclusion**: Every scenario has at least one red flag indicator

---

## 3. Meta-Orchestrator Spawning Sequence

### 3.1 Create Guardian Session Promise

Before spawning the meta-orchestrator, create the guardian's own session promise:

```bash
cs-init

cs-promise --create "Guardian: Validate PRD-{ID} implementation" \
    --ac "Acceptance tests created and stored in config repo" \
    --ac "S3 meta-orchestrator spawned and verified running" \
    --ac "Meta-orchestrator progress monitored through completion" \
    --ac "Independent validation scored against rubric" \
    --ac "Final verdict delivered with evidence"

cs-promise --start <promise-id>
```

### 3.2 Spawn Meta-Orchestrator

Execute the spawn sequence with proper error handling:

```bash
# Step 1: Create tmux session at implementation repo
tmux new-session -d -s "s3-{initiative}" -c "/path/to/impl-repo"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create tmux session"
    exit 1
fi

# Step 2: Unset CLAUDECODE (prevents nested session error)
tmux send-keys -t "s3-{initiative}" "unset CLAUDECODE"
tmux send-keys -t "s3-{initiative}" Enter
sleep 1

# Step 3: Launch ccsystem3
tmux send-keys -t "s3-{initiative}" "ccsystem3"
tmux send-keys -t "s3-{initiative}" Enter

# Step 4: Wait for initialization
sleep 15

# Step 5: Set output style for System 3 meta-orchestrator
tmux send-keys -t "s3-{initiative}" "/output-style system3-meta-orchestrator"
tmux send-keys -t "s3-{initiative}" Enter
sleep 3

# Step 6: Verify output style loaded
PANE_OUTPUT=$(tmux capture-pane -t "s3-{initiative}" -p -S -30)
echo "$PANE_OUTPUT" | grep -iE "system3-meta-orchestrator"
if [ $? -ne 0 ]; then
    echo "WARNING: Output style may not have loaded. Check manually."
fi
```

### 3.3 Send Initial Instructions

After verification, send the meta-orchestrator its mission:

```bash
# Construct the instruction payload
INSTRUCTION="You are the System 3 meta-orchestrator. Invoke Skill('system3-orchestrator') first. Then read PRD-{ID} at .taskmaster/docs/PRD-{ID}.md. Parse tasks with Task Master. Spawn orchestrators as needed. Report when all epics are complete."

# Send via tmux (text first, then Enter separately)
tmux send-keys -t "s3-{initiative}" "$INSTRUCTION"
sleep 2  # Large pastes need time for bracketed paste processing
tmux send-keys -t "s3-{initiative}" Enter
```

### 3.4 Session Resume (Alternative)

If resuming a previous meta-orchestrator session:

```bash
# Check if the session supports resume
tmux capture-pane -t "s3-{initiative}" -p -S -20 | grep -i "resume\|continue\|previous"

# Send resume command
tmux send-keys -t "s3-{initiative}" "/resume"
tmux send-keys -t "s3-{initiative}" Enter
sleep 5

# Verify resumed successfully
tmux capture-pane -t "s3-{initiative}" -p -S -20 | grep -iE "resumed|continuing|loaded"
```

### 3.5 Meet Spawn Acceptance Criteria

```bash
cs-promise --meet <id> --ac-id AC-2 --evidence "tmux session s3-{initiative} created, ccsystem3 launched, output style verified" --type manual
```

---

## 4. Monitoring Loop

### 4.1 Enter Monitoring State

Once the meta-orchestrator is confirmed running, enter the monitoring loop:

```
MONITORING LOOP:
  |
  +-- Capture tmux output
  |
  +-- Scan for signals
  |     |
  |     +-- AskUserQuestion → Intervene
  |     +-- Error pattern → Assess
  |     +-- Completion claim → Validate (Phase 4)
  |     +-- Normal work → Continue
  |
  +-- Check context percentage
  |     |
  |     +-- Above 80% → Expect auto-compact
  |     +-- Above 90% → Consider intervention
  |
  +-- Sleep (cadence-dependent)
  |
  +-- [REPEAT]
```

### 4.2 Cadence Adaptation

Adjust monitoring frequency based on what the meta-orchestrator is doing:

```bash
# Check meta-orchestrator activity
OUTPUT=$(tmux capture-pane -t "s3-{initiative}" -p -S -30)

# Determine cadence
if echo "$OUTPUT" | grep -qiE "edit|write|commit|test"; then
    CADENCE=30   # Active implementation — check frequently
elif echo "$OUTPUT" | grep -qiE "read|grep|analyze|plan"; then
    CADENCE=60   # Investigation phase — less frequent
elif echo "$OUTPUT" | grep -qiE "sleep|wait|idle|background"; then
    CADENCE=120  # Waiting for workers — infrequent
else
    CADENCE=60   # Default
fi

sleep $CADENCE
```

### 4.3 Intervention Protocol

When intervention is needed, follow this decision tree:

1. **AskUserQuestion / Permission Dialog**:
   - Check what is being asked
   - If it is a routine permission (file access, tool use): approve via Down/Enter
   - If it is a strategic question: answer based on PRD scope

2. **Repeated Errors**:
   - Count occurrences of the same error pattern
   - After 3 occurrences: send corrective guidance via tmux
   - After 5 occurrences: consider killing and restarting the session

3. **Scope Creep**:
   - Compare current work against PRD scope
   - If meta-orchestrator is working on unrelated features: send correction
   - If meta-orchestrator is over-engineering: remind of scope boundaries

4. **Time Limits**:
   - Typical initiative: 1-3 hours for implementation
   - At 2 hours: check progress percentage
   - At 3 hours: seriously consider partial completion + validation

### 4.4 Meet Monitoring Acceptance Criteria

When the meta-orchestrator signals completion (or time limit is reached):

```bash
cs-promise --meet <id> --ac-id AC-3 --evidence "Monitored s3-{initiative} for {duration}, {intervention_count} interventions performed" --type manual
```

---

## 5. Validation Cycle

### 5.1 Load Acceptance Rubric

```bash
# Read manifest
cat acceptance-tests/PRD-{ID}/manifest.yaml

# Read all feature files
cat acceptance-tests/PRD-{ID}/*.feature
```

### 5.2 Independent Evidence Gathering

For each feature in the manifest, gather evidence independently:

```bash
# Git history for the implementation period
git -C /path/to/impl-repo log --oneline --since="3 hours ago"
git -C /path/to/impl-repo show --stat HEAD~15..HEAD

# Specific file examination
cat /path/to/impl-repo/src/{file_referenced_in_scenario}

# Test results (if test suite exists)
cd /path/to/impl-repo && python -m pytest --tb=short -q 2>&1

# Import/dependency verification
grep -r "import\|from\|require" /path/to/impl-repo/src/ | grep "{expected_dependency}"
```

### 5.3 Score Each Scenario

For each Gherkin scenario, assign a confidence score using the scenario's scoring guide:

```
Scoring Worksheet:
---
Feature: F1 — {name} (weight: 0.30)
  Scenario 1: {name}
    Evidence found: {what was actually observed}
    Red flags detected: {any red flags from the guide}
    Score: 0.X
    Rationale: {why this score, not higher/lower}

  Scenario 2: {name}
    Evidence found: {what was actually observed}
    Red flags detected: {any red flags from the guide}
    Score: 0.X
    Rationale: {why this score, not higher/lower}

  Feature Score: average(scenario scores) = 0.XX
  Weighted Contribution: 0.XX * 0.30 = 0.XXX

Feature: F2 — {name} (weight: 0.20)
  ...

TOTAL WEIGHTED SCORE: sum(weighted contributions) = 0.XXX
```

### 5.4 Make Decision

Compare the total weighted score against manifest thresholds:

```
Score: 0.XXX
ACCEPT threshold: 0.60
INVESTIGATE range: 0.40-0.59
REJECT threshold: < 0.40

DECISION: {ACCEPT | INVESTIGATE | REJECT}
```

### 5.5 Report Generation

Generate a structured validation report:

```markdown
# Guardian Validation Report: PRD-{ID}

## Summary
- **Decision**: {ACCEPT | INVESTIGATE | REJECT}
- **Weighted Score**: {0.XX} / 1.00
- **Implementation Duration**: {time}
- **Interventions**: {count}

## Feature Scores

| Feature | Weight | Score | Weighted | Notes |
|---------|--------|-------|----------|-------|
| F1: {name} | 0.30 | 0.80 | 0.240 | {brief note} |
| F2: {name} | 0.20 | 0.65 | 0.130 | {brief note} |
| ... | ... | ... | ... | ... |
| **Total** | **1.00** | - | **0.XXX** | |

## Gaps Identified
1. {gap description with affected feature}
2. {gap description with affected feature}

## Red Flags Detected
1. {red flag and its implications}

## Recommendations
- {next steps based on decision}
```

---

## 6. Post-Validation Actions

### 6.1 ACCEPT Path

```bash
# Meet validation acceptance criteria
cs-promise --meet <id> --ac-id AC-4 --evidence "Weighted score: 0.XX, above ACCEPT threshold 0.60" --type manual
cs-promise --meet <id> --ac-id AC-5 --evidence "ACCEPT verdict delivered, report stored" --type manual

# Store to Hindsight
# (see SKILL.md "Storing Validation Results" section)

# Verify guardian promise is complete
cs-verify --check --verbose
```

### 6.2 INVESTIGATE Path

```bash
# Identify specific gaps that need attention
# Create a targeted follow-up plan
# Optionally spawn a new meta-orchestrator session focused on gaps

# Do NOT meet AC-4 yet — investigation is not acceptance
# Log the gaps for tracking
cs-verify --log --action "INVESTIGATE verdict for PRD-{ID}" --outcome "partial" \
    --learning "Gaps found in: {feature_list}"
```

### 6.3 REJECT Path

```bash
# Document specific failures
# Store anti-patterns to Hindsight
# Plan full reimplementation cycle

cs-verify --log --action "REJECT verdict for PRD-{ID}" --outcome "failed" \
    --learning "Critical failures in: {feature_list}. Score: {0.XX}"
```

### 6.4 Meta-Orchestrator Cleanup

After validation is complete (regardless of verdict):

```bash
# Check if meta-orchestrator session is still running
tmux has-session -t "s3-{initiative}" 2>/dev/null

# If running and verdict is ACCEPT — let it finish naturally or send shutdown
tmux send-keys -t "s3-{initiative}" "All work validated. You may finalize and exit."
sleep 2
tmux send-keys -t "s3-{initiative}" Enter

# If running and verdict is REJECT — send correction
tmux send-keys -t "s3-{initiative}" "Guardian validation REJECTED. Gaps: {summary}. Address these issues."
sleep 2
tmux send-keys -t "s3-{initiative}" Enter
```

---

## 7. Timeline Reference

Typical guardian session timeline for a medium-complexity PRD:

| Phase | Duration | Activities |
|-------|----------|------------|
| Pre-flight | 5 min | Environment checks, Hindsight queries |
| Acceptance test creation | 15-30 min | PRD analysis, Gherkin writing, manifest creation |
| Meta-orchestrator spawning | 2-5 min | tmux setup, ccsystem3 launch, verification |
| Monitoring | 1-3 hours | Continuous oversight, periodic interventions |
| Independent validation | 15-30 min | Evidence gathering, scoring, report generation |
| Post-validation | 5-10 min | Hindsight storage, cleanup, promise completion |
| **Total** | **1.5-4 hours** | |

---

**Reference Version**: 0.1.0
**Parent Skill**: s3-guardian
