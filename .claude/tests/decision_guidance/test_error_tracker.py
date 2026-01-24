"""Tests for the decision-time guidance error tracker."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from decision_guidance.state_manager import ErrorTracker, EditHistory, ErrorEvent, EditEvent
from decision_guidance.classifier import SignalClassifier
from decision_guidance.guidance_bank import GuidanceBank


class TestErrorTracker:
    """Test the error tracking functionality."""

    def test_record_error(self, tmp_path):
        """Test recording an error event."""
        tracker = ErrorTracker(state_dir=tmp_path)
        tracker.record_error(
            tool_name="Bash",
            error_type="general",
            message="Command failed",
        )

        errors = tracker.get_recent_errors()
        assert len(errors) == 1
        assert errors[0].tool_name == "Bash"
        assert errors[0].error_type == "general"

    def test_threshold_not_reached(self, tmp_path):
        """Test that threshold is not reached with few errors."""
        tracker = ErrorTracker(state_dir=tmp_path, threshold=4)

        for i in range(3):
            tracker.record_error("Bash", "general", f"Error {i}")

        assert not tracker.is_threshold_reached()

    def test_threshold_reached(self, tmp_path):
        """Test that threshold is reached with enough errors."""
        tracker = ErrorTracker(state_dir=tmp_path, threshold=4)

        for i in range(4):
            tracker.record_error("Bash", "general", f"Error {i}")

        assert tracker.is_threshold_reached()

    def test_window_pruning(self, tmp_path):
        """Test that old errors are pruned from the window."""
        tracker = ErrorTracker(state_dir=tmp_path, window_seconds=1, threshold=2)

        tracker.record_error("Bash", "general", "Old error")
        time.sleep(1.5)  # Wait for window to expire
        tracker.record_error("Bash", "general", "New error")

        errors = tracker.get_recent_errors()
        assert len(errors) == 1
        assert errors[0].message == "New error"

    def test_error_summary(self, tmp_path):
        """Test error summary generation."""
        tracker = ErrorTracker(state_dir=tmp_path)

        tracker.record_error("Bash", "not_found", "File not found")
        tracker.record_error("Bash", "permission", "Permission denied")
        tracker.record_error("Edit", "not_found", "Path does not exist")

        summary = tracker.get_error_summary()
        assert summary["count"] == 3
        assert "Bash" in summary["tools"]
        assert summary["tools"]["Bash"] == 2

    def test_persistence(self, tmp_path):
        """Test that errors persist across tracker instances."""
        tracker1 = ErrorTracker(state_dir=tmp_path)
        tracker1.record_error("Bash", "general", "Error 1")

        tracker2 = ErrorTracker(state_dir=tmp_path)
        errors = tracker2.get_recent_errors()
        assert len(errors) == 1


class TestEditHistory:
    """Test the edit history tracking functionality."""

    def test_record_edit(self, tmp_path):
        """Test recording a file edit."""
        history = EditHistory(state_dir=tmp_path)
        history.record_edit("/path/to/file.py", "Edit", success=True)

        # No doom loop with single edit
        assert history.detect_doom_loop() is None

    def test_doom_loop_detection(self, tmp_path):
        """Test doom loop detection with repeated edits."""
        history = EditHistory(state_dir=tmp_path, repeat_threshold=3)

        for i in range(4):
            history.record_edit("/path/to/file.py", "Edit", success=False)

        doom_loop = history.detect_doom_loop()
        assert doom_loop is not None
        assert "/path/to/file.py" in doom_loop["files"]
        assert doom_loop["files"]["/path/to/file.py"] >= 3

    def test_no_doom_loop_with_different_files(self, tmp_path):
        """Test that different files don't trigger doom loop."""
        history = EditHistory(state_dir=tmp_path, repeat_threshold=3)

        history.record_edit("/path/to/file1.py", "Edit", success=False)
        history.record_edit("/path/to/file2.py", "Edit", success=False)
        history.record_edit("/path/to/file3.py", "Edit", success=False)

        assert history.detect_doom_loop() is None


class TestSignalClassifier:
    """Test the signal classifier."""

    def test_error_detection_in_output(self, tmp_path):
        """Test that errors are detected in tool output."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            classifier = SignalClassifier(state_dir=tmp_path)

            hook_input = {
                "tool_name": "Bash",
                "tool_input": {"command": "ls /nonexistent"},
                "tool_result": {
                    "output": "ls: cannot access '/nonexistent': No such file or directory",
                    "exit_code": 2,
                },
            }

            candidates = classifier.classify_tool_result(hook_input)

            # Should detect the error and potentially not_found
            assert any(c[0] in ("error_recovery", "not_found_reminder") for c in candidates)

    def test_orchestrator_delegation_check(self, tmp_path):
        """Test that orchestrator edit detection works."""
        with patch.dict(os.environ, {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_SESSION_ID": "orch-test-123"
        }):
            classifier = SignalClassifier(state_dir=tmp_path)

            hook_input = {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/path/to/file.py"},
                "tool_result": {"output": "File edited successfully"},
            }

            candidates = classifier.classify_tool_result(hook_input)

            # Should include delegation reminder for orchestrator
            assert any(c[0] == "delegation_reminder" for c in candidates)

    def test_non_orchestrator_no_delegation_check(self, tmp_path):
        """Test that non-orchestrator sessions don't get delegation check."""
        with patch.dict(os.environ, {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "CLAUDE_SESSION_ID": "worker-test-123"
        }):
            classifier = SignalClassifier(state_dir=tmp_path)

            hook_input = {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/path/to/file.py"},
                "tool_result": {"output": "File edited successfully"},
            }

            candidates = classifier.classify_tool_result(hook_input)

            # Should NOT include delegation reminder for non-orchestrator
            assert not any(c[0] == "delegation_reminder" for c in candidates)


class TestGuidanceBank:
    """Test the guidance bank."""

    def test_get_guidance(self):
        """Test retrieving guidance by key."""
        guidance = GuidanceBank.get_guidance(
            "error_recovery",
            error_count=5,
            window_minutes=5,
            error_messages="- Error 1\n- Error 2",
        )

        assert guidance is not None
        assert "5 errors" in guidance
        assert "Error 1" in guidance

    def test_guidance_priority(self):
        """Test guidance priority ordering."""
        assert GuidanceBank.get_priority("error_recovery") < GuidanceBank.get_priority("doom_loop")

    def test_select_guidance_respects_max(self):
        """Test that select_guidance respects max count."""
        candidates = [
            ("error_recovery", {"error_count": 5, "window_minutes": 5, "error_messages": ""}),
            ("doom_loop", {"file_details": ""}),
            ("not_found_reminder", {}),
        ]

        selected = GuidanceBank.select_guidance(candidates, max_count=2)
        assert len(selected) <= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
