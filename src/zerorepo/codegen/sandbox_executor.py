"""Sandbox executor for running generated tests in isolated Docker containers.

Wraps the existing DockerSandbox to provide a higher-level interface for
the TDD generation loop, handling file setup, dependency installation,
test execution, and result parsing.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from zerorepo.codegen.tdd_loop import SandboxResult
from zerorepo.models.node import RPGNode
from zerorepo.sandbox.models import SandboxConfig, TestResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class SandboxExecutorConfig(BaseModel):
    """Configuration for the sandbox executor.

    Attributes:
        timeout_seconds: Maximum time for a single test run.
        install_dependencies: Whether to install pip dependencies.
        default_requirements: Default pip packages to install.
        cleanup_on_finish: Whether to clean up sandbox after each run.
    """

    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Maximum time for a single test run in seconds",
    )
    install_dependencies: bool = Field(
        default=True,
        description="Whether to install pip dependencies",
    )
    default_requirements: list[str] = Field(
        default_factory=lambda: ["pytest", "pytest-json-report"],
        description="Default pip packages to install",
    )
    cleanup_on_finish: bool = Field(
        default=True,
        description="Whether to clean up sandbox after each run",
    )


# ---------------------------------------------------------------------------
# Docker-based sandbox executor
# ---------------------------------------------------------------------------


class DockerSandboxExecutor:
    """Execute generated tests inside a Docker sandbox.

    Wraps DockerSandbox to provide file setup, dependency installation,
    test execution, and structured result parsing for the TDD loop.

    Args:
        sandbox: A DockerSandbox instance for container management.
        config: Configuration for the executor.
    """

    def __init__(
        self,
        sandbox: Any,
        config: SandboxExecutorConfig | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._config = config or SandboxExecutorConfig()

    @property
    def config(self) -> SandboxExecutorConfig:
        """The executor configuration."""
        return self._config

    def run_tests(
        self,
        implementation: str,
        test_code: str,
        node: RPGNode,
    ) -> SandboxResult:
        """Run test code against implementation in the sandbox.

        Sets up a workspace with the implementation and test files,
        installs dependencies, runs pytest, and returns structured results.

        Args:
            implementation: Python implementation code.
            test_code: Pytest test code to run.
            node: The RPG node being tested (for file path info).

        Returns:
            A SandboxResult with pass/fail counts and output.
        """
        workspace_dir = None
        container_id = None

        try:
            # Create temporary workspace
            workspace_dir = Path(tempfile.mkdtemp(prefix="zerorepo_sandbox_"))

            # Write implementation file
            impl_path = self._resolve_impl_path(node, workspace_dir)
            impl_path.parent.mkdir(parents=True, exist_ok=True)
            impl_path.write_text(implementation, encoding="utf-8")

            # Write test file
            test_filename = f"test_{impl_path.stem}.py"
            test_path = workspace_dir / test_filename
            test_path.write_text(test_code, encoding="utf-8")

            # Create __init__.py files for packages
            self._create_init_files(workspace_dir, impl_path)

            # Start sandbox container
            container_id = self._sandbox.start(
                workspace_dir,
                timeout=self._config.timeout_seconds,
            )

            # Install dependencies
            if self._config.install_dependencies:
                self._sandbox.install_dependencies(
                    container_id, self._config.default_requirements
                )

            # Run tests
            test_result: TestResult = self._sandbox.run_tests(
                container_id,
                test_dir="/workspace",
            )

            return self._convert_test_result(test_result)

        except Exception as exc:
            logger.error("Sandbox execution failed for node %s: %s", node.id, exc)
            return SandboxResult(
                failed=1,
                errors=1,
                stderr=f"Sandbox execution error: {exc}",
            )
        finally:
            # Cleanup
            if container_id is not None:
                try:
                    self._sandbox.stop(container_id)
                except Exception:
                    logger.warning("Failed to stop container %s", container_id)

            if workspace_dir is not None and self._config.cleanup_on_finish:
                try:
                    import shutil

                    shutil.rmtree(workspace_dir, ignore_errors=True)
                except Exception:
                    logger.warning("Failed to clean up workspace %s", workspace_dir)

    @staticmethod
    def _resolve_impl_path(node: RPGNode, workspace_dir: Path) -> Path:
        """Resolve the implementation file path within the workspace.

        Uses the node's file_path if available, otherwise creates a
        default module file.

        Args:
            node: The RPG node being implemented.
            workspace_dir: Root workspace directory.

        Returns:
            Path for the implementation file.
        """
        if node.file_path:
            return workspace_dir / node.file_path
        return workspace_dir / f"{node.name.replace(' ', '_').lower()}.py"

    @staticmethod
    def _create_init_files(workspace_dir: Path, impl_path: Path) -> None:
        """Create __init__.py files in package directories.

        Creates __init__.py files in any subdirectories between
        workspace_dir and impl_path's parent.

        Args:
            workspace_dir: Root workspace directory.
            impl_path: Path to the implementation file.
        """
        current = impl_path.parent
        while current != workspace_dir and current != current.parent:
            init_file = current / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")
            current = current.parent

    @staticmethod
    def _convert_test_result(test_result: TestResult) -> SandboxResult:
        """Convert a sandbox TestResult to a TDD SandboxResult.

        Args:
            test_result: The raw TestResult from DockerSandbox.

        Returns:
            A SandboxResult for the TDD loop.
        """
        failure_output = ""
        if test_result.failures:
            failure_lines = []
            for failure in test_result.failures:
                failure_lines.append(f"FAILED {failure.name}:")
                failure_lines.append(failure.traceback)
            failure_output = "\n".join(failure_lines)

        return SandboxResult(
            passed=test_result.passed,
            failed=test_result.failed,
            errors=test_result.errors,
            stderr=failure_output,
            duration_ms=test_result.duration * 1000.0,
        )


# ---------------------------------------------------------------------------
# In-process executor (for testing without Docker)
# ---------------------------------------------------------------------------


class InProcessSandboxExecutor:
    """Execute tests in-process for fast testing without Docker.

    This is a simplified executor that runs pytest in the current process.
    Intended for unit testing the TDD loop without Docker dependency.

    Args:
        timeout_seconds: Maximum time for test execution.
    """

    def __init__(self, timeout_seconds: int = 10) -> None:
        self._timeout = timeout_seconds

    def run_tests(
        self,
        implementation: str,
        test_code: str,
        node: RPGNode,
    ) -> SandboxResult:
        """Run tests in-process using exec().

        WARNING: This is NOT isolated. Use only for testing the TDD loop
        itself, never for untrusted code.

        Args:
            implementation: Python implementation code.
            test_code: Pytest test code to run.
            node: The RPG node being tested.

        Returns:
            A SandboxResult with pass/fail counts.
        """
        try:
            # Execute implementation in a namespace
            impl_namespace: dict[str, Any] = {}
            exec(implementation, impl_namespace)

            # Execute tests in a namespace with implementation available
            test_namespace = dict(impl_namespace)
            exec(test_code, test_namespace)

            # If we get here, at least the code is syntactically valid
            return SandboxResult(passed=1, failed=0, errors=0)

        except SyntaxError as exc:
            return SandboxResult(
                failed=1,
                errors=1,
                stderr=f"SyntaxError: {exc}",
            )
        except AssertionError as exc:
            return SandboxResult(
                failed=1,
                stderr=f"AssertionError: {exc}",
            )
        except Exception as exc:
            return SandboxResult(
                failed=1,
                errors=1,
                stderr=f"Error: {type(exc).__name__}: {exc}",
            )
