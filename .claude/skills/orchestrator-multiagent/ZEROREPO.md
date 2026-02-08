# ZeroRepo: Codebase-Aware Orchestration

ZeroRepo provides a codebase context graph that maps PRD requirements against existing code. It classifies every component as EXISTING (already implemented), MODIFIED (needs changes), or NEW (must be created from scratch). This classification enables orchestrators to generate precise, scoped task descriptions rather than blind decompositions.

---

## Three-Operation Lifecycle

| Operation | Purpose | When to Run | Duration |
|-----------|---------|-------------|----------|
| **init** | Generate baseline graph of current codebase | Once per project (or after major implementation) | ~5s |
| **generate** | Analyze PRD against baseline, produce delta report | Once per PRD during Phase 1 planning | ~2.5 min |
| **update** | Regenerate baseline after implementation completes | End of Phase 2, before next initiative | ~5s |

---

## Operation 1: Initialize Baseline

Generate a structural snapshot of the existing codebase. This baseline serves as the reference point for all delta comparisons.

```bash
# Using wrapper script (recommended)
.claude/skills/orchestrator-multiagent/scripts/zerorepo-init.sh

# Manual command
zerorepo init --project-path . \
  --exclude node_modules,__pycache__,.git,trees,venv,.zerorepo
```

**Arguments**:

| Argument | Default | Description |
|----------|---------|-------------|
| `--project-path` | `.` | Root of the codebase to scan |
| `--exclude` | (none) | Comma-separated directory patterns to skip |
| `--output` | `.zerorepo/baseline.json` | Output path for baseline file |

**Output**: `.zerorepo/baseline.json` -- a JSON graph of modules, classes, functions, and their relationships.

**Standard exclude patterns**: `node_modules,__pycache__,.git,trees,venv,.zerorepo`

**When to re-run**: After completing a major implementation phase. The baseline reflects the codebase at a point in time; stale baselines produce inaccurate delta reports.

---

## Operation 2: Generate Delta Report

Analyze a PRD (or design spec) against the baseline to classify every referenced component.

```bash
# Using wrapper script (recommended)
.claude/skills/orchestrator-multiagent/scripts/zerorepo-generate.sh \
  .taskmaster/docs/prd.md

# Manual command
LITELLM_REQUEST_TIMEOUT=1200 zerorepo generate .taskmaster/docs/prd.md \
  --baseline .zerorepo/baseline.json \
  --model claude-sonnet-4-20250514 \
  --output .zerorepo/output
```

**Arguments**:

| Argument | Default | Description |
|----------|---------|-------------|
| `<spec-file>` | (required) | Path to PRD or design specification |
| `--baseline` | `.zerorepo/baseline.json` | Path to baseline graph |
| `--model` | `claude-sonnet-4-20250514` | LLM model for analysis |
| `--output` | `.zerorepo/output` | Output directory for pipeline artifacts |

**Pipeline stages** (run sequentially):
1. Parse spec into `RepositorySpec`
2. Build `FunctionalityGraph`
3. Convert to `RPGGraph`
4. Enrich with semantic encoders
5. Generate delta report (when baseline provided)

**Primary output**: `.zerorepo/output/05-delta-report.md`

---

## Operation 3: Update Baseline

After completing an implementation phase, regenerate the baseline to reflect new code.

```bash
# Using wrapper script (recommended -- handles backup automatically)
.claude/skills/orchestrator-multiagent/scripts/zerorepo-update.sh

# Manual steps
cp .zerorepo/baseline.json .zerorepo/baseline.prev.json
zerorepo init --project-path . \
  --exclude node_modules,__pycache__,.git,trees,venv,.zerorepo
```

The wrapper script backs up the current baseline to `baseline.prev.json` before regenerating, preserving a rollback point.

---

## Delta Report Interpretation

The delta report (`05-delta-report.md`) classifies each component with one of three statuses:

### Classification Table

| Status | Meaning | Task Implication |
|--------|---------|------------------|
| **EXISTING** | Component already implemented in codebase | Skip -- no task needed. Reference in worker context as "already exists at `<path>`" |
| **MODIFIED** | Component exists but needs changes | Create scoped modification task. Include current file path and specific changes needed |
| **NEW** | Component does not exist in codebase | Create full implementation task. Include suggested module path and interfaces |

### Reading the Report

The delta report contains:
- **Module-level classifications**: Each PRD-referenced module marked as EXISTING/MODIFIED/NEW
- **Change summaries**: For MODIFIED components, a description of what needs to change
- **Suggested interfaces**: For NEW components, proposed structure based on PRD requirements
- **File path mappings**: Existing file locations for EXISTING and MODIFIED components

### Example Delta Excerpt

```markdown
## voice_agent/ [EXISTING]
No changes required. Core voice agent pipeline is fully implemented.

## eddy_validate/ [MODIFIED]
Change: Add multi-form validation handler for new university contact types.
Files: eddy_validate/app.py, eddy_validate/validators.py

## email_service/ [NEW]
Create email notification service for validation results.
Suggested structure: email_service/__init__.py, email_service/sender.py, email_service/templates/
```

