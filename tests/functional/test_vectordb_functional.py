"""Functional tests for the VectorDB module.

These tests validate end-to-end workflows with mocked ChromaDB and
sentence-transformers, exercising the full integration between
VectorStore, EmbeddingGenerator, and ChromaDB.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

from zerorepo.models.enums import NodeLevel, NodeType
from zerorepo.models.node import RPGNode
from zerorepo.vectordb.embeddings import EmbeddingGenerator
from zerorepo.vectordb.exceptions import (
    CollectionError,
    EmbeddingError,
    StoreNotInitializedError,
    VectorStoreError,
)
from zerorepo.vectordb.models import SearchResult, VectorStoreConfig
from zerorepo.vectordb.store import VectorStore


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


def _mock_collection() -> MagicMock:
    """Create a mock ChromaDB collection with sensible defaults."""
    collection = MagicMock()
    collection.count.return_value = 0
    collection.get.return_value = {"ids": [], "metadatas": []}
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
    embedder = MagicMock(spec=EmbeddingGenerator)
    embedder.model_name = "all-MiniLM-L6-v2"
    embedder.embed.return_value = [0.1] * 384
    embedder.embed_batch.return_value = [[0.1] * 384]
    return embedder


def _initialized_store(
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


# =========================================================================== #
#                     Full Lifecycle Functional Tests                          #
# =========================================================================== #


@pytest.mark.functional
class TestVectorStoreLifecycle:
    """Full lifecycle tests: create → add → search → delete → stats."""

    def test_full_lifecycle_single_node(self) -> None:
        """Add one node, search for it, delete it, verify stats."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        # 1. Add a node
        node = _make_node(
            name="user_auth",
            docstring="Handle user authentication and login",
            level=NodeLevel.FEATURE,
        )
        store.add_node(node, path="auth/login")

        # Verify upsert was called with correct data
        coll.upsert.assert_called_once()
        call_kwargs = coll.upsert.call_args.kwargs
        assert call_kwargs["ids"] == [str(node.id)]
        assert "user_auth" in call_kwargs["documents"][0]
        assert "Handle user authentication" in call_kwargs["documents"][0]
        meta = call_kwargs["metadatas"][0]
        assert meta["node_id"] == str(node.id)
        assert meta["level"] == "FEATURE"
        assert meta["node_type"] == "FUNCTIONALITY"
        assert meta["path"] == "auth/login"

        # 2. Search for the node (set count > 0 so search doesn't short-circuit)
        coll.count.return_value = 1
        coll.query.return_value = {
            "documents": [["user_auth Handle user authentication and login"]],
            "distances": [[0.05]],
            "metadatas": [[{
                "node_id": str(node.id),
                "level": "FEATURE",
                "node_type": "FUNCTIONALITY",
                "path": "auth/login",
            }]],
        }
        results = store.search("authentication", top_k=5)
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].score == pytest.approx(0.95, abs=0.01)
        assert results[0].metadata["level"] == "FEATURE"

        # 3. Delete the node
        store.delete_node(node.id)
        coll.delete.assert_called_once_with(ids=[str(node.id)])

    def test_full_lifecycle_batch_nodes(self) -> None:
        """Add multiple nodes in batch, search, clear, verify stats."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)
        store._embedder.embed_batch.return_value = [[0.1] * 384] * 4

        # 1. Create nodes across different levels
        nodes = [
            _make_node(
                name="auth_module",
                docstring="Authentication module",
                level=NodeLevel.MODULE,
            ),
            _make_node(
                name="login_component",
                docstring="Login UI component",
                level=NodeLevel.COMPONENT,
            ),
            _make_node(
                name="password_hash",
                docstring="Password hashing utility",
                level=NodeLevel.FEATURE,
            ),
            _make_node(
                name="jwt_token",
                docstring="JWT token generation",
                level=NodeLevel.FEATURE,
            ),
        ]
        paths = ["auth", "auth/login", "auth/utils", "auth/token"]

        # 2. Batch add
        store.add_nodes_batch(nodes, paths=paths)
        coll.upsert.assert_called_once()
        call_kwargs = coll.upsert.call_args.kwargs
        assert len(call_kwargs["ids"]) == 4
        assert len(call_kwargs["documents"]) == 4
        assert call_kwargs["metadatas"][0]["path"] == "auth"
        assert call_kwargs["metadatas"][3]["path"] == "auth/token"

        # 3. Search with results (set count > 0 so search doesn't short-circuit)
        coll.count.return_value = 4
        coll.query.return_value = {
            "documents": [["password_hash Password hashing utility"]],
            "distances": [[0.1]],
            "metadatas": [[{"level": "FEATURE", "node_type": "FUNCTIONALITY"}]],
        }
        results = store.search("hashing password", top_k=2)
        assert len(results) == 1
        assert results[0].score == pytest.approx(0.9)

        # 4. Clear collection (fetches all IDs, then deletes them)
        coll.get.return_value = {"ids": [str(n.id) for n in nodes]}
        store.clear()
        coll.delete.assert_called_once()

        # 5. Verify stats on empty collection
        coll.count.return_value = 0
        stats = store.get_stats()
        assert stats["count"] == 0


@pytest.mark.functional
class TestVectorStoreInitWorkflow:
    """Functional tests for initialization workflows."""

    @patch("zerorepo.vectordb.store.chromadb")
    @patch("zerorepo.vectordb.store.EmbeddingGenerator")
    def test_initialize_and_use(
        self, mock_emb_cls: MagicMock, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        """Full init → add → search workflow through public API."""
        mock_coll = _mock_collection()
        mock_client = _mock_client(mock_coll)
        mock_chroma.PersistentClient.return_value = mock_client

        mock_embedder = _mock_embedder()
        mock_emb_cls.return_value = mock_embedder

        # Init
        store = VectorStore()
        store.initialize(tmp_path)
        assert store.is_initialized

        # Verify persist directory was created
        mock_chroma.PersistentClient.assert_called_once()

        # Add node
        node = _make_node(name="test_feature")
        store.add_node(node)
        mock_embedder.embed.assert_called_once()
        mock_coll.upsert.assert_called_once()

    @patch("zerorepo.vectordb.store.chromadb")
    @patch("zerorepo.vectordb.store.EmbeddingGenerator")
    def test_initialize_with_custom_config(
        self, mock_emb_cls: MagicMock, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        """Custom config flows through to ChromaDB and EmbeddingGenerator."""
        mock_client = _mock_client()
        mock_chroma.PersistentClient.return_value = mock_client

        config = VectorStoreConfig(
            persist_dir=".custom/vector",
            collection_name="my_features",
            embedding_model="custom-embed-model",
            batch_size=25,
        )
        store = VectorStore(config=config)
        store.initialize(tmp_path)

        # Verify custom persist dir
        persist_call = mock_chroma.PersistentClient.call_args
        assert ".custom/vector" in persist_call.kwargs.get("path", persist_call.args[0] if persist_call.args else "")

        # Verify custom collection name
        create_call = mock_client.get_or_create_collection.call_args
        assert create_call.kwargs.get("name", create_call.args[0] if create_call.args else "") == "my_features"

        # Verify custom embedding model
        mock_emb_cls.assert_called_with(model_name="custom-embed-model")

    @patch("zerorepo.vectordb.store.chromadb")
    @patch("zerorepo.vectordb.store.EmbeddingGenerator")
    def test_initialize_override_embedding_model(
        self, mock_emb_cls: MagicMock, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        """Embedding model can be overridden at init time."""
        mock_chroma.PersistentClient.return_value = _mock_client()

        store = VectorStore()
        store.initialize(tmp_path, embedding_model="text-embedding-3-large")

        mock_emb_cls.assert_called_with(model_name="text-embedding-3-large")


@pytest.mark.functional
class TestVectorStoreSearchWorkflows:
    """Functional tests for search operations."""

    def test_search_returns_sorted_results(self) -> None:
        """Results are returned with similarity scores (highest first)."""
        coll = _mock_collection()
        coll.count.return_value = 10
        coll.query.return_value = {
            "documents": [["best_match", "good_match", "weak_match"]],
            "distances": [[0.05, 0.2, 0.7]],
            "metadatas": [[
                {"level": "FEATURE"},
                {"level": "COMPONENT"},
                {"level": "MODULE"},
            ]],
        }
        store = _initialized_store(collection=coll)

        results = store.search("test query", top_k=10)
        assert len(results) == 3
        assert results[0].score > results[1].score > results[2].score
        assert results[0].document == "best_match"
        assert results[0].score == pytest.approx(0.95)
        assert results[2].score == pytest.approx(0.3)

    def test_search_with_metadata_filters(self) -> None:
        """Filters are passed through to ChromaDB via _build_where_clause."""
        coll = _mock_collection()
        coll.count.return_value = 5
        coll.query.return_value = {
            "documents": [["filtered_result"]],
            "distances": [[0.1]],
            "metadatas": [[{"level": "FEATURE", "node_type": "FUNCTIONALITY"}]],
        }
        store = _initialized_store(collection=coll)

        results = store.search(
            "query",
            filters={"level": "FEATURE"},
        )

        # Verify filter was transformed by _build_where_clause
        query_kwargs = coll.query.call_args.kwargs
        assert query_kwargs.get("where") == {"level": {"$eq": "FEATURE"}}
        assert len(results) == 1

    def test_search_by_node_workflow(self) -> None:
        """search_by_node embeds the node's text and searches."""
        coll = _mock_collection()
        coll.count.return_value = 5
        coll.query.return_value = {
            "documents": [["similar_node"]],
            "distances": [[0.1]],
            "metadatas": [[{"node_id": "abc-123"}]],
        }
        store = _initialized_store(collection=coll)

        query_node = _make_node(
            name="authentication",
            docstring="Handle user auth",
        )
        results = store.search_by_node(query_node, top_k=5)

        # Verify the embedding was generated from node text
        store._embedder.embed.assert_called()
        embed_arg = store._embedder.embed.call_args[0][0]
        assert "authentication" in embed_arg
        assert "Handle user auth" in embed_arg

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)

    def test_search_empty_collection_returns_empty(self) -> None:
        """Searching an empty collection returns no results."""
        coll = _mock_collection()
        coll.count.return_value = 0
        coll.query.return_value = {
            "documents": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }
        store = _initialized_store(collection=coll)

        results = store.search("anything")
        assert results == []


