---
title: "Pilot Autonomy: Goal-Pursuing Agent Design"
description: "Transforms the pipeline pilot from a mechanical gate checker into an autonomous agent that pursues PRD goals through SD fidelity monitoring, cross-node integration testing, Gherkin-driven validation, and pipeline-level E2E verification."
version: "1.0.0"
last-updated: 2026-03-28
status: active
type: sd
grade: authoritative
---

# SD-PILOT-AUTONOMY-001: Pilot Autonomy

## Overview

The pilot agent (Layer 1) drives pipeline execution on behalf of the user. This design transforms it from a reactive gate checker into an autonomous goal-pursuing agent that:

1. **Monitors SD execution fidelity** during the implement stage
2. **Validates per-node + cross-node** during the validate stage
3. **Runs pipeline-level E2E** before declaring completion
4. **Auto-generates manifests** from DOT node acceptance criteria
5. **Evolves Gherkin scenarios** across retries (persistence, not rewrite)

## Architecture

```
CoBuilder (Layer 0)  — strategic planning, PRD authorship
  |
  Pilot (Layer 1)    — AUTONOMOUS GOAL-PURSUING AGENT
  |                     Monitors SD fidelity during implementation
  |                     Writes & executes Gherkin at gates
  |                     Checks cross-node integration
  |                     Runs pipeline E2E before completion
  |                     Auto-generates manifest from ACs
  |
  Runner (Layer 2)   — Python state machine, $0 LLM cost
  |                     Dispatches workers, watches signals
  |                     Enforces scoring (rejects score-less passes)
  |                     Injects context into all prompts
  |
  Workers (Layer 3)  — AgentSDK: codergen, research, refine, validation
                        Write signals with files_changed + message
                        Read predecessor signals for context
```

## Pilot Lifecycle Phases

### Phase 0: Load Context
- Invoke `Skill("cobuilder")` for project conventions
- Parse DOT graph, validate structure, get current status

### Phase 1: Initialize & Dispatch
- Dispatch research nodes (synchronous)
- Dispatch refine nodes (synchronous)
- Launch pipeline runner in background

### Phase 2: Implement Stage — SD Fidelity Monitoring

**NEW**: While workers implement, the pilot monitors SD fidelity.

After each node reaches `impl_complete`:
- Reads worker's `files_changed` from processed signal
- Reads the Solution Design for that node
- Compares actual files to SD's expected file structure
- Detects **gaps** (SD-specified files not touched) and **drift** (files not in SD scope)
- Writes fidelity report to `acceptance-tests/{pipeline_id}/{node_id}-sd-fidelity.md`

**Runner support**: `_build_sd_fidelity_context()` extracts file patterns from SD content (code blocks, scope lines, bullet points) and compares to `files_changed`.

### Phase 3: Validate Stage — Gherkin + Integration + PRD

At each `wait.cobuilder` gate:

#### Per-Node Validation
1. Read upstream node's acceptance criteria (with per-AC `[method]` tags)
2. Read worker's completion signal + validator's scoring signal
3. Write `.feature` file with per-AC Gherkin scenarios
4. Execute each scenario using its tagged method

#### Per-AC Validation Methods

Acceptance criteria support inline method tags:

```
AC-1 [browser-check]: Login form renders with email and password fields
AC-2 [api-call]: POST /auth/login returns JWT token
AC-3 [unit-test]: Token expires after configured TTL
AC-4 [code-review]: Error messages follow i18n pattern
```

Valid tags: `[browser-check]`, `[api-call]`, `[unit-test]`, `[code-review]`. Parsed by `_parse_acceptance_criteria()`.

#### Cross-Node Integration Check
- Read all predecessor/sibling signals from processed/
- Check API contract consistency across nodes
- Check shared type/interface consistency
- Check file overlap (multiple nodes touching same files)
- Write integration findings to `acceptance-tests/{pipeline_id}/integration-report.md`

**Runner support**: `_build_cross_node_context()` builds a map of node_id -> files_changed, detects shared files, and summarizes completed node outputs.

#### Gherkin Persistence
- First attempt: write new `.feature` file with skeleton scenarios
- On retry: READ existing `.feature`, DON'T rewrite
  - Add regression scenarios for previously-failing ACs
  - Evolve Given/When/Then based on what changed
  - Add comments tracking which attempt added each scenario
- The `.feature` file is a living document that grows across retries

### Phase 4: Pipeline Completion Validation

When all nodes reach `accepted`, before signaling PIPELINE_COMPLETE:

