# SD-ATTRACTOR-SDK-001-E1: SDK Worker Backend

**PRD**: GAP-PRD-ATTRACTOR-SDK-001
**Epic**: 1 — SDK Worker Backend
**Priority**: P0
**Depends on**: Epic 3 (Signal Protocol Alignment)

**Validation Status**: ✅ Research-gated (node R1) + SDK decision (2026-03-03)
- Frameworks validated: anthropics/claude-code, claude-agent-sdk
- Research timestamp: 2026-03-02, SDK decision: 2026-03-03
- **Approach: Claude Agent SDK** (`claude_agent_sdk.query()` with `ClaudeAgentOptions`) — NOT subprocess
- Decision rationale: [SDK vs Subprocess Analysis](../references/sdk-vs-subprocess-analysis.md)
- Key benefit: `setting_sources=None` provides clean-room isolation (zero inherited config)
- MCP tools explicitly injected per worker type via `mcp_servers={}`

---

## 1. Problem

In SDK mode, nobody spawns a worker to do the implementation. The guardian calls `spawn_runner.py` which launches `runner_agent.py`, which immediately enters monitoring mode for a tmux session that doesn't exist. The runner needs a DECIDE + SPAWN phase before MONITOR, and it should launch specialist workers directly — no orchestrator layer needed.

**Key insight**: The DOT pipeline IS the orchestration plan. Each codergen node specifies `worker_type` (set by the guardian LLM during pipeline creation), acceptance criteria, and the SD provides implementation details. The runner reads these attributes and spawns the corresponding specialist as a headless Claude Code session. If the guardian judges a `worker_type` needs changing, it modifies the DOT graph directly (LLM-first — no regex heuristics).

## 2. Design

### Architecture: Runner Owns the Worker Lifecycle (3-Layer Model)

Per the Attractor spec's `CodergenBackend` interface (Section 4.5), the backend receives a node + prompt + context and returns an Outcome. In our 3-layer architecture, the **runner** implements this interface — spawning workers and monitoring them:

```
Guardian (Layer 1: Pipeline Driver — headless Claude Code)
  │
  ├── Reads DOT node: worker_type="backend-solutions-engineer"
  ├── Calls spawn_runner.py --node {id} --mode sdk --worker-type {type}
  │
  └── runner_agent.py (Layer 2: RUNNER — headless Claude Code)
        │
        ├── Phase A: SPAWN
        │   ├── Read worker_type from CLI args (set by guardian in DOT graph)
        │   ├── Build focused worker prompt (PRD, SD section, acceptance)
        │   ├── Launch worker as headless Claude Code session
        │   ├── Record process handle, stdout log path, start time
        │   └── Transition to MONITOR mode
        │
        ├── Phase B: MONITOR (see Epic 2)
        │   └── Poll worker health indicators
        │
        ├── Phase C: SIGNAL
        │   └── Notify guardian of completion/failure/input-needed
        │
        └── Phase D: RELAY
            └── Forward guardian responses to worker (remediation)
```

**Why no orchestrator?** The orchestrator's job is to break down work, select workers, and coordinate. In SDK mode, the DOT pipeline already provides:
- **Work breakdown**: each codergen node = one unit of work
- **Worker selection**: `worker_type` attribute on the DOT node (set by guardian LLM)
- **Coordination**: guardian drives graph traversal, runner manages worker lifecycle
- **Implementation details**: SD document provides the plan

The runner spawns the specialist, monitors it, and signals the guardian.

### 2.1 New File: `worker_backend.py`