@pytest.mark.functional
class TestVectorStoreCollectionWorkflows:
    """Functional tests for collection management operations."""

    def test_add_then_delete_workflow(self) -> None:
        """Add nodes and then delete specific ones."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        # Add two nodes
        node1 = _make_node(name="node_to_keep")
        node2 = _make_node(name="node_to_delete")

        store.add_node(node1)
        store.add_node(node2)
        assert coll.upsert.call_count == 2

        # Delete one
        store.delete_node(node2.id)
        coll.delete.assert_called_once_with(ids=[str(node2.id)])

    def test_clear_and_re_add_workflow(self) -> None:
        """Clear collection and verify fresh state for new additions."""
        coll = _mock_collection()
        client = _mock_client(coll)
        store = _initialized_store(collection=coll)
        store._client = client

        # Add nodes
        store._embedder.embed_batch.return_value = [[0.1] * 384] * 3
        nodes = [_make_node(name=f"node_{i}") for i in range(3)]
        store.add_nodes_batch(nodes)
        assert coll.upsert.call_count == 1

        # Clear (fetches all IDs, then deletes them)
        coll.get.return_value = {"ids": [str(n.id) for n in nodes]}
        store.clear()
        coll.delete.assert_called_once_with(
            ids=[str(n.id) for n in nodes]
        )

    def test_stats_reflect_collection_state(self) -> None:
        """Stats correctly report collection breakdown."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        # Configure stats for populated collection
        coll.count.return_value = 5
        coll.get.return_value = {
            "metadatas": [
                {"level": "MODULE", "node_type": "FUNCTIONALITY"},
                {"level": "MODULE", "node_type": "FOLDER_AUGMENTED"},
                {"level": "COMPONENT", "node_type": "FUNCTIONALITY"},
                {"level": "FEATURE", "node_type": "FUNCTION_AUGMENTED"},
                {"level": "FEATURE", "node_type": "FUNCTION_AUGMENTED"},
            ]
        }

        stats = store.get_stats()
        assert stats["count"] == 5
        assert stats["by_level"]["MODULE"] == 2
        assert stats["by_level"]["COMPONENT"] == 1
        assert stats["by_level"]["FEATURE"] == 2
        assert stats["by_type"]["FUNCTIONALITY"] == 2
        assert stats["by_type"]["FOLDER_AUGMENTED"] == 1
        assert stats["by_type"]["FUNCTION_AUGMENTED"] == 2


