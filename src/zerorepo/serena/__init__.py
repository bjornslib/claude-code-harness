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
- :class:`BaselineManager` -- RPGGraph baseline persistence
- :class:`DeltaReportGenerator` -- Delta report generation from baseline-aware graphs
- :class:`DeltaSummary` -- Aggregated delta counts dataclass
- :class:`CodebaseAnalyzerProtocol` -- Protocol for codebase analysis
- :class:`FileBasedCodebaseAnalyzer` -- ast-based standalone analyser
- :class:`CodebaseWalker` -- Walk codebase to produce RPGGraph baseline
"""

from zerorepo.serena.baseline import BaselineManager
from zerorepo.serena.client import MCPClient
from zerorepo.serena.delta_report import DeltaReportGenerator, DeltaSummary
from zerorepo.serena.dependencies import DependencyExtractor
from zerorepo.serena.exceptions import MCPError, SerenaError, ToolNotFoundError
from zerorepo.serena.models import PyrightConfig, SymbolInfo
from zerorepo.serena.pyright import PyrightConfigurator
from zerorepo.serena.server import SerenaMCPServer
from zerorepo.serena.session import (
    CodebaseAnalyzerProtocol,
    FileBasedCodebaseAnalyzer,
)
from zerorepo.serena.symbols import SymbolLookup
from zerorepo.serena.walker import CodebaseWalker
from zerorepo.serena.workspace import WorkspaceManager

__all__ = [
    "BaselineManager",
    "CodebaseAnalyzerProtocol",
    "DeltaReportGenerator",
    "DeltaSummary",
    "CodebaseWalker",
    "DependencyExtractor",
    "FileBasedCodebaseAnalyzer",
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
