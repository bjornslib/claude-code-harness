---
name: s3-guardian
description: This skill should be used when System 3 needs to act as an independent guardian angel — spawning System 3 meta-orchestrators in tmux, creating blind Gherkin acceptance tests from PRDs, monitoring meta-orchestrator progress, independently validating claims against acceptance criteria using gradient confidence scoring (0.0-1.0), and setting session promises. Use when asked to "spawn and monitor a system3 meta-orchestrator", "create acceptance tests for a PRD", "validate orchestrator claims", "act as guardian angel", or "independently verify implementation work".
version: 0.1.0
title: "S3 Guardian"
status: active
---

# S3 Guardian — Independent Validation Pattern

The guardian angel pattern provides independent, blind validation of System 3 meta-orchestrator work. A guardian session creates acceptance tests from PRDs, stores them outside the implementation repo where meta-orchestrators cannot see them, spawns and monitors S3 meta-orchestrators in tmux, and independently validates claims against a gradient confidence rubric.

```
Guardian (this session, config repo)
    |
    |-- Creates blind Gherkin acceptance tests (stored here, NOT in impl repo)
    |-- Spawns S3 Meta-Orchestrator in tmux (at impl repo)
    |       |
    |       +-- Orchestrators (spawned by meta-orchestrator)
    |       |       +-- Workers
    |       |
    |       +-- s3-communicator (heartbeat)
    |
    |-- Monitors meta-orchestrator progress via tmux capture-pane
    |-- Independently validates claims against rubric
    |-- Reports to oversight team with gradient scores
```

**Key Innovation**: Acceptance tests live in `claude-harness-setup/acceptance-tests/PRD-{ID}/`, NOT in the implementation repository. Meta-orchestrators and their workers never see the rubric. This enables truly independent validation — the guardian reads actual code and scores it against criteria the implementers did not have access to.

---

## Guardian Disposition: Skeptical Curiosity

The guardian operates with a specific mindset that distinguishes it from passive monitoring.

### Be Skeptical

- **Never trust self-reported success.** Meta-orchestrators and orchestrators naturally over-report progress. Read the actual code, run the actual tests, check the actual logs.
- **Question surface-level explanations.** When a meta-orchestrator says "X is blocked by Y," independently verify that Y is truly the blocker — and that Y cannot be resolved.
- **Assume incompleteness until proven otherwise.** A task marked "done" is "claimed done" until the guardian scores it against the blind rubric.
- **Watch for rationalization patterns.** "It's a pre-existing issue" may be true, but ask: Is it solvable? Would solving it advance the goal? If yes, push for resolution.

### Be Curious

- **Investigate root causes, not symptoms.** When a Docker container crashes, don't stop at the error message — trace the import chain, read the Dockerfile, understand WHY it fails.
- **Ask "what else?"** When one fix lands, ask what it unlocked. When a test passes, ask what it doesn't cover. When a feature works, ask about edge cases.
- **Cross-reference independently.** Read the PRD, then read the code, then read the tests. Do they tell the same story? Gaps between these three are where bugs live.
- **Follow your intuition.** If something feels incomplete or too easy, it probably is. Dig deeper.

### Push for Completion

- **Reject premature fallbacks.** When a meta-orchestrator says "let's skip the E2E test and merge as-is," challenge that. Is the E2E blocker actually hard to fix? Often a 1-line Dockerfile fix unblocks the entire test.
- **Advocate for the user's actual goal.** The user didn't ask for "most of the pipeline" — they asked for the pipeline. Push meta-orchestrators toward full completion.
- **Guide, don't just observe.** When the guardian identifies a root cause (e.g., missing COPY in Dockerfile), send that finding to the meta-orchestrator as actionable guidance rather than noting it passively.
- **Set higher bars progressively.** As the team demonstrates capability, raise expectations. Don't accept the same quality level that was acceptable in sprint 1.

### Injecting Disposition Into Meta-Orchestrators