---

## Threading Delta Context into Task Master

After generating the delta report, use the classifications to enrich PRD content before parsing with Task Master. This produces better task decompositions because Task Master understands what already exists.

### Workflow

```
1. Generate delta report (Operation 2)
   ↓
2. Read 05-delta-report.md
   ↓
3. Annotate PRD or create enriched design doc
   - Mark EXISTING components: "Already implemented, reference only"
   - Mark MODIFIED components: "Modify existing <path> to add <change>"
   - Mark NEW components: "Create new module at <suggested-path>"
   ↓
4. Parse enriched PRD with Task Master
   task-master parse-prd .taskmaster/docs/prd.md --research --append
   ↓
5. Sync to Beads (standard workflow)
```

### Enriching Worker Task Assignments

Include delta context in TaskCreate descriptions to give workers precise scope:

```python
# Without ZeroRepo (vague scope)
TaskCreate(
    subject="Implement email notifications",
    description="""
    Add email notification support for validation results.
    Files: TBD
    """,
    activeForm="Implementing email notifications"
)

# With ZeroRepo (precise scope)
TaskCreate(
    subject="Implement email notifications",
    description="""
    ## Task: Email notification service [NEW]

    **Delta Status**: NEW -- no existing code for this component.

    **Create**:
    - email_service/__init__.py
    - email_service/sender.py (SMTP integration)
    - email_service/templates/ (Jinja2 templates)

    **Reference** (EXISTING -- do not modify):
    - eddy_validate/app.py (call email_service after validation)

    **Acceptance Criteria**:
    - Sends email on validation completion
    - Uses Jinja2 templates for formatting
    - Configurable SMTP settings via environment variables
    """,
    activeForm="Implementing email notifications"
)
```

---

## Environment Requirements

| Requirement | Value | Notes |
|-------------|-------|-------|
| Python | 3.12+ | ZeroRepo uses modern Python features |
| `LITELLM_REQUEST_TIMEOUT` | `1200` | Must be set for generate operation (LLM calls can take 60-90s per stage) |
| `zerorepo` package | Installed via pip | `pip install -e .` from zerorepo source, or `pip install zerorepo` |
| LLM API key | Set via environment | `ANTHROPIC_API_KEY` for Claude models, or other provider keys |

### Verifying Installation

```bash
python -m zerorepo --version
# Expected: zerorepo X.Y.Z

# If not installed:
# pip install zerorepo
# Or from source: cd trees/rpg-improve && pip install -e .
```

---

## Performance Characteristics

| Operation | Duration | Resource Usage | Notes |
|-----------|----------|----------------|-------|
| `init` | ~5 seconds | CPU-bound (AST parsing) | Scales with codebase size; 3000+ node projects take ~5s |
| `generate` | ~2.5 minutes | LLM API calls (5 stages) | Dominated by LLM latency; set `LITELLM_REQUEST_TIMEOUT=1200` |
| `update` | ~5 seconds | Same as init | Backup adds negligible overhead |
| Delta report parsing | < 1 second | File I/O only | Read and interpret markdown output |

---

## Troubleshooting

### Large Baselines

**Symptom**: Init takes longer than expected or produces very large baseline files.

**Cause**: Scanning directories that should be excluded (node_modules, virtual environments, build artifacts).

**Fix**: Add patterns to the `--exclude` flag:
```bash
zerorepo init --project-path . \
  --exclude node_modules,__pycache__,.git,trees,venv,.zerorepo,dist,build,.next
```

### LLM Timeout During Generate

**Symptom**: Pipeline fails mid-stage with timeout errors.

**Cause**: Default LiteLLM timeout is too short for large specs or complex codebases.

**Fix**: Increase the timeout:
```bash
LITELLM_REQUEST_TIMEOUT=1200 zerorepo generate ...
```

If timeouts persist with very large PRDs, consider splitting the PRD into smaller specifications and running generate on each.

### Naming Mismatch (Low Delta Accuracy)

**Symptom**: Delta report shows most components as NEW even though they clearly exist in the codebase.

**Cause**: The LLM generates abstract module names (e.g., `authentication_module`) that do not match the actual codebase names (e.g., `auth/`). The converter uses exact-match, so mismatches produce 0 EXISTING classifications.

**Known Limitation**: Delta classification accuracy depends on LLM naming alignment with the actual codebase. Expect the following accuracy levels:

| Codebase Convention | Expected Accuracy | Notes |
|--------------------|--------------------|-------|
| Descriptive names (`voice_agent/`, `email_service/`) | High (~80%+) | LLM naturally generates similar names |
| Abbreviated names (`va/`, `es/`) | Low (~20%) | LLM cannot guess abbreviations |
| Mixed conventions | Medium (~50%) | Some matches, some misses |

**Mitigation**: Review the delta report manually. Reclassify obvious mismatches before enriching task descriptions. This manual review typically takes 2-3 minutes and significantly improves task quality.

