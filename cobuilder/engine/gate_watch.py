#!/usr/bin/env python3
"""gate_watch.py — Event-driven pipeline gate watcher.

Blocks until the pipeline runner signals that CoBuilder/Pilot attention is needed,
then prints structured JSON describing the event and exits.

This replaces polling-based monitoring (sleep loops, cyclic Haiku monitors) with
filesystem-event-driven wake using the ``watchdog`` library (already a dependency
of pipeline_runner.py). Falls back to polling if watchdog is unavailable.

Events that trigger a wake:
    - A ``.gate-wait`` marker file appears (wait.cobuilder or wait.human gate)
    - A node failure signal appears (status=failed in a .json signal)
    - The pipeline completes (all nodes terminal in the DOT file)
    - A terminal-targeted escalation signal appears
    - Timeout (configurable, default 3600s)

Usage:
    # Block until a gate or terminal event
    python3 gate_watch.py --signal-dir .pipelines/signals/my-pipeline/ \\
                          --dot-file .pipelines/pipelines/my-pipeline.dot \\
                          --timeout 3600

    # Quick check (return immediately if events pending, else wait)
    python3 gate_watch.py --signal-dir .pipelines/signals/my-pipeline/ --timeout 0

Output (JSON to stdout):
    {"event": "gate", "gate_type": "wait.cobuilder", "node_id": "validate_auth", ...}
    {"event": "gate", "gate_type": "wait.human", "node_id": "review_auth", ...}
    {"event": "failure", "node_id": "impl_auth", "message": "..."}
    {"event": "pipeline_complete", "summary": {...}}
    {"event": "escalation", "signal_type": "NEEDS_INPUT", ...}
    {"event": "timeout", "elapsed_seconds": 3600}
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
import threading
import time
from typing import Any

log = logging.getLogger("gate_watch")

# ---------------------------------------------------------------------------
# Watchdog availability (mirrors pipeline_runner.py pattern)
# ---------------------------------------------------------------------------

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    _WATCHDOG_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 3600.0  # 1 hour
POLL_INTERVAL = 2.0       # fallback polling interval (seconds)


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

class _GateFileHandler(FileSystemEventHandler if _WATCHDOG_AVAILABLE else object):
    """Watchdog handler that wakes the main thread on relevant file events.

    Monitors for:
    - ``.gate-wait`` files (gate markers)
    - ``.json`` files (signals — could be failures or escalations)
    """

    def __init__(self, event: threading.Event) -> None:
        if _WATCHDOG_AVAILABLE:
            super().__init__()
        self._event = event
        self._last_event_time: float = 0.0
        self._debounce_s: float = 0.5  # tighter than runner (we want fast wake)

    def on_created(self, event: Any) -> None:
        self._handle(event)

    def on_modified(self, event: Any) -> None:
        self._handle(event)

    def _handle(self, event: Any) -> None:
        if getattr(event, "is_directory", False):
            return
        src = str(getattr(event, "src_path", ""))
        if src.endswith(".gate-wait") or src.endswith(".json"):
            now = time.time()
            if now - self._last_event_time < self._debounce_s:
                return
            self._last_event_time = now
            self._event.set()


# ---------------------------------------------------------------------------
# Event scanning
# ---------------------------------------------------------------------------

def _scan_gate_markers(signal_dir: str) -> list[dict[str, Any]]:
    """Return list of pending .gate-wait marker dicts."""
    results = []
    pattern = os.path.join(signal_dir, "*.gate-wait")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
            data["_path"] = path
            results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _scan_failure_signals(signal_dir: str) -> list[dict[str, Any]]:
    """Return list of failure signal dicts (status=failed) not yet processed."""
    results = []
    pattern = os.path.join(signal_dir, "*.json")
    for path in sorted(glob.glob(pattern)):
        basename = os.path.basename(path)
        # Skip internal files
        if basename.startswith("_") or basename == "pipeline-events.jsonl":
            continue
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
            status = data.get("status") or data.get("result", "")
            sig_type = data.get("signal_type", "")
            # Match failure signals
            if status in ("failed", "error") or "CRASHED" in sig_type or "STUCK" in sig_type:
                data["_path"] = path
                results.append(data)
            # Match escalation signals targeted at terminal/guardian
            if data.get("target") in ("terminal", "guardian") and sig_type in (
                "NEEDS_REVIEW", "NEEDS_INPUT", "VIOLATION",
                "ORCHESTRATOR_STUCK", "ORCHESTRATOR_CRASHED",
            ):
                data["_path"] = path
                results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _check_pipeline_complete(dot_path: str | None) -> dict[str, Any] | None:
    """Check if all nodes in the DOT file are in terminal states.

    Returns a summary dict if complete, else None.
    """
    if not dot_path or not os.path.exists(dot_path):
        return None

    try:
        from cobuilder.engine.dispatch_parser import parse_dot
        with open(dot_path, "r") as fh:
            data = parse_dot(fh.read())

        nodes = data.get("nodes", [])
        if not nodes:
            return None

        terminal = {"validated", "accepted", "failed"}
        statuses = {}
        for node in nodes:
            nid = node.get("id", "")
            status = node.get("attrs", {}).get("status", "pending")
            statuses[nid] = status

        non_terminal = {
            nid: s for nid, s in statuses.items()
            if s not in terminal
            # Skip start/exit nodes which may stay pending
            and not any(
                node.get("id") == nid and node.get("attrs", {}).get("shape") in ("Mdiamond", "Msquare")
                for node in nodes
            )
        }

        if not non_terminal:
            return {"summary": statuses, "total": len(nodes)}

    except Exception as exc:
        log.debug("DOT parse failed: %s", exc)

    return None


def scan_for_events(
    signal_dir: str,
    dot_path: str | None = None,
) -> dict[str, Any] | None:
    """Scan for any pending event that needs attention.

    Returns the highest-priority event dict, or None if nothing pending.
    Priority: failures > gates > pipeline_complete.
    """
    # 1. Check for failure signals (highest priority)
    failures = _scan_failure_signals(signal_dir)
    if failures:
        sig = failures[0]
        return {
            "event": "failure",
            "node_id": sig.get("payload", {}).get("node_id") or sig.get("node_id", "unknown"),
            "signal_type": sig.get("signal_type", "UNKNOWN"),
            "message": sig.get("payload", {}).get("issue")
                       or sig.get("message", ""),
            "raw": sig,
        }

    # 2. Check for gate markers
    gates = _scan_gate_markers(signal_dir)
    if gates:
        gate = gates[0]
        return {
            "event": "gate",
            "gate_type": gate.get("gate_type", "unknown"),
            "node_id": gate.get("node_id", "unknown"),
            "epic_id": gate.get("epic_id", ""),
            "summary_ref": gate.get("summary_ref", ""),
            "timestamp": gate.get("timestamp", ""),
        }

    # 3. Check for pipeline completion
    completion = _check_pipeline_complete(dot_path)
    if completion:
        return {
            "event": "pipeline_complete",
            **completion,
        }

    return None


# ---------------------------------------------------------------------------
# Main blocking watch function
# ---------------------------------------------------------------------------

def watch(
    signal_dir: str,
    dot_path: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Block until a pipeline event needs attention, then return it.

    Uses watchdog for instant filesystem-event wake (falls back to polling).

    Args:
        signal_dir: Directory to watch for signal/gate-wait files.
        dot_path: Optional DOT file path to check for pipeline completion.
        timeout: Maximum seconds to wait (0 = check once and return).

    Returns:
        Event dict with ``event`` key describing what happened.
    """
    # Ensure signal dir exists
    os.makedirs(signal_dir, exist_ok=True)

    # Immediate check — return without blocking if events already pending
    existing = scan_for_events(signal_dir, dot_path)
    if existing:
        return existing

    # Timeout=0 means "check once only"
    if timeout <= 0:
        return {"event": "timeout", "elapsed_seconds": 0}

    # Set up blocking mechanism
    wake_event = threading.Event()
    start_time = time.monotonic()
    observer = None

    if _WATCHDOG_AVAILABLE and Observer is not None:
        handler = _GateFileHandler(wake_event)
        observer = Observer()
        observer.schedule(handler, signal_dir, recursive=False)
        # Also watch DOT file directory for completion state changes
        if dot_path:
            dot_dir = os.path.dirname(os.path.abspath(dot_path))
            if dot_dir != os.path.abspath(signal_dir):
                try:
                    observer.schedule(handler, dot_dir, recursive=False)
                except Exception:
                    pass  # non-critical
        observer.start()

    try:
        while True:
            elapsed = time.monotonic() - start_time
            remaining = timeout - elapsed

            if remaining <= 0:
                return {"event": "timeout", "elapsed_seconds": round(elapsed, 1)}

            # Wait for filesystem event or poll interval
            if _WATCHDOG_AVAILABLE and observer:
                wake_event.wait(timeout=min(remaining, 30.0))
                wake_event.clear()
            else:
                time.sleep(min(POLL_INTERVAL, remaining))

            # Check for events
            found = scan_for_events(signal_dir, dot_path)
            if found:
                found["elapsed_seconds"] = round(time.monotonic() - start_time, 1)
                return found

    finally:
        if observer:
            observer.stop()
            observer.join(timeout=5)


# ---------------------------------------------------------------------------
# Async wrapper for guardian.py integration
# ---------------------------------------------------------------------------

async def async_watch(
    signal_dir: str,
    dot_path: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Async wrapper around watch() — runs the blocking watch in a thread.

    This allows guardian.py's async _run_agent_event_driven() to await gate
    events without blocking the asyncio event loop.
    """
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, watch, signal_dir, dot_path, timeout)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="gate_watch",
        description="Block until a pipeline gate or terminal event occurs.",
    )
    parser.add_argument("--signal-dir", required=True, dest="signal_dir",
                        help="Signal directory to watch")
    parser.add_argument("--dot-file", default=None, dest="dot_file",
                        help="DOT file to check for pipeline completion")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"Max seconds to wait (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging to stderr")

    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)

    result = watch(
        signal_dir=args.signal_dir,
        dot_path=args.dot_file,
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