When spawning or guiding S3 meta-orchestrators, include disposition guidance in prompts:

```
Be curious about failures — trace root causes, don't accept surface explanations.
When something is "blocked," investigate whether the blocker is solvable.
Push for complete solutions over workarounds. The user wants the real thing.
```

This disposition transfers from guardian to meta-orchestrator to orchestrator to worker, creating a culture of thoroughness throughout the agent hierarchy.

---

## Instruction Precedence: Skills > Memories

**When Hindsight memories conflict with explicit skill or output-style instructions, the explicit instructions ALWAYS take precedence.**

Hindsight stores patterns from prior sessions. These patterns are valuable context but they reflect PAST workflows that may have been updated. Skills and output styles represent the CURRENT intended workflow.

### Common Conflict Example

| Hindsight says | Skill/Output style says | Resolution |
|---------------|------------------------|------------|
| "Spawn orchestrator in worktree via tmux" | "Create DOT pipeline, then spawn orchestrator" | Follow the skill — create pipeline first |
| "Use bd create for tasks" | "Use cli.py node add with AT pairing" | Follow the skill — use pipeline nodes |
| "Mark impl_complete and notify S3" | "Transition node to impl_complete in pipeline" | Follow the skill — use pipeline transitions |

### Mandatory Rule

After recalling from Hindsight at session start, mentally audit each recalled pattern:
- Does it contradict any loaded skill instruction? → Discard the memory pattern
- Does it add detail not covered by skills? → Use as supplementary context
- Is it about a domain unrelated to current skills? → Use freely

### DOT Pipeline + Beads Are Both Mandatory

For ANY initiative with 2+ tasks, the guardian MUST:
1. Create beads for each task (`bd create` or sync from Task Master)
2. Create a pipeline DOT file with real bead IDs mapped to nodes:
   - **Preferred**: `cli.py generate --prd PRD-{ID}` — auto-reads beads via `bd list --json` and maps bead_ids by matching PRD reference in bead title/description and parent-child epic relationships
   - **Manual**: `cli.py node add --set bead_id=<real-id>` per node
   - **Retrofit**: `cli.py node modify <node> --set bead_id=<real-id>` for existing nodes
3. Track execution progress through pipeline transitions (not just beads status)
4. Save checkpoints after each transition

Skipping pipeline creation because "it worked without one before" is an anti-pattern caused by cognitive momentum. Using synthetic bead_ids ("CLEANUP-T1") instead of real beads is also an anti-pattern — always create real beads first.

**How bead-to-node mapping works**: The `generate.py` pipeline generator uses `filter_beads_for_prd()` which matches beads to a PRD by: (a) finding epic beads whose title contains the PRD reference, (b) finding task beads that are children of those epics via `parent-child` dependency type, (c) finding task beads whose title or description contains the PRD reference. This is heuristic matching — it requires beads to include the PRD identifier in their metadata. When creating beads, always include the PRD ID in the title (e.g., `bd create --title="PRD-CLEANUP-001: Fix deprecated imports"`).

---

## Phase 1: Acceptance Test Creation

Generate blind acceptance tests from PRDs before any implementation begins. This phase uses
the `acceptance-test-writer` skill in two modes: `--mode=guardian` for per-epic Gherkin scenarios,
and `--mode=journey` for cross-layer business journey scenarios.

### Step 1: Generate Per-Epic Gherkin Tests (Guardian Mode)

Invoke the acceptance-test-writer skill in guardian mode. This generates the per-epic Gherkin
scenarios with confidence scoring guides that will be used for Phase 4 validation.

```python
Skill("acceptance-test-writer", args="--source=/path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md --mode=guardian")
```

This creates:
- `acceptance-tests/PRD-{ID}/manifest.yaml` — feature weights and decision thresholds
- `acceptance-tests/PRD-{ID}/scenarios.feature` — Gherkin scenarios with confidence scoring guides

