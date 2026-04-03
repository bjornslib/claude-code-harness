# Session Handoff: GasCity Integration — Planning + Spike

## Last Action
Completed two pipelines (GASCITY-INT-001-research + GASCITY-INT-001-spike). Strategic pivot: CoBuilder becomes a GasCity quality pack, not a competing orchestrator. Created enhanced spike beads for hands-on validation.

## Strategic Decisions (User-Approved via AskUserQuestion)

1. **Integration model**: GasCity pack (`packs/cobuilder-verified/`)
2. **DOT format**: Keep as authoring format → transpile to `.formula.toml` (transpiler in **Go**, not Python)
3. **Guardian role**: Convergence evaluator (controller-driven, no separate agent)
4. **Mayor as DOT author**: Mayor emits DOT graph as plan artifact, transpiler converts to quality-gated formula
5. **First deliverable**: Research spike (hands-on GasCity locally) before committing to architecture
6. **Planning model**: Three roles — Planner (enhanced Mayor + human), Architect (research→refine→codergen), Validator (convergence evaluator)

## Three-Role Architecture

| Role | Agent | What They Do |
|------|-------|-------------|
| **Planner** | Enhanced Mayor + human | Co-author BS with multiple human gates (BS-review, TS-review, direction-approval) |
| **Architect** | Rig-scoped agent | Research→refine→codergen pipeline (our proven pattern), parallel solutioning for TS |
| **Validator** | Convergence evaluator | Blind acceptance tests + gradient scoring via `evaluate_prompt` |

## Open Beads (Next Session Work)

### P0 — Must validate first (blocking)
- `claude-harness-setup-bf4b`: **Mayor conversation context** — does Mayor maintain context across formula steps? If not, collaborative BS co-authoring breaks
- `claude-harness-setup-e442`: **Multi-gated formula execution** — create minimal 3-gate formula, verify controller pauses/resumes correctly

### P1 — Design work (blocked by P0)
- `claude-harness-setup-8r1k`: **Enhanced mol-idea-to-plan** — add BS-review, TS-review, acceptance-test-generation gates
- `claude-harness-setup-iark`: **Architect agent design** — rig-scoped agent running research→refine→codergen as formula

### Template task
- Task #6: Create reusable DOT template for BS-to-TS research pipeline

## Completed This Session

### Pipeline 1: GASCITY-INT-001-research (Sonnet 4.6)
- BS: PRD-GASCITY-INT-001 v1.1.0 (refined with exact Go source mappings)
- TS: SD-GASCITY-INT-001 v1.1.0 (1318+ lines, integrates all research findings)
- Evidence: 3 research docs in `.pipelines/pipelines/evidence/`

### Pipeline 2: GASCITY-INT-001-spike (GLM-5)
- 3 research nodes: build/bootstrap (427 lines), convergence internals (568 lines), metadata/formulas (525 lines)
- 1 refine node: architecture proposal refined with all findings
- Key discovery: convergence `evaluate_prompt` is exactly where quality scoring injects

### Key Artifacts
- `docs/prds/gascity-integration/PRD-GASCITY-INT-001.md` — BS v1.1.0
- `docs/sds/gascity-integration/SD-GASCITY-INT-001.md` — TS v1.1.0
- `docs/diagrams/gascity-cobuilder-integration.svg` — architecture diagram
- `.claude/progress/gascity-architecture-research-20260403.md` — initial research synthesis
- `workspace/gascity/` — cloned GasCity repo
- `.pipelines/pipelines/evidence/GASCITY-INT-001-spike/` — 3 spike research docs

## Hindsight State
Server unreachable (port 8888 Docker). File-based fallbacks:
- `memory/project_gascity_architecture_research.md`
- `memory/project_gascity_prd_refinement.md`
Retain to both banks (`cobuilder-guardian` + `claude-code-cobuilder-harness`) when server recovers.

## Next Session Plan
1. Build `gc` binary from `workspace/gascity/` source
2. `gc init` a test city, run swarm pack with a rig
3. Test Mayor conversation context across formula steps (P0 blocker)
4. Test multi-gated formula execution (P0 blocker)
5. If both pass → design enhanced mol-idea-to-plan + architect agent
6. If context breaks → investigate crew agents or session persistence patterns
