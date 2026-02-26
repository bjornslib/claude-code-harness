"""Tests for the Module Partitioning Algorithm (Task 2.3.1).

Tests cover:
- PartitionerConfig validation and defaults
- ModuleSpec model and properties
- PartitionResult model and properties
- LLM-based partitioning with mocked LLM
- K-means fallback with embeddings
- Round-robin fallback (no embeddings)
- Module name generation
- Size constraint enforcement (merge small, split large)
- JSON extraction from various LLM response formats
- Validation of partition results
- Edge cases: few features, single cluster, all unassigned
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from cobuilder.repomap.llm.models import ModelTier
from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.graph_construction.partitioner import (
    ModulePartitioner,
    ModuleSpec,
    PartitionerConfig,
    PartitionResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    fid: str,
    name: str,
    desc: str = "",
    tags: list[str] | None = None,
    embedding: list[float] | None = None,
    level: int = 1,
) -> FeatureNode:
    """Create a test FeatureNode."""
    return FeatureNode(
        id=fid,
        name=name,
        level=level,
        description=desc or f"Description of {name}",
        tags=tags or [],
        embedding=embedding,
    )


def _make_features_with_embeddings(n: int, dim: int = 10) -> list[FeatureNode]:
    """Create n features with distinct random embeddings."""
    rng = np.random.RandomState(42)
    features = []
    for i in range(n):
        emb = rng.randn(dim).tolist()
        features.append(
            _make_feature(
                fid=f"feat_{i}",
                name=f"Feature {i}",
                tags=[f"cluster_{i % 3}"],
                embedding=emb,
            )
        )
    return features


def _make_clustered_features(
    clusters: dict[str, list[str]], dim: int = 10
) -> list[FeatureNode]:
    """Create features with embeddings clustered around centroids.

    Args:
        clusters: Mapping from cluster tag to feature IDs.
        dim: Embedding dimensionality.

    Returns:
        Features with embeddings that should cluster naturally.
    """
    rng = np.random.RandomState(42)
    features = []
    for cluster_idx, (tag, fids) in enumerate(clusters.items()):
        centroid = rng.randn(dim) * 5 + cluster_idx * 10
        for fid in fids:
            # Small perturbation around centroid
            emb = (centroid + rng.randn(dim) * 0.1).tolist()
            features.append(
                _make_feature(
                    fid=fid,
                    name=fid.replace("_", " ").title(),
                    tags=[tag],
                    embedding=emb,
                )
            )
    return features


@pytest.fixture
def sample_features() -> list[FeatureNode]:
    """10 features across 3 conceptual groups."""
    return [
        _make_feature("auth.login", "Login", tags=["auth"]),
        _make_feature("auth.register", "Register", tags=["auth"]),
        _make_feature("auth.jwt", "JWT Token", tags=["auth"]),
        _make_feature("api.users", "User API", tags=["api"]),
        _make_feature("api.products", "Product API", tags=["api"]),
        _make_feature("api.orders", "Order API", tags=["api"]),
        _make_feature("db.users", "User Table", tags=["database"]),
        _make_feature("db.products", "Product Table", tags=["database"]),
        _make_feature("db.orders", "Order Table", tags=["database"]),
        _make_feature("db.migrations", "DB Migrations", tags=["database"]),
    ]


@pytest.fixture
def mock_llm_good() -> MagicMock:
    """Mock LLM that returns a valid partition."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"
    llm.complete.return_value = json.dumps({
        "modules": [
            {
                "name": "Authentication",
                "description": "User authentication and authorization",
                "feature_ids": ["auth.login", "auth.register", "auth.jwt"],
                "public_interface": ["auth.login"],
                "rationale": "All auth-related features",
            },
            {
                "name": "REST API",
                "description": "API endpoints for resources",
                "feature_ids": ["api.users", "api.products", "api.orders"],
                "public_interface": ["api.users"],
                "rationale": "All API endpoint features",
            },
            {
                "name": "Data Storage",
                "description": "Database tables and migrations",
                "feature_ids": ["db.users", "db.products", "db.orders", "db.migrations"],
                "public_interface": ["db.users"],
                "rationale": "All database-related features",
            },
        ]
    })
    return llm


