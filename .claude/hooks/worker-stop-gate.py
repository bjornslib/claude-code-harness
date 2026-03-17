#!/usr/bin/env python3
"""Worker Stop Gate — validates worker behavior before allowing session exit.

Reads the worker's activity JSONL stream, the assigned SD/acceptance criteria,
and the node prompt, then calls a configurable LLM judge to determine whether
the worker followed its instructions and avoided TDD anti-patterns.

Only active when NWAVE_NODE_ID is set (injected by the pipeline runner).
Non-pipeline sessions pass through immediately.

Environment variables:
  NWAVE_NODE_ID          - Pipeline node ID (required for activation)
  NWAVE_SIGNALS_DIR      - Directory for signal/activity files
  NWAVE_SD_PATH          - Path to the Solution Design file
  NWAVE_AC_PATH          - Path to acceptance criteria YAML
  NWAVE_NODE_PROMPT      - The prompt assigned to this worker node
  NWAVE_RIGOR            - Rigor level: lean|standard|thorough|exhaustive
  NWAVE_STOP_GATE_PROFILE - Provider profile name (from providers.yaml)
  NWAVE_ANTI_PATTERNS_PATH - Path to anti-pattern catalog (optional)

Output:
  - JSON decision to stdout: {"decision": "approve"|"block", ...}
  - Signal file: {NWAVE_SIGNALS_DIR}/{NWAVE_NODE_ID}-verdict.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Early exit for non-pipeline sessions
# ---------------------------------------------------------------------------

NODE_ID = os.environ.get("NWAVE_NODE_ID", "")
if not NODE_ID:
    print(json.dumps({"decision": "approve", "systemMessage": "Not a pipeline worker"}))
    sys.exit(0)

SIGNALS_DIR = os.environ.get(
    "NWAVE_SIGNALS_DIR",
    os.environ.get("PIPELINE_SIGNALS_DIR", ""),
)
RIGOR = os.environ.get("NWAVE_RIGOR", "standard")

# Lean rigor skips all enforcement
if RIGOR == "lean":
    print(json.dumps({
        "decision": "approve",
        "systemMessage": f"[nWave] Rigor=lean — stop gate bypassed for {NODE_ID}",
    }))
    sys.exit(0)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SD_PATH = os.environ.get("NWAVE_SD_PATH", "")
AC_PATH = os.environ.get("NWAVE_AC_PATH", "")
NODE_PROMPT = os.environ.get("NWAVE_NODE_PROMPT", "")
STOP_GATE_PROFILE = os.environ.get("NWAVE_STOP_GATE_PROFILE", "worker-stop-gate")
ANTI_PATTERNS_PATH = os.environ.get(
    "NWAVE_ANTI_PATTERNS_PATH",
    os.path.join(
        os.environ.get("CLAUDE_PROJECT_DIR", "."),
        ".claude/skills/acceptance-test-runner/references/nwave-anti-patterns.md",
    ),
)

# Rate limiter — after N consecutive blocks, force approve
MAX_BLOCKS = 2
BLOCK_COUNT_FILE = f"/tmp/nwave-stop-gate-{NODE_ID}.count"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_file_safe(path: str, max_chars: int = 8000) -> str:
    """Read a file, returning empty string on failure. Truncates to max_chars."""
    if not path or not os.path.exists(path):
        return ""
    try:
        content = Path(path).read_text(encoding="utf-8")
        if len(content) > max_chars:
            return content[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return content
    except OSError:
        return ""


def _read_activity_stream() -> str:
    """Read the worker's activity JSONL stream."""
    if not SIGNALS_DIR:
        return ""
    activity_path = os.path.join(SIGNALS_DIR, f"{NODE_ID}-activity.jsonl")
    return _read_file_safe(activity_path, max_chars=12000)


def _load_anti_patterns() -> str:
    """Load the anti-pattern catalog, filtered by rigor level."""
    content = _read_file_safe(ANTI_PATTERNS_PATH, max_chars=6000)
    if not content:
        return "Anti-pattern catalog not available."
    return content


def _get_block_count() -> int:
    """Read current consecutive block count."""
    if not os.path.exists(BLOCK_COUNT_FILE):
        return 0
    try:
        return int(Path(BLOCK_COUNT_FILE).read_text().strip())
    except (OSError, ValueError):
        return 0


def _increment_block_count() -> int:
    """Increment and return block count."""
    count = _get_block_count() + 1
    try:
        Path(BLOCK_COUNT_FILE).write_text(str(count))
    except OSError:
        pass
    return count


