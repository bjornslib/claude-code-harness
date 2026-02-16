"""Tests for the Work Exhaustion Checker.

Tests the three-layer work-state gathering and System 3 vs non-System 3
task enforcement logic.

Key behavioral difference:
- System 3 sessions (session_id starts with "system3-"):
  pending/in_progress tasks → BLOCK (contradiction: stop hook fired but tasks remain)
  no pending tasks → PASS (all work completed or deleted)

- Non-System 3 sessions:
  pending/in_progress tasks → PASS (continuation signal)
  no pending tasks → BLOCK (no continuation intent)
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


# --- Fixtures ---


@pytest.fixture
def system3_config():
    """Config for System 3 sessions (is_system3 = True)."""
    return EnvironmentConfig(
        project_dir=str(Path(__file__).resolve().parents[3]),
        session_dir=None,
        session_id="system3-test",
        max_iterations=25,
        enforce_promise=False,
        enforce_bo=False,
    )


@pytest.fixture
def non_system3_config():
    """Config for non-System 3 sessions (orchestrator, worker, etc.)."""
    return EnvironmentConfig(
        project_dir=str(Path(__file__).resolve().parents[3]),
        session_dir=None,
        session_id="orch-epic4",
        max_iterations=25,
        enforce_promise=False,
        enforce_bo=False,
    )


def _create_task_dir(tmpdir, task_list_id, tasks=None):
    """Helper: create task directory with optional task files."""
    tasks_dir = Path(tmpdir) / ".claude" / "tasks" / task_list_id
    tasks_dir.mkdir(parents=True)
    if tasks:
        for task in tasks:
            task_id = task["id"]
            with open(tasks_dir / f"{task_id}.json", "w") as f:
                json.dump(task, f)
    return tasks_dir


# --- WorkState Tests ---


class TestWorkState:
    """Test the WorkState data class."""

    def test_empty_state_has_no_work(self):
        state = WorkState()
        assert state.has_available_work is False
        assert state.pending_task_count == 0
        assert state.completed_task_count == 0

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
        assert len(lines) == 3  # promises, beads, tasks (no completed)
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

    def test_summary_lines_with_completed_tasks(self):
        """Completed tasks should appear in summary lines."""
        state = WorkState(
            completed_task_count=3,
            completed_task_subjects=["Task A", "Task B", "Task C"],
        )
        lines = state.format_summary_lines()
        assert any("3 tasks done" in l for l in lines)
        assert any("Task A" in l for l in lines)

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
        assert "UNFINISHED" in judge_text

    def test_format_for_judge_includes_completed_tasks(self):
        """Judge format should include both pending and completed task details."""
        state = WorkState(
            pending_task_count=1,
            task_subjects=["Pending task"],
            completed_task_count=2,
            completed_task_subjects=["Done task A", "Done task B"],
        )
        judge_text = state.format_for_judge()
        assert "[pending]" in judge_text
        assert "Pending task" in judge_text
        assert "[done]" in judge_text
        assert "Done task A" in judge_text
        assert "Done task B" in judge_text

    def test_format_for_judge_only_completed(self):
        """Judge format when only completed tasks exist (no pending)."""
        state = WorkState(
            completed_task_count=2,
            completed_task_subjects=["Done A", "Done B"],
        )
        judge_text = state.format_for_judge()
        assert "Unfinished tasks: NO" in judge_text
        assert "COMPLETED task subjects" in judge_text
        assert "Done A" in judge_text


# --- System 3 Session Tests ---


class TestSystem3Sessions:
    """Tests for System 3 session behavior: pending tasks BLOCK."""

    @pytest.fixture
    def config(self, system3_config):
        return system3_config

    def test_skip_when_no_task_list(self, config):
        """Should skip (pass) when no CLAUDE_CODE_TASK_LIST_ID is set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(config)
            result = checker.check()
            assert result.passed is True
            assert "skipped" in result.message

    def test_passes_when_no_tasks(self, config):
        """System 3: no tasks means all work completed → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-empty")

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-empty"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True
                    assert "all tasks completed" in result.message

    def test_blocks_when_pending_task_exists(self, config):
        """System 3: pending task when stop hook fires = contradiction → BLOCK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-pending", tasks=[
                {"id": "1", "subject": "Implement feature", "status": "pending"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-pending"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    assert "UNFINISHED TASKS" in result.message
                    assert "Implement feature" in result.message

    def test_blocks_when_in_progress_task_exists(self, config):
        """System 3: in_progress task when stop hook fires = contradiction → BLOCK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-inprogress", tasks=[
                {"id": "1", "subject": "Working on it", "status": "in_progress"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-inprogress"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    assert "UNFINISHED TASKS" in result.message

    def test_completed_tasks_dont_block(self, config):
        """System 3: only completed tasks → PASS (no unfinished work)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-completed", tasks=[
                {"id": "1", "subject": "Done task", "status": "completed"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-completed"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True

    def test_deleted_tasks_ignored(self, config):
        """System 3: deleted tasks don't count as unfinished → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-deleted", tasks=[
                {"id": "1", "subject": "Deleted task", "status": "deleted"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-deleted"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True

    def test_mixed_tasks_blocks_on_pending(self, config):
        """System 3: mix of completed and pending → BLOCK (pending exists)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-mixed", tasks=[
                {"id": "1", "subject": "Done task", "status": "completed"},
                {"id": "2", "subject": "Still pending", "status": "pending"},
                {"id": "3", "subject": "Also done", "status": "completed"},
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-mixed"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    assert "Still pending" in result.message

    def test_block_message_includes_guidance(self, config):
        """System 3 block message should include actionable guidance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-guidance", tasks=[
                {"id": "1", "subject": "Do something", "status": "pending"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-guidance"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    # Should include guidance about executing or deleting
                    assert "EXECUTE" in result.message or "DELETE" in result.message
                    assert "AskUserQuestion" in result.message

    def test_fail_open_on_gathering_error(self, config):
        """System 3: gathering error → fail open → PASS (empty work state)."""
        with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-error"}):
            checker = WorkExhaustionChecker(config)
            with patch.object(checker, "_gather_work_state", side_effect=RuntimeError("test error")):
                result = checker.check()
                # Fail open: empty WorkState → no unfinished tasks → PASS for system3
                assert result.passed is True


# --- Non-System 3 Session Tests ---


class TestNonSystem3Sessions:
    """Tests for non-System 3 sessions: original behavior preserved."""

    @pytest.fixture
    def config(self, non_system3_config):
        return non_system3_config

    def test_passes_when_pending_task_exists(self, config):
        """Non-System 3: pending task = continuation signal → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-pending", tasks=[
                {"id": "1", "subject": "Continue work", "status": "pending"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-pending"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True

    def test_blocks_when_no_tasks(self, config):
        """Non-System 3: no pending tasks = no continuation intent → BLOCK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-empty")

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-empty"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    assert "NO CONTINUATION TASK" in result.message

    def test_blocks_when_only_completed_tasks(self, config):
        """Non-System 3: only completed tasks = no continuation → BLOCK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-completed", tasks=[
                {"id": "1", "subject": "Done task", "status": "completed"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-completed"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False

    def test_in_progress_task_counts_as_continuation(self, config):
        """Non-System 3: in_progress task = continuation signal → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-inprog", tasks=[
                {"id": "1", "subject": "Working on it", "status": "in_progress"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-inprog"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is True

    def test_block_message_work_available(self, config):
        """Non-System 3: block message when work exists but no tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-nowork")

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-nowork"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    result = checker.check()
                    assert result.passed is False
                    assert "NO CONTINUATION TASK" in result.message

    def test_fail_open_on_gathering_error(self, config):
        """Non-System 3: gathering error → fail open → empty state → BLOCK."""
        with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-error"}):
            checker = WorkExhaustionChecker(config)
            with patch.object(checker, "_gather_work_state", side_effect=RuntimeError("test error")):
                result = checker.check()
                # Fail open: empty WorkState → no unfinished tasks → BLOCK for non-system3
                assert result.passed is False


# --- Work State Summary Tests ---


class TestWorkStateSummary:
    """Test the work_state_summary property for Step 5 judge integration."""

    @pytest.fixture
    def config(self, system3_config):
        return system3_config

    def test_empty_before_check(self, config):
        """work_state_summary should be empty before check() is called."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(config)
            assert checker.work_state_summary == ""

    def test_empty_when_skipped(self, config):
        """work_state_summary should be empty when check is skipped."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(config)
            checker.check()
            assert checker.work_state_summary == ""

    def test_populated_with_pending_tasks(self, config):
        """work_state_summary should contain task details after check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-summary", tasks=[
                {"id": "1", "subject": "Test task", "status": "pending"}
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-summary"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    checker.check()
                    summary = checker.work_state_summary
                    assert "WORK STATE" in summary
                    assert "Test task" in summary
                    assert "[pending]" in summary

    def test_includes_completed_tasks(self, config):
        """work_state_summary should include completed tasks for judge context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-both", tasks=[
                {"id": "1", "subject": "Done task", "status": "completed"},
                {"id": "2", "subject": "Pending task", "status": "pending"},
            ])

            with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "test-both"}):
                with patch.object(Path, "home", return_value=Path(tmpdir)):
                    checker = WorkExhaustionChecker(config)
                    checker.check()
                    summary = checker.work_state_summary
                    assert "Done task" in summary
                    assert "Pending task" in summary
                    assert "[done]" in summary
                    assert "[pending]" in summary