@pytest.mark.functional
class TestVectorStoreErrorHandling:
    """Functional tests for error scenarios."""

    def test_operations_before_init_raise(self) -> None:
        """All operations raise StoreNotInitializedError before init."""
        store = VectorStore()
        node = _make_node()

        with pytest.raises(StoreNotInitializedError):
            store.add_node(node)

        with pytest.raises(StoreNotInitializedError):
            store.add_nodes_batch([node])

        with pytest.raises(StoreNotInitializedError):
            store.search("test")

        with pytest.raises(StoreNotInitializedError):
            store.search_by_node(node)

        with pytest.raises(StoreNotInitializedError):
            store.clear()

        with pytest.raises(StoreNotInitializedError):
            store.delete_node(uuid4())

        with pytest.raises(StoreNotInitializedError):
            store.get_stats()

    def test_chromadb_failure_during_add(self) -> None:
        """ChromaDB failure during add raises CollectionError."""
        coll = _mock_collection()
        coll.upsert.side_effect = RuntimeError("disk full")
        store = _initialized_store(collection=coll)

        with pytest.raises(CollectionError, match="Failed to add node"):
            store.add_node(_make_node())

    def test_chromadb_failure_during_search(self) -> None:
        """ChromaDB failure during search raises CollectionError."""
        coll = _mock_collection()
        coll.count.return_value = 5
        coll.query.side_effect = RuntimeError("index corrupted")
        store = _initialized_store(collection=coll)

        with pytest.raises(CollectionError, match="Search failed"):
            store.search("test")

    def test_chromadb_failure_during_delete(self) -> None:
        """ChromaDB failure during delete raises CollectionError."""
        coll = _mock_collection()
        coll.delete.side_effect = RuntimeError("permission denied")
        store = _initialized_store(collection=coll)

        with pytest.raises(CollectionError, match="Failed to delete"):
            store.delete_node(uuid4())

    def test_batch_with_mismatched_paths_raises(self) -> None:
        """Batch add with wrong number of paths raises ValueError."""
        store = _initialized_store()
        nodes = [_make_node(), _make_node()]

        with pytest.raises(ValueError, match="must match|same length|length"):
            store.add_nodes_batch(nodes, paths=["only_one"])

    @patch("zerorepo.vectordb.store.chromadb")
    def test_chromadb_init_failure(
        self, mock_chroma: MagicMock, tmp_path: Path
    ) -> None:
        """ChromaDB initialization failure raises CollectionError."""
        mock_chroma.PersistentClient.side_effect = RuntimeError("cannot connect")
        store = VectorStore()

        with pytest.raises(CollectionError, match="Failed to initialise"):
            store.initialize(tmp_path)

    def test_invalid_project_dir_raises(self, tmp_path: Path) -> None:
        """Non-existent project directory raises ValueError."""
        store = VectorStore()
        bad_dir = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="existing directory"):
            store.initialize(bad_dir)


@pytest.mark.functional
class TestEmbeddingGeneratorWorkflow:
    """Functional tests for embedding generation with mocked models."""

    def test_embed_single_text(self) -> None:
        """Single text embedding returns correct-dimension vector."""
        import numpy as np

        gen = EmbeddingGenerator(model_name="test-model")
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        gen._model = mock_model

        result = gen.embed("test text")
        assert result == pytest.approx([0.1, 0.2, 0.3], abs=0.001)
        mock_model.encode.assert_called_once_with("test text", convert_to_numpy=True)

    def test_embed_batch_preserves_order(self) -> None:
        """Batch embedding preserves input order."""
        import numpy as np

        gen = EmbeddingGenerator()
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([
            [0.1, 0.2],
            [0.3, 0.4],
            [0.5, 0.6],
        ], dtype=np.float32)
        gen._model = mock_model

        result = gen.embed_batch(["a", "b", "c"])
        assert len(result) == 3
        assert result[0] == pytest.approx([0.1, 0.2], abs=0.001)
        assert result[2] == pytest.approx([0.5, 0.6], abs=0.001)

    def test_embed_empty_text_rejected(self) -> None:
        """Empty and whitespace-only text is rejected."""
        gen = EmbeddingGenerator()

        with pytest.raises(ValueError, match="empty"):
            gen.embed("")

        with pytest.raises(ValueError, match="empty"):
            gen.embed("   ")

        with pytest.raises(ValueError, match="empty"):
            gen.embed_batch(["valid", ""])

    def test_lazy_model_loading(self) -> None:
        """Model is loaded lazily on first use."""
        gen = EmbeddingGenerator()
        assert gen._model is None  # Not loaded yet

        # Simulate loading
        mock_model = MagicMock()
        gen._model = mock_model
        assert gen._model is not None


