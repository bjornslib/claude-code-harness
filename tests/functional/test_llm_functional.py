"""Functional tests for the LLM Gateway – integration tests across components.

All LiteLLM calls are mocked. These tests verify that the gateway, token tracker,
prompt templates, and logging work together correctly as a cohesive system.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from zerorepo.llm.exceptions import (
    ConfigurationError,
    RetryExhaustedError,
    TemplateError,
)
from zerorepo.llm.models import (
    DEFAULT_TIER_MODELS,
    TOKEN_PRICING,
    GatewayConfig,
    LLMLogEntry,
    ModelTier,
)
from zerorepo.llm.prompt_templates import PromptTemplate
from zerorepo.llm.token_tracker import TokenTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(
    text: str = "Hello!",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
) -> MagicMock:
    """Build a mock LiteLLM response object."""
    choice = SimpleNamespace(message=SimpleNamespace(content=text))
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


# Pydantic schemas for JSON tests
class FeatureSpec(BaseModel):
    name: str
    complexity: str
    description: str


class ModulePlan(BaseModel):
    module_name: str
    components: list[str]


# ---------------------------------------------------------------------------
# Functional tests: End-to-end gateway workflows
# ---------------------------------------------------------------------------


@pytest.mark.functional
class TestGatewayEndToEnd:
    """Verify complete gateway workflows from model selection → completion → tracking."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_select_then_complete(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """select_model → complete → verify tracking and logging."""
        from zerorepo.llm.gateway import LLMGateway

        mock_completion.return_value = _mock_response(
            text="Feature: login page", prompt_tokens=50, completion_tokens=20
        )
        gw = LLMGateway()

        # Step 1: Select model
        model = gw.select_model(ModelTier.CHEAP, provider_preference="openai")
        assert model == "gpt-4o-mini"

        # Step 2: Complete
        result = gw.complete(
            messages=[{"role": "user", "content": "Describe the login page"}],
            model=model,
            tier=ModelTier.CHEAP,
        )
        assert "Feature" in result

        # Step 3: Verify tracking
        assert gw.tracker.get_total_tokens() == 70  # 50 + 20
        assert gw.tracker.get_total_cost() > 0

        # Step 4: Verify logging
        assert len(gw.logs) == 1
        log = gw.logs[0]
        assert log.model == "gpt-4o-mini"
        assert log.tier == ModelTier.CHEAP
        assert log.tokens_prompt == 50
        assert log.tokens_completion == 20
        assert log.latency_ms >= 0
        assert log.cost_usd > 0

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_multi_model_session(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Multiple completions with different models track independently."""
        from zerorepo.llm.gateway import LLMGateway

        gw = LLMGateway()

        # First call: cheap model
        mock_completion.return_value = _mock_response(
            text="quick answer", prompt_tokens=10, completion_tokens=5
        )
        gw.complete(
            messages=[{"role": "user", "content": "quick question"}],
            model="gpt-4o-mini",
            tier=ModelTier.CHEAP,
        )

        # Second call: strong model
        mock_completion.return_value = _mock_response(
            text="detailed analysis", prompt_tokens=100, completion_tokens=200
        )
        gw.complete(
            messages=[{"role": "user", "content": "complex analysis"}],
            model="gpt-4o",
            tier=ModelTier.STRONG,
        )

        # Verify aggregate tracking
        assert gw.tracker.get_total_tokens() == 315  # 15 + 300

        # Verify per-model breakdown
        breakdown = gw.tracker.get_breakdown_by_model()
        assert "gpt-4o-mini" in breakdown
        assert "gpt-4o" in breakdown
        assert breakdown["gpt-4o-mini"]["total_tokens"] == 15
        assert breakdown["gpt-4o"]["total_tokens"] == 300

        # Verify both logs recorded
        assert len(gw.logs) == 2
        assert gw.logs[0].model == "gpt-4o-mini"
        assert gw.logs[1].model == "gpt-4o"


