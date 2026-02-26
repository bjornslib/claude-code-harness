"""Unit tests for serena-enforce-pretool.py and serena-enforce-posttool.py.

Tests the decision logic for blocking Read/Grep on source code when Serena is active.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add hooks directory to path for direct imports
_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
sys.path.insert(0, str(_HOOKS_DIR))

import serena_enforce_pretool as pretool
import serena_enforce_posttool as posttool


class TestPreToolHelpers(unittest.TestCase):
    """Test helper functions in serena-enforce-pretool.py."""

    def test_is_source_code_python(self) -> None:
        self.assertTrue(pretool._is_source_code("/path/to/file.py"))

    def test_is_source_code_typescript(self) -> None:
        self.assertTrue(pretool._is_source_code("/path/to/file.ts"))

    def test_is_source_code_tsx(self) -> None:
        self.assertTrue(pretool._is_source_code("/path/to/file.tsx"))

    def test_is_not_source_code_markdown(self) -> None:
        self.assertFalse(pretool._is_source_code("/path/to/README.md"))

    def test_is_not_source_code_json(self) -> None:
        self.assertFalse(pretool._is_source_code("/path/to/config.json"))

    def test_is_not_source_code_yaml(self) -> None:
        self.assertFalse(pretool._is_source_code("/path/to/config.yaml"))

    def test_is_not_source_code_dot(self) -> None:
        self.assertFalse(pretool._is_source_code("/path/to/pipeline.dot"))

    def test_is_not_source_code_feature(self) -> None:
        self.assertFalse(pretool._is_source_code("/path/to/test.feature"))

    def test_is_not_source_code_shell(self) -> None:
        """Shell scripts are config-like, not source code for Serena purposes."""
        self.assertFalse(pretool._is_source_code("/path/to/deploy.sh"))

    def test_unknown_extension_not_blocked(self) -> None:
        """Unknown extensions should not be blocked (err toward approval)."""
        self.assertFalse(pretool._is_source_code("/path/to/file.xyz"))

    def test_no_extension_not_blocked(self) -> None:
        """Files without extension should not be blocked."""
        self.assertFalse(pretool._is_source_code("/path/to/Makefile"))


class TestPreToolWhitelist(unittest.TestCase):
    """Test directory whitelisting."""

    def test_claude_dir_whitelisted(self) -> None:
        self.assertTrue(pretool._is_in_whitelisted_dir(
            "/project/.claude/hooks/test.py", "/project"
        ))

    def test_taskmaster_dir_whitelisted(self) -> None:
        self.assertTrue(pretool._is_in_whitelisted_dir(
            "/project/.taskmaster/docs/prd.md", "/project"
        ))

    def test_acceptance_tests_whitelisted(self) -> None:
        self.assertTrue(pretool._is_in_whitelisted_dir(
            "/project/acceptance-tests/PRD-001/scenarios.feature", "/project"
        ))

    def test_beads_dir_whitelisted(self) -> None:
        self.assertTrue(pretool._is_in_whitelisted_dir(
            "/project/.beads/issues/task-001.md", "/project"
        ))

    def test_src_dir_not_whitelisted(self) -> None:
        self.assertFalse(pretool._is_in_whitelisted_dir(
            "/project/src/auth/routes.py", "/project"
        ))

    def test_app_dir_not_whitelisted(self) -> None:
        self.assertFalse(pretool._is_in_whitelisted_dir(
            "/project/app/components/Login.tsx", "/project"
        ))

    def test_outside_project_not_whitelisted(self) -> None:
        """Files outside project dir are not whitelisted (but also not blocked)."""
        self.assertFalse(pretool._is_in_whitelisted_dir(
            "/other/project/src/file.py", "/project"
        ))


class TestPreToolBypass(unittest.TestCase):
    """Test bypass mechanisms."""

    def test_env_var_bypass(self) -> None:
        with patch.dict(os.environ, {"SERENA_ENFORCE_SKIP": "1"}):
            self.assertTrue(pretool._is_bypassed("/project"))

    def test_env_var_bypass_true(self) -> None:
        with patch.dict(os.environ, {"SERENA_ENFORCE_SKIP": "true"}):
            self.assertTrue(pretool._is_bypassed("/project"))

    def test_env_var_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(pretool._is_bypassed("/tmp/test-project"))

    def test_signal_file_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_dir = Path(tmpdir) / ".claude"
            signal_dir.mkdir()
            (signal_dir / ".serena-enforce-skip").touch()
            with patch.dict(os.environ, {}, clear=True):
                self.assertTrue(pretool._is_bypassed(tmpdir))


class TestPreToolSerenaDetection(unittest.TestCase):
    """Test Serena active detection."""

    def test_serena_active_when_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            serena_dir = Path(tmpdir) / ".serena"
            serena_dir.mkdir()
            (serena_dir / "project.yml").touch()
            self.assertTrue(pretool._serena_is_active(tmpdir))

    def test_serena_not_active_when_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertFalse(pretool._serena_is_active(tmpdir))

    def test_serena_not_active_when_dir_but_no_yml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            serena_dir = Path(tmpdir) / ".serena"
            serena_dir.mkdir()
            self.assertFalse(pretool._serena_is_active(tmpdir))


class TestPreToolEndToEnd(unittest.TestCase):
    """End-to-end tests running the hook as a subprocess."""

    def _run_hook(self, tool_name: str, tool_input: dict, env_extra: dict | None = None) -> dict:
        """Run the pretool hook with given input and return parsed JSON output."""
        hook_path = _HOOKS_DIR / "serena_enforce_pretool.py"

        # Create a temp project with .serena/project.yml
        with tempfile.TemporaryDirectory() as tmpdir:
            serena_dir = Path(tmpdir) / ".serena"
            serena_dir.mkdir()
            (serena_dir / "project.yml").write_text("name: test\n")

            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir
            env.pop("SERENA_ENFORCE_SKIP", None)
            if env_extra:
                env.update(env_extra)

            # Adjust paths to be under the temp project
            if "file_path" in tool_input and not tool_input["file_path"].startswith("/"):
                tool_input["file_path"] = str(Path(tmpdir) / tool_input["file_path"])
            if "path" in tool_input and not tool_input["path"].startswith("/"):
                tool_input["path"] = str(Path(tmpdir) / tool_input["path"])

            stdin_data = json.dumps({
                "tool_name": tool_name,
                "tool_input": tool_input,
            })

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=stdin_data,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

            return json.loads(result.stdout)

    def test_approves_read_on_python_file_with_nudge(self) -> None:
        """AC-1: Read on .py file should be approved with a Serena nudge."""
        result = self._run_hook("Read", {"file_path": "src/auth/routes.py"})
        self.assertEqual(result["decision"], "approve")
        self.assertIn("serena-enforce", result["systemMessage"])
        self.assertIn("find_symbol", result["systemMessage"])

    def test_approves_read_on_markdown(self) -> None:
        """AC-1: Read on .md file should be approved."""
        result = self._run_hook("Read", {"file_path": "README.md"})
        self.assertEqual(result["decision"], "approve")

    def test_approves_read_on_json(self) -> None:
        """AC-3: Read on .json file should be approved."""
        result = self._run_hook("Read", {"file_path": "package.json"})
        self.assertEqual(result["decision"], "approve")

    def test_approves_read_in_claude_dir(self) -> None:
        """AC-3: Read in .claude/ directory should always be approved."""
        result = self._run_hook("Read", {"file_path": ".claude/hooks/test.py"})
        self.assertEqual(result["decision"], "approve")

    def test_approves_read_in_taskmaster(self) -> None:
        """Read in .taskmaster/ should always be approved."""
        result = self._run_hook("Read", {"file_path": ".taskmaster/docs/prd.md"})
        self.assertEqual(result["decision"], "approve")

    def test_approves_read_on_typescript_with_nudge(self) -> None:
        """AC-1: Read on .ts file should be approved with a Serena nudge."""
        result = self._run_hook("Read", {"file_path": "src/components/Login.ts"})
        self.assertEqual(result["decision"], "approve")
        self.assertIn("serena-enforce", result["systemMessage"])

    def test_approves_read_on_tsx_with_nudge(self) -> None:
        """AC-1: Read on .tsx file should be approved with a Serena nudge."""
        result = self._run_hook("Read", {"file_path": "app/page.tsx"})
        self.assertEqual(result["decision"], "approve")
        self.assertIn("serena-enforce", result["systemMessage"])

    def test_bypass_with_env_var(self) -> None:
        """AC-5: SERENA_ENFORCE_SKIP=1 should bypass blocking."""
        result = self._run_hook(
            "Read",
            {"file_path": "src/auth/routes.py"},
            env_extra={"SERENA_ENFORCE_SKIP": "1"},
        )
        self.assertEqual(result["decision"], "approve")

    def test_no_serena_approves_everything(self) -> None:
        """AC-4: When .serena/ doesn't exist, approve everything."""
        hook_path = _HOOKS_DIR / "serena_enforce_pretool.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            # NO .serena directory
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir
            env.pop("SERENA_ENFORCE_SKIP", None)

            stdin_data = json.dumps({
                "tool_name": "Read",
                "tool_input": {"file_path": f"{tmpdir}/src/auth/routes.py"},
            })

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=stdin_data,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

            output = json.loads(result.stdout)
            self.assertEqual(output["decision"], "approve")

    def test_invalid_json_approves(self) -> None:
        """Malformed input should not block anything."""
        hook_path = _HOOKS_DIR / "serena_enforce_pretool.py"
        env = os.environ.copy()
        env.pop("SERENA_ENFORCE_SKIP", None)

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input="not json",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        output = json.loads(result.stdout)
        self.assertEqual(output["decision"], "approve")


