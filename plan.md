# Plan: Align Skills and Output Styles with PRD/SD Document Separation

## Background

We are adopting a BMAD-inspired document separation where:
- **PRD** = business artifact (operator/System 3 writes and reads, stable reference)
- **SD (Solution Design)** = automation input (architect writes, Task Master parses, orchestrators consume)

The pipeline becomes:
```
PRD → solution-design-architect → SD (business context + tech design)
                                        │
                                        ├─→ Task Master (parse SD → tasks)
                                        ├─→ Beads (epic/story hierarchy)
                                        ├─→ Orchestrator brief
                                        └─→ acceptance-test-writer
```

**Templates created**: `.taskmaster/templates/prd-template.md` and `.taskmaster/templates/solution-design-template.md`

## What Needs to Change

### Change 1: `orchestrator-multiagent/SKILL.md` — Phase 1: Planning

**File**: `.claude/skills/orchestrator-multiagent/SKILL.md` (lines ~291-388)

**Current**: Phase 1 planning workflow says:
- "Create PRD from design document"
- `task-master parse-prd docs/prds/prd.md`
- Acceptance tests generated from PRD

**New**: Phase 1 should reference the TWO-DOCUMENT model:
- PRD already exists (created by operator/System 3 in Phase 0)
- Orchestrator creates SD per epic via `solution-design-architect` worker
- `task-master parse-prd .taskmaster/docs/SD-{ID}.md` (parse the SD, not the PRD)
- Acceptance tests generated from SD (which includes business context section)
- SD documents live in `.taskmaster/docs/` alongside PRDs

**Specific edits**:
- Update step 2 comment: "Create SD from PRD (if not exists)" instead of "Create PRD from design document"
- Update step 4: Change `task-master parse-prd docs/prds/prd.md` → `task-master parse-prd .taskmaster/docs/SD-{CATEGORY}-{NUMBER}-{epic-slug}.md`
- Update step 6: Change acceptance-test-writer `--source` to point to SD
- Add a note about SD template location: `.taskmaster/templates/solution-design-template.md`
- Add guidance: "Each epic gets its own SD. The SD includes a Business Context section summarizing the relevant PRD goals."

### Change 2: `orchestrator-multiagent/WORKFLOWS.md` — 4-Phase Pattern

**File**: `.claude/skills/orchestrator-multiagent/WORKFLOWS.md`

**Current**: References PRDs as the input for task creation and feature decomposition.

**New**: Clarify that the SD is the primary input for:
- Feature decomposition (Section 4: Functional Decomposition in SD)
- Task creation (Task Master parses SD)
- Worker briefing (orchestrators reference SD for tech context)
- PRD is referenced only for business validation

### Change 3: `output-styles/orchestrator.md` — 4-Phase Pattern

**File**: `.claude/output-styles/orchestrator.md` (lines ~223-237)

**Current**: Phase 2 (Planning) says:
- `PRD -> Task Master -> Beads hierarchy -> Acceptance Tests`
- `Parse PRD with task-master parse-prd --append`

**New**: Update to show two-document flow:
- `PRD -> SD (per epic) -> Task Master -> Beads -> Acceptance Tests`
- `Parse SD with task-master parse-prd --append` (SD is what Task Master consumes)
- Add note: "SD documents combine business context + technical design — see `.taskmaster/templates/solution-design-template.md`"

### Change 4: `output-styles/system3-meta-orchestrator.md` — Skill Quick-Reference & Planning

**File**: `.claude/output-styles/system3-meta-orchestrator.md`

**Current** (line ~941): "Kick off a new initiative / PRD → acceptance-test-writer first, then system3-orchestrator"
**Current** (line ~974): "Planning — creating PRDs, solution designs (documents, not code)"

**New**:
- Update skill quick-reference to include SD creation step: "Kick off a new initiative → Write PRD → Create SD per epic (via `solution-design-architect`) → `acceptance-test-writer` (from SD) → `system3-orchestrator`"
- Update the "When System 3 Can Work Directly" section to clarify: "Planning — creating PRDs (business-level); SDs are created by solution-design-architect workers"
- Clarify that System 3 writes PRDs but delegates SD creation to architects

