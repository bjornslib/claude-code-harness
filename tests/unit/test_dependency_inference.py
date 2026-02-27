"""Tests for Dependency Inference (Task 2.3.3).

Tests cover:
- DependencyConfig validation and defaults
- DependencyEdge model and properties
- DependencyResult model, properties, and build_graph
- LLM-based inference with mocked LLM
- Heuristic fallback inference
- Cycle detection and resolution
- Max dependencies enforcement
- Self-loop filtering
- JSON extraction from LLM responses
- Edge cases: single module, empty modules, all filtered
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import networkx as nx
import pytest

from cobuilder.repomap.llm.models import ModelTier
from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.graph_construction.partitioner import ModuleSpec
from cobuilder.repomap.graph_construction.dependencies import (
    DependencyConfig,
    DependencyEdge,
    DependencyInference,
    DependencyResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(
    fid: str, name: str = "", tags: list[str] | None = None
) -> FeatureNode:
    return FeatureNode(
        id=fid, name=name or fid, level=1, tags=tags or []
    )


@pytest.fixture
def sample_modules() -> list[ModuleSpec]:
    return [
        ModuleSpec(
            name="Authentication",
            description="User auth and authorization",
            feature_ids=["auth.login", "auth.register", "auth.jwt"],
        ),
        ModuleSpec(
            name="REST API",
            description="API endpoints",
            feature_ids=["api.users", "api.products"],
        ),
        ModuleSpec(
            name="Database",
            description="Data storage layer",
            feature_ids=["db.users", "db.products"],
        ),
    ]


@pytest.fixture
def sample_feature_map() -> dict[str, FeatureNode]:
    return {
        "auth.login": _make_feature("auth.login", tags=["auth"]),
        "auth.register": _make_feature("auth.register", tags=["auth"]),
        "auth.jwt": _make_feature("auth.jwt", tags=["auth", "security"]),
        "api.users": _make_feature("api.users", tags=["api"]),
        "api.products": _make_feature("api.products", tags=["api"]),
        "db.users": _make_feature("db.users", tags=["database"]),
        "db.products": _make_feature("db.products", tags=["database"]),
    }


@pytest.fixture
def mock_llm_deps() -> MagicMock:
    """Mock LLM that returns valid dependencies."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"
    llm.complete.return_value = json.dumps({
        "dependencies": [
            {
                "source": "REST API",
                "target": "Authentication",
                "dependency_type": "uses",
                "weight": 0.9,
                "confidence": 0.95,
                "rationale": "API endpoints require authentication",
            },
            {
                "source": "REST API",
                "target": "Database",
                "dependency_type": "data_flow",
                "weight": 0.85,
                "confidence": 0.9,
                "rationale": "API reads/writes to database",
            },
            {
                "source": "Authentication",
                "target": "Database",
                "dependency_type": "data_flow",
                "weight": 0.7,
                "confidence": 0.85,
                "rationale": "Auth stores user credentials",
            },
        ]
    })
    return llm


