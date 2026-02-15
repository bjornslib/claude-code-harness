#!/usr/bin/env python3
"""
SessionStart hook: Check Hindsight health and report memory status.

Provides a compact health summary of the Hindsight memory system:
- Server health (up/down)
- Last memory flush time
- Memory bank statistics

Hook type: SessionStart
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
HEALTH_TIMEOUT = 3


def _check_server_health() -> tuple:
    """Returns (is_healthy: bool, status_text: str)."""
    try:
        req = Request(f"{HINDSIGHT_BASE_URL}/health")
        with urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            data = json.loads(resp.read())
            if data.get("status") == "healthy":
                return True, "healthy"
            return False, data.get("status", "unknown")
    except Exception as e:
        return False, f"unreachable ({type(e).__name__})"


def _get_bank_stats() -> dict:
    """Get memory bank statistics."""
    try:
        req = Request(f"{HINDSIGHT_BASE_URL}/v1/default/banks/{SHARED_BANK}/stats")
        with urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def _get_last_flush_time() -> str:
    """Check most recent flush marker."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    flush_dir = Path(project_dir) / ".claude" / "state" / "hindsight-flush"
    if not flush_dir.exists():
        return "never"

    markers = list(flush_dir.glob("flush-*.marker"))
    if not markers:
        return "never"

    # Get most recent marker
    latest = max(markers, key=lambda p: p.stat().st_mtime)
    age_seconds = time.time() - latest.stat().st_mtime

    if age_seconds < 60:
        return f"{int(age_seconds)}s ago"
    elif age_seconds < 3600:
        return f"{int(age_seconds / 60)}m ago"
    elif age_seconds < 86400:
        return f"{int(age_seconds / 3600)}h ago"
    else:
        return f"{int(age_seconds / 86400)}d ago"


def main():
    try:
        # Read stdin (required for hooks)
        sys.stdin.read()
    except Exception:
        pass

    # Check health
    is_healthy, status = _check_server_health()

    # Get stats
    stats = _get_bank_stats() if is_healthy else {}
    # Hindsight stats structure: total_nodes, total_links, total_documents
    memory_count = stats.get("total_nodes", "?")
    doc_count = stats.get("total_documents", "?")

    # Get last flush
    last_flush = _get_last_flush_time()

    # Format compact output
    if is_healthy:
        summary = f"Hindsight: {status} | Bank: {SHARED_BANK} | Nodes: {memory_count} | Docs: {doc_count} | Last flush: {last_flush}"
    else:
        summary = f"Hindsight: {status} | Memory system unavailable"

    print(f"<system-reminder>\n{summary}\n</system-reminder>")
    sys.exit(0)


if __name__ == "__main__":
    main()
