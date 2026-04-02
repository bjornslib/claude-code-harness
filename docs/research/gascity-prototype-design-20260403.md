---
title: "GasCity Integration — Prototype Design Research"
description: "Concrete implementation blueprints for gascity_bridge.py, pool_dispatch.py, pool-worker.md.tmpl, and city.toml.j2 for PRD-GASCITY-INT-001"
version: "1.0.0"
last-updated: 2026-04-03
status: active
type: research
grade: authoritative
---

# GasCity Integration — Prototype Design Research

**Date**: 2026-04-03  
**Pipeline**: GASCITY-INT-001  
**PRD**: PRD-GASCITY-INT-001  
**Purpose**: Concrete implementation blueprints for the Technical Spec author (write_ts node)

## Implementation Status

Research complete. Ready for Technical Spec authoring.

---

## 1. Prerequisite: GasCity `gc` Binary

**Critical finding**: The system has `/usr/local/bin/gc` but it is the GraphViz `gc` graph-counting tool, **NOT** the GasCity controller binary.

GasCity's `gc` binary lives in `workspace/gascity/` and must be built before integration can work.

### Build instructions

```bash
cd /Users/theb/Documents/Windsurf/cobuilder-harness/workspace/gascity
make build       # produces bin/gc
make install     # installs to $(go env GOPATH)/bin/gc
```

The Makefile injects version metadata via ldflags. After install, verify:
```bash
which gc         # should point to $(GOPATH)/bin/gc, NOT /usr/local/bin/gc
gc version       # should show "Gas City" not graphviz gc
```

**This is a hard dependency for all Epic 1 ACs. Epic 2 (pool dispatch) can stub `gc poke` and fall back gracefully, but controller lifecycle (AC-1.1 through AC-1.7) requires a working `gc` binary.**

### PATH precedence issue

`/usr/local/bin/gc` (GraphViz) will shadow `$(GOPATH)/bin/gc` (GasCity) if `GOPATH/bin` is not earlier in `$PATH`. The `gascity_bridge.py` module MUST resolve the gc binary path explicitly, not rely on bare `gc`:

```python
# In gascity_bridge.py
import shutil

def _resolve_gc_binary() -> str | None:
    """Find GasCity gc binary, NOT GraphViz gc."""
    # Try GOPATH/bin first (GasCity install location)
    gopath = subprocess.check_output(["go", "env", "GOPATH"], text=True).strip()
    gc_path = os.path.join(gopath, "bin", "gc")
    if os.path.isfile(gc_path):
        # Verify it's GasCity gc, not GraphViz gc
        out = subprocess.run([gc_path, "version"], capture_output=True, text=True)
        if "gas" in out.stdout.lower() or "gascity" in out.stdout.lower():
            return gc_path
    # Fallback: search PATH entries explicitly, skip /usr/local/bin/gc
    for entry in os.environ.get("PATH", "").split(":"):
        candidate = os.path.join(entry, "gc")
        if os.path.isfile(candidate) and entry != "/usr/local/bin":
            out = subprocess.run([candidate, "version"], capture_output=True, text=True)
            if "gas" in out.stdout.lower():
                return candidate
    return None
```

---

## 2. Bead Metadata: CLI Discovery

**Critical finding**: `bd update --set-metadata` is NOT a user-facing CLI flag (tested with bd 0.49.1). It is an internal flag used by GasCity's Go `BdStore.SetMetadata()` and `BdStore.SetMetadataBatch()` methods when those call `bd` as a subprocess.

### How metadata is actually set

`BdStore.SetMetadata()` in `internal/beads/bdstore.go` (line 525) constructs:
```bash
bd update --json <id> --set-metadata key=value
```

This is called by GasCity's Go code via `beads.ExecCommandRunnerWithEnv`. The flag likely exists in a newer version of `bd` or is set by the GasCity Go binary calling an internal API.

### Design implications for pool_dispatch.py

