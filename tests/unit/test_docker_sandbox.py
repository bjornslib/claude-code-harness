"""Unit tests for the Docker Sandbox module.

All tests mock the docker library since Docker may not be available.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from pydantic import ValidationError

from cobuilder.repomap.sandbox.exceptions import DockerError, SandboxTimeoutError
from cobuilder.repomap.sandbox.models import (
    ExecutionResult,
    SandboxConfig,
    TestFailure,
    TestResult,
)
from cobuilder.repomap.sandbox.sandbox import DockerSandbox


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestExecutionResult:
    """Tests for the ExecutionResult dataclass."""

    def test_create_basic(self) -> None:
        result = ExecutionResult(
            stdout="hello", stderr="", exit_code=0, duration_ms=100.0
        )
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.duration_ms == 100.0

    def test_create_with_error(self) -> None:
        result = ExecutionResult(
            stdout="", stderr="error occurred", exit_code=1, duration_ms=50.5
        )
        assert result.exit_code == 1
        assert result.stderr == "error occurred"

    def test_fields_are_mutable(self) -> None:
        result = ExecutionResult(
            stdout="", stderr="", exit_code=0, duration_ms=0.0
        )
        result.stdout = "updated"
        assert result.stdout == "updated"


class TestTestFailure:
    """Tests for the TestFailure dataclass."""

    def test_create(self) -> None:
        failure = TestFailure(
            name="test_module::test_func",
            traceback="AssertionError: expected True",
        )
        assert failure.name == "test_module::test_func"
        assert "AssertionError" in failure.traceback


class TestTestResult:
    """Tests for the TestResult dataclass."""

    def test_create_all_passing(self) -> None:
        result = TestResult(
            total=5, passed=5, failed=0, skipped=0, errors=0, duration=1.5
        )
        assert result.total == 5
        assert result.passed == 5
        assert result.failures == []

    def test_create_with_failures(self) -> None:
        failures = [
            TestFailure(name="test_one", traceback="failed"),
            TestFailure(name="test_two", traceback="error"),
        ]
        result = TestResult(
            total=5,
            passed=3,
            failed=2,
            skipped=0,
            errors=0,
            duration=2.0,
            failures=failures,
        )
        assert result.failed == 2
        assert len(result.failures) == 2

    def test_default_failures_list(self) -> None:
        result = TestResult(
            total=1, passed=1, failed=0, skipped=0, errors=0, duration=0.1
        )
        assert result.failures == []
        # Ensure separate instances get separate lists
        result2 = TestResult(
            total=1, passed=1, failed=0, skipped=0, errors=0, duration=0.1
        )
        result.failures.append(TestFailure(name="x", traceback="y"))
        assert len(result2.failures) == 0


class TestSandboxConfig:
    """Tests for the SandboxConfig Pydantic model."""

    def test_default_values(self) -> None:
        config = SandboxConfig()
        assert config.image == "python:3.11-slim"
        assert config.memory_limit == "512m"
        assert config.cpu_count == 1
        assert config.timeout == 300

    def test_custom_values(self) -> None:
        config = SandboxConfig(
            image="python:3.12",
            memory_limit="1g",
            cpu_count=4,
            timeout=600,
        )
        assert config.image == "python:3.12"
        assert config.memory_limit == "1g"
        assert config.cpu_count == 4
        assert config.timeout == 600

    def test_cpu_count_validation_min(self) -> None:
        with pytest.raises(ValidationError):
            SandboxConfig(cpu_count=0)

    def test_cpu_count_validation_max(self) -> None:
        with pytest.raises(ValidationError):
            SandboxConfig(cpu_count=9)

    def test_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SandboxConfig(timeout=0)
        with pytest.raises(ValidationError):
            SandboxConfig(timeout=-1)


# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestDockerError:
    """Tests for DockerError exception."""

    def test_basic_error(self) -> None:
        exc = DockerError("something went wrong")
        assert str(exc) == "something went wrong"

    def test_is_exception(self) -> None:
        assert issubclass(DockerError, Exception)


class TestSandboxTimeoutError:
    """Tests for SandboxTimeoutError exception."""

    def test_basic_timeout(self) -> None:
        exc = SandboxTimeoutError(timeout=30, operation="container start")
        assert exc.timeout == 30
        assert exc.operation == "container start"
        assert "30 seconds" in str(exc)
        assert "container start" in str(exc)

    def test_default_operation(self) -> None:
        exc = SandboxTimeoutError(timeout=60)
        assert exc.operation == "operation"
        assert "60 seconds" in str(exc)

    def test_inherits_docker_error(self) -> None:
        assert issubclass(SandboxTimeoutError, DockerError)


# ---------------------------------------------------------------------------
# DockerSandbox Tests (all Docker operations mocked)
# ---------------------------------------------------------------------------


class TestDockerSandboxInit:
    """Tests for DockerSandbox initialization."""

    def test_default_config(self) -> None:
        sandbox = DockerSandbox()
        assert sandbox.config.image == "python:3.11-slim"
        assert sandbox.config.memory_limit == "512m"
        assert sandbox._active_containers == []

    def test_custom_config(self) -> None:
        config = SandboxConfig(image="python:3.12", timeout=600)
        sandbox = DockerSandbox(config=config)
        assert sandbox.config.image == "python:3.12"
        assert sandbox.config.timeout == 600

    def test_label_constant(self) -> None:
        assert DockerSandbox.LABEL == "zerorepo-sandbox"

    def test_default_image_constant(self) -> None:
        assert DockerSandbox.DEFAULT_IMAGE == "python:3.11-slim"


class TestDockerSandboxClient:
    """Tests for the Docker client property."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_client_creates_connection(self, mock_docker: MagicMock) -> None:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        client = sandbox.client

        mock_docker.from_env.assert_called_once()
        mock_client.ping.assert_called_once()
        assert client is mock_client

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_client_cached(self, mock_docker: MagicMock) -> None:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        _ = sandbox.client
        _ = sandbox.client

        # from_env should only be called once
        mock_docker.from_env.assert_called_once()

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_client_raises_docker_error(
        self, mock_docker: MagicMock
    ) -> None:
        from docker.errors import DockerException

        mock_docker.from_env.side_effect = DockerException("no daemon")
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        with pytest.raises(DockerError, match="Failed to connect"):
            _ = sandbox.client


