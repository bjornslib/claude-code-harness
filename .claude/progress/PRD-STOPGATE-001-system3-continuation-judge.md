# PRD-STOPGATE-001: Smart System 3 Continuation Judge

## Problem Statement

The `double-shot-latte` plugin spawns an entire Claude Code instance (`claude --print --model haiku`) on every stop attempt, adding **30-60 seconds of overhead**. Its concept (evaluate whether the session should continue) is valuable for System 3 meta-orchestrator sessions, but the implementation is:

1. **Slow**: Spawns a full process (30-60s) instead of a direct API call (~3-5s)
2. **Untargeted**: Runs on EVERY session, not just System 3
3. **Generic**: Uses naive heuristics instead of evaluating against the System 3 closure protocol
4. **Redundant**: Duplicates checks already handled by `unified-stop-gate.sh` (todo continuation, promises)

## Solution

Replace `double-shot-latte`'s blind approach with a **smart, integrated System 3 continuation judge** that:

1. Lives in `unified_stop_gate/` as a proper checker following existing patterns
2. Uses the **Anthropic Python SDK** for a fast, direct Haiku 4.5 API call (~3-5s)
3. Only activates for `system3-*` session IDs (all other sessions: zero overhead)
4. Reads the **last 5 conversation turns** from the transcript
5. Evaluates against the **System 3 closure protocol** (not generic heuristics)
6. Provides actionable continuation **reason + suggestion** when blocking

## Architecture

### Execution Flow

```
unified-stop-gate.sh
  │
  ├─ Step 1: Completion Promise (P1) ← fast, mechanical
  ├─ Step 2: Orchestrator Guidance (P2.5) ← orch-* only
  ├─ Step 3: Beads Sync (P2) ← fast, git check
  ├─ Step 4: Todo Continuation (P3) ← fast, jq check
  ├─ Step 5: System3 Judge (P3.5) ← NEW, system3-* only, Haiku API
  │   └─ Only invoked if Steps 1-4 all PASS
  │   └─ Reads last 5 turns from transcript
  │   └─ Haiku evaluates against S3 closure protocol
  │   └─ Returns: {should_continue, reason, suggestion}
  │   └─ If should_continue → BLOCK with reason + suggestion
  └─ Step 6: Available Work (informational, never blocks)
```

### Key Design Decisions

1. **Late-stage evaluation**: Judge runs AFTER all mechanical checks. If promises are unfulfilled or beads unsynced, those fast checks block first — no API call wasted.
2. **Session prefix gating**: `CLAUDE_SESSION_ID` must start with `system3-` (set by `ccsystem3` launcher via `export CLAUDE_SESSION_ID="system3-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"`)
3. **Timeout protection**: 8-second timeout on the API call. On timeout → approve stop (fail-open).
4. **API key from environment**: `ANTHROPIC_API_KEY` must be in env (standard for hooks).

## Components

### 1. `unified_stop_gate/system3_continuation_judge.py` (NEW)

**Class**: `System3ContinuationJudgeChecker`
- Follows existing checker pattern (`__init__(config, session)` + `check() -> CheckResult`)
- Reads transcript from `session.transcript_path`
- Extracts last 5 user/assistant turns
- Calls Anthropic SDK sync client with Haiku 4.5
- Parses structured JSON response
- Returns CheckResult with P3_5_SYSTEM3_JUDGE priority

**Haiku System Prompt**: Evaluate whether a System 3 meta-orchestrator session has completed its closure protocol:
- Completion promises verified with proof?
- Post-session reflection stored to Hindsight?
- Validation-agent used for independent evaluation (not direct bd close)?
- Orchestrator tmux sessions cleaned up?
- Meaningful work accomplished (not premature stop)?
- Continuation items set or work genuinely complete?

**Haiku User Prompt**: Last 5 turns of conversation (user + assistant messages, tool use summaries)

**Structured Output**: `{should_continue: bool, reason: str, suggestion: str}`

### 2. `unified_stop_gate/config.py` (MODIFY)

- Add `is_system3` property to `EnvironmentConfig`:
  ```python
  @property
  def is_system3(self) -> bool:
      return bool(self.session_id and self.session_id.startswith("system3-"))
  ```
- Add `P3_5_SYSTEM3_JUDGE = 35` to `Priority` enum

### 3. `unified-stop-gate.sh` (MODIFY)

- Add Step 5 (between current Step 4 and Step 5) that:
  - Checks if `SESSION_ID` starts with `system3-`
  - If not → skip entirely (zero overhead)
  - If yes → invoke Python checker with 8s timeout
  - Parse JSON result
  - If `should_continue=true` → BLOCK with reason + suggestion

### 4. `.claude/settings.json` (ALREADY DONE)

- `double-shot-latte@superpowers-marketplace: false` (disabled)

## Acceptance Criteria

| # | Criterion | Validation Method |
|---|-----------|-------------------|
| AC-1 | Non-system3 sessions: stop hook completes in <500ms total | Time the hook without system3- prefix |
| AC-2 | System3 sessions without transcript: judge skipped gracefully | Run with system3- prefix but no transcript file |
| AC-3 | System3 sessions with transcript: judge evaluates in <8s | Time the API call with real transcript |
| AC-4 | Judge blocks premature System3 stops (no reflection, active orch) | Feed transcript showing incomplete protocol |
| AC-5 | Judge approves valid System3 stops (all protocol complete) | Feed transcript showing full protocol |
| AC-6 | Judge provides actionable suggestion when blocking | Verify reason + suggestion in block output |
| AC-7 | Existing checkers continue working unchanged | Run full test suite |
| AC-8 | Timeout handling: API timeout → approve stop (fail-open) | Test with unreachable API |
| AC-9 | Missing API key → skip judge gracefully | Unset ANTHROPIC_API_KEY and verify |

## Task Decomposition

### Epic: Core Implementation
1. **Update config.py** - Add `is_system3` property + `P3_5_SYSTEM3_JUDGE` priority
2. **Create system3_continuation_judge.py** - Full checker with Haiku evaluation
3. **Update unified-stop-gate.sh** - Integrate new step with gating + timeout

### Epic: E2E Validation
4. **Unit test: config changes** - Test is_system3 property
5. **Unit test: judge checker** - Mock API, test extraction + evaluation logic
6. **Integration test: shell script** - Test full stop gate with/without system3 prefix
7. **E2E test: real API** - Live Haiku call with sample transcript

## Performance Budget

| Scenario | Target | Mechanism |
|----------|--------|-----------|
| Non-system3 session | +0ms | Prefix check in bash |
| System3, mechanical check fails | +0ms | Early block before judge |
| System3, all checks pass, API call | +3-5s | Direct SDK call (Haiku) |
| System3, API timeout | +8s max | gtimeout/timeout wrapper |
| System3, no API key | +0ms | Skip gracefully |
