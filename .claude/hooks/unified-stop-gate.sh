#!/bin/bash
# unified-stop-gate.sh - UNIFIED stop hook (only hook that runs)
#
# Architecture:
#   1. Completion Promise Check: BLOCKS if open promises owned by this session
#   1.4 Active Background Agents: ALLOWS stop if non-lead team agents are in_progress
#   2. Orchestrator Guidance: BLOCKS orch-* sessions with unescalated blockers
#   3. Beads Sync Check: BLOCKS if .beads/ has uncommitted changes
#   4. Work Exhaustion Check: BLOCKS if work available but no sensible continuation
#   5. System 3 Judge: BLOCKS system3-* sessions if Haiku judge says continue
#   6. Work Available: INFORMS about priority-ordered work (NEVER blocks)
#
# Changes from v2:
#   - Removed momentum check blocking (user intent: inform, don't block)
#   - Removed stop attempt bypass logic (no longer needed)
#   - Added beads sync enforcement
#   - Added todo continuation enforcement
#   - Fixed priority ordering (P0 → P1 → P2...)
#   - Fixed contradictory output ("No open issues" check)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CS_VERIFY="$PROJECT_ROOT/.claude/scripts/completion-state/cs-verify"

# Read JSON from stdin (Claude Code passes context)
INPUT=$(cat)

# Export for Python subprocesses (needed by SessionInfo.from_hook_input)
export CLAUDE_HOOK_INPUT="$INPUT"

SESSION_ID="${CLAUDE_SESSION_ID:-}"

# --- Block rate-limiter ---
# After MAX_BLOCKS consecutive blocks in a single session, approve unconditionally.
# This prevents infinite stop-gate loops when the agent can't resolve the issue.
# NOTE: MAX_BLOCKS is intentionally NOT disclosed in block messages to prevent gaming.
MAX_BLOCKS=3
_SAFE_SESSION_ID="${SESSION_ID//[^a-zA-Z0-9_-]/}"   # sanitize for filename
BLOCK_COUNT_FILE="/tmp/stop-gate-blocks-${_SAFE_SESSION_ID:-default}.count"
CURRENT_BLOCKS=0
if [ -f "$BLOCK_COUNT_FILE" ]; then
    CURRENT_BLOCKS=$(cat "$BLOCK_COUNT_FILE" 2>/dev/null || echo 0)
fi

# --- Helper functions ---

output_json() {
    local decision="$1"
    local key="$2"  # unused, kept for compatibility
    local message="$3"
    # Use jq for fast JSON construction (avoids python3 startup overhead)
    if [ "$decision" = "approve" ]; then
        jq -n --arg msg "$message" '{"decision": "approve", "systemMessage": $msg}'
    else
        jq -n --arg msg "$message" '{"decision": "block", "reason": $msg}'
    fi
}

# block_gate: rate-limited block helper.
# Records block count and overrides to approve after MAX_BLOCKS.
block_gate() {
    local message="$1"
    CURRENT_BLOCKS=$((CURRENT_BLOCKS + 1))
    echo "$CURRENT_BLOCKS" > "$BLOCK_COUNT_FILE"

    if [ "$CURRENT_BLOCKS" -ge "$MAX_BLOCKS" ]; then
        # Reset counter on override-approve so next stop attempt starts fresh
        echo "0" > "$BLOCK_COUNT_FILE"
        output_json "approve" "systemMessage" "⚠️ STOP GATE OVERRIDE

The gate has blocked multiple times this session without resolution. Forcing approve to prevent an infinite loop.

Last block reason:
${message}"
    else
        output_json "block" "reason" "${message}"
    fi
    exit 0
}

# --- Step 1: Completion Promise Check (via cs-verify) ---
# REQUIRES CLAUDE_SESSION_ID - if not set, skip promise checking entirely

PROMISE_PASSED=true
PROMISE_MESSAGE=""
BG_AGENTS_ACTIVE=false  # set to true by Step 1.4 when background agents are found

if [[ "${CLAUDE_OUTPUT_STYLE:-}" == "orchestrator" ]]; then
    # Orchestrators and their native teammates don't own completion promises —
    # only System 3 creates promises. Skip check to prevent false positives when
    # workers inherit a system3-* CLAUDE_SESSION_ID from the parent shell.
    # (Same guard pattern as Steps 1.4, 1.5, 1.7, 5.)
    PROMISE_MESSAGE="Orchestrator session — promise check skipped"
