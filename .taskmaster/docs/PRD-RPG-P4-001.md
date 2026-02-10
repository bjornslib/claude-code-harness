# PRD-RPG-P4-001: Graph-Guided Code Generation Engine

**Version:** 1.0
**Status:** Draft
**Created:** 2026-02-07
**Phase:** 4 of 6
**Dependencies:** PRD-RPG-P3-001 (RPG Construction)

## Executive Summary

Phase 4 is the **core code generation engine** of ZeroRepo. Given a completed Repository Planning Graph (RPG) from Phase 3, it traverses the graph in topological order and generates working, tested code through a test-driven development loop. This phase produces the actual repository artifact.

**Key Innovation**: Graph-guided localization combined with Serena's LSP-powered structural editing enables precise debugging without breaking working code. The TDD loop ensures each function passes tests before moving to the next node.

**Success Metrics**:
- 60%+ of generated tests pass on first try
- 80%+ of planned dependencies validated by Serena
- Repository builds successfully (`pip install -e .`)
- Generation completes in <30 min for 50-function fixture

---

## Background and Context

### Problem Statement

Previous code generation approaches suffer from:
- **No execution order**: generating files randomly breaks dependencies
- **No validation**: untested code accumulates, failures cascade
- **Poor localization**: LLMs can't find code to fix without perfect context
- **Fragile editing**: naive string replacements break working code

### ZeroRepo Solution

The RPG provides:
1. **Topological order**: generate base classes before derived, utilities before consumers
2. **Test-first loop**: each function must pass tests before commit
3. **Graph-guided search**: fuzzy match failures to RPG node descriptions
4. **Serena precision**: LSP-powered exact symbol lookup and surgical edits

### Architecture Position

```
Phase 1: NL Spec → Phase 2: Plan Refinement → Phase 3: RPG Construction
                                                        ↓
                                              Phase 4: CODE GENERATION ← (this PRD)
                                                        ↓
Phase 5: Repository Validation → Phase 6: User Acceptance
```

**Input**: Completed RPG JSON (nodes, edges, hierarchies, docstrings)
**Output**: Working repository with tests, requirements, README

---

## Goals and Success Criteria

### Epic 4.1: Topological Order Traversal Engine

**Goal**: Compute valid generation order from RPG structure, ensuring dependencies are satisfied before consumers.

**Requirements**:
1. **Dependency Graph Analysis**
   - Parse RPG edges to build directed acyclic graph (DAG)
   - Detect cycles (should be impossible from Phase 3, but validate)
   - Compute topological sort using Kahn's algorithm or DFS
   - Handle hierarchical relationships: process parent nodes before children

2. **Generation State Tracking**
   - Track per-node status: `pending`, `in_progress`, `passed`, `failed`, `skipped`
   - Persist state to JSON checkpoint file after each node
   - Support resume from checkpoint (idempotent generation)
   - Log dependency resolution decisions

3. **Partial Generation Support**
   - CLI flag: `--start-from-node <node_id>` to resume
   - Skip nodes marked `passed` in checkpoint
   - Regenerate nodes marked `failed` or `in_progress`
   - Validate all dependencies of resume node are satisfied

4. **Graceful Failure Handling**
   - If node fails after max retries (8), mark `failed` and continue
   - Skip downstream nodes that depend on failed node
   - Generate final report: success/fail/skip counts per subgraph
   - Export partial repository even if some nodes fail

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_topological_sort_linear_chain()`: A→B→C produces [A,B,C]
  - `test_topological_sort_diamond()`: A→{B,C}→D produces A before {B,C}, {B,C} before D
  - `test_cycle_detection()`: raises error on A→B→A
  - `test_checkpoint_resume()`: can restart from node #5 of 10
  - `test_failed_node_propagation()`: if B fails, C (depends on B) is skipped

- **Functional Tests**:
  - Given RPG fixture with 20 nodes across 3 subgraphs:
    - Generate valid topological order in <1s
    - Checkpoint file written after each node
    - Resume from node #10 skips first 9 nodes
    - Failed node B causes downstream C,D to skip (not fail)

**Edge Cases**:
- Multiple valid topological orders (choose deterministically by node ID)
- Leaf nodes with no dependents (process last)
- Root nodes with no dependencies (process first)

---

### Epic 4.2: Test-Driven Development Loop (per leaf node)

**Goal**: For each RPG leaf node, generate tests first, then implementation, validate in sandbox, and only commit passing code.

**Requirements**:
1. **Test Generation from Specification**
   - Extract docstring from RPG node (includes signature, args, return type)
   - Generate pytest test cases covering:
     - Happy path (typical inputs)
     - Edge cases (empty lists, None, boundary values)
     - Error cases (invalid types, out-of-range values)
   - Use node's example usage (if present) as additional test case
   - Write test to `tests/test_{module_name}.py`

2. **Implementation Code Generation**
   - Generate function body from docstring specification
   - Include type hints from signature
   - Add inline comments explaining complex logic
   - Write to proper module path (from node's `file_path` attribute)
   - Maintain existing imports/classes in file (append only on first pass)

3. **Docker Sandbox Execution**
   - Spin up isolated Python container with dependencies
   - Mount repository code as read-only volume
   - Run `pytest tests/test_{module}.py::{test_name} -v`
   - Capture stdout/stderr and exit code
   - Timeout after 30s per test (prevent infinite loops)

4. **Debugging Loop (max 8 iterations)**
   - If test fails: enter debugging mode
   - Use graph-guided localization (Epic 4.3) to find bug
   - Use Serena editing (Epic 4.4) to fix implementation
   - Re-run test in sandbox
   - Repeat until pass OR hit iteration limit
   - If limit reached: mark node `failed`, log failure reason

5. **Commit Logic**
   - On test pass: mark node `passed`, commit to repository
   - On test fail after 8 retries: mark node `failed`, revert changes
   - Update checkpoint file with final status
   - Trigger regression tests if modifying existing passing code (Epic 4.5)

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_generate_test_from_docstring()`: produces valid pytest function
  - `test_generate_implementation_from_spec()`: produces runnable Python code
  - `test_sandbox_timeout()`: kills hung test after 30s
  - `test_debugging_iteration_limit()`: stops after 8 failed fix attempts
  - `test_revert_on_failure()`: failed node doesn't pollute repository