class TestPostToolEndToEnd(unittest.TestCase):
    """End-to-end tests for the async PostToolUse advisory hook."""

    def _run_hook(self, tool_name: str, tool_input: dict, serena_active: bool = True) -> dict:
        """Run the posttool hook and return parsed JSON output."""
        hook_path = _HOOKS_DIR / "serena_enforce_posttool.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            if serena_active:
                serena_dir = Path(tmpdir) / ".serena"
                serena_dir.mkdir()
                (serena_dir / "project.yml").write_text("name: test\n")

            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir
            env.pop("SERENA_ENFORCE_SKIP", None)

            if "file_path" in tool_input and not tool_input["file_path"].startswith("/"):
                tool_input["file_path"] = str(Path(tmpdir) / tool_input["file_path"])
            if "path" in tool_input and not tool_input["path"].startswith("/"):
                tool_input["path"] = str(Path(tmpdir) / tool_input["path"])

            stdin_data = json.dumps({
                "tool_name": tool_name,
                "tool_input": tool_input,
            })

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=stdin_data,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

            return json.loads(result.stdout)

    def test_advisory_for_source_code(self) -> None:
        """AC-6: Source code read should produce advisory systemMessage."""
        result = self._run_hook("Read", {"file_path": "src/auth/routes.py"})
        self.assertIn("systemMessage", result)
        self.assertIn("serena-advisory", result["systemMessage"])

    def test_no_advisory_for_markdown(self) -> None:
        """Non-code files should produce no advisory."""
        result = self._run_hook("Read", {"file_path": "README.md"})
        self.assertNotIn("systemMessage", result)

    def test_no_advisory_without_serena(self) -> None:
        """AC-6: No advisory when Serena not active."""
        result = self._run_hook("Read", {"file_path": "src/auth/routes.py"}, serena_active=False)
        self.assertNotIn("systemMessage", result)

    def test_no_advisory_for_claude_dir(self) -> None:
        """Whitelisted directories produce no advisory."""
        result = self._run_hook("Read", {"file_path": ".claude/hooks/test.py"})
        self.assertNotIn("systemMessage", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
