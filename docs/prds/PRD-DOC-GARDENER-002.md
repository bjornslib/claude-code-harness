---
prd_id: PRD-DOC-GARDENER-002
title: "Doc-Gardener V2: Unified Documentation Standards Enforcement"
status: active
created: 2026-03-15
last_verified: 2026-03-15
grade: authoritative
---

# PRD-DOC-GARDENER-002: Doc-Gardener V2 — Unified Documentation Standards Enforcement

## 1. Executive Summary

The existing doc-gardener linter enforces frontmatter and naming conventions within `.claude/` only. The `docs/` directory — containing 136 markdown files (PRDs, SDs, research, specs, guides) — has **173 lint violations** and no enforced standard for document headers, implementation status tracking, or placement rules.

This PRD extends the doc-gardener to enforce consistent documentation standards across the entire repository, with three new check categories and enhanced frontmatter requirements.

## 2. Goals

| ID | Goal | Success Metric |
|----|------|---------------|
| G1 | Every docs/ file has a consistent header | 100% of docs/ .md files have title, description, version, last-updated frontmatter |
| G2 | PRDs/SDs track implementation status | 100% of PRD/SD/Epic/Spec documents have an "Implementation Status" section |
| G3 | Documentation lives in docs/ | Zero .md files outside docs/ contain PRD/SD/Epic/Specification content |
| G4 | Gardener runs against docs/ by default | `docs-gardener.config.json` configures docs/ as primary target |
| G5 | Existing docs are remediated | Violations reduced from 173 to 0 via auto-fix + manual pass |

## 3. User Stories

### US-1: Agent Reading Documentation
As an AI agent navigating the docs/ directory, I need every file to have a consistent header with title, description, version, and last-updated date so I can quickly assess relevance, recency, and purpose without reading the full document.

### US-2: Guardian Checking Implementation Status
As a System 3 guardian validating an initiative, I need PRDs and SDs to contain an "Implementation Status" section so I can determine which epics are done, in-progress, or remaining without cross-referencing beads.

### US-3: Developer Finding Documentation
As a developer, I need all PRD/SD/specification files to live in docs/ so I can find them in one place instead of scattered across .claude/documentation/, .claude/evidence/, and the repo root.

## 4. Requirements

### 4.1 Extended Frontmatter Schema (E1)

**New required fields for docs/ files:**

```yaml
---
title: "Human-Readable Title"           # REQUIRED (existing)
description: "One-line purpose summary"  # NEW REQUIRED
version: "1.0.0"                        # NEW REQUIRED (semver)
last-updated: 2026-03-15               # NEW REQUIRED (YYYY-MM-DD)
status: active                          # REQUIRED (existing)
type: prd | sd | epic | specification | research | guide | reference | architecture  # Expanded
grade: authoritative | reference | archive | draft  # Existing
prd_id: PRD-XXX-NNN                    # CONDITIONAL: required for PRDs
---
```

**Validation rules:**
- `description` must be non-empty, max 200 characters
- `version` must match semver pattern `N.N.N` (major.minor.patch)
- `last-updated` must be valid YYYY-MM-DD date
- `type` must be from the expanded set (existing types remain valid for .claude/)
- Auto-fix: generate `description` from first paragraph, `version` as "1.0.0", `last-updated` from git log

### 4.2 Implementation Status Body Check (E2)

**Applies to:** Files where `type` is `prd`, `sd`, `epic`, or `specification`, OR filename matches `PRD-*`, `SD-*`.

**Required section:** An `## Implementation Status` heading (H2) with a status table:

```markdown
## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| E1: Foundation | Done | 2026-03-15 | abc1234 |
| E2: Validation | In Progress | - | - |
```

**Valid statuses:** Done, In Progress, Deferred, Remaining, Cancelled, Blocked

**Validation rules:**
- Check for `## Implementation Status` heading (case-insensitive)
- Severity: `warning` (not error) — allows time for adoption
- Auto-fix: append a template Implementation Status section with "Remaining" status
- Files with `status: draft` in frontmatter are exempt

### 4.3 Misplaced Document Detection (E3)

**Rule:** Any `.md` file outside the `docs/` directory whose content or filename contains PRD, SD, Epic, or Specification keywords should be flagged.

**Detection logic:**
1. Filename pattern: `PRD-*.md`, `SD-*.md`, `*-EPIC-*.md`, `*-SPECIFICATION-*.md`
2. Content pattern: H1/H2 heading containing "PRD", "SD" (as document identifier, not abbreviation in prose), "Epic", "Specification"
3. Frontmatter pattern: `type: prd|sd|epic|specification` or `prd_id:` or `prd_ref:`

