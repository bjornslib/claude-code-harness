# PRD-RPG-E2E-001: ZeroRepo End-to-End Validation Epic

**Version**: 1.0
**Status**: Draft
**Owner**: System 3 (Meta-Orchestrator)
**Created**: 2026-02-07
**Last Updated**: 2026-02-07

---

## Executive Summary

This PRD defines the **End-to-End Validation Epic** for the ZeroRepo project. Unlike implementation epics that are delegated to orchestrators, this epic is **owned and executed by System 3** (the meta-orchestrator). System 3's role is to independently verify that each phase's implementation actually works as intended, looks correct, and meets business outcomes—not just that tests pass.

**Core Principle**: System 3 validates the WHAT (business outcomes), not the HOW (implementation details).

---

## 1. Problem Statement

### 1.1 The Gap Between "Tests Pass" and "Actually Works"

Implementation orchestrators report completion when:
- Unit tests pass
- Integration tests pass
- Code review is complete

However, this doesn't guarantee:
- The system **looks** right (CLI output, visualizations, file structures)
- The system **works** right (functional behavior, edge cases, user experience)
- Business value is actually delivered (usable output, correct semantics, quality results)

### 1.2 System 3's Unique Position

System 3 is the meta-orchestrator that:
- Spawns implementation orchestrators for each phase
- Has context across ALL phases
- Can verify end-to-end behavior
- Can use Claude in Chrome MCP to visually inspect outputs
- Makes the final GO/NO-GO decision for each phase

---

## 2. Goals and Non-Goals

### 2.1 Goals

1. **Independent Verification**: System 3 validates each phase's outputs without relying on orchestrator reports
2. **Visual Quality Assurance**: Use Claude in Chrome to verify CLI output, generated files, and visualizations
3. **Business Outcome Validation**: Confirm that acceptance criteria are ACTUALLY met, not just "tests pass"
4. **Evidence Collection**: Capture screenshots/GIFs of validation for transparency
5. **Go/No-Go Decisions**: System 3 makes the final call on whether a phase is complete

### 2.2 Non-Goals

1. **Not Re-Running All Tests**: Orchestrators already run tests; System 3 spot-checks critical paths
2. **Not Debugging Failures**: If validation fails, System 3 reports back to orchestrator for fixes
3. **Not Implementation**: System 3 never writes code, only validates it

---

## 3. Architecture

### 3.1 Validation Workflow

```
Implementation Orchestrator          System 3 (Meta-Orchestrator)
         │                                    │
         │  "Phase N Complete"                │
         │───────────────────────────────────>│
         │                                    │ Review Implementation
         │                                    │ Run Critical Tests
         │                                    │ Chrome Visual Validation
         │                                    │ Check Acceptance Criteria
         │                                    │
         │                              ┌─────┴─────┐
         │                              │ PASS/FAIL │
         │                              └─────┬─────┘
         │                                    │
         │         PASS: Mark Complete        │ FAIL: Report Issues
         │<───────────────────────────────────┤      + Re-Delegate
```

### 3.2 Tools Used by System 3

| Tool Category | Specific Tools | Purpose |
|---------------|----------------|---------|
| **Chrome MCP** | `mcp__claude-in-chrome__navigate` | Open files/URLs in browser |
| | `mcp__claude-in-chrome__read_page` | Extract rendered content |
| | `mcp__claude-in-chrome__get_page_text` | Analyze text content |
| | `mcp__claude-in-chrome__javascript_tool` | Interact with visualizations |
| | `mcp__claude-in-chrome__gif_creator` | Record validation evidence |
| **File System** | `Read`, `Grep`, `Glob` | Inspect generated artifacts |
| **Testing** | `Bash` (pytest, npm test) | Run critical test suites |
| **Validation** | `validation-test-agent --mode=implementation` | Delegate detailed validation |

---

## 4. Epic Breakdown

### Epic E2E-1: Phase 1 Foundation Validation

**Trigger**: Phase 1 orchestrator reports completion
**Owner**: System 3
**Duration Estimate**: 30 minutes

#### Acceptance Criteria

| Component | Validation Method | Pass Criteria |
|-----------|-------------------|---------------|
| **RPG Data Model** | Python REPL test | Create 10 nodes, 15 edges, serialize/deserialize, topological sort succeeds |
| **LLM Gateway** | API test call | Successful response, logs captured, retry logic verified |
| **Vector DB** | Embed + search test | Embed 5 features, search returns relevant results |
| **Docker Sandbox** | Run pytest in container | Container starts, pytest runs, results captured |
| **Serena MCP** | Query symbol | MCP server starts, responds to query, returns valid JSON |
| **CLI Foundation** | `zerorepo --help` | Help text renders correctly, no errors |
| | `zerorepo init` | Creates `zerorepo.yaml` config file |

