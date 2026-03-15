# SD-ATTRACTOR-SDK-001-E2: Mode-Aware Runner Monitor

**PRD**: GAP-PRD-ATTRACTOR-SDK-001
**Epic**: 2 — Mode-Aware Runner Monitor
**Priority**: P0
**Depends on**: Epic 1 (Worker Backend)

---

**Validation Status**: ✅ Updated for SDK-primary approach (2026-03-03)
- SDK mode uses **pure SDK streaming events** for monitoring — no PID polling, no file heartbeats
- Decision: [SDK vs Subprocess Analysis](../references/sdk-vs-subprocess-analysis.md)

---

## 1. Problem

`RunnerStateMachine._do_monitor_mode()` is hardcoded to tmux monitoring:
- `build_monitor_prompt()` instructs LLM to call `capture_output.py` (tmux-only)
- Status checking only handles COMPLETED and FAILED (missing CRASHED, STUCK, NEEDS_INPUT)
- No SDK-mode monitoring path exists

In the 3-layer model, the runner monitors **workers** (not orchestrators). For SDK mode, the monitoring mechanism is fundamentally different from tmux: the SDK's async event stream (`AssistantMessage`, `ResultMessage`, typed exceptions) IS the monitoring channel. No separate monitoring script is needed.

## 2. Design

### 2.1 New File: `sdk_monitor.py`

Non-tmux monitoring tools that the runner's LLM child can call:

```python
"""sdk_monitor.py — SDK-mode monitoring tools.

Provides process-level and file-level monitoring for SDK worker sessions.
These replace capture_output.py and check_orchestrator_alive.py in SDK mode.

Usage:
    python sdk_monitor.py --check-alive --pid <pid>
    python sdk_monitor.py --tail-log <path> --lines <n>
    python sdk_monitor.py --check-git --target-dir <path> --since <timestamp>
    python sdk_monitor.py --check-progress --stdout-log <path>
"""

import argparse
import json
import os
import subprocess
import sys
import time


def check_process_alive(pid: int) -> dict:
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)  # Signal 0 = check existence
        return {"alive": True, "pid": pid}
    except ProcessLookupError:
        return {"alive": False, "pid": pid, "reason": "process_not_found"}
    except PermissionError:
        return {"alive": True, "pid": pid, "note": "permission_denied_but_exists"}


def tail_log(log_path: str, lines: int = 50) -> dict:
    """Read the last N lines of a log file."""
    if not os.path.exists(log_path):
        return {"status": "error", "message": f"Log file not found: {log_path}"}

    try:
        with open(log_path, "r") as f:
            all_lines = f.readlines()
            tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {
            "status": "ok",
            "total_lines": len(all_lines),
            "returned_lines": len(tail),
            "content": "".join(tail),
            "file_size": os.path.getsize(log_path),
            "last_modified": os.path.getmtime(log_path),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def check_git_activity(target_dir: str, since_timestamp: str | None = None) -> dict:
    """Check for recent git commits in the target directory."""
    try:
        cmd = ["git", "-C", target_dir, "log", "--oneline", "-10"]
        if since_timestamp:
            cmd += [f"--since={since_timestamp}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        commits = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return {
            "status": "ok",
            "commit_count": len(commits),
            "commits": commits,
            "has_recent_commits": len(commits) > 0,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def check_progress(stdout_log: str) -> dict:
    """Analyze worker stdout log for progress indicators."""
    if not os.path.exists(stdout_log):
        return {"status": "no_log", "indicators": []}

    try:
        with open(stdout_log) as f:
            content = f.read()

        indicators = []
        # Check for completion signals
        if "All tasks complete" in content or "Implementation done" in content:
            indicators.append("COMPLETION_SIGNAL")
        if "git commit" in content or "committed" in content.lower():
            indicators.append("GIT_COMMIT")
        if "AskUserQuestion" in content or "Do you want" in content:
            indicators.append("NEEDS_INPUT")
        if "Error" in content or "error" in content:
            indicators.append("HAS_ERRORS")
        if "Editing file" in content or "Writing to" in content:
            indicators.append("FILE_EDITS")

        return {
            "status": "ok",
            "file_size": os.path.getsize(stdout_log),
            "last_modified": os.path.getmtime(stdout_log),
            "indicators": indicators,
            "last_100_chars": content[-100:] if content else "",
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
```

### 2.2 Mode-Aware `build_monitor_prompt()`

Replace the current tmux-only prompt with a mode-aware version:

