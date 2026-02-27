"""Unit tests for LLMGateway – the unified LLM interface.

All LiteLLM calls are mocked so tests run without API keys or network access.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from cobuilder.repomap.llm.exceptions import (
    ConfigurationError,
    RetryExhaustedError,
)
from cobuilder.repomap.llm.gateway import (
    SUPPORTED_MODELS,
    LLMGateway,
    _estimate_cost,
    _truncate,
    _truncate_messages,
)
from cobuilder.repomap.llm.models import GatewayConfig, ModelTier


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


class AnswerSchema(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------


class TestTruncate:
    """Tests for _truncate helper."""

    def test_short_text_unchanged(self) -> None:
        assert _truncate("hello", max_len=10) == "hello"

    def test_exact_length_unchanged(self) -> None:
        assert _truncate("abcde", max_len=5) == "abcde"

    def test_long_text_truncated(self) -> None:
        result = _truncate("abcdefghij", max_len=5)
        assert result == "abcde…"
        assert len(result) == 6  # 5 chars + ellipsis

    def test_default_max_len(self) -> None:
        short = "x" * 1000
        assert _truncate(short) == short  # under default 1000
        long = "x" * 1001
        assert _truncate(long).endswith("…")

    def test_empty_string(self) -> None:
        assert _truncate("") == ""


class TestTruncateMessages:
    """Tests for _truncate_messages helper."""

    def test_truncates_long_content(self) -> None:
        msgs = [{"role": "user", "content": "x" * 2000}]
        result = _truncate_messages(msgs)
        assert len(result[0]["content"]) < 2000

    def test_preserves_short_content(self) -> None:
        msgs = [{"role": "user", "content": "hi"}]
        result = _truncate_messages(msgs)
        assert result[0]["content"] == "hi"

    def test_preserves_non_string_content(self) -> None:
        msgs = [{"role": "user", "content": 42}]
        result = _truncate_messages(msgs)
        assert result[0]["content"] == 42

    def test_preserves_role(self) -> None:
        msgs = [{"role": "system", "content": "hello"}]
        result = _truncate_messages(msgs)
        assert result[0]["role"] == "system"

    def test_does_not_mutate_original(self) -> None:
        original_content = "x" * 2000
        msgs = [{"role": "user", "content": original_content}]
        _truncate_messages(msgs)
        assert msgs[0]["content"] == original_content

    def test_empty_list(self) -> None:
        assert _truncate_messages([]) == []


class TestEstimateCost:
    """Tests for _estimate_cost helper."""

    def test_known_model(self) -> None:
        cost = _estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 0.01

    def test_unknown_model_is_zero(self) -> None:
        assert _estimate_cost("unknown-model", 100, 100) == 0.0

    def test_zero_tokens(self) -> None:
        assert _estimate_cost("gpt-4o-mini", 0, 0) == 0.0

    def test_prompt_only(self) -> None:
        cost = _estimate_cost("gpt-4o", 1_000_000, 0)
        assert abs(cost - 2.50) < 0.01

    def test_completion_only(self) -> None:
        cost = _estimate_cost("gpt-4o", 0, 1_000_000)
        assert abs(cost - 10.0) < 0.01


# ---------------------------------------------------------------------------
# Tests for LLMGateway initialisation
# ---------------------------------------------------------------------------


class TestGatewayInit:
    """Tests for LLMGateway constructor."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_default_config(self, mock_litellm: MagicMock) -> None:
        gw = LLMGateway()
        assert gw.tracker is not None
        assert gw.logs == []

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_custom_config(self, mock_litellm: MagicMock) -> None:
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.5)
        gw = LLMGateway(config=cfg)
        assert gw._config.max_retries == 2

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", False)
    def test_no_litellm_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="litellm"):
            LLMGateway()


# ---------------------------------------------------------------------------
# Tests for select_model (Task 1.3.2)
# ---------------------------------------------------------------------------


