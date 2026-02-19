#!/usr/bin/env python3
"""
Documentation linter for .claude/ harness directory.

Checks (5 categories):
  1. Frontmatter validation (SKILL.md, CLAUDE.md, agent .md files)
  2. Cross-link integrity (verify internal links resolve)
  3. Staleness detection (files not updated in configurable period)
  4. Naming conventions (kebab-case for dirs, UPPER for top-level docs)
  5. Quality-grades sync (grade assignments match directory defaults)

Usage:
  python .claude/scripts/doc-gardener/lint.py                  # Full scan, text output
  python .claude/scripts/doc-gardener/lint.py --dry-run        # Same as default (no changes)
  python .claude/scripts/doc-gardener/lint.py --verbose        # Show all files scanned
  python .claude/scripts/doc-gardener/lint.py --json           # Machine-readable output
  python .claude/scripts/doc-gardener/lint.py --fix            # Auto-fix what's possible

Exit codes:
  0 = no violations
  1 = violations found
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
# .claude/ is two levels up from scripts/doc-gardener/
CLAUDE_DIR = SCRIPT_DIR.parent.parent
QUALITY_GRADES_FILE = SCRIPT_DIR / "quality-grades.json"

VALID_GRADES = {"authoritative", "reference", "archive", "draft"}
VALID_STATUSES = {"active", "draft", "archived", "deprecated"}

# Harness-specific document types
VALID_TYPES = {
    "skill",          # SKILL.md files
    "agent",          # Agent definition files
    "output-style",   # Output style definitions
    "hook",           # Hook documentation
    "command",        # Slash command docs
    "guide",          # Guides and how-tos
    "architecture",   # Architecture decisions
    "reference",      # Reference material
    "config",         # Configuration docs
}

# Directories to skip entirely (runtime state, not documentation)
SKIP_DIRS = {
    "state",
    "message-bus",
    "completion-state",
    "evidence",
    "progress",
    "worker-assignments",
    "user-input-queue",
}

# Top-level files that should use UPPER_CASE naming
UPPER_CASE_FILES = {"CLAUDE.md", "README.md", "INDEX.md", "CHANGELOG.md"}

# Files within skills/ that must exist
SKILL_REQUIRED_FILES = {"SKILL.md"}

# Staleness thresholds (days)
STALENESS_ARCHIVE = 90   # >90 days -> grade should be archive
STALENESS_REFERENCE = 60  # >60 days -> grade should be reference or lower

# Naming: kebab-case for directories
KEBAB_DIR_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Naming: kebab-case for files (with optional date prefix)
KEBAB_FILE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}-)?"   # optional date prefix
    r"[a-z0-9]+(-[a-z0-9]+)*"   # kebab-case body
    r"\.[a-z]+$"                  # extension
)

# UPPER_CASE pattern for top-level docs (e.g. CLAUDE.md, SKILL.md)
UPPER_FILE_PATTERN = re.compile(
    r"^[A-Z][A-Z0-9_]*"   # UPPER start
    r"\.[a-z]+$"           # extension
)

# Severity levels
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Violation:
    """A single lint violation."""

    __slots__ = ("file", "category", "severity", "message", "fixable")

    def __init__(
        self,
        file: str,
        category: str,
        severity: str,
        message: str,
        fixable: bool = False,
    ):
        self.file = file
        self.category = category
        self.severity = severity
        self.message = message
        self.fixable = fixable

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "fixable": self.fixable,
        }

    def __str__(self) -> str:
        icon = {"error": "E", "warning": "W", "info": "I"}.get(self.severity, "?")
        fix = " [fixable]" if self.fixable else ""
        return f"[{icon}] {self.file}: {self.message}{fix}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_quality_grades() -> dict[str, Any]:
    """Load quality-grades.json if it exists."""
    if not QUALITY_GRADES_FILE.exists():
        return {}
    with open(QUALITY_GRADES_FILE) as f:
        return json.load(f)


def parse_frontmatter(content: str) -> tuple[dict[str, str] | None, str]:
    """
    Parse YAML frontmatter from markdown content.
    Returns (frontmatter_dict, body) or (None, full_content).
    Handles simple key: value pairs only (stdlib, no yaml library).
    """
    if not content.startswith("---"):
        return None, content

    lines = content.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, content

    fm: dict[str, str] = {}
    for line in lines[1:end_idx]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")

    body = "\n".join(lines[end_idx + 1:])
    return fm, body


def get_relative_path(filepath: Path) -> str:
    """Get path relative to CLAUDE_DIR."""
    try:
        return str(filepath.relative_to(CLAUDE_DIR))
    except ValueError:
        return str(filepath)


def get_directory_name(filepath: Path) -> str | None:
    """Get the immediate subdirectory name under .claude/."""
    try:
        rel = filepath.relative_to(CLAUDE_DIR)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) > 1:
        return parts[0]
    return None


def is_in_skip_dir(filepath: Path) -> bool:
    """Check if a file is in a directory that should be skipped."""
    dirname = get_directory_name(filepath)
    return dirname in SKIP_DIRS


def is_skill_file(filepath: Path) -> bool:
    """Check if file is a SKILL.md inside skills/."""
    try:
        rel = filepath.relative_to(CLAUDE_DIR)
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 2 and parts[0] == "skills" and filepath.name == "SKILL.md"


def is_agent_file(filepath: Path) -> bool:
    """Check if file is an agent definition in agents/."""
    try:
        rel = filepath.relative_to(CLAUDE_DIR)
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 2 and parts[0] == "agents" and filepath.suffix == ".md"


def is_top_level_file(filepath: Path) -> bool:
    """Check if file is a top-level file directly in .claude/."""
    try:
        rel = filepath.relative_to(CLAUDE_DIR)
    except ValueError:
        return False
    return len(rel.parts) == 1


def collect_md_files() -> list[Path]:
    """Collect markdown files to lint within .claude/ directory."""
    files = []
    for p in CLAUDE_DIR.rglob("*.md"):
        # Skip files in skip directories
        if is_in_skip_dir(p):
            continue
        # Skip hidden directories (e.g. .claude/.claude nested)
        rel = p.relative_to(CLAUDE_DIR)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(p)
    return sorted(files)


def should_require_frontmatter(filepath: Path) -> bool:
    """Determine if a file should have frontmatter.

    Files that require frontmatter:
    - SKILL.md files in skills/
    - Agent definitions in agents/
    - Documentation in documentation/
    - Output styles in output-styles/
    - Commands in commands/

    Files that do NOT require frontmatter:
    - CLAUDE.md (top-level config, not a document)
    - Reference files nested deep in skills (e.g. skills/foo/references/bar.md)
    - Hook scripts documentation
    """
    dirname = get_directory_name(filepath)

    # Top-level CLAUDE.md and similar config files don't need frontmatter
    if is_top_level_file(filepath):
        return False

    # These directories have documentation that should have frontmatter
    frontmatter_dirs = {"skills", "agents", "documentation", "output-styles", "commands"}
    if dirname in frontmatter_dirs:
        return True

    return False


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def check_frontmatter(filepath: Path, content: str) -> list[Violation]:
    """Check frontmatter presence and validity for applicable files."""
    violations = []
    rel = get_relative_path(filepath)

    if not should_require_frontmatter(filepath):
        # Even if not required, validate frontmatter if present
        fm, _ = parse_frontmatter(content)
        if fm is not None:
            violations.extend(_validate_frontmatter_fields(filepath, fm, rel))
        return violations

    fm, _ = parse_frontmatter(content)

    if fm is None:
        violations.append(Violation(
            file=rel,
            category="frontmatter",
            severity=SEVERITY_WARNING,
            message="Missing YAML frontmatter block (---)",
            fixable=True,
        ))
        return violations

    violations.extend(_validate_frontmatter_fields(filepath, fm, rel))
    return violations


def _validate_frontmatter_fields(
    filepath: Path, fm: dict[str, str], rel: str
) -> list[Violation]:
    """Validate individual frontmatter fields."""
    violations = []

    # Required fields depend on file type
    if is_skill_file(filepath):
        required_fields = ["title", "status"]
    elif is_agent_file(filepath):
        required_fields = ["title", "status"]
    else:
        required_fields = ["title", "status"]

    for field in required_fields:
        if field not in fm:
            violations.append(Violation(
                file=rel,
                category="frontmatter",
                severity=SEVERITY_ERROR,
                message=f"Missing required frontmatter field: {field}",
                fixable=False,
            ))

    # Validate field values
    if "status" in fm and fm["status"] not in VALID_STATUSES:
        violations.append(Violation(
            file=rel,
            category="frontmatter",
            severity=SEVERITY_ERROR,
            message=(
                f"Invalid status '{fm['status']}'. "
                f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            ),
        ))

    if "type" in fm and fm["type"] not in VALID_TYPES:
        violations.append(Violation(
            file=rel,
            category="frontmatter",
            severity=SEVERITY_ERROR,
            message=(
                f"Invalid type '{fm['type']}'. "
                f"Must be one of: {', '.join(sorted(VALID_TYPES))}"
            ),
        ))

    if "grade" in fm and fm["grade"] not in VALID_GRADES:
        violations.append(Violation(
            file=rel,
            category="frontmatter",
            severity=SEVERITY_ERROR,
            message=(
                f"Invalid grade '{fm['grade']}'. "
                f"Must be one of: {', '.join(sorted(VALID_GRADES))}"
            ),
        ))

    # Check last_verified date format
    if "last_verified" in fm:
        try:
            datetime.strptime(fm["last_verified"], "%Y-%m-%d")
        except ValueError:
            violations.append(Violation(
                file=rel,
                category="frontmatter",
                severity=SEVERITY_ERROR,
                message=(
                    f"Invalid last_verified date format: '{fm['last_verified']}'. "
                    f"Expected YYYY-MM-DD"
                ),
            ))

    return violations


def check_crosslinks(filepath: Path, content: str) -> list[Violation]:
    """Check that relative markdown links resolve to real files."""
    violations = []
    rel = get_relative_path(filepath)

    # Find markdown links: [text](path) -- only relative paths
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
    for match in link_pattern.finditer(content):
        link_target = match.group(2)

        # Skip external URLs, anchors, mailto, etc.
        if link_target.startswith(("http://", "https://", "#", "mailto:")):
            continue

        # Strip anchor from target
        target_path = link_target.split("#")[0]
        if not target_path:
            continue

        # Resolve relative to the file's directory
        resolved = (filepath.parent / target_path).resolve()

        if not resolved.exists():
            violations.append(Violation(
                file=rel,
                category="crosslinks",
                severity=SEVERITY_ERROR,
                message=f"Broken link: [{match.group(1)}]({link_target})",
            ))

    return violations


def check_staleness(filepath: Path, content: str) -> list[Violation]:
    """Check document staleness based on last_verified date."""
    violations = []
    rel = get_relative_path(filepath)

    fm, _ = parse_frontmatter(content)
    if fm is None or "last_verified" not in fm:
        return violations

    try:
        last_verified = datetime.strptime(fm["last_verified"], "%Y-%m-%d").date()
    except ValueError:
        return violations  # Already caught by frontmatter checker

    today = date.today()
    age_days = (today - last_verified).days
    current_grade = fm.get("grade", "")

    if age_days > STALENESS_ARCHIVE and current_grade not in ("archive", "draft"):
        violations.append(Violation(
            file=rel,
            category="staleness",
            severity=SEVERITY_WARNING,
            message=(
                f"Document is {age_days} days old "
                f"(last_verified: {fm['last_verified']}). "
                f"Grade should be 'archive' but is '{current_grade}'"
            ),
            fixable=True,
        ))
    elif age_days > STALENESS_REFERENCE and current_grade == "authoritative":
        violations.append(Violation(
            file=rel,
            category="staleness",
            severity=SEVERITY_INFO,
            message=(
                f"Document is {age_days} days old "
                f"(last_verified: {fm['last_verified']}). "
                f"Consider downgrading from 'authoritative' to 'reference'"
            ),
            fixable=True,
        ))

    return violations


def check_naming(filepath: Path) -> list[Violation]:
    """Check naming conventions for .claude/ harness files and directories.

    Rules:
    - Directories should be kebab-case (lowercase with hyphens)
    - Top-level docs should be UPPER_CASE (e.g. CLAUDE.md, SKILL.md)
    - Other .md files should be kebab-case
    - No spaces in any file or directory names
    """
    violations = []
    rel = get_relative_path(filepath)
    name = filepath.name

    # Check for spaces in filename
    if " " in name:
        violations.append(Violation(
            file=rel,
            category="naming",
            severity=SEVERITY_ERROR,
            message=f"Filename contains spaces: '{name}'",
            fixable=False,
        ))

    # Check directory naming (kebab-case)
    try:
        rel_path = filepath.relative_to(CLAUDE_DIR)
    except ValueError:
        return violations

    for part in rel_path.parts[:-1]:  # All parent dirs, not the filename
        if not KEBAB_DIR_PATTERN.match(part):
            violations.append(Violation(
                file=rel,
                category="naming",
                severity=SEVERITY_WARNING,
                message=(
                    f"Directory '{part}' doesn't follow kebab-case convention. "
                    f"Expected: lowercase-with-hyphens"
                ),
                fixable=False,
            ))
            break  # Only report once per file path

    # Check file naming
    if name in UPPER_CASE_FILES or name == "SKILL.md":
        # Top-level docs must be UPPER_CASE
        if not UPPER_FILE_PATTERN.match(name):
            violations.append(Violation(
                file=rel,
                category="naming",
                severity=SEVERITY_WARNING,
                message=(
                    f"Expected UPPER_CASE filename for '{name}'"
                ),
                fixable=False,
            ))
    elif is_top_level_file(filepath):
        # Top-level .claude/ files should be UPPER_CASE
        if not UPPER_FILE_PATTERN.match(name) and not KEBAB_FILE_PATTERN.match(name):
            violations.append(Violation(
                file=rel,
                category="naming",
                severity=SEVERITY_INFO,
                message=(
                    f"Top-level file '{name}' should be UPPER_CASE.md "
                    f"or kebab-case.md"
                ),
                fixable=False,
            ))
    else:
        # Non-top-level files: kebab-case or UPPER_CASE are both acceptable
        if (
            not KEBAB_FILE_PATTERN.match(name)
            and not UPPER_FILE_PATTERN.match(name)
        ):
            violations.append(Violation(
                file=rel,
                category="naming",
                severity=SEVERITY_WARNING,
                message=(
                    f"Filename '{name}' doesn't follow naming conventions. "
                    f"Expected: kebab-case.md or UPPER_CASE.md"
                ),
                fixable=False,
            ))

    return violations


def check_grades_sync(
    filepath: Path, content: str, grades_data: dict
) -> list[Violation]:
    """Check that frontmatter grade matches quality-grades.json directory defaults."""
    violations = []
    rel = get_relative_path(filepath)

    if not grades_data:
        return violations

    fm, _ = parse_frontmatter(content)
    if fm is None or "grade" not in fm:
        return violations

    dirname = get_directory_name(filepath)
    if dirname is None:
        return violations

    dir_grades = grades_data.get("directoryGrades", {})
    file_overrides = grades_data.get("fileOverrides", {})

    # Check file-level overrides first
    if isinstance(file_overrides, dict):
        for key, val in file_overrides.items():
            if key in ("_comment", "examples"):
                continue
            if rel == key and fm["grade"] != val:
                violations.append(Violation(
                    file=rel,
                    category="grades-sync",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"Grade mismatch: frontmatter says '{fm['grade']}' "
                        f"but quality-grades.json override says '{val}'"
                    ),
                    fixable=True,
                ))
                return violations

    # Check directory default
    if dirname in dir_grades:
        expected = dir_grades[dirname]
        actual = fm["grade"]
        if actual != expected:
            violations.append(Violation(
                file=rel,
                category="grades-sync",
                severity=SEVERITY_INFO,
                message=(
                    f"Grade '{actual}' differs from directory default "
                    f"'{expected}' for {dirname}/. "
                    f"Consider adding a fileOverride in quality-grades.json"
                ),
            ))

    return violations


# ---------------------------------------------------------------------------
# Fix logic
# ---------------------------------------------------------------------------

def generate_frontmatter(filepath: Path, grades_data: dict) -> str:
    """Generate a frontmatter block for a file that lacks one."""
    dirname = get_directory_name(filepath)
    name = filepath.stem

    # Infer title from filename
    if name == "SKILL":
        # Use parent directory name for SKILL.md
        title = filepath.parent.name.replace("-", " ").title()
    elif name == "CLAUDE":
        title = "Claude Configuration"
    else:
        title = name.replace("-", " ").title()
        # Strip date prefix from title
        date_prefix_match = re.match(r"^\d{4}-\d{2}-\d{2}\s+", title)
        if date_prefix_match:
            title = title[date_prefix_match.end():]

    # Infer type from directory and file
    type_map = {
        "skills": "skill",
        "agents": "agent",
        "output-styles": "output-style",
        "hooks": "hook",
        "commands": "command",
        "documentation": "architecture",
    }
    doc_type = type_map.get(dirname, "reference")

    # Infer grade from quality-grades.json
    dir_grades = grades_data.get("directoryGrades", {})
    grade = dir_grades.get(dirname, "draft")

    # Infer status from grade
    status_map = {
        "authoritative": "active",
        "reference": "active",
        "archive": "archived",
        "draft": "draft",
    }
    status = status_map.get(grade, "draft")

    today_str = date.today().isoformat()

    return (
        f"---\n"
        f"title: \"{title}\"\n"
        f"status: {status}\n"
        f"type: {doc_type}\n"
        f"last_verified: {today_str}\n"
        f"grade: {grade}\n"
        f"---\n\n"
    )


def apply_fixes(violations: list[Violation], grades_data: dict) -> int:
    """Apply automatic fixes. Returns number of files fixed."""
    fixed_count = 0
    # Group fixable violations by file
    fixable_files: dict[str, list[Violation]] = {}
    for v in violations:
        if v.fixable:
            fixable_files.setdefault(v.file, []).append(v)

    for rel_path, file_violations in fixable_files.items():
        filepath = CLAUDE_DIR / rel_path
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        modified = False

        for v in file_violations:
            if (
                v.category == "frontmatter"
                and "Missing YAML frontmatter" in v.message
            ):
                fm_block = generate_frontmatter(filepath, grades_data)
                content = fm_block + content
                modified = True

            elif (
                v.category == "staleness"
                and "should be 'archive'" in v.message
            ):
                content = re.sub(
                    r"^(grade:\s*).*$",
                    r"\1archive",
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
                modified = True

            elif (
                v.category == "staleness"
                and "Consider downgrading" in v.message
            ):
                content = re.sub(
                    r"^(grade:\s*).*$",
                    r"\1reference",
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
                modified = True

            elif (
                v.category == "grades-sync"
                and "Grade mismatch" in v.message
            ):
                # Extract expected grade from the file override
                grade_match = re.search(
                    r"quality-grades\.json override says '([^']+)'",
                    v.message,
                )
                if grade_match:
                    expected_grade = grade_match.group(1)
                    content = re.sub(
                        r"^(grade:\s*).*$",
                        rf"\1{expected_grade}",
                        content,
                        count=1,
                        flags=re.MULTILINE,
                    )
                    modified = True

        if modified:
            filepath.write_text(content, encoding="utf-8")
            fixed_count += 1

    return fixed_count


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def lint(fix: bool = False, verbose: bool = False) -> tuple[list[Violation], int]:
    """Run all lint checks and return (violations, files_scanned)."""
    grades_data = load_quality_grades()
    files = collect_md_files()
    files_scanned = len(files)

    if verbose:
        print(f"Scanning {files_scanned} markdown files in {CLAUDE_DIR}")
        for f in files:
            print(f"  {get_relative_path(f)}")
        print()

    violations: list[Violation] = []

    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            violations.append(Violation(
                file=get_relative_path(filepath),
                category="io",
                severity=SEVERITY_ERROR,
                message="Could not read file",
            ))
            continue

        violations.extend(check_frontmatter(filepath, content))
        violations.extend(check_crosslinks(filepath, content))
        violations.extend(check_staleness(filepath, content))
        violations.extend(check_naming(filepath))
        violations.extend(check_grades_sync(filepath, content, grades_data))

    if fix and violations:
        fixed = apply_fixes(violations, grades_data)
        if fixed > 0:
            # Re-run lint to get updated violations
            return lint(fix=False, verbose=False)

    return violations, files_scanned


def format_text(
    violations: list[Violation], files_scanned: int
) -> str:
    """Format violations as human-readable text."""
    lines = []
    lines.append("Harness Documentation Lint Report")
    lines.append("=" * 50)
    lines.append(f"Target: {CLAUDE_DIR}")
    lines.append(f"Files scanned: {files_scanned}")
    lines.append("")

    if not violations:
        lines.append("No violations found.")
        return "\n".join(lines)

    # Group by category
    by_category: dict[str, list[Violation]] = {}
    for v in violations:
        by_category.setdefault(v.category, []).append(v)

    # Summary
    errors = sum(1 for v in violations if v.severity == SEVERITY_ERROR)
    warnings = sum(1 for v in violations if v.severity == SEVERITY_WARNING)
    infos = sum(1 for v in violations if v.severity == SEVERITY_INFO)
    fixable = sum(1 for v in violations if v.fixable)

    lines.append(
        f"Total: {len(violations)} violations "
        f"({errors} errors, {warnings} warnings, {infos} info)"
    )
    if fixable:
        lines.append(f"Fixable: {fixable} (run with --fix)")
    lines.append("")

    for category, cat_violations in sorted(by_category.items()):
        lines.append(f"--- {category.upper()} ({len(cat_violations)}) ---")
        for v in sorted(cat_violations, key=lambda x: x.file):
            lines.append(f"  {v}")
        lines.append("")

    return "\n".join(lines)


def format_json(
    violations: list[Violation], files_scanned: int
) -> str:
    """Format violations as JSON."""
    return json.dumps(
        {
            "target": str(CLAUDE_DIR),
            "files_scanned": files_scanned,
            "total_violations": len(violations),
            "errors": sum(
                1 for v in violations if v.severity == SEVERITY_ERROR
            ),
            "warnings": sum(
                1 for v in violations if v.severity == SEVERITY_WARNING
            ),
            "info": sum(
                1 for v in violations if v.severity == SEVERITY_INFO
            ),
            "fixable": sum(1 for v in violations if v.fixable),
            "violations": [v.to_dict() for v in violations],
        },
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint documentation in .claude/ harness directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Scan and report only, no changes (default)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all files being scanned",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix what's possible (add frontmatter, update stale grades)",
    )

    args = parser.parse_args()

    violations, files_scanned = lint(fix=args.fix, verbose=args.verbose)

    if args.json_output:
        print(format_json(violations, files_scanned))
    else:
        print(format_text(violations, files_scanned))

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
