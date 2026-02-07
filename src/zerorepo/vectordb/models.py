"""Data models for the VectorDB module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VectorStoreConfig(BaseModel):
    """Configuration for the ChromaDB-based vector store."""

    persist_dir: str = Field(
        default=".zerorepo/chroma",
        description="Directory for persistent ChromaDB storage",
    )
    collection_name: str = Field(
        default="feature_trees",
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


class SearchResult(BaseModel):
    """A single result from a similarity search."""

    document: str = Field(..., description="The matched document text")
    score: float = Field(..., description="Similarity score (higher is more similar)")
    metadata: dict = Field(
        default_factory=dict,
        description="Metadata associated with the matched document",
    )
