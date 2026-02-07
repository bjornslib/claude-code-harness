"""Serena MCP server lifecycle management.

Manages the Serena MCP server process, providing start/stop lifecycle
and context manager support for reliable resource cleanup.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from zerorepo.serena.exceptions import SerenaError

logger = logging.getLogger(__name__)


class SerenaMCPServer:
    """Manage the Serena MCP server process.

    Launches the Serena MCP server via npx and provides lifecycle
    management including graceful shutdown and context manager support.

    Usage::

        server = SerenaMCPServer()
        server.start(Path("/path/to/workspace"))
        try:
            # ... use server ...
        finally:
            server.stop()

    Or as a context manager::

        with SerenaMCPServer() as server:
            server.start(Path("/path/to/workspace"))
            # ... use server ...
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    def start(
        self,
        workspace_dir: Path,
        pyright_config: Path | None = None,
    ) -> None:
        """Launch the Serena MCP server via npx.

        Args:
            workspace_dir: The workspace directory for Serena to analyze.
            pyright_config: Optional path to a pyrightconfig.json file.

        Raises:
            SerenaError: If the server is already running or fails to start.
        """
        if self._process is not None and self._process.poll() is None:
            raise SerenaError("Serena MCP server is already running")

        cmd = [
            "npx",
            "-y",
            "@anthropic/serena-mcp",
            "--workspace",
            str(workspace_dir.resolve()),
        ]
        if pyright_config is not None:
            cmd.extend(["--pyright-config", str(pyright_config.resolve())])

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info(
                "Serena MCP server started (pid=%d, workspace=%s)",
                self._process.pid,
                workspace_dir,
            )
        except FileNotFoundError as exc:
            raise SerenaError(
                "Failed to start Serena MCP server: npx not found. "
                "Ensure Node.js is installed."
            ) from exc
        except OSError as exc:
            raise SerenaError(
                f"Failed to start Serena MCP server: {exc}"
            ) from exc

    def stop(self) -> None:
        """Gracefully shut down the Serena MCP server.

        Sends SIGTERM and waits up to 5 seconds for the process to exit.
        If the process does not exit, it is forcefully killed.
        """
        if self._process is None:
            return

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "Serena MCP server did not exit gracefully, killing"
                )
                self._process.kill()
                self._process.wait(timeout=5)
        except OSError as exc:
            logger.warning("Error stopping Serena MCP server: %s", exc)
        finally:
            self._process = None

    def is_running(self) -> bool:
        """Check if the Serena MCP server process is alive.

        Returns:
            True if the server process is running, False otherwise.
        """
        if self._process is None:
            return False
        return self._process.poll() is None

    def __enter__(self) -> SerenaMCPServer:
        """Enter the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the context manager, stopping the server."""
        self.stop()