**Verify the output:**
- [ ] All PRD features represented with weights summing to 1.0
- [ ] Each scenario has a confidence scoring guide (0.0 / 0.5 / 1.0 anchors)
- [ ] Evidence references are specific (file names, function names, test names)
- [ ] Red flags section present for each scenario
- [ ] manifest.yaml has valid thresholds (default: accept=0.60, investigate=0.40)

If the acceptance-test-writer cannot find a Goals section, derive objectives from the uber-epic
Acceptance Criteria — what the user ultimately wanted to achieve.

### Step 2: Generate Journey Tests (Journey Mode)

After generating per-epic Gherkin, generate blind journey tests from the PRD's Goals section.

```python
Skill("acceptance-test-writer", args="--source=/path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md --mode=journey")
```

This creates `acceptance-tests/PRD-{ID}/journeys/` in the config repo (where meta-orchestrators cannot see it).
Journey tests are generated BEFORE the meta-orchestrator is spawned — they stay blind throughout.

**Verify the output:**
- [ ] At least one `J{N}.feature` file exists per PRD business objective
- [ ] `runner_config.yaml` is present with sensible service URLs
- [ ] Each scenario crosses at least 2 system layers and ends with a business outcome assertion
- [ ] Tags include `@journey @prd-{ID} @J{N}`

**Storage location**: Both per-epic and journey tests live in `acceptance-tests/PRD-{ID}/` in the config
repo (claude-harness-setup), never in the implementation repo. Meta-orchestrators and their workers never see
the rubric or the journeys. This enables truly independent validation.

---

## Phase 2: S3 Meta-Orchestrator Spawning

Spawn a System 3 meta-orchestrator in a tmux session pointed at the implementation repository.

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

# 5. Set output style for System 3 meta-orchestrator
tmux send-keys -t "s3-{initiative}" "/output-style system3-meta-orchestrator"
tmux send-keys -t "s3-{initiative}" Enter
sleep 3

# 6. Verify output style loaded
tmux capture-pane -t "s3-{initiative}" -p -S -50 | grep -i "system3\|meta-orchestrator\|output.style"
```

After verification, either resume a previous session or send fresh instructions:

```bash
# Option A: Resume previous session
tmux send-keys -t "s3-{initiative}" "/resume"
tmux send-keys -t "s3-{initiative}" Enter

# Option B: Fresh instructions
tmux send-keys -t "s3-{initiative}" "You are the System 3 meta-orchestrator. Your output style is already set. Read the PRD at .taskmaster/docs/PRD-{ID}.md and begin. Invoke Skill('system3-orchestrator') as your first action."
sleep 2
tmux send-keys -t "s3-{initiative}" Enter
```

See [references/guardian-workflow.md](references/guardian-workflow.md) for the complete spawn sequence with error handling.

---

## Phase 3: Monitoring

Continuously monitor meta-orchestrator progress via tmux. Monitoring cadence adapts to activity level.

### Monitoring Cadence

| Phase | Interval | Rationale |
|-------|----------|-----------|
| Active implementation | 30s | Catch errors early, detect AskUserQuestion blocks |
| Investigation/planning | 60s | Meta-orchestrator is reading/thinking, less likely to block |
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

The Guardian monitors BOTH the S3 meta-orchestrator AND its orchestrators, but MUST route corrections through the S3 meta-orchestrator:

```
Guardian ──monitors──► S3 Meta-Orchestrator ──delegates──► Orchestrator ──delegates──► Workers
   │                       ▲                                    ▲
   │                       │                                    │
   └──── sends guidance ───┘                                    │
   └──── monitors (read-only) ──────────────────────────────────┘
