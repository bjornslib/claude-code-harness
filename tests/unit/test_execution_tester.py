"""Unit tests for the ExecutionTester class (bead gv1).

Tests cover:
- Test adaptation (import rewriting)
- Package name extraction from import statements
- Execute test flow with mocked sandbox
- Error handling for sandbox failures
- Default dependencies configuration
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.evaluation.execution_testing import ExecutionTester, SandboxProtocol
from zerorepo.evaluation.models import BenchmarkTask, DifficultyLevel, ExecutionResult


def _make_task(
    imports: list[str] | None = None,
    test_code: str = "def test_x():\n    assert True",
    auxiliary_code: str = "",
) -> BenchmarkTask:
    """Create a BenchmarkTask with configurable fields."""
    return BenchmarkTask(
        id="task-001",
        project="test",
        category="test.cat",
        description="A test task",
        test_code=test_code,
        imports=imports or ["from sklearn.linear_model import Ridge"],
        auxiliary_code=auxiliary_code,
    )


class MockSandbox:
    """A mock sandbox for testing ExecutionTester without Docker."""

    def __init__(self, pass_test: bool = True) -> None:
        self._pass = pass_test
        self.started = False
        self.stopped = False
        self.deps_installed: list[str] = []
        self.files_written: list[tuple[str, str]] = []

    def start(self, workspace_dir: Path, timeout: int | None = None) -> str:
        self.started = True
        return "mock-container-id"

    def write_file(self, container_id: str, path: str, content: str) -> None:
        self.files_written.append((path, content))

    def run_code(
        self, container_id: str, code: str, entrypoint: str = "main.py"
    ) -> Any:
        result = MagicMock()
        if self._pass:
            result.stdout = "PASSED: test_x\nTEST_PASSED"
            result.stderr = ""
            result.exit_code = 0
            result.duration_ms = 150.0
        else:
            result.stdout = "FAILED: test_x: AssertionError\nTEST_FAILED"
            result.stderr = "AssertionError: Expected True"
            result.exit_code = 1
            result.duration_ms = 200.0
        return result

    def run_tests(self, container_id: str, test_dir: str = "/workspace") -> Any:
        return self.run_code(container_id, "", "pytest")

    def stop(self, container_id: str) -> None:
        self.stopped = True

    def install_dependencies(
        self, container_id: str, requirements: list[str]
    ) -> bool:
        self.deps_installed = requirements
        return True


# ---------------------------------------------------------------------------
# Test adaptation (import rewriting)
# ---------------------------------------------------------------------------


class TestAdaptTest:
    """Tests for adapt_test() - test file generation."""

    def test_includes_imports(self) -> None:
        """Adapted test should include task imports."""
        tester = ExecutionTester(sandbox=MockSandbox())
        task = _make_task(imports=["import numpy as np", "from sklearn import Ridge"])
        adapted = tester.adapt_test(task, "/tmp/repo")
        assert "import numpy as np" in adapted
        assert "from sklearn import Ridge" in adapted

    def test_import_mapping(self) -> None:
        """Import mapping should rewrite module names."""
        tester = ExecutionTester(sandbox=MockSandbox())
        task = _make_task(imports=["from sklearn.linear_model import Ridge"])
        adapted = tester.adapt_test(
            task, "/tmp/repo", import_mapping={"sklearn": "ml_lib"}
        )
        assert "from ml_lib.linear_model import Ridge" in adapted
        assert "sklearn" not in adapted

    def test_includes_test_code(self) -> None:
        """Adapted test should include the original test code."""
        tester = ExecutionTester(sandbox=MockSandbox())
        task = _make_task(test_code="def test_ridge():\n    assert True")
        adapted = tester.adapt_test(task, "/tmp/repo")
        assert "def test_ridge():" in adapted
        assert "assert True" in adapted

    def test_includes_auxiliary_code(self) -> None:
        """Adapted test should include auxiliary code."""
        tester = ExecutionTester(sandbox=MockSandbox())
        task = _make_task(auxiliary_code="def helper():\n    return 42")
        adapted = tester.adapt_test(task, "/tmp/repo")
        assert "def helper():" in adapted

    def test_includes_sys_path_insertion(self) -> None:
        """Adapted test should add repo to sys.path."""
        tester = ExecutionTester(sandbox=MockSandbox())
        adapted = tester.adapt_test(_make_task(), "/tmp/repo")
        assert "sys.path.insert" in adapted

    def test_includes_runner(self) -> None:
        """Adapted test should include __main__ runner."""
        tester = ExecutionTester(sandbox=MockSandbox())
        adapted = tester.adapt_test(_make_task(), "/tmp/repo")
        assert 'if __name__ == "__main__"' in adapted
        assert "TEST_PASSED" in adapted
        assert "TEST_FAILED" in adapted


# ---------------------------------------------------------------------------
# Package name extraction
# ---------------------------------------------------------------------------


class TestExtractPackageName:
    """Tests for _extract_package_name static method."""

    def test_from_import(self) -> None:
        """'from sklearn.linear_model import Ridge' -> 'sklearn'."""
        assert ExecutionTester._extract_package_name(
            "from sklearn.linear_model import Ridge"
        ) == "sklearn"

    def test_import_simple(self) -> None:
        """'import numpy' -> 'numpy'."""
        assert ExecutionTester._extract_package_name("import numpy") == "numpy"

    def test_import_as(self) -> None:
        """'import numpy as np' -> 'numpy'."""
        assert ExecutionTester._extract_package_name("import numpy as np") == "numpy"

    def test_from_dotted_module(self) -> None:
        """'from os.path import join' -> 'os'."""
        assert ExecutionTester._extract_package_name(
            "from os.path import join"
        ) == "os"

    def test_invalid_statement(self) -> None:
        """Non-import statement should return None."""
        assert ExecutionTester._extract_package_name("x = 1") is None

    def test_empty_string(self) -> None:
        """Empty string should return None."""
        assert ExecutionTester._extract_package_name("") is None


# ---------------------------------------------------------------------------
# Execute test - passing
# ---------------------------------------------------------------------------


class TestExecuteTestPassing:
    """Tests for execute_test() with a passing sandbox."""

    def test_passing_test_result(self) -> None:
        """Passing test should return passed=True, exit_code=0."""
        sandbox = MockSandbox(pass_test=True)
        tester = ExecutionTester(sandbox=sandbox)
        result = tester.execute_test(_make_task(), "/tmp/repo")

        assert result.passed is True
        assert result.exit_code == 0
        assert "TEST_PASSED" in result.stdout
        assert result.error is None

    def test_returns_execution_result(self) -> None:
        """Should return an ExecutionResult instance."""
        sandbox = MockSandbox(pass_test=True)
        tester = ExecutionTester(sandbox=sandbox)
        result = tester.execute_test(_make_task(), "/tmp/repo")
        assert isinstance(result, ExecutionResult)

    def test_sandbox_started_and_stopped(self) -> None:
        """Sandbox should be started and stopped."""
        sandbox = MockSandbox(pass_test=True)
        tester = ExecutionTester(sandbox=sandbox)
        tester.execute_test(_make_task(), "/tmp/repo")
        assert sandbox.started is True
        assert sandbox.stopped is True

    def test_dependencies_installed(self) -> None:
        """Default dependencies should be installed."""
        sandbox = MockSandbox(pass_test=True)
        tester = ExecutionTester(
            sandbox=sandbox, default_dependencies=["pytest", "numpy"]
        )
        tester.execute_test(
            _make_task(imports=["import numpy"]), "/tmp/repo"
        )
        assert "pytest" in sandbox.deps_installed
        assert "numpy" in sandbox.deps_installed


# ---------------------------------------------------------------------------
# Execute test - failing
# ---------------------------------------------------------------------------


class TestExecuteTestFailing:
    """Tests for execute_test() with a failing sandbox."""

    def test_failing_test_result(self) -> None:
        """Failing test should return passed=False."""
        sandbox = MockSandbox(pass_test=False)
        tester = ExecutionTester(sandbox=sandbox)
        result = tester.execute_test(_make_task(), "/tmp/repo")

        assert result.passed is False
        assert result.exit_code == 1
        assert result.error is not None


# ---------------------------------------------------------------------------
# Execute test - sandbox error
# ---------------------------------------------------------------------------


class TestExecuteTestError:
    """Tests for execute_test() when sandbox raises exceptions."""

    def test_sandbox_start_failure(self) -> None:
        """If sandbox.start fails, should return failed ExecutionResult."""
        sandbox = MagicMock()
        sandbox.start = MagicMock(side_effect=RuntimeError("Docker not running"))
        tester = ExecutionTester(sandbox=sandbox)

        result = tester.execute_test(_make_task(), "/tmp/repo")
        assert result.passed is False
        assert "Docker not running" in (result.error or "")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfiguration:
    """Tests for ExecutionTester configuration."""

    def test_custom_timeout(self) -> None:
        """Custom timeout should be stored."""
        tester = ExecutionTester(sandbox=MockSandbox(), timeout=60)
        assert tester.timeout == 60

    def test_custom_dependencies(self) -> None:
        """Custom default dependencies should be stored."""
        tester = ExecutionTester(
            sandbox=MockSandbox(),
            default_dependencies=["pytest", "scipy", "pandas"],
        )
        assert "scipy" in tester.default_dependencies
        assert "pandas" in tester.default_dependencies

    def test_default_dependencies(self) -> None:
        """Default dependencies should include pytest and numpy."""
        tester = ExecutionTester(sandbox=MockSandbox())
        assert "pytest" in tester.default_dependencies
        assert "numpy" in tester.default_dependencies
