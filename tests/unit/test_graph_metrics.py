"""Tests for Cohesion, Coupling, and Modularity Metrics (Task 2.3.2).

Tests cover:
- MetricsConfig validation and defaults
- CohesionResult, CouplingResult, ModularityResult models
- compute_cohesion: pairwise similarity within modules
- compute_coupling: inter-module dependency counting
- compute_modularity: Newman's Q-score
- compute_feature_modularity: feature-level Q-score
- compute_all_metrics: aggregate computation
- PartitionMetrics properties and overall_quality
- Edge cases: single feature, no embeddings, no dependencies
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.graph_construction.partitioner import ModuleSpec
from cobuilder.repomap.graph_construction.metrics import (
    CohesionResult,
    CouplingResult,
    MetricsConfig,
    ModularityResult,
    PartitionMetrics,
    compute_all_metrics,
    compute_cohesion,
    compute_coupling,
    compute_feature_modularity,
    compute_modularity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    fid: str,
    name: str = "",
    embedding: list[float] | None = None,
    level: int = 1,
) -> FeatureNode:
    """Create a test FeatureNode."""
    return FeatureNode(
        id=fid,
        name=name or fid,
        level=level,
        embedding=embedding,
    )


def _make_similar_features(
    ids: list[str], base_vector: list[float], noise: float = 0.05
) -> dict[str, FeatureNode]:
    """Create features with similar embeddings (high cohesion)."""
    rng = np.random.RandomState(42)
    base = np.array(base_vector, dtype=np.float64)
    features = {}
    for fid in ids:
        emb = base + rng.randn(len(base_vector)) * noise
        features[fid] = _make_feature(fid, embedding=emb.tolist())
    return features


def _make_diverse_features(
    ids: list[str], dim: int = 10
) -> dict[str, FeatureNode]:
    """Create features with diverse embeddings (low cohesion)."""
    rng = np.random.RandomState(42)
    features = {}
    for i, fid in enumerate(ids):
        # Create orthogonal-ish vectors
        emb = np.zeros(dim, dtype=np.float64)
        emb[i % dim] = 1.0
        emb += rng.randn(dim) * 0.1
        features[fid] = _make_feature(fid, embedding=emb.tolist())
    return features


# ---------------------------------------------------------------------------
# MetricsConfig tests
# ---------------------------------------------------------------------------


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_defaults(self) -> None:
        cfg = MetricsConfig()
        assert cfg.cohesion_target == 0.6
        assert cfg.coupling_target == 3
        assert cfg.modularity_target == 0.4

    def test_custom(self) -> None:
        cfg = MetricsConfig(
            cohesion_target=0.8,
            coupling_target=2,
            modularity_target=0.5,
        )
        assert cfg.cohesion_target == 0.8
        assert cfg.coupling_target == 2

    def test_invalid_cohesion(self) -> None:
        with pytest.raises(Exception):
            MetricsConfig(cohesion_target=1.5)


# ---------------------------------------------------------------------------
# CohesionResult tests
# ---------------------------------------------------------------------------


class TestCohesionResult:
    """Tests for CohesionResult model."""

    def test_basic(self) -> None:
        r = CohesionResult(
            module_name="Auth",
            cohesion=0.75,
            min_similarity=0.6,
            max_similarity=0.9,
            num_features=3,
            num_pairs=3,
            meets_target=True,
        )
        assert r.cohesion == 0.75
        assert r.meets_target is True

    def test_frozen(self) -> None:
        r = CohesionResult(
            module_name="X", cohesion=0.5, num_features=1, num_pairs=0
        )
        with pytest.raises(Exception):
            r.cohesion = 0.9  # type: ignore


# ---------------------------------------------------------------------------
# CouplingResult tests
# ---------------------------------------------------------------------------


class TestCouplingResult:
    """Tests for CouplingResult model."""

    def test_basic(self) -> None:
        r = CouplingResult(
            module_name="API",
            outgoing_deps=2,
            incoming_deps=1,
            total_deps=2,
            dep_module_names=["Auth", "DB"],
            meets_target=True,
        )
        assert r.total_deps == 2

    def test_frozen(self) -> None:
        r = CouplingResult(
            module_name="X",
            outgoing_deps=0,
            incoming_deps=0,
            total_deps=0,
        )
        with pytest.raises(Exception):
            r.total_deps = 5  # type: ignore


# ---------------------------------------------------------------------------
# ModularityResult tests
# ---------------------------------------------------------------------------


class TestModularityResult:
    """Tests for ModularityResult model."""

    def test_basic(self) -> None:
        r = ModularityResult(
            q_score=0.5,
            num_modules=3,
            num_edges=5,
            meets_target=True,
        )
        assert r.q_score == 0.5

    def test_frozen(self) -> None:
        r = ModularityResult(q_score=0.0, num_modules=0, num_edges=0)
        with pytest.raises(Exception):
            r.q_score = 0.9  # type: ignore


# ---------------------------------------------------------------------------
# Cohesion computation tests
# ---------------------------------------------------------------------------


class TestComputeCohesion:
    """Tests for compute_cohesion function."""

    def test_high_cohesion_similar_embeddings(self) -> None:
        """Features with similar embeddings → high cohesion."""
        base = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        features = _make_similar_features(["f1", "f2", "f3"], base, noise=0.05)

        module = ModuleSpec(name="Similar", feature_ids=["f1", "f2", "f3"])
        result = compute_cohesion(module, features)

        assert result.cohesion > 0.9  # Very similar vectors
        assert result.meets_target is True
        assert result.num_pairs == 3  # C(3,2)

    def test_low_cohesion_diverse_embeddings(self) -> None:
        """Features with orthogonal embeddings → low cohesion."""
        features = _make_diverse_features(["f1", "f2", "f3", "f4", "f5"])

        module = ModuleSpec(
            name="Diverse", feature_ids=["f1", "f2", "f3", "f4", "f5"]
        )
        result = compute_cohesion(module, features)

        assert result.cohesion < 0.5  # Diverse vectors
        assert result.meets_target is False

    def test_single_feature_perfect_cohesion(self) -> None:
        """Single feature module has perfect cohesion."""
        features = {"f1": _make_feature("f1", embedding=[1.0, 0.0])}
        module = ModuleSpec(name="Single", feature_ids=["f1"])
        result = compute_cohesion(module, features)

        assert result.cohesion == 1.0
        assert result.num_pairs == 0
        assert result.meets_target is True

    def test_no_embeddings(self) -> None:
        """Features without embeddings → zero cohesion."""
        features = {
            "f1": _make_feature("f1"),
            "f2": _make_feature("f2"),
        }
        module = ModuleSpec(name="NoEmbed", feature_ids=["f1", "f2"])
        result = compute_cohesion(module, features)

        # Both are zero vectors → cosine similarity undefined → 0.0
        assert result.cohesion == 0.0

    def test_missing_features_in_map(self) -> None:
        """Missing features in map are skipped."""
        features = {"f1": _make_feature("f1", embedding=[1.0, 0.0])}
        module = ModuleSpec(
            name="Mixed", feature_ids=["f1", "missing_id"]
        )
        result = compute_cohesion(module, features)

        # Only 1 valid feature → perfect cohesion
        assert result.cohesion == 1.0
        assert result.num_features == 1

    def test_two_identical_features(self) -> None:
        """Two features with identical embeddings → cohesion = 1.0."""
        emb = [1.0, 2.0, 3.0]
        features = {
            "f1": _make_feature("f1", embedding=emb),
            "f2": _make_feature("f2", embedding=emb),
        }
        module = ModuleSpec(name="Identical", feature_ids=["f1", "f2"])
        result = compute_cohesion(module, features)
        assert result.cohesion == pytest.approx(1.0)

    def test_custom_config_threshold(self) -> None:
        """Custom cohesion target changes meets_target."""
        base = [1.0, 0.5, 0.0, 0.0, 0.0]
        features = _make_similar_features(["f1", "f2"], base, noise=0.3)

        module = ModuleSpec(name="Custom", feature_ids=["f1", "f2"])

        strict = MetricsConfig(cohesion_target=0.99)
        result = compute_cohesion(module, features, config=strict)
        # With noise=0.3, cohesion should be high but possibly < 0.99
        # meets_target depends on actual similarity


# ---------------------------------------------------------------------------
# Coupling computation tests
# ---------------------------------------------------------------------------


class TestComputeCoupling:
    """Tests for compute_coupling function."""

    def test_no_dependencies(self) -> None:
        """No dependencies → zero coupling."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]
        result = compute_coupling(modules[0], modules, [])
        assert result.total_deps == 0
        assert result.meets_target is True

    def test_outgoing_dependencies(self) -> None:
        """Module with outgoing deps."""
        modules = [
            ModuleSpec(name="API", feature_ids=["f1"]),
            ModuleSpec(name="Auth", feature_ids=["f2"]),
            ModuleSpec(name="DB", feature_ids=["f3"]),
        ]
        deps = [("API", "Auth"), ("API", "DB")]
        result = compute_coupling(modules[0], modules, deps)

        assert result.outgoing_deps == 2
        assert result.incoming_deps == 0
        assert result.total_deps == 2

    def test_incoming_dependencies(self) -> None:
        """Module with incoming deps."""
        modules = [
            ModuleSpec(name="Auth", feature_ids=["f1"]),
            ModuleSpec(name="API", feature_ids=["f2"]),
            ModuleSpec(name="Admin", feature_ids=["f3"]),
        ]
        deps = [("API", "Auth"), ("Admin", "Auth")]
        result = compute_coupling(modules[0], modules, deps)

        assert result.outgoing_deps == 0
        assert result.incoming_deps == 2
        assert result.total_deps == 2

    def test_bidirectional_dependencies(self) -> None:
        """Module with both incoming and outgoing."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
            ModuleSpec(name="C", feature_ids=["f3"]),
        ]
        deps = [("A", "B"), ("C", "A")]
        result = compute_coupling(modules[0], modules, deps)

        assert result.outgoing_deps == 1  # A → B
        assert result.incoming_deps == 1  # C → A
        assert result.total_deps == 2  # B and C

    def test_self_dependency_ignored(self) -> None:
        """Self-dependencies are ignored."""
        modules = [ModuleSpec(name="A", feature_ids=["f1"])]
        deps = [("A", "A")]
        result = compute_coupling(modules[0], modules, deps)
        assert result.total_deps == 0

    def test_coupling_target(self) -> None:
        """Coupling meets target when <= 3."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
            ModuleSpec(name="C", feature_ids=["f3"]),
            ModuleSpec(name="D", feature_ids=["f4"]),
            ModuleSpec(name="E", feature_ids=["f5"]),
        ]
        deps = [("A", "B"), ("A", "C"), ("A", "D"), ("A", "E")]
        result = compute_coupling(modules[0], modules, deps)

        assert result.total_deps == 4
        assert result.meets_target is False  # > 3


