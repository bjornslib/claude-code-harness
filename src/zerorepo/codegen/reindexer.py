"""Serena LSP re-indexing after code generation writes.

Triggers the Serena language server to re-analyse newly written or
modified Python files, ensuring that symbol resolution stays up to date
throughout the code generation pipeline.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from zerorepo.serena.client import MCPClient
from zerorepo.serena.exceptions import MCPError, SerenaError

logger = logging.getLogger(__name__)


class SerenaReindexer:
    """Trigger Serena LSP re-indexing after file writes.

    Wraps the existing :class:`MCPClient` to send ``list_dir``
    commands that make the language server aware of changed files.

    Args:
        client: An active MCPClient connected to a Serena server.
    """

    def __init__(self, client: MCPClient) -> None:
        self._client = client
        self._last_indexed_files: set[str] = set()

    def should_reindex(self, written_files: list[Path]) -> bool:
        """Check whether a re-index is needed.

        Returns ``True`` if *written_files* contains at least one
        Python file that has not been indexed since the last call to
        :meth:`trigger_reindex`.

        Args:
            written_files: Paths written since the last index.
        """
        new_python_files = {
            str(p) for p in written_files if p.suffix == ".py"
        }
        return bool(new_python_files - self._last_indexed_files)

    def trigger_reindex(
        self, workspace_dir: Path, timeout: float = 10.0
    ) -> bool:
        """Trigger a Serena LSP re-index for *workspace_dir*.

        Sends ``list_dir`` for the workspace root so that Serena picks
        up any file-system changes. Falls back gracefully when the
        Serena MCP server is unavailable.

        Args:
            workspace_dir: Root directory to re-index.
            timeout: Maximum seconds to wait for completion.

        Returns:
            ``True`` if the re-index succeeded, ``False`` on timeout
            or error.
        """
        start = time.monotonic()
        try:
            self._client.call_tool(
                "list_dir",
                {"path": str(workspace_dir.resolve())},
            )
        except (MCPError, SerenaError) as exc:
            logger.warning("Serena re-index failed: %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected error during re-index: %s", exc)
            return False

        elapsed = time.monotonic() - start
        if elapsed > timeout:
            logger.warning(
                "Serena re-index exceeded timeout (%.1fs > %.1fs)",
                elapsed,
                timeout,
            )
            return False

        # Track indexed files
        self._last_indexed_files = {str(workspace_dir)}
        logger.info(
            "Serena re-index completed for %s in %.2fs",
            workspace_dir,
            elapsed,
        )
        return True
