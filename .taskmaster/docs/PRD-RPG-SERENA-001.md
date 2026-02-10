# PRD-RPG-SERENA-001: ZeroRepo Serena Integration - Codebase-Aware Planning

**Version**: 1.0
**Date**: 2026-02-07
**Status**: Draft
**Dependencies**: PRD-RPG-P2-001 (Planning), PRD-RPG-P3-001 (Enrichment)
**Design Reference**: [ZEROREPO_SERENA_DESIGN.md](../../docs/ZEROREPO_SERENA_DESIGN.md)

---

## Executive Summary

This PRD defines the integration of Serena MCP (semantic code analysis) into the ZeroRepo pipeline as a first-class tool called during planning and enrichment. Currently, the pipeline runs "blind" -- it generates repository plans from PRDs without knowledge of the existing codebase. This produces naming mismatches, hallucinated signatures, and missed integration points (validated at 7/10 against zenagent2 codebase).

By incorporating Serena as a tool callable during planning, ZeroRepo gains:
1. **Codebase baseline** (`zerorepo init`) - real symbols, structure, and relationships
2. **Delta-aware planning** (`zerorepo generate --baseline`) - plans that build on what exists
3. **Inline validation** - enrichment encoders call Serena to verify signatures match existing code

**Key Deliverables**:
1. `zerorepo init` command that walks a codebase via Serena MCP to produce `baseline.json`
2. `--baseline` parameter for `zerorepo generate` that produces delta RPG graphs
3. Serena-enhanced enrichment encoders that validate against real codebase
4. Integration test validating output against zenagent2 codebase

---

## Background

### The Problem: Pipeline Runs Blind

Sprint 1.5 dramatically improved pipeline quality (13 nodes/8 edges -> 34 nodes/51 edges), but validation against the real zenagent2 codebase revealed a 30% accuracy gap:

| What RPG Said | What Actually Exists | Root Cause |
|---------------|---------------------|------------|
| "PostCheckProcessor" | `WorkHistoryCaseService` | No codebase knowledge |
| "dispatch_work_history_call.py" | `livekit_dispatch.py` | No file structure knowledge |
| Generic WorkflowConfig types | Actual Pydantic models with specific fields | No symbol knowledge |
| Missing Clerk auth middleware | Clerk integration in auth/ directory | No dependency knowledge |
| Missing LiveKit/S3/Redis deps | Real infrastructure in docker-compose | No infrastructure knowledge |

**Root cause**: The pipeline has ZERO access to the existing codebase. Every name, signature, and dependency is inferred from the PRD text alone.

### The Paper's Approach

The ZeroRepo paper builds a 1.5M-feature ontology from 1,126 open-source repos. Our implementation doesn't have this ontology. Instead, we can achieve equivalent (and more targeted) results by walking the specific target codebase with Serena.

### Serena MCP Capabilities

Serena provides semantic code analysis via the Model Context Protocol:

| Tool | Purpose | RPG Mapping |
|------|---------|-------------|
| `activate_project(project_root)` | Point Serena at codebase | Session initialization |
| `list_dir(relative_path, recursive)` | Discover all source directories | MODULE node discovery |
| `get_symbols_overview(relative_path)` | Extract modules, classes, functions | COMPONENT/FEATURE nodes |
| `find_symbol(name_path, depth, include_body)` | Hierarchical symbol tree with signatures | FEATURE nodes with signatures |
| `find_referencing_symbols(symbol)` | Trace call/import relationships | DATA_FLOW/INVOCATION edges |
| `onboarding()` | Project overview and architecture | MODULE-level metadata |
| `search_for_pattern(pattern)` | Find code patterns across codebase | Cross-cutting concerns |

### Why Better Than Manual Code Reading

| Approach | Tokens Consumed | Coverage | Structured? |
|----------|-----------------|----------|-------------|
| Read entire codebase | 500K-2M | 100% but noisy | No |
| Serena symbolic walk | 20K-50K | 95%+ of structure | Yes (symbols, types, relationships) |
| No codebase access | 0 | 0% | N/A |

Serena provides structured, token-efficient access to codebase semantics.

---

## Goals and Non-Goals

### Goals

