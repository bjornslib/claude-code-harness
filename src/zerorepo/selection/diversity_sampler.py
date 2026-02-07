"""Diversity-Aware Sampling – rejection sampling with cosine similarity.

Implements Task 2.2.3 of PRD-RPG-P2-001 (Epic 2.2: Explore-Exploit Subtree
Selection), Algorithm 1. Ensures selected features are diverse by rejecting
candidates that are too similar to already-selected features.

Key requirements:
- Rejection sampling with cosine similarity threshold (default 0.85)
- Compute pairwise similarity from cached embeddings
- Track diversity metrics: silhouette score, average pairwise distance
- Selected features must have average distance > 0.5

Example::

    from zerorepo.selection.diversity_sampler import (
        DiversitySampler,
        DiversityConfig,
    )

    sampler = DiversitySampler()
    result = sampler.sample(
        candidates=feature_paths,
        n=20,
    )
    print(f"Selected {result.count} diverse features")
    print(f"Avg pairwise distance: {result.metrics.avg_pairwise_distance:.3f}")
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from zerorepo.ontology.models import FeatureNode, FeaturePath

logger = logging.getLogger(__name__)

# numpy is optional — we use pure Python fallbacks for environments without it.
try:
    import numpy as np
    from numpy.typing import NDArray

    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Vector math (pure Python fallback when numpy unavailable)
# ---------------------------------------------------------------------------


def _cosine_similarity_py(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python).

    Args:
        a: First vector.
        b: Second vector (same length as a).

    Returns:
        Cosine similarity in [-1.0, 1.0]. Returns 0.0 for zero vectors.
    """
    if len(a) != len(b):
        raise ValueError(
            f"Vector lengths must match: {len(a)} != {len(b)}"
        )
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cosine_distance_py(a: list[float], b: list[float]) -> float:
    """Compute cosine distance (1 - similarity)."""
    return 1.0 - _cosine_similarity_py(a, b)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity, using numpy when available.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity in [-1.0, 1.0].
    """
    if _NUMPY_AVAILABLE:
        arr_a = np.array(a, dtype=np.float64)
        arr_b = np.array(b, dtype=np.float64)
        norm_a = np.linalg.norm(arr_a)
        norm_b = np.linalg.norm(arr_b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
    return _cosine_similarity_py(a, b)


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance (1 - cosine_similarity)."""
    return 1.0 - cosine_similarity(a, b)


def pairwise_cosine_distances(
    embeddings: list[list[float]],
) -> list[list[float]]:
    """Compute pairwise cosine distance matrix.

    Args:
        embeddings: List of embedding vectors.

    Returns:
        Square distance matrix where [i][j] = cosine_distance(i, j).
    """
    n = len(embeddings)
    if n == 0:
        return []

    if _NUMPY_AVAILABLE:
        matrix = np.array(embeddings, dtype=np.float64)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        normalized = matrix / norms
        sim_matrix = normalized @ normalized.T
        dist_matrix = 1.0 - sim_matrix
        return dist_matrix.tolist()

    # Pure Python fallback
    distances = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _cosine_distance_py(embeddings[i], embeddings[j])
            distances[i][j] = d
            distances[j][i] = d
    return distances


# ---------------------------------------------------------------------------
# Diversity Metrics
# ---------------------------------------------------------------------------


class DiversityMetrics(BaseModel):
    """Diversity metrics for a set of selected features.

    Attributes:
        avg_pairwise_distance: Average cosine distance between all pairs
            of selected features. Higher = more diverse.
        min_pairwise_distance: Minimum pairwise distance (closest pair).
        max_pairwise_distance: Maximum pairwise distance (farthest pair).
        silhouette_score: Approximate silhouette score (–1 to 1).
            Higher values indicate better clustering/separation.
        num_selected: Number of features in the selection.
        num_rejected: Number of candidates rejected for being too similar.
        passes_diversity_threshold: Whether avg distance > required minimum.
    """

    model_config = ConfigDict(frozen=True)

    avg_pairwise_distance: float = Field(
        default=0.0,
        ge=0.0,
        description="Average pairwise cosine distance",
    )
    min_pairwise_distance: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum pairwise cosine distance",
    )
    max_pairwise_distance: float = Field(
        default=0.0,
        ge=0.0,
        description="Maximum pairwise cosine distance",
    )
    silhouette_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Approximate silhouette score",
    )
    num_selected: int = Field(
        default=0,
        ge=0,
        description="Number of selected features",
    )
    num_rejected: int = Field(
        default=0,
        ge=0,
        description="Number of rejected candidates",
    )
    passes_diversity_threshold: bool = Field(
        default=False,
        description="Whether avg distance exceeds minimum",
    )


