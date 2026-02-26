"""Docker Sandbox – isolated container environment for code execution and testing.

Implements Epic 1.5 of PRD-RPG-P1-001, providing:

- Container lifecycle management (create, stop, cleanup)
- Dependency installation via pip
- Code execution with stdout/stderr capture
- Pytest execution with JSON report parsing
- File system operations (read, write, list)
- Context manager support for automatic cleanup
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, ContainerError, DockerException, NotFound
from docker.models.containers import Container

from cobuilder.repomap.sandbox.exceptions import DockerError, SandboxTimeoutError
from cobuilder.repomap.sandbox.models import (
    ExecutionResult,
    SandboxConfig,
    TestFailure,
    TestResult,
)


class DockerSandbox:
    """Manage Docker container lifecycle for code execution.

    Provides an isolated sandbox environment using Docker containers
    for safely running generated code and tests.

    Attributes:
        LABEL: Docker label applied to all ZeroRepo sandbox containers.
        DEFAULT_IMAGE: Default Docker image when no config is provided.
    """

    LABEL = "zerorepo-sandbox"
    DEFAULT_IMAGE = "python:3.11-slim"

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize the Docker sandbox.

        Args:
            config: Optional sandbox configuration. Uses defaults if None.
        """
        self.config = config or SandboxConfig()
        self._client: docker.DockerClient | None = None
        self._active_containers: list[str] = []

    @property
    def client(self) -> docker.DockerClient:
        """Lazily initialize and return the Docker client.

        Returns:
            A connected Docker client instance.

        Raises:
            DockerError: If Docker daemon is not available.
        """
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except DockerException as exc:
                raise DockerError(
                    f"Failed to connect to Docker daemon: {exc}"
                ) from exc
        return self._client

    # -----------------------------------------------------------------------
    # Task 1.5.1: Container Lifecycle
    # -----------------------------------------------------------------------

    def start(self, workspace_dir: Path, timeout: int | None = None) -> str:
        """Create and start a container with workspace mounted at /workspace.

        Args:
            workspace_dir: Local directory to mount as /workspace in the
                container.
            timeout: Override the default timeout in seconds for this
                container.

        Returns:
            The container ID string.

        Raises:
            DockerError: If the container fails to start.
            SandboxTimeoutError: If the container does not become ready in
                time.
        """
        effective_timeout = timeout or self.config.timeout
        workspace_path = str(workspace_dir.resolve())

        try:
            container: Container = self.client.containers.run(
                image=self.config.image,
                command="sleep infinity",
                detach=True,
                labels={self.LABEL: "true"},
                volumes={
                    workspace_path: {"bind": "/workspace", "mode": "rw"},
                },
                working_dir="/workspace",
                mem_limit=self.config.memory_limit,
                nano_cpus=self.config.cpu_count * 1_000_000_000,
                remove=False,
            )
        except (APIError, DockerException) as exc:
            raise DockerError(f"Failed to start container: {exc}") from exc

        container_id = container.id
        self._active_containers.append(container_id)

        # Wait for container to be running
        start_time = time.monotonic()
        while time.monotonic() - start_time < effective_timeout:
            container.reload()
            if container.status == "running":
                return container_id
            time.sleep(0.1)

        # Timeout – clean up and raise
        self._force_remove(container_id)
        raise SandboxTimeoutError(
            timeout=effective_timeout, operation="container start"
        )

    def stop(self, container_id: str) -> None:
        """Stop and remove a container.

        Args:
            container_id: The ID of the container to stop.

        Raises:
            DockerError: If the container cannot be stopped or removed.
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove(force=True)
        except NotFound:
            pass  # Container already gone – nothing to do
        except (APIError, DockerException) as exc:
            raise DockerError(
                f"Failed to stop container {container_id}: {exc}"
            ) from exc
        finally:
            if container_id in self._active_containers:
                self._active_containers.remove(container_id)

    # -----------------------------------------------------------------------
    # Task 1.5.2: Dependency Installation
    # -----------------------------------------------------------------------

    def install_dependencies(
        self, container_id: str, requirements: list[str]
    ) -> bool:
        """Install Python dependencies from a list of package specifiers.

        Writes a requirements.txt inside the container and runs pip install.

        Args:
            container_id: The container to install into.
            requirements: List of pip requirement specifiers
                (e.g., ["requests>=2.0", "flask"]).

        Returns:
            True if installation succeeded, False otherwise.
        """
        if not requirements:
            return True

        requirements_content = "\n".join(requirements)
        self.write_file(
            container_id, "/tmp/requirements.txt", requirements_content
        )

        result = self._exec_in_container(
            container_id,
            ["pip", "install", "--no-cache-dir", "-r", "/tmp/requirements.txt"],
        )
        return result.exit_code == 0

    def install_dependencies_from_file(
        self, container_id: str, requirements_file: Path
    ) -> bool:
        """Install Python dependencies from a local requirements file.

        Copies the requirements file into the container and runs pip install.

        Args:
            container_id: The container to install into.
            requirements_file: Path to a local requirements.txt file.

        Returns:
            True if installation succeeded, False otherwise.

        Raises:
            DockerError: If the requirements file cannot be read.
        """
        try:
            content = requirements_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise DockerError(
                f"Cannot read requirements file {requirements_file}: {exc}"
            ) from exc

        self.write_file(container_id, "/tmp/requirements.txt", content)

        result = self._exec_in_container(
            container_id,
            ["pip", "install", "--no-cache-dir", "-r", "/tmp/requirements.txt"],
        )
        return result.exit_code == 0

    # -----------------------------------------------------------------------
    # Task 1.5.3: Code Execution
    # -----------------------------------------------------------------------

    def run_code(
        self,
        container_id: str,
        code: str,
        entrypoint: str = "main.py",
    ) -> ExecutionResult:
        """Write code to the container workspace and execute it.

        Args:
            container_id: The container to run in.
            code: Python source code to execute.
            entrypoint: Filename for the code file (default: main.py).

        Returns:
            An ExecutionResult with stdout, stderr, exit_code, and duration.
        """
        file_path = f"/workspace/{entrypoint}"
        self.write_file(container_id, file_path, code)
        return self._exec_in_container(
            container_id, ["python", file_path]
        )

    def run_script(
        self, container_id: str, script_path: Path
    ) -> ExecutionResult:
        """Copy a local script into the container and execute it.

        Args:
            container_id: The container to run in.
            script_path: Path to a local Python script.

        Returns:
            An ExecutionResult with stdout, stderr, exit_code, and duration.

        Raises:
            DockerError: If the script file cannot be read.
        """
        try:
            code = script_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DockerError(
                f"Cannot read script file {script_path}: {exc}"
            ) from exc

        file_path = f"/workspace/{script_path.name}"
        self.write_file(container_id, file_path, code)
        return self._exec_in_container(
            container_id, ["python", file_path]
        )

    # -----------------------------------------------------------------------
    # Task 1.5.4: Pytest Execution
    # -----------------------------------------------------------------------

    def run_tests(
        self, container_id: str, test_dir: str = "/workspace"
    ) -> TestResult:
        """Run pytest inside the container with JSON report output.

        Installs pytest and pytest-json-report, runs the test suite, and
        parses the JSON report into a structured TestResult.

        Args:
            container_id: The container to run tests in.
            test_dir: Directory containing test files (default: /workspace).

        Returns:
            A TestResult with aggregated pass/fail/skip counts and failures.
        """
        # Ensure pytest and json-report plugin are installed
        self._exec_in_container(
            container_id,
            [
                "pip",
                "install",
                "--no-cache-dir",
                "pytest",
                "pytest-json-report",
            ],
        )

        report_path = "/tmp/pytest_report.json"
        result = self._exec_in_container(
            container_id,
            [
                "python",
                "-m",
                "pytest",
                test_dir,
                f"--json-report-file={report_path}",
                "--json-report",
                "-v",
            ],
        )

        # Try to read and parse the JSON report
        try:
            report_content = self.read_file(container_id, report_path)
            report = json.loads(report_content)
            return self._parse_pytest_report(report)
        except (DockerError, json.JSONDecodeError, KeyError):
            # Fallback: derive results from exit code
            return TestResult(
                total=0,
                passed=0,
                failed=1 if result.exit_code != 0 else 0,
                skipped=0,
                errors=1 if result.exit_code != 0 else 0,
                duration=result.duration_ms / 1000.0,
                failures=[
                    TestFailure(
                        name="<unknown>",
                        traceback=result.stderr or result.stdout,
                    )
                ]
                if result.exit_code != 0
                else [],
            )

    @staticmethod
    def _parse_pytest_report(report: dict[str, Any]) -> TestResult:
        """Parse a pytest-json-report JSON report into a TestResult.

        Args:
            report: Parsed JSON report dictionary.

        Returns:
            A structured TestResult.
        """
        summary = report.get("summary", {})
        duration = report.get("duration", 0.0)

        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        errors = summary.get("error", 0)

        failures: list[TestFailure] = []
        for test in report.get("tests", []):
            if test.get("outcome") in ("failed", "error"):
                call_info = test.get("call", {})
                crash = call_info.get("crash", {})
                longrepr = call_info.get("longrepr", "")
                name = test.get("nodeid", "<unknown>")
                tb = longrepr if longrepr else crash.get("message", "")
                failures.append(TestFailure(name=name, traceback=str(tb)))

        return TestResult(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration=duration,
            failures=failures,
        )

    # -----------------------------------------------------------------------
    # Task 1.5.5: File System Operations
    # -----------------------------------------------------------------------

    def write_file(
        self, container_id: str, path: str, content: str
    ) -> None:
        """Write a file inside the container.

        Args:
            container_id: The container to write to.
            path: Absolute path inside the container.
            content: File content as a string.

        Raises:
            DockerError: If the file cannot be written.
        """
        # Use shell to write content via heredoc-style echo
        escaped = content.replace("'", "'\\''")
        cmd = f"sh -c 'mkdir -p $(dirname {path}) && printf \"%s\" '\"'\"'{escaped}'\"'\"' > {path}'"
        self._exec_raw(container_id, cmd)

    def read_file(self, container_id: str, path: str) -> str:
        """Read a file from inside the container.

        Args:
            container_id: The container to read from.
            path: Absolute path inside the container.

        Returns:
            The file content as a string.

        Raises:
            DockerError: If the file cannot be read.
        """
        result = self._exec_in_container(
            container_id, ["cat", path]
        )
        if result.exit_code != 0:
            raise DockerError(
                f"Failed to read file {path}: {result.stderr}"
            )
        return result.stdout

    def list_files(
        self, container_id: str, path: str = "/workspace"
    ) -> list[str]:
        """List files in a directory inside the container.

        Args:
            container_id: The container to list files from.
            path: Directory path inside the container.

        Returns:
            A list of file/directory names.

        Raises:
            DockerError: If the directory cannot be listed.
        """
        result = self._exec_in_container(
            container_id, ["find", path, "-type", "f", "-name", "*.py"]
        )
        if result.exit_code != 0:
            raise DockerError(
                f"Failed to list files in {path}: {result.stderr}"
            )
        files = [
            line.strip()
            for line in result.stdout.strip().split("\n")
            if line.strip()
        ]
        return files

    # -----------------------------------------------------------------------
    # Task 1.5.6: Cleanup and Context Manager
    # -----------------------------------------------------------------------

    def __enter__(self) -> DockerSandbox:
        """Enter context manager – returns self."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager – stop all active containers."""
        self.cleanup(force=True)

    def cleanup(self, force: bool = False) -> None:
        """Remove all ZeroRepo sandbox containers.

        If force is True, removes ALL containers with the ZeroRepo label,
        not just those tracked by this instance.

        Args:
            force: If True, remove all labeled containers system-wide.
        """
        if force:
            try:
                containers = self.client.containers.list(
                    all=True,
                    filters={"label": self.LABEL},
                )
                for container in containers:
                    try:
                        container.stop(timeout=5)
                        container.remove(force=True)
                    except (APIError, NotFound):
                        pass  # Already gone or can't be stopped
            except DockerException:
                pass  # Docker daemon unreachable – nothing we can do

        # Clean up tracked containers
        for cid in list(self._active_containers):
            try:
                self.stop(cid)
            except DockerError:
                pass

        self._active_containers.clear()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _exec_in_container(
        self, container_id: str, cmd: list[str]
    ) -> ExecutionResult:
        """Execute a command inside a running container.

        Args:
            container_id: The container to execute in.
            cmd: Command and arguments as a list.

        Returns:
            An ExecutionResult capturing stdout, stderr, exit code, and
            duration.

        Raises:
            DockerError: If the execution fails at the Docker API level.
        """
        start_time = time.monotonic()
        try:
            container = self.client.containers.get(container_id)
            exit_code, output = container.exec_run(
                cmd, demux=True, workdir="/workspace"
            )
        except NotFound as exc:
            raise DockerError(
                f"Container {container_id} not found"
            ) from exc
        except (APIError, ContainerError, DockerException) as exc:
            raise DockerError(
                f"Execution failed in container {container_id}: {exc}"
            ) from exc

        elapsed_ms = (time.monotonic() - start_time) * 1000.0

        stdout = ""
        stderr = ""
        if output is not None:
            if isinstance(output, tuple):
                stdout = (output[0] or b"").decode("utf-8", errors="replace")
                stderr = (output[1] or b"").decode("utf-8", errors="replace")
            elif isinstance(output, bytes):
                stdout = output.decode("utf-8", errors="replace")

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=elapsed_ms,
        )

    def _exec_raw(self, container_id: str, cmd: str) -> ExecutionResult:
        """Execute a raw shell command string inside a container.

        Args:
            container_id: The container to execute in.
            cmd: Shell command string.

        Returns:
            An ExecutionResult.
        """
        return self._exec_in_container(
            container_id, ["sh", "-c", cmd]
        )

    def _force_remove(self, container_id: str) -> None:
        """Force-remove a container without raising errors.

        Args:
            container_id: The container to remove.
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
        except (NotFound, APIError, DockerException):
            pass
        finally:
            if container_id in self._active_containers:
                self._active_containers.remove(container_id)