elif [ -z "$SESSION_ID" ]; then
    # No session ID = no promise tracking = always OK to stop
    PROMISE_MESSAGE="No CLAUDE_SESSION_ID set - OK to stop"
elif [ ! -x "$CS_VERIFY" ]; then
    PROMISE_MESSAGE="cs-verify not found - promise check skipped"
else
    # Run cs-verify and capture exit code properly
    CS_EXIT=0
    CS_OUTPUT=$("$CS_VERIFY" --check --verbose 2>&1) || CS_EXIT=$?

    # cs-verify returns: 0=can stop, 2=cannot stop, 1=error
    if [ "$CS_EXIT" -eq 2 ]; then
        PROMISE_PASSED=false
        PROMISE_MESSAGE="$CS_OUTPUT"
    elif [ "$CS_EXIT" -eq 0 ]; then
        PROMISE_MESSAGE="$CS_OUTPUT"
    else
        # Error case - allow stop but note the error
        PROMISE_MESSAGE="Promise check error (allowing stop): $CS_OUTPUT"
    fi
fi

# --- Step 1.4: Active Background Agents Check ---
# If promise check failed for a system3 session, check if the session's TaskList
# has in_progress tasks owned by non-lead agents. If so, those agents will wake
# the session via SendMessage when they complete — allow stop now.
# Guard: CLAUDE_OUTPUT_STYLE != orchestrator (same as Steps 1.5, 1.7).

if [ "$PROMISE_PASSED" = false ] && [[ "$SESSION_ID" == system3-* ]] && [[ "${CLAUDE_OUTPUT_STYLE:-}" != "orchestrator" ]]; then
    _TASK_LIST_ID="${CLAUDE_CODE_TASK_LIST_ID:-}"
    if [ -n "$_TASK_LIST_ID" ]; then
        _TASK_DIR="$HOME/.claude/tasks/$_TASK_LIST_ID"
        if [ -d "$_TASK_DIR" ]; then
            _ACTIVE_AGENTS=$(CLAUDE_CODE_TASK_LIST_ID="$_TASK_LIST_ID" python3 - <<'ACTIVE_CHECK'
import json, os, glob

task_dir = os.path.join(
    os.path.expanduser("~"), ".claude", "tasks",
    os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "")
)
active = []
for f in glob.glob(os.path.join(task_dir, "*.json")):
    try:
        with open(f) as fp:
            t = json.load(fp)
        owner = t.get("owner", "")
        status = t.get("status", "")
        subject = t.get("subject", "")[:50]
        if status == "in_progress" and owner and owner not in ("team-lead", ""):
            active.append(f"  - {owner}: {subject}")
    except Exception:
        pass
if active:
    print("\n".join(active))
ACTIVE_CHECK
)
            if [ -n "$_ACTIVE_AGENTS" ]; then
                PROMISE_PASSED=true
                BG_AGENTS_ACTIVE=true   # signals Step 4 to skip task exhaustion check
                PROMISE_MESSAGE="Background team agents are actively working — session will resume via SendMessage when they complete.
Active in_progress tasks:
${_ACTIVE_AGENTS}"
            fi
        fi
    fi
fi

# If promises block, output immediately
if [ "$PROMISE_PASSED" = false ]; then
    block_gate "🚫 COMPLETION CRITERIA NOT MET

${PROMISE_MESSAGE}

To proceed:
1. Complete or verify your promises: cs-promise --mine
2. Or adopt/cancel orphaned promises
3. Session ID is auto-generated by ccsystem3"
fi

# --- Step 1.5: Heartbeat Existence Check (system3-* sessions only) ---
# Ensures System 3 sessions have spawned a session-scoped team with a heartbeat agent.
# Team naming convention: s3-live-${CLAUDE_SESSION_ID: -8}
# Example: system3-20260222T103045Z-7fe01d4c → s3-live-7fe01d4c
# Guard: CLAUDE_OUTPUT_STYLE != orchestrator prevents false-positives when orchestrators
# inherit a stale system3-* CLAUDE_SESSION_ID from a parent shell.

