"""Integration tests for unified stop gate hook."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from unified_stop_gate.checkers import SessionInfo
from unified_stop_gate.config import EnvironmentConfig, PathResolver, Priority
from unified_stop_gate.evaluator import EvaluationResult, PriorityEvaluator
from unified_stop_gate.formatter import DecisionFormatter


class TestP0CircuitBreaker:
    """Test P0: Circuit breaker forces ALLOW."""

    def test_circuit_breaker_triggers_at_max(self):
        """When iterations >= max_iterations, circuit breaker forces ALLOW."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=25, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        assert result.decision == "ALLOW"
        assert result.priority_breaker == Priority.P0_CIRCUIT_BREAKER

    def test_circuit_breaker_triggers_over_max(self):
        """When iterations > max_iterations, circuit breaker forces ALLOW."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=10,
            enforce_promise=True,
            enforce_bo=True,
        )
        session = SessionInfo(session_id="test", current_iteration=15, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        assert result.decision == "ALLOW"
        # Only P0 should be in results when circuit breaker triggers
        assert len(result.results) == 1

    def test_circuit_breaker_not_triggered_under_max(self):
        """When iterations < max_iterations, circuit breaker does not trigger."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        assert result.decision != "ALLOW" or result.priority_breaker != Priority.P0_CIRCUIT_BREAKER


class TestP1CompletionPromise:
    """Test P1: Completion promise checking."""

    def test_promise_blocks_when_not_verified(self):
        """When promise exists but not verified, BLOCK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=tmpdir,
                session_dir=None,
                max_iterations=25,
                enforce_promise=True,
                enforce_bo=False,
            )
            session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

            # Create promise without verification
            paths = PathResolver(config)
            paths.ensure_dirs_exist()
            paths.promise_file.write_text("Complete the feature")

            evaluator = PriorityEvaluator(config, session)
            result = evaluator.evaluate()

            assert result.decision == "BLOCK"
            assert result.priority_breaker == Priority.P1_COMPLETION_PROMISE

    def test_promise_passes_when_verified(self):
        """When promise is verified, PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=tmpdir,
                session_dir=None,
                max_iterations=25,
                enforce_promise=True,
                enforce_bo=False,
            )
            session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

            # Create promise with verification
            paths = PathResolver(config)
            paths.ensure_dirs_exist()
            paths.promise_file.write_text("Complete the feature")
            paths.verification_log.write_text("VERIFIED: Feature complete")

            evaluator = PriorityEvaluator(config, session)
            result = evaluator.evaluate()

            # Should not block on P1
            if result.decision == "BLOCK":
                assert result.priority_breaker != Priority.P1_COMPLETION_PROMISE

    def test_no_promise_passes(self):
        """When no promise file exists, P1 passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=tmpdir,
                session_dir=None,
                max_iterations=25,
                enforce_promise=True,
                enforce_bo=False,
            )
            session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

            evaluator = PriorityEvaluator(config, session)
            result = evaluator.evaluate()

            # Should not block on P1
            if result.decision == "BLOCK":
                assert result.priority_breaker != Priority.P1_COMPLETION_PROMISE


class TestP2BeadsSync:
    """Test P2: Beads sync checking."""

    def test_beads_clean_passes(self):
        """When .beads/ is clean, P2 passes."""
        # This test depends on actual git state
        # In a clean repo, P2 should pass
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # Find P2 result
        p2_results = [r for r in result.results if r.priority == Priority.P2_BEADS_SYNC]
        assert len(p2_results) == 1
        # Result structure is correct
        assert p2_results[0].blocking == True


class TestP3TodoContinuation:
    """Test P3: Todo continuation (placeholder)."""

    def test_todo_placeholder_passes(self):
        """Placeholder always passes."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # Find P3 result
        p3_results = [r for r in result.results if r.priority == Priority.P3_TODO_CONTINUATION]
        assert len(p3_results) == 1
        assert p3_results[0].passed == True


class TestP4GitStatus:
    """Test P4: Git status (advisory, non-blocking)."""

    def test_git_status_is_non_blocking(self):
        """P4 should never block, only warn."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # Find P4 result
        p4_results = [r for r in result.results if r.priority == Priority.P4_GIT_STATUS]
        assert len(p4_results) == 1
        assert p4_results[0].blocking == False

    def test_git_dirty_produces_warning(self):
        """When git is dirty, P4 produces a warning, not a block."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # P4 failure should be in warnings, not blocking_checks
        p4_in_blocking = any(c.priority == Priority.P4_GIT_STATUS for c in result.blocking_checks)
        assert not p4_in_blocking, "P4 should never be in blocking_checks"


