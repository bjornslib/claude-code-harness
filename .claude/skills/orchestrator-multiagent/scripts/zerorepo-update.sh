#!/usr/bin/env bash
set -euo pipefail

# zerorepo-update.sh — Regenerate ZeroRepo baseline after implementation
# Usage: zerorepo-update.sh [PROJECT_PATH] [EXCLUDE_PATTERNS]
#
# Backs up current baseline to baseline.prev.json before regenerating.

PROJECT_PATH="${1:-.}"
EXCLUDE="${2:-node_modules,__pycache__,.git,trees,venv,.zerorepo}"
BASELINE_DIR="${PROJECT_PATH}/.zerorepo"
BASELINE="${BASELINE_DIR}/baseline.json"
BACKUP="${BASELINE_DIR}/baseline.prev.json"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== ZeroRepo Update ==="
echo "Project path: ${PROJECT_PATH}"
echo "Exclude patterns: ${EXCLUDE}"
echo "Timestamp: ${TIMESTAMP}"

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

echo ""
echo "Running update via Python runner (backup + re-init)..."

# Use the centralized Python runner (handles backup internally)
RUNNER_SCRIPT="$(dirname "$0")/zerorepo-run-pipeline.py"

python "${RUNNER_SCRIPT}" \
    --operation update \
    --project-path "${PROJECT_PATH}" \
    --exclude "${EXCLUDE}"

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo ""
    echo "Updated: ${TIMESTAMP}"
    echo "=== Done ==="
else
    echo "=== Update Failed ==="
    exit $exit_code
fi
