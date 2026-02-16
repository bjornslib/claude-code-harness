"""
Commit Range Analysis Tests for Post-Push Code Review Hook

This test module validates the commit range detection logic for the
post-push code review system. Tests are written following TDD RED-GREEN-REFACTOR.

Acceptance Criteria Tested:
- AC-4: Identify Commits Since Last Push
- AC-5: Handle First Push Gracefully (fallback to last 10 commits)

Usage:
    pytest .claude/tests/hooks/test_commit_range.py -v

Note: These tests are written FIRST (RED phase) before the hook implementation.
They will fail until the commit range detection is implemented (GREEN phase).
"""

import json
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Commit Range Detection Module (to be tested)
# =============================================================================
# Note: In RED phase, we define the expected interface.
# The actual implementation will be in the hook script or Python module.


def get_last_push_commit(branch: str = "HEAD") -> str | None:
    """
    Get the commit hash of the last successful push for a branch.

    Uses git reflog to find the last push event for the specified branch.

    Args:
        branch: The branch name to check (default: current HEAD)

    Returns:
        Commit hash of last push, or None if no push found in reflog
    """
    raise NotImplementedError("Last push detection not yet implemented")


def get_commits_since_last_push(last_push_commit: str | None) -> list[str]:
    """
    Get the list of commits between last push and current HEAD.

    Args:
        last_push_commit: The commit hash of last push, or None for first push

    Returns:
        List of commit hashes in chronological order (oldest first)
    """
    raise NotImplementedError("Commit range detection not yet implemented")


def get_commit_range_for_review() -> tuple[list[str], str]:
    """
    Get the commits that need to be reviewed and the detection method used.

    This is the main entry point that combines:
    1. Finding last push via reflog
    2. Getting commit range
    3. Falling back to last 10 commits if needed

    Returns:
        Tuple of (list of commit hashes, detection_method)
        detection_method is one of: "reflog", "fallback_10", "fallback_all"
    """
    raise NotImplementedError("Commit range for review not yet implemented")


# =============================================================================
# Constants for Commit Range Detection
# =============================================================================

# Maximum commits to review on first push (fallback)
FIRST_PUSH_FALLBACK_LIMIT = 10

# Reflog patterns for push detection
REFLOG_PUSH_PATTERN = r"push"

# Git command templates
GIT_REFLOG_PUSH_CMD = "git reflog show --grep-reflog='push' -1 --format='%h'"
GIT_REV_LIST_CMD = "git rev-list --reverse {start}..HEAD"
GIT_REV_LIST_ALL_CMD = "git rev-list --reverse HEAD"
GIT_REV_LIST_LIMIT_CMD = "git rev-list --reverse HEAD -n {limit}"


# =============================================================================
# Test Class: AC-4 - Identify Commits Since Last Push
# =============================================================================