```python
"""worker_backend.py — Launch specialist workers via Claude Agent SDK.

Implements the CodergenBackend pattern from the Attractor spec.
Spawns headless Claude Code sessions via claude_agent_sdk.query() with:
- Clean-room isolation (setting_sources=None — zero inherited config)
- Focused system_prompt (role definition, no delegation)
- Explicit MCP tool injection per worker type
- Acceptance criteria from DOT node attributes

The runner calls spawn_worker_sdk() to launch a specialist and iterates
the async generator for monitoring events.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage


# Worker type → role definition (system_prompt — stable per type, enables prompt caching)
WORKER_ROLES = {
    "backend-solutions-engineer": (
        "You are a senior Python backend engineer. "
        "You implement features directly — you do NOT delegate or orchestrate. "
        "You use Read, Write, Edit, Bash, Glob, Grep. "
        "You follow existing code patterns. You write tests. You commit with descriptive messages."
    ),
    "frontend-dev-expert": (
        "You are a senior frontend developer specializing in React, Next.js, TypeScript, "
        "and Tailwind CSS. You implement UI features directly — no delegation."
    ),
    "tdd-test-engineer": (
        "You are a test engineer. You write comprehensive tests using Jest and Pytest. "
        "You do NOT implement features — you write tests only."
    ),
}

# Worker type → allowed tools
WORKER_TOOLS = {
    "backend-solutions-engineer": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
    "frontend-dev-expert": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
    "tdd-test-engineer": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
}

# Worker type → required MCP servers (explicit injection, NOT inherited)
# Researched from agent definitions (2026-03-03)
# Serena is mandatory for ALL types — symbolic code navigation
WORKER_MCP_SERVERS: dict[str, dict] = {
    "backend-solutions-engineer": {
        "serena": {"command": "serena-mcp", "args": []},
        "context7": {"command": "npx", "args": ["-y", "@context7/mcp"]},
        "perplexity": {"command": "npx", "args": ["-y", "server-perplexity-ask"]},
        "brave-search": {"command": "npx", "args": ["-y", "@anthropic/mcp-brave-search"]},
    },
    "frontend-dev-expert": {
        "serena": {"command": "serena-mcp", "args": []},
        "context7": {"command": "npx", "args": ["-y", "@context7/mcp"]},
    },
    "tdd-test-engineer": {
        "serena": {"command": "serena-mcp", "args": []},
        "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]},
    },
    "validation-reviewer": {
        "serena": {"command": "serena-mcp", "args": []},
        "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]},
    },
}

DEFAULT_WORKER_TYPE = "backend-solutions-engineer"


@dataclass
class WorkerResult:
    """Result from a completed SDK worker session."""
    node_id: str
    worker_type: str
    target_dir: str
    start_time: float
    stop_reason: str | None = None
    result: str | None = None
    session_id: str | None = None
    error: str | None = None


def build_task_prompt(
    node_id: str,
    prd_ref: str,
    acceptance: str,
    target_dir: str,
    solution_design_path: str | None = None,
    additional_context: str = "",
) -> str:
    """Build the task-specific prompt (per-node context).

    This is SEPARATE from the system_prompt (role definition).
    The system_prompt is stable per worker type (enables prompt caching).
    The task prompt changes per node.
    """
    sd_block = ""
    if solution_design_path and os.path.exists(solution_design_path):
        with open(solution_design_path) as f:
            sd_content = f.read()[:8000]  # Cap at 8k chars
        sd_block = f"\n## Solution Design\n{sd_content}\n"

    prompt = (
        f"## Assignment: Node {node_id}\n"
        f"- PRD Reference: {prd_ref}\n"
        f"- Target Directory: {target_dir}\n"
        f"- Acceptance Criteria: {acceptance or 'See PRD'}\n"
        f"{sd_block}\n"
    )
    if additional_context:
        prompt += f"\n## Additional Context\n{additional_context}\n"
    prompt += (
        "\nBegin by reading the relevant source files, "
        "then implement the changes to meet the acceptance criteria. "
        "Commit your changes with descriptive messages."
    )
    return prompt


async def spawn_worker_sdk(
    node_id: str,
    worker_type: str,
    prd_ref: str,
    acceptance: str,
    target_dir: str,
    solution_design_path: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_turns: int = 100,
    timeout_seconds: int = 1800,
    additional_context: str = "",
) -> WorkerResult:
    """Spawn a specialist worker via Claude Agent SDK.

    Uses claude_agent_sdk.query() with ClaudeAgentOptions for clean-room
    isolation. Workers inherit ZERO filesystem config (setting_sources=None).
    Required MCP tools are explicitly injected per worker type.

    The SDK manages the subprocess internally — no direct PID access.
    Monitoring is via the async event stream (AssistantMessage, ResultMessage)
    and typed exceptions (ProcessError, TimeoutError).

    Args:
        node_id: Pipeline node identifier
        worker_type: Specialist type (e.g., 'backend-solutions-engineer')
        prd_ref: PRD reference string
        acceptance: Acceptance criteria text
        target_dir: Working directory for the worker
        solution_design_path: Optional path to the SD document
        model: Claude model to use
        max_turns: Max conversation turns
        timeout_seconds: Maximum wall-clock time before cancellation
        additional_context: Extra context (e.g., Seance remediation feedback)

    Returns:
        WorkerResult with stop_reason, result, session_id, and any error.
    """
    # Resolve worker type with fallback
    if worker_type not in WORKER_ROLES:
        worker_type = DEFAULT_WORKER_TYPE

    # Build role (system_prompt) and task (prompt) — separated for caching
    system_prompt = WORKER_ROLES[worker_type]
    task_prompt = build_task_prompt(
        node_id=node_id,
        prd_ref=prd_ref,
        acceptance=acceptance,
        target_dir=target_dir,
        solution_design_path=solution_design_path,
        additional_context=additional_context,
    )

    # Clean environment — prevent CLAUDECODE nested session conflict
    clean_env = {
        k: v for k, v in os.environ.items()
        if k not in ("CLAUDECODE", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")
    }

    # SDK options — clean-room isolation is the default
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=WORKER_TOOLS.get(worker_type, ["Read", "Write", "Edit", "Bash"]),
        permission_mode="bypassPermissions",
        model=model,
        cwd=str(target_dir),
        max_turns=max_turns,
        setting_sources=None,  # CRITICAL: zero filesystem inheritance
        mcp_servers=WORKER_MCP_SERVERS.get(worker_type, {}),
        env=clean_env,
    )

    result = WorkerResult(
        node_id=node_id,
        worker_type=worker_type,
        target_dir=target_dir,
        start_time=time.time(),
    )

    try:
        async for message in asyncio.wait_for(
            _consume_query(task_prompt, options),
            timeout=timeout_seconds,
        ):
            if isinstance(message, ResultMessage):
                result.stop_reason = message.stop_reason
                result.result = getattr(message, "result", None)
                result.session_id = getattr(message, "session_id", None)
    except asyncio.TimeoutError:
        result.error = f"Worker timed out after {timeout_seconds}s"
        result.stop_reason = "timeout"
    except Exception as exc:
        result.error = str(exc)
        result.stop_reason = "error"

    return result


async def _consume_query(prompt: str, options: ClaudeAgentOptions):
    """Thin wrapper to make query() compatible with asyncio.wait_for."""
    async for message in query(prompt=prompt, options=options):
        yield message
```

