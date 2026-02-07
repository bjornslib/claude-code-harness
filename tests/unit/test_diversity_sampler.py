"""Tests for the Diversity-Aware Sampler (Task 2.2.3).

Tests cover:
- DiversityConfig validation and defaults
- Cosine similarity/distance functions
- Pairwise distance matrix computation
- DiversitySampler rejection sampling
- Diversity metrics computation (avg distance, silhouette)
- SamplingResult model
- Edge cases: empty candidates, no embeddings, single item
- Diversity threshold enforcement (avg distance > 0.5)
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from zerorepo.ontology.models import FeatureNode, FeaturePath
from zerorepo.selection.diversity_sampler import (
    DiversityConfig,
    DiversityMetrics,
    DiversitySampler,
    SamplingResult,
    cosine_distance,
    cosine_similarity,
    pairwise_cosine_distances,
    _cosine_similarity_py,
    _cosine_distance_py,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    node_id: str,
    name: str,
    embedding: list[float] | None = None,
    level: int = 1,
) -> FeatureNode:
    """Create a test FeatureNode with optional embedding."""
    return FeatureNode(
        id=node_id,
        name=name,
        level=level,
        embedding=embedding,
    )


def _make_path(
    node_id: str,
    name: str,
    score: float,
    embedding: list[float] | None = None,
) -> FeaturePath:
    """Create a single-node FeaturePath."""
    node = _make_node(node_id, name, embedding=embedding)
    return FeaturePath(nodes=[node], score=score)


# ---------------------------------------------------------------------------
# Cosine similarity tests
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    """Tests for cosine similarity/distance functions."""

    def test_identical_vectors(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self) -> None:
        a = [1.0, 2.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_cosine_distance(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert cosine_distance(v, v) == pytest.approx(0.0)

    def test_cosine_distance_orthogonal(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_distance(a, b) == pytest.approx(1.0)

    def test_pure_python_cosine_similarity(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        sim = _cosine_similarity_py(a, b)
        # Known value
        expected = 32.0 / (math.sqrt(14) * math.sqrt(77))
        assert sim == pytest.approx(expected)

    def test_pure_python_cosine_distance(self) -> None:
        v = [1.0, 0.0]
        assert _cosine_distance_py(v, v) == pytest.approx(0.0)

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="lengths"):
            _cosine_similarity_py([1.0], [1.0, 2.0])


# ---------------------------------------------------------------------------
# Pairwise distances tests
# ---------------------------------------------------------------------------


class TestPairwiseDistances:
    """Tests for pairwise distance matrix."""

    def test_empty(self) -> None:
        assert pairwise_cosine_distances([]) == []

    def test_single_vector(self) -> None:
        result = pairwise_cosine_distances([[1.0, 0.0]])
        assert len(result) == 1
        assert result[0][0] == pytest.approx(0.0)

    def test_two_orthogonal(self) -> None:
        result = pairwise_cosine_distances([
            [1.0, 0.0],
            [0.0, 1.0],
        ])
        assert result[0][0] == pytest.approx(0.0)
        assert result[0][1] == pytest.approx(1.0)
        assert result[1][0] == pytest.approx(1.0)
        assert result[1][1] == pytest.approx(0.0)

    def test_symmetric(self) -> None:
        embeddings = [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ]
        result = pairwise_cosine_distances(embeddings)
        n = len(embeddings)
        for i in range(n):
            for j in range(n):
                assert result[i][j] == pytest.approx(result[j][i], abs=1e-10)


# ---------------------------------------------------------------------------
# DiversityConfig tests
# ---------------------------------------------------------------------------


class TestDiversityConfig:
    """Tests for DiversityConfig."""

    def test_defaults(self) -> None:
        cfg = DiversityConfig()
        assert cfg.similarity_threshold == 0.85
        assert cfg.min_avg_distance == 0.5
        assert cfg.default_embedding_dim == 384

    def test_custom(self) -> None:
        cfg = DiversityConfig(
            similarity_threshold=0.9,
            min_avg_distance=0.3,
            default_embedding_dim=768,
        )
        assert cfg.similarity_threshold == 0.9
        assert cfg.default_embedding_dim == 768

    def test_invalid_threshold(self) -> None:
        with pytest.raises(Exception):
            DiversityConfig(similarity_threshold=0.0)

    def test_invalid_dim(self) -> None:
        with pytest.raises(Exception):
            DiversityConfig(default_embedding_dim=0)


# ---------------------------------------------------------------------------
# DiversityMetrics tests
# ---------------------------------------------------------------------------


class TestDiversityMetrics:
    """Tests for DiversityMetrics model."""

    def test_default_metrics(self) -> None:
        m = DiversityMetrics()
        assert m.avg_pairwise_distance == 0.0
        assert m.num_selected == 0
        assert m.passes_diversity_threshold is False

    def test_frozen(self) -> None:
        m = DiversityMetrics()
        with pytest.raises(Exception):
            m.num_selected = 99  # type: ignore

    def test_custom_metrics(self) -> None:
        m = DiversityMetrics(
            avg_pairwise_distance=0.7,
            min_pairwise_distance=0.3,
            max_pairwise_distance=0.95,
            silhouette_score=0.6,
            num_selected=10,
            num_rejected=3,
            passes_diversity_threshold=True,
        )
        assert m.avg_pairwise_distance == 0.7
        assert m.passes_diversity_threshold is True


# ---------------------------------------------------------------------------
# DiversitySampler tests
# ---------------------------------------------------------------------------


class TestDiversitySampler:
    """Tests for DiversitySampler."""

    def test_properties(self) -> None:
        cfg = DiversityConfig(similarity_threshold=0.9)
        sampler = DiversitySampler(config=cfg)
        assert sampler.config.similarity_threshold == 0.9

    def test_sample_empty(self) -> None:
        sampler = DiversitySampler()
        result = sampler.sample([], n=10)
        assert result.count == 0
        assert result.metrics.num_selected == 0

    def test_sample_invalid_n(self) -> None:
        sampler = DiversitySampler()
        with pytest.raises(ValueError, match="positive"):
            sampler.sample([], n=0)

    def test_sample_single_candidate(self) -> None:
        sampler = DiversitySampler()
        candidates = [
            _make_path("a", "Feature A", 0.9, embedding=[1.0, 0.0, 0.0])
        ]
        result = sampler.sample(candidates, n=5)
        assert result.count == 1
        assert result.selected[0].leaf.id == "a"

    def test_sample_diverse_candidates(self) -> None:
        """Orthogonal embeddings should all be selected."""
        sampler = DiversitySampler()
        candidates = [
            _make_path("a", "A", 0.9, embedding=[1.0, 0.0, 0.0]),
            _make_path("b", "B", 0.8, embedding=[0.0, 1.0, 0.0]),
            _make_path("c", "C", 0.7, embedding=[0.0, 0.0, 1.0]),
        ]
        result = sampler.sample(candidates, n=3)
        assert result.count == 3
        assert result.metrics.num_rejected == 0
        assert result.metrics.passes_diversity_threshold is True

    def test_sample_rejects_similar(self) -> None:
        """Nearly identical embeddings should be rejected."""
        sampler = DiversitySampler(
            config=DiversityConfig(similarity_threshold=0.9)
        )
        candidates = [
            _make_path("a", "A", 0.9, embedding=[1.0, 0.0, 0.0]),
            _make_path("b", "B", 0.8, embedding=[0.99, 0.01, 0.0]),  # Very similar to A
            _make_path("c", "C", 0.7, embedding=[0.0, 1.0, 0.0]),
        ]
        result = sampler.sample(candidates, n=3)
        # B should be rejected (too similar to A)
        assert result.count == 2
        assert result.metrics.num_rejected == 1
        assert "b" in result.rejected_ids

    def test_sample_respects_n(self) -> None:
        sampler = DiversitySampler()
        candidates = [
            _make_path(f"f{i}", f"F{i}", 1.0 - i * 0.1,
                       embedding=[float(i == j) for j in range(5)])
            for i in range(5)
        ]
        result = sampler.sample(candidates, n=2)
        assert result.count == 2

    def test_sample_no_embeddings(self) -> None:
        """Nodes without embeddings use zero vectors (always pass)."""
        sampler = DiversitySampler()
        candidates = [
            _make_path("a", "A", 0.9, embedding=None),
            _make_path("b", "B", 0.8, embedding=None),
        ]
        result = sampler.sample(candidates, n=5)
        # Zero vectors have similarity 0.0, so both pass
        # Actually, zero vectors return sim=0.0, so they're diverse
        assert result.count == 2

    def test_diversity_threshold_check(self) -> None:
        """Verify avg_distance > 0.5 requirement."""
        cfg = DiversityConfig(
            similarity_threshold=0.99,  # Allow most candidates
            min_avg_distance=0.5,
        )
        sampler = DiversitySampler(config=cfg)

        # Nearly identical vectors
        candidates = [
            _make_path("a", "A", 0.9, embedding=[1.0, 0.0]),
            _make_path("b", "B", 0.8, embedding=[0.99, 0.01]),
        ]
        result = sampler.sample(candidates, n=5)
        # Both selected (threshold allows) but avg distance may be low
        # The passes_diversity_threshold flag tells us
        if result.count == 2:
            # avg distance between [1,0] and [0.99,0.01] is very small
            assert result.metrics.passes_diversity_threshold is False


# ---------------------------------------------------------------------------
# Compute metrics tests
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    """Tests for compute_metrics method."""

    def test_empty_embeddings(self) -> None:
        sampler = DiversitySampler()
        metrics = sampler.compute_metrics([])
        assert metrics.num_selected == 0
        assert metrics.avg_pairwise_distance == 0.0

    def test_single_embedding(self) -> None:
        sampler = DiversitySampler()
        metrics = sampler.compute_metrics([[1.0, 0.0]])
        assert metrics.num_selected == 1
        assert metrics.avg_pairwise_distance == 1.0  # Trivial

    def test_orthogonal_embeddings(self) -> None:
        sampler = DiversitySampler()
        metrics = sampler.compute_metrics([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        assert metrics.num_selected == 3
        assert metrics.avg_pairwise_distance == pytest.approx(1.0)
        assert metrics.passes_diversity_threshold is True

    def test_identical_embeddings(self) -> None:
        sampler = DiversitySampler()
        metrics = sampler.compute_metrics([
            [1.0, 0.0],
            [1.0, 0.0],
        ])
        assert metrics.avg_pairwise_distance == pytest.approx(0.0)
        assert metrics.passes_diversity_threshold is False

    def test_silhouette_score_range(self) -> None:
        sampler = DiversitySampler()
        metrics = sampler.compute_metrics([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        assert -1.0 <= metrics.silhouette_score <= 1.0


# ---------------------------------------------------------------------------
# SamplingResult tests
# ---------------------------------------------------------------------------


class TestSamplingResult:
    """Tests for SamplingResult model."""

    def test_empty(self) -> None:
        result = SamplingResult()
        assert result.count == 0
        assert result.selected == []
        assert result.rejected_ids == []

    def test_frozen(self) -> None:
        result = SamplingResult()
        with pytest.raises(Exception):
            result.selected = []  # type: ignore

    def test_count_property(self) -> None:
        result = SamplingResult(
            selected=[_make_path("a", "A", 0.9), _make_path("b", "B", 0.8)]
        )
        assert result.count == 2


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from zerorepo.selection import (
            DiversityConfig,
            DiversityMetrics,
            DiversitySampler,
            SamplingResult,
        )
        assert DiversitySampler is not None

    def test_import_from_module(self) -> None:
        from zerorepo.selection.diversity_sampler import (
            DiversityConfig,
            DiversityMetrics,
            DiversitySampler,
            SamplingResult,
            cosine_similarity,
            cosine_distance,
            pairwise_cosine_distances,
        )
        assert cosine_similarity is not None


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration-style tests combining sampling with realistic data."""

    def test_full_pipeline(self) -> None:
        """Full sampling pipeline with varied embeddings."""
        import random
        random.seed(42)

        candidates: list[FeaturePath] = []
        for i in range(30):
            # Create some clusters + noise
            if i < 10:
                base = [1.0, 0.0, 0.0, 0.0]
            elif i < 20:
                base = [0.0, 1.0, 0.0, 0.0]
            else:
                base = [0.0, 0.0, 1.0, 0.0]

            # Add noise
            embedding = [v + random.gauss(0, 0.1) for v in base]
            score = 1.0 - i * 0.02
            candidates.append(
                _make_path(f"f{i}", f"Feature {i}", score, embedding)
            )

        sampler = DiversitySampler(
            config=DiversityConfig(
                similarity_threshold=0.85,
                min_avg_distance=0.5,
            )
        )
        result = sampler.sample(candidates, n=10)

        # Should select diverse features across clusters
        assert result.count > 0
        assert result.count <= 10
        # Should have rejected some similar ones
        assert result.metrics.num_rejected > 0
        # Diversity should be reasonable
        assert result.metrics.avg_pairwise_distance > 0.0

    def test_all_identical_features(self) -> None:
        """All candidates with identical embeddings."""
        candidates = [
            _make_path(f"f{i}", f"F{i}", 0.9, embedding=[1.0, 0.0, 0.0])
            for i in range(10)
        ]
        sampler = DiversitySampler()
        result = sampler.sample(candidates, n=5)
        # Only first should be selected; rest rejected as too similar
        assert result.count == 1
        assert result.metrics.num_rejected == 9