- **Functional Tests**:
  - Given RPG node for `calculate_mean(numbers: List[float]) -> float`:
    - Test generation creates 3+ test cases
    - Implementation passes all tests on first try (simple spec)
    - Test execution completes in <5s
  - Given RPG node with intentionally buggy spec:
    - Debugging loop activates
    - Localization identifies the buggy function
    - Fix applied via Serena
    - Test passes within 3 iterations

**Edge Cases**:
- Flaky tests (network timeouts, randomness): majority-vote diagnosis (Epic 4.5)
- Missing imports in generated code: auto-detect from test failure, add to file
- Conflicting function signatures: prioritize RPG spec over generated code

---

### Epic 4.3: Graph-Guided Localization Engine

**Goal**: Provide three complementary tools to locate buggy code during debugging: RPG search, repository view, and dependency exploration.

**Requirements**:
1. **RPG-Guided Fuzzy Search**
   - Input: natural language query (e.g., "find validation logic", "where is mean calculated")
   - Embed query using sentence transformer (same as Phase 3 node embeddings)
   - Compute cosine similarity against all RPG node descriptions
   - Return top-5 matching nodes with scores
   - Highlight matching keywords in node docstrings
   - Limit to current subgraph (don't search entire RPG unless flag set)

2. **Repository Code View**
   - Input: node ID or file path
   - Retrieve full source code for file (with syntax highlighting)
   - Extract all function/class signatures (via AST parsing)
   - Show interfaces without implementation (1-line preview per function)
   - Support drill-down: "show implementation of function X"
   - Cache file contents to avoid re-reading

3. **Dependency Exploration**
   - Input: node ID
   - Show incoming edges (who depends on this node)
   - Show outgoing edges (what this node depends on)
   - Traverse 2 hops: "what depends on my dependencies?"
   - Visualize as ASCII tree or JSON structure
   - Highlight nodes marked `failed` (may be root cause)

4. **Localization Attempt Tracking**
   - Log each localization query (query, tool used, results)
   - Limit to 20 attempts per debugging iteration (prevent infinite search)
   - If limit reached: escalate to human review (export debug context)
   - Provide search history to next iteration (avoid repeating failed searches)

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_fuzzy_search_exact_match()`: "calculate mean" finds `calculate_mean` node
  - `test_fuzzy_search_semantic()`: "average" finds `calculate_mean` node (semantic match)
  - `test_code_view_signatures()`: extracts function names and type hints
  - `test_dependency_traversal()`: A→B→C, querying B shows A and C
  - `test_localization_limit()`: 21st attempt raises `LocalizationExhaustedError`

- **Functional Tests**:
  - Given test failure: "AssertionError: expected 5.0, got nan"
    - Fuzzy search "mean calculation" returns correct node
    - Code view shows function body with float division
    - Dependency exploration reveals missing zero-check in upstream validator
  - Given RPG with 50 nodes:
    - Fuzzy search completes in <500ms
    - Code view retrieves file in <100ms
    - Dependency traversal (2 hops) completes in <200ms

**Edge Cases**:
- Query matches multiple nodes equally: return all with same score
- Node has no dependencies: show empty list (not error)
- File not yet generated: code view shows "not yet generated" message

---

### Epic 4.4: Serena-Powered Localization and Editing

**Goal**: Enhance localization with Serena's LSP tools for exact symbol lookup and surgical code edits without breaking structure.

**Requirements**:
1. **Serena Integration Setup**
   - Initialize Serena workspace pointing to generated repository
   - Trigger re-indexing after each file write batch (see Epic 4.7)
   - Handle Serena MCP connection failures gracefully (fall back to RPG search)
   - Cache Serena responses to reduce MCP round-trips

2. **Exact Symbol Localization** (`find_symbol`)
   - Input: function/class name from test failure traceback
   - Query Serena for exact definition location (file, line, column)
   - Return full symbol context (signature, docstring, body preview)
   - Faster than fuzzy search (LSP index vs embedding similarity)
   - Use as first localization attempt before falling back to RPG search

3. **Caller Tracing** (`find_referencing_symbols`)
   - Input: symbol name from suspected bug location
   - Find all call sites in repository
   - Validate actual dependencies match RPG edges (catch Phase 3 errors)
   - Identify unused functions (generated but never called)
   - Surface in debugging context: "this function is called by X, Y, Z"

4. **Surgical Symbol Editing** (`replace_symbol_body`)
   - Input: symbol name, new implementation code
   - Replace only function body, preserve signature and decorators
   - Maintain indentation and formatting
   - Atomic write: either succeeds fully or reverts
   - Verify syntax validity before writing (AST parse check)

5. **Structural Insertion** (`insert_after_symbol`, `insert_before_symbol`)
   - Add new methods to existing class without manual positioning
   - Insert helper functions near usage site
   - Maintain class structure (group related methods)
   - Preserve existing docstrings and comments

6. **Safe Renaming** (`rename_symbol`)
   - Propagate interface name changes across all call sites
   - Update imports automatically
   - Validate no name collisions
   - Use when RPG node name doesn't match generated code

**Strategy**: Try Serena first (fast, precise), fall back to RPG-guided when:
- Serena can't find symbol (not yet generated or LSP index stale)
- Symbol ambiguous (multiple definitions in different files)
- Serena MCP connection unavailable

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_find_symbol_exact()`: locates `calculate_mean` in 3 files
  - `test_find_referencing_symbols()`: finds 5 call sites of `validate_input`
  - `test_replace_symbol_body()`: updates function without breaking signature
  - `test_insert_after_symbol()`: adds method after existing method in class
  - `test_rename_symbol()`: renames function and updates 4 call sites
  - `test_serena_fallback()`: falls back to RPG search on MCP failure

- **Functional Tests**:
  - Given generated repository with 10 files, 30 functions:
    - Serena localization finds symbols in <200ms (vs 500ms fuzzy search)
    - Replace symbol body preserves 100% of non-body lines
    - Rename symbol updates all references (validated by grep)
  - Given test failure in `process_data()`:
    - Serena finds symbol in 1 attempt (vs 3 attempts with fuzzy search)
    - `find_referencing_symbols` reveals 2 callers with wrong argument types
    - Fix applied via `replace_symbol_body`, test passes

**Edge Cases**:
- Symbol exists in multiple files: return all, let user/LLM choose
- LSP index out of sync: trigger re-index, retry once
- Symbol is a class method: handle class.method syntax
- Generated code has syntax errors: Serena fails, fall back to AST-based editing

---

### Epic 4.5: Staged Test Validation Framework

**Goal**: Three-tiered testing aligned with RPG structure: unit tests per function, regression tests on modifications, integration tests per subgraph.

**Requirements**:
1. **Unit Test Validation** (per leaf node)
   - Generate from node docstring (Epic 4.2)
   - Run in isolation (mock all dependencies)
   - Pass threshold: 100% of unit tests must pass before commit
   - Coverage goal: test all code paths (branches, edge cases)
   - Store test results in checkpoint file

2. **Regression Test Triggering**
   - Detect when debugging modifies a previously `passed` node
   - Re-run all unit tests for that node
   - If regression detected: revert change, try different fix
   - If no regression: commit change, update checkpoint
   - Log regression events for final report

3. **Integration Test Validation** (per subgraph)
   - Triggered when all leaf nodes in subgraph marked `passed`
   - Test data flow across module boundaries
   - Example: for data processing pipeline, validate end-to-end transformation
   - Generate integration tests from RPG subgraph structure:
     - Identify entry points (nodes with no dependencies)
     - Identify exit points (nodes with no dependents)
     - Create test that calls entry → validates exit output
   - Pass threshold: 80% of integration tests (some may fail due to spec ambiguity)

4. **Majority-Vote Diagnosis** (5 rounds, LLM judge)
   - When test fails: ask LLM "is this an implementation bug or test/environment issue?"
   - Run diagnosis 5 times with different temperatures
   - If ≥3 say "implementation bug": enter debugging loop (Epic 4.2)
   - If ≥3 say "test issue": regenerate test
   - If ≥3 say "environment issue": log warning, skip node
   - Prevents wasting debugging iterations on flaky/bad tests

5. **Test Artifact Management**
   - Store all tests in `tests/` directory (pytest convention)
   - Organize by module: `tests/test_module_name.py`
   - Generate `pytest.ini` with coverage settings
   - Export test results as JUnit XML (for CI integration later)
   - Track coverage per node (store in checkpoint)

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_unit_test_generation()`: creates pytest function with 3+ cases
  - `test_regression_detection()`: modifying passed node re-runs tests
  - `test_integration_test_generation()`: creates end-to-end test from subgraph
  - `test_majority_vote_implementation_bug()`: 5/5 agree → debug
  - `test_majority_vote_test_issue()`: 4/5 say bad test → regenerate test

- **Functional Tests**:
  - Given RPG subgraph with 5 nodes:
    - Unit tests generated for all 5 nodes
    - Integration test covers entry (node 1) → exit (node 5) flow
    - Regression test triggered when node 3 modified during debugging
  - Given intentionally flaky test (random failure):
    - Majority vote identifies "environment issue" 80%+ of time
    - Node not marked failed due to flakiness

**Edge Cases**:
- Integration test requires external resource (database): mock with fixture
- Majority vote split 2-2-1: escalate to human review
- Test times out: treat as environment issue, skip node

---

### Epic 4.6: Repository Assembly

**Goal**: Write generated code to proper file structure, manage cross-file references, and generate repository metadata (README, requirements, setup.py).

**Requirements**:
1. **File Structure Generation**
   - Create directory hierarchy from RPG node paths
     - Example: `rpg_node.file_path = "src/data/processors.py"` → create `src/data/`
   - Generate `__init__.py` for each package (with `__all__` exports)
   - Organize by module: related functions in same file
   - Follow Python conventions: `src/` for code, `tests/` for tests, `docs/` for docs

2. **Import Management**
   - Track dependencies from RPG edges
   - Generate import statements at top of each file
   - Resolve relative vs absolute imports (use absolute for clarity)
   - Group imports: stdlib, third-party, local (PEP 8)
   - Auto-detect missing imports from test failures, add to file

3. **Cross-File Reference Resolution**
   - When node A depends on node B in different file:
     - Add `from B_module import B_function` to A's file
     - Validate import path matches actual file structure
     - Handle circular imports: raise warning, suggest refactoring
   - Use RPG edges as ground truth for dependencies

4. **Requirements.txt Generation**
   - Extract library dependencies from RPG node specifications
   - Detect imports in generated code (scan for third-party packages)
   - Pin versions: `numpy>=1.24.0,<2.0.0` (allow minor updates)
   - Include dev dependencies: `pytest`, `black`, `mypy`
   - Generate both `requirements.txt` and `requirements-dev.txt`

5. **setup.py / pyproject.toml Generation**
   - Extract metadata from Phase 1 NL spec (project name, description, author)
   - Set entry points if CLI detected in RPG
   - Include package discovery: `find_packages(where="src")`
   - Add classifiers: Python version, license, development status
   - Prefer `pyproject.toml` (modern), fall back to `setup.py` if needed

6. **README.md Generation**
   - Extract project overview from Phase 1 spec
   - Generate usage examples from RPG node examples
   - List key modules and their purposes (from RPG subgraphs)
   - Include installation instructions: `pip install -e .`
   - Add testing instructions: `pytest tests/`
   - Link to generated RPG JSON artifact (for inspection)

7. **RPG Artifact Export**
   - Export final RPG as `docs/rpg.json` (inspectable artifact)
   - Include node statuses: `passed`, `failed`, `skipped`
   - Store generation metadata: timestamp, LLM model, phase versions
   - Human-readable format (indented JSON, not minified)

8. **Coverage Report**
   - Compare planned vs generated:
     - Total nodes planned: X
     - Nodes passed: Y (Z%)
     - Nodes failed: A (B%)
     - Nodes skipped: C (D%)
   - Export as `docs/generation_report.md`
   - Include failure reasons for each failed node

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_directory_creation()`: creates `src/data/` from path `src/data/module.py`
  - `test_init_generation()`: generates `__init__.py` with correct exports
  - `test_import_resolution()`: adds `from foo import bar` when node depends on bar
  - `test_requirements_extraction()`: detects `numpy`, `pandas` from code
  - `test_readme_generation()`: includes project name, installation, usage
  - `test_coverage_report()`: shows 15/20 passed (75%)

- **Functional Tests**:
  - Given RPG with 3 subgraphs, 15 files, 50 functions:
    - Repository structure matches RPG paths
    - All `__init__.py` files generated with exports
    - `pip install -e .` succeeds without errors
    - `pytest tests/` runs (even if some fail)
    - README.md includes usage examples
    - Coverage report shows breakdown by subgraph

**Edge Cases**:
- Node path conflicts (two nodes → same file): merge into same file, different functions
- Circular imports: log warning, suggest restructuring in report
- Missing project metadata: use placeholder values, log warning

---

### Epic 4.7: Incremental Workspace Management

**Goal**: Manage file writes, trigger Serena re-indexing, maintain clean repository state, and support checkpoint/resume for long runs.

**Requirements**:
1. **Batched File Writing**
   - Buffer generated code in memory during node processing
   - Write to disk in batches (after each subgraph or every 5 nodes)
   - Atomic writes: use temp file + rename (avoid partial writes)
   - Maintain file consistency: never leave half-written files
   - Log each write operation for debugging

2. **Serena Workspace Re-Indexing**
   - Trigger Serena LSP re-index after each write batch
   - Wait for index completion before next localization (avoid stale results)
   - Timeout after 10s (Serena may hang on large repos)
   - Fall back to RPG search if re-index fails
   - Cache re-index status: skip if no files changed since last index

3. **Repository State Management**
   - Track which files are "dirty" (modified but not committed)
   - Validate syntax of all Python files before commit (AST parse)
   - Revert file if syntax error detected (don't corrupt repository)
   - Maintain `.gitignore`: exclude `__pycache__`, `*.pyc`, `.pytest_cache`

4. **Checkpoint/Resume Support**
   - Checkpoint file: `docs/generation_checkpoint.json`
   - Schema: `{node_id: {status, timestamp, test_results, retry_count}}`
   - Write after each node completion (success or failure)
   - Resume: read checkpoint, skip `passed` nodes, retry `in_progress` and `failed`
   - Idempotent: running twice produces same result

5. **Git Integration** (optional but recommended)
   - Initialize git repository: `git init` on first run
   - Commit after each successful subgraph:
     - Commit message: "feat: complete [subgraph_name] (nodes X-Y)"
     - Tag: `phase4-subgraph-{id}`
   - Provide rollback capability: revert to last passing subgraph
   - Export git log as part of generation report

6. **Long-Running Job Support**
   - Estimate remaining time: (completed_nodes / total_nodes) * elapsed_time
   - Log progress every 10 nodes: "Completed 30/50 nodes (60%), ETA: 15 min"
   - Support graceful shutdown: SIGINT writes checkpoint, exits cleanly
   - Support resume after crash: read checkpoint, continue from last node

**Acceptance Criteria**:
- **Unit Tests**:
  - `test_batched_write()`: writes 5 files, flushes after 5th
  - `test_atomic_write()`: temp file renamed only after full write
  - `test_syntax_validation()`: rejects file with syntax error
  - `test_checkpoint_write()`: checkpoint updated after each node
  - `test_checkpoint_resume()`: skips passed nodes, retries failed
  - `test_graceful_shutdown()`: SIGINT writes checkpoint before exit

- **Functional Tests**:
  - Given RPG with 20 nodes:
    - Files written in batches of 5
    - Serena re-index triggered 4 times (after each batch)
    - Checkpoint file updated 20 times
    - Simulation: kill process after node 12, resume completes nodes 13-20
  - Given long-running job (50 nodes, 30 min):
    - Progress logged every 10 nodes
    - ETA accurate to ±5 min
    - Graceful shutdown saves progress, resume from same point

**Edge Cases**:
- Disk full during write: catch exception, log error, mark node failed
- Serena re-index timeout: fall back to RPG search, log warning
- Checkpoint file corrupted: fall back to regenerating all nodes (warn user)
- Git conflicts (user modified files): abort with error, suggest manual resolution

---

## Architecture and Design

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 4: Graph-Guided Code Generation Engine                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Epic 4.1: Topological Traversal                             │    │
│  │ - Compute generation order from RPG                         │    │
│  │ - Track state: pending → in_progress → passed/failed       │    │
│  └──────────────┬─────────────────────────────────────────────┘    │
│                 │                                                    │
│                 ▼                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Epic 4.2: Test-Driven Development Loop (per node)           │    │
│  │ 1. Generate test from docstring                             │    │
│  │ 2. Generate implementation                                   │    │
│  │ 3. Run test in Docker sandbox                               │    │
│  │ 4. If fail: debug loop (max 8 iterations) ──┐               │    │
│  │ 5. If pass: commit to repository             │               │    │
│  └──────────────┬───────────────────────────────┼───────────────┘    │
│                 │                               │                    │
│                 │ (on test failure)             │                    │
│                 │                               ▼                    │
│                 │              ┌─────────────────────────────────┐  │
│                 │              │ Epic 4.3: Graph-Guided          │  │
│                 │              │ Localization Engine             │  │
│                 │              │ - RPG fuzzy search              │  │
│                 │              │ - Repository code view          │  │
│                 │              │ - Dependency exploration        │  │
│                 │              └────────┬────────────────────────┘  │
│                 │                       │                            │
│                 │                       ▼                            │
│                 │              ┌─────────────────────────────────┐  │
│                 │              │ Epic 4.4: Serena-Powered        │  │
│                 │              │ Localization and Editing        │  │
│                 │              │ - find_symbol (exact lookup)    │  │
│                 │              │ - replace_symbol_body (surgical)│  │
│                 │              │ - find_referencing_symbols      │  │
│                 │              └────────┬────────────────────────┘  │
│                 │                       │                            │
│                 │                       │ (fix applied)              │
│                 │                       └──────────┐                 │
│                 │                                  │                 │
│                 │                                  ▼                 │
│                 │              ┌─────────────────────────────────┐  │
│                 │              │ Epic 4.5: Staged Test           │  │
│                 │              │ Validation Framework            │  │
│                 │              │ - Unit tests (per node)         │  │
│                 │              │ - Regression tests (on modify)  │  │
│                 │              │ - Integration tests (subgraph)  │  │
│                 │              │ - Majority-vote diagnosis       │  │
│                 │              └─────────────────────────────────┘  │
│                 │                                                    │
│                 ▼                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Epic 4.6: Repository Assembly                               │    │
│  │ - File structure generation                                 │    │
│  │ - Import management                                         │    │
│  │ - README, requirements, setup.py                            │    │
│  │ - RPG artifact export                                       │    │
│  │ - Coverage report                                           │    │
│  └──────────────┬─────────────────────────────────────────────┘    │
│                 │                                                    │
│                 ▼                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Epic 4.7: Incremental Workspace Management                  │    │
│  │ - Batched file writing                                      │    │
│  │ - Serena re-indexing                                        │    │
│  │ - Checkpoint/resume support                                 │    │
│  │ - Git integration                                           │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

INPUT:  RPG JSON (from Phase 3)
OUTPUT: Working repository with tests, README, requirements
```

### Data Flow

```
RPG JSON
  │
  ├─→ Topological Sort → [Node A, Node B, Node C, ...]
  │
  └─→ For each node in order:
       │
       ├─→ Generate test from docstring
       │    └─→ Write to tests/test_module.py
       │
       ├─→ Generate implementation
       │    └─→ Write to src/module.py
       │
       ├─→ Run test in Docker sandbox
       │    │
       │    ├─→ PASS → Mark node 'passed', commit code
       │    │
       │    └─→ FAIL → Enter debugging loop:
       │         │
       │         ├─→ Localize bug (Epic 4.3: RPG search)
       │         │    └─→ Find candidate functions
       │         │
       │         ├─→ Localize bug (Epic 4.4: Serena)
       │         │    └─→ find_symbol, find_referencing_symbols
       │         │
       │         ├─→ Fix bug (Epic 4.4: Serena)
       │         │    └─→ replace_symbol_body
       │         │
       │         ├─→ Re-run test
       │         │
       │         └─→ Repeat (max 8 iterations) → If still fails: mark 'failed'
       │
       └─→ Update checkpoint file
            └─→ Continue to next node

After all nodes:
  │
  ├─→ Run integration tests per subgraph (Epic 4.5)
  │
  ├─→ Generate repository metadata (Epic 4.6):
  │    ├─→ README.md
  │    ├─→ requirements.txt
  │    ├─→ setup.py / pyproject.toml
  │    └─→ docs/generation_report.md
  │
  └─→ Export final RPG artifact
       └─→ docs/rpg.json
```

### Key Algorithms

**Topological Sort** (Epic 4.1):
```python
def topological_sort(rpg_nodes, rpg_edges):
    """Kahn's algorithm for DAG traversal."""
    in_degree = {node.id: 0 for node in rpg_nodes}
    for edge in rpg_edges:
        in_degree[edge.target] += 1

    queue = [node for node in rpg_nodes if in_degree[node.id] == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for edge in rpg_edges:
            if edge.source == node.id:
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(find_node(edge.target))

    if len(result) != len(rpg_nodes):
        raise CycleDetectedError("RPG contains circular dependencies")

    return result
```

**TDD Loop** (Epic 4.2):
```python
def generate_and_test_node(node, max_retries=8):
    """Test-driven development loop for single node."""
    test_code = generate_test_from_docstring(node.docstring)
    write_file(f"tests/test_{node.module}.py", test_code)

    impl_code = generate_implementation(node.docstring)
    write_file(node.file_path, impl_code)

    for iteration in range(max_retries):
        result = run_test_in_sandbox(test_code)

        if result.passed:
            mark_node_passed(node.id)
            commit_code(node.file_path)
            return True

        # Debugging loop
        bug_location = localize_bug(node, result.error_message)
        fix = generate_fix(bug_location, result.error_message)
        apply_fix_via_serena(bug_location, fix)

    mark_node_failed(node.id)
    revert_code(node.file_path)
    return False
```

**Serena-First Localization** (Epic 4.4):
```python
def localize_bug(node, error_message):
    """Try Serena first, fall back to RPG search."""
    # Extract function name from traceback
    function_name = extract_function_from_traceback(error_message)

    # Try Serena exact lookup
    try:
        location = serena.find_symbol(function_name)
        if location:
            return location
    except SerenaError:
        pass  # Fall back to RPG search

    # Fall back to RPG fuzzy search
    query = f"find {function_name} or related validation logic"
    candidates = rpg_fuzzy_search(query, top_k=5)

    return candidates[0]  # Return top match
```

---

## Testing Strategy

### Unit Testing (per epic)

Each epic must have comprehensive unit tests covering:
- Happy path: typical inputs produce expected outputs
- Edge cases: empty inputs, boundary values, None handling
- Error cases: invalid inputs raise appropriate exceptions
- Mocking: external dependencies (Docker, Serena MCP) are mocked

**Example** (Epic 4.2 - TDD Loop):
```python
def test_generate_test_from_docstring():
    """Test generation creates valid pytest function."""
    docstring = """
    Calculate mean of numbers.

    Args:
        numbers: List of floats
    Returns:
        float: Mean value
    """
    node = RPGNode(id="test", docstring=docstring)

    test_code = generate_test_from_docstring(node.docstring)

    assert "def test_calculate_mean" in test_code
    assert "assert" in test_code
    assert "numbers" in test_code

def test_debugging_iteration_limit():
    """Stops after 8 failed fix attempts."""
    node = create_buggy_node()

    result = generate_and_test_node(node, max_retries=8)

    assert result == False  # Failed after 8 retries
    assert node.status == "failed"
    assert node.retry_count == 8
```

### Functional Testing (end-to-end)

**Master Test Fixture**: Small ML library RPG
- 5 modules (data loading, preprocessing, model, evaluation, visualization)
- 15 files
- 50 functions
- 10 integration points

**Functional Test Scenarios**:
1. **Full Generation Test**:
   - Input: Complete RPG JSON fixture
   - Expected: Repository with 60%+ tests passing, builds successfully
   - Validation: `pip install -e . && pytest tests/`

2. **Checkpoint/Resume Test**:
   - Generate first 25 nodes
   - Kill process (simulate crash)
   - Resume: should skip first 25, complete 26-50
   - Validation: checkpoint shows 50/50 completed

3. **Debugging Loop Test**:
   - Input: RPG node with intentionally buggy spec (off-by-one error)
   - Expected: Debugging loop localizes bug, fixes within 3 iterations
   - Validation: test passes after fix

4. **Serena Integration Test**:
   - Generate repository with 10 files
   - Trigger debugging on function in file #5
   - Expected: Serena finds symbol in <200ms, fix applied surgically
   - Validation: compare pre/post edit, only function body changed

5. **Integration Test Validation**:
   - Complete one subgraph (5 nodes)
   - Expected: Integration test runs end-to-end
   - Validation: test covers entry → exit flow

### Performance Benchmarks

| Metric | Target | Measurement |
|--------|--------|-------------|
| Topological sort (50 nodes) | <1s | Time from RPG input to sorted list |
| Test generation (per node) | <5s | Time to generate pytest function |
| Implementation generation | <10s | Time to generate function body |
| Sandbox test execution | <30s | Time to run single test (timeout) |
| Serena symbol lookup | <200ms | Time to find_symbol |
| RPG fuzzy search | <500ms | Time to search 50 nodes |
| Full fixture generation | <30 min | Time to generate 50-function repo |

### Error Injection Testing

Test failure modes:
- **Node with missing dependency**: should be skipped, not failed
- **Test times out**: should be diagnosed as environment issue, not implementation bug
- **Serena MCP connection fails**: should fall back to RPG search
- **Syntax error in generated code**: should be reverted before commit
- **Checkpoint file corrupted**: should fall back to full regeneration

---

## Dependencies and Integration

### Input Dependencies

**From Phase 3** (RPG Construction):
- `rpg.json`: Completed RPG with nodes, edges, hierarchies, docstrings
  - Schema: `{nodes: [{id, name, type, docstring, file_path, dependencies}], edges: [{source, target, type}]}`
  - Required fields per node: `id`, `name`, `docstring`, `file_path`, `node_type` (leaf/composite)
  - Must pass validation: no cycles, all dependencies resolved, all leaf nodes have docstrings

**From Phase 1** (NL Spec):
- `nl_spec.md`: Original natural language specification
  - Used for: README.md generation, project metadata (name, description, author)

### Output Artifacts

**Primary Output**:
- Working Python repository with structure:
  ```
  generated_repo/
  ├── src/
  │   ├── __init__.py
  │   ├── module1.py
  │   ├── module2.py
  │   └── subpackage/
  │       ├── __init__.py
  │       └── module3.py
  ├── tests/
  │   ├── test_module1.py
  │   ├── test_module2.py
  │   └── test_module3.py
  ├── docs/
  │   ├── rpg.json (inspectable artifact)
  │   └── generation_report.md
  ├── README.md
  ├── requirements.txt
  ├── requirements-dev.txt
  ├── setup.py (or pyproject.toml)
  ├── pytest.ini
  └── .gitignore
  ```

**Secondary Outputs**:
- `docs/generation_checkpoint.json`: Node-by-node generation state
- `docs/generation_report.md`: Coverage, failures, statistics
- `test_results.xml`: JUnit XML for CI integration

**Validation Outputs** (for Phase 5):
- Repository builds: `pip install -e .` succeeds
- Tests run: `pytest tests/` executes (even if some fail)
- 60%+ test pass rate
- All planned dependencies exist in code (validated by Serena)

### Integration with Phase 5 (Repository Validation)

Phase 5 will:
- Run static analysis (mypy, pylint) on generated code
- Execute full test suite with coverage analysis
- Validate documentation completeness
- Check for security vulnerabilities
- Generate final quality report

Phase 4 must ensure:
- All Python files are syntactically valid
- All imports are resolvable
- Repository structure follows conventions
- Tests are executable (even if some fail)

### External Tool Dependencies

| Tool | Purpose | Fallback |
|------|---------|----------|
| Docker | Sandbox test execution | Local venv (less isolation) |
| Serena MCP | LSP-powered localization/editing | RPG fuzzy search + AST editing |
| pytest | Test execution framework | unittest (less features) |
| sentence-transformers | Embedding for fuzzy search | TF-IDF similarity (faster, less accurate) |
| Git | Version control | Optional, skip if not available |

---

## Risk Analysis and Mitigation

### High-Risk Areas

1. **Debugging Loop Divergence**
   - **Risk**: Infinite debugging loop, wasting tokens/time
   - **Mitigation**: Hard limit of 8 iterations, escalate to human review
   - **Detection**: Track iteration count per node, log when limit reached

2. **Serena MCP Connection Failures**
   - **Risk**: All Serena calls fail, fall back to slower RPG search
   - **Mitigation**: Graceful degradation, cache Serena responses, retry once
   - **Detection**: Monitor Serena error rate, alert if >20%

3. **Test Flakiness**
   - **Risk**: Random failures due to timing, network, environment
   - **Mitigation**: Majority-vote diagnosis (5 rounds), classify as environment issue
   - **Detection**: If same test fails 3 times then passes, flag as flaky

4. **Memory Explosion on Large Repos**
   - **Risk**: Buffering all code in memory before write causes OOM
   - **Mitigation**: Batched writes (every 5 nodes), flush to disk regularly
   - **Detection**: Monitor memory usage, trigger early flush if >80%

5. **Topological Sort Ambiguity**
   - **Risk**: Multiple valid orders, non-deterministic results
   - **Mitigation**: Tie-break by node ID (deterministic), log chosen order
   - **Detection**: Hash final repository, compare across runs

### Medium-Risk Areas

1. **Generated Code Quality**
   - **Risk**: Code passes tests but is unreadable/unmaintainable
   - **Mitigation**: Use LLM with code quality instructions, validate in Phase 5
   - **Detection**: Manual code review of samples

2. **Import Resolution Failures**
   - **Risk**: Generated imports don't match actual file structure
   - **Mitigation**: Validate imports by AST parsing, auto-correct if possible
   - **Detection**: Syntax errors during test execution

3. **Integration Test Coverage Gaps**
   - **Risk**: Integration tests don't cover all data flow paths
   - **Mitigation**: Generate from RPG edges (explicit dependencies)
   - **Detection**: Coverage analysis in Phase 5

### Mitigation Strategies

| Risk | Strategy | Owner | Timeline |
|------|----------|-------|----------|
| Debugging divergence | Hard iteration limit | Epic 4.2 | Phase 4 start |
| Serena failures | Fallback to RPG search | Epic 4.4 | Phase 4 start |
| Test flakiness | Majority-vote diagnosis | Epic 4.5 | Phase 4 mid |
| Memory explosion | Batched writes | Epic 4.7 | Phase 4 start |
| Non-determinism | Deterministic tie-breaking | Epic 4.1 | Phase 4 start |

---

## Milestones and Timeline

### Phase 4 Epic Breakdown

| Epic | Estimated Effort | Dependencies | Deliverable |
|------|------------------|--------------|-------------|
| 4.1: Topological Traversal | 3 days | Phase 3 complete | Sorted node list, checkpoint system |
| 4.2: TDD Loop | 5 days | Epic 4.1 | Test generation, implementation, sandbox execution |
| 4.3: Graph-Guided Localization | 4 days | Epic 4.2 | Fuzzy search, code view, dependency explorer |
| 4.4: Serena Integration | 4 days | Epic 4.3 | LSP tools, surgical editing |
| 4.5: Staged Testing | 4 days | Epic 4.2, 4.4 | Unit/regression/integration tests |
| 4.6: Repository Assembly | 3 days | Epic 4.5 | README, requirements, setup.py |
| 4.7: Workspace Management | 3 days | Epic 4.6 | Batched writes, git integration |

**Total Estimated Effort**: 26 days (5.2 weeks)

### Critical Path

```
Epic 4.1 (3d) → Epic 4.2 (5d) → Epic 4.3 (4d) → Epic 4.4 (4d) → Epic 4.5 (4d) → Epic 4.6 (3d) → Epic 4.7 (3d)
```

All epics are sequential (each depends on previous).

### Milestone Schedule

| Milestone | Date | Criteria |
|-----------|------|----------|
| M1: Topological Sort Working | Day 3 | Can traverse 50-node RPG in order |
| M2: TDD Loop Functional | Day 8 | Single node generates test + impl + validates |
| M3: Localization Integrated | Day 12 | Debugging loop uses RPG search successfully |
| M4: Serena Operational | Day 16 | Serena finds symbols, applies edits |
| M5: Testing Framework Complete | Day 20 | Unit/integration tests run |
| M6: Repository Assembly | Day 23 | Generates valid Python package |
| M7: Phase 4 Complete | Day 26 | Master fixture generates 60%+ passing repo |

---

## Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Test pass rate (first try) | ≥60% | Count passing tests / total tests |
| Debugging success rate | ≥80% | Nodes passing after debug / nodes entering debug |
| Serena localization speed | <200ms | Median time for find_symbol |
| RPG fuzzy search speed | <500ms | Median time for top-5 search |
| Repository build success | 100% | `pip install -e .` exit code |
| Generation completion time | <30 min | Wall time for 50-function fixture |
| Dependency validation | ≥80% | Serena-confirmed deps / planned deps |

### Qualitative Metrics

| Metric | Target | Validation Method |
|--------|--------|------------------|
| Code readability | "Good" | Manual review of 10 random functions |
| Test coverage completeness | "Comprehensive" | Check edge cases, error cases covered |
| Repository structure | "Conventional" | Follows Python packaging best practices |
| Documentation quality | "Clear" | README usable by new developer |

### Phase 4 Exit Criteria

Phase 4 is complete when:
1. ✅ Master fixture (50 functions) generates successfully
2. ✅ At least 60% of generated tests pass
3. ✅ Repository builds: `pip install -e .` succeeds
4. ✅ Serena validates 80%+ of planned dependencies exist
5. ✅ All 7 epics have passing unit tests
6. ✅ Functional tests pass for each epic
7. ✅ Generation completes in <30 minutes
8. ✅ Coverage report generated with breakdown

---

## Open Questions and Future Work

### Open Questions (to be resolved in Phase 4)

1. **Optimal Batch Size for File Writes**
   - Current: 5 nodes per batch
   - Question: Does larger batch (10 nodes) reduce Serena re-index overhead?
   - Resolution: Benchmark 5 vs 10 vs 20, choose optimal

2. **Majority-Vote Round Count**
   - Current: 5 rounds for diagnosis
   - Question: Is 3 rounds sufficient? Does 7 improve accuracy?
   - Resolution: A/B test with flaky test corpus

3. **Serena vs RPG Search Trade-Off**
   - Current: Try Serena first, fall back to RPG
   - Question: When should we skip Serena (too slow, too inaccurate)?
   - Resolution: Track Serena success rate, auto-adjust strategy

4. **Integration Test Generation Strategy**
   - Current: Generate from RPG subgraph structure
   - Question: Should we use data flow analysis instead?
   - Resolution: Prototype both, compare coverage

### Future Enhancements (post-Phase 4)

1. **Multi-Language Support**
   - Extend beyond Python to JavaScript, Java, Rust
   - Requires language-specific test frameworks, LSP servers
   - Target: Phase 7 (post-MVP)

2. **Parallel Node Generation**
   - Current: Sequential topological order
   - Enhancement: Process independent subgraphs in parallel
   - Benefit: 2-3x speedup on multi-core machines

3. **LLM Model Selection per Node**
   - Use GPT-4 for complex nodes, GPT-3.5 for simple ones
   - Cost optimization: reduce token usage by 40%
   - Target: Phase 5 (cost optimization)

4. **Incremental Regeneration**
   - User edits NL spec, only regenerate affected nodes
   - Requires diffing RPGs, dependency impact analysis
   - Target: Phase 6 (iterative refinement)

5. **Human-in-the-Loop Debugging**
   - When debugging fails after 8 iterations, prompt user for fix
   - Requires UI for presenting debugging context
   - Target: Phase 8 (production readiness)

---

## Appendix

### A. RPG JSON Schema (Input)

```json
{
  "nodes": [
    {
      "id": "node_001",
      "name": "calculate_mean",
      "type": "function",
      "node_type": "leaf",
      "file_path": "src/stats/descriptive.py",
      "docstring": "Calculate arithmetic mean of numbers.\n\nArgs:\n    numbers: List of floats\nReturns:\n    float: Mean value\nRaises:\n    ValueError: If list is empty",
      "dependencies": ["node_002"],
      "subgraph_id": "stats"
    }
  ],
  "edges": [
    {
      "source": "node_001",
      "target": "node_002",
      "type": "function_call"
    }
  ],
  "metadata": {
    "phase": 3,
    "timestamp": "2026-02-07T10:30:00Z",
    "nl_spec_path": "docs/nl_spec.md"
  }
}
```

### B. Checkpoint File Schema

```json
{
  "node_001": {
    "status": "passed",
    "timestamp": "2026-02-07T10:35:12Z",
    "test_results": {
      "passed": 3,
      "failed": 0
    },
    "retry_count": 0
  },
  "node_002": {
    "status": "failed",
    "timestamp": "2026-02-07T10:40:45Z",
    "test_results": {
      "passed": 2,
      "failed": 1
    },
    "retry_count": 8,
    "failure_reason": "AssertionError: expected 5.0, got nan (after 8 debug iterations)"
  }
}
```

### C. Generation Report Template

```markdown
# Code Generation Report

**Generated**: 2026-02-07 10:45:30
**Phase**: 4 (Graph-Guided Code Generation)
**RPG Input**: docs/rpg.json
**Repository Output**: generated_repo/

## Summary

- **Total Nodes Planned**: 50
- **Nodes Passed**: 35 (70%)
- **Nodes Failed**: 10 (20%)
- **Nodes Skipped**: 5 (10%)

## Breakdown by Subgraph

| Subgraph | Nodes | Passed | Failed | Skipped | Pass Rate |
|----------|-------|--------|--------|---------|-----------|
| data_loading | 10 | 9 | 1 | 0 | 90% |
| preprocessing | 12 | 10 | 2 | 0 | 83% |
| model | 15 | 10 | 5 | 0 | 67% |
| evaluation | 8 | 6 | 2 | 0 | 75% |
| visualization | 5 | 0 | 0 | 5 | N/A (skipped) |

## Failed Nodes (detail)

### node_023: train_model
- **Failure Reason**: AssertionError in test_train_model_convergence
- **Debug Iterations**: 8
- **Root Cause**: Off-by-one error in epoch counting
- **Recommendation**: Manual review of training loop logic

### node_034: plot_confusion_matrix
- **Failure Reason**: ImportError: matplotlib not in requirements
- **Debug Iterations**: 1
- **Root Cause**: Missing dependency detection
- **Recommendation**: Add matplotlib to requirements.txt

## Test Results

- **Unit Tests**: 120 generated, 85 passing (71%)
- **Integration Tests**: 5 generated, 3 passing (60%)
- **Regression Tests**: 12 triggered, 12 passing (100%)

## Performance

- **Generation Time**: 28 minutes 34 seconds
- **Average Time per Node**: 34 seconds
- **Serena Localization Success**: 42/50 (84%)
- **RPG Fuzzy Search Usage**: 8/50 (16%)

## Repository Validation

- ✅ `pip install -e .` succeeds
- ✅ `pytest tests/` runs (85/120 tests pass)
- ✅ All Python files syntactically valid
- ⚠️ 10 nodes failed (see details above)
- ⚠️ 5 nodes skipped (dependency failures)

## Recommendations

1. **Manual Fix Required**: Nodes 023, 034 need human review
2. **Dependency Update**: Add matplotlib, seaborn to requirements.txt
3. **Re-run Generation**: After fixes, re-run from checkpoint (resume mode)
4. **Proceed to Phase 5**: Repository quality sufficient for validation phase
```

### D. Key Algorithms (Pseudocode)

**Majority-Vote Diagnosis**:
```python
def diagnose_test_failure(test_result, rounds=5):
    """Classify test failure as implementation, test, or environment issue."""
    votes = []

    for i in range(rounds):
        prompt = f"""
        Test failed with error: {test_result.error_message}

        Is this:
        A) Implementation bug (code is wrong)
        B) Test issue (test is wrong)
        C) Environment issue (sandbox/dependencies)

        Answer with A, B, or C only.
        """

        response = llm_call(prompt, temperature=0.3 + i*0.1)
        votes.append(response.strip())

    # Majority vote
    vote_counts = Counter(votes)
    winner, count = vote_counts.most_common(1)[0]

    if count >= 3:  # Majority (≥3/5)
        if winner == "A":
            return "implementation_bug"
        elif winner == "B":
            return "test_issue"
        else:
            return "environment_issue"
    else:
        return "unclear"  # No majority, escalate to human
```

### E. Glossary

| Term | Definition |
|------|------------|
| **RPG** | Repository Planning Graph - structured representation of code to generate |
| **Leaf Node** | RPG node representing single function/class (not composite) |
| **Composite Node** | RPG node representing module/package (contains leaf nodes) |
| **Topological Order** | Sequence respecting dependencies (A before B if B depends on A) |
| **TDD Loop** | Test-Driven Development: write test, write code, validate, debug if needed |
| **Graph-Guided Search** | Fuzzy search over RPG node descriptions to find relevant code |
| **Serena** | LSP-powered code analysis tool (via MCP) for exact symbol lookup |
| **Checkpoint** | JSON file tracking generation state (resume capability) |
| **Sandbox** | Isolated Docker container for running tests safely |
| **Majority-Vote** | Running LLM diagnosis multiple times, choosing most common answer |

---

## Document Metadata

**Author**: AI Planning Agent
**Reviewers**: [TBD]
**Approval**: [Pending]
**Next Review Date**: [After Epic 4.1 completion]

**Change Log**:
- 2026-02-07: Initial draft (v1.0)

**Related Documents**:
- PRD-RPG-P1-001: Natural Language Specification Refinement
- PRD-RPG-P2-001: Iterative Plan Refinement
- PRD-RPG-P3-001: Repository Planning Graph Construction
- PRD-RPG-P5-001: Repository Validation (TBD)
- PRD-RPG-P6-001: User Acceptance and Refinement (TBD)

---

*End of PRD-RPG-P4-001*
