"""ZeroRepo CLI logging infrastructure.

Sets up structured logging with a Rich console handler for *stderr* and
an optional file handler with timestamps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    *,
    console: Console | None = None,
) -> logging.Logger:
    """Configure the ``zerorepo`` logger.

    Parameters
    ----------
    level:
        Logging level name (e.g. ``"DEBUG"``, ``"INFO"``).
    log_file:
        Optional path to a log file. A :class:`~logging.FileHandler` with
        timestamps is added when provided.
    console:
        Optional Rich console for the console handler.

    Returns
    -------
    logging.Logger
        The configured ``zerorepo`` logger.
    """
    logger = logging.getLogger("zerorepo")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplication on repeated calls
    logger.handlers.clear()

    # Rich console handler (stderr)
    rich_console = console or Console(stderr=True)
    rich_handler = RichHandler(
        console=rich_console,
        show_time=True,
        show_path=False,
        markup=True,
    )
    rich_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(rich_handler)

    # Optional file handler
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file))
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_fmt = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger
