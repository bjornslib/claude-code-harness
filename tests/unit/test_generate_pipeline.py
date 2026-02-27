"""Unit tests for F2.1/F2.2/F2.4/F2.6 — RepoMap-native pipeline generation.

Tests cover:
- F2.1: ensure_baseline() auto-init when baseline missing
- F2.2: collect_repomap_nodes() MODIFIED/NEW filtering
- F2.4: cross_reference_beads() bead matching logic
- F2.6: generate_pipeline_dot() enriched DOT attribute rendering
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from cobuilder.pipeline.generate import (
    collect_repomap_nodes,
    cross_reference_beads,
    ensure_baseline,
    generate_pipeline_dot,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_baseline_json(nodes: list[dict]) -> str:
    """Build a minimal baseline.json string with the given node dicts."""
    nodes_section: dict[str, dict] = {}
    for node in nodes:
        node_id = node["id"]
        nodes_section[node_id] = {
            "id": node_id,
            "name": node.get("name", "unnamed"),
            "level": node.get("level", "COMPONENT"),
            "node_type": node.get("node_type", "FUNCTIONALITY"),
            "parent_id": None,
            "folder_path": node.get("folder_path"),
            "file_path": node.get("file_path"),
            "interface_type": node.get("interface_type"),
            "signature": None,
            "docstring": None,
            "implementation": None,
            "test_code": None,
            "test_status": "pending",
            "serena_validated": False,
            "actual_dependencies": [],
            "metadata": node.get("metadata", {}),
        }

    data = {
        "nodes": nodes_section,
        "edges": {},
        "metadata": {
            "baseline_generated_at": "2026-01-01T00:00:00+00:00",
            "project_root": "/tmp/test",
            "baseline_version": "1.0",
        },
    }
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# F2.1 — ensure_baseline
# ---------------------------------------------------------------------------


class TestEnsureBaseline:
    """Tests for ensure_baseline()."""

    def test_returns_path_when_baseline_exists(self, tmp_path: Path) -> None:
        """Should return the baseline path without calling bridge when file exists."""
        repo_name = "testrepo"
        baseline_dir = tmp_path / ".repomap" / "baselines" / repo_name
        baseline_dir.mkdir(parents=True)
        baseline_file = baseline_dir / "baseline.json"
        baseline_file.write_text("{}")

        with patch("cobuilder.pipeline.generate.bridge") as mock_bridge:
            result = ensure_baseline(repo_name, tmp_path)

        assert result == baseline_file
        mock_bridge.init_repo.assert_not_called()
        mock_bridge.sync_baseline.assert_not_called()

    def test_auto_init_when_baseline_missing(self, tmp_path: Path) -> None:
        """Should call bridge.init_repo + bridge.sync_baseline when baseline absent."""
        repo_name = "newrepo"

        # After sync_baseline is called, simulate the file being created
        baseline_dir = tmp_path / ".repomap" / "baselines" / repo_name
        baseline_file = baseline_dir / "baseline.json"

        def fake_sync_baseline(name: str, *, project_root: Path) -> dict:
            baseline_dir.mkdir(parents=True, exist_ok=True)
            baseline_file.write_text("{}")
            return {}

        with patch("cobuilder.pipeline.generate.bridge") as mock_bridge:
            mock_bridge.sync_baseline.side_effect = fake_sync_baseline
            result = ensure_baseline(repo_name, tmp_path)

        mock_bridge.init_repo.assert_called_once_with(
            repo_name, tmp_path, project_root=tmp_path, force=True
        )
        mock_bridge.sync_baseline.assert_called_once_with(repo_name, project_root=tmp_path)
        assert result == baseline_file

    def test_returns_correct_path_structure(self, tmp_path: Path) -> None:
        """Returned path should follow .repomap/baselines/{repo_name}/baseline.json."""
        repo_name = "myrepo"
        baseline_dir = tmp_path / ".repomap" / "baselines" / repo_name
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "baseline.json").write_text("{}")

        with patch("cobuilder.pipeline.generate.bridge"):
            result = ensure_baseline(repo_name, tmp_path)

        assert result.name == "baseline.json"
        assert result.parent.name == repo_name
        assert result.parent.parent.name == "baselines"

    def test_accepts_string_project_root(self, tmp_path: Path) -> None:
        """project_root can be passed as a str (not only Path)."""
        repo_name = "strrepo"
        baseline_dir = tmp_path / ".repomap" / "baselines" / repo_name
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "baseline.json").write_text("{}")

        with patch("cobuilder.pipeline.generate.bridge"):
            result = ensure_baseline(repo_name, str(tmp_path))

        assert isinstance(result, Path)
        assert result.exists()


# ---------------------------------------------------------------------------
# F2.2 — collect_repomap_nodes
# ---------------------------------------------------------------------------


class TestCollectRepomapNodes:
    """Tests for collect_repomap_nodes()."""

    def _write_baseline(self, tmp_path: Path, repo_name: str, nodes: list[dict]) -> Path:
        baseline_dir = tmp_path / ".repomap" / "baselines" / repo_name
        baseline_dir.mkdir(parents=True)
        baseline_file = baseline_dir / "baseline.json"
        baseline_file.write_text(_make_baseline_json(nodes))
        return baseline_file

    def test_returns_modified_and_new_nodes_only(self, tmp_path: Path) -> None:
        """Should filter to MODIFIED and NEW delta_status nodes."""
        repo_name = "filterrepo"
        nodes = [
            {
                "id": "aaaa-0001",
                "name": "existing_module",
                "metadata": {"delta_status": "EXISTING"},
            },
            {
                "id": "aaaa-0002",
                "name": "modified_module",
                "metadata": {"delta_status": "MODIFIED"},
            },
            {
                "id": "aaaa-0003",
                "name": "new_module",
                "metadata": {"delta_status": "NEW"},
            },
        ]
        self._write_baseline(tmp_path, repo_name, nodes)

        with patch("cobuilder.pipeline.generate.bridge"):
            result = collect_repomap_nodes(repo_name, tmp_path)

        titles = {n["title"] for n in result}
        assert "modified_module" in titles
        assert "new_module" in titles
        assert "existing_module" not in titles

    def test_returns_all_nodes_when_no_delta_status(self, tmp_path: Path) -> None:
        """If no nodes have delta_status, all nodes should be returned (duplicate guard)."""
        # This test intentionally duplicates the real test below to ensure the
        # fixture helper works; the real assertion is in the _real variant.
        repo_name = "nodeltarepo"
        nodes = [
            {"id": "bbbb-0001", "name": "alpha", "metadata": {}},
            {"id": "bbbb-0002", "name": "beta", "metadata": {}},
        ]
        self._write_baseline(tmp_path, repo_name, nodes)

        with patch("cobuilder.pipeline.generate.bridge"):
            result = collect_repomap_nodes(repo_name, tmp_path)

        assert len(result) == 2

    def test_returns_all_nodes_when_no_delta_status_real(self, tmp_path: Path) -> None:
        """If no nodes have delta_status, all nodes should be returned (real call)."""
        repo_name = "nodeltarepo2"
        nodes = [
            {"id": "cccc-0001", "name": "alpha", "metadata": {}},
            {"id": "cccc-0002", "name": "beta", "metadata": {}},
        ]
        self._write_baseline(tmp_path, repo_name, nodes)

        with patch("cobuilder.pipeline.generate.bridge"):
            result = collect_repomap_nodes(repo_name, tmp_path)

        assert len(result) == 2
        titles = {n["title"] for n in result}
        assert "alpha" in titles
        assert "beta" in titles

    def test_node_dict_keys(self, tmp_path: Path) -> None:
        """Each returned node dict must have the required keys."""
        repo_name = "keysrepo"
        nodes = [
            {
                "id": "dddd-0001",
                "name": "auth_handler",
                "folder_path": "auth/handlers",
                "file_path": "auth/handlers/login.py",
                "metadata": {"delta_status": "NEW"},
            }
        ]
        self._write_baseline(tmp_path, repo_name, nodes)

        with patch("cobuilder.pipeline.generate.bridge"):
            result = collect_repomap_nodes(repo_name, tmp_path)

        assert len(result) == 1
        node = result[0]
        assert "node_id" in node
        assert "title" in node
        assert "file_path" in node
        assert "delta_status" in node
        assert "module" in node
        assert "interfaces" in node

    def test_module_extracted_from_folder_path(self, tmp_path: Path) -> None:
        """module should be the first segment of folder_path."""
        repo_name = "modulerepo"
        nodes = [
            {
                "id": "eeee-0001",
                "name": "service",
                "folder_path": "cobuilder/pipeline",
                "metadata": {"delta_status": "MODIFIED"},
            }
        ]
        self._write_baseline(tmp_path, repo_name, nodes)

        with patch("cobuilder.pipeline.generate.bridge"):
            result = collect_repomap_nodes(repo_name, tmp_path)

        assert result[0]["module"] == "cobuilder"

    def test_interfaces_from_metadata(self, tmp_path: Path) -> None:
        """interfaces key should be populated from metadata['interfaces'] list."""
        repo_name = "ifacerepo"
        nodes = [
            {
                "id": "ffff-0001",
                "name": "iface_node",
                "metadata": {
                    "delta_status": "NEW",
                    "interfaces": ["IFoo", "IBar"],
                },
            }
        ]
        self._write_baseline(tmp_path, repo_name, nodes)

        with patch("cobuilder.pipeline.generate.bridge"):
            result = collect_repomap_nodes(repo_name, tmp_path)

        assert result[0]["interfaces"] == ["IFoo", "IBar"]


# ---------------------------------------------------------------------------
# F2.4 — cross_reference_beads
# ---------------------------------------------------------------------------


class TestCrossReferenceBeads:
    """Tests for cross_reference_beads()."""

    def _node(self, title: str, file_path: str = "") -> dict:
        return {
            "node_id": "test-uuid",
            "title": title,
            "file_path": file_path,
            "delta_status": "MODIFIED",
            "module": "cobuilder",
            "interfaces": [],
        }

    def _bead(self, bead_id: str, title: str, description: str = "", priority: int = 2) -> dict:
        return {
            "id": bead_id,
            "title": title,
            "description": description,
            "priority": priority,
            "status": "open",
            "issue_type": "task",
        }

    def test_matched_by_word_overlap(self) -> None:
        """A bead with ≥50% word overlap should be matched."""
        nodes = [self._node("implement auth handler")]
        beads = [self._bead("cb-001", "implement auth module", priority=1)]

        with patch("cobuilder.pipeline.generate.get_beads_data", return_value=beads):
            result = cross_reference_beads(nodes, "PRD-TEST-001")

        assert result[0]["bead_id"] == "cb-001"
        assert result[0]["priority"] == 1

    def test_no_match_sets_bead_id_none(self) -> None:
        """Nodes with no matching bead should have bead_id=None."""
        nodes = [self._node("completely unrelated xyz")]
        beads = [self._bead("cb-001", "something entirely different")]

        with patch("cobuilder.pipeline.generate.get_beads_data", return_value=beads):
            result = cross_reference_beads(nodes, "PRD-TEST-001")

        assert result[0]["bead_id"] is None
        assert result[0]["priority"] is None

    def test_matched_by_file_path_in_description(self) -> None:
        """A bead whose description mentions the node file_path should match."""
        nodes = [self._node("some node", file_path="cobuilder/pipeline/generate.py")]
        beads = [
            self._bead(
                "cb-002",
                "update pipeline",
                description="Modify cobuilder/pipeline/generate.py to add enrichment",
            )
        ]

        with patch("cobuilder.pipeline.generate.get_beads_data", return_value=beads):
            result = cross_reference_beads(nodes, "PRD-TEST-001")

        assert result[0]["bead_id"] == "cb-002"

    def test_empty_beads_returns_unmatched(self) -> None:
        """When bd list returns empty, all nodes should be unmatched."""
        nodes = [self._node("anything")]

        with patch("cobuilder.pipeline.generate.get_beads_data", return_value=[]):
            result = cross_reference_beads(nodes, "PRD-TEST-001")

        assert result[0]["bead_id"] is None

    def test_does_not_mutate_input_nodes(self) -> None:
        """Input node dicts must not be modified in-place."""
        original = self._node("auth service")
        nodes = [original]
        beads = [self._bead("cb-003", "auth service implementation")]

        with patch("cobuilder.pipeline.generate.get_beads_data", return_value=beads):
            cross_reference_beads(nodes, "PRD-TEST-001")

        assert "bead_id" not in original

    def test_subprocess_called_for_beads(self) -> None:
        """Should invoke get_beads_data which runs bd list --json via subprocess."""
        nodes = [self._node("test node")]

        with patch("cobuilder.pipeline.generate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")
            result = cross_reference_beads(nodes, "PRD-TEST-001")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "bd" in call_args
        assert "--json" in call_args


# ---------------------------------------------------------------------------
# F2.6 — generate_pipeline_dot enriched attributes
# ---------------------------------------------------------------------------


class TestGeneratePipelineDot:
    """Tests for the updated generate_pipeline_dot() signature and DOT output."""

    def _make_node(
        self,
        title: str = "implement feature",
        file_path: str = "cobuilder/feature.py",
        delta_status: str = "MODIFIED",
        interfaces: list[str] | None = None,
        change_summary: str = "",
        worker_type: str = "",
        bead_id: str | None = None,
    ) -> dict:
        return {
            "node_id": "uuid-1234",
            "title": title,
            "file_path": file_path,
            "delta_status": delta_status,
            "module": "cobuilder",
            "interfaces": interfaces or [],
            "change_summary": change_summary,
            "worker_type": worker_type,
            "bead_id": bead_id,
            "priority": None,
        }

    def test_new_signature_accepted(self) -> None:
        """generate_pipeline_dot should accept the new nodes + solution_design params."""
        nodes = [self._make_node()]
        dot = generate_pipeline_dot(
            prd_ref="PRD-TEST-001",
            nodes=nodes,
            solution_design="docs/sd.md",
        )
        assert "PRD-TEST-001" in dot

    def test_file_path_in_dot_output(self) -> None:
        """file_path should appear as a DOT attribute on the codergen node."""
        nodes = [self._make_node(file_path="cobuilder/pipeline/generate.py")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert 'file_path="cobuilder/pipeline/generate.py"' in dot

    def test_delta_status_in_dot_output(self) -> None:
        """delta_status should appear as a DOT attribute on the codergen node."""
        nodes = [self._make_node(delta_status="NEW")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert 'delta_status="NEW"' in dot

    def test_interfaces_in_dot_output(self) -> None:
        """interfaces should appear comma-joined in the DOT output."""
        nodes = [self._make_node(interfaces=["IFoo", "IBar"])]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert "IFoo, IBar" in dot

    def test_change_summary_in_dot_output(self) -> None:
        """change_summary should appear as a DOT attribute when non-empty."""
        nodes = [self._make_node(change_summary="Adds delta tracking support")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert "Adds delta tracking support" in dot

    def test_worker_type_explicit_in_dot_output(self) -> None:
        """An explicit worker_type on the node should appear in DOT output."""
        nodes = [self._make_node(worker_type="frontend-dev-expert")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert 'worker_type="frontend-dev-expert"' in dot

    def test_worker_type_inferred_when_absent(self) -> None:
        """worker_type should be inferred from title when not explicitly set."""
        nodes = [self._make_node(title="implement python backend api", worker_type="")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert 'worker_type="backend-solutions-engineer"' in dot

    def test_solution_design_on_codergen_node(self) -> None:
        """solution_design path should appear on each codergen node."""
        nodes = [self._make_node()]
        dot = generate_pipeline_dot(
            prd_ref="PRD-TEST-001",
            nodes=nodes,
            solution_design="docs/solution-design.md",
        )
        assert 'solution_design="docs/solution-design.md"' in dot

    def test_solution_design_on_graph_level(self) -> None:
        """solution_design should also be a graph-level attribute."""
        nodes = [self._make_node()]
        dot = generate_pipeline_dot(
            prd_ref="PRD-TEST-001",
            nodes=nodes,
            solution_design="docs/sd.md",
        )
        # Graph-level attr appears in the graph [ ... ] block before node defs
        graph_section = dot.split("graph [")[1].split("];")[0]
        assert "solution_design" in graph_section

    def test_scaffold_structure_preserved(self) -> None:
        """Standard scaffold nodes (start, validate_graph, init_env, finalize) must be present."""
        nodes = [self._make_node()]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)

        assert "start [" in dot
        assert "validate_graph [" in dot
        assert "init_env [" in dot
        assert "finalize [" in dot

    def test_validation_hexagons_present(self) -> None:
        """Each task should generate technical and business validation hexagons."""
        nodes = [self._make_node(title="auth feature")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)

        assert 'shape=hexagon' in dot
        assert "Technical\\nValidation" in dot
        assert "Business\\nValidation" in dot

    def test_empty_nodes_generates_placeholder(self) -> None:
        """With no nodes, a placeholder codergen node should be emitted."""
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=[])
        assert "impl_placeholder" in dot
        assert 'bead_id="UNASSIGNED"' in dot

    def test_multiple_nodes_parallel_structure(self) -> None:
        """Two or more nodes should produce a parallel fan-out/fan-in structure."""
        nodes = [
            self._make_node(title="feature alpha"),
            self._make_node(title="feature beta"),
        ]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)

        assert "parallel_start" in dot
        assert "join_validation" in dot

    def test_no_file_path_attr_when_empty(self) -> None:
        """file_path attribute should be omitted when the node has no file_path."""
        nodes = [self._make_node(file_path="")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert "file_path=" not in dot

    def test_no_delta_status_attr_when_empty(self) -> None:
        """delta_status attribute should be omitted when empty."""
        nodes = [self._make_node(delta_status="")]
        dot = generate_pipeline_dot(prd_ref="PRD-TEST-001", nodes=nodes)
        assert "delta_status=" not in dot
