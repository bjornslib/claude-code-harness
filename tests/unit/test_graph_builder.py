"""Tests for Functionality Graph Builder (Task 2.3.4).

Tests cover:
- BuilderConfig validation and defaults
- FunctionalityGraph model and properties
- FunctionalityGraph.build_networkx_graph()
- FunctionalityGraph export: to_json, to_graphml, to_dot
- FunctionalityGraph.from_json() round-trip
- FunctionalityGraphBuilder.build() full pipeline
- FunctionalityGraphBuilder.build_from_modules()
- Integration with partitioner, dependencies, metrics
- Edge cases: empty features, no LLM, no metrics
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import networkx as nx
import numpy as np
import pytest

from cobuilder.repomap.llm.models import ModelTier
from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.graph_construction.builder import (
    BuilderConfig,
    FunctionalityGraph,
    FunctionalityGraphBuilder,
)
from cobuilder.repomap.graph_construction.dependencies import DependencyEdge
from cobuilder.repomap.graph_construction.partitioner import ModuleSpec, PartitionerConfig


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


def _make_sample_features() -> list[FeatureNode]:
    """Create 10 features in 3 groups."""
    rng = np.random.RandomState(42)
    features = []
    for i in range(10):
        group = i % 3
        base = np.zeros(10)
        base[group * 3: group * 3 + 3] = 1.0
        emb = (base + rng.randn(10) * 0.1).tolist()
        features.append(
            _make_feature(
                f"feat_{i}",
                f"Feature {i}",
                tags=[f"group_{group}"],
                embedding=emb,
            )
        )
    return features


def _make_graph() -> FunctionalityGraph:
    """Create a sample FunctionalityGraph."""
    return FunctionalityGraph(
        modules=[
            ModuleSpec(
                name="Auth",
                description="Authentication module",
                feature_ids=["auth.login", "auth.register"],
                public_interface=["auth.login"],
                rationale="Auth features",
            ),
            ModuleSpec(
                name="API",
                description="REST API endpoints",
                feature_ids=["api.users", "api.products"],
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
        ],
        dependencies=[
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
        ],
        is_acyclic=True,
    )


# ---------------------------------------------------------------------------
# BuilderConfig tests
# ---------------------------------------------------------------------------


class TestBuilderConfig:
    """Tests for BuilderConfig."""

    def test_defaults(self) -> None:
        cfg = BuilderConfig()
        assert cfg.require_acyclic is True
        assert cfg.compute_metrics is True
        assert isinstance(cfg.partitioner_config, PartitionerConfig)

    def test_custom(self) -> None:
        cfg = BuilderConfig(
            require_acyclic=False,
            compute_metrics=False,
        )
        assert cfg.require_acyclic is False
        assert cfg.compute_metrics is False


# ---------------------------------------------------------------------------
# FunctionalityGraph model tests
# ---------------------------------------------------------------------------


class TestFunctionalityGraph:
    """Tests for FunctionalityGraph model."""

    def test_properties(self) -> None:
        g = _make_graph()
        assert g.module_count == 3
        assert g.dependency_count == 3
        assert g.feature_count == 6
        assert g.is_acyclic is True

    def test_empty(self) -> None:
        g = FunctionalityGraph()
        assert g.module_count == 0
        assert g.dependency_count == 0
        assert g.feature_count == 0

    def test_frozen(self) -> None:
        g = FunctionalityGraph()
        with pytest.raises(Exception):
            g.is_acyclic = False  # type: ignore


# ---------------------------------------------------------------------------
# NetworkX graph tests
# ---------------------------------------------------------------------------


class TestBuildNetworkxGraph:
    """Tests for build_networkx_graph."""

    def test_basic(self) -> None:
        g = _make_graph()
        nx_graph = g.build_networkx_graph()

        assert isinstance(nx_graph, nx.DiGraph)
        assert len(nx_graph.nodes) == 3
        assert len(nx_graph.edges) == 3

    def test_node_attributes(self) -> None:
        g = _make_graph()
        nx_graph = g.build_networkx_graph()

        auth_attrs = nx_graph.nodes["Auth"]
        assert auth_attrs["description"] == "Authentication module"
        assert "auth.login" in auth_attrs["features"]
        assert auth_attrs["feature_count"] == 2

    def test_edge_attributes(self) -> None:
        g = _make_graph()
        nx_graph = g.build_networkx_graph()

        edge_data = nx_graph.edges["API", "Auth"]
        assert edge_data["dependency_type"] == "uses"
        assert edge_data["weight"] == 0.9

    def test_acyclic(self) -> None:
        g = _make_graph()
        nx_graph = g.build_networkx_graph()
        assert nx.is_directed_acyclic_graph(nx_graph)


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------


class TestToJson:
    """Tests for to_json export."""

    def test_json_string(self) -> None:
        g = _make_graph()
        json_str = g.to_json()
        data = json.loads(json_str)

        assert len(data["modules"]) == 3
        assert len(data["dependencies"]) == 3
        assert data["metadata"]["module_count"] == 3
        assert data["metadata"]["is_acyclic"] is True

    def test_json_file(self, tmp_path: Path) -> None:
        g = _make_graph()
        filepath = tmp_path / "graph.json"
        g.to_json(filepath)

        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert len(data["modules"]) == 3

    def test_json_with_metrics(self) -> None:
        from cobuilder.repomap.graph_construction.metrics import (
            MetricsConfig,
            ModularityResult,
            PartitionMetrics,
        )

        g = FunctionalityGraph(
            modules=[ModuleSpec(name="A", feature_ids=["f1", "f2"])],
            metrics=PartitionMetrics(
                avg_cohesion=0.75,
                max_coupling=2,
                all_cohesion_met=True,
                all_coupling_met=True,
                modularity_met=True,
                modularity=ModularityResult(
                    q_score=0.5, num_modules=1, num_edges=0, meets_target=True
                ),
            ),
        )
        json_str = g.to_json()
        data = json.loads(json_str)

        assert "metrics" in data
        assert data["metrics"]["avg_cohesion"] == 0.75
        assert data["metrics"]["q_score"] == 0.5


class TestToGraphml:
    """Tests for to_graphml export."""

    def test_graphml_file(self, tmp_path: Path) -> None:
        g = _make_graph()
        filepath = tmp_path / "graph.graphml"
        g.to_graphml(filepath)

        assert filepath.exists()
        # Verify it can be read back by NetworkX
        loaded = nx.read_graphml(str(filepath))
        assert len(loaded.nodes) == 3
        assert len(loaded.edges) == 3


class TestToDot:
    """Tests for to_dot export."""

    def test_dot_string(self) -> None:
        g = _make_graph()
        dot = g.to_dot()

        assert "digraph FunctionalityGraph" in dot
        assert '"Auth"' in dot
        assert '"API" -> "Auth"' in dot

    def test_dot_file(self, tmp_path: Path) -> None:
        g = _make_graph()
        filepath = tmp_path / "graph.dot"
        g.to_dot(filepath)

        assert filepath.exists()
        content = filepath.read_text()
        assert "digraph" in content


# ---------------------------------------------------------------------------
# from_json round-trip tests
# ---------------------------------------------------------------------------


class TestFromJson:
    """Tests for from_json loading."""

    def test_round_trip(self) -> None:
        original = _make_graph()
        json_str = original.to_json()
        loaded = FunctionalityGraph.from_json(json_str)

        assert loaded.module_count == original.module_count
        assert loaded.dependency_count == original.dependency_count
        assert loaded.is_acyclic == original.is_acyclic

        # Verify module names match
        orig_names = {m.name for m in original.modules}
        loaded_names = {m.name for m in loaded.modules}
        assert orig_names == loaded_names

    def test_round_trip_preserves_features(self) -> None:
        original = _make_graph()
        loaded = FunctionalityGraph.from_json(original.to_json())

        for orig, load in zip(original.modules, loaded.modules):
            assert set(orig.feature_ids) == set(load.feature_ids)

    def test_round_trip_preserves_dependencies(self) -> None:
        original = _make_graph()
        loaded = FunctionalityGraph.from_json(original.to_json())

        orig_pairs = {(d.source, d.target) for d in original.dependencies}
        loaded_pairs = {(d.source, d.target) for d in loaded.dependencies}
        assert orig_pairs == loaded_pairs


# ---------------------------------------------------------------------------
# Builder tests
# ---------------------------------------------------------------------------


class TestFunctionalityGraphBuilder:
    """Tests for FunctionalityGraphBuilder."""

    def test_build_no_llm(self) -> None:
        """Build without LLM uses fallback methods."""
        features = _make_sample_features()
        builder = FunctionalityGraphBuilder(llm_gateway=None)
        graph = builder.build(features)

        assert graph.module_count >= 1
        assert graph.feature_count == 10
        assert graph.is_acyclic is True

    def test_build_with_mock_llm(self) -> None:
        """Build with mocked LLM for both partitioning and dependencies."""
        features = [
            _make_feature(f"f{i}", f"Feature {i}", tags=[f"g{i % 3}"])
            for i in range(9)
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"

        call_count = {"n": 0}

        def complete_side_effect(messages, model, tier=None, **kwargs):
            call_count["n"] += 1
            prompt = messages[0]["content"]

            if "partitioning" in prompt.lower() or "partition" in prompt.lower():
                return json.dumps({
                    "modules": [
                        {
                            "name": "Group Zero",
                            "description": "Features in group 0",
                            "feature_ids": ["f0", "f3", "f6"],
                            "public_interface": ["f0"],
                        },
                        {
                            "name": "Group One",
                            "description": "Features in group 1",
                            "feature_ids": ["f1", "f4", "f7"],
                            "public_interface": ["f1"],
                        },
                        {
                            "name": "Group Two",
                            "description": "Features in group 2",
                            "feature_ids": ["f2", "f5", "f8"],
                            "public_interface": ["f2"],
                        },
                    ]
                })
            else:
                # Dependency inference
                return json.dumps({
                    "dependencies": [
                        {
                            "source": "Group One",
                            "target": "Group Zero",
                            "dependency_type": "uses",
                            "weight": 0.8,
                            "confidence": 0.9,
                            "rationale": "Group 1 uses Group 0",
                        },
                    ]
                })

        llm.complete.side_effect = complete_side_effect

        builder = FunctionalityGraphBuilder(llm_gateway=llm)
        graph = builder.build(features)

        assert graph.module_count == 3
        assert graph.feature_count == 9
        assert graph.is_acyclic is True
        assert graph.dependency_count >= 1

    def test_build_computes_metrics(self) -> None:
        """Build computes quality metrics by default."""
        features = _make_sample_features()
        builder = FunctionalityGraphBuilder(llm_gateway=None)
        graph = builder.build(features)

        assert graph.metrics is not None
        assert graph.metrics.avg_cohesion >= 0.0

    def test_build_no_metrics(self) -> None:
        """Build with compute_metrics=False skips metrics."""
        features = _make_sample_features()
        cfg = BuilderConfig(compute_metrics=False)
        builder = FunctionalityGraphBuilder(llm_gateway=None, config=cfg)
        graph = builder.build(features)

        assert graph.metrics is None

    def test_build_empty_raises(self) -> None:
        builder = FunctionalityGraphBuilder()
        with pytest.raises(ValueError, match="empty"):
            builder.build([])


# ---------------------------------------------------------------------------
# build_from_modules tests
# ---------------------------------------------------------------------------


class TestBuildFromModules:
    """Tests for build_from_modules."""

    def test_basic(self) -> None:
        modules = [
            ModuleSpec(name="Auth", feature_ids=["f1", "f2"]),
            ModuleSpec(name="API", feature_ids=["f3", "f4"]),
        ]
        builder = FunctionalityGraphBuilder(llm_gateway=None)
        graph = builder.build_from_modules(modules)

        assert graph.module_count == 2
        assert graph.is_acyclic is True

    def test_with_feature_map(self) -> None:
        features = {
            "f1": _make_feature("f1", embedding=[1.0, 0.0, 0.0]),
            "f2": _make_feature("f2", embedding=[0.9, 0.1, 0.0]),
            "f3": _make_feature("f3", embedding=[0.0, 1.0, 0.0]),
            "f4": _make_feature("f4", embedding=[0.0, 0.9, 0.1]),
        }
        modules = [
            ModuleSpec(name="A", feature_ids=["f1", "f2"]),
            ModuleSpec(name="B", feature_ids=["f3", "f4"]),
        ]

        builder = FunctionalityGraphBuilder(llm_gateway=None)
        graph = builder.build_from_modules(modules, features)

        assert graph.metrics is not None

    def test_empty_modules_raises(self) -> None:
        builder = FunctionalityGraphBuilder()
        with pytest.raises(ValueError, match="empty"):
            builder.build_from_modules([])


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from cobuilder.repomap.graph_construction import (
            BuilderConfig,
            FunctionalityGraph,
            FunctionalityGraphBuilder,
        )
        assert FunctionalityGraphBuilder is not None

    def test_import_from_module(self) -> None:
        from cobuilder.repomap.graph_construction.builder import (
            BuilderConfig,
            FunctionalityGraph,
            FunctionalityGraphBuilder,
        )
        assert FunctionalityGraph is not None
