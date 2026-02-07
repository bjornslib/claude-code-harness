"""Stage 3: Execution testing in isolated Docker sandbox.

Adapts ground-truth tests to work with generated repository code
and executes them in isolated Docker containers.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional, Protocol

from zerorepo.evaluation.models import BenchmarkTask, ExecutionResult

logger = logging.getLogger(__name__)


class SandboxProtocol(Protocol):
    """Protocol for sandbox execution. Compatible with DockerSandbox."""

    def start(self, workspace_dir: Path, timeout: int | None = None) -> str: ...

    def write_file(
        self, container_id: str, path: str, content: str
    ) -> None: ...

    def run_code(
        self, container_id: str, code: str, entrypoint: str = "main.py"
    ) -> Any: ...

    def run_tests(
        self, container_id: str, test_dir: str = "/workspace"
    ) -> Any: ...

    def stop(self, container_id: str) -> None: ...

    def install_dependencies(
        self, container_id: str, requirements: list[str]
    ) -> bool: ...


class ExecutionTester:
    """Executes ground-truth tests against generated code in Docker sandbox."""

    def __init__(
        self,
        sandbox: SandboxProtocol | None = None,
        timeout: int = 30,
        default_dependencies: list[str] | None = None,
    ):
        self._sandbox = sandbox
        self.timeout = timeout
        self.default_dependencies = default_dependencies or ["pytest", "numpy"]

    @property
    def sandbox(self) -> SandboxProtocol:
        """Get or create sandbox instance."""
        if self._sandbox is None:
            from zerorepo.sandbox.sandbox import DockerSandbox

            self._sandbox = DockerSandbox()
        return self._sandbox

    def adapt_test(
        self,
        task: BenchmarkTask,
        repo_path: str | Path,
        import_mapping: dict[str, str] | None = None,
    ) -> str:
        """Adapt ground-truth test to use generated repo's import structure.

        Rewrites import statements to map from reference repo (e.g., sklearn)
        to the generated repo's module structure.
        """
        import_mapping = import_mapping or {}

        # Start with task imports
        adapted_imports = []
        for imp in task.imports:
            adapted = imp
            for old, new in import_mapping.items():
                adapted = adapted.replace(old, new)
            adapted_imports.append(adapted)

        # Build complete test file
        test_code = f'''"""Adapted test for task: {task.id}"""
import sys
sys.path.insert(0, "/workspace/repo")

{chr(10).join(adapted_imports)}

{task.auxiliary_code}

{task.test_code}

if __name__ == "__main__":
    # Extract test function name and call it
    import inspect
    test_funcs = [
        name for name, obj in locals().items()
        if callable(obj) and name.startswith("test_")
    ]

    all_passed = True
    for func_name in test_funcs:
        try:
            locals()[func_name]()
            print(f"PASSED: {{func_name}}")
        except Exception as e:
            print(f"FAILED: {{func_name}}: {{e}}")
            all_passed = False

    if all_passed:
        print("TEST_PASSED")
    else:
        print("TEST_FAILED")
        sys.exit(1)
'''
        return test_code

    def execute_test(
        self,
        task: BenchmarkTask,
        repo_path: str | Path,
        import_mapping: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Run adapted test in Docker sandbox.

        1. Copy repo to temp workspace
        2. Write adapted test
        3. Execute in container
        4. Parse results
        """
        repo_path = Path(repo_path)
        adapted_test = self.adapt_test(task, repo_path, import_mapping)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Copy repo
            repo_dest = tmpdir_path / "repo"
            if repo_path.exists():
                shutil.copytree(repo_path, repo_dest, dirs_exist_ok=True)
            else:
                repo_dest.mkdir(parents=True)

            # Write test file
            test_file = tmpdir_path / "test_adapted.py"
            test_file.write_text(adapted_test)

            try:
                container_id = self.sandbox.start(
                    tmpdir_path, timeout=self.timeout
                )

                try:
                    # Install dependencies
                    deps = list(self.default_dependencies)
                    # Extract additional deps from imports
                    for imp in task.imports:
                        pkg = self._extract_package_name(imp)
                        if pkg and pkg not in deps:
                            deps.append(pkg)

                    self.sandbox.install_dependencies(container_id, deps)

                    # Run test
                    result = self.sandbox.run_code(
                        container_id,
                        adapted_test,
                        entrypoint="test_adapted.py",
                    )

                    stdout = getattr(result, "stdout", str(result))
                    stderr = getattr(result, "stderr", "")
                    exit_code = getattr(result, "exit_code", -1)
                    duration = getattr(result, "duration_ms", 0.0)

                    passed = "TEST_PASSED" in stdout and exit_code == 0

                    return ExecutionResult(
                        passed=passed,
                        exit_code=exit_code,
                        stdout=stdout,
                        stderr=stderr,
                        error=None if passed else (stderr or stdout),
                        duration_ms=duration,
                    )

                finally:
                    self.sandbox.stop(container_id)

            except Exception as e:
                logger.error(f"Execution failed for task {task.id}: {e}")
                return ExecutionResult(
                    passed=False,
                    error=str(e),
                )

    @staticmethod
    def _extract_package_name(import_stmt: str) -> str | None:
        """Extract top-level package from import statement."""
        # "from sklearn.linear_model import Ridge" -> "sklearn"
        # "import numpy as np" -> "numpy"
        match = re.match(r"(?:from\s+(\S+)|import\s+(\S+))", import_stmt)
        if match:
            module = match.group(1) or match.group(2)
            return module.split(".")[0]
        return None