#### Chrome Validation Steps

1. **Navigate** to generated `zerorepo.yaml` file in browser/editor
2. **Read page** to verify YAML structure is correct
3. **Navigate** to CLI output log
4. **Get page text** to verify help text formatting
5. **Create GIF** recording full CLI walkthrough
6. **Pass/Fail**: All components functional + visual quality acceptable

---

### Epic E2E-2: Phase 2 Proposal-Level Validation

**Trigger**: Phase 2 orchestrator reports completion
**Owner**: System 3
**Duration Estimate**: 45 minutes

#### Test Specification

**Input**: "Build a machine learning library with data preprocessing, model training, evaluation, and deployment modules"

#### Acceptance Criteria

| Metric | Validation Method | Pass Criteria |
|--------|-------------------|---------------|
| **Functionality Graph** | Run proposal pipeline | Graph JSON exists at expected path |
| **Node Count** | Parse JSON | 20+ features across 3+ modules |
| **Orphan Detection** | Graph analysis | Zero orphan nodes (all connected to root) |
| **Diversity** | Ontology analysis | Features from 3+ ontology branches |
| **Convergence** | Iteration log | Diversity score converges within 5 iterations |
| **Module Structure** | Graph topology | 3-5 top-level modules, 3-7 features per module |

#### Chrome Validation Steps

1. **Navigate** to functionality graph visualization (if HTML output exists)
2. **Read page** to verify visual rendering
3. **Navigate** to exported JSON file
4. **Get page text** to inspect structure
5. **JavaScript tool** to interact with graph (zoom, pan, highlight)
6. **Create GIF** showing graph exploration
7. **Pass/Fail**: Graph is well-structured, diverse, and visually interpretable

---

### Epic E2E-3: Phase 3 Implementation-Level Validation

**Trigger**: Phase 3 orchestrator reports completion
**Owner**: System 3
**Duration Estimate**: 60 minutes

#### Test Input

Use the functionality graph from Epic E2E-2 as input to RPG enrichment.

#### Acceptance Criteria

| Component | Validation Method | Pass Criteria |
|-----------|-------------------|---------------|
| **RPG Enrichment** | Run enrichment pipeline | All leaf nodes have required fields |
| **File Path Assignment** | Parse RPG JSON | 100% of leaf nodes have `file_path` |
| **Interface Types** | Validate types | All interfaces in {function, class, module, enum, protocol} |
| **Signatures** | Validate signatures | All functions have type-annotated signatures |
| **Docstrings** | Validate docstrings | All public interfaces have docstrings |
| **Data Flow DAG** | Cycle detection | Zero cycles in data flow graph |
| **Base Classes** | Abstraction analysis | At least one base class per module |
| **Serialization** | Round-trip test | RPG.serialize() → RPG.deserialize() → identical structure |

#### Chrome Validation Steps

1. **Navigate** to exported RPG JSON file (likely 1000+ lines)
2. **Get page text** to extract structure
3. **JavaScript tool** to collapse/expand sections
4. **Verify** random sample of 10 nodes have all required fields
5. **Navigate** to data flow visualization (if exists)
6. **Create GIF** showing RPG structure walkthrough
7. **Pass/Fail**: RPG is complete, cycle-free, and semantically correct

---

### Epic E2E-4: Phase 4 Code Generation Validation

**Trigger**: Phase 4 orchestrator reports completion
**Owner**: System 3
**Duration Estimate**: 90 minutes

#### Test Input

Use a **small RPG fixture**:
- 5 modules
- 15 files
- ~50 functions
- Pre-validated structure from Epic E2E-3

#### Acceptance Criteria

| Stage | Validation Method | Pass Criteria |
|-------|-------------------|---------------|
| **Repository Structure** | File system inspection | Generated repo matches RPG structure |
| **File Count** | `find` command | 15 Python files + setup.py + README + tests |
| **Installability** | `pip install -e .` | Installation succeeds, no errors |
| **Import Validity** | Python REPL | `import <package>` succeeds for all modules |
| **Test Suite** | `pytest` | At least 60% pass rate |
| **Serena Validation** | Serena dependency check | 80%+ of planned dependencies confirmed |
| **Code Quality** | Manual inspection | Key files have docstrings, type hints, clean structure |

