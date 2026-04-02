---
title: "GasCity Integration — Resilient Work Allocation for CoBuilder Pipelines"
description: "Integrate GasCity's pull-based work allocation, agent health patrol, and pool scaling with CoBuilder's deterministic DAG pipeline execution"
version: "1.1.0"
last-updated: 2026-04-03
status: active
type: prd
grade: authoritative
prd_id: PRD-GASCITY-INT-001
---

# PRD-GASCITY-INT-001: GasCity Integration

## 1. Problem Statement

CoBuilder's pipeline engine (`pipeline_runner.py`) executes deterministic DOT graph pipelines by directly dispatching workers via AgentSDK (`dispatch_worker.py`). This push-based model has three structural weaknesses:

1. **No crash recovery**: If a worker process dies mid-task, the pipeline runner has no mechanism to detect the failure and restart the worker. It relies on signal file timeouts, which can stall pipelines for minutes before detection.

2. **Fixed worker assignment**: Each DOT node specifies exactly which `worker_type` runs it. There is no work-stealing, elastic scaling, or pool-based allocation. If a worker type is overloaded, other idle workers cannot help.

3. **No agent health management**: The pipeline runner has no liveness monitoring for workers. Dead workers are only detected when signal files fail to appear within timeout windows. There is no drift detection, crash loop protection, or graceful termination protocol.

GasCity (github.com/gastownhall/gascity) — Steve Yegge's Go-based multi-agent orchestration SDK extracted from Gastown — solves exactly these problems with battle-tested patterns: pull-based work discovery, Erlang/OTP-style health patrol, pool agents with dynamic scaling, and crash-recovery reconciliation.

## 2. Vision

CoBuilder pipelines retain their deterministic DAG execution (ordered nodes, quality gates, checkpoint/resume) while delegating agent lifecycle management to GasCity's controller. The result: pipelines that are both structurally reliable (CoBuilder) and operationally resilient (GasCity).

**Three-layer architecture:**
```
CoBuilder Pipeline Engine  →  GasCity Controller  →  Claude SDK / claw-code Runtime
(ordering + gates)            (allocation + health)   (LLM execution)
```

## 3. User Stories

**US-1**: As a CoBuilder operator, I want workers to automatically restart after crashes so that pipelines recover without manual intervention.

**US-2**: As a CoBuilder operator, I want idle workers to claim available work from a shared pool so that pipeline execution is faster and more resource-efficient.

**US-3**: As a CoBuilder operator, I want agent health monitoring with crash loop protection so that misbehaving workers are quarantined instead of endlessly restarted.

**US-4**: As a CoBuilder operator, I want to see unified observability across both CoBuilder pipeline events and GasCity agent events so I have a single view of what is happening.

## 4. Shared Foundation: Beads

Both systems already use beads (`bd`) as the fundamental work unit. CoBuilder tracks beads via `bd create/close/ready` and maps them to DOT nodes via `bead_id` attributes. GasCity's entire Store abstraction is built on beads with CRUD, labels, parent-child relationships, and query.

This shared primitive is the natural integration point — no new persistence layer needed.

## 5. Architecture Overview

### Current Flow (Push-Based)

```
pipeline_runner.py
  PipelineRunner._dispatch_agent_sdk()          # line 2008 — background thread
    → _dispatch_via_sdk()                        # line 2215 — ClaudeCodeSession direct
      → worker executes → writes signal file
  → _process_signals() → _apply_signal()         # node state transition
```

The primary integration point is `_dispatch_agent_sdk()` in `pipeline_runner.py` at line 2008. This single method is the boundary between CoBuilder's graph engine and worker execution. GasCity integration intercepts here via a `dispatch_mode` node attribute check.

### Proposed Flow (Pull-Based via GasCity)

```
pipeline_runner.py
  _dispatch_agent_sdk()                          # line 2008
    pool_mode = node_attrs.get("dispatch_mode", "sdk")
    if pool_mode == "pool":
      pool_dispatch.create_bead(...)             # NEW: bead creation path
        bd create --label=pool:{worker_type}-worker
        gc poke                                  # trigger immediate reconcile
    else:
      _dispatch_via_sdk(...)                     # existing path unchanged

GasCity Controller (subprocess provider)
  → reconciliation loop (30s tick + fsnotify)
  → pool.check = "bd ready --json --label=pool:X | jq length"
  → scales pool agent instances (min=0, max=5)
  → pool agent hook fires → executes work_query
  → pool agent: bd update <id> --claim          # atomic compare-and-swap

Pool Agent (Claude subprocess session)
  → executes pipeline node task
  → writes {node_id}.json to $PIPELINE_SIGNAL_DIR/  # CoBuilder protocol
  → bd close <bead-id>                              # GasCity protocol

pipeline_runner.py
  → _process_signals() detects signal file → _apply_signal()
  → node transitions: active → impl_complete → validated → accepted
```