### 2.2 Runner Integration: SPAWN + MONITOR via SDK Events

In `runner_agent.py`, the `RunnerStateMachine` gains a combined SPAWN+MONITOR phase for SDK mode. The runner reads `worker_type` from CLI args (sourced from DOT node, set by guardian) and uses the SDK's async event stream for both spawning and monitoring:

```python
class RunnerStateMachine:
    def __init__(self, ..., mode: str = "tmux", worker_type: str = "backend-solutions-engineer"):
        self.mode = mode
        self.worker_type = worker_type  # From DOT node, via CLI args

    async def run_sdk(self) -> str:
        """SDK-mode execution: spawn worker and monitor via event stream.

        The SDK's async generator IS the monitoring mechanism —
        AssistantMessage events indicate progress, ResultMessage indicates
        completion, ProcessError indicates crash, TimeoutError indicates stall.
        """
        from worker_backend import spawn_worker_sdk

        try:
            result = await spawn_worker_sdk(
                node_id=self.node_id,
                worker_type=self.worker_type,
                prd_ref=self.prd_ref,
                acceptance=self._acceptance,
                target_dir=self.target_dir,
                solution_design_path=self._sd_path,
                additional_context=self._additional_context,
            )

            logfire.info("runner.worker_completed",
                         node_id=self.node_id,
                         worker_type=self.worker_type,
                         stop_reason=result.stop_reason,
                         session_id=result.session_id)

            if result.error:
                logfire.error("runner.worker_error", error=result.error)
                self._write_completion_record("WORKER_CRASHED", error=result.error)
                return RunnerMode.FAILED

            if result.stop_reason == "timeout":
                self._write_completion_record("WORKER_STUCK", error=result.error)
                return RunnerMode.FAILED

            self._write_completion_record("NODE_COMPLETE",
                                          session_id=result.session_id)
            return RunnerMode.COMPLETE

        except Exception as exc:
            logfire.error("runner.spawn_failed", error=str(exc))
            self._write_completion_record("WORKER_CRASHED", error=str(exc))
            return RunnerMode.FAILED

    def _write_completion_record(self, status: str, **kwargs):
        """Write pull-based completion record to stable path for Guardian to poll."""
        from signal_protocol import write_signal
        write_signal(
            self._signals_dir,
            f"{self.node_id}/complete",
            {"status": status, "node_id": self.node_id,
             "ts": time.time(), **kwargs},
        )
```