```

| Action | Target | When |
|--------|--------|------|
| Send guidance/corrections | S3 Meta-Orchestrator session | Always (primary communication channel) |
| Monitor output (read-only) | Both S3 + Orchestrator | Continuous (for awareness) |
| Direct orchestrator injection | Orchestrator session | **Last resort only** — when S3 meta-orchestrator is compacting/stuck |
| Answer AskUserQuestion | Whichever session shows the dialog | Immediately (blocks are time-critical) |

**Anti-pattern**: Sending implementation guidance directly to the orchestrator bypasses the S3 meta-orchestrator's context and coordination. The S3 meta-orchestrator needs to know what guidance was given to maintain coherent oversight.

**Exception**: When the S3 meta-orchestrator is at <5% context and actively compacting, the Guardian may inject time-critical corrections directly into the orchestrator to prevent wrong work from being committed.

### AskUserQuestion Handling

When the meta-orchestrator or a worker hits an AskUserQuestion dialog:

```bash
# Navigate to the appropriate option and confirm
tmux send-keys -t "s3-{initiative}" Down
tmux send-keys -t "s3-{initiative}" Enter
```

See [references/monitoring-patterns.md](references/monitoring-patterns.md) for the complete monitoring command reference and red flag patterns.

---

## Phase 4: Independent Validation

After the meta-orchestrator claims completion, independently validate all work against the blind acceptance rubric.

### Validation Protocol

1. **Read the acceptance manifest**: Load `acceptance-tests/PRD-{ID}/manifest.yaml` and the `.feature` files
2. **Read the actual code**: Navigate the implementation repo independently — examine git diffs, file contents, test results
3. **Score each scenario**: Assign a confidence score (0.0 to 1.0) per Gherkin scenario
4. **Compute weighted total**: Multiply each scenario score by its feature weight, sum across all features
5. **Decide**: Compare the weighted total against the manifest thresholds

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

### DOT Pipeline Integration

When the initiative uses a `.dot` attractor pipeline, Phase 4 validation is node-driven. Each hexagon node in the pipeline graph represents a single validation gate. The guardian reads node attributes directly rather than inferring scope from PRD text.

#### Reading Validation Scope from Hexagon Nodes

```bash
# Extract node attributes from the pipeline DOT file
# Hexagon nodes (shape=hexagon) represent validation gates
grep -A 20 'shape=hexagon' .claude/attractor/<pipeline>.dot
```

A hexagon node exposes these attributes:

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `gate` | `technical` / `business` / `e2e` | Which validation mode to run |
| `mode` | `technical` / `business` | Maps directly to `--mode` parameter |
| `acceptance` | criteria text | What must be true for the gate to pass |
| `files` | comma-separated paths | Exact files to examine — no guessing |
| `bead_id` | e.g., `AT-10-TECH` | Beads task ID for recording results |
| `promise_ac` | e.g., `AC-1` | Completion promise criterion to meet |

**Example hexagon node:**
```dot
validate_backend_tech [
    shape=hexagon
    label="Backend\nTechnical\nValidation"
    gate="technical"
    mode="technical"
    bead_id="AT-10-TECH"
    acceptance="POST /auth/login returns JWT; POST /auth/refresh rotates token"
    files="src/auth/routes.py,src/auth/jwt.py,src/auth/models.py"
    promise_ac="AC-1"
    status="pending"
];
```

#### Validation Method Inference

The `files` attribute determines which validation technique the guardian uses:

```python
def infer_validation_method(files: list[str]) -> str:
    """Map file paths to the appropriate validation method."""
    for f in files:
        # Browser-required: frontend pages, components, stores
        if any(p in f for p in ["page.tsx", "component", "components/", "stores/", ".tsx", ".vue"]):
            return "browser-required"
        # API-required: route handlers, API modules, controllers
        if any(p in f for p in ["routes.py", "api/", "controllers/", "handlers/", "views.py"]):
            return "api-required"
    # Default: static code analysis is sufficient
    return "code-analysis"
