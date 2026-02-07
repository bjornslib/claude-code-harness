"""Workspace management for Serena MCP integration.

Manages workspace initialization and incremental file addition
through the Serena MCP activate_project tool.
"""

from __future__ import annotations

import logging
from pathlib import Path

from zerorepo.serena.client import MCPClient
from zerorepo.serena.exceptions import SerenaError

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manage Serena workspace initialization and file tracking.

    Uses the MCP client to activate a workspace and incrementally
    add files for analysis.

    Args:
        client: An MCPClient connected to a running Serena server.
    """

    def __init__(self, client: MCPClient) -> None:
        self._client = client
        self._initialized = False
        self._workspace_dir: Path | None = None

    def initialize_workspace(
        self,
        workspace_dir: Path,
        files: list[Path] | None = None,
    ) -> None:
        """Initialize the Serena workspace with activate_project.

        Args:
            workspace_dir: Root directory of the workspace.
            files: Optional list of files to add after activation.

        Raises:
            SerenaError: If workspace activation fails.
        """
        try:
            self._client.call_tool(
                "activate_project",
                {"workspace_dir": str(workspace_dir.resolve())},
            )
        except Exception as exc:
            raise SerenaError(
                f"Failed to initialize workspace: {exc}"
            ) from exc

        self._workspace_dir = workspace_dir
        self._initialized = True
        logger.info("Workspace initialized: %s", workspace_dir)

        if files:
            for filepath in files:
                self.add_file(filepath)

    def add_file(self, filepath: Path) -> None:
        """Add a single file to the workspace and trigger re-analysis.

        Uses list_dir to make Serena aware of the file's directory,
        which triggers incremental analysis.

        Args:
            filepath: Path to the file to add.

        Raises:
            SerenaError: If the workspace is not initialized or the
                operation fails.
        """
        if not self._initialized:
            raise SerenaError(
                "Workspace not initialized. Call initialize_workspace first."
            )

        parent_dir = str(filepath.parent)
        try:
            self._client.call_tool("list_dir", {"path": parent_dir})
        except Exception as exc:
            raise SerenaError(
                f"Failed to add file '{filepath}': {exc}"
            ) from exc

        logger.debug("Added file to workspace: %s", filepath)
