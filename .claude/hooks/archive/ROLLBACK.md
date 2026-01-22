# Rollback Instructions for Unified Stop Gate

## Quick Rollback

If the unified stop gate causes issues, restore the previous hook:

### Step 1: Update settings.json

Edit `.claude/settings.json` and change the Stop hook command:

**From (new):**
```json
"Stop": {
    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/unified-stop-gate.py"
}
```

**To (rollback):**
```json
"Stop": {
    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/archive/stop-gate.py"
}
```

### Step 2: Verify

Test the hook by running a session and attempting to stop.

## Archived Files

| File | Original Purpose |
|------|------------------|
| `stop-gate.py` | Original stop hook with comprehensive checks |
| `completion-gate.py` | Completion promise checking (integrated into P1) |

## Migration Notes

The unified stop gate consolidates multiple hooks into a priority-based system:

| Priority | Check | Previously |
|----------|-------|------------|
| P0 | Circuit Breaker | Built into stop-gate.py |
| P1 | Completion Promise | completion-gate.py |
| P2 | Beads Sync | Built into stop-gate.py |
| P3 | Todo Continuation | New |
| P4 | Git Status | Built into stop-gate.py |
| P5 | Business Outcomes | New |

## Reverting Individual Checks

If only specific checks are problematic:

### Disable P1 (Completion Promise)
Set environment variable:
```bash
export CLAUDE_ENFORCE_PROMISE=false
```

### Disable P5 (Business Outcomes)
Set environment variable:
```bash
export CLAUDE_ENFORCE_BO=false
```

### Increase P0 Circuit Breaker Threshold
```bash
export CLAUDE_MAX_ITERATIONS=50  # Default is 25
```

## Permanent Rollback

To permanently rollback:

1. Move archived hooks back to active:
   ```bash
   mv .claude/hooks/archive/stop-gate.py .claude/hooks/
   mv .claude/hooks/archive/completion-gate.py .claude/hooks/
   ```

2. Update settings.json to use original stop-gate.py

3. Remove unified stop gate:
   ```bash
   rm -rf .claude/hooks/unified_stop_gate/
   rm .claude/hooks/unified-stop-gate.py
   ```

## Contact

If issues persist, check the session logs or contact the maintainer.
