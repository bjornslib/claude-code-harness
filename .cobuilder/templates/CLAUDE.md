---
title: "Pipeline Template Library"
status: active
type: reference
last_verified: 2026-04-09
grade: authoritative
---

# Pipeline Template Library

Jinja2 DOT pipeline templates for the CoBuilder engine. Each template directory contains a `manifest.yaml` (parameters, constraints, defaults) and a `template.dot.j2` (the rendered pipeline graph).

## Instantiation

```bash
# List available templates
python3 cobuilder/templates/instantiator.py --list

# Instantiate a template
python3 cobuilder/templates/instantiator.py <template-name> \
  --param key="value" \
  --output .pipelines/pipelines/my-pipeline.dot

# Or use the CLI
cobuilder template instantiate <template-name> --param-file params.yaml --output pipeline.dot
```

The instantiator loads `template.dot.j2` + `manifest.yaml`, validates required parameters, renders with Jinja2, and optionally runs static constraint validation on the output.

## Template Comparison

| Template | Topology | Purpose | Key Feature | When to Use |
|----------|----------|---------|-------------|-------------|
| `sequential-validated` | Linear | Single task: implement → validate → finalize | Simplest pipeline; optional research pre-step | One worker, one task, quick validation |
| `hub-spoke` | Parallel | N workers fan-out, join, validate | Fan-out/fan-in with tech + biz validation per worker | Multi-task epics with independent workers |
| `tdd-validated` | Parallel | N workers each run RED→GREEN→REFACTOR | Full TDD cycle per worker with superpowers | Strict TDD discipline, parallel workers |
| `planner-tdd-validated` | Sequential gated | Planner→Red→Green→Validator with guardian gates | Anthropic Planner-Worker-Validator pattern | Single epic, TS-first, highest quality |
| `tdd-conditional-ci` | Sequential gated | Planner→Red→Green→CI→Route→Validate | CI-driven conditional routing (unit/browser/both) | Epics needing different test types per change |
| `cobuilder-lifecycle` | Linear gated | Research→Refine→Plan→Execute→Validate→Close | Full autonomous lifecycle with paired gates | Initiative-level autonomy (Pilot mode) |

## Templates

### sequential-validated

**Version**: 1.0 | **Topology**: Linear | **Nodes**: 5-10

The simplest pipeline. One worker implements a task, then a validation gate checks the result. A conditional diamond routes to finalize (pass) or back to implementation (fail).

```
START → [Research] → Implement → Validate → Decision → FINALIZE
                                                ↓ fail
                                             Implement (retry)
```

**Required params**: `prd_ref`, `worker` (object with label, worker_type, bead_id, acceptance)
**Optional params**: `promise_id`, `include_research` (boolean)

**Use when**: You have a single focused task that doesn't need TDD ceremony or multi-worker coordination.

---

### hub-spoke

**Version**: 1.0 | **Topology**: Parallel | **Nodes**: 5-50

Central coordinator fans out to N parallel workers, each with tech + business validation gates. Workers join at a fan-in node, then an optional E2E integration test runs before finalization.

```
START → Validate Graph → Init Env → [Fan-Out] → Worker 1 → Tech Val → Biz Val → Decision ─┐
                                               → Worker 2 → Tech Val → Biz Val → Decision ─┤
                                               → Worker N → ...                             ─┤
                                                                                              ↓
                                                                     [Fan-In] → [E2E] → FINALIZE
```

**Required params**: `prd_ref`, `workers` (list, 1-10 items)
**Optional params**: `promise_id`, `include_e2e` (boolean, default true)

**Key features**:
- Tool nodes for graph validation and environment initialization
- Dual validation gates per worker (technical + business)
- Fan-out/fan-in for parallel worker execution
- Conditional retry loops per worker

**Use when**: Multiple independent tasks can be worked in parallel, each needing separate validation.

---

### tdd-validated

**Version**: 1.0 | **Topology**: Parallel | **Nodes**: 7-60

Each worker follows the full RED→GREEN→REFACTOR TDD cycle. Workers receive "superpowers" (systematic-debugging, verification-before-completion). Supports optional research pre-step and E2E integration.

```
START → [Research] → [Fan-Out] → RED: Write Failing Tests ──→ GREEN: Minimal Impl ──→ REFACTOR ──→ Validate → Decision ─┐
                                                                                                                          ↓
                               [Fan-In] → [E2E Integration] → E2E Validate → Decision → FINALIZE
```

