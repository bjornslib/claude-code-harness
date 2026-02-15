#!/usr/bin/env python3
"""
Stop hook: Update the capability self-model after each session.

Reads session outcomes (git activity, beads status, completion state) to infer
which domain was active and whether the session was successful.  Updates
confidence levels and success rates in .claude/capability_model.json.

Optionally stores a snapshot of the capability model in Hindsight for
cross-session trend analysis.

IMPORTANT: Stop hooks must output JSON in this format:
  {"decision": "approve", "systemMessage": "..."}

This hook always approves — it captures capability updates but never blocks stopping.

Hook type: Stop
Implements: F5.1 from PRD-S3-CLAWS-001 (Epic 5: Self-Model and Context Hygiene)
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

# -- Configuration -----------------------------------------------------------

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
API_TIMEOUT = 10
MAX_RECENT_OUTCOMES = 10  # Keep last N outcomes per domain
CONFIDENCE_ADJUSTMENT = 0.05  # How much confidence shifts per session


# -- Helpers -----------------------------------------------------------------

def _log(msg: str) -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    log_file = Path(project_dir) / ".claude" / "state" / "capability-update" / "capability.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _run_cmd(cmd: list, cwd: str = None, timeout: int = 5) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _load_capability_model(project_dir: str) -> dict:
    """Load the capability model from disk."""
    model_path = Path(project_dir) / ".claude" / "capability_model.json"
    if not model_path.exists():
        _log("capability_model.json not found, skipping")
        return {}
    try:
        with open(model_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"Failed to load capability_model.json: {exc}")
        return {}


def _save_capability_model(project_dir: str, model: dict) -> bool:
    """Save the capability model to disk."""
    model_path = Path(project_dir) / ".claude" / "capability_model.json"
    try:
        with open(model_path, "w") as f:
            json.dump(model, f, indent=2)
            f.write("\n")
        return True
    except OSError as exc:
        _log(f"Failed to save capability_model.json: {exc}")
        return False


def _detect_active_domains(project_dir: str) -> list:
    """Infer which domains were active in this session from git and beads."""
    domains = set()

    # Check recent git commits for file patterns
    diff = _run_cmd(["git", "diff", "--name-only", "HEAD~5"], cwd=project_dir)
    if not diff:
        diff = _run_cmd(["git", "diff", "--name-only", "--cached"], cwd=project_dir)

    diff_lower = diff.lower() if diff else ""

    # Map file patterns to domains
    if any(p in diff_lower for p in ["frontend", "react", "tsx", "jsx", "css", "tailwind", "component"]):
        domains.add("frontend_orchestration")
    if any(p in diff_lower for p in ["backend", "fastapi", "pydantic", ".py", "agent", "mcp"]):
        domains.add("backend_orchestration")
    if any(p in diff_lower for p in ["test", "spec", "pytest", "jest", "e2e", "acceptance"]):
        domains.add("testing")
    if any(p in diff_lower for p in ["prd", "epic", "acceptance-criteria", "design"]):
        domains.add("prd_writing")
    if any(p in diff_lower for p in ["deploy", "railway", "docker", "ci", "cd", "worktree"]):
        domains.add("devops")

    # Check output style for hints
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "").lower()
    if "system3" in output_style or "orchestrator" in output_style:
        # Orchestrator sessions typically involve backend orchestration
        domains.add("backend_orchestration")

    # Check active beads for domain hints
    active_beads = _run_cmd(["bd", "list", "--status=in_progress"], cwd=project_dir)
    if active_beads:
        beads_lower = active_beads.lower()
        if any(p in beads_lower for p in ["frontend", "ui", "react", "component"]):
            domains.add("frontend_orchestration")
        if any(p in beads_lower for p in ["backend", "api", "database", "agent"]):
            domains.add("backend_orchestration")
        if any(p in beads_lower for p in ["prd", "design", "spec"]):
            domains.add("prd_writing")
        if any(p in beads_lower for p in ["test", "e2e", "validation"]):
            domains.add("testing")
        if any(p in beads_lower for p in ["research", "investigate"]):
            domains.add("research")

    # Default: if we can't detect anything, attribute to backend orchestration
    if not domains:
        domains.add("backend_orchestration")

    return list(domains)


def _assess_session_success(project_dir: str) -> tuple:
    """Assess whether the session was successful. Returns (success: bool, reason: str)."""
    indicators_positive = 0
    indicators_negative = 0
    reasons = []

    # 1. Clean git status → positive signal
    git_status = _run_cmd(["git", "status", "--porcelain"], cwd=project_dir)
    if not git_status:
        indicators_positive += 1
        reasons.append("clean working tree")
    else:
        uncommitted = len(git_status.strip().split("\n"))
        if uncommitted > 5:
            indicators_negative += 1
            reasons.append(f"{uncommitted} uncommitted changes")

    # 2. Recent commits → positive signal
    recent = _run_cmd(["git", "log", "--oneline", "-3", "--since=2.hours.ago"], cwd=project_dir)
    if recent:
        commit_count = len(recent.strip().split("\n"))
        indicators_positive += min(commit_count, 2)
        reasons.append(f"{commit_count} recent commits")

    # 3. Closed beads → positive signal
    closed = _run_cmd(["bd", "list", "--status=closed"], cwd=project_dir)
    if closed and "No issues" not in closed:
        indicators_positive += 1
        reasons.append("beads closed")

    # 4. Completion state → check if promise completed
    cs_file = Path(project_dir) / ".claude" / "state" / "completion-state.json"
    if cs_file.exists():
        try:
            with open(cs_file) as f:
                cs = json.load(f)
            status = cs.get("status", "")
            if status in ("completed", "done"):
                indicators_positive += 2
                reasons.append("completion promise fulfilled")
            elif status == "failed":
                indicators_negative += 2
                reasons.append("completion promise failed")
        except Exception:
            pass

    success = indicators_positive > indicators_negative
    reason = "; ".join(reasons) if reasons else "no clear signals"
    return success, reason


def _update_domain(domain_data: dict, success: bool, reason: str, now_iso: str) -> dict:
    """Update a single domain's metrics."""
    domain_data["sessions_total"] = domain_data.get("sessions_total", 0) + 1
    if success:
        domain_data["sessions_successful"] = domain_data.get("sessions_successful", 0) + 1

    # Recalculate success rate
    total = domain_data["sessions_total"]
    successful = domain_data["sessions_successful"]
    domain_data["success_rate"] = round(successful / total, 3) if total > 0 else 0.0

    # Adjust confidence: nudge toward success rate, bounded [0.1, 0.95]
    current_conf = domain_data.get("confidence", 0.5)
    if success:
        new_conf = min(current_conf + CONFIDENCE_ADJUSTMENT, 0.95)
    else:
        new_conf = max(current_conf - CONFIDENCE_ADJUSTMENT, 0.1)
    domain_data["confidence"] = round(new_conf, 3)

    # Append to recent outcomes (ring buffer)
    outcomes = domain_data.get("recent_outcomes", [])
    outcomes.append({
        "timestamp": now_iso,
        "success": success,
        "reason": reason[:200],
    })
    domain_data["recent_outcomes"] = outcomes[-MAX_RECENT_OUTCOMES:]

    return domain_data


