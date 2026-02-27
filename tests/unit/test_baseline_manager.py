"""Unit tests for zerorepo.serena.baseline.BaselineManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.serena.baseline import BaselineManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sample_graph() -> RPGGraph:
    """Build a simple RPGGraph with a MODULE, COMPONENT, and FEATURE node."""
    graph = RPGGraph()
    mod = RPGNode(
        name="auth_module",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="auth/",
    )
    comp = RPGNode(
        name="login_handler",
        level=NodeLevel.COMPONENT,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="auth/",
        file_path="auth/login.py",
    )
    feat = RPGNode(
        name="validate_credentials",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="auth/",
        file_path="auth/login.py",
    )
    graph.add_node(mod)
    graph.add_node(comp)
    graph.add_node(feat)

    # HIERARCHY edge: module → component
    edge1 = RPGEdge(
        source_id=mod.id,
        target_id=comp.id,
        edge_type=EdgeType.HIERARCHY,
    )
    graph.add_edge(edge1)

    # HIERARCHY edge: component → feature
    edge2 = RPGEdge(
        source_id=comp.id,
        target_id=feat.id,
        edge_type=EdgeType.HIERARCHY,
    )
    graph.add_edge(edge2)

    return graph


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBaselineManagerDefaultPath:
    def test_default_path_construction(self, tmp_path: Path) -> None:
        """default_path() returns .zerorepo/baseline.json under project root."""
        result = BaselineManager.default_path(tmp_path)
        assert result == tmp_path / ".zerorepo" / "baseline.json"


class TestBaselineManagerSave:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        """save() creates the JSON file at the given path."""
        mgr = BaselineManager()
        graph = _make_sample_graph()
        output = tmp_path / "baseline.json"
        result = mgr.save(graph, output_path=output, project_root=tmp_path)

        assert result.exists()
        assert result == output.resolve()

    def test_save_adds_metadata(self, tmp_path: Path) -> None:
        """save() sets baseline_generated_at, project_root, baseline_version."""
        mgr = BaselineManager()
        graph = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(graph, output_path=output, project_root=tmp_path)

        assert "baseline_generated_at" in graph.metadata
        assert "project_root" in graph.metadata
        assert graph.metadata["baseline_version"] == "1.0"

    def test_save_with_extra_metadata(self, tmp_path: Path) -> None:
        """save() merges extra_metadata into graph metadata."""
        mgr = BaselineManager()
        graph = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(
            graph,
            output_path=output,
            project_root=tmp_path,
            extra_metadata={"source": "test", "version": "0.1"},
        )

        assert graph.metadata["source"] == "test"
        assert graph.metadata["version"] == "0.1"

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        """save() creates parent directories if they don't exist."""
        mgr = BaselineManager()
        graph = _make_sample_graph()
        output = tmp_path / "deep" / "nested" / "baseline.json"
        result = mgr.save(graph, output_path=output, project_root=tmp_path)

        assert result.exists()
        assert (tmp_path / "deep" / "nested").is_dir()

    def test_save_produces_valid_json(self, tmp_path: Path) -> None:
        """save() produces valid JSON content."""
        mgr = BaselineManager()
        graph = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(graph, output_path=output, project_root=tmp_path)

        content = output.read_text(encoding="utf-8")
        data = json.loads(content)
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data


class TestBaselineManagerLoad:
    def test_load_restores_graph(self, tmp_path: Path) -> None:
        """load() restores the RPGGraph from a saved baseline."""
        mgr = BaselineManager()
        original = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(original, output_path=output, project_root=tmp_path)

        loaded = mgr.load(output)

        assert loaded.node_count == original.node_count
        assert loaded.edge_count == original.edge_count

    def test_load_preserves_node_names(self, tmp_path: Path) -> None:
        """Loaded graph has same node names as original."""
        mgr = BaselineManager()
        original = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(original, output_path=output, project_root=tmp_path)

        loaded = mgr.load(output)

        original_names = sorted(n.name for n in original.nodes.values())
        loaded_names = sorted(n.name for n in loaded.nodes.values())
        assert loaded_names == original_names

    def test_load_preserves_metadata(self, tmp_path: Path) -> None:
        """Loaded graph has the baseline metadata."""
        mgr = BaselineManager()
        original = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(original, output_path=output, project_root=tmp_path)

        loaded = mgr.load(output)
        assert loaded.metadata["baseline_version"] == "1.0"
        assert "baseline_generated_at" in loaded.metadata

    def test_load_preserves_edge_types(self, tmp_path: Path) -> None:
        """Loaded graph has correct edge types."""
        mgr = BaselineManager()
        original = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(original, output_path=output, project_root=tmp_path)

        loaded = mgr.load(output)
        edge_types = [e.edge_type for e in loaded.edges.values()]
        assert all(et == EdgeType.HIERARCHY for et in edge_types)

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """load() raises FileNotFoundError for missing baseline."""
        mgr = BaselineManager()
        with pytest.raises(FileNotFoundError, match="not found"):
            mgr.load(tmp_path / "nope.json")

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """load() raises ValueError for invalid JSON."""
        mgr = BaselineManager()
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to parse"):
            mgr.load(bad_file)


class TestBaselineRoundtrip:
    def test_roundtrip_empty_graph(self, tmp_path: Path) -> None:
        """Empty graph roundtrips correctly."""
        mgr = BaselineManager()
        original = RPGGraph()
        output = tmp_path / "baseline.json"
        mgr.save(original, output_path=output, project_root=tmp_path)

        loaded = mgr.load(output)
        assert loaded.node_count == 0
        assert loaded.edge_count == 0

    def test_roundtrip_preserves_node_levels(self, tmp_path: Path) -> None:
        """Node levels are preserved through roundtrip."""
        mgr = BaselineManager()
        original = _make_sample_graph()
        output = tmp_path / "baseline.json"
        mgr.save(original, output_path=output, project_root=tmp_path)

        loaded = mgr.load(output)
        original_levels = sorted(n.level.value for n in original.nodes.values())
        loaded_levels = sorted(n.level.value for n in loaded.nodes.values())
        assert loaded_levels == original_levels
