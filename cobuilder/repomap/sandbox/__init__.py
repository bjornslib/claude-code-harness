"""ZeroRepo Docker Sandbox – isolated container environment for code execution.

This package implements Epic 1.5 of PRD-RPG-P1-001, providing:

- :class:`DockerSandbox` – Container lifecycle, code execution, and test running
- :class:`SandboxConfig` – Configuration for sandbox instances
- :class:`ExecutionResult` – Captured output from code execution
- :class:`TestResult` – Aggregated pytest results
- :class:`TestFailure` – Individual test failure details
"""

from cobuilder.repomap.sandbox.exceptions import DockerError, SandboxTimeoutError
from cobuilder.repomap.sandbox.models import (
    ExecutionResult,
    SandboxConfig,
    TestFailure,
    TestResult,
)
from cobuilder.repomap.sandbox.sandbox import DockerSandbox

__all__ = [
    "DockerError",
    "DockerSandbox",
    "ExecutionResult",
    "SandboxConfig",
    "SandboxTimeoutError",
    "TestFailure",
    "TestResult",
]
