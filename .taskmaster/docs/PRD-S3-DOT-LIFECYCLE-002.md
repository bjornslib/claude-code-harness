---
prd_id: PRD-S3-DOT-LIFECYCLE-002
title: "LLM-Collaborative Attractor Pipeline: Graph Manipulation Foundation"
product: "Claude Code Harness"
version: "1.0"
status: active
created: "2026-02-23"
author: "System 3 Guardian"
phase: "Phase 1 of 4"
---

# PRD-S3-DOT-LIFECYCLE-002: LLM-Collaborative Attractor Pipeline — Phase 1

## 1. Problem Statement

PRD-S3-ATTRACTOR-001 delivered a static lifecycle management system for DOT pipeline graphs. The CLI can parse, validate, transition, and checkpoint graphs — but cannot **modify** them. The LLM (System 3 or orchestrator) has no tools to add/remove nodes, add/remove edges, or generate minimal scaffolds for iterative refinement.

This means the LLM must either:
- Accept auto-generated graphs wholesale (no design input)
- Manually edit DOT syntax (error-prone, no incremental validation)

The gap analysis (GAP-ANALYSIS-LLM-COLLABORATIVE-ATTRACTOR.md) identified 10 gaps. This PRD covers Phase 1: the graph manipulation foundation (Gaps 1, 2, 3).

## 2. Goals

1. Enable LLMs to iteratively design pipeline graphs through CLI tools
2. Provide node and edge CRUD operations with full validation
3. Add scaffold generation for minimal starting graphs
4. Update System 3 and orchestrator documentation to reference the new workflow
5. Verify the complete workflow against a real project (story-writer)

## 3. Success Criteria

- An LLM can generate a scaffold, add nodes, add edges, validate, and checkpoint — all via CLI commands
- The iterative refinement loop (scaffold → modify → validate → adjust → checkpoint) works end-to-end
- Existing `generate`, `validate`, `transition`, and `checkpoint` commands remain backward compatible
- The story-writer project can be used as a test case for the full workflow

## 4. Epic Breakdown

### Epic A: Node CRUD Operations (P0)

Add CLI subcommands for adding, removing, and modifying nodes in a DOT pipeline graph.

#### Features

**F-A1: `attractor node add`**
- Add a new node to an existing DOT file
- Required parameters: `--id`, `--shape` (box/hexagon/diamond/Msquare/parallelogram/point/record), `--handler`
- Optional parameters: `--label`, `--worker-type`, `--bead-id`, `--acceptance`, `--promise-ac`, `--status`
- Validates: no duplicate ID, shape is valid, handler matches shape
- If shape is `box` (codergen), auto-creates paired hexagon AT node (with edge) unless `--no-at-pair`
- Writes updated DOT file in place

**F-A2: `attractor node remove`**
- Remove a node by ID from a DOT file
- `--cascade` flag removes all connected edges
- Without `--cascade`, fails if node has edges (safety)
- If removing a codergen node, also removes its paired AT hexagon (with confirmation or `--force`)

**F-A3: `attractor node modify`**
- Modify attributes of an existing node
- Can change: `--label`, `--handler`, `--worker-type`, `--bead-id`, `--acceptance`, `--promise-ac`, `--status`
- Cannot change: `--id` (use remove + add), `--shape` (shape determines handler type)
- Validates modified attributes against schema

**Acceptance Criteria:**
1. `node add` creates a valid node with correct DOT syntax and attributes
2. `node add` with shape=box auto-creates paired AT hexagon
3. `node remove` without `--cascade` fails if edges exist
4. `node remove --cascade` removes node and all connected edges
5. `node modify` updates attributes while preserving graph structure
6. All operations produce valid DOT that passes `attractor validate`

### Epic B: Edge CRUD Operations (P0)

Add CLI subcommands for adding, removing, and listing edges.

#### Features

**F-B1: `attractor edge add`**
- Add an edge between two existing nodes
- Parameters: `<from_node>` `<to_node>` `[--label "reason"]`
- Validates: both nodes exist, no duplicate edge, no self-loop
- Cycle detection: warns if adding this edge creates a cycle (but allows it with `--allow-cycle`)

**F-B2: `attractor edge remove`**
- Remove an edge between two nodes
- Parameters: `<from_node>` `<to_node>`
- Fails if edge doesn't exist