**Required params**: `prd_ref`, `sd_path`, `workers` (list, 1-10)
**Optional params**: `promise_id`, `include_research`, `include_e2e`, `default_worker_powers`, `llm_profile_test`, `llm_profile_impl`, `llm_profile_refactor`

**Key features**:
- Three codergen nodes per worker: RED (write failing tests), GREEN (minimal impl), REFACTOR (cleanup)
- Worker superpowers: `tdd`, `systematic-debugging`, `verification`
- Per-worker `scope` and `test_command` attributes
- Configurable LLM profiles per TDD phase (fast for RED/REFACTOR, smart for GREEN)
- `wait.cobuilder` gates verify tests actually fail (RED) and pass (GREEN)

**Use when**: You want strict TDD discipline with automated red/green verification.

---

### planner-tdd-validated

**Version**: 1.0 | **Topology**: Sequential gated | **Nodes**: 11-15

Implements Anthropic's recommended **Planner→Worker→Validator** architecture with TDD. A planner agent researches the codebase and domain, produces a Technical Spec, then a TDD test engineer writes failing tests against it, an implementation worker makes them pass, and an independent validator scores the result.

```
START → Research Codebase → Research Domain → Write TS → [Guardian Gate] → [Human Review] → Decision
                                                                                               ↓ approved
RED: Write Failing Tests → [Guardian Gate] → GREEN: Implement → [Guardian Gate] → Validate
                                                                                      ↓
                                                               [Guardian Gate] → [Human Review] → Decision → EXIT
```

**Required params**: `prd_ref`, `bs_path`, `epic_id`, `epic_label`, `sd_output_path`, `worker_type`, `bead_id_planner`, `bead_id_impl`, `cobuilder_root`, `target_dir`
**Optional params**: `test_worker_type`, `validator_worker_type`, `llm_profile`, `llm_profile_planner`, `llm_profile_test`, `llm_profile_impl`, `test_type`, `test_command`

**Key features**:
- Two research nodes (codebase + domain) feed into TS authoring
- Paired `wait.cobuilder` + `wait.human` gates at planner and validator stages
- `wait.cobuilder` gate after RED verifies tests actually fail
- `wait.cobuilder` gate after GREEN verifies tests actually pass
- Independent validator that never sees worker output — audits against BS + TS
- Retry loop: final decision can send back to GREEN for rework

**Use when**: Highest-quality single-epic implementation with TS-first design and independent validation.

---

### tdd-conditional-ci

**Version**: 1.0 | **Topology**: Sequential gated | **Nodes**: 16-22

Extends `planner-tdd-validated` with **CI-driven conditional test routing**. After GREEN phase passes, a CI analysis tool node runs a script in the target repository (`working_dir="target_dir"`) that outputs JSON. A conditional diamond routes to unit tests, browser tests, or both based on the script's output.

```
START → Research → Write TS → [Guardian] → [Human] → Decision
                                                         ↓ approved
RED → [Guardian] → GREEN → [Guardian] → CI Analysis (tool, JSON output)
                                              ↓
                                        Route by test_type
                                       /        |         \
                                 unit only   browser only   both
                                   ↓            ↓         ↓     ↓
                               Run Unit    Run Browser  Unit + Browser → Fan-In
                                   ↓            ↓                          ↓
                                   └────────────┴──────────────────────────┘
                                                       ↓
                                    Validator → [Guardian] → [Human] → Decision → EXIT
```

**Required params**: `prd_ref`, `bs_path`, `epic_id`, `epic_label`, `sd_output_path`, `worker_type`, `bead_id_planner`, `bead_id_impl`, `cobuilder_root`, `target_dir`
**Optional params**: `ci_script` (default `./scripts/determine-test-type.sh`), `unit_test_command`, `browser_test_command`, `test_worker_type`, `validator_worker_type`, `llm_profile_*`

**Key features**:
- **`parse_json_output="true"`** on CI analysis tool node — parses JSON stdout into pipeline context keys
- **N-way conditional routing** — diamond evaluates `$run_ci.test_type` to route to unit, browser, or both branches
- **`working_dir="target_dir"`** on all tool nodes — commands run in the implementation repo, not the pipeline run directory
- **Catch-all edge** (`condition="true"`) defaults to unit tests if script output is unexpected
- **Fan-out for "both"** — parallel unit + browser test execution with fan-in join
- Showcases all three new ToolHandler capabilities in a single pipeline

**CI script contract**: The `ci_script` must output a JSON object to stdout:
```json
{"test_type": "unit", "coverage": 85}
```
Valid `test_type` values: `"unit"`, `"browser"`, `"both"`.

