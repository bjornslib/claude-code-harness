"""Unit tests for LLM Gateway data models and enumerations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from cobuilder.repomap.llm.models import (
    DEFAULT_TIER_MODELS,
    TOKEN_PRICING,
    GatewayConfig,
    LLMLogEntry,
    ModelTier,
)


class TestModelTier:
    """Tests for the ModelTier enumeration."""

    def test_tier_values(self) -> None:
        """Verify all expected tier values exist."""
        assert ModelTier.CHEAP == "CHEAP"
        assert ModelTier.MEDIUM == "MEDIUM"
        assert ModelTier.STRONG == "STRONG"

    def test_tier_from_string(self) -> None:
        """Verify tiers can be constructed from strings."""
        assert ModelTier("CHEAP") is ModelTier.CHEAP
        assert ModelTier("MEDIUM") is ModelTier.MEDIUM
        assert ModelTier("STRONG") is ModelTier.STRONG

    def test_tier_invalid_string(self) -> None:
        """Invalid tier string raises ValueError."""
        with pytest.raises(ValueError):
            ModelTier("INVALID")

    def test_tier_is_string_subclass(self) -> None:
        """ModelTier values are string-compatible."""
        assert isinstance(ModelTier.CHEAP, str)


class TestDefaultTierModels:
    """Tests for the default tier-to-model mapping."""

    def test_all_tiers_have_mappings(self) -> None:
        """Every tier must have at least one provider mapping."""
        for tier in ModelTier:
            assert tier in DEFAULT_TIER_MODELS
            assert len(DEFAULT_TIER_MODELS[tier]) > 0

    def test_cheap_tier_has_openai(self) -> None:
        assert "openai" in DEFAULT_TIER_MODELS[ModelTier.CHEAP]
        assert DEFAULT_TIER_MODELS[ModelTier.CHEAP]["openai"] == "gpt-5.2"

    def test_cheap_tier_has_anthropic(self) -> None:
        assert "anthropic" in DEFAULT_TIER_MODELS[ModelTier.CHEAP]
        assert "claude-3-haiku" in DEFAULT_TIER_MODELS[ModelTier.CHEAP]["anthropic"]

    def test_medium_tier_has_openai(self) -> None:
        assert DEFAULT_TIER_MODELS[ModelTier.MEDIUM]["openai"] == "gpt-5.2"

    def test_medium_tier_has_anthropic(self) -> None:
        assert "claude-3-5-sonnet" in DEFAULT_TIER_MODELS[ModelTier.MEDIUM]["anthropic"]

    def test_strong_tier_exists(self) -> None:
        assert ModelTier.STRONG in DEFAULT_TIER_MODELS


class TestTokenPricing:
    """Tests for the token pricing table."""

    def test_gpt52_pricing(self) -> None:
        pricing = TOKEN_PRICING["gpt-5.2"]
        assert pricing["input"] == 2.00
        assert pricing["output"] == 8.0

    def test_gpt4o_mini_pricing(self) -> None:
        pricing = TOKEN_PRICING["gpt-4o-mini"]
        assert pricing["input"] == 0.15
        assert pricing["output"] == 0.60

    def test_gpt4o_pricing(self) -> None:
        pricing = TOKEN_PRICING["gpt-4o"]
        assert pricing["input"] == 2.50
        assert pricing["output"] == 10.0

    def test_claude_haiku_pricing(self) -> None:
        pricing = TOKEN_PRICING["claude-3-haiku-20240307"]
        assert pricing["input"] == 0.25
        assert pricing["output"] == 1.25

    def test_claude_sonnet_pricing(self) -> None:
        pricing = TOKEN_PRICING["claude-3-5-sonnet-20241022"]
        assert pricing["input"] == 3.0
        assert pricing["output"] == 15.0

    def test_all_models_have_input_and_output(self) -> None:
        """Every model in the pricing table has both input and output prices."""
        for model, pricing in TOKEN_PRICING.items():
            assert "input" in pricing, f"{model} missing 'input' price"
            assert "output" in pricing, f"{model} missing 'output' price"
            assert pricing["input"] >= 0
            assert pricing["output"] >= 0


class TestLLMLogEntry:
    """Tests for the LLMLogEntry model."""

    def test_create_minimal_entry(self) -> None:
        """Create a log entry with only the required field (model)."""
        entry = LLMLogEntry(model="gpt-4o-mini")
        assert entry.model == "gpt-4o-mini"
        assert isinstance(entry.request_id, UUID)
        assert isinstance(entry.timestamp, datetime)
        assert entry.tokens_prompt == 0
        assert entry.tokens_completion == 0
        assert entry.tokens_total == 0
        assert entry.latency_ms == 0.0
        assert entry.cost_usd == 0.0
        assert entry.response == ""
        assert entry.messages == []
        assert entry.tier is None

    def test_create_full_entry(self) -> None:
        """Create a log entry with all fields populated."""
        entry = LLMLogEntry(
            model="gpt-4o",
            tier=ModelTier.MEDIUM,
            messages=[{"role": "user", "content": "hello"}],
            response="world",
            tokens_prompt=10,
            tokens_completion=5,
            tokens_total=15,
            latency_ms=123.4,
            cost_usd=0.001,
        )
        assert entry.model == "gpt-4o"
        assert entry.tier == ModelTier.MEDIUM
        assert entry.messages == [{"role": "user", "content": "hello"}]
        assert entry.response == "world"
        assert entry.tokens_prompt == 10
        assert entry.tokens_completion == 5
        assert entry.tokens_total == 15
        assert entry.latency_ms == 123.4
        assert entry.cost_usd == 0.001

    def test_entry_is_frozen(self) -> None:
        """LLMLogEntry should be immutable (frozen)."""
        entry = LLMLogEntry(model="gpt-4o-mini")
        with pytest.raises(ValidationError):
            entry.model = "gpt-4o"  # type: ignore[misc]

    def test_entry_timestamp_is_utc(self) -> None:
        """Timestamp should default to UTC."""
        entry = LLMLogEntry(model="gpt-4o-mini")
        assert entry.timestamp.tzinfo is not None


class TestGatewayConfig:
    """Tests for the GatewayConfig model."""

    def test_default_config(self) -> None:
        """Default config should have sensible values."""
        config = GatewayConfig()
        assert config.max_retries == 4
        assert config.base_retry_delay == 1.0
        assert config.default_provider == "openai"
        assert ModelTier.CHEAP in config.tier_models

    def test_custom_config(self) -> None:
        """Create a config with custom values."""
        config = GatewayConfig(
            max_retries=2,
            base_retry_delay=0.5,
            default_provider="anthropic",
        )
        assert config.max_retries == 2
        assert config.base_retry_delay == 0.5
        assert config.default_provider == "anthropic"

    def test_max_retries_validation(self) -> None:
        """max_retries must be within [0, 10]."""
        with pytest.raises(ValidationError):
            GatewayConfig(max_retries=-1)
        with pytest.raises(ValidationError):
            GatewayConfig(max_retries=11)

    def test_base_retry_delay_must_be_positive(self) -> None:
        """base_retry_delay must be > 0."""
        with pytest.raises(ValidationError):
            GatewayConfig(base_retry_delay=0)
        with pytest.raises(ValidationError):
            GatewayConfig(base_retry_delay=-1.0)

    def test_config_is_mutable(self) -> None:
        """GatewayConfig allows assignment updates."""
        config = GatewayConfig()
        config.max_retries = 3
        assert config.max_retries == 3

    def test_custom_tier_models(self) -> None:
        """Override tier models in config."""
        custom = {
            ModelTier.CHEAP: {"openai": "custom-cheap-model"},
        }
        config = GatewayConfig(tier_models=custom)
        assert config.tier_models[ModelTier.CHEAP]["openai"] == "custom-cheap-model"