```

| Files pattern | Validation method | Tools |
|--------------|-------------------|-------|
| `*.tsx`, `page.tsx`, `components/` | `browser-required` | chrome-devtools MCP, screenshot capture |
| `routes.py`, `api/`, `handlers/` | `api-required` | HTTP calls against real endpoints |
| `*.py`, `*.ts` (non-route) | `code-analysis` | Read file, check implementation, run pytest |

#### Evidence Storage

All evidence from DOT-based validation is stored under `.claude/evidence/<node-id>/`:

```
.claude/evidence/
└── <node-id>/                        # e.g., validate_backend_tech/
    ├── technical-validation.md       # Technical gate findings
    ├── business-validation.md        # Business gate findings (if mode=business)
    └── validation-summary.json       # Machine-readable summary
```

**validation-summary.json schema:**
```json
{
    "node_id": "validate_backend_tech",
    "bead_id": "AT-10-TECH",
    "gate": "technical",
    "mode": "technical",
    "verdict": "PASS",
    "confidence": 0.92,
    "files_examined": ["src/auth/routes.py", "src/auth/jwt.py"],
    "acceptance_criteria": "POST /auth/login returns JWT; POST /auth/refresh rotates token",
    "evidence": "pytest: 18/18 passing. routes.py: login endpoint at line 24. jwt.py: token rotation confirmed.",
    "timestamp": "2026-02-22T10:30:00Z"
}
```

**technical-validation.md template:**
```markdown
# Technical Validation: <node-id>

**Gate**: technical
**Bead**: <bead_id>
**Acceptance**: <acceptance text from node>

## Files Examined
- <file_path> — <summary of what was found>

## Checklist
- [ ] Unit tests pass (pytest/jest output)
- [ ] Build clean (no compile errors)
- [ ] Imports resolve
- [ ] TODO/FIXME count: 0
- [ ] Linter clean

## Verdict
**PASS** | **FAIL** (confidence: 0.XX)

## Evidence
<exact test output, file excerpts, or error messages>
```

#### Advancing the Pipeline After Validation

When a node passes, advance its status using the attractor CLI:

```bash
# Transition node to 'validated' status
python3 .claude/scripts/attractor/cli.py transition .claude/attractor/pipelines/<pipeline>.dot <node_id> validated

# If validation fails, transition to 'failed'
python3 .claude/scripts/attractor/cli.py transition .claude/attractor/pipelines/<pipeline>.dot <node_id> failed

# Save checkpoint after any transition
python3 .claude/scripts/attractor/cli.py checkpoint save .claude/attractor/pipelines/<pipeline>.dot
```

**Guardian workflow for DOT pipelines:**
```python
def validate_dot_pipeline_node(node_id: str, node_attrs: dict):
    # 1. Extract scope from node attributes
    gate = node_attrs["gate"]       # technical / business / e2e
    mode = node_attrs["mode"]       # maps to --mode parameter
    files = node_attrs["files"].split(",")
    acceptance = node_attrs["acceptance"]
    bead_id = node_attrs["bead_id"]

    # 2. Infer validation method from files
    method = infer_validation_method(files)

    # 3. Execute appropriate validation
    if mode == "technical":
        result = run_technical_validation(files, acceptance)
    elif mode == "business":
        result = run_business_validation(files, acceptance, method)

    # 4. Store evidence
    evidence_dir = f".claude/evidence/{node_id}/"
    write_evidence(evidence_dir, result, gate, mode, bead_id, acceptance)

    # 5. Advance pipeline status
    status = "validated" if result.verdict == "PASS" else "failed"
    run(f"python3 .claude/scripts/attractor/cli.py transition .claude/attractor/pipelines/<pipeline>.dot {node_id} {status}")
    run(f"python3 .claude/scripts/attractor/cli.py checkpoint save .claude/attractor/pipelines/<pipeline>.dot")

    # 6. Meet completion promise AC
    if result.verdict == "PASS":
        run(f"cs-promise --meet <id> --ac-id {node_attrs['promise_ac']} "
            f"--evidence 'Evidence at .claude/evidence/{node_id}/'")

    return result
