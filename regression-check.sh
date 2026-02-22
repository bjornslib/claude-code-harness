#!/usr/bin/env bash
# regression-check.sh — Epic 6 Regression Detection Workflow
#
# Runs a full regression check against a ZeroRepo project:
#   1. Backs up the current baseline as "before"
#   2. Runs zerorepo update (via zerorepo-run-pipeline.py) to regenerate the graph
#   3. Runs `zerorepo diff` to detect regressions between before and after
#   4. Outputs regression-check.dot into .zerorepo/ (or --output-dir)
#
# Usage:
#   ./regression-check.sh --project-path /path/to/project
#   ./regression-check.sh --project-path /path/to/project --pipeline pipeline.dot
#   ./regression-check.sh --project-path /path/to/project --output-dir /tmp/results
#
# Exit codes:
#   0 — No regressions detected
#   1 — Regressions detected (see regression-check.dot for details)
#   2 — Script usage/configuration error
#   3 — Update step failed
#
# Requirements:
#   - Python 3 with zerorepo installed (zerorepo CLI available)
#   - .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py available
#     relative to PROJECT_PATH
#
# PRD: PRD-S3-DOT-LIFECYCLE-001 / Epic 6

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

PROJECT_PATH=""
PIPELINE_DOT=""
OUTPUT_DIR=""
ZEROREPO_DIR=".zerorepo"
BASELINE_FILENAME="baseline.json"
BEFORE_FILENAME="baseline.before.json"
OUTPUT_FILENAME="regression-check.dot"
RUNNER_SCRIPT=".claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py"
VERBOSE=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
    echo "[regression-check] $*" >&2
}

log_verbose() {
    if [[ "$VERBOSE" -eq 1 ]]; then
        echo "[regression-check] [DEBUG] $*" >&2
    fi
}

usage() {
    cat >&2 <<EOF
Usage: $0 --project-path PATH [options]

Options:
  --project-path PATH   Path to the ZeroRepo project (must contain .zerorepo/)
  --pipeline PATH       Optional: Attractor .dot pipeline for in-scope filtering
  --output-dir PATH     Optional: Directory to write regression-check.dot
                        (default: PROJECT_PATH/.zerorepo/)
  --verbose             Enable verbose output
  -h, --help            Show this help message

Exit codes:
  0 — No regressions detected
  1 — Regressions detected (review regression-check.dot)
  2 — Configuration/usage error
  3 — Update pipeline step failed
EOF
    exit 2
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-path)
            PROJECT_PATH="$2"
            shift 2
            ;;
        --project-path=*)
            PROJECT_PATH="${1#*=}"
            shift
            ;;
        --pipeline)
            PIPELINE_DOT="$2"
            shift 2
            ;;
        --pipeline=*)
            PIPELINE_DOT="${1#*=}"
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --output-dir=*)
            OUTPUT_DIR="${1#*=}"
            shift
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "[regression-check] ERROR: Unknown argument: $1" >&2
            usage
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate inputs
# ---------------------------------------------------------------------------

if [[ -z "$PROJECT_PATH" ]]; then
    echo "[regression-check] ERROR: --project-path is required" >&2
    usage
fi

if [[ ! -d "$PROJECT_PATH" ]]; then
    echo "[regression-check] ERROR: Project path does not exist: $PROJECT_PATH" >&2
    exit 2
fi

ZEROREPO_BASEDIR="$PROJECT_PATH/$ZEROREPO_DIR"
if [[ ! -d "$ZEROREPO_BASEDIR" ]]; then
    echo "[regression-check] ERROR: .zerorepo/ not found in $PROJECT_PATH" >&2
    echo "[regression-check]        Run 'zerorepo init' first." >&2
    exit 2
fi

BASELINE_PATH="$ZEROREPO_BASEDIR/$BASELINE_FILENAME"
if [[ ! -f "$BASELINE_PATH" ]]; then
    echo "[regression-check] ERROR: Baseline not found: $BASELINE_PATH" >&2
    echo "[regression-check]        Run 'zerorepo init --project-path ...' to generate one." >&2
    exit 2
