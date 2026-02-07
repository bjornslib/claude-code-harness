"""Unit tests for codegen serena_editing and localization_orchestrator modules.

Tests SerenaEditor and LocalizationOrchestrator classes with
fully mocked Serena MCP and VectorStore dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from zerorepo.codegen.localization import (
    LocalizationTracker,
    RPGFuzzySearch,
)
from zerorepo.codegen.localization_models import LocalizationResult
from zerorepo.codegen.localization_orchestrator import LocalizationOrchestrator
from zerorepo.codegen.serena_editing import SerenaEditor
from zerorepo.models.enums import (
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.serena.exceptions import MCPError, SerenaError
from zerorepo.serena.models import SymbolInfo
from zerorepo.vectordb.models import SearchResult


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_node(
    *,
    name: str = "node",
    level: NodeLevel = NodeLevel.COMPONENT,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    node_id: UUID | None = None,
    test_status: TestStatus = TestStatus.PENDING,
    file_path: str | None = None,
    folder_path: str | None = None,
    docstring: str | None = None,
) -> RPGNode:
    kwargs: dict = dict(
        name=name,
        level=level,
        node_type=node_type,
        test_status=test_status,
    )
    if node_id is not None:
        kwargs["id"] = node_id
    if file_path is not None:
        kwargs["file_path"] = file_path
        if folder_path is not None:
            kwargs["folder_path"] = folder_path
    if docstring is not None:
        kwargs["docstring"] = docstring
    return RPGNode(**kwargs)


def _make_mock_client(
    *,
    find_result: dict | None = None,
    find_callers_result: dict | None = None,
    replace_result: dict | None = None,
    insert_result: dict | None = None,
    rename_result: dict | None = None,
    side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock MCPClient with configurable responses."""
    client = MagicMock()

    def call_tool(tool_name: str, arguments: dict) -> dict:
        if side_effect:
            raise side_effect
        if tool_name == "find_symbol":
            return find_result or {"symbols": []}
        if tool_name == "find_referencing_symbols":
            return find_callers_result or {"symbols": []}
        if tool_name == "replace_symbol_body":
            return replace_result or {}
        if tool_name == "insert_after_symbol":
            return insert_result or {}
        if tool_name == "rename_symbol":
            return rename_result or {"count": 0}
        return {}

    client.call_tool = MagicMock(side_effect=call_tool)
    return client


# --------------------------------------------------------------------------- #
#                           SerenaEditor Tests                                 #
# --------------------------------------------------------------------------- #


