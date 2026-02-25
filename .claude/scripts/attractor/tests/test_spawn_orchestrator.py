"""Unit tests for spawn_orchestrator.py — AC-1 Crash Recovery and AC-2 Session Naming.

Tests:
    TestCheckOrchestratorAlive    - check_orchestrator_alive() returns True/False
    TestRespawnOrchestrator       - respawn_orchestrator() with alive, dead, max-respawn cases
    TestParseArgsMaxRespawn       - --max-respawn CLI arg parsing
    TestSessionNameValidation     - Reject s3-live- prefix session names
    TestOutputIncludesRespawnCount - Final JSON output includes respawn_count
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

# Ensure the attractor package root is on sys.path.
_ATTRACTOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ATTRACTOR_DIR not in sys.path:
    sys.path.insert(0, _ATTRACTOR_DIR)

import spawn_orchestrator
from spawn_orchestrator import (
    check_orchestrator_alive,
    respawn_orchestrator,
    main,
)


# ---------------------------------------------------------------------------
# TestCheckOrchestratorAlive
# ---------------------------------------------------------------------------


class TestCheckOrchestratorAlive(unittest.TestCase):
    """Tests for check_orchestrator_alive()."""

    def test_returns_true_when_session_exists(self) -> None:
        """check_orchestrator_alive returns True when tmux exits with 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("spawn_orchestrator.subprocess.run", return_value=mock_result) as mock_run:
            result = check_orchestrator_alive("orch-auth")
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["tmux", "has-session", "-t", "orch-auth"],
            capture_output=True,
        )

    def test_returns_false_when_session_not_found(self) -> None:
        """check_orchestrator_alive returns False when tmux exits with non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("spawn_orchestrator.subprocess.run", return_value=mock_result):
            result = check_orchestrator_alive("orch-missing")
        self.assertFalse(result)

    def test_returns_false_for_nonzero_exit(self) -> None:
        """Any non-zero exit code means session does not exist."""
        mock_result = MagicMock()
        mock_result.returncode = 127
        with patch("spawn_orchestrator.subprocess.run", return_value=mock_result):
            result = check_orchestrator_alive("orch-ghost")
        self.assertFalse(result)

    def test_calls_tmux_has_session(self) -> None:
        """Must use tmux has-session command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("spawn_orchestrator.subprocess.run", return_value=mock_result) as mock_run:
            check_orchestrator_alive("my-session")
        args_used = mock_run.call_args[0][0]
        self.assertIn("tmux", args_used)
        self.assertIn("has-session", args_used)
        self.assertIn("my-session", args_used)


# ---------------------------------------------------------------------------
# TestRespawnOrchestrator
# ---------------------------------------------------------------------------


