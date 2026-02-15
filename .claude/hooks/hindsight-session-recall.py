#!/usr/bin/env python3
"""
SessionStart hook: Recall context from Hindsight memory.

Fires on ALL SessionStart events to restore active goals, recent patterns,
and session context from Hindsight long-term memory.

This closes the memory preservation loop:
  PreCompact -> retain() -> [compress] -> SessionStart -> recall()

Hook type: SessionStart
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
RECALL_TIMEOUT = 10  # seconds per query
MAX_RESULTS = 5


def _log(msg: str) -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    log_file = Path(project_dir) / ".claude" / "state" / "hindsight-recall" / "session-recall.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _recall(bank_id: str, query: str, budget: str = "mid", max_results: int = MAX_RESULTS) -> list:
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{bank_id}/memories/recall"
    payload = json.dumps({
        "query": query,
        "budget": budget,
        "max_tokens": 2048,
    }).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=RECALL_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            _log(f"recall({bank_id}, '{query[:40]}...'): {len(results)} results")
            return results
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        _log(f"recall FAILED: {exc}")
        return []


def _format_results(results: list, heading: str) -> str:
    if not results:
        return ""
    lines = [f"### {heading}"]
    for r in results[:MAX_RESULTS]:
        text = r.get("text", "")
        if len(text) > 300:
            text = text[:297] + "..."
        context = r.get("context", "")
        lines.append(f"- [{context}] {text}")
    return "\n".join(lines)


def main():
    start = time.time()
    try:
        # Read stdin
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    source = hook_input.get("source", "startup")
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "unknown")

    _log(f"Session recall starting: source={source}, session={session_id}")

    # Check Hindsight availability
    try:
        health_req = Request(f"{HINDSIGHT_BASE_URL}/health")
        with urlopen(health_req, timeout=3) as resp:
            health = json.loads(resp.read())
            if health.get("status") != "healthy":
                _log("Hindsight not healthy, skipping")
                sys.exit(0)
    except Exception:
        _log("Hindsight unavailable, skipping")
        sys.exit(0)

    # Query 1: Active goals and session context
    goals = _recall(SHARED_BANK, f"active goals session context for {output_style} session")

    # Query 2: Recent patterns and lessons
    patterns = _recall(SHARED_BANK, "recent patterns lessons learned mistakes to avoid")

    # Query 3: For post-compact, recall recent precompact flush
    precompact = []
    if source == "compact":
        precompact = _recall(SHARED_BANK, f"precompact memory flush session {session_id}")

    # Format output
    sections = []
    sections.append("# Hindsight Session Recall")
    sections.append(f"*Source: {source} | Session: {session_id}*")

    goals_text = _format_results(goals, "Active Goals & Session Context")
    if goals_text:
        sections.append(goals_text)

    patterns_text = _format_results(patterns, "Recent Patterns & Lessons")
    if patterns_text:
        sections.append(patterns_text)

    if precompact:
        precompact_text = _format_results(precompact, "Pre-Compaction Context (restored)")
        if precompact_text:
            sections.append(precompact_text)

    elapsed = time.time() - start
    sections.append(f"\n*Recall completed in {elapsed:.1f}s*")

    # Only output if we got meaningful results
    if goals or patterns or precompact:
        output = "\n\n".join(sections)
        print(f"<system-reminder>\n{output}\n</system-reminder>")
        _log(f"Recalled {len(goals)}+{len(patterns)}+{len(precompact)} memories in {elapsed:.1f}s")
    else:
        _log(f"No memories found ({elapsed:.1f}s)")

    sys.exit(0)


if __name__ == "__main__":
    main()
