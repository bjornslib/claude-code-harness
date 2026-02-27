"""Unit tests for the ontology vector embedding pipeline.

Tests cover FeatureEmbedder, EmbedderConfig, and EmbeddingResult
as defined in Task 2.1.3 of PRD-RPG-P2-001.

All sentence-transformer calls are mocked so tests run without model downloads.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from pydantic import ValidationError

from cobuilder.repomap.ontology.embeddings import (
    EmbedderConfig,
    EmbeddingResult,
    FeatureEmbedder,
)
from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.vectordb.embeddings import EmbeddingGenerator
from cobuilder.repomap.vectordb.exceptions import EmbeddingError


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _mock_generator(dim: int = 384) -> MagicMock:
    """Create a mock EmbeddingGenerator that returns deterministic embeddings."""
    gen = MagicMock(spec=EmbeddingGenerator)
    gen.model_name = "mock-model"

    def _embed(text: str) -> list[float]:
        rng = np.random.default_rng(hash(text) % 2**32)
        return rng.random(dim).astype(np.float32).tolist()

    def _embed_batch(texts: list[str]) -> list[list[float]]:
        return [_embed(t) for t in texts]

    gen.embed = MagicMock(side_effect=_embed)
    gen.embed_batch = MagicMock(side_effect=_embed_batch)
    return gen


def _make_nodes(count: int = 5) -> list[FeatureNode]:
    """Create a list of sample FeatureNodes without embeddings."""
    nodes = []
    for i in range(count):
        nodes.append(
            FeatureNode(
                id=f"feature.{i}",
                name=f"Feature {i}",
                description=f"Description of feature {i}",
                level=i % 3,
                tags=[f"tag-{i}", "common"],
            )
        )
    return nodes


# ---------------------------------------------------------------------------
# EmbedderConfig Tests
# ---------------------------------------------------------------------------


class TestEmbedderConfig:
    """Test EmbedderConfig validation and defaults."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = EmbedderConfig()
        assert config.model_name == "all-MiniLM-L6-v2"
        assert config.batch_size == 100
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.rate_limit_delay == 0.0

    def test_custom_config(self) -> None:
        """Custom config values are accepted."""
        config = EmbedderConfig(
            model_name="custom-model",
            batch_size=50,
            max_retries=5,
            retry_delay=2.0,
            rate_limit_delay=0.5,
        )
        assert config.model_name == "custom-model"
        assert config.batch_size == 50
        assert config.max_retries == 5

    def test_batch_size_min_one(self) -> None:
        """Batch size must be at least 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            EmbedderConfig(batch_size=0)

    def test_batch_size_max(self) -> None:
        """Batch size must not exceed 10000."""
        with pytest.raises(ValidationError, match="less than or equal to 10000"):
            EmbedderConfig(batch_size=10001)

    def test_max_retries_bounds(self) -> None:
        """Max retries must be between 0 and 10."""
        EmbedderConfig(max_retries=0)  # OK
        EmbedderConfig(max_retries=10)  # OK
        with pytest.raises(ValidationError):
            EmbedderConfig(max_retries=-1)
        with pytest.raises(ValidationError):
            EmbedderConfig(max_retries=11)

    def test_retry_delay_must_be_positive(self) -> None:
        """Retry delay must be > 0."""
        with pytest.raises(ValidationError, match="greater than 0"):
            EmbedderConfig(retry_delay=0.0)

    def test_rate_limit_delay_non_negative(self) -> None:
        """Rate limit delay must be >= 0."""
        EmbedderConfig(rate_limit_delay=0.0)  # OK
        with pytest.raises(ValidationError):
            EmbedderConfig(rate_limit_delay=-0.1)


# ---------------------------------------------------------------------------
# EmbeddingResult Tests
# ---------------------------------------------------------------------------


class TestEmbeddingResult:
    """Test EmbeddingResult model."""

    def test_create_result(self) -> None:
        """Create a valid EmbeddingResult."""
        result = EmbeddingResult(
            total_nodes=100,
            embedded_count=95,
            failed_count=3,
            skipped_count=2,
            elapsed_seconds=5.5,
            model_name="test-model",
        )
        assert result.total_nodes == 100
        assert result.embedded_count == 95
        assert result.failed_count == 3
        assert result.skipped_count == 2

    def test_success_rate_full(self) -> None:
        """Success rate with all embedded."""
        result = EmbeddingResult(
            total_nodes=10,
            embedded_count=10,
            failed_count=0,
            skipped_count=0,
            elapsed_seconds=1.0,
            model_name="test",
        )
        assert result.success_rate == 1.0

    def test_success_rate_partial(self) -> None:
        """Success rate with some failures."""
        result = EmbeddingResult(
            total_nodes=100,
            embedded_count=80,
            failed_count=10,
            skipped_count=10,
            elapsed_seconds=1.0,
            model_name="test",
        )
        assert result.success_rate == 0.8

    def test_success_rate_empty(self) -> None:
        """Success rate with no nodes returns 1.0."""
        result = EmbeddingResult(
            total_nodes=0,
            embedded_count=0,
            failed_count=0,
            skipped_count=0,
            elapsed_seconds=0.0,
            model_name="test",
        )
        assert result.success_rate == 1.0

    def test_repr(self) -> None:
        """repr is informative."""
        result = EmbeddingResult(
            total_nodes=10,
            embedded_count=8,
            failed_count=1,
            skipped_count=1,
            elapsed_seconds=2.5,
            model_name="test",
        )
        r = repr(result)
        assert "EmbeddingResult" in r
        assert "total=10" in r
        assert "embedded=8" in r

    def test_frozen(self) -> None:
        """EmbeddingResult is frozen (immutable)."""
        result = EmbeddingResult(
            total_nodes=10,
            embedded_count=8,
            failed_count=1,
            skipped_count=1,
            elapsed_seconds=2.5,
            model_name="test",
        )
        with pytest.raises(ValidationError):
            result.total_nodes = 20  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FeatureEmbedder Init Tests
# ---------------------------------------------------------------------------


class TestFeatureEmbedderInit:
    """Test FeatureEmbedder initialization."""

    def test_default_init(self) -> None:
        """Default initialization creates config and generator."""
        embedder = FeatureEmbedder(generator=_mock_generator())
        assert embedder.config is not None
        assert embedder.generator is not None

    def test_custom_config(self) -> None:
        """Custom config is used."""
        config = EmbedderConfig(batch_size=25)
        embedder = FeatureEmbedder(config=config, generator=_mock_generator())
        assert embedder.config.batch_size == 25

    def test_custom_generator(self) -> None:
        """Custom generator is used."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        assert embedder.generator is gen


