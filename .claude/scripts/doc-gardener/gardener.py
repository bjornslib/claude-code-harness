#!/usr/bin/env python3
"""
Doc-Gardener: Automated remediation for .claude/ harness documentation.

Wraps lint.py to:
  1. Run full lint scan (before snapshot)
  2. Auto-fix what's possible (--execute mode)
  3. Re-scan to get remaining violations (after snapshot)
  4. Generate gardening-report.md with before/after stats

Usage:
  python .claude/scripts/doc-gardener/gardener.py                # Dry-run: report only
  python .claude/scripts/doc-gardener/gardener.py --execute      # Apply fixes, generate report
  python .claude/scripts/doc-gardener/gardener.py --report       # Generate report without fixing
  python .claude/scripts/doc-gardener/gardener.py --json         # Machine-readable output

Exit codes:
  0 = clean (no manual-fix items remaining)
  1 = manual-fix items exist (doc-debt)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
LINTER_SCRIPT = SCRIPT_DIR / "lint.py"
CLAUDE_DIR = SCRIPT_DIR.parent.parent
REPORT_FILE = CLAUDE_DIR / "documentation" / "gardening-report.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_linter(
    json_output: bool = True, fix: bool = False
) -> dict[str, Any]:
    """Run lint.py and return parsed JSON output."""
    cmd = [sys.executable, str(LINTER_SCRIPT)]
    if json_output:
        cmd.append("--json")
    if fix:
        cmd.append("--fix")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if json_output:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "target": str(CLAUDE_DIR),
                "files_scanned": 0,
                "total_violations": 0,
                "errors": 0,
                "warnings": 0,
                "info": 0,
                "fixable": 0,
                "violations": [],
            }
    else:
        return {"text_output": result.stdout}


def categorize_violations(
    violations: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split violations into fixable vs. manual-fix-required."""
    fixable = [v for v in violations if v.get("fixable", False)]
    manual = [v for v in violations if not v.get("fixable", False)]
    return fixable, manual


def generate_report(
    timestamp: str,
    before: dict[str, Any],
    after: dict[str, Any],
    fixed_count: int,
    executed: bool,
) -> str:
    """Generate markdown report with before/after stats."""
    lines = []
    lines.append("# Harness Documentation Gardening Report")
    lines.append("")
    lines.append(f"**Generated**: {timestamp}")
    lines.append(f"**Target**: `{before.get('target', '.claude/')}`")
    mode_str = "EXECUTE (fixes applied)" if executed else "DRY-RUN (no changes)"
    lines.append(f"**Mode**: {mode_str}")
    lines.append("")

    # Summary stats
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Files scanned**: {before['files_scanned']}")
    lines.append(f"- **Total violations found**: {before['total_violations']}")
    lines.append(f"- **Auto-fixed**: {fixed_count}")
    lines.append(
        f"- **Remaining violations**: {after['total_violations']}"
    )
    lines.append("")

    # Severity breakdown
    lines.append("### Before")
    lines.append("")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| Errors   | {before['errors']} |")
    lines.append(f"| Warnings | {before['warnings']} |")
    lines.append(f"| Info     | {before['info']} |")
    lines.append(f"| Fixable  | {before['fixable']} |")
    lines.append("")

    if executed:
        lines.append("### After Auto-fix")
        lines.append("")
        lines.append(f"| Severity | Count |")
        lines.append(f"|----------|-------|")
        lines.append(f"| Errors   | {after['errors']} |")
        lines.append(f"| Warnings | {after['warnings']} |")
        lines.append(f"| Info     | {after['info']} |")
        lines.append("")

    # Auto-fixed violations
    before_violations = before.get("violations", [])
    after_violations = after.get("violations", [])
    fixable, _ = categorize_violations(before_violations)

    if fixable:
        lines.append("## Auto-fixed Violations")
        lines.append("")
        if executed:
            lines.append(
                "These violations were automatically remediated:"
            )
        else:
            lines.append(
                "These violations **would be** auto-fixed with `--execute`:"
            )
        lines.append("")
        lines.append("| File | Category | Severity | Message |")
        lines.append("|------|----------|----------|---------|")
        for v in fixable:
            file_path = v.get("file", "")
            category = v.get("category", "")
            severity = v.get("severity", "")
            message = v.get("message", "").replace("|", "\\|")
            lines.append(
                f"| `{file_path}` | {category} | {severity} | {message} |"
            )
        lines.append("")

    # Manual-fix-required violations
    _, manual = categorize_violations(after_violations)

    if manual:
        lines.append("## Manual Fix Required (Doc-Debt)")
        lines.append("")
        lines.append("These violations require human attention:")
        lines.append("")
        lines.append("| File | Category | Severity | Message |")
        lines.append("|------|----------|----------|---------|")
        for v in manual:
            file_path = v.get("file", "")
            category = v.get("category", "")
            severity = v.get("severity", "")
            message = v.get("message", "").replace("|", "\\|")
            lines.append(
                f"| `{file_path}` | {category} | {severity} | {message} |"
            )
        lines.append("")
    else:
        lines.append("## Status: Clean")
        lines.append("")
        lines.append(
            "No manual-fix violations remain. "
            "Harness documentation is lint-clean."
        )
        lines.append("")

    return "\n".join(lines)