class TestDockerSandboxStart:
    """Tests for container start lifecycle."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_start_returns_container_id(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        cid = sandbox.start(Path("/tmp/workspace"))

        assert cid == "abc123"
        assert "abc123" in sandbox._active_containers

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_start_passes_resource_limits(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        config = SandboxConfig(memory_limit="1g", cpu_count=2)
        sandbox = DockerSandbox(config=config)
        sandbox.start(Path("/tmp/workspace"))

        call_kwargs = mock_client.containers.run.call_args
        assert call_kwargs.kwargs["mem_limit"] == "1g"
        assert call_kwargs.kwargs["nano_cpus"] == 2_000_000_000

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_start_mounts_workspace(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        workspace = Path("/tmp/test_workspace")
        sandbox.start(workspace)

        call_kwargs = mock_client.containers.run.call_args
        volumes = call_kwargs.kwargs["volumes"]
        resolved = str(workspace.resolve())
        assert resolved in volumes
        assert volumes[resolved]["bind"] == "/workspace"
        assert volumes[resolved]["mode"] == "rw"

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_start_uses_label(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        sandbox.start(Path("/tmp/workspace"))

        call_kwargs = mock_client.containers.run.call_args
        assert call_kwargs.kwargs["labels"] == {"zerorepo-sandbox": "true"}

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_start_raises_on_api_error(
        self, mock_docker: MagicMock
    ) -> None:
        from docker.errors import APIError

        mock_client = MagicMock()
        mock_client.containers.run.side_effect = APIError("failed")
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        with pytest.raises(DockerError, match="Failed to start"):
            sandbox.start(Path("/tmp/workspace"))


class TestDockerSandboxStop:
    """Tests for container stop/removal."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_stop_removes_container(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        sandbox._active_containers.append("abc123")
        sandbox.stop("abc123")

        mock_container.stop.assert_called_once_with(timeout=10)
        mock_container.remove.assert_called_once_with(force=True)
        assert "abc123" not in sandbox._active_containers

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_stop_handles_not_found(
        self, mock_docker: MagicMock
    ) -> None:
        from docker.errors import NotFound

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = NotFound("gone")
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        sandbox._active_containers.append("abc123")
        # Should not raise
        sandbox.stop("abc123")
        assert "abc123" not in sandbox._active_containers


