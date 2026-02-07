"""Functional tests for the Docker Sandbox module.

These tests exercise the full workflow of the DockerSandbox class
by mocking Docker at the boundary. They verify multi-step operations
like starting a container, installing deps, running code, running tests,
and cleaning up work correctly as integrated flows.

All Docker operations are mocked since Docker may not be available.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.sandbox import (
    DockerError,
    DockerSandbox,
    ExecutionResult,
    SandboxConfig,
    SandboxTimeoutError,
    TestFailure,
    TestResult,
)


@pytest.fixture
def mock_docker():
    """Fixture that patches the docker module used by sandbox.py."""
    with patch("zerorepo.sandbox.sandbox.docker") as mock_mod:
        mock_client = MagicMock()
        mock_mod.from_env.return_value = mock_client
        mock_mod.DockerClient = MagicMock
        yield mock_mod, mock_client


@pytest.fixture
def mock_container():
    """Create a mock container with running status."""
    container = MagicMock()
    container.id = "func-test-container-001"
    container.status = "running"
    container.exec_run.return_value = (0, (b"", b""))
    return container


class TestFullLifecycleFlow:
    """Functional tests for complete sandbox lifecycle."""

    @pytest.mark.functional
    def test_start_run_code_stop(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full lifecycle: start -> run code -> stop."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        # Configure exec_run to return code output on python calls
        def exec_side_effect(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "python":
                return (0, (b"Hello from sandbox!\n", b""))
            return (0, (b"", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Start
        cid = sandbox.start(workspace)
        assert cid == "func-test-container-001"

        # Run code
        result = sandbox.run_code(cid, 'print("Hello from sandbox!")')
        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert "Hello from sandbox!" in result.stdout

        # Stop
        sandbox.stop(cid)
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()

    @pytest.mark.functional
    def test_start_install_deps_run_code_stop(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full lifecycle: start -> install deps -> run code -> stop."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        call_count = [0]

        def exec_side_effect(cmd, **kwargs):
            call_count[0] += 1
            if isinstance(cmd, list):
                if cmd[0] == "pip":
                    return (0, (b"Successfully installed requests\n", b""))
                if cmd[0] == "python":
                    return (0, (b"200\n", b""))
            return (0, (b"", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cid = sandbox.start(workspace)

        # Install deps
        success = sandbox.install_dependencies(cid, ["requests"])
        assert success is True

        # Run code that uses the dependency
        result = sandbox.run_code(cid, "import requests; print(200)")
        assert result.exit_code == 0

        sandbox.stop(cid)

    @pytest.mark.functional
    def test_context_manager_lifecycle(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Context manager should cleanup on exit."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container
        mock_client.containers.list.return_value = [mock_container]

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with DockerSandbox() as sandbox:
            cid = sandbox.start(workspace)
            assert cid == mock_container.id

        # After exiting context, cleanup should have been called
        mock_client.containers.list.assert_called()


class TestFullTestExecutionFlow:
    """Functional tests for pytest execution workflow."""

    @pytest.mark.functional
    def test_run_tests_with_json_report(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full test run: start -> write tests -> install pytest -> run tests."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        report = {
            "summary": {
                "total": 3,
                "passed": 2,
                "failed": 1,
                "skipped": 0,
                "error": 0,
            },
            "duration": 1.5,
            "tests": [
                {
                    "nodeid": "test_math.py::test_add",
                    "outcome": "passed",
                },
                {
                    "nodeid": "test_math.py::test_subtract",
                    "outcome": "passed",
                },
                {
                    "nodeid": "test_math.py::test_divide_zero",
                    "outcome": "failed",
                    "call": {
                        "longrepr": "ZeroDivisionError: division by zero",
                        "crash": {"message": "division by zero"},
                    },
                },
            ],
        }
        report_json = json.dumps(report)

        def exec_side_effect(cmd, **kwargs):
            if isinstance(cmd, list):
                if cmd[0] == "cat":
                    return (0, (report_json.encode(), b""))
                if cmd[0] == "pip":
                    return (0, (b"installed", b""))
                if cmd[0] == "python" and "-m" in cmd:
                    return (1, (b"1 failed, 2 passed", b""))
            return (0, (b"", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cid = sandbox.start(workspace)
        result = sandbox.run_tests(cid)

        assert isinstance(result, TestResult)
        assert result.total == 3
        assert result.passed == 2
        assert result.failed == 1
        assert len(result.failures) == 1
        assert result.failures[0].name == "test_math.py::test_divide_zero"
        assert "ZeroDivisionError" in result.failures[0].traceback


class TestFileOperationsFlow:
    """Functional tests for file system operations workflow."""

    @pytest.mark.functional
    def test_write_read_list_files(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Write a file, read it back, and list files."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        file_content = "def hello():\n    return 'world'\n"

        def exec_side_effect(cmd, **kwargs):
            if isinstance(cmd, list):
                if cmd[0] == "cat":
                    return (0, (file_content.encode(), b""))
                if cmd[0] == "find":
                    return (
                        0,
                        (b"/workspace/hello.py\n/workspace/main.py\n", b""),
                    )
            return (0, (b"", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cid = sandbox.start(workspace)

        # Write
        sandbox.write_file(cid, "/workspace/hello.py", file_content)

        # Read
        content = sandbox.read_file(cid, "/workspace/hello.py")
        assert content == file_content

        # List
        files = sandbox.list_files(cid)
        assert len(files) == 2
        assert "/workspace/hello.py" in files


class TestDependencyInstallationFlow:
    """Functional tests for dependency installation workflows."""

    @pytest.mark.functional
    def test_install_from_requirements_file(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Install dependencies from a local requirements.txt file."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        def exec_side_effect(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "pip":
                return (0, (b"Successfully installed packages\n", b""))
            return (0, (b"", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        # Create a local requirements file
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests>=2.28\nflask>=3.0\npydantic>=2.0\n")

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cid = sandbox.start(workspace)
        result = sandbox.install_dependencies_from_file(cid, req_file)

        assert result is True

    @pytest.mark.functional
    def test_install_dependencies_failure_recovery(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When pip install fails, return False instead of raising."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        def exec_side_effect(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "pip":
                return (1, (b"", b"ERROR: No matching distribution"))
            return (0, (b"", b""))

        mock_container.exec_run.side_effect = exec_side_effect

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        cid = sandbox.start(workspace)
        result = sandbox.install_dependencies(cid, ["nonexistent-package"])

        assert result is False


class TestErrorHandlingFlow:
    """Functional tests for error handling scenarios."""

    @pytest.mark.functional
    def test_container_not_found_during_exec(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Operations should raise DockerError when container is gone."""
        from docker.errors import NotFound

        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.side_effect = NotFound("gone")

        sandbox = DockerSandbox()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Start works because containers.run is used, not containers.get
        mock_client.containers.run.return_value = mock_container
        cid = sandbox.start(workspace)

        # But running code fails because containers.get raises NotFound
        with pytest.raises(DockerError, match="not found"):
            sandbox.run_code(cid, "print('hello')")

    @pytest.mark.functional
    def test_sandbox_config_validation(self) -> None:
        """SandboxConfig should validate its fields."""
        # Valid config
        config = SandboxConfig(
            image="python:3.12",
            memory_limit="1g",
            cpu_count=4,
            timeout=600,
        )
        assert config.image == "python:3.12"

        # Invalid cpu_count
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SandboxConfig(cpu_count=0)

        with pytest.raises(ValidationError):
            SandboxConfig(timeout=-1)

    @pytest.mark.functional
    def test_cleanup_handles_docker_errors_gracefully(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
    ) -> None:
        """Cleanup should not raise even if Docker operations fail."""
        from docker.errors import APIError

        mock_mod, mock_client = mock_docker
        mock_container.stop.side_effect = APIError("failed")
        mock_client.containers.list.return_value = [mock_container]

        sandbox = DockerSandbox()
        # Should not raise
        sandbox.cleanup(force=True)


class TestCustomConfigFlow:
    """Functional tests for custom sandbox configurations."""

    @pytest.mark.functional
    def test_custom_image_and_limits(
        self,
        mock_docker: tuple[MagicMock, MagicMock],
        mock_container: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Custom config should be passed through to container creation."""
        mock_mod, mock_client = mock_docker
        mock_client.containers.run.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        config = SandboxConfig(
            image="python:3.12-slim",
            memory_limit="1g",
            cpu_count=2,
            timeout=600,
        )
        sandbox = DockerSandbox(config=config)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        sandbox.start(workspace)

        call_kwargs = mock_client.containers.run.call_args
        assert call_kwargs.kwargs["image"] == "python:3.12-slim"
        assert call_kwargs.kwargs["mem_limit"] == "1g"
        assert call_kwargs.kwargs["nano_cpus"] == 2_000_000_000
