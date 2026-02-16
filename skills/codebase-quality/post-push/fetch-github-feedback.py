#!/usr/bin/env python3
"""
Fetch GitHub Feedback Tool

Fetches feedback from GitHub for both push-level and PR-level sources.
Can be run as a CLI tool or imported as a module.

Last touched: 2025-12-23

Usage:
    # Check feedback for a specific commit (push-level)
    ./fetch-github-feedback.py --commit abc123

    # Check feedback for a specific PR (PR-level)
    ./fetch-github-feedback.py --pr 137

    # Check both for current HEAD (auto-detect PR)
    ./fetch-github-feedback.py --auto

    # Full options
    ./fetch-github-feedback.py --commit abc123 --pr 137 --repo owner/name --json

Sources checked:
    Push-Level (always when --commit provided):
        - Workflow runs triggered by the commit
        - Check run annotations (::warning, ::error from workflows)
        - Commit comments

    PR-Level (when --pr provided):
        - PR comments from bots
        - PR review comments
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Finding:
    """A single finding from GitHub feedback."""
    source: str  # "workflow", "check_run", "commit_comment", "pr_comment"
    severity: Severity
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    author: Optional[str] = None
    url: Optional[str] = None


@dataclass
class FeedbackReport:
    """Aggregated feedback from all sources."""
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    pr_number: Optional[int] = None
    repo: Optional[str] = None

    workflow_runs: list[dict] = field(default_factory=list)
    check_runs: list[dict] = field(default_factory=list)
    annotations: list[dict] = field(default_factory=list)
    commit_comments: list[dict] = field(default_factory=list)
    pr_comments: list[dict] = field(default_factory=list)

    findings: list[Finding] = field(default_factory=list)

    def add_finding(self, finding: Finding):
        self.findings.append(finding)

    def has_critical(self) -> bool:
        return any(f.severity == Severity.CRITICAL for f in self.findings)

    def has_high(self) -> bool:
        return any(f.severity == Severity.HIGH for f in self.findings)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "## Push Feedback Summary",
            "",
            f"**Commit**: `{self.commit_sha[:8] if self.commit_sha else 'N/A'}`",
            f"**Branch**: `{self.branch or 'N/A'}`",
            f"**PR**: #{self.pr_number}" if self.pr_number else "**PR**: None",
            f"**Fetched**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Workflow Runs
        lines.append("### Workflow Runs")
        if self.workflow_runs:
            lines.append("| Workflow | Status | Event |")
            lines.append("|----------|--------|-------|")
            for run in self.workflow_runs:
                status = "✅" if run.get("conclusion") == "success" else "❌" if run.get("conclusion") == "failure" else "⏳"
                lines.append(f"| {run.get('name', 'Unknown')} | {status} {run.get('conclusion', run.get('status', 'unknown'))} | {run.get('event', 'N/A')} |")
        else:
            lines.append("*No workflow runs found for this commit*")
        lines.append("")

        # Check Run Annotations
        lines.append("### Check Run Annotations")
        if self.annotations:
            lines.append(f"**{len(self.annotations)} annotation(s) found:**")
            lines.append("")
            lines.append("| File | Level | Message |")
            lines.append("|------|-------|---------|")
            for ann in self.annotations[:20]:  # Limit to 20
                level_icon = "❌" if ann.get("annotation_level") == "failure" else "⚠️" if ann.get("annotation_level") == "warning" else "ℹ️"
                file_loc = f"{ann.get('path', 'N/A')}:{ann.get('start_line', '')}"
                message = ann.get("message", "")[:80]
                lines.append(f"| {file_loc} | {level_icon} {ann.get('annotation_level', 'N/A')} | {message} |")
            if len(self.annotations) > 20:
                lines.append(f"*... and {len(self.annotations) - 20} more*")
        else:
            lines.append("*No annotations found*")
        lines.append("")

        # Commit Comments
        lines.append("### Commit Comments")
        if self.commit_comments:
            for comment in self.commit_comments[:5]:
                author = comment.get("user", {}).get("login", "unknown")
                body = comment.get("body", "")[:200]
                lines.append(f"**@{author}**: {body}")
        else:
            lines.append("*No comments on this commit*")
        lines.append("")

        # PR Comments
        if self.pr_number:
            lines.append(f"### PR #{self.pr_number} Comments")
            if self.pr_comments:
                for comment in self.pr_comments[:5]:
                    author = comment.get("author", {}).get("login", "unknown")
                    body = comment.get("body", "")[:200]
                    lines.append(f"**@{author}**: {body}")
            else:
                lines.append("*No bot comments on this PR*")
            lines.append("")

        # Action Items
        lines.append("### Action Items")
        if self.findings:
            for i, finding in enumerate(sorted(self.findings, key=lambda f: f.severity.value), 1):
                icon = "🔴" if finding.severity == Severity.CRITICAL else "🟠" if finding.severity == Severity.HIGH else "🟡" if finding.severity == Severity.MEDIUM else "🟢"
                location = f" in {finding.file}:{finding.line}" if finding.file else ""
                lines.append(f"{i}. {icon} **{finding.severity.value}**: {finding.message}{location}")
        else:
            lines.append("✅ **No issues found** - all checks passing")
        lines.append("")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Generate JSON report."""
        return json.dumps({
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "pr_number": self.pr_number,
            "repo": self.repo,
            "workflow_runs": self.workflow_runs,
            "check_runs": self.check_runs,
            "annotations": self.annotations,
            "commit_comments": self.commit_comments,
            "pr_comments": self.pr_comments,
            "findings": [
                {
                    "source": f.source,
                    "severity": f.severity.value,
                    "message": f.message,
                    "file": f.file,
                    "line": f.line,
                    "author": f.author,
                }
                for f in self.findings
            ],
            "summary": {
                "has_critical": self.has_critical(),
                "has_high": self.has_high(),
                "total_findings": len(self.findings),
            }
        }, indent=2)


