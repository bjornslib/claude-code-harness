"""Unit tests for the Serena MCP integration module.

All tests mock subprocess and MCP calls since no external processes
are available. Uses unittest.mock.patch for:
- subprocess.Popen (server lifecycle)
- MCP client communication (JSON-RPC responses)
- File system operations where needed
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from pydantic import ValidationError

from zerorepo.serena.client import MCPClient, SUPPORTED_TOOLS
from zerorepo.serena.dependencies import DependencyExtractor
from zerorepo.serena.exceptions import MCPError, SerenaError, ToolNotFoundError
from zerorepo.serena.models import PyrightConfig, SymbolInfo
from zerorepo.serena.pyright import PyrightConfigurator
from zerorepo.serena.server import SerenaMCPServer
from zerorepo.serena.symbols import SymbolLookup
from zerorepo.serena.workspace import WorkspaceManager


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestSymbolInfo:
    """Tests for the SymbolInfo model."""

    def test_create_basic(self) -> None:
        info = SymbolInfo(
            name="MyClass",
            kind="class",
            filepath="src/mymodule.py",
            line=10,
        )
        assert info.name == "MyClass"
        assert info.kind == "class"
        assert info.filepath == "src/mymodule.py"
        assert info.line == 10
        assert info.column == 0
        assert info.docstring is None

    def test_create_full(self) -> None:
        info = SymbolInfo(
            name="my_func",
            kind="function",
            filepath="src/utils.py",
            line=42,
            column=4,
            docstring="A utility function.",
        )
        assert info.name == "my_func"
        assert info.kind == "function"
        assert info.column == 4
        assert info.docstring == "A utility function."

    def test_line_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SymbolInfo(name="x", kind="function", filepath="a.py", line=0)

    def test_column_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            SymbolInfo(
                name="x", kind="function", filepath="a.py", line=1, column=-1
            )

    def test_serialization_roundtrip(self) -> None:
        info = SymbolInfo(
            name="Foo",
            kind="class",
            filepath="foo.py",
            line=5,
            column=0,
            docstring="Foo class.",
        )
        data = info.model_dump()
        restored = SymbolInfo.model_validate(data)
        assert restored == info

    def test_json_roundtrip(self) -> None:
        info = SymbolInfo(
            name="bar", kind="method", filepath="bar.py", line=20
        )
        json_str = info.model_dump_json()
        restored = SymbolInfo.model_validate_json(json_str)
        assert restored == info


class TestPyrightConfig:
    """Tests for the PyrightConfig model."""

    def test_defaults(self) -> None:
        config = PyrightConfig()
        assert config.include == ["**/*.py"]
        assert config.exclude == ["**/node_modules", "**/__pycache__"]
        assert config.type_checking_mode == "basic"
        assert config.report_missing_imports is True

    def test_custom_values(self) -> None:
        config = PyrightConfig(
            include=["src/**/*.py"],
            exclude=["tests/**"],
            type_checking_mode="strict",
            report_missing_imports=False,
        )
        assert config.include == ["src/**/*.py"]
        assert config.exclude == ["tests/**"]
        assert config.type_checking_mode == "strict"
        assert config.report_missing_imports is False

    def test_separate_default_lists(self) -> None:
        """Ensure separate instances get separate default lists."""
        config1 = PyrightConfig()
        config2 = PyrightConfig()
        config1.include.append("extra/**/*.py")
        assert "extra/**/*.py" not in config2.include

    def test_serialization_roundtrip(self) -> None:
        config = PyrightConfig(
            include=["src/**"], type_checking_mode="standard"
        )
        data = config.model_dump()
        restored = PyrightConfig.model_validate(data)
        assert restored == config


# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestSerenaError:
    """Tests for SerenaError exception."""

    def test_basic_error(self) -> None:
        exc = SerenaError("something went wrong")
        assert str(exc) == "something went wrong"

    def test_is_exception(self) -> None:
        assert issubclass(SerenaError, Exception)


class TestMCPError:
    """Tests for MCPError exception."""

    def test_with_code(self) -> None:
        exc = MCPError("tool failed", code=-32601)
        assert exc.code == -32601
        assert exc.message == "tool failed"
        assert "-32601" in str(exc)
        assert "tool failed" in str(exc)

    def test_without_code(self) -> None:
        exc = MCPError("generic failure")
        assert exc.code is None
        assert "generic failure" in str(exc)
        assert "code=" not in str(exc)

    def test_inherits_serena_error(self) -> None:
        assert issubclass(MCPError, SerenaError)


class TestToolNotFoundError:
    """Tests for ToolNotFoundError exception."""

    def test_basic(self) -> None:
        exc = ToolNotFoundError("nonexistent_tool")
        assert exc.tool_name == "nonexistent_tool"
        assert exc.available_tools == []
        assert "nonexistent_tool" in str(exc)

    def test_with_available_tools(self) -> None:
        exc = ToolNotFoundError(
            "bad_tool", available_tools=["find_symbol", "list_dir"]
        )
        assert exc.tool_name == "bad_tool"
        assert exc.available_tools == ["find_symbol", "list_dir"]
        assert "find_symbol" in str(exc)
        assert "list_dir" in str(exc)

    def test_inherits_serena_error(self) -> None:
        assert issubclass(ToolNotFoundError, SerenaError)


# ---------------------------------------------------------------------------
# SerenaMCPServer Tests
# ---------------------------------------------------------------------------


class TestSerenaMCPServerInit:
    """Tests for SerenaMCPServer initialization."""

    def test_init_no_process(self) -> None:
        server = SerenaMCPServer()
        assert server._process is None

    def test_not_running_initially(self) -> None:
        server = SerenaMCPServer()
        assert server.is_running() is False


class TestSerenaMCPServerStart:
    """Tests for server start lifecycle."""

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_start_launches_process(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "npx" in cmd
        assert "@anthropic/serena-mcp" in cmd
        assert "--workspace" in cmd
        assert str(tmp_path.resolve()) in cmd

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_start_with_pyright_config(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        pyright_path = tmp_path / "pyrightconfig.json"
        server = SerenaMCPServer()
        server.start(tmp_path, pyright_config=pyright_path)

        cmd = mock_popen.call_args[0][0]
        assert "--pyright-config" in cmd
        assert str(pyright_path.resolve()) in cmd

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_start_sets_stdio_pipes(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)

        import subprocess

        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["stdin"] == subprocess.PIPE
        assert call_kwargs["stdout"] == subprocess.PIPE
        assert call_kwargs["stderr"] == subprocess.PIPE

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_start_raises_if_already_running(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)

        with pytest.raises(SerenaError, match="already running"):
            server.start(tmp_path)

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_start_raises_on_file_not_found(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_popen.side_effect = FileNotFoundError("npx not found")

        server = SerenaMCPServer()
        with pytest.raises(SerenaError, match="npx not found"):
            server.start(tmp_path)

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_start_raises_on_os_error(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_popen.side_effect = OSError("permission denied")

        server = SerenaMCPServer()
        with pytest.raises(SerenaError, match="Failed to start"):
            server.start(tmp_path)


class TestSerenaMCPServerStop:
    """Tests for server stop lifecycle."""

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_stop_terminates_process(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)
        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert server._process is None

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_stop_kills_on_timeout(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        import subprocess

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired("serena", 5),
            None,
        ]
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)
        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_stop_noop_when_not_running(self) -> None:
        server = SerenaMCPServer()
        # Should not raise
        server.stop()

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_stop_handles_os_error(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.terminate.side_effect = OSError("process gone")
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)
        # Should not raise
        server.stop()
        assert server._process is None


class TestSerenaMCPServerIsRunning:
    """Tests for the is_running check."""

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_is_running_true(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)
        assert server.is_running() is True

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_is_running_false_after_exit(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        server = SerenaMCPServer()
        server.start(tmp_path)
        assert server.is_running() is False


class TestSerenaMCPServerContextManager:
    """Tests for context manager support."""

    @patch("zerorepo.serena.server.subprocess.Popen")
    def test_context_manager_stops_on_exit(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        with SerenaMCPServer() as server:
            server.start(tmp_path)
            assert server.is_running() is True

        mock_process.terminate.assert_called_once()

    def test_context_manager_without_start(self) -> None:
        with SerenaMCPServer() as server:
            assert server.is_running() is False
        # Should not raise


# ---------------------------------------------------------------------------
# MCPClient Tests
# ---------------------------------------------------------------------------


class TestMCPClientInit:
    """Tests for MCPClient initialization."""

    def test_init(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        client = MCPClient(server)
        assert client._server is server
        assert client._request_id == 0


class TestMCPClientListTools:
    """Tests for listing available tools."""

    def test_list_tools(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        client = MCPClient(server)
        tools = client.list_tools()
        assert isinstance(tools, list)
        assert "find_symbol" in tools
        assert "activate_project" in tools
        assert "get_symbols_overview" in tools
        assert "list_dir" in tools
        # Should be sorted
        assert tools == sorted(tools)

    def test_supported_tools_constant(self) -> None:
        assert "activate_project" in SUPPORTED_TOOLS
        assert "find_symbol" in SUPPORTED_TOOLS
        assert "get_symbols_overview" in SUPPORTED_TOOLS
        assert "list_dir" in SUPPORTED_TOOLS


class TestMCPClientCallTool:
    """Tests for MCP tool invocation."""

    def _make_server_with_response(
        self, response: dict
    ) -> MagicMock:
        """Create a mock server that returns a given JSON-RPC response."""
        server = MagicMock(spec=SerenaMCPServer)
        server.is_running.return_value = True

        mock_process = MagicMock()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()

        response_bytes = json.dumps(response).encode("utf-8") + b"\n"
        mock_stdout.readline.return_value = response_bytes

        mock_process.stdin = mock_stdin
        mock_process.stdout = mock_stdout
        server._process = mock_process

        return server

    def test_call_tool_success(self) -> None:
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"symbols": [{"name": "Foo", "kind": "class"}]},
        }
        server = self._make_server_with_response(response)
        client = MCPClient(server)

        result = client.call_tool("find_symbol", {"name": "Foo"})
        assert result == {"symbols": [{"name": "Foo", "kind": "class"}]}

    def test_call_tool_sends_json_rpc(self) -> None:
        response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        server = self._make_server_with_response(response)
        client = MCPClient(server)

        client.call_tool("activate_project", {"workspace_dir": "/tmp"})

        written = server._process.stdin.write.call_args[0][0]
        request = json.loads(written.decode("utf-8"))
        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "tools/call"
        assert request["params"]["name"] == "activate_project"
        assert request["params"]["arguments"] == {"workspace_dir": "/tmp"}

    def test_call_tool_increments_id(self) -> None:
        response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        server = self._make_server_with_response(response)
        client = MCPClient(server)

        client.call_tool("list_dir", {"path": "."})
        client.call_tool("list_dir", {"path": ".."})

        first_call = json.loads(
            server._process.stdin.write.call_args_list[0][0][0].decode()
        )
        second_call = json.loads(
            server._process.stdin.write.call_args_list[1][0][0].decode()
        )
        assert first_call["id"] == 1
        assert second_call["id"] == 2

    def test_call_tool_unsupported_raises(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        client = MCPClient(server)

        with pytest.raises(ToolNotFoundError, match="nonexistent"):
            client.call_tool("nonexistent", {})

    def test_call_tool_server_not_running_raises(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        server.is_running.return_value = False
        client = MCPClient(server)

        with pytest.raises(MCPError, match="not running"):
            client.call_tool("find_symbol", {"name": "Foo"})

    def test_call_tool_server_error_response(self) -> None:
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        }
        server = self._make_server_with_response(response)
        client = MCPClient(server)

        with pytest.raises(MCPError, match="Method not found") as exc_info:
            client.call_tool("find_symbol", {"name": "x"})
        assert exc_info.value.code == -32601

    def test_call_tool_empty_response_raises(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        server.is_running.return_value = True

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline.return_value = b""
        server._process = mock_process

        client = MCPClient(server)
        with pytest.raises(MCPError, match="No response"):
            client.call_tool("find_symbol", {"name": "x"})

    def test_call_tool_invalid_json_raises(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        server.is_running.return_value = True

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline.return_value = b"not valid json\n"
        server._process = mock_process

        client = MCPClient(server)
        with pytest.raises(MCPError, match="Invalid response"):
            client.call_tool("find_symbol", {"name": "x"})

    def test_call_tool_os_error_raises(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        server.is_running.return_value = True

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write.side_effect = OSError("broken pipe")
        mock_process.stdout = MagicMock()
        server._process = mock_process

        client = MCPClient(server)
        with pytest.raises(MCPError, match="Communication error"):
            client.call_tool("find_symbol", {"name": "x"})

    def test_call_tool_process_none_raises(self) -> None:
        server = MagicMock(spec=SerenaMCPServer)
        server.is_running.return_value = True
        server._process = None

        client = MCPClient(server)
        with pytest.raises(MCPError, match="not available"):
            client.call_tool("find_symbol", {"name": "x"})

    def test_call_tool_result_missing_defaults_empty(self) -> None:
        response = {"jsonrpc": "2.0", "id": 1}
        server = self._make_server_with_response(response)
        client = MCPClient(server)

        result = client.call_tool("find_symbol", {"name": "Foo"})
        assert result == {}


# ---------------------------------------------------------------------------
# WorkspaceManager Tests
# ---------------------------------------------------------------------------


class TestWorkspaceManagerInit:
    """Tests for WorkspaceManager initialization."""

    def test_init(self) -> None:
        client = MagicMock(spec=MCPClient)
        manager = WorkspaceManager(client)
        assert manager._client is client
        assert manager._initialized is False
        assert manager._workspace_dir is None


class TestWorkspaceManagerInitialize:
    """Tests for workspace initialization."""

    def test_initialize_workspace(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {}

        manager = WorkspaceManager(client)
        manager.initialize_workspace(tmp_path)

        client.call_tool.assert_called_once_with(
            "activate_project",
            {"workspace_dir": str(tmp_path.resolve())},
        )
        assert manager._initialized is True
        assert manager._workspace_dir == tmp_path

    def test_initialize_workspace_with_files(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {}

        files = [tmp_path / "a.py", tmp_path / "b.py"]
        manager = WorkspaceManager(client)
        manager.initialize_workspace(tmp_path, files=files)

        # activate_project + 2 list_dir calls
        assert client.call_tool.call_count == 3

    def test_initialize_workspace_failure(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.side_effect = MCPError("connection failed")

        manager = WorkspaceManager(client)
        with pytest.raises(SerenaError, match="Failed to initialize"):
            manager.initialize_workspace(tmp_path)


class TestWorkspaceManagerAddFile:
    """Tests for adding files to workspace."""

    def test_add_file(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {}

        manager = WorkspaceManager(client)
        manager.initialize_workspace(tmp_path)

        filepath = tmp_path / "src" / "main.py"
        manager.add_file(filepath)

        # Second call should be list_dir with parent
        calls = client.call_tool.call_args_list
        assert calls[1][0][0] == "list_dir"
        assert calls[1][0][1]["path"] == str(filepath.parent)

    def test_add_file_not_initialized(self) -> None:
        client = MagicMock(spec=MCPClient)
        manager = WorkspaceManager(client)

        with pytest.raises(SerenaError, match="not initialized"):
            manager.add_file(Path("/some/file.py"))

    def test_add_file_failure(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        # First call (activate) succeeds, second (list_dir) fails
        client.call_tool.side_effect = [
            {},
            MCPError("list_dir failed"),
        ]

        manager = WorkspaceManager(client)
        manager.initialize_workspace(tmp_path)

        with pytest.raises(SerenaError, match="Failed to add file"):
            manager.add_file(tmp_path / "broken.py")


# ---------------------------------------------------------------------------
# SymbolLookup Tests
# ---------------------------------------------------------------------------


class TestSymbolLookupInit:
    """Tests for SymbolLookup initialization."""

    def test_init(self) -> None:
        client = MagicMock(spec=MCPClient)
        lookup = SymbolLookup(client)
        assert lookup._client is client


class TestSymbolLookupFindSymbol:
    """Tests for finding individual symbols."""

    def test_find_symbol_found(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {
            "symbols": [
                {
                    "name": "MyClass",
                    "kind": "class",
                    "filepath": "src/mymodule.py",
                    "line": 10,
                    "column": 0,
                    "docstring": "My class.",
                }
            ]
        }

        lookup = SymbolLookup(client)
        result = lookup.find_symbol("MyClass", tmp_path)

        assert result is not None
        assert isinstance(result, SymbolInfo)
        assert result.name == "MyClass"
        assert result.kind == "class"
        assert result.line == 10
        assert result.docstring == "My class."

    def test_find_symbol_not_found_empty_symbols(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {"symbols": []}

        lookup = SymbolLookup(client)
        result = lookup.find_symbol("NonExistent", tmp_path)

        assert result is None

    def test_find_symbol_not_found_no_symbols_key(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {}

        lookup = SymbolLookup(client)
        result = lookup.find_symbol("NonExistent", tmp_path)

        assert result is None

    def test_find_symbol_not_found_none_result(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = None

        lookup = SymbolLookup(client)
        result = lookup.find_symbol("NonExistent", tmp_path)

        assert result is None

    def test_find_symbol_failure(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.side_effect = MCPError("server down")

        lookup = SymbolLookup(client)
        with pytest.raises(SerenaError, match="Failed to find symbol"):
            lookup.find_symbol("MyClass", tmp_path)

    def test_find_symbol_returns_first_match(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {
            "symbols": [
                {"name": "Foo", "kind": "class", "filepath": "a.py", "line": 1},
                {"name": "Foo", "kind": "function", "filepath": "b.py", "line": 5},
            ]
        }

        lookup = SymbolLookup(client)
        result = lookup.find_symbol("Foo", tmp_path)

        assert result is not None
        assert result.kind == "class"
        assert result.filepath == "a.py"


class TestSymbolLookupGetOverview:
    """Tests for getting symbols overview."""

    def test_get_symbols_overview(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {
            "symbols": [
                {"name": "Foo", "kind": "class", "filepath": "a.py", "line": 1},
                {
                    "name": "bar",
                    "kind": "function",
                    "filepath": "b.py",
                    "line": 10,
                    "docstring": "Bar func.",
                },
            ]
        }

        lookup = SymbolLookup(client)
        symbols = lookup.get_symbols_overview(tmp_path)

        assert len(symbols) == 2
        assert all(isinstance(s, SymbolInfo) for s in symbols)
        assert symbols[0].name == "Foo"
        assert symbols[1].name == "bar"
        assert symbols[1].docstring == "Bar func."

    def test_get_symbols_overview_empty(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {"symbols": []}

        lookup = SymbolLookup(client)
        symbols = lookup.get_symbols_overview(tmp_path)

        assert symbols == []

    def test_get_symbols_overview_no_symbols_key(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {}

        lookup = SymbolLookup(client)
        symbols = lookup.get_symbols_overview(tmp_path)

        assert symbols == []

    def test_get_symbols_overview_failure(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.side_effect = MCPError("server error")

        lookup = SymbolLookup(client)
        with pytest.raises(SerenaError, match="Failed to get symbols"):
            lookup.get_symbols_overview(tmp_path)


# ---------------------------------------------------------------------------
# PyrightConfigurator Tests
# ---------------------------------------------------------------------------


class TestPyrightConfigurator:
    """Tests for Pyright configuration generation."""

    def test_configure_default(self, tmp_path: Path) -> None:
        configurator = PyrightConfigurator()
        configurator.configure_pyright(tmp_path)

        config_path = tmp_path / "pyrightconfig.json"
        assert config_path.exists()

        data = json.loads(config_path.read_text())
        assert data["include"] == ["**/*.py"]
        assert data["exclude"] == ["**/node_modules", "**/__pycache__"]
        assert data["typeCheckingMode"] == "basic"
        assert data["reportMissingImports"] is True

    def test_configure_custom(self, tmp_path: Path) -> None:
        config = PyrightConfig(
            include=["src/**/*.py"],
            exclude=["tests/**"],
            type_checking_mode="strict",
            report_missing_imports=False,
        )
        configurator = PyrightConfigurator()
        configurator.configure_pyright(tmp_path, config=config)

        data = json.loads((tmp_path / "pyrightconfig.json").read_text())
        assert data["include"] == ["src/**/*.py"]
        assert data["exclude"] == ["tests/**"]
        assert data["typeCheckingMode"] == "strict"
        assert data["reportMissingImports"] is False

    def test_configure_overwrites_existing(self, tmp_path: Path) -> None:
        config_path = tmp_path / "pyrightconfig.json"
        config_path.write_text('{"old": true}')

        configurator = PyrightConfigurator()
        configurator.configure_pyright(tmp_path)

        data = json.loads(config_path.read_text())
        assert "old" not in data
        assert "include" in data

    def test_configure_failure(self) -> None:
        configurator = PyrightConfigurator()
        # Use a path that doesn't exist as parent
        bad_path = Path("/nonexistent/directory/that/does/not/exist")
        with pytest.raises(SerenaError, match="Failed to write"):
            configurator.configure_pyright(bad_path)

    def test_configure_json_formatting(self, tmp_path: Path) -> None:
        configurator = PyrightConfigurator()
        configurator.configure_pyright(tmp_path)

        content = (tmp_path / "pyrightconfig.json").read_text()
        # Should be indented JSON with trailing newline
        assert content.endswith("\n")
        assert "  " in content  # indented


# ---------------------------------------------------------------------------
# DependencyExtractor Tests
# ---------------------------------------------------------------------------


class TestDependencyExtractorInit:
    """Tests for DependencyExtractor initialization."""

    def test_init(self) -> None:
        client = MagicMock(spec=MCPClient)
        extractor = DependencyExtractor(client)
        assert extractor._client is client


class TestDependencyExtractorExtract:
    """Tests for dependency extraction."""

    def test_extract_dependencies(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {
            "references": [
                {"name": "UserService"},
                {"name": "AuthMiddleware"},
            ]
        }

        extractor = DependencyExtractor(client)
        deps = extractor.extract_dependencies("User", tmp_path)

        assert deps == ["UserService", "AuthMiddleware"]

    def test_extract_dependencies_excludes_self(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {
            "references": [
                {"name": "User"},  # self-reference
                {"name": "UserService"},
            ]
        }

        extractor = DependencyExtractor(client)
        deps = extractor.extract_dependencies("User", tmp_path)

        assert "User" not in deps
        assert "UserService" in deps

    def test_extract_dependencies_empty(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {"references": []}

        extractor = DependencyExtractor(client)
        deps = extractor.extract_dependencies("Orphan", tmp_path)

        assert deps == []

    def test_extract_dependencies_no_references_key(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {}

        extractor = DependencyExtractor(client)
        deps = extractor.extract_dependencies("Orphan", tmp_path)

        assert deps == []

    def test_extract_dependencies_skips_empty_names(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.return_value = {
            "references": [
                {"name": ""},
                {"name": "Valid"},
            ]
        }

        extractor = DependencyExtractor(client)
        deps = extractor.extract_dependencies("Target", tmp_path)

        assert deps == ["Valid"]

    def test_extract_dependencies_failure(self, tmp_path: Path) -> None:
        client = MagicMock(spec=MCPClient)
        client.call_tool.side_effect = MCPError("server error")

        extractor = DependencyExtractor(client)
        with pytest.raises(SerenaError, match="Failed to extract"):
            extractor.extract_dependencies("Target", tmp_path)


# ---------------------------------------------------------------------------
# Import Tests
# ---------------------------------------------------------------------------


class TestSerenaImports:
    """Tests that the module's public API is correctly exported."""

    def test_import_from_package(self) -> None:
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

        assert SerenaMCPServer is not None
        assert MCPClient is not None
        assert WorkspaceManager is not None
        assert SymbolLookup is not None
        assert PyrightConfigurator is not None
        assert DependencyExtractor is not None
        assert SymbolInfo is not None
        assert PyrightConfig is not None
        assert SerenaError is not None
        assert MCPError is not None
        assert ToolNotFoundError is not None
