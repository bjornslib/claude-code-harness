---
title: "SD-DOC-GARDENER-002: Doc-Gardener V2 Implementation"
description: "Solution design for extending doc-gardener with unified docs/ standards, implementation status checks, and misplaced document detection"
version: "1.0.0"
last-updated: 2026-03-15
status: active
type: architecture
grade: authoritative
prd_ref: PRD-DOC-GARDENER-002
---

# SD-DOC-GARDENER-002: Doc-Gardener V2 Implementation

## 1. Architecture Overview

The doc-gardener V2 extends the existing `lint.py` (1203 lines) and `gardener.py` (440 lines) with three new check categories while maintaining full backward compatibility with `.claude/` scanning.

### Key Design Decisions

1. **Config-driven schema extension**: New fields (description, version, last-updated) are enforced via config, not hardcoded — .claude/ retains its existing schema
2. **Body-level checks as a new category**: Implementation Status is the first "body check" pattern, designed to be extensible for future body-level validations
3. **Misplaced detection uses file-walk, not grep**: We walk the repo tree once and apply exclusion patterns, rather than shelling out to grep

### File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/scripts/doc-gardener/lint.py` | MODIFY | Add 3 new check functions, extend config handling, expand VALID_TYPES |
| `.claude/scripts/doc-gardener/gardener.py` | MODIFY | Wire new checks, update report template |
| `.claude/scripts/doc-gardener/quality-grades.json` | MODIFY | Add docs/ directory grades |
| `docs-gardener.config.json` | CREATE | Config file for docs/ scanning |
| `.claude/scripts/doc-gardener/test_lint.py` | MODIFY | Add tests for new checks |

## 2. Epic E1: Extended Frontmatter Schema

### 2.1 New Fields

Add to `_validate_frontmatter_fields()`:

```python
# Config-driven required fields
DOCS_REQUIRED_FIELDS = ["title", "description", "version", "last-updated"]
CLAUDE_REQUIRED_FIELDS = ["title", "status"]  # existing

def _get_required_fields(ctx: LintContext) -> list[str]:
    """Return required frontmatter fields based on target context."""
    if ctx.is_claude_dir:
        return CLAUDE_REQUIRED_FIELDS
    # Use config if available
    if hasattr(ctx, 'required_fields') and ctx.required_fields:
        return ctx.required_fields
    return DOCS_REQUIRED_FIELDS
```

### 2.2 Validation Rules

```python
# Description: non-empty, max 200 chars
if "description" in fm:
    desc = fm["description"]
    if not desc or len(desc) > 200:
        violations.append(...)

# Version: semver N.N.N
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
if "version" in fm and not VERSION_PATTERN.match(fm["version"]):
    violations.append(...)

# last-updated: YYYY-MM-DD date
# Note: supports both "last-updated" and "last_verified" for backward compat
```

### 2.3 Expanded Types

```python
VALID_DOCS_TYPES = VALID_TYPES | {
    "prd",            # Product Requirement Documents
    "sd",             # Solution Design documents
    "epic",           # Epic specifications
    "specification",  # Technical specifications
    "research",       # Research documents and spikes
    "guide",          # How-to guides
}
```

### 2.4 Auto-fix for New Fields

In `generate_frontmatter()`, add inference logic:

```python
def _infer_description(filepath: Path, content: str) -> str:
    """Extract first non-heading paragraph as description."""
    _, body = parse_frontmatter(content)
    for line in body.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return line[:200]
    return f"Documentation for {filepath.stem}"

def _infer_version() -> str:
    return "1.0.0"

def _infer_last_updated(filepath: Path) -> str:
    """Get last git commit date for file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ai", str(filepath)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:10]  # YYYY-MM-DD
    except Exception:
        pass
    return date.today().isoformat()

def _infer_type(filepath: Path) -> str:
    """Infer document type from filename prefix or directory."""
    name = filepath.stem.upper()
    if name.startswith("PRD"):
        return "prd"
    if name.startswith("SD"):
        return "sd"
    dirname = filepath.parent.name
    type_map = {
        "prds": "prd",
        "sds": "sd",
        "research": "research",
        "guides": "guide",
        "specs": "specification",
        "references": "reference",
        "solution-designs": "sd",
    }
    return type_map.get(dirname, "reference")
```