```python
def build_monitor_prompt(
    node_id: str,
    session_name: str,
    scripts_dir: str,
    mode: str = "tmux",
    worker_pid: int | None = None,
    worker_stdout_log: str | None = None,
    target_dir: str | None = None,
) -> str:
    if mode == "sdk":
        return _build_sdk_monitor_prompt(
            node_id, scripts_dir, worker_pid, worker_stdout_log, target_dir
        )
    else:
        return _build_tmux_monitor_prompt(node_id, session_name, scripts_dir)


def _build_sdk_monitor_prompt(node_id, scripts_dir, pid, stdout_log, target_dir):
    return f"""\
You are monitoring SDK worker for pipeline node '{node_id}'.

## Your ONLY job
Run these checks and respond with a STATUS line:

1. Check if worker process is alive:
   python3 {scripts_dir}/sdk_monitor.py --check-alive --pid {pid}

2. Check stdout log for progress:
   python3 {scripts_dir}/sdk_monitor.py --check-progress --stdout-log {stdout_log}

3. Check for git commits:
   python3 {scripts_dir}/sdk_monitor.py --check-git --target-dir {target_dir}

## Response format (EXACTLY this, no other text):
STATUS: <COMPLETED|STUCK|CRASHED|WORKING|NEEDS_INPUT>
EVIDENCE: <one-line summary>
COMMIT: <git hash if found, else NONE>

## Status rules:
- COMPLETED: Process exited AND (git commits found OR completion indicator in log)
- CRASHED: Process not alive AND no completion indicators
- STUCK: Process alive but log not growing for 2+ minutes
- NEEDS_INPUT: NEEDS_INPUT indicator found in progress check
- WORKING: Process alive and log is growing

Run the checks now and report.
"""


def _build_tmux_monitor_prompt(node_id, session_name, scripts_dir):
    # Existing tmux monitor prompt (unchanged)
    return f"""..."""  # Current implementation
```

### 2.3 Full Status Handling in `_do_monitor_mode()`

```python
def _do_monitor_mode(self) -> str:
    """Run one monitoring cycle. Returns status string."""
    prompt = build_monitor_prompt(
        node_id=self.node_id,
        session_name=self.session_name,
        scripts_dir=self._scripts_dir,
        mode=self._mode,
        worker_pid=self._worker_handle.pid if self._worker_handle else None,
        worker_stdout_log=self._worker_handle.stdout_log if self._worker_handle else None,
        target_dir=self.target_dir,
    )

    # ... existing SDK query logic ...

    full_text = "\n".join(text_blocks)

    # Full status handling (was: only COMPLETED and FAILED)
    if "STATUS: COMPLETED" in full_text:
        return "COMPLETED"
    if "STATUS: FAILED" in full_text:
        return "FAILED"
    if "STATUS: CRASHED" in full_text:
        return "CRASHED"
    if "STATUS: STUCK" in full_text:
        return "STUCK"
    if "STATUS: NEEDS_INPUT" in full_text:
        return "NEEDS_INPUT"
    return "IN_PROGRESS"  # STATUS: WORKING or unrecognized
```

### 2.4 State Machine Transitions for All Statuses

```python
def run(self) -> str:
    try:
        # SPAWN phase (Epic 1)
        if self._mode == "sdk":
            self._worker_handle = self._spawn_worker_sdk()
            ...

        # MONITOR phase
        cycles = 0
        while self.mode == RunnerMode.MONITOR:
            cycles += 1
            if cycles > self.max_cycles:
                self.mode = RunnerMode.FAILED
                break

            status = self._do_monitor_mode()

            if status == "COMPLETED":
                self._signal_guardian("NODE_COMPLETE")
                self.mode = RunnerMode.COMPLETE

            elif status == "FAILED":
                self.mode = RunnerMode.FAILED

            elif status == "CRASHED":
                self._signal_guardian("WORKER_CRASHED")
                self.mode = RunnerMode.FAILED

            elif status == "STUCK":
                self._signal_guardian("WORKER_STUCK")
                # Stay in MONITOR — guardian may send guidance
                self._wait_for_guardian_response()

            elif status == "NEEDS_INPUT":
                self._signal_guardian("NEEDS_INPUT")
                response = self._wait_for_guardian_response()
                if response:
                    self._relay_to_worker(response)
                # Stay in MONITOR

            # else: IN_PROGRESS — continue monitoring

            # Sleep between cycles (avoid tight loop)
            if self.mode == RunnerMode.MONITOR:
                time.sleep(self._check_interval)

    finally:
        self._write_safety_net_if_needed()
    return self.mode
```

### 2.5 SDK Event-Stream Monitoring (Primary Approach)

