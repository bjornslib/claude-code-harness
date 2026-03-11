---
title: "Abstract Workflow System: MASFactory-Inspired Design for Claude Code Harness"
status: draft
type: architecture
grade: reference
last_verified: 2026-03-11
---

# Abstract Workflow System: MASFactory-Inspired Design

## Executive Summary

This document analyzes [MASFactory](https://github.com/BUPT-GAMMA/MASFactory) — a graph-based multi-agent orchestration framework — and proposes how its key ideas can be adapted to make the Claude Code harness workflow **abstract, configurable, storable, and loadable**.

Currently, our 3-tier workflow (System3 → Orchestrator → Workers) is defined implicitly through a combination of output-styles, skills, hooks, and hardcoded patterns in markdown files. MASFactory offers a proven model for making such workflows explicit, composable, and user-customizable.

---

## Part 1: MASFactory Key Concepts

### Graph-Based Workflow Model

MASFactory represents all multi-agent workflows as **directed graphs**:

```
Nodes  = Agents, control structures, subgraphs
Edges  = Message pathways with explicit field mappings
Gates  = Conditional routing logic
```

A workflow is a `RootGraph` containing nodes and edges, built with `.build()` and executed with `.invoke()`.

### Composed Graph Patterns (Pre-Built Topologies)

MASFactory ships reusable **composed graph patterns** — the most relevant insight for us:

| Pattern | Topology | Our Equivalent |
|---------|----------|----------------|
| `VerticalGraph` | Sequential pipeline (A→B→C) | Our 4-phase pattern (Ideation→Planning→Execution→Validation) |
| `HorizontalGraph` | Parallel fan-out, fan-in | Parallel worker dispatch |
| `BrainstormingGraph` | Multiple agents contribute ideas, then synthesize | Our `parallel-solutioning` skill |
| `HubGraph` | Central coordinator delegates to spokes | Our Orchestrator→Worker pattern |
| `PingPongGraph` | Two agents iterating back-and-forth | Code review loops, instructor-assistant |
| `InstructorAssistantGraph` | Instructor guides, assistant executes | Our System3→Orchestrator relationship |
| `MeshGraph` | All-to-all agent communication | Peer worker coordination |
| `VerticalDecisionGraph` | Sequential with conditional branches | Our LogicSwitch-style task routing |
| `Loop` | Iterative refinement with exit condition | TDD red-green-refactor cycles |

### VibeGraph: Intent-to-Workflow Generation

MASFactory's `VibeGraph` generates workflow topology from natural language:
1. User describes intent ("Build a code review pipeline")
2. LLM generates a `graph_design.json` with nodes, edges, agent configs
3. User refines visually in VS Code
4. System compiles and executes

### NodeTemplate & Factory

`NodeTemplate` allows parameterized agent definitions that can be instantiated multiple times with different configs. `Factory` creates agents from templates. This is analogous to our agent directory but declarative rather than hardcoded.

### Hooks System

MASFactory has `HookManager` with `HookStage` and `masf_hook` — lifecycle hooks at graph/node/edge levels. Similar to our `SessionStart`, `Stop`, `PreCompact` hooks but more granular.

### Serialization

Workflows serialize to `graph_design.json` — the entire topology, agent configs, and edge mappings in one file. This enables **storing and loading workflows**.

---

## Part 2: Current Harness Architecture (What We Have)

### Workflow Definition Is Implicit

Our workflow is defined across **7+ scattered locations**:

| Component | Location | What It Defines |
|-----------|----------|-----------------|
| Agent hierarchy | `CLAUDE.md` | 3-tier structure (System3→Orchestrator→Worker) |
| Orchestrator behavior | `.claude/output-styles/orchestrator.md` | Delegation rules, investigation boundaries |
| System3 behavior | `.claude/output-styles/system3-meta-orchestrator.md` | Strategic planning, monitor patterns |
| Worker dispatch | `orchestrator-multiagent/SKILL.md` | Team creation, task delegation |
| Phase pattern | `orchestrator-multiagent/WORKFLOWS.md` | 4-phase orchestration pattern |
| Agent selection | `CLAUDE.md` Agent Directory | Which specialist for which task |
| Lifecycle hooks | `.claude/settings.json` | SessionStart, Stop, PreCompact |

### What's Hardcoded vs Configurable

| Aspect | Current State | Customizable? |
|--------|--------------|---------------|
| Number of tiers (3) | Hardcoded in docs | No |
| Phase sequence (4 phases) | Hardcoded in WORKFLOWS.md | No |
| Agent types | Hardcoded in CLAUDE.md | No (must edit markdown) |
| Delegation rules | Hardcoded in output-styles | No |
| Hook scripts | Configurable in settings.json | Yes (partially) |
| Worker selection logic | Hardcoded decision tree in CLAUDE.md | No |
| Validation requirements | Hardcoded in multiple files | No |

### Pain Points

1. **No workflow switching** — Can't switch between "full 4-phase" and "quick 2-phase" without editing files
2. **No workflow sharing** — Can't export a working workflow config for others
3. **No experimentation** — Can't A/B test different orchestration strategies
4. **Scattered definition** — Understanding the full workflow requires reading 7+ files
5. **No programmatic access** — Workflows are prose in markdown, not structured data

---

## Part 3: Proposed Abstract Workflow System

### Core Design: Workflow as Data

Inspired by MASFactory's graph model, define workflows as **structured JSON/YAML** that the harness interprets at runtime.

```yaml
# .claude/workflows/standard-coding.workflow.yaml
---
name: standard-coding
description: "Full 4-phase software development workflow"
version: "1.0"

# Graph topology
topology: vertical  # vertical | hub-spoke | mesh | custom

# Phases (nodes in the graph)
phases:
  - id: ideation
    type: phase
    agent_tier: orchestrator
    description: "Research, brainstorm, parallel-solutioning"
    skills: [research-first, explore-first-navigation, parallel-solutioning]
    outputs: [investigation_summary, solution_options]
    next: planning

  - id: planning
    type: phase
    agent_tier: orchestrator
    description: "PRD creation, task decomposition, acceptance test generation"
    skills: [acceptance-test-writer, s3-guardian]
    tools: [task-master]
    outputs: [prd, task_list, acceptance_tests]
    next: execution

  - id: execution
    type: phase
    agent_tier: orchestrator
    description: "Delegate to workers, monitor progress"
    delegation:
      pattern: hub-spoke  # orchestrator delegates to parallel workers
      worker_selection: auto  # uses agent directory decision tree
    outputs: [implemented_code, unit_tests]
    next: validation

  - id: validation
    type: phase
    agent_tier: system3
    description: "Run acceptance tests, validate against PRD"
    skills: [acceptance-test-runner]
    agents: [validation-test-agent]
    outputs: [validation_evidence, pass_fail]
    on_fail: execution  # loop back

# Agent definitions (NodeTemplate equivalent)
agents:
  orchestrator:
    output_style: orchestrator
    capabilities: [read, grep, glob, delegate]
    restrictions: [no_edit, no_write]

  workers:
    frontend:
      type: frontend-dev-expert
      capabilities: [edit, write, read, grep]
      skills: [react-best-practices, frontend-design]
    backend:
      type: backend-solutions-engineer
      capabilities: [edit, write, read, grep]
      skills: [research-first]
    tester:
      type: tdd-test-engineer
      capabilities: [edit, write, read, bash]

# Worker selection rules (replaces hardcoded decision tree)
worker_routing:
  rules:
    - match: { file_pattern: "*/frontend/*", task_type: "implementation" }
      agent: workers.frontend
    - match: { file_pattern: "*/agent/*", task_type: "implementation" }
      agent: workers.backend
    - match: { task_type: "testing" }
      agent: workers.tester
  default: general-purpose

# Hooks (lifecycle events)
hooks:
  session_start:
    - detect-orchestrator-mode
    - load-mcp-skills
  phase_transition:
    - log-phase-change
    - update-completion-promise
  worker_complete:
    - validate-output
    - update-task-status
  session_end:
    - unified-stop-gate
```

### Workflow Variants (Storable & Loadable)

```
.claude/workflows/
├── standard-coding.workflow.yaml      # Full 4-phase for complex features
├── quick-fix.workflow.yaml            # 2-phase: investigate → fix → validate
├── research-only.workflow.yaml        # Investigation without implementation
├── tdd-first.workflow.yaml            # Tests before code
├── review-pipeline.workflow.yaml      # Code review focused workflow
├── custom/                            # User-created workflows
│   └── my-team-process.workflow.yaml
└── templates/                         # Composable building blocks
    ├── phase-ideation.yaml
    ├── phase-planning.yaml
    ├── phase-execution.yaml
    ├── phase-validation.yaml
    └── pattern-hub-spoke.yaml
```

### Example: Quick-Fix Workflow (Simplified)

```yaml
name: quick-fix
description: "Rapid bug fix - skip ideation, minimal planning"
version: "1.0"
topology: vertical

phases:
  - id: investigate
    type: phase
    agent_tier: orchestrator
    description: "Find the bug, understand root cause"
    max_duration: "5min"
    outputs: [root_cause, fix_plan]
    next: fix

  - id: fix
    type: phase
    agent_tier: worker
    description: "Implement fix and write regression test"
    delegation:
      pattern: single-worker
      worker_selection: auto
    outputs: [fix_commit, regression_test]
    next: verify

  - id: verify
    type: phase
    agent_tier: orchestrator
    description: "Run tests, verify fix"
    validation:
      run_tests: true
      require_passing: true
    outputs: [test_results]

agents:
  orchestrator:
    output_style: orchestrator
    capabilities: [read, grep, glob, delegate]
    restrictions: [no_edit, no_write]
```

### Composed Patterns (MASFactory's Best Idea)

Reusable graph patterns that can be referenced in workflows:

```yaml
# .claude/workflows/templates/pattern-parallel-solutioning.yaml
name: parallel-solutioning
type: pattern
topology: brainstorming

nodes:
  - id: researcher_1
    agent: general-purpose
    prompt_template: "Research approach A: {approach_a}"
  - id: researcher_2
    agent: general-purpose
    prompt_template: "Research approach B: {approach_b}"
  - id: synthesizer
    agent: solution-architect
    prompt_template: "Compare findings and recommend: {research_results}"

edges:
  - from: [researcher_1, researcher_2]
    to: synthesizer
    aggregation: collect  # wait for all, then pass combined
```

Referenced in a workflow:

```yaml
phases:
  - id: ideation
    type: pattern
    pattern: parallel-solutioning
    params:
      approach_a: "React Server Components"
      approach_b: "Traditional SPA with API"
```

---

## Part 4: Workflow Lifecycle Commands

### Loading & Switching Workflows

```bash
# List available workflows
/workflow list

# Show current active workflow
/workflow active

# Switch workflow for this session
/workflow use quick-fix

# Create from template
/workflow create my-process --from standard-coding

# Import shared workflow
/workflow import ./team-workflow.yaml

# Export for sharing
/workflow export standard-coding > ./shared-workflow.yaml
```

### VibeGraph-Inspired: Generate from Intent

```bash
# Describe what you want, get a workflow draft
/workflow generate "I want a TDD-first process where tests are written
before code, with peer review between implementation rounds"
```

This would use an LLM to generate a `.workflow.yaml` from natural language description, similar to MASFactory's VibeGraph.

---

## Part 5: Implementation Approach

### Phase 1: Schema & Parser (Foundation)

1. Define the workflow YAML schema (JSON Schema for validation)
2. Build a workflow parser that reads `.workflow.yaml` files
3. Create a workflow registry (list, load, validate workflows)
4. Store workflow definitions in `.claude/workflows/`

### Phase 2: Runtime Interpreter

1. Build a workflow engine that interprets phase transitions
2. Map phases to existing output-styles and skills
3. Implement worker routing from workflow rules
4. Hook into existing lifecycle events

### Phase 3: Workflow Management

1. `/workflow` slash commands for switching and managing
2. Workflow validation (check all referenced agents/skills exist)
3. Workflow diff (compare two workflows)
4. Active workflow indicator in status line

### Phase 4: Generation & Sharing

1. VibeGraph-style intent-to-workflow generation
2. Export/import workflows
3. Workflow marketplace/registry
4. Visual workflow editor (stretch goal)

---

## Part 6: Mapping MASFactory Concepts to Our System

| MASFactory Concept | Our Adaptation | Implementation |
|-------------------|----------------|----------------|
| `RootGraph` | Workflow definition file | `.workflow.yaml` |
| `Node` | Phase or agent step | Phase entries in YAML |
| `Edge` | Phase transitions | `next` field + `on_fail` |
| `Agent` | Agent type definition | `agents` section |
| `NodeTemplate` | Agent templates | Parameterized agent configs |
| `VerticalGraph` | Sequential phase pattern | `topology: vertical` |
| `HubGraph` | Orchestrator→Workers | `delegation.pattern: hub-spoke` |
| `BrainstormingGraph` | Parallel solutioning | `pattern: parallel-solutioning` |
| `PingPongGraph` | Review loops | `pattern: review-cycle` |
| `Loop` | Validation retry | `on_fail: <phase_id>` |
| `LogicSwitch` | Conditional routing | Worker routing rules |
| `VibeGraph` | `/workflow generate` | Intent-to-YAML generation |
| `graph_design.json` | `.workflow.yaml` | Serialized workflow format |
| `HookManager` | Existing hooks + phase hooks | `hooks` section |
| `Factory` | Agent spawning | Worker dispatch from routing rules |

---

## Part 7: Key Design Decisions

### 1. YAML over JSON

YAML is more readable for workflow definitions that humans will edit. JSON Schema validates the structure. Support both formats for interop.

### 2. Declarative over Imperative

MASFactory uses Python code to build graphs. We should use **declarative YAML** because:
- Our "runtime" is Claude itself, not a Python process
- Workflows are interpreted by the LLM reading them, not compiled
- YAML is easier for non-programmers to customize
- Still machine-parseable for tooling

### 3. Backwards Compatible

The workflow system should be **additive** — existing output-styles, skills, and hooks continue to work. Workflows layer on top as a coordination mechanism. A missing workflow file falls back to the current implicit behavior.

### 4. Composable Building Blocks

Following MASFactory's composed graph patterns, workflows should reference reusable patterns and phase templates. This prevents duplication across workflow variants.

### 5. Progressive Complexity

- **Simple**: Pick a pre-built workflow (`/workflow use quick-fix`)
- **Medium**: Customize an existing workflow (edit YAML)
- **Advanced**: Create from scratch or generate from intent

---

## Part 8: What MASFactory Does That We Should NOT Copy

| MASFactory Feature | Why We Skip It |
|-------------------|----------------|
| Python-based graph definition | Our "runtime" is the LLM, not Python |
| Explicit field mappings on edges | Over-engineering for LLM context passing |
| VS Code visualizer extension | Out of scope (could be future work) |
| Embedding/retrieval adapters | We have MCP servers for this |
| Model adapter abstraction | Claude Code handles model selection |
| `DynamicAgent` runtime creation | Security concern in autonomous systems |

---

## Appendix: Quick-Start Workflows to Ship

| Workflow | Phases | When to Use |
|----------|--------|-------------|
| `standard-coding` | Ideation→Planning→Execution→Validation | Complex features, new systems |
| `quick-fix` | Investigate→Fix→Verify | Bug fixes, small changes |
| `research-only` | Investigate→Synthesize→Report | Architecture research, spikes |
| `tdd-first` | Write Tests→Implement→Refactor→Validate | Test-driven development |
| `review-pipeline` | Implement→Self-Review→Fix→Final-Review | Code quality focused |
| `parallel-build` | Plan→Parallel-Execute→Integrate→Validate | Multi-component features |
| `spike` | Research→Prototype→Evaluate | Technical exploration |
