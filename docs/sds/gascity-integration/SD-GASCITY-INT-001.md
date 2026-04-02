---
title: "GasCity Integration — Technical Spec for CoBuilder Pipeline Resilience"
description: "Technical specification for integrating GasCity's pull-based work allocation and health patrol with CoBuilder's deterministic DAG pipeline execution"
version: "1.0.0"
last-updated: 2026-04-03
status: active
type: sd
grade: authoritative
prd_id: PRD-GASCITY-INT-001
---

# SD-GASCITY-INT-001: GasCity Integration — Technical Spec

> **Scope**: Prototype integration — Epic 2 (Pool-Based Dispatch) before Epic 1 (Controller Adoption), with Epic 3 (Health Events) as optional follow-on. Builds the shared surface first to validate end-to-end flow before adding full controller lifecycle management.

## Implementation Status

Technical Spec complete (v1.0.0). Based on three prior research passes:

- `docs/research/gascity-integration-research-20260403.md` — deep source analysis of GasCity SDK primitives, CoBuilder dispatch path
- `docs/prds/gascity-integration/PRD-GASCITY-INT-001.md` — refined business requirements (v1.1.0)
- `docs/research/gascity-prototype-design-20260403.md` — concrete implementation blueprints, critical discoveries (gc binary clash, bd metadata API)

---

## 1. System Context

### 1.1 Current Architecture (Push-Based)

CoBuilder dispatches workers synchronously via `AgentSDK`. Each DOT node maps 1:1 to one worker subprocess. Failures are only detected via timeout (900s default).

```
pipeline_runner.py
  PipelineRunner._handle_worker()         # ThreadPoolExecutor.submit()
    _dispatch_agent_sdk()                 # line 2008 — target integration point
      effective_dir = target_dir or ...
      _resolve_llm_config()
      _dispatch_via_sdk()                 # line 2215 — ClaudeCodeSession.query()
        worker executes → writes {node_id}.json to signal_dir
  _check_worker_liveness()               # line 2966 — 900s WORKER_SIGNAL_TIMEOUT
  _process_signals()                      # line 2908 — consumes signal files
  _apply_signal()                         # node state transition
```

**Failure modes**:
- Worker crash → detected only via `WORKER_SIGNAL_TIMEOUT` (default 900s / 15 min)
- No automatic restart on crash
- Fixed 1:1 node-to-worker assignment — no pool sharing

### 1.2 Proposed Architecture (Pull-Based via GasCity)

The integration adds a pull-based dispatch path. CoBuilder's graph engine is unchanged; GasCity manages agent lifecycle.

```
pipeline_runner.py
  _dispatch_agent_sdk()                           # UNCHANGED signature
    if dispatch_mode == "pool" and bridge healthy:
      pool_dispatch.create_pool_bead()            # NEW: bead creation path
        bd create --title "..." --labels "pool:codergen-worker,..."
        bd update <id> --notes '{"signal_dir": ..., "node_id": ..., "prompt_file": ...}'
        gc poke                                   # immediate controller reconcile

GasCity Controller (gc start --foreground)
  doReconcileAgents()                             # 30s tick + fsnotify poke
    pool.check = "bd ready --json --label=pool:codergen-worker | jq length"
    → scale up pool agent if count > 0

Pool Agent (claude subprocess)
  [boot] read bead metadata → parse notes JSON
  [claim] bd update <bead_id> --claim             # atomic compare-and-swap
  [execute] read prompt_file → run task
  [signal] write $SIGNAL_DIR/$NODE_ID.json        # CoBuilder protocol
  [close] bd close <bead_id>                      # GasCity protocol

pipeline_runner.py
  _process_signals()                              # UNCHANGED — detects signal file
  _apply_signal()                                 # UNCHANGED — node transition
```

**Three-layer separation**:
```
CoBuilder Pipeline Engine  →  GasCity Controller  →  Claude SDK
(ordering + quality gates)    (allocation + health)   (LLM execution)
```

---

## 2. Critical Prerequisites

### 2.1 GasCity `gc` Binary — PATH Clash Warning

**CRITICAL**: `/usr/local/bin/gc` is the GraphViz graph-counting tool, **not** GasCity's controller. Bare `gc` in PATH will invoke the wrong binary silently.

```bash
# Build GasCity gc binary from source
cd workspace/gascity
make build       # produces bin/gc
make install     # installs to $(go env GOPATH)/bin/gc

# Verify (must show "gas" not graphviz)
$(go env GOPATH)/bin/gc version
```

All code invoking `gc` must resolve the binary path explicitly (see `gascity_bridge.py` Section 3).

### 2.2 Bead Metadata API Discovery

`bd update --set-metadata` is **NOT** a user-facing CLI flag in bd v0.49.1. It is an internal flag used by GasCity's Go `BdStore.SetMetadata()` method.

**Prototype approach**: Use `bd update --notes` with a JSON payload. The `notes` field is:
- Human-readable in `bd show` output
- Available as `--json` output: `bd show <id> --json | jq -r '.notes'`
- Large enough for all metadata we need (signal_dir, node_id, prompt_file, pipeline_id, handler, worker_type)

### 2.3 `dispatch_worker.py` — No Extraction Required

Research found: `build_worker_prompt()` does not exist as a standalone function in `dispatch_worker.py`. Prompt construction is inlined in `_dispatch_via_sdk()`. Pool dispatch handles prompt storage independently via `pool_dispatch._write_prompt_file()`. No changes to `dispatch_worker.py` required.

---

## 3. New Files

### 3.1 `cobuilder/engine/gascity_bridge.py`

Manages GasCity controller subprocess lifecycle. Provides `is_healthy()` guard used throughout the integration.

**Key design decisions**:
- `_find_gc_binary()` explicitly avoids GraphViz `/usr/local/bin/gc` via GOPATH-first resolution
- `is_healthy()` checks socket existence + ping response — safe to call frequently
- Opt-in via `COBUILDER_GASCITY_ENABLED=1` env var; all code paths fall back gracefully when `is_healthy()` returns False
- `city_root` defaults to `os.getcwd()` (project directory where `city.toml` lives)