### Key Integration Points

| Component | CoBuilder Side | GasCity Side |
|-----------|---------------|-------------|
| Work creation | `pool_dispatch.create_bead()` with pool labels | `pool.check` command detects new work |
| Agent lifecycle | — (delegates fully) | Controller: start/stop/scale/quarantine |
| Work claiming | — (delegates fully) | Pool agent: `bd update {id} --claim` (atomic CAS) |
| Immediate dispatch | `gc poke` after bead creation | Controller reconciles within seconds, not 30s |
| Completion signal | `{node_id}.json` in `$PIPELINE_SIGNAL_DIR` | `bd close {bead_id}` |
| Health monitoring | — (delegates fully) | Health Patrol: crash loop, drift, idle timeout |
| Observability | 18-type event bus (JSONL/Logfire/SignalBridge) | `.gc/events.jsonl` (JSONL, monotonic Seq) |

### Provider Selection: `subprocess` (not `tmux`)

CoBuilder workers are headless pipeline workers. The GasCity `subprocess` provider launches `claude` processes without requiring a tmux session — matching how `dispatch_worker.py` currently operates. The `tmux` provider is for interactive/human-attached sessions and is out of scope.

### Dual-Protocol Completion

Pool agents MUST emit both protocols on task completion:

1. **CoBuilder signal**: Write `{node_id}.json` to `$PIPELINE_SIGNAL_DIR/` (runner watches this for state transitions)
2. **GasCity close**: Run `bd close {bead_id}` (enables convoy auto-close and pool reclaim)

Both are required. The signal file drives graph state; the bead close drives agent lifecycle.

### Bead Label Conventions

```
pipeline:{pipeline_id}         # pipeline identifier
node:{node_id}                 # DOT node identifier  
worker:{worker_type}           # codergen | research | refine
handler:{handler}              # maps to HANDLER_REGISTRY (codergen | research | refine | ...)
pool:{worker_type}-worker      # enables GasCity pool claiming
```

Signal dir is stored as bead **metadata** (not a label): `signal_dir` field contains the absolute path. Pool agent prompt templates read this via `bd get {id}` at task start. This avoids base64 encoding and fragile env injection.

## 6. Design Principles (Inherited from GasCity)

- **ZFC (Zero Framework Cognition)**: Go handles transport, not reasoning. Judgment calls stay in prompts.
- **NDI (Nondeterministic Idempotence)**: System converges to correct outcomes because beads and hooks are persistent. Sessions come and go; work survives.
- **GUPP**: "If you find work on your hook, YOU RUN IT." No confirmation. The hook having work IS the assignment.
- **Bitter Lesson**: Every primitive must become MORE useful as models improve.
- **ZERO hardcoded roles**: All role behavior is configuration (prompt templates), not Go code.

## 7. Non-Goals (Prototype Scope)

- Full GasCity deployment with Kubernetes provider (use `subprocess` provider only)
- Formulas/Molecules integration (future — would replace DOT templates with reactive graphs)
- Inter-agent messaging via beads (future — would replace signal files with bead-native pub/sub)
- GasCity Orders/automation (future — would enable cron-triggered pipelines)
- Replacing CoBuilder's DOT graph with GasCity's flat bead model
- Crash tracker persistence across controller restarts (intentionally ephemeral by design — Erlang/OTP pattern; use quarantine labels in beads for persistence if needed)

## 8. Epics

**Implementation order**: Epic 2 before Epic 1. Pool dispatch can be validated end-to-end with a minimal `city.toml` before adding full controller lifecycle management. This reduces integration risk by building the shared surface first.

### Epic 2: Pool-Based Worker Dispatch (P0 — build first)

**Goal**: Replace direct `dispatch_worker.py` SDK calls with bead creation + pool-based claiming. This is the foundational integration surface that everything else builds on.

**Acceptance Criteria**:
- AC-2.1: `pipeline_runner._dispatch_agent_sdk()` (line 2008) checks `dispatch_mode` node attribute; when `"pool"`, creates a bead via `pool_dispatch.py` instead of calling `_dispatch_via_sdk()`
- AC-2.2: Bead is created with labels: `pipeline:{id}`, `node:{node_id}`, `pool:{worker_type}-worker`; bead metadata includes `signal_dir` (absolute path), `node_id`, and prompt file path
- AC-2.3: Pool agents discover work via `work_query = "bd ready --label=pool:{type}-worker --unassigned --limit=1"` and claim atomically via `bd update {id} --claim`
- AC-2.4: Worker execution produces both a signal file (`{node_id}.json` in `$PIPELINE_SIGNAL_DIR`) and `bd close {bead_id}` on completion
- AC-2.5: pipeline_runner detects signal files and transitions nodes identically to current behavior (no changes to `_process_signals()` or `_apply_signal()`)
- AC-2.6: Fallback to direct `_dispatch_via_sdk()` when `dispatch_mode` is absent or GasCity unavailable (`gascity_bridge.is_healthy()` returns False)
- AC-2.7: `gc poke` is called after bead creation to trigger immediate controller reconcile (avoids 30s delay)
- AC-2.8: Prompt content stored in a temp file; bead metadata contains file path (not raw prompt) to avoid bead metadata size limits