# ---------------------------------------------------------------------------
# FeatureEmbedder.embed_text Tests
# ---------------------------------------------------------------------------


class TestFeatureEmbedderEmbedText:
    """Test single text embedding."""

    def test_embed_text_returns_floats(self) -> None:
        """embed_text returns a list of floats."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        result = embedder.embed_text("hello world")
        assert isinstance(result, list)
        assert len(result) == 384
        gen.embed.assert_called_once_with("hello world")

    def test_embed_text_empty_raises(self) -> None:
        """embed_text with empty text raises ValueError."""
        gen = _mock_generator()
        gen.embed.side_effect = ValueError("Cannot embed empty")
        embedder = FeatureEmbedder(generator=gen)
        with pytest.raises(ValueError):
            embedder.embed_text("")


# ---------------------------------------------------------------------------
# FeatureEmbedder.embed_node Tests
# ---------------------------------------------------------------------------


class TestFeatureEmbedderEmbedNode:
    """Test single node embedding."""

    def test_embed_node_populates_embedding(self) -> None:
        """embed_node sets the embedding field."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        node = FeatureNode(
            id="ml.transformers",
            name="Transformers",
            level=3,
            description="Attention-based",
            tags=["nlp"],
        )
        assert node.embedding is None

        result = embedder.embed_node(node)
        assert result.embedding is not None
        assert len(result.embedding) == 384
        assert result is node  # Same object, mutated

    def test_embed_node_uses_embedding_input(self) -> None:
        """embed_node uses FeatureNode.embedding_input() for text."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        node = FeatureNode(
            id="auth",
            name="Authentication",
            level=1,
            description="User auth",
            tags=["security"],
        )
        embedder.embed_node(node)
        expected_text = node.embedding_input()
        gen.embed.assert_called_once_with(expected_text)

    def test_embed_node_skips_existing(self) -> None:
        """embed_node skips nodes with existing embeddings."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        node = FeatureNode(
            id="test",
            name="Test",
            level=0,
            embedding=[0.1, 0.2, 0.3],
        )
        result = embedder.embed_node(node)
        assert result.embedding == [0.1, 0.2, 0.3]
        gen.embed.assert_not_called()

    def test_embed_node_overwrite(self) -> None:
        """embed_node with overwrite=True re-embeds existing."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        node = FeatureNode(
            id="test",
            name="Test",
            level=0,
            embedding=[0.1, 0.2, 0.3],
        )
        result = embedder.embed_node(node, overwrite=True)
        assert result.embedding is not None
        assert len(result.embedding) == 384
        assert result.embedding != [0.1, 0.2, 0.3]
        gen.embed.assert_called_once()


# ---------------------------------------------------------------------------
# FeatureEmbedder.embed_nodes Tests
# ---------------------------------------------------------------------------


class TestFeatureEmbedderEmbedNodes:
    """Test batch node embedding."""

    def test_embed_empty_list(self) -> None:
        """embed_nodes with empty list returns zero result."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        result = embedder.embed_nodes([])
        assert result.total_nodes == 0
        assert result.embedded_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 0

    def test_embed_nodes_populates_all(self) -> None:
        """embed_nodes populates embeddings for all nodes."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        nodes = _make_nodes(5)

        result = embedder.embed_nodes(nodes)
        assert result.total_nodes == 5
        assert result.embedded_count == 5
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert all(n.embedding is not None for n in nodes)

    def test_embed_nodes_skips_existing(self) -> None:
        """Nodes with existing embeddings are skipped."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        nodes = _make_nodes(3)
        nodes[1].embedding = [0.1] * 384  # Pre-populated

        result = embedder.embed_nodes(nodes)
        assert result.total_nodes == 3
        assert result.embedded_count == 2
        assert result.skipped_count == 1

    def test_embed_nodes_overwrite(self) -> None:
        """overwrite=True re-embeds all nodes."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        nodes = _make_nodes(3)
        nodes[1].embedding = [0.1] * 384  # Pre-populated

        result = embedder.embed_nodes(nodes, overwrite=True)
        assert result.total_nodes == 3
        assert result.embedded_count == 3
        assert result.skipped_count == 0

    def test_embed_nodes_batch_size(self) -> None:
        """Nodes are processed in batches according to config."""
        gen = _mock_generator()
        config = EmbedderConfig(batch_size=2)
        embedder = FeatureEmbedder(config=config, generator=gen)
        nodes = _make_nodes(5)

        result = embedder.embed_nodes(nodes)
        assert result.embedded_count == 5
        # With 5 nodes and batch_size=2, should be 3 batch calls
        assert gen.embed_batch.call_count == 3

    def test_embed_nodes_reports_elapsed(self) -> None:
        """embed_nodes reports elapsed time."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        nodes = _make_nodes(2)

        result = embedder.embed_nodes(nodes)
        assert result.elapsed_seconds >= 0.0

    def test_embed_nodes_model_name_in_result(self) -> None:
        """Result includes the model name."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        nodes = _make_nodes(1)

        result = embedder.embed_nodes(nodes)
        assert result.model_name == "mock-model"


# ---------------------------------------------------------------------------
# FeatureEmbedder retry logic tests
# ---------------------------------------------------------------------------


class TestFeatureEmbedderRetry:
    """Test retry logic for batch embedding."""

    def test_retry_on_failure(self) -> None:
        """Retries on EmbeddingError and succeeds on second attempt."""
        gen = _mock_generator()
        # First call fails, second succeeds
        gen.embed_batch.side_effect = [
            EmbeddingError("Transient failure"),
            [[0.1] * 384, [0.2] * 384],
        ]
        config = EmbedderConfig(max_retries=1, retry_delay=0.01)
        embedder = FeatureEmbedder(config=config, generator=gen)
        nodes = _make_nodes(2)

        result = embedder.embed_nodes(nodes)
        assert result.embedded_count == 2
        assert result.failed_count == 0
        assert gen.embed_batch.call_count == 2

    def test_retry_exhausted(self) -> None:
        """All retries exhausted marks batch as failed."""
        gen = _mock_generator()
        gen.embed_batch.side_effect = EmbeddingError("Persistent failure")
        config = EmbedderConfig(max_retries=2, retry_delay=0.01)
        embedder = FeatureEmbedder(config=config, generator=gen)
        nodes = _make_nodes(3)

        result = embedder.embed_nodes(nodes)
        assert result.embedded_count == 0
        assert result.failed_count == 3
        assert gen.embed_batch.call_count == 3  # initial + 2 retries

    def test_no_retries(self) -> None:
        """With max_retries=0, failure is immediate."""
        gen = _mock_generator()
        gen.embed_batch.side_effect = EmbeddingError("Failure")
        config = EmbedderConfig(max_retries=0, retry_delay=0.01)
        embedder = FeatureEmbedder(config=config, generator=gen)
        nodes = _make_nodes(2)

        result = embedder.embed_nodes(nodes)
        assert result.failed_count == 2
        assert gen.embed_batch.call_count == 1


# ---------------------------------------------------------------------------
# FeatureEmbedder.get_embedding_texts Tests
# ---------------------------------------------------------------------------


class TestFeatureEmbedderGetTexts:
    """Test embedding text extraction."""

    def test_get_texts(self) -> None:
        """get_embedding_texts returns correct texts."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        nodes = [
            FeatureNode(
                id="auth",
                name="Auth",
                level=0,
                description="Authentication",
                tags=["security"],
            ),
            FeatureNode(
                id="db",
                name="Database",
                level=0,
            ),
        ]
        texts = embedder.get_embedding_texts(nodes)
        assert len(texts) == 2
        assert texts[0] == "auth | Authentication | security"
        assert texts[1] == "db"

    def test_get_texts_empty(self) -> None:
        """get_embedding_texts with empty list returns empty."""
        gen = _mock_generator()
        embedder = FeatureEmbedder(generator=gen)
        assert embedder.get_embedding_texts([]) == []


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Test that embedding classes are importable from the ontology package."""

    def test_import_from_package(self) -> None:
        """All new symbols importable from cobuilder.repomap.ontology."""
        from cobuilder.repomap.ontology import (
            EmbedderConfig,
            EmbeddingResult,
            FeatureEmbedder,
        )

        assert EmbedderConfig is not None
        assert EmbeddingResult is not None
        assert FeatureEmbedder is not None

    def test_import_from_module(self) -> None:
        """All symbols importable from cobuilder.repomap.ontology.embeddings."""
        from cobuilder.repomap.ontology.embeddings import (
            EmbedderConfig,
            EmbeddingResult,
            FeatureEmbedder,
        )

        assert EmbedderConfig is not None
        assert EmbeddingResult is not None
        assert FeatureEmbedder is not None
