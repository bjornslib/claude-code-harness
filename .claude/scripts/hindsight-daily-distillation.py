#!/usr/bin/env python3
"""
Daily Session Distillation Script (F3.3)

Cron-triggered script that distills recent session narratives into consolidated
patterns using Hindsight's reflect + retain APIs.

Workflow:
  1. Load last distillation timestamp (skip already-processed narratives)
  2. Recall recent session narratives from Hindsight (last 24h or since last run)
  3. Reflect on recalled narratives with budget=high to synthesize patterns
  4. Retain consolidated patterns to both shared and private banks
  5. Update last distillation timestamp

Usage:
  python .claude/scripts/hindsight-daily-distillation.py
  python .claude/scripts/hindsight-daily-distillation.py --dry-run
  python .claude/scripts/hindsight-daily-distillation.py --bank claude-harness-setup
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

# --- Configuration ---

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
SHARED_BANK = os.environ.get("HINDSIGHT_SHARED_BANK", "claude-harness-setup")
PRIVATE_BANK = os.environ.get("HINDSIGHT_PRIVATE_BANK", "system3-private")
API_TIMEOUT = 30  # Higher timeout for reflect operations
RECALL_LIMIT = 50  # Max narratives to process per run

# State tracking
STATE_DIR = Path(
    os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
) / ".claude" / "state" / "hindsight-distillation"
LAST_RUN_FILE = STATE_DIR / "last_distillation.json"
LOG_FILE = STATE_DIR / "distillation.log"


# --- Logging ---


def _log(msg: str, level: str = "INFO") -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line, file=sys.stderr)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# --- Hindsight API Helpers ---


def _check_health() -> bool:
    """Verify Hindsight is available and healthy."""
    try:
        req = Request(f"{HINDSIGHT_BASE_URL}/health")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "healthy"
    except Exception as exc:
        _log(f"Health check failed: {exc}", "ERROR")
        return False


def _recall(bank_id: str, query: str, limit: int = RECALL_LIMIT) -> list:
    """Recall memories from a Hindsight bank."""
    params = urlencode({"query": query, "n_results": limit})
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{quote(bank_id, safe='')}/memories/recall?{params}"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=API_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("results", data.get("memories", []))
    except Exception as exc:
        _log(f"Recall from {bank_id} failed: {exc}", "ERROR")
        return []


def _reflect(bank_id: str, budget: str = "high") -> dict:
    """Trigger reflection on a Hindsight bank to synthesize patterns."""
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{quote(bank_id, safe='')}/reflect"
    payload = json.dumps({"budget": budget}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:  # Reflect can take longer
            return json.loads(resp.read())
    except Exception as exc:
        _log(f"Reflect on {bank_id} failed: {exc}", "ERROR")
        return {}


def _retain(bank_id: str, items: list) -> bool:
    """Store items in a Hindsight bank."""
    url = f"{HINDSIGHT_BASE_URL}/v1/default/banks/{quote(bank_id, safe='')}/memories"
    payload = json.dumps({"items": items, "async": True}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=API_TIMEOUT) as resp:
            return True
    except Exception as exc:
        _log(f"Retain to {bank_id} failed: {exc}", "ERROR")
        return False


# --- State Management ---


def _load_last_run() -> datetime | None:
    """Load timestamp of last successful distillation."""
    if not LAST_RUN_FILE.exists():
        return None
    try:
        with open(LAST_RUN_FILE) as f:
            data = json.load(f)
        ts = data.get("last_distillation")
        if ts:
            return datetime.fromisoformat(ts)
    except Exception as exc:
        _log(f"Failed to load last run state: {exc}", "WARN")
    return None


def _save_last_run(timestamp: datetime) -> None:
    """Save timestamp of successful distillation."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "last_distillation": timestamp.isoformat(),
            "narratives_processed": True,
        }
        with open(LAST_RUN_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        _log(f"Failed to save last run state: {exc}", "ERROR")


# --- Core Distillation Logic ---


def _filter_recent_narratives(memories: list, since: datetime) -> list:
    """Filter memories to only those after the given timestamp."""
    recent = []
    for mem in memories:
        # Handle various timestamp field names
        ts_str = mem.get("timestamp") or mem.get("created_at") or mem.get("date")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts > since:
                    recent.append(mem)
                    continue
            except (ValueError, TypeError):
                pass
        # If no parseable timestamp, include it (better safe than missing data)
        recent.append(mem)
    return recent


def _build_distillation_summary(
    narratives: list, reflection: dict, run_time: datetime
) -> str:
    """Build a consolidated distillation summary from narratives + reflection."""
    narrative_count = len(narratives)

    # Extract session IDs from narratives
    session_ids = []
    for n in narratives:
        content = n.get("content", "") if isinstance(n, dict) else str(n)
        if "Session:" in content or "session_id" in str(n.get("metadata", {})):
            meta = n.get("metadata", {}) if isinstance(n, dict) else {}
            sid = meta.get("session_id", "unknown")
            if sid not in session_ids:
                session_ids.append(sid)

    # Extract reflection insights
    insights = reflection.get("insights", reflection.get("summary", "No insights generated"))
    if isinstance(insights, list):
        insights = "\n".join(f"- {i}" for i in insights)

    patterns = reflection.get("patterns", [])
    if isinstance(patterns, list) and patterns:
        pattern_text = "\n".join(f"- {p}" for p in patterns)
    else:
        pattern_text = "No cross-session patterns detected"

    return f"""## Daily Distillation Summary
**Generated**: {run_time.isoformat()}
**Narratives Processed**: {narrative_count}
**Sessions Covered**: {', '.join(session_ids[:10]) if session_ids else 'N/A'}

### Synthesized Insights
{insights}

### Cross-Session Patterns
{pattern_text}

### Distillation Metadata
- Source: hindsight-daily-distillation.py
- Bank: {SHARED_BANK}
- Budget: high
- Narrative window: last 24h (or since last distillation)"""


def run_distillation(dry_run: bool = False, bank: str | None = None) -> bool:
    """
    Execute the daily distillation pipeline.

    Returns True if distillation succeeded, False otherwise.
    """
    target_bank = bank or SHARED_BANK
    run_time = datetime.now(timezone.utc)

    _log(f"Starting daily distillation (bank={target_bank}, dry_run={dry_run})")

    # Step 0: Health check
    if not _check_health():
        _log("Hindsight not available, aborting distillation", "ERROR")
        return False

    # Step 1: Determine time window
    last_run = _load_last_run()
    if last_run:
        since = last_run
        _log(f"Processing narratives since last run: {since.isoformat()}")
    else:
        since = run_time - timedelta(hours=24)
        _log(f"No previous run found, processing last 24h since: {since.isoformat()}")

    # Step 2: Recall recent session narratives
    _log("Recalling session narratives...")
    narratives = _recall(
        target_bank,
        query="session narrative GEO chain goal experience outcome",
        limit=RECALL_LIMIT,
    )

    if not narratives:
        _log("No narratives found, nothing to distill")
        if not dry_run:
            _save_last_run(run_time)
        return True

    # Filter to recent only
    recent = _filter_recent_narratives(narratives, since)
    _log(f"Found {len(narratives)} total narratives, {len(recent)} since last run")

    if not recent:
        _log("No new narratives since last distillation")
        if not dry_run:
            _save_last_run(run_time)
        return True

    # Step 3: Reflect to synthesize patterns
    _log(f"Running reflect(budget=high) on {target_bank}...")

    if dry_run:
        _log("[DRY RUN] Would reflect on bank, skipping")
        reflection = {"insights": "DRY RUN - no reflection performed", "patterns": []}
    else:
        reflection = _reflect(target_bank, budget="high")

    if not reflection:
        _log("Reflection returned empty result", "WARN")
        reflection = {"insights": "Reflection produced no output", "patterns": []}

    # Step 4: Build consolidated summary
    summary = _build_distillation_summary(recent, reflection, run_time)
    _log(f"Distillation summary built ({len(summary)} chars)")

    if dry_run:
        _log("[DRY RUN] Summary preview:")
        print(summary)
        return True

    # Step 5: Retain to both banks
    item = {
        "content": summary,
        "context": "daily-distillation",
        "timestamp": run_time.isoformat(),
        "metadata": {
            "source": "hindsight-daily-distillation",
            "type": "distillation-summary",
            "narratives_processed": len(recent),
            "since": since.isoformat(),
        },
    }

    success_shared = _retain(target_bank, [item])
    _log(f"Retain to shared bank ({target_bank}): {'OK' if success_shared else 'FAILED'}")

    success_private = _retain(PRIVATE_BANK, [item])
    _log(f"Retain to private bank ({PRIVATE_BANK}): {'OK' if success_private else 'FAILED'}")

    # Step 6: Save state
    if success_shared or success_private:
        _save_last_run(run_time)
        _log(f"Distillation complete. Processed {len(recent)} narratives.")
        return True
    else:
        _log("Both retain operations failed", "ERROR")
        return False


# --- CLI ---


def main():
    parser = argparse.ArgumentParser(
        description="Daily session distillation: synthesize Hindsight narratives into patterns"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview distillation without writing to Hindsight",
    )
    parser.add_argument(
        "--bank",
        type=str,
        default=None,
        help=f"Target bank (default: {SHARED_BANK})",
    )
    args = parser.parse_args()

    success = run_distillation(dry_run=args.dry_run, bank=args.bank)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