**F-B3: `attractor edge list`**
- List all edges, optionally filtered
- `--from <node>` — edges originating from node
- `--to <node>` — edges terminating at node
- `--json` — machine-readable output

**Acceptance Criteria:**
1. `edge add` creates valid DOT edge syntax
2. `edge add` detects and warns about cycles
3. `edge remove` correctly removes the specified edge
4. `edge list` shows all edges with optional filtering
5. All operations produce valid DOT that passes `attractor validate`

### Epic C: Scaffold Generation Mode (P1)

Add `--scaffold` flag to the `generate` command.

#### Features

**F-C1: `attractor generate --scaffold`**
- Produces minimal graph: start node, one placeholder per epic/feature, exit node
- Sequential edges between placeholders (conservative default)
- No validation gates, no conditional routing (LLM designs these)
- Each placeholder has `handler=codergen`, `status=pending`, `label` from epic/feature title
- Can work from `--prd` flag (reads PRD markdown) or from beads (existing behavior)

**F-C2: PRD-aware scaffold**
- When `--prd <file.md>` is provided, read the PRD and extract epics/features
- Create one placeholder codergen node per epic
- Set `label` to epic title, `acceptance` to epic's acceptance criteria text
- If beads exist for the same epic, cross-reference with `--bead-id`

**Acceptance Criteria:**
1. `generate --scaffold` produces a valid minimal graph
2. Scaffold has exactly one start node, one exit node, and placeholder nodes
3. Scaffold nodes are sequentially connected (start → placeholder1 → ... → exit)
4. `generate --scaffold --prd` extracts epics from PRD markdown
5. Scaffold passes `attractor validate`
6. LLM can use node/edge CRUD to refine the scaffold into a full pipeline

### Epic D: Documentation Updates (P1)

Update System 3 and orchestrator documentation to reference the new iterative refinement workflow.

#### Features

**F-D1: S3 output style — DOT Graph Navigation update**
- Add "Iterative Refinement Loop" subsection
- Document: scaffold → parse → node add/remove → edge add/remove → validate → checkpoint
- Reference new CLI commands with examples

**F-D2: Orchestrator skill — LLM graph editing workflow**
- Add section to orchestrator-multiagent SKILL.md
- Document when orchestrators should use graph editing (before execution phase)
- Show example workflow of refining a scaffold

**Acceptance Criteria:**
1. S3 output style contains iterative refinement loop documentation
2. Orchestrator skill contains graph editing workflow documentation
3. Examples use real CLI commands (not pseudocode)
4. Backward compatibility noted (existing workflows unchanged)

### Epic E: E2E Verification (P1)

Verify the complete workflow against the story-writer project.

#### Features

**F-E1: Story-writer scaffold generation**
- Generate a scaffold from story-writer's codebase or a test PRD
- Verify scaffold is valid and minimal

**F-E2: Graph refinement**
- Use node/edge CRUD to refine the scaffold
- Add validation gates, conditional routing, parallel groups
- Verify the refined graph passes validation

**F-E3: Full lifecycle test**
- Checkpoint the refined graph
- Run status to show dispatchable nodes
- Verify the graph is execution-ready

**Acceptance Criteria:**
1. Scaffold generated for story-writer validates successfully
2. Node add/remove/modify operations work on the scaffold
3. Edge add/remove operations work on the scaffold
4. Refined graph passes `attractor validate`
5. `attractor status` shows correct dispatchable nodes
6. `attractor checkpoint save` preserves the refined state

## 5. Technical Constraints

- All new commands must be subcommands of `cli.py` (same entry point)
- DOT file format must remain compatible with Graphviz
- Parser must handle both generated and hand-edited DOT files
- Node IDs must be valid DOT identifiers (alphanumeric + underscore)
- All operations must be idempotent where possible
- Changes must be backward compatible with existing `generate`/`validate`/`transition`

## 6. Out of Scope

- Semantic validation (`validate --semantic --prd`) — Phase 2
- PRD analysis tool (`analyze-prd`) — Phase 2
- Explain/Suggest commands — Phase 3
- Diff/Compare tool — Phase 3
- ZeroRepo bridge — Phase 4
- Parallel dispatch locking — Already implemented in PR #15

## 7. Dependencies

- PR #15 (DOT lifecycle gaps) should be merged first for JSONL logging and signal files
- story-writer repo must have attractor CLI deployed (confirmed: yes)
