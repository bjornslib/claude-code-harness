---
title: "SD-DOC-GARDENER-002-TYPEBUG: Fix docs_types Not Used in Validation"
description: "Fix lint.py to use docs_types from config when validating docs/ files, and fix date format validation to strip ISO timestamps"
version: "1.0.0"
last-updated: 2026-03-25
status: active
type: sd
grade: authoritative
prd_ref: PRD-DOC-GARDENER-002
---

# SD-DOC-GARDENER-002-TYPEBUG: Fix docs_types Not Used in Validation

## Problem

`lint.py` rejects `prd` and `sd` as valid frontmatter `type` values when scanning `docs/` files. The config file (`docs-gardener.config.json`) defines `docs_types` including these values, but the validation function only checks against the hardcoded `.claude/` type set.

Additionally, `last_verified` / `last-updated` dates with ISO timestamp suffixes (e.g., `2026-03-09T00:00:00.000Z`) are rejected — only `YYYY-MM-DD` is accepted.

## Root Cause

In `_validate_frontmatter_fields()`, the valid types set is not extended with `ctx.docs_types` when scanning docs/ targets.

Date validation uses strict `YYYY-MM-DD` matching but many files have ISO timestamps from automated tools.

## Fix

### 1. Type Validation (lint.py)

In the frontmatter validation function, when checking the `type` field:

```python
# Current (broken):
valid_types = VALID_TYPES  # Only .claude/ types

# Fixed:
valid_types = VALID_TYPES
if ctx.docs_types:
    valid_types = valid_types | ctx.docs_types
```

### 2. Date Validation (lint.py)

Accept ISO timestamps and extract just the date portion:

```python
# For last_verified / last-updated fields:
date_str = str(value)
# Strip ISO timestamp suffix: 2026-03-09T00:00:00.000Z -> 2026-03-09
if "T" in date_str:
    date_str = date_str.split("T")[0]
# Then validate YYYY-MM-DD pattern
```

### 3. Auto-fix for Date Format

In `gardener.py`, when auto-fixing frontmatter, normalize ISO timestamps to YYYY-MM-DD.

## Files Changed

| File | Change |
|------|--------|
| `.claude/scripts/doc-gardener/lint.py` | Extend valid types with docs_types from context; accept ISO date timestamps |
| `.claude/scripts/doc-gardener/gardener.py` | Normalize ISO dates during auto-fix |

## Testing

- Run `lint.py --target docs/` — `prd`/`sd` types should no longer error
- Run `lint.py --target .claude/` — `prd`/`sd` should still be invalid (backward compat)
- Verify date format `2026-03-09T00:00:00.000Z` no longer errors

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| Type validation fix | Remaining | - | - |
| Date format fix | Remaining | - | - |
