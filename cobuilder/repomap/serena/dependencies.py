"""Dependency extraction via Serena MCP integration.

Uses Serena's find_symbol tool to discover what symbols
reference or depend on a given symbol.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cobuilder.repomap.serena.client import MCPClient
from cobuilder.repomap.serena.exceptions import SerenaError

logger = logging.getLogger(__name__)


class DependencyExtractor:
    """Extract code dependencies using Serena MCP tools.

    Discovers which symbols reference or depend on a given symbol
    by leveraging Serena's symbol analysis capabilities.

    Args:
        client: An MCPClient connected to a running Serena server.
    """

    def __init__(self, client: MCPClient) -> None:
        self._client = client

    def extract_dependencies(
        self, symbol: str, workspace_dir: Path
    ) -> list[str]:
        """Find what symbols reference or depend on the given symbol.

        Args:
            symbol: The symbol name to find dependencies for.
            workspace_dir: The workspace directory to search in.

        Returns:
            List of symbol names that reference the given symbol.

        Raises:
            SerenaError: If the dependency extraction fails.
        """
        try:
            result = self._client.call_tool(
                "find_symbol",
                {
                    "name": symbol,
                    "workspace_dir": str(workspace_dir.resolve()),
                },
            )
        except Exception as exc:
            raise SerenaError(
                f"Failed to extract dependencies for '{symbol}': {exc}"
            ) from exc

        references: list[str] = []
        for sym in result.get("references", []):
            name = sym.get("name", "")
            if name and name != symbol:
                references.append(name)

        return references
