"""Data models for the Docker Sandbox module."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


@dataclass
class ExecutionResult:
    """Result of executing code or a script inside the sandbox.

    Attributes:
        stdout: Standard output captured from execution.
        stderr: Standard error captured from execution.
        exit_code: Process exit code (0 = success).
        duration_ms: Execution duration in milliseconds.
    """

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float


@dataclass
class TestFailure:
    """Details of a single test failure.

    Attributes:
        name: Fully qualified test name (e.g., test_module::test_func).
        traceback: Full traceback string from the failure.
    """

    name: str
    traceback: str


@dataclass
class TestResult:
    """Aggregated result of running pytest inside the sandbox.

    Attributes:
        total: Total number of tests collected.
        passed: Number of tests that passed.
        failed: Number of tests that failed.
        skipped: Number of tests that were skipped.
        errors: Number of tests that errored (collection or runtime).
        duration: Total test suite duration in seconds.
        failures: Detailed information about each failure.
    """

    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    failures: list[TestFailure] = field(default_factory=list)


class SandboxConfig(BaseModel):
    """Configuration for a Docker sandbox instance.

    Attributes:
        image: Docker image to use for the sandbox container.
        memory_limit: Memory limit string (e.g., '512m', '1g').
        cpu_count: Number of CPU cores to allocate.
        timeout: Default timeout in seconds for operations.
    """

    image: str = Field(
        default="python:3.11-slim",
        description="Docker image to use for the sandbox container",
    )
    memory_limit: str = Field(
        default="512m",
        description="Memory limit for the container (e.g., '512m', '1g')",
    )
    cpu_count: int = Field(
        default=1,
        ge=1,
        le=8,
        description="Number of CPU cores to allocate",
    )
    timeout: int = Field(
        default=300,
        ge=1,
        description="Default timeout in seconds for operations",
    )
