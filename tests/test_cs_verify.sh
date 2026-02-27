#!/bin/bash
# test_cs_verify.sh — Tests for cs-verify check_repomap_freshness()
#
# Tests:
#   1. ENFORCE=1, last_synced < last_validated  → exit non-zero (stale, blocking)
#   2. ENFORCE=1, last_synced > last_validated  → exit 0 (fresh)
#   3. COBUILDER_PIPELINE_DOT unset             → exit 0 (skip)
#   4. No validated entries in transitions file → exit 0 (skip)

set -euo pipefail

PASS=0
FAIL=0
ERRORS=()

# --- Helpers ---
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); ERRORS+=("$1"); }

run_freshness_check() {
    # Source only the check_repomap_freshness function from cs-verify.
    # We do this by extracting the function body and eval-ing it, then calling it.
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    local cs_verify="$script_dir/.claude/scripts/completion-state/cs-verify"

    # Extract the function definition and call it in a subshell
    bash -c "
        $(sed -n '/^check_repomap_freshness()/,/^}/p' "$cs_verify")
        VERBOSE=\${VERBOSE:-false}
        check_repomap_freshness
    "
}

# --- Test Setup ---
TMPDIR_BASE=$(mktemp -d)
trap 'rm -rf "$TMPDIR_BASE"' EXIT

PIPELINE_DOT="$TMPDIR_BASE/pipeline"
REPO_NAME="test-repo"
REPOMAP_DIR="$TMPDIR_BASE/.repomap"
CONFIG_FILE="$REPOMAP_DIR/config.yaml"
TRANSITIONS_FILE="${PIPELINE_DOT}.transitions.jsonl"

# Create .repomap directory
mkdir -p "$REPOMAP_DIR"

# Timestamps: validated=T+10, older_synced=T, newer_synced=T+20
TS_VALIDATED="2026-01-01T10:00:10Z"
TS_OLDER="2026-01-01T10:00:00Z"
TS_NEWER="2026-01-01T10:00:20Z"

# Helper: write transitions file with a "validated" entry at a given timestamp
write_transitions() {
    local ts="$1"
    cat > "$TRANSITIONS_FILE" <<EOF
{"node_id": "node-1", "old_status": "pending", "new_status": "validated", "timestamp": "$ts"}
EOF
}

# Helper: write config.yaml with a given last_synced timestamp
write_config() {
    local ts="$1"
    cat > "$CONFIG_FILE" <<EOF
repos:
  - name: $REPO_NAME
    last_synced: "$ts"
EOF
}

echo "=== cs-verify check_repomap_freshness tests ==="
echo ""

# --- Test 1: Stale baseline, ENFORCE=1 → non-zero exit ---
echo "Test 1: Stale baseline (last_synced < last_validated), ENFORCE=1 → blocking exit"
write_transitions "$TS_VALIDATED"
write_config "$TS_OLDER"

export COBUILDER_PIPELINE_DOT="$PIPELINE_DOT"
export COBUILDER_REPO_NAME="$REPO_NAME"
export COBUILDER_ENFORCE_FRESHNESS="1"
export CLAUDE_PROJECT_DIR="$TMPDIR_BASE"
export VERBOSE=false

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -ne 0 ]; then
    pass "Test 1: Non-zero exit when stale and ENFORCE=1"
else
    fail "Test 1: Expected non-zero exit for stale baseline, got 0"
fi

# --- Test 2: Fresh baseline, ENFORCE=1 → exit 0 ---
echo "Test 2: Fresh baseline (last_synced > last_validated), ENFORCE=1 → exit 0"
write_config "$TS_NEWER"

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 2: Exit 0 when baseline is fresh"
else
    fail "Test 2: Expected exit 0 for fresh baseline, got $EXIT_CODE"
fi

# --- Test 3: COBUILDER_PIPELINE_DOT unset → exit 0 (skip) ---
echo "Test 3: COBUILDER_PIPELINE_DOT unset → silently skip (exit 0)"
unset COBUILDER_PIPELINE_DOT

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 3: Exit 0 when COBUILDER_PIPELINE_DOT is unset"
else
    fail "Test 3: Expected exit 0 when pipeline not configured, got $EXIT_CODE"
fi

# Restore for remaining tests
export COBUILDER_PIPELINE_DOT="$PIPELINE_DOT"

# --- Test 4: COBUILDER_REPO_NAME unset → exit 0 (skip) ---
echo "Test 4: COBUILDER_REPO_NAME unset → silently skip (exit 0)"
unset COBUILDER_REPO_NAME

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 4: Exit 0 when COBUILDER_REPO_NAME is unset"
else
    fail "Test 4: Expected exit 0 when repo not configured, got $EXIT_CODE"
fi

# Restore
export COBUILDER_REPO_NAME="$REPO_NAME"

# --- Test 5: No validated entries in transitions file → exit 0 ---
echo "Test 5: No validated entries in transitions.jsonl → exit 0 (skip)"
cat > "$TRANSITIONS_FILE" <<EOF
{"node_id": "node-1", "old_status": "pending", "new_status": "active", "timestamp": "2026-01-01T10:00:05Z"}
EOF

write_config "$TS_OLDER"  # Older than active, but no "validated" entries

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 5: Exit 0 when no validated transitions exist"
else
    fail "Test 5: Expected exit 0 when no validated entries, got $EXIT_CODE"
fi

# Restore transitions with validated entry
write_transitions "$TS_VALIDATED"

# --- Test 6: Stale baseline, ENFORCE=0 (warning only) → exit 0 ---
echo "Test 6: Stale baseline, ENFORCE=0 → warning only (exit 0)"
write_config "$TS_OLDER"
export COBUILDER_ENFORCE_FRESHNESS="0"

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 6: Exit 0 (warning only) when stale and ENFORCE=0"
else
    fail "Test 6: Expected exit 0 for warning-only mode, got $EXIT_CODE"
fi

# --- Test 7: Missing transitions file → exit 0 ---
echo "Test 7: Missing .transitions.jsonl → silently skip (exit 0)"
rm -f "$TRANSITIONS_FILE"
export COBUILDER_ENFORCE_FRESHNESS="1"

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 7: Exit 0 when transitions file does not exist"
else
    fail "Test 7: Expected exit 0 when transitions file missing, got $EXIT_CODE"
fi

# --- Test 8: Missing .repomap/config.yaml → exit 0 ---
echo "Test 8: Missing .repomap/config.yaml → silently skip (exit 0)"
# Restore transitions file but remove config
write_transitions "$TS_VALIDATED"
rm -f "$CONFIG_FILE"

EXIT_CODE=0
run_freshness_check 2>/dev/null || EXIT_CODE=$?
if [ "$EXIT_CODE" -eq 0 ]; then
    pass "Test 8: Exit 0 when .repomap/config.yaml does not exist"
else
    fail "Test 8: Expected exit 0 when config missing, got $EXIT_CODE"
fi

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ $FAIL -gt 0 ]; then
    echo ""
    echo "Failures:"
    for err in "${ERRORS[@]}"; do
        echo "  - $err"
    done
    exit 1
fi

exit 0
