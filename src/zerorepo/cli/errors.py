"""ZeroRepo CLI error handling.

Provides structured error handling with Rich-formatted output and
consistent exit codes for the CLI application.

Exit codes:
    0 - Success
    1 - General error
    2 - Configuration error
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.panel import Panel

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_CONFIG_ERROR = 2

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CLIError(Exception):
    """Base exception for CLI errors.

    Parameters
    ----------
    message:
        Human-readable error description.
    exit_code:
        Process exit code (default :data:`EXIT_GENERAL_ERROR`).
    """

    def __init__(self, message: str, exit_code: int = EXIT_GENERAL_ERROR) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ConfigError(CLIError):
    """Raised when configuration loading or validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=EXIT_CONFIG_ERROR)


# ---------------------------------------------------------------------------
# Error handler context manager
# ---------------------------------------------------------------------------

_stderr = Console(stderr=True)


@contextmanager
def error_handler(console: Console | None = None) -> Generator[None, None, None]:
    """Context manager that catches exceptions and prints a Rich error panel.

    Parameters
    ----------
    console:
        Rich console to use for output. Defaults to stderr console.

    Raises
    ------
    SystemExit
        Always raised when an exception is caught, with the appropriate
        exit code.
    """
    out = console or _stderr
    try:
        yield
    except CLIError as exc:
        out.print(
            Panel(
                f"[bold red]{exc.message}[/bold red]",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        out.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)
    except Exception as exc:
        out.print(
            Panel(
                f"[bold red]{exc}[/bold red]",
                title="[red]Unexpected Error[/red]",
                border_style="red",
            )
        )
        sys.exit(EXIT_GENERAL_ERROR)