## 3. Epic E2: Implementation Status Body Check

### 3.1 New Check Function

```python
def check_implementation_status(
    filepath: Path, content: str, ctx: LintContext
) -> list[Violation]:
    """Check that PRD/SD/Epic/Spec documents have an Implementation Status section."""
    if not _requires_implementation_status(filepath, content, ctx):
        return []

    # Check for the heading (case-insensitive)
    if not re.search(r"^##\s+Implementation\s+Status", content, re.MULTILINE | re.IGNORECASE):
        return [Violation(
            file=get_relative_path(filepath, ctx.target_dir),
            category="implementation-status",
            severity=SEVERITY_WARNING,
            message="Missing '## Implementation Status' section (required for PRD/SD/Epic/Spec documents)",
            fixable=True,
            target_dir=ctx.target_dir,
        )]
    return []
```

### 3.2 Detection Logic

```python
def _requires_implementation_status(
    filepath: Path, content: str, ctx: LintContext
) -> bool:
    """Determine if a file needs an Implementation Status section."""
    # Check frontmatter type
    fm, _ = parse_frontmatter(content)
    if fm:
        if fm.get("status") == "draft":
            return False  # Drafts exempt
        doc_type = fm.get("type", "")
        if doc_type in ("prd", "sd", "epic", "specification"):
            return True

    # Check filename pattern
    name = filepath.stem.upper()
    if name.startswith(("PRD-", "SD-")):
        return True

    # Check config
    require_types = getattr(ctx, 'require_implementation_status', [])
    if require_types and fm:
        return fm.get("type", "") in require_types

    return False
```

### 3.3 Auto-fix: Append Template

```python
IMPL_STATUS_TEMPLATE = """

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| - | Remaining | - | - |
"""
```

## 4. Epic E3: Misplaced Document Detection

### 4.1 New Check Function

```python
def check_misplaced_documents(
    repo_root: Path, docs_dir: Path, ctx: LintContext
) -> list[Violation]:
    """Scan for .md files outside docs/ that contain PRD/SD/Epic/Spec content."""
    violations = []
    exclusion_patterns = getattr(ctx, 'misplaced_exclusions', [])

    for md_file in repo_root.rglob("*.md"):
        # Skip files inside docs/
        if _is_under(md_file, docs_dir):
            continue
        # Skip exclusions
        if _matches_exclusion(md_file, repo_root, exclusion_patterns):
            continue
        # Skip hidden dirs
        rel = md_file.relative_to(repo_root)
        if any(part.startswith(".") and part != ".claude" for part in rel.parts):
            continue

        if _is_misplaced_document(md_file):
            violations.append(Violation(
                file=str(rel),
                category="misplaced-document",
                severity=SEVERITY_WARNING,
                message=f"Document appears to be a PRD/SD/Epic/Spec but is outside docs/. Consider moving to docs/",
                fixable=False,
                target_dir=ctx.target_dir,
            ))
    return violations
```

### 4.2 Detection Heuristics

```python
def _is_misplaced_document(filepath: Path) -> bool:
    """Check if a file looks like it should be in docs/."""
    name = filepath.stem.upper()

    # Filename check
    if re.match(r"^(PRD|SD)-", name):
        return True

    # Content check (read first 2KB only for performance)
    try:
        content = filepath.read_text(encoding="utf-8")[:2048]
    except Exception:
        return False

    # Frontmatter check
    fm, _ = parse_frontmatter(content)
    if fm:
        if fm.get("type") in ("prd", "sd", "epic", "specification"):
            return True
        if "prd_id" in fm or "prd_ref" in fm:
            return True

    # Heading check: H1/H2 with document identifier
    if re.search(r"^#{1,2}\s+(?:PRD|SD)-\w+", content, re.MULTILINE):
        return True

    return False
```

