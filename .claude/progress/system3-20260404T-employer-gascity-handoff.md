# Session Handoff: Employer Contact + GasCity — Two Track Plan

## Two Tracks Ready

### Track A: Employer Contact Research Agent (NEXT — launch now)

**Pipeline**: `.pipelines/pipelines/EMPLOYER-CONTACT-E1-ptv.dot` (validated)
**Template**: `planner-tdd-validated` (new — Anthropic Planner→Worker→Validator pattern)
**Target**: `~/Documents/Windsurf/zenagent` (worktree)
**PRD**: `docs/prds/employer-contact-search/PRD-EMPLOYER-CONTACT-001.md`
**Epic**: E1 — Research Agent only (DSPy + Perplexity + Web Search)

```
Phase 1 (GLM-5):  research_codebase → research_domain → write_ts → [TS gate] → [human review]
Phase 2 (Sonnet):  red_tests (write failing tests) → [red gate]
Phase 3 (Sonnet):  green_impl (make tests pass) → [green gate]
Phase 4 (Sonnet):  validate (independent BS+TS check) → [validation gate] → [human review]
```

**Key decisions**:
- All worker nodes invoke `Skill('dspy-development')` mandatory
- Dual-source research: Perplexity Deep Research API + web search (Brave/Google)
- Contact classification: general vs named_poc with confidence scoring
- Tests: classification, scoring, dedup, prioritisation, integration
- Implementation in zenagent worktree, not harness

**Launch**:
```bash
# Create worktree first
cd ~/Documents/Windsurf/zenagent
git worktree add ../zenagent-employer-contact feature/employer-contact-research

# Then launch pipeline (update target_dir in DOT to point to worktree)
python3 cobuilder/engine/pipeline_runner.py --dot-file .pipelines/pipelines/EMPLOYER-CONTACT-E1-ptv.dot
```

**Before launch**: Create real beads and update `bead_id_planner` / `bead_id_impl` in the DOT file (currently PLACEHOLDER-*).

### Track B: GasCity Hands-On Spike (AFTER Track A)

**Pipeline**: `.pipelines/pipelines/GASCITY-INT-001-handson.dot` (validated)
**Goal**: Build gc locally, test Mayor context + multi-gate formulas, design enhanced Mayor + Architect
**Compare**: Could Track A have run natively in GasCity?

## New Template: planner-tdd-validated

Location: `.cobuilder/templates/planner-tdd-validated/`

Parameterised Jinja2 template implementing Anthropic's Planner→Worker→Validator pattern:
- **Planner**: 2 research nodes + 1 codergen (TS writing) + guardian gate + human review
- **Red**: TDD test engineer writes failing tests + guardian gate
- **Green**: Implementation worker makes tests pass + guardian gate
- **Validator**: Independent BS+TS audit + guardian gate + human review

Parameters: `prd_ref`, `bs_path`, `epic_id`, `epic_label`, `sd_output_path`, `worker_type`, `bead_id_planner`, `bead_id_impl`, `llm_profile*`, `test_command`, `cobuilder_root`, `target_dir`

## Session Artifacts

- `docs/prds/employer-contact-search/PRD-EMPLOYER-CONTACT-001.md` — copied from ~/Downloads/
- `docs/sds/employer-contact-search/SD-EMPLOYER-CONTACT-E1.md` — placeholder (Planner will write)
- `.cobuilder/templates/planner-tdd-validated/` — new template (manifest + Jinja2)
- `.pipelines/pipelines/EMPLOYER-CONTACT-E1-ptv.dot` — instantiated, validated pipeline
- `.pipelines/pipelines/GASCITY-INT-001-handson.dot` — GasCity spike pipeline (from prior session)