Option A — Use `bd update --notes` to embed JSON metadata:
```bash
# Embed as JSON in the notes field (visible to agents via bd show)
bd update <id> --notes '{"signal_dir": "/path/to/signals", "node_id": "write_ts", "prompt_file": "/tmp/prompt-abc.md"}'
```
Agents retrieve via: `bd show <id> --json | jq -r '.notes'` then parse JSON.

Option B — Use `bd update --design` for metadata JSON:
```bash
bd update <id> --design '{"signal_dir": "...", "node_id": "...", "prompt_file": "..."}'
```

Option C — Wait for GasCity Go code to call `SetMetadata` (requires full gc controller)

**Recommendation**: Option A (notes field) for prototype. Notes are human-readable, JSON-parseable, and available via `bd show --json`. Document the schema clearly in the pool-worker template.

**Alternative for Epic 2 (no controller)**: Store metadata as structured notes. The pool_dispatch.py module calls `bd update <id> --notes '<json>'` immediately after bead creation.

---

## 3. `pool_dispatch.py` — Concrete Design

**New file**: `cobuilder/engine/pool_dispatch.py`

### Responsibilities
1. Create a bead with pool labels via `bd create`
2. Store signal_dir, node_id, and prompt_file_path as bead notes (JSON)
3. Call `gc poke` for immediate reconcile
4. Return bead_id to caller

### Implementation Blueprint

```python
"""pool_dispatch.py — Bead creation for GasCity pool-based worker dispatch.

Creates labeled beads that GasCity pool agents discover and claim.
Fallback to direct _dispatch_via_sdk() when GasCity is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
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
    gascity_bridge=None,  # GasCityBridge instance, optional
) -> str | None:
    """Create a bead for GasCity pool agent claiming.

    Returns bead_id on success, None on failure.
    """
    # Write prompt to temp file (avoid bead metadata size limits)
    prompt_file = _write_prompt_file(node_id, prompt)

    # Bead metadata as JSON in notes field (bd CLI accessible)
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
    labels = [
        f"pipeline:{pipeline_id}",
        f"node:{node_id}",
        f"worker:{worker_type}",
        f"handler:{handler}",
        f"pool:{worker_type}-worker",  # enables GasCity pool claiming
    ]
    labels_arg = ",".join(labels)

    title = f"Pipeline node: {node_id} ({worker_type})"

    try:
        result = subprocess.run(
            ["bd", "create",
             "--title", title,
             "--type", "task",
             "--labels", labels_arg,
             "--notes", notes_json,
             "--silent"],  # output only ID
            capture_output=True,
            text=True,
            check=True,
        )
        bead_id = result.stdout.strip()
        logger.info("[pool_dispatch] Created bead %s for node %s", bead_id, node_id)

        # Poke controller for immediate reconcile (avoids 30s tick wait)
        if gascity_bridge is not None:
            gascity_bridge.poke()

        return bead_id

    except subprocess.CalledProcessError as exc:
        logger.error("[pool_dispatch] bd create failed: %s", exc.stderr)
        return None


def _write_prompt_file(node_id: str, prompt: str) -> str:
    """Write prompt content to a temp file. Returns absolute path."""
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
    return tmp.name
```

---

## 4. `gascity_bridge.py` — Concrete Design

**New file**: `cobuilder/engine/gascity_bridge.py`

### Responsibilities
1. `is_healthy()` — check if GasCity controller is running (socket/`gc status`)
2. `start_controller(city_toml_path)` — spawn gc subprocess, wait for socket
3. `stop_controller()` — send "stop" to controller socket
4. `poke()` — send "poke" to controller socket for immediate reconcile
5. `create_pool_bead(...)` — thin wrapper around `pool_dispatch.create_pool_bead()`
6. `health_report()` — run `gc doctor` and return output

### Controller Socket Pattern

