"""Unit tests for the VectorDB module.

Tests cover:
- VectorStoreConfig model defaults and validation
- SearchResult model
- EmbeddingGenerator (mocked sentence-transformers)
- VectorStore (store.py, uses ChromaDB default embeddings)
  - initialize()
  - add_node() / add_nodes_batch()
  - search() / search_by_node()
  - clear() / delete_node() / get_stats() / count()
- Exception classes
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from cobuilder.repomap.models.enums import (
    NodeLevel,
    NodeType,
    TestStatus,
)
from cobuilder.repomap.models.node import RPGNode

from cobuilder.repomap.vectordb.exceptions import (
    CollectionError,
    EmbeddingError,
    StoreNotInitializedError,
    VectorStoreError,
)
from cobuilder.repomap.vectordb.models import SearchResult, VectorStoreConfig
from cobuilder.repomap.vectordb.embeddings import EmbeddingGenerator
from cobuilder.repomap.vectordb import VectorStore


# --------------------------------------------------------------------------- #
#                               Helpers                                        #
# --------------------------------------------------------------------------- #


def _make_node(
    name: str = "test_node",
    level: NodeLevel = NodeLevel.COMPONENT,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    docstring: str | None = None,
    **kwargs,
) -> RPGNode:
    """Create an RPGNode with sensible defaults."""
    return RPGNode(
        name=name,
        level=level,
        node_type=node_type,
        docstring=docstring,
        **kwargs,
    )


def _mock_embedder() -> MagicMock:
    """Create a mock EmbeddingGenerator that returns fake embeddings."""
    mock = MagicMock(spec=EmbeddingGenerator)
    mock.model_name = "mock-model"
    mock.embed.return_value = [0.1] * 384
    mock.embed_batch.return_value = [[0.1] * 384]
    return mock


# =========================================================================== #
#                        VectorStoreConfig Tests                               #
# =========================================================================== #


class TestVectorStoreConfig:
    """Tests for VectorStoreConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = VectorStoreConfig()
        assert config.persist_dir == ".zerorepo/chroma"
        assert config.collection_name == "feature_trees"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.batch_size == 100

    def test_custom_values(self) -> None:
        config = VectorStoreConfig(
            persist_dir="/tmp/chroma",
            collection_name="my_collection",
            embedding_model="custom-model",
            batch_size=50,
        )
        assert config.persist_dir == "/tmp/chroma"
        assert config.collection_name == "my_collection"
        assert config.embedding_model == "custom-model"
        assert config.batch_size == 50

    def test_batch_size_minimum(self) -> None:
        with pytest.raises(Exception):  # Pydantic ValidationError
            VectorStoreConfig(batch_size=0)

    def test_batch_size_one_is_valid(self) -> None:
        config = VectorStoreConfig(batch_size=1)
        assert config.batch_size == 1


# =========================================================================== #
#                          SearchResult Tests                                  #
# =========================================================================== #


class TestSearchResult:
    """Tests for SearchResult Pydantic model."""

    def test_basic_creation(self) -> None:
        result = SearchResult(
            document="some text", score=0.95, metadata={"key": "val"}
        )
        assert result.document == "some text"
        assert result.score == 0.95
        assert result.metadata == {"key": "val"}

    def test_default_metadata(self) -> None:
        result = SearchResult(document="text", score=0.5)
        assert result.metadata == {}

    def test_requires_document_and_score(self) -> None:
        with pytest.raises(Exception):
            SearchResult(score=0.5)  # type: ignore[call-arg]
        with pytest.raises(Exception):
            SearchResult(document="text")  # type: ignore[call-arg]