```python
"""gascity_bridge.py — Python bridge to GasCity controller subprocess.

Manages gc controller lifecycle and provides the is_healthy() guard used
by pool_dispatch.py and pipeline_runner.py to enable/disable pool dispatch.

IMPORTANT: Do NOT use bare `gc` command. The /usr/local/bin/gc binary on
this system is GraphViz's gc tool, not GasCity. Always use _find_gc_binary().
"""
from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

logger = logging.getLogger(__name__)

# GasCity runtime directory relative to city root
CONTROLLER_SOCK = ".gc/controller.sock"
CONTROLLER_LOCK = ".gc/controller.lock"
EVENTS_JSONL = ".gc/events.jsonl"

# Template path relative to cobuilder root
CITY_TOML_TEMPLATE = "cobuilder/templates/city.toml.j2"


class GasCityBridge:
    """Bridge between CoBuilder pipeline_runner and GasCity controller.

    Falls back gracefully when gc binary unavailable or controller not running.
    Callers check is_healthy() before using pool dispatch paths.

    Usage:
        bridge = GasCityBridge(city_root="/path/to/project")
        if bridge.start_controller(city_toml_path):
            # pool dispatch enabled
        # In pipeline_runner finally block:
        bridge.stop_controller()
    """

    def __init__(
        self,
        city_root: str | None = None,
        gc_binary: str | None = None,
    ) -> None:
        self.city_root = city_root or os.getcwd()
        self._gc_binary = gc_binary or self._find_gc_binary()
        self._controller_proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Health check — safe to call frequently
    # ------------------------------------------------------------------

    def is_healthy(self) -> bool:
        """Return True if GasCity controller is accepting connections.

        Checks socket existence + responds to ping. Returns False gracefully
        when gc binary unavailable or controller not running.
        """
        if self._gc_binary is None:
            return False
        sock_path = Path(self.city_root) / CONTROLLER_SOCK
        if not sock_path.exists():
            return False
        try:
            response = self._socket_send("ping")
            return bool(response.strip())
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Controller lifecycle (Epic 1)
    # ------------------------------------------------------------------

    def start_controller(
        self, city_toml_path: str, timeout: float = 30.0
    ) -> bool:
        """Start gc controller subprocess. Returns True when ready.

        Blocks until controller socket appears or timeout expires.
        Safe to call if controller already running (returns True immediately).
        """
        if self._gc_binary is None:
            logger.warning(
                "[gascity] gc binary not found — controller unavailable. "
                "Build from workspace/gascity/ and ensure GOPATH/bin is in PATH."
            )
            return False
        if self.is_healthy():
            logger.info("[gascity] Controller already running")
            return True
        try:
            self._controller_proc = subprocess.Popen(
                [self._gc_binary, "start", "--foreground"],
                cwd=os.path.dirname(city_toml_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.is_healthy():
                    logger.info(
                        "[gascity] Controller started (pid=%d)",
                        self._controller_proc.pid,
                    )
                    return True
                time.sleep(0.5)
            logger.error(
                "[gascity] Controller did not become ready within %ds", timeout
            )
            return False
        except OSError as exc:
            logger.error("[gascity] Failed to start controller: %s", exc)
            return False

    def stop_controller(self) -> None:
        """Send graceful stop to GasCity controller via socket.

        Called in pipeline_runner.run() finally block.
        """
        if not self.is_healthy():
            if self._controller_proc:
                self._controller_proc.terminate()
                self._controller_proc = None
            return
        try:
            self._socket_send("stop")
            logger.info("[gascity] Stop signal sent to controller")
        except OSError as exc:
            logger.warning("[gascity] Failed to send stop: %s", exc)
        if self._controller_proc is not None:
            try:
                self._controller_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("[gascity] Controller did not stop cleanly; killing")
                self._controller_proc.kill()
            self._controller_proc = None

    def poke(self) -> None:
        """Trigger immediate controller reconcile (bypasses 30s tick).

        Called by pool_dispatch after bead creation to minimize dispatch latency.
        No-op when controller not running (non-fatal).
        """
        if not self.is_healthy():
            return
        try:
            self._socket_send("poke")
            logger.debug("[gascity] Controller poked for immediate reconcile")
        except OSError as exc:
            logger.debug("[gascity] Poke failed (non-fatal): %s", exc)

    def health_report(self) -> str:
        """Run gc doctor and return output string for diagnostics panel."""
        if self._gc_binary is None:
            return "gc binary not found — build from workspace/gascity/"
        try:
            result = subprocess.run(
                [self._gc_binary, "doctor"],
                cwd=self.city_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout + result.stderr
        except (subprocess.TimeoutExpired, OSError) as exc:
            return f"gc doctor failed: {exc}"

    # ------------------------------------------------------------------
    # city.toml generator
    # ------------------------------------------------------------------

    @staticmethod
    def generate_city_toml(
        pipeline_id: str,
        worker_types: list[str],
        output_path: str,
        cobuilder_root: str,
        pool_maxes: dict[str, int] | None = None,
    ) -> str:
        """Render city.toml from Jinja2 template. Returns path to generated file.

        Args:
            pipeline_id: Pipeline identifier (used in workspace name)
            worker_types: List of worker types to configure (codergen, research, refine)
            output_path: Absolute path where city.toml should be written
            cobuilder_root: Absolute path to CoBuilder harness root
            pool_maxes: Optional per-worker max pool sizes. Defaults: codergen=5, others=3

        Returns:
            output_path (absolute path to generated city.toml)
        """
        template_path = Path(cobuilder_root) / CITY_TOML_TEMPLATE
        if not template_path.exists():
            raise FileNotFoundError(
                f"city.toml.j2 template not found at {template_path}"
            )
        template = Template(template_path.read_text())
        pool_maxes = pool_maxes or {}
        content = template.render(
            pipeline_id=pipeline_id,
            worker_types=worker_types,
            timestamp=datetime.now(timezone.utc).isoformat(),
            cobuilder_root=cobuilder_root,
            codergen_max_pool=pool_maxes.get("codergen", 5),
            research_max_pool=pool_maxes.get("research", 3),
            refine_max_pool=pool_maxes.get("refine", 3),
        )
        Path(output_path).write_text(content)
        logger.info("[gascity] Generated city.toml at %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _socket_send(self, command: str) -> str:
        """Send a text command to the controller Unix socket. Returns response."""
        sock_path = str(Path(self.city_root) / CONTROLLER_SOCK)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect(sock_path)
            s.sendall((command + "\n").encode())
            s.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                data = s.recv(1024)
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks).decode()

    def _find_gc_binary(self) -> str | None:
        """Find GasCity gc binary. Explicitly avoids GraphViz /usr/local/bin/gc.

        Search order:
        1. $(go env GOPATH)/bin/gc — standard GasCity install location
        2. workspace/gascity/bin/gc — local workspace build
        3. PATH entries, excluding /usr/local/bin (known GraphViz location)
        """
        # 1. GOPATH/bin — preferred (installed via make install)
        try:
            gopath = subprocess.check_output(
                ["go", "env", "GOPATH"], text=True, timeout=5
            ).strip()
            candidate = os.path.join(gopath, "bin", "gc")
            if _is_gascity_binary(candidate):
                return candidate
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 2. Local workspace build
        workspace_bin = os.path.join(
            os.path.dirname(  # cobuilder-harness/
                os.path.dirname(  # cobuilder/engine/
                    os.path.dirname(__file__)
                )
            ),
            "workspace", "gascity", "bin", "gc",
        )
        if _is_gascity_binary(workspace_bin):
            return workspace_bin

        # 3. PATH search, skipping /usr/local/bin (GraphViz)
        for entry in os.environ.get("PATH", "").split(":"):
            if entry in ("/usr/local/bin", "/usr/bin"):
                continue  # GraphViz gc lives here
            candidate = os.path.join(entry, "gc")
            if _is_gascity_binary(candidate):
                return candidate

        logger.warning(
            "[gascity] gc binary not found. "
            "Run: cd workspace/gascity && make build && make install"
        )
        return None


def _is_gascity_binary(path: str) -> bool:
    """Return True if path points to GasCity's gc binary (not GraphViz gc)."""
    if not os.path.isfile(path):
        return False
    try:
        result = subprocess.run(
            [path, "version"], capture_output=True, text=True, timeout=5
        )
        combined = (result.stdout + result.stderr).lower()
        # GasCity outputs "gas city" or "gascity" in version string
        # GraphViz gc outputs nothing useful or shows graphviz branding
        return "gas" in combined and "graphviz" not in combined
    except (subprocess.TimeoutExpired, OSError):
        return False
```

### 3.2 `cobuilder/engine/pool_dispatch.py`

Creates labeled beads for GasCity pool agent claiming. Handles prompt file storage to avoid bead metadata size limits.

**Bead label conventions**:

| Label | Purpose |
|-------|---------|
| `pool:{worker_type}-worker` | GasCity pool claim routing — REQUIRED for pool discovery |
| `pipeline:{pipeline_id}` | Pipeline identifier for tracking |
| `node:{node_id}` | DOT node identifier for correlation |
| `worker:{worker_type}` | Worker type classification |
| `handler:{handler}` | Maps to HANDLER_REGISTRY (codergen, research, refine) |

**Metadata storage**: All runtime metadata stored as JSON in the `--notes` field (not `--metadata`, which is GasCity-internal):

```json
{
  "signal_dir": "/abs/path/to/.pipelines/pipelines/signals/PIPELINE-ID/",
  "node_id": "impl_feature",
  "prompt_file": "/tmp/cobuilder-prompt-impl_feature-abc123.md",
  "pipeline_id": "GASCITY-INT-001",
  "handler": "codergen",
  "worker_type": "backend-solutions-engineer"
}
```

```python
"""pool_dispatch.py — Bead creation for GasCity pool-based worker dispatch.

Creates labeled beads that GasCity pool agents discover and claim.
Prompt content stored in temp files to avoid bead metadata size limits.
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def create_pool_bead(
    node_id: str,
    worker_type: str,
    prompt: str,
    signal_dir: str,
    pipeline_id: str,
    handler: str = "codergen",
    gascity_bridge=None,  # GasCityBridge | None
) -> str | None:
    """Create a bead for GasCity pool agent claiming.

    Writes prompt to temp file (avoids bead size limits), stores all
    runtime metadata in bead notes as JSON, then pokes controller for
    immediate reconcile.

    Returns:
        bead_id (str) on success, None on failure.
        Callers should fall back to _dispatch_via_sdk() on None return.
    """
    # Write prompt to temp file — avoids bead metadata size limits
    prompt_file = _write_prompt_file(node_id, prompt)

    # All metadata as JSON in notes field (bd CLI accessible)
    metadata = {
        "signal_dir": signal_dir,
        "node_id": node_id,
        "prompt_file": prompt_file,
        "pipeline_id": pipeline_id,
        "handler": handler,
        "worker_type": worker_type,
    }
    notes_json = json.dumps(metadata)

    # Labels: pipeline identity + pool routing
    labels = ",".join([
        f"pool:{worker_type}-worker",   # GasCity pool claim routing
        f"pipeline:{pipeline_id}",
        f"node:{node_id}",
        f"worker:{worker_type}",
        f"handler:{handler}",
    ])

    title = f"[{pipeline_id}] {handler}: {node_id}"

    try:
        result = subprocess.run(
            [
                "bd", "create",
                "--title", title,
                "--type", "task",
                "--labels", labels,
                "--notes", notes_json,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        # bd create outputs the new bead ID on stdout (last token)
        bead_id = result.stdout.strip().split()[-1]
        logger.info(
            "[pool_dispatch] Created bead %s for node %s (worker=%s)",
            bead_id, node_id, worker_type,
        )

        # Poke controller for immediate reconcile (skips 30s tick)
        if gascity_bridge is not None:
            gascity_bridge.poke()

        return bead_id

    except subprocess.CalledProcessError as exc:
        logger.error(
            "[pool_dispatch] bd create failed for node %s: %s",
            node_id, exc.stderr,
        )
        return None
    except (ValueError, IndexError) as exc:
        logger.error(
            "[pool_dispatch] Failed to parse bead ID from bd output: %s", exc
        )
        return None


def _write_prompt_file(node_id: str, prompt: str) -> str:
    """Write prompt content to a temp file. Returns absolute path.

    Temp files accumulate during a pipeline run. Callers are responsible
    for cleanup (or use pipeline_runner._cleanup_pool_prompt_files()).
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        prefix=f"cobuilder-prompt-{node_id}-",
        suffix=".md",
        delete=False,
        encoding="utf-8",
    )
    tmp.write(prompt)
    tmp.flush()
    tmp.close()
    logger.debug("[pool_dispatch] Wrote prompt to %s (%d bytes)", tmp.name, len(prompt))
    return tmp.name
```

