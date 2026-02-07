"""ZeroRepo Serena MCP integration -- workspace validation and symbol analysis.

This package implements Epic 1.6 of PRD-RPG-P1-001, providing:

- :class:`SerenaMCPServer` -- MCP server lifecycle management
- :class:`MCPClient` -- JSON-RPC client for MCP tool calls
- :class:`WorkspaceManager` -- Workspace initialization and file tracking
- :class:`SymbolLookup` -- Symbol search and overview
- :class:`PyrightConfigurator` -- Pyright configuration generation
- :class:`DependencyExtractor` -- Code dependency extraction
- :class:`SymbolInfo` -- Symbol information model
- :class:`PyrightConfig` -- Pyright configuration model
"""

from zerorepo.serena.client import MCPClient
from zerorepo.serena.dependencies import DependencyExtractor
from zerorepo.serena.exceptions import MCPError, SerenaError, ToolNotFoundError
from zerorepo.serena.models import PyrightConfig, SymbolInfo
from zerorepo.serena.pyright import PyrightConfigurator
from zerorepo.serena.server import SerenaMCPServer
from zerorepo.serena.symbols import SymbolLookup
from zerorepo.serena.workspace import WorkspaceManager

__all__ = [
    "DependencyExtractor",
    "MCPClient",
    "MCPError",
    "PyrightConfig",
    "PyrightConfigurator",
    "SerenaMCPServer",
    "SerenaError",
    "SymbolInfo",
    "SymbolLookup",
    "ToolNotFoundError",
    "WorkspaceManager",
]