# ---------------------------------------------------------------------------
# Sampling Result
# ---------------------------------------------------------------------------


class SamplingResult(BaseModel):
    """Result of a diversity-aware sampling operation.

    Attributes:
        selected: Feature paths that passed the diversity filter.
        metrics: Diversity metrics for the selection.
        rejected_ids: IDs of features rejected for similarity.
    """

    model_config = ConfigDict(frozen=True)

    selected: list[FeaturePath] = Field(
        default_factory=list,
        description="Selected diverse feature paths",
    )
    metrics: DiversityMetrics = Field(
        default_factory=DiversityMetrics,
        description="Diversity metrics for the selection",
    )
    rejected_ids: list[str] = Field(
        default_factory=list,
        description="IDs of features rejected for being too similar",
    )

    @property
    def count(self) -> int:
        """Number of selected features."""
        return len(self.selected)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class DiversityConfig(BaseModel):
    """Configuration for the DiversitySampler.

    Attributes:
        similarity_threshold: Maximum cosine similarity allowed between any
            pair of selected features. Candidates above this are rejected.
        min_avg_distance: Minimum average pairwise distance for the
            final selection to pass the diversity check.
        default_embedding_dim: Default embedding dimension when nodes lack
            embeddings (used for zero-vector fallback).
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    similarity_threshold: float = Field(
        default=0.85,
        gt=0.0,
        le=1.0,
        description="Max cosine similarity to accept (0.85 = 15% min distance)",
    )
    min_avg_distance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum avg pairwise distance for selection to pass",
    )
    default_embedding_dim: int = Field(
        default=384,
        ge=1,
        description="Default embedding dimensionality for zero-vector fallback",
    )


# ---------------------------------------------------------------------------
# Diversity Sampler
# ---------------------------------------------------------------------------


class DiversitySampler:
    """Diversity-aware rejection sampler for feature selection.

    Implements Algorithm 1 from PRD-RPG-P2-001: iterates through candidate
    features (sorted by relevance score), accepting each only if its cosine
    similarity to all previously selected features is below a threshold.

    The sampler uses cached embeddings from :class:`FeatureNode` objects.
    Nodes without embeddings are assigned zero vectors and will always pass
    the similarity check (they are "orthogonal" to everything).

    Args:
        config: Optional sampler configuration.

    Example::

        sampler = DiversitySampler()
        result = sampler.sample(candidates=paths, n=20)
        assert result.metrics.passes_diversity_threshold
    """

    def __init__(self, config: DiversityConfig | None = None) -> None:
        self._config = config or DiversityConfig()

    @property
    def config(self) -> DiversityConfig:
        """Return the sampler configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sample(
        self,
        candidates: list[FeaturePath],
        n: int = 20,
    ) -> SamplingResult:
        """Select up to n diverse features from candidates.

        Candidates are processed in order (assumed pre-sorted by relevance
        score). Each candidate is accepted only if its cosine similarity
        to all already-selected features is below the threshold.

        Args:
            candidates: Ordered list of candidate FeaturePaths (best first).
            n: Maximum number of features to select.

        Returns:
            A SamplingResult with selected features and metrics.

        Raises:
            ValueError: If n is not positive.
        """
        if n <= 0:
            raise ValueError("n must be positive")

        if not candidates:
            return SamplingResult()

        selected: list[FeaturePath] = []
        selected_embeddings: list[list[float]] = []
        rejected_ids: list[str] = []
        threshold = self._config.similarity_threshold

        for path in candidates:
            if len(selected) >= n:
                break

            embedding = self._get_embedding(path.leaf)

            # Check similarity against all selected
            if self._is_diverse(embedding, selected_embeddings, threshold):
                selected.append(path)
                selected_embeddings.append(embedding)
            else:
                rejected_ids.append(path.leaf.id)

        # Compute diversity metrics
        metrics = self.compute_metrics(
            selected_embeddings,
            num_rejected=len(rejected_ids),
        )

        logger.info(
            "DiversitySampler: candidates=%d, selected=%d, rejected=%d, "
            "avg_dist=%.3f, passes=%s",
            len(candidates),
            len(selected),
            len(rejected_ids),
            metrics.avg_pairwise_distance,
            metrics.passes_diversity_threshold,
        )

        return SamplingResult(
            selected=selected,
            metrics=metrics,
            rejected_ids=rejected_ids,
        )

    def compute_metrics(
        self,
        embeddings: list[list[float]],
        num_rejected: int = 0,
    ) -> DiversityMetrics:
        """Compute diversity metrics for a set of embeddings.

        Args:
            embeddings: List of embedding vectors.
            num_rejected: Number of rejected candidates.

        Returns:
            DiversityMetrics for the set.
        """
        n = len(embeddings)

        if n < 2:
            return DiversityMetrics(
                avg_pairwise_distance=1.0 if n == 1 else 0.0,
                min_pairwise_distance=1.0 if n == 1 else 0.0,
                max_pairwise_distance=1.0 if n == 1 else 0.0,
                silhouette_score=0.0,
                num_selected=n,
                num_rejected=num_rejected,
                passes_diversity_threshold=(
                    n <= 1 or True  # Single items trivially pass
                ),
            )

        # Compute pairwise distances
        dist_matrix = pairwise_cosine_distances(embeddings)

        # Collect all pairwise distances (upper triangle)
        distances: list[float] = []
        for i in range(n):
            for j in range(i + 1, n):
                distances.append(dist_matrix[i][j])

        avg_dist = sum(distances) / len(distances)
        min_dist = min(distances)
        max_dist = max(distances)

        # Compute approximate silhouette score
        silhouette = self._compute_silhouette(dist_matrix, n)

        passes = avg_dist >= self._config.min_avg_distance

        return DiversityMetrics(
            avg_pairwise_distance=avg_dist,
            min_pairwise_distance=min_dist,
            max_pairwise_distance=max_dist,
            silhouette_score=silhouette,
            num_selected=n,
            num_rejected=num_rejected,
            passes_diversity_threshold=passes,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_embedding(self, node: FeatureNode) -> list[float]:
        """Get the embedding for a node, with zero-vector fallback.

        Args:
            node: The feature node.

        Returns:
            The node's embedding, or a zero vector if None.
        """
        if node.embedding is not None:
            return node.embedding
        return [0.0] * self._config.default_embedding_dim

    def _is_diverse(
        self,
        embedding: list[float],
        selected_embeddings: list[list[float]],
        threshold: float,
    ) -> bool:
        """Check if an embedding is diverse compared to selected ones.

        A candidate is diverse if its cosine similarity to ALL selected
        embeddings is below the threshold.

        Args:
            embedding: Candidate embedding.
            selected_embeddings: Already-selected embeddings.
            threshold: Maximum allowed cosine similarity.

        Returns:
            True if the candidate is diverse (passes rejection sampling).
        """
        if not selected_embeddings:
            return True  # First item always selected

        for sel_emb in selected_embeddings:
            sim = cosine_similarity(embedding, sel_emb)
            if sim >= threshold:
                return False
        return True

    @staticmethod
    def _compute_silhouette(
        dist_matrix: list[list[float]], n: int
    ) -> float:
        """Compute approximate silhouette score.

        For a single-cluster scenario (all selected features form one
        group), we use the average distance from each point to its
        nearest neighbor vs. average distance to all others.

        A higher score (closer to 1.0) indicates points are well-spread.
        For diversity sampling, we want high silhouette.

        Args:
            dist_matrix: Pairwise distance matrix.
            n: Number of points.

        Returns:
            Silhouette score in [-1.0, 1.0].
        """
        if n < 2:
            return 0.0

        silhouette_scores: list[float] = []

        for i in range(n):
            # Average distance to all other points
            other_dists = [dist_matrix[i][j] for j in range(n) if j != i]
            avg_dist = sum(other_dists) / len(other_dists)

            # Nearest neighbor distance
            min_dist = min(other_dists) if other_dists else 0.0

            # Silhouette for this point
            max_val = max(avg_dist, min_dist)
            if max_val == 0.0:
                s = 0.0
            else:
                s = (avg_dist - min_dist) / max_val

            silhouette_scores.append(s)

        return sum(silhouette_scores) / len(silhouette_scores)