```

---

## Phase 4.5: Regression Detection

After the meta-orchestrator completes implementation but **before** running journey tests, run an
automated regression check to detect components that were previously stable (`delta_status=existing`)
but have been unexpectedly modified or re-flagged as new in the updated graph.

This phase uses the `regression-check.sh` workflow script and the `zerorepo diff` CLI command.

### When to Run Phase 4.5

Run regression detection when:
- The initiative uses a ZeroRepo baseline (``.zerorepo/baseline.json`` exists in the impl repo)
- The meta-orchestrator has completed at least one implementation cycle (some nodes have been marked as modified/new)
- You suspect scope creep or unexpected side-effects from implementation work

Skip Phase 4.5 if:
- No ``.zerorepo/`` directory exists in the implementation repo (no baseline tracking)
- The initiative is in its first generation (no "before" baseline to compare against)

### Running the Regression Check

```bash
# Basic regression check (compares current baseline to post-update baseline)
./regression-check.sh --project-path /path/to/impl-repo

# With pipeline in-scope filter (only checks nodes referenced in the DOT pipeline)
./regression-check.sh \
    --project-path /path/to/impl-repo \
    --pipeline /path/to/impl-repo/.zerorepo/pipeline.dot \
    --output-dir /path/to/impl-repo/.zerorepo/

# Direct zerorepo diff (when you already have before/after baselines)
zerorepo diff \
    /path/to/impl-repo/.zerorepo/baseline.before.json \
    /path/to/impl-repo/.zerorepo/baseline.json \
    --pipeline /path/to/impl-repo/.zerorepo/pipeline.dot \
    --output /path/to/impl-repo/.zerorepo/regression-check.dot
```

### Interpreting regression-check.dot

The output ``.dot`` file contains one red-filled box per regressed node:

| Node attribute | Meaning |
|----------------|---------|
| `regression_type="status_change"` | Node was `existing` in baseline, now `modified`/`new` — unexpected change |
| `regression_type="unexpected_new"` | Node exists in updated graph but was absent from baseline entirely |
| `delta_status="modified"` or `"new"` | The status assigned to this node in the updated graph |
| `file_path="..."` | File associated with the regressed node |

```bash
# Quick scan: count regressions
grep 'regression_type=' /path/to/impl-repo/.zerorepo/regression-check.dot | wc -l

# List regressed node names
grep -oP 'label="\K[^\\]+' /path/to/impl-repo/.zerorepo/regression-check.dot
```

A `no_regressions` node with green fill means the check passed cleanly.

### Guardian Response Protocol

| Regression Check Result | Guardian Action |
|------------------------|-----------------|
| Exit 0 — no regressions | Log PASS, proceed to Phase 5 (journey tests) |
| Exit 1 — regressions detected | Send findings to meta-orchestrator with specific node names and file paths |
| Exit 3 — update step failed | Check runner script path; verify `.zerorepo/` is properly initialized |

**When regressions are found**, send structured guidance to the meta-orchestrator:

```
tmux send-keys -t "s3-{initiative}" \
  "REGRESSION ALERT: zerorepo diff found {N} regressed nodes. Review .zerorepo/regression-check.dot.
   Affected nodes: {node_names}
   These nodes were previously stable (delta_status=existing) and are now marked as modified/new.
   Investigate whether these changes are intentional or are side-effects of recent implementation work.
   If intentional, update the baseline. If unintentional, revert the affecting changes." Enter
```

### Evidence Storage for Regression Phase

```
.claude/evidence/PRD-{ID}-epic6/
├── regression-check.dot          # DOT output from zerorepo diff
├── baseline.before.json          # The "before" snapshot (copy)
└── regression-summary.md         # Human-readable summary
```

**regression-summary.md template:**
```markdown
# Regression Check: PRD-{ID}

**Date**: {timestamp}
**Before baseline**: .zerorepo/baseline.before.json
**After baseline**: .zerorepo/baseline.json
**Pipeline filter**: {pipeline_path or "none"}

## Result: PASS | FAIL ({N} regressions)