### 2.3 spawn_runner.py Changes

Pass `--worker-type` (from DOT node) and node context to runner_agent.py:

```python
# New CLI arguments
parser.add_argument("--worker-type", default="backend-solutions-engineer",
                    help="Specialist worker type (from DOT node worker_type attribute)")
parser.add_argument("--acceptance", default="",
                    help="Acceptance criteria for the node")
parser.add_argument("--sd-path", default=None,
                    help="Path to solution design document")

# In cmd construction:
cmd += ["--worker-type", args.worker_type]
if args.acceptance:
    cmd += ["--acceptance", args.acceptance]
if args.sd_path:
    cmd += ["--sd-path", args.sd_path]
```

### 2.4 Guardian System Prompt Update

The guardian reads `worker_type` from the DOT node and passes it to the runner:

```
### Phase 2b: Dispatch Codergen Nodes
For each codergen node with --deps-met:
1. Read the node's worker_type, acceptance criteria, and SD path
2. Transition node → active
3. Spawn runner with worker_type from DOT node:
   python3 {scripts_dir}/spawn_runner.py \
       --node {node_id} \
       --mode sdk \
       --worker-type {worker_type} \
       --acceptance "{acceptance_criteria}" \
       --sd-path {sd_path} \
       --dot-file {dot_path} \
       --signals-dir {signals_dir} \
       --project-root {project_root}
4. Wait for runner signal (NODE_COMPLETE or error)

Note: worker_type is set on the DOT node during pipeline creation.
If the guardian judges the worker_type should change, it modifies
the DOT graph before dispatching (LLM-first approach).
```

### 3. Testing

- **Unit test**: `build_worker_system_prompt()` includes correct persona for each worker_type
- **Unit test**: `build_worker_system_prompt()` includes SD content when path provided
- **Unit test**: `spawn_worker()` launches headless Claude Code with correct env (no CLAUDECODE)
- **Unit test**: `spawn_worker()` creates log files in correct directory
- **Unit test**: Unknown `worker_type` falls back to `backend-solutions-engineer`
- **Integration test**: Runner receives worker_type from CLI → spawns worker → worker commits → runner detects completion
- **Regression test**: tmux mode unaffected (no worker_backend used)

### 4. Files Changed

| File | Change |
|------|--------|
| `worker_backend.py` | **NEW** — Headless Claude Code worker launcher with persona mapping |
| `runner_agent.py` | Add SPAWN phase with _spawn_worker(), worker_type from CLI args |
| `spawn_runner.py` | Pass --worker-type, --acceptance, --sd-path to runner_agent.py |
| `guardian_agent.py` | Update system prompt Phase 2b to read worker_type from DOT node |
| `tests/test_worker_backend.py` | **NEW** — unit tests |

### 5. Design Decisions & Implementation Notes

#### 5.1 Claude Agent SDK — Primary Approach (Decision: 2026-03-03)

**Decision**: Use `claude_agent_sdk.query()` with `ClaudeAgentOptions` for all worker spawning.

**Rationale** (full analysis: [SDK vs Subprocess Analysis](../references/sdk-vs-subprocess-analysis.md)):
- `setting_sources=None` (SDK default) provides clean-room isolation — zero inherited config
- Our harness loads 8+ MCP servers, 6 hooks, and plugins — subprocess would inherit ALL of this (~5-12K tokens overhead per worker)
- SDK provides typed exceptions (`ProcessError`, `CLIConnectionError`) vs raw stderr parsing
- Native async (`async for message in query(...)`) vs manual `asyncio.to_thread`
- System prompt is a first-class parameter that does NOT strip Claude Code's built-in tools
- SDK handles CLAUDECODE env var internally

**What we lose**: Direct PID access (SDK manages subprocess internally). Monitoring is via SDK event stream and `asyncio.wait_for()` for timeouts.

#### 5.2 Worker model selection

Default to `claude-sonnet-4-6` for implementation workers. Allow override via `ClaudeAgentOptions(model=...)` from DOT node `model` attribute.

#### 5.3 Worker MCP Tool Requirements (RESEARCHED)

Workers run with `setting_sources=None` — they get NO MCP tools unless explicitly injected via `mcp_servers={}`. Research findings from agent definitions and usage patterns:

| Worker Type | Required MCP Servers | Rationale |
|-------------|---------------------|-----------|
| `backend-solutions-engineer` | **Serena**, **Context7**, **Perplexity**, **Brave Search** | Needs symbolic code navigation + framework docs + research for implementation decisions |
| `frontend-dev-expert` | **Serena**, **Context7** | Needs code navigation + React/Next.js docs for component implementation |
| `tdd-test-engineer` | **Serena**, **Chrome DevTools** | Needs code exploration + browser automation for E2E testing |
| `validation-reviewer` | **Serena**, **Chrome DevTools** | Needs read-only code analysis + browser inspection for validation evidence |

**Key findings**:
- **Serena is mandatory for ALL worker types** — symbolic code navigation is core to every specialist. Must be activated at session start (`activate_project`, `check_onboarding_performed`, `switch_modes`)
- **Chrome DevTools MCP** (`chrome-devtools-mcp` npm package) is injected for test and validation workers. This is the standalone DevTools Protocol package — NOT the `claude-in-chrome` browser extension (which auto-discovers and cannot be injected via `mcp_servers={}`)
- **Beads should NOT be injected into workers** — workers focus on implementation. Bead status is managed by the runner/guardian layer
- **Logfire is conditional** — only needed when workers are adding observability instrumentation, not for general implementation

**Skills are NOT inherited** — `setting_sources=None` disables `.claude/skills/` discovery entirely. This is correct by design:

| Skill | Used By (not workers) | What Workers Get Instead |
|-------|----------------------|--------------------------|
| `acceptance-test-writer` | Guardian (Phase 1) | N/A — guardian creates tests |
| `acceptance-test-runner` | Guardian (Phase 4) | Acceptance criteria in task prompt |
| `frontend-design` | Guardian/Orchestrator | Design spec in task prompt |
| `research-first` | Guardian (Phase 0) | Research findings baked into SD |
| `react-best-practices` | Guardian briefing | Relevant patterns in task prompt |

**Architecture principle**: Skills are orchestration-level tools. Workers receive the *output* of skills (acceptance criteria, design specs, SD content) in their task prompt. They don't invoke skills themselves — this keeps workers focused on implementation with minimal context overhead.

**Implementation note**: The `WORKER_MCP_SERVERS` dict must contain the full MCP server connection config (command, args, env) for each server. Serena in particular requires project activation before use — workers must call `mcp__serena__activate_project()` at session start.

#### 5.4 Known Gotchas

1. **CLAUDECODE env var**: SDK handles this internally, but if using any manual subprocess fallback, must be stripped. Reference: GitHub issue #573.

2. **SDK version pinning**: SDK had breaking changes v0.0.x→v0.1.x. Pin version in requirements. Core interface (`system_prompt`, `model`, `cwd`, `max_turns`, `setting_sources`) is stable as of v1.0+.

3. **Prompt caching opportunity**: `system_prompt` is stable per worker type. Anthropic caches identical system prompts — ~90% cost reduction on cached tokens. Keep role definitions stable; put per-node context in the `prompt` parameter.

4. **Session resumption for remediation (Epic 4)**: SDK supports `ClaudeAgentOptions(resume="<session_id>")`. Seance context recovery (E4) can use this OR pass predecessor context as `additional_context` in a fresh session. Fresh session is simpler; resume is more token-efficient but couples to session storage.

### 5.5 Implementation Checklist

1. **Install SDK**: `pip install claude-agent-sdk` and pin version in requirements
2. **Verify SDK query works**: Run a simple `async for msg in query("hello", ClaudeAgentOptions(setting_sources=None))` to confirm SDK functions
3. **Test clean-room isolation**: Verify worker does NOT see harness MCP servers or hooks
4. **Define MCP requirements per worker type**: Research and populate `WORKER_MCP_SERVERS`
5. **Integration smoke test**: Spawn one worker via SDK, verify it completes, verify git commits appear, verify pull-based completion record is written

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| - | Remaining | - | - |
