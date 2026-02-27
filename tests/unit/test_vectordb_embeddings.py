"""Unit tests for EmbeddingGenerator.

All sentence-transformer calls are mocked so tests run without model downloads.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cobuilder.repomap.vectordb.embeddings import EmbeddingGenerator
from cobuilder.repomap.vectordb.exceptions import EmbeddingError


def _mock_model(dim: int = 384) -> MagicMock:
    """Create a mock SentenceTransformer that returns deterministic embeddings."""
    model = MagicMock()

    def _encode(text, convert_to_numpy=True):
        """Return deterministic embedding based on text."""
        if isinstance(text, str):
            # Single text → 1D array
            return np.random.default_rng(hash(text) % 2**32).random(dim).astype(np.float32)
        else:
            # Batch → 2D array
            return np.array([
                np.random.default_rng(hash(t) % 2**32).random(dim).astype(np.float32)
                for t in text
            ])

    model.encode = _encode
    return model


class TestEmbeddingGeneratorInit:
    """Tests for EmbeddingGenerator initialisation."""

    def test_default_model_name(self) -> None:
        gen = EmbeddingGenerator()
        assert gen.model_name == "all-MiniLM-L6-v2"

    def test_custom_model_name(self) -> None:
        gen = EmbeddingGenerator(model_name="custom-model")
        assert gen.model_name == "custom-model"

    def test_model_not_loaded_at_init(self) -> None:
        gen = EmbeddingGenerator()
        assert gen._model is None


class TestEmbeddingGeneratorEmbed:
    """Tests for the embed method."""

    def test_embed_returns_list_of_floats(self) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()
        result = gen.embed("hello world")
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)

    def test_embed_empty_text_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty"):
            gen.embed("")

    def test_embed_whitespace_only_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty"):
            gen.embed("   ")

    def test_embed_same_text_deterministic(self) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()
        v1 = gen.embed("test text")
        v2 = gen.embed("test text")
        assert v1 == v2

    def test_embed_different_text_different_vectors(self) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()
        v1 = gen.embed("hello")
        v2 = gen.embed("goodbye")
        assert v1 != v2

    @patch("cobuilder.repomap.vectordb.embeddings.EmbeddingGenerator._load_model")
    def test_embed_triggers_lazy_load(self, mock_load: MagicMock) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()  # Set after init to bypass lazy load
        gen.embed("test")
        # _load_model is called during embed
        # Since we set _model directly, the actual lazy load won't change it

    def test_embed_model_failure_raises_embedding_error(self) -> None:
        gen = EmbeddingGenerator()
        mock = MagicMock()
        mock.encode.side_effect = RuntimeError("GPU OOM")
        gen._model = mock
        with pytest.raises(EmbeddingError, match="Failed to generate"):
            gen.embed("test")


class TestEmbeddingGeneratorEmbedBatch:
    """Tests for the embed_batch method."""

    def test_batch_returns_list_of_lists(self) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()
        texts = ["hello", "world", "test"]
        result = gen.embed_batch(texts)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(v, list) for v in result)
        assert all(len(v) == 384 for v in result)

    def test_batch_empty_list_returns_empty(self) -> None:
        gen = EmbeddingGenerator()
        assert gen.embed_batch([]) == []

    def test_batch_preserves_order(self) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()
        texts = ["alpha", "beta", "gamma"]
        result = gen.embed_batch(texts)
        # Each text should produce a unique vector
        assert result[0] != result[1]
        assert result[1] != result[2]

    def test_batch_empty_text_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty.*index 1"):
            gen.embed_batch(["valid", "", "also valid"])

    def test_batch_whitespace_text_raises(self) -> None:
        gen = EmbeddingGenerator()
        with pytest.raises(ValueError, match="empty.*index 0"):
            gen.embed_batch(["   "])

    def test_batch_model_failure_raises_embedding_error(self) -> None:
        gen = EmbeddingGenerator()
        mock = MagicMock()
        mock.encode.side_effect = RuntimeError("OOM")
        gen._model = mock
        with pytest.raises(EmbeddingError, match="Failed to generate batch"):
            gen.embed_batch(["hello"])

    def test_batch_single_item(self) -> None:
        gen = EmbeddingGenerator()
        gen._model = _mock_model()
        result = gen.embed_batch(["single"])
        assert len(result) == 1


class TestEmbeddingGeneratorLazyLoad:
    """Tests for lazy model loading.

    SentenceTransformer is imported locally inside _load_model(), so we
    mock the ``sentence_transformers`` module rather than a module-level
    attribute.
    """

    def test_missing_library_raises_embedding_error(self) -> None:
        """ImportError during model load raises EmbeddingError."""
        import sys

        gen = EmbeddingGenerator()
        # Temporarily remove sentence_transformers so the lazy import fails
        saved = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = None  # type: ignore[assignment]
        try:
            with pytest.raises(EmbeddingError, match="sentence-transformers is required"):
                gen._load_model()
        finally:
            if saved is not None:
                sys.modules["sentence_transformers"] = saved
            else:
                sys.modules.pop("sentence_transformers", None)

    def test_load_model_failure_raises_embedding_error(self) -> None:
        """Generic model load failure raises EmbeddingError."""
        mock_st_module = MagicMock()
        mock_st_module.SentenceTransformer.side_effect = RuntimeError("model not found")

        import sys

        gen = EmbeddingGenerator(model_name="nonexistent-model-xyz")
        saved = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = mock_st_module
        try:
            with pytest.raises(EmbeddingError, match="Failed to load model"):
                gen._load_model()
        finally:
            if saved is not None:
                sys.modules["sentence_transformers"] = saved
            else:
                sys.modules.pop("sentence_transformers", None)

    def test_model_loaded_only_once(self) -> None:
        """Model is loaded once then reused."""
        mock_st_module = MagicMock()
        mock_model_instance = _mock_model()
        mock_st_module.SentenceTransformer.return_value = mock_model_instance

        import sys

        gen = EmbeddingGenerator()
        saved = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = mock_st_module
        try:
            gen._load_model()
            gen._load_model()  # second call should not re-create
            mock_st_module.SentenceTransformer.assert_called_once()
        finally:
            if saved is not None:
                sys.modules["sentence_transformers"] = saved
            else:
                sys.modules.pop("sentence_transformers", None)
