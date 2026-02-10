"""Functional tests for the Serena MCP integration module.

These tests exercise the full workflow of the Serena MCP integration
by mocking at the MCP client boundary. They verify multi-step operations
like initializing a workspace, looking up symbols, extracting dependencies,
and configuring Pyright work correctly as integrated flows.

All MCP and subprocess operations are mocked since no external processes
are available.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.serena import (
    DependencyExtractor,
    MCPClient,
    MCPError,
    PyrightConfig,
    PyrightConfigurator,
    SerenaMCPServer,
    SerenaError,
    SymbolInfo,
    SymbolLookup,
    ToolNotFoundError,
    WorkspaceManager,
)


@pytest.fixture
def mock_server() -> MagicMock:
    """Create a mock Serena MCP server that appears running."""
    server = MagicMock(spec=SerenaMCPServer)
    server.is_running.return_value = True

    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.stdout = MagicMock()
    server._process = mock_process

    return server


def _setup_responses(
    server: MagicMock, responses: list[dict]
) -> None:
    """Configure mock server to return a sequence of JSON-RPC responses."""
    response_iter = iter(responses)

    def readline_side_effect():
        try:
            resp = next(response_iter)
            return json.dumps(resp).encode("utf-8") + b"\n"
        except StopIteration:
            return b""

    server._process.stdout.readline.side_effect = readline_side_effect


class TestFullWorkspaceFlow:
    """Functional tests for complete workspace initialization and usage."""

    @pytest.mark.functional
    def test_initialize_find_symbol_flow(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Full flow: initialize workspace -> find symbol."""
        _setup_responses(
            mock_server,
            [
                # activate_project response
                {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}},
                # find_symbol response
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "symbols": [
                            {
                                "name": "RPGNode",
                                "kind": "class",
                                "filepath": "src/zerorepo/models/node.py",
                                "line": 19,
                                "column": 0,
                                "docstring": "A node in the RPG.",
                            }
                        ]
                    },
                },
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)
        symbols = SymbolLookup(client)

        workspace.initialize_workspace(tmp_path)
        result = symbols.find_symbol("RPGNode", tmp_path)

        assert result is not None
        assert isinstance(result, SymbolInfo)
        assert result.name == "RPGNode"
        assert result.kind == "class"
        assert result.line == 19

    @pytest.mark.functional
    def test_initialize_add_files_overview_flow(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Full flow: initialize -> add files -> get overview."""
        _setup_responses(
            mock_server,
            [
                # activate_project
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                # list_dir for add_file(a.py)
                {"jsonrpc": "2.0", "id": 2, "result": {}},
                # list_dir for add_file(b.py)
                {"jsonrpc": "2.0", "id": 3, "result": {}},
                # get_symbols_overview
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {
                        "symbols": [
                            {
                                "name": "ClassA",
                                "kind": "class",
                                "filepath": "a.py",
                                "line": 1,
                            },
                            {
                                "name": "func_b",
                                "kind": "function",
                                "filepath": "b.py",
                                "line": 5,
                            },
                        ]
                    },
                },
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)
        symbols = SymbolLookup(client)

        workspace.initialize_workspace(tmp_path)
        workspace.add_file(tmp_path / "a.py")
        workspace.add_file(tmp_path / "b.py")

        overview = symbols.get_symbols_overview(tmp_path)
        assert len(overview) == 2
        assert overview[0].name == "ClassA"
        assert overview[1].name == "func_b"

    @pytest.mark.functional
    def test_workspace_initialization_with_files(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Initialize workspace with file list in one call."""
        _setup_responses(
            mock_server,
            [
                # activate_project
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                # list_dir for file1
                {"jsonrpc": "2.0", "id": 2, "result": {}},
                # list_dir for file2
                {"jsonrpc": "2.0", "id": 3, "result": {}},
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)

        files = [tmp_path / "src" / "main.py", tmp_path / "src" / "utils.py"]
        workspace.initialize_workspace(tmp_path, files=files)

        # 3 calls: activate + 2 list_dir
        assert mock_server._process.stdin.write.call_count == 3


class TestDependencyExtractionFlow:
    """Functional tests for dependency extraction workflow."""

    @pytest.mark.functional
    def test_initialize_extract_dependencies_flow(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Full flow: initialize -> extract dependencies."""
        _setup_responses(
            mock_server,
            [
                # activate_project
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                # find_symbol for dependency extraction
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "references": [
                            {"name": "UserService"},
                            {"name": "AuthHandler"},
                            {"name": "Database"},
                        ]
                    },
                },
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)
        extractor = DependencyExtractor(client)

        workspace.initialize_workspace(tmp_path)
        deps = extractor.extract_dependencies("User", tmp_path)

        assert len(deps) == 3
        assert "UserService" in deps
        assert "AuthHandler" in deps
        assert "Database" in deps


class TestPyrightConfigurationFlow:
    """Functional tests for Pyright configuration workflow."""

    @pytest.mark.functional
    def test_configure_pyright_and_start_server(
        self, tmp_path: Path
    ) -> None:
        """Full flow: configure pyright -> start server with config."""
        # Step 1: Configure pyright
        config = PyrightConfig(
            include=["src/**/*.py"],
            type_checking_mode="strict",
        )
        configurator = PyrightConfigurator()
        configurator.configure_pyright(tmp_path, config=config)

        config_path = tmp_path / "pyrightconfig.json"
        assert config_path.exists()

        data = json.loads(config_path.read_text())
        assert data["typeCheckingMode"] == "strict"
        assert data["include"] == ["src/**/*.py"]

        # Step 2: Start server with pyright config
        with patch("zerorepo.serena.server.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 99999
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            server = SerenaMCPServer()
            server.start(tmp_path, pyright_config=config_path)

            cmd = mock_popen.call_args[0][0]
            assert "--pyright-config" in cmd
            assert str(config_path.resolve()) in cmd

            server.stop()

    @pytest.mark.functional
    def test_pyright_default_config(self, tmp_path: Path) -> None:
        """Default pyright config should be valid."""
        configurator = PyrightConfigurator()
        configurator.configure_pyright(tmp_path)

        config_path = tmp_path / "pyrightconfig.json"
        data = json.loads(config_path.read_text())

        # Verify all default keys present
        assert "include" in data
        assert "exclude" in data
        assert "typeCheckingMode" in data
        assert "reportMissingImports" in data

        # Verify defaults
        assert data["typeCheckingMode"] == "basic"
        assert data["reportMissingImports"] is True


class TestServerLifecycleFlow:
    """Functional tests for server lifecycle management."""

    @pytest.mark.functional
    def test_context_manager_full_flow(self, tmp_path: Path) -> None:
        """Context manager should start and stop cleanly."""
        with patch("zerorepo.serena.server.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            with SerenaMCPServer() as server:
                server.start(tmp_path)
                assert server.is_running() is True

            # After exiting context, server should be stopped
            mock_process.terminate.assert_called_once()

    @pytest.mark.functional
    def test_restart_after_stop(self, tmp_path: Path) -> None:
        """Server should be restartable after stopping."""
        with patch("zerorepo.serena.server.subprocess.Popen") as mock_popen:
            mock_process1 = MagicMock()
            mock_process1.pid = 111
            mock_process1.poll.return_value = None

            mock_process2 = MagicMock()
            mock_process2.pid = 222
            mock_process2.poll.return_value = None

            mock_popen.side_effect = [mock_process1, mock_process2]

            server = SerenaMCPServer()

            # First start/stop
            server.start(tmp_path)
            assert server.is_running() is True
            server.stop()
            assert server._process is None

            # Second start/stop
            server.start(tmp_path)
            assert server.is_running() is True
            server.stop()


class TestErrorRecoveryFlow:
    """Functional tests for error handling and recovery."""

    @pytest.mark.functional
    def test_workspace_init_failure_recovery(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Failed workspace init should not leave manager in bad state."""
        # First call fails
        mock_server._process.stdout.readline.side_effect = [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -1, "message": "init failed"},
                }
            ).encode()
            + b"\n",
        ]

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)

        with pytest.raises(SerenaError):
            workspace.initialize_workspace(tmp_path)

        assert workspace._initialized is False

    @pytest.mark.functional
    def test_symbol_lookup_after_server_error(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Symbol lookup should raise clear error when server returns error."""
        _setup_responses(
            mock_server,
            [
                # activate_project succeeds
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                # find_symbol returns error
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "error": {"code": -32000, "message": "analysis failed"},
                },
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)
        symbols = SymbolLookup(client)

        workspace.initialize_workspace(tmp_path)

        with pytest.raises(SerenaError, match="Failed to find symbol"):
            symbols.find_symbol("Missing", tmp_path)

    @pytest.mark.functional
    def test_tool_not_found_error(self, mock_server: MagicMock) -> None:
        """Calling unsupported tool should raise ToolNotFoundError."""
        client = MCPClient(mock_server)

        with pytest.raises(ToolNotFoundError) as exc_info:
            client.call_tool("unsupported_tool", {})

        assert exc_info.value.tool_name == "unsupported_tool"
        assert len(exc_info.value.available_tools) > 0


class TestMultiComponentIntegration:
    """Tests combining multiple Serena components together."""

    @pytest.mark.functional
    def test_full_analysis_pipeline(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Full pipeline: pyright -> workspace -> symbols -> deps."""
        # Step 1: Configure pyright
        configurator = PyrightConfigurator()
        configurator.configure_pyright(
            tmp_path,
            PyrightConfig(type_checking_mode="strict"),
        )

        # Step 2: Setup MCP responses for remaining steps
        _setup_responses(
            mock_server,
            [
                # activate_project
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                # list_dir for add_file
                {"jsonrpc": "2.0", "id": 2, "result": {}},
                # find_symbol
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "result": {
                        "symbols": [
                            {
                                "name": "RPGNode",
                                "kind": "class",
                                "filepath": "src/models/node.py",
                                "line": 19,
                            }
                        ]
                    },
                },
                # find_symbol for dependencies
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {
                        "references": [
                            {"name": "RPGGraph"},
                            {"name": "NodeBuilder"},
                        ]
                    },
                },
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)
        symbols = SymbolLookup(client)
        extractor = DependencyExtractor(client)

        # Step 3: Initialize workspace and add files
        workspace.initialize_workspace(tmp_path)
        workspace.add_file(tmp_path / "src" / "models" / "node.py")

        # Step 4: Find symbol
        result = symbols.find_symbol("RPGNode", tmp_path)
        assert result is not None
        assert result.name == "RPGNode"

        # Step 5: Extract dependencies
        deps = extractor.extract_dependencies("RPGNode", tmp_path)
        assert "RPGGraph" in deps
        assert "NodeBuilder" in deps

        # Step 6: Verify pyright config exists
        assert (tmp_path / "pyrightconfig.json").exists()

    @pytest.mark.functional
    def test_symbols_overview_with_workspace(
        self, mock_server: MagicMock, tmp_path: Path
    ) -> None:
        """Get symbols overview after workspace initialization."""
        _setup_responses(
            mock_server,
            [
                # activate_project
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                # get_symbols_overview
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "symbols": [
                            {
                                "name": "RPGNode",
                                "kind": "class",
                                "filepath": "node.py",
                                "line": 19,
                            },
                            {
                                "name": "RPGEdge",
                                "kind": "class",
                                "filepath": "edge.py",
                                "line": 10,
                            },
                            {
                                "name": "RPGGraph",
                                "kind": "class",
                                "filepath": "graph.py",
                                "line": 15,
                            },
                        ]
                    },
                },
            ],
        )

        client = MCPClient(mock_server)
        workspace = WorkspaceManager(client)
        symbols = SymbolLookup(client)

        workspace.initialize_workspace(tmp_path)
        overview = symbols.get_symbols_overview(tmp_path)

        assert len(overview) == 3
        names = [s.name for s in overview]
        assert "RPGNode" in names
        assert "RPGEdge" in names
        assert "RPGGraph" in names