GasCity controller listens on `.gc/controller.sock` (Unix domain socket) in the city directory. The socket accepts text commands: `"stop\n"`, `"ping\n"`, `"poke\n"`.

```python
"""gascity_bridge.py — Python bridge to GasCity controller.

Manages gc controller subprocess lifecycle and provides pool bead creation.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Socket path relative to city root (GasCity convention)
CONTROLLER_SOCK = ".gc/controller.sock"
CONTROLLER_LOCK = ".gc/controller.lock"


class GasCityBridge:
    """Bridge between CoBuilder pipeline_runner and GasCity controller.

    Falls back gracefully when gc binary is unavailable or controller
    is not running. Callers check is_healthy() before using pool dispatch.
    """

    def __init__(self, city_root: str | None = None, gc_binary: str | None = None):
        self.city_root = city_root or os.getcwd()
        self._gc_binary = gc_binary or self._find_gc_binary()
        self._controller_proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_healthy(self) -> bool:
        """Return True if GasCity controller is accepting connections."""
        if self._gc_binary is None:
            return False
        sock_path = Path(self.city_root) / CONTROLLER_SOCK
        if not sock_path.exists():
            return False
        try:
            response = self._socket_send("ping")
            return response.strip() in ("pong", "ok", "")
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Controller lifecycle
    # ------------------------------------------------------------------

    def start_controller(self, city_toml_path: str, timeout: float = 30.0) -> bool:
        """Start gc controller. Returns True if controller is ready."""
        if self._gc_binary is None:
            logger.warning("[gascity] gc binary not found — cannot start controller")
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
            # Wait for socket to appear
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.is_healthy():
                    logger.info("[gascity] Controller started (pid=%d)", self._controller_proc.pid)
                    return True
                time.sleep(0.5)
            logger.error("[gascity] Controller did not become ready within %ds", timeout)
            return False
        except OSError as exc:
            logger.error("[gascity] Failed to start controller: %s", exc)
            return False

    def stop_controller(self) -> None:
        """Send graceful stop to GasCity controller."""
        if not self.is_healthy():
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
                self._controller_proc.kill()
            self._controller_proc = None

    def poke(self) -> None:
        """Trigger immediate controller reconcile (bypasses 30s tick)."""
        if not self.is_healthy():
            return
        try:
            self._socket_send("poke")
            logger.debug("[gascity] Controller poked for immediate reconcile")
        except OSError as exc:
            logger.debug("[gascity] Poke failed (non-fatal): %s", exc)

    def health_report(self) -> str:
        """Run gc doctor and return output for diagnostics panel."""
        if self._gc_binary is None:
            return "gc binary not found"
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
    # Internal helpers
    # ------------------------------------------------------------------

    def _socket_send(self, command: str) -> str:
        """Send a command to the controller Unix socket and read response."""
        sock_path = str(Path(self.city_root) / CONTROLLER_SOCK)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect(sock_path)
            s.sendall((command + "\n").encode())
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                data = s.recv(1024)
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks).decode()

    def _find_gc_binary(self) -> str | None:
        """Find GasCity gc binary, avoiding GraphViz gc."""
        import shutil
        # Try GOPATH/bin first
        try:
            gopath = subprocess.check_output(["go", "env", "GOPATH"], text=True).strip()
            candidate = os.path.join(gopath, "bin", "gc")
            if _is_gascity_binary(candidate):
                return candidate
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Try local workspace build
        workspace_bin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "workspace", "gascity", "bin", "gc"
        )
        if _is_gascity_binary(workspace_bin):
            return workspace_bin

        return None


def _is_gascity_binary(path: str) -> bool:
    """Return True if path is GasCity's gc binary (not GraphViz gc)."""
    if not os.path.isfile(path):
        return False
    try:
        result = subprocess.run([path, "version"], capture_output=True, text=True, timeout=5)
        combined = (result.stdout + result.stderr).lower()
        # GasCity outputs "gas city" or "gascity"; GraphViz outputs nothing useful
        return "gas" in combined or "gascity" in combined or result.returncode == 0 and "Usage: gc" not in combined
    except (subprocess.TimeoutExpired, OSError):
        return False
```