fi

# Resolve output directory
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$ZEROREPO_BASEDIR"
fi
mkdir -p "$OUTPUT_DIR"

OUTPUT_DOT="$OUTPUT_DIR/$OUTPUT_FILENAME"
BEFORE_PATH="$ZEROREPO_BASEDIR/$BEFORE_FILENAME"

log_verbose "PROJECT_PATH: $PROJECT_PATH"
log_verbose "BASELINE_PATH: $BASELINE_PATH"
log_verbose "BEFORE_PATH: $BEFORE_PATH"
log_verbose "OUTPUT_DOT: $OUTPUT_DOT"
log_verbose "PIPELINE_DOT: ${PIPELINE_DOT:-<none>}"

# ---------------------------------------------------------------------------
# Step 1: Back up current baseline as "before"
# ---------------------------------------------------------------------------

log "Step 1/3: Backing up current baseline → $BEFORE_PATH"
cp "$BASELINE_PATH" "$BEFORE_PATH"
log_verbose "Backup complete: $(wc -c < "$BEFORE_PATH") bytes"

# ---------------------------------------------------------------------------
# Step 2: Run zerorepo update to regenerate the graph
# ---------------------------------------------------------------------------

log "Step 2/3: Running zerorepo update pipeline..."

# Locate the runner script relative to PROJECT_PATH
RUNNER_PATH="$PROJECT_PATH/$RUNNER_SCRIPT"

if [[ -f "$RUNNER_PATH" ]]; then
    log_verbose "Using runner: $RUNNER_PATH"
    python "$RUNNER_PATH" \
        --operation update \
        --project-path "$PROJECT_PATH" \
        || {
            echo "[regression-check] ERROR: zerorepo update pipeline failed." >&2
            echo "[regression-check]        Review the output above for details." >&2
            exit 3
        }
else
    # Fallback: try zerorepo CLI directly
    log_verbose "Runner not found at $RUNNER_PATH, falling back to zerorepo CLI"
    log_verbose "Falling back to: zerorepo init --project-path $PROJECT_PATH"
    python -m zerorepo init \
        --project-path "$PROJECT_PATH" \
        || {
            echo "[regression-check] ERROR: zerorepo update (CLI fallback) failed." >&2
            exit 3
        }
fi

log "Update complete. New baseline at: $BASELINE_PATH"

# Verify the updated baseline exists
if [[ ! -f "$BASELINE_PATH" ]]; then
    echo "[regression-check] ERROR: Updated baseline not found after update step." >&2
    exit 3
fi

# ---------------------------------------------------------------------------
# Step 3: Run zerorepo diff
# ---------------------------------------------------------------------------

log "Step 3/3: Running regression check (diff)..."

DIFF_ARGS=(
    "$BEFORE_PATH"
    "$BASELINE_PATH"
    "--output" "$OUTPUT_DOT"
)

if [[ -n "$PIPELINE_DOT" ]]; then
    if [[ ! -f "$PIPELINE_DOT" ]]; then
        echo "[regression-check] WARNING: Pipeline DOT file not found: $PIPELINE_DOT" >&2
        echo "[regression-check]          Proceeding without in-scope filter." >&2
    else
        DIFF_ARGS+=("--pipeline" "$PIPELINE_DOT")
        log_verbose "Using pipeline filter: $PIPELINE_DOT"
    fi
fi

# Run zerorepo diff; exit code 1 means regressions found, 0 means clean
python -m zerorepo diff "${DIFF_ARGS[@]}"
DIFF_EXIT=$?

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

echo "" >&2
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "$DIFF_EXIT" -eq 0 ]]; then
    log "✓ REGRESSION CHECK PASSED — no regressions detected."
    log "  Output: $OUTPUT_DOT"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
else
    log "✗ REGRESSION CHECK FAILED — regressions detected!"
    log "  Review: $OUTPUT_DOT"
    log "  Before: $BEFORE_PATH"
    log "  After:  $BASELINE_PATH"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi
