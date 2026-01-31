"""Tests for the Work Exhaustion Checker.

Tests the three-layer work-state gathering and continuation task checking.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks"))

from unified_stop_gate.work_exhaustion_checker import WorkExhaustionChecker, WorkState
from unified_stop_gate.config import EnvironmentConfig, Priority


# --- WorkState Tests ---


class TestWorkState:
    """Test the WorkState data class."""

    def test_empty_state_has_no_work(self):
        state = WorkState()
        assert state.has_available_work is False
        assert state.pending_task_count == 0

    def test_promises_count_as_work(self):
        state = WorkState(has_promises=True, unmet_promise_count=1, promise_summaries=["Fix auth"])
        assert state.has_available_work is True

    def test_verified_promises_dont_count_as_work(self):
        state = WorkState(has_promises=True, unmet_promise_count=0)
        assert state.has_available_work is False

    def test_ready_beads_count_as_work(self):
        state = WorkState(ready_bead_count=5)
        assert state.has_available_work is True

    def test_high_priority_beads_count_as_work(self):
        state = WorkState(high_priority_bead_count=2)
        assert state.has_available_work is True

    def test_business_epics_count_as_work(self):
        state = WorkState(open_business_epic_count=1)
        assert state.has_available_work is True

    def test_summary_lines_empty(self):
        state = WorkState()
        lines = state.format_summary_lines()
        assert len(lines) == 3  # promises, beads, tasks
        assert any("none active" in l for l in lines)
        assert any("no ready work" in l for l in lines)
        assert any("none pending" in l for l in lines)

    def test_summary_lines_with_work(self):
        state = WorkState(
            has_promises=True,
            unmet_promise_count=2,
            promise_summaries=["Promise A", "Promise B"],
            ready_bead_count=3,
            high_priority_bead_count=1,
            pending_task_count=1,
            task_subjects=["Implement feature X"],
        )
        lines = state.format_summary_lines()
        assert any("2 unmet" in l for l in lines)
        assert any("3 ready" in l for l in lines)
        assert any("1 pending" in l for l in lines)

    def test_format_for_judge_includes_all_sections(self):
        state = WorkState(
            ready_bead_count=2,
            pending_task_count=1,
            task_subjects=["Run tests"],
        )
        judge_text = state.format_for_judge()
        assert "WORK STATE" in judge_text
        assert "YES" in judge_text  # has_available_work
        assert "Run tests" in judge_text


# --- WorkExhaustionChecker Tests ---


class TestWorkExhaustionChecker:
    """Test the main checker logic."""

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return EnvironmentConfig(
            project_dir=str(Path(__file__).resolve().parents[3]),
            session_dir=None,
            session_id="system3-test",
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )

    def test_skip_when_no_task_list(self, config):
        """Should skip (pass) when no CLAUDE_CODE_TASK_LIST_ID is set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(config)
            result = checker.check()
            assert result.passed is True
            assert "skipped" in result.message

    def test_blocks_when_no_tasks(self, config):
        """Should block when task list exists but has no pending tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_list_id = "test-empty"
            tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
            tasks_dir.mkdir(parents=True)

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": task_list_id}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    assert "NO CONTINUATION TASK" in result.message

    def test_passes_when_task_exists(self, config):
        """Should pass when a pending task exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_list_id = "test-with-task"
            tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
            tasks_dir.mkdir(parents=True)

            # Create a pending task
            task_data = {"id": "1", "subject": "Implement feature", "status": "pending"}
            with open(tasks_dir / "1.json", "w") as f:
                json.dump(task_data, f)

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": task_list_id}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True
                    assert "continuation task exists" in result.message

    def test_completed_tasks_dont_count(self, config):
        """Completed tasks should not count as continuation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_list_id = "test-completed"
            tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
            tasks_dir.mkdir(parents=True)

            task_data = {"id": "1", "subject": "Done task", "status": "completed"}
            with open(tasks_dir / "1.json", "w") as f:
                json.dump(task_data, f)

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": task_list_id}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False  # No PENDING tasks

    def test_in_progress_tasks_count(self, config):
        """In-progress tasks should count as continuation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_list_id = "test-inprogress"
            tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
            tasks_dir.mkdir(parents=True)

            task_data = {"id": "1", "subject": "Working on it", "status": "in_progress"}
            with open(tasks_dir / "1.json", "w") as f:
                json.dump(task_data, f)

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": task_list_id}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True

    def test_work_state_summary_available_after_check(self, config):
        """work_state_summary should be populated after check()."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(config)
            # Before check
            assert checker.work_state_summary == ""
            # After check (skip case)
            checker.check()
            # Still empty for skip case (no work_state gathered)
            assert checker.work_state_summary == ""

    def test_work_state_summary_populated_when_checked(self, config):
        """work_state_summary should contain structured data after check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_list_id = "test-summary"
            tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
            tasks_dir.mkdir(parents=True)

            task_data = {"id": "1", "subject": "Test task", "status": "pending"}
            with open(tasks_dir / "1.json", "w") as f:
                json.dump(task_data, f)

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": task_list_id}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    checker.check()
                    summary = checker.work_state_summary
                    assert "WORK STATE" in summary
                    assert "Test task" in summary

    def test_block_message_includes_work_state_when_work_available(self, config):
        """Block message should show work state and three-layer guidance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_list_id = "test-guidance"
            tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
            tasks_dir.mkdir(parents=True)

            # Create promise to simulate available work
            promises_dir = Path(config.project_dir) / ".claude" / "completion-state" / "promises"

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": task_list_id}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    # Should block (no tasks) and include guidance
                    assert result.passed is False
                    assert "Three-layer self-assessment" in result.message or "NO CONTINUATION TASK" in result.message

    def test_priority_is_p3_todo_continuation(self, config):
        """Check should use P3_TODO_CONTINUATION priority."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(config)
            result = checker.check()
            assert result.priority == Priority.P3_TODO_CONTINUATION

    def test_fail_open_on_gathering_error(self, config):
        """Should fail open if work state gathering raises an exception."""
        with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-error"}):
            checker = WorkExhaustionChecker(config)
            # Mock _gather_work_state to raise
            with patch.object(checker, "_gather_work_state", side_effect=RuntimeError("test error")):
                result = checker.check()
                # Should still check for tasks (fail open on gather)
                # With no tasks found, it blocks
                assert result.passed is False


# --- Integration-like Tests ---


class TestBlockMessageContent:
    """Test the content of blocking messages for guidance quality."""

    def test_work_available_message_has_three_layers(self):
        state = WorkState(ready_bead_count=3, high_priority_bead_count=1)
        config = EnvironmentConfig(
            project_dir=".", session_dir=None, session_id="test",
            max_iterations=25, enforce_promise=False, enforce_bo=False,
        )
        checker = WorkExhaustionChecker(config)
        msg = checker._format_block_message(state)
        assert "SESSION PROMISES" in msg
        assert "HIGH-PRIORITY BEADS" in msg
        assert "SELF-ASSESSMENT" in msg
        assert "AskUserQuestion" in msg

    def test_no_work_message_suggests_options(self):
        state = WorkState()  # No work at all
        config = EnvironmentConfig(
            project_dir=".", session_dir=None, session_id="test",
            max_iterations=25, enforce_promise=False, enforce_bo=False,
        )
        checker = WorkExhaustionChecker(config)
        msg = checker._format_block_message(state)
        assert "NO AVAILABLE WORK" in msg
        assert "AskUserQuestion" in msg
        assert "PRESENT OPTIONS" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
