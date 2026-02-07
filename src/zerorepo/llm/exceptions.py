"""Custom exceptions for the LLM Gateway module."""

from __future__ import annotations


class LLMGatewayError(Exception):
    """Base exception for all LLM Gateway errors."""


class ConfigurationError(LLMGatewayError):
    """Raised when the LLM Gateway is misconfigured.

    Examples: missing API keys, invalid model names, bad provider config.
    """


class RetryExhaustedError(LLMGatewayError):
    """Raised when all retry attempts have been exhausted.

    Attributes:
        attempts: Number of retry attempts made.
        last_error: The last error encountered before giving up.
    """

    def __init__(self, attempts: int, last_error: Exception) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"All {attempts} retry attempts exhausted. "
            f"Last error: {last_error}"
        )


class TemplateError(LLMGatewayError):
    """Raised when a prompt template cannot be rendered.

    Examples: missing variables, invalid template syntax, template not found.
    """
