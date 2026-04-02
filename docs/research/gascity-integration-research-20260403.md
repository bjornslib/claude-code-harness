---
title: "GasCity Integration Research — Technical Deep Dive"
description: "Detailed technical research on GasCity SDK primitives, CoBuilder dispatch path, and integration architecture for PRD-GASCITY-INT-001"
version: "1.0.0"
last-updated: 2026-04-03
status: active
type: research
grade: authoritative
---

# GasCity Integration Research — Technical Deep Dive

**Date**: 2026-04-03  
**Pipeline**: GASCITY-INT-001  
**PRD**: PRD-GASCITY-INT-001  
**Purpose**: Deep technical research to inform SD and implementation

## Implementation Status

Research complete. Findings ready for Business Spec refinement and Technical Spec authoring.

---

## 1. GasCity Repository Structure

Source: `github.com/gastownhall/gascity` (MIT licensed, public)

```
gascity/
├── cmd/gc/              # CLI (~150 files) — all gc subcommands as cmd_*.go
├── internal/
│   ├── agent/           # Session naming, startup hints
│   ├── beads/           # Store interface + implementations (bdstore, filestore, memstore, exec)
│   ├── config/          # city.toml parsing, pack composition, patch/override resolution
│   ├── convergence/     # Bounded iterative refinement loops
│   ├── dispatch/        # Work routing helpers
│   ├── events/          # Append-only event bus (JSONL)
│   ├── formula/         # Formula compilation, types, graph, retry, conditions
│   ├── molecule/        # Molecule runtime
│   ├── nudgequeue/      # Nudge delivery queue
│   ├── orders/          # Order discovery and gate evaluation
│   ├── runtime/         # Provider interface + implementations (tmux, subprocess, k8s, acp, hybrid, fake)
│   ├── session/         # Session metadata and wait conditions
│   ├── supervisor/      # Machine-wide supervisor process
│   ├── telemetry/       # Dispatch telemetry recording
│   └── workdir/         # Working directory management
├── docs/                # Mintlify user docs (reference/config.md, reference/formula.md, reference/cli.md)
├── engdocs/
│   ├── architecture/    # controller.md, health-patrol.md, agent-protocol.md, dispatch.md, formulas.md, beads.md
│   └── design/          # agent-pools.md, idle-session-sleep.md, named-configured-sessions.md
├── examples/            # gastown/, swarm/, lifecycle/, hyperscale/, bd/ — each with city.toml + packs/
└── test/                # Integration tests (build tag: //go:build integration)
```

---

## 2. GasCity Five Irreducible Primitives

### Primitive 1: Agent Protocol (`internal/runtime/runtime.go`)

```go
type Provider interface {
    Start(ctx context.Context, name string, cfg Config) error
    Stop(name string) error
    Interrupt(name string) error
    IsRunning(name string) bool
    IsAttached(name string) bool
    Attach(name string) error
    ProcessAlive(name string, processNames []string) bool
    Nudge(name string, content []ContentBlock) error
    GetLastActivity(name string) (time.Time, error)
    // ... + metadata, peek, copy, session operations
}
```

Implementations: `tmux` (production), `subprocess` (remote), `k8s`, `acp`, `hybrid`, `auto`, `Fake` (tests).

**Key insight for integration**: `subprocess` provider is the most relevant for CoBuilder — it launches `claude` processes without requiring tmux.

### Primitive 2: Task Store (`internal/beads/beads.go`)

```go
type Store interface {
    Create(ctx, bead) (Bead, error)
    Get(ctx, id) (Bead, error)
    Update(ctx, id, UpdateOpts) (Bead, error)
    Close(ctx, id) error
    List(ctx, query) ([]Bead, error)
    Ready(ctx, query) ([]Bead, error)
    Children(ctx, parentID) ([]Bead, error)
    ListByLabel(ctx, label) ([]Bead, error)
    MolCook(ctx, formulaName, vars) (Bead, error)
    // ...
}
```

Both CoBuilder and GasCity share `bd` (beads) as the fundamental work unit. This is the **primary integration surface**.