**Use when**: Your epic affects both backend and frontend, and you want the CI to dynamically determine which test suites to run based on what changed.

---

### cobuilder-lifecycle

**Version**: 2.0 | **Topology**: Linear gated | **Nodes**: 14-19

The **Pilot mode** template. A self-driving lifecycle pipeline that takes an initiative from research through implementation to validation, with paired `wait.cobuilder` + `wait.human` gates at every stage. Used when CoBuilder operates autonomously.

```
START → RESEARCH → REFINE → [at_refine] → [hr_refine] → PLAN → [at_plan] → [hr_plan]
    → EXECUTE → [LINT CHECK] → [at_execute] → [hr_execute] → CLOSE
```

**Required params**: `initiative_id`, `business_spec_path`, `target_dir`
**Optional params**: `max_cycles`, `execution_template` (default "hub-spoke"), `model_research`, `model_refine`, `model_plan`, `model_execute`, `cobuilder_root`, `research_queries`, `enable_lint_check` (default true), `model_lint`

**Key features**:
- Research node (`tab`) investigates problem domain, writes state JSON
- Refine node produces updated Business Spec with constraints
- Plan node generates a child pipeline DOT file
- Optional lint check (ruff + pylint) between execute and validation
- Paired gates at refine, plan, and execute stages
- State files under `target_dir/state/` enable inter-node communication
- Failure-aware research: checks for `state/{id}-failures.md` from prior cycles

**Use when**: Full initiative autonomy — CoBuilder drives the entire research→implement→validate loop as a Pilot.

---

## Shared Conventions

### Node Shapes → Handlers

| Shape | Handler | Purpose |
|-------|---------|---------|
| `Mdiamond` | `start` | Pipeline entry |
| `Msquare` | `exit` | Pipeline exit |
| `box` | `codergen` | LLM worker dispatch |
| `tab` | `planner` (research) | Research via Context7 + Perplexity |
| `note` | `planner` (refine) | SD/BS refinement |
| `diamond` | `conditional` | No-op routing; EdgeSelector evaluates edge conditions |
| `parallelogram` | `tool` | Shell command execution with context capture |
| `hexagon` | `wait.cobuilder` / `wait.human` | Validation or approval gate |
| `component` | `parallel` | Fan-out to parallel branches |
| `tripleoctagon` | `fan_in` | Merge parallel branches |
| `house` | `manager_loop` | Recursive sub-pipeline management |
| `octagon` | `close` | Programmatic epic closure |

### Status Chain

```
pending → active → impl_complete → validated → accepted
                 ↘ failed
```

### Color Conventions (visual, not functional)

| Color | Meaning |
|-------|---------|
| `green` | Start / exit nodes |
| `lightyellow` | Standard implementation nodes |
| `lightcyan` | Research nodes |
| `#ffcccc` (light red) | RED phase (TDD) |
| `#ccffcc` (light green) | GREEN phase (TDD) |
| `#ccccff` (light blue) | Refactor / validator nodes |
| `purple` | `wait.cobuilder` gates |
| `red` / `lightcoral` | `wait.human` gates |
| `orange` | Tool / lint check nodes |

### Common Parameters

All templates accept:

| Parameter | Description |
|-----------|-------------|
| `prd_ref` | PRD identifier (e.g., `PRD-AUTH-001`) |
| `promise_id` | Completion promise UUID (optional) |

Most templates also accept per-phase LLM profile overrides (`llm_profile_*`).

### Manifest Structure

```yaml
template:
  name: template-name
  version: "1.0"
  description: "What this template does"
  topology: linear | parallel | sequential-gated
  min_nodes: N
  max_nodes: N

parameters:
  param_name:
    type: string | boolean | integer | list | object
    required: true | false
    default: "value"
    description: "What this parameter controls"

defaults:
  llm_profile: "anthropic-smart"
  handler_defaults:
    research:
      llm_profile: "anthropic-fast"

constraints:
  constraint_name:
    type: node_state_machine | path_constraint | topology_constraint | loop_constraint
    ...
```

### Creating a New Template

1. Create a directory under `.cobuilder/templates/<name>/`
2. Add `manifest.yaml` with parameters, defaults, and constraints
3. Add `template.dot.j2` using Jinja2 syntax
4. Use `{{ param }}` for parameters, `{{ param | slugify }}` for DOT-safe IDs
5. Test: `python3 cobuilder/templates/instantiator.py <name> --param ... --output /dev/stdout`
6. Validate: `cobuilder pipeline validate <output.dot>`