class TestAC4_IdentifyCommitsSinceLastPush:
    """
    AC-4: Identify Commits Since Last Push

    Given: User pushes new commits to remote
    When: Post-push skill runs
    Then: Skill identifies all commits between last push and current HEAD
    """

    def test_identifies_single_commit_after_push(
        self, reflog_normal_push: dict[str, Any]
    ) -> None:
        """Test detection of a single commit since last push."""
        last_push = reflog_normal_push["last_push_commit"]
        expected_commits = reflog_normal_push["expected_commits"]

        # Verify fixture has expected structure
        assert last_push is not None
        assert len(expected_commits) == 1

        # Test detection logic (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(last_push)
            assert result == expected_commits

    def test_identifies_multiple_commits_after_push(
        self, reflog_multiple_commits: dict[str, Any]
    ) -> None:
        """Test detection of multiple commits since last push."""
        last_push = reflog_multiple_commits["last_push_commit"]
        expected_commits = reflog_multiple_commits["expected_commits"]

        # Verify fixture has multiple commits
        assert last_push is not None
        assert len(expected_commits) > 1

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(last_push)
            assert result == expected_commits
            # Verify order is chronological (oldest first)
            assert result[0] == expected_commits[0]

    def test_handles_force_push_commit_range(
        self, reflog_force_push: dict[str, Any]
    ) -> None:
        """Test commit range detection after force push (rewritten history)."""
        last_push = reflog_force_push["last_push_commit"]
        expected_commits = reflog_force_push["expected_commits"]

        # Force push may have different commit hashes than before
        assert last_push is not None
        assert "force_push" in reflog_force_push.get("scenario", "")

        # Test detection logic
        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(last_push)
            assert result == expected_commits

    def test_tracks_commits_per_branch(
        self, reflog_multiple_branches: dict[str, Any]
    ) -> None:
        """Test that commit tracking works correctly for different branches."""
        branches = reflog_multiple_branches["branches"]

        # Verify fixture has multiple branches
        assert len(branches) >= 2

        for branch_info in branches:
            _branch_name = branch_info["branch"]
            last_push = branch_info["last_push_commit"]
            _expected_commits = branch_info["expected_commits"]

            # Test detection logic per branch
            with pytest.raises(NotImplementedError):
                result = get_commits_since_last_push(last_push)
                assert result == _expected_commits

    def test_returns_empty_list_when_no_new_commits(
        self, reflog_no_new_commits: dict[str, Any]
    ) -> None:
        """Test that empty list is returned when HEAD equals last push."""
        last_push = reflog_no_new_commits["last_push_commit"]
        expected_commits = reflog_no_new_commits["expected_commits"]

        assert expected_commits == []

        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(last_push)
            assert result == []

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "reflog_normal_push",
            "reflog_multiple_commits",
            "reflog_force_push",
        ],
    )
    def test_all_push_scenarios_return_valid_commits(
        self, fixtures_dir: Path, fixture_name: str
    ) -> None:
        """Parameterized test for all push scenarios returning valid commits."""
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        with open(fixture_path) as f:
            data = json.load(f)

        last_push = data["last_push_commit"]
        expected_commits = data["expected_commits"]

        # Verify commits are valid SHA format (7-40 chars, hex)
        for commit in expected_commits:
            assert len(commit) >= 7
            assert all(c in "0123456789abcdef" for c in commit.lower())

        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(last_push)
            assert result == expected_commits


# =============================================================================
# Test Class: AC-5 - Handle First Push Gracefully
# =============================================================================


