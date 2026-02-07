"""ZeroRepo CLI progress display utilities.

Wraps Rich :class:`~rich.progress.Progress` and :class:`~rich.status.Status`
into convenient context managers for CLI feedback.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

# ---------------------------------------------------------------------------
# ProgressDisplay
# ---------------------------------------------------------------------------


class ProgressDisplay:
    """Wrapper around Rich Progress for ZeroRepo CLI operations.

    Parameters
    ----------
    console:
        Rich console to use.  Defaults to stderr.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(stderr=True)

    @contextmanager
    def spinner(self, message: str) -> Generator[None, None, None]:
        """Show an indeterminate spinner with *message*.

        Usage::

            display = ProgressDisplay()
            with display.spinner("Generating graph..."):
                run_slow_operation()
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            progress.add_task(message, total=None)
            yield

    @contextmanager
    def bar(self, total: int, description: str = "Working") -> Generator[Progress, None, None]:
        """Show a determinate progress bar.

        Yields the :class:`~rich.progress.Progress` instance so callers
        can call ``progress.advance(task_id)``.

        Usage::

            display = ProgressDisplay()
            with display.bar(100, "Processing files") as progress:
                task = progress.tasks[0]
                for _ in range(100):
                    progress.advance(task.id)
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            progress.add_task(description, total=total)
            yield progress


# ---------------------------------------------------------------------------
# StatusDisplay
# ---------------------------------------------------------------------------


class StatusDisplay:
    """Display a Rich status panel.

    Parameters
    ----------
    console:
        Rich console to use.  Defaults to stderr.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(stderr=True)

    def show(self, title: str, message: str, style: str = "blue") -> None:
        """Print a status panel to the console.

        Parameters
        ----------
        title:
            Panel title.
        message:
            Panel body text.
        style:
            Rich border style (default ``"blue"``).
        """
        self.console.print(
            Panel(message, title=title, border_style=style)
        )

    def success(self, message: str) -> None:
        """Print a green success panel."""
        self.show("Success", f"[green]{message}[/green]", style="green")

    def warning(self, message: str) -> None:
        """Print a yellow warning panel."""
        self.show("Warning", f"[yellow]{message}[/yellow]", style="yellow")

    def error(self, message: str) -> None:
        """Print a red error panel."""
        self.show("Error", f"[red]{message}[/red]", style="red")


# ---------------------------------------------------------------------------
# Convenience context managers
# ---------------------------------------------------------------------------

_default_display = None


def _get_default_display() -> ProgressDisplay:
    global _default_display
    if _default_display is None:
        _default_display = ProgressDisplay()
    return _default_display


@contextmanager
def progress_spinner(message: str) -> Generator[None, None, None]:
    """Convenience context manager for a spinner."""
    with _get_default_display().spinner(message):
        yield


@contextmanager
def progress_bar(total: int, description: str = "Working") -> Generator[Progress, None, None]:
    """Convenience context manager for a progress bar."""
    with _get_default_display().bar(total, description) as progress:
        yield progress
