#!/usr/bin/env python3
"""
Stop hook: Generate and store session narrative as GEO chain in Hindsight.

GEO Chain = Goal -> Experience -> Outcome
- Goal: What was the session trying to achieve?
- Experience: What happened? Key decisions, blockers, breakthroughs.
- Outcome: What was accomplished? What remains?

IMPORTANT: Stop hooks must output JSON in this format:
  {"decision": "approve", "systemMessage": "..."}

This hook always approves — it captures the narrative but never blocks stopping.

Hook type: Stop
"""

import json
import os
import sys
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
API_TIMEOUT = 10


def _log(msg: str) -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    log_file = Path(project_dir) / ".claude" / "state" / "hindsight-narrative" / "narrative.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _retain(bank_id: str, items: list) -> bool:
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{bank_id}/memories"
    payload = json.dumps({"items": items, "async": True}).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=API_TIMEOUT) as resp:
            return True
    except Exception as exc:
        _log(f"retain FAILED: {exc}")
        return False


def _run_cmd(cmd: list, cwd: str = None, timeout: int = 5) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _gather_goal(project_dir: str) -> str:
    """Determine session goal from completion state and beads."""
    parts = []
    # Check completion state
    cs_file = Path(project_dir) / ".claude" / "state" / "completion-state.json"
    if cs_file.exists():
        try:
            with open(cs_file) as f:
                cs = json.load(f)
            goal = cs.get("goal", "")
            if goal:
                parts.append(f"Promise goal: {goal}")
        except Exception:
            pass

    # Check active beads
    active = _run_cmd(["bd", "list", "--status=in_progress"], cwd=project_dir)
    if active:
        parts.append(f"Active tasks: {active[:200]}")

    return "\n".join(parts) if parts else "No explicit goal recorded"


def _gather_experience(project_dir: str) -> str:
    """Gather what happened during the session."""
    parts = []
    # Recent git commits
    commits = _run_cmd(["git", "log", "--oneline", "-5", "--no-merges"], cwd=project_dir)
    if commits:
        parts.append(f"Recent commits:\n{commits}")

    # Closed beads in this session
    closed = _run_cmd(["bd", "list", "--status=closed"], cwd=project_dir)
    if closed:
        # Take last few lines (most recent closures)
        lines = closed.strip().split("\n")[-5:]
        parts.append(f"Recently closed: {'; '.join(lines)}")

    # Git diff summary
    diff_stat = _run_cmd(["git", "diff", "--stat", "HEAD~3"], cwd=project_dir)
    if diff_stat:
        parts.append(f"Changes: {diff_stat[:200]}")

    return "\n".join(parts) if parts else "No activity recorded"


def _gather_outcome(project_dir: str) -> str:
    """Determine session outcomes."""
    parts = []
    # Check if branch is clean
    status = _run_cmd(["git", "status", "--porcelain"], cwd=project_dir)
    if not status:
        parts.append("Git: clean working tree")
    else:
        parts.append(f"Git: {len(status.split(chr(10)))} uncommitted changes")

    # Remaining work
    ready = _run_cmd(["bd", "ready"], cwd=project_dir)
    if ready and "No issues" not in ready:
        lines = ready.strip().split("\n")[:3]
        parts.append(f"Remaining work: {'; '.join(lines)}")

    return "\n".join(parts) if parts else "No outcome recorded"


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "unknown")

    try:
        # Read hook input
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    try:
        # Check Hindsight availability
        health_req = Request(f"{HINDSIGHT_BASE_URL}/health")
        with urlopen(health_req, timeout=3) as resp:
            health = json.loads(resp.read())
            if health.get("status") != "healthy":
                _log("Hindsight not healthy, skipping narrative")
                print(json.dumps({"decision": "approve", "systemMessage": "Hindsight unavailable, narrative skipped"}))
                return
    except Exception:
        _log("Hindsight unavailable")
        print(json.dumps({"decision": "approve", "systemMessage": "Hindsight unavailable, narrative skipped"}))
        return

    # Gather GEO components
    goal = _gather_goal(project_dir)
    experience = _gather_experience(project_dir)
    outcome = _gather_outcome(project_dir)

    now = datetime.now(timezone.utc).isoformat()

    # Format GEO narrative
    narrative = f"""## Session Narrative (GEO Chain)
**Session**: {session_id}
**Style**: {output_style}
**Time**: {now}

### Goal
{goal}

### Experience
{experience}

### Outcome
{outcome}"""

    # Store in Hindsight
    item = {
        "content": narrative,
        "context": "session-narrative",
        "timestamp": now,
        "metadata": {
            "source": "stop-hook-narrative",
            "session_id": session_id,
            "output_style": output_style,
            "type": "geo-chain",
        },
    }

    success = _retain(SHARED_BANK, [item])
    if success:
        _log(f"Narrative stored for session {session_id}")
        msg = f"Session narrative logged to Hindsight (session: {session_id})"
    else:
        _log(f"Failed to store narrative for session {session_id}")
        msg = "Session narrative logging failed (Hindsight error)"

    # Always approve stop
    print(json.dumps({"decision": "approve", "systemMessage": msg}))


if __name__ == "__main__":
    main()
