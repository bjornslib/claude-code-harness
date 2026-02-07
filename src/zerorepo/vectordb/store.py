"""VectorStore – ChromaDB-based storage for RPG feature trees.

This module implements the core VectorStore class (Tasks 1.4.1, 1.4.3,
1.4.4, 1.4.5) providing:
- ChromaDB collection management with persistent storage
- Feature tree node storage with metadata
- Similarity search with metadata filtering
- Collection management (clear, delete, stats)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from zerorepo.vectordb.embeddings import EmbeddingGenerator
from zerorepo.vectordb.exceptions import (
    CollectionError,
    StoreNotInitializedError,
)
from zerorepo.vectordb.models import SearchResult, VectorStoreConfig

# ChromaDB is a required dependency but lazily imported to allow mocking.
try:
    import chromadb
    from chromadb.config import Settings

    _CHROMADB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CHROMADB_AVAILABLE = False


class VectorStore:
    """ChromaDB-backed vector store for RPG feature trees.

    Provides persistent storage, embedding-based similarity search, and
    metadata filtering over RPGNode documents.

    Example::

        store = VectorStore()
        store.initialize(Path("/my/project"))
        store.add_node(my_node)
        results = store.search("authentication", top_k=5)
    """

    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        """Create a VectorStore instance.

        Args:
            config: Optional configuration. Defaults to sensible values.

        Raises:
            CollectionError: If chromadb is not installed.
        """
        if not _CHROMADB_AVAILABLE:
            raise CollectionError(
                "chromadb is not installed. Run: pip install chromadb"
            )
        self._config = config or VectorStoreConfig()
        self._client: Any = None
        self._collection: Any = None
        self._embedder: EmbeddingGenerator | None = None
        self._initialized = False

    @property
    def config(self) -> VectorStoreConfig:
        """Return the store configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Initialisation (Task 1.4.1)
    # ------------------------------------------------------------------

    def initialize(
        self,
        project_dir: Path,
        embedding_model: str | None = None,
    ) -> None:
        """Create or open the ChromaDB collection with persistent storage.

        Args:
            project_dir: The project root directory. The ChromaDB data will
                be stored under ``{project_dir}/{persist_dir}``.
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

            # EmbeddingGenerator is optional – when sentence-transformers
            # is not installed, we fall back to ChromaDB's default embedder.
            try:
                self._embedder = EmbeddingGenerator(model_name=model_name)
            except Exception:
                self._embedder = None

            self._initialized = True

        except Exception as exc:
            raise CollectionError(
                f"Failed to initialise ChromaDB: {exc}"
            ) from exc

    @property
    def is_initialized(self) -> bool:
        """Whether the store has been initialised."""
        return self._initialized

    def _require_initialized(self) -> None:
        """Raise if the store has not been initialised."""
        if not self._initialized:
            raise StoreNotInitializedError(
                "VectorStore must be initialized before use. "
                "Call initialize(project_dir) first."
            )

    def count(self) -> int:
        """Return the number of documents in the collection.

        Returns:
            Number of stored documents.

        Raises:
            StoreNotInitializedError: If not initialised.
        """
        self._require_initialized()
        return self._collection.count()

    # ------------------------------------------------------------------
    # Node text and metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _node_text(node: Any) -> str:
        """Convert a node to embeddable text.

        Args:
            node: An RPGNode instance.

        Returns:
            Concatenated text of node name and docstring.
        """
        text = node.name
        docstring = getattr(node, "docstring", None)
        if docstring:
            text = f"{node.name} {docstring}"
        return text

    @staticmethod
    def _node_metadata(node: Any, path: str = "") -> dict[str, Any]:
        """Build metadata dict from a node.

        Args:
            node: An RPGNode instance.
            path: Optional hierarchical path. Defaults to node name.

        Returns:
            Metadata dict for ChromaDB storage.
        """
        node_path = path or node.name
        return {
            "node_id": str(node.id),
            "level": getattr(node, "level", "").value if hasattr(getattr(node, "level", ""), "value") else str(getattr(node, "level", "")),
            "node_type": getattr(node, "node_type", "").value if hasattr(getattr(node, "node_type", ""), "value") else str(getattr(node, "node_type", "")),
            "path": node_path,
        }

    @staticmethod
    def _build_where_clause(
        filters: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Convert a user-facing filter dict to a ChromaDB where clause.

        Supported filter keys: ``level``, ``node_type``, ``path``.

        - ``level`` and ``node_type`` generate ``$eq`` clauses.
        - ``path`` generates a ``$contains`` clause.
        - Multiple filters are combined with ``$and``.

        Args:
            filters: User-facing filter dictionary.

        Returns:
            A ChromaDB where clause dict, or None if filters are empty.
        """
        if not filters:
            return None

        clauses: list[dict[str, Any]] = []
        for key, value in filters.items():
            # Convert enum values to strings
            str_value = value.value if hasattr(value, "value") else str(value)
            if key == "path":
                clauses.append({key: {"$contains": str_value}})
            else:
                clauses.append({key: {"$eq": str_value}})

        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    # ------------------------------------------------------------------
    # Feature tree storage (Task 1.4.3)
    # ------------------------------------------------------------------

    def add_node(
        self,
        node: Any,
        path: str = "",
    ) -> None:
        """Store an RPGNode in the vector collection.

        The node is embedded using ``node.name + " " + node.docstring``
        (or just ``node.name`` if no docstring is available).

        When an :class:`EmbeddingGenerator` is available (i.e. the store
        was initialised with an embedding model), explicit embeddings are
        computed. Otherwise, ChromaDB's built-in embedding function is used.

        Args:
            node: An RPGNode instance.
            path: Hierarchical path (e.g. ``"auth/login"``). Defaults to
                the node's name if empty.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the add operation fails.
        """
        self._require_initialized()

        doc_text = self._node_text(node)
        metadata = self._node_metadata(node, path)
        node_id = str(node.id)

        try:
            upsert_kwargs: dict[str, Any] = {
                "ids": [node_id],
                "documents": [doc_text],
                "metadatas": [metadata],
            }
            if self._embedder is not None:
                upsert_kwargs["embeddings"] = [self._embedder.embed(doc_text)]
            self._collection.upsert(**upsert_kwargs)
        except Exception as exc:
            raise CollectionError(
                f"Failed to add node '{node.name}': {exc}"
            ) from exc

    def add_nodes_batch(
        self,
        nodes: list[Any],
        paths: list[str] | None = None,
    ) -> None:
        """Store multiple RPGNodes in a single batch operation.

        Args:
            nodes: List of RPGNode instances.
            paths: Optional list of hierarchical paths, one per node.
                If not provided, node names are used.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the batch add fails.
        """
        self._require_initialized()

        if not nodes:
            return

        if paths is not None and len(paths) != len(nodes):
            raise ValueError(
                f"paths length ({len(paths)}) must match nodes length ({len(nodes)})"
            )

        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for i, node in enumerate(nodes):
            path = paths[i] if paths else ""
            texts.append(self._node_text(node))
            ids.append(str(node.id))
            metadatas.append(self._node_metadata(node, path))

        try:
            # Process in batches according to config
            batch_size = self._config.batch_size
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
                if self._embedder is not None:
                    upsert_kwargs["embeddings"] = self._embedder.embed_batch(batch_texts)
                self._collection.upsert(**upsert_kwargs)
        except Exception as exc:
            raise CollectionError(
                f"Failed to add batch of {len(nodes)} nodes: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Similarity search (Task 1.4.4)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents by text query.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters (ChromaDB where clause).

        Returns:
            List of :class:`SearchResult` ordered by similarity (best first).

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the search fails.
        """
        self._require_initialized()

        try:
            # Build query kwargs
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

            where_clause = self._build_where_clause(filters) if filters else None
            if where_clause:
                query_kwargs["where"] = where_clause

            results = self._collection.query(**query_kwargs)

            return self._parse_query_results(results)

        except StoreNotInitializedError:
            raise
        except Exception as exc:
            raise CollectionError(
                f"Search failed: {exc}"
            ) from exc

    def search_by_node(
        self,
        node: Any,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Find nodes similar to the given node.

        Args:
            node: An RPGNode to find similar nodes for.
            top_k: Maximum number of results.

        Returns:
            List of :class:`SearchResult` ordered by similarity.
        """
        text = node.name
        docstring = getattr(node, "docstring", None)
        if docstring:
            text = f"{node.name} {docstring}"
        return self.search(text, top_k=top_k)

    @staticmethod
    def _parse_query_results(results: dict[str, Any]) -> list[SearchResult]:
        """Convert ChromaDB query results to SearchResult list."""
        search_results: list[SearchResult] = []

        if not results or not results.get("documents"):
            return search_results

        documents = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results.get("distances") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []

        for i, doc in enumerate(documents):
            score = 1.0 - (distances[i] if i < len(distances) else 0.0)
            meta = metadatas[i] if i < len(metadatas) else {}
            search_results.append(
                SearchResult(document=doc, score=score, metadata=meta)
            )

        return search_results

    # ------------------------------------------------------------------
    # Collection management (Task 1.4.5)
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Delete all documents from the collection.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the clear operation fails.
        """
        self._require_initialized()

        try:
            # ChromaDB doesn't have a bulk clear, so we delete all IDs
            all_ids = self._collection.get()["ids"]
            if all_ids:
                self._collection.delete(ids=all_ids)
        except Exception as exc:
            raise CollectionError(
                f"Failed to clear collection: {exc}"
            ) from exc

    def delete_node(self, node_id: UUID) -> None:
        """Remove a specific node from the collection.

        Args:
            node_id: The UUID of the node to remove.

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If the delete fails.
        """
        self._require_initialized()

        try:
            self._collection.delete(ids=[str(node_id)])
        except Exception as exc:
            raise CollectionError(
                f"Failed to delete node {node_id}: {exc}"
            ) from exc

    def get_stats(self) -> dict[str, Any]:
        """Return collection statistics.

        Returns:
            Dict with keys: ``count``, ``by_level`` (level → count mapping),
            and ``by_type`` (node_type → count mapping).

        Raises:
            StoreNotInitializedError: If the store is not initialised.
            CollectionError: If stats retrieval fails.
        """
        self._require_initialized()

        try:
            count = self._collection.count()
            stats: dict[str, Any] = {"count": count}

            if count == 0:
                return stats

            # Fetch all metadata for breakdown
            all_data = self._collection.get(include=["metadatas"])
            metadatas = all_data.get("metadatas", [])

            level_counts: dict[str, int] = {}
            type_counts: dict[str, int] = {}

            for meta in metadatas:
                level = meta.get("level", "unknown")
                node_type = meta.get("node_type", "unknown")
                level_counts[level] = level_counts.get(level, 0) + 1
                type_counts[node_type] = type_counts.get(node_type, 0) + 1

            # Add nested format (for test_vectordb.py)
            stats["by_level"] = level_counts
            stats["by_type"] = type_counts

            # Add flat format (for test_vectordb_functional.py)
            for level, count in level_counts.items():
                stats[f"by_level_{level}"] = count
            for node_type, count in type_counts.items():
                stats[f"by_type_{node_type}"] = count

            return stats

        except StoreNotInitializedError:
            raise
        except Exception as exc:
            raise CollectionError(
                f"Failed to get collection stats: {exc}"
            ) from exc
