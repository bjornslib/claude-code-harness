"""Unit tests for OntologyChromaStore.

Tests cover the ChromaDB-backed ontology store implementing OntologyBackend
as defined in Task 2.1.3 of PRD-RPG-P2-001.

ChromaDB and sentence-transformer calls are mocked so tests run without
external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from pydantic import ValidationError

from cobuilder.repomap.ontology.chromadb_store import (
    OntologyChromaStore,
    OntologyStoreConfig,
)
from cobuilder.repomap.ontology.models import FeatureNode, FeaturePath, OntologyStats
from cobuilder.repomap.vectordb.exceptions import (
    CollectionError,
    StoreNotInitializedError,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _mock_collection() -> MagicMock:
    """Create a mock ChromaDB collection."""
    coll = MagicMock()
    coll.count.return_value = 0
    coll.get.return_value = {"ids": [], "metadatas": [], "embeddings": []}
    coll.query.return_value = {
        "ids": [[]],
        "distances": [[]],
        "metadatas": [[]],
        "documents": [[]],
        "embeddings": [[]],
    }
    return coll


def _mock_embedder(dim: int = 384) -> MagicMock:
    """Create a mock EmbeddingGenerator."""
    embedder = MagicMock()
    embedder.model_name = "mock-model"

    def _embed(text: str) -> list[float]:
        rng = np.random.default_rng(hash(text) % 2**32)
        return rng.random(dim).astype(np.float32).tolist()

    def _embed_batch(texts: list[str]) -> list[list[float]]:
        return [_embed(t) for t in texts]

    embedder.embed = MagicMock(side_effect=_embed)
    embedder.embed_batch = MagicMock(side_effect=_embed_batch)
    return embedder


def _make_node(
    node_id: str = "auth",
    name: str = "Authentication",
    level: int = 1,
    parent_id: str | None = None,
    description: str | None = "User authentication",
    tags: list[str] | None = None,
) -> FeatureNode:
    """Create a sample FeatureNode."""
    return FeatureNode(
        id=node_id,
        name=name,
        level=level,
        parent_id=parent_id,
        description=description,
        tags=tags or [],
    )


def _create_initialized_store(tmp_path: Path) -> OntologyChromaStore:
    """Create an OntologyChromaStore with mocked ChromaDB and embedder."""
    store = OntologyChromaStore.__new__(OntologyChromaStore)
    store._config = OntologyStoreConfig()
    store._client = MagicMock()
    store._collection = _mock_collection()
    store._embedder = _mock_embedder()
    store._feature_embedder = MagicMock()
    store._initialized = True
    store._nodes = {}
    return store


# ---------------------------------------------------------------------------
# OntologyStoreConfig Tests
# ---------------------------------------------------------------------------


class TestOntologyStoreConfig:
    """Test OntologyStoreConfig validation and defaults."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = OntologyStoreConfig()
        assert config.persist_dir == ".zerorepo/ontology_chroma"
        assert config.collection_name == "feature_ontology"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.batch_size == 100

    def test_custom_config(self) -> None:
        """Custom config values are accepted."""
        config = OntologyStoreConfig(
            persist_dir="/custom/path",
            collection_name="my_ontology",
            embedding_model="custom-model",
            batch_size=50,
        )
        assert config.persist_dir == "/custom/path"
        assert config.collection_name == "my_ontology"

    def test_batch_size_min(self) -> None:
        """Batch size must be at least 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            OntologyStoreConfig(batch_size=0)


# ---------------------------------------------------------------------------
# OntologyChromaStore Init Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreInit:
    """Test OntologyChromaStore initialization."""

    def test_not_initialized_by_default(self) -> None:
        """Store is not initialized after creation."""
        store = OntologyChromaStore()
        assert store.is_initialized is False

    def test_custom_config(self) -> None:
        """Custom config is used."""
        config = OntologyStoreConfig(collection_name="test")
        store = OntologyChromaStore(config=config)
        assert store.config.collection_name == "test"

    def test_operations_before_init_raise(self) -> None:
        """Operations before initialization raise StoreNotInitializedError."""
        store = OntologyChromaStore()
        node = _make_node()

        with pytest.raises(StoreNotInitializedError):
            store.add_node(node)
        with pytest.raises(StoreNotInitializedError):
            store.count()
        with pytest.raises(StoreNotInitializedError):
            store.clear()


# ---------------------------------------------------------------------------
# OntologyChromaStore.initialize Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreInitialize:
    """Test store initialization."""

    def test_initialize_success(self, tmp_path: Path) -> None:
        """Initialize creates ChromaDB client and collection."""
        with patch("cobuilder.repomap.ontology.chromadb_store.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = _mock_collection()
            mock_chroma.PersistentClient.return_value = mock_client

            store = OntologyChromaStore()
            store.initialize(tmp_path)

            assert store.is_initialized
            mock_chroma.PersistentClient.assert_called_once()
            mock_client.get_or_create_collection.assert_called_once()

    def test_initialize_nonexistent_dir(self) -> None:
        """Initialize with nonexistent directory raises ValueError."""
        store = OntologyChromaStore()
        with pytest.raises(ValueError, match="existing directory"):
            store.initialize(Path("/nonexistent/path"))

    def test_initialize_file_not_dir(self, tmp_path: Path) -> None:
        """Initialize with file path raises ValueError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.touch()
        store = OntologyChromaStore()
        with pytest.raises(ValueError, match="existing directory"):
            store.initialize(file_path)


