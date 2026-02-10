# PRD-RPG-UBER-001: ZeroRepo - Repository Planning Graph Implementation

**Status**: ACTIVE
**Author**: System 3 Meta-Orchestrator
**Date**: 2026-02-07
**Version**: 1.0

---

## 1. Executive Summary

Build **ZeroRepo**, a graph-driven framework for generating complete software repositories from natural language specifications. The system implements the Repository Planning Graph (RPG) approach from Luo, Zhang et al. (Microsoft, October 2025), enhanced with Serena LSP-powered code intelligence for ground-truth validation.

### What We're Building

A Python system that:
1. Takes a natural language repository description as input
2. Constructs a structured planning graph (RPG) encoding capabilities, files, data flows, and functions
3. Traverses the graph in topological order to generate working, tested code
4. Validates generated code against the plan using LSP-powered analysis (Serena)
5. Produces a complete, runnable repository with tests

### Why It Matters

Current LLM-based approaches (Claude Code, Gemini CLI, etc.) use natural language as the planning medium, which degrades at scale. The paper demonstrates ZeroRepo achieves:
- **81.5% functionality coverage** (vs 54.2% for Claude Code - +27.3pp)
- **69.7% test pass rate** (vs 33.9% for Claude Code - +35.8pp)
- **3.9x larger repositories** than the strongest baseline
- **Near-linear feature scaling** (vs diminishing returns in baselines)

### Serena Enhancement

The original paper's critical gap: all code analysis is LLM-driven with no actual static analysis. We integrate Serena (github.com/oraios/serena) to provide LSP-powered code intelligence - ground-truth symbol resolution, dependency validation, and structural editing. This pairs RPG's top-down planning with bottom-up semantic understanding.

---

## 2. Architecture Overview

### System Layers

| Layer | Responsibility | Key Components |
|-------|---------------|----------------|
| **User Interface** | Accept specs, display RPG state, deliver outputs | CLI tool (Click/Typer), RPG JSON export |
| **Orchestration** | Coordinate 3-stage pipeline, manage iterations | Pipeline controller, state machine |
| **Planning** | Construct and refine RPG | Feature ontology, explore-exploit engine, graph builder |
| **Generation** | Traverse RPG to produce code | Code generator, test runner, localization engine |
| **Code Intelligence** | LSP-powered code analysis | Serena MCP server, Pyright backend, symbol cache |
| **Infrastructure** | LLM access, execution, storage | LLM gateway (LiteLLM), Docker sandbox, vector DB |

### Three-Stage Pipeline

```
User Specification
        |
        v
[Stage 1: Proposal-Level Construction]
  Feature tree -> Explore-exploit -> Functionality graph
        |
        v
[Stage 2: Implementation-Level Construction]
  Folder encoding -> File encoding -> Data flow -> Function interfaces -> RPG
        |
        v
[Stage 3: Graph-Guided Code Generation]
  Topological traversal -> TDD per node -> Localization -> Validation -> Repository
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Core language | Python 3.11+ | Ecosystem, LLM library support |
| Graph library | NetworkX (prototype) / custom (production) | Rapid dev then optimize |
| Vector DB | ChromaDB (dev) / Qdrant (production) | Local dev, scalable prod |
| Embedding | text-embedding-3-small or all-MiniLM-L6-v2 | Cost-effective similarity |
| LLM gateway | LiteLLM | Unified multi-provider interface |
| Code intelligence | Serena MCP server + Pyright | LSP-powered, 30+ languages |
| Code execution | Docker with resource limits | Isolated test execution |
| Serialization | JSON (RPG), SQLite (session) | Inspectable, portable |
| CLI | Click or Typer | Standard Python CLI |
| Testing | pytest | Generated tests use pytest |

---

## 3. Phase PRD Index

This uber-PRD is decomposed into 6 phase PRDs, each representing a self-contained implementation phase with its own acceptance criteria, tests, and deliverables.

| Phase | PRD ID | Title | Priority | Est. Effort |
|-------|--------|-------|----------|-------------|
| 1 | PRD-RPG-P1-001 | Foundation: Data Model, Graph Primitives, Infrastructure | P0 | High |
| 2 | PRD-RPG-P2-001 | Proposal-Level Construction: Feature Planning Pipeline | P0 | High |
| 3 | PRD-RPG-P3-001 | Implementation-Level Construction: RPG Enrichment | P0 | High |
| 4 | PRD-RPG-P4-001 | Graph-Guided Code Generation | P0 | Very High |
| 5 | PRD-RPG-P5-001 | Evaluation, Benchmarking, and Refinement | P1 | High |
| E2E | PRD-RPG-E2E-001 | System 3 E2E Validation Epic | P0 | Medium |

### Dependency Graph

```
Phase 1 (Foundation)
    |
    +---> Phase 2 (Proposal-Level)
    |         |
    |         +---> Phase 3 (Implementation-Level)
    |                   |
    |                   +---> Phase 4 (Code Generation)
    |                              |
    |                              +---> Phase 5 (Evaluation)
    |
    +---> E2E Validation Epic (runs after EACH phase)