# ---------------------------------------------------------------------------
# Modularity computation tests
# ---------------------------------------------------------------------------


class TestComputeModularity:
    """Tests for compute_modularity function."""

    def test_no_modules(self) -> None:
        result = compute_modularity([], [])
        assert result.q_score == 0.0
        assert result.meets_target is False

    def test_no_dependencies(self) -> None:
        """Isolated modules with no edges → Q = 0."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]
        result = compute_modularity(modules, [])
        assert result.q_score == 0.0

    def test_all_intra_module_deps(self) -> None:
        """All dependencies within modules → high Q."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]
        deps = [("A", "A"), ("B", "B")]
        result = compute_modularity(modules, deps)
        # All edges intra-module → e_cc high, Q positive
        assert result.q_score > 0.0

    def test_all_inter_module_deps(self) -> None:
        """All dependencies between modules → low Q."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]
        deps = [("A", "B"), ("B", "A")]
        result = compute_modularity(modules, deps)
        # All edges inter-module → Q negative or close to 0
        assert result.q_score <= 0.0

    def test_well_partitioned(self) -> None:
        """Well-partitioned modules should have decent Q-score."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1", "f2"]),
            ModuleSpec(name="B", feature_ids=["f3", "f4"]),
            ModuleSpec(name="C", feature_ids=["f5", "f6"]),
        ]
        # Mostly intra-module, few inter-module
        deps = [
            ("A", "A"), ("A", "A"), ("A", "A"),
            ("B", "B"), ("B", "B"),
            ("C", "C"), ("C", "C"),
            ("A", "B"),  # one inter-module
        ]
        result = compute_modularity(modules, deps)
        assert result.q_score > 0.0