**Key Files**:
- `cobuilder/engine/pipeline_runner.py` — add `dispatch_mode` check in `_dispatch_agent_sdk()` (line ~2008); wire `gascity_bridge.is_healthy()` guard
- `cobuilder/engine/dispatch_worker.py` — extract `build_worker_prompt()` as standalone function (reused by pool agents)
- New: `cobuilder/engine/pool_dispatch.py` — bead creation with pool labels, `gc poke` after creation
- New: `cobuilder/engine/gascity_bridge.py` — `GasCityBridge.is_healthy()` (checks `gc status`), `create_pool_bead()`, `poke()`
- New: `cobuilder/prompts/pool-worker.md.tmpl` — Go `text/template` prompt for pool agents; reads `signal_dir` and `node_id` from bead metadata via `bd get {id}`
- New: `city.toml.j2` — Jinja2 template generating `city.toml` with `subprocess` provider, worker pool definitions

### Epic 1: GasCity Controller Adoption (P0 — build second)

**Goal**: Run a GasCity controller alongside pipeline_runner, managing CoBuilder worker agent lifecycles with full health patrol.

**Acceptance Criteria**:
- AC-1.1: `gc start` launches successfully with a generated `city.toml` defining `codergen-worker`, `research-worker`, and `refine-worker` pools with `provider = "subprocess"`
- AC-1.2: Controller crash recovery: detects agent process death and restarts within one reconcile tick (≤ 30s, typically seconds via `poke`)
- AC-1.3: Crash loop quarantine: workers that restart ≥ 5 times within 1h are quarantined; `max_restarts` and `restart_window` are configurable in `city.toml` `[daemon]` section
- AC-1.4: `gc stop` sends graceful shutdown to controller socket (`.gc/controller.sock`) and terminates all managed agents within `shutdown_timeout` (default 5s)
- AC-1.5: Single-instance enforcement via `flock(LOCK_EX|LOCK_NB)` on `.gc/controller.lock` — second `gc start` fails immediately
- AC-1.6: Controller reconciliation on restart: in-progress beads (status=open) are re-claimed by pool agents via normal work claiming lifecycle
- AC-1.7: `gascity_bridge.start_controller()` starts `gc` subprocess, waits for socket readiness; `stop_controller()` sends `"stop"` to socket and waits for process exit

**Key Files**:
- `cobuilder/engine/gascity_bridge.py` — add `start_controller(city_toml_path)`, `stop_controller()`, socket communication via `.gc/controller.sock`
- `cobuilder/engine/pipeline_runner.py` — call `gascity_bridge.start_controller()` in `PipelineRunner.__init__()` or `run()` startup; `stop_controller()` in `__del__` / shutdown
- `city.toml.j2` — full daemon config: `patrol_interval`, `max_restarts`, `restart_window`, `shutdown_timeout`, `wisp_gc_interval`, `wisp_ttl`, `drift_drain_timeout`

### Epic 3: Health Patrol Integration (P1)

**Goal**: Bridge GasCity's health events (crash, drift, idle) to CoBuilder's event bus, giving operators a unified view across both systems.

**Acceptance Criteria**:
- AC-3.1: Health Patrol monitors workers at `patrol_interval` (default 30s); idle workers (no `GetLastActivity()` response within `idle_timeout`) are terminated
- AC-3.2: SHA-256 drift detection (`CoreFingerprint()`) identifies workers running with stale config; stale workers are drained with reason `"config-drift"` and restarted
- AC-3.3: GasCity `.gc/events.jsonl` is tailed by `gascity_backend.py` and translated to CoBuilder event bus events (type prefix: `gascity.*`)
- AC-3.4: `pipeline-watch` TUI renders `gascity.*` health events alongside `node.*` and `pipeline.*` events with color-coded display
- AC-3.5: `gc doctor` output is captured and surfaced via `gascity_bridge.health_report()` for `pipeline-watch` diagnostics panel

