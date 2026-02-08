#!/usr/bin/env bash
set -euo pipefail

# zerorepo-generate.sh — Run ZeroRepo pipeline to generate delta report
# Usage: zerorepo-generate.sh <SPEC_FILE> [BASELINE] [MODEL] [OUTPUT_DIR]

if [ $# -lt 1 ]; then
    echo "Usage: zerorepo-generate.sh <SPEC_FILE> [BASELINE] [MODEL] [OUTPUT_DIR]"
    echo ""
    echo "Arguments:"
    echo "  SPEC_FILE   Path to PRD or design specification (required)"
    echo "  BASELINE    Path to baseline JSON (default: .zerorepo/baseline.json)"
    echo "  MODEL       LLM model for analysis (default: claude-sonnet-4-20250514)"
    echo "  OUTPUT_DIR  Output directory (default: .zerorepo/output)"
    exit 1
fi

SPEC_FILE="$1"
BASELINE="${2:-.zerorepo/baseline.json}"
MODEL="${3:-claude-sonnet-4-20250514}"
OUTPUT="${4:-.zerorepo/output}"

echo "=== ZeroRepo Generate ==="
echo "Spec file: ${SPEC_FILE}"
echo "Baseline: ${BASELINE}"
echo "Model: ${MODEL}"
echo "Output: ${OUTPUT}"

# Check if zerorepo is installed
if ! python -m zerorepo --version &>/dev/null; then
    echo "ERROR: zerorepo is not installed."
    echo ""
    echo "Install options:"
    echo "  pip install zerorepo"
    echo "  # Or from source:"
    echo "  cd trees/rpg-improve && pip install -e ."
    exit 1
fi

# Verify spec file exists
if [ ! -f "${SPEC_FILE}" ]; then
    echo "ERROR: Spec file not found: ${SPEC_FILE}"
    exit 1
fi

# Verify baseline exists
if [ ! -f "${BASELINE}" ]; then
    echo "ERROR: Baseline not found: ${BASELINE}"
    echo "Run zerorepo-init.sh first to generate the baseline."
    exit 1
fi

echo ""
echo "Running pipeline (5 stages, ~2.5 minutes)..."
echo "Setting LITELLM_REQUEST_TIMEOUT=1200"

export LITELLM_REQUEST_TIMEOUT=1200

zerorepo generate "${SPEC_FILE}" \
    --baseline "${BASELINE}" \
    --model "${MODEL}" \
    --output "${OUTPUT}"

echo ""
echo "Pipeline complete."
echo "Delta report: ${OUTPUT}/05-delta-report.md"
echo "=== Done ==="
