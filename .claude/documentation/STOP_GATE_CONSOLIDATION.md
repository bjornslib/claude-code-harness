# Stop Gate Consolidation (2026-01-31)

## Problem

Previously, **THREE stop hooks** ran on every stop attempt, causing:
1. **3-minute delays** from plugin hooks reading entire transcript files
2. **Duplication** - multiple hooks checking similar things
3. **Blocking when shouldn't** - momentum check forced continuation
4. **Confusing output** - contradictory messages

## Solution

### Architecture Change

```
Before (3 hooks):
Stop → stop-gate.py (plugin, 3min delay)
    → momentum-check-stop.sh (plugin)
    → unified-stop-gate.sh (project)

After (1 hook):
Stop → unified-stop-gate.sh (project only)
    ├─ Step 1: Completion Promise Check (BLOCKS)
    ├─ Step 2: Orchestrator Guidance (BLOCKS orch-*)
    ├─ Step 3: Beads Sync Check (BLOCKS)
    ├─ Step 4: Todo Continuation (BLOCKS)
    └─ Step 5: Work Available (INFORMS, never blocks)
```

### Plugin Hooks Disabled

```bash
mv ~/.claude/plugins/cache/claude-orchestration \
   ~/.claude/plugins/cache/claude-orchestration.disabled
```

**Root cause of 3-minute delay**: Plugin's `stop-gate.py` line 59:
```python
lines = f.readlines()  # Reads ENTIRE transcript into memory
recent_lines = lines[-2000:]
```

For long sessions, transcript files are megabytes. This was the bottleneck.

### Key Changes

| Component | Before | After |
|-----------|--------|-------|
| Momentum check | BLOCKS after 2 attempts | INFORMS only, never blocks |
| Work prioritization | Arbitrary order | P0 → P1 → P2 sorted |
| Beads sync | Not enforced | BLOCKS if uncommitted |
| Todo continuation | Not enforced | BLOCKS if missing |
| Performance | 3 minutes | 61ms average |

### Completion-State Location

Completion promises are **project-specific**:
```
.claude/completion-state/
├── promises/      # Active promises (gitignored)
├── history/       # Completed promises (gitignored)
└── sessions/      # Session metadata (gitignored)
```

Scripts use `${CLAUDE_PROJECT_DIR:-$(pwd)}/.claude/completion-state`.

## Testing

Comprehensive test suite: `.claude/hooks/test-stop-gate.sh`

```bash
# Run tests
./.claude/hooks/test-stop-gate.sh

# Results (2026-01-31)
✅ Test 1: No Promises, No Work → approve (1s)
✅ Test 2: Open Promise Blocks → block (0s)
✅ Test 3: Todo Continuation Required → block (0s)
✅ Test 4: Performance Benchmark → 61ms avg
```

## User Intent Alignment

**Original requirements**:
1. ✅ Always share available bead tasks (non-blocking, priority-ordered)
2. ✅ Block if promises owned by current SESSION_ID are open
3. ✅ Inform/encourage if promises owned by other session IDs are open

**Changes made**:
- Momentum check changed from blocking to informational (respects user choice)
- Work displayed in priority order (P0 first)
- No contradictory output ("No open issues" filtered out)

## Migration Notes

If issues arise after this change:

### Rollback Plugin Hooks

```bash
# Re-enable plugin hooks (NOT recommended - they cause 3min delays)
mv ~/.claude/plugins/cache/claude-orchestration.disabled \
   ~/.claude/plugins/cache/claude-orchestration
```

### Restore Old Unified Gate

```bash
git show HEAD~1:.claude/hooks/unified-stop-gate.sh > \
    .claude/hooks/unified-stop-gate.sh
```

## Performance Comparison

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Average time | 180000ms | 61ms | 2950x faster |
| Plugin transcript read | Yes (3min) | No | Eliminated |
| Momentum blocking | Yes (2 attempts) | No | User choice |
| Priority ordering | No | Yes | Better UX |

## Files Changed

| File | Change |
|------|--------|
| `.claude/hooks/unified-stop-gate.sh` | Rewrote with 5-step architecture |
| `.claude/hooks/test-stop-gate.sh` | New comprehensive test suite |
| `.claude/.gitignore` | Added completion-state directories |
| `.claude/completion-state/` | Created directory structure |
| `~/.claude/plugins/cache/claude-orchestration` | Renamed to .disabled |

## Success Criteria

All criteria met:
- [x] Only ONE stop hook runs (unified-stop-gate.sh)
- [x] No 3-minute delays (61ms vs 180000ms)
- [x] Completion promises block when owned by session
- [x] Completion promises inform when owned by others
- [x] Work available shown but NEVER blocks
- [x] Work shown in priority order (P0, P1, P2...)
- [x] No contradictory output
- [x] Beads sync enforced before stop
- [x] Todo continuation enforced before stop
- [x] Business outcome blocking removed (redundant with promises)

---

**Implementation Date**: 2026-01-31
**Testing**: All 4 tests passing
**Performance**: 2950x improvement (3min → 61ms)
