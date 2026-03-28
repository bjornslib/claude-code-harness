---
name: cobuilder:ideation-to-execution
description: This skill should be used when the user asks to "brainstorm a feature", "create a PRD", "write a solution design", "plan a new initiative", "start a new project", "ideate on a feature", "brainstorm and build", "go from idea to implementation", or when CoBuilder needs to drive the complete ideation → PRD → SD → worktree → autonomous TDD pipeline.
version: 1.0.0
title: "Ideation to Execution"
status: active
type: skill
last_verified: 2026-03-21
grade: authoritative
---

# Ideation to Execution

End-to-end workflow from brainstorming through PRD, solution design, worktree creation, and autonomous TDD pilot launch. Inspired by the [superpowers](https://github.com/obra/superpowers) methodology.

**Core Principle**: Never jump to code. Discover → Design → Plan → Execute with TDD.

---

## Phase 1: Brainstorming (Discovery)

Modeled after superpowers:brainstorming — structured discovery through dialogue.

### Workflow

1. **Clarify goals** — Ask 2-3 focused questions about the initiative. What problem does it solve? Who benefits? What does success look like?
2. **Present designs in digestible sections** — Break the design into logical chunks. Present each for approval before moving on.
3. **Challenge assumptions** — Use `Skill("parallel-solutioning")` to generate 2-3 competing approaches. Evaluate trade-offs.
4. **Converge** — Synthesize the approved design sections into a coherent brief.

### Output

A brainstorm brief in `docs/brainstorms/{initiative-id}-brief.md` with:
- Problem statement
- Target users and impact
- Proposed approach (with rejected alternatives noted)
- Open questions resolved
- Success criteria (proto-acceptance criteria)

Template available at `references/brainstorm-template.md`.

---

## Phase 2: PRD Creation

Transform the brainstorm brief into a formal Product Requirements Document.

### Workflow

1. **Read brainstorm brief** — Load `docs/brainstorms/{initiative-id}-brief.md`
2. **Research domain** — Use `Skill("research-first")` to validate technical feasibility and framework choices
3. **Draft PRD** — Write to `docs/prds/PRD-{CATEGORY}-{NNN}.md` with required frontmatter:

```yaml
---
title: "Feature Title"
description: "One-line purpose"
version: "1.0.0"
last-updated: 2026-03-21
status: draft
type: prd
prd_id: PRD-{CATEGORY}-{NNN}
grade: authoritative
---
```

4. **Include acceptance criteria with validation methods** — Each requirement must have testable acceptance criteria written as Gherkin scenarios. Use the per-AC method tag format:
   ```
   AC-1 [browser-check]: Login form renders with email and password fields
   AC-2 [api-call]: POST /auth/login returns JWT with valid credentials
   AC-3 [unit-test]: Token TTL is configurable via environment variable
   AC-4 [code-review]: Error messages follow i18n pattern
   ```
   Valid tags: `[browser-check]`, `[api-call]`, `[unit-test]`, `[code-review]`. If omitted, the validator infers from file types.
5. **Generate blind acceptance tests** — Use `Skill("acceptance-test-writer")` to create executable test scripts from the PRD before any implementation begins. Each scenario should be tagged with `@browser-check`, `@api-call`, `@unit-test`, or `@code-review` matching the AC's method.

### PRD Structure

```markdown
## Problem Statement
## User Stories
## Requirements
### Functional Requirements (with Gherkin acceptance criteria)
### Non-Functional Requirements
## Technical Constraints
## Out of Scope
## Implementation Status
```

---

## Phase 3: Solution Design

Create the technical blueprint that workers will follow.

### Workflow

1. **Research-first** — Spawn research sub-agent with `Skill("research-first")` targeting frameworks, libraries, and patterns
2. **Architecture decisions** — Document key decisions with rationale and alternatives considered
3. **Write SD** — Create `docs/sds/SD-{CATEGORY}-{NNN}.md` with frontmatter (`type: sd`, `prd_ref: PRD-{CATEGORY}-{NNN}`)
4. **Task decomposition** — Break the SD into worker-sized tasks with:
   - Explicit file scope (which files each task touches)
   - Validation criteria per task
   - Dependencies between tasks
   - Worker type assignment (frontend-dev-expert, backend-solutions-engineer, etc.)

### SD Structure

```markdown
## Overview
## Architecture
## Component Design
## Data Model
## API Design (if applicable)
## Task Breakdown
### Task 1: [Name] (worker_type: frontend-dev-expert)
- Scope: [files]
- Acceptance:
  AC-1 [browser-check]: Login form renders with email and password fields
  AC-2 [api-call]: POST /auth/login returns JWT with valid credentials
  AC-3 [unit-test]: Token TTL is configurable via env var
- Dependencies: [none | task IDs]
### Task 2: ...
## Testing Strategy
## Implementation Status
```

---

## Phase 4: Worktree & Pipeline Setup

Create an isolated development environment and TDD pipeline.

### Workflow

1. **Create worktree** — Use `Skill("worktree-manager-skill")`:

```bash
git worktree add .worktrees/{initiative-id} -b feature/{initiative-id}
```

2. **Copy PRD and SD** — Ensure the worktree has access to PRD, SD, and blind acceptance tests

3. **Generate TDD pipeline** — Use `Skill("cobuilder:tdd-pipeline")` to instantiate the `tdd-validated` template from the SD task breakdown

4. **Configure worker powers** — The `tdd-validated` template automatically sets `worker_powers="tdd,systematic-debugging,verification"` on all codergen nodes

---

## Phase 5: Launch Autonomous TDD Pilot

Hand off to the pipeline runner for autonomous execution.

### Workflow

1. **Validate pipeline** — `python3 cobuilder/engine/cli.py validate {pipeline.dot}`
2. **Launch runner** — `python3 cobuilder/engine/pipeline_runner.py --dot-file {pipeline.dot}`
3. **Monitor via Haiku sub-agent** — Spawn blocking monitor that completes on gate detection, failure, or stall
4. **Handle gates via Pilot Gherkin Validation Protocol** — At each `wait.cobuilder` gate, the pilot independently:
   a. Reads the upstream node's acceptance criteria (with per-AC `[method]` tags)
   b. Reads the worker's completion signal and validator's scoring signal from `processed/`
   c. Writes its own `.feature` file: `acceptance-tests/{pipeline_id}/<gate>-pilot.feature`
   d. Executes each scenario using its tagged method (`@browser-check`, `@api-call`, `@unit-test`)
   e. Decides pass/fail based on actual execution results

### Signal-Based Communication

All pipeline nodes communicate via signal files:
- **Workers** write: `{status, files_changed, message}` — successors read these from `processed/`
- **Validators** write: `{result, scores, overall_score, criteria_results}` — pilots read for gate decisions
- **Runner** moves signals to `processed/` and injects signal history into retry prompts
- **Pilot** reads `processed/` signals to understand what happened before making gate decisions

Each node can see its predecessors' and successors' signal file paths via the "Pipeline Graph" section injected into its prompt.

---

## Quick Decision Tree

```
User says "I have an idea" or "Let's build X"
    → Phase 1: Brainstorm (cobuilder:brainstorming for sub-decisions)

Brainstorm approved
    → Phase 2: PRD + blind acceptance tests

PRD approved
    → Phase 3: Solution Design + task decomposition

SD approved
    → Phase 4: Worktree + TDD pipeline generation (cobuilder:tdd-pipeline)

Pipeline ready
    → Phase 5: Launch autonomous pilot (workers use cobuilder:tdd)
```

---

## Additional Resources

### Reference Files

- **`references/brainstorm-template.md`** — Template for brainstorm brief documents