# ---------------------------------------------------------------------------
# OntologyChromaStore.add_node Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreAddNode:
    """Test node storage operations."""

    def test_add_node_calls_upsert(self, tmp_path: Path) -> None:
        """add_node calls ChromaDB upsert with correct parameters."""
        store = _create_initialized_store(tmp_path)
        node = _make_node()

        store.add_node(node)

        store._collection.upsert.assert_called_once()
        call_kwargs = store._collection.upsert.call_args
        assert call_kwargs[1]["ids"] == ["auth"]
        assert call_kwargs[1]["documents"] == [node.embedding_input()]

    def test_add_node_stores_metadata(self, tmp_path: Path) -> None:
        """add_node stores FeatureNode metadata."""
        store = _create_initialized_store(tmp_path)
        node = _make_node(tags=["security", "login"])

        store.add_node(node)

        call_kwargs = store._collection.upsert.call_args
        meta = call_kwargs[1]["metadatas"][0]
        assert meta["node_id"] == "auth"
        assert meta["name"] == "Authentication"
        assert meta["level"] == 1
        assert "security" in meta["tags"]
        assert "login" in meta["tags"]

    def test_add_node_updates_memory_index(self, tmp_path: Path) -> None:
        """add_node updates the in-memory node index."""
        store = _create_initialized_store(tmp_path)
        node = _make_node()

        store.add_node(node)
        assert "auth" in store._nodes
        assert store._nodes["auth"] is node

    def test_add_node_with_precomputed_embedding(self, tmp_path: Path) -> None:
        """add_node uses precomputed embedding when available."""
        store = _create_initialized_store(tmp_path)
        node = _make_node()
        node.embedding = [0.5] * 384

        store.add_node(node)

        call_kwargs = store._collection.upsert.call_args
        assert call_kwargs[1]["embeddings"] == [[0.5] * 384]

    def test_add_node_upsert_failure_raises(self, tmp_path: Path) -> None:
        """add_node raises CollectionError on upsert failure."""
        store = _create_initialized_store(tmp_path)
        store._collection.upsert.side_effect = RuntimeError("DB error")
        node = _make_node()

        with pytest.raises(CollectionError, match="Failed to add node"):
            store.add_node(node)