### Primitive 3: Event Bus (`internal/events/`)

```go
type Provider interface {
    Record(ctx, event) error
    List(ctx, query) ([]Event, error)
    Watch(ctx, fromSeq) (<-chan Event, error)
    Close() error
}
```

Stored as JSONL at `.gc/events.jsonl`. Events are immutable, monotonically increasing `Seq`.

### Primitive 4: Config (`internal/config/`)

`config.Load()` / `config.LoadWithIncludes()`. Progressive activation via section presence (Levels 0-8). Config IS the feature flag — no code changes needed to change behavior.

### Primitive 5: Prompt Templates

Go `text/template` in Markdown. Entry point: `renderPrompt()` in `cmd/gc/prompt.go`. All role behavior is user-supplied configuration — **Zero Framework Cognition** (ZFC).

---

## 3. GasCity Controller Architecture

### 3.1 Reconciliation Loop (`cmd/gc/controller.go`, `session_reconciler.go`)

The controller loop runs in `CityRuntime.run(ctx)` and fires on two triggers:

1. **Configurable ticker** — default 30s (`patrol_interval`)
2. **fsnotify filesystem events** — watches `city.toml` and pack directories (200ms debounce)

**Per-tick sequence:**
```
1. Check dirty flag → if config changed: tryReloadConfig()
2. buildAgents() — evaluate desired agent set; pool agents run scale_check in parallel goroutines
3. doReconcileAgents() — declarative convergence: running ↔ desired
4. Wisp GC — delete closed molecules older than wisp_ttl
5. Order dispatch — evaluate gate conditions for non-manual orders
```

**Controller socket** (`.gc/controller.sock`, Unix domain):
- Accepts: `"stop"`, `"ping"`, `"poke"`, `"control-dispatcher"`, `"converge:{json}"`
- `poke` triggers immediate reconcile without waiting for 30s tick

**Single-instance locking**: `flock(LOCK_EX|LOCK_NB)` on `.gc/controller.lock`. Second `gc start` fails immediately.

### 3.2 Four-State Session Machine

| State | Condition | Action |
|-------|-----------|--------|
| **not-running** | `sp.IsRunning()` returns false | → Start if in desired state |
| **healthy** | Running + `ProcessAlive()` + dependencies met + stable | → Continue; clear wake failures |
| **drifted** | Running but `CoreFingerprint()` hash mismatch | → Drain with reason `"config-drift"` (deferred if user attached) |
| **orphaned** | Bead exists, not in desired state, not in `configuredNames` | → Immediately drain or close |

Additional reconciler states: `asleep`, `drained`, `quarantined`, `creating`, `suspended`.

### 3.3 Config Hot-Reload

```go
func watchConfigDirs(dirs []string, dirty *atomic.Bool, stderr io.Writer) func()
// Uses fsnotify.NewWatcher(), 200ms debounce window

func tryReloadConfig(tomlPath, lockedCityName, cityRoot string) (*reloadResult, error)
// Returns: parsed cfg, provenance, revision SHA-256 hash
```

Workspace name changes are **rejected** — old config persists on error. All four trackers (crash, idle, wisp GC, orders) rebuild atomically on same tick.

---

## 4. GasCity Health Patrol

### 4.1 Crash Loop Protection (`cmd/gc/crash_tracker.go`)

```go
type memoryCrashTracker struct {
    mu            sync.Mutex
    maxRestarts   int           // default: 5
    restartWindow time.Duration // default: "1h"
    starts        map[string][]time.Time
}
```

- Quarantine triggers when restart count `>= maxRestarts` within `restartWindow`
- `prune()` removes timestamps older than window (bounded memory)
- State is **intentionally ephemeral** — resets on controller restart (Erlang/OTP pattern)
- Set `max_restarts <= 0` to disable quarantine

### 4.2 Idle Timeout (`cmd/gc/idle_tracker.go`)

