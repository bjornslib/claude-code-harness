"""ChromaDB-backed ontology store implementing OntologyBackend.

Implements Task 2.1.3 of PRD-RPG-P2-001: stores FeatureNode embeddings
in ChromaDB with metadata filters, providing semantic search over the
feature ontology.

Example::

    store = OntologyChromaStore()
    store.initialize(Path("/my/project"))
    store.add_node(feature_node)
    results = store.search("authentication", top_k=5)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from cobuilder.repomap.ontology.backend import OntologyBackend
from cobuilder.repomap.ontology.embeddings import FeatureEmbedder
from cobuilder.repomap.ontology.models import FeatureNode, FeaturePath, OntologyStats
from cobuilder.repomap.vectordb.embeddings import EmbeddingGenerator
from cobuilder.repomap.vectordb.exceptions import (
    CollectionError,
    EmbeddingError,
    StoreNotInitializedError,
)

logger = logging.getLogger(__name__)

# ChromaDB is a required dependency but lazily imported to allow mocking.
try:
    import chromadb
    from chromadb.config import Settings

    _CHROMADB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CHROMADB_AVAILABLE = False


class OntologyStoreConfig(BaseModel):
    """Configuration for the OntologyChromaStore."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    persist_dir: str = Field(
        default=".zerorepo/ontology_chroma",
        description="Directory for persistent ChromaDB storage",
    )
    collection_name: str = Field(
        default="feature_ontology",
        description="Name of the ChromaDB collection",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformer model for embeddings",
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        description="Maximum batch size for bulk operations",
    )