class TestSerenaEditor:
    """Tests for SerenaEditor."""

    def test_find_symbol_exact(self) -> None:
        """Locates a function by exact name."""
        client = _make_mock_client(
            find_result={
                "symbols": [
                    {
                        "name": "calculate_mean",
                        "kind": "function",
                        "filepath": "src/stats.py",
                        "line": 10,
                        "column": 0,
                        "docstring": "Calculate the arithmetic mean",
                    }
                ]
            }
        )
        lookup = MagicMock()
        editor = SerenaEditor(
            mcp_client=client,
            symbol_lookup=lookup,
            workspace_dir=Path("/workspace"),
        )

        symbols = editor.find_symbol("calculate_mean")

        assert len(symbols) == 1
        assert symbols[0].name == "calculate_mean"
        assert symbols[0].kind == "function"
        assert symbols[0].filepath == "src/stats.py"
        assert symbols[0].line == 10

    def test_find_symbol_not_found(self) -> None:
        """Returns empty list when symbol doesn't exist."""
        client = _make_mock_client(find_result={"symbols": []})
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        symbols = editor.find_symbol("nonexistent")

        assert symbols == []

    def test_find_symbol_serena_unavailable(self) -> None:
        """Returns empty list when Serena is unavailable."""
        editor = SerenaEditor(mcp_client=None, symbol_lookup=None)

        symbols = editor.find_symbol("anything")

        assert symbols == []

    def test_find_symbol_mcp_error(self) -> None:
        """Returns empty list on MCP error."""
        client = _make_mock_client(side_effect=MCPError("server down"))
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        symbols = editor.find_symbol("test")

        assert symbols == []

    def test_find_callers(self) -> None:
        """Finds symbols that reference the given name."""
        client = _make_mock_client(
            find_callers_result={
                "symbols": [
                    {
                        "name": "test_calculate_mean",
                        "kind": "function",
                        "filepath": "tests/test_stats.py",
                        "line": 5,
                    },
                    {
                        "name": "main",
                        "kind": "function",
                        "filepath": "src/app.py",
                        "line": 20,
                    },
                ]
            }
        )
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        callers = editor.find_callers("calculate_mean")

        assert len(callers) == 2
        assert callers[0].name == "test_calculate_mean"
        assert callers[1].name == "main"

    def test_replace_symbol_body(self) -> None:
        """Replaces function body without breaking signature."""
        client = _make_mock_client()
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        new_code = "def calculate_mean(values):\n    return sum(values) / len(values)\n"
        result = editor.replace_body("src/stats.py", "calculate_mean", new_code)

        assert result is True
        client.call_tool.assert_called_once_with(
            "replace_symbol_body",
            {
                "filepath": "src/stats.py",
                "symbol_name": "calculate_mean",
                "new_code": new_code,
            },
        )

    def test_replace_body_serena_unavailable(self) -> None:
        """Returns False when Serena is unavailable."""
        editor = SerenaEditor(mcp_client=None, symbol_lookup=None)

        result = editor.replace_body(
            "src/stats.py", "func", "def func():\n    pass\n"
        )

        assert result is False

    def test_syntax_validation_rejects_invalid(self) -> None:
        """Rejects syntactically invalid Python code."""
        client = _make_mock_client()
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        result = editor.replace_body(
            "src/test.py", "func", "def broken(:\n  return\n"
        )

        assert result is False
        # Client should NOT have been called
        client.call_tool.assert_not_called()

    def test_syntax_validation_accepts_valid(self) -> None:
        """Accepts syntactically valid Python code."""
        assert SerenaEditor._validate_syntax("x = 1\n") is True
        assert SerenaEditor._validate_syntax("def f(): pass\n") is True
        assert SerenaEditor._validate_syntax("class C:\n    pass\n") is True

    def test_syntax_validation_rejects_invalid_static(self) -> None:
        """Rejects syntactically invalid Python code (static method)."""
        assert SerenaEditor._validate_syntax("def broken(:\n") is False
        assert SerenaEditor._validate_syntax("class {\n") is False

    def test_insert_after(self) -> None:
        """Inserts code after a symbol."""
        client = _make_mock_client()
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        code = "def helper():\n    return True\n"
        result = editor.insert_after("src/test.py", "main", code)

        assert result is True

    def test_insert_after_invalid_syntax(self) -> None:
        """Rejects insertion of invalid syntax."""
        client = _make_mock_client()
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        result = editor.insert_after("src/test.py", "main", "def bad(:\n")

        assert result is False

    def test_rename_symbol(self) -> None:
        """Renames a symbol across the workspace."""
        client = _make_mock_client(rename_result={"count": 5})
        lookup = MagicMock()
        editor = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        count = editor.rename_symbol("old_name", "new_name")

        assert count == 5

    def test_rename_symbol_unavailable(self) -> None:
        """Returns 0 when Serena is unavailable."""
        editor = SerenaEditor(mcp_client=None, symbol_lookup=None)

        count = editor.rename_symbol("old", "new")

        assert count == 0

    def test_is_available(self) -> None:
        """is_available reflects client + lookup presence."""
        assert SerenaEditor(mcp_client=MagicMock(), symbol_lookup=MagicMock()).is_available
        assert not SerenaEditor(mcp_client=None, symbol_lookup=None).is_available
        assert not SerenaEditor(mcp_client=MagicMock(), symbol_lookup=None).is_available


# --------------------------------------------------------------------------- #
#                    LocalizationOrchestrator Tests                             #
# --------------------------------------------------------------------------- #


