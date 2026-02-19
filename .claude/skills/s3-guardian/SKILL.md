---
name: s3-guardian
description: This skill should be used when System 3 needs to act as an independent guardian angel — spawning System 3 operators in tmux, creating blind Gherkin acceptance tests from PRDs, monitoring operator progress, independently validating claims against acceptance criteria using gradient confidence scoring (0.0-1.0), and setting session promises. Use when asked to "spawn and monitor a system3 operator", "create acceptance tests for a PRD", "validate orchestrator claims", "act as guardian angel", or "independently verify implementation work".
version: 0.1.0
title: "S3 Guardian"
status: active
---

# S3 Guardian — Independent Validation Pattern

The guardian angel pattern provides independent, blind validation of System 3 operator work. A guardian session creates acceptance tests from PRDs, stores them outside the implementation repo where operators cannot see them, spawns and monitors S3 operators in tmux, and independently validates claims against a gradient confidence rubric.

```
Guardian (this session, config repo)
    |
    |-- Creates blind Gherkin acceptance tests (stored here, NOT in impl repo)
    |-- Spawns S3 Operator in tmux (at impl repo)
    |       |
    |       +-- Orchestrators (spawned by operator)
    |       |       +-- Workers
    |       |
    |       +-- s3-communicator (heartbeat)
    |
    |-- Monitors operator progress via tmux capture-pane
    |-- Independently validates claims against rubric
    |-- Reports to oversight team with gradient scores
```

**Key Innovation**: Acceptance tests live in `claude-harness-setup/acceptance-tests/PRD-{ID}/`, NOT in the implementation repository. Operators and their workers never see the rubric. This enables truly independent validation — the guardian reads actual code and scores it against criteria the implementers did not have access to.

---

## Guardian Disposition: Skeptical Curiosity

The guardian operates with a specific mindset that distinguishes it from passive monitoring.

### Be Skeptical

- **Never trust self-reported success.** Operators and orchestrators naturally over-report progress. Read the actual code, run the actual tests, check the actual logs.
- **Question surface-level explanations.** When an operator says "X is blocked by Y," independently verify that Y is truly the blocker — and that Y cannot be resolved.
- **Assume incompleteness until proven otherwise.** A task marked "done" is "claimed done" until the guardian scores it against the blind rubric.
- **Watch for rationalization patterns.** "It's a pre-existing issue" may be true, but ask: Is it solvable? Would solving it advance the goal? If yes, push for resolution.

### Be Curious

- **Investigate root causes, not symptoms.** When a Docker container crashes, don't stop at the error message — trace the import chain, read the Dockerfile, understand WHY it fails.
- **Ask "what else?"** When one fix lands, ask what it unlocked. When a test passes, ask what it doesn't cover. When a feature works, ask about edge cases.
- **Cross-reference independently.** Read the PRD, then read the code, then read the tests. Do they tell the same story? Gaps between these three are where bugs live.
- **Follow your intuition.** If something feels incomplete or too easy, it probably is. Dig deeper.

### Push for Completion

- **Reject premature fallbacks.** When an operator says "let's skip the E2E test and merge as-is," challenge that. Is the E2E blocker actually hard to fix? Often a 1-line Dockerfile fix unblocks the entire test.
- **Advocate for the user's actual goal.** The user didn't ask for "most of the pipeline" — they asked for the pipeline. Push operators toward full completion.
- **Guide, don't just observe.** When the guardian identifies a root cause (e.g., missing COPY in Dockerfile), send that finding to the operator as actionable guidance rather than noting it passively.
- **Set higher bars progressively.** As the team demonstrates capability, raise expectations. Don't accept the same quality level that was acceptable in sprint 1.

### Injecting Disposition Into Operators

When spawning or guiding S3 operators, include disposition guidance in prompts:

```
Be curious about failures — trace root causes, don't accept surface explanations.
When something is "blocked," investigate whether the blocker is solvable.
Push for complete solutions over workarounds. The user wants the real thing.
```

This disposition transfers from guardian to operator to orchestrator to worker, creating a culture of thoroughness throughout the agent hierarchy.

---

## Phase 1: Acceptance Test Creation

Generate blind Gherkin-style acceptance tests from PRDs before any implementation begins.