def _reset_block_count() -> None:
    """Reset block count on approve."""
    try:
        if os.path.exists(BLOCK_COUNT_FILE):
            os.remove(BLOCK_COUNT_FILE)
    except OSError:
        pass


def _write_verdict_signal(verdict: dict) -> None:
    """Write verdict signal file for the pipeline runner to pick up."""
    if not SIGNALS_DIR:
        return
    signal_path = os.path.join(SIGNALS_DIR, f"{NODE_ID}-verdict.json")
    tmp_path = signal_path + ".tmp"
    try:
        os.makedirs(os.path.dirname(signal_path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(verdict, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.rename(tmp_path, signal_path)
    except OSError:
        pass


def _resolve_profile() -> dict:
    """Resolve the LLM profile from providers.yaml."""
    providers_path = os.path.join(
        os.environ.get("CLAUDE_PROJECT_DIR", "."),
        "cobuilder/engine/providers.yaml",
    )
    if not os.path.exists(providers_path):
        return {
            "model": "claude-haiku-4-5-20251001",
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "base_url": "https://api.anthropic.com",
            "max_tokens": 2048,
        }
    try:
        import yaml  # type: ignore[import-untyped]
        with open(providers_path) as fh:
            config = yaml.safe_load(fh)
        profiles = config.get("profiles", {})
        profile = profiles.get(STOP_GATE_PROFILE, {})
        if not profile:
            profile = profiles.get("worker-stop-gate", {})
        # Resolve $VAR references
        resolved = {}
        for key, val in profile.items():
            if isinstance(val, str) and val.startswith("$"):
                resolved[key] = os.environ.get(val[1:], val)
            else:
                resolved[key] = val
        return resolved
    except Exception:
        return {
            "model": "claude-haiku-4-5-20251001",
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "base_url": "https://api.anthropic.com",
            "max_tokens": 2048,
        }


def _call_judge(prompt: str, profile: dict) -> dict:
    """Call the LLM judge and return parsed JSON verdict."""
    try:
        import anthropic
    except ImportError:
        # If anthropic SDK not available, fail open
        return {"verdict": "pass", "reasoning": "anthropic SDK not available — fail open"}

    client = anthropic.Anthropic(
        api_key=profile.get("api_key", ""),
        base_url=profile.get("base_url", "https://api.anthropic.com"),
    )

    try:
        response = client.messages.create(
            model=profile.get("model", "claude-haiku-4-5-20251001"),
            max_tokens=profile.get("max_tokens", 2048),
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())
    except json.JSONDecodeError:
        # If LLM doesn't return valid JSON, fail open with warning
        return {
            "verdict": "pass",
            "reasoning": f"LLM response not valid JSON — fail open. Raw: {content[:200]}",
            "anti_patterns_detected": [],
        }
    except Exception as exc:
        # Network/API errors — fail open
        return {
            "verdict": "pass",
            "reasoning": f"LLM judge error — fail open: {exc}",
            "anti_patterns_detected": [],
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Read stdin (Claude Code hook input)
    raw = sys.stdin.read()

    # Check rate limiter
    current_blocks = _get_block_count()
    if current_blocks >= MAX_BLOCKS:
        _reset_block_count()
        verdict = {
            "node_id": NODE_ID,
            "verdict": "pass",
            "reasoning": f"Rate limiter: {MAX_BLOCKS} consecutive blocks — forced approve",
            "phase_compliance": None,
            "anti_patterns_detected": [],
            "rigor": RIGOR,
            "forced_approve": True,
        }
        _write_verdict_signal(verdict)
        print(json.dumps({
            "decision": "approve",
            "systemMessage": f"[nWave] Stop gate rate-limited — forced approve after {MAX_BLOCKS} blocks",
        }))
        return

    # Gather context
    activity_stream = _read_activity_stream()
    sd_content = _read_file_safe(SD_PATH, max_chars=4000)
    ac_content = _read_file_safe(AC_PATH, max_chars=4000)
    anti_patterns = _load_anti_patterns()

    # If no activity stream at all, that's suspicious but not blocking for lean
    if not activity_stream.strip():
        if RIGOR in ("thorough", "exhaustive"):
            count = _increment_block_count()
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"[nWave] No activity stream found for node {NODE_ID}. "
                    f"Expected file: {SIGNALS_DIR}/{NODE_ID}-activity.jsonl. "
                    "The worker appears to have completed without performing any tracked work. "
                    "Please ensure Edit/Write operations are being logged."
                ),
            }))
            return
        else:
            # standard: warn but approve
            verdict = {
                "node_id": NODE_ID,
                "verdict": "pass",
                "reasoning": "No activity stream — approved with warning",
                "phase_compliance": None,
                "anti_patterns_detected": [],
                "rigor": RIGOR,
            }
            _write_verdict_signal(verdict)
            print(json.dumps({
                "decision": "approve",
                "systemMessage": f"[nWave] Warning: no activity stream for {NODE_ID}",
            }))
            return

    # Build the judge prompt
    judge_prompt = f"""You are a TDD compliance judge for a software development pipeline.

## Your Task
Analyze a worker agent's activity stream and determine whether it followed its
assigned instructions and TDD discipline. Return a JSON verdict.

## Rigor Level: {RIGOR}
- standard: Block on critical anti-patterns (AP-001, AP-004), warn on others
- thorough: Block on most anti-patterns, all phases must be present
- exhaustive: Block on all anti-patterns, strict phase ordering required

## Node Assignment
**Node ID**: {NODE_ID}
**Assigned Prompt**: {NODE_PROMPT or 'Not provided'}

## Solution Design (context for what the worker should have implemented)
{sd_content or 'Not provided'}

## Acceptance Criteria
{ac_content or 'Not provided'}

## Anti-Pattern Catalog
{anti_patterns}

## Worker Activity Stream (chronological)
```jsonl
{activity_stream}
```

## Analysis Required
1. **Phase Compliance**: Did the worker follow RED→GREEN→REFACTOR ordering?
   - Were test files edited before source files?
   - Was there interleaving of test and source edits (good) vs all-tests-then-all-source (bad)?

2. **Anti-Pattern Detection**: Check each anti-pattern from the catalog against the activity.
   Apply the enforcement matrix for rigor level "{RIGOR}".

3. **Work Quality**: Based on the activity stream:
   - Did the worker appear to do meaningful work related to the assigned prompt?
   - Were the files touched consistent with the acceptance criteria?

## Required Output Format
Return ONLY a JSON object (no markdown, no explanation outside JSON):
```json
{{
    "verdict": "pass" | "fail",
    "phase_compliance": true | false,
    "anti_patterns_detected": [
        {{"id": "AP-001", "severity": "critical", "evidence": "First edit was src/auth.py at t=..."}}
    ],
    "work_assessment": "Brief assessment of whether the worker did the right work",
    "reasoning": "2-3 sentence explanation of the verdict",
    "recommendation": "What the worker should do if blocked (empty string if pass)"
}}
```
"""

    # Call the LLM judge
    profile = _resolve_profile()
    judge_result = _call_judge(judge_prompt, profile)

    verdict_status = judge_result.get("verdict", "pass")
    anti_patterns = judge_result.get("anti_patterns_detected", [])
    reasoning = judge_result.get("reasoning", "No reasoning provided")
    recommendation = judge_result.get("recommendation", "")

    # Build the full verdict signal
    verdict = {
        "node_id": NODE_ID,
        "verdict": verdict_status,
        "phase_compliance": judge_result.get("phase_compliance"),
        "anti_patterns_detected": anti_patterns,
        "work_assessment": judge_result.get("work_assessment", ""),
        "reasoning": reasoning,
        "rigor": RIGOR,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stop_gate_profile": STOP_GATE_PROFILE,
    }

    # Write verdict signal (always, regardless of pass/fail)
    _write_verdict_signal(verdict)

    if verdict_status == "fail":
        count = _increment_block_count()
        blocking_patterns = [
            f"  - {ap['id']}: {ap.get('evidence', 'no evidence')}"
            for ap in anti_patterns
            if ap.get("severity") in ("critical", "high")
        ]
        block_detail = "\n".join(blocking_patterns) if blocking_patterns else "  (see verdict file for details)"

        print(json.dumps({
            "decision": "block",
            "reason": (
                f"[nWave] Worker stop gate BLOCKED exit for node {NODE_ID}\n"
                f"Rigor: {RIGOR}\n"
                f"Reason: {reasoning}\n"
                f"Anti-patterns detected:\n{block_detail}\n"
                f"{'Recommendation: ' + recommendation if recommendation else ''}\n"
                f"Verdict file: {SIGNALS_DIR}/{NODE_ID}-verdict.json"
            ),
        }))
    else:
        _reset_block_count()
        print(json.dumps({
            "decision": "approve",
            "systemMessage": (
                f"[nWave] Worker stop gate PASSED for node {NODE_ID} "
                f"(rigor={RIGOR}, anti-patterns={len(anti_patterns)})"
            ),
        }))


if __name__ == "__main__":
    main()
