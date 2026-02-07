"""ZeroRepo CLI application entry point.

Built with `Typer <https://typer.tiangolo.com/>`_ and
`Rich <https://rich.readthedocs.io/>`_.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from zerorepo.cli.config import load_config
from zerorepo.cli.errors import error_handler
from zerorepo.cli.init_cmd import run_init
from zerorepo.cli.logging_setup import setup_logging

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="zerorepo",
    help="ZeroRepo – Repository Planning Graph for generating complete software repositories.",
    add_completion=False,
    no_args_is_help=True,
)

_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from zerorepo import __version__

        _console.print(f"zerorepo {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Main callback (global options)
# ---------------------------------------------------------------------------

@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG) output.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration TOML file.",
    ),
) -> None:
    """Global options for ZeroRepo CLI."""
    # Setup logging based on verbosity
    level = "DEBUG" if verbose else "INFO"
    setup_logging(level)

    # Store config path for sub-commands via context
    ctx = typer.Context
    # We use a simple module-level store since Typer callbacks
    # execute before commands
    app._zerorepo_verbose = verbose  # type: ignore[attr-defined]
    app._zerorepo_config_path = config  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------

@app.command()
def init(
    path: Optional[Path] = typer.Argument(
        None,
        help="Target directory to initialise. Defaults to current directory.",
    ),
) -> None:
    """Initialise a new ZeroRepo project.

    Creates the ``.zerorepo/`` directory structure with default configuration.
    """
    with error_handler(_console):
        project_dir = run_init(path)
        _console.print(f"[green]Initialised ZeroRepo project at {project_dir}[/green]")

        # Check if it's a git repo and warn
        from zerorepo.cli.init_cmd import _is_git_repo

        if not _is_git_repo(project_dir):
            _console.print(
                "[yellow]Warning: Not a git repository. "
                "ZeroRepo works best inside a git repo.[/yellow]"
            )
