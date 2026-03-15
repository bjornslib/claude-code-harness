# Architecture

Deep technical reference for CoBuilder internals. For an overview and quick start, see [README.md](README.md).

## 3-Layer Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 0: GUARDIAN (User's Terminal)                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Strategic planning, OKR tracking, acceptance tests       │  │
│  │  Writes blind Gherkin tests BEFORE implementation         │  │
│  │  Creates DOT pipelines with research + codergen nodes     │  │
│  │  Launches pipeline_runner.py (pure Python, no LLM)        │  │
│  │  Post-pipeline blind validation (cobuilder-guardian)       │  │
│  │  UUID-based completion promises (multi-session aware)     │  │
│  │                                                            │  │
│  │  Skills: cobuilder-guardian/, completion-promise           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ Launches with --dot-file          │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: PIPELINE RUNNER (Pure Python State Machine)           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Zero LLM intelligence — mechanical state machine         │  │
│  │  Parses DOT files, tracks node states                     │  │
│  │  Dispatches workers via AgentSDK (not subprocess)         │  │
│  │  Watches signal files (atomic writes, timeout detection)  │  │
│  │  Auto-detects dead workers (AdvancedWorkerTracker)        │  │
│  │  Auto-dispatches validation agents at impl_complete       │  │
│  │  Checkpoints pipeline state after each transition         │  │
│  │                                                            │  │
│  │  Entry: cobuilder/engine/pipeline_runner.py               │  │
│  │  Cost: $0 (no LLM tokens for graph traversal)             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ Dispatches via AgentSDK           │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: WORKERS (Standalone AgentSDK Queries)                 │
│  ┌───────────────┬───────────────┬───────────────────────────┐  │
│  │ Frontend Dev  │ Backend Eng   │ TDD Test Engineer        │  │
│  │               │               │ + Validation Agent       │  │
│  │ React/Next    │ Python/API    │ Write tests first        │  │
│  │ Zustand       │ PydanticAI    │ Technical validation     │  │
│  │ Tailwind      │ Supabase      │ Business validation      │  │
│  └───────────────┴───────────────┴───────────────────────────┘  │
│                                                                   │
│  Each worker = standalone claude_code_sdk.query() call           │
│  Workers write signal files; never validate their own work       │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Layer 0 (Guardian)**: LLM-driven strategy, business judgement, independent validation
2. **Layer 1 (Runner)**: Deterministic automation, zero LLM tokens, mechanical transitions
3. **Layer 2 (Workers)**: Focused implementation via standalone `claude_code_sdk.query()`, reporting via signals, never self-grading

**The implementer never validates its own work.**
- Runner detects completion via signals
- Validation agent (Layer 2 peer) provides independent technical/business gating
- Guardian (Layer 0) runs blind Gherkin E2E tests post-pipeline

## Pipeline Runner Internals

### Dispatch Model

```python
async for msg in claude_code_sdk.query(
    prompt=worker_prompt,
    options=ClaudeCodeOptions(
        system_prompt=handler_system_prompt,
        allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        model=resolved_model,
        cwd=target_dir,
        max_turns=50
    )
)
```

Workers are standalone AgentSDK queries. Not Native Agent Teams, not subprocess, not tmux. Each gets handler-specific `allowed_tools` for role isolation:

| Handler | Allowed Tools |
|---------|--------------|
| `codergen` | Bash, Read, Write, Edit, Glob, Grep + Serena |
| `research` | Read, Glob, Grep + Context7, Perplexity, Hindsight, Serena |
| `refine` | Read, Edit, Write + Hindsight, perplexity_reason, Serena |

### Signal Protocol

**Format:**
```json
// Worker completion
{"status": "success"|"failed", "files_changed": [...], "message": "..."}

// Validation result
{"result": "pass"|"fail"|"requeue", "reason": "...", "requeue_target": "node_id"}
```

**Atomic writes:** Signals use temp file → rename to prevent partial writes on crash. Metadata includes `_seq` counter, `_ts` timestamp, and `_pid` for ordering and forensics.

**Corruption handling:** Invalid JSON is moved to `signals/quarantine/` (not silently dropped). The apply-before-consume pattern means signal transitions are written to the DOT file BEFORE the signal moves to `processed/` — a crash between is safe because the signal will be re-applied on restart.