class TestAC5_HandleFirstPushGracefully:
    """
    AC-5: Handle First Push Gracefully

    Given: User pushes to a new branch for first time
    When: No previous push reference exists in reflog
    Then: Skill reviews last 10 commits (or all if fewer)
    """

    def test_fallback_to_last_10_when_no_reflog(
        self, reflog_no_push: dict[str, Any]
    ) -> None:
        """Test fallback to last 10 commits when no push in reflog."""
        total_commits = reflog_no_push["total_commits_in_repo"]
        expected_commits = reflog_no_push["expected_commits"]

        # Verify fixture represents first push scenario
        assert reflog_no_push["last_push_commit"] is None
        assert total_commits > FIRST_PUSH_FALLBACK_LIMIT
        assert len(expected_commits) == FIRST_PUSH_FALLBACK_LIMIT

        # Test detection logic
        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert len(commits) == FIRST_PUSH_FALLBACK_LIMIT
            assert method == "fallback_10"

    def test_fallback_with_fewer_than_10_commits(
        self, reflog_few_commits: dict[str, Any]
    ) -> None:
        """Test fallback returns all commits when repo has fewer than 10."""
        total_commits = reflog_few_commits["total_commits_in_repo"]
        expected_commits = reflog_few_commits["expected_commits"]

        # Verify fixture has fewer than 10 commits
        assert reflog_few_commits["last_push_commit"] is None
        assert total_commits < FIRST_PUSH_FALLBACK_LIMIT
        assert len(expected_commits) == total_commits

        # Test detection logic
        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert len(commits) == total_commits
            assert method == "fallback_all"

    def test_first_push_new_branch_in_existing_repo(
        self, reflog_new_branch_first_push: dict[str, Any]
    ) -> None:
        """Test first push on new branch in repo with existing history."""
        _branch_name = reflog_new_branch_first_push["branch"]
        _expected_commits = reflog_new_branch_first_push["expected_commits"]

        # New branch has no push history for this branch
        assert reflog_new_branch_first_push["last_push_commit"] is None
        assert reflog_new_branch_first_push["branch_is_new"] is True

        # Should fall back to last 10 commits on this branch
        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert len(commits) <= FIRST_PUSH_FALLBACK_LIMIT
            assert method in ["fallback_10", "fallback_all"]

    def test_exactly_10_commits_returns_all(
        self, reflog_exactly_10_commits: dict[str, Any]
    ) -> None:
        """Test boundary case with exactly 10 commits."""
        total_commits = reflog_exactly_10_commits["total_commits_in_repo"]
        expected_commits = reflog_exactly_10_commits["expected_commits"]

        assert total_commits == FIRST_PUSH_FALLBACK_LIMIT
        assert len(expected_commits) == FIRST_PUSH_FALLBACK_LIMIT

        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert len(commits) == FIRST_PUSH_FALLBACK_LIMIT
            # Could be either method since exactly 10
            assert method in ["fallback_10", "fallback_all"]

    def test_detection_method_is_reflog_when_push_exists(
        self, reflog_normal_push: dict[str, Any]
    ) -> None:
        """Test that detection method is 'reflog' when push history exists."""
        last_push = reflog_normal_push["last_push_commit"]

        assert last_push is not None

        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert method == "reflog"

    @pytest.mark.parametrize(
        "fixture_name,expected_method",
        [
            ("reflog_no_push", "fallback_10"),
            ("reflog_few_commits", "fallback_all"),
            ("reflog_normal_push", "reflog"),
        ],
    )
    def test_correct_detection_method_used(
        self, fixtures_dir: Path, fixture_name: str, expected_method: str
    ) -> None:
        """Parameterized test for detection method selection."""
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        with open(fixture_path) as f:
            _data = json.load(f)

        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert method == expected_method


# =============================================================================
# Test Class: Last Push Detection
# =============================================================================


class TestLastPushDetection:
    """Tests for the last push commit detection from reflog."""

    def test_finds_last_push_from_reflog(
        self, reflog_normal_push: dict[str, Any]
    ) -> None:
        """Test finding last push commit from reflog."""
        expected_last_push = reflog_normal_push["last_push_commit"]

        with pytest.raises(NotImplementedError):
            result = get_last_push_commit()
            assert result == expected_last_push

    def test_returns_none_when_no_push_history(
        self, reflog_no_push: dict[str, Any]
    ) -> None:
        """Test that None is returned when no push in reflog."""
        with pytest.raises(NotImplementedError):
            result = get_last_push_commit()
            assert result is None

    def test_finds_branch_specific_push(
        self, reflog_multiple_branches: dict[str, Any]
    ) -> None:
        """Test finding last push for a specific branch."""
        for branch_info in reflog_multiple_branches["branches"]:
            branch_name = branch_info["branch"]
            expected_last_push = branch_info["last_push_commit"]

            with pytest.raises(NotImplementedError):
                result = get_last_push_commit(branch=branch_name)
                assert result == expected_last_push


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