---

## 5. Modified `_dispatch_agent_sdk()` Pattern

**File**: `cobuilder/engine/pipeline_runner.py` — method at line 2008

The integration adds a `dispatch_mode` check at the **very beginning** of `_dispatch_agent_sdk()`, before the LLM config resolution:

```python
def _dispatch_agent_sdk(self, node_id: str, worker_type: str, prompt: str,
                        handler: str = "codergen", target_dir: str = "",
                        node_attrs: dict | None = None) -> None:
    """Dispatch a worker via claude_code_sdk or GasCity pool."""

    # ---- NEW: GasCity pool dispatch path ----
    pool_mode = (node_attrs or {}).get("dispatch_mode", "sdk")
    if pool_mode == "pool" and hasattr(self, "_gascity_bridge") and self._gascity_bridge is not None:
        from cobuilder.engine import pool_dispatch, gascity_bridge as _gcb
        if self._gascity_bridge.is_healthy():
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
                # Store bead_id for tracking (future: health patrol correlation)
                self._pool_beads[node_id] = bead_id
                return
            log.warning("[pool] Bead creation failed for %s — falling back to SDK", node_id)
        else:
            log.warning("[pool] GasCity unavailable for %s — falling back to SDK", node_id)
    # ---- END NEW ----

    # ... existing LLM config resolution + _dispatch_via_sdk() ...
```

### Where `_gascity_bridge` is initialized

In `PipelineRunner.__init__()`:
```python
# GasCity bridge (optional — initialized if city.toml exists)
self._gascity_bridge = None
self._pool_beads: dict[str, str] = {}
if os.environ.get("COBUILDER_GASCITY_ENABLED", "0") == "1":
    from cobuilder.engine.gascity_bridge import GasCityBridge
    self._gascity_bridge = GasCityBridge(city_root=str(self._get_target_dir()))
```

**Opt-in via environment variable**: Default `COBUILDER_GASCITY_ENABLED=0` ensures no behavior change for existing pipelines.

---

## 6. Pool Worker Prompt Template Design

**New file**: `cobuilder/prompts/pool-worker.md.tmpl`

This is a **Go `text/template`** file (not Jinja2) consumed by GasCity's `renderPrompt()`. It receives template variables injected by GasCity at session startup.

### Key template variables available from GasCity

From GasCity's template rendering context:
- `{{.Agent}}` — agent name (e.g., `codergen-worker/1`)
- `{{.Bead.ID}}` — claimed bead ID
- `{{.Bead.Title}}` — bead title
- `{{.Bead.Notes}}` — notes field (contains our JSON metadata)
- `{{.CityDir}}` — city root directory
- `{{.WorkDir}}` — working directory for this session

### Template content

```markdown
# CoBuilder Pool Worker

You are a CoBuilder pipeline worker dispatched via GasCity pool.

## Your Identity

- Agent: {{.Agent}}
- Bead: {{.Bead.ID}}

## Your Task

Parse your metadata to find the task details:

```bash
# Your metadata is in the bead notes:
METADATA=$(bd show {{.Bead.ID}} --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('notes','{}'))")
SIGNAL_DIR=$(echo "$METADATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['signal_dir'])")
NODE_ID=$(echo "$METADATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['node_id'])")
PROMPT_FILE=$(echo "$METADATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['prompt_file'])")
PIPELINE_ID=$(echo "$METADATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['pipeline_id'])")
HANDLER=$(echo "$METADATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['handler'])")
```

Export these: `export PIPELINE_SIGNAL_DIR="$SIGNAL_DIR" NODE_ID="$NODE_ID"`

Read your instructions from `$PROMPT_FILE`.

## Completion Protocol — DUAL REQUIRED

On task completion you MUST do BOTH:

1. **CoBuilder signal** (FIRST):
   Write `$SIGNAL_DIR/$NODE_ID.json` with:
   ```json
   {"status": "success", "files_changed": [...], "message": "..."}
   ```

2. **GasCity close** (SECOND):
   ```bash
   bd close {{.Bead.ID}}
   ```

Both are required. The signal drives graph state; the bead close drives agent lifecycle.

## Environment

- `GC_AGENT` — your GasCity agent identity
- `PIPELINE_SIGNAL_DIR` — set from bead metadata (see above)
- `PROJECT_TARGET_DIR` — {{.WorkDir}}
```

