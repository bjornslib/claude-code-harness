"""Unit tests for zerorepo.cli.logging_setup."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.logging import RichHandler

from cobuilder.repomap.cli.logging_setup import setup_logging


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up the zerorepo logger after each test."""
        logger = logging.getLogger("zerorepo")
        logger.handlers.clear()

    def test_returns_logger(self) -> None:
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "zerorepo"

    def test_default_level_is_info(self) -> None:
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_debug_level(self) -> None:
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_warning_level(self) -> None:
        logger = setup_logging(level="WARNING")
        assert logger.level == logging.WARNING

    def test_case_insensitive_level(self) -> None:
        logger = setup_logging(level="debug")
        assert logger.level == logging.DEBUG

    def test_has_rich_handler(self) -> None:
        logger = setup_logging()
        rich_handlers = [h for h in logger.handlers if isinstance(h, RichHandler)]
        assert len(rich_handlers) == 1

    def test_no_file_handler_by_default(self) -> None:
        logger = setup_logging()
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

    def test_file_handler_added(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_file=log_file)
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1

    def test_file_handler_creates_parent_dirs(self, tmp_path: Path) -> None:
        log_file = tmp_path / "subdir" / "deep" / "test.log"
        logger = setup_logging(log_file=log_file)
        assert log_file.parent.exists()

    def test_file_handler_format_has_timestamp(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_file=log_file)
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        fmt = file_handlers[0].formatter
        assert fmt is not None
        assert "asctime" in fmt._fmt

    def test_clears_existing_handlers(self) -> None:
        """Calling setup_logging twice doesn't duplicate handlers."""
        setup_logging()
        logger = setup_logging()
        assert len(logger.handlers) == 1  # Only one rich handler

    def test_custom_console(self) -> None:
        from rich.console import Console
        console = Console(stderr=True)
        logger = setup_logging(console=console)
        rich_handlers = [h for h in logger.handlers if isinstance(h, RichHandler)]
        assert len(rich_handlers) == 1

    def test_file_handler_writes(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_file=log_file)
        logger.info("test message")
        # Flush handlers
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text()
        assert "test message" in content
