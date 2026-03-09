---
title: "SD-PIPELINE-RUNNER-HARDENING-001: Pipeline Runner & Worker Hardening"
status: draft
type: architecture
last_verified: 2026-03-09
grade: authoritative
prd_ref: PRD-HARNESS-UPGRADE-001
---

# SD-PIPELINE-RUNNER-HARDENING-001: Pipeline Runner & Worker Hardening

## 1. Context & Motivation

### 1.1 Current State (2026-03-09)

The `pipeline_runner.py` has run **7 pipelines in the last 24 hours** producing **81 signal files** with **zero failures**. Logfire confirms zero exceptions. However, deep code analysis reveals **4 critical latent bugs** that will surface under adversarial conditions (concurrent workers, crash recovery, validation timeouts).

### 1.2 Evidence Summary

| Source | Finding |
|--------|---------|
| **Logfire (24h)** | 5 pipeline spans, 0 exceptions. Longest: 85min (AURA-LIVEKIT impl). Workers avg ~6min each. Parallel dispatch confirmed (B+C at same second). |
| **Code Analysis** | 4 CRITICAL, 4 MEDIUM, 3 LOW severity issues identified |
| **Signal Files** | 81 signals processed, all `result: pass`. Zero `fail` or `requeue` signals observed. |
| **Worker Telemetry** | Tools used: Bash(40%), Read(25%), Write(15%), Grep/Glob(12%), TaskCreate/Update(5%), Explore(3%) |

### 1.3 The Problem

The runner works perfectly on the **happy path**. But it has never been stress-tested on:
- Concurrent signal writes from parallel workers
- Validation agent crashes mid-execution
- Force-status persistence across DOT reloads
- Corrupted signal file recovery
- Orphaned non-codergen nodes after crash

These are **ticking time bombs** — invisible until they detonate during a critical pipeline run.

### 1.4 Research Pipeline Evidence (2026-03-09)

A 4-node research pipeline was run to validate the SD. **The failures proved the thesis:**

| Node | Outcome | What It Proves |
|------|---------|----------------|
| `research_worker_context` | **FAILED 3/3** — worker modified SD with code fixes instead of research | Workers don't understand handler roles. Prompts are identical for codergen/research/refine. |
| `research_signal_atomicity` | **CRASHED** — JSON buffer overflow (1MB). No signal written. Node stuck `active` forever. | Dead workers leave nodes orphaned. No liveness check. No signal timeout. |
| `research_feedback_loops` | **ACCEPTED** — comprehensive doc on act-observe-correct loops | Current validation is sequential + binary. Needs parallel, predictive, graduated feedback. |
| `research_env_legibility` | **2 docs written** — gap analysis scores codebase | Discoverability: 5/10. Failure handling: 3/10. Inter-agent communication: 4/10. |

**2 new bugs discovered during the run:**
1. **Dead SDK workers → zombie nodes**: When worker process dies without writing signal, node stays `active` forever. Runner has no process liveness check.
2. **Validation agent spam**: After node reaches `accepted`, runner dispatches ~6 extra validation signals (blocked but noisy).

### 1.5 Harness Engineering Principles (Research Basis)

Per Anthropic, OpenAI, and Martin Fowler harness engineering best practices:

1. **Environment Legibility** > plumbing fixes. Make the codebase discoverable with AGENTS.md, architecture diagrams, schemas, and principles encoded in repo files.
2. **Worker Context** > raw model power. Workers need to know their role, what happened before them, and what "done" looks like for their specific handler type.
3. **Feedback Loops** > binary pass/fail. Implement act-observe-correct loops with graduated, actionable feedback.
4. **Constraints** > micromanagement. Enforce boundaries (linter rules, structured logging, schema validation) to prevent drift.