**Key Files**:
- New: `cobuilder/engine/events/gascity_backend.py` — tail `.gc/events.jsonl`, translate to CoBuilder event types, publish to event bus
- `tools/pipeline-watch/` — add `gascity.*` event rendering with health-specific color codes
- `city.toml.j2` — health patrol section: `patrol_interval`, `idle_timeout` per agent pool

## 9. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Worker crash recovery time | Manual intervention (minutes-hours) | < 30 seconds automatic |
| Pipeline stall detection | Signal file timeout (configurable, minutes) | Health patrol ping (30s) |
| Worker utilization | Fixed 1:1 node-to-worker | Pool sharing across nodes |
| Controller resilience | None (pipeline_runner is single point) | flock + reconciliation |

## 10. Dependencies

- GasCity Go binary (`gc`) must be installed and on PATH — built from `github.com/gastownhall/gascity` (MIT)
- GasCity requires Go 1.22+ for building
- `jq` must be on PATH — used by pool `check` commands (`bd ready --json | jq length`)
- Beads CLI (`bd`) already shared between systems (Dolt-backed `bdstore` provider)
- Claude SDK (`claude_code_sdk`) for worker sessions (unchanged)
- Unix domain socket support (`.gc/controller.sock`) — standard on macOS/Linux; not Windows

## 11. Risks

| Risk | Root Cause | Likelihood | Impact | Mitigation |
|------|-----------|-----------|--------|------------|
| GasCity API instability (`internal/` package) | Active development SDK | Medium | High | Pin to specific commit hash; vendor if needed |
| Go↔Python bridge complexity | Two runtimes | Medium | Medium | Shell-out subprocess bridge (not FFI); `gc` CLI is the stable surface |
| Controller adds dispatch latency | 30s reconcile tick | Low | Medium | Call `gc poke` immediately after bead creation; typical latency drops to 1-2s |
| Two reconciliation loops conflict | Independent state machines | Medium | Low | Separate concerns clearly: CoBuilder=graph/node state; GasCity=agent process state |
| Pool agents can't locate signal dir | Path encoding in bead metadata | Low | Medium | Store `signal_dir` as bead metadata field; agents `bd get {id}` to retrieve |
| Crash tracker state lost on controller restart | Intentionally ephemeral (Erlang/OTP) | High | Low | Acceptable by design; use quarantine labels in beads for persistence if needed |
| Worker prompt exceeds bead metadata limits | Large prompt strings | Medium | Medium | Store prompt content in temp file; pass file path in bead metadata |

## 12. Relation to Other Initiatives

- **PRD-CLAWCODE-COBUILDER-001**: GasCity provides the agent runtime layer that claw-code's Rust ConversationRuntime also provides. Three-way integration (CoBuilder → GasCity → claw-code) is more composable than direct CoBuilder↔claw-code.
- **SD-PILOT-AUTONOMY-001**: Pilot (guardian.py) currently manages its own worker lifecycle. GasCity controller would subsume this responsibility.

## 13. Reference: `city.toml` for CoBuilder Worker Pools

Canonical configuration generated from `city.toml.j2`. All agents use `subprocess` provider.

```toml
[workspace]
name = "cobuilder"
provider = "subprocess"
max_active_sessions = 10

[daemon]
patrol_interval = "30s"
max_restarts = 5
restart_window = "1h"
shutdown_timeout = "5s"
wisp_gc_interval = "5m"
wisp_ttl = "24h"
drift_drain_timeout = "2m"

[beads]
provider = "bd"

[[agent]]
name = "codergen-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:codergen-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:codergen-worker"
idle_timeout = "4h"
prompt_template = "cobuilder/prompts/pool-worker.md.tmpl"
prompt_mode = "arg"
nudge = "Check your hook for pipeline work, then execute it."

[agent.pool]
min = 0
max = 5
check = "bd ready --json --label=pool:codergen-worker | jq length"

[[agent]]
name = "research-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:research-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:research-worker"
idle_timeout = "2h"
prompt_template = "cobuilder/prompts/pool-worker.md.tmpl"
prompt_mode = "arg"
nudge = "Check your hook for pipeline work, then execute it."

[agent.pool]
min = 0
max = 3
check = "bd ready --json --label=pool:research-worker | jq length"

[[agent]]
name = "refine-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:refine-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:refine-worker"
idle_timeout = "2h"
prompt_template = "cobuilder/prompts/pool-worker.md.tmpl"
prompt_mode = "arg"
nudge = "Check your hook for pipeline work, then execute it."

[agent.pool]
min = 0
max = 3
check = "bd ready --json --label=pool:refine-worker | jq length"
```

## Implementation Status

Research complete (v1.1.0). Architecture grounded in source-verified findings from `github.com/gastownhall/gascity`. Technical Spec and implementation pending.
