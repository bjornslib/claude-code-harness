"""MCP client for communicating with the Serena MCP server.

Implements JSON-RPC 2.0 over stdio transport for calling Serena MCP tools.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from zerorepo.serena.exceptions import MCPError, ToolNotFoundError
from zerorepo.serena.server import SerenaMCPServer

logger = logging.getLogger(__name__)

# Tools supported by the Serena MCP server
SUPPORTED_TOOLS = frozenset({
    "activate_project",
    "find_symbol",
    "get_symbols_overview",
    "list_dir",
})


class MCPClient:
    """Client for calling Serena MCP tools via stdio transport.

    Communicates with the Serena MCP server process using JSON-RPC 2.0
    messages over stdin/stdout.

    Args:
        server: A running SerenaMCPServer instance.
    """

    def __init__(self, server: SerenaMCPServer) -> None:
        self._server = server
        self._request_id = 0

    def _next_id(self) -> int:
        """Generate the next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke an MCP tool and return the response.

        Args:
            tool_name: Name of the MCP tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            The tool's response as a dictionary.

        Raises:
            ToolNotFoundError: If the tool is not in the supported set.
            MCPError: If the server is not running or returns an error.
            SerenaError: If communication with the server fails.
        """
        if tool_name not in SUPPORTED_TOOLS:
            raise ToolNotFoundError(
                tool_name, available_tools=sorted(SUPPORTED_TOOLS)
            )

        if not self._server.is_running():
            raise MCPError("Serena MCP server is not running")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        process = self._server._process
        if process is None or process.stdin is None or process.stdout is None:
            raise MCPError("Serena MCP server process is not available")

        try:
            request_bytes = json.dumps(request).encode("utf-8") + b"\n"
            process.stdin.write(request_bytes)
            process.stdin.flush()

            response_line = process.stdout.readline()
            if not response_line:
                raise MCPError("No response from Serena MCP server")

            response = json.loads(response_line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MCPError(f"Invalid response from server: {exc}") from exc
        except OSError as exc:
            raise MCPError(
                f"Communication error with Serena MCP server: {exc}"
            ) from exc

        if "error" in response:
            error = response["error"]
            raise MCPError(
                message=error.get("message", "Unknown error"),
                code=error.get("code"),
            )

        return response.get("result", {})

    def list_tools(self) -> list[str]:
        """Return list of available tool names.

        Returns:
            Sorted list of supported MCP tool names.
        """
        return sorted(SUPPORTED_TOOLS)