**Exclusions:**
- `.claude/skills/*/references/` — skill reference material (allowed)
- `.claude/output-styles/` — output style definitions (allowed)
- `.claude/commands/` — command definitions (allowed)
- `.claude/evidence/` — validation evidence (allowed)
- `.claude/narrative/` — living narratives (allowed)
- `acceptance-tests/` — test artifacts (allowed)
- `node_modules/`, `.git/`, `.pipelines/` — infrastructure (ignored)

**Severity:** `warning` with message suggesting move to docs/

### 4.4 Config File and Quality Grades (E4)

**Create `docs-gardener.config.json`:**

```json
{
  "targets": ["docs/"],
  "skip_dirs": ["evidence", "templates"],
  "frontmatter_required_dirs": ["prds", "sds", "research", "references", "guides", "tests", "specs", "solution-designs", "design-references"],
  "directory_grades": {
    "prds": "authoritative",
    "sds": "authoritative",
    "research": "reference",
    "references": "reference",
    "guides": "reference",
    "tests": "reference",
    "specs": "reference",
    "solution-designs": "authoritative",
    "design-references": "reference"
  },
  "docs_types": ["prd", "sd", "epic", "specification", "research", "guide", "reference", "architecture"],
  "require_implementation_status": ["prd", "sd", "epic", "specification"],
  "misplaced_document_scan": true,
  "misplaced_document_exclusions": [
    ".claude/skills/*/references/",
    ".claude/output-styles/",
    ".claude/commands/",
    ".claude/evidence/",
    ".claude/narrative/",
    "acceptance-tests/",
    "node_modules/",
    ".git/",
    ".pipelines/"
  ]
}
```

**Update quality-grades.json:** Add docs/ directory grades.

### 4.5 Auto-Remediation (E5)

Run the enhanced gardener with `--fix` against all 136 existing docs files:
1. Add missing frontmatter with inferred values
2. Add missing Implementation Status sections to PRDs/SDs
3. Generate gardening report with before/after stats
4. Commit all changes

**Inference rules for auto-fix:**
- `title`: From filename (PRD-FOO-001.md → "PRD FOO 001") or first H1 heading
- `description`: First non-heading paragraph, truncated to 200 chars
- `version`: Default "1.0.0"
- `last-updated`: From `git log -1 --format=%ai <file>` (last commit date)
- `type`: Inferred from filename prefix (PRD- → prd, SD- → sd) or directory (research/ → research)

## 5. Non-Goals

- Moving existing files from .claude/ to docs/ (separate initiative)
- Enforcing content quality beyond structural checks
- Breaking existing .claude/ linting behavior

## 6. Technical Constraints

- Must maintain backward compatibility with existing .claude/ frontmatter schema
- `docs/` schema extends (not replaces) the .claude/ schema
- All changes to lint.py must pass existing test suite
- Config file approach allows different rules per target directory

## 7. Acceptance Criteria

| AC | Criterion | Verification |
|----|-----------|-------------|
| AC-1 | `lint.py --target docs/ --config docs-gardener.config.json` reports 0 violations after remediation | Run linter, verify exit code 0 |
| AC-2 | All PRD/SD files have `## Implementation Status` section | Grep for heading in all PRD/SD files |
| AC-3 | Running `lint.py --target . --config docs-gardener.config.json` flags any .md file with PRD/SD content outside docs/ | Create test file, verify detection |
| AC-4 | Existing .claude/ linting behavior unchanged | Run `lint.py` (no args) against .claude/, compare with baseline |
| AC-5 | All 136 docs files have title, description, version, last-updated frontmatter | Parse all files, verify fields present |

## 8. Epics

| Epic | Title | Scope |
|------|-------|-------|
| E1 | Extended Frontmatter Schema | Add description, version, last-updated to required fields; expand valid types for docs/ |
| E2 | Implementation Status Body Check | New check category for PRD/SD/Epic/Spec documents |
| E3 | Misplaced Document Detection | New check category scanning outside docs/ for PRD/SD content |
| E4 | Config & Quality Grades Integration | Create docs-gardener.config.json, update quality-grades.json |
| E5 | Auto-Remediation Run | Apply fixes to all 136 existing docs files |

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| E1: Extended Frontmatter Schema | Remaining | - | - |
| E2: Implementation Status Body Check | Remaining | - | - |
| E3: Misplaced Document Detection | Remaining | - | - |
| E4: Config & Quality Grades | Remaining | - | - |
| E5: Auto-Remediation Run | Remaining | - | - |
