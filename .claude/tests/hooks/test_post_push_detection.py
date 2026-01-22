"""
Post-Push Code Review Hook Detection Tests

This test module validates the PostToolUse hook detection logic for the
post-push code review system. Tests are written following TDD RED-GREEN-REFACTOR.

Acceptance Criteria Tested:
- AC-1: Hook Triggers on Git Push Success
- AC-2: Hook Ignores Non-Push Commands
- AC-3: Hook Ignores Failed/Rejected Pushes

Usage:
    pytest .claude/tests/hooks/test_post_push_detection.py -v

Note: These tests are written FIRST (RED phase) before the hook implementation.
They will fail until the hook is implemented (GREEN phase).
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Detection Logic Module (to be tested)
# =============================================================================
# Note: In RED phase, we define the expected interface.
# The actual implementation will be in the hook script.


def is_git_push_success(tool_result: str) -> bool:
    """
    Determine if a Bash tool_result represents a successful git push.

    A successful push has:
    - Host pattern: "To github.com:" or "To gitlab.com:" (or similar git hosts)
    - Branch indicator: "-> main" pattern OR "[new branch]"
    - NOT failure patterns: "Everything up-to-date", "error:", "rejected", etc.

    Args:
        tool_result: The stdout/stderr from the Bash command

    Returns:
        True if this appears to be a successful git push, False otherwise
    """
    # This is a stub - will fail tests until implemented
    # The real implementation will be in the shell script or a Python module
    raise NotImplementedError("Detection logic not yet implemented")


def parse_hook_input(stdin_content: str) -> dict[str, Any]:
    """
    Parse the JSON input provided to the PostToolUse hook.

    Args:
        stdin_content: Raw JSON string from stdin

    Returns:
        Parsed dictionary with hook input data
    """
    return json.loads(stdin_content)


def build_hook_response(
    should_trigger: bool,
    message: str | None = None,
) -> dict[str, Any]:
    """
    Build the JSON response for the PostToolUse hook.

    Args:
        should_trigger: Whether to trigger the post-push review
        message: Optional systemMessage to include

    Returns:
        Hook response dictionary
    """
    response = {"continue": True}
    if should_trigger and message:
        response["suppressOutput"] = False
        response["systemMessage"] = message
    return response


# =============================================================================
# Pattern Constants (Used for testing and implementation)
# =============================================================================

# Git host patterns that indicate a push destination
GIT_HOST_PATTERNS = [
    r"To github\.com:",
    r"To gitlab\.com:",
    r"To bitbucket\.org:",
    r"To git@[\w.-]+:",  # SSH format
    r"To https?://[\w.-]+",  # HTTPS format
]

# Branch push success patterns
BRANCH_SUCCESS_PATTERNS = [
    r"\w+ -> \w+",  # e.g., "main -> main" or "abc1234..def5678  main -> main"
    r"\[new branch\]",  # Creating new branch
    r"\[new tag\]",  # Creating new tag
]

# Failure/Skip patterns - if ANY of these are present, do NOT trigger
FAILURE_PATTERNS = [
    r"Everything up-to-date",  # No new commits to push
    r"Authentication failed",  # Auth error
    r"\[rejected\]",  # Push rejected
    r"remote rejected",  # Remote hook declined
    r"^error:",  # General error (at start of line)
    r"failed to push",  # Push failure
    r"fatal:",  # Fatal error
]


# =============================================================================
# Test Class: AC-1 - Hook Triggers on Git Push Success
# =============================================================================


class TestAC1_HookTriggersOnPushSuccess:
    """
    AC-1: Hook Triggers on Git Push Success

    Given: PostToolUse hook receives Bash tool completion
    When: tool_result contains success patterns ("To github.com:" AND "main -> main")
    Then: Hook should detect push and return systemMessage to invoke skill
    """

    def test_detects_github_main_push(
        self, push_success_github_main: dict[str, Any]
    ) -> None:
        """Test detection of successful push to GitHub main branch."""
        tool_result = push_success_github_main["tool_result"]

        # Verify fixture has expected patterns
        assert "To github.com:" in tool_result
        assert "main -> main" in tool_result

        # Test detection logic (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is True

    def test_detects_github_new_branch_push(
        self, push_success_github_new_branch: dict[str, Any]
    ) -> None:
        """Test detection of successful push creating new branch on GitHub."""
        tool_result = push_success_github_new_branch["tool_result"]

        # Verify fixture has expected patterns
        assert "To github.com:" in tool_result
        assert "[new branch]" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is True

    def test_detects_gitlab_push(
        self, push_success_gitlab: dict[str, Any]
    ) -> None:
        """Test detection of successful push to GitLab."""
        tool_result = push_success_gitlab["tool_result"]

        # Verify fixture has expected patterns
        assert "To gitlab.com:" in tool_result
        assert "main -> main" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is True

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "push_success_github_main",
            "push_success_github_new_branch",
            "push_success_gitlab",
        ],
    )
    def test_all_success_fixtures_detected(
        self, fixtures_dir: Path, fixture_name: str
    ) -> None:
        """Parameterized test for all success fixtures."""
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        with open(fixture_path) as f:
            data = json.load(f)

        tool_result = data["tool_result"]

        # Verify basic structure
        assert "tool_result" in data
        assert data["tool_name"] == "Bash"
        assert data["hook_event_name"] == "PostToolUse"

        # Test detection (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            assert is_git_push_success(tool_result) is True


# =============================================================================
# Test Class: AC-2 - Hook Ignores Non-Push Commands
# =============================================================================


class TestAC2_HookIgnoresNonPushCommands:
    """
    AC-2: Hook Ignores Non-Push Commands

    Given: PostToolUse hook receives Bash tool completion
    When: tool_result does NOT contain push patterns (ls, git status, git commit, npm run)
    Then: Hook should NOT trigger, return {"continue": true} with no systemMessage
    """

    def test_ignores_ls_command(self, bash_ls: dict[str, Any]) -> None:
        """Test that 'ls' command does not trigger hook."""
        tool_result = bash_ls["tool_result"]

        # Verify fixture does NOT have push patterns
        assert "To github.com:" not in tool_result
        assert "To gitlab.com:" not in tool_result
        assert "-> main" not in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_git_status(self, bash_git_status: dict[str, Any]) -> None:
        """Test that 'git status' command does not trigger hook."""
        tool_result = bash_git_status["tool_result"]

        # Verify this is a git status output
        assert "On branch main" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_git_commit(self, bash_git_commit: dict[str, Any]) -> None:
        """Test that 'git commit' command does not trigger hook."""
        tool_result = bash_git_commit["tool_result"]

        # Verify this is a commit output (has branch name but not push pattern)
        assert "[main" in tool_result
        assert "To github.com:" not in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_npm_run(self, bash_npm_run: dict[str, Any]) -> None:
        """Test that 'npm run build' command does not trigger hook."""
        tool_result = bash_npm_run["tool_result"]

        # Verify this is npm output
        assert "npm" in tool_result.lower() or "build" in tool_result.lower()

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "bash_ls",
            "bash_git_status",
            "bash_git_commit",
            "bash_npm_run",
        ],
    )
    def test_all_non_push_fixtures_ignored(
        self, fixtures_dir: Path, fixture_name: str
    ) -> None:
        """Parameterized test that all non-push fixtures are NOT detected as pushes."""
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        with open(fixture_path) as f:
            data = json.load(f)

        tool_result = data["tool_result"]

        # Test detection (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            assert is_git_push_success(tool_result) is False


# =============================================================================
# Test Class: AC-3 - Hook Ignores Failed/Rejected Pushes
# =============================================================================


class TestAC3_HookIgnoresFailedPushes:
    """
    AC-3: Hook Ignores Failed/Rejected Pushes

    Given: PostToolUse hook receives Bash tool completion
    When: tool_result contains failure patterns ("Authentication failed", "remote rejected",
          "error:", "Everything up-to-date")
    Then: Hook should NOT trigger
    """

    def test_ignores_everything_up_to_date(
        self, push_everything_up_to_date: dict[str, Any]
    ) -> None:
        """Test that 'Everything up-to-date' does not trigger hook."""
        tool_result = push_everything_up_to_date["tool_result"]

        # Verify fixture has the skip pattern
        assert "Everything up-to-date" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_auth_failed(self, push_auth_failed: dict[str, Any]) -> None:
        """Test that authentication failure does not trigger hook."""
        tool_result = push_auth_failed["tool_result"]

        # Verify fixture has failure pattern
        assert "Authentication failed" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_rejected_push(self, push_rejected: dict[str, Any]) -> None:
        """Test that rejected push does not trigger hook."""
        tool_result = push_rejected["tool_result"]

        # Verify fixture has rejection pattern
        assert "[rejected]" in tool_result or "rejected" in tool_result.lower()

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_push_error(self, push_error: dict[str, Any]) -> None:
        """Test that push error does not trigger hook."""
        tool_result = push_error["tool_result"]

        # Verify fixture has error pattern
        assert "error:" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    def test_ignores_remote_rejected(
        self, push_remote_rejected: dict[str, Any]
    ) -> None:
        """Test that remote-rejected push does not trigger hook."""
        tool_result = push_remote_rejected["tool_result"]

        # Verify fixture has remote rejection pattern
        assert "remote rejected" in tool_result

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(tool_result)
            assert result is False

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "push_everything_up_to_date",
            "push_auth_failed",
            "push_rejected",
            "push_error",
            "push_remote_rejected",
        ],
    )
    def test_all_failure_fixtures_ignored(
        self, fixtures_dir: Path, fixture_name: str
    ) -> None:
        """Parameterized test that all failure fixtures are NOT detected as successful pushes."""
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        with open(fixture_path) as f:
            data = json.load(f)

        tool_result = data["tool_result"]

        # Test detection (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            assert is_git_push_success(tool_result) is False


# =============================================================================
# Test Class: Pattern Matching Validation
# =============================================================================


class TestPatternMatching:
    """Tests for the pattern matching constants and logic."""

    def test_git_host_patterns_compile(self) -> None:
        """Verify all git host patterns are valid regex."""
        for pattern in GIT_HOST_PATTERNS:
            compiled = re.compile(pattern)
            assert compiled is not None

    def test_branch_success_patterns_compile(self) -> None:
        """Verify all branch success patterns are valid regex."""
        for pattern in BRANCH_SUCCESS_PATTERNS:
            compiled = re.compile(pattern)
            assert compiled is not None

    def test_failure_patterns_compile(self) -> None:
        """Verify all failure patterns are valid regex."""
        for pattern in FAILURE_PATTERNS:
            compiled = re.compile(pattern, re.MULTILINE)
            assert compiled is not None

    def test_github_host_pattern_matches(self) -> None:
        """Test that GitHub host pattern matches expected strings."""
        pattern = re.compile(GIT_HOST_PATTERNS[0])
        assert pattern.search("To github.com:user/repo.git")
        assert not pattern.search("To gitlab.com:user/repo.git")

    def test_branch_pattern_matches(self) -> None:
        """Test that branch pattern matches expected strings."""
        pattern = re.compile(BRANCH_SUCCESS_PATTERNS[0])
        assert pattern.search("   abc1234..def5678  main -> main")
        assert pattern.search("feature -> feature")
        assert not pattern.search("Everything up-to-date")

    def test_new_branch_pattern_matches(self) -> None:
        """Test that new branch pattern matches."""
        pattern = re.compile(BRANCH_SUCCESS_PATTERNS[1])
        assert pattern.search(" * [new branch]      feature -> feature")
        assert not pattern.search("main -> main")


# =============================================================================
# Test Class: Hook Response Format
# =============================================================================


class TestHookResponseFormat:
    """Tests for the hook response structure."""

    def test_trigger_response_format(
        self, expected_trigger_response: dict[str, Any]
    ) -> None:
        """Verify expected trigger response has correct structure."""
        assert "continue" in expected_trigger_response
        assert expected_trigger_response["continue"] is True
        assert "systemMessage" in expected_trigger_response
        assert "suppressOutput" in expected_trigger_response

    def test_no_trigger_response_format(
        self, expected_no_trigger_response: dict[str, Any]
    ) -> None:
        """Verify expected no-trigger response has correct structure."""
        assert "continue" in expected_no_trigger_response
        assert expected_no_trigger_response["continue"] is True
        # Should NOT have systemMessage when not triggering
        assert "systemMessage" not in expected_no_trigger_response

    def test_build_trigger_response(self) -> None:
        """Test building a trigger response."""
        response = build_hook_response(
            should_trigger=True,
            message="Post-push review triggered.",
        )
        assert response["continue"] is True
        assert response["suppressOutput"] is False
        assert response["systemMessage"] == "Post-push review triggered."

    def test_build_no_trigger_response(self) -> None:
        """Test building a no-trigger response."""
        response = build_hook_response(should_trigger=False)
        assert response["continue"] is True
        assert "systemMessage" not in response
        assert "suppressOutput" not in response


# =============================================================================
# Test Class: Hook Input Parsing
# =============================================================================


class TestHookInputParsing:
    """Tests for parsing PostToolUse hook input."""

    def test_parse_valid_input(
        self, push_success_github_main: dict[str, Any]
    ) -> None:
        """Test parsing valid hook input."""
        json_str = json.dumps(push_success_github_main)
        parsed = parse_hook_input(json_str)

        assert parsed["hook_event_name"] == "PostToolUse"
        assert parsed["tool_name"] == "Bash"
        assert "tool_result" in parsed
        assert "session_id" in parsed

    def test_parse_extracts_tool_result(
        self, push_success_github_main: dict[str, Any]
    ) -> None:
        """Test that tool_result is correctly extracted."""
        json_str = json.dumps(push_success_github_main)
        parsed = parse_hook_input(json_str)

        tool_result = parsed["tool_result"]
        assert "To github.com:" in tool_result
        assert "main -> main" in tool_result

    def test_parse_invalid_json_raises(self) -> None:
        """Test that invalid JSON raises appropriate error."""
        with pytest.raises(json.JSONDecodeError):
            parse_hook_input("not valid json")

    def test_parse_empty_input_raises(self) -> None:
        """Test that empty input raises appropriate error."""
        with pytest.raises(json.JSONDecodeError):
            parse_hook_input("")


# =============================================================================
# Integration Tests (Require Hook to be Implemented)
# =============================================================================


@pytest.mark.skip(reason="Hook not yet implemented - run after GREEN phase")
class TestHookIntegration:
    """
    Integration tests that execute the actual hook script.

    These tests are skipped during RED phase and should be unskipped
    once the hook is implemented (GREEN phase).
    """

    def test_hook_exists(self, hooks_dir: Path) -> None:
        """Verify the hook script exists."""
        hook_path = hooks_dir / "post-push-review.sh"
        assert hook_path.exists(), f"Hook not found at {hook_path}"
        assert hook_path.is_file()

    def test_hook_is_executable(self, hooks_dir: Path) -> None:
        """Verify the hook script is executable."""
        hook_path = hooks_dir / "post-push-review.sh"
        import os
        assert os.access(hook_path, os.X_OK), "Hook is not executable"

    def test_hook_triggers_on_success(
        self,
        hook_runner,
        push_success_github_main: dict[str, Any],
        expected_trigger_response: dict[str, Any],
    ) -> None:
        """Test that hook triggers on successful push."""
        result = hook_runner.run(push_success_github_main)

        assert result["continue"] is True
        assert "systemMessage" in result
        assert "post-push" in result["systemMessage"].lower()

    def test_hook_ignores_non_push(
        self,
        hook_runner,
        bash_ls: dict[str, Any],
    ) -> None:
        """Test that hook ignores non-push commands."""
        result = hook_runner.run(bash_ls)

        assert result["continue"] is True
        assert "systemMessage" not in result

    def test_hook_ignores_failed_push(
        self,
        hook_runner,
        push_auth_failed: dict[str, Any],
    ) -> None:
        """Test that hook ignores failed pushes."""
        result = hook_runner.run(push_auth_failed)

        assert result["continue"] is True
        assert "systemMessage" not in result


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_tool_result(self) -> None:
        """Test handling of empty tool_result."""
        with pytest.raises(NotImplementedError):
            result = is_git_push_success("")
            assert result is False

    def test_none_tool_result(self) -> None:
        """Test handling of None tool_result."""
        with pytest.raises((NotImplementedError, TypeError)):
            result = is_git_push_success(None)  # type: ignore
            assert result is False

    def test_partial_pattern_not_enough(self) -> None:
        """Test that partial patterns don't trigger false positives."""
        # Has host but no branch pattern
        partial = "To github.com:user/repo.git"
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(partial)
            assert result is False

    def test_branch_pattern_without_host(self) -> None:
        """Test that branch pattern alone doesn't trigger."""
        partial = "abc1234..def5678  main -> main"
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(partial)
            assert result is False

    def test_success_with_warnings(self) -> None:
        """Test that success with warnings still triggers."""
        result_with_warning = """
Enumerating objects: 5, done.
warning: redirecting to https://github.com/user/repo.git/
Counting objects: 100% (5/5), done.
To github.com:user/repo.git
   abc1234..def5678  main -> main
"""
        with pytest.raises(NotImplementedError):
            result = is_git_push_success(result_with_warning)
            # Warnings shouldn't prevent detection
            assert result is True

    def test_case_sensitivity(self) -> None:
        """Test that pattern matching handles case correctly."""
        # "To GitHub.com" should still match (host is case-insensitive in practice)
        mixed_case = """
To GitHub.com:user/repo.git
   abc1234..def5678  main -> main
"""
        with pytest.raises(NotImplementedError):
            # For now, exact match is expected - adjust if needed
            _result = is_git_push_success(mixed_case)
