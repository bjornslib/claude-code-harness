"""Unit tests for VectorStore – the ChromaDB-backed vector store.

All ChromaDB and embedding calls are mocked so tests run without
external dependencies or model downloads.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from cobuilder.repomap.vectordb.exceptions import (
    CollectionError,
    StoreNotInitializedError,
)
from cobuilder.repomap.vectordb.models import SearchResult, VectorStoreConfig
from cobuilder.repomap.vectordb.store import VectorStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_node(
    name: str = "login",
    level: str = "FEATURE",
    node_type: str = "FUNCTION_AUGMENTED",
    docstring: str | None = None,
) -> SimpleNamespace:
    """Build a fake RPGNode-like object for testing."""
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        level=level,
        node_type=node_type,
        docstring=docstring,
    )


def _mock_collection(count: int = 0) -> MagicMock:
    """Create a mock ChromaDB collection."""
    collection = MagicMock()
    collection.count.return_value = count
    collection.get.return_value = {"metadatas": [], "ids": []}
    collection.query.return_value = {
        "documents": [[]],
        "distances": [[]],
        "metadatas": [[]],
    }
    return collection


def _mock_client(collection: MagicMock | None = None) -> MagicMock:
    """Create a mock ChromaDB PersistentClient."""
    client = MagicMock()
    coll = collection or _mock_collection()
    client.get_or_create_collection.return_value = coll
    return client


def _mock_embedder() -> MagicMock:
    """Create a mock EmbeddingGenerator."""
    embedder = MagicMock()
    embedder.model_name = "all-MiniLM-L6-v2"
    embedder.embed.return_value = [0.1] * 384
    embedder.embed_batch.return_value = [[0.1] * 384]
    return embedder


def _initialized_store(
    tmp_path: Path,
    collection: MagicMock | None = None,
) -> VectorStore:
    """Return a VectorStore that's been initialised with mocks."""
    store = VectorStore()
    coll = collection or _mock_collection()
    store._client = _mock_client(coll)
    store._collection = coll
    store._embedder = _mock_embedder()
    store._initialized = True
    return store


# ---------------------------------------------------------------------------
# Init tests (Task 1.4.1)
# ---------------------------------------------------------------------------


class TestVectorStoreInit:
    """Tests for VectorStore construction."""

    def test_default_config(self) -> None:
        store = VectorStore()
        assert store._config.collection_name == "feature_trees"
        assert not store.is_initialized

    def test_custom_config(self) -> None:
        cfg = VectorStoreConfig(collection_name="custom")
        store = VectorStore(config=cfg)
        assert store._config.collection_name == "custom"

    @patch("cobuilder.repomap.vectordb.store._CHROMADB_AVAILABLE", False)
    def test_no_chromadb_raises(self) -> None:
        with pytest.raises(CollectionError, match="chromadb"):
            VectorStore()