```go
type memoryIdleTracker struct {
    mu       sync.Mutex
    timeouts map[string]time.Duration
}
// checkIdle() calls sp.GetLastActivity() → compares now.Sub(lastActivity) > timeout
// Idle trigger: sets sleep_reason="idle-timeout", marks for immediate re-wake same tick
```

If provider doesn't implement `GetLastActivity`, silently returns false (no-op).

### 4.3 SHA-256 Drift Detection (`internal/runtime/fingerprint.go`)

```go
ConfigFingerprint(cfg Config) string   // full behavioral hash
CoreFingerprint(cfg Config) string     // core fields → triggers drain+restart
LiveFingerprint(cfg Config) string     // SessionLive fields only → re-apply without restart
```

**Core fields hashed (restart-triggering)**: Command, env allowlist, FingerprintExtra (pool config), Nudge, PreStart, SessionSetup, SessionSetupScript, OverlayDir, CopyFiles.

**Env allowlist that triggers restart**: `GC_CITY*`, `GC_RIG*`, `GC_TEMPLATE`, `GC_ALIAS`, `GC_SKILLS_DIR`, `GC_BLESSED_BIN_DIR`, `GC_PUBLICATION_*`, `BEADS_DIR`. Excludes ephemeral: `GC_SESSION_*`, `GC_AGENT`, `GC_INSTANCE_TOKEN`.

Implementation: sorted keys + null-byte separators; slice entries separated by sentinel byte `0x01`.

---

## 5. Pool Agent & Work Claiming

### 5.1 Pool Agent Configuration

```toml
[[agent]]
name = "codergen-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:codergen-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:codergen-worker"
idle_timeout = "4h"
nudge = "Check your hook and mail, then act accordingly."

[agent.pool]
min = 0
max = 5                                # -1 = unlimited
check = "bd ready --json --label=pool:codergen-worker | jq length"
drain_timeout = "15m"
on_boot = ["setup.sh"]
```

The `pool.check` command output is an integer — controller scales up instances when > 0.

### 5.2 Pool Work Claiming Lifecycle

```
1. ROUTE: gc sling <pool-agent> <bead-id>
   → executes sling_query = "bd update <id> --label=pool:<name>"

2. DISCOVER: Pool agent hook fires → runs "gc hook"
   → calls EffectiveWorkQuery() = "bd ready --label=pool:<name> --unassigned --limit=1"

3. CLAIM (atomic): Agent runs "bd update <id> --claim"
   → compare-and-swap: open → in_progress; sets assignee

4. EXECUTE: Agent works; may call "bd update" for metadata

5. COMPLETE: Agent calls "bd close <id>"
   → status: closed; wisp autoclose hook fires
```

**GUPP principle**: "If you find work on your hook, YOU RUN IT." Hook having work IS the assignment — no confirmation.

**Label accumulation**: Labels never replace — each `bd update --label=X` appends. Immutable history.

### 5.3 Sling Dispatch (`cmd/gc/cmd_sling.go`)

```go
// For pool agents:
sling_query = "bd update {} --label=pool:<qualified-name>"
// {} is replaced with shell-quoted bead ID at dispatch time

// Idempotency guard: beads already routed to same target skip re-dispatch
// Cross-rig guard: blocks routing across rig boundaries unless --force
```

---

## 6. `city.toml` Full Configuration Reference

```toml
[workspace]
name = "cobuilder"
provider = "subprocess"                # default for all agents
max_active_sessions = 10
global_fragments = ["command-glossary"]
includes = ["packs/cobuilder"]

[daemon]
patrol_interval = "30s"
max_restarts = 5
restart_window = "1h"
shutdown_timeout = "5s"
wisp_gc_interval = "5m"
wisp_ttl = "24h"
drift_drain_timeout = "2m"

[beads]
provider = "bd"                        # bd (Dolt-backed), file, mem, exec

[session]
provider = "subprocess"
startup_timeout = "60s"

[[agent]]
name = "codergen-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:codergen-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:codergen-worker"
idle_timeout = "4h"
max_active_sessions = 3
prompt_template = "prompts/codergen-worker.md.tmpl"
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

[agent.pool]
min = 0
max = 3
check = "bd ready --json --label=pool:research-worker | jq length"
```