### Step 1: Read the PRD

Locate and read the PRD document from the implementation repository. Extract:
- Feature list with descriptions
- Acceptance criteria (if specified)
- Scope boundaries (IN/OUT)
- Technical constraints
- Dependencies

```bash
# Read PRD from the implementation repo
cat /path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md
```

### Step 2: Extract Weighted Features

Identify every testable feature. Assign weights based on business criticality:

| Weight | Meaning | Example |
|--------|---------|---------|
| 0.30+ | Core feature, initiative fails without it | Pipeline execution engine |
| 0.15-0.29 | Important feature, degrades experience | Error handling, retry logic |
| 0.05-0.14 | Supporting feature, nice to have | Logging, configuration |
| < 0.05 | Polish, documentation | README, inline comments |

Weights across all features MUST sum to 1.0.

### Step 3: Write Gherkin Scenarios

For each feature, write one or more Gherkin scenarios with confidence scoring guides. Each scenario includes:
- `Given` / `When` / `Then` clauses
- Confidence scoring guide (what 0.0 vs 0.5 vs 1.0 looks like)
- Evidence to check (specific files, functions, tests)
- Red flags (indicators of incomplete or false claims)

See [references/gherkin-test-patterns.md](references/gherkin-test-patterns.md) for syntax, calibration, and a complete example.

### Step 4: Generate Manifest

Create the directory structure and manifest:

```bash
# Use the template generator
.claude/skills/s3-guardian/scripts/generate-manifest.sh PRD-{ID} "PRD Title"
```

Then populate `manifest.yaml` with features, weights, and thresholds. Populate `scenarios.feature` with the Gherkin scenarios.

**Storage location**: `acceptance-tests/PRD-{ID}/` in the config repo (claude-harness-setup), never in the implementation repo.

See [references/gherkin-test-patterns.md](references/gherkin-test-patterns.md) for the manifest schema and scoring thresholds.

---

## Phase 2: S3 Operator Spawning

Spawn a System 3 operator in a tmux session pointed at the implementation repository.

### Pre-flight Checks

Before spawning, verify:
- [ ] Implementation repo exists and is accessible
- [ ] PRD exists in the implementation repo
- [ ] Acceptance tests have been created (Phase 1 complete)
- [ ] No existing tmux session with the same name
- [ ] Session promise created for the guardian session itself

### Spawn Sequence

```bash
# 1. Create tmux session at the implementation repo
tmux new-session -d -s "s3-{initiative}" -c "/path/to/impl-repo"

# 2. CRITICAL: Unset CLAUDECODE to prevent nested session error
tmux send-keys -t "s3-{initiative}" "unset CLAUDECODE"
tmux send-keys -t "s3-{initiative}" Enter

# 3. Launch ccsystem3
tmux send-keys -t "s3-{initiative}" "ccsystem3"
tmux send-keys -t "s3-{initiative}" Enter

# 4. Wait for initialization (15 seconds minimum)
sleep 15

# 5. Verify output style loaded
tmux capture-pane -t "s3-{initiative}" -p -S -50 | grep -i "system3\|meta-orchestrator\|output.style"
```

After verification, either resume a previous session or send fresh instructions:

```bash
# Option A: Resume previous session
tmux send-keys -t "s3-{initiative}" "/resume"
tmux send-keys -t "s3-{initiative}" Enter

# Option B: Fresh instructions
tmux send-keys -t "s3-{initiative}" "Your mission: implement PRD-{ID}. Read the PRD at .taskmaster/docs/PRD-{ID}.md and begin."
sleep 2
tmux send-keys -t "s3-{initiative}" Enter
```

See [references/guardian-workflow.md](references/guardian-workflow.md) for the complete spawn sequence with error handling.

---

## Phase 3: Monitoring

Continuously monitor operator progress via tmux. Monitoring cadence adapts to activity level.

### Monitoring Cadence

| Phase | Interval | Rationale |
|-------|----------|-----------|
| Active implementation | 30s | Catch errors early, detect AskUserQuestion blocks |
| Investigation/planning | 60s | Operator is reading/thinking, less likely to block |
| Idle / waiting for workers | 120s | Nothing to intervene on |

### Core Monitoring Loop

