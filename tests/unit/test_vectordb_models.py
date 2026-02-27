"""Unit tests for VectorDB data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cobuilder.repomap.vectordb.models import SearchResult, VectorStoreConfig


class TestVectorStoreConfig:
    """Tests for VectorStoreConfig."""

    def test_default_values(self) -> None:
        cfg = VectorStoreConfig()
        assert cfg.persist_dir == ".zerorepo/chroma"
        assert cfg.collection_name == "feature_trees"
        assert cfg.embedding_model == "all-MiniLM-L6-v2"
        assert cfg.batch_size == 100

    def test_custom_values(self) -> None:
        cfg = VectorStoreConfig(
            persist_dir="/custom/path",
            collection_name="my_collection",
            embedding_model="text-embedding-3-small",
            batch_size=50,
        )
        assert cfg.persist_dir == "/custom/path"
        assert cfg.collection_name == "my_collection"
        assert cfg.embedding_model == "text-embedding-3-small"
        assert cfg.batch_size == 50

    def test_batch_size_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            VectorStoreConfig(batch_size=0)

    def test_batch_size_minimum_one(self) -> None:
        cfg = VectorStoreConfig(batch_size=1)
        assert cfg.batch_size == 1


class TestSearchResult:
    """Tests for SearchResult."""

    def test_create_minimal(self) -> None:
        result = SearchResult(document="hello", score=0.95)
        assert result.document == "hello"
        assert result.score == 0.95
        assert result.metadata == {}

    def test_create_with_metadata(self) -> None:
        meta = {"node_id": "abc-123", "level": "FEATURE"}
        result = SearchResult(document="auth login", score=0.8, metadata=meta)
        assert result.metadata == meta

    def test_document_is_required(self) -> None:
        with pytest.raises(ValidationError):
            SearchResult(score=0.5)  # type: ignore[call-arg]

    def test_score_is_required(self) -> None:
        with pytest.raises(ValidationError):
            SearchResult(document="test")  # type: ignore[call-arg]

    def test_score_can_be_negative(self) -> None:
        """Similarity scores can be negative for some distance metrics."""
        result = SearchResult(document="test", score=-0.1)
        assert result.score == -0.1

    def test_score_can_exceed_one(self) -> None:
        """Some metrics produce scores > 1."""
        result = SearchResult(document="test", score=1.5)
        assert result.score == 1.5
