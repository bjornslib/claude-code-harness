"""Tests for Graph Export and Serialization (Task 2.3.6).

Tests cover:
- ExportConfig validation and defaults
- ExportFormat enum
- ExportResult model
- GraphExporter.export() for JSON, GraphML, DOT, YAML, SUMMARY formats
- GraphExporter.export_all() batch export
- GraphExporter.to_rpg_graph() Phase 1 conversion
- GraphExporter.from_json() round-trip loading
- File I/O (write and read back)
- Config options: include_metrics, include_rationale, include_features
- Edge cases: empty graph, graph without metrics
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
import pytest

from cobuilder.repomap.graph_construction.builder import FunctionalityGraph
from cobuilder.repomap.graph_construction.dependencies import DependencyEdge
from cobuilder.repomap.graph_construction.metrics import (
    ModularityResult,
    PartitionMetrics,
)
from cobuilder.repomap.graph_construction.partitioner import ModuleSpec
from cobuilder.repomap.graph_construction.export import (
    ExportConfig,
    ExportFormat,
    ExportResult,
    GraphExporter,
)
from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        metadata={"pipeline": "test"},
    )


def _make_graph_with_metrics() -> FunctionalityGraph:
    """Create a graph with metrics attached."""
    return FunctionalityGraph(
        modules=[
            ModuleSpec(name="A", feature_ids=["f1", "f2"]),
            ModuleSpec(name="B", feature_ids=["f3", "f4"]),
        ],
        dependencies=[
            DependencyEdge(source="A", target="B", weight=0.8),
        ],
        metrics=PartitionMetrics(
            avg_cohesion=0.75,
            max_coupling=1,
            all_cohesion_met=True,
            all_coupling_met=True,
            modularity_met=True,
            modularity=ModularityResult(
                q_score=0.45, num_modules=2, num_edges=1, meets_target=True,
            ),
        ),
        is_acyclic=True,
    )


# ---------------------------------------------------------------------------
# ExportConfig tests
# ---------------------------------------------------------------------------


class TestExportConfig:
    """Tests for ExportConfig."""

    def test_defaults(self) -> None:
        cfg = ExportConfig()
        assert cfg.include_metrics is True
        assert cfg.include_rationale is True
        assert cfg.include_metadata is True
        assert cfg.include_features is True
        assert cfg.pretty_print is True
        assert cfg.indent == 2
        assert cfg.dot_rankdir == "LR"

    def test_custom(self) -> None:
        cfg = ExportConfig(
            include_metrics=False,
            include_rationale=False,
            dot_rankdir="TB",
            dot_node_color="lightgreen",
        )
        assert cfg.include_metrics is False
        assert cfg.dot_rankdir == "TB"
        assert cfg.dot_node_color == "lightgreen"


# ---------------------------------------------------------------------------
# ExportFormat tests
# ---------------------------------------------------------------------------


class TestExportFormat:
    """Tests for ExportFormat enum."""

    def test_values(self) -> None:
        assert ExportFormat.JSON == "json"
        assert ExportFormat.GRAPHML == "graphml"
        assert ExportFormat.DOT == "dot"
        assert ExportFormat.YAML == "yaml"
        assert ExportFormat.SUMMARY == "summary"


# ---------------------------------------------------------------------------
# ExportResult tests
# ---------------------------------------------------------------------------


class TestExportResult:
    """Tests for ExportResult model."""

    def test_success(self) -> None:
        r = ExportResult(
            success=True,
            format=ExportFormat.JSON,
            content="{}",
            size_bytes=2,
            module_count=3,
        )
        assert r.success is True
        assert r.format == ExportFormat.JSON

    def test_failure(self) -> None:
        r = ExportResult(
            success=False,
            format=ExportFormat.DOT,
            error="Failed to export",
        )
        assert r.success is False
        assert r.error == "Failed to export"

    def test_frozen(self) -> None:
        r = ExportResult(success=True, format=ExportFormat.JSON)
        with pytest.raises(Exception):
            r.success = False  # type: ignore


# ---------------------------------------------------------------------------
# JSON export tests
# ---------------------------------------------------------------------------


class TestJsonExport:
    """Tests for JSON export."""

    def test_basic_json(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        assert result.success is True
        assert result.format == ExportFormat.JSON
        assert result.module_count == 3
        assert result.dependency_count == 3
        assert result.size_bytes > 0

        data = json.loads(result.content)
        assert len(data["modules"]) == 3
        assert len(data["dependencies"]) == 3
        assert data["metadata"]["is_acyclic"] is True

    def test_json_with_metrics(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph_with_metrics()
        result = exporter.export(graph, ExportFormat.JSON)

        data = json.loads(result.content)
        assert "metrics" in data
        assert data["metrics"]["avg_cohesion"] == 0.75
        assert data["metrics"]["q_score"] == 0.45

    def test_json_no_metrics(self) -> None:
        cfg = ExportConfig(include_metrics=False)
        exporter = GraphExporter(config=cfg)
        graph = _make_graph_with_metrics()
        result = exporter.export(graph, ExportFormat.JSON)

        data = json.loads(result.content)
        assert "metrics" not in data

    def test_json_no_rationale(self) -> None:
        cfg = ExportConfig(include_rationale=False)
        exporter = GraphExporter(config=cfg)
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        data = json.loads(result.content)
        assert "rationale" not in data["modules"][0]
        assert "rationale" not in data["dependencies"][0]

    def test_json_no_features(self) -> None:
        cfg = ExportConfig(include_features=False)
        exporter = GraphExporter(config=cfg)
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        data = json.loads(result.content)
        assert "feature_ids" not in data["modules"][0]

    def test_json_no_metadata(self) -> None:
        cfg = ExportConfig(include_metadata=False)
        exporter = GraphExporter(config=cfg)
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        data = json.loads(result.content)
        assert "metadata" not in data

    def test_json_file(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        filepath = tmp_path / "graph.json"
        result = exporter.export(graph, ExportFormat.JSON, filepath)

        assert result.success is True
        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert len(data["modules"]) == 3

    def test_json_compact(self) -> None:
        cfg = ExportConfig(pretty_print=False)
        exporter = GraphExporter(config=cfg)
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        # No indentation means no newlines in values
        assert "\n" not in result.content


# ---------------------------------------------------------------------------
# GraphML export tests
# ---------------------------------------------------------------------------


class TestGraphmlExport:
    """Tests for GraphML export."""

    def test_graphml_string(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.GRAPHML)

        assert result.success is True
        assert "graphml" in result.content.lower()

    def test_graphml_file(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        filepath = tmp_path / "graph.graphml"
        result = exporter.export(graph, ExportFormat.GRAPHML, filepath)

        assert result.success is True
        assert filepath.exists()

        # Verify NetworkX can read it back
        loaded = nx.read_graphml(str(filepath))
        assert len(loaded.nodes) == 3
        assert len(loaded.edges) == 3


# ---------------------------------------------------------------------------
# DOT export tests
# ---------------------------------------------------------------------------


class TestDotExport:
    """Tests for DOT export."""

    def test_dot_basic(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.DOT)

        assert result.success is True
        assert "digraph FunctionalityGraph" in result.content
        assert '"Auth"' in result.content
        assert '"API" -> "Auth"' in result.content

    def test_dot_custom_config(self) -> None:
        cfg = ExportConfig(
            dot_rankdir="TB",
            dot_node_shape="ellipse",
            dot_node_color="lightgreen",
        )
        exporter = GraphExporter(config=cfg)
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.DOT)

        assert "rankdir=TB" in result.content
        assert "shape=ellipse" in result.content
        assert "fillcolor=lightgreen" in result.content

    def test_dot_with_tooltip(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.DOT)

        # Rationale should appear as tooltip
        assert "tooltip" in result.content

    def test_dot_no_rationale(self) -> None:
        cfg = ExportConfig(include_rationale=False)
        exporter = GraphExporter(config=cfg)
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.DOT)

        # Edges should not have tooltip when rationale disabled
        # (tooltip only added when include_rationale=True)
        edge_lines = [
            l for l in result.content.split("\n")
            if "->" in l
        ]
        for line in edge_lines:
            assert "tooltip" not in line

    def test_dot_file(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        filepath = tmp_path / "graph.dot"
        result = exporter.export(graph, ExportFormat.DOT, filepath)

        assert result.success is True
        assert filepath.exists()
        content = filepath.read_text()
        assert "digraph" in content


# ---------------------------------------------------------------------------
# YAML export tests
# ---------------------------------------------------------------------------


class TestYamlExport:
    """Tests for YAML export."""

    def test_yaml_basic(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.YAML)

        assert result.success is True
        assert "modules:" in result.content
        assert "dependencies:" in result.content
        assert "  - name: Auth" in result.content

    def test_yaml_with_metadata(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.YAML)

        assert "metadata:" in result.content
        assert "module_count: 3" in result.content

    def test_yaml_with_metrics(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph_with_metrics()
        result = exporter.export(graph, ExportFormat.YAML)

        assert "metrics:" in result.content
        assert "avg_cohesion:" in result.content

    def test_yaml_file(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        filepath = tmp_path / "graph.yaml"
        result = exporter.export(graph, ExportFormat.YAML, filepath)

        assert result.success is True
        assert filepath.exists()


# ---------------------------------------------------------------------------
# Summary export tests
# ---------------------------------------------------------------------------


class TestSummaryExport:
    """Tests for text summary export."""

    def test_summary_basic(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.SUMMARY)

        assert result.success is True
        assert "FUNCTIONALITY GRAPH SUMMARY" in result.content
        assert "Modules: 3" in result.content
        assert "Dependencies: 3" in result.content
        assert "[Auth]" in result.content

    def test_summary_with_metrics(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph_with_metrics()
        result = exporter.export(graph, ExportFormat.SUMMARY)

        assert "QUALITY METRICS" in result.content
        assert "Average Cohesion:" in result.content

    def test_summary_file(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        filepath = tmp_path / "summary.txt"
        result = exporter.export(graph, ExportFormat.SUMMARY, filepath)

        assert result.success is True
        assert filepath.exists()


# ---------------------------------------------------------------------------
# export_all tests
# ---------------------------------------------------------------------------


class TestExportAll:
    """Tests for batch export."""

    def test_export_all(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        results = exporter.export_all(graph, tmp_path, "test_graph")

        assert len(results) == 5
        for fmt, result in results.items():
            assert result.success is True, f"Failed for {fmt}"

        # Verify files exist
        assert (tmp_path / "test_graph.json").exists()
        assert (tmp_path / "test_graph.graphml").exists()
        assert (tmp_path / "test_graph.dot").exists()
        assert (tmp_path / "test_graph.yaml").exists()
        assert (tmp_path / "test_graph.txt").exists()


# ---------------------------------------------------------------------------
# RPGGraph conversion tests
# ---------------------------------------------------------------------------


class TestToRpgGraph:
    """Tests for FunctionalityGraph → RPGGraph conversion."""

    def test_basic_conversion(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        assert isinstance(rpg, RPGGraph)
        # 3 modules + 6 features = 9 nodes
        assert rpg.node_count == 9
        # 6 hierarchy edges + 3 dependency edges = 9 edges
        assert rpg.edge_count == 9

    def test_module_nodes(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        module_nodes = [
            n for n in rpg.nodes.values()
            if n.level == NodeLevel.MODULE
        ]
        assert len(module_nodes) == 3
        module_names = {n.name for n in module_nodes}
        assert module_names == {"Auth", "API", "Database"}

    def test_feature_nodes(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        feature_nodes = [
            n for n in rpg.nodes.values()
            if n.level == NodeLevel.FEATURE
        ]
        assert len(feature_nodes) == 6
        feature_names = {n.name for n in feature_nodes}
        assert "auth.login" in feature_names
        assert "api.users" in feature_names

    def test_hierarchy_edges(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        hier_edges = [
            e for e in rpg.edges.values()
            if e.edge_type == EdgeType.HIERARCHY
        ]
        assert len(hier_edges) == 6  # 2+2+2 features

    def test_dependency_edges(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        dep_edges = [
            e for e in rpg.edges.values()
            if e.edge_type in (EdgeType.DATA_FLOW, EdgeType.INVOCATION)
        ]
        assert len(dep_edges) == 3

    def test_data_flow_mapping(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        data_flow_edges = [
            e for e in rpg.edges.values()
            if e.edge_type == EdgeType.DATA_FLOW
        ]
        # API→Database and Auth→Database are data_flow
        assert len(data_flow_edges) == 2

    def test_invocation_mapping(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        invocation_edges = [
            e for e in rpg.edges.values()
            if e.edge_type == EdgeType.INVOCATION
        ]
        # API→Auth is "uses" → INVOCATION
        assert len(invocation_edges) == 1

    def test_metadata(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph, project_name="test_project")

        assert rpg.metadata["project"] == "test_project"
        assert rpg.metadata["source"] == "FunctionalityGraph"
        assert rpg.metadata["module_count"] == 3

    def test_feature_parent_ids(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        rpg = exporter.to_rpg_graph(graph)

        feature_nodes = [
            n for n in rpg.nodes.values()
            if n.level == NodeLevel.FEATURE
        ]
        for fn in feature_nodes:
            assert fn.parent_id is not None
            parent = rpg.get_node(fn.parent_id)
            assert parent is not None
            assert parent.level == NodeLevel.MODULE


# ---------------------------------------------------------------------------
# Round-trip (from_json) tests
# ---------------------------------------------------------------------------


class TestFromJson:
    """Tests for JSON round-trip loading."""

    def test_round_trip_string(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        loaded = GraphExporter.from_json(json_str=result.content)
        assert loaded.module_count == graph.module_count
        assert loaded.dependency_count == graph.dependency_count

    def test_round_trip_file(self, tmp_path: Path) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        filepath = tmp_path / "roundtrip.json"
        exporter.export(graph, ExportFormat.JSON, filepath)

        loaded = GraphExporter.from_json(filepath=filepath)
        assert loaded.module_count == 3
        assert loaded.dependency_count == 3

    def test_round_trip_preserves_modules(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        loaded = GraphExporter.from_json(json_str=result.content)
        orig_names = {m.name for m in graph.modules}
        loaded_names = {m.name for m in loaded.modules}
        assert orig_names == loaded_names

    def test_round_trip_preserves_deps(self) -> None:
        exporter = GraphExporter()
        graph = _make_graph()
        result = exporter.export(graph, ExportFormat.JSON)

        loaded = GraphExporter.from_json(json_str=result.content)
        orig_pairs = {(d.source, d.target) for d in graph.dependencies}
        loaded_pairs = {(d.source, d.target) for d in loaded.dependencies}
        assert orig_pairs == loaded_pairs

    def test_no_args_raises(self) -> None:
        with pytest.raises(ValueError, match="Must provide"):
            GraphExporter.from_json()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_graph(self) -> None:
        exporter = GraphExporter()
        graph = FunctionalityGraph()

        for fmt in ExportFormat:
            result = exporter.export(graph, fmt)
            assert result.success is True, f"Failed for {fmt}"

    def test_graph_no_dependencies(self) -> None:
        exporter = GraphExporter()
        graph = FunctionalityGraph(
            modules=[
                ModuleSpec(name="Solo", feature_ids=["f1"]),
            ]
        )
        result = exporter.export(graph, ExportFormat.JSON)
        data = json.loads(result.content)
        assert data["dependencies"] == []

    def test_rpg_conversion_empty(self) -> None:
        exporter = GraphExporter()
        graph = FunctionalityGraph()
        rpg = exporter.to_rpg_graph(graph)

        assert rpg.node_count == 0
        assert rpg.edge_count == 0


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from cobuilder.repomap.graph_construction import (
            ExportConfig,
            ExportFormat,
            ExportResult,
            GraphExporter,
        )
        assert GraphExporter is not None

    def test_import_from_module(self) -> None:
        from cobuilder.repomap.graph_construction.export import (
            ExportConfig,
            ExportFormat,
            ExportResult,
            GraphExporter,
        )
        assert ExportResult is not None