# --- Priority Tests ---


class TestPriority:
    """Test priority assignment."""

    def test_priority_is_p3_todo_continuation(self, system3_config):
        """Check should use P3_TODO_CONTINUATION priority."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            checker = WorkExhaustionChecker(system3_config)
            result = checker.check()
            assert result.priority == Priority.P3_TODO_CONTINUATION


# --- Message Content Tests ---


class TestMessageContent:
    """Test the content of blocking/passing messages for quality."""

    def test_system3_unfinished_block_message(self):
        """System 3 block message should guide toward execute or delete."""
        state = WorkState(
            pending_task_count=2,
            task_subjects=["Task A", "Task B"],
            ready_bead_count=3,
        )
        config = EnvironmentConfig(
            project_dir=".", session_dir=None, session_id="system3-test",
            max_iterations=25, enforce_promise=False, enforce_bo=False,
        )
        checker = WorkExhaustionChecker(config)
        msg = checker._format_system3_unfinished_block(state)
        assert "UNFINISHED TASKS" in msg
        assert "Task A" in msg
        assert "Task B" in msg
        assert "EXECUTE" in msg or "execute" in msg.lower()
        assert "DELETE" in msg or "delete" in msg.lower()
        assert "AskUserQuestion" in msg

    def test_non_system3_block_work_available(self):
        """Non-System 3 block when work exists shows available work."""
        state = WorkState(
            ready_bead_count=5,
            high_priority_bead_count=2,
        )
        config = EnvironmentConfig(
            project_dir=".", session_dir=None, session_id="orch-test",
            max_iterations=25, enforce_promise=False, enforce_bo=False,
        )
        checker = WorkExhaustionChecker(config)
        msg = checker._format_non_system3_block(state)
        assert "NO CONTINUATION TASK" in msg
        assert "WORK IS AVAILABLE" in msg

    def test_non_system3_block_no_work(self):
        """Non-System 3 block when no work suggests completion."""
        state = WorkState()  # Empty — no work
        config = EnvironmentConfig(
            project_dir=".", session_dir=None, session_id="orch-test",
            max_iterations=25, enforce_promise=False, enforce_bo=False,
        )
        checker = WorkExhaustionChecker(config)
        msg = checker._format_non_system3_block(state)
        assert "NO CONTINUATION TASK" in msg
        assert "NO AVAILABLE WORK" in msg


# --- Task Gathering Tests ---


class TestTaskGathering:
    """Test the _gather_task_state method directly."""

    def test_gathers_pending_tasks(self):
        """Should count pending tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-gather", tasks=[
                {"id": "1", "subject": "Task 1", "status": "pending"},
                {"id": "2", "subject": "Task 2", "status": "pending"},
            ])

            config = EnvironmentConfig(
                project_dir=".", session_dir=None, session_id="test",
                max_iterations=25, enforce_promise=False, enforce_bo=False,
            )
            checker = WorkExhaustionChecker(config)
            state = WorkState()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                checker._gather_task_state(state, "test-gather")

            assert state.pending_task_count == 2
            assert "Task 1" in state.task_subjects
            assert "Task 2" in state.task_subjects

    def test_gathers_completed_tasks(self):
        """Should count and track completed tasks separately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-gather", tasks=[
                {"id": "1", "subject": "Done A", "status": "completed"},
                {"id": "2", "subject": "Done B", "status": "completed"},
            ])

            config = EnvironmentConfig(
                project_dir=".", session_dir=None, session_id="test",
                max_iterations=25, enforce_promise=False, enforce_bo=False,
            )
            checker = WorkExhaustionChecker(config)
            state = WorkState()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                checker._gather_task_state(state, "test-gather")

            assert state.completed_task_count == 2
            assert "Done A" in state.completed_task_subjects
            assert "Done B" in state.completed_task_subjects
            assert state.pending_task_count == 0

    def test_ignores_deleted_tasks(self):
        """Deleted tasks should not appear in any count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-gather", tasks=[
                {"id": "1", "subject": "Deleted", "status": "deleted"},
            ])

            config = EnvironmentConfig(
                project_dir=".", session_dir=None, session_id="test",
                max_iterations=25, enforce_promise=False, enforce_bo=False,
            )
            checker = WorkExhaustionChecker(config)
            state = WorkState()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                checker._gather_task_state(state, "test-gather")

            assert state.pending_task_count == 0
            assert state.completed_task_count == 0

    def test_mixed_statuses(self):
        """Should correctly categorize mixed task statuses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_task_dir(tmpdir, "test-gather", tasks=[
                {"id": "1", "subject": "Pending", "status": "pending"},
                {"id": "2", "subject": "In Progress", "status": "in_progress"},
                {"id": "3", "subject": "Completed", "status": "completed"},
                {"id": "4", "subject": "Deleted", "status": "deleted"},
            ])

            config = EnvironmentConfig(
                project_dir=".", session_dir=None, session_id="test",
                max_iterations=25, enforce_promise=False, enforce_bo=False,
            )
            checker = WorkExhaustionChecker(config)
            state = WorkState()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                checker._gather_task_state(state, "test-gather")

            assert state.pending_task_count == 2  # pending + in_progress
            assert state.completed_task_count == 1
            assert "Pending" in state.task_subjects
            assert "In Progress" in state.task_subjects
            assert "Completed" in state.completed_task_subjects

    def test_handles_missing_directory(self):
        """Should handle non-existent task directory gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=".", session_dir=None, session_id="test",
                max_iterations=25, enforce_promise=False, enforce_bo=False,
            )
            checker = WorkExhaustionChecker(config)
            state = WorkState()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                checker._gather_task_state(state, "nonexistent-list")

            assert state.pending_task_count == 0
            assert state.completed_task_count == 0

    def test_handles_malformed_json(self):
        """Should skip malformed task files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_dir = _create_task_dir(tmpdir, "test-gather", tasks=[
                {"id": "1", "subject": "Good task", "status": "pending"},
            ])
            # Write a malformed file
            with open(tasks_dir / "2.json", "w") as f:
                f.write("not valid json{{{")

            config = EnvironmentConfig(
                project_dir=".", session_dir=None, session_id="test",
                max_iterations=25, enforce_promise=False, enforce_bo=False,
            )
            checker = WorkExhaustionChecker(config)
            state = WorkState()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                checker._gather_task_state(state, "test-gather")

            # Should still pick up the valid task
            assert state.pending_task_count == 1
            assert "Good task" in state.task_subjects


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
