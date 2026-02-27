---
name: s3-guardian
description: This skill should be used when System 3 needs to act as an independent guardian angel — designing PRDs with CoBuilder RepoMap context injection, challenging designs via parallel solutioning, spawning orchestrators in tmux, creating blind Gherkin acceptance tests and executable browser test scripts from PRDs, monitoring orchestrator progress, independently validating claims against acceptance criteria using gradient confidence scoring (0.0-1.0), and setting session promises. Use when asked to "spawn and monitor an orchestrator", "create acceptance tests for a PRD", "validate orchestrator claims", "act as guardian angel", "independently verify implementation work", or "design and challenge a PRD".
version: 0.1.0
title: "S3 Guardian"
status: active
---

# S3 Guardian — Independent Validation Pattern

The guardian angel pattern provides independent, blind validation of System 3 meta-orchestrator work. A guardian session creates acceptance tests from PRDs, stores them outside the implementation repo where meta-orchestrators cannot see them, spawns and monitors S3 meta-orchestrators in tmux, and independently validates claims against a gradient confidence rubric.

```
Guardian (this session, config repo)
    |
    |-- Designs PRDs with CoBuilder RepoMap context (Phase 0)
    |-- Challenges own designs via parallel-solutioning + research-first (Phase 0)
    |-- Creates blind Gherkin acceptance tests (stored here, NOT in impl repo)
    |-- Generates executable browser test scripts for UX prototypes
    |-- Spawns Orchestrators in tmux (one per epic/DOT node)
    |       |
    |       +-- Workers (native Agent Teams, spawned by orchestrator)
    |
    |-- Monitors orchestrator progress via tmux capture-pane
    |-- Independently validates claims against rubric
    |-- Delivers verdict with gradient confidence scores
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

For new initiatives, pipeline creation is part of Phase 0 (Step 0.2). For initiatives where a pipeline already exists, verify it with `cli.py validate` before Phase 1.

**How bead-to-node mapping works**: The `generate.py` pipeline generator uses `filter_beads_for_prd()` which matches beads to a PRD by: (a) finding epic beads whose title contains the PRD reference, (b) finding task beads that are children of those epics via `parent-child` dependency type, (c) finding task beads whose title or description contains the PRD reference. This is heuristic matching — it requires beads to include the PRD identifier in their metadata. When creating beads, always include the PRD ID in the title (e.g., `bd create --title="PRD-CLEANUP-001: Fix deprecated imports"`).

---

## Step 0: Promise Creation (MANDATORY — Do This First)

Before ANY other work, identify whether the user has given you a goal or task to achieve. If they have, create a completion promise that captures it.

Use your judgment to understand:
- What the user wants you to achieve (the promise title)
- What the key deliverables or outcomes are (acceptance criteria — 3–5 measurable results)

Then create and start the promise:

```bash
cs-promise --create "<goal title>" \
    --ac "<deliverable 1>" \
    --ac "<deliverable 2>" \
    --ac "<deliverable 3>"
cs-promise --start <promise-id>
```

**Store the promise ID** — you will `--meet` each AC as its phase completes (see "Session Promise Integration" section for the per-phase `--meet` calls).

> **Note**: The "Session Promise Integration" section at the bottom of this skill provides a pre-built template specifically for guardian validation sessions (acceptance tests, spawning, monitoring, validation, verdict). Use that template's `--ac` text directly when your goal matches the standard guardian pattern; adjust the ACs for non-standard goals.

---

## Phase 0: PRD Design & Challenge

When the guardian is initiating a new initiative (rather than validating an existing one), it must first design the PRD, create the pipeline infrastructure, and challenge its own design before proceeding to acceptance test creation.

**Skip Phase 0 if**: A finalized PRD already exists at the implementation repo's `docs/prds/PRD-{ID}.md` and has been reviewed. Proceed directly to Phase 1.

### Step 0.1: PRD Authoring with CoBuilder RepoMap Context

Before writing the PRD, understand the current codebase structure using CoBuilder's RepoMap context command:

```bash
# Generate structured YAML codebase context filtered to the relevant PRD scope
cobuilder repomap context --name <repo-name> --prd PRD-{ID}

# For agent-consumable output (recommended when delegating to solution-design-architect):
cobuilder repomap context --name <repo-name> --prd PRD-{ID} --format yaml
```

The command outputs structured YAML with module relevance, dependency graph, and protected files:

```yaml
# Example output of: cobuilder repomap context --name agencheck --prd PRD-AUTH-001

repository: agencheck
snapshot_date: 2026-02-27T10:00:00Z
total_nodes: 3037
total_files: 312

modules_relevant_to_epic:
  - name: src/auth/
    delta: existing          # existing | modified | new
    files: 8
    summary: |
      Authentication module with JWT handling.
      Fully implemented — no changes needed for this epic.
    key_interfaces:
      - signature: "authenticate(token: str) -> User"
        file: src/auth/middleware.py
        line: 42

  - name: src/api/routes/
    delta: modified
    files: 12
    summary: |
      API route handlers for all endpoints.
      Needs new refresh token endpoint added.
    change_summary: "Add POST /auth/refresh route handler"

  - name: src/email/
    delta: new
    files: 0
    summary: |
      Email notification service — does not exist yet.
      Needs to be created from scratch.
    suggested_structure:
      - email_service/__init__.py
      - email_service/sender.py

dependency_graph:
  - from: src/api/routes/
    to: src/auth/
    type: invokes
    description: "Route handlers call authenticate()"

protected_files:
  - path: src/database/models.py
    reason: "Core data models — shared across all modules"
  - path: src/auth/jwt.py
    reason: "JWT utilities — security-critical, modify with care"
