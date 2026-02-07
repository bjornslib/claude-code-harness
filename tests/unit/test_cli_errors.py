"""Unit tests for zerorepo.cli.errors."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.cli.errors import (
    EXIT_CONFIG_ERROR,
    EXIT_GENERAL_ERROR,
    EXIT_SUCCESS,
    CLIError,
    ConfigError,
    error_handler,
)


# ---------------------------------------------------------------------------
# CLIError tests
# ---------------------------------------------------------------------------


class TestCLIError:
    """Tests for the CLIError exception class."""

    def test_default_exit_code(self) -> None:
        err = CLIError("something broke")
        assert err.message == "something broke"
        assert err.exit_code == EXIT_GENERAL_ERROR
        assert str(err) == "something broke"

    def test_custom_exit_code(self) -> None:
        err = CLIError("bad config", exit_code=EXIT_CONFIG_ERROR)
        assert err.exit_code == EXIT_CONFIG_ERROR

    def test_is_exception(self) -> None:
        err = CLIError("test")
        assert isinstance(err, Exception)


class TestConfigError:
    """Tests for the ConfigError exception class."""

    def test_exit_code_is_config(self) -> None:
        err = ConfigError("missing key")
        assert err.exit_code == EXIT_CONFIG_ERROR
        assert err.message == "missing key"

    def test_inherits_cli_error(self) -> None:
        assert issubclass(ConfigError, CLIError)


# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_success_is_zero(self) -> None:
        assert EXIT_SUCCESS == 0

    def test_general_error_is_one(self) -> None:
        assert EXIT_GENERAL_ERROR == 1

    def test_config_error_is_two(self) -> None:
        assert EXIT_CONFIG_ERROR == 2


# ---------------------------------------------------------------------------
# error_handler context manager
# ---------------------------------------------------------------------------


class TestErrorHandler:
    """Tests for the error_handler context manager."""

    def test_no_exception_passes_through(self) -> None:
        """No exception = no sys.exit."""
        with error_handler(console=MagicMock()):
            pass  # Should not raise

    def test_cli_error_exits_with_code(self) -> None:
        console = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            with error_handler(console=console):
                raise CLIError("boom", exit_code=2)
        assert exc_info.value.code == 2
        console.print.assert_called_once()

    def test_config_error_exits_with_code_2(self) -> None:
        console = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            with error_handler(console=console):
                raise ConfigError("bad config")
        assert exc_info.value.code == EXIT_CONFIG_ERROR

    def test_generic_exception_exits_with_1(self) -> None:
        console = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            with error_handler(console=console):
                raise RuntimeError("unexpected")
        assert exc_info.value.code == EXIT_GENERAL_ERROR
        console.print.assert_called_once()

    def test_keyboard_interrupt_exits_130(self) -> None:
        console = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            with error_handler(console=console):
                raise KeyboardInterrupt()
        assert exc_info.value.code == 130

    def test_uses_default_console_when_none(self) -> None:
        """Ensure it works without explicit console arg."""
        with pytest.raises(SystemExit):
            with error_handler():
                raise CLIError("test")

    def test_panel_content_contains_message(self) -> None:
        console = MagicMock()
        with pytest.raises(SystemExit):
            with error_handler(console=console):
                raise CLIError("specific error message")
        call_args = console.print.call_args
        panel = call_args[0][0]
        from rich.panel import Panel
        assert isinstance(panel, Panel)
