"""Unit tests for codegen localization module.

Tests RPGFuzzySearch, RepositoryCodeView, DependencyExplorer,
and LocalizationTracker classes.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from zerorepo.codegen.localization import (
    DependencyExplorer,
    LocalizationTracker,
    RPGFuzzySearch,
    RepositoryCodeView,
)
from zerorepo.codegen.localization_models import (
    DependencyMap,
    LocalizationExhaustedError,
    LocalizationResult,
)
from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
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
    parent_id: UUID | None = None,
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
    if parent_id is not None:
        kwargs["parent_id"] = parent_id
    if file_path is not None:
        kwargs["file_path"] = file_path
        if folder_path is not None:
            kwargs["folder_path"] = folder_path
    if docstring is not None:
        kwargs["docstring"] = docstring
    return RPGNode(**kwargs)


def _make_edge(
    source_id: UUID,
    target_id: UUID,
    edge_type: EdgeType = EdgeType.DATA_FLOW,
    *,
    edge_id: UUID | None = None,
) -> RPGEdge:
    kwargs: dict = dict(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
    )
    if edge_id is not None:
        kwargs["id"] = edge_id
    return RPGEdge(**kwargs)


def _build_abc_graph() -> tuple[RPGGraph, list[UUID]]:
    """Build A -> B -> C (DATA_FLOW edges)."""
    ids = [uuid4() for _ in range(3)]
    graph = RPGGraph()
    for i, uid in enumerate(ids):
        graph.add_node(
            _make_node(
                name=f"node_{chr(65+i)}",  # A, B, C
                node_id=uid,
                docstring=f"Description of node {chr(65+i)}",
            )
        )
    # A -> B
    graph.add_edge(_make_edge(ids[0], ids[1], EdgeType.DATA_FLOW))
    # B -> C
    graph.add_edge(_make_edge(ids[1], ids[2], EdgeType.DATA_FLOW))
    return graph, ids


# --------------------------------------------------------------------------- #
#                          RPGFuzzySearch Tests                                #
# --------------------------------------------------------------------------- #


class TestRPGFuzzySearch:
    """Tests for RPGFuzzySearch."""

    def test_fuzzy_search_exact_match(self) -> None:
        """'calculate mean' finds calculate_mean node."""
        node_id = uuid4()
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                name="calculate_mean",
                node_id=node_id,
                file_path="src/stats/mean.py",
                folder_path="src/stats",
                docstring="Calculate the arithmetic mean of a list of numbers",
            )
        )

        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(
                document="calculate_mean Calculate the arithmetic mean of a list of numbers",
                score=0.95,
                metadata={"node_id": str(node_id)},
            )
        ]

        searcher = RPGFuzzySearch(graph, mock_store)
        results = searcher.search("calculate mean", top_k=5)

        assert len(results) == 1
        assert results[0].node_id == node_id
        assert results[0].source == "rpg_fuzzy"
        assert results[0].score >= 0.9
        mock_store.search.assert_called_once()

    def test_fuzzy_search_semantic(self) -> None:
        """'average' finds calculate_mean node via semantic similarity."""
        node_id = uuid4()
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                name="calculate_mean",
                node_id=node_id,
                file_path="src/stats/mean.py",
                folder_path="src/stats",
                docstring="Calculate the arithmetic mean of a list of numbers",
            )
        )

        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(
                document="calculate_mean Calculate the arithmetic mean of a list of numbers",
                score=0.78,
                metadata={"node_id": str(node_id)},
            )
        ]

        searcher = RPGFuzzySearch(graph, mock_store)
        results = searcher.search("average", top_k=5)

        assert len(results) == 1
        assert results[0].node_id == node_id
        assert results[0].score > 0.0

    def test_fuzzy_search_empty_results(self) -> None:
        """Search returns empty list when no matches found."""
        graph = RPGGraph()
        mock_store = MagicMock()
        mock_store.search.return_value = []

        searcher = RPGFuzzySearch(graph, mock_store)
        results = searcher.search("nonexistent", top_k=5)

        assert results == []

    def test_fuzzy_search_with_subgraph_filter(self) -> None:
        """Search passes subgraph filter to the vector store."""
        graph = RPGGraph()
        mock_store = MagicMock()
        mock_store.search.return_value = []

        searcher = RPGFuzzySearch(graph, mock_store)
        searcher.search("query", top_k=5, subgraph_id="auth/login")

        mock_store.search.assert_called_once_with(
            query="query",
            top_k=5,
            filters={"path": "auth/login"},
        )

    def test_fuzzy_search_store_failure(self) -> None:
        """Search returns empty list on VectorStore failure."""
        graph = RPGGraph()
        mock_store = MagicMock()
        mock_store.search.side_effect = RuntimeError("DB error")

        searcher = RPGFuzzySearch(graph, mock_store)
        results = searcher.search("query", top_k=5)

        assert results == []

    def test_fuzzy_search_score_clamping(self) -> None:
        """Scores are clamped to [0.0, 1.0]."""
        graph = RPGGraph()
        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(document="test", score=1.5, metadata={}),
            SearchResult(document="test2", score=-0.3, metadata={}),
        ]

        searcher = RPGFuzzySearch(graph, mock_store)
        results = searcher.search("query")

        assert results[0].score == 1.0
        assert results[1].score == 0.0

    def test_fuzzy_search_multiple_results(self) -> None:
        """Search returns multiple results in score order."""
        id1, id2 = uuid4(), uuid4()
        graph = RPGGraph()
        graph.add_node(_make_node(name="func_a", node_id=id1, docstring="First function"))
        graph.add_node(_make_node(name="func_b", node_id=id2, docstring="Second function"))

        mock_store = MagicMock()
        mock_store.search.return_value = [
            SearchResult(document="func_a", score=0.9, metadata={"node_id": str(id1)}),
            SearchResult(document="func_b", score=0.7, metadata={"node_id": str(id2)}),
        ]

        searcher = RPGFuzzySearch(graph, mock_store)
        results = searcher.search("function", top_k=5)

        assert len(results) == 2
        assert results[0].score > results[1].score


# --------------------------------------------------------------------------- #
#                        RepositoryCodeView Tests                              #
# --------------------------------------------------------------------------- #


class TestRepositoryCodeView:
    """Tests for RepositoryCodeView."""

    def test_get_file_content(self, tmp_path: Path) -> None:
        """Reads file content correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")

        view = RepositoryCodeView(tmp_path)
        content = view.get_file_content("test.py")

        assert content == "print('hello')\n"

    def test_get_file_content_caching(self, tmp_path: Path) -> None:
        """File content is cached on repeated reads."""
        test_file = tmp_path / "test.py"
        test_file.write_text("original")

        view = RepositoryCodeView(tmp_path)
        first = view.get_file_content("test.py")
        test_file.write_text("modified")
        second = view.get_file_content("test.py")

        assert first == second == "original"

    def test_get_file_content_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for missing files."""
        view = RepositoryCodeView(tmp_path)
        with pytest.raises(FileNotFoundError):
            view.get_file_content("nonexistent.py")

    def test_get_signatures(self, tmp_path: Path) -> None:
        """Extracts function names and type hints from a Python file."""
        code = textwrap.dedent("""\
            def calculate_mean(values: list[float]) -> float:
                return sum(values) / len(values)

            class StatisticsEngine:
                def compute(self, data: list[int]) -> dict:
                    pass
        """)
        test_file = tmp_path / "stats.py"
        test_file.write_text(code)

        view = RepositoryCodeView(tmp_path)
        sigs = view.get_signatures("stats.py")

        assert any("calculate_mean" in s for s in sigs)
        assert any("StatisticsEngine" in s for s in sigs)
        assert any("compute" in s for s in sigs)
        # Check type hints are present
        assert any("list[float]" in s for s in sigs)

    def test_get_signatures_syntax_error(self, tmp_path: Path) -> None:
        """Returns empty list for files with syntax errors."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("def broken(:\n  pass\n")

        view = RepositoryCodeView(tmp_path)
        sigs = view.get_signatures("bad.py")

        assert sigs == []

    def test_get_function_body(self, tmp_path: Path) -> None:
        """Extracts a specific function body including def line."""
        code = textwrap.dedent("""\
            def foo():
                return 1

            def bar():
                return 2
        """)
        test_file = tmp_path / "funcs.py"
        test_file.write_text(code)

        view = RepositoryCodeView(tmp_path)
        body = view.get_function_body("funcs.py", "bar")

        assert "def bar()" in body
        assert "return 2" in body
        assert "def foo()" not in body

    def test_get_function_body_not_found(self, tmp_path: Path) -> None:
        """Raises ValueError when function doesn't exist."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("x = 1\n")

        view = RepositoryCodeView(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            view.get_function_body("empty.py", "nonexistent")

    def test_clear_cache(self, tmp_path: Path) -> None:
        """Cache can be cleared to force re-read."""
        test_file = tmp_path / "test.py"
        test_file.write_text("original")

        view = RepositoryCodeView(tmp_path)
        view.get_file_content("test.py")
        test_file.write_text("modified")
        view.clear_cache()
        content = view.get_file_content("test.py")

        assert content == "modified"

    def test_get_signatures_async_function(self, tmp_path: Path) -> None:
        """Extracts async function signatures."""
        code = textwrap.dedent("""\
            async def fetch_data(url: str) -> dict:
                pass
        """)
        test_file = tmp_path / "async_mod.py"
        test_file.write_text(code)

        view = RepositoryCodeView(tmp_path)
        sigs = view.get_signatures("async_mod.py")

        assert any("async def" in s and "fetch_data" in s for s in sigs)


# --------------------------------------------------------------------------- #
#                        DependencyExplorer Tests                              #
# --------------------------------------------------------------------------- #


class TestDependencyExplorer:
    """Tests for DependencyExplorer."""

    def test_dependency_traversal(self) -> None:
        """A->B->C, querying B shows A (incoming) and C (outgoing)."""
        graph, ids = _build_abc_graph()
        explorer = DependencyExplorer(graph)

        dep_map = explorer.explore(ids[1], hops=2)

        assert dep_map.center_node_id == ids[1]
        assert dep_map.hops == 2
        # A should be in incoming
        incoming_ids = [nid for nid, _ in dep_map.incoming]
        assert ids[0] in incoming_ids
        # C should be in outgoing
        outgoing_ids = [nid for nid, _ in dep_map.outgoing]
        assert ids[2] in outgoing_ids

    def test_dependency_single_hop(self) -> None:
        """With 1 hop, only direct neighbours are shown."""
        graph, ids = _build_abc_graph()
        explorer = DependencyExplorer(graph)

        dep_map = explorer.explore(ids[1], hops=1)

        incoming_ids = [nid for nid, _ in dep_map.incoming]
        outgoing_ids = [nid for nid, _ in dep_map.outgoing]
        assert ids[0] in incoming_ids
        assert ids[2] in outgoing_ids

    def test_dependency_zero_hops(self) -> None:
        """With 0 hops, no neighbours are shown."""
        graph, ids = _build_abc_graph()
        explorer = DependencyExplorer(graph)

        dep_map = explorer.explore(ids[1], hops=0)

        assert dep_map.incoming == []
        assert dep_map.outgoing == []

    def test_dependency_node_not_found(self) -> None:
        """Raises ValueError for missing nodes."""
        graph = RPGGraph()
        explorer = DependencyExplorer(graph)

        with pytest.raises(ValueError, match="not found"):
            explorer.explore(uuid4(), hops=2)

    def test_dependency_failed_node_highlight(self) -> None:
        """Failed nodes have [FAILED] in their edge labels."""
        ids = [uuid4() for _ in range(3)]
        graph = RPGGraph()
        graph.add_node(_make_node(name="A", node_id=ids[0]))
        graph.add_node(
            _make_node(name="B", node_id=ids[1], test_status=TestStatus.FAILED)
        )
        graph.add_node(_make_node(name="C", node_id=ids[2]))
        graph.add_edge(_make_edge(ids[0], ids[1], EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(ids[1], ids[2], EdgeType.DATA_FLOW))

        explorer = DependencyExplorer(graph)
        dep_map = explorer.explore(ids[0], hops=2)

        # B is outgoing from A and is FAILED
        outgoing_labels = {nid: label for nid, label in dep_map.outgoing}
        assert "FAILED" in outgoing_labels.get(ids[1], "")

    def test_ascii_tree_rendering(self) -> None:
        """as_ascii_tree produces readable output."""
        graph, ids = _build_abc_graph()
        explorer = DependencyExplorer(graph)
        dep_map = explorer.explore(ids[1], hops=1)

        tree = explorer.as_ascii_tree(dep_map)

        assert "node_B" in tree
        assert "Incoming:" in tree
        assert "Outgoing:" in tree
        assert "node_A" in tree
        assert "node_C" in tree


# --------------------------------------------------------------------------- #
#                       LocalizationTracker Tests                              #
# --------------------------------------------------------------------------- #


class TestLocalizationTracker:
    """Tests for LocalizationTracker."""

    def test_log_query(self) -> None:
        """Queries are recorded in the history."""
        tracker = LocalizationTracker(max_attempts=20)
        tracker.log_query("test query", "serena", 3)

        assert tracker.attempt_count == 1
        assert tracker.history[0]["query"] == "test query"
        assert tracker.history[0]["tool"] == "serena"
        assert tracker.history[0]["results_count"] == 3

    def test_localization_limit(self) -> None:
        """21st attempt raises LocalizationExhaustedError."""
        tracker = LocalizationTracker(max_attempts=20)

        for i in range(20):
            tracker.log_query(f"query_{i}", "serena", 1)

        with pytest.raises(LocalizationExhaustedError):
            tracker.log_query("query_20", "serena", 1)

    def test_localization_limit_exact(self) -> None:
        """20th attempt succeeds, 21st fails."""
        tracker = LocalizationTracker(max_attempts=20)

        for i in range(20):
            tracker.log_query(f"query_{i}", "serena", 0)

        assert tracker.attempt_count == 20

        with pytest.raises(LocalizationExhaustedError) as exc_info:
            tracker.log_query("query_overflow", "serena", 0)
        assert exc_info.value.limit == 20

    def test_has_queried(self) -> None:
        """Detects already-run queries."""
        tracker = LocalizationTracker()
        tracker.log_query("find_user", "serena", 1)

        assert tracker.has_queried("find_user", "serena") is True
        assert tracker.has_queried("find_user", "rpg_fuzzy") is False
        assert tracker.has_queried("other_query", "serena") is False

    def test_search_history_no_repeats(self) -> None:
        """get_previous_queries returns unique queries."""
        tracker = LocalizationTracker()
        tracker.log_query("query_a", "serena", 1)
        tracker.log_query("query_b", "rpg_fuzzy", 2)
        tracker.log_query("query_a", "rpg_fuzzy", 0)  # same query, diff tool

        queries = tracker.get_previous_queries()
        assert queries == ["query_a", "query_b"]

    def test_reset(self) -> None:
        """Reset clears all history."""
        tracker = LocalizationTracker()
        tracker.log_query("test", "serena", 1)
        tracker.reset()

        assert tracker.attempt_count == 0
        assert tracker.history == []

    def test_custom_max_attempts(self) -> None:
        """Custom max_attempts is respected."""
        tracker = LocalizationTracker(max_attempts=5)

        for i in range(5):
            tracker.log_query(f"q{i}", "serena", 0)

        with pytest.raises(LocalizationExhaustedError):
            tracker.log_query("overflow", "serena", 0)

    def test_history_contains_timestamps(self) -> None:
        """Each history entry has a timestamp."""
        tracker = LocalizationTracker()
        tracker.log_query("test", "serena", 1)

        assert "timestamp" in tracker.history[0]
        assert tracker.history[0]["timestamp"]  # not empty


# --------------------------------------------------------------------------- #
#                      LocalizationResult Model Tests                          #
# --------------------------------------------------------------------------- #


class TestLocalizationResultModel:
    """Tests for LocalizationResult Pydantic model."""

    def test_basic_creation(self) -> None:
        """Creates a valid LocalizationResult."""
        result = LocalizationResult(
            node_id=uuid4(),
            symbol_name="calculate_mean",
            filepath="src/stats.py",
            line=10,
            score=0.95,
            source="serena",
            context="def calculate_mean(values):",
        )
        assert result.symbol_name == "calculate_mean"
        assert result.score == 0.95

    def test_score_validation(self) -> None:
        """Score must be between 0.0 and 1.0."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            LocalizationResult(
                symbol_name="test",
                filepath="test.py",
                score=1.5,
                source="serena",
            )

    def test_optional_fields(self) -> None:
        """node_id and line are optional."""
        result = LocalizationResult(
            symbol_name="test",
            filepath="test.py",
            score=0.5,
            source="ast",
        )
        assert result.node_id is None
        assert result.line is None
        assert result.context == ""


class TestDependencyMapModel:
    """Tests for DependencyMap Pydantic model."""

    def test_basic_creation(self) -> None:
        """Creates a valid DependencyMap."""
        center = uuid4()
        dep_map = DependencyMap(
            center_node_id=center,
            incoming=[(uuid4(), "DATA_FLOW")],
            outgoing=[(uuid4(), "HIERARCHY")],
            hops=2,
        )
        assert dep_map.center_node_id == center
        assert dep_map.hops == 2
        assert len(dep_map.incoming) == 1
        assert len(dep_map.outgoing) == 1

    def test_empty_maps(self) -> None:
        """DependencyMap can have empty incoming/outgoing."""
        dep_map = DependencyMap(
            center_node_id=uuid4(),
            hops=0,
        )
        assert dep_map.incoming == []
        assert dep_map.outgoing == []