### Regressions Found
- {node_name} ({file_path}): was existing → now {delta_status}
- ...

### Unexpected New Nodes
- {node_name} ({file_path}): appears in updated graph but not in baseline
- ...

## Disposition
{CLEARED: All regressions are intentional (implementation of planned changes) OR
ESCALATED: N regressions are unintentional side-effects, sent to meta-orchestrator}
```

### Meeting the Completion Promise AC

```bash
# When regression check passes
cs-promise --meet <id> --ac-id AC-4.5 \
    --evidence "regression-check.dot: 0 regressions detected. Baseline updated." \
    --type manual

# When regressions found but cleared (intentional)
cs-promise --meet <id> --ac-id AC-4.5 \
    --evidence "regression-check.dot: 3 regressions — all intentional (confirmed with meta-orch)" \
    --type manual
```

---

### Step 5a: Validation Method-Specific Prompt Construction

Before dispatching scoring agents for each feature, read `validation_method` from the manifest and prepend mandatory instructions to the scoring agent's prompt:

**For `browser-required` features:**
```
MANDATORY: YOU MUST use Claude in Chrome (mcp__claude-in-chrome__*) to validate this feature.
Static code analysis alone (Read/Grep) = automatic 0.0 score.
Required tool sequence: tabs_context_mcp → navigate → read_page → screenshot → interact with elements.
If the frontend is not running, report "BLOCKED: frontend not running" — do NOT fall back to code analysis.
```

**For `api-required` features:**
```
MANDATORY: YOU MUST make actual HTTP requests (curl/httpx) to validate this feature.
Reading router/endpoint code alone = automatic 0.0 score.
Required: Make real requests, capture response status codes and bodies as evidence.
If the API server is not running, report "BLOCKED: API server not running" — do NOT fall back to code analysis.
```

**For `code-analysis` features:**
No special prepend. Current behavior (Read/Grep/file examination) is appropriate.

**For `hybrid` features (or absent field):**
No special prepend. Scoring agent uses its best judgment on which tools to employ.

**Implementation**: When constructing the scoring agent prompt in Phase 4, read each feature's `validation_method` from the manifest. If the field is present and not `hybrid`, prepend the corresponding instruction block above to the agent's prompt BEFORE the scenario text.

### Step 5b: Evidence Gate Enforcement

After scoring agents return results but BEFORE computing the weighted total, scan each feature's evidence for method-appropriate keywords. This is the strongest enforcement — it catches agents that ignore the prompt prepend.

**Evidence keyword requirements:**

| `validation_method` | Required keywords (at least 2) | What they prove |
|---------------------|-------------------------------|-----------------|
| `browser-required` | "screenshot", "navigate", "tabs_context", "read_page", "Chrome", "localhost:3000" | Agent actually used the browser |
| `api-required` | "curl", "HTTP 200", "HTTP 201", "HTTP 202", "response body", "localhost:8000", actual JSON snippets | Agent actually made HTTP requests |
| `code-analysis` | No keyword requirement | Static analysis is the expected method |
| `hybrid` | No keyword requirement | Agent discretion |

**Enforcement logic:**
1. For each feature with `validation_method` = `browser-required` or `api-required`:
2. Scan the scoring agent's evidence text for the required keywords
3. If fewer than 2 required keywords are found:
   - **Override the feature score to 0.0**
   - Set reason: `"EVIDENCE GATE: {validation_method} feature scored without {validation_method} evidence. Agent used static analysis instead of required tooling."`
   - Log the override in the validation worksheet
4. Proceed with weighted total computation using the overridden score

**Why 2 keywords minimum?** A single keyword match could be coincidental (e.g., mentioning "Chrome" in a description without using it). Two keywords indicate actual tool usage.

This gate ensures that even if a scoring agent ignores the prompt prepend, its score is corrected to 0.0 — making it impossible to score well on a browser-required feature without actually opening a browser.

### Step 6: Execute Journey Tests

After computing the per-feature weighted score, execute the journey tests in `journeys/`.

**Execution approach** — spawn a tdd-test-engineer sub-agent:

```python
Task(
    subagent_type="tdd-test-engineer",
    description="Execute journey tests for PRD-{ID}",
    prompt="""
    Execute the journey test scenarios at: acceptance-tests/PRD-{ID}/journeys/

    For each J{N}.feature file:
    1. Read the scenario
    2. Execute each step in sequence:
       - @browser steps: use chrome-devtools MCP (navigate, click, assert_visible, etc.)
       - @api steps: make actual API calls and assert responses
       - @db steps: query the DB directly using runner_config.yaml dsn
       - "eventually" steps: poll the specified condition every interval_seconds, up to max_wait_seconds
       - Pass artifacts forward: contact_id extracted in step 3 → used in step 5 DB query
    3. Report pass/fail per step, plus the artifact values at each step
    4. Return journey-results.json: {J1: {status: PASS/FAIL, steps: [...]}, J2: ...}

    Services are defined in runner_config.yaml.
    If services are not running, mark all @async and @browser steps as SKIP (not FAIL)
    and note "requires live services". Mark @smoke steps as runnable anyway.

    Return journey-results.json to the guardian session.
    """
)
```

**If services not running** (structural-only mode):
- Guardian reads the journey `.feature` files manually
- Checks that each layer mentioned in the scenario has corresponding code
- Marks as `STRUCTURAL_PASS` / `STRUCTURAL_FAIL`
- Does not block the per-feature verdict (only live execution can apply the override)

**Override Rule (MANDATORY when live execution runs)**:
```
If ANY journey test returns FAIL (not SKIP):
  → Final verdict = REJECT regardless of per-feature weighted score
  → Reason: "Journey J{N} failed at step: {step_description} — business outcome not achieved"