# =========================================================================== #
#                       EmbeddingGenerator Tests                               #
# =========================================================================== #


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator input validation."""

    def test_model_name_property(self) -> None:
        gen = EmbeddingGenerator(model_name="test-model")
        assert gen.model_name == "test-model"

    def test_default_model_name(self) -> None:
        gen = EmbeddingGenerator()
        assert gen.model_name == "all-MiniLM-L6-v2"

    def test_embed_empty_text_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty"):
            gen.embed("")

    def test_embed_whitespace_only_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty"):
            gen.embed("   ")

    def test_embed_batch_empty_list(self) -> None:
        gen = EmbeddingGenerator()
        assert gen.embed_batch([]) == []

    def test_embed_batch_with_empty_text_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty"):
            gen.embed_batch(["valid", ""])


# =========================================================================== #
#                       Exception Hierarchy Tests                              #
# =========================================================================== #


class TestExceptions:
    """Tests for vectordb exception hierarchy."""

    def test_base_exception(self) -> None:
        err = VectorStoreError("base error")
        assert str(err) == "base error"
        assert isinstance(err, Exception)

    def test_store_not_initialized_inherits(self) -> None:
        err = StoreNotInitializedError("not init")
        assert isinstance(err, VectorStoreError)
        assert isinstance(err, Exception)

    def test_embedding_error_inherits(self) -> None:
        err = EmbeddingError("embed fail")
        assert isinstance(err, VectorStoreError)

    def test_collection_error_inherits(self) -> None:
        err = CollectionError("col fail")
        assert isinstance(err, VectorStoreError)


# =========================================================================== #
#             VectorStore (store.py) Tests with mocked embedder                #
# =========================================================================== #


class TestVectorStoreInitialization:
    """Tests for VectorStore initialization."""

    def test_not_initialized_by_default(self) -> None:
        store = VectorStore()
        assert not store.is_initialized

    def test_initialize_requires_valid_directory(self, tmp_path: Path) -> None:
        store = VectorStore()
        fake_dir = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="directory"):
            store.initialize(fake_dir)

    def test_initialize_success(self, tmp_path: Path) -> None:
        store = VectorStore()
        store.initialize(tmp_path)
        assert store.is_initialized

    def test_initialize_creates_persist_dir(self, tmp_path: Path) -> None:
        config = VectorStoreConfig(persist_dir=".test_chroma")
        store = VectorStore(config=config)
        store.initialize(tmp_path)
        assert (tmp_path / ".test_chroma").exists()

    def test_require_initialized_raises(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store._require_initialized()

    def test_initialize_idempotent(self, tmp_path: Path) -> None:
        store = VectorStore()
        store.initialize(tmp_path)
        store.initialize(tmp_path)
        assert store.is_initialized


class TestVectorStoreNodeOperations:
    """Tests for add_node, add_nodes_batch, delete_node with real ChromaDB."""

    @pytest.fixture
    def store(self, tmp_path: Path):
        s = VectorStore()
        s.initialize(tmp_path)
        s._embedder = _mock_embedder()
        return s

    def test_add_node_before_init_raises(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.add_node(_make_node())

    def test_add_node_success(self, store) -> None:
        node = _make_node(name="auth_login", docstring="Handle login")
        store.add_node(node)
        count = store._collection.count()
        assert count == 1

    def test_add_node_upsert(self, store) -> None:
        node = _make_node(name="auth_login")
        store.add_node(node)
        store.add_node(node)
        assert store._collection.count() == 1

    def test_add_nodes_batch_empty(self, store) -> None:
        store.add_nodes_batch([])
        assert store._collection.count() == 0

    def test_add_nodes_batch_success(self, store) -> None:
        nodes = [_make_node(name=f"node_{i}") for i in range(3)]
        embedder = _mock_embedder()
        embedder.embed_batch.return_value = [[0.1] * 384] * 3
        store._embedder = embedder
        store.add_nodes_batch(nodes)
        assert store._collection.count() == 3

    def test_add_nodes_batch_with_paths(self, store) -> None:
        nodes = [_make_node(name=f"n{i}") for i in range(3)]
        embedder = _mock_embedder()
        embedder.embed_batch.return_value = [[0.1] * 384] * 3
        store._embedder = embedder
        store.add_nodes_batch(nodes, paths=["a", "b", "c"])
        assert store._collection.count() == 3

    def test_add_nodes_batch_paths_mismatch(self, store) -> None:
        nodes = [_make_node(name=f"n{i}") for i in range(3)]
        with pytest.raises(ValueError, match="length"):
            store.add_nodes_batch(nodes, paths=["one"])

    def test_delete_node(self, store) -> None:
        node = _make_node(name="to_delete")
        store.add_node(node)
        assert store._collection.count() == 1
        store.delete_node(node.id)
        assert store._collection.count() == 0

    def test_delete_nonexistent(self, store) -> None:
        store.delete_node(uuid4())  # Should not raise

    def test_delete_before_init_raises(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.delete_node(uuid4())


class TestVectorStoreSearch:
    """Tests for search and search_by_node with real ChromaDB."""

    @pytest.fixture
    def store_with_data(self, tmp_path: Path):
        s = VectorStore()
        s.initialize(tmp_path)
        embedder = _mock_embedder()
        # Return different embeddings for each call
        embedder.embed.side_effect = lambda text: [float(hash(text) % 100) / 100.0] * 384
        embedder.embed_batch.side_effect = lambda texts: [
            [float(hash(t) % 100) / 100.0] * 384 for t in texts
        ]
        s._embedder = embedder

        nodes = [
            _make_node(name="user_auth", docstring="Handle login", level=NodeLevel.FEATURE),
            _make_node(name="password", docstring="Hash passwords", level=NodeLevel.FEATURE),
            _make_node(name="database", docstring="Connection pool", level=NodeLevel.MODULE),
        ]
        for node in nodes:
            s.add_node(node)
        return s

    def test_search_before_init_raises(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.search("query")

    def test_search_returns_results(self, store_with_data) -> None:
        results = store_with_data.search("authentication", top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_result_has_score(self, store_with_data) -> None:
        results = store_with_data.search("login", top_k=3)
        for r in results:
            assert isinstance(r.score, float)

    def test_search_result_has_metadata(self, store_with_data) -> None:
        results = store_with_data.search("auth", top_k=1)
        assert len(results) >= 1
        assert "node_id" in results[0].metadata

    def test_search_empty_collection(self, tmp_path: Path) -> None:
        store = VectorStore()
        store.initialize(tmp_path)
        store._embedder = _mock_embedder()
        results = store.search("anything")
        assert results == []

    def test_search_by_node(self, store_with_data) -> None:
        query_node = _make_node(name="auth", docstring="Check credentials")
        results = store_with_data.search_by_node(query_node, top_k=2)
        assert len(results) <= 2

    def test_search_with_filter(self, store_with_data) -> None:
        results = store_with_data.search(
            "something", top_k=10,
            filters={"level": NodeLevel.FEATURE},
        )
        for r in results:
            assert r.metadata.get("level") == "FEATURE"


class TestVectorStoreCollectionManagement:
    """Tests for clear, get_stats, count."""

    @pytest.fixture
    def store(self, tmp_path: Path):
        s = VectorStore()
        s.initialize(tmp_path)
        s._embedder = _mock_embedder()
        return s

    def test_clear_empty(self, store) -> None:
        store.clear()

    def test_clear_removes_all(self, store) -> None:
        store.add_node(_make_node(name="n1"))
        store.add_node(_make_node(name="n2"))
        assert store._collection.count() == 2
        store.clear()
        assert store._collection.count() == 0

    def test_clear_before_init_raises(self) -> None:
        with pytest.raises(StoreNotInitializedError):
            VectorStore().clear()

    def test_get_stats_empty(self, store) -> None:
        stats = store.get_stats()
        assert stats["count"] == 0

    def test_get_stats_with_data(self, store) -> None:
        nodes = [
            _make_node(name="m1", level=NodeLevel.MODULE),
            _make_node(name="c1", level=NodeLevel.COMPONENT),
        ]
        embedder = _mock_embedder()
        embedder.embed_batch.return_value = [[0.1] * 384] * 2
        store._embedder = embedder
        store.add_nodes_batch(nodes)
        stats = store.get_stats()
        assert stats["count"] == 2

    def test_get_stats_before_init_raises(self) -> None:
        with pytest.raises(StoreNotInitializedError):
            VectorStore().get_stats()


# =========================================================================== #
#            VectorStore (vectorstore.py) Static Method Tests                  #
# =========================================================================== #


class TestVectorStoreNodeMetadata:
    """Tests for _node_text and _node_metadata static methods."""

    def test_node_text_name_only(self) -> None:
        node = _make_node(name="simple_node")
        text = VectorStore._node_text(node)
        assert "simple_node" in text

    def test_node_text_with_docstring(self) -> None:
        node = _make_node(name="func", docstring="Does stuff")
        text = VectorStore._node_text(node)
        assert "func" in text
        assert "Does stuff" in text

    def test_node_metadata_required_fields(self) -> None:
        node = _make_node(
            name="test", level=NodeLevel.MODULE,
            node_type=NodeType.FOLDER_AUGMENTED,
        )
        meta = VectorStore._node_metadata(node)
        assert meta["node_id"] == str(node.id)
        assert meta["level"] == "MODULE"
        assert meta["node_type"] == "FOLDER_AUGMENTED"
        assert "path" in meta

    def test_node_metadata_custom_path(self) -> None:
        node = _make_node(name="test")
        meta = VectorStore._node_metadata(node, path="custom/path")
        assert meta["path"] == "custom/path"

    def test_node_metadata_default_path(self) -> None:
        node = _make_node(name="test")
        meta = VectorStore._node_metadata(node)
        assert meta["path"] == "test"


class TestVectorStoreParseResults:
    """Tests for _parse_query_results static method."""

    def test_parse_empty_results(self) -> None:
        assert VectorStore._parse_query_results({}) == []
        assert VectorStore._parse_query_results({"documents": None}) == []

    def test_parse_valid_results(self) -> None:
        raw = {
            "documents": [["doc1", "doc2"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [[{"key": "a"}, {"key": "b"}]],
        }
        results = VectorStore._parse_query_results(raw)
        assert len(results) == 2
        assert results[0].document == "doc1"
        assert results[0].score == pytest.approx(0.9, abs=0.01)
        assert results[1].score == pytest.approx(0.7, abs=0.01)

    def test_parse_no_distances(self) -> None:
        raw = {"documents": [["doc1"]], "metadatas": [[{"k": "v"}]]}
        results = VectorStore._parse_query_results(raw)
        assert len(results) == 1
        assert results[0].score == pytest.approx(1.0, abs=0.01)

    def test_parse_no_metadatas(self) -> None:
        raw = {"documents": [["doc1"]], "distances": [[0.2]]}
        results = VectorStore._parse_query_results(raw)
        assert results[0].metadata == {}


class TestVectorStoreBuildWhereClause:
    """Tests for _build_where_clause static method."""

    def test_empty_filters(self) -> None:
        assert VectorStore._build_where_clause({}) is None

    def test_level_filter_enum(self) -> None:
        result = VectorStore._build_where_clause({"level": NodeLevel.MODULE})
        assert result == {"level": {"$eq": "MODULE"}}

    def test_level_filter_string(self) -> None:
        result = VectorStore._build_where_clause({"level": "MODULE"})
        assert result == {"level": {"$eq": "MODULE"}}

    def test_node_type_filter(self) -> None:
        result = VectorStore._build_where_clause(
            {"node_type": NodeType.FUNCTIONALITY}
        )
        assert result == {"node_type": {"$eq": "FUNCTIONALITY"}}

    def test_path_filter(self) -> None:
        result = VectorStore._build_where_clause({"path": "auth/"})
        assert result == {"path": {"$contains": "auth/"}}

    def test_combined_filters(self) -> None:
        result = VectorStore._build_where_clause(
            {"level": "MODULE", "node_type": "FUNCTIONALITY"}
        )
        assert "$and" in result
        assert len(result["$and"]) == 2
