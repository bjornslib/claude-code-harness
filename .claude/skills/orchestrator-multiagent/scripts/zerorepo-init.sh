#!/usr/bin/env bash
set -euo pipefail

# zerorepo-init.sh — Initialize ZeroRepo baseline for a codebase
# Usage: zerorepo-init.sh [PROJECT_PATH] [EXCLUDE_PATTERNS]

PROJECT_PATH="${1:-.}"
EXCLUDE="${2:-node_modules,__pycache__,.git,trees,venv,.zerorepo}"

echo "=== ZeroRepo Init ==="
echo "Project path: ${PROJECT_PATH}"
echo "Exclude patterns: ${EXCLUDE}"

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
echo "Running init via Python runner..."

# Use the centralized Python runner
RUNNER_SCRIPT="$(dirname "$0")/zerorepo-run-pipeline.py"

python "${RUNNER_SCRIPT}" \
    --operation init \
    --project-path "${PROJECT_PATH}" \
    --exclude "${EXCLUDE}"

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "=== Done ==="
else
    echo "=== Init Failed ==="
    exit $exit_code
fi