**Priority rebalancing**: Worker context and legibility promoted to P0 alongside signal/crash fixes. The root cause of the `research_worker_context` failure (workers don't know their role) is more impactful than signal atomicity (which only manifests under concurrent writes).

### 1.6 ToolSearch Gap Discovery (2026-03-10)

**Root cause**: Two separate mechanisms gate MCP tool access in Claude Code SDK:

1. **`allowed_tools` (permission gate)**: A restrict list — ONLY listed tools can be called. If any tool is listed, unlisted tools are blocked. If `allowed_tools` is omitted entirely, ALL tools are available.
2. **ToolSearch (schema discovery)**: MCP tools are deferred — their schemas are NOT in the agent's context until loaded via ToolSearch. Even with permission, the agent can't call a tool it doesn't know exists.

**Both mechanisms must be satisfied**: the tool must be in `allowed_tools` AND loaded via ToolSearch.

| File | Issue |
|------|-------|
| `pipeline_runner.py` `allowed_tools` | Listed Serena tools but NOT context7/Hindsight/Perplexity — research/refine workers were permission-blocked from MCP research tools |
| `pipeline_runner.py` prompts | No handler-specific preambles — all workers got identical generic prompts regardless of role |
| `run_research.py:83` | Prompt says "you do NOT need to use ToolSearch" — **false** |
| `run_refine.py:106` | Same incorrect claim. Additionally, `ToolSearch` was **missing from `allowed_tools`** |
| `worker-tool-reference.md` | Zero mention of ToolSearch or deferred tool loading |

**Context7 finding** (Claude Code agent docs): "Agents can use MCP tools autonomously without requiring pre-allowed lists, allowing Claude to determine which tools are necessary for the task at hand." — This means omitting `allowed_tools` gives agents ALL tools. We chose to keep explicit lists for role isolation (codergen shouldn't research, research shouldn't implement).

**Fix applied (2 phases)**:

Phase 1 (initial): ToolSearch added to all `allowed_tools` lists. Prompts updated with mandatory ToolSearch loading step. `worker-tool-reference.md` updated with ToolSearch section.

Phase 2 (deeper fix): Handler-specific `allowed_tools` — each handler type (codergen, research, refine) gets only the MCP tools appropriate for its role. Research workers get context7 + Perplexity + Hindsight. Refine workers get Hindsight + perplexity_reason. Codergen workers get Serena only. Prompts changed from "here are the exact tool names" to "use ToolSearch to discover available tools" — letting the agent self-discover rather than hardcoding names.

**Validated**: Test pipeline v3 (research node) successfully used ToolSearch → context7 → Hindsight in sequence.

---

## 2. Architecture Changes (Rebalanced Post-Research)

### 2.1 Epic A: Atomic Signal File Protocol (P0 — Critical)

**Problem**: `_write_node_signal()` does direct file writes without atomic guarantees. Concurrent writes to same node_id.json race silently.

**Current** (pipeline_runner.py:1419-1476):
```python
with open(signal_path, "w") as fh:
    fh.write(json.dumps(payload) + "\n")
```

**Proposed**:
```python
def _write_node_signal(self, node_id: str, payload: dict) -> str:
    signal_path = os.path.join(self.signal_dir, f"{node_id}.json")
    tmp_path = signal_path + f".tmp.{os.getpid()}.{time.monotonic_ns()}"

    # Add sequence number for ordering
    payload["_seq"] = self._signal_seq.get(node_id, 0) + 1
    self._signal_seq[node_id] = payload["_seq"]
    payload["_ts"] = datetime.utcnow().isoformat() + "Z"

    with open(tmp_path, "w") as fh:
        fh.write(json.dumps(payload) + "\n")
        fh.flush()
        os.fsync(fh.fileno())

    os.rename(tmp_path, signal_path)  # Atomic on POSIX
    return signal_path
```

**Also fix signal consumption order** (pipeline_runner.py:1230-1243):
```python
# BEFORE: consume then apply (data loss on crash)
os.rename(signal_path, dest)  # ← signal lost if _apply_signal crashes
self._apply_signal(node_id, signal)

# AFTER: apply then consume (idempotent)
self._apply_signal(node_id, signal)
os.rename(signal_path, dest)  # Only consumed after successful apply
```

**Corrupted signal handling**:
```python
except (OSError, json.JSONDecodeError) as exc:
    # Quarantine instead of silently skipping
    quarantine = os.path.join(self.signal_dir, "quarantine")
    os.makedirs(quarantine, exist_ok=True)
    shutil.move(signal_path, os.path.join(quarantine, os.path.basename(signal_path)))
    log.error("Quarantined corrupted signal %s: %s", signal_path, exc)
```

**Files to modify**:
- `pipeline_runner.py`: `_write_node_signal()`, `_process_signals()`, `_apply_signal()`

**Acceptance Criteria**:
- AC-1: Signal writes use temp-file-then-rename (atomic on POSIX)
- AC-2: Each signal includes `_seq` and `_ts` metadata fields
- AC-3: Corrupted signals moved to `signals/quarantine/` (not silently dropped)
- AC-4: Signal consumption happens AFTER successful transition application
- AC-5: Concurrent write test: 10 parallel writers, zero corruption

---

### 2.2 Epic B: force_status Persistence Fix (P0 — Critical)

**Problem**: `_force_status()` edits in-memory `self.dot_content` but `_main_loop()` reloads DOT from disk, clobbering the forced status.

**Current** (pipeline_runner.py ~line 1380):
```python
def _force_status(self, node_id, target_status):
    # Edits self.dot_content in memory only
    self.dot_content = self.dot_content.replace(...)
```

**Meanwhile** (pipeline_runner.py:335-349):
```python
# Main loop reloads from disk → clobbers in-memory edits
with open(self.dot_path) as fh:
    self.dot_content = fh.read()
```

**Proposed**: Use `_do_transition()` (which already writes to disk with fcntl lock) instead of `_force_status()`:

```python
def _force_status(self, node_id: str, target_status: str) -> None:
    """Force node status — writes to disk (not just memory)."""
    self._do_transition(node_id, target_status)
    # Also persist requeue guidance if present
    if node_id in self.requeue_guidance:
        self._persist_requeue_guidance(node_id, self.requeue_guidance[node_id])
```

**Files to modify**:
- `pipeline_runner.py`: `_force_status()`, add `_persist_requeue_guidance()`

**Acceptance Criteria**:
- AC-1: `_force_status()` writes to DOT file on disk (not just memory)
- AC-2: Status survives `_main_loop()` reload cycle
- AC-3: Requeue guidance persisted alongside status change
- AC-4: Test: force_status → reload DOT → verify status persists

---

### 2.3 Epic C: Validation Agent Error Handling (P0 — Critical)

**Problem**: Validation subprocess failures are invisible. If validation agent crashes, node stays `impl_complete` forever — "Pipeline stuck" with no clear cause.

**Current** (pipeline_runner.py:933-1210):
- Spawns validation subprocess in background
- No stdout/stderr capture
- No timeout enforcement
- No retry on failure

**Proposed**:

```python
def _dispatch_validation_agent(self, node_id, target_node_id):
    """Dispatch validation with error handling and configurable timeout."""
    timeout = int(os.environ.get("VALIDATION_TIMEOUT", "600"))  # 10min default

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            log.error("[validation] %s failed (rc=%d): %s",
                     node_id, result.returncode, result.stderr[:500])
            # Write failure signal so node doesn't hang
            self._write_node_signal(target_node_id, {
                "status": "fail",
                "result": "fail",
                "reason": f"Validation agent crashed: {result.stderr[:200]}",
                "validator_exit_code": result.returncode,
            })

    except subprocess.TimeoutExpired:
        log.error("[validation] %s timed out after %ds", node_id, timeout)
        self._write_node_signal(target_node_id, {
            "status": "fail",
            "result": "fail",
            "reason": f"Validation timed out after {timeout}s",
        })
```

**Files to modify**:
- `pipeline_runner.py`: `_dispatch_validation_agent()`

**Acceptance Criteria**:
- AC-1: Validation timeout configurable via `VALIDATION_TIMEOUT` env var (default 600s)
- AC-2: Validation failures write explicit `fail` signal (node never hangs)
- AC-3: stderr captured and included in failure signal (first 500 chars)
- AC-4: Test: mock validation crash → verify fail signal written within 5s

---

### 2.4 Epic D: Orphaned Node Resume Expansion (P1 — High)

**Problem**: After runner restart, only `codergen` nodes with status `active` are re-dispatched. Orphaned `research`, `refine`, and `acceptance-test-writer` nodes remain stuck.

**Current** (pipeline_runner.py:384-393):
```python
orphaned_active_nodes = [
    n for n in nodes
    if n["attrs"].get("status") == "active"
    and n["attrs"].get("handler") == "codergen"  # ← Only codergen!
    and n["id"] not in self.active_workers
]
```

**Proposed**:
```python
RESUMABLE_HANDLERS = frozenset({"codergen", "research", "refine", "acceptance-test-writer"})
GATE_HANDLERS = frozenset({"wait.system3", "wait.human"})

orphaned_active_nodes = [
    n for n in nodes
    if n["attrs"].get("status") == "active"
    and n["id"] not in self.active_workers
]

for node in orphaned_active_nodes:
    handler = node["attrs"].get("handler", "")
    if handler in RESUMABLE_HANDLERS:
        retries = self.orphan_resume_counts.get(node["id"], 0)
        if retries < 3:  # Exponential backoff
            delay = min(2 ** retries * 5, 60)  # 5s, 10s, 20s, max 60s
            log.info("[resume] Re-dispatch %s (handler=%s, attempt=%d, delay=%ds)",
                    node["id"], handler, retries + 1, delay)
            time.sleep(delay)
            self._dispatch_node(node, data)
            self.orphan_resume_counts[node["id"]] = retries + 1
        else:
            log.error("[resume] Exhausted retries for orphaned node %s", node["id"])
            self._do_transition(node["id"], "failed")
    elif handler in GATE_HANDLERS:
        log.warning("[resume] Gate node %s stuck in active — emitting escalation", node["id"])
        self._write_node_signal(node["id"], {
            "status": "escalation",
            "reason": f"Gate node {node['id']} orphaned after restart",
        })
```

**Files to modify**:
- `pipeline_runner.py`: orphaned node detection block, add `orphan_resume_counts` dict

**Acceptance Criteria**:
- AC-1: All WORKER_HANDLERS covered by orphan resume (not just codergen)
- AC-2: Exponential backoff: 5s, 10s, 20s delays between retries
- AC-3: Max 3 retries per orphaned node before marking failed
- AC-4: Gate nodes (wait.system3, wait.human) emit escalation signal instead of re-dispatch
- AC-5: Test: simulate crash → verify research/refine nodes resume correctly

---

### 2.5 Epic E: Worker Prompt Improvements (P1 — High)

**Problem**: Workers receive identical prompts regardless of handler type. Research nodes don't know they should validate docs. Validation agents don't see git diffs. Requeue guidance is lost after first dispatch.

**5 sub-improvements**:

#### E.1: Handler-Specific Prompt Preambles

```python
HANDLER_PREAMBLES = {
    "codergen": "You are implementing code changes. Write production-quality code.",
    "research": "You are researching framework patterns. Validate docs against installed versions. Update the SD with findings.",
    "refine": "You are refining a Solution Design. Merge research findings into the SD as first-class content.",
    "acceptance-test-writer": "You are writing Gherkin acceptance tests from the PRD acceptance criteria.",
}
```

#### E.2: Validation Prompt Gets Pre-Computed Diff

```python
def _build_validation_prompt(self, node_id, ...):
    # Pre-compute diff so validator doesn't waste 30s
    diff = subprocess.run(
        ["git", "diff", "--stat", "HEAD~1"],
        capture_output=True, text=True, timeout=10
    ).stdout[:2000]

    prompt += f"\n## Changes Made\n```\n{diff}\n```\n"
```

#### E.3: Persistent Requeue Guidance

```python
# Instead of .pop() (one-shot), keep guidance in persistent store
def _get_requeue_guidance(self, node_id):
    # Check persistent file first
    guidance_path = os.path.join(self.signal_dir, "guidance", f"{node_id}.txt")
    if os.path.exists(guidance_path):
        return open(guidance_path).read()
    return self.requeue_guidance.get(node_id, "")
```

#### E.4: Worker Model Selection Documentation

Add to `worker-tool-reference.md`:
```markdown
## Model Selection Guide
| Handler | Default Model | When to Override |
|---------|--------------|-----------------|
| codergen | Haiku 4.5 | Sonnet for complex multi-file changes |
| research | Haiku 4.5 | Rarely needs upgrade |
| refine | Sonnet 4.6 | Always Sonnet (requires synthesis) |
| validation | Sonnet 4.6 | Never downgrade (needs judgment) |
```

#### E.5: SD Path Fallback Clarity

```python
# Replace ambiguous "(none)" with actionable message
if not os.path.exists(sd_path):
    sd_section = f"## Solution Design\nNo SD found at `{sd_path}`. If this is unexpected, check the DOT node's sd_path attribute."
```

**Files to modify**:
- `pipeline_runner.py`: `_build_worker_prompt()`, `_build_validation_prompt()`, requeue guidance
- `.claude/agents/worker-tool-reference.md`: model selection section

**Acceptance Criteria**:
- AC-1: Each handler type gets a distinct preamble in the worker prompt
- AC-2: Validation prompts include pre-computed `git diff --stat`
- AC-3: Requeue guidance persists across dispatches (not one-shot `.pop()`)
- AC-4: Model selection guide added to worker-tool-reference.md
- AC-5: SD path fallback shows actionable error (not just "(none)")

---

### 2.6 Epic F: Global Pipeline Safeguards (P2 — Medium)

#### F.1: Pipeline Timeout

```python
# Add --max-duration flag
parser.add_argument("--max-duration", type=int, default=7200,
                   help="Max pipeline duration in seconds (default: 2h)")
```

In main loop:
```python
if time.monotonic() - self.start_time > self.max_duration:
    log.error("[timeout] Pipeline exceeded %ds. Failing remaining nodes.", self.max_duration)
    for node_id in self._get_non_terminal_nodes():
        self._do_transition(node_id, "failed")
    return PipelineResult.TIMEOUT
```

#### F.2: Cost Tracking in Signals

```python
# Workers report token usage in signal
{
    "status": "success",
    "cost": {"input_tokens": 12500, "output_tokens": 3400, "model": "haiku-4.5"},
    ...
}
```

Runner aggregates:
```python
self.pipeline_cost = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "by_node": {},
}
```

#### F.3: Rate Limiting Per Worker Type

```python
# Prevent API rate limit exhaustion
WORKER_TYPE_LIMITS = {
    "codergen": 4,      # Max 4 parallel codergen workers
    "research": 6,      # Research is lightweight
    "validation": 2,    # Validation needs sequential access
}
```

**Acceptance Criteria**:
- AC-1: `--max-duration` flag with 2h default, failing remaining nodes on timeout
- AC-2: Cost data (tokens, model) included in worker signal payloads
- AC-3: Per-worker-type concurrency limits configurable via env vars

---

### 2.7 Epic G: Worker Context & Handler-Specific Preambles (P0 — Critical, NEW)

**Problem proven by research_worker_context failure**: Workers don't understand their handler role. A research node modified the SD with implementation fixes instead of conducting comparative research. Validator correctly rejected 3/3 times.

**Root cause**: `_build_worker_prompt()` generates identical prompts regardless of handler type. Workers have no context about:
- What their handler role means (research ≠ codergen ≠ refine)
- What happened in predecessor nodes (no prior-node-outcome injection)
- What "done" looks like for their specific handler type
- Decision history from the pipeline

**Proposed**:

```python
HANDLER_CONTEXT = {
    "codergen": {
        "preamble": """You are an IMPLEMENTATION worker. Your job is to write production-quality code.
DO NOT research, investigate, or write documentation — only implement.
Read the Solution Design carefully. It contains the exact changes to make.""",
        "done_criteria": "All files changed, tests pass, signal written with files_changed list.",
    },
    "research": {
        "preamble": """You are a RESEARCH worker. Your job is to investigate and document findings.
DO NOT modify source code or the Solution Design directly.
Write your findings to a NEW markdown file (not the SD) at the repo root.
Use WebSearch, WebFetch, and Read to gather information from external sources AND the codebase.
Compare best practices against the current implementation.""",
        "done_criteria": "Research doc written with all acceptance criteria addressed. Signal written with doc path.",
    },
    "refine": {
        "preamble": """You are a REFINEMENT worker. Your job is to merge research findings into the Solution Design.
Read the research docs produced by predecessor nodes (check signal files for paths).
Edit the SD to incorporate findings as first-class content (not annotations).
Use Hindsight reflect before editing to check for prior patterns.""",
        "done_criteria": "SD updated with research findings integrated. No research annotations remain.",
    },
    "acceptance-test-writer": {
        "preamble": """You are a TEST WRITER. Your job is to create Gherkin acceptance test scenarios.
Read the PRD acceptance criteria. Write .feature files with Given/When/Then.
Tests should be blind (not peek at implementation).""",
        "done_criteria": "Feature files written with scenarios covering all PRD acceptance criteria.",
    },
}
```

**Prior-node-outcome injection** — embed predecessor signals in prompt:

```python
def _inject_predecessor_context(self, node_id, data):
    """Read signals from predecessor nodes and embed in prompt."""
    predecessors = data.get("edges", {}).get(node_id, {}).get("predecessors", [])
    context_lines = []
    for pred_id in predecessors:
        signal_path = os.path.join(self.signal_dir, "processed", f"*-{pred_id}.json")
        signals = sorted(glob.glob(signal_path))
        if signals:
            with open(signals[-1]) as f:
                sig = json.load(f)
            context_lines.append(f"### Predecessor: {pred_id}")
            context_lines.append(f"- Status: {sig.get('status', 'unknown')}")
            context_lines.append(f"- Files: {sig.get('files_changed', [])}")
            context_lines.append(f"- Message: {sig.get('message', 'N/A')[:200]}")
    return "\n".join(context_lines) if context_lines else "No predecessor signals available."
```

**Files to modify**:
- `pipeline_runner.py`: `_build_worker_prompt()`, add `HANDLER_CONTEXT` dict, add `_inject_predecessor_context()`

**Acceptance Criteria**:
- AC-1: Each handler type gets a distinct preamble that clearly states what the worker SHOULD and SHOULD NOT do
- AC-2: Predecessor node signals are embedded in the prompt (status, files_changed, message)
- AC-3: "Done criteria" for each handler type is included in the prompt
- AC-4: Test: research handler prompt does NOT contain "implement" or "write code"
- AC-5: Test: codergen handler prompt does NOT contain "research" or "investigate"

---

### 2.8 Epic H: Dead Worker Detection & Signal Timeout (P0 — Critical, NEW)

**Problem proven by research_signal_atomicity crash**: Worker PID 98114 died with JSON buffer overflow. No signal was ever written. Node stayed `active` forever with no process working on it. Runner had no way to detect the dead worker.

**Root cause**: `_dispatch_agent_sdk()` tracks workers in `self.active_workers` dict but never checks if the underlying process is still alive. AgentSDK workers run in ThreadPoolExecutor futures — if the future completes with an exception, the result is silently lost.

**Proposed**:

```python
def _check_worker_liveness(self):
    """Detect dead workers whose futures completed but wrote no signal."""
    for node_id, future in list(self.active_workers.items()):
        if future.done():
            # Future completed but no signal was written
            signal_path = os.path.join(self.signal_dir, f"{node_id}.json")
            if not os.path.exists(signal_path):
                exc = future.exception()
                if exc:
                    log.error("[liveness] Worker %s died with exception: %s", node_id, exc)
                    self._write_node_signal(node_id, {
                        "status": "error",
                        "result": "fail",
                        "reason": f"Worker process died: {str(exc)[:300]}",
                        "worker_crash": True,
                    })
                else:
                    # Completed without exception but no signal — worker forgot to write
                    elapsed = time.monotonic() - self.dispatch_times.get(node_id, 0)
                    log.warning("[liveness] Worker %s completed silently after %.0fs", node_id, elapsed)
                    self._write_node_signal(node_id, {
                        "status": "error",
                        "result": "fail",
                        "reason": f"Worker completed without writing signal after {elapsed:.0f}s",
                    })
                del self.active_workers[node_id]

    # Also check for signal timeout (worker running too long)
    timeout = int(os.environ.get("WORKER_SIGNAL_TIMEOUT", "900"))  # 15min default
    for node_id, dispatch_time in list(self.dispatch_times.items()):
        if node_id in self.active_workers:
            elapsed = time.monotonic() - dispatch_time
            if elapsed > timeout:
                log.error("[liveness] Worker %s exceeded signal timeout (%ds)", node_id, timeout)
                # Kill the future if possible
                future = self.active_workers[node_id]
                future.cancel()
                self._write_node_signal(node_id, {
                    "status": "error",
                    "result": "fail",
                    "reason": f"Worker timed out after {elapsed:.0f}s (limit: {timeout}s)",
                })
                del self.active_workers[node_id]
```

Call `_check_worker_liveness()` in every iteration of `_main_loop()`.

**Files to modify**:
- `pipeline_runner.py`: add `_check_worker_liveness()`, add `dispatch_times` dict, integrate into `_main_loop()`

**Acceptance Criteria**:
- AC-1: Dead worker futures detected within one loop iteration (~2s)
- AC-2: Failure signal written automatically when worker dies without signal
- AC-3: Worker signal timeout configurable via `WORKER_SIGNAL_TIMEOUT` env var (default 900s)
- AC-4: Timed-out workers have their futures cancelled
- AC-5: Test: mock future.exception() → verify fail signal written

---

### 2.9 Epic I: Centralized AGENTS.md & Environment Legibility (P0 — Critical, NEW)

**Problem proven by env_legibility research**: Current discoverability score is **5/10**. Workers must manually search for agent configs. No centralized menu, no competency matrices, no boundary definitions.

**Root cause**: Agent docs exist in `.claude/agents/*.md` but there's no index, no routing guidance, and no cross-agent handoff protocols. Workers arriving at a new codebase have no map.

**Proposed**:

Create `.claude/agents/AGENTS.md` as a centralized directory:

```markdown
# Agent Directory

## Quick Selection Guide

| If your task involves... | Use Agent | Model |
|--------------------------|-----------|-------|
| Python backend, APIs, databases | backend-solutions-engineer | Sonnet |
| React, TypeScript, CSS, UI | frontend-dev-expert | Sonnet |
| System design, PRDs, SDs | solution-architect | Sonnet |
| Writing/running tests | tdd-test-engineer | Sonnet |
| Validating implementations | validation-test-agent | Sonnet |

## Competency Matrix

| Agent | Can Do | Cannot Do | Escalate To |
|-------|--------|-----------|-------------|
| backend-solutions-engineer | Python, FastAPI, PydanticAI, SQL, MCP | Frontend, CSS, React | frontend-dev-expert |
| frontend-dev-expert | React, Next.js, Tailwind, Zustand | Python, databases | backend-solutions-engineer |
| tdd-test-engineer | Unit/integration/E2E tests | Implementation, design | backend/frontend agent |
| validation-test-agent | PRD validation, acceptance testing | Implementation, design | orchestrator |

## Handoff Protocol

When an agent encounters work outside its competency:
1. Document what was found (in signal file message)
2. Set signal status to "needs_handoff"
3. Include target_agent in signal payload
4. Runner will dispatch appropriate agent
```

Also create `.claude/agents/ARCHITECTURE.md` — a lightweight codebase map for workers arriving fresh:

```markdown
# Codebase Architecture (for AI Workers)

## Repository Map
- `.claude/scripts/attractor/` — Pipeline runner and worker dispatch
- `.claude/agents/` — Agent configurations (YOU ARE HERE)
- `.claude/skills/` — Skill definitions (invoked via Skill tool)
- `docs/prds/` — Product requirement documents
- `docs/sds/` — Solution design documents
- `acceptance-tests/` — Gherkin acceptance test suites
```

**Files to create/modify**:
- `.claude/agents/AGENTS.md` (new)
- `.claude/agents/ARCHITECTURE.md` (new)
- `.claude/agents/worker-tool-reference.md` (update with model selection guide)

**Acceptance Criteria**:
- AC-1: AGENTS.md exists with quick selection guide, competency matrix, and handoff protocol
- AC-2: ARCHITECTURE.md exists with repo map, directory purposes, and key file locations
- AC-3: worker-tool-reference.md includes model selection guide per handler type
- AC-4: All agent *.md files cross-linked from AGENTS.md
- AC-5: doc-gardener lint passes on all new files

---

### 2.10 Epic J: Validation Spam Suppression (P1 — High, NEW)

**Problem discovered during research pipeline**: After `research_feedback_loops` reached `accepted`, the runner dispatched ~6 additional validation signals (mix of pass/fail from lingering agents). Blocked by state machine but noisy.

**Root cause**: `_dispatch_validation_agent()` is called whenever a signal arrives for a node, even if the node is already in a terminal state.

**Proposed**:

```python
def _dispatch_validation_agent(self, node_id, target_node_id):
    # Guard: skip if node already terminal
    node_status = self._get_node_status(target_node_id)
    if node_status in ("validated", "accepted", "failed"):
        log.debug("[validation] Skipping dispatch for terminal node %s (status=%s)",
                 target_node_id, node_status)
        return
    # ... existing dispatch logic
```

**Acceptance Criteria**:
- AC-1: Validation not dispatched for nodes in terminal states
- AC-2: Zero validation signals for already-accepted nodes
- AC-3: Test: accept node → trigger signal → verify no validation dispatch

---

## 3. Implementation Priority (Rebalanced Post-Research)

| Priority | Epic | Effort | Impact | Evidence |
|----------|------|--------|--------|----------|
| **P0** | G: Worker Context & Handler Preambles | 3h | CRITICAL | research_worker_context failed 3/3 — workers don't know their role |
| **P0** | H: Dead Worker Detection | 2h | CRITICAL | research_signal_atomicity crashed — node stuck active forever |
| **P0** | I: AGENTS.md & Environment Legibility | 2h | CRITICAL | Gap analysis: discoverability 5/10, failure handling 3/10 |
| **P1** | A: Atomic Signals | 2h | HIGH | Code analysis: race condition under parallel writes |
| **P1** | B: force_status Fix | 1h | HIGH | Code analysis: in-memory edits lost on reload |
| **P1** | C: Validation Error Handling | 2h | HIGH | Code analysis: invisible validation failures |
| **P1** | J: Validation Spam Suppression | 1h | MEDIUM | Research pipeline: ~6 extra signals per accepted node |
| **P2** | D: Orphan Resume Expansion | 2h | MEDIUM | Partially addressed by Epic H |
| **P2** | E: Worker Prompt (remaining sub-items) | 1h | MEDIUM | Partially addressed by Epic G |
| **P2** | F: Global Safeguards | 3h | LOW | Nice-to-have (timeout, cost tracking) |

**Total estimated effort**: ~19h (6 new hours from research-discovered epics)

---

## 4. Testing Strategy

### Unit Tests (per epic)
- Epic A: Concurrent signal write stress test (10 threads)
- Epic B: force_status → reload → verify persistence
- Epic C: Mock validation crash → verify fail signal timing
- Epic D: Simulate crash → verify all handler types resume
- Epic E: Prompt generation snapshot tests per handler type
- Epic F: Timeout enforcement test

### Integration Test
- Full pipeline with intentional failures injected at each stage
- Verify recovery from every failure mode

### Regression Guard
- Existing 15+ test files (~8500 LOC) must continue passing
- Add `test_hardening.py` with all new scenarios

---

## 5. Dependencies

- `claude_code_sdk` (existing, unchanged)
- `watchdog` (existing, optional)
- `logfire` (existing, optional — enhanced with cost tracking)
- No new external dependencies

---

## 6. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Atomic rename not truly atomic on NFS | Document: pipeline requires local filesystem |
| Exponential backoff delays pipeline | Cap at 60s, configurable via env var |
| Validation timeout too aggressive | Default 600s (10min), configurable |
| Cost tracking adds overhead | Opt-in via env var `PIPELINE_TRACK_COST=1` |

---

## 7. Open Questions (Resolved by Research)

- **Q1**: Should corrupted signals trigger immediate node failure or wait for manual inspection?
  - **RESOLVED**: Quarantine to `signals/quarantine/` + log error. Node retries via normal retry logic. Human can inspect quarantine dir.
- **Q2**: What is the right default for `--max-duration`? 2h may be too short for large initiatives.
  - **RESOLVED**: 2h is fine. Longest observed pipeline in 24h was 85min (AURA-LIVEKIT). Large initiatives run multiple pipelines, not one long one.
- **Q3**: Should we add structured logging (JSON) to complement Logfire spans?
  - **RESOLVED**: No. Logfire already provides structured tracing. Adding JSON logs would duplicate without value.
- **Q4**: Is there value in a `--dry-run` mode that validates the pipeline without dispatching workers?
  - **RESOLVED**: Yes — `cobuilder pipeline validate` already does this for graph structure. Adding `--dry-run` to runner would validate dispatch config without actual execution. Low priority (P2).

## 8. Research Artifacts

| Artifact | Location | Status |
|----------|----------|--------|
| Feedback & Verification Loops Research | `research_feedback_and_verification_loops.md` (repo root) | Complete |
| Environment Legibility Guide | `docs/environment-legibility-for-ai-agents.md` | Complete |
| Agent Documentation Gap Analysis | `docs/agent-documentation-gap-analysis.md` | Complete |
| Worker Context Research | Not produced (worker failed 3/3) | Failed — proves Epic G thesis |
| Signal Atomicity Research | Not produced (worker crashed) | Failed — proves Epic H thesis |
