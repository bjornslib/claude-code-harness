# Session Handoff: GasCity Integration — Hands-On Spike Ready

## Last Action
Created hands-on spike pipeline at `.pipelines/pipelines/GASCITY-INT-001-handson.dot` (validated, 13 nodes). Two prior pipelines completed this session. Beads synced, Hindsight retained to both banks.

## Pipeline: GASCITY-INT-001-handson

### Structure
```
Phase 1: research_build         — Build gc binary, gc init city, run swarm, register rig, verify agents
Phase 2: research_context       — P0: Does Mayor maintain context across formula steps?
         research_multigate     — P0: Do multi-gated formulas work?
         refine_ts_validation   — Compare TS assumptions against hands-on reality
         gate_p0 + review_p0   — Guardian + human review of TS validity
Phase 3: design_mayor           — Enhanced mol-idea-to-plan with 3 human gates + acceptance tests
         design_architect       — Rig-scoped Architect agent with research→refine→codergen formula
         gate_design + review   — Guardian + human review of designs
```

### Launch Command
```bash
python3 cobuilder/engine/pipeline_runner.py --dot-file .pipelines/pipelines/GASCITY-INT-001-handson.dot
```
LLM profile: `alibaba-glm5` (near-zero cost) for all nodes.

### Expected Outcome
1. GasCity running locally with swarm pack and this repo as a rig
2. TS design assumptions validated or invalidated against hands-on evidence
3. Enhanced Mayor formula design (mol-cobuilder-plan.formula.toml)
4. Architect agent design (mol-architect-work.formula.toml)

## Strategic Context (User-Approved Decisions)

### CoBuilder's Role
CoBuilder is NOT a competing orchestrator. It becomes `packs/cobuilder-verified/` — a GasCity quality pack adding:
- Blind acceptance testing (hidden from workers)
- Gradient quality scoring (0.0-1.0 per acceptance criterion)
- Guardian convergence evaluation (via `evaluate_prompt`)
- Quality-gated formulas (human gates for BS-review, TS-review, direction-approval)

### Three-Role Architecture
| Role | Agent | Integration |
|------|-------|-------------|
| **Planner** | Enhanced Mayor + human | mol-cobuilder-plan formula with 3+ human gates |
| **Architect** | Rig-scoped agent | research→refine→codergen formula (our proven pattern) |
| **Validator** | Convergence evaluator | evaluate_prompt with blind acceptance tests + scoring |

### Key Technical Decisions
- **DOT format**: Keep as authoring format → transpile to `.formula.toml` (transpiler in **Go**)
- **Mayor DOT authoring**: Teach Mayor to emit DOT graphs as plan artifacts
- **Guardian**: Convergence evaluator (controller-driven, no separate agent session)
- **Integration**: GasCity pack, not sidecar or upstream PR

## Completed This Session

### Pipelines Executed
1. **GASCITY-INT-001-research** (Sonnet 4.6): BS v1.1 + TS v1.1 (1318 lines)
2. **GASCITY-INT-001-spike** (GLM-5): 3 research docs (1520 lines) on build, convergence, metadata

### Key Discoveries
- Convergence `evaluate_prompt` = quality gate injection point
- Bead metadata = `string→string` with `gc.*`/`convergence.*` namespaces
- Formula compilation = 11-stage pipeline (TOML→Recipe)
- `mol-idea-to-plan` ≈ our `cobuilder-lifecycle` but with only 1 human gate
- `gc` binary clashes with GraphViz at `/usr/local/bin/gc`

### Artifacts
- `docs/prds/gascity-integration/PRD-GASCITY-INT-001.md` — BS v1.1.0
- `docs/sds/gascity-integration/SD-GASCITY-INT-001.md` — TS v1.1.0
- `docs/diagrams/gascity-cobuilder-integration.svg` — architecture diagram
- `workspace/gascity/` — cloned GasCity repo (built binary TBD)
- `.pipelines/pipelines/evidence/GASCITY-INT-001-spike/` — 3 research docs

### Open Beads
- `claude-harness-setup-h4ey` (epic, open): Research Spike umbrella
- `claude-harness-setup-bf4b` (P0): Mayor context persistence
- `claude-harness-setup-e442` (P0): Multi-gated formula test
- `claude-harness-setup-8r1k` (P1): Enhanced Mayor formula design
- `claude-harness-setup-iark` (P1): Architect agent design

### Hindsight
Retained to both banks (`cobuilder-guardian` + `claude-code-cobuilder-harness`). Server recovered mid-session after Docker port 8888 issue.