def _update_aggregate(model: dict) -> dict:
    """Recalculate aggregate metrics from domain data."""
    domains = model.get("domains", {})
    total_sessions = 0
    total_successful = 0
    best_domain = None
    best_conf = -1
    worst_domain = None
    worst_conf = 2

    for name, data in domains.items():
        total_sessions += data.get("sessions_total", 0)
        total_successful += data.get("sessions_successful", 0)
        conf = data.get("confidence", 0.5)
        if data.get("sessions_total", 0) > 0:
            if conf > best_conf:
                best_conf = conf
                best_domain = name
            if conf < worst_conf:
                worst_conf = conf
                worst_domain = name

    agg = model.get("aggregate", {})
    agg["total_sessions"] = total_sessions
    agg["total_successful"] = total_successful
    agg["overall_success_rate"] = round(total_successful / total_sessions, 3) if total_sessions > 0 else 0.0
    agg["strongest_domain"] = best_domain
    agg["weakest_domain"] = worst_domain
    model["aggregate"] = agg
    return model


def _retain_to_hindsight(model: dict, session_id: str, now_iso: str) -> bool:
    """Store a snapshot of the capability model in Hindsight."""
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{SHARED_BANK}/memories"

    # Build a human-readable summary
    domains = model.get("domains", {})
    agg = model.get("aggregate", {})
    lines = [
        "## Capability Self-Model Update",
        f"**Session**: {session_id}",
        f"**Time**: {now_iso}",
        f"**Overall**: {agg.get('total_sessions', 0)} sessions, "
        f"{agg.get('overall_success_rate', 0):.0%} success rate",
        "",
        "### Domain Confidence Levels",
    ]
    for name, data in sorted(domains.items()):
        conf = data.get("confidence", 0.5)
        total = data.get("sessions_total", 0)
        lines.append(f"- **{name}**: {conf:.0%} confidence ({total} sessions)")

    strongest = agg.get("strongest_domain")
    weakest = agg.get("weakest_domain")
    if strongest:
        lines.append(f"\n**Strongest**: {strongest}")
    if weakest:
        lines.append(f"**Weakest**: {weakest}")

    content = "\n".join(lines)

    item = {
        "content": content,
        "context": "capability-self-model",
        "document_id": f"capability-model-{session_id}",
        "timestamp": now_iso,
        "metadata": {
            "source": "stop-hook-capability-update",
            "session_id": session_id,
            "type": "capability-snapshot",
            "overall_success_rate": agg.get("overall_success_rate", 0.0),
        },
    }

    payload = json.dumps({"items": [item], "async": True}).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=API_TIMEOUT) as resp:
            return True
    except Exception as exc:
        _log(f"Hindsight retain FAILED: {exc}")
        return False