```

Example: per-feature score = 0.92 (would be ACCEPT) + J1 FAILS at "Prefect flow Completed"
  → Final verdict: **REJECT**
  → Reason: "Prefect trigger not firing; contact_id xxx never appeared in flow runs"

Include `journey-results.json` in the evidence package alongside per-feature scores.

### Deliver Verdict

Combine results:
- Per-feature weighted score (0.0–1.0)
- Journey test results (PASS / FAIL / SKIP per J{N}, or STRUCTURAL_PASS/FAIL)

Final decision matrix:

| Per-feature score | Journey results     | Final verdict                                   |
|-------------------|---------------------|-------------------------------------------------|
| >= 0.60           | All PASS            | ACCEPT                                          |
| >= 0.60           | Any FAIL            | REJECT (journey override)                       |
| >= 0.60           | All SKIP            | ACCEPT (note: live validation pending)          |
| 0.40–0.59         | Any                 | INVESTIGATE                                     |
| < 0.40            | Any                 | REJECT                                          |

Thresholds are configurable per initiative in `manifest.yaml`.

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
    --ac "S3 meta-orchestrator spawned and verified running" \
    --ac "Meta-orchestrator progress monitored through completion" \
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
- An S3 meta-orchestrator who spawns orchestrators who spawn workers (standard)
- Another guardian who is watching an S3 meta-orchestrator (meta-guardian)
- Multiple S3 meta-orchestrators in parallel (multi-initiative guardian)

Each level adds independent verification. The key constraint: each guardian stores its acceptance tests where the entity being watched cannot access them.

---

## Quick Reference

| Phase | Key Action | Reference |
|-------|------------|-----------|
| 1. Acceptance Tests | Read PRD, write Gherkin, create manifest | [gherkin-test-patterns.md](references/gherkin-test-patterns.md) |
| 2. Meta-Orchestrator Spawn | tmux create, unset CLAUDECODE, ccsystem3, set output style | [guardian-workflow.md](references/guardian-workflow.md) |
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
| Storing tests in impl repo | Meta-orchestrators can read and game the rubric | Store in config repo only |
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
