"""Unit tests for the OntologyService facade (Task 2.1.6).

Covers:
- OntologyServiceConfig defaults and customization
- BuildResult and SearchResult models
- OntologyService initialization (constructor, create factory)
- build() with mocked OntologyBuilder
- search() with and without filters
- stats() passthrough
- extend() from nodes, CSV path, CSV string
- export_csv() from builder and store fallback
- get_node() and get_children() passthrough
- count() method
- Error handling and custom exceptions
- Package imports
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from zerorepo.ontology.chromadb_store import OntologyChromaStore, OntologyStoreConfig
from zerorepo.ontology.embeddings import EmbeddingResult, FeatureEmbedder
from zerorepo.ontology.extension import (
    ConflictResolution,
    ExtensionResult,
    OntologyExtensionAPI,
)
from zerorepo.ontology.models import FeatureNode, FeaturePath, OntologyStats
from zerorepo.ontology.service import (
    BuildError,
    BuildResult,
    OntologyService,
    OntologyServiceConfig,
    OntologyServiceError,
    SearchError,
    SearchResult,
    ServiceNotInitializedError,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _mock_store(initialized: bool = True) -> MagicMock:
    """Create a mock OntologyChromaStore."""
    store = MagicMock(spec=OntologyChromaStore)
    store.is_initialized = initialized
    store._nodes = {}
    store.get_node.side_effect = KeyError("not found")
    store.add_node.return_value = None
    store.add_nodes_batch.return_value = 0
    store.count.return_value = 0
    store.search.return_value = []
    store.search_with_filters.return_value = []
    store.get_statistics.return_value = OntologyStats(
        total_nodes=0, total_levels=0, avg_children=0.0, max_depth=0
    )
    return store


def _mock_embedder() -> MagicMock:
    """Create a mock FeatureEmbedder."""
    embedder = MagicMock(spec=FeatureEmbedder)
    embedder.embed_nodes.return_value = EmbeddingResult(
        total_nodes=0,
        embedded_count=0,
        failed_count=0,
        skipped_count=0,
        elapsed_seconds=0.1,
        model_name="mock-model",
    )
    return embedder


def _mock_extension_api() -> MagicMock:
    """Create a mock OntologyExtensionAPI."""
    api = MagicMock(spec=OntologyExtensionAPI)
    api.extend.return_value = ExtensionResult(
        added=0, updated=0, skipped=0, errors=0, total_processed=0
    )
    api.extend_from_csv.return_value = ExtensionResult(
        added=0, updated=0, skipped=0, errors=0, total_processed=0
    )
    api.extend_from_csv_string.return_value = ExtensionResult(
        added=0, updated=0, skipped=0, errors=0, total_processed=0
    )
    return api


def _make_node(
    node_id: str = "test",
    name: str = "Test",
    level: int = 0,
    parent_id: str | None = None,
) -> FeatureNode:
    """Create a sample FeatureNode."""
    return FeatureNode(id=node_id, name=name, level=level, parent_id=parent_id)


def _make_path(node_id: str = "test", score: float = 0.9) -> FeaturePath:
    """Create a sample FeaturePath."""
    return FeaturePath(
        nodes=[_make_node(node_id=node_id)],
        score=score,
    )


# ---------------------------------------------------------------------------
# OntologyServiceConfig tests
# ---------------------------------------------------------------------------


class TestOntologyServiceConfig:
    """Tests for OntologyServiceConfig."""

    def test_default_config(self) -> None:
        config = OntologyServiceConfig()
        assert isinstance(config.store_config, OntologyStoreConfig)
        assert config.include_github is True
        assert config.include_stackoverflow is True
        assert config.include_libraries is True
        assert config.include_expander is True
        assert config.auto_embed_on_build is True
        assert config.auto_store_on_build is True
        assert config.expander_target_count == 50000

    def test_custom_config(self) -> None:
        config = OntologyServiceConfig(
            include_github=False,
            include_expander=False,
            expander_target_count=1000,
        )
        assert config.include_github is False
        assert config.include_expander is False
        assert config.expander_target_count == 1000


# ---------------------------------------------------------------------------
# BuildResult tests
# ---------------------------------------------------------------------------


class TestBuildResult:
    """Tests for BuildResult model."""

    def test_basic_result(self) -> None:
        result = BuildResult(
            total_nodes=100,
            stored_count=95,
            max_depth=5,
        )
        assert result.total_nodes == 100
        assert result.stored_count == 95
        assert result.max_depth == 5
        assert result.embedding_result is None

    def test_with_embedding_result(self) -> None:
        emb = EmbeddingResult(
            total_nodes=100,
            embedded_count=100,
            failed_count=0,
            skipped_count=0,
            elapsed_seconds=5.0,
            model_name="test",
        )
        result = BuildResult(
            total_nodes=100, stored_count=100, embedding_result=emb
        )
        assert result.embedding_result is not None
        assert result.embedding_result.embedded_count == 100

    def test_repr(self) -> None:
        result = BuildResult(
            total_nodes=50, stored_count=50, max_depth=3
        )
        r = repr(result)
        assert "total_nodes=50" in r
        assert "stored=50" in r


# ---------------------------------------------------------------------------
# SearchResult tests
# ---------------------------------------------------------------------------


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_basic_search_result(self) -> None:
        paths = [_make_path("a", 0.9), _make_path("b", 0.7)]
        result = SearchResult(
            paths=paths, query="test query", total_results=2
        )
        assert result.total_results == 2
        assert result.query == "test query"
        assert len(result.paths) == 2

    def test_top_result(self) -> None:
        paths = [_make_path("best", 0.95)]
        result = SearchResult(paths=paths, query="test", total_results=1)
        assert result.top_result is not None
        assert result.top_result.score == 0.95

    def test_top_result_empty(self) -> None:
        result = SearchResult(paths=[], query="test", total_results=0)
        assert result.top_result is None

    def test_repr(self) -> None:
        result = SearchResult(paths=[], query="auth", total_results=0)
        r = repr(result)
        assert "auth" in r


# ---------------------------------------------------------------------------
# OntologyService init tests
# ---------------------------------------------------------------------------


class TestOntologyServiceInit:
    """Tests for OntologyService initialization."""

    def test_init_with_mocks(self) -> None:
        store = _mock_store()
        embedder = _mock_embedder()
        service = OntologyService(store=store, embedder=embedder)
        assert service.store is store
        assert service.embedder is embedder
        assert service.is_built is False

    def test_init_creates_extension_api(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        assert service.extension_api is not None

    def test_init_with_explicit_extension_api(self) -> None:
        store = _mock_store()
        ext_api = _mock_extension_api()
        service = OntologyService(store=store, extension_api=ext_api)
        assert service.extension_api is ext_api

    def test_config_defaults(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        assert isinstance(service.config, OntologyServiceConfig)

    def test_custom_config(self) -> None:
        store = _mock_store()
        config = OntologyServiceConfig(include_github=False)
        service = OntologyService(store=store, config=config)
        assert service.config.include_github is False


# ---------------------------------------------------------------------------
# OntologyService.search tests
# ---------------------------------------------------------------------------


class TestOntologyServiceSearch:
    """Tests for search method."""

    def test_search_basic(self) -> None:
        store = _mock_store()
        paths = [_make_path("auth", 0.9)]
        store.search.return_value = paths

        service = OntologyService(store=store)
        result = service.search("authentication", top_k=5)

        assert result.total_results == 1
        assert result.query == "authentication"
        store.search.assert_called_once_with(query="authentication", top_k=5)

    def test_search_with_filters(self) -> None:
        store = _mock_store()
        paths = [_make_path("auth.jwt", 0.8)]
        store.search_with_filters.return_value = paths

        service = OntologyService(store=store)
        result = service.search("jwt", level=2, tags=["jwt"])

        assert result.total_results == 1
        store.search_with_filters.assert_called_once()

    def test_search_empty_query_raises(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        with pytest.raises(ValueError, match="empty"):
            service.search("")

    def test_search_invalid_top_k_raises(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        with pytest.raises(ValueError, match="positive"):
            service.search("test", top_k=0)

    def test_search_store_error_wraps(self) -> None:
        store = _mock_store()
        store.search.side_effect = RuntimeError("DB error")
        service = OntologyService(store=store)
        with pytest.raises(SearchError, match="DB error"):
            service.search("test")


# ---------------------------------------------------------------------------
# OntologyService.stats tests
# ---------------------------------------------------------------------------


class TestOntologyServiceStats:
    """Tests for stats method."""

    def test_stats_empty(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        stats = service.stats()
        assert stats.total_nodes == 0

    def test_stats_populated(self) -> None:
        store = _mock_store()
        store.get_statistics.return_value = OntologyStats(
            total_nodes=100,
            total_levels=4,
            avg_children=2.5,
            max_depth=4,
            root_count=5,
            leaf_count=60,
            nodes_with_embeddings=95,
        )
        service = OntologyService(store=store)
        stats = service.stats()
        assert stats.total_nodes == 100
        assert stats.total_levels == 4

    def test_stats_error_wraps(self) -> None:
        store = _mock_store()
        store.get_statistics.side_effect = RuntimeError("fail")
        service = OntologyService(store=store)
        with pytest.raises(OntologyServiceError, match="fail"):
            service.stats()


# ---------------------------------------------------------------------------
# OntologyService.extend tests
# ---------------------------------------------------------------------------


class TestOntologyServiceExtend:
    """Tests for extend method."""

    def test_extend_from_nodes(self) -> None:
        store = _mock_store()
        ext_api = _mock_extension_api()
        ext_api.extend.return_value = ExtensionResult(
            added=3, updated=0, skipped=0, errors=0, total_processed=3
        )
        service = OntologyService(store=store, extension_api=ext_api)

        nodes = [_make_node(f"n{i}", f"Node {i}", i) for i in range(3)]
        result = service.extend(nodes=nodes)
        assert result.added == 3
        ext_api.extend.assert_called_once()

    def test_extend_from_csv_path(self, tmp_path: Path) -> None:
        store = _mock_store()
        ext_api = _mock_extension_api()
        ext_api.extend_from_csv.return_value = ExtensionResult(
            added=5, updated=0, skipped=0, errors=0, total_processed=5
        )
        service = OntologyService(store=store, extension_api=ext_api)

        csv_file = tmp_path / "features.csv"
        csv_file.write_text("feature_id,name,level\na,A,0\n")
        result = service.extend(csv_path=csv_file)
        assert result.added == 5
        ext_api.extend_from_csv.assert_called_once()

    def test_extend_from_csv_string(self) -> None:
        store = _mock_store()
        ext_api = _mock_extension_api()
        ext_api.extend_from_csv_string.return_value = ExtensionResult(
            added=2, updated=0, skipped=0, errors=0, total_processed=2
        )
        service = OntologyService(store=store, extension_api=ext_api)

        result = service.extend(csv_content="feature_id,name,level\na,A,0\n")
        assert result.added == 2
        ext_api.extend_from_csv_string.assert_called_once()

    def test_extend_no_source_raises(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        with pytest.raises(ValueError, match="Must provide one of"):
            service.extend()

    def test_extend_multiple_sources_raises(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        with pytest.raises(ValueError, match="exactly one"):
            service.extend(nodes=[_make_node()], csv_content="foo")

    def test_extend_no_extension_api_raises(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store, extension_api=None)
        # Force extension_api to None (bypassing auto-creation)
        service._extension_api = None
        with pytest.raises(OntologyServiceError, match="not configured"):
            service.extend(nodes=[_make_node()])

    def test_extend_with_conflict_resolution(self) -> None:
        store = _mock_store()
        ext_api = _mock_extension_api()
        service = OntologyService(store=store, extension_api=ext_api)

        service.extend(nodes=[_make_node()], conflict_resolution="skip")
        ext_api.extend.assert_called_once()
        call_kwargs = ext_api.extend.call_args
        assert call_kwargs[1]["conflict_resolution"] == "skip"


# ---------------------------------------------------------------------------
# OntologyService.export_csv tests
# ---------------------------------------------------------------------------


class TestOntologyServiceExport:
    """Tests for export_csv method."""

    def test_export_from_store(self) -> None:
        store = _mock_store()
        node = _make_node("auth", "Authentication", 0)
        store._nodes = {"auth": node}
        service = OntologyService(store=store)

        csv_content = service.export_csv()
        assert "feature_id" in csv_content  # Header
        assert "auth" in csv_content
        assert "Authentication" in csv_content

    def test_export_to_file(self, tmp_path: Path) -> None:
        store = _mock_store()
        node = _make_node("test", "Test Node", 1)
        store._nodes = {"test": node}
        service = OntologyService(store=store)

        output_file = tmp_path / "export.csv"
        csv_content = service.export_csv(output_path=output_file)
        assert output_file.exists()
        assert "test" in output_file.read_text()
        assert csv_content == output_file.read_text()

    def test_export_empty_store(self) -> None:
        store = _mock_store()
        store._nodes = {}
        service = OntologyService(store=store)
        csv_content = service.export_csv()
        # Should have header only
        assert "feature_id" in csv_content

    def test_export_from_builder(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        # Simulate a previous build
        mock_builder = MagicMock()
        mock_builder.export_csv.return_value = "feature_id,name\nfoo,Foo\n"
        mock_builder.node_count = 1
        service._last_builder = mock_builder

        csv_content = service.export_csv()
        mock_builder.export_csv.assert_called_once()
        assert "foo" in csv_content


# ---------------------------------------------------------------------------
# OntologyService.get_node / get_children / count tests
# ---------------------------------------------------------------------------


class TestOntologyServicePassthrough:
    """Tests for passthrough methods."""

    def test_get_node(self) -> None:
        store = _mock_store()
        node = _make_node("auth")
        store.get_node.side_effect = None
        store.get_node.return_value = node
        service = OntologyService(store=store)

        result = service.get_node("auth")
        assert result.id == "auth"
        store.get_node.assert_called_once_with("auth")

    def test_get_node_not_found(self) -> None:
        store = _mock_store()
        service = OntologyService(store=store)
        with pytest.raises(KeyError):
            service.get_node("nonexistent")

    def test_get_children(self) -> None:
        store = _mock_store()
        children = [_make_node("child1"), _make_node("child2")]
        store.get_children.return_value = children
        service = OntologyService(store=store)

        result = service.get_children("parent")
        assert len(result) == 2
        store.get_children.assert_called_once_with("parent")

    def test_count_initialized(self) -> None:
        store = _mock_store(initialized=True)
        store.count.return_value = 42
        service = OntologyService(store=store)
        assert service.count() == 42

    def test_count_not_initialized(self) -> None:
        store = _mock_store(initialized=False)
        service = OntologyService(store=store)
        assert service.count() == 0


# ---------------------------------------------------------------------------
# Build tests (with mocked builder)
# ---------------------------------------------------------------------------


class TestOntologyServiceBuild:
    """Tests for build method."""

    @patch("zerorepo.ontology.scrapers.build_ontology.build_ontology")
    def test_build_basic(self, mock_build_fn: MagicMock) -> None:
        store = _mock_store()
        embedder = _mock_embedder()
        embedder.embed_nodes.return_value = EmbeddingResult(
            total_nodes=10,
            embedded_count=10,
            failed_count=0,
            skipped_count=0,
            elapsed_seconds=1.0,
            model_name="mock",
        )
        store.add_nodes_batch.return_value = 10

        mock_builder = MagicMock()
        mock_builder.nodes = [_make_node(f"n{i}", f"N{i}", 0) for i in range(10)]
        mock_builder.get_depth_stats.return_value = {0: 10}
        mock_builder.get_source_stats.return_value = {"github": 10}
        mock_builder.get_max_depth.return_value = 0
        mock_build_fn.return_value = mock_builder

        service = OntologyService(store=store, embedder=embedder)
        result = service.build()

        assert result.total_nodes == 10
        assert result.stored_count == 10
        assert result.embedding_result is not None
        assert service.is_built is True

    @patch("zerorepo.ontology.scrapers.build_ontology.build_ontology")
    def test_build_no_embed(self, mock_build_fn: MagicMock) -> None:
        store = _mock_store()
        config = OntologyServiceConfig(auto_embed_on_build=False)

        mock_builder = MagicMock()
        mock_builder.nodes = [_make_node()]
        mock_builder.get_depth_stats.return_value = {0: 1}
        mock_builder.get_source_stats.return_value = {}
        mock_builder.get_max_depth.return_value = 0
        store.add_nodes_batch.return_value = 1
        mock_build_fn.return_value = mock_builder

        service = OntologyService(store=store, config=config)
        result = service.build()

        assert result.embedding_result is None

    @patch("zerorepo.ontology.scrapers.build_ontology.build_ontology")
    def test_build_failure_raises(self, mock_build_fn: MagicMock) -> None:
        store = _mock_store()
        mock_build_fn.side_effect = RuntimeError("Generator failed")

        service = OntologyService(store=store)
        with pytest.raises(BuildError, match="Generator failed"):
            service.build()


# ---------------------------------------------------------------------------
# Error hierarchy tests
# ---------------------------------------------------------------------------


class TestErrors:
    """Tests for custom exception hierarchy."""

    def test_service_error_hierarchy(self) -> None:
        assert issubclass(ServiceNotInitializedError, OntologyServiceError)
        assert issubclass(BuildError, OntologyServiceError)
        assert issubclass(SearchError, OntologyServiceError)

    def test_service_error_is_exception(self) -> None:
        assert issubclass(OntologyServiceError, Exception)


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Tests for package-level imports."""

    def test_import_service(self) -> None:
        from zerorepo.ontology.service import (
            BuildResult,
            OntologyService,
            OntologyServiceConfig,
            SearchResult,
        )

        assert OntologyService is not None
        assert OntologyServiceConfig is not None
        assert BuildResult is not None
        assert SearchResult is not None

    def test_import_errors(self) -> None:
        from zerorepo.ontology.service import (
            BuildError,
            OntologyServiceError,
            SearchError,
            ServiceNotInitializedError,
        )

        assert OntologyServiceError is not None
        assert ServiceNotInitializedError is not None
        assert BuildError is not None
        assert SearchError is not None