### 3.3 `cobuilder/templates/city.toml.j2`

Jinja2 template for generating `city.toml` per pipeline run. Generated file is written to `{project_target_dir}/city.toml`.

```toml
# city.toml — Auto-generated by CoBuilder GasCityBridge.generate_city_toml()
# Pipeline: {{ pipeline_id }}
# Generated: {{ timestamp }}
# DO NOT EDIT — regenerated on each pipeline run

[workspace]
name = "cobuilder-{{ pipeline_id }}"
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

[session]
provider = "subprocess"
startup_timeout = "120s"

{% if "codergen" in worker_types %}
[[agent]]
name = "codergen-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:codergen-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:codergen-worker"
idle_timeout = "4h"
prompt_template = "{{ cobuilder_root }}/cobuilder/prompts/pool-worker.md.tmpl"
prompt_mode = "arg"
nudge = "Check your hook for pipeline work, then execute it."

[agent.pool]
min = 0
max = {{ codergen_max_pool }}
check = "bd ready --json --label=pool:codergen-worker | jq length"
{% endif %}

{% if "research" in worker_types %}
[[agent]]
name = "research-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:research-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:research-worker"
idle_timeout = "2h"
prompt_template = "{{ cobuilder_root }}/cobuilder/prompts/pool-worker.md.tmpl"
prompt_mode = "arg"
nudge = "Check your hook for pipeline work, then execute it."

[agent.pool]
min = 0
max = {{ research_max_pool }}
check = "bd ready --json --label=pool:research-worker | jq length"
{% endif %}

{% if "refine" in worker_types %}
[[agent]]
name = "refine-worker"
provider = "subprocess"
work_query = "bd ready --label=pool:refine-worker --unassigned --limit=1"
sling_query = "bd update {} --label=pool:refine-worker"
idle_timeout = "2h"
prompt_template = "{{ cobuilder_root }}/cobuilder/prompts/pool-worker.md.tmpl"
prompt_mode = "arg"
nudge = "Check your hook for pipeline work, then execute it."

[agent.pool]
min = 0
max = {{ refine_max_pool }}
check = "bd ready --json --label=pool:refine-worker | jq length"
{% endif %}
```

### 3.4 `cobuilder/prompts/pool-worker.md.tmpl`

Go `text/template` file rendered by GasCity's `renderPrompt()` and passed to the `claude` subprocess as the `--prompt` argument.

GasCity template variables available:
- `{{.Agent}}` — agent name (e.g., `codergen-worker/1`)
- `{{.Bead.ID}}` — claimed bead ID
- `{{.Bead.Notes}}` — notes field (contains our JSON metadata)
- `{{.WorkDir}}` — working directory

```markdown
# CoBuilder Pool Worker

You are a CoBuilder pipeline worker dispatched via GasCity pool.

## Your Identity

- Agent: {{.Agent}}
- Bead: {{.Bead.ID}}

## Step 1: Parse Your Metadata

Run this to extract task details from the bead notes:

```bash
NOTES=$(bd show {{.Bead.ID}} --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('notes','{}'))")
SIGNAL_DIR=$(echo "$NOTES" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['signal_dir'])")
NODE_ID=$(echo "$NOTES" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['node_id'])")
PROMPT_FILE=$(echo "$NOTES" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['prompt_file'])")
PIPELINE_ID=$(echo "$NOTES" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['pipeline_id'])")
HANDLER=$(echo "$NOTES" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['handler'])")

export PIPELINE_SIGNAL_DIR="$SIGNAL_DIR"
export NODE_ID="$NODE_ID"
```

## Step 2: Read Your Task

```bash
cat "$PROMPT_FILE"
```

Execute the task described in `$PROMPT_FILE`. Follow all instructions in that file exactly.

## Step 3: Completion Protocol — BOTH REQUIRED

When your task is done, perform BOTH of these in order:

**1. Write CoBuilder signal (FIRST)**:

```bash
cat > "$SIGNAL_DIR/$NODE_ID.json" << 'EOF'
{
  "status": "success",
  "files_changed": ["path/to/changed/file.py"],
  "message": "Brief description of what was accomplished"
}
EOF
```

**2. Close bead (SECOND)**:

```bash
bd close {{.Bead.ID}}
```

Both are required. The signal file drives pipeline graph state. The bead close enables GasCity pool lifecycle management.

## If No Bead Available

If `bd show {{.Bead.ID}}` shows the bead is already claimed or closed, do nothing and exit cleanly. GasCity's atomic claim protocol prevents duplicate work.
```

### 3.5 `cobuilder/engine/events/gascity_backend.py`

(Epic 3 — Health Patrol Integration)

Tails `.gc/events.jsonl` and bridges GasCity health events to CoBuilder's event bus. Uses `agent.message` with `agent_role="gascity"` to avoid requiring new event types.