@pytest.mark.functional
class TestGatewayJsonEndToEnd:
    """Verify JSON structured output end-to-end workflows."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_complete_json_with_complex_schema(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """complete_json parses complex Pydantic models correctly."""
        from zerorepo.llm.gateway import LLMGateway

        json_text = json.dumps({
            "name": "user-authentication",
            "complexity": "HIGH",
            "description": "Full OAuth2 authentication flow",
        })
        mock_completion.return_value = _mock_response(
            text=json_text, prompt_tokens=30, completion_tokens=20
        )
        gw = LLMGateway()
        result = gw.complete_json(
            messages=[{"role": "user", "content": "Extract features"}],
            model="gpt-4o-mini",
            response_schema=FeatureSpec,
            tier=ModelTier.CHEAP,
        )
        assert isinstance(result, FeatureSpec)
        assert result.name == "user-authentication"
        assert result.complexity == "HIGH"

        # Verify tracking and logging still work
        assert gw.tracker.get_total_tokens() == 50
        assert len(gw.logs) == 1

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_json_then_text_completions(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Mixing JSON and text completions in the same session."""
        from zerorepo.llm.gateway import LLMGateway

        gw = LLMGateway()

        # JSON call
        mock_completion.return_value = _mock_response(
            text='{"module_name": "auth", "components": ["login", "signup"]}',
            prompt_tokens=20,
            completion_tokens=15,
        )
        module = gw.complete_json(
            messages=[{"role": "user", "content": "Plan modules"}],
            model="gpt-4o-mini",
            response_schema=ModulePlan,
        )
        assert module.module_name == "auth"

        # Text call
        mock_completion.return_value = _mock_response(
            text="The auth module should use JWT tokens.",
            prompt_tokens=40,
            completion_tokens=30,
        )
        text = gw.complete(
            messages=[{"role": "user", "content": "How should auth work?"}],
            model="gpt-4o",
        )
        assert "JWT" in text

        # Verify both tracked
        assert gw.tracker.get_total_tokens() == 105  # 35 + 70
        assert len(gw.logs) == 2


@pytest.mark.functional
class TestGatewayRetryEndToEnd:
    """Verify retry logic works correctly in integration scenarios."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.time.sleep")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_retry_then_success_tracks_correctly(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Retried request still tracks tokens and logs on eventual success."""
        from zerorepo.llm.gateway import LLMGateway

        mock_completion.side_effect = [
            TimeoutError("first attempt"),
            _mock_response(text="recovered", prompt_tokens=25, completion_tokens=10),
        ]
        cfg = GatewayConfig(max_retries=3, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)

        result = gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert result == "recovered"

        # Token tracking: only successful response is tracked
        assert gw.tracker.get_total_tokens() == 35
        assert len(gw.logs) == 1
        assert gw.logs[0].tokens_prompt == 25

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.time.sleep")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_retry_exhaustion_no_tracking(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Fully exhausted retries leave tracker and logs empty."""
        from zerorepo.llm.gateway import LLMGateway

        mock_completion.side_effect = TimeoutError("always fails")
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)

        with pytest.raises(RetryExhaustedError):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )

        assert gw.tracker.get_total_tokens() == 0
        assert gw.tracker.get_total_cost() == 0.0
        assert len(gw.logs) == 0


@pytest.mark.functional
class TestGatewayLogFilteringEndToEnd:
    """Verify log filtering works with real timestamps in integration."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_filter_logs_by_time_range(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Time-filtered log retrieval returns correct subset."""
        from zerorepo.llm.gateway import LLMGateway

        mock_completion.return_value = _mock_response()
        gw = LLMGateway()

        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        gw.complete(
            messages=[{"role": "user", "content": "first"}],
            model="gpt-4o-mini",
        )
        between = datetime.now(timezone.utc)
        time.sleep(0.01)  # Tiny gap to separate timestamps
        gw.complete(
            messages=[{"role": "user", "content": "second"}],
            model="gpt-4o-mini",
        )
        after = datetime.now(timezone.utc) + timedelta(seconds=1)

        # All logs
        assert len(gw.get_logs()) == 2

        # Only within time range
        filtered = gw.get_logs(start_time=before, end_time=after)
        assert len(filtered) == 2

        # Future start excludes all
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert len(gw.get_logs(start_time=future)) == 0

        # Past end excludes all
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert len(gw.get_logs(end_time=past)) == 0


