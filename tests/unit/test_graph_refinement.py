"""Tests for Iterative Graph Refinement (Task 2.3.5).

Tests cover:
- RefinementConfig validation and defaults
- ActionType enum
- RefinementAction model
- RefinementHistory model, add/pop/summary
- RefinementResult model
- GraphRefinement.move_feature() with validation
- GraphRefinement.merge_modules() with dependency updates
- GraphRefinement.split_module() with clustering and round-robin
- GraphRefinement.undo() restoring state
- LLM suggestions integration
- Metrics recomputation after edits
- Edge cases: empty modules, self-merge, invalid feature
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from zerorepo.llm.models import ModelTier
from zerorepo.ontology.models import FeatureNode
from zerorepo.graph_construction.dependencies import DependencyEdge
from zerorepo.graph_construction.metrics import (
    MetricsConfig,
    PartitionMetrics,
)
from zerorepo.graph_construction.partitioner import ModuleSpec
from zerorepo.graph_construction.refinement import (
    ActionType,
    GraphRefinement,
    RefinementAction,
    RefinementConfig,
    RefinementHistory,
    RefinementResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    fid: str,
    name: str = "",
    tags: list[str] | None = None,
    embedding: list[float] | None = None,
) -> FeatureNode:
    return FeatureNode(
        id=fid,
        name=name or fid,
        level=1,
        tags=tags or [],
        embedding=embedding,
    )


def _make_modules() -> list[ModuleSpec]:
    """Create 3 sample modules."""
    return [
        ModuleSpec(
            name="Auth",
            description="Authentication module",
            feature_ids=["auth.login", "auth.register", "auth.jwt"],
            public_interface=["auth.login"],
            rationale="Auth features",
        ),
        ModuleSpec(
            name="API",
            description="REST API endpoints",
            feature_ids=["api.users", "api.products", "api.orders"],
            public_interface=["api.users"],
            rationale="API features",
        ),
        ModuleSpec(
            name="Database",
            description="Data storage",
            feature_ids=["db.users", "db.products"],
            public_interface=["db.users"],
            rationale="DB features",
        ),
    ]


def _make_dependencies() -> list[DependencyEdge]:
    """Create sample dependencies."""
    return [
        DependencyEdge(
            source="API", target="Auth",
            dependency_type="uses", weight=0.9,
            rationale="API requires auth",
        ),
        DependencyEdge(
            source="API", target="Database",
            dependency_type="data_flow", weight=0.85,
            rationale="API reads/writes DB",
        ),
        DependencyEdge(
            source="Auth", target="Database",
            dependency_type="data_flow", weight=0.7,
            rationale="Auth stores credentials",
        ),
    ]


def _make_feature_map() -> dict[str, FeatureNode]:
    """Create a feature map with embeddings."""
    rng = np.random.RandomState(42)
    features = {}
    for fid in [
        "auth.login", "auth.register", "auth.jwt",
        "api.users", "api.products", "api.orders",
        "db.users", "db.products",
    ]:
        emb = rng.randn(10).tolist()
        features[fid] = _make_feature(fid, embedding=emb)
    return features


def _make_refiner(
    llm: Any = None,
    config: RefinementConfig | None = None,
) -> GraphRefinement:
    """Create a GraphRefinement instance."""
    return GraphRefinement(
        modules=_make_modules(),
        dependencies=_make_dependencies(),
        feature_map=_make_feature_map(),
        llm_gateway=llm,
        config=config,
    )


# ---------------------------------------------------------------------------
# RefinementConfig tests
# ---------------------------------------------------------------------------


class TestRefinementConfig:
    """Tests for RefinementConfig."""

    def test_defaults(self) -> None:
        cfg = RefinementConfig()
        assert cfg.enable_llm_suggestions is True
        assert cfg.llm_tier == ModelTier.MEDIUM
        assert cfg.recompute_metrics is True
        assert cfg.min_module_size == 1
        assert cfg.max_history_size == 100

    def test_custom(self) -> None:
        cfg = RefinementConfig(
            enable_llm_suggestions=False,
            min_module_size=3,
            max_history_size=50,
        )
        assert cfg.enable_llm_suggestions is False
        assert cfg.min_module_size == 3
        assert cfg.max_history_size == 50

    def test_metrics_config(self) -> None:
        cfg = RefinementConfig(
            metrics_config=MetricsConfig(cohesion_target=0.8)
        )
        assert cfg.metrics_config.cohesion_target == 0.8


# ---------------------------------------------------------------------------
# ActionType tests
# ---------------------------------------------------------------------------


class TestActionType:
    """Tests for ActionType enum."""

    def test_values(self) -> None:
        assert ActionType.MOVE_FEATURE == "move_feature"
        assert ActionType.MERGE_MODULES == "merge_modules"
        assert ActionType.SPLIT_MODULE == "split_module"

    def test_from_string(self) -> None:
        assert ActionType("move_feature") == ActionType.MOVE_FEATURE


# ---------------------------------------------------------------------------
# RefinementAction tests
# ---------------------------------------------------------------------------


class TestRefinementAction:
    """Tests for RefinementAction model."""

    def test_create(self) -> None:
        action = RefinementAction(
            action_type=ActionType.MOVE_FEATURE,
            params={"feature_id": "f1", "from": "A", "to": "B"},
        )
        assert action.action_type == ActionType.MOVE_FEATURE
        assert action.params["feature_id"] == "f1"
        assert action.timestamp  # Should auto-generate

    def test_frozen(self) -> None:
        action = RefinementAction(
            action_type=ActionType.MOVE_FEATURE
        )
        with pytest.raises(Exception):
            action.action_type = ActionType.MERGE_MODULES  # type: ignore


# ---------------------------------------------------------------------------
# RefinementHistory tests
# ---------------------------------------------------------------------------


class TestRefinementHistory:
    """Tests for RefinementHistory model."""

    def test_empty(self) -> None:
        h = RefinementHistory()
        assert h.action_count == 0
        assert h.can_undo is False
        assert h.last_action is None

    def test_add_and_pop(self) -> None:
        h = RefinementHistory()
        action = RefinementAction(action_type=ActionType.MOVE_FEATURE)
        h.add(action)

        assert h.action_count == 1
        assert h.can_undo is True
        assert h.last_action is action

        popped = h.pop()
        assert popped is action
        assert h.action_count == 0

    def test_max_size(self) -> None:
        h = RefinementHistory(max_size=3)
        for i in range(5):
            h.add(
                RefinementAction(
                    action_type=ActionType.MOVE_FEATURE,
                    params={"step": i},
                )
            )
        assert h.action_count == 3
        # Oldest should be trimmed
        assert h.actions[0].params["step"] == 2

    def test_to_summary(self) -> None:
        h = RefinementHistory()
        h.add(RefinementAction(
            action_type=ActionType.MOVE_FEATURE,
            suggestion="Move related features",
        ))
        h.add(RefinementAction(
            action_type=ActionType.MERGE_MODULES,
        ))

        summary = h.to_summary()
        assert len(summary) == 2
        assert summary[0]["action"] == "move_feature"
        assert summary[0]["has_suggestion"] is True
        assert summary[1]["action"] == "merge_modules"
        assert summary[1]["has_suggestion"] is False


# ---------------------------------------------------------------------------
# RefinementResult tests
# ---------------------------------------------------------------------------


class TestRefinementResult:
    """Tests for RefinementResult model."""

    def test_success(self) -> None:
        r = RefinementResult(success=True, modules=[])
        assert r.success is True
        assert r.error == ""

    def test_failure(self) -> None:
        r = RefinementResult(success=False, error="Something went wrong")
        assert r.success is False
        assert r.error == "Something went wrong"

    def test_frozen(self) -> None:
        r = RefinementResult(success=True)
        with pytest.raises(Exception):
            r.success = False  # type: ignore


# ---------------------------------------------------------------------------
# GraphRefinement initialization tests
# ---------------------------------------------------------------------------


class TestGraphRefinementInit:
    """Tests for GraphRefinement initialization."""

    def test_basic(self) -> None:
        refiner = _make_refiner()
        assert len(refiner.modules) == 3
        assert len(refiner.dependencies) == 3
        assert refiner.module_names == {"Auth", "API", "Database"}

    def test_empty_modules(self) -> None:
        refiner = GraphRefinement(modules=[])
        assert len(refiner.modules) == 0

    def test_no_dependencies(self) -> None:
        refiner = GraphRefinement(modules=_make_modules())
        assert len(refiner.dependencies) == 0


# ---------------------------------------------------------------------------
# move_feature tests
# ---------------------------------------------------------------------------


class TestMoveFeature:
    """Tests for move_feature operation."""

    def test_basic_move(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.action is not None
        assert result.action.action_type == ActionType.MOVE_FEATURE

        # Verify the move
        auth = next(m for m in refiner.modules if m.name == "Auth")
        api = next(m for m in refiner.modules if m.name == "API")
        assert "auth.jwt" not in auth.feature_ids
        assert "auth.jwt" in api.feature_ids

    def test_move_updates_public_interface(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("auth.login", "Auth", "API")

        assert result.success is True
        auth = next(m for m in refiner.modules if m.name == "Auth")
        assert "auth.login" not in auth.public_interface

    def test_move_invalid_source(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("auth.jwt", "NonExistent", "API")

        assert result.success is False
        assert "not found" in result.error

    def test_move_invalid_destination(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("auth.jwt", "Auth", "NonExistent")

        assert result.success is False
        assert "not found" in result.error

    def test_move_same_module(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("auth.jwt", "Auth", "Auth")

        assert result.success is False
        assert "same" in result.error

    def test_move_feature_not_in_source(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("db.users", "Auth", "API")

        assert result.success is False
        assert "not in module" in result.error

    def test_move_recomputes_metrics(self) -> None:
        refiner = _make_refiner()
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.metrics_before is not None
        assert result.metrics_after is not None

    def test_move_no_metrics(self) -> None:
        cfg = RefinementConfig(recompute_metrics=False)
        refiner = _make_refiner(config=cfg)
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.metrics_before is None
        assert result.metrics_after is None

    def test_move_records_history(self) -> None:
        refiner = _make_refiner()
        refiner.move_feature("auth.jwt", "Auth", "API")

        assert refiner.history.action_count == 1
        assert refiner.history.last_action is not None
        assert refiner.history.last_action.action_type == ActionType.MOVE_FEATURE

    def test_move_with_min_module_size_warning(self) -> None:
        cfg = RefinementConfig(min_module_size=3)
        refiner = _make_refiner(config=cfg)
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert len(result.warnings) > 0
        assert "below minimum" in result.warnings[0]


# ---------------------------------------------------------------------------
# merge_modules tests
# ---------------------------------------------------------------------------


class TestMergeModules:
    """Tests for merge_modules operation."""

    def test_basic_merge(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("Auth", "Database")

        assert result.success is True
        assert len(refiner.modules) == 2  # 3 → 2

        merged = next(
            m for m in refiner.modules
            if "auth.login" in m.feature_ids
        )
        assert "db.users" in merged.feature_ids
        assert merged.feature_count == 5  # 3 + 2

    def test_merge_custom_name(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("Auth", "Database", merged_name="AuthDB")

        assert result.success is True
        names = refiner.module_names
        assert "AuthDB" in names
        assert "Auth" not in names
        assert "Database" not in names

    def test_merge_default_name(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("Auth", "Database")

        assert result.success is True
        assert "Auth+Database" in refiner.module_names

    def test_merge_updates_dependencies(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("Auth", "Database")

        assert result.success is True
        # Auth→Database was internal, should become self-loop and be removed
        dep_pairs = [(d.source, d.target) for d in refiner.dependencies]
        merged_name = "Auth+Database"
        # API→Auth and API→Database should become API→merged
        assert ("API", merged_name) in dep_pairs
        # No self-loops
        assert all(d.source != d.target for d in refiner.dependencies)

    def test_merge_deduplicates_deps(self) -> None:
        refiner = _make_refiner()
        # API→Auth and API→Database both become API→merged
        result = refiner.merge_modules("Auth", "Database")

        assert result.success is True
        api_deps = [
            d for d in refiner.dependencies if d.source == "API"
        ]
        # Should be deduplicated to 1
        assert len(api_deps) == 1

    def test_merge_invalid_module_a(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("NonExistent", "Auth")

        assert result.success is False
        assert "not found" in result.error

    def test_merge_invalid_module_b(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("Auth", "NonExistent")

        assert result.success is False
        assert "not found" in result.error

    def test_merge_same_module(self) -> None:
        refiner = _make_refiner()
        result = refiner.merge_modules("Auth", "Auth")

        assert result.success is False
        assert "itself" in result.error

    def test_merge_records_history(self) -> None:
        refiner = _make_refiner()
        refiner.merge_modules("Auth", "Database")

        assert refiner.history.action_count == 1
        assert refiner.history.last_action is not None
        assert refiner.history.last_action.action_type == ActionType.MERGE_MODULES


# ---------------------------------------------------------------------------
# split_module tests
# ---------------------------------------------------------------------------


class TestSplitModule:
    """Tests for split_module operation."""

    def test_basic_split(self) -> None:
        refiner = _make_refiner()
        result = refiner.split_module("Auth", num_parts=2)

        assert result.success is True
        assert "Auth" not in refiner.module_names

        # Should have new sub-modules
        auth_parts = [
            m for m in refiner.modules if m.name.startswith("Auth_part")
        ]
        assert len(auth_parts) == 2

        # All features preserved
        all_feats = []
        for p in auth_parts:
            all_feats.extend(p.feature_ids)
        assert set(all_feats) == {"auth.login", "auth.register", "auth.jwt"}

    def test_split_with_embeddings(self) -> None:
        """Split should use k-means when embeddings are available."""
        refiner = _make_refiner()
        result = refiner.split_module("Auth", num_parts=2)

        assert result.success is True
        # Verify split happened (details depend on clustering)
        auth_parts = [
            m for m in refiner.modules if m.name.startswith("Auth_part")
        ]
        assert len(auth_parts) >= 2

    def test_split_without_embeddings(self) -> None:
        """Split should use round-robin when no embeddings."""
        refiner = GraphRefinement(
            modules=_make_modules(),
            feature_map={},  # No embeddings
        )
        result = refiner.split_module("Auth", num_parts=2)

        assert result.success is True
        auth_parts = [
            m for m in refiner.modules if m.name.startswith("Auth_part")
        ]
        assert len(auth_parts) == 2

    def test_split_updates_dependencies(self) -> None:
        refiner = _make_refiner()
        result = refiner.split_module("Auth", num_parts=2)

        assert result.success is True
        # API→Auth should become API→Auth_part1 and API→Auth_part2
        dep_targets = {d.target for d in refiner.dependencies if d.source == "API"}
        auth_targets = {t for t in dep_targets if t.startswith("Auth_part")}
        assert len(auth_targets) >= 1

    def test_split_invalid_module(self) -> None:
        refiner = _make_refiner()
        result = refiner.split_module("NonExistent")

        assert result.success is False
        assert "not found" in result.error

    def test_split_too_few_parts(self) -> None:
        refiner = _make_refiner()
        result = refiner.split_module("Auth", num_parts=1)

        assert result.success is False
        assert "at least 2" in result.error

    def test_split_too_many_parts(self) -> None:
        refiner = _make_refiner()
        result = refiner.split_module("Database", num_parts=5)

        assert result.success is False
        assert "cannot split" in result.error

    def test_split_records_history(self) -> None:
        refiner = _make_refiner()
        refiner.split_module("Auth", num_parts=2)

        assert refiner.history.action_count == 1
        assert refiner.history.last_action is not None
        assert refiner.history.last_action.action_type == ActionType.SPLIT_MODULE


# ---------------------------------------------------------------------------
# Undo tests
# ---------------------------------------------------------------------------


class TestUndo:
    """Tests for undo operation."""

    def test_undo_move(self) -> None:
        refiner = _make_refiner()
        refiner.move_feature("auth.jwt", "Auth", "API")

        # Verify the move happened
        auth = next(m for m in refiner.modules if m.name == "Auth")
        assert "auth.jwt" not in auth.feature_ids

        # Undo
        result = refiner.undo()
        assert result.success is True

        # Verify restored
        auth = next(m for m in refiner.modules if m.name == "Auth")
        assert "auth.jwt" in auth.feature_ids

    def test_undo_merge(self) -> None:
        refiner = _make_refiner()
        refiner.merge_modules("Auth", "Database")
        assert len(refiner.modules) == 2

        result = refiner.undo()
        assert result.success is True
        assert len(refiner.modules) == 3
        assert "Auth" in refiner.module_names
        assert "Database" in refiner.module_names

    def test_undo_split(self) -> None:
        refiner = _make_refiner()
        refiner.split_module("Auth", num_parts=2)
        assert "Auth" not in refiner.module_names

        result = refiner.undo()
        assert result.success is True
        assert "Auth" in refiner.module_names

    def test_undo_restores_dependencies(self) -> None:
        refiner = _make_refiner()
        original_deps = len(refiner.dependencies)
        refiner.merge_modules("Auth", "Database")

        refiner.undo()
        assert len(refiner.dependencies) == original_deps

    def test_undo_empty_history(self) -> None:
        refiner = _make_refiner()
        result = refiner.undo()

        assert result.success is False
        assert "No actions" in result.error

    def test_multiple_undo(self) -> None:
        refiner = _make_refiner()
        refiner.move_feature("auth.jwt", "Auth", "API")
        refiner.move_feature("api.orders", "API", "Database")

        assert refiner.history.action_count == 2

        refiner.undo()
        assert refiner.history.action_count == 1

        refiner.undo()
        assert refiner.history.action_count == 0

        # Should be back to original state
        auth = next(m for m in refiner.modules if m.name == "Auth")
        assert "auth.jwt" in auth.feature_ids
        api = next(m for m in refiner.modules if m.name == "API")
        assert "api.orders" in api.feature_ids


# ---------------------------------------------------------------------------
# LLM suggestions tests
# ---------------------------------------------------------------------------


class TestLLMSuggestions:
    """Tests for LLM-based suggestions."""

    def test_suggestion_with_mock_llm(self) -> None:
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = (
            "Consider moving auth.register to the API module "
            "to improve cohesion."
        )

        refiner = _make_refiner(llm=llm)
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.suggestion != ""
        assert "cohesion" in result.suggestion.lower()
        llm.complete.assert_called_once()

    def test_no_suggestion_without_llm(self) -> None:
        refiner = _make_refiner(llm=None)
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.suggestion == ""

    def test_no_suggestion_when_disabled(self) -> None:
        llm = MagicMock()
        cfg = RefinementConfig(enable_llm_suggestions=False)
        refiner = _make_refiner(llm=llm, config=cfg)
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.suggestion == ""
        llm.complete.assert_not_called()

    def test_llm_error_graceful(self) -> None:
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.side_effect = RuntimeError("LLM down")

        refiner = _make_refiner(llm=llm)
        result = refiner.move_feature("auth.jwt", "Auth", "API")

        assert result.success is True
        assert result.suggestion == ""


# ---------------------------------------------------------------------------
# Utility method tests
# ---------------------------------------------------------------------------


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_metrics(self) -> None:
        refiner = _make_refiner()
        metrics = refiner.get_metrics()

        assert metrics is not None
        # avg_cohesion can be negative with random embeddings
        assert isinstance(metrics.avg_cohesion, float)

    def test_get_module_features(self) -> None:
        refiner = _make_refiner()
        features = refiner.get_module_features("Auth")

        assert "auth.login" in features
        assert "auth.jwt" in features

    def test_get_module_features_not_found(self) -> None:
        refiner = _make_refiner()
        features = refiner.get_module_features("NonExistent")

        assert features == []

    def test_get_history_summary(self) -> None:
        refiner = _make_refiner()
        refiner.move_feature("auth.jwt", "Auth", "API")
        refiner.merge_modules("Auth", "Database")

        summary = refiner.get_history_summary()
        assert len(summary) == 2
        assert summary[0]["action"] == "move_feature"
        assert summary[1]["action"] == "merge_modules"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests for chained operations."""

    def test_move_then_merge(self) -> None:
        refiner = _make_refiner()

        # Move a feature
        r1 = refiner.move_feature("auth.jwt", "Auth", "API")
        assert r1.success is True

        # Now merge
        r2 = refiner.merge_modules("Auth", "Database")
        assert r2.success is True

        # Should have 2 modules (API, Auth+Database)
        assert len(refiner.modules) == 2

        # JWT should be in API
        api = next(m for m in refiner.modules if m.name == "API")
        assert "auth.jwt" in api.feature_ids

    def test_split_then_merge(self) -> None:
        refiner = _make_refiner()

        # Split Auth
        r1 = refiner.split_module("Auth", num_parts=2)
        assert r1.success is True
        auth_parts = [
            m.name for m in refiner.modules if m.name.startswith("Auth_part")
        ]
        assert len(auth_parts) == 2

        # Merge the parts back
        r2 = refiner.merge_modules(auth_parts[0], auth_parts[1])
        assert r2.success is True

        # All auth features should be in the merged module
        merged = next(
            m for m in refiner.modules
            if "auth.login" in m.feature_ids
        )
        assert "auth.register" in merged.feature_ids
        assert "auth.jwt" in merged.feature_ids

    def test_full_undo_chain(self) -> None:
        refiner = _make_refiner()

        # Perform 3 operations
        refiner.move_feature("auth.jwt", "Auth", "API")
        refiner.merge_modules("Auth", "Database")
        refiner.split_module("API", num_parts=2)

        assert refiner.history.action_count == 3

        # Undo all 3
        for _ in range(3):
            result = refiner.undo()
            assert result.success is True

        # Should be back to original
        assert len(refiner.modules) == 3
        assert refiner.module_names == {"Auth", "API", "Database"}
        auth = next(m for m in refiner.modules if m.name == "Auth")
        assert "auth.jwt" in auth.feature_ids


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from zerorepo.graph_construction import (
            ActionType,
            GraphRefinement,
            RefinementAction,
            RefinementConfig,
            RefinementHistory,
            RefinementResult,
        )
        assert GraphRefinement is not None

    def test_import_from_module(self) -> None:
        from zerorepo.graph_construction.refinement import (
            ActionType,
            GraphRefinement,
            RefinementAction,
            RefinementConfig,
            RefinementHistory,
            RefinementResult,
        )
        assert RefinementResult is not None