class TestSelectModel:
    """Tests for tier-based model selection."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_cheap_tier_default_is_openai(self, mock_litellm: MagicMock) -> None:
        gw = LLMGateway()
        model = gw.select_model(ModelTier.CHEAP)
        assert model == "gpt-5.2"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_medium_tier_default_is_openai(self, mock_litellm: MagicMock) -> None:
        gw = LLMGateway()
        model = gw.select_model(ModelTier.MEDIUM)
        assert model == "gpt-5.2"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_prefer_anthropic(self, mock_litellm: MagicMock) -> None:
        gw = LLMGateway()
        model = gw.select_model(ModelTier.CHEAP, provider_preference="anthropic")
        assert "claude" in model.lower()

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_prefer_unknown_provider_falls_back(self, mock_litellm: MagicMock) -> None:
        gw = LLMGateway()
        model = gw.select_model(ModelTier.CHEAP, provider_preference="nonexistent")
        # Should fall back to provider priority (openai first)
        assert model == "gpt-5.2"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_empty_tier_raises(self, mock_litellm: MagicMock) -> None:
        cfg = GatewayConfig(tier_models={})
        gw = LLMGateway(config=cfg)
        with pytest.raises(ConfigurationError, match="No model configured"):
            gw.select_model(ModelTier.CHEAP)


# ---------------------------------------------------------------------------
# Tests for complete (Task 1.3.1 + 1.3.5)
# ---------------------------------------------------------------------------


class TestComplete:
    """Tests for the complete method."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_basic_completion(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(text="Hi there!")
        gw = LLMGateway()
        result = gw.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o-mini",
        )
        assert result == "Hi there!"
        mock_completion.assert_called_once()

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_unsupported_model_raises(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        gw = LLMGateway()
        with pytest.raises(ConfigurationError, match="Unsupported model"):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="totally-fake-model",
            )
        mock_completion.assert_not_called()

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_records_token_usage(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o-mini",
        )
        assert gw.tracker.get_total_tokens() == 150

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_creates_log_entry(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(text="logged")
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
            tier=ModelTier.CHEAP,
        )
        assert len(gw.logs) == 1
        log = gw.logs[0]
        assert log.model == "gpt-4o-mini"
        assert log.tier == ModelTier.CHEAP
        assert log.latency_ms >= 0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_multiple_completions_accumulate_logs(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        for _ in range(3):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        assert len(gw.logs) == 3

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_handles_none_content(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Response with None content returns empty string."""
        resp = _mock_response()
        resp.choices[0].message.content = None
        mock_completion.return_value = resp
        gw = LLMGateway()
        result = gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert result == ""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_handles_none_usage(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Response with None usage records zero tokens."""
        resp = _mock_response()
        resp.usage = None
        mock_completion.return_value = resp
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert gw.tracker.get_total_tokens() == 0


# ---------------------------------------------------------------------------
# Tests for retry logic (Task 1.3.5)
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for exponential backoff retry behaviour."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_retries_on_rate_limit(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Rate limit errors trigger retries."""
        from litellm.exceptions import RateLimitError

        mock_completion.side_effect = [
            RateLimitError(message="rate limited", llm_provider="openai", model="gpt-4o-mini"),
            _mock_response(text="success after retry"),
        ]
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        result = gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert result == "success after retry"
        assert mock_sleep.call_count == 1

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_retries_on_timeout(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """TimeoutError triggers retry."""
        mock_completion.side_effect = [
            TimeoutError("timed out"),
            _mock_response(text="recovered"),
        ]
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        result = gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert result == "recovered"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_retry_exhausted_raises(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """All retries exhausted raises RetryExhaustedError."""
        mock_completion.side_effect = TimeoutError("always fails")
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        with pytest.raises(RetryExhaustedError) as exc_info:
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        assert exc_info.value.attempts == 3  # initial + 2 retries
        assert isinstance(exc_info.value.last_error, TimeoutError)

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_no_retry_on_auth_error(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Authentication errors are NOT retried."""
        from litellm.exceptions import AuthenticationError

        mock_completion.side_effect = AuthenticationError(
            message="invalid key", llm_provider="openai", model="gpt-4o-mini"
        )
        gw = LLMGateway()
        with pytest.raises(AuthenticationError):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        mock_sleep.assert_not_called()

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_no_retry_on_bad_request(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Bad request errors are NOT retried."""
        from litellm.exceptions import BadRequestError

        mock_completion.side_effect = BadRequestError(
            message="invalid params", llm_provider="openai", model="gpt-4o-mini"
        )
        gw = LLMGateway()
        with pytest.raises(BadRequestError):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        mock_sleep.assert_not_called()

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_exponential_backoff_delays(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Retry delays follow exponential backoff: base * 2^attempt."""
        mock_completion.side_effect = TimeoutError("fail")
        cfg = GatewayConfig(max_retries=3, base_retry_delay=1.0)
        gw = LLMGateway(config=cfg)
        with pytest.raises(RetryExhaustedError):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]  # 1*2^0, 1*2^1, 1*2^2

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_zero_retries_fails_immediately(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """With max_retries=0, first failure raises immediately."""
        mock_completion.side_effect = TimeoutError("fail")
        cfg = GatewayConfig(max_retries=0, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        with pytest.raises(RetryExhaustedError) as exc_info:
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        assert exc_info.value.attempts == 1
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for complete_json (structured output)
# ---------------------------------------------------------------------------


class TestCompleteJson:
    """Tests for structured JSON completion."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_returns_parsed_model(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(
            text='{"answer": "42"}'
        )
        gw = LLMGateway()
        result = gw.complete_json(
            messages=[{"role": "user", "content": "What is 6*7?"}],
            model="gpt-4o-mini",
            response_schema=AnswerSchema,
        )
        assert isinstance(result, AnswerSchema)
        assert result.answer == "42"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_appends_schema_instruction(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(
            text='{"answer": "yes"}'
        )
        gw = LLMGateway()
        gw.complete_json(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o-mini",
            response_schema=AnswerSchema,
        )
        # Check the messages passed to litellm include schema instruction
        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        if messages is None:
            # Try positional
            messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 2  # original + schema instruction
        assert "json" in messages[-1]["content"].lower()

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_invalid_json_raises_validation_error(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Invalid JSON response raises pydantic ValidationError."""
        from pydantic import ValidationError

        mock_completion.return_value = _mock_response(text="not json at all")
        gw = LLMGateway()
        with pytest.raises(ValidationError):
            gw.complete_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4o-mini",
                response_schema=AnswerSchema,
            )

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_sets_json_response_format(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """complete_json sets response_format to json_object by default."""
        mock_completion.return_value = _mock_response(text='{"answer": "x"}')
        gw = LLMGateway()
        gw.complete_json(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o-mini",
            response_schema=AnswerSchema,
        )
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}


# ---------------------------------------------------------------------------
# Tests for log retrieval (Task 1.3.3)
# ---------------------------------------------------------------------------


class TestGetLogs:
    """Tests for log filtering by time."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_get_all_logs(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        gw.complete(messages=[{"role": "user", "content": "a"}], model="gpt-4o-mini")
        gw.complete(messages=[{"role": "user", "content": "b"}], model="gpt-4o-mini")
        assert len(gw.get_logs()) == 2

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_filter_by_start_time(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        gw.complete(messages=[{"role": "user", "content": "old"}], model="gpt-4o-mini")

        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        filtered = gw.get_logs(start_time=future)
        assert len(filtered) == 0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_filter_by_end_time(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        gw.complete(messages=[{"role": "user", "content": "x"}], model="gpt-4o-mini")

        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        filtered = gw.get_logs(end_time=past)
        assert len(filtered) == 0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_empty_logs(self, mock_litellm: MagicMock) -> None:
        gw = LLMGateway()
        assert gw.get_logs() == []

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_logs_property_returns_copy(self, mock_litellm: MagicMock) -> None:
        """The logs property returns a copy, not the internal list."""
        gw = LLMGateway()
        logs = gw.logs
        assert logs is not gw._logs


# ---------------------------------------------------------------------------
# Tests for SUPPORTED_MODELS
# ---------------------------------------------------------------------------


class TestSupportedModels:
    """Tests for the supported model set."""

    def test_contains_gpt52(self) -> None:
        assert "gpt-5.2" in SUPPORTED_MODELS

    def test_contains_gpt4o_mini(self) -> None:
        assert "gpt-4o-mini" in SUPPORTED_MODELS

    def test_contains_gpt4o(self) -> None:
        assert "gpt-4o" in SUPPORTED_MODELS

    def test_contains_claude_haiku(self) -> None:
        assert "claude-3-haiku-20240307" in SUPPORTED_MODELS

    def test_contains_claude_sonnet(self) -> None:
        assert "claude-3-5-sonnet-20241022" in SUPPORTED_MODELS

    def test_contains_ollama(self) -> None:
        assert "ollama/llama3.2" in SUPPORTED_MODELS

    def test_is_a_set(self) -> None:
        assert isinstance(SUPPORTED_MODELS, set)

    def test_contains_claude_sonnet_4(self) -> None:
        assert "claude-sonnet-4-20250514" in SUPPORTED_MODELS


# ---------------------------------------------------------------------------
# Additional tests for coverage gaps
# ---------------------------------------------------------------------------


class TestCompleteAdditional:
    """Additional completion edge cases."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_forwards_extra_kwargs(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Extra kwargs are forwarded to litellm.completion."""
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=200,
        )
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.7
        assert call_kwargs.get("max_tokens") == 200

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_all_supported_models_accepted(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Every model in SUPPORTED_MODELS can be called without error."""
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        for model in sorted(SUPPORTED_MODELS):
            result = gw.complete(
                messages=[{"role": "user", "content": "test"}],
                model=model,
            )
            assert isinstance(result, str)

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_log_tier_none_when_not_specified(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Without tier parameter, log entry tier is None."""
        mock_completion.return_value = _mock_response()
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert gw.logs[0].tier is None

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_log_response_field(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Log entry captures the response text."""
        mock_completion.return_value = _mock_response(text="answer text")
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert gw.logs[0].response == "answer text"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_log_cost_for_known_model(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Log entry cost is positive for known pricing model."""
        mock_completion.return_value = _mock_response(
            prompt_tokens=1000, completion_tokens=500
        )
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert gw.logs[0].cost_usd > 0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_log_cost_zero_for_unknown_model(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Log entry cost is 0 for model not in pricing table."""
        mock_completion.return_value = _mock_response(
            prompt_tokens=1000, completion_tokens=500
        )
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="ollama/llama3.2",
        )
        assert gw.logs[0].cost_usd == 0.0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_log_truncates_long_content(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Messages >1000 chars are truncated in logs."""
        long_msg = "x" * 2000
        mock_completion.return_value = _mock_response(text="y" * 2000)
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": long_msg}],
            model="gpt-4o-mini",
        )
        log = gw.logs[0]
        assert len(log.messages[0]["content"]) <= 1001
        assert log.messages[0]["content"].endswith("…")
        assert len(log.response) <= 1001
        assert log.response.endswith("…")

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_exact_1000_chars_not_truncated(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Exactly 1000 chars should NOT be truncated."""
        exact = "z" * 1000
        mock_completion.return_value = _mock_response(text="ok")
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": exact}],
            model="gpt-4o-mini",
        )
        assert gw.logs[0].messages[0]["content"] == exact


class TestRetryAdditional:
    """Additional retry edge cases."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_no_log_on_failure(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Failed completions (exhausted retries) don't create log entries."""
        mock_completion.side_effect = TimeoutError("fail")
        cfg = GatewayConfig(max_retries=1, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        with pytest.raises(RetryExhaustedError):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        assert len(gw.logs) == 0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_no_tracker_update_on_failure(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Failed completions don't update the token tracker."""
        mock_completion.side_effect = TimeoutError("fail")
        cfg = GatewayConfig(max_retries=1, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        with pytest.raises(RetryExhaustedError):
            gw.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
            )
        assert gw.tracker.get_total_tokens() == 0

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_success_on_last_retry_attempt(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """Succeed on the very last allowed attempt."""
        mock_completion.side_effect = [
            TimeoutError("1"),
            TimeoutError("2"),
            _mock_response(text="last chance"),
        ]
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        result = gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert result == "last chance"
        assert mock_completion.call_count == 3

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.time.sleep")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_retries_on_connection_error(
        self,
        mock_completion: MagicMock,
        mock_sleep: MagicMock,
        mock_litellm: MagicMock,
    ) -> None:
        """APIConnectionError triggers retries."""
        from litellm.exceptions import APIConnectionError

        mock_completion.side_effect = [
            APIConnectionError(message="lost", llm_provider="openai", model="gpt-4o-mini"),
            _mock_response(text="reconnected"),
        ]
        cfg = GatewayConfig(max_retries=2, base_retry_delay=0.01)
        gw = LLMGateway(config=cfg)
        result = gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        assert result == "reconnected"


class TestCostAccuracy:
    """Verify cost calculations within ±1% of expected."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_gpt4o_mini_cost_1pct(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(
            prompt_tokens=1_000_000, completion_tokens=1_000_000
        )
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        expected = 0.15 + 0.60  # $0.75
        actual = gw.logs[0].cost_usd
        assert abs(actual - expected) / expected < 0.01

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_gpt4o_cost_1pct(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_completion.return_value = _mock_response(
            prompt_tokens=500_000, completion_tokens=200_000
        )
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o",
        )
        expected = (500_000 / 1_000_000) * 2.50 + (200_000 / 1_000_000) * 10.0
        actual = gw.logs[0].cost_usd
        assert abs(actual - expected) / expected < 0.01

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    @patch("cobuilder.repomap.llm.gateway.litellm_completion")
    def test_tracker_cost_matches_log_cost(
        self, mock_completion: MagicMock, mock_litellm: MagicMock
    ) -> None:
        """Tracker total cost should match sum of log entry costs."""
        mock_completion.return_value = _mock_response(
            prompt_tokens=10_000, completion_tokens=5_000
        )
        gw = LLMGateway()
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        gw.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
        )
        log_cost_sum = sum(log.cost_usd for log in gw.logs)
        tracker_cost = gw.tracker.get_total_cost()
        assert abs(tracker_cost - log_cost_sum) < 0.0001


class TestSelectModelAdditional:
    """Additional model selection edge cases."""

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_all_tier_provider_combos(self, mock_litellm: MagicMock) -> None:
        """Every tier+provider returns the correct model."""
        from cobuilder.repomap.llm.models import DEFAULT_TIER_MODELS

        gw = LLMGateway()
        expected = {
            (ModelTier.CHEAP, "openai"): "gpt-5.2",
            (ModelTier.CHEAP, "anthropic"): "claude-3-haiku-20240307",
            (ModelTier.CHEAP, "ollama"): "ollama/llama3.2",
            (ModelTier.MEDIUM, "openai"): "gpt-5.2",
            (ModelTier.MEDIUM, "anthropic"): "claude-3-5-sonnet-20241022",
            (ModelTier.STRONG, "openai"): "gpt-5.2",
            (ModelTier.STRONG, "anthropic"): "claude-sonnet-4-5-20250929",
        }
        for (tier, provider), model in expected.items():
            assert gw.select_model(tier, provider) == model

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_custom_tier_mapping(self, mock_litellm: MagicMock) -> None:
        """Custom tier mapping overrides defaults."""
        custom = {ModelTier.CHEAP: {"custom": "my-model"}}
        cfg = GatewayConfig(tier_models=custom)
        gw = LLMGateway(config=cfg)
        assert gw.select_model(ModelTier.CHEAP, "custom") == "my-model"

    @patch("cobuilder.repomap.llm.gateway._LITELLM_AVAILABLE", True)
    @patch("cobuilder.repomap.llm.gateway.litellm")
    def test_select_each_tier_no_preference(self, mock_litellm: MagicMock) -> None:
        """Each tier returns a string model without provider preference."""
        gw = LLMGateway()
        for tier in ModelTier:
            model = gw.select_model(tier)
            assert isinstance(model, str)
            assert len(model) > 0
