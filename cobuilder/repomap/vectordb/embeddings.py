"""Embedding generation for the VectorDB module."""

from __future__ import annotations

from cobuilder.repomap.vectordb.exceptions import EmbeddingError


class EmbeddingGenerator:
    """Generate embeddings for text content using sentence-transformers.

    Uses the specified sentence-transformer model to convert text into
    dense vector representations suitable for similarity search.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the embedding generator.

        Args:
            model_name: Name of the sentence-transformer model to use.
        """
        self._model_name = model_name
        self._model = None

    def _load_model(self) -> None:
        """Lazily load the sentence-transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            except ImportError as exc:
                raise EmbeddingError(
                    "sentence-transformers is required for embedding generation. "
                    "Install with: pip install sentence-transformers"
                ) from exc
            except Exception as exc:
                raise EmbeddingError(
                    f"Failed to load model '{self._model_name}': {exc}"
                ) from exc

    @property
    def model_name(self) -> str:
        """Return the name of the embedding model."""
        return self._model_name

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: The text to embed. Must not be empty.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            ValueError: If text is empty or whitespace-only.
            EmbeddingError: If embedding generation fails.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty or whitespace-only text")

        self._load_model()

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to generate embedding: {exc}"
            ) from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts.

        Args:
            texts: List of texts to embed. Empty list returns empty list.
                Each text must not be empty.

        Returns:
            A list of embedding vectors in the same order as input texts.

        Raises:
            ValueError: If any text is empty or whitespace-only.
            EmbeddingError: If embedding generation fails.
        """
        if not texts:
            return []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(
                    f"Cannot embed empty or whitespace-only text at index {i}"
                )

        self._load_model()

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to generate batch embeddings: {exc}"
            ) from exc