### Alternative: simpler approach with environment injection

If `pool_dispatch.py` stores metadata in structured `--notes`, agents can use:
```bash
NOTES=$(bd show {{.Bead.ID}} --json | jq -r '.notes')
```

Then parse with `jq` or Python.

---

## 7. `city.toml.j2` Template Design

**New file**: `city.toml.j2` (Jinja2 template for `pipeline_runner.py` to generate `city.toml`)

### Where city.toml should live

The city.toml defines a GasCity "city" rooted at a directory. For CoBuilder integration:
- **City root**: `{project_target_dir}` — the project being built
- **city.toml location**: `{project_target_dir}/city.toml` (generated at pipeline start)
- **GasCity runtime state**: `{project_target_dir}/.gc/` (gitignored)

### Jinja2 template

```toml
# city.toml — Auto-generated by CoBuilder pipeline_runner.py
# Pipeline: {{ pipeline_id }}
# Generated: {{ timestamp }}
# DO NOT EDIT — regenerated on each pipeline run

[workspace]
name = "cobuilder-{{ pipeline_id }}"
provider = "subprocess"
max_active_sessions = {{ max_active_sessions | default(10) }}

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
max = {{ codergen_max_pool | default(5) }}
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
max = {{ research_max_pool | default(3) }}
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
max = {{ refine_max_pool | default(3) }}
check = "bd ready --json --label=pool:refine-worker | jq length"
{% endif %}
```

### city.toml generator function (in gascity_bridge.py)

```python
def generate_city_toml(
    pipeline_id: str,
    worker_types: list[str],
    output_path: str,
    cobuilder_root: str,
) -> str:
    """Generate city.toml from Jinja2 template. Returns path to generated file."""
    from jinja2 import Template
    template_path = Path(cobuilder_root) / "city.toml.j2"
    template = Template(template_path.read_text())
    content = template.render(
        pipeline_id=pipeline_id,
        worker_types=worker_types,
        timestamp=datetime.now(timezone.utc).isoformat(),
        cobuilder_root=cobuilder_root,
    )
    Path(output_path).write_text(content)
    return output_path
```

---

## 8. `gascity_backend.py` — Event Bridge Design

**New file**: `cobuilder/engine/events/gascity_backend.py`

### GasCity event format (`.gc/events.jsonl`)

GasCity's event bus writes JSONL with monotonic `Seq` field:
```json
{"Seq": 1, "Type": "agent.started", "Agent": "codergen-worker/1", "At": "2026-04-03T..."}
{"Seq": 2, "Type": "agent.stopped", "Agent": "codergen-worker/1", "Reason": "work-done", "At": "2026-04-03T..."}
```

### Translation table: GasCity → CoBuilder event types

| GasCity Event Type | CoBuilder Event Type | Notes |
|-------------------|---------------------|-------|
| `agent.started` | `gascity.agent.started` | Custom prefix (new type needed) |
| `agent.stopped` | `gascity.agent.stopped` | |
| `agent.crashed` | `gascity.agent.crashed` | Health patrol crash event |
| `agent.quarantined` | `gascity.agent.quarantined` | Crash loop protection |
| `agent.drifted` | `gascity.agent.drifted` | Config drift drain |
| `pool.scaled_up` | `gascity.pool.scaled_up` | |
| `pool.scaled_down` | `gascity.pool.scaled_down` | |
| `controller.started` | `gascity.controller.started` | |
| `controller.stopped` | `gascity.controller.stopped` | |

