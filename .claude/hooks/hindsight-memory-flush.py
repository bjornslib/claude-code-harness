#!/usr/bin/env python3
"""
PreCompact hook: Flush session context to Hindsight before context compression.

Implements F3.1 from PRD-S3-CLAWS-001 (Epic 3: Enhanced Hindsight Integration).

Before the context window is compressed, this hook captures durable session
information and stores it in Hindsight via the REST API. This ensures that
active goals, in-progress decisions, key findings, and unresolved questions
survive context compaction and can be recalled in future sessions.

The hook writes to BOTH Hindsight banks:
  - claude-harness-setup (shared/project): project-relevant findings
  - system3-orchestrator (private): meta-orchestration state (if S3 session)

Design principles:
  - NEVER block compaction: always output {"continue": true}
  - Use async=true for API calls to avoid blocking on LLM processing
  - Skip silently (NO_REPLY pattern) when there is nothing to save
  - Track flushes per session to avoid duplicate writes
  - Use urllib only (no external dependencies beyond stdlib)

Hook type: PreCompact
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# -- Configuration ----------------------------------------------------------

HINDSIGHT_BASE_URL = os.environ.get(
    "HINDSIGHT_URL", "http://localhost:8888"
)
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
PRIVATE_BANK = os.environ.get("HINDSIGHT_PRIVATE_BANK", "system3-orchestrator")
API_TIMEOUT_SECONDS = 10


# -- Helpers ----------------------------------------------------------------

def _log(state_dir: Path, message: str) -> None:
    """Append a timestamped line to the debug log."""
    try:
        log_file = state_dir / "hindsight-memory-flush.log"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def _retain(bank_id: str, items: list[dict], state_dir: Path) -> bool:
    """POST items to Hindsight retain endpoint. Returns True on success."""
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{bank_id}/memories"
    payload = json.dumps({"items": items, "async": True}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=API_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            success = body.get("success", False)
            _log(state_dir, f"retain({bank_id}): {len(items)} items, success={success}")
            return success
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        _log(state_dir, f"retain({bank_id}) FAILED: {exc}")
        return False


def _session_fingerprint(session_id: str) -> str:
    """Short hash for dedup tracking."""
    return hashlib.md5(session_id.encode()).hexdigest()[:8]


def _already_flushed(state_dir: Path, fingerprint: str) -> bool:
    """Check if we already flushed for this compaction cycle."""
    marker = state_dir / f"flush-{fingerprint}.marker"
    return marker.exists()


def _mark_flushed(state_dir: Path, fingerprint: str) -> None:
    """Record that we flushed for this compaction cycle."""
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        marker = state_dir / f"flush-{fingerprint}.marker"
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass


def _is_system3_session() -> bool:
    """Detect whether this is a System 3 meta-orchestrator session."""
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "")
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    # Check output style for system3 indicator
    if "system3" in output_style.lower():
        return True
    # Check session ID for explicit system3 or s3- prefix patterns
    sid_lower = session_id.lower()
    if "system3" in sid_lower:
        return True
    # Match s3- prefix or -s3- infix but not arbitrary substrings like "test-non-s3"
    import re
    if re.search(r"(?:^|[-_])s3(?:[-_]|$)", sid_lower):
        return True
    return False


def _gather_session_context(hook_input: dict) -> dict:
    """Build a structured summary of the current session state."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "unknown")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    now = datetime.now(timezone.utc).isoformat()

    context = {
        "session_id": session_id,
        "output_style": output_style,
        "project_dir": project_dir,
        "timestamp": now,
        "hook_source": "PreCompact/hindsight-memory-flush",
    }

    # Try to read completion state for active goals
    completion_file = Path(project_dir) / ".claude" / "state" / "completion-state.json"
    if completion_file.exists():
        try:
            with open(completion_file) as f:
                cs = json.load(f)
            context["completion_state"] = {
                "promise_id": cs.get("promise_id", ""),
                "goal": cs.get("goal", ""),
                "progress_pct": cs.get("progress_pct", 0),
                "status": cs.get("status", ""),
            }
        except Exception:
            pass

    # Try to read preserved context (from context-preserver-hook)
    preserved_file = (
        Path(project_dir)
        / ".claude"
        / "state"
        / "decision-guidance"
        / "preserved-context.json"
    )
    if preserved_file.exists():
        try:
            with open(preserved_file) as f:
                preserved = json.load(f)
            context["preserved_context"] = preserved
        except Exception:
            pass

    # Try to get git branch info
    try:
        import subprocess

        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        if result.returncode == 0:
            context["git_branch"] = result.stdout.strip()
    except Exception:
        pass

    # Try to read active team info
    teams_dir = Path.home() / ".claude" / "teams"
    if teams_dir.exists():
        try:
            active_teams = []
            for team_config in teams_dir.glob("*/config.json"):
                with open(team_config) as f:
                    tc = json.load(f)
                active_teams.append(
                    {
                        "name": tc.get("name", team_config.parent.name),
                        "members": len(tc.get("members", [])),
                    }
                )
            if active_teams:
                context["active_teams"] = active_teams
        except Exception:
            pass

    return context