class TestP5BusinessOutcomes:
    """Test P5: Business outcomes."""

    def test_business_outcomes_disabled(self):
        """When enforce_bo=False, P5 passes."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # Find P5 result
        p5_results = [r for r in result.results if r.priority == Priority.P5_BUSINESS_OUTCOMES]
        assert len(p5_results) == 1
        assert p5_results[0].passed == True

    def test_business_outcomes_enabled_placeholder(self):
        """When enforce_bo=True, placeholder passes."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=True,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # Find P5 result
        p5_results = [r for r in result.results if r.priority == Priority.P5_BUSINESS_OUTCOMES]
        assert len(p5_results) == 1
        # Placeholder passes even when enforced
        assert p5_results[0].passed == True


class TestCombinedScenarios:
    """Test combined scenarios."""

    def test_block_with_warnings(self):
        """BLOCK can include warnings from lower priority checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=tmpdir,
                session_dir=None,
                max_iterations=25,
                enforce_promise=True,
                enforce_bo=False,
            )
            session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

            # Create unverified promise (will block on P1)
            paths = PathResolver(config)
            paths.ensure_dirs_exist()
            paths.promise_file.write_text("Complete everything")

            evaluator = PriorityEvaluator(config, session)
            result = evaluator.evaluate()

            assert result.decision == "BLOCK"
            # Can have both blocking checks and warnings
            assert len(result.blocking_checks) >= 1

    def test_highest_priority_blocker_wins(self):
        """When multiple blockers, highest priority determines priority_breaker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=tmpdir,
                session_dir=None,
                max_iterations=25,
                enforce_promise=True,
                enforce_bo=True,
            )
            session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

            # Create unverified promise
            paths = PathResolver(config)
            paths.ensure_dirs_exist()
            paths.promise_file.write_text("Complete")

            evaluator = PriorityEvaluator(config, session)
            result = evaluator.evaluate()

            assert result.decision == "BLOCK"
            # P1 is higher priority than P5
            assert result.priority_breaker == Priority.P1_COMPLETION_PROMISE


class TestDecisionFormatter:
    """Test DecisionFormatter output format."""

    def test_block_format(self):
        """BLOCK produces correct JSON structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EnvironmentConfig(
                project_dir=tmpdir,
                session_dir=None,
                max_iterations=25,
                enforce_promise=True,
                enforce_bo=False,
            )
            session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

            paths = PathResolver(config)
            paths.ensure_dirs_exist()
            paths.promise_file.write_text("Complete")

            evaluator = PriorityEvaluator(config, session)
            result = evaluator.evaluate()

            output = DecisionFormatter.format(result)

            assert output["decision"] == "block"
            assert "reason" in output
            assert "blocking_checks" in output
            assert "warnings" in output
            assert isinstance(output["blocking_checks"], list)

    def test_approve_format(self):
        """PASS/WARN/ALLOW produces 'approve' decision."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        output = DecisionFormatter.format(result)

        assert output["decision"] == "approve"
        assert "reason" in output
        assert "warnings" in output

    def test_circuit_breaker_approve_format(self):
        """ALLOW (circuit breaker) produces 'approve' with specific reason."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=5,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=10, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        output = DecisionFormatter.format(result)

        assert output["decision"] == "approve"
        assert "circuit breaker" in output["reason"].lower()


class TestErrorHandling:
    """Test error handling."""

    def test_format_error_approves(self):
        """Errors should approve to avoid blocking."""
        output = DecisionFormatter.format_error(ValueError("Test error"))

        assert output["decision"] == "approve"
        assert "error" in output["reason"].lower()
        assert len(output["warnings"]) == 1

    def test_session_info_defaults(self):
        """SessionInfo handles missing fields gracefully."""
        session = SessionInfo.from_hook_input({})

        assert session.session_id == "unknown"
        assert session.current_iteration == 0
        assert session.transcript_path is None

    def test_session_info_string_iteration(self):
        """SessionInfo converts string iteration to int."""
        session = SessionInfo.from_hook_input({"iteration": "15"})

        assert session.current_iteration == 15


class TestJSONOutput:
    """Test JSON serialization."""

    def test_output_is_json_serializable(self):
        """All output should be JSON serializable."""
        config = EnvironmentConfig(
            project_dir=".",
            session_dir=None,
            max_iterations=25,
            enforce_promise=False,
            enforce_bo=False,
        )
        session = SessionInfo(session_id="test", current_iteration=5, transcript_path=None)

        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        output = DecisionFormatter.format(result)

        # Should not raise
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed == output
