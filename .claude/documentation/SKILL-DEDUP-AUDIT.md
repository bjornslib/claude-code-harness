---
title: "Skill Dedup Audit"
status: active
type: architecture
last_verified: 2026-02-19
grade: reference
---

# Skill Deduplication Audit Report

**Date**: 2026-02-17
**Feature**: F5.2 - Deduplicate `.claude/skills/` directory
**Branch**: `epic5-context-optimization`

## Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total .md lines | 58,404 | 44,285 | -14,119 (-24.2%) |
| Total .md files | 278 | 183 | -95 files |

Target of 20%+ line reduction: **ACHIEVED** (24.2%).

## Actions Taken

### 1. Deleted Recursive Copy (-4,207 lines, -47 files)

**What**: An exact recursive duplicate existed at `.claude/skills/.claude/skills/react-best-practices/` -- a full copy of the `react-best-practices` skill nested inside a spurious `.claude/skills/` subdirectory.

**Verification**: `diff -r` confirmed the two directories were byte-identical.

**Action**: Removed `.claude/skills/.claude/` entirely.

**Lines saved**: 4,207

### 2. Consolidated Railway Reference Files (-9,912 lines, -48 files)

**What**: Four reference files were duplicated identically across all 13 `railway-*` skill directories:

| File | Lines per copy | Copies | Total duplicated lines |
|------|---------------|--------|----------------------|
| `environment-config.md` | 183 | 13 | 2,379 |
| `monorepo.md` | 216 | 13 | 2,808 |
| `railpack.md` | 257 | 13 | 3,341 |
| `variables.md` | 170 | 13 | 2,210 |
| **Total** | **826** | **13** | **10,738** |

All 13 copies were verified identical via MD5 checksums (1 unique hash per file).

**Action**:
1. Created `.claude/skills/railway-common/references/` as the single canonical location
2. Copied the 4 files from `railway-central-station/references/` to `railway-common/references/`
3. Deleted all 52 duplicate files (4 files x 13 directories)
4. Removed all 13 now-empty `references/` subdirectories
5. Updated 10 cross-references in 5 SKILL.md files to use `../railway-common/references/` paths

**Lines saved**: 826 x 12 = 9,912 (keeping 1 copy of 826 lines)

### Railway Reference Cross-Reference Map

These SKILL.md files reference the consolidated files:

| SKILL.md | References |
|----------|------------|
| `railway-new/SKILL.md` | `railpack.md` (x2), `monorepo.md` (x2) |
| `railway-service/SKILL.md` | `variables.md` (x1) |
| `railway-environment/SKILL.md` | `environment-config.md` (x1), `variables.md` (x1) |
| `railway-database/SKILL.md` | `environment-config.md` (x1), `variables.md` (x1) |
| `railway-templates/SKILL.md` | `variables.md` (x1) |

All other railway skills (railway-central-station, railway-deploy, railway-deployment, railway-domain, railway-metrics, railway-projects, railway-railway-docs, railway-status) had the reference files but did not link to them from their SKILL.md.

## Verification

- Zero broken references: `grep` for old `references/` paths returns no matches
- All 10 updated references point to `../railway-common/references/` and resolve correctly
- The `railway-railway-docs/SKILL.md` reference to `variables.md` is a Railway docs URL (not a local file) and was not modified

## Remaining Known Duplication (Accepted)

No further exact-duplicate files were identified. The remaining 44,285 lines represent unique skill content across 183 .md files.

Potential future optimization areas (not in scope for F5.2):
- Some railway SKILL.md files share structural patterns but have distinct content
- MCP skill wrappers in `mcp-skills/` have similar boilerplate headers but differ in API details
