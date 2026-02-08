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
echo "Generating baseline..."
zerorepo init "${PROJECT_PATH}" \
    --project-path "${PROJECT_PATH}" \
    --exclude "${EXCLUDE}"

echo ""
echo "Baseline generated at: ${PROJECT_PATH}/.zerorepo/baseline.json"
echo "=== Done ==="