@pytest.mark.functional
class TestVectorStoreNodeTextGeneration:
    """Functional tests for node text and metadata generation."""

    def test_node_with_name_only(self) -> None:
        """Node without docstring uses name only."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        node = _make_node(name="simple_feature")
        store.add_node(node)

        doc = coll.upsert.call_args.kwargs["documents"][0]
        assert doc == "simple_feature"

    def test_node_with_docstring(self) -> None:
        """Node with docstring combines name and docstring."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        node = _make_node(
            name="auth_handler",
            docstring="Handles all authentication flows",
        )
        store.add_node(node)

        doc = coll.upsert.call_args.kwargs["documents"][0]
        assert "auth_handler" in doc
        assert "Handles all authentication flows" in doc

    def test_metadata_includes_all_fields(self) -> None:
        """Stored metadata includes node_id, level, node_type, path."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        node = _make_node(
            name="test_feature",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
        )
        store.add_node(node, path="src/features/test")

        meta = coll.upsert.call_args.kwargs["metadatas"][0]
        assert meta["node_id"] == str(node.id)
        assert meta["level"] == "FEATURE"
        assert meta["node_type"] == "FILE_AUGMENTED"
        assert meta["path"] == "src/features/test"

    def test_default_path_uses_node_name(self) -> None:
        """When no path is given, node name is used as path."""
        coll = _mock_collection()
        store = _initialized_store(collection=coll)

        node = _make_node(name="my_feature")
        store.add_node(node)

        meta = coll.upsert.call_args.kwargs["metadatas"][0]
        assert meta["path"] == "my_feature"


@pytest.mark.functional
class TestVectorStoreModelsIntegration:
    """Functional tests for model classes in context."""

    def test_config_defaults_match_store(self) -> None:
        """Default config values match what VectorStore expects."""
        config = VectorStoreConfig()
        assert config.persist_dir == ".zerorepo/chroma"
        assert config.collection_name == "feature_trees"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.batch_size == 100

    def test_search_result_roundtrip(self) -> None:
        """SearchResult can be serialized and deserialized."""
        result = SearchResult(
            document="test doc",
            score=0.85,
            metadata={"node_id": "abc", "level": "MODULE"},
        )
        data = result.model_dump()
        restored = SearchResult(**data)
        assert restored.document == result.document
        assert restored.score == result.score
        assert restored.metadata == result.metadata

    def test_exception_hierarchy(self) -> None:
        """All vectordb exceptions inherit from VectorStoreError."""
        assert issubclass(StoreNotInitializedError, VectorStoreError)
        assert issubclass(EmbeddingError, VectorStoreError)
        assert issubclass(CollectionError, VectorStoreError)
        assert issubclass(VectorStoreError, Exception)