@pytest.fixture
def mock_llm_cyclic() -> MagicMock:
    """Mock LLM that returns cyclic dependencies."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"
    llm.complete.return_value = json.dumps({
        "dependencies": [
            {"source": "REST API", "target": "Authentication", "weight": 0.9, "confidence": 0.9},
            {"source": "Authentication", "target": "Database", "weight": 0.8, "confidence": 0.85},
            {"source": "Database", "target": "REST API", "weight": 0.3, "confidence": 0.6},  # Creates cycle
        ]
    })
    return llm


# ---------------------------------------------------------------------------
# DependencyConfig tests
# ---------------------------------------------------------------------------


class TestDependencyConfig:
    """Tests for DependencyConfig."""

    def test_defaults(self) -> None:
        cfg = DependencyConfig()
        assert cfg.llm_tier == ModelTier.MEDIUM
        assert cfg.enable_llm is True
        assert cfg.enable_cycle_resolution is True
        assert cfg.max_deps_per_module == 5
        assert cfg.min_confidence == 0.5

    def test_custom(self) -> None:
        cfg = DependencyConfig(
            llm_tier=ModelTier.STRONG,
            max_deps_per_module=3,
            min_confidence=0.7,
        )
        assert cfg.max_deps_per_module == 3

    def test_disable_cycle_resolution(self) -> None:
        cfg = DependencyConfig(enable_cycle_resolution=False)
        assert cfg.enable_cycle_resolution is False


# ---------------------------------------------------------------------------
# DependencyEdge tests
# ---------------------------------------------------------------------------


class TestDependencyEdge:
    """Tests for DependencyEdge model."""

    def test_basic(self) -> None:
        e = DependencyEdge(
            source="API",
            target="Auth",
            dependency_type="uses",
            weight=0.9,
            confidence=0.95,
            rationale="API uses auth",
        )
        assert e.source == "API"
        assert e.target == "Auth"

    def test_frozen(self) -> None:
        e = DependencyEdge(source="A", target="B")
        with pytest.raises(Exception):
            e.source = "C"  # type: ignore

    def test_defaults(self) -> None:
        e = DependencyEdge(source="A", target="B")
        assert e.dependency_type == "uses"
        assert e.weight == 1.0
        assert e.confidence == 1.0


# ---------------------------------------------------------------------------
# DependencyResult tests
# ---------------------------------------------------------------------------


class TestDependencyResult:
    """Tests for DependencyResult model."""

    def test_empty(self) -> None:
        r = DependencyResult()
        assert r.dependency_count == 0
        assert r.as_pairs == []
        assert r.is_acyclic is True

    def test_properties(self) -> None:
        r = DependencyResult(
            dependencies=[
                DependencyEdge(source="A", target="B"),
                DependencyEdge(source="B", target="C"),
            ],
            method="llm",
        )
        assert r.dependency_count == 2
        assert r.as_pairs == [("A", "B"), ("B", "C")]

    def test_build_graph(self) -> None:
        r = DependencyResult(
            dependencies=[
                DependencyEdge(source="A", target="B", weight=0.9),
                DependencyEdge(source="B", target="C", weight=0.7),
            ],
        )
        g = r.build_graph()
        assert isinstance(g, nx.DiGraph)
        assert len(g.nodes) == 3
        assert len(g.edges) == 2
        assert g.has_edge("A", "B")

    def test_frozen(self) -> None:
        r = DependencyResult()
        with pytest.raises(Exception):
            r.method = "other"  # type: ignore


# ---------------------------------------------------------------------------
# LLM inference tests
# ---------------------------------------------------------------------------


class TestLLMInference:
    """Tests for LLM-based inference."""

    def test_llm_inference_success(
        self,
        sample_modules: list[ModuleSpec],
        mock_llm_deps: MagicMock,
    ) -> None:
        inf = DependencyInference(llm_gateway=mock_llm_deps)
        result = inf.infer(sample_modules)

        assert result.method == "llm"
        assert result.dependency_count == 3
        assert result.is_acyclic is True

        # Verify specific dependencies
        pairs = result.as_pairs
        assert ("REST API", "Authentication") in pairs
        assert ("REST API", "Database") in pairs
        assert ("Authentication", "Database") in pairs

    def test_llm_fallback_on_error(
        self, sample_modules: list[ModuleSpec]
    ) -> None:
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.side_effect = RuntimeError("LLM error")

        inf = DependencyInference(llm_gateway=llm)
        result = inf.infer(sample_modules)

        assert result.method == "heuristic"

    def test_no_llm_uses_heuristic(
        self, sample_modules: list[ModuleSpec]
    ) -> None:
        inf = DependencyInference(llm_gateway=None)
        result = inf.infer(sample_modules)
        assert result.method == "heuristic"

    def test_llm_disabled(
        self,
        sample_modules: list[ModuleSpec],
        mock_llm_deps: MagicMock,
    ) -> None:
        cfg = DependencyConfig(enable_llm=False)
        inf = DependencyInference(llm_gateway=mock_llm_deps, config=cfg)
        result = inf.infer(sample_modules)

        mock_llm_deps.complete.assert_not_called()
        assert result.method == "heuristic"


# ---------------------------------------------------------------------------
# Cycle detection and resolution tests
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """Tests for cycle detection and resolution."""

    def test_cycle_detected_and_resolved(
        self,
        sample_modules: list[ModuleSpec],
        mock_llm_cyclic: MagicMock,
    ) -> None:
        inf = DependencyInference(llm_gateway=mock_llm_cyclic)
        result = inf.infer(sample_modules)

        assert result.cycles_found > 0
        assert result.is_acyclic is True
        assert result.cycles_resolved > 0
        # Weakest edge (DB → API, weight*conf = 0.18) should be removed
        pairs = result.as_pairs
        assert ("Database", "REST API") not in pairs

    def test_cycle_resolution_disabled(
        self,
        sample_modules: list[ModuleSpec],
        mock_llm_cyclic: MagicMock,
    ) -> None:
        cfg = DependencyConfig(enable_cycle_resolution=False)
        inf = DependencyInference(llm_gateway=mock_llm_cyclic, config=cfg)
        result = inf.infer(sample_modules)

        assert result.cycles_found > 0
        assert result.is_acyclic is False
        assert result.cycles_resolved == 0

    def test_acyclic_graph_no_resolution(
        self,
        sample_modules: list[ModuleSpec],
        mock_llm_deps: MagicMock,
    ) -> None:
        inf = DependencyInference(llm_gateway=mock_llm_deps)
        result = inf.infer(sample_modules)

        assert result.cycles_found == 0
        assert result.is_acyclic is True


# ---------------------------------------------------------------------------
# Heuristic inference tests
# ---------------------------------------------------------------------------


class TestHeuristicInference:
    """Tests for heuristic fallback inference."""

    def test_heuristic_with_feature_map(
        self,
        sample_modules: list[ModuleSpec],
        sample_feature_map: dict[str, FeatureNode],
    ) -> None:
        inf = DependencyInference(llm_gateway=None)
        result = inf.infer(sample_modules, sample_feature_map)

        assert result.method == "heuristic"
        # May or may not have dependencies based on tag overlap

    def test_heuristic_without_feature_map(
        self, sample_modules: list[ModuleSpec]
    ) -> None:
        inf = DependencyInference(llm_gateway=None)
        result = inf.infer(sample_modules)

        assert result.method == "heuristic"
        assert result.is_acyclic is True


# ---------------------------------------------------------------------------
# Max dependencies enforcement tests
# ---------------------------------------------------------------------------


class TestMaxDeps:
    """Tests for maximum dependencies enforcement."""

    def test_enforce_max_deps(self) -> None:
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
            ModuleSpec(name="C", feature_ids=["f3"]),
            ModuleSpec(name="D", feature_ids=["f4"]),
            ModuleSpec(name="E", feature_ids=["f5"]),
            ModuleSpec(name="F", feature_ids=["f6"]),
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = json.dumps({
            "dependencies": [
                {"source": "A", "target": "B", "weight": 0.9, "confidence": 0.9},
                {"source": "A", "target": "C", "weight": 0.8, "confidence": 0.8},
                {"source": "A", "target": "D", "weight": 0.7, "confidence": 0.7},
                {"source": "A", "target": "E", "weight": 0.6, "confidence": 0.6},
                {"source": "A", "target": "F", "weight": 0.5, "confidence": 0.5},
            ]
        })

        cfg = DependencyConfig(max_deps_per_module=3)
        inf = DependencyInference(llm_gateway=llm, config=cfg)
        result = inf.infer(modules)

        # A should have at most 3 outgoing deps
        a_deps = [d for d in result.dependencies if d.source == "A"]
        assert len(a_deps) <= 3


# ---------------------------------------------------------------------------
# Filtering tests
# ---------------------------------------------------------------------------


class TestFiltering:
    """Tests for dependency filtering."""

    def test_self_loops_removed(self) -> None:
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = json.dumps({
            "dependencies": [
                {"source": "A", "target": "A", "confidence": 0.9},  # self-loop
                {"source": "A", "target": "B", "confidence": 0.9},
            ]
        })

        inf = DependencyInference(llm_gateway=llm)
        result = inf.infer(modules)

        pairs = result.as_pairs
        assert ("A", "A") not in pairs
        assert ("A", "B") in pairs

    def test_unknown_modules_filtered(self) -> None:
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = json.dumps({
            "dependencies": [
                {"source": "A", "target": "Unknown", "confidence": 0.9},
                {"source": "A", "target": "B", "confidence": 0.9},
            ]
        })

        inf = DependencyInference(llm_gateway=llm)
        result = inf.infer(modules)

        pairs = result.as_pairs
        assert ("A", "Unknown") not in pairs

    def test_low_confidence_filtered(self) -> None:
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = json.dumps({
            "dependencies": [
                {"source": "A", "target": "B", "confidence": 0.2},  # too low
            ]
        })

        cfg = DependencyConfig(min_confidence=0.5)
        inf = DependencyInference(llm_gateway=llm, config=cfg)
        result = inf.infer(modules)

        assert result.dependency_count == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_modules_raises(self) -> None:
        inf = DependencyInference()
        with pytest.raises(ValueError, match="empty"):
            inf.infer([])

    def test_single_module(self) -> None:
        inf = DependencyInference()
        result = inf.infer([ModuleSpec(name="Solo", feature_ids=["f1"])])

        assert result.method == "trivial"
        assert result.dependency_count == 0
        assert result.is_acyclic is True

    def test_invalid_llm_response(self) -> None:
        modules = [
            ModuleSpec(name="A", feature_ids=["f1"]),
            ModuleSpec(name="B", feature_ids=["f2"]),
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = "Not valid JSON at all"

        inf = DependencyInference(llm_gateway=llm)
        result = inf.infer(modules)

        # Falls back to heuristic
        assert result.method == "heuristic"


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from cobuilder.repomap.graph_construction import (
            DependencyConfig,
            DependencyEdge,
            DependencyInference,
            DependencyResult,
        )
        assert DependencyInference is not None

    def test_import_from_module(self) -> None:
        from cobuilder.repomap.graph_construction.dependencies import (
            DependencyConfig,
            DependencyEdge,
            DependencyInference,
            DependencyResult,
        )
        assert DependencyResult is not None