class OntologyChromaStore(OntologyBackend):
    """ChromaDB-backed store for feature ontology nodes.

    Implements the :class:`~zerorepo.ontology.backend.OntologyBackend` interface,
    providing semantic search over FeatureNode objects stored in ChromaDB.

    Features:
    - Stores FeatureNode embeddings with full metadata
    - Semantic search using vector similarity
    - Metadata filtering by level, tags, parent_id
    - Upsert support for updating existing nodes
    - Batch add operations

    Example::

        store = OntologyChromaStore()
        store.initialize(Path("/my/project"))

        node = FeatureNode(id="auth", name="Authentication", level=1)
        store.add_node(node)

        results = store.search("login", top_k=5)
        for path in results:
            print(f"{path.leaf.name}: {path.score:.3f}")
    """

    def __init__(self, config: OntologyStoreConfig | None = None) -> None:
        """Create an OntologyChromaStore instance.

        Args:
            config: Optional configuration. Defaults to sensible values.

        Raises:
            CollectionError: If chromadb is not installed.
        """
        if not _CHROMADB_AVAILABLE:
            raise CollectionError(
                "chromadb is not installed. Run: pip install chromadb"
            )
        self._config = config or OntologyStoreConfig()
        self._client: Any = None
        self._collection: Any = None
        self._embedder: EmbeddingGenerator | None = None
        self._feature_embedder: FeatureEmbedder | None = None
        self._initialized = False
        # In-memory index for get_node / get_children
        self._nodes: dict[str, FeatureNode] = {}

    @property
    def config(self) -> OntologyStoreConfig:
        """Return the store configuration."""
        return self._config

    @property
    def is_initialized(self) -> bool:
        """Whether the store has been initialised."""
        return self._initialized

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize(
        self,
        project_dir: Path,
        embedding_model: str | None = None,
    ) -> None:
        """Create or open the ChromaDB collection with persistent storage.

        Args:
            project_dir: The project root directory. ChromaDB data will be
                stored under ``{project_dir}/{persist_dir}``.
            embedding_model: Override the embedding model from config.

        Raises:
            ValueError: If *project_dir* does not exist or is not a directory.
            CollectionError: If ChromaDB initialisation fails.
        """
        if not project_dir.exists() or not project_dir.is_dir():
            raise ValueError(
                f"project_dir must be an existing directory: {project_dir}"
            )

        model_name = embedding_model or self._config.embedding_model
        persist_path = project_dir / self._config.persist_dir

        try:
            persist_path.mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=str(persist_path),
                settings=Settings(anonymized_telemetry=False),
            )

            self._collection = self._client.get_or_create_collection(
                name=self._config.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            # Initialize embedding generator
            try:
                self._embedder = EmbeddingGenerator(model_name=model_name)
                self._feature_embedder = FeatureEmbedder(generator=self._embedder)
            except Exception:
                self._embedder = None
                self._feature_embedder = None

            self._initialized = True

            logger.info(
                "OntologyChromaStore initialized at %s with collection '%s'",
                persist_path,
                self._config.collection_name,
            )

        except Exception as exc:
            raise CollectionError(
                f"Failed to initialise OntologyChromaStore: {exc}"
            ) from exc

    def _require_initialized(self) -> None:
        """Raise if the store has not been initialised."""
        if not self._initialized:
            raise StoreNotInitializedError(
                "OntologyChromaStore must be initialized before use. "
                "Call initialize(project_dir) first."
            )

    # ------------------------------------------------------------------
    # Node storage
    # ------------------------------------------------------------------

    @staticmethod
    def _node_metadata(node: FeatureNode) -> dict[str, Any]:
        """Build ChromaDB metadata dict from a FeatureNode.

        Stores all searchable/filterable fields as metadata.

        Args:
            node: The feature node.

        Returns:
            Metadata dict for ChromaDB storage.
        """
        meta: dict[str, Any] = {
            "node_id": node.id,
            "name": node.name,
            "level": node.level,
        }
        if node.parent_id is not None:
            meta["parent_id"] = node.parent_id
        if node.description is not None:
            meta["description"] = node.description
        if node.tags:
            meta["tags"] = ",".join(node.tags)
        return meta

    @staticmethod
    def _node_from_metadata(
        meta: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> FeatureNode:
        """Reconstruct a FeatureNode from ChromaDB metadata.

        Args:
            meta: Metadata dict from ChromaDB.
            embedding: Optional embedding vector.

        Returns:
            A reconstructed FeatureNode.
        """
        tags_str = meta.get("tags", "")
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

        return FeatureNode(
            id=meta["node_id"],
            name=meta["name"],
            level=meta["level"],
            parent_id=meta.get("parent_id"),
            description=meta.get("description"),
            tags=tags,
            embedding=embedding,
        )

    def add_node(self, node: FeatureNode) -> None:
        """Store a FeatureNode in the ChromaDB collection.

        Uses ``node.embedding_input()`` for the document text. If an
        EmbeddingGenerator is available, explicit embeddings are computed.
        Otherwise, ChromaDB's built-in embedding function is used.

        Args:
            node: The feature node to store.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the add operation fails.
        """
        self._require_initialized()

        doc_text = node.embedding_input()
        metadata = self._node_metadata(node)

        try:
            upsert_kwargs: dict[str, Any] = {
                "ids": [node.id],
                "documents": [doc_text],
                "metadatas": [metadata],
            }
            if self._embedder is not None:
                if node.embedding is not None:
                    upsert_kwargs["embeddings"] = [node.embedding]
                else:
                    upsert_kwargs["embeddings"] = [
                        self._embedder.embed(doc_text)
                    ]
            self._collection.upsert(**upsert_kwargs)

            # Update in-memory index
            self._nodes[node.id] = node

        except Exception as exc:
            raise CollectionError(
                f"Failed to add node '{node.id}': {exc}"
            ) from exc

    def add_nodes_batch(
        self,
        nodes: list[FeatureNode],
        embed: bool = True,
    ) -> int:
        """Store multiple FeatureNodes in batch.

        Args:
            nodes: List of FeatureNodes to store.
            embed: If True and a FeatureEmbedder is available, auto-embed
                nodes that don't have embeddings. Defaults to True.

        Returns:
            Number of nodes successfully stored.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the batch add fails.
        """
        self._require_initialized()

        if not nodes:
            return 0

        # Optionally embed nodes first
        if embed and self._feature_embedder is not None:
            self._feature_embedder.embed_nodes(nodes)

        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        embeddings_list: list[list[float]] = []
        has_embeddings = True

        for node in nodes:
            texts.append(node.embedding_input())
            ids.append(node.id)
            metadatas.append(self._node_metadata(node))
            if node.embedding is not None:
                embeddings_list.append(node.embedding)
            else:
                has_embeddings = False

        try:
            batch_size = self._config.batch_size
            stored = 0

            for start in range(0, len(texts), batch_size):
                end = start + batch_size
                batch_texts = texts[start:end]
                batch_ids = ids[start:end]
                batch_meta = metadatas[start:end]

                upsert_kwargs: dict[str, Any] = {
                    "ids": batch_ids,
                    "documents": batch_texts,
                    "metadatas": batch_meta,
                }

                if has_embeddings and embeddings_list:
                    upsert_kwargs["embeddings"] = embeddings_list[start:end]
                elif self._embedder is not None:
                    upsert_kwargs["embeddings"] = self._embedder.embed_batch(
                        batch_texts
                    )

                self._collection.upsert(**upsert_kwargs)
                stored += len(batch_ids)

            # Update in-memory index
            for node in nodes:
                self._nodes[node.id] = node

            return stored

        except Exception as exc:
            raise CollectionError(
                f"Failed to add batch of {len(nodes)} nodes: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # OntologyBackend interface implementation
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
        """Search for features matching a query using vector similarity.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            Ordered list of FeaturePath results, sorted by descending
            relevance score.

        Raises:
            ValueError: If query is empty or top_k is not positive.
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the search fails.
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        self._require_initialized()

        try:
            collection_count = self._collection.count()
            if collection_count == 0:
                return []

            query_kwargs: dict[str, Any] = {
                "n_results": min(top_k, collection_count),
            }

            if self._embedder is not None:
                query_kwargs["query_embeddings"] = [self._embedder.embed(query)]
            else:
                query_kwargs["query_texts"] = [query]

            results = self._collection.query(**query_kwargs)
            return self._parse_results(results)

        except (ValueError, StoreNotInitializedError):
            raise
        except Exception as exc:
            raise CollectionError(f"Search failed: {exc}") from exc

    def search_with_filters(
        self,
        query: str,
        top_k: int = 10,
        level: int | None = None,
        parent_id: str | None = None,
        tags: list[str] | None = None,
    ) -> list[FeaturePath]:
        """Search with additional metadata filters.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.
            level: Filter by hierarchical level.
            parent_id: Filter by parent node ID.
            tags: Filter by tags (any match).

        Returns:
            Ordered list of FeaturePath results.

        Raises:
            ValueError: If query is empty or top_k is not positive.
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the search fails.
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        self._require_initialized()

        try:
            collection_count = self._collection.count()
            if collection_count == 0:
                return []

            query_kwargs: dict[str, Any] = {
                "n_results": min(top_k, collection_count),
            }

            if self._embedder is not None:
                query_kwargs["query_embeddings"] = [self._embedder.embed(query)]
            else:
                query_kwargs["query_texts"] = [query]

            # Build where clause
            where = self._build_where(level, parent_id, tags)
            if where:
                query_kwargs["where"] = where

            results = self._collection.query(**query_kwargs)
            return self._parse_results(results)

        except (ValueError, StoreNotInitializedError):
            raise
        except Exception as exc:
            raise CollectionError(f"Filtered search failed: {exc}") from exc

    def get_node(self, feature_id: str) -> FeatureNode:
        """Retrieve a single feature node by ID.

        Args:
            feature_id: The unique feature ID.

        Returns:
            The FeatureNode with the given ID.

        Raises:
            ValueError: If feature_id is empty.
            KeyError: If no node with the given ID exists.
        """
        if not feature_id:
            raise ValueError("feature_id must not be empty")

        # Check in-memory index first
        if feature_id in self._nodes:
            return self._nodes[feature_id]

        # Fall back to ChromaDB
        if self._initialized and self._collection is not None:
            try:
                result = self._collection.get(
                    ids=[feature_id],
                    include=["metadatas", "embeddings"],
                )
                if result["ids"]:
                    meta = result["metadatas"][0]
                    emb = (
                        result["embeddings"][0]
                        if result.get("embeddings")
                        else None
                    )
                    node = self._node_from_metadata(meta, emb)
                    self._nodes[feature_id] = node
                    return node
            except Exception:
                pass

        raise KeyError(f"Node '{feature_id}' not found")

    def get_children(self, feature_id: str) -> list[FeatureNode]:
        """List direct children of a feature node.

        Args:
            feature_id: The unique ID of the parent feature node.

        Returns:
            List of child FeatureNodes.

        Raises:
            ValueError: If feature_id is empty.
            KeyError: If no node with the given ID exists.
        """
        if not feature_id:
            raise ValueError("feature_id must not be empty")

        # Ensure the parent exists
        self.get_node(feature_id)

        # Search in-memory index
        children = [
            node
            for node in self._nodes.values()
            if node.parent_id == feature_id
        ]

        # If store is initialized but we might not have all nodes in memory,
        # also check ChromaDB
        if self._initialized and self._collection is not None:
            try:
                result = self._collection.get(
                    where={"parent_id": {"$eq": feature_id}},
                    include=["metadatas", "embeddings"],
                )
                child_ids_in_memory = {c.id for c in children}
                if result["ids"]:
                    for i, nid in enumerate(result["ids"]):
                        if nid not in child_ids_in_memory:
                            meta = result["metadatas"][i]
                            emb = (
                                result["embeddings"][i]
                                if result.get("embeddings")
                                else None
                            )
                            node = self._node_from_metadata(meta, emb)
                            children.append(node)
                            self._nodes[node.id] = node
            except Exception:
                pass

        return children

    def get_statistics(self) -> OntologyStats:
        """Compute aggregate ontology statistics.

        Returns:
            OntologyStats with summary metrics.
        """
        total = len(self._nodes)

        if total == 0:
            return OntologyStats(
                total_nodes=0,
                total_levels=0,
                avg_children=0.0,
                max_depth=0,
            )

        levels = {node.level for node in self._nodes.values()}
        roots = [n for n in self._nodes.values() if n.is_root]
        parent_ids = {n.parent_id for n in self._nodes.values() if n.parent_id}
        leaves = [
            n for n in self._nodes.values() if n.id not in parent_ids
        ]
        embedded = sum(
            1 for n in self._nodes.values() if n.embedding is not None
        )

        # Average children per non-leaf node
        non_leaf_count = total - len(leaves)
        if non_leaf_count > 0:
            child_count = total - len(roots)
            avg_children = child_count / non_leaf_count
        else:
            avg_children = 0.0

        return OntologyStats(
            total_nodes=total,
            total_levels=len(levels),
            avg_children=avg_children,
            max_depth=max(levels),
            root_count=len(roots),
            leaf_count=len(leaves),
            nodes_with_embeddings=embedded,
            metadata={
                "backend": "chromadb",
                "collection": self._config.collection_name,
            },
        )

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of documents in the collection.

        Returns:
            Number of stored documents.

        Raises:
            StoreNotInitializedError: If not initialised.
        """
        self._require_initialized()
        return self._collection.count()

    def clear(self) -> None:
        """Delete all documents from the collection and clear in-memory index.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the clear operation fails.
        """
        self._require_initialized()

        try:
            all_ids = self._collection.get()["ids"]
            if all_ids:
                self._collection.delete(ids=all_ids)
            self._nodes.clear()
        except Exception as exc:
            raise CollectionError(
                f"Failed to clear collection: {exc}"
            ) from exc

    def delete_node(self, feature_id: str) -> None:
        """Remove a specific node from the collection.

        Args:
            feature_id: The ID of the node to remove.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the delete fails.
        """
        self._require_initialized()

        try:
            self._collection.delete(ids=[feature_id])
            self._nodes.pop(feature_id, None)
        except Exception as exc:
            raise CollectionError(
                f"Failed to delete node '{feature_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where(
        level: int | None = None,
        parent_id: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Build a ChromaDB where clause from filter parameters.

        Args:
            level: Filter by hierarchical level.
            parent_id: Filter by parent ID.
            tags: Filter by tags (any match via $contains).

        Returns:
            A ChromaDB where clause dict, or None if no filters.
        """
        clauses: list[dict[str, Any]] = []

        if level is not None:
            clauses.append({"level": {"$eq": level}})
        if parent_id is not None:
            clauses.append({"parent_id": {"$eq": parent_id}})
        if tags:
            # Match any of the provided tags using $contains on the
            # comma-separated tags string
            tag_clauses = [
                {"tags": {"$contains": tag}} for tag in tags
            ]
            if len(tag_clauses) == 1:
                clauses.append(tag_clauses[0])
            else:
                clauses.append({"$or": tag_clauses})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _parse_results(self, results: dict[str, Any]) -> list[FeaturePath]:
        """Convert ChromaDB query results to FeaturePath list.

        Args:
            results: Raw ChromaDB query results.

        Returns:
            List of FeaturePath objects sorted by score.
        """
        paths: list[FeaturePath] = []

        if not results or not results.get("ids"):
            return paths

        ids = results["ids"][0] if results["ids"] else []
        distances = (
            results["distances"][0] if results.get("distances") else []
        )
        metadatas = (
            results["metadatas"][0] if results.get("metadatas") else []
        )
        embeddings_result = (
            results["embeddings"][0]
            if results.get("embeddings")
            else [None] * len(ids)
        )

        for i, node_id in enumerate(ids):
            # Cosine distance → similarity score
            distance = distances[i] if i < len(distances) else 0.0
            score = max(0.0, min(1.0, 1.0 - distance))

            meta = metadatas[i] if i < len(metadatas) else {}
            emb = (
                embeddings_result[i]
                if embeddings_result and i < len(embeddings_result)
                else None
            )

            # Reconstruct FeatureNode from metadata
            node = self._node_from_metadata(meta, emb)

            # Build a single-node path (leaf = root for flat results)
            path = FeaturePath(nodes=[node], score=score)
            paths.append(path)

        return paths
