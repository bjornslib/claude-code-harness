---
title: "ccsystem3 → cccb Migration"
description: "Update harness hooks and docs to support cccb- session ID prefix alongside system3-"
version: "1.0.0"
last-updated: 2026-03-25
status: active
type: sd
grade: authoritative
---

# SD-CCCB-MIGRATION-001: ccsystem3 → cccb Migration

## Overview

The user is renaming the `ccsystem3` shell alias to `cccb` (ClaudeCodeCoBuild). This SD covers the harness-side changes needed to support the new prefix.

## Background

The harness hooks detect CoBuilder sessions by checking if `CLAUDE_SESSION_ID` starts with `system3-`. The new `cccb` alias will set session IDs with a `cccb-` prefix instead. Until hooks are updated, stop-gate and GChat forwarding will not fire for `cccb` sessions.

## Scope

### Epic E1: Update Hook Session ID Detection

**Files to update:**
- `.claude/hooks/unified_stop_gate/config.py` — `is_system3()` property: add `cccb-` to detection logic
- `.claude/hooks/unified-stop-gate.sh` — all `[[ "$SESSION_ID" == system3-* ]]` patterns
- `.claude/hooks/gchat-ask-user-forward.py` — `is_system3_session()` function
- `.claude/hooks/hindsight-memory-flush.py` — `_is_system3_session()` function
- `.claude/hooks/unified_stop_gate/communicator_checker.py` — session ID prefix check
- `.claude/hooks/unified_stop_gate/work_exhaustion_checker.py` — `is_system3` references (these use `config.is_system3` so fixing config.py may be sufficient)

**Approach:** Accept both `system3-` and `cccb-` prefixes so existing sessions continue to work.

```python
# config.py — before
session_ok = bool(self.session_id and self.session_id.startswith("system3-"))

# config.py — after
session_ok = bool(self.session_id and (
    self.session_id.startswith("system3-") or
    self.session_id.startswith("cccb-")
))
```

```bash
# unified-stop-gate.sh — before
if [[ "$SESSION_ID" == system3-* ]]; then

# unified-stop-gate.sh — after
if [[ "$SESSION_ID" == system3-* ]] || [[ "$SESSION_ID" == cccb-* ]]; then
```

### Epic E2: Update Doc References

**Files to update (non-historical):**
- `launch_cobuilder.sh` — update comments referencing `ccsystem3`
- `.claude/skills/cobuilder-guardian/SKILL.md` — dependencies line
- `.claude/skills/cobuilder-guardian/references/guardian-workflow.md` — `which ccsystem3` check
- `.claude/skills/cobuilder-guardian/references/hindsight-validation-checklist.md` — set by ccsystem3 comment
- `.claude/documentation/SOLUTION-DESIGN-GCHAT-HOOKS-001.md` — ccsystem3 function references
- Other `.claude/documentation/` files with non-historical ccsystem3 references

**Preserve as-is (historical records):**
- `.taskmaster/` — all files
- `.claude/documentation/SYSTEM3_CHANGELOG.md`
- `documentation/SYSTEM3_CHANGELOG.md`

## Acceptance Criteria

1. `config.py is_system3()` returns True for both `system3-*` and `cccb-*` session IDs
2. `unified-stop-gate.sh` fires stop-gate logic for `cccb-*` sessions
3. `gchat-ask-user-forward.py` and `hindsight-memory-flush.py` detect `cccb-` sessions
4. `launch_cobuilder.sh` references updated
5. Non-historical docs in `.claude/` updated

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| E1: Hook session ID detection | Remaining | - | - |
| E2: Doc references | Remaining | - | - |
