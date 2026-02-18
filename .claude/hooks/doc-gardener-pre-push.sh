#!/bin/bash
# Doc-Gardener Pre-Push Hook
# Runs documentation lint before allowing git push
# Exit 0 = push allowed, Exit 1 = push blocked
#
# Two integration modes:
#   1. Claude Code hook: Wired as PreToolUse in settings.json (auto)
#   2. Git pre-push hook: Symlink to .git/hooks/pre-push (manual)
#
# Usage:
#   .claude/hooks/doc-gardener-pre-push.sh         # Direct invocation
#   git push                                        # Via git hook symlink
#
# Environment:
#   DOC_GARDENER_SKIP=1   - Skip lint (emergency bypass)

set -e

# Allow emergency bypass
if [ "${DOC_GARDENER_SKIP:-}" = "1" ]; then
    echo "[doc-gardener] Skipped (DOC_GARDENER_SKIP=1)"
    exit 0
fi

# Resolve paths relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GARDENER="$CLAUDE_DIR/scripts/doc-gardener/gardener.py"

# Drain stdin if invoked as a git hook (git passes ref info on stdin)
if [ ! -t 0 ]; then
    cat > /dev/null 2>&1 || true
fi

if [ ! -f "$GARDENER" ]; then
    echo "[doc-gardener] gardener.py not found at $GARDENER, skipping"
    exit 0
fi

echo "[doc-gardener] Running documentation lint..."

EXIT_CODE=0
python3 "$GARDENER" --execute || EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[doc-gardener] Documentation violations found. Fix before pushing."
    echo "[doc-gardener] Run: python3 .claude/scripts/doc-gardener/gardener.py --report"
    exit 1
fi

echo "[doc-gardener] Documentation lint passed."
exit 0
