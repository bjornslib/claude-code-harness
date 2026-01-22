"""
Pytest fixtures for Claude Code hook testing.

This module provides shared fixtures for testing PostToolUse hooks,
particularly the post-push code review hook infrastructure.

Usage:
    pytest .claude/tests/hooks/ -v

Fixture Categories:
    - Hook Input Fixtures: Mock stdin JSON payloads for PostToolUse hooks
    - Detection Logic Fixtures: Pattern matching helpers
    - Expected Output Fixtures: Expected hook response structures
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Path Constants
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"
HOOKS_DIR = Path(__file__).parent.parent.parent / "hooks"


# =============================================================================
# Hook Input Fixtures - Loading JSON payloads
# =============================================================================


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def hooks_dir() -> Path:
    """Return the path to the hooks directory."""
    return HOOKS_DIR


def load_fixture(fixture_name: str) -> dict[str, Any]:
    """Load a JSON fixture file by name (without .json extension)."""
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    with open(fixture_path, "r") as f:
        return json.load(f)


# =============================================================================
# AC-1: Push Success Fixtures
# =============================================================================


@pytest.fixture
def push_success_github_main() -> dict[str, Any]:
    """PostToolUse input for successful push to GitHub main branch."""
    return load_fixture("push_success_github_main")


@pytest.fixture
def push_success_github_new_branch() -> dict[str, Any]:
    """PostToolUse input for successful push creating a new branch on GitHub."""
    return load_fixture("push_success_github_new_branch")


@pytest.fixture
def push_success_gitlab() -> dict[str, Any]:
    """PostToolUse input for successful push to GitLab main branch."""
    return load_fixture("push_success_gitlab")


@pytest.fixture
def all_push_success_fixtures() -> list[dict[str, Any]]:
    """Return all push success fixtures for parameterized testing."""
    return [
        load_fixture("push_success_github_main"),
        load_fixture("push_success_github_new_branch"),
        load_fixture("push_success_gitlab"),
    ]


# =============================================================================
# AC-2: Non-Push Command Fixtures
# =============================================================================


@pytest.fixture
def bash_ls() -> dict[str, Any]:
    """PostToolUse input for 'ls' command."""
    return load_fixture("bash_ls")


@pytest.fixture
def bash_git_status() -> dict[str, Any]:
    """PostToolUse input for 'git status' command."""
    return load_fixture("bash_git_status")


@pytest.fixture
def bash_git_commit() -> dict[str, Any]:
    """PostToolUse input for 'git commit' command."""
    return load_fixture("bash_git_commit")


@pytest.fixture
def bash_npm_run() -> dict[str, Any]:
    """PostToolUse input for 'npm run build' command."""
    return load_fixture("bash_npm_run")


@pytest.fixture
def all_non_push_fixtures() -> list[dict[str, Any]]:
    """Return all non-push command fixtures for parameterized testing."""
    return [
        load_fixture("bash_ls"),
        load_fixture("bash_git_status"),
        load_fixture("bash_git_commit"),
        load_fixture("bash_npm_run"),
    ]


# =============================================================================
# AC-3: Push Failure/Skip Fixtures
# =============================================================================


@pytest.fixture
def push_everything_up_to_date() -> dict[str, Any]:
    """PostToolUse input for push with no new commits."""
    return load_fixture("push_everything_up_to_date")


@pytest.fixture
def push_auth_failed() -> dict[str, Any]:
    """PostToolUse input for push with authentication failure."""
    return load_fixture("push_auth_failed")


@pytest.fixture
def push_rejected() -> dict[str, Any]:
    """PostToolUse input for push rejected due to remote changes."""
    return load_fixture("push_rejected")


@pytest.fixture
def push_error() -> dict[str, Any]:
    """PostToolUse input for push with general error."""
    return load_fixture("push_error")


@pytest.fixture
def push_remote_rejected() -> dict[str, Any]:
    """PostToolUse input for push rejected by remote (protected branch)."""
    return load_fixture("push_remote_rejected")


@pytest.fixture
def all_push_failure_fixtures() -> list[dict[str, Any]]:
    """Return all push failure fixtures for parameterized testing."""
    return [
        load_fixture("push_everything_up_to_date"),
        load_fixture("push_auth_failed"),
        load_fixture("push_rejected"),
        load_fixture("push_error"),
        load_fixture("push_remote_rejected"),
    ]


# =============================================================================
# Expected Output Fixtures
# =============================================================================


@pytest.fixture
def expected_trigger_response() -> dict[str, Any]:
    """Expected hook output when post-push review should trigger."""
    return {
        "continue": True,
        "suppressOutput": False,
        "systemMessage": "Post-push review triggered. Invoking codebase-quality:post-push skill...",
    }


@pytest.fixture
def expected_no_trigger_response() -> dict[str, Any]:
    """Expected hook output when post-push review should NOT trigger."""
    return {
        "continue": True,
    }


# =============================================================================
# Hook Execution Helpers
# =============================================================================


class HookRunner:
    """Helper class to execute hooks and capture output."""

    def __init__(self, hook_path: Path):
        self.hook_path = hook_path

    def run(self, input_data: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
        """
        Execute the hook with the given input and return parsed JSON output.

        Args:
            input_data: The PostToolUse hook input dictionary
            timeout: Maximum execution time in seconds

        Returns:
            Parsed JSON output from the hook

        Raises:
            subprocess.TimeoutExpired: If hook exceeds timeout
            json.JSONDecodeError: If hook output is not valid JSON
        """
        input_json = json.dumps(input_data)

        result = subprocess.run(
            [str(self.hook_path)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Empty stdout means hook returned without output (continue with no message)
        if not result.stdout.strip():
            return {"continue": True}

        return json.loads(result.stdout)

    def run_raw(
        self, input_data: dict[str, Any], timeout: int = 10
    ) -> subprocess.CompletedProcess:
        """
        Execute the hook and return the raw subprocess result.

        Useful for testing error conditions and exit codes.
        """
        input_json = json.dumps(input_data)

        return subprocess.run(
            [str(self.hook_path)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=timeout,
        )


@pytest.fixture
def hook_runner(hooks_dir: Path) -> HookRunner:
    """
    Create a HookRunner for the post-push-review hook.

    Note: This will fail if the hook doesn't exist yet (RED phase).
    """
    hook_path = hooks_dir / "post-push-review.sh"
    return HookRunner(hook_path)


# =============================================================================
# Detection Pattern Fixtures
# =============================================================================


@pytest.fixture
def success_patterns() -> list[str]:
    """Patterns that indicate a successful git push."""
    return [
        "To github.com:",
        "To gitlab.com:",
        "main -> main",
        "[new branch]",
    ]


@pytest.fixture
def failure_patterns() -> list[str]:
    """Patterns that indicate a failed or no-op push."""
    return [
        "Everything up-to-date",
        "Authentication failed",
        "remote rejected",
        "error:",
        "[rejected]",
    ]


# =============================================================================
# AC-4: Commit Range Detection Fixtures
# =============================================================================


@pytest.fixture
def reflog_normal_push() -> dict[str, Any]:
    """Reflog fixture for normal push with single commit since last push."""
    return load_fixture("reflog_normal_push")


@pytest.fixture
def reflog_multiple_commits() -> dict[str, Any]:
    """Reflog fixture with multiple commits since last push."""
    return load_fixture("reflog_multiple_commits")


@pytest.fixture
def reflog_force_push() -> dict[str, Any]:
    """Reflog fixture for force push scenario (rewritten history)."""
    return load_fixture("reflog_force_push")


@pytest.fixture
def reflog_multiple_branches() -> dict[str, Any]:
    """Reflog fixture with multiple branches and different push histories."""
    return load_fixture("reflog_multiple_branches")


@pytest.fixture
def reflog_no_new_commits() -> dict[str, Any]:
    """Reflog fixture where HEAD equals last push (no new commits)."""
    return load_fixture("reflog_no_new_commits")


@pytest.fixture
def reflog_with_merge() -> dict[str, Any]:
    """Reflog fixture including a merge commit in the range."""
    return load_fixture("reflog_with_merge")


# =============================================================================
# AC-5: First Push Fallback Fixtures
# =============================================================================


@pytest.fixture
def reflog_no_push() -> dict[str, Any]:
    """Reflog fixture for first push ever (no push history)."""
    return load_fixture("reflog_no_push")


@pytest.fixture
def reflog_few_commits() -> dict[str, Any]:
    """Reflog fixture with fewer than 10 commits in repo."""
    return load_fixture("reflog_few_commits")


@pytest.fixture
def reflog_new_branch_first_push() -> dict[str, Any]:
    """Reflog fixture for first push on a new branch."""
    return load_fixture("reflog_new_branch_first_push")


@pytest.fixture
def reflog_exactly_10_commits() -> dict[str, Any]:
    """Reflog fixture with exactly 10 commits (boundary case)."""
    return load_fixture("reflog_exactly_10_commits")


@pytest.fixture
def reflog_expired() -> dict[str, Any]:
    """Reflog fixture where old entries have been garbage collected."""
    return load_fixture("reflog_expired")


@pytest.fixture
def all_reflog_fixtures() -> list[dict[str, Any]]:
    """Return all reflog fixtures for parameterized testing."""
    return [
        load_fixture("reflog_normal_push"),
        load_fixture("reflog_multiple_commits"),
        load_fixture("reflog_force_push"),
        load_fixture("reflog_no_push"),
        load_fixture("reflog_few_commits"),
    ]