```python
"""gascity_backend.py — Bridge GasCity events to CoBuilder event bus.

Tails .gc/events.jsonl and republishes health events as agent.message
events with agent_role="gascity". Runs as a daemon thread alongside
the pipeline runner.

Event type mapping (GasCity → CoBuilder agent.message payload):
  agent.started    → {"gc_type": "agent.started", "agent": "codergen-worker/1"}
  agent.crashed    → {"gc_type": "agent.crashed",  "agent": "...", "reason": "..."}
  agent.quarantined → {"gc_type": "agent.quarantined", ...}
  pool.scaled_up   → {"gc_type": "pool.scaled_up", "pool": "codergen-worker"}
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class GasCityEventBridge:
    """Tails .gc/events.jsonl and republishes to CoBuilder event bus.

    Handles file growth correctly: re-reads from start on each poll tick,
    skipping events with Seq <= last_seq. This is safe because GasCity
    events.jsonl is append-only and Seq is monotonically increasing.
    """

    def __init__(self, gc_dir: str, emitter, pipeline_id: str) -> None:
        """
        Args:
            gc_dir: Path to .gc/ directory (contains events.jsonl)
            emitter: CoBuilder EventEmitter instance
            pipeline_id: Current pipeline ID for event attribution
        """
        self._gc_dir = Path(gc_dir)
        self._emitter = emitter
        self._pipeline_id = pipeline_id
        self._last_seq = 0
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()

    def start(self) -> None:
        """Start background tail thread."""
        self._thread = threading.Thread(
            target=self._tail_loop, daemon=True, name="gascity-event-bridge"
        )
        self._thread.start()
        logger.info("[gascity_backend] Event bridge started (tailing %s)", self._gc_dir / "events.jsonl")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop background thread."""
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _tail_loop(self) -> None:
        events_path = self._gc_dir / "events.jsonl"
        while not self._stop_flag.is_set():
            if events_path.exists():
                self._process_new_events(events_path)
            self._stop_flag.wait(timeout=1.0)

    def _process_new_events(self, path: Path) -> None:
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    seq = ev.get("Seq", 0)
                    if seq <= self._last_seq:
                        continue
                    self._last_seq = seq
                    self._publish(ev)
        except OSError:
            pass

    def _publish(self, gc_event: dict) -> None:
        """Convert GasCity event to CoBuilder agent.message event."""
        try:
            # Reuse agent.message with agent_role="gascity"
            # Full gascity.* event type extension is a follow-up task
            self._emitter.emit_agent_message(
                pipeline_id=self._pipeline_id,
                node_id=None,
                agent_role="gascity",
                turn=gc_event.get("Seq", 0),
                text=json.dumps(gc_event),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[gascity_backend] Emit failed (non-fatal): %s", exc)
```

---

## 4. Modified Files

### 4.1 `cobuilder/engine/pipeline_runner.py` — Integration Point

**Change 1**: Add `_gascity_bridge` and `_pool_beads` initialization in `__init__()`.

Integration is **opt-in** via `COBUILDER_GASCITY_ENABLED=1`. Default is `0` — existing pipelines are unchanged.

Add after existing instance variable setup (around line 530):

```python
# GasCity pool dispatch (opt-in via COBUILDER_GASCITY_ENABLED=1)
self._gascity_bridge: GasCityBridge | None = None
self._pool_beads: dict[str, str] = {}  # node_id -> bead_id
if os.environ.get("COBUILDER_GASCITY_ENABLED", "0") == "1":
    from cobuilder.engine.gascity_bridge import GasCityBridge
    self._gascity_bridge = GasCityBridge(city_root=self._get_target_dir())
```

**Change 2**: Add controller startup/shutdown in `run()`.

After observer setup and before `return self._main_loop()`:

```python
# Start GasCity controller if bridge configured
_city_toml_path = None
if self._gascity_bridge is not None:
    from cobuilder.engine.gascity_bridge import GasCityBridge as _GCB
    _city_toml_path = os.path.join(
        self._get_target_dir(),
        f"city-{self.pipeline_id}.toml"
    )
    worker_types = self._get_pipeline_worker_types()
    _GCB.generate_city_toml(
        pipeline_id=self.pipeline_id,
        worker_types=worker_types,
        output_path=_city_toml_path,
        cobuilder_root=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )
    started = self._gascity_bridge.start_controller(_city_toml_path)
    if started:
        log.info("[gascity] Controller started for pipeline %s", self.pipeline_id)
    else:
        log.warning("[gascity] Controller start failed — falling back to SDK dispatch")
        self._gascity_bridge = None
```

In the `finally` block:

```python
finally:
    for obs in observers:
        obs.stop()
        obs.join()
    if self._gascity_bridge is not None:
        self._gascity_bridge.stop_controller()
        self._cleanup_pool_prompt_files()
    if self._pipeline_span is not None:
        self._pipeline_span.__exit__(None, None, None)
```

**Change 3**: Add `dispatch_mode` check in `_dispatch_agent_sdk()` (line 2008).

Insert at the **top of the method**, before the `effective_dir` assignment:

```python
def _dispatch_agent_sdk(
    self, node_id: str, worker_type: str, prompt: str,
    handler: str = "codergen", target_dir: str = "",
    node_attrs: dict | None = None,
) -> None:
    """Dispatch a worker via claude_code_sdk or GasCity pool (if available).

    Pool dispatch path requires:
    1. dispatch_mode="pool" on the DOT node  OR  COBUILDER_GASCITY_ENABLED=1
       (when env var set, all nodes use pool dispatch)
    2. GasCity controller healthy (self._gascity_bridge.is_healthy())
    Falls back to direct SDK dispatch silently on any failure.
    """
    node_attrs = node_attrs or {}

    # ---- NEW: GasCity pool dispatch path ----
    pool_mode = node_attrs.get("dispatch_mode", "sdk")
    # Also enable pool mode globally when env var set (no per-node attribute needed)
    if os.environ.get("COBUILDER_GASCITY_ENABLED", "0") == "1":
        pool_mode = "pool"

    if pool_mode == "pool" and self._gascity_bridge is not None:
        if self._gascity_bridge.is_healthy():
            from cobuilder.engine import pool_dispatch
            bead_id = pool_dispatch.create_pool_bead(
                node_id=node_id,
                worker_type=worker_type,
                prompt=prompt,
                signal_dir=str(self.signal_dir),
                pipeline_id=self.pipeline_id,
                handler=handler,
                gascity_bridge=self._gascity_bridge,
            )
            if bead_id is not None:
                log.info("[pool] Dispatched node %s as bead %s", node_id, bead_id)
                self._pool_beads[node_id] = bead_id
                # Active worker metadata for liveness tracking
                if node_id not in self.active_workers:
                    self.active_workers[node_id] = {}
                self.active_workers[node_id]["dispatch_mode"] = "pool"
                self.active_workers[node_id]["bead_id"] = bead_id
                return  # Pool agent will write signal; _process_signals() picks it up unchanged
            log.warning(
                "[pool] Bead creation failed for %s — falling back to SDK dispatch",
                node_id,
            )
        else:
            log.debug(
                "[pool] GasCity unavailable for %s — falling back to SDK dispatch",
                node_id,
            )
    # ---- END NEW ----

    # Existing path (unchanged) ------------------------------------------------
    effective_dir = target_dir or self._get_target_dir()
    # ... rest of existing method ...
```

