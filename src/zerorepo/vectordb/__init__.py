"""ZeroRepo VectorDB – ChromaDB-based embedding storage for feature trees.

This package implements Epic 1.4 of PRD-RPG-P1-001, providing:

- :class:`VectorStore` – ChromaDB wrapper with feature tree storage and search
- :class:`EmbeddingGenerator` – Sentence-transformer embedding generation
- :class:`VectorStoreConfig` – Configuration for the vector store
- :class:`SearchResult` – Similarity search result model
"""

from zerorepo.vectordb.embeddings import EmbeddingGenerator
from zerorepo.vectordb.exceptions import (
    CollectionError,
    EmbeddingError,
    StoreNotInitializedError,
    VectorStoreError,
)
from zerorepo.vectordb.models import SearchResult, VectorStoreConfig
from zerorepo.vectordb.store import VectorStore

__all__ = [
    "CollectionError",
    "EmbeddingError",
    "EmbeddingGenerator",
    "SearchResult",
    "StoreNotInitializedError",
    "VectorStore",
    "VectorStoreConfig",
    "VectorStoreError",
]