```

---

## 4. RPG Data Model (Shared Across All Phases)

### Node Schema

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique node identifier |
| name | String | Human-readable name |
| level | Enum | MODULE, COMPONENT, FEATURE |
| node_type | Enum | FUNCTIONALITY -> FOLDER_AUGMENTED -> FILE_AUGMENTED -> FUNCTION_AUGMENTED |
| parent_id | UUID/null | Reference to parent node |
| folder_path | String/null | After folder-level encoding |
| file_path | String/null | After file-level encoding |
| interface_type | Enum/null | FUNCTION, CLASS, METHOD (leaf nodes) |
| signature | String/null | Full function/class signature with type hints |
| docstring | String/null | Detailed docstring |
| implementation | String/null | Actual code (populated during generation) |
| test_code | String/null | Generated test code |
| test_status | Enum | PENDING, PASSED, FAILED, SKIPPED |
| serena_validated | Boolean | Whether Serena confirmed structure matches plan |
| actual_dependencies | JSON/null | Dependencies discovered by Serena |
| metadata | JSON | Extensible metadata |

### Edge Schema

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique edge identifier |
| source_id | UUID | Source node |
| target_id | UUID | Target node |
| edge_type | Enum | HIERARCHY, DATA_FLOW, ORDERING, INHERITANCE, INVOCATION |
| data_id | String/null | For DATA_FLOW: data identifier |
| data_type | String/null | For DATA_FLOW: type/structure |
| transformation | String/null | For DATA_FLOW: how data is transformed |
| validated | Boolean | Whether Serena confirmed this edge exists |

### Required Graph Operations

- Add/remove/update nodes and edges
- Topological sort (with cycle detection)
- Subgraph extraction (by module, by level)
- Dependency traversal (ancestors, descendants)
- Node filtering (by type, status, validation state)
- Serialization to/from JSON
- Diff between planned and actual (Serena validation)

---

## 5. Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| NFR-01 | End-to-end generation time (medium complexity) | < 60 minutes |
| NFR-02 | Functionality coverage on benchmarks | > 75% |
| NFR-03 | Test pass rate on generated repos | > 60% |
| NFR-04 | Feature growth linearity (R-squared) | > 0.90 |
| NFR-05 | LLM token budget per generation | < 5M tokens |
| NFR-06 | Runs on single machine, 32GB RAM, no GPU | Required |
| NFR-07 | Deterministic reproduction (same seed + model) | Should Have |
| NFR-08 | Serena LSP query latency (cached) | < 10ms |
| NFR-09 | Serena LSP query latency (cold) | < 500ms |
| NFR-10 | Dependency validation accuracy | > 90% |

---

## 6. Key Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Feature tree unavailability (EpiCoder not open-source) | High | Medium | Build custom ontology from GitHub topics, SO tags, library docs. LLM-generated fallback. |
| LLM cost at scale (30 iterations, multiple calls each) | High | High | Caching, batching, tiered model selection. Budget $5-15/repo. |
| Prompt sensitivity across backends | Medium | High | Prompt testing framework with regression tests. Per-model variants. |
| Cyclic dependencies in topological ordering | Medium | Low | Cycle detection + automated resolution (dependency inversion). |
| Test environment fragility | Medium | Medium | Containerized execution, majority-vote diagnosis. |
| Serena bootstrap on incrementally generated code | Medium | High | Incremental initialization: write files before querying, trigger workspace change notifications. |
| Serena re-indexing latency | Medium | Medium | Batched writes, two-tier caching (repeated queries <10ms). |

---

## 7. System Constraints

1. The system orchestrates LLM calls but does NOT train or fine-tune models
2. Code execution for testing MUST occur in isolated Docker containers
3. The feature ontology MUST be extensible by users (custom domain knowledge)
4. The RPG schema MUST be language-agnostic at the graph level (initial target: Python)
5. All LLM interactions MUST be logged for debugging and prompt improvement
6. Serena language server MUST run in read-write mode for editing operations

---

## 8. Open Decisions

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Feature ontology source | Build custom from public data + LLM supplement | Stability over waiting for EpiCoder |
| Primary LLM backend | Anthropic (Claude Sonnet/Opus) for dev, test others for cost | Strong reasoning, good tool use |
| Graph persistence | SQLite | Persistence + queryability without complexity |
| Test execution | Local Docker | Dev-friendly, secure |
| Language support | Python only (MVP) | RPG schema is language-agnostic, gen templates are not |
| Serena invocation | MCP server (subprocess) | Clean process isolation, standard protocol |
| Serena re-indexing | Batched during generation, on-demand during debugging | Balance latency vs accuracy |

---

## 9. Completion Promises

| # | Promise | Verification Method |
|---|---------|-------------------|
| 1 | Develop uber-PRD and phase PRDs | All PRD files exist with acceptance criteria |
| 2 | Implement ZeroRepo from start to finish | All 5 phases pass unit + functional tests |
| 3 | E2E validate each phase | System 3 validates via Claude in Chrome + test suites |

---

**Version**: 1.0
**Research Papers**: `docs/research/rpg-zerorepo-paper.pdf`, `docs/research/rpg-implementation-plan.pdf`
**Serena**: github.com/oraios/serena