#### Chrome Validation Steps

1. **Navigate** to generated repository root in file browser
2. **Read page** to see directory structure
3. **Navigate** to 3-5 key files (e.g., `__init__.py`, core module, base class)
4. **Get page text** to inspect code quality
5. **Verify** imports, docstrings, type hints are present
6. **Navigate** to test output HTML report
7. **Create GIF** showing repository walkthrough
8. **Pass/Fail**: Repository is installable, testable, and well-structured

---

### Epic E2E-5: Phase 5 Evaluation Validation

**Trigger**: Phase 5 orchestrator reports completion
**Owner**: System 3
**Duration Estimate**: 60 minutes

#### Test Input

Use the generated repository from Epic E2E-4 as input to evaluation.

#### Acceptance Criteria

| Component | Validation Method | Pass Criteria |
|-----------|-------------------|---------------|
| **RepoCraft Benchmark** | Inspect benchmark dataset | 500+ tasks across multiple difficulty levels |
| **Evaluation Run** | Run evaluation pipeline | Completes without errors |
| **Metrics Computed** | Parse evaluation report | Coverage, pass rate, voting rate, LOC all present |
| **Failure Analysis** | Inspect failure report | Categorized failure types (syntax, import, logic, timeout) |
| **Comparative Baseline** | Compare to reference | Within 20% of reference implementation metrics |

#### Chrome Validation Steps

1. **Navigate** to evaluation report HTML
2. **Read page** to extract metrics
3. **Verify** all metrics are reasonable (not 0%, not 100%)
4. **Navigate** to failure analysis section
5. **Get page text** to inspect categorized failures
6. **Navigate** to benchmark task samples
7. **Create GIF** showing report walkthrough
8. **Pass/Fail**: Evaluation is thorough, metrics are believable, failures are analyzed

---

### Epic E2E-6: Full Pipeline Integration Test

**Trigger**: All previous epics (E2E-1 through E2E-5) pass
**Owner**: System 3
**Duration Estimate**: 2-3 hours

#### Test Specification

**Input**: A **fresh specification** not used during development:

> "Build a data visualization library with:
> - Core plotting engine (line, bar, scatter, heatmap)
> - Layout system (grid, stack, inset)
> - Export formats (PNG, SVG, HTML interactive)
> - Style themes (default, dark, colorblind-safe)
> - Data adapters (pandas, numpy, CSV)"

#### End-to-End Workflow

```
Specification
    ↓
[Phase 2] Proposal Generation
    ↓ (functionality graph)
[Phase 3] RPG Enrichment
    ↓ (implementation-level RPG)
[Phase 4] Code Generation
    ↓ (generated repository)
[Phase 5] Evaluation
    ↓ (metrics + failure analysis)
Final Validation
```

#### Acceptance Criteria

| Stage | Validation | Pass Criteria |
|-------|------------|---------------|
| **Proposal** | Functionality graph | 25+ features, 4-5 modules, diverse ontology coverage |
| **RPG** | Enrichment completeness | 100% leaf nodes enriched, zero cycles |
| **Repository** | Generation quality | Installable, 70%+ tests pass, Serena validates 85%+ deps |
| **Evaluation** | Metrics quality | Coverage >80%, pass rate >70%, voting rate >60% |
| **Installability** | `pip install -e .` | Succeeds on fresh Python 3.11 environment |
| **Usability** | Write sample usage script | Script runs and produces output |

#### Chrome Validation Steps

1. **Navigate** through entire repository structure
2. **Read pages** for 10+ key files
3. **Verify** code quality across all modules
4. **Navigate** to evaluation report
5. **Get metrics** and verify quality thresholds
6. **Navigate** to sample usage script output
7. **Create comprehensive GIF** showing full walkthrough
8. **Pass/Fail**: Entire pipeline produces a usable, high-quality repository

---

## 5. Validation Patterns

### 5.1 Pass/Fail Decision Framework

Each epic validation ends with a **binary decision**:

| Outcome | System 3 Action |
|---------|----------------|
| **PASS** | Mark phase complete in Task Master, proceed to next phase |
| **FAIL** | Document specific failures, send detailed report to orchestrator, re-delegate |

### 5.2 Failure Reporting Format

When validation fails, System 3 creates a structured report:

```markdown
## Validation Failure Report: Epic E2E-{N}

**Phase**: {Phase Name}
**Validation Date**: {ISO timestamp}
**Validator**: System 3

### Failed Criteria

1. **{Criterion Name}**
   - **Expected**: {Expected outcome}
   - **Actual**: {Actual outcome}
   - **Evidence**: {Screenshot/GIF link}
   - **Severity**: Critical | High | Medium | Low

### Recommended Actions

1. {Action 1}
2. {Action 2}

### Re-Validation Trigger

{Specific conditions for re-running validation}
```

### 5.3 Evidence Collection

All validations must produce **visual evidence**:

| Evidence Type | Tool | Storage Location |
|---------------|------|------------------|
| Screenshots | `mcp__claude-in-chrome__navigate` + screenshot | `.claude/validation-evidence/screenshots/` |
| GIF Recordings | `mcp__claude-in-chrome__gif_creator` | `.claude/validation-evidence/gifs/` |
| JSON Artifacts | File system inspection | `.claude/validation-evidence/artifacts/` |
| Logs | CLI output capture | `.claude/validation-evidence/logs/` |

---

## 6. Task Master Integration

### 6.1 Epic Structure

```
Epic E2E-1: Phase 1 Foundation Validation
├── Task E2E-1.1: RPG Data Model Validation
├── Task E2E-1.2: LLM Gateway Validation
├── Task E2E-1.3: Vector DB Validation
├── Task E2E-1.4: Docker Sandbox Validation
├── Task E2E-1.5: Serena MCP Validation
├── Task E2E-1.6: CLI Foundation Validation
└── Task E2E-1.7: Chrome Visual Validation

Epic E2E-2: Phase 2 Proposal-Level Validation
├── Task E2E-2.1: Run Proposal Pipeline
├── Task E2E-2.2: Validate Graph Metrics
├── Task E2E-2.3: Check Diversity Coverage
├── Task E2E-2.4: Verify Convergence
└── Task E2E-2.5: Chrome Visual Validation

... (similarly for E2E-3 through E2E-6)
```

### 6.2 Dependencies

```
E2E-1 → E2E-2 → E2E-3 → E2E-4 → E2E-5 → E2E-6
   ↑       ↑       ↑       ↑       ↑       ↑
Phase 1  Phase 2  Phase 3  Phase 4  Phase 5  All phases
```

Each E2E epic **blocks** the start of the next implementation phase.

---

## 7. Chrome MCP Tool Reference

### 7.1 Tool Usage Patterns

| Task | Tool Sequence | Expected Outcome |
|------|---------------|------------------|
| **Inspect Generated File** | `navigate(file://...)` → `get_page_text()` | File content extracted |
| **Validate CLI Output** | `navigate(log_file)` → `read_page()` | Output formatted correctly |
| **Explore Visualization** | `navigate(html)` → `javascript_tool(interact)` → `gif_creator()` | Interactive demo recorded |
| **Check Directory Structure** | `navigate(file://dir)` → `read_page()` | Directory tree visible |

### 7.2 Deferred Tool Loading

**CRITICAL**: Chrome MCP tools are deferred. System 3 must load them BEFORE first use:

```python
# CORRECT
ToolSearch(query="select:mcp__claude-in-chrome__navigate")
# Now tool is available
mcp__claude-in-chrome__navigate(url="file:///path/to/file")

# WRONG (will fail)
mcp__claude-in-chrome__navigate(url="...")  # Tool not loaded yet
```

---

## 8. Success Metrics

### 8.1 Epic-Level Metrics

| Epic | Key Metric | Target |
|------|------------|--------|
| E2E-1 | Foundation components functional | 100% pass |
| E2E-2 | Proposal quality score | >80% |
| E2E-3 | RPG completeness | 100% leaf nodes enriched |
| E2E-4 | Generated repository quality | 70%+ tests pass |
| E2E-5 | Evaluation coverage | >80% |
| E2E-6 | End-to-end pipeline success | Repository is usable |

### 8.2 System 3 Performance Metrics

| Metric | Target |
|--------|--------|
| **False Positive Rate** (Pass but actually broken) | <5% |
| **False Negative Rate** (Fail but actually works) | <10% |
| **Validation Time** (per epic) | <90 minutes |
| **Evidence Completeness** (GIFs/screenshots) | 100% |

---

## 9. Risk Mitigation

### 9.1 Known Risks

| Risk | Mitigation |
|------|------------|
| **Chrome MCP tool unreliable** | Fall back to manual file inspection + screenshots |
| **System 3 overwhelmed by details** | Focus on acceptance criteria, not implementation |
| **Validation takes too long** | Spot-check critical paths, not exhaustive testing |
| **Orchestrator disputes failure** | Validation evidence (GIFs) is definitive |

