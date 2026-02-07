"""Unit tests for zerorepo.cli.progress."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from zerorepo.cli.progress import (
    ProgressDisplay,
    StatusDisplay,
    progress_bar,
    progress_spinner,
)


# ---------------------------------------------------------------------------
# ProgressDisplay tests
# ---------------------------------------------------------------------------


class TestProgressDisplay:
    def test_init_default_console(self) -> None:
        display = ProgressDisplay()
        assert display.console is not None

    def test_init_custom_console(self) -> None:
        console = Console(stderr=True)
        display = ProgressDisplay(console=console)
        assert display.console is console

    def test_spinner_context_manager(self) -> None:
        """Spinner context manager enters and exits cleanly."""
        console = Console(stderr=True, force_terminal=False)
        display = ProgressDisplay(console=console)
        with display.spinner("Testing..."):
            pass  # Should not raise

    def test_bar_context_manager(self) -> None:
        """Bar context manager enters and exits cleanly."""
        console = Console(stderr=True, force_terminal=False)
        display = ProgressDisplay(console=console)
        with display.bar(10, "Processing") as progress:
            assert progress is not None
            assert len(progress.tasks) == 1
            assert progress.tasks[0].total == 10

    def test_bar_yields_progress(self) -> None:
        from rich.progress import Progress
        console = Console(stderr=True, force_terminal=False)
        display = ProgressDisplay(console=console)
        with display.bar(5, "Test") as progress:
            assert isinstance(progress, Progress)


# ---------------------------------------------------------------------------
# StatusDisplay tests
# ---------------------------------------------------------------------------


class TestStatusDisplay:
    def test_init_default_console(self) -> None:
        display = StatusDisplay()
        assert display.console is not None

    def test_init_custom_console(self) -> None:
        console = MagicMock(spec=Console)
        display = StatusDisplay(console=console)
        assert display.console is console

    def test_show_prints_panel(self) -> None:
        console = MagicMock(spec=Console)
        display = StatusDisplay(console=console)
        display.show("Title", "Message", "blue")
        console.print.assert_called_once()
        from rich.panel import Panel
        panel = console.print.call_args[0][0]
        assert isinstance(panel, Panel)

    def test_success_uses_green(self) -> None:
        console = MagicMock(spec=Console)
        display = StatusDisplay(console=console)
        display.success("All good!")
        console.print.assert_called_once()
        panel = console.print.call_args[0][0]
        assert panel.border_style == "green"

    def test_warning_uses_yellow(self) -> None:
        console = MagicMock(spec=Console)
        display = StatusDisplay(console=console)
        display.warning("Watch out!")
        panel = console.print.call_args[0][0]
        assert panel.border_style == "yellow"

    def test_error_uses_red(self) -> None:
        console = MagicMock(spec=Console)
        display = StatusDisplay(console=console)
        display.error("Oh no!")
        panel = console.print.call_args[0][0]
        assert panel.border_style == "red"


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    def test_progress_spinner(self) -> None:
        """Convenience spinner works."""
        # Reset the default display to avoid stale state
        import zerorepo.cli.progress as mod
        mod._default_display = None
        with progress_spinner("Test"):
            pass

    def test_progress_bar(self) -> None:
        """Convenience bar works."""
        import zerorepo.cli.progress as mod
        mod._default_display = None
        with progress_bar(5, "Test") as progress:
            assert progress is not None