# -- Main --------------------------------------------------------------------

def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    try:
        # Read hook input from stdin (required for Stop hooks)
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    try:
        # 1. Load capability model
        model = _load_capability_model(project_dir)
        if not model:
            _log("No capability model found, skipping update")
            print(json.dumps({"decision": "approve", "systemMessage": "Capability model not found, update skipped"}))
            return

        # 2. Detect active domains
        active_domains = _detect_active_domains(project_dir)
        _log(f"Detected active domains: {active_domains}")

        # 3. Assess session success
        success, reason = _assess_session_success(project_dir)
        _log(f"Session success={success}, reason={reason}")

        now_iso = datetime.now(timezone.utc).isoformat()

        # 4. Update each active domain
        domains = model.get("domains", {})
        for domain_name in active_domains:
            if domain_name in domains:
                domains[domain_name] = _update_domain(domains[domain_name], success, reason, now_iso)
                _log(f"Updated domain {domain_name}: conf={domains[domain_name]['confidence']}")

        model["domains"] = domains
        model["_last_updated"] = now_iso

        # 5. Recalculate aggregates
        model = _update_aggregate(model)

        # 6. Save to disk
        saved = _save_capability_model(project_dir, model)

        # 7. Store snapshot in Hindsight (best-effort)
        hindsight_ok = False
        try:
            health_req = Request(f"{HINDSIGHT_BASE_URL}/health")
            with urlopen(health_req, timeout=3) as resp:
                health = json.loads(resp.read())
                if health.get("status") == "healthy":
                    hindsight_ok = _retain_to_hindsight(model, session_id, now_iso)
        except Exception:
            pass

        # Build status message
        parts = []
        if saved:
            parts.append(f"Capability model updated (domains: {', '.join(active_domains)})")
        if hindsight_ok:
            parts.append("snapshot stored in Hindsight")

        agg = model.get("aggregate", {})
        parts.append(f"overall: {agg.get('total_sessions', 0)} sessions, "
                     f"{agg.get('overall_success_rate', 0):.0%} success")

        msg = "; ".join(parts) if parts else "Capability update completed"

    except Exception as exc:
        _log(f"ERROR: {exc}")
        msg = f"Capability update error: {exc}"

    # Always approve stop
    print(json.dumps({"decision": "approve", "systemMessage": msg}))


if __name__ == "__main__":
    main()