```bash
# Capture recent output
tmux capture-pane -t "s3-{initiative}" -p -S -100

# Check for key signals
tmux capture-pane -t "s3-{initiative}" -p -S -100 | grep -iE "error|stuck|complete|failed|AskUser|permission"
```

### Intervention Triggers

| Signal | Action |
|--------|--------|
| `AskUserQuestion` / permission dialog | Answer via `tmux send-keys` (Down, Enter) |
| Repeated error (3+ occurrences) | Send guidance or restart |
| No output for 5+ minutes | Check if context is exhausted |
| Scope creep (unrelated work) | Send corrective instruction |
| `TODO` / `FIXME` markers accumulating | Flag for later cleanup |
| Time exceeded (2+ hours) | Assess progress, consider intervention |

### Communication Hierarchy (CRITICAL)

The Guardian monitors BOTH the S3 operator AND its orchestrators, but MUST route corrections through the S3 operator:

```
Guardian ──monitors──► S3 Operator ──delegates──► Orchestrator ──delegates──► Workers
   │                       ▲                          ▲
   │                       │                          │
   └──── sends guidance ───┘                          │
   └──── monitors (read-only) ────────────────────────┘
```

| Action | Target | When |
|--------|--------|------|
| Send guidance/corrections | S3 Operator session | Always (primary communication channel) |
| Monitor output (read-only) | Both S3 + Orchestrator | Continuous (for awareness) |
| Direct orchestrator injection | Orchestrator session | **Last resort only** — when S3 operator is compacting/stuck |
| Answer AskUserQuestion | Whichever session shows the dialog | Immediately (blocks are time-critical) |

**Anti-pattern**: Sending implementation guidance directly to the orchestrator bypasses the S3 operator's context and coordination. The S3 operator needs to know what guidance was given to maintain coherent oversight.

**Exception**: When the S3 operator is at <5% context and actively compacting, the Guardian may inject time-critical corrections directly into the orchestrator to prevent wrong work from being committed.

### AskUserQuestion Handling

When the operator or a worker hits an AskUserQuestion dialog:

```bash
# Navigate to the appropriate option and confirm
tmux send-keys -t "s3-{initiative}" Down
tmux send-keys -t "s3-{initiative}" Enter
```

See [references/monitoring-patterns.md](references/monitoring-patterns.md) for the complete monitoring command reference and red flag patterns.

---

## Phase 4: Independent Validation

After the operator claims completion, independently validate all work against the blind acceptance rubric.

### Validation Protocol

1. **Read the acceptance manifest**: Load `acceptance-tests/PRD-{ID}/manifest.yaml` and the `.feature` files
2. **Read the actual code**: Navigate the implementation repo independently — examine git diffs, file contents, test results
3. **Score each scenario**: Assign a confidence score (0.0 to 1.0) per Gherkin scenario
4. **Compute weighted total**: Multiply each scenario score by its feature weight, sum across all features
5. **Decide**: Compare the weighted total against the manifest thresholds

### Decision Thresholds

| Weighted Score | Decision | Action |
|----------------|----------|--------|
| >= 0.60 | ACCEPT | Report to oversight team, proceed to merge |
| 0.40 - 0.59 | INVESTIGATE | Identify gaps, plan targeted follow-up session |
| < 0.40 | REJECT | Document failures, restart implementation cycle |

Thresholds are configurable per initiative in `manifest.yaml`.

### Evidence Gathering

```bash
# Check what actually changed
git -C /path/to/impl-repo show --stat HEAD~10..HEAD

# Look for specific implementations
grep -r "function_name\|class_name" /path/to/impl-repo/src/

# Read actual function bodies
cat /path/to/impl-repo/src/module.py

# Run tests independently (if test suite exists)
cd /path/to/impl-repo && pytest --tb=short 2>&1 | tail -20
```

**Critical principle**: Read the code directly. Do NOT trust orchestrator self-reports, progress logs, or status messages. The entire point of the guardian pattern is independent verification.

See [references/validation-scoring.md](references/validation-scoring.md) for the scoring methodology and evidence mapping.

---

## Session Promise Integration

The guardian session itself tracks completion via the `cs-promise` CLI.

### At Guardian Session Start