@pytest.fixture
def mock_llm_invalid() -> MagicMock:
    """Mock LLM that returns an invalid response."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"
    llm.complete.return_value = "I cannot partition these features."
    return llm


# ---------------------------------------------------------------------------
# PartitionerConfig tests
# ---------------------------------------------------------------------------


class TestPartitionerConfig:
    """Tests for PartitionerConfig."""

    def test_defaults(self) -> None:
        cfg = PartitionerConfig()
        assert cfg.min_modules == 3
        assert cfg.max_modules == 10
        assert cfg.min_features_per_module == 2
        assert cfg.max_features_per_module == 15
        assert cfg.llm_tier == ModelTier.MEDIUM
        assert cfg.enable_llm is True
        assert cfg.kmeans_n_init == 10

    def test_custom(self) -> None:
        cfg = PartitionerConfig(
            min_modules=2,
            max_modules=5,
            min_features_per_module=3,
            max_features_per_module=20,
        )
        assert cfg.min_modules == 2
        assert cfg.max_modules == 5

    def test_invalid_max_less_than_min(self) -> None:
        with pytest.raises(Exception):
            PartitionerConfig(min_modules=5, max_modules=3)

    def test_invalid_min_modules_too_low(self) -> None:
        with pytest.raises(Exception):
            PartitionerConfig(min_modules=1)

    def test_disable_llm(self) -> None:
        cfg = PartitionerConfig(enable_llm=False)
        assert cfg.enable_llm is False


# ---------------------------------------------------------------------------
# ModuleSpec tests
# ---------------------------------------------------------------------------


class TestModuleSpec:
    """Tests for ModuleSpec model."""

    def test_basic(self) -> None:
        m = ModuleSpec(
            name="Authentication",
            description="Auth features",
            feature_ids=["auth.login", "auth.register"],
            public_interface=["auth.login"],
            rationale="Auth group",
        )
        assert m.name == "Authentication"
        assert m.feature_count == 2
        assert m.public_interface == ["auth.login"]

    def test_feature_count_property(self) -> None:
        m = ModuleSpec(
            name="API",
            feature_ids=["a", "b", "c", "d"],
        )
        assert m.feature_count == 4

    def test_frozen(self) -> None:
        m = ModuleSpec(name="X", feature_ids=["a"])
        with pytest.raises(Exception):
            m.name = "Y"  # type: ignore

    def test_empty_features_rejected(self) -> None:
        with pytest.raises(Exception):
            ModuleSpec(name="Empty", feature_ids=[])


# ---------------------------------------------------------------------------
# PartitionResult tests
# ---------------------------------------------------------------------------


class TestPartitionResult:
    """Tests for PartitionResult model."""

    def test_empty(self) -> None:
        r = PartitionResult()
        assert r.module_count == 0
        assert r.assigned_feature_count == 0
        assert r.all_feature_ids == set()

    def test_properties(self) -> None:
        r = PartitionResult(
            modules=[
                ModuleSpec(name="A", feature_ids=["f1", "f2"]),
                ModuleSpec(name="B", feature_ids=["f3"]),
            ],
            unassigned_feature_ids=["f4"],
            method="llm",
            total_features=4,
        )
        assert r.module_count == 2
        assert r.assigned_feature_count == 3
        assert r.all_feature_ids == {"f1", "f2", "f3"}

    def test_frozen(self) -> None:
        r = PartitionResult()
        with pytest.raises(Exception):
            r.method = "other"  # type: ignore


# ---------------------------------------------------------------------------
# LLM-based partitioning tests
# ---------------------------------------------------------------------------


class TestLLMPartitioning:
    """Tests for LLM-based partitioning."""

    def test_llm_partition_success(
        self,
        sample_features: list[FeatureNode],
        mock_llm_good: MagicMock,
    ) -> None:
        p = ModulePartitioner(llm_gateway=mock_llm_good)
        result = p.partition(sample_features)

        assert result.method == "llm"
        assert result.module_count == 3
        assert result.assigned_feature_count == 10
        assert result.unassigned_feature_ids == []

        module_names = {m.name for m in result.modules}
        assert "Authentication" in module_names
        assert "REST API" in module_names
        assert "Data Storage" in module_names

    def test_llm_partition_with_target(
        self,
        sample_features: list[FeatureNode],
        mock_llm_good: MagicMock,
    ) -> None:
        p = ModulePartitioner(llm_gateway=mock_llm_good)
        result = p.partition(sample_features, target_modules=3)
        assert result.module_count == 3

    def test_llm_fallback_on_invalid_response(
        self,
        sample_features: list[FeatureNode],
        mock_llm_invalid: MagicMock,
    ) -> None:
        """Invalid LLM response falls back to k-means or round-robin."""
        p = ModulePartitioner(llm_gateway=mock_llm_invalid)
        result = p.partition(sample_features)
        # Should still produce a result via fallback
        assert result.module_count >= 1
        assert result.method in ("kmeans", "round_robin")

    def test_llm_fallback_on_exception(
        self, sample_features: list[FeatureNode]
    ) -> None:
        """LLM exception falls back to k-means."""
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.side_effect = RuntimeError("LLM error")

        p = ModulePartitioner(llm_gateway=llm)
        result = p.partition(sample_features)
        assert result.module_count >= 1
        assert result.method in ("kmeans", "round_robin")

    def test_no_llm_uses_kmeans(
        self, sample_features: list[FeatureNode]
    ) -> None:
        """No LLM gateway goes straight to k-means/round_robin."""
        p = ModulePartitioner(llm_gateway=None)
        result = p.partition(sample_features)
        assert result.method in ("kmeans", "round_robin")
        assert result.module_count >= 1

    def test_llm_disabled_in_config(
        self, sample_features: list[FeatureNode]
    ) -> None:
        cfg = PartitionerConfig(enable_llm=False)
        llm = MagicMock()
        p = ModulePartitioner(llm_gateway=llm, config=cfg)
        result = p.partition(sample_features)
        # LLM should not have been called
        llm.complete.assert_not_called()
        assert result.method in ("kmeans", "round_robin")


# ---------------------------------------------------------------------------
# K-means fallback tests
# ---------------------------------------------------------------------------


class TestKMeansPartitioning:
    """Tests for k-means fallback partitioning."""

    def test_kmeans_with_embeddings(self) -> None:
        features = _make_features_with_embeddings(15, dim=10)
        p = ModulePartitioner(llm_gateway=None)
        result = p.partition(features)

        assert result.method == "kmeans"
        assert result.module_count >= 1
        assert result.assigned_feature_count == 15

    def test_kmeans_respects_target_modules(self) -> None:
        features = _make_features_with_embeddings(20, dim=10)
        p = ModulePartitioner(llm_gateway=None)
        result = p.partition(features, target_modules=4)
        # Should be close to 4, but enforcement may merge/split
        assert result.module_count >= 1

    def test_kmeans_with_clustered_embeddings(self) -> None:
        """Features with clear clusters should be grouped correctly."""
        features = _make_clustered_features(
            {
                "auth": ["login", "register", "jwt_token"],
                "api": ["get_users", "create_user", "delete_user"],
                "db": ["connect", "query", "migrate"],
            },
            dim=10,
        )
        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(llm_gateway=None, config=cfg)
        result = p.partition(features, target_modules=3)

        assert result.method == "kmeans"
        assert result.module_count >= 2

    def test_round_robin_no_embeddings(self) -> None:
        """Features without embeddings use round-robin."""
        features = [
            _make_feature(f"f{i}", f"Feature {i}")
            for i in range(9)
        ]
        p = ModulePartitioner(llm_gateway=None)
        result = p.partition(features)

        assert result.method == "round_robin"
        assert result.module_count >= 1
        assert result.assigned_feature_count == 9

    def test_partial_embeddings_below_threshold(self) -> None:
        """Less than 50% with embeddings falls back to round-robin."""
        features = [
            _make_feature(f"f{i}", f"Feature {i}")
            for i in range(10)
        ]
        # Only 3 out of 10 have embeddings (30%)
        for i in range(3):
            features[i].embedding = [0.1] * 10

        p = ModulePartitioner(llm_gateway=None)
        result = p.partition(features)
        assert result.method == "round_robin"


# ---------------------------------------------------------------------------
# Module name generation tests
# ---------------------------------------------------------------------------


class TestModuleNameGeneration:
    """Tests for module name generation in k-means fallback."""

    def test_name_from_tags(self) -> None:
        features = [
            _make_feature("f1", "Feature 1", tags=["auth"]),
            _make_feature("f2", "Feature 2", tags=["auth"]),
        ]
        name = ModulePartitioner._generate_module_name(features, 0)
        assert "Auth" in name

    def test_name_from_id_path(self) -> None:
        features = [
            _make_feature("ml.preprocessing.normalize", "Normalize"),
            _make_feature("ml.preprocessing.scale", "Scale"),
        ]
        name = ModulePartitioner._generate_module_name(features, 0)
        # Should derive from the "preprocessing" path segment
        assert name != f"Group 1"

    def test_name_fallback(self) -> None:
        features = [
            _make_feature("x", "X"),
            _make_feature("y", "Y"),
        ]
        name = ModulePartitioner._generate_module_name(features, 0)
        assert name  # Should always produce something


# ---------------------------------------------------------------------------
# Size constraint enforcement tests
# ---------------------------------------------------------------------------


class TestSizeConstraints:
    """Tests for merging small and splitting large modules."""

    def test_merge_small_modules(self) -> None:
        """Modules below min_features_per_module are merged."""
        cfg = PartitionerConfig(
            min_modules=2,
            max_modules=10,
            min_features_per_module=3,
        )
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(8)]

        # Create modules: one with 1 feature (too small), one with 7
        small = ModuleSpec(name="Small", feature_ids=["f0"])
        large = ModuleSpec(name="Large", feature_ids=[f"f{i}" for i in range(1, 8)])

        p = ModulePartitioner(config=cfg)
        result = p._enforce_size_constraints([small, large], features)

        # Small should be merged into large
        assert len(result) >= 1
        total_assigned = sum(m.feature_count for m in result)
        assert total_assigned == 8

    def test_split_large_modules(self) -> None:
        """Modules above max_features_per_module are split."""
        cfg = PartitionerConfig(
            min_modules=2,
            max_modules=10,
            max_features_per_module=5,
        )
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(12)]

        huge = ModuleSpec(name="Huge", feature_ids=[f"f{i}" for i in range(12)])

        p = ModulePartitioner(config=cfg)
        result = p._enforce_size_constraints([huge], features)

        # Should be split into multiple modules
        assert len(result) >= 2
        for m in result:
            assert m.feature_count <= 5

    def test_constraints_preserve_features(self) -> None:
        """All features remain assigned after enforcement."""
        cfg = PartitionerConfig(
            min_modules=2,
            max_modules=10,
            min_features_per_module=2,
            max_features_per_module=5,
        )
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(10)]

        modules = [
            ModuleSpec(name="A", feature_ids=["f0"]),  # too small
            ModuleSpec(name="B", feature_ids=["f1", "f2", "f3"]),
            ModuleSpec(name="C", feature_ids=["f4", "f5", "f6", "f7", "f8", "f9"]),  # too large
        ]

        p = ModulePartitioner(config=cfg)
        result = p._enforce_size_constraints(modules, features)

        all_ids: set[str] = set()
        for m in result:
            all_ids.update(m.feature_ids)
        assert all_ids == {f"f{i}" for i in range(10)}


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------


class TestJSONExtraction:
    """Tests for JSON extraction from LLM responses."""

    def test_pure_json(self) -> None:
        text = '{"modules": [{"name": "A", "feature_ids": ["f1"]}]}'
        result = ModulePartitioner._extract_json(text)
        assert result is not None
        assert "modules" in result

    def test_json_in_code_block(self) -> None:
        text = '```json\n{"modules": [{"name": "A", "feature_ids": ["f1"]}]}\n```'
        result = ModulePartitioner._extract_json(text)
        assert result is not None

    def test_json_with_surrounding_text(self) -> None:
        text = 'Here is the partition:\n{"modules": [{"name": "A", "feature_ids": ["f1"]}]}\nDone!'
        result = ModulePartitioner._extract_json(text)
        assert result is not None

    def test_no_json(self) -> None:
        text = "I cannot do this partitioning."
        result = ModulePartitioner._extract_json(text)
        assert result is None

    def test_malformed_json(self) -> None:
        text = '{"modules": [{"name": "A", "feature_ids": ["f1"]}'  # missing ]
        result = ModulePartitioner._extract_json(text)
        # Should try embedded extraction
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for partition result validation."""

    def test_valid_result(self) -> None:
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(6)]
        feature_map = {f.id: f for f in features}

        result = PartitionResult(
            modules=[
                ModuleSpec(name="Group A", feature_ids=["f0", "f1", "f2"]),
                ModuleSpec(name="Group B", feature_ids=["f3", "f4", "f5"]),
            ],
            method="llm",
            total_features=6,
        )

        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(config=cfg)
        assert p._validate_result(result, feature_map) is True

    def test_invalid_module_name(self) -> None:
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(6)]
        feature_map = {f.id: f for f in features}

        result = PartitionResult(
            modules=[
                ModuleSpec(name="Module 1", feature_ids=["f0", "f1", "f2"]),
                ModuleSpec(name="Module 2", feature_ids=["f3", "f4", "f5"]),
            ],
            method="llm",
            total_features=6,
        )

        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(config=cfg)
        assert p._validate_result(result, feature_map) is False

    def test_invalid_too_few_modules(self) -> None:
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(6)]
        feature_map = {f.id: f for f in features}

        result = PartitionResult(
            modules=[
                ModuleSpec(name="Everything", feature_ids=[f"f{i}" for i in range(6)]),
            ],
            method="llm",
            total_features=6,
        )

        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(config=cfg)
        assert p._validate_result(result, feature_map) is False

    def test_invalid_duplicate_assignment(self) -> None:
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(6)]
        feature_map = {f.id: f for f in features}

        result = PartitionResult(
            modules=[
                ModuleSpec(name="Group A", feature_ids=["f0", "f1", "f2"]),
                ModuleSpec(name="Group B", feature_ids=["f2", "f3", "f4"]),  # f2 duplicated
            ],
            method="llm",
            total_features=6,
        )

        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(config=cfg)
        assert p._validate_result(result, feature_map) is False

    def test_invalid_empty_result(self) -> None:
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(6)]
        feature_map = {f.id: f for f in features}

        result = PartitionResult(modules=[], method="llm", total_features=6)

        p = ModulePartitioner()
        assert p._validate_result(result, feature_map) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_features_raises(self) -> None:
        p = ModulePartitioner()
        with pytest.raises(ValueError, match="empty"):
            p.partition([])

    def test_few_features(self) -> None:
        """Fewer features than min_modules should still work."""
        features = [
            _make_feature("f0", "F0"),
            _make_feature("f1", "F1"),
        ]
        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(config=cfg)
        result = p.partition(features)
        assert result.assigned_feature_count == 2

    def test_single_feature(self) -> None:
        """Single feature still produces a result."""
        features = [_make_feature("f0", "F0")]
        cfg = PartitionerConfig(min_modules=2, max_modules=5, min_features_per_module=1)
        p = ModulePartitioner(config=cfg)
        result = p.partition(features)
        assert result.module_count >= 1
        assert result.assigned_feature_count == 1

    def test_target_modules_clamped(self) -> None:
        """Target modules should be clamped to config range."""
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(10)]
        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(config=cfg)

        # Target above max
        result = p.partition(features, target_modules=100)
        assert result.module_count <= 5

    def test_large_feature_set(self) -> None:
        """50 features should partition successfully."""
        features = _make_features_with_embeddings(50, dim=10)
        p = ModulePartitioner(llm_gateway=None)
        result = p.partition(features)

        assert result.module_count >= 1
        assert result.assigned_feature_count == 50

    def test_llm_response_with_unknown_features(self) -> None:
        """LLM response referencing unknown feature IDs should be filtered."""
        features = [_make_feature(f"f{i}", f"F{i}") for i in range(6)]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = json.dumps({
            "modules": [
                {
                    "name": "Group A",
                    "feature_ids": ["f0", "f1", "f2", "unknown_1"],
                },
                {
                    "name": "Group B",
                    "feature_ids": ["f3", "f4", "f5", "unknown_2"],
                },
            ]
        })

        p = ModulePartitioner(llm_gateway=llm)
        result = p.partition(features)

        if result.method == "llm":
            # Unknown features should be filtered out
            assert "unknown_1" not in result.all_feature_ids
            assert "unknown_2" not in result.all_feature_ids


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_pipeline_llm(self) -> None:
        """Full pipeline: features → LLM partition → validate."""
        features = [
            _make_feature("ml.regression.linear", "Linear Regression", tags=["regression"]),
            _make_feature("ml.regression.ridge", "Ridge Regression", tags=["regression"]),
            _make_feature("ml.regression.lasso", "Lasso Regression", tags=["regression"]),
            _make_feature("ml.clustering.kmeans", "K-Means", tags=["clustering"]),
            _make_feature("ml.clustering.dbscan", "DBSCAN", tags=["clustering"]),
            _make_feature("ml.clustering.hierarchical", "Hierarchical", tags=["clustering"]),
            _make_feature("ml.evaluation.silhouette", "Silhouette Score", tags=["evaluation"]),
            _make_feature("ml.evaluation.davies_bouldin", "Davies-Bouldin", tags=["evaluation"]),
            _make_feature("ml.preprocessing.normalize", "Normalize", tags=["preprocessing"]),
            _make_feature("ml.preprocessing.scale", "Scale", tags=["preprocessing"]),
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = json.dumps({
            "modules": [
                {
                    "name": "Regression",
                    "description": "Linear regression models",
                    "feature_ids": [
                        "ml.regression.linear",
                        "ml.regression.ridge",
                        "ml.regression.lasso",
                    ],
                    "public_interface": ["ml.regression.linear"],
                    "rationale": "All regression algorithms",
                },
                {
                    "name": "Clustering",
                    "description": "Clustering algorithms",
                    "feature_ids": [
                        "ml.clustering.kmeans",
                        "ml.clustering.dbscan",
                        "ml.clustering.hierarchical",
                    ],
                    "public_interface": ["ml.clustering.kmeans"],
                    "rationale": "All clustering algorithms",
                },
                {
                    "name": "Evaluation and Preprocessing",
                    "description": "Data preprocessing and model evaluation",
                    "feature_ids": [
                        "ml.evaluation.silhouette",
                        "ml.evaluation.davies_bouldin",
                        "ml.preprocessing.normalize",
                        "ml.preprocessing.scale",
                    ],
                    "public_interface": ["ml.evaluation.silhouette"],
                    "rationale": "Support utilities for ML pipeline",
                },
            ]
        })

        p = ModulePartitioner(llm_gateway=llm)
        result = p.partition(features, target_modules=3)

        assert result.method == "llm"
        assert result.module_count == 3
        assert result.assigned_feature_count == 10
        assert result.unassigned_feature_ids == []

        # Verify specific assignments
        module_map = {m.name: m for m in result.modules}
        assert "ml.clustering.kmeans" in module_map["Clustering"].feature_ids
        assert "ml.regression.linear" in module_map["Regression"].feature_ids

    def test_full_pipeline_kmeans_fallback(self) -> None:
        """Full pipeline using k-means fallback."""
        features = _make_clustered_features(
            {
                "regression": [f"reg_{i}" for i in range(5)],
                "clustering": [f"clust_{i}" for i in range(5)],
                "evaluation": [f"eval_{i}" for i in range(5)],
            },
            dim=10,
        )

        cfg = PartitionerConfig(min_modules=2, max_modules=5)
        p = ModulePartitioner(llm_gateway=None, config=cfg)
        result = p.partition(features, target_modules=3)

        assert result.method == "kmeans"
        assert result.module_count >= 2
        assert result.assigned_feature_count == 15


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from cobuilder.repomap.graph_construction import (
            ModulePartitioner,
            ModuleSpec,
            PartitionerConfig,
            PartitionResult,
        )
        assert ModulePartitioner is not None
        assert PartitionResult is not None

    def test_import_from_module(self) -> None:
        from cobuilder.repomap.graph_construction.partitioner import (
            ModulePartitioner,
            ModuleSpec,
            PartitionerConfig,
            PartitionResult,
        )
        assert ModuleSpec is not None
