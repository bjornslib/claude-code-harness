"""Unit tests for the sandbox executor module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cobuilder.repomap.codegen.sandbox_executor import (
    DockerSandboxExecutor,
    InProcessSandboxExecutor,
    SandboxExecutorConfig,
)
from cobuilder.repomap.codegen.tdd_loop import SandboxResult
from cobuilder.repomap.models.enums import InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.sandbox.models import TestFailure, TestResult


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_func_node(
    *,
    name: str = "calculate_mean",
    file_path: str | None = "src/module.py",
) -> RPGNode:
    """Create a FUNCTION_AUGMENTED node for testing."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        folder_path="src",
        file_path=file_path,
        signature=f"def {name}() -> None",
    )


def _make_mock_sandbox(
    test_result: TestResult | None = None,
) -> MagicMock:
    """Create a mock DockerSandbox."""
    sandbox = MagicMock()
    sandbox.start.return_value = "container-123"
    sandbox.install_dependencies.return_value = True
    if test_result is None:
        test_result = TestResult(
            total=3, passed=3, failed=0, skipped=0, errors=0, duration=1.5
        )
    sandbox.run_tests.return_value = test_result
    return sandbox


# --------------------------------------------------------------------------- #
#                              Tests: SandboxExecutorConfig                    #
# --------------------------------------------------------------------------- #


class TestSandboxExecutorConfig:
    """Tests for the SandboxExecutorConfig model."""

    def test_defaults(self):
        config = SandboxExecutorConfig()
        assert config.timeout_seconds == 30
        assert config.install_dependencies is True
        assert "pytest" in config.default_requirements
        assert config.cleanup_on_finish is True

    def test_custom_values(self):
        config = SandboxExecutorConfig(
            timeout_seconds=60,
            install_dependencies=False,
            default_requirements=["pytest", "numpy"],
            cleanup_on_finish=False,
        )
        assert config.timeout_seconds == 60
        assert config.install_dependencies is False
        assert "numpy" in config.default_requirements

    def test_timeout_minimum(self):
        with pytest.raises(Exception):  # Pydantic validation
            SandboxExecutorConfig(timeout_seconds=0)


# --------------------------------------------------------------------------- #
#                              Tests: DockerSandboxExecutor                    #
# --------------------------------------------------------------------------- #