1. **Auto-generate manifest** from DOT node ACs:
   - `_auto_generate_manifest()` reads all node `acceptance` attributes
   - Writes `acceptance-tests/{prd_ref}/manifest.yaml`
   - Features weighted by AC count, methods aggregated from per-AC tags

2. **Aggregate Gherkin into E2E suite**:
   - Read all per-node `.feature` files
   - Write `acceptance-tests/{pipeline_id}/e2e-suite.feature` with cross-cutting scenarios

3. **Execute E2E suite**: run all scenarios by tagged method

4. **Write pipeline validation report**: `acceptance-tests/{pipeline_id}/pipeline-validation-report.md`
   - Per-node scores + score trends
   - Cross-node integration results
   - SD fidelity summary
   - E2E suite results
   - PRD coverage analysis

5. **Decide**: PIPELINE_COMPLETE only if E2E passes and PRD is covered

**Runner support**: `_build_pipeline_e2e_context()` aggregates all node ACs, scores, file changes, and score trends into a holistic pipeline-level view.

## Signal-Based Communication System

All pipeline nodes communicate via signal files:

```
{signal_dir}/
  {node_id}.json          <- active signals (runner watches)
  processed/
    {timestamp}-{node_id}.json  <- historical (nodes read for context)
  _score_history.json     <- score trends across retries
```

| Agent | Writes | Reads |
|-------|--------|-------|
| Worker | `{status, files_changed, message}` | Predecessor signals, validator feedback |
| Validator | `{result, scores, overall_score, criteria_results}` | Worker signal, SD, predecessor signals |
| Runner | Transitions DOT, moves to processed/ | Active signals directory |
| Pilot | Gate responses, .feature files, reports | All processed signals, score history |

### Scoring Enforcement

The runner **rejects** validation PASS signals that lack `scores`, `overall_score`, or `criteria_results` — requeues to validator. This ensures the evaluator-optimizer feedback loop always has data.

### Scoring Dimensions (5)

| Dimension | Weight | What to Assess |
|-----------|--------|----------------|
| Correctness | 35% | Does the code do what the AC specifies? |
| Completeness | 25% | Are ALL acceptance criteria addressed? |
| Code Quality | 15% | Clean code, proper error handling |
| SD Adherence | 10% | Follows Solution Design architecture? |
| Process Discipline | 15% | Beads tracking (`bd start/done`)? |

Pass threshold: overall_score >= 7.0

## Pilot MCP Tool Access

The pilot has full tool access to act as an autonomous agent:

| Category | Tools |
|----------|-------|
| File access | Write, Edit, MultiEdit, Read, Glob, Grep, Bash |
| Code navigation | Serena (10 tools) |
| Memory | Hindsight (reflect, retain, recall) |
| Browser validation | Claude-in-Chrome (9 tools) |
| Research | Context7 (2), Perplexity (4) |
| Web | WebFetch, WebSearch |
| Planning | TodoWrite, ToolSearch, Skill, LSP |

## Key Files

| File | What Changed |
|------|-------------|
| `cobuilder/engine/pipeline_runner.py` | `_build_sd_fidelity_context()`, `_build_cross_node_context()`, `_build_pipeline_e2e_context()`, `_auto_generate_manifest()`, `_parse_acceptance_criteria()`, scoring enforcement, signal history/graph neighborhood injection |
| `cobuilder/engine/guardian.py` | Pilot system prompt: Phase 2.5 (SD fidelity), Phase 3 (Gherkin + integration), Phase 4 (E2E completion), full tool access |
| `.claude/agents/validation-test-agent.md` | 5 scoring dimensions, per-AC method tags, method in criteria_results |
| `.claude/skills/cobuilder/ideation-to-execution/SKILL.md` | AC format with [method] tags, Phase 5 Gherkin protocol, signal communication |
| `.claude/skills/acceptance-test-writer/SKILL.md` | Per-AC method tags for DOT nodes |

## Implementation Status

- [x] Validator scoring enforcement (reject score-less passes)
- [x] Per-AC validation method tags (`AC-N [method]: text`)
- [x] Signal history injection into all prompts
- [x] Graph neighborhood injection into all prompts
- [x] SD fidelity context builder
- [x] Cross-node integration context builder
- [x] Pipeline E2E context builder
- [x] Manifest auto-generation from ACs
- [x] Pilot system prompt: full autonomous agent protocol
- [x] Pilot tool access: Write/Edit/Chrome/Perplexity/Context7
- [x] Gherkin persistence instructions (read existing, evolve)
- [x] Worker SD fidelity notice (workers know they'll be checked)
- [x] All handler preambles updated with signal communication awareness
