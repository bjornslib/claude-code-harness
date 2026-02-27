"""Unit tests for BaselineManager.merge_nodes() and scoped_save() — F4.2.

Tests cover:
- merge_nodes: replace existing node with same ID
- merge_nodes: append new node with different ID
- merge_nodes: combined replace + append
- merge_nodes: metadata preservation
- scoped_save: rotates baseline.json → baseline.prev.json
- scoped_save: saves merged graph
- scoped_save: handles missing existing baseline gracefully
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.serena.baseline import BaselineManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    level: NodeLevel = NodeLevel.COMPONENT,
    folder: str = "src/",
    file: str | None = None,
    node_id: UUID | None = None,
) -> RPGNode:
    """Create a minimal RPGNode."""
    kwargs: dict = dict(
        name=name,
        level=level,
        node_type=NodeType.FUNCTIONALITY,
        folder_path=folder,
        serena_validated=True,
        metadata={"baseline": True},
    )
    if file:
        kwargs["file_path"] = file
    node = RPGNode(**kwargs)
    if node_id is not None:
        # Override the auto-generated UUID for deterministic testing
        object.__setattr__(node, "id", node_id)
    return node


def _make_graph(*names: str, level: NodeLevel = NodeLevel.COMPONENT) -> RPGGraph:
    """Build an RPGGraph with N nodes named by *names*."""
    graph = RPGGraph()
    for name in names:
        node = _make_node(name, level=level, file=f"src/{name}.py")
        graph.add_node(node)
    return graph


def _make_graph_with_ids(
    node_specs: list[tuple[str, UUID]],
    level: NodeLevel = NodeLevel.COMPONENT,
) -> RPGGraph:
    """Build an RPGGraph using specific UUIDs for deterministic ID-based tests."""
    graph = RPGGraph()
    for name, nid in node_specs:
        node = _make_node(name, level=level, file=f"src/{name}.py", node_id=nid)
        graph.nodes[nid] = node
    return graph


# ---------------------------------------------------------------------------
# TestMergeNodes
# ---------------------------------------------------------------------------


class TestMergeNodes:
    """Tests for BaselineManager.merge_nodes()."""

    def test_merge_replaces_existing_node(self) -> None:
        """A scoped node with the same UUID replaces the existing node."""
        shared_id = uuid4()

        existing = _make_graph_with_ids([("old_name", shared_id)])
        scoped = _make_graph_with_ids([("new_name", shared_id)])

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        assert merged.node_count == 1
        replaced = merged.nodes[shared_id]
        assert replaced.name == "new_name", (
            f"Expected 'new_name' but got '{replaced.name}'"
        )

    def test_merge_appends_new_node(self) -> None:
        """A scoped node with a fresh UUID is appended to existing."""
        existing = _make_graph("a", "b", "c", "d", "e")  # 5 nodes
        scoped_node = _make_node("new_file", file="src/new_file.py")
        scoped = RPGGraph()
        scoped.add_node(scoped_node)

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        assert merged.node_count == 6
        merged_names = {n.name for n in merged.nodes.values()}
        assert "new_file" in merged_names

    def test_merge_combined_replace_and_append(self) -> None:
        """One scoped node replaces an existing; another is appended."""
        shared_id = uuid4()

        # 5 existing nodes; one has the shared_id
        existing = RPGGraph()
        for i in range(4):
            existing.add_node(
                _make_node(f"node_{i}", file=f"src/node_{i}.py")
            )
        existing.nodes[shared_id] = _make_node(
            "to_replace", node_id=shared_id, file="src/to_replace.py"
        )

        # scoped: 1 replacement + 1 brand new
        scoped = _make_graph_with_ids([("replaced", shared_id)])
        brand_new = _make_node("brand_new", file="src/brand_new.py")
        scoped.add_node(brand_new)

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        # 4 unchanged + 1 replaced (same id) + 1 new = 6
        assert merged.node_count == 6

        merged_names = {n.name for n in merged.nodes.values()}
        assert "replaced" in merged_names, "replaced node should appear by new name"
        assert "to_replace" not in merged_names, "old name should be gone"
        assert "brand_new" in merged_names

    def test_merge_preserves_unchanged_nodes(self) -> None:
        """Nodes in existing that are not in scoped are kept unchanged."""
        existing = _make_graph("keeper_a", "keeper_b", "keeper_c")
        scoped = _make_graph("newcomer")

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        merged_names = {n.name for n in merged.nodes.values()}
        assert "keeper_a" in merged_names
        assert "keeper_b" in merged_names
        assert "keeper_c" in merged_names
        assert "newcomer" in merged_names

    def test_merge_metadata_preserved_and_timestamp_updated(self) -> None:
        """Existing metadata is preserved; baseline_generated_at is refreshed."""
        existing = _make_graph("x")
        existing.metadata["repo_name"] = "testrepo"
        existing.metadata["baseline_generated_at"] = "2020-01-01T00:00:00+00:00"

        scoped = _make_graph("y")

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        assert merged.metadata.get("repo_name") == "testrepo"
        assert merged.metadata["baseline_generated_at"] != "2020-01-01T00:00:00+00:00"

    def test_merge_empty_scoped_into_existing(self) -> None:
        """Merging an empty scoped graph into existing leaves existing unchanged."""
        existing = _make_graph("a", "b", "c")
        scoped = RPGGraph()

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        assert merged.node_count == 3

    def test_merge_existing_empty_uses_scoped_only(self) -> None:
        """Merging scoped into empty existing produces scoped nodes only."""
        existing = RPGGraph()
        scoped = _make_graph("x", "y")

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        assert merged.node_count == 2

    def test_merge_edges_combined(self) -> None:
        """Edges from both existing and scoped appear in merged."""
        # Create two graphs, each with one edge
        existing = RPGGraph()
        n1 = _make_node("mod", level=NodeLevel.MODULE, folder="src/")
        n2 = _make_node("comp", level=NodeLevel.COMPONENT, file="src/comp.py")
        existing.add_node(n1)
        existing.add_node(n2)
        e1 = RPGEdge(source_id=n1.id, target_id=n2.id, edge_type=EdgeType.HIERARCHY)
        existing.add_edge(e1)

        scoped = RPGGraph()
        n3 = _make_node("mod2", level=NodeLevel.MODULE, folder="lib/")
        n4 = _make_node("comp2", level=NodeLevel.COMPONENT, folder="lib/", file="lib/comp2.py")
        scoped.add_node(n3)
        scoped.add_node(n4)
        e2 = RPGEdge(source_id=n3.id, target_id=n4.id, edge_type=EdgeType.HIERARCHY)
        scoped.add_edge(e2)

        mgr = BaselineManager()
        merged = mgr.merge_nodes(existing, scoped)

        assert merged.edge_count == 2


# ---------------------------------------------------------------------------
# TestScopedSave
# ---------------------------------------------------------------------------


class TestScopedSave:
    """Tests for BaselineManager.scoped_save()."""

    def test_scoped_save_creates_baseline_json(self, tmp_path: Path) -> None:
        """scoped_save writes baseline.json in the expected location."""
        repomap_dir = tmp_path / ".repomap"
        project_root = tmp_path / "repo"
        project_root.mkdir()

        scoped = _make_graph("module_a", "module_b")
        mgr = BaselineManager()
        mgr.scoped_save(
            repo_name="testrepo",
            scoped=scoped,
            project_root=project_root,
            repomap_dir=repomap_dir,
        )

        baseline = repomap_dir / "baselines" / "testrepo" / "baseline.json"
        assert baseline.exists(), "baseline.json should be created"

    def test_scoped_save_rotates_existing_baseline(self, tmp_path: Path) -> None:
        """scoped_save rotates baseline.json → baseline.prev.json before writing."""
        repomap_dir = tmp_path / ".repomap"
        baseline_dir = repomap_dir / "baselines" / "testrepo"
        baseline_dir.mkdir(parents=True)
        project_root = tmp_path / "repo"
        project_root.mkdir()

        # Write a pre-existing baseline
        current = baseline_dir / "baseline.json"
        current.write_text(
            json.dumps({"nodes": {}, "edges": {}, "metadata": {"old": True}})
        )

        scoped = _make_graph("new_node")
        mgr = BaselineManager()
        mgr.scoped_save(
            repo_name="testrepo",
            scoped=scoped,
            project_root=project_root,
            repomap_dir=repomap_dir,
        )

        prev = baseline_dir / "baseline.prev.json"
        assert prev.exists(), "baseline.prev.json should be created from rotation"

    def test_scoped_save_merges_with_existing(self, tmp_path: Path) -> None:
        """scoped_save merges scoped nodes into the existing baseline."""
        repomap_dir = tmp_path / ".repomap"
        baseline_dir = repomap_dir / "baselines" / "testrepo"
        baseline_dir.mkdir(parents=True)
        project_root = tmp_path / "repo"
        project_root.mkdir()

        # Save an existing baseline with 3 nodes
        existing = _make_graph("existing_a", "existing_b", "existing_c")
        mgr = BaselineManager()
        existing.metadata["baseline_version"] = "1.0"
        existing.metadata["project_root"] = str(project_root)
        current = baseline_dir / "baseline.json"
        current.write_text(existing.to_json(indent=2))

        # Scoped adds 1 new node
        scoped = _make_graph("new_node")
        mgr.scoped_save(
            repo_name="testrepo",
            scoped=scoped,
            project_root=project_root,
            repomap_dir=repomap_dir,
        )

        # Load the saved baseline and verify merge
        saved = RPGGraph.from_json(
            (baseline_dir / "baseline.json").read_text()
        )
        saved_names = {n.name for n in saved.nodes.values()}

        assert "existing_a" in saved_names
        assert "existing_b" in saved_names
        assert "existing_c" in saved_names
        assert "new_node" in saved_names
        assert saved.node_count == 4

    def test_scoped_save_no_existing_baseline(self, tmp_path: Path) -> None:
        """scoped_save works even when no prior baseline.json exists."""
        repomap_dir = tmp_path / ".repomap"
        project_root = tmp_path / "repo"
        project_root.mkdir()

        scoped = _make_graph("solo_node")
        mgr = BaselineManager()
        result = mgr.scoped_save(
            repo_name="newrepo",
            scoped=scoped,
            project_root=project_root,
            repomap_dir=repomap_dir,
        )

        assert result["node_count"] >= 1
        baseline = repomap_dir / "baselines" / "newrepo" / "baseline.json"
        assert baseline.exists()

    def test_scoped_save_returns_result_dict(self, tmp_path: Path) -> None:
        """scoped_save returns dict with expected keys."""
        repomap_dir = tmp_path / ".repomap"
        project_root = tmp_path / "repo"
        project_root.mkdir()

        scoped = _make_graph("node_x")
        mgr = BaselineManager()
        result = mgr.scoped_save(
            repo_name="testrepo",
            scoped=scoped,
            project_root=project_root,
            repomap_dir=repomap_dir,
        )

        assert "baseline_hash" in result
        assert "node_count" in result
        assert "file_count" in result
        assert "last_synced" in result
        assert "duration_seconds" in result

    def test_scoped_save_hash_starts_with_sha256(self, tmp_path: Path) -> None:
        """Returned baseline_hash is a sha256 fingerprint."""
        repomap_dir = tmp_path / ".repomap"
        project_root = tmp_path / "repo"
        project_root.mkdir()

        scoped = _make_graph("node_z")
        mgr = BaselineManager()
        result = mgr.scoped_save(
            repo_name="testrepo",
            scoped=scoped,
            project_root=project_root,
            repomap_dir=repomap_dir,
        )

        assert result["baseline_hash"].startswith("sha256:")
