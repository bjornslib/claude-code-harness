"""Custom exceptions for the Docker Sandbox module."""

from __future__ import annotations


class DockerError(Exception):
    """Base exception for all Docker Sandbox errors.

    Raised when a Docker operation fails unexpectedly.
    """


class SandboxTimeoutError(DockerError):
    """Raised when a sandbox operation exceeds the configured timeout.

    Attributes:
        timeout: The timeout value in seconds that was exceeded.
        operation: Description of the operation that timed out.
    """

    def __init__(self, timeout: int, operation: str = "operation") -> None:
        self.timeout = timeout
        self.operation = operation
        super().__init__(
            f"Sandbox {operation} timed out after {timeout} seconds"
        )