With the Claude Agent SDK as the primary spawning mechanism (E1), SDK-mode monitoring uses the **async event stream directly** — no separate monitoring script or PID polling needed:

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

async def monitor_worker(prompt: str, options: ClaudeAgentOptions, timeout: int = 1800):
    """The SDK event stream IS the monitoring channel.

    - AssistantMessage: worker is actively reasoning/acting → WORKING
    - ResultMessage: worker completed → check stop_reason
    - ProcessError exception: worker crashed → CRASHED
    - asyncio.TimeoutError: no events for timeout period → STUCK
    """
    try:
        async for message in asyncio.wait_for(
            query(prompt=prompt, options=options),
            timeout=timeout,
        ):
            if isinstance(message, AssistantMessage):
                # Worker is making progress — check for NEEDS_INPUT
                for block in message.content:
                    if hasattr(block, 'name') and block.name == 'AskUserQuestion':
                        return "NEEDS_INPUT", message
                # else: WORKING (continue monitoring)

            elif isinstance(message, ResultMessage):
                if message.stop_reason in ("end_turn", "stop_sequence"):
                    return "COMPLETED", message
                elif message.stop_reason == "refusal":
                    return "FAILED", message
                else:
                    return "COMPLETED", message

    except asyncio.TimeoutError:
        return "STUCK", None
    except ProcessError as exc:
        return "CRASHED", exc
```

**Key advantage over Popen monitoring**: No polling interval, no PID checks, no file-based progress indicators. The SDK's event stream provides real-time visibility into worker state with typed Python objects.

### 2.6 SDK Hooks for Enhanced Monitoring (Future Enhancement)

For long-running worker sessions (30+ minutes), SDK programmatic hooks provide additional monitoring capabilities:

```python
# Example: Use PreToolUse hook to detect NEEDS_INPUT immediately
hooks = {
    "PreToolUse": [
        HookMatcher(
            matcher="AskUserQuestion",
            callback=lambda event: write_gupp_record(
                "NEEDS_INPUT", context=event.input
            )
        )
    ]
}
worker_options = ClaudeAgentOptions(hooks=hooks, ...)
```

This is an enhancement on top of the event-stream approach — it provides lower-latency detection of specific events without waiting for the next `AssistantMessage` in the stream.

### 2.7 Implementation Gotchas (SDK Mode)

The following pitfalls apply when using Claude Agent SDK for worker spawning:

1. **CLAUDECODE env var** — SDK handles this internally when `setting_sources=None`, but if any fallback subprocess code is used, must be stripped explicitly. Reference: GitHub issue #573.

2. **No Direct PID Access** — SDK manages subprocess internally. Cannot `os.kill(pid, 0)` for health checks. Monitoring is purely via event stream + `asyncio.wait_for()`. If a worker hangs without producing events, the timeout is the only detection mechanism.

3. **asyncio.wait_for Cancellation** — When timeout fires, `asyncio.wait_for` cancels the underlying coroutine. The SDK subprocess may not terminate cleanly. Implement a cleanup handler that ensures the subprocess is killed if the event stream is abandoned.

4. **Prompt Caching Sensitivity** — The `system_prompt` must be identical across workers of the same type to benefit from Anthropic's prompt caching. Any per-node variation in the system_prompt breaks the cache. Keep role definitions stable; put all per-node context in the `prompt` parameter.

5. **MCP Server Startup Overhead** — Explicitly injected MCP servers (via `mcp_servers={}`) add startup time to each worker spawn. If a worker type needs 3+ MCP servers, expect 5-15s initialization overhead. For short-lived workers (validation), minimize MCP requirements.

---

### 3. Testing

- **Unit test**: `_build_sdk_monitor_prompt()` includes PID, log path, target dir
- **Unit test**: `_build_tmux_monitor_prompt()` unchanged from current behavior
- **Unit test**: `_do_monitor_mode()` returns correct status for all 5 types
- **Unit test**: State machine transitions for CRASHED, STUCK, NEEDS_INPUT
- **Integration test**: SDK monitor detects process death → CRASHED
- **Integration test**: SDK monitor detects git commit → COMPLETED
- **Regression test**: tmux mode monitor unchanged

### 4. Files Changed

| File | Change |
|------|--------|
| `sdk_monitor.py` | **NEW** — SDK-mode monitoring tools |
| `runner_agent.py` | Mode-aware `build_monitor_prompt()`, full status handling in state machine |
| `tests/test_sdk_monitor.py` | **NEW** — unit tests |
| `tests/test_runner_state_machine.py` | Updated tests for all status transitions |

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| - | Remaining | - | - |
