"""Result caching for the evaluation pipeline.

Provides deterministic caching for embeddings and LLM responses
to reduce token usage during iterative development.
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Cache for embedding vectors, keyed by MD5 of input text."""

    def __init__(self, cache_dir: str | Path = ".cache/embeddings"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _key(self, text: str) -> str:
        """Generate cache key from text."""
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> Any | None:
        """Retrieve cached embedding for text."""
        key = self._key(text)
        path = self.cache_dir / f"{key}.pkl"

        if path.exists():
            self._hits += 1
            with open(path, "rb") as f:
                return pickle.load(f)

        self._misses += 1
        return None

    def put(self, text: str, embedding: Any) -> None:
        """Store embedding in cache."""
        key = self._key(text)
        path = self.cache_dir / f"{key}.pkl"

        with open(path, "wb") as f:
            pickle.dump(embedding, f)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as fraction."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, int | float]:
        """Cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "cache_files": len(list(self.cache_dir.glob("*.pkl"))),
        }

    def clear(self) -> int:
        """Clear all cached embeddings. Returns count of files removed."""
        count = 0
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink()
            count += 1
        self._hits = 0
        self._misses = 0
        return count


class LLMResponseCache:
    """Cache for LLM responses, keyed by model + prompt hash."""

    def __init__(self, cache_dir: str | Path = ".cache/llm_responses"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _key(self, model: str, prompt: str) -> str:
        """Generate cache key from model and prompt."""
        content = f"{model}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, model: str, prompt: str) -> str | None:
        """Retrieve cached response."""
        key = self._key(model, prompt)
        path = self.cache_dir / f"{key}.txt"

        if path.exists():
            self._hits += 1
            return path.read_text()

        self._misses += 1
        return None

    def put(self, model: str, prompt: str, response: str) -> None:
        """Store response in cache."""
        key = self._key(model, prompt)
        path = self.cache_dir / f"{key}.txt"
        path.write_text(response)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as fraction."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, int | float]:
        """Cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "cache_files": len(list(self.cache_dir.glob("*.txt"))),
        }

    def clear(self) -> int:
        """Clear all cached responses. Returns count removed."""
        count = 0
        for f in self.cache_dir.glob("*.txt"):
            f.unlink()
            count += 1
        self._hits = 0
        self._misses = 0
        return count


class BatchedFunctionGenerator:
    """Optimizes token usage with batched function generation.

    Creates prompts for batch_size functions at once, then parses
    the response to split into individual functions.
    """

    def __init__(
        self,
        max_batch_size: int = 5,
        separator: str = "---FUNCTION---",
    ):
        self.max_batch_size = max_batch_size
        self.separator = separator

    def create_batch_prompt(
        self,
        requirements: list[dict[str, str]],
    ) -> str:
        """Create a batched prompt for multiple function requirements.

        Args:
            requirements: List of dicts with 'name', 'description', 'signature' keys
        """
        lines = [
            "Generate the following Python functions. Separate each with '---FUNCTION---'.",
            "",
        ]

        for i, req in enumerate(requirements[: self.max_batch_size], 1):
            lines.extend(
                [
                    f"### Function {i}: {req.get('name', 'unknown')}",
                    f"Description: {req.get('description', '')}",
                    f"Signature: {req.get('signature', '')}",
                    "",
                ]
            )

        return "\n".join(lines)

    def parse_batch_response(self, response: str) -> list[str]:
        """Parse batched response into individual function codes."""
        parts = response.split(self.separator)
        return [part.strip() for part in parts if part.strip()]

    def create_batches(
        self,
        requirements: list[dict[str, str]],
    ) -> list[list[dict[str, str]]]:
        """Split requirements into batches of max_batch_size."""
        batches = []
        for i in range(0, len(requirements), self.max_batch_size):
            batches.append(requirements[i : i + self.max_batch_size])
        return batches
