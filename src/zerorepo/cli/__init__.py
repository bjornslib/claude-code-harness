"""ZeroRepo CLI – command-line interface built with Typer and Rich.

This package implements Epic 1.7 of PRD-RPG-P1-001, providing:

- :data:`app` – The main Typer application
- :class:`ZeroRepoConfig` – Configuration model
- :func:`setup_logging` – Logging infrastructure
- :class:`ProgressDisplay` – Rich progress wrappers
- :class:`CLIError` – Structured error handling
"""

from zerorepo.cli.app import app
from zerorepo.cli.config import ZeroRepoConfig, load_config
from zerorepo.cli.errors import CLIError, ConfigError, error_handler
from zerorepo.cli.logging_setup import setup_logging
from zerorepo.cli.progress import ProgressDisplay, StatusDisplay, progress_bar, progress_spinner

__all__ = [
    "CLIError",
    "ConfigError",
    "ProgressDisplay",
    "StatusDisplay",
    "ZeroRepoConfig",
    "app",
    "error_handler",
    "load_config",
    "progress_bar",
    "progress_spinner",
    "setup_logging",
]
