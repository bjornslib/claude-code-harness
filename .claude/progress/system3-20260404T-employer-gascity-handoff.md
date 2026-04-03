# Session Handoff: Employer Contact + GasCity — Two Track Plan

## Next Session: Launch Track A — Employer Contact Research Agent

### Pre-Launch Checklist

```bash
# 1. Create worktree in zenagent repo
cd ~/Documents/Windsurf/zenagent
git worktree add ../zenagent-employer-contact feature/employer-contact-research

# 2. Create real beads (replace PLACEHOLDER-* in DOT file)
bd create --title="PRD-EMPLOYER-CONTACT-001 E1: Plan TS for employer research agent" --type=task --priority=1
bd create --title="PRD-EMPLOYER-CONTACT-001 E1: Implement DSPy employer contact researcher" --type=task --priority=1
# Then: update bead_id_planner and bead_id_impl in the DOT file

# 3. Update target_dir in DOT to point to worktree
# Change: target_dir="/Users/theb/Documents/Windsurf/zenagent"
# To:     target_dir="/Users/theb/Documents/Windsurf/zenagent-employer-contact"

# 4. Launch pipeline
python3 cobuilder/engine/pipeline_runner.py --dot-file .pipelines/pipelines/EMPLOYER-CONTACT-E1-ptv.dot
```

### Pipeline Overview

**Pipeline**: `.pipelines/pipelines/EMPLOYER-CONTACT-E1-ptv.dot` (validated)
**Template**: `planner-tdd-validated` (Anthropic Planner→Worker→Validator)
**PRD**: `docs/prds/employer-contact-search/PRD-EMPLOYER-CONTACT-001.md`
**Epic**: E1 — Research Agent only (DSPy + Perplexity + Web Search)

```
Phase 1 (GLM-5):   research_codebase → research_domain → write_ts → [TS gate] → [human review]
Phase 2 (Sonnet):   red_tests (write failing tests) → [red gate]
Phase 3 (Sonnet):   green_impl (make tests pass) → [green gate]
Phase 4 (Sonnet):   validate (independent BS+TS check) → [validation gate] → [human review]
```

### Architecture: Clean Architecture (Feature-First)

**CRITICAL**: Implementation follows Clean Architecture from `docs/AGENCHECK_CLEANUP.md` § "Layer Structure". Feature-first directories, NOT horizontal layers.

```
agencheck/
└── employer_research/
    ├── domain.py           # Pydantic models, classification logic, scoring — NO I/O
    ├── classifier.py       # Pure classification: general vs named_poc — NO I/O
    ├── service.py          # Orchestrates research pipeline — calls adapters + domain
    ├── repository.py       # Supabase employer_contacts CRUD — adapter
    ├── researcher.py       # DSPy module (Perplexity + web search) — adapter
    ├── router.py           # FastAPI / Prefect entry — thin, delegates to service
    └── tests/
        ├── test_classifier.py
        ├── test_researcher.py
        ├── test_service.py
        └── conftest.py     # Fixtures with mock API responses
```

**Layer rules**: Dependencies flow inward: `entrypoints → service_layer → domain ← adapters`
- **domain** (domain.py, classifier.py): Pure Python, no framework imports, no I/O
- **service_layer** (service.py): Orchestration, calls adapters, applies domain logic
- **adapters** (repository.py, researcher.py): External integrations (Supabase, Perplexity, web search)
- **entrypoints** (router.py): FastAPI routes or Prefect task wrappers — thin delegation

### Key Design Decisions

- All worker nodes invoke `Skill('dspy-development')` mandatory
- Dual-source research: Perplexity Deep Research API + web search (Brave/Google). NOT Perplexity alone.
- Contact classification: general vs named_poc with confidence scoring per PRD Section 5
- Contact prioritisation: 7-tier priority per PRD Section 5.2
- Tests: classification, scoring, dedup, prioritisation, integration (with mock API fixtures)
- Implementation in zenagent worktree, not harness repo

### LLM Profile Mix

| Phase | Profile | Model | Cost |
|-------|---------|-------|------|
| Planner (research + TS) | `alibaba-glm5` | GLM-5 | ~$0 |
| Red (failing tests) | `anthropic-sonnet46` | Sonnet 4.6 | ~$1-2 |
| Green (implementation) | `anthropic-sonnet46` | Sonnet 4.6 | ~$1-2 |
| Validator (audit) | `anthropic-sonnet46` | Sonnet 4.6 | ~$1-2 |

### Expected Deliverables

1. **TS**: `docs/sds/employer-contact-search/SD-EMPLOYER-CONTACT-E1.md` — full technical spec with Clean Architecture file mapping
2. **Tests**: pytest test suite covering classification, scoring, dedup, prioritisation
3. **Implementation**: DSPy employer contact research module in zenagent worktree
4. **Validation report**: Per-criterion scores against BS Section 5 acceptance criteria

---

## Track B: GasCity Hands-On Spike (AFTER Track A)

**Pipeline**: `.pipelines/pipelines/GASCITY-INT-001-handson.dot` (validated)
**Goal**: Build gc locally, test Mayor context + multi-gate formulas, design enhanced Mayor + Architect
**Compare**: Could Track A have run natively in GasCity?

---

## New Template: planner-tdd-validated

Location: `.cobuilder/templates/planner-tdd-validated/`

Parameterised Jinja2 template implementing Anthropic's Planner→Worker→Validator with TDD:
- **Planner**: 2 research nodes + 1 codergen (TS writing) + guardian gate + human review
- **Red**: TDD test engineer writes failing tests + guardian gate
- **Green**: Implementation worker makes tests pass + guardian gate
- **Validator**: Independent BS+TS audit + guardian gate + human review

Parameters: `prd_ref`, `bs_path`, `epic_id`, `epic_label`, `sd_output_path`, `worker_type`, `bead_id_planner`, `bead_id_impl`, `llm_profile*`, `test_command`, `cobuilder_root`, `target_dir`

---

## Session Artifacts

- `docs/prds/employer-contact-search/PRD-EMPLOYER-CONTACT-001.md` — BS with Section 13 (Clean Architecture)
- `docs/sds/employer-contact-search/SD-EMPLOYER-CONTACT-E1.md` — placeholder (Planner will write)
- `.cobuilder/templates/planner-tdd-validated/` — new template (manifest + Jinja2)
- `.pipelines/pipelines/EMPLOYER-CONTACT-E1-ptv.dot` — instantiated, validated, DSPy-enriched
- `.pipelines/pipelines/GASCITY-INT-001-handson.dot` — GasCity spike (Track B)
- `workspace/gascity/` — cloned GasCity repo for Track B