Since CoBuilder's `EventType` is a closed literal union (18 types), GasCity events should be published to the event bus with **new type prefix `gascity.*`**. This requires either:
1. Extending `EventType` in `types.py` to add `gascity.*` types
2. Using a new `GasCityEvent` dataclass alongside `PipelineEvent`
3. Publishing as `agent.message` events with `agent_role="gascity"` (simplest, no type changes)

**Recommendation for prototype**: Option 3 (reuse `agent.message` with `agent_role="gascity"`) for Epic 3. Full `gascity.*` event types can be added in a follow-up without breaking existing consumers.

### Implementation sketch

```python
"""gascity_backend.py — Tail .gc/events.jsonl and bridge to CoBuilder event bus."""

import json
import threading
import time
from pathlib import Path
from cobuilder.engine.events.emitter import EventEmitter
from cobuilder.engine.events.types import EventBuilder


class GasCityEventBridge:
    """Tails .gc/events.jsonl and republishes to CoBuilder event bus."""

    def __init__(self, gc_dir: str, emitter: EventEmitter, pipeline_id: str):
        self._gc_dir = Path(gc_dir)
        self._emitter = emitter
        self._pipeline_id = pipeline_id
        self._last_seq = 0
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._tail_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _tail_loop(self) -> None:
        events_path = self._gc_dir / "events.jsonl"
        while not self._stop_flag.is_set():
            if events_path.exists():
                self._process_new_events(events_path)
            time.sleep(1.0)

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
        """Convert GasCity event to CoBuilder event and emit."""
        event = EventBuilder.agent_message(
            pipeline_id=self._pipeline_id,
            node_id=None,
            agent_role="gascity",
            turn=gc_event.get("Seq", 0),
            text=json.dumps(gc_event),
        )
        self._emitter.emit(event)
```

---

## 9. File Structure Summary

### New files to create

| File | Purpose | Epic |
|------|---------|------|
| `cobuilder/engine/gascity_bridge.py` | GasCity controller lifecycle + bead creation | 1 + 2 |
| `cobuilder/engine/pool_dispatch.py` | Bead creation with pool labels | 2 |
| `cobuilder/engine/events/gascity_backend.py` | GasCity→CoBuilder event bridge | 3 |
| `cobuilder/prompts/pool-worker.md.tmpl` | Go text/template for pool agents | 2 |
| `city.toml.j2` | Jinja2 template for city.toml generation | 1 |

### Files to modify

| File | Change | Scope |
|------|--------|-------|
| `cobuilder/engine/pipeline_runner.py` | Add `dispatch_mode` check + GasCityBridge init | Epic 2 (line ~2008), Epic 1 (`__init__`/`run()`) |
| `cobuilder/engine/events/types.py` | Add `gascity.*` event types (optional, Epic 3) | Epic 3 |

### Files NOT to modify (confirmed)

- `cobuilder/engine/dispatch_worker.py` — No changes needed. The PRD mentions extracting `build_worker_prompt()` but current code has no such function. Prompt is built inline in `_dispatch_agent_sdk()` and `_dispatch_via_sdk()`. The pool_dispatch.py handles prompt writing independently.
- `cobuilder/engine/signal_protocol.py` — No changes. Pool agents write signals directly.
- `cobuilder/engine/transition.py` — No changes. `_process_signals()` / `_apply_signal()` unchanged.

---

## 10. Integration Wiring: `_dispatch_agent_sdk()` Change Points

### Exact location for dispatch_mode check