class TestLocalizationOrchestrator:
    """Tests for LocalizationOrchestrator."""

    def test_serena_first_success(self) -> None:
        """Tries Serena first and succeeds."""
        node = _make_node(
            name="calculate_mean",
            node_id=uuid4(),
            file_path="src/stats/mean.py",
            folder_path="src/stats",
        )

        # Set up SerenaEditor that finds the symbol
        client = _make_mock_client(
            find_result={
                "symbols": [
                    {
                        "name": "calculate_mean",
                        "kind": "function",
                        "filepath": "src/stats/mean.py",
                        "line": 10,
                        "docstring": "Calculate the arithmetic mean",
                    }
                ]
            }
        )
        lookup = MagicMock()
        serena = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        mock_store = MagicMock()
        graph = RPGGraph()
        graph.add_node(node)
        fuzzy = RPGFuzzySearch(graph, mock_store)
        tracker = LocalizationTracker()

        orchestrator = LocalizationOrchestrator(serena, fuzzy, tracker)

        error_msg = 'File "src/stats/mean.py", line 10, in calculate_mean\n  ZeroDivisionError'
        result = orchestrator.localize_bug(node, error_msg)

        assert result is not None
        assert result.source == "serena"
        assert result.score == 1.0
        assert result.symbol_name == "calculate_mean"
        # VectorStore should NOT have been called (Serena succeeded)
        mock_store.search.assert_not_called()

    def test_serena_fails_fallback_to_fuzzy(self) -> None:
        """Serena fails, RPG fuzzy search succeeds."""
        node_id = uuid4()
        node = _make_node(
            name="process_data",
            node_id=node_id,
            file_path="src/data/process.py",
            folder_path="src/data",
        )

        # Serena returns no results
        client = _make_mock_client(find_result={"symbols": []})
        lookup = MagicMock()
        serena = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        # Fuzzy search finds it
        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(
                document="process_data Process input data and validate",
                score=0.8,
                metadata={"node_id": str(node_id)},
            )
        ]

        graph = RPGGraph()
        graph.add_node(node)
        fuzzy = RPGFuzzySearch(graph, mock_store)
        tracker = LocalizationTracker()

        orchestrator = LocalizationOrchestrator(serena, fuzzy, tracker)

        result = orchestrator.localize_bug(node, "TypeError: invalid argument")

        assert result is not None
        assert result.source == "rpg_fuzzy"
        assert result.score > 0.0
        # Both Serena and fuzzy were tried
        assert tracker.attempt_count == 2

    def test_both_strategies_fail(self) -> None:
        """Both Serena and RPG fuzzy return None."""
        node = _make_node(name="mystery_func", node_id=uuid4())

        client = _make_mock_client(find_result={"symbols": []})
        lookup = MagicMock()
        serena = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        mock_store = MagicMock()
        mock_store.search.return_value = []
        graph = RPGGraph()
        graph.add_node(node)
        fuzzy = RPGFuzzySearch(graph, mock_store)

        orchestrator = LocalizationOrchestrator(serena, fuzzy)

        result = orchestrator.localize_bug(node, "Unknown error")

        assert result is None

    def test_serena_unavailable_goes_to_fuzzy(self) -> None:
        """When Serena is unavailable, goes straight to fuzzy search."""
        node_id = uuid4()
        node = _make_node(
            name="validate_input",
            node_id=node_id,
            file_path="src/validation.py",
            folder_path="src",
        )

        serena = SerenaEditor(mcp_client=None, symbol_lookup=None)

        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(
                document="validate_input",
                score=0.85,
                metadata={"node_id": str(node_id)},
            )
        ]

        graph = RPGGraph()
        graph.add_node(node)
        fuzzy = RPGFuzzySearch(graph, mock_store)
        tracker = LocalizationTracker()

        orchestrator = LocalizationOrchestrator(serena, fuzzy, tracker)

        result = orchestrator.localize_bug(node, "ValueError: bad input")

        assert result is not None

    def test_extract_function_name_from_traceback(self) -> None:
        """Extracts function name from Python traceback."""
        error = 'File "src/stats.py", line 10, in calculate_mean\n  ZeroDivisionError'
        name = LocalizationOrchestrator._extract_function_name(error)
        assert name == "calculate_mean"

    def test_extract_function_name_module_level(self) -> None:
        """Ignores <module> in traceback."""
        error = 'File "main.py", line 1, in <module>'
        name = LocalizationOrchestrator._extract_function_name(error)
        assert name is None

    def test_extract_function_name_no_match(self) -> None:
        """Returns None when no function name found."""
        name = LocalizationOrchestrator._extract_function_name("generic error")
        assert name is None

    def test_tracker_is_accessible(self) -> None:
        """Orchestrator exposes its tracker."""
        serena = SerenaEditor()
        mock_store = MagicMock()
        graph = RPGGraph()
        fuzzy = RPGFuzzySearch(graph, mock_store)
        tracker = LocalizationTracker(max_attempts=10)

        orchestrator = LocalizationOrchestrator(serena, fuzzy, tracker)

        assert orchestrator.tracker is tracker
        assert orchestrator.tracker.max_attempts == 10

    def test_no_duplicate_queries(self) -> None:
        """Orchestrator avoids re-running identical queries."""
        node = _make_node(name="func", node_id=uuid4())

        client = _make_mock_client(find_result={"symbols": []})
        lookup = MagicMock()
        serena = SerenaEditor(mcp_client=client, symbol_lookup=lookup)

        mock_store = MagicMock()
        mock_store.search.return_value = []
        graph = RPGGraph()
        graph.add_node(node)
        fuzzy = RPGFuzzySearch(graph, mock_store)
        tracker = LocalizationTracker()

        orchestrator = LocalizationOrchestrator(serena, fuzzy, tracker)

        # First call
        orchestrator.localize_bug(node, "error")
        first_count = tracker.attempt_count

        # Second call with same error - should skip already-queried
        orchestrator.localize_bug(node, "error")
        second_count = tracker.attempt_count

        # Should not have added duplicate queries
        assert second_count == first_count