### Status Chain

```
pending
    │
    ├─ Runner dispatches worker via AgentSDK
    ▼
active
    │
    ├─ Wait for signal file OR timeout
    ├─ If signal: read {status, message, files_changed}
    ├─ If timeout: auto-generate fail signal (AdvancedWorkerTracker)
    ├─ If corrupted: quarantine, retry
    ▼
impl_complete (signal: status=success)
    │
    ├─ Check if node already terminal → skip (prevents duplicate validation)
    ├─ Auto-dispatch validation-test-agent
    │  (--mode=technical then --mode=business)
    │
    └─ Wait for validation signal
       ├─ pass    → validated → accepted
       ├─ fail    → blocked (explicit fail signal, never silent auto-pass)
       └─ requeue → predecessor back to pending + guidance file
```

### LLM Profile Resolution

Five-layer resolution (first non-null wins):
1. Node attribute: `llm_profile="anthropic-smart"`
2. Handler defaults in template manifest
3. Template manifest defaults
4. Environment variables
5. Runner defaults

Profiles defined in `cobuilder/engine/providers.yaml`. Supports `$VAR` expansion for credentials (e.g., `api_key: $DASHSCOPE_API_KEY`).

## Node Handler Reference

### research (shape=tab)

Pre-implementation gates that validate framework patterns against current documentation before coding begins.

```
Execution:
    1. Runner reads node attributes (downstream_node, solution_design, research_queries)
    2. Dispatches Haiku agent (~15s, ~$0.02) that:
       a. Reads the current technical spec
       b. Queries Context7 for each framework's current API patterns
       c. Cross-validates with Perplexity
       d. Updates the spec directly with validated patterns
       e. Writes evidence JSON to .pipelines/evidence/{node_id}/
       f. Persists learnings to Hindsight
    3. Downstream codergen node reads the corrected spec naturally
```

**Key insight:** Research updates the spec directly — no side-channel injection. Downstream agents read the corrected spec as their implementation brief.

| Attribute | Required | Purpose |
|-----------|----------|---------|
| `handler` | Yes | `"research"` |
| `shape` | Yes | `tab` |
| `downstream_node` | Yes | ID of the codergen node this feeds |
| `solution_design` | Yes | Path to spec document to validate |
| `research_queries` | Recommended | Comma-separated frameworks (e.g., `"fastapi,pydantic"`) |

### refine (shape=note)

Runs after research to rewrite the spec with findings as first-class content. Uses Sonnet with mandatory Hindsight reflection before editing.

### codergen (shape=box)

Implementation nodes. Dispatches a worker via AgentSDK with scoped context:
- The technical spec is inlined into the system prompt (not passed as a file path)
- Worker type determines specialisation (`backend-solutions-engineer`, `frontend-dev-expert`, etc.)
- Handler-specific `allowed_tools` prevent cross-concern access

### wait.cobuilder (shape=hexagon)

Validation gates. When a predecessor reaches `impl_complete`, the runner auto-dispatches a validation-test-agent with dual-pass validation:
1. **Technical** (tests, build, imports, TODOs)
2. **Business** (acceptance criteria matrix, E2E user flows)

### wait.human (shape=octagon)

Human approval gates. Pipeline pauses and emits a notification (GChat webhook). Resumes when a human writes a response signal file.

### manager_loop (shape=house)

Recursive sub-pipeline nodes. Spawns a child `pipeline_runner.py` process for a nested DOT graph. Supports gate detection — if the child pipeline hits a `wait.cobuilder` or `wait.human` gate, the parent runner is notified.

## Pipeline Runner Hardening

The runner was hardened across 7 epics to survive crashes without human intervention:

| Epic | Problem Solved | Mechanism |
|------|---------------|-----------|
| **H** | Workers die silently, runner waits forever | `AdvancedWorkerTracker`: WorkerState enum, `_check_worker_liveness()` in main loop, 900s default timeout → auto-kill + fail signal |
| **A** | Partial JSON writes corrupt signals | Temp+rename atomic writes, `_seq` counter, quarantine directory, apply-before-consume ordering |
| **B** | `_force_status()` lost on restart | Now calls `_do_transition()` (disk write), requeue guidance persisted to `signals/guidance/` |
| **C** | Validation timeout/crash = silent hang | `VALIDATION_TIMEOUT` env var (600s), both TimeoutError and Exception write explicit fail signals |
| **J** | Duplicate validation for terminal nodes | `_get_node_status()` guard before dispatch, skips validated/accepted/failed nodes |
| **D** | Orphan nodes not resumable | All handlers resumable with exponential backoff (5s → 60s max), gate escalation signals |
| **Cancel scope** | SDK teardown crashes on CancelledError | `BaseException` catch (not just `Exception`), cancel scope detection treats 30+ message streams as success |

**33 E2E tests** cover all hardening features (`tests/e2e/test_pipeline_hardening.py`).

## Validation Architecture

### Phase 1: Inline (During Pipeline Execution)

```
Runner detects impl_complete
  │
  ├─ Phase 1a: Technical validation (--mode=technical)
  │  Unit tests, build, imports, TODOs
  │  Returns: TECHNICAL_PASS | TECHNICAL_FAIL
  │
  └─ Phase 1b: Business validation (--mode=business, only if 1a passes)
     Acceptance criteria matrix, E2E journey tests
     Returns: BUSINESS_PASS | BUSINESS_FAIL
```

### Phase 2: Blind Post-Pipeline (Guardian)

After all nodes reach terminal state:

```
Guardian (Layer 0)
  │
  ├─ Run blind Gherkin E2E tests (from acceptance-tests/PRD-XXX/)
  │  Tests written BEFORE implementation, never shown to builders
  │
  ├─ Score gradient confidence (0.0 - 1.0)
  │  Completeness · edge cases · user flows · performance
  │
  └─ Verdict:
     ACCEPT ≥ 0.70 (auto-create fix-it beads for minor gaps)
     INVESTIGATE 0.50-0.69
     REJECT < 0.50
```

## Checkpoint and Resume

Pipeline state is checkpointed after every node transition to `.pipelines/pipelines/*-checkpoint-*.json`. On crash or interruption:

```bash
python3 cobuilder/engine/pipeline_runner.py --dot-file <path> --resume
```

The runner restores from the latest checkpoint and continues from where it left off. Active nodes that were mid-dispatch are detected as timed-out by the AdvancedWorkerTracker and re-dispatched.

## Template System

Templates in `.cobuilder/templates/` are Jinja2 DOT files with constraint enforcement:

```yaml
# manifest.yaml
name: sequential-validated
constraints:
  topology:
    max_nodes: 30
    must_have_validation: true
    no_orphan_nodes: true
  paths:
    max_depth: 4
  loops:
    max_iterations: 3
parameters:
  initiative_id:
    type: string
    required: true
  epic_count:
    type: integer
    default: 3
defaults:
  llm_profile: "anthropic-fast"
  handler_defaults:
    research:
      llm_profile: "anthropic-fast"
    codergen:
      llm_profile: "anthropic-smart"
```

Templates are validated at instantiation time. Constraint violations fail fast with clear error messages.

## Symlink Deployment Model

The harness is designed to be shared across projects via symlinks:

```
~/claude-code-harness/           (this repository)
    │
    ├── .claude/ ◄───── symlinked from Project A, B, C
    ├── .mcp.json ◄──── symlinked or copied (for custom MCP config)
    └── cobuilder/ ◄──── available via PATH or direct reference
```

Update once in the harness → all projects get the update automatically. Projects can override settings via `.claude/settings.local.json`.

## Hooks System

| Hook | Trigger | Purpose |
|------|---------|---------|
| `session-start-orchestrator-detector.py` | Session start | Detect agent role from env vars |
| `load-mcp-skills.sh` | Session start | Load MCP skill registry |
| `user-prompt-orchestrator-reminder.py` | Before each prompt | Enforce delegation rules for orchestrators |
| `unified-stop-gate.sh` | Before session end | Validate completion promises, check open work |
| `hindsight-memory-flush.py` | Before context compression | Flush learnings to Hindsight memory |
| `gchat-notification-dispatch.py` | On notifications | Forward to webhooks |