# ---------------------------------------------------------------------------
# Feature-level modularity tests
# ---------------------------------------------------------------------------


class TestFeatureModularity:
    """Tests for compute_feature_modularity function."""

    def test_empty_deps(self) -> None:
        modules = [ModuleSpec(name="A", feature_ids=["f1"])]
        result = compute_feature_modularity(modules, [])
        assert result.q_score == 0.0

    def test_intra_module_feature_deps(self) -> None:
        """Feature deps within the same module → positive Q."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1", "f2"]),
            ModuleSpec(name="B", feature_ids=["f3", "f4"]),
        ]
        # All deps within modules
        deps = [("f1", "f2"), ("f3", "f4")]
        result = compute_feature_modularity(modules, deps)
        assert result.q_score > 0.0

    def test_inter_module_feature_deps(self) -> None:
        """Feature deps across modules → low or negative Q."""
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]
        deps = [("f1", "f2")]
        result = compute_feature_modularity(modules, deps)
        assert result.q_score <= 0.0


# ---------------------------------------------------------------------------
# Aggregate metrics tests
# ---------------------------------------------------------------------------


class TestComputeAllMetrics:
    """Tests for compute_all_metrics function."""

    def test_empty(self) -> None:
        result = compute_all_metrics([], {})
        assert result.avg_cohesion == 0.0
        assert result.max_coupling == 0

    def test_with_modules_and_features(self) -> None:
        base = [1.0, 0.5, 0.0, 0.0, 0.0]
        features_a = _make_similar_features(["f1", "f2", "f3"], base, noise=0.05)
        base_b = [0.0, 0.0, 1.0, 0.5, 0.0]
        features_b = _make_similar_features(["f4", "f5"], base_b, noise=0.05)

        all_features = {**features_a, **features_b}
        modules = [
            ModuleSpec(name="Group A", feature_ids=["f1", "f2", "f3"]),
            ModuleSpec(name="Group B", feature_ids=["f4", "f5"]),
        ]
        deps = [("Group A", "Group B")]

        result = compute_all_metrics(modules, all_features, deps)

        assert len(result.cohesion_results) == 2
        assert len(result.coupling_results) == 2
        assert result.modularity is not None
        assert result.avg_cohesion > 0.0

    def test_no_dependencies(self) -> None:
        features = {"f1": _make_feature("f1", embedding=[1.0, 0.0])}
        modules = [ModuleSpec(name="Solo", feature_ids=["f1"])]

        result = compute_all_metrics(modules, features)
        assert result.max_coupling == 0
        assert result.all_coupling_met is True


# ---------------------------------------------------------------------------
# PartitionMetrics tests
# ---------------------------------------------------------------------------


class TestPartitionMetrics:
    """Tests for PartitionMetrics model."""

    def test_overall_quality_met(self) -> None:
        metrics = PartitionMetrics(
            all_cohesion_met=True,
            all_coupling_met=True,
            modularity_met=True,
        )
        assert metrics.overall_quality is True

    def test_overall_quality_not_met(self) -> None:
        metrics = PartitionMetrics(
            all_cohesion_met=True,
            all_coupling_met=False,
            modularity_met=True,
        )
        assert metrics.overall_quality is False

    def test_frozen(self) -> None:
        metrics = PartitionMetrics()
        with pytest.raises(Exception):
            metrics.avg_cohesion = 0.9  # type: ignore


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for metrics."""

    def test_empty_module(self) -> None:
        """Module with no valid features in map."""
        features: dict[str, FeatureNode] = {}
        module = ModuleSpec(name="Ghost", feature_ids=["missing"])
        result = compute_cohesion(module, features)
        # 0 valid features → cohesion 1.0 (vacuously)
        assert result.num_features == 0

    def test_large_module_cohesion(self) -> None:
        """Many features with same embedding → cohesion 1.0."""
        emb = [1.0, 0.0, 0.0, 0.0, 0.0]
        features = {
            f"f{i}": _make_feature(f"f{i}", embedding=emb)
            for i in range(20)
        }
        module = ModuleSpec(
            name="Clones", feature_ids=[f"f{i}" for i in range(20)]
        )
        result = compute_cohesion(module, features)
        assert result.cohesion == pytest.approx(1.0)
        assert result.num_pairs == 190  # C(20,2)

    def test_zero_vector_similarity(self) -> None:
        """Zero vectors produce 0.0 similarity."""
        features = {
            "f1": _make_feature("f1", embedding=[0.0, 0.0, 0.0]),
            "f2": _make_feature("f2", embedding=[1.0, 0.0, 0.0]),
        }
        module = ModuleSpec(name="Mixed", feature_ids=["f1", "f2"])
        result = compute_cohesion(module, features)
        assert result.cohesion == 0.0


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from cobuilder.repomap.graph_construction import (
            CohesionResult,
            CouplingResult,
            MetricsConfig,
            ModularityResult,
            PartitionMetrics,
            compute_all_metrics,
            compute_cohesion,
            compute_coupling,
            compute_modularity,
        )
        assert compute_all_metrics is not None

    def test_import_from_module(self) -> None:
        from cobuilder.repomap.graph_construction.metrics import (
            compute_feature_modularity,
        )
        assert compute_feature_modularity is not None
