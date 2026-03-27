# Doc-Gardener Pre-Push Hook Implementation

**Date**: 2026-03-25  
**Node**: impl_hook  
**Pipeline**: PRD-DOC-GARDENER-002

## Implementation Summary

A PreToolUse hook that intercepts `git push` commands and blocks if doc-gardener violations remain.

## Key Design Decisions

### Hook Registration
- Location: `.claude/settings.json` → `hooks.PreToolUse`
- Matcher: `"Bash"` (intercepts all Bash commands)
- Timeout: 90 seconds

### Fast Path Optimization
- `_has_real_git_push()` regex checks if command contains standalone `git push`
- Ignores occurrences in quoted strings
- Non-push commands return `approve` in < 1ms

### Bypass Methods (5 options)
1. `DOC_GARDENER_SKIP=1` env var
2. `DOC_GARDENER_SKIP=1 git push` inline
3. `git push --no-verify`
4. `git push --skip-lint`
5. `touch .claude/.doc-gardener-skip`

### Testing Commands
```bash
# Test blocking
echo '{"tool_input": {"command": "git push"}}' | python3 .claude/hooks/doc-gardener-pre-push-hook.py

# Test bypass
echo '{"tool_input": {"command": "git push --no-verify"}}' | python3 .claude/hooks/doc-gardener-pre-push-hook.py
```