**Helper methods to add**:

```python
def _get_pipeline_worker_types(self) -> list[str]:
    """Extract unique worker types from all pending DOT nodes."""
    worker_types: set[str] = set()
    for node_id, attrs in self._graph.nodes(data=True):
        handler = attrs.get("handler", "codergen")
        if handler in ("codergen", "research", "refine"):
            worker_types.add(handler)
    return sorted(worker_types) or ["codergen"]


def _cleanup_pool_prompt_files(self) -> None:
    """Remove temp prompt files created by pool_dispatch._write_prompt_file()."""
    import glob as _glob, os as _os
    for node_id, bead_id in self._pool_beads.items():
        pattern = f"/tmp/cobuilder-prompt-{node_id}-*.md"
        for path in _glob.glob(pattern):
            try:
                _os.unlink(path)
                log.debug("[pool] Cleaned up prompt file %s", path)
            except OSError:
                pass
```

---

## 5. DOT Node Attribute for Pool Dispatch

Operators enable pool dispatch per-node by adding `dispatch_mode="pool"`:

```dot
impl_feature [
    shape=box
    handler="codergen"
    status=pending
    worker_type="backend-solutions-engineer"
    dispatch_mode="pool"
    prompt="Implement the auth service in app/auth.py"
]
```

Without this attribute (default `dispatch_mode="sdk"`), or when `COBUILDER_GASCITY_ENABLED=0` (default), behavior is identical to current CoBuilder. **Zero regression risk.**

For pipeline-wide pool dispatch (e.g., for prototype testing), set `COBUILDER_GASCITY_ENABLED=1` — no DOT file changes required.

---

## 6. Sequence Diagrams

### 6.1 Pool Dispatch — Normal Flow

```
pipeline_runner        pool_dispatch        gc_controller        pool_agent
      │                     │                    │                    │
      │_dispatch_agent_sdk()│                    │                    │
      │ dispatch_mode="pool"│                    │                    │
      │────────────────────>│                    │                    │
      │                     │ bd create          │                    │
      │                     │ --labels pool:...  │                    │
      │                     │ --notes <metadata> │                    │
      │                     │─────────────────────────────────────────┤
      │                     │ poke socket ──────>│                    │
      │<── bead_id ─────────│                    │                    │
      │                     │                    │                    │
      │  (returns; no wait) │                    │ reconcile tick     │
      │                     │                    │ pool.check > 0     │
      │                     │                    │────────────────────>
      │                     │                    │ start(subprocess)  │
      │                     │                    │                    │ [boot]
      │                     │                    │                    │ bd show bead_id
      │                     │                    │                    │ parse notes
      │                     │                    │                    │
      │                     │                    │                    │ bd update --claim
      │                     │                    │                    │ read prompt_file
      │                     │                    │                    │ [execute task]
      │                     │                    │                    │
      │                     │                    │                    │ write signal.json
      │                     │                    │                    │ bd close bead_id
      │                     │                    │                    │
      │ _process_signals()  │                    │                    │
      │ detects signal.json │                    │                    │
      │ _apply_signal()     │                    │                    │
      │ node → impl_complete│                    │                    │
```

### 6.2 GasCity Unavailable — Fallback to SDK

```
pipeline_runner        gascity_bridge       pool_dispatch
      │                     │                    │
      │ _dispatch_agent_sdk │                    │
      │ dispatch_mode="pool"│                    │
      │ is_healthy()? ─────>│                    │
      │<─── False ──────────│                    │
      │                     │                    │
      │ fallback to SDK     │                    │
      │ _dispatch_via_sdk() │                    │
      │ (existing path)     │                    │
```

### 6.3 Crash Recovery (Epic 1 — Health Patrol)

```
gc_controller              pool_agent (crashed)    new_pool_agent
      │                           │                     │
      │── patrol tick ─────────── │                     │
      │── ProcessAlive()? ─────── │                     │
      │<─ (dead process)          │                     │
      │                                                  │
      │── crashTracker.recordStart()                     │
      │── count < max_restarts (5)                       │
      │── Start(subprocess) ──────────────────────────── │
      │                                                   │ [boot]
      │                                                   │ bd ready --label=pool:...
      │                                                   │ bd update <same_bead_id> --claim
      │                                                   │ [re-execute task]
      │                                                   │ write signal.json
      │                                                   │ bd close bead_id
      │
      │ [if count >= max_restarts]
      │── drain("quarantined")
      │── bd update bead_id --labels "quarantined"
```

### 6.4 GasCity Controller Startup Sequence

```
pipeline_runner.run()    GasCityBridge       gc_process
      │                       │                   │
      │ generate_city_toml()  │                   │
      │──────────────────────>│                   │
      │                       │ Jinja2 render      │
      │                       │ write city.toml    │
      │ start_controller()    │                   │
      │──────────────────────>│                   │
      │                       │ Popen([gc, start, --foreground])
      │                       │──────────────────>│
      │                       │                   │ [gc init]
      │                       │                   │ acquire flock
      │                       │                   │ bind controller.sock
      │                       │                   │ ready
      │                       │ poll is_healthy() │
      │                       │ socket ping ──────>│
      │                       │<── pong ───────────│
      │                       │ return True        │
      │<─── True ─────────────│                   │
      │ _main_loop()          │                   │
      ...pipeline runs...
      │ [finally]             │                   │
      │ stop_controller()     │                   │
      │──────────────────────>│                   │
      │                       │ socket send "stop" │
      │                       │──────────────────>│
      │                       │                   │ graceful shutdown
```