def format_summary(
    before: dict[str, Any],
    after: dict[str, Any],
    fixed_count: int,
    executed: bool,
) -> str:
    """Format a concise summary for stdout."""
    lines = []
    lines.append("Harness Documentation Gardening Summary")
    lines.append("=" * 50)
    mode_str = "EXECUTE" if executed else "DRY-RUN"
    lines.append(f"Mode: {mode_str}")
    lines.append(f"Files scanned: {before['files_scanned']}")
    lines.append(f"Violations found: {before['total_violations']}")
    if executed:
        lines.append(f"Auto-fixed: {fixed_count}")
    else:
        lines.append(f"Would auto-fix: {fixed_count}")
    lines.append(f"Remaining: {after['total_violations']}")
    lines.append("")

    if after["total_violations"] == 0:
        lines.append("Status: CLEAN (no manual-fix items)")
    else:
        _, manual = categorize_violations(after.get("violations", []))
        lines.append(
            f"Status: {len(manual)} manual-fix items remain (doc-debt)"
        )

    return "\n".join(lines)


def format_json_output(
    timestamp: str,
    before: dict[str, Any],
    after: dict[str, Any],
    fixed_count: int,
    executed: bool,
) -> str:
    """Format machine-readable JSON output."""
    fixable, manual_before = categorize_violations(
        before.get("violations", [])
    )
    _, manual_after = categorize_violations(
        after.get("violations", [])
    )

    return json.dumps(
        {
            "timestamp": timestamp,
            "mode": "execute" if executed else "dry-run",
            "target": before.get("target", str(CLAUDE_DIR)),
            "files_scanned": before["files_scanned"],
            "total_violations_found": before["total_violations"],
            "auto_fixed": fixed_count,
            "remaining_violations": after["total_violations"],
            "severity_before": {
                "errors": before["errors"],
                "warnings": before["warnings"],
                "info": before["info"],
            },
            "severity_after": {
                "errors": after["errors"],
                "warnings": after["warnings"],
                "info": after["info"],
            },
            "auto_fixed_violations": fixable,
            "manual_fix_required": manual_after,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Doc-Gardener: Automated remediation for "
            ".claude/ harness documentation"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply auto-fixes and generate report",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate report file (without applying fixes)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Machine-readable JSON output",
    )

    args = parser.parse_args()

    timestamp = datetime.now().isoformat(timespec="seconds")

    # Step 1: Initial scan (before snapshot)
    before = run_linter(json_output=True, fix=False)

    if not args.execute:
        # Dry-run mode: report what would happen
        fixable, manual = categorize_violations(
            before.get("violations", [])
        )
        fixed_count = len(fixable)

        if args.report:
            # Generate report file even in dry-run
            report_content = generate_report(
                timestamp, before, before, 0, executed=False
            )
            REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
            REPORT_FILE.write_text(report_content, encoding="utf-8")

        if args.json_output:
            print(format_json_output(
                timestamp, before, before, 0, executed=False
            ))
        else:
            print("DRY-RUN MODE (no changes made)")
            print("=" * 50)
            print(f"Files scanned: {before['files_scanned']}")
            print(f"Total violations: {before['total_violations']}")
            print(f"Would auto-fix: {len(fixable)}")
            print(f"Manual-fix required: {len(manual)}")
            print("")
            if args.report:
                print(f"Report written to: {REPORT_FILE}")
            else:
                print(
                    "Run with --execute to apply fixes. "
                    "Add --report to generate report file."
                )

        return 1 if manual else 0

    # Step 2: Apply fixes (execute mode)
    run_linter(json_output=False, fix=True)
    fixed_count = before.get("fixable", 0)

    # Step 3: Re-scan for remaining violations (after snapshot)
    after = run_linter(json_output=True, fix=False)

    # Step 4: Generate report and/or output
    if args.json_output:
        print(format_json_output(
            timestamp, before, after, fixed_count, executed=True
        ))
    else:
        # Always write report in execute mode
        report_content = generate_report(
            timestamp, before, after, fixed_count, executed=True
        )
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(report_content, encoding="utf-8")

        # Print summary
        print(format_summary(before, after, fixed_count, executed=True))
        print("")
        try:
            rel_report = REPORT_FILE.relative_to(CLAUDE_DIR.parent)
        except ValueError:
            rel_report = REPORT_FILE
        print(f"Full report: {rel_report}")

    # Exit code: 0 if clean, 1 if manual-fix items remain
    _, manual_remaining = categorize_violations(
        after.get("violations", [])
    )
    return 1 if manual_remaining else 0


if __name__ == "__main__":
    sys.exit(main())