# ---------------------------------------------------------------------------
# OntologyChromaStore.add_nodes_batch Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreAddBatch:
    """Test batch node storage."""

    def test_add_batch_empty(self, tmp_path: Path) -> None:
        """Empty batch returns 0."""
        store = _create_initialized_store(tmp_path)
        assert store.add_nodes_batch([]) == 0

    def test_add_batch_stores_all(self, tmp_path: Path) -> None:
        """Batch add stores all nodes."""
        store = _create_initialized_store(tmp_path)
        nodes = [
            _make_node("a", "Node A", 0),
            _make_node("b", "Node B", 1, parent_id="a"),
            _make_node("c", "Node C", 2, parent_id="b"),
        ]

        count = store.add_nodes_batch(nodes)
        assert count == 3
        assert len(store._nodes) == 3

    def test_add_batch_respects_batch_size(self, tmp_path: Path) -> None:
        """Batch add processes nodes in configured batch sizes."""
        store = _create_initialized_store(tmp_path)
        store._config.batch_size = 2
        nodes = [_make_node(f"n{i}", f"Node {i}", i % 3) for i in range(5)]

        store.add_nodes_batch(nodes)
        # With 5 nodes and batch_size=2, should be 3 upsert calls
        assert store._collection.upsert.call_count == 3