```bash
# Initialize completion state
cs-init

# Create guardian promise
cs-promise --create "Guardian: Validate PRD-{ID} implementation" \
    --ac "Acceptance tests created and stored in config repo" \
    --ac "S3 operator spawned and verified running" \
    --ac "Operator progress monitored through completion" \
    --ac "Independent validation scored against rubric" \
    --ac "Final verdict delivered with evidence"
```

### During Monitoring

```bash
# Meet criteria as work progresses
cs-promise --meet <id> --ac-id AC-1 --evidence "acceptance-tests/PRD-{ID}/ created with 8 scenarios" --type manual
cs-promise --meet <id> --ac-id AC-2 --evidence "tmux session s3-{initiative} running, output style verified" --type manual
```

### At Validation Complete

```bash
# Meet remaining criteria
cs-promise --meet <id> --ac-id AC-3 --evidence "Monitored for 2h15m, 3 interventions" --type manual
cs-promise --meet <id> --ac-id AC-4 --evidence "Weighted score: 0.73 (ACCEPT threshold: 0.60)" --type manual
cs-promise --meet <id> --ac-id AC-5 --evidence "ACCEPT verdict, report stored to Hindsight" --type manual

# Verify all criteria met
cs-verify --check --verbose
```

---

## Storing Validation Results

After completing validation, store findings for institutional memory:

```python
# Store to Hindsight (private bank for future guardian sessions)
mcp__hindsight__retain(
    content=f"""
    ## Guardian Validation: PRD-{prd_id}
    ### Weighted Score: {score} ({verdict})
    ### Feature Scores: {feature_breakdown}
    ### Gaps Found: {gaps}
    ### Lessons: {lessons}
    """,
    context="s3-guardian-validations",
    bank_id="system3-orchestrator"
)

# Store to project bank (shared, for team awareness)
mcp__hindsight__retain(
    content=f"PRD-{prd_id} validated: {verdict} (score: {score}). Key findings: {summary}",
    context="project-validations",
    bank_id="claude-code-{project}"
)
```

---

## Recursive Guardian Pattern

The guardian pattern is recursive. A guardian can watch:
- An S3 operator who spawns orchestrators who spawn workers (standard)
- Another guardian who is watching an S3 operator (meta-guardian)
- Multiple S3 operators in parallel (multi-initiative guardian)

Each level adds independent verification. The key constraint: each guardian stores its acceptance tests where the entity being watched cannot access them.

---

## Quick Reference

| Phase | Key Action | Reference |
|-------|------------|-----------|
| 1. Acceptance Tests | Read PRD, write Gherkin, create manifest | [gherkin-test-patterns.md](references/gherkin-test-patterns.md) |
| 2. Operator Spawn | tmux create, unset CLAUDECODE, ccsystem3 | [guardian-workflow.md](references/guardian-workflow.md) |
| 3. Monitoring | capture-pane loop, intervention triggers | [monitoring-patterns.md](references/monitoring-patterns.md) |
| 4. Validation | Read code, score scenarios, weighted total | [validation-scoring.md](references/validation-scoring.md) |

### Key Files

| File | Purpose |
|------|---------|
| `acceptance-tests/PRD-{ID}/manifest.yaml` | Feature weights, thresholds, metadata |
| `acceptance-tests/PRD-{ID}/*.feature` | Gherkin scenarios with scoring guides |
| `scripts/generate-manifest.sh` | Template generator for new initiatives |

### Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|-------------|------------------|
| Storing tests in impl repo | Operators can read and game the rubric | Store in config repo only |
| Boolean pass/fail scoring | Misses partial implementations | Use 0.0-1.0 gradient scoring |
| Trusting orchestrator reports | Self-reported status is biased | Read code independently |
| Skipping monitoring | AskUserQuestion blocks go undetected | Monitor continuously |
| Completing promise before validation | Premature closure | Meet AC-4 and AC-5 last |
| Equal feature weights | Distorts overall score | Weight by business criticality |

---

**Version**: 0.1.0
**Dependencies**: cs-promise CLI, tmux, Hindsight MCP, ccsystem3 shell function
**Integration**: system3-orchestrator skill, completion-promise skill, acceptance-test-writer skill
**Theory**: Independent verification eliminates self-reporting bias in agentic systems