class TestDockerSandboxDependencies:
    """Tests for dependency installation methods."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_install_dependencies_success(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"Success", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.install_dependencies("abc123", ["requests", "flask"])

        assert result is True

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_install_dependencies_failure(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (1, (b"", b"pip error"))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.install_dependencies("abc123", ["nonexistent-pkg"])

        assert result is False

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_install_empty_requirements(
        self, mock_docker: MagicMock
    ) -> None:
        mock_docker.DockerClient = MagicMock
        sandbox = DockerSandbox()
        result = sandbox.install_dependencies("abc123", [])
        assert result is True

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_install_from_file(
        self, mock_docker: MagicMock, tmp_path: Path
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"Success", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests>=2.0\nflask\n")

        sandbox = DockerSandbox()
        result = sandbox.install_dependencies_from_file("abc123", req_file)

        assert result is True

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_install_from_missing_file(
        self, mock_docker: MagicMock
    ) -> None:
        mock_docker.DockerClient = MagicMock
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        sandbox = DockerSandbox()
        with pytest.raises(DockerError, match="Cannot read requirements"):
            sandbox.install_dependencies_from_file(
                "abc123", Path("/nonexistent/requirements.txt")
            )


class TestDockerSandboxCodeExecution:
    """Tests for code execution methods."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_code_success(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            0,
            (b"Hello World\n", b""),
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.run_code("abc123", 'print("Hello World")')

        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert "Hello World" in result.stdout

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_code_with_custom_entrypoint(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"ok", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.run_code("abc123", "pass", entrypoint="app.py")

        assert result.exit_code == 0
        # Verify the exec_run was called with the custom entrypoint path
        calls = mock_container.exec_run.call_args_list
        # The last call (for running the code) should reference app.py
        found_app_py = any(
            "app.py" in str(c) for c in calls
        )
        assert found_app_py

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_code_with_error(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            1,
            (b"", b"SyntaxError: invalid syntax"),
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.run_code("abc123", "def broken(")

        assert result.exit_code == 1
        assert "SyntaxError" in result.stderr

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_script(
        self, mock_docker: MagicMock, tmp_path: Path
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"script output", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        script = tmp_path / "test_script.py"
        script.write_text('print("script output")')

        sandbox = DockerSandbox()
        result = sandbox.run_script("abc123", script)

        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_script_missing_file(
        self, mock_docker: MagicMock
    ) -> None:
        mock_docker.DockerClient = MagicMock
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        sandbox = DockerSandbox()
        with pytest.raises(DockerError, match="Cannot read script"):
            sandbox.run_script("abc123", Path("/nonexistent/script.py"))


class TestDockerSandboxTestExecution:
    """Tests for pytest execution and report parsing."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_tests_success(self, mock_docker: MagicMock) -> None:
        report = {
            "summary": {
                "total": 5,
                "passed": 4,
                "failed": 1,
                "skipped": 0,
                "error": 0,
            },
            "duration": 2.5,
            "tests": [
                {
                    "nodeid": "test_example::test_fail",
                    "outcome": "failed",
                    "call": {
                        "crash": {"message": "assert False"},
                        "longrepr": "AssertionError: assert False",
                    },
                },
            ],
        }
        report_json = json.dumps(report)

        mock_container = MagicMock()

        def exec_side_effect(cmd, **kwargs):
            """Route exec calls based on command."""
            if isinstance(cmd, list) and "cat" in cmd:
                return (0, (report_json.encode(), b""))
            return (0, (b"ok", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.run_tests("abc123")

        assert isinstance(result, TestResult)
        assert result.total == 5
        assert result.passed == 4
        assert result.failed == 1
        assert len(result.failures) == 1
        assert result.failures[0].name == "test_example::test_fail"

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_run_tests_fallback_on_report_failure(
        self, mock_docker: MagicMock
    ) -> None:
        """When JSON report fails, should provide fallback result."""
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            1,
            (b"FAILED", b"some error"),
        )

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox.run_tests("abc123")

        assert isinstance(result, TestResult)
        # Fallback: should indicate failure
        assert result.errors >= 1 or result.failed >= 1

    def test_parse_pytest_report_all_passing(self) -> None:
        report = {
            "summary": {
                "total": 10,
                "passed": 10,
                "failed": 0,
                "skipped": 0,
                "error": 0,
            },
            "duration": 1.2,
            "tests": [],
        }
        result = DockerSandbox._parse_pytest_report(report)
        assert result.total == 10
        assert result.passed == 10
        assert result.failed == 0
        assert result.failures == []
        assert result.duration == 1.2

    def test_parse_pytest_report_with_failures(self) -> None:
        report = {
            "summary": {
                "total": 3,
                "passed": 1,
                "failed": 2,
                "skipped": 0,
                "error": 0,
            },
            "duration": 0.8,
            "tests": [
                {
                    "nodeid": "test_a::test_one",
                    "outcome": "failed",
                    "call": {
                        "longrepr": "AssertionError",
                        "crash": {"message": "assert 1 == 2"},
                    },
                },
                {
                    "nodeid": "test_a::test_two",
                    "outcome": "error",
                    "call": {
                        "longrepr": "",
                        "crash": {"message": "ImportError"},
                    },
                },
            ],
        }
        result = DockerSandbox._parse_pytest_report(report)
        assert result.failed == 2
        assert len(result.failures) == 2
        assert result.failures[0].name == "test_a::test_one"
        assert result.failures[0].traceback == "AssertionError"
        assert result.failures[1].traceback == "ImportError"

    def test_parse_pytest_report_empty(self) -> None:
        report = {"summary": {}, "duration": 0.0, "tests": []}
        result = DockerSandbox._parse_pytest_report(report)
        assert result.total == 0
        assert result.passed == 0
        assert result.failures == []


class TestDockerSandboxFileOps:
    """Tests for file system operations."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_write_file(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        # Should not raise
        sandbox.write_file("abc123", "/workspace/test.py", "print('hello')")

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_read_file_success(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            0,
            (b"file contents here", b""),
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        content = sandbox.read_file("abc123", "/workspace/test.py")

        assert content == "file contents here"

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_read_file_not_found(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            1,
            (b"", b"No such file"),
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        with pytest.raises(DockerError, match="Failed to read"):
            sandbox.read_file("abc123", "/workspace/missing.py")

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_list_files(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            0,
            (b"/workspace/main.py\n/workspace/test.py\n", b""),
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        files = sandbox.list_files("abc123")

        assert len(files) == 2
        assert "/workspace/main.py" in files
        assert "/workspace/test.py" in files

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_list_files_empty(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        files = sandbox.list_files("abc123")

        assert files == []


class TestDockerSandboxCleanup:
    """Tests for cleanup and context manager."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_context_manager(self, mock_docker: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.containers.list.return_value = []
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        with DockerSandbox() as sandbox:
            assert isinstance(sandbox, DockerSandbox)

        # Cleanup should have been called
        mock_client.containers.list.assert_called()

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_cleanup_force_removes_labeled(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container1 = MagicMock()
        mock_container2 = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.list.return_value = [
            mock_container1,
            mock_container2,
        ]
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        sandbox.cleanup(force=True)

        mock_client.containers.list.assert_called_with(
            all=True, filters={"label": "zerorepo-sandbox"}
        )
        mock_container1.stop.assert_called_once()
        mock_container1.remove.assert_called_once_with(force=True)
        mock_container2.stop.assert_called_once()
        mock_container2.remove.assert_called_once_with(force=True)

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_cleanup_clears_active_containers(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_client.containers.list.return_value = []
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        sandbox._active_containers = ["abc123", "def456"]
        sandbox.cleanup(force=True)

        assert sandbox._active_containers == []

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_cleanup_non_force_only_tracked(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        sandbox._active_containers = ["abc123"]
        sandbox.cleanup(force=False)

        # Should NOT call containers.list for labeled containers
        mock_client.containers.list.assert_not_called()
        assert sandbox._active_containers == []


class TestDockerSandboxExecHelpers:
    """Tests for internal execution helpers."""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_exec_in_container_demux_tuple(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (
            0,
            (b"stdout data", b"stderr data"),
        )
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox._exec_in_container("abc123", ["echo", "test"])

        assert result.stdout == "stdout data"
        assert result.stderr == "stderr data"
        assert result.exit_code == 0
        assert result.duration_ms > 0

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_exec_in_container_bytes_output(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"raw bytes output")
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox._exec_in_container("abc123", ["echo", "test"])

        assert result.stdout == "raw bytes output"
        assert result.stderr == ""

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_exec_in_container_none_output(
        self, mock_docker: MagicMock
    ) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, None)
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox._exec_in_container("abc123", ["true"])

        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_exec_in_container_not_found(
        self, mock_docker: MagicMock
    ) -> None:
        from docker.errors import NotFound

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = NotFound("gone")
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        with pytest.raises(DockerError, match="not found"):
            sandbox._exec_in_container("abc123", ["echo"])

    @patch("cobuilder.repomap.sandbox.sandbox.docker")
    def test_exec_raw(self, mock_docker: MagicMock) -> None:
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"ok", b""))
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client
        mock_docker.DockerClient = MagicMock

        sandbox = DockerSandbox()
        result = sandbox._exec_raw("abc123", "echo hello")

        assert result.exit_code == 0
        # Should have been called with sh -c
        call_args = mock_container.exec_run.call_args
        assert call_args[0][0] == ["sh", "-c", "echo hello"]


class TestDockerSandboxImports:
    """Tests that the module's public API is correctly exported."""

    def test_import_from_package(self) -> None:
        from cobuilder.repomap.sandbox import (
            DockerError,
            DockerSandbox,
            ExecutionResult,
            SandboxConfig,
            SandboxTimeoutError,
            TestFailure,
            TestResult,
        )

        assert DockerSandbox is not None
        assert SandboxConfig is not None
        assert ExecutionResult is not None
        assert TestResult is not None
        assert TestFailure is not None
        assert DockerError is not None
        assert SandboxTimeoutError is not None
