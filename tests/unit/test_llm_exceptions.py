"""Unit tests for LLM Gateway custom exceptions."""

from __future__ import annotations

import pytest

from zerorepo.llm.exceptions import (
    ConfigurationError,
    LLMGatewayError,
    RetryExhaustedError,
    TemplateError,
)


class TestLLMGatewayError:
    """Tests for the base LLMGatewayError."""

    def test_is_exception_subclass(self) -> None:
        """LLMGatewayError inherits from Exception."""
        assert issubclass(LLMGatewayError, Exception)

    def test_instantiate_with_message(self) -> None:
        err = LLMGatewayError("something went wrong")
        assert str(err) == "something went wrong"

    def test_instantiate_no_message(self) -> None:
        err = LLMGatewayError()
        assert str(err) == ""

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(LLMGatewayError):
            raise LLMGatewayError("test")


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_is_llm_gateway_error(self) -> None:
        assert issubclass(ConfigurationError, LLMGatewayError)

    def test_is_exception(self) -> None:
        assert issubclass(ConfigurationError, Exception)

    def test_message_preserved(self) -> None:
        err = ConfigurationError("missing API key")
        assert "missing API key" in str(err)

    def test_caught_as_base_class(self) -> None:
        """ConfigurationError can be caught as LLMGatewayError."""
        with pytest.raises(LLMGatewayError):
            raise ConfigurationError("bad config")

    def test_caught_as_own_class(self) -> None:
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("bad config")


class TestRetryExhaustedError:
    """Tests for RetryExhaustedError."""

    def test_is_llm_gateway_error(self) -> None:
        assert issubclass(RetryExhaustedError, LLMGatewayError)

    def test_is_exception(self) -> None:
        assert issubclass(RetryExhaustedError, Exception)

    def test_stores_attempts(self) -> None:
        original = RuntimeError("connection timeout")
        err = RetryExhaustedError(attempts=5, last_error=original)
        assert err.attempts == 5

    def test_stores_last_error(self) -> None:
        original = RuntimeError("connection timeout")
        err = RetryExhaustedError(attempts=3, last_error=original)
        assert err.last_error is original

    def test_message_contains_attempts(self) -> None:
        original = RuntimeError("timeout")
        err = RetryExhaustedError(attempts=5, last_error=original)
        assert "5" in str(err)

    def test_message_contains_last_error(self) -> None:
        original = RuntimeError("connection refused")
        err = RetryExhaustedError(attempts=3, last_error=original)
        assert "connection refused" in str(err)

    def test_message_format(self) -> None:
        original = ValueError("bad response")
        err = RetryExhaustedError(attempts=4, last_error=original)
        assert str(err) == (
            "All 4 retry attempts exhausted. Last error: bad response"
        )

    def test_caught_as_base_class(self) -> None:
        with pytest.raises(LLMGatewayError):
            raise RetryExhaustedError(attempts=1, last_error=RuntimeError("x"))

    def test_single_attempt(self) -> None:
        err = RetryExhaustedError(attempts=1, last_error=TimeoutError("slow"))
        assert err.attempts == 1
        assert "1" in str(err)

    def test_last_error_type_preserved(self) -> None:
        """The original exception type is preserved on last_error."""
        original = TimeoutError("timed out")
        err = RetryExhaustedError(attempts=2, last_error=original)
        assert isinstance(err.last_error, TimeoutError)


class TestTemplateError:
    """Tests for TemplateError."""

    def test_is_llm_gateway_error(self) -> None:
        assert issubclass(TemplateError, LLMGatewayError)

    def test_is_exception(self) -> None:
        assert issubclass(TemplateError, Exception)

    def test_message_preserved(self) -> None:
        err = TemplateError("template not found: foo.jinja2")
        assert "template not found" in str(err)

    def test_caught_as_base_class(self) -> None:
        with pytest.raises(LLMGatewayError):
            raise TemplateError("render failed")

    def test_caught_as_own_class(self) -> None:
        with pytest.raises(TemplateError):
            raise TemplateError("missing variable")


class TestExceptionHierarchy:
    """Tests verifying the complete exception hierarchy."""

    def test_all_errors_subclass_base(self) -> None:
        """All custom exceptions inherit from LLMGatewayError."""
        for exc_cls in [ConfigurationError, RetryExhaustedError, TemplateError]:
            assert issubclass(exc_cls, LLMGatewayError)

    def test_all_errors_subclass_exception(self) -> None:
        """All custom exceptions ultimately inherit from Exception."""
        for exc_cls in [
            LLMGatewayError,
            ConfigurationError,
            RetryExhaustedError,
            TemplateError,
        ]:
            assert issubclass(exc_cls, Exception)

    def test_exceptions_are_distinct(self) -> None:
        """Each exception type is distinguishable."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("config")
        with pytest.raises(TemplateError):
            raise TemplateError("template")
        with pytest.raises(RetryExhaustedError):
            raise RetryExhaustedError(attempts=1, last_error=RuntimeError("x"))

    def test_configuration_not_caught_as_template(self) -> None:
        """ConfigurationError is not caught by TemplateError handler."""
        with pytest.raises(ConfigurationError):
            try:
                raise ConfigurationError("bad")
            except TemplateError:
                pytest.fail("Should not be caught as TemplateError")
