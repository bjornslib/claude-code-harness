"""Unit tests for runner_agent.py — Layer 2 Runner Agent.

Tests:
    TestParseArgs               - parse_args() with various CLI combinations
    TestBuildSystemPrompt       - build_system_prompt() content and format
    TestBuildInitialPrompt      - build_initial_prompt() content and format
    TestBuildOptions            - build_options() returns correct ClaudeCodeOptions
    TestDryRunMode              - --dry-run exits 0 and prints JSON config
    TestEnvConfig               - build_env_config() handles CLAUDECODE correctly
    TestResolveScriptsDir       - resolve_scripts_dir() returns valid path
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure the attractor package root is on sys.path (mirrors conftest.py).
_ATTRACTOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ATTRACTOR_DIR not in sys.path:
    sys.path.insert(0, _ATTRACTOR_DIR)

import runner_agent  # noqa: E402
from runner_agent import (  # noqa: E402
    build_env_config,
    build_initial_prompt,
    build_options,
    build_system_prompt,
    parse_args,
    resolve_scripts_dir,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_STUCK_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_NODE = "impl_auth"
_PRD = "PRD-AUTH-001"
_SESSION = "orch-auth-001"
_ACCEPTANCE = "All auth tests pass"
_SCRIPTS_DIR = "/path/to/scripts"
_CHECK = 30
_STUCK = 300


def _make_system_prompt(**overrides) -> str:
    kwargs = dict(
        node_id=_NODE,
        prd_ref=_PRD,
        session_name=_SESSION,
        acceptance=_ACCEPTANCE,
        scripts_dir=_SCRIPTS_DIR,
        check_interval=_CHECK,
        stuck_threshold=_STUCK,
    )
    kwargs.update(overrides)
    return build_system_prompt(**kwargs)


def _make_initial_prompt(**overrides) -> str:
    kwargs = dict(
        node_id=_NODE,
        prd_ref=_PRD,
        session_name=_SESSION,
        acceptance=_ACCEPTANCE,
        scripts_dir=_SCRIPTS_DIR,
        check_interval=_CHECK,
        stuck_threshold=_STUCK,
    )
    kwargs.update(overrides)
    return build_initial_prompt(**kwargs)


# ---------------------------------------------------------------------------
# TestParseArgs
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Tests for parse_args()."""

    def test_required_args_only(self) -> None:
        args = parse_args(["--node", "n1", "--prd", "PRD-X-001", "--session", "sess1",
                           "--target-dir", "/tmp"])
        self.assertEqual(args.node, "n1")
        self.assertEqual(args.prd, "PRD-X-001")
        self.assertEqual(args.session, "sess1")

    def test_defaults(self) -> None:
        args = parse_args(["--node", "n1", "--prd", "P", "--session", "s",
                           "--target-dir", "/tmp"])
        self.assertEqual(args.check_interval, DEFAULT_CHECK_INTERVAL)
        self.assertEqual(args.stuck_threshold, DEFAULT_STUCK_THRESHOLD)
        self.assertEqual(args.max_turns, DEFAULT_MAX_TURNS)
        self.assertEqual(args.model, DEFAULT_MODEL)
        self.assertIsNone(args.acceptance)
        self.assertEqual(args.target_dir, "/tmp")
        self.assertIsNone(args.bead_id)
        self.assertIsNone(args.dot_file)
        self.assertIsNone(args.solution_design)
        self.assertIsNone(args.signals_dir)
        self.assertFalse(args.dry_run)

    def test_full_args(self) -> None:
        args = parse_args([
            "--node", "impl_auth",
            "--prd", "PRD-AUTH-001",
            "--session", "orch-auth",
            "--dot-file", "/tmp/pipe.dot",
            "--solution-design", "/tmp/design.md",
            "--acceptance", "Tests pass",
            "--target-dir", "/tmp/project",
            "--bead-id", "BEAD-42",
            "--check-interval", "60",
            "--stuck-threshold", "600",
            "--max-turns", "200",
            "--model", "claude-opus-4-6",
            "--signals-dir", "/tmp/signals",
            "--dry-run",
        ])
        self.assertEqual(args.node, "impl_auth")
        self.assertEqual(args.prd, "PRD-AUTH-001")
        self.assertEqual(args.session, "orch-auth")
        self.assertEqual(args.dot_file, "/tmp/pipe.dot")
        self.assertEqual(args.solution_design, "/tmp/design.md")
        self.assertEqual(args.acceptance, "Tests pass")
        self.assertEqual(args.target_dir, "/tmp/project")
        self.assertEqual(args.bead_id, "BEAD-42")
        self.assertEqual(args.check_interval, 60)
        self.assertEqual(args.stuck_threshold, 600)
        self.assertEqual(args.max_turns, 200)
        self.assertEqual(args.model, "claude-opus-4-6")
        self.assertEqual(args.signals_dir, "/tmp/signals")
        self.assertTrue(args.dry_run)

    def test_missing_required_node_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--prd", "P", "--session", "s"])

    def test_missing_required_prd_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--node", "n", "--session", "s"])

    def test_missing_required_session_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--node", "n", "--prd", "P"])

    def test_check_interval_type(self) -> None:
        args = parse_args(["--node", "n", "--prd", "P", "--session", "s",
                           "--target-dir", "/tmp", "--check-interval", "45"])
        self.assertIsInstance(args.check_interval, int)
        self.assertEqual(args.check_interval, 45)

    def test_stuck_threshold_type(self) -> None:
        args = parse_args(["--node", "n", "--prd", "P", "--session", "s",
                           "--target-dir", "/tmp", "--stuck-threshold", "180"])
        self.assertIsInstance(args.stuck_threshold, int)
        self.assertEqual(args.stuck_threshold, 180)

    def test_max_turns_type(self) -> None:
        args = parse_args(["--node", "n", "--prd", "P", "--session", "s",
                           "--target-dir", "/tmp", "--max-turns", "50"])
        self.assertIsInstance(args.max_turns, int)
        self.assertEqual(args.max_turns, 50)

    def test_dry_run_default_false(self) -> None:
        args = parse_args(["--node", "n", "--prd", "P", "--session", "s",
                           "--target-dir", "/tmp"])
        self.assertFalse(args.dry_run)

    def test_dry_run_flag_true(self) -> None:
        args = parse_args(["--node", "n", "--prd", "P", "--session", "s",
                           "--target-dir", "/tmp", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_missing_required_target_dir_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--node", "n", "--prd", "P", "--session", "s"])


# ---------------------------------------------------------------------------
# TestBuildSystemPrompt
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt(unittest.TestCase):
    """Tests for build_system_prompt()."""

    def test_returns_string(self) -> None:
        result = _make_system_prompt()
        self.assertIsInstance(result, str)

    def test_contains_node_id(self) -> None:
        result = _make_system_prompt(node_id="impl_payments")
        self.assertIn("impl_payments", result)

    def test_contains_prd_ref(self) -> None:
        result = _make_system_prompt(prd_ref="PRD-PAY-007")
        self.assertIn("PRD-PAY-007", result)

    def test_contains_session_name(self) -> None:
        result = _make_system_prompt(session_name="orch-pay")
        self.assertIn("orch-pay", result)

    def test_contains_acceptance(self) -> None:
        result = _make_system_prompt(acceptance="Payments processed correctly")
        self.assertIn("Payments processed correctly", result)

    def test_contains_scripts_dir(self) -> None:
        result = _make_system_prompt(scripts_dir="/custom/scripts")
        self.assertIn("/custom/scripts", result)

    def test_contains_check_interval(self) -> None:
        result = _make_system_prompt(check_interval=45)
        self.assertIn("45", result)

    def test_contains_stuck_threshold(self) -> None:
        result = _make_system_prompt(stuck_threshold=600)
        self.assertIn("600", result)

    def test_contains_signal_types(self) -> None:
        result = _make_system_prompt()
        for signal_type in ["NEEDS_REVIEW", "NEEDS_INPUT", "VIOLATION",
                             "ORCHESTRATOR_STUCK", "ORCHESTRATOR_CRASHED", "NODE_COMPLETE"]:
            self.assertIn(signal_type, result, f"Missing signal type: {signal_type}")

    def test_contains_guardian_response_types(self) -> None:
        result = _make_system_prompt()
        for response in ["VALIDATION_PASSED", "VALIDATION_FAILED", "INPUT_RESPONSE",
                          "KILL_ORCHESTRATOR", "GUIDANCE"]:
            self.assertIn(response, result, f"Missing response type: {response}")

    def test_contains_tool_scripts(self) -> None:
        result = _make_system_prompt()
        for tool in ["capture_output.py", "check_orchestrator_alive.py",
                     "signal_guardian.py", "wait_for_guardian.py",
                     "send_to_orchestrator.py"]:
            self.assertIn(tool, result, f"Missing tool reference: {tool}")

    def test_contains_monitoring_loop_description(self) -> None:
        result = _make_system_prompt()
        self.assertIn("Monitoring Loop", result)

    def test_empty_acceptance_uses_fallback(self) -> None:
        result = _make_system_prompt(acceptance="")
        self.assertIn("See DOT file", result)

    def test_nonempty_acceptance_appears_directly(self) -> None:
        result = _make_system_prompt(acceptance="Custom acceptance text")
        self.assertIn("Custom acceptance text", result)

    def test_substantial_length(self) -> None:
        result = _make_system_prompt()
        self.assertGreater(len(result), 500)


# ---------------------------------------------------------------------------
# TestBuildInitialPrompt
# ---------------------------------------------------------------------------


class TestBuildInitialPrompt(unittest.TestCase):
    """Tests for build_initial_prompt()."""

    def test_returns_string(self) -> None:
        result = _make_initial_prompt()
        self.assertIsInstance(result, str)

    def test_contains_node_id(self) -> None:
        result = _make_initial_prompt(node_id="impl_billing")
        self.assertIn("impl_billing", result)

    def test_contains_prd_ref(self) -> None:
        result = _make_initial_prompt(prd_ref="PRD-BILL-003")
        self.assertIn("PRD-BILL-003", result)

    def test_contains_session_name(self) -> None:
        result = _make_initial_prompt(session_name="orch-billing")
        self.assertIn("orch-billing", result)

    def test_contains_acceptance(self) -> None:
        result = _make_initial_prompt(acceptance="Billing works end to end")
        self.assertIn("Billing works end to end", result)

    def test_contains_check_interval(self) -> None:
        result = _make_initial_prompt(check_interval=60)
        self.assertIn("60s", result)

    def test_contains_stuck_threshold(self) -> None:
        result = _make_initial_prompt(stuck_threshold=900)
        self.assertIn("900s", result)

    def test_contains_scripts_dir(self) -> None:
        result = _make_initial_prompt(scripts_dir="/my/scripts")
        self.assertIn("/my/scripts", result)

    def test_contains_start_instruction(self) -> None:
        result = _make_initial_prompt()
        # Should tell Claude to check if orchestrator is alive first
        self.assertIn("alive", result.lower())

    def test_empty_acceptance_fallback(self) -> None:
        result = _make_initial_prompt(acceptance="")
        self.assertIn("See DOT file", result)

    def test_nonempty_acceptance(self) -> None:
        result = _make_initial_prompt(acceptance="My custom acceptance")
        self.assertIn("My custom acceptance", result)

    def test_reasonable_length(self) -> None:
        result = _make_initial_prompt()
        self.assertGreater(len(result), 50)
        self.assertLess(len(result), 5000)


# ---------------------------------------------------------------------------
# TestBuildOptions
# ---------------------------------------------------------------------------


class TestBuildOptions(unittest.TestCase):
    """Tests for build_options()."""

    def _build(self, **overrides) -> object:
        kwargs = dict(
            system_prompt="Test system prompt",
            cwd="/tmp",
            model=DEFAULT_MODEL,
            max_turns=DEFAULT_MAX_TURNS,
        )
        kwargs.update(overrides)
        return build_options(**kwargs)

    def test_returns_claude_code_options(self) -> None:
        from claude_code_sdk import ClaudeCodeOptions
        opts = self._build()
        self.assertIsInstance(opts, ClaudeCodeOptions)

    def test_allowed_tools_bash_only(self) -> None:
        opts = self._build()
        self.assertEqual(opts.allowed_tools, ["Bash"])

    def test_system_prompt_set(self) -> None:
        opts = self._build(system_prompt="Custom system prompt here")
        self.assertEqual(opts.system_prompt, "Custom system prompt here")

    def test_cwd_set(self) -> None:
        opts = self._build(cwd="/project/root")
        self.assertEqual(str(opts.cwd), "/project/root")

    def test_model_set(self) -> None:
        opts = self._build(model="claude-opus-4-6")
        self.assertEqual(opts.model, "claude-opus-4-6")

    def test_max_turns_set(self) -> None:
        opts = self._build(max_turns=50)
        self.assertEqual(opts.max_turns, 50)

    def test_env_contains_claudecode_override(self) -> None:
        opts = self._build()
        # CLAUDECODE must be overridden (to empty string to suppress nesting)
        self.assertIn("CLAUDECODE", opts.env)
        self.assertEqual(opts.env["CLAUDECODE"], "")

    def test_default_model(self) -> None:
        opts = self._build(model=DEFAULT_MODEL)
        self.assertEqual(opts.model, DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# TestDryRunMode
# ---------------------------------------------------------------------------


class TestDryRunMode(unittest.TestCase):
    """Tests for --dry-run: should exit 0 and print JSON config."""

    def _run_dry(self, extra_args: list[str] | None = None) -> str:
        """Run main() in dry-run mode and capture stdout as a string."""
        import io
        from contextlib import redirect_stdout

        base_args = ["--node", "n1", "--prd", "PRD-X-001", "--session", "s1",
                     "--target-dir", "/tmp", "--dry-run"]
        if extra_args:
            base_args.extend(extra_args)

        buf = io.StringIO()
        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(buf):
                runner_agent.main(base_args)

        self.assertEqual(cm.exception.code, 0)
        return buf.getvalue()

    def test_dry_run_exits_zero(self) -> None:
        # _run_dry already asserts exit code 0
        self._run_dry()

    def test_dry_run_prints_json(self) -> None:
        output = self._run_dry()
        data = json.loads(output)  # must not raise
        self.assertIsInstance(data, dict)

    def test_dry_run_json_has_dry_run_true(self) -> None:
        data = json.loads(self._run_dry())
        self.assertTrue(data["dry_run"])

    def test_dry_run_json_has_node_id(self) -> None:
        data = json.loads(self._run_dry())
        self.assertEqual(data["node_id"], "n1")

    def test_dry_run_json_has_prd_ref(self) -> None:
        data = json.loads(self._run_dry())
        self.assertEqual(data["prd_ref"], "PRD-X-001")

    def test_dry_run_json_has_session_name(self) -> None:
        data = json.loads(self._run_dry())
        self.assertEqual(data["session_name"], "s1")

    def test_dry_run_json_has_model(self) -> None:
        data = json.loads(self._run_dry())
        self.assertIn("model", data)
        self.assertEqual(data["model"], DEFAULT_MODEL)

    def test_dry_run_json_has_scripts_dir(self) -> None:
        data = json.loads(self._run_dry())
        self.assertIn("scripts_dir", data)
        self.assertTrue(os.path.isabs(data["scripts_dir"]))

    def test_dry_run_json_has_prompt_lengths(self) -> None:
        data = json.loads(self._run_dry())
        self.assertIn("system_prompt_length", data)
        self.assertIn("initial_prompt_length", data)
        self.assertGreater(data["system_prompt_length"], 0)
        self.assertGreater(data["initial_prompt_length"], 0)

    def test_dry_run_accepts_all_optional_args(self) -> None:
        extra = [
            "--acceptance", "Tests pass",
            "--target-dir", "/tmp",
            "--bead-id", "BID-1",
            "--check-interval", "60",
            "--stuck-threshold", "600",
            "--max-turns", "50",
        ]
        data = json.loads(self._run_dry(extra))
        self.assertEqual(data["acceptance"], "Tests pass")
        self.assertEqual(data["target_dir"], "/tmp")
        self.assertEqual(data["bead_id"], "BID-1")
        self.assertEqual(data["check_interval"], 60)
        self.assertEqual(data["stuck_threshold"], 600)
        self.assertEqual(data["max_turns"], 50)

    def test_dry_run_does_not_call_query(self) -> None:
        """Dry-run must never invoke the SDK query()."""
        import io
        from contextlib import redirect_stdout

        with patch("runner_agent._run_agent") as mock_run:
            buf = io.StringIO()
            with self.assertRaises(SystemExit):
                with redirect_stdout(buf):
                    runner_agent.main(
                        ["--node", "n", "--prd", "P", "--session", "s", "--dry-run"]
                    )
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# TestEnvConfig
# ---------------------------------------------------------------------------


class TestEnvConfig(unittest.TestCase):
    """Tests for build_env_config()."""

    def test_returns_dict(self) -> None:
        result = build_env_config()
        self.assertIsInstance(result, dict)

    def test_claudecode_key_present(self) -> None:
        result = build_env_config()
        self.assertIn("CLAUDECODE", result)

    def test_claudecode_value_is_empty_string(self) -> None:
        """We suppress CLAUDECODE by overriding to empty string."""
        result = build_env_config()
        self.assertEqual(result["CLAUDECODE"], "")

    def test_does_not_contain_arbitrary_env(self) -> None:
        """build_env_config should only return intentional overrides."""
        result = build_env_config()
        # The function should not blindly copy the entire environment.
        # It should be a small override dict, not os.environ.
        self.assertNotIn("PATH", result)
        self.assertNotIn("HOME", result)


# ---------------------------------------------------------------------------
# TestResolveScriptsDir
# ---------------------------------------------------------------------------


class TestResolveScriptsDir(unittest.TestCase):
    """Tests for resolve_scripts_dir()."""

    def test_returns_string(self) -> None:
        result = resolve_scripts_dir()
        self.assertIsInstance(result, str)

    def test_returns_absolute_path(self) -> None:
        result = resolve_scripts_dir()
        self.assertTrue(os.path.isabs(result), f"Expected absolute path, got: {result}")

    def test_path_exists(self) -> None:
        result = resolve_scripts_dir()
        self.assertTrue(os.path.isdir(result), f"Scripts dir does not exist: {result}")

    def test_contains_signal_guardian(self) -> None:
        result = resolve_scripts_dir()
        expected = os.path.join(result, "signal_guardian.py")
        self.assertTrue(
            os.path.exists(expected),
            f"Expected signal_guardian.py in {result}",
        )

    def test_contains_capture_output(self) -> None:
        result = resolve_scripts_dir()
        expected = os.path.join(result, "capture_output.py")
        self.assertTrue(
            os.path.exists(expected),
            f"Expected capture_output.py in {result}",
        )

    def test_consistent_across_calls(self) -> None:
        """Should return the same path every time."""
        result1 = resolve_scripts_dir()
        result2 = resolve_scripts_dir()
        self.assertEqual(result1, result2)

    def test_contains_runner_agent_itself(self) -> None:
        """The scripts dir IS the attractor dir, which contains runner_agent.py."""
        result = resolve_scripts_dir()
        self.assertTrue(
            os.path.exists(os.path.join(result, "runner_agent.py")),
            f"runner_agent.py not found in {result}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