if [[ "$SESSION_ID" == system3-* ]] && [[ "${CLAUDE_OUTPUT_STYLE:-}" != "orchestrator" ]]; then
    TEAM_HASH="${SESSION_ID: -8}"
    TEAM_CONFIG="$HOME/.claude/teams/s3-live-${TEAM_HASH}/config.json"

    if [ ! -f "$TEAM_CONFIG" ]; then
        block_gate "🚫 NO SESSION-SCOPED TEAM

System 3 session detected but no s3-live-${TEAM_HASH} team exists.

The session-scoped team (s3-live-${TEAM_HASH}) must be created during PREFLIGHT
with at least an s3-heartbeat member.

To proceed:
1. Create the team: TeamCreate(team_name=\"s3-live-${TEAM_HASH}\")
2. Spawn the heartbeat agent into the team
3. Try stopping again"
    fi

    HAS_HEARTBEAT=$(jq '[.members[] | select(.name | startswith("s3-heartbeat"))] | length' "$TEAM_CONFIG" 2>/dev/null)
    if [ "$HAS_HEARTBEAT" -eq 0 ] 2>/dev/null; then
        block_gate "🚫 NO HEARTBEAT AGENT

System 3 team s3-live-${TEAM_HASH} exists but has no heartbeat member.

The s3-heartbeat agent must be spawned during PREFLIGHT to enable
work scanning and session keep-alive.

To proceed:
1. Spawn the heartbeat: Task(subagent_type=\"general-purpose\", model=\"haiku\", team_name=\"s3-live-${TEAM_HASH}\", name=\"s3-heartbeat\", ...)
2. Try stopping again"
    fi
fi

# --- Step 1.7: Pending GChat Questions Check (system3-* sessions only) ---
# S3 sessions must not stop if they have unanswered GChat questions for THIS session.
# The hook writes session_id (CLAUDE_SESSION_ID) into each marker file.
# Guard: CLAUDE_OUTPUT_STYLE != orchestrator prevents false-positives (same as Step 1.5).

if [[ "$SESSION_ID" == system3-* ]] && [[ "${CLAUDE_OUTPUT_STYLE:-}" != "orchestrator" ]]; then
    GCHAT_ASK_DIR="$PROJECT_ROOT/.claude/state/gchat-forwarded-ask"
    if [ -d "$GCHAT_ASK_DIR" ]; then
        GCHAT_PENDING_FOR_SESSION=0
        for marker in "$GCHAT_ASK_DIR"/*.json; do
            [ -f "$marker" ] || continue
            # Block on ANY marker that isn't definitively resolved or timed out.
            # This catches: pending, auth_failed, or any other non-terminal status.
            if python3 -c "
import json, sys, os
m = json.load(open('$marker'))
terminal = ('resolved', 'timeout')
if m.get('status') not in terminal and m.get('session_id') == os.environ.get('CLAUDE_SESSION_ID', ''):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                GCHAT_PENDING_FOR_SESSION=$((GCHAT_PENDING_FOR_SESSION + 1))
            fi
        done

        if [ "$GCHAT_PENDING_FOR_SESSION" -gt 0 ]; then
            block_gate "🚫 UNRESOLVED GCHAT QUESTIONS

You have $GCHAT_PENDING_FOR_SESSION unresolved GChat question(s) for this session.
(Status is not 'resolved' or 'timeout' — could be pending, auth_failed, or other.)

Spawn a blocking Haiku agent to poll for replies before stopping.
See output style section 'GChat AskUserQuestion Round-Trip' for the exact pattern.

If the poller previously failed (auth_failed), fix the issue and retry.
If the user already replied, manually update the marker status to 'resolved'.

Marker directory: $GCHAT_ASK_DIR"
        fi
    fi
fi

# --- Step 1.8: REMOVED (2026-02-22) ---
# Previously enforced AskUserQuestion programmatically before exit.
# Now handled by the Haiku judge (Step 5) which considers GChat markers
# as part of its holistic session evaluation. This avoids race conditions
# with timestamp-based state machines.

# --- Step 2: Orchestrator Guidance Check (orch-* sessions only) ---

if [[ "$SESSION_ID" == orch-* ]]; then
    # Use gtimeout on macOS (GNU coreutils), fallback to timeout on Linux
    TIMEOUT_CMD="timeout"
    if command -v gtimeout &> /dev/null; then
        TIMEOUT_CMD="gtimeout"
    fi

    ORCH_EXIT=0
    ORCH_RESULT=$(cd "$PROJECT_ROOT" && $TIMEOUT_CMD 20s python3 << 'ORCH_CHECK'
import json
import sys
import os

sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()), '.claude', 'hooks'))

try:
    from unified_stop_gate.checkers import OrchestratorGuidanceChecker
    from unified_stop_gate.config import EnvironmentConfig, PathResolver

    config = EnvironmentConfig.from_env()
    paths = PathResolver(config=config)
    checker = OrchestratorGuidanceChecker(config, paths)
    result = checker.check()

    if not result.passed:
        print(json.dumps({"passed": False, "message": result.message}))
    else:
        print(json.dumps({"passed": True, "message": result.message}))
except Exception as e:
    print(json.dumps({"passed": True, "message": f"Orchestrator check error: {e}"}))
ORCH_CHECK
) || ORCH_EXIT=$?
    if [ $ORCH_EXIT -eq 124 ]; then
        echo "⚠️  Orchestrator check timed out (20s), allowing stop" >&2
        ORCH_RESULT='{"passed": true, "message": "Check timed out, allowing stop"}'
    elif [ $ORCH_EXIT -ne 0 ] && [ -z "$ORCH_RESULT" ]; then
        echo "⚠️  Orchestrator check failed (exit $ORCH_EXIT), allowing stop" >&2
        ORCH_RESULT='{"passed": true, "message": "Check failed (fail-open), allowing stop"}'
    fi

    # NOTE: jq's // operator treats false same as null, so '.passed // true' ALWAYS returns true.
    # Use explicit null check to preserve false values.
    ORCH_PASSED=$(printf '%s\n' "$ORCH_RESULT" | jq -r 'if .passed == null then "true" else (.passed | tostring) end')
    if [ "$ORCH_PASSED" = "false" ]; then
        ORCH_MSG=$(printf '%s\n' "$ORCH_RESULT" | jq -r '.message // ""')
        block_gate "$ORCH_MSG"
    fi
fi

# --- Step 3: Beads Sync Check ---
# Ensure beads changes are committed to git

BEADS_NEEDS_SYNC=false

if [ -d "$PROJECT_ROOT/.beads" ] && command -v bd &>/dev/null; then
    # Check if beads directory has uncommitted changes
    if git -C "$PROJECT_ROOT" status --porcelain .beads/ 2>/dev/null | grep -q .; then
        BEADS_NEEDS_SYNC=true
    fi
fi

if [ "$BEADS_NEEDS_SYNC" = true ]; then
    block_gate "🚫 BEADS SYNC REQUIRED

Beads directory has uncommitted changes. Run 'bd sync' before stopping.

Beads changes must be committed to git before stopping to prevent loss of work tracking.

To proceed:
1. Run: bd sync
2. Try stopping again"
fi

# --- Step 4: Work Exhaustion Check (replaces simple Todo Continuation) ---
# Three-layer evaluation: promises + beads + task sensibility
# Produces WORK_STATE_SUMMARY for Step 5 (System 3 Judge)

WORK_EXHAUSTION_PASSED=true
WORK_STATE_SUMMARY=""

TASK_LIST_ID="${CLAUDE_CODE_TASK_LIST_ID:-}"

# Skip Step 4 task exhaustion check if Step 1.4 found active background agents.
# The in_progress tasks in the list ARE the background agents — checking them again
# would block exactly the scenario Step 1.4 is designed to allow.
if [ "$BG_AGENTS_ACTIVE" = true ]; then
    WORK_STATE_SUMMARY="Background agents active (Step 1.4) — task exhaustion check skipped"
fi

if [ -n "$TASK_LIST_ID" ] && [ "$BG_AGENTS_ACTIVE" != true ]; then
    # Use gtimeout on macOS (GNU coreutils), fallback to timeout on Linux
    TIMEOUT_CMD="timeout"
    if command -v gtimeout &> /dev/null; then
        TIMEOUT_CMD="gtimeout"
    fi

    STEP4_EXIT=0
    STEP4_RESULT=$($TIMEOUT_CMD 20s python3 << 'WORK_CHECK'
import json
import sys
import os

sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()), '.claude', 'hooks'))

try:
    from unified_stop_gate.work_exhaustion_checker import WorkExhaustionChecker
    from unified_stop_gate.config import EnvironmentConfig

    config = EnvironmentConfig.from_env()
    checker = WorkExhaustionChecker(config)
    result = checker.check()
    work_summary = checker.work_state_summary

    print(json.dumps({
        "passed": result.passed,
        "message": result.message,
        "work_state_summary": work_summary
    }))
except Exception as e:
    print(json.dumps({
        "passed": True,
        "message": f"Work exhaustion check error (fail-open): {e}",
        "work_state_summary": ""
    }))
WORK_CHECK
) || STEP4_EXIT=$?
    if [ $STEP4_EXIT -eq 124 ]; then
        echo "⚠️  Work exhaustion check timed out (20s), allowing stop" >&2
        STEP4_RESULT='{"passed": true, "message": "Work exhaustion check timed out, allowing stop", "work_state_summary": ""}'
    elif [ $STEP4_EXIT -ne 0 ] && [ -z "$STEP4_RESULT" ]; then
        echo "⚠️  Work exhaustion check failed (exit $STEP4_EXIT), allowing stop" >&2
        STEP4_RESULT='{"passed": true, "message": "Work exhaustion check failed (fail-open), allowing stop", "work_state_summary": ""}'
    fi

    # Parse result (using explicit null check to preserve false values)
    STEP4_PASSED=$(printf '%s\n' "$STEP4_RESULT" | jq -r 'if .passed == null then "true" else (.passed | tostring) end')
    STEP4_MSG=$(printf '%s\n' "$STEP4_RESULT" | jq -r '.message // ""')

    # Extract work state summary for Step 5
    export WORK_STATE_SUMMARY=$(printf '%s\n' "$STEP4_RESULT" | jq -r '.work_state_summary // ""')

    if [ "$STEP4_PASSED" = "false" ]; then
        WORK_EXHAUSTION_PASSED=false
    fi
fi

if [ "$WORK_EXHAUSTION_PASSED" = false ]; then
    block_gate "$STEP4_MSG"
fi

# --- Step 4.5: REMOVED (2026-02-22) ---
# Previously: approved stop when GChat questions were pending ("async reply" pattern).
# Now: Step 1.7 blocks S3 sessions with pending GChat questions (forces poller spawn).
# Non-S3 sessions are auto-answered by Haiku (no pending markers created).
# Removing the early approval ensures Step 5 judge always runs for S3 sessions,
# which enforces the "must present AskUserQuestion before stopping" rule.

# --- Step 5: Continuation Judge (System 3 sessions only) ---
# Uses Haiku 4.5 API call to evaluate if System 3 session should continue
# Non-System 3 sessions skip this step entirely (Step 4 already passes them)
# Guard: CLAUDE_OUTPUT_STYLE != orchestrator prevents orchestrators that inherit a stale
# system3-* CLAUDE_SESSION_ID from triggering this judge (ccorch sets CLAUDE_OUTPUT_STYLE=orchestrator).

S3_MSG=""

if [[ "$SESSION_ID" == system3-* ]] && [[ "${CLAUDE_OUTPUT_STYLE:-}" != "orchestrator" ]]; then
    TIMEOUT_CMD="timeout"
    if command -v gtimeout &> /dev/null; then
        TIMEOUT_CMD="gtimeout"
    fi

    S3_EXIT=0
    S3_RESULT=$($TIMEOUT_CMD 20s python3 << 'S3_CHECK'
import json
import sys
import os

sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()), '.claude', 'hooks'))

try:
    from unified_stop_gate.system3_continuation_judge import System3ContinuationJudgeChecker
    from unified_stop_gate.config import EnvironmentConfig
    from unified_stop_gate.checkers import SessionInfo

    hook_input = json.loads(os.environ.get('CLAUDE_HOOK_INPUT', '{}'))
    config = EnvironmentConfig.from_env()
    session = SessionInfo.from_hook_input(hook_input)
    checker = System3ContinuationJudgeChecker(config, session)
    result = checker.check()

    print(json.dumps({"passed": result.passed, "message": result.message}))
except Exception as e:
    print(json.dumps({"passed": True, "message": f"System 3 judge error: {e}"}))
S3_CHECK
) || S3_EXIT=$?
    if [ $S3_EXIT -eq 124 ]; then
        echo "⚠️  System 3 judge timed out (20s), allowing stop" >&2
        S3_RESULT='{"passed": true, "message": "Judge timed out, allowing stop"}'
    elif [ $S3_EXIT -ne 0 ] && [ -z "$S3_RESULT" ]; then
        echo "⚠️  System 3 judge failed (exit $S3_EXIT), allowing stop" >&2
        S3_RESULT='{"passed": true, "message": "Judge failed (fail-open), allowing stop"}'
    fi

    # NOTE: jq's // operator treats false same as null, so '.passed // true' ALWAYS returns true.
    # Use explicit null check to preserve false values.
    S3_PASSED=$(printf '%s\n' "$S3_RESULT" | jq -r 'if .passed == null then "true" else (.passed | tostring) end')
    # ALWAYS extract message (not just on block)
    S3_MSG=$(printf '%s\n' "$S3_RESULT" | jq -r '.message // ""')

    if [ "$S3_PASSED" = "false" ]; then
        block_gate "$S3_MSG"
    fi
fi

# --- Step 6: Work Available (INFORMATIONAL ONLY - NEVER BLOCKS) ---
# Show priority-ordered work, but always approve

READY_WORK=""

if [ -d "$PROJECT_ROOT/.beads" ] && command -v bd &>/dev/null; then
    # Get all open tasks, sort by priority (P0 → P1 → P2...), take top 5
    READY_WORK=$(bd list --status=open 2>/dev/null | grep -E '\[P[0-9]\]' | sort -t'[' -k2,2n | head -5) || READY_WORK=""
fi

# Check for impl_complete tasks awaiting S3 validation
IMPL_COMPLETE_WORK=""
if [ -d "$PROJECT_ROOT/.beads" ] && command -v bd &>/dev/null; then
    IMPL_COMPLETE_WORK=$(bd list --status=impl_complete 2>/dev/null | grep -E '(beads-|bd-)' | head -5) || IMPL_COMPLETE_WORK=""
fi

# Build final message
MSG_PARTS="✅ ${PROMISE_MESSAGE}"

# Add Step 4 work-state context if available (even when passing)
if [ -n "$STEP4_MSG" ]; then
    MSG_PARTS="${MSG_PARTS}
📊 ${STEP4_MSG}"
fi

# Add System 3 judge result if present
if [ -n "$S3_MSG" ]; then
    MSG_PARTS="${MSG_PARTS}
🧠 ${S3_MSG}"
fi

# Only show work section if there's actual work (not just "No open issues")
if [ -n "$READY_WORK" ] && ! echo "$READY_WORK" | grep -q "No open issues"; then
    MSG_PARTS="${MSG_PARTS}

## 🚀 Available Work (Priority Order)

\`\`\`
${READY_WORK}
\`\`\`

**Decision Framework:**
- **Continue** if: P0-P2 tasks ready, clear implementation path
- **Stop** if: Only P3-P4 work, blocked on external factors, user feedback required

If continuing: Add specific todos and proceed autonomously."
fi

# Add impl_complete work section if present
if [ -n "$IMPL_COMPLETE_WORK" ]; then
    MSG_PARTS="${MSG_PARTS}

## Awaiting S3 Validation (impl_complete)

\`\`\`
${IMPL_COMPLETE_WORK}
\`\`\`

These tasks have been implemented but not yet validated by System 3's oversight team."
fi

# Session end GChat notifications DISABLED per user request (2026-02-22).
# Only AskUserQuestion forwarding is sent to GChat.
# Previously: sent "Session Ending" messages via gchat-send.sh --type session_end
# if [[ "$SESSION_ID" == system3-* ]] || [[ "$CLAUDE_OUTPUT_STYLE" == *system3* ]]; then
#     _session_summary="System 3 session ending."
#     if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
#         _session_summary="$_session_summary Session: $CLAUDE_SESSION_ID."
#     fi
#     _session_summary="$_session_summary Result: $RESULT"
#     "$CLAUDE_PROJECT_DIR/.claude/scripts/gchat-send.sh" --type session_end \
#         --title "Session Ending" \
#         "$_session_summary" 2>/dev/null || true
# fi

# Reset block counter on successful approval (prevents stale counts across stop attempts)
echo "0" > "$BLOCK_COUNT_FILE"

# Always approve (blocking happens earlier or not at all)
output_json "approve" "systemMessage" "$MSG_PARTS"