```

Also gather domain context from Hindsight:

```python
PROJECT_BANK = os.environ.get("CLAUDE_PROJECT_BANK", "claude-harness-setup")
domain_context = mcp__hindsight__reflect(
    query=f"Architecture patterns, prior PRDs, and design decisions for {initiative_domain}",
    budget="mid",
    bank_id=PROJECT_BANK
)
```

Using RepoMap context and Hindsight context, write the PRD to `docs/prds/PRD-{ID}.md` in the impl repo. The PRD must include:
- YAML frontmatter with `prd_id`, `title`, `status`, `created`
- Goals section (maps to journey tests)
- Epic breakdown with acceptance criteria per epic
- Technical approach (informed by RepoMap delta analysis — what's `new` vs `existing` vs `modified`)

#### Injecting RepoMap Context into SD Creation

When delegating SD creation to a `solution-design-architect`, inject the RepoMap YAML directly into the prompt. This ensures the SD references actual file paths, uses real interface signatures, and respects protected files:

```python
# Generate RepoMap context (capture output as string)
context_yaml = Bash(
    f"cobuilder repomap context --name {repo_name} --prd {prd_id} --format yaml"
)

# Inject into solution-design-architect prompt
Task(
    subagent_type="solution-design-architect",
    prompt=f"""
    Create a Solution Design for Epic {epic_num} of {prd_id}.

    ## PRD Reference
    Read: {prd_path}

    ## Codebase Context (RepoMap — read carefully before designing)
    ```yaml
    {context_yaml}
    ```

    Use this context to:
    - Reference EXISTING modules by their actual file paths
    - Scope MODIFIED modules to specific changes needed
    - Design NEW modules with suggested structure from RepoMap
    - Respect protected_files — do not include them in File Scope unless PRD requires changes
    - Use key_interfaces for accurate API contracts in your design
    """
)
```

> **Note on `--format yaml`**: This is the default format and produces structured YAML with module info, dependency graph, and key interfaces. Use `--format yaml` (or omit the flag) when reviewing context yourself or when the output is consumed by another agent or for LLM injection.

### Step 0.2: Create DOT Pipeline

Create the task tracking and pipeline infrastructure:

```bash
# 1. Create beads for each epic and task (include PRD ID in titles)
bd create --title="PRD-{ID}: Epic 1 — {name}" --type=epic --priority=2
bd create --title="PRD-{ID}: Task 1.1 — {name}" --type=task --priority=2
bd dep add <task-bead> <epic-bead>  # Task belongs to epic

# 2. Generate pipeline DOT file from beads
CLI="python3 /path/to/impl-repo/.claude/scripts/attractor/cli.py"
$CLI generate --prd PRD-{ID} --output /path/to/impl-repo/.claude/attractor/pipelines/${INITIATIVE}.dot

# 3. Validate the pipeline
$CLI validate /path/to/impl-repo/.claude/attractor/pipelines/${INITIATIVE}.dot

# 4. Review status
$CLI status /path/to/impl-repo/.claude/attractor/pipelines/${INITIATIVE}.dot --summary
```

If `generate` cannot auto-map beads (no PRD reference in bead metadata), build manually:

```bash
$CLI node add pipeline.dot impl_epic1 --handler codergen --label "Epic 1" --set bead_id=<real-bead-id>
$CLI edge add pipeline.dot start impl_epic1 --label "begin"
$CLI edge add pipeline.dot impl_epic1 validate_epic1 --label "pass"
# ... repeat for each node
$CLI validate pipeline.dot
```

### Step 0.3: Parse PRD with Task Master

Use Task Master to decompose the PRD into structured tasks, then sync to beads:

```python
# Parse PRD into tasks
mcp__task-master-ai__parse_prd(
    input="docs/prds/PRD-{ID}.md",
    project_root="/path/to/impl-repo"
)

# Verify tasks were created
mcp__task-master-ai__get_tasks(project_root="/path/to/impl-repo")
```

```bash
# Sync Task Master output into beads
node /path/to/config-repo/.claude/scripts/sync-taskmaster-to-features.js \
    --project-root /path/to/impl-repo

