"""Data models and enumerations for the LLM Gateway module."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ModelTier(str, Enum):
    """Tiered classification for model selection.

    CHEAP: Fast, low-cost models for simple tasks.
    MEDIUM: Balanced models for general-purpose tasks.
    STRONG: High-quality models for complex reasoning.
    """

    CHEAP = "CHEAP"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


# ---------------------------------------------------------------------------
# Default tier-to-model mapping
# ---------------------------------------------------------------------------

DEFAULT_TIER_MODELS: dict[ModelTier, dict[str, str]] = {
    ModelTier.CHEAP: {
        "openai": "gpt-5.2",
        "anthropic": "claude-3-haiku-20240307",
        "ollama": "ollama/llama3.2",
    },
    ModelTier.MEDIUM: {
        "openai": "gpt-5.2",
        "anthropic": "claude-3-5-sonnet-20241022",
        "ollama": "ollama/llama3.2",
    },
    ModelTier.STRONG: {
        "openai": "gpt-5.2",
        "anthropic": "claude-sonnet-4-20250514",
        "ollama": "ollama/llama3.2",
    },
}

# Ordered list of providers used as fallback priority.
PROVIDER_PRIORITY: list[str] = ["openai", "anthropic", "ollama"]

# ---------------------------------------------------------------------------
# Token pricing table (approximate USD per 1 M tokens)
# ---------------------------------------------------------------------------

TOKEN_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.2": {"input": 2.00, "output": 8.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
}


# ---------------------------------------------------------------------------
# Request / Response log entry
# ---------------------------------------------------------------------------


class LLMLogEntry(BaseModel):
    """Structured log entry for a single LLM request/response cycle."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="ISO 8601 timestamp of the request",
    )
    request_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this request",
    )
    model: str = Field(..., description="Model identifier used for the request")
    tier: Optional[ModelTier] = Field(
        default=None,
        description="Model tier used for this request",
    )
    messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Request messages (truncated if >1000 chars)",
    )
    response: str = Field(
        default="",
        description="Response text (truncated if >1000 chars)",
    )
    tokens_prompt: int = Field(default=0, description="Prompt token count")
    tokens_completion: int = Field(default=0, description="Completion token count")
    tokens_total: int = Field(default=0, description="Total token count")
    latency_ms: float = Field(default=0.0, description="Request latency in ms")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")


# ---------------------------------------------------------------------------
# Gateway configuration
# ---------------------------------------------------------------------------


class GatewayConfig(BaseModel):
    """Configuration for the LLM Gateway."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    tier_models: dict[ModelTier, dict[str, str]] = Field(
        default_factory=lambda: dict(DEFAULT_TIER_MODELS),
        description="Mapping of tier → provider → model name",
    )
    max_retries: int = Field(
        default=4,
        ge=0,
        le=10,
        description="Maximum retry attempts on transient errors",
    )
    base_retry_delay: float = Field(
        default=1.0,
        gt=0,
        description="Base delay in seconds for exponential backoff",
    )
    default_provider: str = Field(
        default="openai",
        description="Default LLM provider when none specified",
    )
