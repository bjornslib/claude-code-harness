"""LLM Gateway – unified interface for multi-provider LLM access via LiteLLM.

This module implements the complete LLM Gateway (Epic 1.3) with:
- Multi-provider completion via LiteLLM (Task 1.3.1)
- Tiered model selection (Task 1.3.2)
- Request/response logging (Task 1.3.3)
- Token usage tracking (Task 1.3.4)
- Retry logic with exponential backoff (Task 1.3.5)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional, Type
from uuid import uuid4

from pydantic import BaseModel

from zerorepo.llm.exceptions import (
    ConfigurationError,
    RetryExhaustedError,
)
from zerorepo.llm.models import (
    DEFAULT_TIER_MODELS,
    PROVIDER_PRIORITY,
    TOKEN_PRICING,
    GatewayConfig,
    LLMLogEntry,
    ModelTier,
)
from zerorepo.llm.token_tracker import TokenTracker

# ---------------------------------------------------------------------------
# LiteLLM imports (lazy so tests can mock at module level)
# ---------------------------------------------------------------------------
try:
    import litellm
    from litellm import completion as litellm_completion
    from litellm.exceptions import (
        APIConnectionError as LiteLLMAPIConnectionError,
        AuthenticationError as LiteLLMAuthenticationError,
        BadRequestError as LiteLLMBadRequestError,
        RateLimitError as LiteLLMRateLimitError,
    )

    _LITELLM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LITELLM_AVAILABLE = False

# Errors that should trigger a retry
_RETRYABLE_ERRORS: tuple[type[Exception], ...] = ()
_NON_RETRYABLE_ERRORS: tuple[type[Exception], ...] = ()
if _LITELLM_AVAILABLE:
    _RETRYABLE_ERRORS = (
        LiteLLMRateLimitError,
        LiteLLMAPIConnectionError,
        TimeoutError,
    )
    _NON_RETRYABLE_ERRORS = (
        LiteLLMAuthenticationError,
        LiteLLMBadRequestError,
    )

# Maximum truncation length for logged messages / responses.
_LOG_TRUNCATE_LEN = 1000


def _truncate(text: str, max_len: int = _LOG_TRUNCATE_LEN) -> str:
    """Truncate text to *max_len* characters, appending '…' if clipped."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _truncate_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a copy of *messages* with ``content`` values truncated."""
    truncated: list[dict[str, Any]] = []
    for msg in messages:
        entry = dict(msg)
        if isinstance(entry.get("content"), str):
            entry["content"] = _truncate(entry["content"])
        truncated.append(entry)
    return truncated


# ---------------------------------------------------------------------------
# Supported model validation set
# ---------------------------------------------------------------------------

SUPPORTED_MODELS: set[str] = {
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-haiku-20240307",
    "claude-3-5-sonnet-20241022",
    "claude-sonnet-4-20250514",
    "ollama/llama3.2",
}