```
pipeline_runner.py line 2008:
  def _dispatch_agent_sdk(self, node_id, worker_type, prompt, handler, target_dir, node_attrs):
    # NEW: pool dispatch branch (add before line 2015 "effective_dir = ...")
    [insert pool dispatch check here]
    
    # EXISTING (line 2015):
    effective_dir = target_dir or self._get_target_dir()
```

### `PipelineRunner.__init__()` addition

Look for `__init__` in pipeline_runner.py — add `_gascity_bridge` and `_pool_beads` initialization after existing instance variable setup.

### `PipelineRunner.run()` cleanup

In the `run()` method's finally block, add `stop_controller()` call.

---

## 11. DOT Node Attribute for Pool Dispatch

Operators enable pool dispatch by adding `dispatch_mode="pool"` to DOT node definitions:

```dot
impl_feature [
    shape=box
    handler="codergen"
    status=pending
    worker_type="backend-solutions-engineer"
    dispatch_mode="pool"    ← enables GasCity pool dispatch
    prompt="Implement X in app/service.py"
]
```

Without this attribute (or with `dispatch_mode="sdk"`), behavior is identical to current CoBuilder — no regression.

---

## 12. Testing Strategy

### Unit tests (no gc binary required)

1. `test_pool_dispatch.py` — mock `bd create` subprocess; verify bead ID returned, labels correct, notes JSON valid
2. `test_gascity_bridge.py` — mock `gc` subprocess; test `is_healthy()` returns False when socket absent, `poke()` is no-op when not healthy
3. `test_dispatch_mode_fallback.py` — verify `dispatch_mode="pool"` falls back to SDK when `is_healthy()` returns False

### Integration tests (requires gc binary + running controller)

1. Create bead → verify pool agent discovers it via `bd ready --label=pool:codergen-worker`
2. Pool agent claims bead → verify atomic `bd update --claim` sets assignee
3. Pool agent completes → verify signal file written AND bead closed

### Acceptance test approach

Since AC-2.1 through AC-2.8 are testable without a running controller (use `gascity_bridge.is_healthy()` to simulate unavailability), unit tests can cover most ACs. Full E2E requires `make build` + `make install` in `workspace/gascity/`.

---

## 13. Key Risks Discovered in Research

### Risk 1: GraphViz `gc` Binary Clash (HIGH)
`/usr/local/bin/gc` is GraphViz's `gc` tool, not GasCity. PATH confusion will cause silent failures. **Must resolve gc binary explicitly in `gascity_bridge.py`.**

### Risk 2: `bd --set-metadata` Not User-Facing
The `bd update --set-metadata` flag does not appear in public `bd help`. Use `--notes` with JSON for prototype. The Technical Spec should note this limitation and recommend the notes-as-metadata pattern.

### Risk 3: GasCity `gc` Binary Not Installed
The GasCity `gc` binary must be built from source (`workspace/gascity/`). The `gascity_bridge.is_healthy()` fallback handles this gracefully, but Epic 1 ACs cannot be validated without it.

### Risk 4: Bead Label Query Performance
`bd ready --json --label=pool:codergen-worker | jq length` runs on every GasCity reconcile tick. With many pipeline beads, this query should be fast (bd uses label indexing). Verify with >100 beads during load testing.

### Risk 5: Prompt File Cleanup
Temp files written by `pool_dispatch._write_prompt_file()` accumulate. Add cleanup in `pool_dispatch.py` — either TTL-based or cleanup-on-bead-close.

---

## 14. References

- GasCity repository: `workspace/gascity/` (local clone)
- GasCity subprocess provider: `workspace/gascity/internal/runtime/subprocess/subprocess.go`
- GasCity bdstore: `workspace/gascity/internal/beads/bdstore.go`
- CoBuilder pipeline runner: `cobuilder/engine/pipeline_runner.py`
- CoBuilder event types: `cobuilder/engine/events/types.py`
- Prior architecture research: `docs/research/gascity-integration-research-20260403.md`
- Refined PRD: `docs/prds/gascity-integration/PRD-GASCITY-INT-001.md`