class TestVectorStoreInitialize:
    """Tests for the initialize method."""

    @patch("cobuilder.repomap.vectordb.store.chromadb")
    @patch("cobuilder.repomap.vectordb.store.EmbeddingGenerator")
    def test_initialize_creates_collection(
        self, mock_emb_cls: MagicMock, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        mock_client = _mock_client()
        mock_chroma.PersistentClient.return_value = mock_client

        store = VectorStore()
        store.initialize(tmp_path)

        assert store.is_initialized
        mock_client.get_or_create_collection.assert_called_once()

    @patch("cobuilder.repomap.vectordb.store.chromadb")
    @patch("cobuilder.repomap.vectordb.store.EmbeddingGenerator")
    def test_initialize_idempotent(
        self, mock_emb_cls: MagicMock, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        """Calling initialize twice doesn't raise."""
        mock_chroma.PersistentClient.return_value = _mock_client()
        store = VectorStore()
        store.initialize(tmp_path)
        store.initialize(tmp_path)
        assert store.is_initialized

    def test_initialize_invalid_dir_raises(self, tmp_path: Path) -> None:
        store = VectorStore()
        bad = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="existing directory"):
            store.initialize(bad)

    def test_initialize_file_not_dir_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "afile.txt"
        f.write_text("hi")
        store = VectorStore()
        with pytest.raises(ValueError, match="existing directory"):
            store.initialize(f)

    @patch("cobuilder.repomap.vectordb.store.chromadb")
    @patch("cobuilder.repomap.vectordb.store.EmbeddingGenerator")
    def test_initialize_custom_embedding_model(
        self, mock_emb_cls: MagicMock, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        mock_chroma.PersistentClient.return_value = _mock_client()
        store = VectorStore()
        store.initialize(tmp_path, embedding_model="text-embedding-3-small")
        mock_emb_cls.assert_called_with(model_name="text-embedding-3-small")

    @patch("cobuilder.repomap.vectordb.store.chromadb")
    def test_initialize_chromadb_failure_raises(
        self, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        mock_chroma.PersistentClient.side_effect = RuntimeError("disk full")
        store = VectorStore()
        with pytest.raises(CollectionError, match="Failed to initialise"):
            store.initialize(tmp_path)


# ---------------------------------------------------------------------------
# Uninitialised guard tests
# ---------------------------------------------------------------------------


class TestRequireInitialized:
    """All methods should raise StoreNotInitializedError before init."""

    def test_add_node_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.add_node(_fake_node())

    def test_add_nodes_batch_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.add_nodes_batch([_fake_node()])

    def test_search_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.search("query")

    def test_search_by_node_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.search_by_node(_fake_node())

    def test_clear_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.clear()

    def test_delete_node_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.delete_node(uuid4())

    def test_get_stats_before_init(self) -> None:
        store = VectorStore()
        with pytest.raises(StoreNotInitializedError):
            store.get_stats()


# ---------------------------------------------------------------------------
# Add node tests (Task 1.4.3)
# ---------------------------------------------------------------------------


class TestAddNode:
    """Tests for add_node and add_nodes_batch."""

    def test_add_single_node(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="login")
        store.add_node(node)
        coll.upsert.assert_called_once()
        call_kwargs = coll.upsert.call_args.kwargs
        assert call_kwargs["ids"] == [str(node.id)]
        assert call_kwargs["documents"] == ["login"]

    def test_add_node_with_docstring(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="login", docstring="Handle user login")
        store.add_node(node)
        call_kwargs = coll.upsert.call_args.kwargs
        assert call_kwargs["documents"] == ["login Handle user login"]

    def test_add_node_with_custom_path(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="login")
        store.add_node(node, path="auth/login")
        call_kwargs = coll.upsert.call_args.kwargs
        assert call_kwargs["metadatas"][0]["path"] == "auth/login"

    def test_add_node_default_path_is_name(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="register")
        store.add_node(node)
        call_kwargs = coll.upsert.call_args.kwargs
        assert call_kwargs["metadatas"][0]["path"] == "register"

    def test_add_node_metadata_fields(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="login", level="FEATURE", node_type="FUNCTION_AUGMENTED")
        store.add_node(node)
        meta = coll.upsert.call_args.kwargs["metadatas"][0]
        assert meta["node_id"] == str(node.id)
        assert meta["level"] == "FEATURE"
        assert meta["node_type"] == "FUNCTION_AUGMENTED"

    def test_add_node_collection_error(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        coll.upsert.side_effect = RuntimeError("disk full")
        store = _initialized_store(tmp_path, collection=coll)
        with pytest.raises(CollectionError, match="Failed to add node"):
            store.add_node(_fake_node())

    def test_add_nodes_batch(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        store._embedder.embed_batch.return_value = [[0.1] * 384] * 3
        nodes = [_fake_node(name=f"n{i}") for i in range(3)]
        store.add_nodes_batch(nodes)
        coll.upsert.assert_called_once()
        call_kwargs = coll.upsert.call_args.kwargs
        assert len(call_kwargs["ids"]) == 3

    def test_add_nodes_batch_empty(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        store.add_nodes_batch([])
        coll.upsert.assert_not_called()

    def test_add_nodes_batch_with_paths(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        store._embedder.embed_batch.return_value = [[0.1] * 384] * 2
        nodes = [_fake_node(name="a"), _fake_node(name="b")]
        store.add_nodes_batch(nodes, paths=["path/a", "path/b"])
        metas = coll.upsert.call_args.kwargs["metadatas"]
        assert metas[0]["path"] == "path/a"
        assert metas[1]["path"] == "path/b"

    def test_add_nodes_batch_mismatched_paths_raises(self, tmp_path: Path) -> None:
        store = _initialized_store(tmp_path)
        nodes = [_fake_node(), _fake_node()]
        with pytest.raises(ValueError, match="must match|same length|length"):
            store.add_nodes_batch(nodes, paths=["only_one"])

    def test_add_nodes_batch_collection_error(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        coll.upsert.side_effect = RuntimeError("batch failed")
        store = _initialized_store(tmp_path, collection=coll)
        store._embedder.embed_batch.return_value = [[0.1] * 384]
        with pytest.raises(CollectionError, match="Failed to add batch"):
            store.add_nodes_batch([_fake_node()])

    def test_add_nodes_batch_respects_batch_size(self, tmp_path: Path) -> None:
        """Large batch is split according to config.batch_size."""
        coll = _mock_collection()
        cfg = VectorStoreConfig(batch_size=2)
        store = VectorStore(config=cfg)
        store._client = _mock_client(coll)
        store._collection = coll
        store._embedder = _mock_embedder()
        store._embedder.embed_batch.return_value = [[0.1] * 384] * 2
        store._initialized = True

        nodes = [_fake_node(name=f"n{i}") for i in range(5)]
        store.add_nodes_batch(nodes)
        # 5 nodes / batch_size 2 = 3 batches
        assert coll.upsert.call_count == 3


# ---------------------------------------------------------------------------
# Search tests (Task 1.4.4)
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for search and search_by_node."""

    def test_search_returns_results(self, tmp_path: Path) -> None:
        coll = _mock_collection(count=10)
        coll.query.return_value = {
            "documents": [["auth login", "user profile"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [[{"level": "FEATURE"}, {"level": "COMPONENT"}]],
        }
        store = _initialized_store(tmp_path, collection=coll)
        results = store.search("authentication", top_k=5)
        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].document == "auth login"
        assert results[0].score == pytest.approx(0.9)  # 1.0 - 0.1
        assert results[0].metadata["level"] == "FEATURE"

    def test_search_empty_collection(self, tmp_path: Path) -> None:
        store = _initialized_store(tmp_path)
        results = store.search("anything")
        assert results == []

    def test_search_with_filters(self, tmp_path: Path) -> None:
        coll = _mock_collection(count=5)
        coll.query.return_value = {
            "documents": [["result"]],
            "distances": [[0.2]],
            "metadatas": [[{"level": "FEATURE"}]],
        }
        store = _initialized_store(tmp_path, collection=coll)
        store.search("query", filters={"level": "FEATURE"})
        call_kwargs = coll.query.call_args.kwargs
        # The current implementation uses _build_where_clause which transforms
        # {"level": "FEATURE"} into {"level": {"$eq": "FEATURE"}}
        assert "where" in call_kwargs
        where = call_kwargs["where"]
        assert where == {"level": {"$eq": "FEATURE"}}

    def test_search_respects_top_k(self, tmp_path: Path) -> None:
        coll = _mock_collection(count=10)
        store = _initialized_store(tmp_path, collection=coll)
        store.search("test", top_k=3)
        call_kwargs = coll.query.call_args.kwargs
        assert call_kwargs["n_results"] == 3

    def test_search_caps_top_k_to_collection_count(self, tmp_path: Path) -> None:
        """When top_k > collection count, n_results is capped."""
        coll = _mock_collection(count=2)
        store = _initialized_store(tmp_path, collection=coll)
        store.search("test", top_k=100)
        call_kwargs = coll.query.call_args.kwargs
        assert call_kwargs["n_results"] == 2

    def test_search_collection_error(self, tmp_path: Path) -> None:
        coll = _mock_collection(count=5)
        coll.query.side_effect = RuntimeError("query failed")
        store = _initialized_store(tmp_path, collection=coll)
        with pytest.raises(CollectionError, match="Search failed"):
            store.search("test")

    def test_search_by_node_uses_name(self, tmp_path: Path) -> None:
        coll = _mock_collection(count=5)
        coll.query.return_value = {
            "documents": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="login_handler")
        store.search_by_node(node, top_k=3)
        store._embedder.embed.assert_called_with("login_handler")

    def test_search_by_node_uses_docstring(self, tmp_path: Path) -> None:
        coll = _mock_collection(count=5)
        coll.query.return_value = {"documents": [[]], "distances": [[]], "metadatas": [[]]}
        store = _initialized_store(tmp_path, collection=coll)
        node = _fake_node(name="login", docstring="Handle user login")
        store.search_by_node(node)
        store._embedder.embed.assert_called_with("login Handle user login")


# ---------------------------------------------------------------------------
# Collection management tests (Task 1.4.5)
# ---------------------------------------------------------------------------


class TestCollectionManagement:
    """Tests for clear, delete_node, get_stats."""

    def test_clear_deletes_all_ids(self, tmp_path: Path) -> None:
        """clear() fetches all IDs and deletes them."""
        coll = _mock_collection()
        coll.get.return_value = {"ids": ["id1", "id2", "id3"]}
        store = _initialized_store(tmp_path, collection=coll)
        store.clear()
        coll.get.assert_called_once()
        coll.delete.assert_called_once_with(ids=["id1", "id2", "id3"])

    def test_clear_empty_collection_no_delete(self, tmp_path: Path) -> None:
        """clear() on empty collection doesn't call delete."""
        coll = _mock_collection()
        coll.get.return_value = {"ids": []}
        store = _initialized_store(tmp_path, collection=coll)
        store.clear()
        coll.get.assert_called_once()
        coll.delete.assert_not_called()

    def test_clear_error_raises(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        coll.get.side_effect = RuntimeError("fail")
        store = _initialized_store(tmp_path, collection=coll)
        with pytest.raises(CollectionError, match="Failed to clear"):
            store.clear()

    def test_delete_node(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        store = _initialized_store(tmp_path, collection=coll)
        nid = uuid4()
        store.delete_node(nid)
        coll.delete.assert_called_once_with(ids=[str(nid)])

    def test_delete_node_error_raises(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        coll.delete.side_effect = RuntimeError("fail")
        store = _initialized_store(tmp_path, collection=coll)
        with pytest.raises(CollectionError, match="Failed to delete"):
            store.delete_node(uuid4())

    def test_get_stats_empty(self, tmp_path: Path) -> None:
        store = _initialized_store(tmp_path)
        stats = store.get_stats()
        assert stats == {"count": 0}

    def test_get_stats_with_data(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        coll.count.return_value = 3
        coll.get.return_value = {
            "metadatas": [
                {"level": "MODULE", "node_type": "FUNCTIONALITY"},
                {"level": "FEATURE", "node_type": "FUNCTION_AUGMENTED"},
                {"level": "FEATURE", "node_type": "FUNCTION_AUGMENTED"},
            ]
        }
        store = _initialized_store(tmp_path, collection=coll)
        stats = store.get_stats()
        assert stats["count"] == 3
        assert stats["by_level"]["MODULE"] == 1
        assert stats["by_level"]["FEATURE"] == 2
        assert stats["by_type"]["FUNCTIONALITY"] == 1
        assert stats["by_type"]["FUNCTION_AUGMENTED"] == 2

    def test_get_stats_error_raises(self, tmp_path: Path) -> None:
        coll = _mock_collection()
        coll.count.side_effect = RuntimeError("fail")
        store = _initialized_store(tmp_path, collection=coll)
        with pytest.raises(CollectionError, match="Failed to get"):
            store.get_stats()


# ---------------------------------------------------------------------------
# Parse query results
# ---------------------------------------------------------------------------


class TestParseQueryResults:
    """Tests for _parse_query_results static method."""

    def test_empty_results(self) -> None:
        assert VectorStore._parse_query_results({}) == []

    def test_empty_documents(self) -> None:
        assert VectorStore._parse_query_results({"documents": None}) == []

    def test_parse_single_result(self) -> None:
        results = VectorStore._parse_query_results({
            "documents": [["hello"]],
            "distances": [[0.2]],
            "metadatas": [[{"key": "val"}]],
        })
        assert len(results) == 1
        assert results[0].document == "hello"
        assert results[0].score == pytest.approx(0.8)
        assert results[0].metadata == {"key": "val"}

    def test_parse_multiple_results(self) -> None:
        results = VectorStore._parse_query_results({
            "documents": [["a", "b", "c"]],
            "distances": [[0.1, 0.3, 0.5]],
            "metadatas": [[{}, {}, {}]],
        })
        assert len(results) == 3
        assert results[0].score > results[1].score > results[2].score

    def test_missing_distances(self) -> None:
        results = VectorStore._parse_query_results({
            "documents": [["a"]],
            "metadatas": [[{}]],
        })
        assert len(results) == 1
        assert results[0].score == pytest.approx(1.0)  # 1 - 0