def _build_memory_content(context: dict) -> str:
    """Format the session context into a human-readable memory item."""
    parts = [
        f"## Pre-Compaction Memory Flush",
        f"**Session**: {context.get('session_id', 'unknown')}",
        f"**Style**: {context.get('output_style', 'unknown')}",
        f"**Branch**: {context.get('git_branch', 'unknown')}",
        f"**Time**: {context.get('timestamp', 'unknown')}",
    ]

    cs = context.get("completion_state")
    if cs:
        parts.append("")
        parts.append("### Active Goal")
        parts.append(f"- **Promise**: {cs.get('promise_id', 'none')}")
        parts.append(f"- **Goal**: {cs.get('goal', 'none')}")
        parts.append(f"- **Progress**: {cs.get('progress_pct', 0)}%")
        parts.append(f"- **Status**: {cs.get('status', 'unknown')}")

    preserved = context.get("preserved_context")
    if preserved:
        parts.append("")
        parts.append("### Preserved Decision Context")
        # Include key preserved fields if available
        for key in ["active_phase", "current_focus", "key_findings", "unresolved"]:
            val = preserved.get(key)
            if val:
                parts.append(f"- **{key}**: {val}")

    teams = context.get("active_teams")
    if teams:
        parts.append("")
        parts.append("### Active Teams")
        for t in teams:
            parts.append(f"- {t['name']} ({t['members']} members)")

    return "\n".join(parts)


# -- Main ------------------------------------------------------------------

def main():
    """Main hook entry point. Always outputs {"continue": true}."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    state_dir = Path(project_dir) / ".claude" / "state" / "hindsight-flush"

    try:
        # 1. Read hook input from stdin
        try:
            hook_input = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        # 2. Build session fingerprint for dedup
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        cycle_key = f"{session_id}-{int(time.time() // 60)}"  # 1-minute window dedup
        fingerprint = _session_fingerprint(cycle_key)

        if _already_flushed(state_dir, fingerprint):
            _log(state_dir, f"Skipped: already flushed this cycle ({fingerprint})")
            print(json.dumps({"continue": True}))
            return

        # 3. Gather session context
        context = _gather_session_context(hook_input)

        # 4. Build memory content
        content = _build_memory_content(context)

        # NO_REPLY pattern: if there is nothing meaningful to save, skip
        if not context.get("completion_state") and not context.get("preserved_context"):
            _log(state_dir, "Skipped: no active goals or preserved context to flush")
            print(json.dumps({"continue": True}))
            return

        # 5. Build memory items
        now_iso = datetime.now(timezone.utc).isoformat()
        shared_item = {
            "content": content,
            "context": "session-continuity",
            "document_id": f"precompact-{context.get('session_id', 'unknown')}-{fingerprint}",
            "timestamp": now_iso,
            "metadata": {
                "source": "precompact-hook",
                "session_id": context.get("session_id", "unknown"),
                "output_style": context.get("output_style", "unknown"),
                "git_branch": context.get("git_branch", "unknown"),
            },
        }

        # 6. Retain to shared bank (always)
        _retain(SHARED_BANK, [shared_item], state_dir)

        # 7. Retain to private bank (only for System 3 sessions)
        if _is_system3_session():
            private_item = dict(shared_item)
            private_item["context"] = "system3-active-goals"
            private_item["document_id"] = (
                f"s3-precompact-{context.get('session_id', 'unknown')}-{fingerprint}"
            )
            _retain(PRIVATE_BANK, [private_item], state_dir)
            _log(state_dir, "Flushed to both banks (System 3 session)")
        else:
            _log(state_dir, "Flushed to shared bank only")

        # 8. Mark this cycle as flushed
        _mark_flushed(state_dir, fingerprint)

    except Exception as exc:
        # NEVER block compaction
        _log(state_dir, f"ERROR: {exc}")

    # ALWAYS allow compaction to proceed
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
