"""Unit tests for EmbeddingCache, LLMResponseCache, and BatchedFunctionGenerator.

Tests cover:
- EmbeddingCache: put/get round-trip, miss tracking, hit rate, stats, clear, deterministic keys
- LLMResponseCache: put/get round-trip, model+prompt keying, miss, hit rate, stats, clear
- BatchedFunctionGenerator: prompt creation, response parsing, batching, edge cases
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import pytest

from zerorepo.evaluation.caching import (
    BatchedFunctionGenerator,
    EmbeddingCache,
    LLMResponseCache,
)


# ---------------------------------------------------------------------------
# EmbeddingCache
# ---------------------------------------------------------------------------


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    def test_put_and_get(self, tmp_path: Path) -> None:
        """Stored embedding should be retrievable."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        embedding = [0.1, 0.2, 0.3]
        cache.put("hello world", embedding)
        result = cache.get("hello world")
        assert result == embedding

    def test_get_miss_returns_none(self, tmp_path: Path) -> None:
        """Cache miss should return None."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.get("nonexistent") is None

    def test_hit_rate_empty(self, tmp_path: Path) -> None:
        """Hit rate with no accesses should be 0.0."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.hit_rate == 0.0

    def test_hit_rate_all_misses(self, tmp_path: Path) -> None:
        """Hit rate with all misses should be 0.0."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.get("a")
        cache.get("b")
        assert cache.hit_rate == 0.0

    def test_hit_rate_all_hits(self, tmp_path: Path) -> None:
        """Hit rate with all hits should be 1.0."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("x", [1.0])
        cache.get("x")
        cache.get("x")
        assert cache.hit_rate == 1.0

    def test_hit_rate_mixed(self, tmp_path: Path) -> None:
        """Hit rate should reflect actual hit/miss ratio."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("x", [1.0])
        cache.get("x")       # hit
        cache.get("missing")  # miss
        assert cache.hit_rate == pytest.approx(0.5)

    def test_stats(self, tmp_path: Path) -> None:
        """Stats should report hits, misses, hit_rate, cache_files."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1])
        cache.put("b", [2])
        cache.get("a")       # hit
        cache.get("c")       # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(0.5)
        assert stats["cache_files"] == 2

    def test_clear(self, tmp_path: Path) -> None:
        """Clear should remove all cache files and reset counters."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("a", [1])
        cache.put("b", [2])
        cache.get("a")  # hit

        removed = cache.clear()
        assert removed == 2
        assert cache.get("a") is None
        assert cache._hits == 0
        assert cache._misses == 1  # the get("a") after clear is a miss

    def test_clear_empty_cache(self, tmp_path: Path) -> None:
        """Clearing empty cache should return 0."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache.clear() == 0

    def test_deterministic_key(self, tmp_path: Path) -> None:
        """Same text should always produce the same cache key."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        key1 = cache._key("test string")
        key2 = cache._key("test string")
        assert key1 == key2
        expected = hashlib.md5("test string".encode()).hexdigest()
        assert key1 == expected

    def test_different_texts_different_keys(self, tmp_path: Path) -> None:
        """Different texts should produce different keys."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        assert cache._key("abc") != cache._key("def")

    def test_put_overwrites(self, tmp_path: Path) -> None:
        """Putting a new embedding for same text should overwrite."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        cache.put("key", [1, 2, 3])
        cache.put("key", [4, 5, 6])
        assert cache.get("key") == [4, 5, 6]

    def test_complex_embedding(self, tmp_path: Path) -> None:
        """Should handle complex embedding types (numpy-like lists, nested)."""
        cache = EmbeddingCache(cache_dir=tmp_path / "emb")
        embedding = {"vector": [0.1] * 768, "metadata": {"model": "test"}}
        cache.put("complex", embedding)
        assert cache.get("complex") == embedding

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Cache should create directory if it doesn't exist."""
        deep_path = tmp_path / "a" / "b" / "c" / "emb"
        cache = EmbeddingCache(cache_dir=deep_path)
        assert deep_path.exists()


# ---------------------------------------------------------------------------
# LLMResponseCache
# ---------------------------------------------------------------------------