class TestDockerSandboxExecutor:
    """Tests for the Docker-based sandbox executor."""

    def test_run_tests_success(self):
        """Successful test run returns proper SandboxResult."""
        sandbox = _make_mock_sandbox()
        executor = DockerSandboxExecutor(sandbox)
        node = _make_func_node()

        result = executor.run_tests(
            implementation="def calculate_mean(n): return sum(n)/len(n)",
            test_code="def test_it(): assert True",
            node=node,
        )

        assert result.passed == 3
        assert result.failed == 0
        assert result.errors == 0
        sandbox.start.assert_called_once()
        sandbox.stop.assert_called_once_with("container-123")

    def test_run_tests_with_failures(self):
        """Test run with failures returns accurate counts."""
        test_result = TestResult(
            total=5,
            passed=3,
            failed=2,
            skipped=0,
            errors=0,
            duration=2.0,
            failures=[
                TestFailure(name="test_edge", traceback="AssertionError"),
                TestFailure(name="test_empty", traceback="ZeroDivisionError"),
            ],
        )
        sandbox = _make_mock_sandbox(test_result)
        executor = DockerSandboxExecutor(sandbox)
        node = _make_func_node()

        result = executor.run_tests("def foo(): pass", "def test_it(): pass", node)

        assert result.passed == 3
        assert result.failed == 2
        assert "FAILED test_edge" in result.stderr
        assert "AssertionError" in result.stderr

    def test_sandbox_timeout(self):
        """Sandbox start failure returns error result."""
        sandbox = MagicMock()
        sandbox.start.side_effect = RuntimeError("Container timeout")
        executor = DockerSandboxExecutor(sandbox)
        node = _make_func_node()

        result = executor.run_tests("def foo(): pass", "def test_it(): pass", node)

        assert result.failed == 1
        assert result.errors == 1
        assert "Sandbox execution error" in result.stderr

    def test_isolation_cleanup(self):
        """Container is stopped even on test failure."""
        sandbox = _make_mock_sandbox()
        sandbox.run_tests.side_effect = RuntimeError("Test crashed")
        executor = DockerSandboxExecutor(sandbox)
        node = _make_func_node()

        result = executor.run_tests("def foo(): pass", "def test_it(): pass", node)

        assert result.errors == 1
        sandbox.stop.assert_called_once_with("container-123")

    def test_no_dependency_install(self):
        """Dependencies are not installed when config says so."""
        sandbox = _make_mock_sandbox()
        config = SandboxExecutorConfig(install_dependencies=False)
        executor = DockerSandboxExecutor(sandbox, config)
        node = _make_func_node()

        executor.run_tests("def foo(): pass", "def test_it(): pass", node)

        sandbox.install_dependencies.assert_not_called()

    def test_config_property(self):
        """Config property returns the config."""
        config = SandboxExecutorConfig(timeout_seconds=45)
        executor = DockerSandboxExecutor(MagicMock(), config)
        assert executor.config.timeout_seconds == 45

    def test_resolve_impl_path_with_file_path(self):
        """Node with file_path uses it for implementation file."""
        node = _make_func_node(file_path="src/math_utils.py")
        workspace = Path("/tmp/workspace")
        path = DockerSandboxExecutor._resolve_impl_path(node, workspace)
        assert path == workspace / "src/math_utils.py"

    def test_resolve_impl_path_without_file_path(self):
        """Node without file_path uses sanitized name."""
        node = _make_func_node(name="my_func", file_path=None)
        workspace = Path("/tmp/workspace")
        path = DockerSandboxExecutor._resolve_impl_path(node, workspace)
        assert path == workspace / "my_func.py"

    def test_convert_test_result_all_passed(self):
        """Convert TestResult with all passed."""
        tr = TestResult(
            total=5, passed=5, failed=0, skipped=0, errors=0, duration=1.0
        )
        result = DockerSandboxExecutor._convert_test_result(tr)
        assert result.passed == 5
        assert result.failed == 0
        assert result.all_passed is True
        assert result.duration_ms == 1000.0

    def test_convert_test_result_with_failures(self):
        """Convert TestResult with failures includes error details."""
        tr = TestResult(
            total=3,
            passed=1,
            failed=2,
            skipped=0,
            errors=0,
            duration=2.0,
            failures=[
                TestFailure(name="test_a", traceback="assert 1 == 2"),
            ],
        )
        result = DockerSandboxExecutor._convert_test_result(tr)
        assert result.failed == 2
        assert "FAILED test_a" in result.stderr


# --------------------------------------------------------------------------- #
#                              Tests: InProcessSandboxExecutor                 #
# --------------------------------------------------------------------------- #


class TestInProcessSandboxExecutor:
    """Tests for the in-process sandbox executor."""

    def test_valid_code_passes(self):
        """Valid implementation + test code passes."""
        executor = InProcessSandboxExecutor()
        node = _make_func_node()

        result = executor.run_tests(
            implementation="def calculate_mean(nums): return sum(nums)/len(nums)",
            test_code="result = calculate_mean([1,2,3])\nassert result == 2.0",
            node=node,
        )

        assert result.passed == 1
        assert result.failed == 0

    def test_syntax_error_in_impl(self):
        """Syntax error in implementation returns error."""
        executor = InProcessSandboxExecutor()
        node = _make_func_node()

        result = executor.run_tests(
            implementation="def bad(: pass",
            test_code="assert True",
            node=node,
        )

        assert result.failed == 1
        assert result.errors == 1
        assert "SyntaxError" in result.stderr

    def test_runtime_error(self):
        """Runtime error in code returns failure."""
        executor = InProcessSandboxExecutor()
        node = _make_func_node()

        result = executor.run_tests(
            implementation="def foo(): raise ValueError('boom')",
            test_code="foo()",
            node=node,
        )

        assert result.failed == 1
        assert "ValueError" in result.stderr

    def test_assertion_error(self):
        """Assertion error in tests returns failure."""
        executor = InProcessSandboxExecutor()
        node = _make_func_node()

        result = executor.run_tests(
            implementation="x = 1",
            test_code="assert x == 2",
            node=node,
        )

        assert result.failed == 1