# ---------------------------------------------------------------------------
# OntologyChromaStore.search Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreSearch:
    """Test search via OntologyBackend interface."""

    def test_search_empty_query_raises(self, tmp_path: Path) -> None:
        """Empty query raises ValueError."""
        store = _create_initialized_store(tmp_path)
        with pytest.raises(ValueError, match="empty"):
            store.search("")

    def test_search_whitespace_query_raises(self, tmp_path: Path) -> None:
        """Whitespace-only query raises ValueError."""
        store = _create_initialized_store(tmp_path)
        with pytest.raises(ValueError, match="empty"):
            store.search("   ")

    def test_search_zero_top_k_raises(self, tmp_path: Path) -> None:
        """Non-positive top_k raises ValueError."""
        store = _create_initialized_store(tmp_path)
        with pytest.raises(ValueError, match="positive"):
            store.search("test", top_k=0)

    def test_search_negative_top_k_raises(self, tmp_path: Path) -> None:
        """Negative top_k raises ValueError."""
        store = _create_initialized_store(tmp_path)
        with pytest.raises(ValueError, match="positive"):
            store.search("test", top_k=-1)

    def test_search_empty_collection(self, tmp_path: Path) -> None:
        """Search on empty collection returns empty list."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 0

        results = store.search("test")
        assert results == []

    def test_search_returns_feature_paths(self, tmp_path: Path) -> None:
        """Search returns list of FeaturePath objects."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 2
        store._collection.query.return_value = {
            "ids": [["auth", "jwt"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [
                [
                    {
                        "node_id": "auth",
                        "name": "Authentication",
                        "level": 1,
                        "description": "User auth",
                        "tags": "security,login",
                    },
                    {
                        "node_id": "jwt",
                        "name": "JWT",
                        "level": 2,
                        "parent_id": "auth",
                        "description": "JSON Web Tokens",
                        "tags": "security",
                    },
                ]
            ],
            "documents": [["auth text", "jwt text"]],
            "embeddings": [None],
        }

        results = store.search("authentication", top_k=5)
        assert len(results) == 2
        assert all(isinstance(r, FeaturePath) for r in results)

        # First result should have higher score (lower distance)
        assert results[0].score > results[1].score
        assert results[0].leaf.id == "auth"
        assert results[0].leaf.name == "Authentication"
        assert results[1].leaf.id == "jwt"

    def test_search_score_clamped(self, tmp_path: Path) -> None:
        """Scores are clamped between 0.0 and 1.0."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 1
        store._collection.query.return_value = {
            "ids": [["x"]],
            "distances": [[1.5]],  # Would produce negative score
            "metadatas": [[{"node_id": "x", "name": "X", "level": 0}]],
            "documents": [["x"]],
            "embeddings": [None],
        }

        results = store.search("test")
        assert results[0].score == 0.0  # Clamped to 0.0

    def test_search_not_initialized_raises(self) -> None:
        """Search on uninitialized store raises."""
        store = OntologyChromaStore()
        with pytest.raises(StoreNotInitializedError):
            store.search("test")


# ---------------------------------------------------------------------------
# OntologyChromaStore.search_with_filters Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreSearchFiltered:
    """Test filtered search."""

    def test_filter_by_level(self, tmp_path: Path) -> None:
        """search_with_filters passes level filter to ChromaDB."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 5

        store.search_with_filters("test", level=2)

        call_kwargs = store._collection.query.call_args[1]
        assert call_kwargs["where"] == {"level": {"$eq": 2}}

    def test_filter_by_parent_id(self, tmp_path: Path) -> None:
        """search_with_filters passes parent_id filter."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 5

        store.search_with_filters("test", parent_id="auth")

        call_kwargs = store._collection.query.call_args[1]
        assert call_kwargs["where"] == {"parent_id": {"$eq": "auth"}}

    def test_filter_by_tags(self, tmp_path: Path) -> None:
        """search_with_filters passes tag filters."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 5

        store.search_with_filters("test", tags=["security"])

        call_kwargs = store._collection.query.call_args[1]
        assert call_kwargs["where"] == {"tags": {"$contains": "security"}}

    def test_filter_multiple_tags(self, tmp_path: Path) -> None:
        """Multiple tags create $or clause."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 5

        store.search_with_filters("test", tags=["security", "auth"])

        call_kwargs = store._collection.query.call_args[1]
        where = call_kwargs["where"]
        assert "$or" in where

    def test_combined_filters(self, tmp_path: Path) -> None:
        """Multiple filter types create $and clause."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 5

        store.search_with_filters("test", level=2, parent_id="auth")

        call_kwargs = store._collection.query.call_args[1]
        where = call_kwargs["where"]
        assert "$and" in where


# ---------------------------------------------------------------------------
# OntologyChromaStore.get_node Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreGetNode:
    """Test node retrieval."""

    def test_get_node_from_memory(self, tmp_path: Path) -> None:
        """get_node returns from in-memory index."""
        store = _create_initialized_store(tmp_path)
        node = _make_node()
        store._nodes["auth"] = node

        result = store.get_node("auth")
        assert result is node

    def test_get_node_empty_id_raises(self, tmp_path: Path) -> None:
        """Empty feature_id raises ValueError."""
        store = _create_initialized_store(tmp_path)
        with pytest.raises(ValueError, match="empty"):
            store.get_node("")

    def test_get_node_not_found_raises(self, tmp_path: Path) -> None:
        """Non-existent node raises KeyError."""
        store = _create_initialized_store(tmp_path)
        store._collection.get.return_value = {
            "ids": [],
            "metadatas": [],
            "embeddings": [],
        }

        with pytest.raises(KeyError, match="not found"):
            store.get_node("nonexistent")

    def test_get_node_falls_back_to_chromadb(self, tmp_path: Path) -> None:
        """get_node falls back to ChromaDB when not in memory."""
        store = _create_initialized_store(tmp_path)
        store._collection.get.return_value = {
            "ids": ["auth"],
            "metadatas": [
                {
                    "node_id": "auth",
                    "name": "Authentication",
                    "level": 1,
                    "description": "User auth",
                    "tags": "security",
                }
            ],
            "embeddings": [[0.1] * 384],
        }

        result = store.get_node("auth")
        assert result.id == "auth"
        assert result.name == "Authentication"
        assert result.embedding is not None


# ---------------------------------------------------------------------------
# OntologyChromaStore.get_children Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreGetChildren:
    """Test children retrieval."""

    def test_get_children_from_memory(self, tmp_path: Path) -> None:
        """get_children returns children from in-memory index."""
        store = _create_initialized_store(tmp_path)
        parent = _make_node("auth", "Auth", 0)
        child1 = _make_node("jwt", "JWT", 1, parent_id="auth")
        child2 = _make_node("oauth", "OAuth", 1, parent_id="auth")
        store._nodes = {"auth": parent, "jwt": child1, "oauth": child2}
        # Mock ChromaDB to not return additional children
        store._collection.get.return_value = {
            "ids": [],
            "metadatas": [],
            "embeddings": [],
        }

        children = store.get_children("auth")
        assert len(children) == 2
        child_ids = {c.id for c in children}
        assert child_ids == {"jwt", "oauth"}

    def test_get_children_empty_id_raises(self, tmp_path: Path) -> None:
        """Empty feature_id raises ValueError."""
        store = _create_initialized_store(tmp_path)
        with pytest.raises(ValueError, match="empty"):
            store.get_children("")

    def test_get_children_parent_not_found_raises(self, tmp_path: Path) -> None:
        """Non-existent parent raises KeyError."""
        store = _create_initialized_store(tmp_path)
        store._collection.get.return_value = {
            "ids": [],
            "metadatas": [],
            "embeddings": [],
        }
        with pytest.raises(KeyError, match="not found"):
            store.get_children("nonexistent")

    def test_get_children_leaf_returns_empty(self, tmp_path: Path) -> None:
        """Leaf node returns empty children list."""
        store = _create_initialized_store(tmp_path)
        leaf = _make_node("leaf", "Leaf", 3, parent_id="parent")
        store._nodes = {"leaf": leaf}
        store._collection.get.return_value = {
            "ids": [],
            "metadatas": [],
            "embeddings": [],
        }

        children = store.get_children("leaf")
        assert children == []


# ---------------------------------------------------------------------------
# OntologyChromaStore.get_statistics Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreStats:
    """Test statistics computation."""

    def test_empty_stats(self, tmp_path: Path) -> None:
        """Empty store returns zero stats."""
        store = _create_initialized_store(tmp_path)

        stats = store.get_statistics()
        assert isinstance(stats, OntologyStats)
        assert stats.total_nodes == 0
        assert stats.total_levels == 0

    def test_populated_stats(self, tmp_path: Path) -> None:
        """Populated store returns correct stats."""
        store = _create_initialized_store(tmp_path)
        root = _make_node("root", "Root", 0)
        child1 = _make_node("c1", "Child 1", 1, parent_id="root")
        child2 = _make_node("c2", "Child 2", 1, parent_id="root")
        leaf = _make_node("l1", "Leaf 1", 2, parent_id="c1")
        leaf.embedding = [0.1] * 384
        store._nodes = {"root": root, "c1": child1, "c2": child2, "l1": leaf}

        stats = store.get_statistics()
        assert stats.total_nodes == 4
        assert stats.root_count == 1
        assert stats.leaf_count == 2  # c2 and l1 are leaves
        assert stats.nodes_with_embeddings == 1
        assert stats.total_levels == 3  # levels 0, 1, 2
        assert stats.max_depth == 2
        assert stats.metadata["backend"] == "chromadb"


# ---------------------------------------------------------------------------
# OntologyChromaStore collection management Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreManagement:
    """Test collection management operations."""

    def test_count(self, tmp_path: Path) -> None:
        """count returns collection size."""
        store = _create_initialized_store(tmp_path)
        store._collection.count.return_value = 42

        assert store.count() == 42

    def test_clear(self, tmp_path: Path) -> None:
        """clear removes all documents and in-memory nodes."""
        store = _create_initialized_store(tmp_path)
        store._nodes = {"a": _make_node("a", "A", 0)}
        store._collection.get.return_value = {"ids": ["a"]}

        store.clear()

        store._collection.delete.assert_called_once_with(ids=["a"])
        assert len(store._nodes) == 0

    def test_delete_node(self, tmp_path: Path) -> None:
        """delete_node removes a specific node."""
        store = _create_initialized_store(tmp_path)
        store._nodes = {"a": _make_node("a", "A", 0)}

        store.delete_node("a")

        store._collection.delete.assert_called_once_with(ids=["a"])
        assert "a" not in store._nodes


# ---------------------------------------------------------------------------
# OntologyChromaStore._build_where Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreBuildWhere:
    """Test where clause building."""

    def test_no_filters_returns_none(self) -> None:
        """No filters returns None."""
        assert OntologyChromaStore._build_where() is None

    def test_level_filter(self) -> None:
        """Level filter produces $eq clause."""
        result = OntologyChromaStore._build_where(level=2)
        assert result == {"level": {"$eq": 2}}

    def test_parent_id_filter(self) -> None:
        """parent_id filter produces $eq clause."""
        result = OntologyChromaStore._build_where(parent_id="auth")
        assert result == {"parent_id": {"$eq": "auth"}}

    def test_single_tag_filter(self) -> None:
        """Single tag produces $contains clause."""
        result = OntologyChromaStore._build_where(tags=["security"])
        assert result == {"tags": {"$contains": "security"}}

    def test_multiple_tags_filter(self) -> None:
        """Multiple tags produce $or clause."""
        result = OntologyChromaStore._build_where(tags=["security", "auth"])
        assert "$or" in result
        assert len(result["$or"]) == 2

    def test_combined_filters(self) -> None:
        """Multiple filter types produce $and clause."""
        result = OntologyChromaStore._build_where(level=1, parent_id="root")
        assert "$and" in result
        assert len(result["$and"]) == 2


# ---------------------------------------------------------------------------
# OntologyChromaStore._node_metadata Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreNodeMetadata:
    """Test metadata conversion."""

    def test_metadata_required_fields(self) -> None:
        """Required metadata fields are present."""
        node = _make_node()
        meta = OntologyChromaStore._node_metadata(node)
        assert meta["node_id"] == "auth"
        assert meta["name"] == "Authentication"
        assert meta["level"] == 1

    def test_metadata_optional_fields(self) -> None:
        """Optional metadata fields are included when present."""
        node = _make_node(parent_id="root", tags=["security", "login"])
        meta = OntologyChromaStore._node_metadata(node)
        assert meta["parent_id"] == "root"
        assert meta["description"] == "User authentication"
        assert "security" in meta["tags"]
        assert "login" in meta["tags"]

    def test_metadata_no_parent(self) -> None:
        """Root node metadata has no parent_id."""
        node = _make_node(parent_id=None)
        meta = OntologyChromaStore._node_metadata(node)
        assert "parent_id" not in meta

    def test_metadata_no_tags(self) -> None:
        """Node without tags has no tags in metadata."""
        node = _make_node(tags=[])
        meta = OntologyChromaStore._node_metadata(node)
        assert "tags" not in meta


# ---------------------------------------------------------------------------
# OntologyChromaStore._node_from_metadata Tests
# ---------------------------------------------------------------------------


class TestOntologyChromaStoreNodeFromMetadata:
    """Test node reconstruction from metadata."""

    def test_reconstruct_full_node(self) -> None:
        """Reconstruct a node with all metadata fields."""
        meta = {
            "node_id": "auth",
            "name": "Authentication",
            "level": 1,
            "parent_id": "root",
            "description": "User auth",
            "tags": "security,login",
        }
        node = OntologyChromaStore._node_from_metadata(meta)
        assert node.id == "auth"
        assert node.name == "Authentication"
        assert node.level == 1
        assert node.parent_id == "root"
        assert node.description == "User auth"
        assert node.tags == ["security", "login"]

    def test_reconstruct_minimal_node(self) -> None:
        """Reconstruct a node with only required fields."""
        meta = {
            "node_id": "root",
            "name": "Root",
            "level": 0,
        }
        node = OntologyChromaStore._node_from_metadata(meta)
        assert node.id == "root"
        assert node.parent_id is None
        assert node.tags == []
        assert node.embedding is None

    def test_reconstruct_with_embedding(self) -> None:
        """Reconstruct a node with embedding vector."""
        meta = {"node_id": "x", "name": "X", "level": 0}
        emb = [0.1, 0.2, 0.3]
        node = OntologyChromaStore._node_from_metadata(meta, embedding=emb)
        assert node.embedding == [0.1, 0.2, 0.3]

    def test_reconstruct_empty_tags(self) -> None:
        """Empty tags string produces empty list."""
        meta = {"node_id": "x", "name": "X", "level": 0, "tags": ""}
        node = OntologyChromaStore._node_from_metadata(meta)
        assert node.tags == []


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Test that ChromaDB store classes are importable."""

    def test_import_from_package(self) -> None:
        """Symbols importable from cobuilder.repomap.ontology."""
        from cobuilder.repomap.ontology import OntologyChromaStore, OntologyStoreConfig

        assert OntologyChromaStore is not None
        assert OntologyStoreConfig is not None

    def test_import_from_module(self) -> None:
        """Symbols importable from cobuilder.repomap.ontology.chromadb_store."""
        from cobuilder.repomap.ontology.chromadb_store import (
            OntologyChromaStore,
            OntologyStoreConfig,
        )

        assert OntologyChromaStore is not None
        assert OntologyStoreConfig is not None
