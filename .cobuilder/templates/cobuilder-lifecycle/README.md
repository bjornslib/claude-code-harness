# cobuilder-lifecycle Template

**Version**: 2.0
**Topology**: Linear with paired validation gates
**Min Nodes**: 9
**Max Nodes**: 12

## Overview

Self-driving CoBuilder Guardian lifecycle pipeline that orchestrates the full research-to-close cycle. Each codergen node is followed by a paired `wait.cobuilder` (automated validation) + `wait.human` (human review) gate before the next stage begins.

```
START → RESEARCH → REFINE → at_refine → hr_refine → PLAN → at_plan → hr_plan → EXECUTE → at_execute → hr_execute → CLOSE
```

## Nodes

| Node | Shape | Handler | Description |
|------|-------|---------|-------------|
| `start` | Mdiamond | start | Entry point |
| `research` | tab | research | Problem domain investigation (writes state/{id}-research.json) |
| `refine` | box | codergen | Produce refined Business Spec (writes state/{id}-refined.md) |
| `at_refine` | hexagon | wait.cobuilder | Automated validation gate for refine output |
| `hr_refine` | hexagon | wait.human | Human review gate for refined BS |
| `plan` | box | codergen | Generate child pipeline DOT (writes state/{id}-plan.json) |
| `at_plan` | hexagon | wait.cobuilder | Automated validation gate for plan output |
| `hr_plan` | hexagon | wait.human | Human approval gate before execution |
| `execute` | box | codergen | Implementation (reads plan, writes code) |
| `at_execute` | hexagon | wait.cobuilder | Automated validation gate for implementation |
| `hr_execute` | hexagon | wait.human | Human review gate for implementation |
| `pipeline_exit` | Msquare | exit | Session finalization |

## Parameters

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `initiative_id` | string | Initiative identifier (e.g., INIT-AUTH-001) |
| `business_spec_path` | string | Path to the Business Spec markdown file |
| `target_dir` | string | Path to the target repository/directory |

### Optional

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_cycles` | integer | 3 | Used in `default_max_retry` calculation for the graph |
| `execution_template` | string | "hub-spoke" | Child pipeline template referenced in PLAN prompt |
| `model_research` | string | "anthropic-fast" | LLM profile for research node |
| `model_refine` | string | "anthropic-smart" | LLM profile for refine node |
| `model_plan` | string | "anthropic-smart" | LLM profile for plan node |
| `model_execute` | string | "alibaba-glm5" | LLM profile for execute node |
| `cobuilder_root` | string | "/path/to/harness" | Path to harness root (for script resolution) |
| `research_queries` | string | "" | Additional research queries for the research node |

## Usage

### Basic Instantiation

```bash
python3 cobuilder/templates/instantiator.py cobuilder-lifecycle \
  --param initiative_id="INIT-AUTH-001" \
  --param business_spec_path="docs/bs/BS-AUTH-001.md" \
  --param target_dir="/path/to/repo" \
  --output .pipelines/pipelines/INIT-AUTH-001-lifecycle.dot
```

### With Custom Model Profiles

```bash
python3 cobuilder/templates/instantiator.py cobuilder-lifecycle \
  --param initiative_id="INIT-AUTH-001" \
  --param business_spec_path="docs/bs/BS-AUTH-001.md" \
  --param target_dir="/path/to/repo" \
  --param model_research="anthropic-fast" \
  --param model_refine="anthropic-smart" \
  --param model_plan="anthropic-smart" \
  --param model_execute="anthropic-smart" \
  --output .pipelines/pipelines/INIT-AUTH-001-lifecycle.dot
```

## Lifecycle Flow

1. **START**: Entry point
2. **RESEARCH** (`tab`/research): Reads business spec, writes `state/{id}-research.json`
3. **REFINE** (`box`/codergen): Reads research JSON + business spec, writes `state/{id}-refined.md`
4. **at_refine** (`hexagon`/wait.cobuilder): Guardian validates refined BS exists and has acceptance criteria
5. **hr_refine** (`hexagon`/wait.human): Human reviews and approves the refined Business Spec
6. **PLAN** (`box`/codergen): Reads refined BS, generates child pipeline DOT, writes `state/{id}-plan.json`
7. **at_plan** (`hexagon`/wait.cobuilder): Guardian validates plan JSON has required fields
8. **hr_plan** (`hexagon`/wait.human): Human approves the plan before execution begins
9. **EXECUTE** (`box`/codergen): Reads plan, implements code, runs tests
10. **at_execute** (`hexagon`/wait.cobuilder): Guardian runs acceptance tests against refined BS
11. **hr_execute** (`hexagon`/wait.human): Human reviews implementation
12. **CLOSE** (`Msquare`/exit): Session finalized

## v2.0 Changes from v1.0

| v1.0 | v2.0 |
|------|------|
| Cyclic topology with loop-back | Linear topology — no automatic loop-back |
| Single human gate (`wait_approval`) | Paired gates per stage: `wait.cobuilder` + `wait.human` |
| `evaluate` (conditional) node | Removed — human review handles goal assessment |
| `manager_loop` for execute | `codergen` box — simpler direct dispatch |
| `require_human_before_launch` param | Always has human gates (hr_refine, hr_plan, hr_execute) |
| `model_research="haiku"` default | `model_research="anthropic-fast"` (named profile) |
| `_template_version="1.0"` | `_template_version="2.0"` in graph attributes |

## State Files

The pipeline reads and writes these files under `target_dir/state/`:

| File | Written By | Read By |
|------|-----------|---------|
| `{id}-research.json` | research node | refine node |
| `{id}-refined.md` | refine node | plan, execute nodes |
| `{id}-plan.json` | plan node | execute node |
| `{id}-failures.md` | Guardian (on retry) | research node (next cycle) |

## Signal Protocol

Each node writes completion to `.pipelines/pipelines/signals/{pipeline_id}/{node_id}.json`:

```json
{
  "status": "success",
  "files_changed": ["state/INIT-AUTH-001-refined.md"],
  "message": "Refined Business Spec written with updated acceptance criteria"
}
```

## See Also

- [PRD-GUARDIAN-DISPATCH-001](../../docs/prds/PRD-GUARDIAN-DISPATCH-001.md) - Guardian dispatch hardening (ClaudeSDKClient, stop hook, tools)
- [hub-spoke template](../hub-spoke/) - Default execution template used by PLAN node
- [sequential-validated template](../sequential-validated/) - Simpler linear pipeline without lifecycle gates
