"""Custom exceptions for the VectorDB module."""

from __future__ import annotations


class VectorStoreError(Exception):
    """Base exception for all VectorStore errors."""


class StoreNotInitializedError(VectorStoreError):
    """Raised when the store is used before initialization.

    Examples: calling add_node or search before calling initialize().
    """


class EmbeddingError(VectorStoreError):
    """Raised when embedding generation fails.

    Examples: empty text input, model loading failure, dimension mismatch.
    """


class CollectionError(VectorStoreError):
    """Raised when a ChromaDB collection operation fails.

    Examples: add failure, query failure, delete failure.
    """