@pytest.mark.functional
class TestCostTracking:
    """Verify cost tracking accuracy across multiple calls."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_aggregate_cost_accuracy(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Total cost from tracker matches sum of individual log costs."""
        from zerorepo.llm.gateway import LLMGateway

        gw = LLMGateway()

        # Call 1: gpt-4o-mini
        mock_completion.return_value = _mock_response(
            prompt_tokens=1000, completion_tokens=500
        )
        gw.complete(
            messages=[{"role": "user", "content": "q1"}],
            model="gpt-4o-mini",
        )

        # Call 2: gpt-4o
        mock_completion.return_value = _mock_response(
            prompt_tokens=2000, completion_tokens=1000
        )
        gw.complete(
            messages=[{"role": "user", "content": "q2"}],
            model="gpt-4o",
        )

        # Verify tracker matches logs
        log_total_cost = sum(log.cost_usd for log in gw.logs)
        tracker_cost = gw.tracker.get_total_cost()
        assert abs(tracker_cost - log_total_cost) < 0.0001

        # Verify individual costs are reasonable
        # gpt-4o-mini: 1000/1M * 0.15 + 500/1M * 0.60 = 0.00015 + 0.0003 = 0.00045
        # gpt-4o: 2000/1M * 2.50 + 1000/1M * 10.0 = 0.005 + 0.01 = 0.015
        assert gw.logs[0].cost_usd > 0
        assert gw.logs[1].cost_usd > 0
        assert tracker_cost > 0


@pytest.mark.functional
class TestTokenTrackerIntegration:
    """Verify TokenTracker accumulates correctly through gateway calls."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_tracker_reset_mid_session(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Token tracker can be reset mid-session; new calls accumulate fresh."""
        from zerorepo.llm.gateway import LLMGateway

        mock_completion.return_value = _mock_response(
            prompt_tokens=100, completion_tokens=50
        )
        gw = LLMGateway()

        gw.complete(
            messages=[{"role": "user", "content": "q1"}],
            model="gpt-4o-mini",
        )
        assert gw.tracker.get_total_tokens() == 150

        # Reset tracker
        gw.tracker.reset()
        assert gw.tracker.get_total_tokens() == 0

        # New call
        gw.complete(
            messages=[{"role": "user", "content": "q2"}],
            model="gpt-4o-mini",
        )
        assert gw.tracker.get_total_tokens() == 150

        # Logs still contain both entries (logs are NOT reset)
        assert len(gw.logs) == 2