def _estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate the USD cost for a request."""
    pricing = TOKEN_PRICING.get(model)
    if pricing is None:
        return 0.0
    return (
        (prompt_tokens / 1_000_000) * pricing["input"]
        + (completion_tokens / 1_000_000) * pricing["output"]
    )


class LLMGateway:
    """Unified LLM interface with tiered selection, retry, logging, and tracking.

    Example::

        gw = LLMGateway()
        response = gw.complete(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gpt-4o-mini",
        )

    For structured output::

        class Answer(BaseModel):
            answer: str

        result = gw.complete_json(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            model="gpt-4o-mini",
            response_schema=Answer,
        )
    """

    def __init__(self, config: GatewayConfig | None = None) -> None:
        if not _LITELLM_AVAILABLE:
            raise ConfigurationError(
                "litellm is not installed. Run: pip install litellm"
            )
        self._config = config or GatewayConfig()
        self._tracker = TokenTracker()
        self._logs: list[LLMLogEntry] = []

        # Suppress litellm's own verbose logging by default
        litellm.suppress_debug_info = True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tracker(self) -> TokenTracker:
        """Access the token usage tracker."""
        return self._tracker

    @property
    def logs(self) -> list[LLMLogEntry]:
        """Access the request/response log."""
        return list(self._logs)

    # ------------------------------------------------------------------
    # Model selection (Task 1.3.2)
    # ------------------------------------------------------------------

    def select_model(
        self,
        tier: ModelTier,
        provider_preference: str | None = None,
    ) -> str:
        """Select a model name based on tier and optional provider preference.

        Args:
            tier: The model tier (CHEAP, MEDIUM, STRONG).
            provider_preference: Preferred provider name (e.g. ``"openai"``).
                If unavailable, falls back to the cheapest available provider.

        Returns:
            A model identifier string (e.g. ``"gpt-4o-mini"``).

        Raises:
            ConfigurationError: If no model can be found for the given tier.
        """
        tier_mapping = self._config.tier_models.get(tier, {})

        # Try the preferred provider first
        if provider_preference and provider_preference in tier_mapping:
            return tier_mapping[provider_preference]

        # Fall back through provider priority
        for provider in PROVIDER_PRIORITY:
            if provider in tier_mapping:
                return tier_mapping[provider]

        raise ConfigurationError(
            f"No model configured for tier={tier.value}"
        )

    # ------------------------------------------------------------------
    # Completion (Task 1.3.1 + 1.3.5 retry)
    # ------------------------------------------------------------------

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tier: ModelTier | None = None,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request and return the response text.

        Transparently retries on transient errors (rate limits, timeouts,
        connection errors) with exponential backoff.

        Args:
            messages: A list of chat messages (``{"role": …, "content": …}``).
            model: The model identifier (e.g. ``"gpt-4o-mini"``).
            tier: Optional tier for logging purposes.
            **kwargs: Additional keyword arguments forwarded to ``litellm.completion()``.

        Returns:
            The assistant's response text.

        Raises:
            ConfigurationError: If the model is not supported.
            RetryExhaustedError: If all retry attempts are exhausted.
        """
        if model not in SUPPORTED_MODELS:
            raise ConfigurationError(f"Unsupported model: {model!r}")

        request_id = uuid4()
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                response = litellm_completion(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
                elapsed_ms = (time.monotonic() - start) * 1000

                # Extract response text
                text = response.choices[0].message.content or ""

                # Extract token usage
                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                total_tokens = usage.total_tokens if usage else 0

                # Record usage (Task 1.3.4)
                self._tracker.record(model, prompt_tokens, completion_tokens)

                # Estimate cost
                cost = _estimate_cost(model, prompt_tokens, completion_tokens)

                # Log entry (Task 1.3.3)
                log_entry = LLMLogEntry(
                    request_id=request_id,
                    model=model,
                    tier=tier,
                    messages=_truncate_messages(messages),
                    response=_truncate(text),
                    tokens_prompt=prompt_tokens,
                    tokens_completion=completion_tokens,
                    tokens_total=total_tokens,
                    latency_ms=elapsed_ms,
                    cost_usd=cost,
                )
                self._logs.append(log_entry)

                return text

            except _NON_RETRYABLE_ERRORS:
                # Re-raise immediately – do NOT retry authentication /
                # invalid-request errors.
                raise

            except _RETRYABLE_ERRORS as exc:
                last_error = exc
                if attempt < self._config.max_retries:
                    delay = self._config.base_retry_delay * (2 ** attempt)
                    time.sleep(delay)

        # All retries exhausted
        assert last_error is not None
        raise RetryExhaustedError(
            attempts=self._config.max_retries + 1,
            last_error=last_error,
        )

    def complete_json(
        self,
        messages: list[dict[str, Any]],
        model: str,
        response_schema: Type[BaseModel],
        tier: ModelTier | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        """Send a chat completion and parse the response into a Pydantic model.

        This uses LiteLLM's JSON-mode or function-calling to ensure a
        structured response that conforms to *response_schema*.

        Args:
            messages: Chat messages.
            model: Model identifier.
            response_schema: Pydantic model class for the expected response.
            tier: Optional tier for logging.
            **kwargs: Extra keyword arguments forwarded to ``complete()``.

        Returns:
            An instance of *response_schema* populated from the LLM response.

        Raises:
            ConfigurationError: If the model is not supported.
            RetryExhaustedError: If retries are exhausted.
            pydantic.ValidationError: If the response doesn't match the schema.
        """
        # Append schema instruction to the messages
        schema_json = json.dumps(
            response_schema.model_json_schema(), indent=2
        )
        augmented_messages = list(messages) + [
            {
                "role": "user",
                "content": (
                    f"Respond ONLY with valid JSON matching this schema:\n"
                    f"```json\n{schema_json}\n```"
                ),
            }
        ]

        # Request JSON mode via response_format
        kwargs.setdefault("response_format", {"type": "json_object"})

        text = self.complete(
            messages=augmented_messages,
            model=model,
            tier=tier,
            **kwargs,
        )

        # Parse into schema
        return response_schema.model_validate_json(text)

    # ------------------------------------------------------------------
    # Log retrieval (Task 1.3.3)
    # ------------------------------------------------------------------

    def get_logs(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[LLMLogEntry]:
        """Return log entries optionally filtered by time range.

        Args:
            start_time: Inclusive lower bound (UTC).
            end_time: Inclusive upper bound (UTC).

        Returns:
            List of log entries within the time range.
        """
        result: list[LLMLogEntry] = []
        for entry in self._logs:
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
            result.append(entry)
        return result