### Missing Baseline File

**Symptom**: Generate fails with "baseline file not found".

**Fix**: Run init first:
```bash
zerorepo init --project-path . --exclude node_modules,__pycache__,.git,trees,venv,.zerorepo
```

### Output Directory Already Exists

**Symptom**: Generate warns about existing output files.

**Fix**: The pipeline overwrites existing output by default. To preserve previous runs, specify a different output directory:
```bash
zerorepo generate spec.md --output .zerorepo/output-v2
```

---

## Pipeline Runner Script

The wrapper scripts (`zerorepo-init.sh`, `zerorepo-generate.sh`, `zerorepo-update.sh`) all delegate to a centralized Python runner at `.claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py`.

### Why a Python Runner?

The previous inline `python -c "..."` approach was fragile:
- Timeout settings got lost during execution
- String escaping was complex and error-prone
- No diagnostic output for troubleshooting
- Not reusable across operations

The Python runner solves these issues with:
- Belt-and-suspenders timeout setup (environment var + direct monkey-patch)
- Comprehensive diagnostic output (baseline size, prompt estimate, timeout value)
- Proper error handling with specific timeout detection
- Single source of truth for all operations

### Direct Usage

While the shell wrappers are recommended for most use cases, you can call the runner directly for advanced scenarios:

```bash
# Generate with custom timeout and model
python .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py \
  --operation generate \
  --prd /path/to/prd.md \
  --baseline /path/to/baseline.json \
  --output /path/to/output \
  --timeout 1800 \
  --model claude-opus-4-20250514

# Init with custom exclude patterns
python .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py \
  --operation init \
  --project-path /path/to/project \
  --exclude "node_modules,dist,build,.next,venv"

# Update (backup + re-init)
python .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py \
  --operation update \
  --project-path .
```

### Parameters Reference

| Parameter | Operations | Default | Description |
|-----------|-----------|---------|-------------|
| `--operation` | all | `generate` | Operation type: `init`, `generate`, `update` |
| `--prd` | generate | (required) | Path to PRD file |
| `--baseline` | generate | (optional) | Path to baseline JSON |
| `--model` | generate | `claude-sonnet-4-20250514` | LLM model for analysis |
| `--output` | generate | `.zerorepo/output` | Output directory |
| `--skip-enrichment` | generate | `True` | Skip enrichment stage |
| `--timeout` | generate | `1200` | LLM request timeout (seconds) |
| `--project-path` | init, update | `.` | Project root directory |
| `--exclude` | init, update | `node_modules,...` | Comma-separated exclude patterns |

### Timeout Handling

The runner implements a belt-and-suspenders approach to timeout configuration:

1. **Pre-import environment setup**: Sets `LITELLM_REQUEST_TIMEOUT` before importing any modules
2. **Direct monkey-patch**: Also sets `litellm.request_timeout` after import as a fallback
3. **Diagnostic output**: Prints timeout value and baseline size for troubleshooting
4. **Timeout detection**: Catches timeout errors and provides actionable suggestions

This dual approach ensures the timeout propagates correctly even if litellm doesn't read the environment variable properly in certain execution contexts.

### Diagnostic Output

The runner provides comprehensive diagnostic information before executing:

```
=== ZeroRepo Generate ===
PRD file: /path/to/prd.md
Estimated prompt size: ~1,250 tokens
Baseline: /path/to/baseline.json
Baseline node count: 3,037 nodes
Model: claude-sonnet-4-20250514
Output directory: .zerorepo/output
Skip enrichment: True
Timeout: 1200s

[zerorepo-runner] LITELLM_REQUEST_TIMEOUT set to 1200s
[zerorepo-runner] Also set litellm.request_timeout=1200 (fallback)
[zerorepo-runner] Running pipeline (5 stages, ~2-3 minutes)...
```

If a timeout occurs, the runner prints additional diagnosis:

```
[TIMEOUT DIAGNOSIS]
- LITELLM_REQUEST_TIMEOUT was set to: 1200s
- Baseline size: 3037 nodes
- Estimated prompt: ~1,250 tokens

Suggestions:
1. Increase --timeout (try 1800 or 2400)
2. Use a faster model (claude-sonnet-3-5-20241022)
3. Split the PRD into smaller specifications
4. Check API rate limits
```

---

## Integration with Orchestrator Phases

| Phase | ZeroRepo Role |
|-------|---------------|
| **Phase 0: Ideation** | Not used -- focus on design and research |
| **Phase 1: Planning** | Run init + generate. Use delta report to enrich PRD before Task Master parsing |
| **Phase 2: Execution** | Include delta context in worker task assignments (file paths, change summaries) |
| **Phase 3: Validation** | Not directly used -- validation focuses on test results |
| **Post-initiative** | Run update to refresh baseline for next initiative |

---

**Reference Version**: 1.0
**Created**: 2026-02-08
**CLI Source**: `src/zerorepo/cli/` (in trees/rpg-improve worktree)