def run_command(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout
    except subprocess.TimeoutExpired:
        return False, ""
    except Exception as e:
        return False, str(e)


def get_current_commit() -> Optional[str]:
    """Get the current HEAD commit SHA."""
    success, output = run_command(["git", "rev-parse", "HEAD"])
    return output.strip() if success else None


def get_current_branch() -> Optional[str]:
    """Get the current branch name."""
    success, output = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return output.strip() if success else None


def get_pr_number() -> Optional[int]:
    """Get PR number for current branch."""
    success, output = run_command(["gh", "pr", "view", "--json", "number", "-q", ".number"])
    if success and output.strip().isdigit():
        return int(output.strip())
    return None


def get_repo() -> Optional[str]:
    """Get repository owner/name."""
    success, output = run_command(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    return output.strip() if success else None


def fetch_workflow_runs(commit_sha: str) -> list[dict]:
    """Fetch workflow runs for a specific commit."""
    success, output = run_command([
        "gh", "run", "list",
        "--commit", commit_sha,
        "--json", "status,conclusion,name,databaseId,event"
    ])
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return []


def fetch_check_runs(repo: str, commit_sha: str) -> tuple[list[dict], list[dict]]:
    """Fetch check runs and their annotations for a commit."""
    success, output = run_command([
        "gh", "api", f"repos/{repo}/commits/{commit_sha}/check-runs",
        "--jq", ".check_runs"
    ])

    check_runs = []
    annotations = []

    if success:
        try:
            check_runs = json.loads(output)

            # Fetch annotations for each check run with annotations
            for run in check_runs:
                ann_count = run.get("output", {}).get("annotations_count", 0)
                if ann_count > 0:
                    run_id = run.get("id")
                    if run_id:
                        ann_success, ann_output = run_command([
                            "gh", "api", f"repos/{repo}/check-runs/{run_id}/annotations"
                        ])
                        if ann_success:
                            try:
                                annotations.extend(json.loads(ann_output))
                            except json.JSONDecodeError:
                                pass
        except json.JSONDecodeError:
            pass

    return check_runs, annotations


def fetch_commit_comments(repo: str, commit_sha: str) -> list[dict]:
    """Fetch comments on a specific commit."""
    success, output = run_command([
        "gh", "api", f"repos/{repo}/commits/{commit_sha}/comments"
    ])
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return []


def fetch_pr_comments(pr_number: int) -> list[dict]:
    """Fetch comments on a PR."""
    success, output = run_command([
        "gh", "pr", "view", str(pr_number),
        "--json", "comments",
        "-q", ".comments"
    ])
    if success:
        try:
            comments = json.loads(output)
            # Filter to bot comments
            bot_keywords = ["github-actions", "claude", "bot", "dependabot", "renovate"]
            return [
                c for c in comments
                if any(kw in c.get("author", {}).get("login", "").lower() for kw in bot_keywords)
            ]
        except json.JSONDecodeError:
            pass
    return []


def analyze_findings(report: FeedbackReport) -> None:
    """Analyze all sources and populate findings."""

    # Analyze workflow runs
    for run in report.workflow_runs:
        if run.get("conclusion") == "failure":
            report.add_finding(Finding(
                source="workflow",
                severity=Severity.CRITICAL,
                message=f"Workflow '{run.get('name')}' failed",
            ))

    # Analyze check runs
    for run in report.check_runs:
        if run.get("conclusion") == "failure":
            report.add_finding(Finding(
                source="check_run",
                severity=Severity.CRITICAL,
                message=f"Check '{run.get('name')}' failed: {run.get('output', {}).get('title', '')}",
            ))

    # Analyze annotations
    for ann in report.annotations:
        level = ann.get("annotation_level", "notice")
        if level == "failure":
            severity = Severity.CRITICAL
        elif level == "warning":
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        report.add_finding(Finding(
            source="check_run",
            severity=severity,
            message=ann.get("message", "Unknown annotation"),
            file=ann.get("path"),
            line=ann.get("start_line"),
        ))

    # Analyze commit comments
    for comment in report.commit_comments:
        body = comment.get("body", "").lower()
        if "fail" in body or "error" in body or "critical" in body:
            severity = Severity.HIGH
        elif "warning" in body or "fix" in body:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        report.add_finding(Finding(
            source="commit_comment",
            severity=severity,
            message=comment.get("body", "")[:100],
            author=comment.get("user", {}).get("login"),
        ))

    # Analyze PR comments
    for comment in report.pr_comments:
        body = comment.get("body", "").lower()
        if "fail" in body or "error" in body or "changes requested" in body:
            severity = Severity.HIGH
        elif "warning" in body or "review" in body:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        report.add_finding(Finding(
            source="pr_comment",
            severity=severity,
            message=comment.get("body", "")[:100],
            author=comment.get("author", {}).get("login"),
        ))


def fetch_all_feedback(
    commit_sha: Optional[str] = None,
    pr_number: Optional[int] = None,
    repo: Optional[str] = None,
    branch: Optional[str] = None,
) -> FeedbackReport:
    """Fetch all feedback from both push and PR levels."""

    report = FeedbackReport(
        commit_sha=commit_sha,
        branch=branch,
        pr_number=pr_number,
        repo=repo,
    )

    # Fetch push-level feedback if we have commit and repo
    if commit_sha and repo:
        report.workflow_runs = fetch_workflow_runs(commit_sha)
        report.check_runs, report.annotations = fetch_check_runs(repo, commit_sha)
        report.commit_comments = fetch_commit_comments(repo, commit_sha)

    # Fetch PR-level feedback if we have PR number
    if pr_number:
        report.pr_comments = fetch_pr_comments(pr_number)

    # Analyze all sources
    analyze_findings(report)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Fetch GitHub feedback for push and PR events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--commit",
        help="Commit SHA to check (for push-level feedback)",
    )
    parser.add_argument(
        "--pr",
        type=int,
        help="PR number to check (for PR-level feedback)",
    )
    parser.add_argument(
        "--repo",
        help="Repository in owner/name format (auto-detected if not provided)",
    )
    parser.add_argument(
        "--branch",
        help="Branch name (for context only)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect commit, branch, PR, and repo from current git state",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output as JSON instead of markdown",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output if there are findings",
    )

    args = parser.parse_args()

    # Auto-detect values if requested or if nothing provided
    if args.auto or (not args.commit and not args.pr):
        if not args.commit:
            args.commit = get_current_commit()
        if not args.branch:
            args.branch = get_current_branch()
        if not args.pr:
            args.pr = get_pr_number()
        if not args.repo:
            args.repo = get_repo()

    # Need at least commit or PR
    if not args.commit and not args.pr:
        print("Error: Must provide --commit, --pr, or use --auto", file=sys.stderr)
        sys.exit(1)

    # Auto-detect repo if we have commit but no repo
    if args.commit and not args.repo:
        args.repo = get_repo()

    # Fetch all feedback
    report = fetch_all_feedback(
        commit_sha=args.commit,
        pr_number=args.pr,
        repo=args.repo,
        branch=args.branch,
    )

    # Output
    if args.quiet and not report.findings:
        sys.exit(0)

    if args.output_json:
        print(report.to_json())
    else:
        print(report.to_markdown())

    # Exit code based on findings
    if report.has_critical():
        sys.exit(2)
    elif report.has_high():
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