---

## 7. Error Handling and Fallback Strategy

The integration is designed as **additive only**. Every pool dispatch failure falls back to existing SDK dispatch. No new failure modes are introduced.

| Failure Scenario | Detection | Fallback Behavior |
|-----------------|-----------|-------------------|
| `gc` binary not found | `_find_gc_binary()` returns None | `is_healthy()` → False; SDK dispatch |
| Controller not started | Socket missing | `is_healthy()` → False; SDK dispatch |
| `bd create` fails | CalledProcessError | `create_pool_bead()` returns None; SDK dispatch |
| Pool agent crashes | Health patrol (30s) | Auto-restart by controller (up to max_restarts) |
| Crash loop | max_restarts=5 exceeded | Quarantined; bead stays open; pipeline stalls |
| `gc poke` fails | OSError caught | Silent no-op; controller still reconciles at 30s tick |
| Controller socket timeout | OSError/TimeoutExpired | `is_healthy()` → False; next dispatch uses SDK |

---

## 8. Testing Strategy

### 8.1 Unit Tests (no `gc` binary required)

All tests mock `subprocess.run` and socket connections. Full isolation.

**File**: `cobuilder/tests/test_gascity_bridge.py`

| Test | What to Verify |
|------|----------------|
| `test_is_healthy_no_socket` | Returns False when `.gc/controller.sock` absent |
| `test_is_healthy_socket_present` | Returns True when socket present + ping returns pong |
| `test_find_gc_binary_graphviz_skipped` | Skips `/usr/local/bin/gc` (GraphViz) |
| `test_find_gc_binary_gopath` | Finds `$(GOPATH)/bin/gc` when gc version output has "gas" |
| `test_stop_controller_no_proc` | No-op when not running |
| `test_poke_no_op_when_unhealthy` | poke() is no-op when is_healthy() is False |

**File**: `cobuilder/tests/test_pool_dispatch.py`

| Test | What to Verify |
|------|----------------|
| `test_create_pool_bead_labels` | `bd create` called with correct comma-separated labels |
| `test_create_pool_bead_notes_json` | Notes contain valid JSON with all 6 metadata fields |
| `test_create_pool_bead_prompt_file` | Temp file written with prompt content |
| `test_create_pool_bead_returns_id` | Returns bead ID from `bd create` stdout |
| `test_create_pool_bead_pokes_bridge` | `gascity_bridge.poke()` called after bead creation |
| `test_create_pool_bead_fallback_on_failure` | Returns None when `bd create` fails |

**File**: `cobuilder/tests/test_pipeline_runner_pool_dispatch.py`

| Test | What to Verify |
|------|----------------|
| `test_dispatch_falls_back_when_bridge_none` | SDK path used when `_gascity_bridge=None` |
| `test_dispatch_falls_back_when_unhealthy` | SDK path used when `is_healthy()` returns False |
| `test_dispatch_uses_pool_when_healthy` | `create_pool_bead()` called when dispatch_mode="pool" |
| `test_dispatch_pool_mode_global_env` | Pool used when `COBUILDER_GASCITY_ENABLED=1` even without DOT attribute |
| `test_dispatch_sdk_fallback_on_bead_failure` | Falls back to SDK when `create_pool_bead()` returns None |

### 8.2 Integration Test (requires `gc` binary)

**Prerequisite**: Build GasCity from source:
```bash
cd workspace/gascity && make build && make install
```

**Test flow** (`cobuilder/tests/integration/test_gascity_pool_dispatch.py`):

1. Generate `city.toml` with `GasCityBridge.generate_city_toml()` using `["codergen"]` worker types
2. Start controller with `bridge.start_controller(city_toml_path)`
3. Create a test bead via `create_pool_bead()` with a simple prompt
4. Assert: `bd ready --label=pool:codergen-worker --unassigned --limit=1` returns the bead
5. Simulate pool agent claim: `bd update <bead_id> --claim`
6. Simulate signal write: write `{node_id}.json` to `signal_dir`
7. Simulate bead close: `bd close <bead_id>`
8. Assert: bead status is "closed"
9. Assert: signal file exists with `"status": "success"`
10. Stop controller: `bridge.stop_controller()`

### 8.3 Crash Recovery Test

1. Start pipeline runner with `COBUILDER_GASCITY_ENABLED=1` and a long-running codergen node
2. Identify pool agent subprocess PID from `gc status`
3. Kill pool agent subprocess: `kill -9 <pid>`
4. Wait up to 60s for GasCity health patrol to detect crash and restart
5. Assert: pipeline eventually transitions node to `impl_complete`
6. Assert: `gc status` shows no quarantined agents

### 8.4 Acceptance Criteria Coverage

| AC | Test Category | How to Verify |
|----|-------------|---------------|
| AC-2.1 dispatch_mode check | Unit: `test_pipeline_runner_pool_dispatch.py` | Mock bridge + verify create_pool_bead called |
| AC-2.2 Bead labels + metadata | Unit: `test_pool_dispatch.py` | Assert bd create args |
| AC-2.3 Pool claiming | Integration | bd ready query returns unclaimed bead |
| AC-2.4 Dual completion | Integration | Both signal file AND bead closed |
| AC-2.5 Signal detection unchanged | Unit (existing pipeline_runner tests) | _process_signals unchanged |
| AC-2.6 SDK fallback | Unit: `test_pipeline_runner_pool_dispatch.py` | is_healthy=False → SDK path |
| AC-2.7 gc poke after creation | Unit: `test_pool_dispatch.py` | bridge.poke() called |
| AC-2.8 Prompt in temp file | Unit: `test_pool_dispatch.py` | Notes contain file path not content |
| AC-1.1 gc start | Integration | Controller socket appears within 30s |
| AC-1.2 Crash recovery ≤30s | Crash test | Agent restarted within one reconcile tick |
| AC-1.3 Crash loop quarantine | Crash test (force loop) | After 5 restarts: quarantined label |
| AC-1.4 gc stop | Integration | Socket gone after stop_controller() |
| AC-1.5 Single instance | Integration | Second gc start fails with lock error |