---

## 7. `gc` CLI Command Reference (Integration-Relevant)

### Controller Lifecycle
```bash
gc start [--foreground] [--dry-run]   # Start controller (default: supervisor mode)
gc stop                                # Graceful shutdown; delegates to controller socket
gc status [--json]                     # City overview: state, agent counts, pool instances
gc rig status <name>                   # Per-rig agent states
gc events [--filter] [--watch]         # Event log streaming
gc doctor                              # Workspace diagnostics with auto-repair
gc poke                                # Trigger immediate reconcile (via socket)
```

### Work Distribution
```bash
gc sling [target] <bead-id>           # Route bead to agent/pool
gc hook                                # Check for available work (executes work_query)
gc bd [--rig] <bd-args...>            # Route bd to correct rig directory
gc nudge <agent> <text>               # Send nudge to agent
```

### Session Management
```bash
gc session new/attach/close/suspend/wake/logs/nudge
gc runtime list/drain/status
```

---

## 8. CoBuilder Engine — Dispatch Integration Points

### 8.1 Dispatch Architecture (Current)

```
pipeline_runner.py
  PipelineRunner.run()                     # line 751
    _main_loop()                           # line 796
      _find_dispatchable_nodes()           # line 953 — identify ready nodes
      _dispatch_node()                     # line 1801 — route to handler
        _handle_worker()                   # line 1847 — queue dispatch
          ThreadPoolExecutor.submit()      # line 1889 — background thread
            _dispatch_agent_sdk()          # line 2008 — background execution
              _dispatch_via_sdk()          # line 2215 — ClaudeSDKClient
      _process_signals()                   # line 2908 — consume signal files
        _apply_signal()                    # line 3043 — state transitions
```

### 8.2 Handler Registry

```python
HANDLER_REGISTRY = {
    "start":      "_handle_noop",
    "noop":       "_handle_noop",
    "codergen":   "_handle_worker",
    "research":   "_handle_worker",
    "refine":     "_handle_worker",
    "tool":       "_handle_tool",
    "exit":       "_handle_exit",
    "gate":       "_handle_gate",
    "wait.human": "_handle_human",
    "wait.cobuilder": "_handle_gate",
    "acceptance-test-writer": "_handle_worker",
}
```

### 8.3 `_dispatch_agent_sdk()` — Primary Integration Point

**Location**: `pipeline_runner.py` line 2008

**Function signature**:
```python
def _dispatch_agent_sdk(self, node_id: str, worker_type: str, prompt: str,
                        handler: str = "codergen", target_dir: str = "",
                        node_attrs: dict | None = None) -> None:
```

**Runs in background thread** (spawned by `ThreadPoolExecutor`).

**Integration pattern** — add pool dispatch check before `_dispatch_via_sdk()`:
```python
pool_mode = node_attrs.get("dispatch_mode", "sdk")  # "sdk" | "pool"
if pool_mode == "pool":
    # Create bead with pool label instead of direct SDK dispatch
    # GasCity controller handles agent lifecycle from here
    return pool_dispatch.create_bead(node_id, worker_type, prompt, ...)
else:
    self._dispatch_via_sdk(...)  # existing path, unchanged
```

### 8.4 Signal File Format

```json
{
  "status": "success" | "failed" | "error",
  "files_changed": ["path/to/file.py"],
  "message": "Completion summary",
  "sd_hash": "<16-char SHA256>",
  "sd_path": "docs/sds/feature.md",
  "_seq": 1,
  "_ts": "2026-04-03T15:30:45.123456Z",
  "_pid": 12345
}
```

**Atomicity invariant**: All signal writes go to temp file → fsync → rename. Never partial writes.

### 8.5 Signal Directory Structure

```
.pipelines/pipelines/signals/{pipeline_id}/
  ├── {node_id}.json                    ← runner watches this
  ├── {node_id}-validation.json         ← separate suffix (avoids debounce race)
  ├── processed/
  │   └── {timestamp}-{node_id}.json   ← historical record
  └── guidance/
      └── {node_id}.txt                ← requeue feedback text
```