# Verify beads are populated and DOT pipeline nodes have real bead_ids
bd list --status=open
$CLI status pipeline.dot --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for n in data.get('nodes', []):
    bid = n.get('bead_id', 'MISSING')
    print(f\"{n['node_id']}: bead_id={bid}\")
"
```

**If bead_ids are missing in DOT nodes**, retrofit them:
```bash
$CLI node modify pipeline.dot <node_id> --set bead_id=<real-bead-id>
$CLI checkpoint save pipeline.dot
```

### RepoMap Context Injection (Phase 0 Step 2.5)

Before delegating SD creation to solution-design-architect, generate codebase context:

```bash
# Generate structured YAML context for the repo
cobuilder repomap context --name <repo_name> --prd <prd_id>
```

Then inject into the solution-design-architect prompt:

```python
context_yaml = Bash("cobuilder repomap context --name {repo_name} --prd {prd_id}")

Task(
    subagent_type="solution-design-architect",
    prompt=f"""
    Create a Solution Design for Epic {epic_num} of {prd_id}.

    ## PRD Reference
    Read: {prd_path}

    ## Codebase Context (RepoMap — read carefully before designing)
    ```yaml
    {context_yaml}
    ```

    Use this context to:
    - Reference EXISTING modules by their actual file paths
    - Scope MODIFIED modules to specific changes needed
    - Design NEW modules with suggested structure from RepoMap
    - Respect protected_files — do not include them in File Scope unless PRD requires changes
    - Use key_interfaces for accurate API contracts in your design
    """
)
```

**When to use**: Any initiative targeting a codebase registered with `cobuilder repomap init`.
**Skip when**: First-time setup (no baseline yet), or purely config/docs changes.

### Step 0.4: Design Challenge Protocol (MANDATORY)

Before proceeding to Phase 1, the guardian MUST challenge its own PRD design by spawning a solution-architect agent that independently evaluates the design.

**Why this matters**: The guardian wrote the PRD — it cannot objectively evaluate its own design. Independent challenge prevents proceeding with flawed architecture, missed edge cases, or technology choices that seem reasonable but have known pitfalls.

#### Launch Design Challenge Agent

```python
Task(
    subagent_type="solution-design-architect",
    description="Challenge PRD-{ID} design via parallel solutioning + research",
    prompt=f"""
    You are reviewing PRD-{prd_id} as an independent design challenger.

    ## MANDATORY First Actions
    1. Skill("parallel-solutioning") with the prompt:
       "Review and challenge the solution design in docs/prds/PRD-{prd_id}.md.
       Identify architectural weaknesses, missing edge cases, scalability concerns,
       and alternative approaches."
       - This spawns 7 architects with diverse reasoning strategies
       - Each architect must identify weaknesses, alternatives, and risks

    2. Skill("research-first") for each major technology choice in the PRD:
       - Validate framework versions and API compatibility
       - Check for deprecations or known issues
       - Cross-reference with context7 docs for current best practices
       - Validate integration patterns between chosen technologies

    ## Your Deliverable
    Write a design-challenge report to {config_repo}/acceptance-tests/PRD-{prd_id}/design-challenge.md:

    ### Report Structure
    - **Consensus Concerns**: Issues flagged by 5+ of the 7 architects
    - **Technology Validation**: research-first findings per technology choice
    - **Recommended PRD Amendments**: Specific changes with rationale
    - **Risk Matrix**: severity (critical/high/medium/low) x likelihood
    - **VERDICT**: PROCEED / AMEND / REDESIGN

    Read the PRD at: {impl_repo}/docs/prds/PRD-{prd_id}.md
    Store the report at: {config_repo}/acceptance-tests/PRD-{prd_id}/design-challenge.md
    """
)
```

#### Handling Challenge Results

| Verdict | Guardian Action |
|---------|----------------|
| PROCEED | Log result to Hindsight, continue to Phase 1 |
| AMEND | Apply recommended changes to PRD, re-run Step 0.3 (Task Master re-parse), update beads |
| REDESIGN | Major rework needed — revisit Step 0.1 with architect feedback as input |

**Anti-pattern**: Ignoring AMEND/REDESIGN verdicts because "it's probably fine" or "we already created beads." The cost of fixing a flawed design after implementation is 10x the cost of fixing the PRD.

#### Evidence Storage

```
acceptance-tests/PRD-{ID}/
├── design-challenge.md         # Architect consensus report
└── research-validation.md      # research-first findings (if separate)
```

#### Promise Integration

```bash
# After Phase 0 completes successfully
cs-promise --meet <id> --ac-id AC-0 \
    --evidence "PRD written, pipeline created with N nodes, design challenge verdict: PROCEED" \
    --type manual
```

---

## Phase 1: Acceptance Test Creation

Generate blind acceptance tests from **Solution Design (SD) documents** before any implementation begins.
The SD is the correct input because it contains:
- **Business Context section** — the goals and success metrics the tests should validate
- **Section 6: Acceptance Criteria per Feature** — Gherkin-ready criteria for each feature

The PRD (business artifact) provides the broader context, but the SD contains the structured,
feature-level acceptance criteria that `acceptance-test-writer` needs to generate meaningful tests.

This phase uses `acceptance-test-writer` in two modes: `--mode=guardian` for per-epic Gherkin scenarios,
and `--mode=journey` for cross-layer business journey scenarios.

**Document lookup**:
- SD files are in the implementation repo at: `.taskmaster/docs/SD-{CATEGORY}-{NUMBER}-{epic-slug}.md`
- PRD files are at: `.taskmaster/docs/PRD-{CATEGORY}-{DESCRIPTOR}.md`
- Both live in `.taskmaster/docs/` — SDs can be read directly from the impl repo path

### Step 1: Generate Per-Epic Gherkin Tests (Guardian Mode)

Invoke the acceptance-test-writer skill in guardian mode. This generates the per-epic Gherkin
scenarios with confidence scoring guides that will be used for Phase 4 validation.

```python
# Source the SD document — it has the structured acceptance criteria
# The --prd flag identifies the parent PRD for test organisation
Skill("acceptance-test-writer", args="--source=/path/to/impl-repo/.taskmaster/docs/SD-{ID}.md --prd=PRD-{ID} --mode=guardian")
```

If no SD exists yet (legacy initiative), fall back to the PRD:
```python
Skill("acceptance-test-writer", args="--source=/path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md --mode=guardian")
```

This creates:
- `acceptance-tests/PRD-{ID}/manifest.yaml` — feature weights and decision thresholds
- `acceptance-tests/PRD-{ID}/scenarios.feature` — Gherkin scenarios with confidence scoring guides

**Verify the output:**
- [ ] All SD features (Section 4: Functional Decomposition) represented with weights summing to 1.0
- [ ] Each scenario has a confidence scoring guide (0.0 / 0.5 / 1.0 anchors)
- [ ] Evidence references are specific (file names, function names, test names from SD File Scope)
- [ ] Red flags section present for each scenario
- [ ] manifest.yaml has valid thresholds (default: accept=0.60, investigate=0.40)

If the acceptance-test-writer cannot find a Goals section in the SD, use the SD's Business Context
section (Section 1) or derive objectives from the parent PRD's Goals (Section 2).

### Step 2: Generate Journey Tests (Journey Mode)

After generating per-epic Gherkin, generate blind journey tests from the **PRD** — not the SD.
Journey tests are cross-epic: they verify end-to-end business flows that span multiple epics and
cannot be validated by any single SD. The PRD's Goals and User Stories sections define these flows.

```python
# Source the PRD — journey tests must capture cross-epic business outcomes
# One set of journey tests per PRD (not per SD)
Skill("acceptance-test-writer", args="--source=/path/to/impl-repo/.taskmaster/docs/PRD-{ID}.md --prd=PRD-{ID} --mode=journey")
```

This creates `acceptance-tests/PRD-{ID}/journeys/` in the config repo (where meta-orchestrators cannot see it).
Journey tests are generated BEFORE the meta-orchestrator is spawned — they stay blind throughout.

**Verify the output:**
- [ ] At least one `J{N}.feature` file exists per PRD business objective (Goals section / Section 2)
- [ ] Scenarios cross epic boundaries — a journey that stays within one epic is a mis-scoped scenario
- [ ] `runner_config.yaml` is present with sensible service URLs
- [ ] Each scenario crosses at least 2 system layers and ends with a business outcome assertion
- [ ] Tags include `@journey @prd-{ID} @J{N}`

**Storage location**: Both per-epic and journey tests live in `acceptance-tests/PRD-{ID}/` in the config
repo (claude-harness-setup), never in the implementation repo. Meta-orchestrators and their workers never see
the rubric or the journeys. This enables truly independent validation.

### Step 3: Generate Executable Browser Test Scripts (MANDATORY for UX PRDs)

**Trigger condition**: If the manifest.yaml contains ANY feature with `validation_method: browser-required`, this step is MANDATORY. Skip for PRDs with only `code-analysis` and `api-required` features.

The Gherkin scenarios from Step 1 are scoring rubrics — they guide confidence scoring but are not directly executable. This step generates companion executable test scripts that can be run by a tdd-test-engineer agent against a live frontend using claude-in-chrome MCP tools.

**Why the existing scenarios.feature is NOT sufficient**: The PRD-P1.1-UNIFIED-FORM-001 experience demonstrated this gap. 17 Gherkin scenarios were written as scoring rubrics with confidence guides (0.0/0.5/1.0 anchors), but none were executable. The guardian could not automatically verify whether the voice bar was hidden in chat mode, whether the progress bar replaced the case reference, or whether field confirmation changed the background color. These checks require browser automation.

#### Why Both Formats Are Needed

| Format | Purpose | Used By | Executable? |
|--------|---------|---------|-------------|
| `scenarios.feature` | Confidence scoring rubric | Guardian Phase 4 manual scoring | No — requires judgment |
| `executable-tests/` | Automated browser validation | tdd-test-engineer agent | Yes — deterministic pass/fail |

#### Output Structure

```
acceptance-tests/PRD-{ID}/
├── manifest.yaml              # (from Step 1)
├── scenarios.feature          # (from Step 1) — scoring rubric
├── journeys/                  # (from Step 2)
└── executable-tests/          # Browser automation test scripts
    ├── config.yaml            # Base URL, selectors, test data
    ├── S1-layout.yaml         # Executable version of S1.x scenarios
    ├── S2-mode-switching.yaml # Executable version of S2.x scenarios
    └── S3-form-panel.yaml     # Executable version of S3.x scenarios
```

#### Executable Test YAML Schema

Each test file maps Gherkin scenarios to claude-in-chrome MCP tool calls:

```yaml
test_group: S1-layout
prd_id: PRD-{ID}
base_url: "http://localhost:3000"
prerequisites:
  - frontend_running: true
  - route_exists: "/verify/test-task-123?mode=chat"

tests:
  - id: S1.1
    name: "Page header shows verification title at very top"
    steps:
      - tool: mcp__claude-in-chrome__navigate
        args:
          url: "${base_url}/verify/test-task-123?mode=chat"
      - tool: mcp__claude-in-chrome__get_page_text
        args: {}
        assert:
          contains: "Employment Verification"
      - tool: mcp__claude-in-chrome__find
        args:
          query: "h1, h2"
        assert:
          first_element_text_contains: "Employment Verification"
      - tool: mcp__claude-in-chrome__computer
        args:
          action: screenshot
        evidence: "s1-1-header.png"

  - id: S2.1
    name: "Chat mode does NOT show voice bar"
    steps:
      - tool: mcp__claude-in-chrome__navigate
        args:
          url: "${base_url}/verify/test-task-123?mode=chat"
      - tool: mcp__claude-in-chrome__javascript_tool
        args:
          javascript: |
            const voiceBar = document.querySelector('[data-testid="voice-bar"], [class*="speaking"], [class*="voice-controls"]');
            return { voiceBarVisible: voiceBar !== null && voiceBar.offsetHeight > 0 };
        assert:
          voiceBarVisible: false
      - tool: mcp__claude-in-chrome__find
        args:
          query: "input[type='text'], textarea"
        assert:
          found: true  # Chat input should exist in chat mode
```

#### Mapping Rules: Gherkin to MCP Tools

| Gherkin Pattern | MCP Tool | Assertion Type |
|-----------------|----------|----------------|
| "I navigate to {url}" | `navigate` | N/A |
| "the page shows {text}" | `get_page_text` | `contains: {text}` |
| "{element} is visible" | `find` or `javascript_tool` | `found: true` |
| "{element} is NOT visible" | `javascript_tool` (offsetHeight check) | `visible: false` |
| "I click {element}" | `find` + `computer` (click) | N/A |
| "I enter {value} in {field}" | `form_input` | N/A |
| "background changes to {color}" | `javascript_tool` (getComputedStyle) | `contains: {color}` |
| layout/CSS assertion | `javascript_tool` (grid/flex inspection) | custom assertion |
| screenshot capture | `computer` (screenshot) | evidence artifact |

#### Generation Process

For each feature group in `manifest.yaml` where `validation_method: browser-required`:

1. Read the corresponding Gherkin scenarios from `scenarios.feature`
2. Map each `Then` assertion to a specific `mcp__claude-in-chrome__*` tool call
3. Map each `When` action to a `navigate`, `form_input`, `find`, or `javascript_tool` call
4. Add `evidence` capture (screenshot) after each scenario's assertions
5. Include `assert` blocks with deterministic pass/fail conditions (not confidence scores)

#### Execution During Phase 4

These executable tests are run by a tdd-test-engineer agent during Phase 4 validation:

```python
Task(
    subagent_type="tdd-test-engineer",
    description="Execute browser automation tests for PRD-{ID}",
    prompt=f"""
    Execute the browser automation tests at: acceptance-tests/PRD-{prd_id}/executable-tests/

    For each test file:
    1. Read config.yaml for base URL and prerequisites
    2. Verify prerequisites (frontend running, routes accessible)
    3. Execute each test's steps sequentially using the specified MCP tools
    4. Evaluate assert blocks — deterministic PASS/FAIL per step
    5. Capture evidence screenshots to .claude/evidence/PRD-{prd_id}/
    6. Return executable-test-results.json with per-test pass/fail

    If frontend is not running, mark ALL tests as BLOCKED (not FAIL).
    """
)
```

#### Integration with Phase 4 Confidence Scoring

Executable test results serve as hard evidence for Phase 4 confidence scoring:

| Test Result | Impact on Confidence Score |
|-------------|---------------------------|
| **PASS** | Confidence floor of 0.7 for that scenario (evidence of working implementation) |
| **FAIL** | Confidence ceiling of 0.3 for that scenario (implementation has defects) |
| **BLOCKED** | No constraint on scoring (manual assessment still applies) |

This prevents the guardian from scoring a scenario at 0.9 based on code reading when the executable test shows the feature is actually broken in the browser.

---

## Phase 2: Orchestrator Spawning

Spawn orchestrators directly in tmux sessions — one per epic or DOT pipeline node. Under the guardian-direct model, there is no intermediate System 3 layer. Each orchestrator receives the epic scope, bead IDs, DOT node context, and Hindsight wisdom from the guardian.

```
Guardian (this session) ──spawns──► Orchestrator A (orch-epic1) ──delegates──► Workers
                        ──spawns──► Orchestrator B (orch-epic2) ──delegates──► Workers
```

### Pre-flight Checks

Before spawning, verify:
- [ ] Implementation repo exists and is accessible
- [ ] PRD exists in `.taskmaster/docs/PRD-{ID}.md` (business artifact)
- [ ] SD exists per epic in `.taskmaster/docs/SD-{ID}.md` (technical spec; Task Master input)
- [ ] Acceptance tests have been created from SD (Phase 1 complete)
- [ ] DOT pipeline exists (or create via `cli.py generate`) with bead IDs mapped to nodes
- [ ] DOT codergen nodes have `solution_design` attribute pointing to their SD file
- [ ] No existing tmux session with the same name
- [ ] Hindsight wisdom gathered from project bank

### Gather Wisdom from Hindsight

Before spawning each orchestrator, query the project Hindsight bank:

```python
PROJECT_BANK = os.environ.get("CLAUDE_PROJECT_BANK", "claude-harness-setup")
wisdom = mcp__hindsight__reflect(
    query=f"What patterns apply to {epic_name}? Any anti-patterns or lessons for this domain?",
    budget="mid",
    bank_id=PROJECT_BANK
)
# Include the wisdom output in the orchestrator's initialization prompt
```

### DOT Pipeline-Driven Dispatch

When a DOT pipeline exists, identify dispatchable nodes before spawning:

```bash
PIPELINE="/path/to/impl-repo/.claude/attractor/pipelines/${INITIATIVE}.dot"
CLI="python3 /path/to/impl-repo/.claude/scripts/attractor/cli.py"

# Find nodes with all upstream deps validated
$CLI status "$PIPELINE" --filter=pending --deps-met --json

# Transition node to active before dispatch (one per orchestrator)
$CLI transition "$PIPELINE" <node_id> active
$CLI checkpoint save "$PIPELINE"
```

Each orchestrator targets one pipeline node. Include the node's `acceptance`, `worker_type`, `file_path/folder_path`, and `bead_id` attributes in the initialization prompt.

### Critical tmux Patterns

**These patterns are mandatory. Violating them causes silent failures.**

**Pattern 1 — Enter as separate send-keys call** (not appended to the command):
```bash
# WRONG — Enter gets silently ignored
tmux send-keys -t "orch-epic1" "ccorch" Enter

# CORRECT
tmux send-keys -t "orch-epic1" "ccorch"
tmux send-keys -t "orch-epic1" Enter
```

**Pattern 2 — Use `ccorch` not plain `claude`** (prevents invisible permission dialog blocks):
```bash
# WRONG — orchestrator blocks silently on approval dialogs
tmux send-keys -t "orch-epic1" "claude"
tmux send-keys -t "orch-epic1" Enter

# CORRECT
tmux send-keys -t "orch-epic1" "ccorch"
tmux send-keys -t "orch-epic1" Enter
```

**Pattern 3 — Interactive mode is MANDATORY** (headless orchestrators cannot spawn native teams):
```bash
# WRONG — headless mode cannot spawn workers
claude -p "Do the work"

# CORRECT — interactive allows team spawning
tmux send-keys -t "orch-epic1" "ccorch"
tmux send-keys -t "orch-epic1" Enter
```

**Pattern 4 — Large pastes need `sleep 2` before Enter** (bracketed paste processing takes time):
```bash
tmux send-keys -t "orch-epic1" "$(cat /tmp/wisdom-epic1.md)"
sleep 2   # Wait for bracketed paste to complete
tmux send-keys -t "orch-epic1" Enter
```

### The Mandatory 3-Step Boot Sequence

Every orchestrator MUST go through these 3 steps in this exact order. No exceptions.

```
Step 1: ccorch          → Sets 9 env vars (output style, session ID, agent teams, etc.)
Step 2: /output-style   → Loads orchestrator persona and delegation rules
Step 3: Skill prompt    → Orchestrator invokes Skill("orchestrator-multiagent") before any work
```

Skipping ANY step produces a crippled orchestrator that either:
- Has no delegation rules (missing Step 2) → tries to implement directly
- Has no team coordination patterns (missing Step 3) → cannot spawn workers
- Has no session tracking, no model selection, no chrome (missing Step 1) → everything breaks silently

### Spawn Sequence: Use `spawn_orchestrator.py` (MANDATORY)

**Always use the canonical spawn script.** Never write ad-hoc tmux Bash for spawning.

The script at `.claude/scripts/attractor/spawn_orchestrator.py` handles:
- tmux session creation with `exec zsh` and correct dimensions
- `unset CLAUDECODE && ccorch --worktree <node_id>` (Step 1)
- `/output-style orchestrator` (Step 2)
- Prompt delivery (Step 3)
- Pattern 1 (Enter as separate send-keys call)
- Respawn logic if session dies

**CRITICAL: `IMPL_REPO` must point to the directory that contains `.claude/`** — this is the Claude Code project root. For monorepo layouts like `zenagent2/zenagent/agencheck/`, the project root is at `agencheck/` (where `.claude/output-styles/`, `.claude/settings.json`, etc. live), NOT at a subdirectory like `agencheck-support-agent/` or `agencheck-support-frontend/`. Spawning at the wrong level means the orchestrator boots without output styles, hooks, or skills.

```bash
EPIC_NAME="epic1"
# ✅ CORRECT: points to directory containing .claude/
IMPL_REPO="/path/to/impl-repo/agencheck"
# ❌ WRONG: subdirectory — no .claude/ here, orchestrator boots broken
# IMPL_REPO="/path/to/impl-repo/agencheck/agencheck-support-agent"  # DON'T use subdirectories!
PRD_ID="PRD-XXX-001"

# 1. Write the wisdom/prompt to a temp file FIRST
#    SD_PATH is the solution_design attribute from the DOT node
#    e.g., SD_PATH=".taskmaster/docs/SD-AUTH-001-login.md"
cat > "/tmp/wisdom-${EPIC_NAME}.md" << 'WISDOMEOF'
You are an orchestrator for initiative: ${EPIC_NAME}

> Your output style was set to "orchestrator" by the guardian during spawn.

## FIRST ACTIONS (Mandatory — do these BEFORE any investigation or implementation)
1. Skill("orchestrator-multiagent")   ← This loads your delegation patterns
2. Teammate(operation="spawnTeam", team_name="${EPIC_NAME}-workers", description="Workers for ${EPIC_NAME}")

## Your Mission
${EPIC_DESCRIPTION}

## Solution Design (Primary Technical Reference)
Your full technical specification is in: ${SD_PATH}
Read it before delegating to workers. Key sections:
- Section 2: Technical Architecture (data models, API contracts, component design)
- Section 4: Functional Decomposition (features with explicit dependencies)
- Section 6: Acceptance Criteria per Feature (definition of done for each worker task)
- Section 8: File Scope (which files workers are allowed to touch)

## DOT Node Scope (pipeline-driven)
- Node ID: ${NODE_ID}
- Acceptance: "${ACCEPTANCE_CRITERIA}"
- File Scope: ${FILE_PATHS} (see SD Section 8 for full scoping)
- Bead ID: ${BEAD_ID}

## Patterns from Hindsight
${WISDOM_FROM_HINDSIGHT}

## On Completion
Update bead to impl_complete: bd update ${BEAD_ID} --status=impl_complete
WISDOMEOF

# 2. Spawn via canonical script (handles Steps 1-3 of the boot sequence)
python3 "${IMPL_REPO}/.claude/scripts/attractor/spawn_orchestrator.py" \
    --node "${EPIC_NAME}" \
    --prd "${PRD_ID}" \
    --repo-root "${IMPL_REPO}" \
    --prompt "Read the file at /tmp/wisdom-${EPIC_NAME}.md and follow those instructions. Your FIRST ACTION must be: Skill(\"orchestrator-multiagent\")"

# 3. Verify spawn succeeded (script outputs JSON)
# {"status": "ok", "session": "orch-epic1", ...}
```

**What `spawn_orchestrator.py` does internally** (you should NOT replicate this manually):
1. Creates tmux session with `exec zsh` in `--repo-root` directory
2. Sends `unset CLAUDECODE && ccorch --worktree <node>` (8s pause) — **Step 1**
3. Sends `/output-style orchestrator` (3s pause) — **Step 2**
4. Sends the `--prompt` text (2s pause) — **Step 3**
5. All sends use Pattern 1 (Enter as separate call)

### Anti-Pattern: Ad-Hoc Bash Spawn (NEVER DO THIS)

The following code was found in a real session. It produces a **broken orchestrator** that lacks output style, delegation patterns, session tracking, and agent team support:

```bash
# ❌ WRONG — 5 critical violations that produce a crippled orchestrator
tmux new-session -d -s "orch-v2-ux" -c "$WORK_DIR"
sleep 1
tmux send-keys -t "orch-v2-ux" "exec zsh" Enter           # ❌ Pattern 1: Enter appended
sleep 2
tmux send-keys -t "orch-v2-ux" "unset CLAUDECODE && cd $WORK_DIR && claude --dangerously-skip-permissions" Enter
#                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                                    ❌ Uses plain `claude` instead of `ccorch`
#                                    ❌ Missing: output style, session ID, agent teams,
#                                       task list, project bank, model, chrome flag
sleep 10
tmux send-keys -t "orch-v2-ux" "$WISDOM"                   # ❌ No /output-style step
sleep 2                                                      # ❌ No Skill("orchestrator-multiagent")
tmux send-keys -t "orch-v2-ux" "" Enter
```

**Why each violation matters:**

| Violation | Consequence |
|-----------|-------------|
| `claude` instead of `ccorch` | No `CLAUDE_OUTPUT_STYLE`, no `CLAUDE_SESSION_ID`, no `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, no `--model claude-opus-4-6`, no `--chrome`. Orchestrator boots as a generic Claude session. |
| No `/output-style orchestrator` | Orchestrator has no delegation rules — will try to implement code directly instead of spawning workers. |
| No `Skill("orchestrator-multiagent")` in prompt | Orchestrator doesn't know HOW to create teams, delegate tasks, or coordinate workers. |
| `Enter` appended to command | tmux may silently drop the Enter key, causing commands to not execute. |
| Direct paste instead of file reference | Large wisdom text can overflow tmux paste buffer, causing truncation. |
| `IMPL_REPO` points to subdirectory instead of `.claude/` root | Orchestrator boots without output styles, hooks, or skills. e.g., using `agencheck-support-agent/` instead of `agencheck/`. |

**The fix is always the same:** Use `spawn_orchestrator.py` with `--repo-root` pointing to the directory that contains `.claude/`.

### Parallel Spawning (Multiple Epics)

When multiple DOT nodes have no dependency relationship, spawn orchestrators in parallel:

```bash
# Check edges to confirm independence before parallel dispatch
cobuilder pipeline edge-list "${PIPELINE}" --output json

# Spawn each independent node as a separate orchestrator
for NODE_ID in node1 node2 node3; do
    EPIC_NAME="${NODE_ID}"
    # ... run spawn sequence above for each ...
done
```

### After Spawn: Communication Hierarchy

The guardian monitors orchestrators DIRECTLY:

```
Guardian ──monitors──► Orchestrator ──delegates──► Workers (native teams)
   │                       ▲
   └──── sends guidance ───┘
```

| Action | Target | When |
|--------|--------|------|
| Send guidance/corrections | Orchestrator tmux session | Primary channel |
| Monitor output (read-only) | Orchestrator tmux session | Continuous |
| Answer AskUserQuestion | Whichever session shows the dialog | Immediately (blocks are time-critical) |

Proceed to **Phase 3: Monitoring** after all orchestrators are spawned and running.

---

## Phase 3: Monitoring

Continuously monitor orchestrator progress via tmux. Monitoring cadence adapts to activity level.

### Monitoring Cadence

| Phase | Interval | Rationale |
|-------|----------|-----------|
| Active implementation | 30s | Catch errors early, detect AskUserQuestion blocks |
| Investigation/planning | 60s | Orchestrator is reading/thinking, less likely to block |
| Idle / waiting for workers | 120s | Nothing to intervene on |

### Core Monitoring Loop

```bash
# Capture recent output (per orchestrator session)
tmux capture-pane -t "orch-{epic}" -p -S -100

# Check for key signals
tmux capture-pane -t "orch-{epic}" -p -S -100 | grep -iE "error|stuck|complete|failed|AskUser|permission"

# Monitor multiple orchestrators in parallel
for SESSION in orch-epic1 orch-epic2 orch-epic3; do
    echo "=== $SESSION ===" && tmux capture-pane -t "$SESSION" -p -S -20 2>/dev/null || echo "(not running)"
done
```

### Intervention Triggers

| Signal | Action |
|--------|--------|
| `AskUserQuestion` / permission dialog | Answer via `tmux send-keys` (Down, Enter) |
| Repeated error (3+ occurrences) | Send guidance or restart |
| No output for 5+ minutes | Check if context is exhausted |
| Scope creep (files outside epic scope) | Send corrective instruction |
| `TODO` / `FIXME` markers accumulating | Flag for later cleanup |
| Time exceeded (2+ hours) | Assess progress, consider intervention |

### Sending Guidance

The guardian communicates directly with orchestrators:

```bash
# Send corrective instruction (Pattern 1: separate Enter)
tmux send-keys -t "orch-{epic}" "GUARDIAN: Focus on {correct scope}. Do not modify {out-of-scope files}."
tmux send-keys -t "orch-{epic}" Enter

# Send unblocking guidance
tmux send-keys -t "orch-{epic}" "GUARDIAN: The issue is {root cause}. Fix: {specific fix}."
tmux send-keys -t "orch-{epic}" Enter
```

### AskUserQuestion Handling

When an orchestrator or worker hits an AskUserQuestion dialog:

```bash
# Navigate to the appropriate option and confirm
tmux send-keys -t "orch-{epic}" Down
tmux send-keys -t "orch-{epic}" Enter
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
cobuilder pipeline transition .claude/attractor/pipelines/<pipeline>.dot <node_id> validated

# If validation fails, transition to 'failed'
cobuilder pipeline transition .claude/attractor/pipelines/<pipeline>.dot <node_id> failed

# Save checkpoint after any transition
cobuilder pipeline checkpoint-save .claude/attractor/pipelines/<pipeline>.dot
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
    run(f"cobuilder pipeline transition .claude/attractor/pipelines/<pipeline>.dot {node_id} {status}")
    run(f"cobuilder pipeline checkpoint-save .claude/attractor/pipelines/<pipeline>.dot")

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

Before dispatching scoring agents for each feature, provide the scoring agent with both:
- The **Gherkin scenario** (blind rubric from Phase 1, generated from the SD)
- The **SD document** for this epic (`solution_design` attribute on the DOT node, or from
  `.taskmaster/docs/SD-{CATEGORY}-{NUMBER}-{epic-slug}.md`)

The SD contains the file scope, API contracts, and per-feature acceptance criteria that tell
the scoring agent exactly what "done" looks like. Without it, agents score on gut feel rather
than specification.

```python
# Read SD path from DOT node or construct from naming convention
sd_path = node_attrs.get("solution_design", f".taskmaster/docs/SD-{epic_id}.md")

# Build per-feature scoring prompt
scoring_prompt = f"""
You are scoring the implementation of this feature against its acceptance rubric.

**Solution Design** (read this first — it defines done):
{sd_path}

Key sections to check:
- Section 4: Functional Decomposition (is each capability implemented?)
- Section 6: Acceptance Criteria per Feature (per-feature definition of done)
- Section 8: File Scope (were only allowed files modified?)

**Feature scenario to score:**
[scenario text from Gherkin file]
"""
```

Also read `validation_method` from the manifest and prepend mandatory tooling instructions:

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

Journey tests were generated from the **PRD** (`PRD-{ID}.md`) — they verify cross-epic business
flows that no single orchestrator owns. The runner should be given the PRD for context so it can
understand *why* each step exists, not just whether it passes.

**Execution approach** — spawn a tdd-test-engineer sub-agent:

```python
Task(
    subagent_type="tdd-test-engineer",
    description="Execute journey tests for PRD-{ID}",
    prompt="""
    Execute the journey test scenarios at: acceptance-tests/PRD-{ID}/journeys/

    Context: these tests were generated from .taskmaster/docs/PRD-{ID}.md and validate
    end-to-end business flows that span multiple implementation epics. Read the PRD
    Goals section (Section 2) to understand the business outcomes being verified.

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
    --ac "PRD designed, pipeline created, and design challenge passed (Phase 0)" \
    --ac "Acceptance tests and executable browser tests created in config repo" \
    --ac "Orchestrator(s) spawned and verified running" \
    --ac "Orchestrator progress monitored through completion" \
    --ac "Independent validation scored against rubric" \
    --ac "Final verdict delivered with evidence"
```

### During Monitoring

```bash
# Meet criteria as work progresses
cs-promise --meet <id> --ac-id AC-1 --evidence "acceptance-tests/PRD-{ID}/ created with N scenarios + executable browser tests" --type manual
cs-promise --meet <id> --ac-id AC-2 --evidence "tmux session orch-{initiative} running, output style verified" --type manual
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
| 0. PRD Design | Write PRD, ZeroRepo analysis, pipeline, design challenge | [this skill — Phase 0] |
| 1. Acceptance Tests | Gherkin rubrics + executable browser tests (Step 3) | [gherkin-test-patterns.md](references/gherkin-test-patterns.md) |
| 2. Orchestrator Spawn | DOT dispatch, tmux patterns, wisdom inject, `ccorch --worktree` | [guardian-workflow.md](references/guardian-workflow.md) |
| 3. Monitoring | capture-pane loop, intervention triggers | [monitoring-patterns.md](references/monitoring-patterns.md) |
| 4. Validation | Score scenarios, run executable tests, weighted total | [validation-scoring.md](references/validation-scoring.md) |
| 4.5 Regression | ZeroRepo diff before journey tests | [this skill — Phase 4.5] |

### Key Files

| File | Purpose |
|------|---------|
| `acceptance-tests/PRD-{ID}/manifest.yaml` | Feature weights, thresholds, metadata |
| `acceptance-tests/PRD-{ID}/*.feature` | Gherkin scenarios with scoring guides |
| `acceptance-tests/PRD-{ID}/executable-tests/` | Browser automation test scripts (UX PRDs) |
| `acceptance-tests/PRD-{ID}/design-challenge.md` | Phase 0 design challenge results |
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
| Skipping design challenge (Phase 0) | Flawed PRDs propagate through entire pipeline | Always run Step 0.4 |
| Ignoring AMEND verdict | Sunk cost fallacy — beads already exist | Re-parse is cheap, bad design is expensive |
| Only writing scoring rubrics for UX PRDs | Cannot automatically verify browser behavior | Write executable-tests/ alongside scenarios.feature |
| Scoring UX at 0.9 from code reading alone | Code may compile but render incorrectly | Executable browser tests cap/floor confidence scores |
| Ad-hoc Bash spawn (plain `claude` in tmux) | Missing output style, session ID, agent teams, model — orchestrator is crippled | Always use `spawn_orchestrator.py` |
| Skipping `/output-style orchestrator` step | Orchestrator has no delegation rules, tries to implement directly | Script handles this automatically |
| Wisdom without `Skill("orchestrator-multiagent")` | Orchestrator cannot create teams or delegate to workers | Include in `--prompt` or wisdom file |

---

**Version**: 0.2.1
**Dependencies**: cs-promise CLI, tmux, Hindsight MCP, ccsystem3 shell function, Task Master MCP, ZeroRepo
**Integration**: system3-orchestrator skill, completion-promise skill, acceptance-test-writer skill, parallel-solutioning skill, research-first skill
**Theory**: Independent verification eliminates self-reporting bias in agentic systems

**Changelog**:
- v0.2.1: Replaced inline Bash spawn sequence with mandatory `spawn_orchestrator.py` usage. Added "Mandatory 3-Step Boot Sequence" section. Added "Anti-Pattern: Ad-Hoc Bash Spawn" with real-world example showing 5 violations. Added 3 new anti-patterns to table. Root cause: inline Bash in Phase 2 invited copy-paste adaptation that dropped ccorch, /output-style, and Skill("orchestrator-multiagent").
- v0.2.0: Added Phase 0 (PRD Design & Challenge) with ZeroRepo analysis, Task Master parsing, beads sync, and mandatory design challenge via parallel-solutioning + research-first. Added executable browser test scripts (Phase 1, Step 3) for UX PRDs with claude-in-chrome MCP tool mapping. Updated promise template with AC-0. Added 4 new anti-patterns. Lesson learned: PRD-P1.1-UNIFIED-FORM-001 had 17 Gherkin scoring rubrics but zero executable tests — the guardian could not automatically verify browser behavior.
- v0.1.0: Initial release — blind Gherkin acceptance tests, tmux monitoring, gradient confidence scoring, DOT pipeline integration, SDK mode.