1. **Build codebase baseline** via `zerorepo init` using Serena MCP tools
2. **Enable delta planning** via `zerorepo generate --baseline` that distinguishes new vs existing vs modified code
3. **Integrate Serena into enrichment** so InterfaceDesignEncoder validates signatures against real code
4. **Validate against zenagent2** achieving 9/10+ accuracy (up from 7/10)
5. **Token-efficient** - baseline building uses <50K tokens of Serena output

### Non-Goals

1. Replacing the LLM-based spec parser (Serena supplements, doesn't replace)
2. Full code generation (Phase 4 scope)
3. Real-time code synchronization (baseline is point-in-time snapshot)
4. Supporting non-Python codebases (Serena/Pyright is Python-focused)
5. Ontology integration (separate initiative)

---

## Detailed Design

### Epic 1: `zerorepo init` - Baseline RPG Builder

**Purpose**: Walk an existing codebase with Serena MCP to produce a complete RPG baseline.

#### Feature 1.1: Serena Session Manager

Create a Serena client that manages MCP tool calls:

```python
class SerenaSession:
    """Manages Serena MCP connection for codebase analysis."""

    async def activate(self, project_root: Path) -> ProjectInfo
    async def list_directory(self, path: str, recursive: bool = False) -> list[FileEntry]
    async def get_symbols(self, path: str) -> list[SymbolInfo]
    async def find_symbol(self, name_path: str, depth: int = 2) -> list[SymbolDetail]
    async def find_references(self, symbol: str) -> list[ReferenceInfo]
    async def search_pattern(self, pattern: str) -> list[SearchResult]
```

**Acceptance Criteria**:
- [ ] SerenaSession connects to Serena MCP server
- [ ] All 6 core Serena tools are wrapped with proper error handling
- [ ] Connection failures produce clear error messages
- [ ] Session can be used as async context manager

#### Feature 1.2: Codebase Walker

Walk the entire codebase systematically and extract structure:

**Algorithm**:
1. `activate_project(project_root)` - Initialize Serena
2. `list_dir("/", recursive=True)` - Discover all Python source directories
3. For each package directory:
   - `get_symbols_overview(dir)` - Get modules, classes, functions
   - Create MODULE node for package, COMPONENT nodes for modules, FEATURE nodes for classes/functions
4. For each class/function:
   - `find_symbol(name, depth=1, include_body=False)` - Get signature and docstring
   - Populate FEATURE node metadata: signature, docstring, file_path, interface_type
5. For each non-trivial function/class:
   - `find_referencing_symbols(symbol)` - Trace who calls/imports this
   - Create DATA_FLOW and INVOCATION edges

**Acceptance Criteria**:
- [ ] Walker produces MODULE nodes for each Python package
- [ ] Walker produces COMPONENT nodes for each module file
- [ ] Walker produces FEATURE nodes for classes and top-level functions
- [ ] All FEATURE nodes have: file_path, signature, docstring (where available)
- [ ] HIERARCHY edges connect MODULE -> COMPONENT -> FEATURE
- [ ] INVOCATION edges created from find_referencing_symbols results
- [ ] All nodes marked `serena_validated: true`

#### Feature 1.3: Baseline Persistence

Save and load baseline RPG:

- Output format: `.zerorepo/baseline.json` (standard RPGGraph JSON)
- Include metadata: `baseline_generated_at`, `project_root`, `serena_version`
- Support incremental updates: `zerorepo init --update` re-walks changed files only

**Acceptance Criteria**:
- [ ] `zerorepo init --project-path /path` produces `.zerorepo/baseline.json`
- [ ] Baseline JSON is valid RPGGraph format (loadable by `RPGGraph.from_json()`)
- [ ] Metadata includes generation timestamp and project root
- [ ] Re-running init overwrites cleanly

#### Feature 1.4: CLI Integration

New CLI command:

```bash
zerorepo init --project-path /path/to/project [--output baseline.json] [--exclude "tests/*,docs/*"]
```

**Acceptance Criteria**:
- [ ] `zerorepo init --project-path` works from CLI
- [ ] `--exclude` pattern filters out test/doc directories
- [ ] `--output` overrides default `.zerorepo/baseline.json` path
- [ ] Progress output shows: directories scanned, symbols extracted, edges created
- [ ] Error handling for: non-existent path, no Python files, Serena unavailable

---

### Epic 2: Delta-Aware Planning (`--baseline` parameter)

**Purpose**: When generating from a PRD + baseline, produce a delta RPG that distinguishes new, existing, and modified code.

#### Feature 2.1: Baseline Loading in Generate Pipeline

Modify `zerorepo generate` to accept `--baseline`:

```bash
zerorepo generate spec.md --baseline .zerorepo/baseline.json -o output/
```

**Pipeline changes**:
1. Load baseline RPG before spec parsing
2. Pass baseline to spec parser (so LLM knows what already exists)
3. Pass baseline to graph construction (merge vs create)
4. Pass baseline to enrichment (validate against existing)

**Acceptance Criteria**:
- [ ] `--baseline` parameter accepted by `zerorepo generate`
- [ ] Baseline RPG loaded and validated before pipeline starts
- [ ] All pipeline stages receive baseline reference
- [ ] Without `--baseline`, pipeline behaves identically to current

#### Feature 2.2: Baseline-Aware Spec Parsing

Enhance the spec parser Jinja2 template to include codebase context:

```jinja2
{% if baseline %}
## Existing Codebase Structure
The following modules, components, and features ALREADY EXIST in the codebase:

{% for module in baseline.modules %}
### {{ module.name }} ({{ module.folder_path }})
{% for component in module.components %}
- {{ component.name }}: {{ component.signature }}
{% endfor %}
{% endfor %}

When extracting components from the PRD, indicate:
- EXISTING: Component that already exists (reference by name)
- NEW: Component that must be created
- MODIFIED: Existing component that needs changes
{% endif %}
```

**Acceptance Criteria**:
- [ ] Spec parser includes baseline summary when `--baseline` provided
- [ ] Parsed spec includes `status` field per component: NEW, EXISTING, MODIFIED
- [ ] Existing component references use actual names from baseline (not invented names)
- [ ] Parser correctly identifies overlap between PRD requirements and baseline capabilities

#### Feature 2.3: Delta Graph Construction

Modify `build_from_spec()` to produce delta graphs:

- **EXISTING nodes**: Copied from baseline with `delta_status: "existing"`
- **NEW nodes**: Created from spec with `delta_status: "new"`
- **MODIFIED nodes**: Baseline node + spec changes with `delta_status: "modified"`
- **Delta edges**: New relationships between existing and new nodes

```python
class DeltaStatus(str, Enum):
    NEW = "new"           # Doesn't exist in baseline
    EXISTING = "existing" # Already in baseline, unchanged
    MODIFIED = "modified" # In baseline but needs changes
```

**Acceptance Criteria**:
- [ ] Every node has `delta_status` metadata field
- [ ] Existing nodes preserve baseline signatures and file paths
- [ ] New nodes get fresh signatures from enrichment
- [ ] Modified nodes clearly indicate what changes are needed
- [ ] Implementation ordering respects: existing (skip) -> modified (update) -> new (create)

#### Feature 2.4: Delta Report

Enhanced pipeline report showing delta summary:

```markdown
## Delta Summary
- Existing (unchanged): 45 nodes
- Modified: 8 nodes
- New: 14 nodes
- New edges: 12

## Implementation Order (new + modified only)
1. [NEW] WorkHistoryCaseService.create_case() -> depends on [EXISTING] SupabaseClient
2. [MODIFIED] dispatch_handler() -> add work_history routing
3. [NEW] VerificationResultProcessor -> depends on [NEW] WorkHistoryCaseService
```

**Acceptance Criteria**:
- [ ] Report includes delta breakdown (existing/modified/new counts)
- [ ] Implementation order only includes new and modified nodes
- [ ] Dependencies on existing nodes are clearly marked
- [ ] Report is human-readable and actionable

---

### Epic 3: Serena-Enhanced Enrichment

**Purpose**: Enrichment encoders call Serena during processing to validate and improve output quality.

#### Feature 3.1: InterfaceDesignEncoder with Serena Validation

When baseline is available, InterfaceDesignEncoder:
1. Checks if a similar function exists in baseline
2. If yes: uses the REAL signature from baseline (not LLM-generated)
3. If no: generates signature but uses baseline patterns (naming conventions, type patterns)

```python
class InterfaceDesignEncoder(BaseEncoder):
    def encode(self, graph: RPGGraph, spec: RepositorySpec | None = None,
               baseline: RPGGraph | None = None) -> RPGGraph:
        for node in graph.get_features():
            if baseline:
                existing = baseline.find_similar_node(node.name)
                if existing and existing.signature:
                    node.signature = existing.signature  # Use REAL signature
                    node.serena_validated = True
                    continue
            # Fall through to LLM generation for new nodes
            node.signature = self._generate_with_context(node, spec, baseline)
```

**Acceptance Criteria**:
- [ ] Existing features get real signatures from baseline
- [ ] New features get LLM-generated signatures informed by baseline patterns
- [ ] `serena_validated` flag set True for baseline-derived signatures
- [ ] Signature quality improves when baseline available (measured by zenagent2 comparison)

#### Feature 3.2: DataFlowEncoder with Real Dependencies

DataFlowEncoder uses baseline INVOCATION edges to create accurate DATA_FLOW edges:

- Baseline knows who calls whom (from `find_referencing_symbols`)
- New nodes' data flows are inferred by matching against baseline patterns
- Real data types from baseline replace generic types

**Acceptance Criteria**:
- [ ] DATA_FLOW edges between existing nodes use baseline relationships
- [ ] Data type annotations reference real Pydantic models from baseline
- [ ] New-to-existing edges correctly identify integration points
- [ ] Edge count increases when baseline available (more connections discovered)

#### Feature 3.3: FolderEncoder with Real File Structure

FolderEncoder uses baseline file_path values to place new code in correct locations:

- Existing modules have known folder_path and file_path
- New modules placed following baseline's directory conventions
- New features in existing modules get the module's actual path

**Acceptance Criteria**:
- [ ] Existing nodes retain their real file paths from baseline
- [ ] New nodes placed following existing directory conventions
- [ ] No path conflicts between new and existing files
- [ ] Folder structure matches actual project layout

---

### Epic 4: Validation and Quality Measurement

**Purpose**: Measure improvement from Serena integration against zenagent2 codebase.

#### Feature 4.1: zenagent2 Baseline Test

Create an integration test that:
1. Runs `zerorepo init --project-path /path/to/zenagent2`
2. Runs `zerorepo generate test-spec.md --baseline .zerorepo/baseline.json`
3. Compares output against known-good zenagent2 structure
4. Scores accuracy on: naming, signatures, file paths, dependencies

**Scoring Rubric**:
| Dimension | Weight | How Measured |
|-----------|--------|--------------|
| Name accuracy | 25% | Do feature names match real class/function names? |
| Signature accuracy | 25% | Do signatures match real Python signatures? |
| File path accuracy | 20% | Are files placed in correct directories? |
| Dependency accuracy | 20% | Are inter-module dependencies correct? |
| Missing components | 10% | Are all major components represented? |

**Target**: 9/10 overall score (up from 7/10 without baseline)

**Acceptance Criteria**:
- [ ] Integration test runnable with `pytest tests/integration/test_serena_baseline.py`
- [ ] Test produces quantitative score across all 5 dimensions
- [ ] Score >= 9.0/10 with baseline vs 7.0/10 without
- [ ] Test documents specific improvements over non-baseline run

#### Feature 4.2: Regression Test Suite

Ensure Serena integration doesn't break existing pipeline:

- All existing 3,885+ unit tests continue to pass
- Pipeline without `--baseline` produces identical output to current
- New tests cover: init command, baseline loading, delta graph, enrichment with baseline

**Acceptance Criteria**:
- [ ] All existing tests pass without modification
- [ ] 50+ new tests covering Serena integration features
- [ ] `zerorepo generate` without `--baseline` produces identical output
- [ ] CI-compatible (tests can run without Serena by using baseline fixtures)

---

## Technical Constraints

### MUST HAVE
1. Serena MCP must be available for `zerorepo init` (not for `generate --baseline`)
2. Baseline JSON must be standard RPGGraph format
3. All existing tests must pass unchanged
4. Pipeline without `--baseline` must be identical to current behavior
5. Real LLM calls (not mocked) for integration tests

### SHOULD HAVE
1. Baseline building should complete in <2 minutes for medium projects
2. Token usage for init should be <50K tokens
3. Delta report should be human-readable by developers
4. Incremental baseline updates via `--update` flag

### NICE TO HAVE
1. Support for TypeScript codebases (when Serena gains TS support)
2. Visual diff between baseline and delta RPG
3. Automatic baseline refresh on file change detection

---

## Implementation Phases

### Sprint 1: Serena Session + Init Command (Epic 1)
- Features 1.1-1.4
- Deliverable: `zerorepo init` produces baseline.json from real codebase
- Test: Run against zerorepo's own codebase as dogfooding

### Sprint 2: Delta Pipeline (Epic 2)
- Features 2.1-2.4
- Deliverable: `zerorepo generate --baseline` produces delta RPG
- Test: Compare delta output against non-baseline output

### Sprint 3: Enhanced Enrichment (Epic 3)
- Features 3.1-3.3
- Deliverable: Enrichment encoders use baseline for validation
- Test: Signature accuracy improves with baseline

### Sprint 4: Validation (Epic 4)
- Features 4.1-4.2
- Deliverable: zenagent2 integration test scoring 9/10+
- Test: Full regression suite passes

---

## Success Metrics

| Metric | Current (no baseline) | Target (with baseline) |
|--------|----------------------|------------------------|
| Name accuracy vs real codebase | 70% | 95%+ |
| Signature accuracy | 60% | 90%+ |
| File path accuracy | 50% | 95%+ |
| Dependency accuracy | 40% | 85%+ |
| Missing components | 20% | 5%- |
| Overall score | 7.0/10 | 9.0/10+ |
| Baseline build time | N/A | <2 min |
| Serena token usage | N/A | <50K |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Serena MCP unavailable at runtime | Init fails | Graceful fallback: generate works without baseline |
| Large codebases slow baseline build | >5 min init | Exclude patterns, depth limits, incremental updates |
| Baseline stale after code changes | Wrong signatures | Timestamp check, `--update` flag, warning on age |
| Pyright analysis failures | Missing symbols | Error-tolerant walker, skip un-parseable files |
| LiteLLM + Serena token budget conflict | Cost overrun | Separate token tracking for Serena vs LLM calls |

---

## Appendix: Serena MCP Tool Reference

### Core Tools Used

```python
# 1. Project activation (one-time per session)
mcp__serena__activate_project(project_root="/path/to/project")

# 2. Directory discovery
mcp__serena__list_dir(relative_path="/", recursive=True)
# Returns: [{name, type, size, relative_path}]

# 3. Symbol overview (per directory)
mcp__serena__get_symbols_overview(relative_path="src/")
# Returns: [{name, kind, range, children}] - classes, functions, variables

# 4. Detailed symbol lookup
mcp__serena__find_symbol(
    name_path="WorkHistoryCaseService",
    depth=2,             # Include methods
    include_body=False   # Signatures only (token-efficient)
)
# Returns: [{name_path, kind, signature, docstring, relative_path}]

# 5. Reference tracing
mcp__serena__find_referencing_symbols(symbol="WorkHistoryCaseService")
# Returns: [{referencing_symbol, reference_kind, code_snippet}]

# 6. Pattern search (for cross-cutting concerns)
mcp__serena__search_for_pattern(pattern="@router\\.(get|post|put|delete)")
# Returns: [{file, line, content}]
```

### Token Budget Estimation

| Operation | Tokens (approx) | Frequency |
|-----------|-----------------|-----------|
| activate_project | 500 | 1x |
| list_dir (recursive) | 2K-5K | 1x |
| get_symbols_overview (per dir) | 1K-3K | N dirs |
| find_symbol (per symbol) | 500-2K | M symbols |
| find_referencing_symbols | 1K-5K | Top symbols |
| **Total for medium project** | **20K-50K** | - |

---

*PRD-RPG-SERENA-001 v1.0 - ZeroRepo Serena Integration*