### 8.6 Node Status State Machine

```
pending → active → impl_complete → validated → accepted
                ↘→ failed
```

**Transition validation**: `apply_transition()` in `transition.py`, enforces `VALID_TRANSITIONS` dict. DOT file written atomically.

### 8.7 Worker Lifecycle Tracking

```python
class WorkerState(Enum):
    SUBMITTED, RUNNING, COMPLETED, FAILED, TIMED_OUT, CANCELLED

class WorkerInfo:
    future: Future
    state: WorkerState
    submitted_at: datetime
    exception: Exception | None
    process_handle: Any | None
```

**Dead worker detection** (`_check_worker_liveness()` line 2966):
- Checks completed futures without signal files
- Guard: skip if node already advanced past "active" (race prevention)
- Timeout: `WORKER_SIGNAL_TIMEOUT` (default 900s)

---

## 9. Integration Architecture Design

### 9.1 Proposed Three-Layer Architecture

```
Layer 1: CoBuilder Pipeline Engine (pipeline_runner.py)
   - DOT graph ordering + quality gates
   - Checkpoint/resume state machine
   - 18-type event bus (JSONL + Logfire + SignalBridge)
   - Validation agent dispatch + scoring
   
   ↓ Creates beads with pool labels (instead of direct AgentSDK calls)

Layer 2: GasCity Controller (gc controller)
   - Reconciliation loop (30s tick + fsnotify)
   - Pool agent lifecycle (start/stop/scale)
   - Health patrol (crash loop quarantine, drift detection, idle timeout)
   - Erlang/OTP supervision model
   
   ↓ Pool agents claim beads and execute

Layer 3: Claude SDK / subprocess Runtime
   - Worker executes pipeline node task
   - Writes signal file (CoBuilder protocol)
   - bd close (GasCity protocol)
```

### 9.2 Dual-Protocol Completion

Pool agents MUST emit BOTH protocols on completion:
1. **CoBuilder signal**: Write `{node_id}.json` to `$PIPELINE_SIGNAL_DIR/`
2. **GasCity close**: Run `bd close {bead_id}`

This enables both systems to track completion independently.

### 9.3 Bead Label Conventions

```
pipeline:{pipeline_id}            # pipeline identifier
node:{node_id}                    # DOT node identifier
worker:{worker_type}              # codergen | research | refine
handler:{handler}                 # maps to HANDLER_REGISTRY
pool:{worker_type}-worker         # enables GasCity pool claiming
signal_dir:{base64_encoded_path}  # where to write signal file
```

Signal dir encoding needed because path contains slashes. Base64 or percent-encoding.

### 9.4 GasCity Bridge Module Design

New file: `cobuilder/engine/gascity_bridge.py`

**Responsibilities**:
- Start/stop `gc controller` subprocess with appropriate `city.toml`
- Create beads with pool labels via `bd create` CLI
- Generate `city.toml` for CoBuilder worker pools
- Bridge GasCity event log to CoBuilder event bus
- Health check `gc status` for unified observability

**Interface (sketch)**:
```python
class GasCityBridge:
    def start_controller(self, city_toml_path: str) -> None: ...
    def stop_controller(self) -> None: ...
    def is_healthy(self) -> bool: ...
    def create_pool_bead(self, node_id: str, worker_type: str, 
                         prompt: str, signal_dir: str) -> str: ...  # returns bead_id
    def get_bead_status(self, bead_id: str) -> str: ...
```

### 9.5 Backward Compatibility

When GasCity controller is not running, `pool_dispatch.py` falls back to direct `dispatch_worker.py` call.

```python
def dispatch_node(node_id, worker_type, prompt, ...):
    if gascity_bridge.is_healthy():
        return gascity_bridge.create_pool_bead(...)
    else:
        logger.warning("GasCity unavailable — falling back to direct dispatch")
        return dispatch_agent_sdk_direct(...)
```

---

## 10. Key Design Decisions & Trade-offs

