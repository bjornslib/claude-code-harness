"""ZeroRepo CLI – command-line interface built with Typer and Rich.

This package implements Epic 1.7 of PRD-RPG-P1-001, providing:

- :data:`app` – The main Typer application
- :class:`ZeroRepoConfig` – Configuration model
- :func:`setup_logging` – Logging infrastructure
- :class:`ProgressDisplay` – Rich progress wrappers
- :class:`CLIError` – Structured error handling
"""

from cobuilder.repomap.cli.app import app
from cobuilder.repomap.cli.config import ZeroRepoConfig, load_config
from cobuilder.repomap.cli.errors import CLIError, ConfigError, error_handler
from cobuilder.repomap.cli.logging_setup import setup_logging
from cobuilder.repomap.cli.progress import ProgressDisplay, StatusDisplay, progress_bar, progress_spinner

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