## 5. Epic E4: Config & Quality Grades

### 5.1 LintContext Extension

```python
class LintContext:
    def __init__(self, ...,
        required_fields: list[str] | None = None,
        require_implementation_status: list[str] | None = None,
        misplaced_exclusions: list[str] | None = None,
        misplaced_scan: bool = False,
        docs_types: set[str] | None = None,
    ):
        ...
        self.required_fields = required_fields
        self.require_implementation_status = require_implementation_status or []
        self.misplaced_exclusions = misplaced_exclusions or []
        self.misplaced_scan = misplaced_scan
        self.docs_types = docs_types
```

### 5.2 Config Loading

Extend `load_config()` to parse new fields:
- `docs_types` → expanded valid types
- `require_implementation_status` → list of types needing the section
- `misplaced_document_scan` → enable/disable
- `misplaced_document_exclusions` → paths to skip

## 6. Epic E5: Auto-Remediation

### 6.1 Remediation Sequence

```bash
# Step 1: Baseline scan
python3 .claude/scripts/doc-gardener/lint.py --target docs/ --config docs-gardener.config.json --json > /tmp/before.json

# Step 2: Auto-fix
python3 .claude/scripts/doc-gardener/gardener.py --target docs/ --config docs-gardener.config.json --execute

# Step 3: Verify
python3 .claude/scripts/doc-gardener/lint.py --target docs/ --config docs-gardener.config.json --json > /tmp/after.json

# Step 4: Diff
python3 -c "import json; b=json.load(open('/tmp/before.json')); a=json.load(open('/tmp/after.json')); print(f'Before: {b[\"total_violations\"]} → After: {a[\"total_violations\"]}')"
```

### 6.2 Expected Fix Coverage

| Category | Before (est.) | Auto-fixable | After (est.) |
|----------|--------------|-------------|-------------|
| Missing frontmatter | ~40 | Yes (generate) | 0 |
| Missing description | ~90 | Yes (infer from content) | 0 |
| Missing version | ~130 | Yes (default 1.0.0) | 0 |
| Missing last-updated | ~60 | Yes (from git log) | 0 |
| Missing Implementation Status | ~50 | Yes (append template) | 0 |
| Misplaced documents | ~30 | No (manual move) | ~30 |
| Naming violations | ~10 | No | ~10 |
| Broken crosslinks | ~5 | No | ~5 |

## 7. Testing Strategy

### 7.1 Unit Tests (test_lint.py)

- `test_extended_frontmatter_docs_target` — verify description/version/last-updated required for docs/
- `test_extended_frontmatter_claude_unchanged` — verify .claude/ still only needs title/status
- `test_implementation_status_present` — verify PRD with section passes
- `test_implementation_status_missing` — verify PRD without section fails
- `test_implementation_status_draft_exempt` — verify drafts are exempt
- `test_misplaced_document_detected` — verify PRD outside docs/ is flagged
- `test_misplaced_document_exclusion` — verify .claude/skills/ PRDs are NOT flagged
- `test_config_loading` — verify docs-gardener.config.json parses correctly
- `test_autofix_frontmatter` — verify auto-generated frontmatter includes new fields
- `test_autofix_implementation_status` — verify template is appended

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| E1: Extended Frontmatter Schema | Done | 2026-03-15 | Pipeline impl_e1_e4 |
| E2: Implementation Status Body Check | Done | 2026-03-15 | Pipeline impl_e1_e4 |
| E3: Misplaced Document Detection | Done | 2026-03-15 | Pipeline impl_e1_e4 |
| E4: Config & Quality Grades | Done | 2026-03-15 | Pipeline impl_e1_e4 |
| E5: Auto-Remediation Run | Done | 2026-03-15 | Pipeline impl_e5 |
