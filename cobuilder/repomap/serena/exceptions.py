"""Custom exceptions for the Serena MCP integration module."""

from __future__ import annotations


class SerenaError(Exception):
    """Base exception for all Serena MCP errors.

    Raised when a Serena operation fails unexpectedly.
    """


class MCPError(SerenaError):
    """Raised when an MCP protocol-level error occurs.

    Attributes:
        code: The JSON-RPC error code, if available.
        message: The error message from the MCP server.
    """

    def __init__(self, message: str, code: int | None = None) -> None:
        self.code = code
        self.message = message
        detail = f" (code={code})" if code is not None else ""
        super().__init__(f"MCP error{detail}: {message}")


class ToolNotFoundError(SerenaError):
    """Raised when a requested MCP tool is not available.

    Attributes:
        tool_name: The name of the tool that was not found.
        available_tools: List of tools that are available.
    """

    def __init__(
        self, tool_name: str, available_tools: list[str] | None = None
    ) -> None:
        self.tool_name = tool_name
        self.available_tools = available_tools or []
        available = (
            f" Available: {', '.join(self.available_tools)}"
            if self.available_tools
            else ""
        )
        super().__init__(f"MCP tool '{tool_name}' not found.{available}")
