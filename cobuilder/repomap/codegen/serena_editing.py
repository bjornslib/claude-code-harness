"""Serena MCP-based code editing for the code generation pipeline.

Wraps the existing Serena MCPClient and SymbolLookup to provide
structural editing operations (find, replace, insert, rename)
with AST syntax validation and graceful fallback.

Classes:
    SerenaEditor -- Structural code editor using Serena MCP tools.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from cobuilder.repomap.serena.exceptions import MCPError, SerenaError
from cobuilder.repomap.serena.models import SymbolInfo

logger = logging.getLogger(__name__)


class SerenaEditor:
    """Structural code editor using Serena MCP tools.

    Provides symbol lookup, body replacement, insertion, and renaming
    operations. Validates Python syntax before any write operation.
    Falls back gracefully when Serena MCP is unavailable.

    Args:
        mcp_client: An MCPClient instance (or None if unavailable).
        symbol_lookup: A SymbolLookup instance (or None if unavailable).
        workspace_dir: The workspace directory for Serena operations.
    """

    def __init__(
        self,
        mcp_client: Any | None = None,
        symbol_lookup: Any | None = None,
        workspace_dir: Path | None = None,
    ) -> None:
        self._client = mcp_client
        self._symbol_lookup = symbol_lookup
        self._workspace_dir = workspace_dir or Path(".")

    @property
    def is_available(self) -> bool:
        """Whether Serena MCP client is available for use."""
        return self._client is not None and self._symbol_lookup is not None

    def find_symbol(self, name: str) -> list[SymbolInfo]:
        """Find symbols by exact name using Serena MCP.

        Args:
            name: The symbol name to search for.

        Returns:
            List of SymbolInfo objects matching the name.
            Empty list if Serena is unavailable or the symbol is not found.
        """
        if not self.is_available:
            logger.debug("Serena unavailable; find_symbol returning empty")
            return []

        try:
            result = self._client.call_tool(
                "find_symbol",
                {
                    "name": name,
                    "workspace_dir": str(self._workspace_dir.resolve()),
                },
            )
        except (MCPError, SerenaError) as exc:
            logger.warning("Serena find_symbol failed: %s", exc)
            return []

        symbols: list[SymbolInfo] = []
        for sym in result.get("symbols", []):
            symbols.append(
                SymbolInfo(
                    name=sym.get("name", name),
                    kind=sym.get("kind", "unknown"),
                    filepath=sym.get("filepath", ""),
                    line=sym.get("line", 1),
                    column=sym.get("column", 0),
                    docstring=sym.get("docstring"),
                )
            )
        return symbols

    def find_callers(self, name: str) -> list[SymbolInfo]:
        """Find symbols that reference/call the given name.

        Uses Serena's find_referencing_symbols tool if available,
        otherwise returns an empty list.

        Args:
            name: The symbol name to find callers for.

        Returns:
            List of SymbolInfo objects representing callers.
        """
        if not self.is_available:
            return []

        try:
            result = self._client.call_tool(
                "find_referencing_symbols",
                {
                    "name": name,
                    "workspace_dir": str(self._workspace_dir.resolve()),
                },
            )
        except (MCPError, SerenaError) as exc:
            logger.warning("Serena find_callers failed: %s", exc)
            return []

        callers: list[SymbolInfo] = []
        for sym in result.get("symbols", []):
            callers.append(
                SymbolInfo(
                    name=sym.get("name", ""),
                    kind=sym.get("kind", "unknown"),
                    filepath=sym.get("filepath", ""),
                    line=sym.get("line", 1),
                    column=sym.get("column", 0),
                    docstring=sym.get("docstring"),
                )
            )
        return callers

    def replace_body(
        self,
        filepath: str,
        symbol_name: str,
        new_code: str,
    ) -> bool:
        """Replace the body of a symbol with new code.

        Performs AST syntax validation before writing. Uses Serena's
        replace_symbol_body tool for surgical edits.

        Args:
            filepath: The file path containing the symbol.
            symbol_name: The name of the function/class to replace.
            new_code: The new code to replace the body with.

        Returns:
            True if the replacement succeeded, False otherwise.
        """
        if not self._validate_syntax(new_code):
            logger.warning("Syntax validation failed for replace_body")
            return False

        if not self.is_available:
            logger.debug("Serena unavailable; replace_body returning False")
            return False

        try:
            self._client.call_tool(
                "replace_symbol_body",
                {
                    "filepath": filepath,
                    "symbol_name": symbol_name,
                    "new_code": new_code,
                },
            )
            return True
        except (MCPError, SerenaError) as exc:
            logger.warning("Serena replace_body failed: %s", exc)
            return False

    def insert_after(
        self,
        filepath: str,
        symbol_name: str,
        code: str,
    ) -> bool:
        """Insert code after a specified symbol.

        Performs AST syntax validation before writing. Uses Serena's
        insert_after_symbol tool for structural insertion.

        Args:
            filepath: The file path containing the symbol.
            symbol_name: The name of the symbol to insert after.
            code: The code to insert.

        Returns:
            True if the insertion succeeded, False otherwise.
        """
        if not self._validate_syntax(code):
            logger.warning("Syntax validation failed for insert_after")
            return False

        if not self.is_available:
            logger.debug("Serena unavailable; insert_after returning False")
            return False

        try:
            self._client.call_tool(
                "insert_after_symbol",
                {
                    "filepath": filepath,
                    "symbol_name": symbol_name,
                    "code": code,
                },
            )
            return True
        except (MCPError, SerenaError) as exc:
            logger.warning("Serena insert_after failed: %s", exc)
            return False

    def rename_symbol(
        self,
        old_name: str,
        new_name: str,
    ) -> int:
        """Rename a symbol across the workspace.

        Uses Serena to propagate the rename to all usages.

        Args:
            old_name: The current symbol name.
            new_name: The new symbol name.

        Returns:
            The number of locations updated, 0 if failed.
        """
        if not self.is_available:
            return 0

        try:
            result = self._client.call_tool(
                "rename_symbol",
                {
                    "old_name": old_name,
                    "new_name": new_name,
                    "workspace_dir": str(self._workspace_dir.resolve()),
                },
            )
            return result.get("count", 0)
        except (MCPError, SerenaError) as exc:
            logger.warning("Serena rename_symbol failed: %s", exc)
            return 0

    @staticmethod
    def _validate_syntax(code: str) -> bool:
        """Validate that the given code is syntactically valid Python.

        Args:
            code: The Python code string to validate.

        Returns:
            True if the code parses successfully, False otherwise.
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False
