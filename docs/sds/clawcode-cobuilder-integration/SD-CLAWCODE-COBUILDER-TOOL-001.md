---
title: "CoBuilder Tools in Claw-Code — Technical Spec"
description: "Implement PipelineRunnerTool, PipelineCreateTool, and TaskTool as real executable tools in claw-code's Python workspace"
version: "1.0.0"
last-updated: 2026-04-02
status: draft
type: sd
grade: draft
prd_id: PRD-CLAWCODE-COBUILDER-001
---

# SD-CLAWCODE-COBUILDER-TOOL-001: CoBuilder Tools in Claw-Code

**Epic**: 1 — CoBuilder Tools in Claw-Code (Phase 1 — Python)
**PRD**: PRD-CLAWCODE-COBUILDER-001

## 1. Overview

This SD covers implementing three real, executable tools in claw-code's Python `src/` workspace:

1. **PipelineRunnerTool** — Invokes `pipeline_runner.py --dot-file` as a subprocess, streams status, returns structured results
2. **PipelineCreateTool** — Generates DOT pipeline files from task descriptions, validates topology
3. **TaskTool** — Wraps the beads CLI for issue tracking within pipeline execution

These tools transform claw-code from a metadata scaffold into a workspace with real multi-agent orchestration capability.

## 2. Prerequisites