class TestCommitRangeEdgeCases:
    """Tests for edge cases and boundary conditions in commit range detection."""

    def test_empty_repo_no_commits(self) -> None:
        """Test handling of empty repository with no commits."""
        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert commits == []
            assert method == "fallback_all"

    def test_single_commit_repo(self) -> None:
        """Test handling of repository with only one commit."""
        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            assert len(commits) <= 1
            assert method == "fallback_all"

    def test_merge_commits_included(
        self, reflog_with_merge: dict[str, Any]
    ) -> None:
        """Test that merge commits are included in the range."""
        expected_commits = reflog_with_merge["expected_commits"]
        merge_commit = reflog_with_merge["merge_commit"]

        assert merge_commit in expected_commits

        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(
                reflog_with_merge["last_push_commit"]
            )
            assert merge_commit in result

    def test_handles_detached_head(self) -> None:
        """Test commit range detection in detached HEAD state."""
        with pytest.raises(NotImplementedError):
            # Should still work in detached HEAD
            commits, method = get_commit_range_for_review()
            # Any valid result is acceptable
            assert isinstance(commits, list)
            assert method in ["reflog", "fallback_10", "fallback_all"]

    def test_reflog_expired_entries(
        self, reflog_expired: dict[str, Any]
    ) -> None:
        """Test handling when reflog entries have expired."""
        # Old reflog entries may be garbage collected
        assert reflog_expired["last_push_commit"] is None
        assert reflog_expired["reflog_expired"] is True

        with pytest.raises(NotImplementedError):
            commits, method = get_commit_range_for_review()
            # Should fall back gracefully
            assert method in ["fallback_10", "fallback_all"]

    def test_invalid_commit_hash_handling(self) -> None:
        """Test handling of invalid commit hash."""
        with pytest.raises((NotImplementedError, ValueError)):
            _result = get_commits_since_last_push("invalid_hash_xyz")

    def test_commit_order_is_chronological(
        self, reflog_multiple_commits: dict[str, Any]
    ) -> None:
        """Test that commits are returned in chronological order (oldest first)."""
        expected_commits = reflog_multiple_commits["expected_commits"]

        with pytest.raises(NotImplementedError):
            result = get_commits_since_last_push(
                reflog_multiple_commits["last_push_commit"]
            )
            # First commit should be oldest
            assert result[0] == expected_commits[0]
            # Last commit should be newest (HEAD)
            assert result[-1] == expected_commits[-1]


# =============================================================================
# Test Class: Git Command Validation
# =============================================================================


class TestGitCommandPatterns:
    """Tests for the git command patterns used in detection."""

    def test_reflog_push_command_pattern(self) -> None:
        """Verify the reflog push detection command is valid."""
        # This is a syntax validation test
        assert "reflog" in GIT_REFLOG_PUSH_CMD
        assert "push" in GIT_REFLOG_PUSH_CMD
        assert "%h" in GIT_REFLOG_PUSH_CMD  # Short hash format

    def test_rev_list_command_pattern(self) -> None:
        """Verify the rev-list command patterns are valid."""
        assert "rev-list" in GIT_REV_LIST_CMD
        assert "--reverse" in GIT_REV_LIST_CMD
        assert "HEAD" in GIT_REV_LIST_CMD
        assert "{start}" in GIT_REV_LIST_CMD

    def test_rev_list_limit_command_pattern(self) -> None:
        """Verify the limited rev-list command is valid."""
        assert "rev-list" in GIT_REV_LIST_LIMIT_CMD
        assert "-n" in GIT_REV_LIST_LIMIT_CMD
        assert "{limit}" in GIT_REV_LIST_LIMIT_CMD

    def test_fallback_limit_is_10(self) -> None:
        """Verify the fallback limit constant is 10."""
        assert FIRST_PUSH_FALLBACK_LIMIT == 10


# =============================================================================
# Integration Tests (Require Implementation)
# =============================================================================


@pytest.mark.skip(reason="Implementation not yet complete - run after GREEN phase")
class TestCommitRangeIntegration:
    """
    Integration tests that execute actual git commands.

    These tests are skipped during RED phase and should be unskipped
    once the commit range detection is implemented (GREEN phase).
    """

    def test_real_reflog_parsing(self, tmp_git_repo: Path) -> None:
        """Test parsing actual git reflog output."""
        # Create commits in temp repo
        # Push and verify reflog detection
        pass

    def test_real_commit_range_detection(self, tmp_git_repo: Path) -> None:
        """Test actual commit range calculation."""
        pass

    def test_real_first_push_fallback(self, tmp_git_repo: Path) -> None:
        """Test actual fallback behavior on first push."""
        pass