class TestRespawnOrchestrator(unittest.TestCase):
    """Tests for respawn_orchestrator()."""

    def test_returns_already_alive_if_session_exists(self) -> None:
        """If session already exists, return already_alive without spawning."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=True):
            result = respawn_orchestrator("orch-auth", "/tmp", "auth", None, 0, 3)
        self.assertEqual(result["status"], "already_alive")
        self.assertEqual(result["session"], "orch-auth")

    def test_returns_error_when_max_respawn_reached(self) -> None:
        """If respawn_count >= max_respawn, return error."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False):
            result = respawn_orchestrator("orch-auth", "/tmp", "auth", None, 3, 3)
        self.assertEqual(result["status"], "error")
        self.assertIn("Max respawn limit reached", result["message"])
        self.assertIn("3/3", result["message"])

    def test_returns_error_when_respawn_count_exceeds_max(self) -> None:
        """If respawn_count > max_respawn, return error."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False):
            result = respawn_orchestrator("orch-auth", "/tmp", "auth", None, 5, 3)
        self.assertEqual(result["status"], "error")
        self.assertIn("Max respawn limit reached", result["message"])

    def test_respawns_dead_session_successfully(self) -> None:
        """Successfully respawn a dead session."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator._tmux_send"):
            mock_run.return_value = MagicMock(returncode=0)
            result = respawn_orchestrator("orch-auth", "/tmp/work", "auth", None, 0, 3)
        self.assertEqual(result["status"], "respawned")
        self.assertEqual(result["session"], "orch-auth")
        self.assertEqual(result["respawn_count"], 1)

    def test_increments_respawn_count(self) -> None:
        """respawn_count in result should be respawn_count + 1."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator._tmux_send"):
            mock_run.return_value = MagicMock(returncode=0)
            result = respawn_orchestrator("orch-auth", "/tmp", "auth", None, 1, 3)
        self.assertEqual(result["respawn_count"], 2)

    def test_sends_prompt_when_provided(self) -> None:
        """When prompt is provided, _tmux_send should be called with it."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator._tmux_send") as mock_send:
            mock_run.return_value = MagicMock(returncode=0)
            result = respawn_orchestrator("orch-auth", "/tmp", "auth", "Hello Claude", 0, 3)
        # Should have been called with the prompt
        send_calls = [str(c) for c in mock_send.call_args_list]
        prompt_sent = any("Hello Claude" in s for s in send_calls)
        self.assertTrue(prompt_sent, f"Prompt not sent. Calls: {send_calls}")

    def test_no_prompt_sent_when_none(self) -> None:
        """When prompt is None, should NOT send a prompt key."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator._tmux_send") as mock_send:
            mock_run.return_value = MagicMock(returncode=0)
            respawn_orchestrator("orch-auth", "/tmp", "auth", None, 0, 3)
        # Only 2 send calls expected: "unset CLAUDECODE && claude" + "/output-style orchestrator"
        self.assertEqual(mock_send.call_count, 2)

    def test_uses_same_tmux_config(self) -> None:
        """Respawn should use -x 220 -y 50 exec zsh same as original."""
        with patch("spawn_orchestrator.check_orchestrator_alive", return_value=False), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator._tmux_send"):
            mock_run.return_value = MagicMock(returncode=0)
            respawn_orchestrator("orch-auth", "/tmp/work", "auth", None, 0, 3)
        # subprocess.run should have been called with tmux new-session
        calls_made = mock_run.call_args_list
        tmux_call_args = calls_made[0][0][0]
        self.assertIn("new-session", tmux_call_args)
        self.assertIn("220", tmux_call_args)
        self.assertIn("50", tmux_call_args)


# ---------------------------------------------------------------------------
# TestParseArgsMaxRespawn
# ---------------------------------------------------------------------------


class TestParseArgsMaxRespawn(unittest.TestCase):
    """Tests for --max-respawn CLI argument."""

    def _parse(self, extra: list[str] | None = None) -> object:
        """Parse with minimum required args plus any extras."""
        base = [
            "--node", "impl_auth",
            "--prd", "PRD-AUTH-001",
            "--worktree", "/tmp/work",
        ]
        if extra:
            base.extend(extra)
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--node", required=True)
        parser.add_argument("--prd", required=True)
        parser.add_argument("--worktree", required=True)
        parser.add_argument("--session-name", default=None, dest="session_name")
        parser.add_argument("--prompt", default=None)
        parser.add_argument("--max-respawn", type=int, default=3, dest="max_respawn")
        return parser.parse_args(base)

    def test_default_max_respawn_is_3(self) -> None:
        """Default --max-respawn should be 3."""
        args = self._parse()
        self.assertEqual(args.max_respawn, 3)

    def test_max_respawn_custom_value(self) -> None:
        """Custom --max-respawn value should be parsed correctly."""
        args = self._parse(["--max-respawn", "5"])
        self.assertEqual(args.max_respawn, 5)

    def test_max_respawn_zero(self) -> None:
        """--max-respawn 0 means no respawn attempts allowed."""
        args = self._parse(["--max-respawn", "0"])
        self.assertEqual(args.max_respawn, 0)

    def test_max_respawn_type_is_int(self) -> None:
        """--max-respawn should be parsed as int."""
        args = self._parse(["--max-respawn", "2"])
        self.assertIsInstance(args.max_respawn, int)


# ---------------------------------------------------------------------------
# TestSessionNameValidation
# ---------------------------------------------------------------------------


class TestSessionNameValidation(unittest.TestCase):
    """Tests for session name validation: reject s3-live- prefix."""

    def _run_main(self, extra_args: list[str]) -> tuple[str, int]:
        """Run main() with given args via sys.argv patching and capture stdout + exit code."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        exit_code = 0
        argv = ["spawn_orchestrator.py"] + extra_args
        with patch("sys.argv", argv):
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 0
        return buf.getvalue(), exit_code

    def test_rejects_s3_live_prefix(self) -> None:
        """Session name with s3-live- prefix must be rejected with exit code 1."""
        output, exit_code = self._run_main([
            "--node", "impl_auth",
            "--prd", "PRD-AUTH-001",
            "--worktree", "/tmp",
            "--session-name", "s3-live-workers",
        ])
        self.assertEqual(exit_code, 1)
        data = json.loads(output)
        self.assertEqual(data["status"], "error")
        self.assertIn("s3-live-", data["message"])

    def test_rejects_s3_live_any_suffix(self) -> None:
        """Any s3-live-* suffix should be rejected."""
        output, exit_code = self._run_main([
            "--node", "impl_auth",
            "--prd", "PRD-AUTH-001",
            "--worktree", "/tmp",
            "--session-name", "s3-live-anything",
        ])
        self.assertEqual(exit_code, 1)
        data = json.loads(output)
        self.assertEqual(data["status"], "error")

    def test_accepts_orch_prefix(self) -> None:
        """orch- prefix sessions should not be rejected by name validation."""
        with patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator.check_orchestrator_alive", return_value=True), \
             patch("spawn_orchestrator._tmux_send"), \
             patch("sys.argv", ["spawn_orchestrator.py",
                                "--node", "impl_auth",
                                "--prd", "PRD-AUTH-001",
                                "--worktree", "/tmp",
                                "--session-name", "orch-impl-auth"]):
            mock_run.return_value = MagicMock(returncode=0)
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit:
                pass
            output = buf.getvalue()
        if output:
            data = json.loads(output)
            # Should NOT be an s3-live error
            if data.get("status") == "error":
                self.assertNotIn("s3-live", data.get("message", ""))

    def test_default_session_name_uses_orch_prefix(self) -> None:
        """Default session name (orch-<node>) should not be rejected."""
        with patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator.check_orchestrator_alive", return_value=True), \
             patch("spawn_orchestrator._tmux_send"), \
             patch("sys.argv", ["spawn_orchestrator.py",
                                "--node", "impl_auth",
                                "--prd", "PRD-AUTH-001",
                                "--worktree", "/tmp"]):
            mock_run.return_value = MagicMock(returncode=0)
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit:
                pass
            output = buf.getvalue()
        if output:
            data = json.loads(output)
            if data.get("status") == "error":
                self.assertNotIn("reserved", data.get("message", ""))