class TestLLMResponseCache:
    """Tests for LLMResponseCache."""

    def test_put_and_get(self, tmp_path: Path) -> None:
        """Stored response should be retrievable."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("gpt-4", "Write hello", "Hello!")
        result = cache.get("gpt-4", "Write hello")
        assert result == "Hello!"

    def test_get_miss_returns_none(self, tmp_path: Path) -> None:
        """Cache miss should return None."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.get("model", "prompt") is None

    def test_different_models_different_keys(self, tmp_path: Path) -> None:
        """Same prompt with different models should be separate entries."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("gpt-4", "prompt", "response-gpt4")
        cache.put("claude", "prompt", "response-claude")
        assert cache.get("gpt-4", "prompt") == "response-gpt4"
        assert cache.get("claude", "prompt") == "response-claude"

    def test_different_prompts_same_model(self, tmp_path: Path) -> None:
        """Different prompts with same model should be separate entries."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("model", "prompt-a", "response-a")
        cache.put("model", "prompt-b", "response-b")
        assert cache.get("model", "prompt-a") == "response-a"
        assert cache.get("model", "prompt-b") == "response-b"

    def test_hit_rate_empty(self, tmp_path: Path) -> None:
        """Hit rate with no accesses should be 0.0."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.hit_rate == 0.0

    def test_hit_rate_tracking(self, tmp_path: Path) -> None:
        """Hit rate should track correctly."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "r")
        cache.get("m", "p")     # hit
        cache.get("m", "miss")  # miss
        cache.get("m", "miss2") # miss
        assert cache.hit_rate == pytest.approx(1 / 3)

    def test_stats(self, tmp_path: Path) -> None:
        """Stats should report hits, misses, hit_rate, cache_files."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m1", "p1", "r1")
        cache.put("m2", "p2", "r2")
        cache.get("m1", "p1")  # hit
        cache.get("m3", "p3")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["cache_files"] == 2

    def test_clear(self, tmp_path: Path) -> None:
        """Clear should remove all cache files and reset counters."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p1", "r1")
        cache.put("m", "p2", "r2")

        removed = cache.clear()
        assert removed == 2
        assert cache.get("m", "p1") is None
        assert cache._hits == 0
        assert cache._misses == 1

    def test_clear_empty(self, tmp_path: Path) -> None:
        """Clearing empty cache should return 0."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        assert cache.clear() == 0

    def test_deterministic_key(self, tmp_path: Path) -> None:
        """Same model+prompt should always produce the same key."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        key1 = cache._key("model", "prompt")
        key2 = cache._key("model", "prompt")
        assert key1 == key2
        expected = hashlib.md5("model:prompt".encode()).hexdigest()
        assert key1 == expected

    def test_put_overwrites(self, tmp_path: Path) -> None:
        """Putting a new response for same key should overwrite."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        cache.put("m", "p", "old")
        cache.put("m", "p", "new")
        assert cache.get("m", "p") == "new"

    def test_multiline_response(self, tmp_path: Path) -> None:
        """Should handle multiline responses."""
        cache = LLMResponseCache(cache_dir=tmp_path / "llm")
        response = "def hello():\n    return 'world'\n\n# comment"
        cache.put("m", "p", response)
        assert cache.get("m", "p") == response

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Cache should create directory if it doesn't exist."""
        deep_path = tmp_path / "x" / "y" / "llm"
        cache = LLMResponseCache(cache_dir=deep_path)
        assert deep_path.exists()


# ---------------------------------------------------------------------------
# BatchedFunctionGenerator
# ---------------------------------------------------------------------------