### 10.1 Why `subprocess` Provider (not `tmux`)

CoBuilder workers are headless pipeline workers, not interactive sessions. The `subprocess` provider in GasCity launches `claude` processes without requiring a tmux session. This matches how `dispatch_worker.py` currently works.

### 10.2 Controller Latency

Pool agents need to poll `bd ready` to discover work. This adds ~1s latency vs. direct dispatch. Mitigation: controller `poke` endpoint allows pipeline_runner to immediately trigger reconcile after creating a bead.

### 10.3 Two Reconciliation Loops

- **CoBuilder checkpoint**: Tracks DOT graph state (node status, edge conditions)
- **GasCity reconcile**: Tracks agent state (running/healthy/orphaned/drifted)

These are **complementary, not conflicting**. CoBuilder checkpoint handles graph topology; GasCity reconcile handles agent processes. They communicate via beads (shared store) and signal files.

### 10.4 Signal Dir in Bead Metadata

Pool agents need to know WHERE to write the signal file. Options:
- Pass via bead metadata (cleanest — agents can `bd get {id}` to retrieve)
- Pass via prompt (works but fragile)
- Pass via env (requires per-bead env injection)

Recommended: Store as bead metadata field `signal_dir` and include in pool agent prompt template.

### 10.5 Epic Prioritization

Based on PRD analysis:
1. **Epic 2 (Pool Dispatch)** before **Epic 1 (Controller)**: Pool dispatch can work without full health patrol. Build the integration surface first.
2. **Epic 1 (Controller)** adds health patrol once pool dispatch is validated.
3. **Epic 3 (Health Events)** — unified observability — is incremental improvement on top of working integration.

---

## 11. Implementation Risks & Mitigations

| Risk | Root Cause | Mitigation |
|------|-----------|------------|
| GasCity API instability | SDK is `internal/` | Pin to specific commit hash; vendor if needed |
| Go↔Python bridge complexity | Two runtimes | Shell-out subprocess bridge (not FFI); `gc` CLI is stable surface |
| Controller adds dispatch latency | 30s reconcile tick | Use `poke` endpoint for immediate reconcile after bead creation |
| Two reconciliation loops conflict | Independent state machines | Separate concerns: CoBuilder=graph state, GasCity=agent state |
| Pool agents can't find signal dir | Bead metadata encoding | Store as bead metadata; include in pool agent prompt |
| Crash tracker state lost on controller restart | Intentional ephemeral by design | Acceptable — ERL/OTP pattern; use quarantine label in beads for persistence |
| Worker bead metadata size limits | Prompt can be large | Store prompt in file; pass file path in bead metadata |

---

## 12. Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `cobuilder/engine/gascity_bridge.py` | Python↔Go bridge: start/stop controller, create pool beads |
| `cobuilder/engine/pool_dispatch.py` | Bead creation with pool labels; fallback to direct dispatch |
| `cobuilder/engine/events/gascity_backend.py` | Bridge GasCity event log to CoBuilder event bus |
| `city.toml.j2` | Jinja2 template for generating city.toml from pipeline context |
| `cobuilder/prompts/pool-worker.md.tmpl` | Go text/template: pool agent prompt that reads bead metadata |

### Files to Modify

| File | Change | Integration Point |
|------|--------|-------------------|
| `cobuilder/engine/pipeline_runner.py` | Add GasCity controller startup/shutdown; add pool dispatch path | `_dispatch_agent_sdk()` line 2008, `run()` startup, `__del__` cleanup |
| `cobuilder/engine/dispatch_worker.py` | Extract prompt building logic (reused by pool agents) | `build_worker_prompt()` → standalone function |

---

## 13. References

- GasCity repository: `https://github.com/gastownhall/gascity`
- GasCity engineering docs: `engdocs/architecture/controller.md`, `engdocs/architecture/health-patrol.md`
- CoBuilder pipeline runner: `cobuilder/engine/pipeline_runner.py`
- Prior research: `.claude/progress/gascity-architecture-research-20260403.md`
- PRD: `PRD-GASCITY-INT-001` (in SD above)