---

## 9. Prototype Scope

The prototype validates end-to-end viability for a single pipeline node through the pool dispatch path.

### Included in Prototype

| Component | Status |
|-----------|--------|
| `gascity_bridge.py` — `is_healthy()`, `poke()`, `generate_city_toml()` | Required |
| `gascity_bridge.py` — `start_controller()`, `stop_controller()` | Required (Epic 1) |
| `pool_dispatch.py` — `create_pool_bead()`, `_write_prompt_file()` | Required (Epic 2) |
| `cobuilder/templates/city.toml.j2` | Required |
| `cobuilder/prompts/pool-worker.md.tmpl` | Required |
| `pipeline_runner.py` — `dispatch_mode` check + bridge init + run() wiring | Required |
| Unit tests (no gc binary) | Required |
| Single integration test on minimal pipeline | Required |

### Excluded from Prototype (post-prototype)

| Component | Why Deferred |
|-----------|-------------|
| `gascity_backend.py` — event bus bridge | Epic 3; no blocking dependency |
| `pipeline-watch` TUI GasCity event rendering | Depends on Epic 3 |
| `gc doctor` integration in diagnostics panel | Depends on Epic 3 |
| Production multi-pipeline city.toml | Hardcoded pipeline_id is acceptable for prototype |
| Crash tracker persistence across restarts | Intentionally ephemeral (Erlang/OTP design) |
| Kubernetes provider | Out of scope (subprocess only) |

---

## 10. File Change Summary

| File | Status | Epic | Notes |
|------|--------|------|-------|
| `cobuilder/engine/gascity_bridge.py` | **NEW** | 1 + 2 | Controller lifecycle + city.toml generator |
| `cobuilder/engine/pool_dispatch.py` | **NEW** | 2 | Bead creation with pool labels |
| `cobuilder/templates/city.toml.j2` | **NEW** | 1 | Jinja2 template for city.toml generation |
| `cobuilder/prompts/pool-worker.md.tmpl` | **NEW** | 2 | Go text/template for pool agent startup |
| `cobuilder/engine/events/gascity_backend.py` | **NEW** | 3 | Event bus bridge (Epic 3, post-prototype) |
| `cobuilder/engine/pipeline_runner.py` | **MODIFY** | 1 + 2 | 3 changes: `__init__`, `run()`, `_dispatch_agent_sdk()` |
| `cobuilder/engine/dispatch_worker.py` | **NO CHANGE** | — | Research confirmed: no `build_worker_prompt()` to extract |
| `cobuilder/tests/test_gascity_bridge.py` | **NEW** | 1 + 2 | Unit tests |
| `cobuilder/tests/test_pool_dispatch.py` | **NEW** | 2 | Unit tests |
| `cobuilder/tests/test_pipeline_runner_pool_dispatch.py` | **NEW** | 2 | Integration point tests |

---

## 11. Dependencies

| Dependency | Required For | Notes |
|------------|-------------|-------|
| `gc` binary (GasCity) | Controller lifecycle (Epic 1) | Build: `cd workspace/gascity && make build && make install`. Go 1.22+. Must be in `$(GOPATH)/bin` to avoid GraphViz clash. |
| `bd` CLI | Pool bead creation | Already present (beads system, v0.49.1+) |
| `jq` | `pool.check` command in `city.toml` | Common CLI tool; verify: `which jq` |
| `jinja2` Python package | `generate_city_toml()` | Already a CoBuilder dependency |
| `socket` (stdlib) | Controller socket ping/poke | Unix domain sockets; macOS/Linux only |
| `subprocess` (stdlib) | Bridge + pool dispatch | stdlib |
| Unix domain sockets | `.gc/controller.sock` | Not available on Windows (out of scope) |

---

## 12. Known Risks and Mitigations

| Risk | Source | Likelihood | Impact | Mitigation |
|------|--------|-----------|--------|------------|
| GraphViz `gc` binary clash | `/usr/local/bin/gc` shadows GasCity | High | High | `_find_gc_binary()` explicitly avoids `/usr/local/bin`; verifies version output contains "gas" |
| `bd --set-metadata` not user-facing | bd v0.49.1 internals | High | Medium | Use `--notes` with JSON payload (research-verified workaround) |
| GasCity binary not built | Build step required | Medium | Medium | `is_healthy()` returns False gracefully; falls back to SDK |
| Prompt file accumulation | Temp files not cleaned up | Medium | Low | `_cleanup_pool_prompt_files()` called in `run()` finally block |
| Bead metadata exceeds notes limit | Large prompts | Low | Medium | Prompt stored in temp file; only file path in notes |
| GasCity API changes | Active development SDK | Medium | High | Pin to specific git commit in `workspace/gascity/`; vendor if needed |
| Two-runtime bridge complexity | Python↔Go subprocess | Low | Medium | Shell-out only (no FFI); `gc` CLI is the stable surface |
| Pool check query performance | bd label query per reconcile tick | Low | Low | `bd ready --label=...` uses label indexing; acceptable for ≤1000 beads |

---

## 13. References

- GasCity source: `workspace/gascity/` (local clone, MIT license)
- Integration research: `docs/research/gascity-integration-research-20260403.md`
- Prototype design research: `docs/research/gascity-prototype-design-20260403.md`
- Business requirements: `docs/prds/gascity-integration/PRD-GASCITY-INT-001.md`
- Pipeline runner (integration target): `cobuilder/engine/pipeline_runner.py` line 2008 (`_dispatch_agent_sdk`)
- Event bus types: `cobuilder/engine/events/types.py`
- Existing dispatch worker: `cobuilder/engine/dispatch_worker.py`