class TestBatchedFunctionGenerator:
    """Tests for BatchedFunctionGenerator."""

    def test_default_config(self) -> None:
        """Default batch size and separator."""
        gen = BatchedFunctionGenerator()
        assert gen.max_batch_size == 5
        assert gen.separator == "---FUNCTION---"

    def test_custom_config(self) -> None:
        """Custom batch size and separator."""
        gen = BatchedFunctionGenerator(max_batch_size=3, separator="===")
        assert gen.max_batch_size == 3
        assert gen.separator == "==="

    def test_create_batch_prompt_single(self) -> None:
        """Batch prompt with single requirement."""
        gen = BatchedFunctionGenerator()
        reqs = [{"name": "add", "description": "Add two numbers", "signature": "def add(a, b)"}]
        prompt = gen.create_batch_prompt(reqs)

        assert "---FUNCTION---" in prompt
        assert "Function 1: add" in prompt
        assert "Add two numbers" in prompt
        assert "def add(a, b)" in prompt

    def test_create_batch_prompt_multiple(self) -> None:
        """Batch prompt with multiple requirements."""
        gen = BatchedFunctionGenerator()
        reqs = [
            {"name": "add", "description": "Add", "signature": "def add(a, b)"},
            {"name": "sub", "description": "Subtract", "signature": "def sub(a, b)"},
            {"name": "mul", "description": "Multiply", "signature": "def mul(a, b)"},
        ]
        prompt = gen.create_batch_prompt(reqs)

        assert "Function 1: add" in prompt
        assert "Function 2: sub" in prompt
        assert "Function 3: mul" in prompt

    def test_create_batch_prompt_truncates_at_max(self) -> None:
        """Should only include up to max_batch_size requirements."""
        gen = BatchedFunctionGenerator(max_batch_size=2)
        reqs = [
            {"name": f"func_{i}", "description": f"Desc {i}", "signature": f"def func_{i}()"}
            for i in range(5)
        ]
        prompt = gen.create_batch_prompt(reqs)

        assert "Function 1: func_0" in prompt
        assert "Function 2: func_1" in prompt
        assert "func_2" not in prompt

    def test_create_batch_prompt_missing_keys(self) -> None:
        """Should handle missing keys with defaults."""
        gen = BatchedFunctionGenerator()
        reqs = [{"name": "test"}, {}]
        prompt = gen.create_batch_prompt(reqs)

        assert "Function 1: test" in prompt
        assert "Function 2: unknown" in prompt

    def test_parse_batch_response(self) -> None:
        """Should split response by separator."""
        gen = BatchedFunctionGenerator()
        response = (
            "def add(a, b):\n    return a + b\n"
            "---FUNCTION---\n"
            "def sub(a, b):\n    return a - b\n"
        )
        parts = gen.parse_batch_response(response)

        assert len(parts) == 2
        assert "def add(a, b):" in parts[0]
        assert "def sub(a, b):" in parts[1]

    def test_parse_batch_response_empty_parts_filtered(self) -> None:
        """Empty parts between separators should be filtered out."""
        gen = BatchedFunctionGenerator()
        response = "code1\n---FUNCTION---\n\n---FUNCTION---\ncode2"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 2

    def test_parse_batch_response_no_separator(self) -> None:
        """Response with no separator should return single part."""
        gen = BatchedFunctionGenerator()
        response = "def only_func():\n    pass"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 1
        assert "def only_func():" in parts[0]

    def test_parse_batch_response_empty(self) -> None:
        """Empty response should return empty list."""
        gen = BatchedFunctionGenerator()
        assert gen.parse_batch_response("") == []

    def test_parse_batch_response_custom_separator(self) -> None:
        """Custom separator should be used for parsing."""
        gen = BatchedFunctionGenerator(separator="===CUT===")
        response = "func_a\n===CUT===\nfunc_b"
        parts = gen.parse_batch_response(response)
        assert len(parts) == 2

    def test_create_batches_even_split(self) -> None:
        """Requirements evenly divisible by batch size."""
        gen = BatchedFunctionGenerator(max_batch_size=2)
        reqs = [{"name": f"f{i}"} for i in range(4)]
        batches = gen.create_batches(reqs)

        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2

    def test_create_batches_remainder(self) -> None:
        """Last batch should contain remainder."""
        gen = BatchedFunctionGenerator(max_batch_size=3)
        reqs = [{"name": f"f{i}"} for i in range(7)]
        batches = gen.create_batches(reqs)

        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 1

    def test_create_batches_empty(self) -> None:
        """Empty requirements should return empty batches."""
        gen = BatchedFunctionGenerator()
        assert gen.create_batches([]) == []

    def test_create_batches_single_item(self) -> None:
        """Single item should create single batch."""
        gen = BatchedFunctionGenerator(max_batch_size=5)
        reqs = [{"name": "only"}]
        batches = gen.create_batches(reqs)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_create_batches_size_equals_total(self) -> None:
        """When batch size equals total, should be single batch."""
        gen = BatchedFunctionGenerator(max_batch_size=5)
        reqs = [{"name": f"f{i}"} for i in range(5)]
        batches = gen.create_batches(reqs)
        assert len(batches) == 1
        assert len(batches[0]) == 5

    def test_create_batches_preserves_order(self) -> None:
        """Batches should preserve original order."""
        gen = BatchedFunctionGenerator(max_batch_size=2)
        reqs = [{"name": f"f{i}"} for i in range(4)]
        batches = gen.create_batches(reqs)

        assert batches[0][0]["name"] == "f0"
        assert batches[0][1]["name"] == "f1"
        assert batches[1][0]["name"] == "f2"
        assert batches[1][1]["name"] == "f3"

    def test_roundtrip_prompt_parse(self) -> None:
        """Prompt and parse should be consistent for well-formed responses."""
        gen = BatchedFunctionGenerator(max_batch_size=3)
        reqs = [
            {"name": "add", "description": "Add", "signature": "def add(a, b)"},
            {"name": "sub", "description": "Sub", "signature": "def sub(a, b)"},
        ]
        # Create prompt (just verify it's well-formed)
        prompt = gen.create_batch_prompt(reqs)
        assert "Function 1:" in prompt
        assert "Function 2:" in prompt

        # Simulate a response that uses the separator
        simulated_response = (
            "def add(a, b):\n    return a + b\n"
            "---FUNCTION---\n"
            "def sub(a, b):\n    return a - b"
        )
        parts = gen.parse_batch_response(simulated_response)
        assert len(parts) == 2