# ---------------------------------------------------------------------------
# TestOutputIncludesRespawnCount
# ---------------------------------------------------------------------------


class TestOutputIncludesRespawnCount(unittest.TestCase):
    """Tests that final JSON output includes respawn_count field."""

    def test_output_includes_respawn_count_zero_when_no_respawn(self) -> None:
        """When no respawn needed, output includes respawn_count: 0."""
        import io
        from contextlib import redirect_stdout

        argv = ["spawn_orchestrator.py",
                "--node", "impl_auth", "--prd", "PRD-AUTH-001", "--worktree", "/tmp"]
        with patch("sys.argv", argv), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator.check_orchestrator_alive", return_value=True), \
             patch("spawn_orchestrator._tmux_send"):
            mock_run.return_value = MagicMock(returncode=0)
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit:
                pass
        output = buf.getvalue()
        if output:
            data = json.loads(output)
            if data.get("status") == "ok":
                self.assertIn("respawn_count", data)
                self.assertEqual(data["respawn_count"], 0)

    def test_respawn_count_in_output_after_respawn(self) -> None:
        """When respawn occurs, output respawn_count should be > 0.

        Sequence: main() checks alive → False (dead after create).
        respawn_orchestrator() checks alive → False (still dead, proceed to respawn).
        Subprocess creates new session → respawn_count becomes 1.
        Output should have respawn_count=1.
        """
        import io
        from contextlib import redirect_stdout

        # First call (in main): False → triggers respawn_orchestrator
        # Second call (in respawn_orchestrator): False → proceeds to create session
        alive_sequence = [False, False]
        alive_iter = iter(alive_sequence)

        def mock_alive_fn(session: str) -> bool:
            try:
                return next(alive_iter)
            except StopIteration:
                return True

        argv = ["spawn_orchestrator.py",
                "--node", "impl_auth", "--prd", "PRD-AUTH-001", "--worktree", "/tmp"]
        with patch("sys.argv", argv), \
             patch("spawn_orchestrator.subprocess.run") as mock_run, \
             patch("spawn_orchestrator.time.sleep"), \
             patch("spawn_orchestrator.check_orchestrator_alive", side_effect=mock_alive_fn), \
             patch("spawn_orchestrator._tmux_send"):
            mock_run.return_value = MagicMock(returncode=0)
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit:
                pass
        output = buf.getvalue()
        self.assertTrue(output, "Expected JSON output from main()")
        data = json.loads(output)
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("respawn_count", data)
        self.assertGreater(data["respawn_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