The stop gate is the most complex hook. For Guardian-level sessions, it runs a 5-step validation:
1. Work exhaustion check (any pending work?)
2. Completion promise verification (`cs-verify`)
3. Hindsight retention check
4. Open beads/task check
5. LLM judge for protocol compliance

Non-Guardian sessions skip the judge entirely.

## Observability

### Logfire Integration

All pipeline operations emit Logfire spans:

| Service Name | What It Traces |
|-------------|---------------|
| `cobuilder-pipeline-runner` | Node transitions, worker dispatch, signal processing |
| `cobuilder-guardian` | Guardian agent operations |
| `cobuilder-session-runner` | Session monitoring |

### CLI Dashboard

```bash
python3 cobuilder/engine/cli.py dashboard .pipelines/pipelines/my-pipeline.dot
```

Shows real-time node states, worker status, and signal activity.

## Package Structure

```
cobuilder/
├── engine/                       # Core pipeline engine
│   ├── pipeline_runner.py        # Main state machine (zero LLM)
│   ├── guardian.py               # Guardian agent launcher
│   ├── session_runner.py         # Session monitoring
│   ├── handlers/                 # Node handler implementations
│   │   ├── codergen.py           # box — coding agent dispatch
│   │   ├── manager_loop.py       # house — recursive sub-pipelines
│   │   ├── wait_human.py         # octagon — human gates
│   │   ├── research.py           # tab — research agents (run_research.py)
│   │   ├── refine.py             # note — spec refinement (run_refine.py)
│   │   └── [base, close, conditional, exit, fan_in, parallel, start, tool]
│   ├── signal_protocol.py        # Atomic JSON signal I/O
│   ├── providers.py + .yaml      # LLM profile resolution
│   ├── dispatch_worker.py        # AgentSDK worker dispatch
│   ├── dispatch_parser.py        # DOT file parsing
│   ├── checkpoint.py             # Pydantic-based state persistence
│   ├── generate.py               # Pipeline DOT generation from beads
│   └── cli.py                    # CLI: status, validate, transition, dashboard
├── templates/                    # Jinja2 template instantiation
│   ├── instantiator.py           # Template renderer
│   ├── constraints.py            # Static constraint validation
│   └── manifest.py               # Template manifest loader
└── repomap/                      # Codebase intelligence for context injection

.claude/
├── output-styles/                # Auto-loaded agent behaviours
│   ├── cobuilder-guardian.md     # Layer 0: strategic oversight
│   └── orchestrator.md           # Layer 2: coordination
├── skills/                       # 20+ invocable capabilities
│   ├── cobuilder-guardian/       # Guardian validation workflow
│   ├── orchestrator-multiagent/  # Multi-agent coordination
│   ├── mcp-skills/               # Progressive disclosure MCP wrappers
│   └── [18+ additional skills]
├── hooks/                        # Lifecycle event handlers
├── scripts/                      # CLI utilities
│   └── completion-state/         # cs-* commands for promise tracking
└── settings.json                 # Core configuration

.cobuilder/templates/             # Pipeline template library
├── sequential-validated/         # Linear with validation gates
├── hub-spoke/                    # Fan-out parallel dispatch
└── cobuilder-lifecycle/          # Full initiative lifecycle
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API authentication |
| `DASHSCOPE_API_KEY` | DashScope (GLM-5, Qwen3) authentication |
| `CLAUDE_SESSION_ID` | Unique session identifier |
| `CLAUDE_OUTPUT_STYLE` | Active output style |
| `PIPELINE_SIGNAL_DIR` | Override signal file directory |
| `PIPELINE_RATE_LIMIT_RETRIES` | Max retries on rate-limit (default: 3) |
| `PIPELINE_RATE_LIMIT_BACKOFF` | Backoff seconds on rate-limit (default: 65) |
| `PIPELINE_MAX_MANAGER_DEPTH` | Max recursive sub-pipeline depth (default: 5) |
| `VALIDATION_TIMEOUT` | Validation agent timeout in seconds (default: 600) |

---

**Architecture Version**: 3.0.0
**Last Updated**: March 15, 2026