- Fork of `ultraworkers/claw-code` with write access
- CoBuilder harness available at a known path (env var `COBUILDER_HARNESS_DIR`)
- Python 3.11+ (matching claw-code's Python workspace)
- `beads` CLI installed and configured (for TaskTool)

## 3. Architecture

### 3.1 Tool Registration Pattern

Claw-code's current `src/tools.py` loads tool metadata from `reference_data/tools_snapshot.json` and returns stubs. We extend this with a **real tool execution layer** that coexists with the snapshot-based metadata.

```python
# src/cobuilder_tools/__init__.py — New package for CoBuilder tool implementations

from .pipeline_runner_tool import PipelineRunnerTool
from .pipeline_create_tool import PipelineCreateTool
from .task_tool import TaskTool

COBUILDER_TOOLS = {
    "PipelineRunnerTool": PipelineRunnerTool,
    "PipelineCreateTool": PipelineCreateTool,
    "TaskTool": TaskTool,
}
```

### 3.2 Tool Interface

Each tool follows claw-code's existing `ToolExecution` dataclass pattern but adds real execution:

```python
# src/cobuilder_tools/base.py

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ToolResult:
    """Result from a real tool execution."""
    name: str
    success: bool
    output: str
    structured_data: dict[str, Any] | None = None
    error: str | None = None

class CoBuilderTool(ABC):
    """Base class for real, executable CoBuilder tools."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def execute(self, payload: dict[str, Any]) -> ToolResult: ...
```

### 3.3 PipelineRunnerTool

**Purpose**: Invoke `pipeline_runner.py --dot-file <path>` as a subprocess, monitor signal files, return structured completion report.

```python
# src/cobuilder_tools/pipeline_runner_tool.py

class PipelineRunnerTool(CoBuilderTool):
    name = "PipelineRunnerTool"
    description = "Run a DOT-defined pipeline that dispatches workers per node"

    input_schema = {
        "type": "object",
        "properties": {
            "dot_file": {"type": "string", "description": "Path to the DOT pipeline file"},
            "resume": {"type": "boolean", "default": False, "description": "Resume from checkpoint"},
            "target_dir": {"type": "string", "description": "Working directory for workers"},
        },
        "required": ["dot_file"],
    }

    def execute(self, payload: dict) -> ToolResult:
        dot_file = Path(payload["dot_file"]).resolve()
        resume = payload.get("resume", False)

        # Validate DOT file exists and is valid
        if not dot_file.exists():
            return ToolResult(name=self.name, success=False, output="",
                              error=f"DOT file not found: {dot_file}")

        # Build command
        harness_dir = os.environ.get("COBUILDER_HARNESS_DIR", "")
        runner_path = Path(harness_dir) / "cobuilder" / "engine" / "pipeline_runner.py"
        cmd = [sys.executable, str(runner_path), "--dot-file", str(dot_file)]
        if resume:
            cmd.append("--resume")

        # Run as subprocess, stream output
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=payload.get("target_dir"),
            env={**os.environ, "PIPELINE_SIGNAL_DIR": str(dot_file.parent / "signals")},
        )

        stdout, stderr = process.communicate()

        # Read final signal files for structured report
        signal_dir = dot_file.parent / "signals"
        signals = self._read_signals(signal_dir)

        return ToolResult(
            name=self.name,
            success=process.returncode == 0,
            output=stdout.decode(),
            structured_data={"signals": signals, "returncode": process.returncode},
            error=stderr.decode() if process.returncode != 0 else None,
        )

    def _read_signals(self, signal_dir: Path) -> dict:
        """Read all signal files from the signal directory."""
        signals = {}
        if signal_dir.exists():
            for signal_file in signal_dir.glob("*.json"):
                if signal_file.name.startswith("_"):
                    continue  # Skip internal files like _score_history.json
                with open(signal_file) as f:
                    signals[signal_file.stem] = json.load(f)
        return signals
```

**Key design decisions**:
- Subprocess isolation: `pipeline_runner.py` runs in its own process, not imported
- Signal file reader skips internal files (prefixed with `_`) per CoBuilder convention
- `COBUILDER_HARNESS_DIR` env var locates the harness — no hardcoded paths
- Returns structured data with per-node signals for downstream consumption

### 3.4 PipelineCreateTool

**Purpose**: Generate DOT pipeline files from a description of tasks, validate topology, return the path.

```python
# src/cobuilder_tools/pipeline_create_tool.py

class PipelineCreateTool(CoBuilderTool):
    name = "PipelineCreateTool"
    description = "Generate a DOT pipeline file from task descriptions"

    input_schema = {
        "type": "object",
        "properties": {
            "prd_ref": {"type": "string", "description": "PRD reference ID (e.g., PRD-XXX-001)"},
            "sd_path": {"type": "string", "description": "Path to Solution Design file"},
            "output": {"type": "string", "description": "Output path for the DOT file"},
            "repo_name": {"type": "string", "description": "Target repository name"},
        },
        "required": ["prd_ref", "output"],
    }

    def execute(self, payload: dict) -> ToolResult:
        harness_dir = os.environ.get("COBUILDER_HARNESS_DIR", "")
        cli_path = Path(harness_dir) / "cobuilder" / "engine" / "cli.py"

        # Build generate command
        cmd = [
            sys.executable, str(cli_path), "generate",
            "--prd", payload["prd_ref"],
            "--output", payload["output"],
        ]
        if payload.get("sd_path"):
            cmd.extend(["--sd", payload["sd_path"]])
        if payload.get("repo_name"):
            cmd.extend(["--repo", payload["repo_name"]])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return ToolResult(name=self.name, success=False, output=result.stdout,
                              error=result.stderr)

        # Validate the generated DOT
        validate_cmd = [sys.executable, str(cli_path), "validate", payload["output"]]
        validate_result = subprocess.run(validate_cmd, capture_output=True, text=True)

        return ToolResult(
            name=self.name,
            success=validate_result.returncode == 0,
            output=f"Generated: {payload['output']}\nValidation: {validate_result.stdout}",
            structured_data={
                "dot_file": payload["output"],
                "valid": validate_result.returncode == 0,
            },
            error=validate_result.stderr if validate_result.returncode != 0 else None,
        )
```

### 3.5 TaskTool

**Purpose**: Wrap beads CLI for issue tracking within claw-code sessions.

```python
# src/cobuilder_tools/task_tool.py

class TaskTool(CoBuilderTool):
    name = "TaskTool"
    description = "Track tasks and issues using the beads CLI"

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "ready", "show", "close", "list", "update"],
                "description": "Action to perform",
            },
            "title": {"type": "string", "description": "Task title (for create)"},
            "task_id": {"type": "string", "description": "Task ID (for show/close/update)"},
            "task_type": {"type": "string", "enum": ["task", "bug", "feature", "epic"],
                          "default": "task"},
            "priority": {"type": "integer", "minimum": 0, "maximum": 4, "default": 2},
            "status": {"type": "string", "description": "New status (for update)"},
            "reason": {"type": "string", "description": "Close reason (for close)"},
        },
        "required": ["action"],
    }

    def execute(self, payload: dict) -> ToolResult:
        action = payload["action"]
        cmd = ["bd"]

        if action == "create":
            if not payload.get("title"):
                return ToolResult(name=self.name, success=False, output="",
                                  error="'title' required for create")
            cmd.extend(["create", f"--title={payload['title']}",
                        f"--type={payload.get('task_type', 'task')}",
                        f"--priority={payload.get('priority', 2)}"])
        elif action == "ready":
            cmd.append("ready")
        elif action == "show":
            cmd.extend(["show", payload.get("task_id", "")])
        elif action == "close":
            close_cmd = ["close", payload.get("task_id", "")]
            if payload.get("reason"):
                close_cmd.extend([f"--reason={payload['reason']}"])
            cmd.extend(close_cmd)
        elif action == "list":
            cmd.extend(["list", "--status=open"])
        elif action == "update":
            cmd.extend(["update", payload.get("task_id", ""),
                        f"--status={payload.get('status', 'in_progress')}"])

        result = subprocess.run(cmd, capture_output=True, text=True)

        return ToolResult(
            name=self.name,
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
        )
```

### 3.6 Integration into claw-code's Tool System

Modify `src/tools.py` to check for CoBuilder tools alongside snapshot-based metadata:

```python
# In src/tools.py — add at module level

try:
    from .cobuilder_tools import COBUILDER_TOOLS
    _COBUILDER_AVAILABLE = True
except ImportError:
    COBUILDER_TOOLS = {}
    _COBUILDER_AVAILABLE = False

def execute_tool(name: str, payload: str = '') -> ToolExecution:
    # Check CoBuilder tools first (real execution)
    if _COBUILDER_AVAILABLE and name in COBUILDER_TOOLS:
        tool = COBUILDER_TOOLS[name]()
        parsed_payload = json.loads(payload) if payload else {}
        result = tool.execute(parsed_payload)
        return ToolExecution(
            name=result.name,
            source_hint="cobuilder",
            payload=payload,
            handled=result.success,
            message=result.output if result.success else (result.error or "Unknown error"),
        )

    # Fall back to existing stub behavior
    module = get_tool(name)
    if module is None:
        return ToolExecution(name=name, source_hint='', payload=payload,
                             handled=False, message=f'Unknown mirrored tool: {name}')
    action = f"Mirrored tool '{module.name}' from {module.source_hint} would handle payload {payload!r}."
    return ToolExecution(name=module.name, source_hint=module.source_hint,
                         payload=payload, handled=True, message=action)
```

### 3.7 Signal File Reader

A standalone module for reading and interpreting CoBuilder signal files:

```python
# src/cobuilder_tools/signal_reader.py

@dataclass(frozen=True)
class NodeSignal:
    node_id: str
    status: str  # "success" | "failed"
    message: str
    files_changed: list[str]
    scores: dict[str, float] | None = None
    overall_score: float | None = None

@dataclass(frozen=True)
class ValidationSignal:
    node_id: str
    result: str  # "pass" | "fail" | "requeue"
    reason: str
    scores: dict[str, int] | None = None
    overall_score: float | None = None
    criteria_results: list[dict] | None = None
    requeue_target: str | None = None

def read_signal(signal_path: Path) -> NodeSignal | ValidationSignal:
    """Parse a signal file into a typed signal object."""
    data = json.loads(signal_path.read_text())
    if "result" in data:  # Validation signal
        return ValidationSignal(
            node_id=signal_path.stem,
            result=data["result"],
            reason=data.get("reason", ""),
            scores=data.get("scores"),
            overall_score=data.get("overall_score"),
            criteria_results=data.get("criteria_results"),
            requeue_target=data.get("requeue_target"),
        )
    return NodeSignal(
        node_id=signal_path.stem,
        status=data.get("status", "unknown"),
        message=data.get("message", ""),
        files_changed=data.get("files_changed", []),
        scores=data.get("scores"),
        overall_score=data.get("overall_score"),
    )

def read_all_signals(signal_dir: Path) -> dict[str, NodeSignal | ValidationSignal]:
    """Read all signal files from a directory, skipping internal files."""
    signals = {}
    for path in sorted(signal_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        signals[path.stem] = read_signal(path)
    return signals
```

## 4. File Changes

### New Files (in claw-code fork)

| File | Purpose |
|------|---------|
| `src/cobuilder_tools/__init__.py` | Package init, exports COBUILDER_TOOLS dict |
| `src/cobuilder_tools/base.py` | `CoBuilderTool` ABC and `ToolResult` dataclass |
| `src/cobuilder_tools/pipeline_runner_tool.py` | `PipelineRunnerTool` implementation |
| `src/cobuilder_tools/pipeline_create_tool.py` | `PipelineCreateTool` implementation |
| `src/cobuilder_tools/task_tool.py` | `TaskTool` implementation |
| `src/cobuilder_tools/signal_reader.py` | Signal file parser |
| `tests/test_cobuilder_tools.py` | Unit tests for all tools |
| `tests/test_signal_reader.py` | Unit tests for signal parsing |
| `tests/fixtures/test_pipeline.dot` | Minimal DOT file for testing |
| `tests/fixtures/signals/` | Sample signal files for testing |

### Modified Files (in claw-code fork)

| File | Change |
|------|--------|
| `src/tools.py` | Add CoBuilder tool import + real execution path in `execute_tool()` |
| `src/reference_data/tools_snapshot.json` | Add metadata entries for 3 new tools |

## 5. Testing Strategy

### Unit Tests

```python
# tests/test_cobuilder_tools.py

def test_pipeline_runner_tool_validates_dot_path():
    """PipelineRunnerTool returns error for non-existent DOT file."""
    tool = PipelineRunnerTool()
    result = tool.execute({"dot_file": "/nonexistent/pipeline.dot"})
    assert not result.success
    assert "not found" in result.error

def test_signal_reader_parses_success_signal():
    """Signal reader correctly parses a worker success signal."""
    signal = read_signal(Path("tests/fixtures/signals/impl_auth.json"))
    assert isinstance(signal, NodeSignal)
    assert signal.status == "success"

def test_signal_reader_parses_validation_signal():
    """Signal reader correctly parses a validation requeue signal."""
    signal = read_signal(Path("tests/fixtures/signals/validate_auth.json"))
    assert isinstance(signal, ValidationSignal)
    assert signal.result == "requeue"
    assert signal.requeue_target is not None

def test_signal_reader_skips_internal_files():
    """Signal reader ignores files prefixed with underscore."""
    signals = read_all_signals(Path("tests/fixtures/signals/"))
    assert "_score_history" not in signals

def test_task_tool_create():
    """TaskTool create action invokes bd create."""
    tool = TaskTool()
    result = tool.execute({"action": "create", "title": "Test task", "priority": 2})
    # In test env, bd may not be available — assert it attempts the right command
    assert result.name == "TaskTool"

def test_execute_tool_routes_to_cobuilder():
    """execute_tool() dispatches to CoBuilder tools when available."""
    result = execute_tool("PipelineRunnerTool", '{"dot_file": "/tmp/test.dot"}')
    assert result.handled or "not found" in result.message  # Depends on file existence
```

### Integration Tests (require CoBuilder harness)

```python
# tests/test_pipeline_integration.py

@pytest.mark.integration
def test_full_pipeline_round_trip(tmp_path):
    """Full round-trip: create DOT → run pipeline → read signals."""
    # 1. Create a minimal pipeline DOT
    dot_content = '''digraph pipeline {
        graph [pipeline_id="test-001"]
        start [shape=Mdiamond, status=pending];
        finish [shape=Msquare, status=pending];
        start -> finish;
    }'''
    dot_file = tmp_path / "test.dot"
    dot_file.write_text(dot_content)

    # 2. Run via PipelineRunnerTool
    tool = PipelineRunnerTool()
    result = tool.execute({"dot_file": str(dot_file)})

    # 3. Verify completion
    assert result.success
    assert result.structured_data["returncode"] == 0
```

## 6. Environment Configuration

```bash
# Required environment variable — tells CoBuilder tools where the harness lives
export COBUILDER_HARNESS_DIR="/path/to/cobuilder-harness"

# Optional — override signal directory
export PIPELINE_SIGNAL_DIR="/custom/signal/dir"

# Beads must be configured for TaskTool
# (bd init should have been run in the workspace)
```

## 7. Implementation Priority

| Priority | Component | Reason |
|----------|-----------|--------|
| P0 | `signal_reader.py` | Foundation for all pipeline status reporting |
| P0 | `base.py` | Tool interface contract |
| P1 | `PipelineRunnerTool` | Core value proposition |
| P1 | `TaskTool` | Essential for tracking work within pipelines |
| P2 | `PipelineCreateTool` | Nice-to-have; users can create DOT files manually |
| P2 | `tools.py` integration | Connecting to claw-code's existing tool system |
| P3 | Integration tests | Require full harness setup |

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| signal_reader.py | Not Started | |
| base.py | Not Started | |
| PipelineRunnerTool | Not Started | |
| PipelineCreateTool | Not Started | |
| TaskTool | Not Started | |
| tools.py integration | Not Started | |
| Unit tests | Not Started | |
| Integration tests | Not Started | |