### Change 5: `s3-guardian/SKILL.md` — Phase 1: Acceptance Test Creation

**File**: `.claude/skills/s3-guardian/SKILL.md` (lines ~134-183)

**Current**: Phase 1 generates acceptance tests from PRDs:
- `Skill("acceptance-test-writer", args="--source=/path/to/PRD-{ID}.md --mode=guardian")`
- "Generate blind acceptance tests from PRDs"

**New**: Acceptance tests should be generated from SDs (which include business context):
- `Skill("acceptance-test-writer", args="--source=.taskmaster/docs/SD-{ID}.md --mode=guardian")`
- "Generate blind acceptance tests from Solution Designs"
- Add note: "The SD's Business Context section provides the goals/metrics needed for meaningful acceptance criteria. The SD's Acceptance Criteria section (Section 6) provides per-feature Gherkin-ready criteria."
- Update Phase 1 heading or description to reference SDs
- Also update Phase 2 spawning: the wisdom injection template should reference SDs for technical context, not just PRDs for scope

### Change 6: `s3-guardian/SKILL.md` — Phase 2: Orchestrator Spawning

**File**: `.claude/skills/s3-guardian/SKILL.md` (lines ~186-341)

**Current**: Wisdom injection template references `${EPIC_DESCRIPTION}` and `${ACCEPTANCE_CRITERIA}` pulled from DOT nodes which reference PRDs.

**New**: Add SD reference to the wisdom injection:
- Add `SD_PATH` variable to the spawn sequence
- Include `## Solution Design` section in the wisdom template that points to the SD document
- Orchestrators should load the SD as their primary technical reference
- DOT node `solution_design` attribute should point to SD file path

### Change 7: `orchestrator-multiagent/SKILL.md` — Phase 0: Ideation

**File**: `.claude/skills/orchestrator-multiagent/SKILL.md` (lines ~218-229)

**Current**: Phase 0 outputs "Design document, implementation plan, research notes"

**New**: Clarify that Phase 0 outputs a PRD (business-level), and Phase 1 begins by creating SDs from that PRD:
- Phase 0 output: "PRD document (business goals, user stories, architectural decisions)"
- Phase 1 prerequisite: "PRD exists → Create SD per epic → Parse SD with Task Master"

### Change 8: `orchestrator-multiagent/PREFLIGHT.md` — Session Start

**File**: `.claude/skills/orchestrator-multiagent/PREFLIGHT.md`

Review and update any references to PRD-as-input to clarify the SD role. If preflight references reading PRDs for context, add: "For technical context, read the relevant SD document."

## What Does NOT Change

- **Template files** — already created (`.taskmaster/templates/`)
- **DOT pipeline schema** — `solution_design` attribute already exists on nodes
- **validation-test-agent** — already uses `--prd=PRD-XXX` flag; the naming stays but it can reference SDs
- **acceptance-test-runner** — no changes needed (runs stored tests)
- **Beads integration** — no changes (beads track work items, agnostic to document source)
- **Worker skills** — workers receive briefings from orchestrators; they don't read PRDs or SDs directly
- **Hook system** — no changes needed

## Implementation Order

1. **orchestrator output-style** (Change 3) — loaded at 100%, highest impact
2. **system3 output-style** (Change 4) — loaded at 100% for S3 sessions
3. **orchestrator-multiagent SKILL.md** (Changes 1, 7) — Phase 0/1 planning workflow
4. **orchestrator-multiagent WORKFLOWS.md** (Change 2) — detailed workflow reference
5. **orchestrator-multiagent PREFLIGHT.md** (Change 8) — session start reference
6. **s3-guardian SKILL.md** (Changes 5, 6) — acceptance test creation + spawning

## Risk Assessment

- **LOW risk**: These are documentation/skill changes, not code changes
- **Backward compatible**: Existing PRDs in `.taskmaster/docs/` still work; SD is additive
- **Gradual adoption**: Orchestrators and guardians will use SDs when available, fall back to PRDs when not