@pytest.mark.functional
class TestPromptTemplateIntegration:
    """Verify prompt templates integrate correctly with the gateway."""

    def test_template_render_then_complete(self) -> None:
        """Render a template, then use its output as a prompt for the gateway."""
        pt = PromptTemplate()
        prompt = pt.render("feature_extraction", spec_text="Build a login page")

        # Verify the prompt is a non-empty string suitable for LLM input
        assert isinstance(prompt, str)
        assert len(prompt) > 50  # Should be a substantial prompt
        assert "login page" in prompt.lower()
        assert "specification" in prompt.lower()

    def test_all_builtin_templates_available(self) -> None:
        """All built-in templates are listed and renderable."""
        pt = PromptTemplate()
        templates = pt.list_templates()
        assert "feature_extraction" in templates
        assert "module_planning" in templates
        assert "function_generation" in templates
        assert len(templates) >= 3

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_template_driven_completion(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Full workflow: render template → select model → complete."""
        from zerorepo.llm.gateway import LLMGateway

        # Step 1: Render template
        pt = PromptTemplate()
        prompt = pt.render("feature_extraction", spec_text="Build a REST API")

        # Step 2: Select model
        gw = LLMGateway()
        model = gw.select_model(ModelTier.CHEAP, provider_preference="openai")

        # Step 3: Complete
        mock_completion.return_value = _mock_response(
            text="Feature: REST API endpoints", prompt_tokens=80, completion_tokens=30
        )
        result = gw.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            tier=ModelTier.CHEAP,
        )

        # Verify end-to-end
        assert "REST API" in result
        assert gw.tracker.get_total_tokens() == 110
        assert len(gw.logs) == 1


@pytest.mark.functional
class TestExceptionPropagation:
    """Verify exceptions propagate correctly through the component stack."""

    def test_unsupported_model_error_message(self) -> None:
        """ConfigurationError contains the offending model name."""
        with patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True), \
             patch("zerorepo.llm.gateway.litellm"):
            from zerorepo.llm.gateway import LLMGateway

            gw = LLMGateway()
            with pytest.raises(ConfigurationError) as exc_info:
                gw.complete(
                    messages=[{"role": "user", "content": "hi"}],
                    model="fake-model-v99",
                )
            assert "fake-model-v99" in str(exc_info.value)

    def test_template_not_found_error(self) -> None:
        """TemplateError when rendering a non-existent template."""
        pt = PromptTemplate()
        with pytest.raises(TemplateError, match="not found"):
            pt.render("this_template_does_not_exist", foo="bar")

    def test_template_missing_variable_error(self, tmp_path: Path) -> None:
        """TemplateError when a required template variable is missing."""
        (tmp_path / "strict.jinja2").write_text("Hello, {{ name }}!")
        pt = PromptTemplate(template_dir=tmp_path)
        with pytest.raises(TemplateError, match="Error rendering"):
            pt.render("strict")  # Missing 'name'


@pytest.mark.functional
class TestGatewayConfigVariations:
    """Verify gateway behaviour under different configurations."""

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_minimal_config(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Gateway works with minimal default config."""
        from zerorepo.llm.gateway import LLMGateway

        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        result = gw.complete(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o-mini",
        )
        assert isinstance(result, str)

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    @patch("zerorepo.llm.gateway.litellm_completion")
    def test_custom_retry_config(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Custom retry settings are respected."""
        from zerorepo.llm.gateway import LLMGateway

        with patch("zerorepo.llm.gateway.time.sleep") as mock_sleep:
            mock_completion.side_effect = TimeoutError("fail")
            cfg = GatewayConfig(max_retries=1, base_retry_delay=0.5)
            gw = LLMGateway(config=cfg)

            with pytest.raises(RetryExhaustedError) as exc_info:
                gw.complete(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-4o-mini",
                )
            assert exc_info.value.attempts == 2  # 1 initial + 1 retry
            mock_sleep.assert_called_once_with(0.5)  # base * 2^0

    @patch("zerorepo.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("zerorepo.llm.gateway.litellm")
    def test_empty_tier_model_config(self, mock_litellm: MagicMock) -> None:
        """Empty tier models raise ConfigurationError on select_model."""
        from zerorepo.llm.gateway import LLMGateway

        cfg = GatewayConfig(tier_models={})
        gw = LLMGateway(config=cfg)
        with pytest.raises(ConfigurationError):
            gw.select_model(ModelTier.MEDIUM)


@pytest.mark.functional
class TestTokenTrackerStandalone:
    """Standalone TokenTracker integration tests."""

    def test_multi_model_tracking(self) -> None:
        """Track usage across multiple models."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", 100, 50)
        tracker.record("gpt-4o", 200, 100)
        tracker.record("claude-3-haiku-20240307", 150, 75)

        assert tracker.get_total_tokens() == 675
        breakdown = tracker.get_breakdown_by_model()
        assert len(breakdown) == 3
        assert breakdown["gpt-4o"]["total_tokens"] == 300

    def test_cost_accumulation_accuracy(self) -> None:
        """Cost across multiple models matches manual calculation."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", 1_000_000, 1_000_000)
        tracker.record("gpt-4o", 1_000_000, 1_000_000)

        expected = (
            0.15 + 0.60  # gpt-4o-mini
            + 2.50 + 10.0  # gpt-4o
        )
        assert abs(tracker.get_total_cost() - expected) < 0.01

    def test_reset_and_reuse(self) -> None:
        """Tracker can be reset and reused with clean state."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", 100, 50)
        tracker.reset()
        assert tracker.get_total_tokens() == 0
        assert tracker.get_total_cost() == 0.0
        assert tracker.get_breakdown_by_model() == {}

        tracker.record("gpt-4o", 200, 100)
        assert tracker.get_total_tokens() == 300
        assert "gpt-4o-mini" not in tracker.get_breakdown_by_model()


@pytest.mark.functional
class TestModelTierMapping:
    """Verify model tier configuration is consistent and complete."""

    def test_all_tiers_have_all_providers(self) -> None:
        """Every tier has entries for openai, anthropic, and ollama."""
        for tier in ModelTier:
            mapping = DEFAULT_TIER_MODELS[tier]
            assert "openai" in mapping, f"Missing openai for {tier}"
            assert "anthropic" in mapping, f"Missing anthropic for {tier}"
            assert "ollama" in mapping, f"Missing ollama for {tier}"

    def test_all_default_models_are_supported(self) -> None:
        """Every model in DEFAULT_TIER_MODELS is in SUPPORTED_MODELS."""
        from zerorepo.llm.gateway import SUPPORTED_MODELS

        for tier in ModelTier:
            for provider, model in DEFAULT_TIER_MODELS[tier].items():
                assert model in SUPPORTED_MODELS, (
                    f"{model} ({tier.value}/{provider}) not in SUPPORTED_MODELS"
                )

    def test_pricing_covers_known_models(self) -> None:
        """All non-ollama models in tier mapping have pricing entries."""
        for tier in ModelTier:
            for provider, model in DEFAULT_TIER_MODELS[tier].items():
                if provider == "ollama":
                    continue  # Ollama models are free / self-hosted
                assert model in TOKEN_PRICING, (
                    f"{model} ({tier.value}/{provider}) missing from TOKEN_PRICING"
                )
