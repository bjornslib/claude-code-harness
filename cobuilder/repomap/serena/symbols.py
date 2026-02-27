"""Symbol lookup via Serena MCP integration.

Provides symbol search and overview capabilities using the
Serena MCP find_symbol and get_symbols_overview tools.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cobuilder.repomap.serena.client import MCPClient
from cobuilder.repomap.serena.exceptions import SerenaError
from cobuilder.repomap.serena.models import SymbolInfo

logger = logging.getLogger(__name__)


class SymbolLookup:
    """Look up symbols in a Serena workspace.

    Provides methods to find individual symbols by name and to
    retrieve an overview of all symbols in a workspace.

    Args:
        client: An MCPClient connected to a running Serena server.
    """

    def __init__(self, client: MCPClient) -> None:
        self._client = client

    def find_symbol(
        self, name: str, workspace_dir: Path
    ) -> SymbolInfo | None:
        """Find a symbol by name in the workspace.

        Args:
            name: The symbol name to search for.
            workspace_dir: The workspace directory to search in.

        Returns:
            A SymbolInfo if the symbol is found, None otherwise.

        Raises:
            SerenaError: If the lookup operation fails unexpectedly.
        """
        try:
            result = self._client.call_tool(
                "find_symbol",
                {
                    "name": name,
                    "workspace_dir": str(workspace_dir.resolve()),
                },
            )
        except Exception as exc:
            raise SerenaError(
                f"Failed to find symbol '{name}': {exc}"
            ) from exc

        if not result or not result.get("symbols"):
            return None

        symbols = result["symbols"]
        if not symbols:
            return None

        # Return the first match
        sym = symbols[0]
        return SymbolInfo(
            name=sym.get("name", name),
            kind=sym.get("kind", "unknown"),
            filepath=sym.get("filepath", ""),
            line=sym.get("line", 1),
            column=sym.get("column", 0),
            docstring=sym.get("docstring"),
        )

    def get_symbols_overview(
        self, workspace_dir: Path
    ) -> list[SymbolInfo]:
        """Get an overview of all symbols in the workspace.

        Args:
            workspace_dir: The workspace directory to analyze.

        Returns:
            List of SymbolInfo objects for all discovered symbols.

        Raises:
            SerenaError: If the overview operation fails.
        """
        try:
            result = self._client.call_tool(
                "get_symbols_overview",
                {"workspace_dir": str(workspace_dir.resolve())},
            )
        except Exception as exc:
            raise SerenaError(
                f"Failed to get symbols overview: {exc}"
            ) from exc

        symbols: list[SymbolInfo] = []
        for sym in result.get("symbols", []):
            symbols.append(
                SymbolInfo(
                    name=sym.get("name", ""),
                    kind=sym.get("kind", "unknown"),
                    filepath=sym.get("filepath", ""),
                    line=sym.get("line", 1),
                    column=sym.get("column", 0),
                    docstring=sym.get("docstring"),
                )
            )

        return symbols