### 9.2 Escalation Path

If System 3 cannot resolve a validation failure:
1. Document the issue in `.claude/validation-evidence/blockers/`
2. Alert the user (human) with a structured report
3. Pause the epic until resolution

---

## 10. Appendix

### 10.1 Example Validation Session

**Epic E2E-1, Task E2E-1.6: CLI Foundation Validation**

```bash
# System 3 runs in tmux session "system3-validation"

# Step 1: Navigate to project root
cd /path/to/zerorepo

# Step 2: Run CLI help
zerorepo --help > /tmp/cli-help.txt

# Step 3: Open help output in Chrome
ToolSearch(query="select:mcp__claude-in-chrome__navigate")
mcp__claude-in-chrome__navigate(url="file:///tmp/cli-help.txt")
mcp__claude-in-chrome__get_page_text()

# Expected output:
# "Usage: zerorepo [OPTIONS] COMMAND [ARGS]..."
# "Commands: init, propose, enrich, generate, evaluate"

# Step 4: Run init
zerorepo init

# Step 5: Verify config file
ls -la zerorepo.yaml  # Exists?
mcp__claude-in-chrome__navigate(url="file:///path/to/zerorepo.yaml")
mcp__claude-in-chrome__read_page()

# Expected structure:
# llm_provider: openai
# vector_db: faiss
# ...

# Step 6: Create evidence
mcp__claude-in-chrome__gif_creator(
    steps=["Navigate to help", "Navigate to config"],
    output_path=".claude/validation-evidence/gifs/e2e-1-6-cli.gif"
)

# Result: PASS
```

### 10.2 Chrome MCP Tool Inventory

| Tool Name | Purpose | Typical Usage |
|-----------|---------|---------------|
| `mcp__claude-in-chrome__navigate` | Open URL/file in browser | Inspect files, HTML reports |
| `mcp__claude-in-chrome__read_page` | Extract rendered content | Parse HTML, verify rendering |
| `mcp__claude-in-chrome__get_page_text` | Get text-only content | Analyze logs, configs |
| `mcp__claude-in-chrome__javascript_tool` | Run JS in page | Interact with visualizations |
| `mcp__claude-in-chrome__gif_creator` | Record multi-step flow | Evidence collection |
| `mcp__claude-in-chrome__find` | Search page content | Verify specific text exists |
| `mcp__claude-in-chrome__form_input` | Fill forms | (Less relevant for validation) |

### 10.3 Validation Checklist Template

```markdown
# Validation Checklist: Epic E2E-{N}

**Phase**: {Phase Name}
**Date**: {ISO timestamp}
**Validator**: System 3

## Pre-Validation
- [ ] Implementation orchestrator reported completion
- [ ] All implementation tests passed
- [ ] Chrome MCP tools loaded

## Functional Validation
- [ ] {Criterion 1}: {Expected outcome}
- [ ] {Criterion 2}: {Expected outcome}
- [ ] ...

## Visual Validation (Chrome)
- [ ] {File/output 1} inspected
- [ ] {File/output 2} inspected
- [ ] GIF evidence created

## Decision
- [ ] **PASS**: All criteria met → Mark phase complete
- [ ] **FAIL**: Document failures → Re-delegate to orchestrator

## Evidence
- Screenshots: {links}
- GIFs: {links}
- Artifacts: {links}
```

---

## 11. Conclusion

This PRD defines System 3's role as the **final arbiter** of ZeroRepo phase completion. By combining traditional testing with visual validation via Chrome MCP tools, System 3 ensures that "tests pass" actually means "the system works and looks right."

**Key Takeaways**:
1. System 3 validates WHAT (business outcomes), not HOW (implementation)
2. Visual validation via Chrome MCP is mandatory for quality assurance
3. Evidence collection (GIFs, screenshots) ensures transparency
4. Pass/Fail decisions are binary and block subsequent phases
5. Validation failures are documented and re-delegated to orchestrators

**Next Steps**:
1. System 3 monitors Phase 1 orchestrator for completion signal
2. Upon completion, System 3 invokes Epic E2E-1
3. Process repeats for each phase
4. Final Epic E2E-6 validates the entire pipeline end-to-end

---

**Document Owner**: System 3 (Meta-Orchestrator)
**Review Cycle**: After each phase completion
**Versioning**: Increment on validation workflow changes
