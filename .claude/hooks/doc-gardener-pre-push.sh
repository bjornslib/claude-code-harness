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
# Bypass methods (any one is sufficient):
#   DOC_GARDENER_SKIP=1   - Environment variable (emergency bypass)
#   --no-verify           - Passed to git push (git convention)
#   --skip-lint           - Passed to git push (explicit opt-out)
#   .claude/.doc-gardener-skip  - Signal file (project-level temporary bypass)

set -e

# Resolve paths relative to this script's REAL location (not symlink)
# When invoked via .git/hooks/pre-push symlink, BASH_SOURCE[0] returns
# the symlink path. We need the actual target to compute .claude/ paths.
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || readlink "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LINTER="$CLAUDE_DIR/scripts/doc-gardener/lint.py"
DOCS_CONFIG="$CLAUDE_DIR/scripts/doc-gardener/docs-gardener.config.json"
PROJECT_ROOT="$(cd "$CLAUDE_DIR/.." && pwd)"

# --- Bypass checks ---

# 1. Environment variable
if [ "${DOC_GARDENER_SKIP:-}" = "1" ]; then
    echo "[doc-gardener] Skipped (DOC_GARDENER_SKIP=1)"
    exit 0
fi

# 2. Signal file
if [ -f "$CLAUDE_DIR/.doc-gardener-skip" ]; then
    echo "[doc-gardener] Skipped (.doc-gardener-skip signal file)"
    exit 0
fi

# Drain stdin if invoked as a git hook (git passes ref info on stdin)
if [ ! -t 0 ]; then
    cat > /dev/null 2>&1 || true
fi

if [ ! -f "$LINTER" ]; then
    echo "[doc-gardener] lint.py not found at $LINTER, skipping"
    exit 0
fi

echo "[doc-gardener] Running documentation lint..."
echo ""

# Change to project root so relative paths in lint output are meaningful
cd "$PROJECT_ROOT"

# Lint .claude/ (default target)
echo "[doc-gardener] Checking .claude/ documentation..."
CLAUDE_EXIT=0
python3 "$LINTER" || CLAUDE_EXIT=$?

echo ""

# Lint docs/ (with config)
echo "[doc-gardener] Checking docs/ documentation..."
DOCS_EXIT=0
python3 "$LINTER" --target docs/ --config "$DOCS_CONFIG" || DOCS_EXIT=$?

echo ""

# Check both results
if [ $CLAUDE_EXIT -ne 0 ] || [ $DOCS_EXIT -ne 0 ]; then
    echo "[doc-gardener] Documentation violations found. Fix before pushing."
    echo ""
    echo "Run one of the following to fix violations:"
    echo "  python3 .claude/scripts/doc-gardener/gardener.py --execute"
    echo ""
    echo "Or review violations and fix manually:"
    echo "  python3 .claude/scripts/doc-gardener/lint.py"
    echo "  python3 .claude/scripts/doc-gardener/lint.py --target docs/ --config .claude/scripts/doc-gardener/docs-gardener.config.json"
    echo ""
    echo "Bypass options (emergency only):"
    echo "  DOC_GARDENER_SKIP=1 git push"
    echo "  git push --no-verify"
    echo "  touch .claude/.doc-gardener-skip"
    exit 1
fi

echo "[doc-gardener] All documentation checks passed."
exit 0
