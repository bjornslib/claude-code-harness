"""Unit tests for cobuilder.repomap.context_filter — F3.2.

Tests cover:
- Direct match strategy (sd_file_references)
- Dependency expansion (modules depended on by direct matches)
- Keyword match (prd_keywords)
- Combined results: deduplicated and sorted (NEW/MODIFIED first)
- extract_dependency_graph helper
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from cobuilder.repomap.context_filter import (
    extract_dependency_graph,
    filter_relevant_modules,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_node(
    name: str,
    folder_path: str = "",
    file_path: str = "",
    node_type: str = "FUNCTIONALITY",
    level: str = "COMPONENT",
    delta_status: str = "existing",
    signature: str | None = None,
) -> tuple[str, dict]:
    """Return (node_id, node_dict) suitable for embedding in a baseline JSON."""
    node_id = _uuid()
    node: dict = {
        "id": node_id,
        "name": name,
        "level": level,
        "node_type": node_type,
        "parent_id": None,
        "folder_path": folder_path,
        "file_path": file_path,
        "interface_type": None,
        "signature": signature,
        "docstring": None,
        "implementation": None,
        "test_code": None,
        "test_status": "PENDING",
        "serena_validated": False,
        "actual_dependencies": [],
        "metadata": {"delta_status": delta_status} if delta_status != "existing" else {},
    }
    return node_id, node


def _make_edge(
    source_id: str,
    target_id: str,
    edge_type: str = "INVOCATION",
) -> tuple[str, dict]:
    edge_id = _uuid()
    edge: dict = {
        "id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type,
        "data_id": None,
        "data_type": None,
        "transformation": None,
        "validated": False,
    }
    return edge_id, edge


def _write_baseline(tmp_path: Path, nodes: list[tuple[str, dict]], edges: list[tuple[str, dict]] | None = None) -> Path:
    """Write a minimal baseline.json with the given nodes and edges."""
    nodes_section = {nid: ndata for nid, ndata in nodes}
    edges_section = {eid: edata for eid, edata in (edges or [])}
    data = {
        "nodes": nodes_section,
        "edges": edges_section,
        "metadata": {"baseline_version": "1.0"},
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(data, indent=2))
    return path


# ---------------------------------------------------------------------------
# filter_relevant_modules — Strategy 1: Direct match
# ---------------------------------------------------------------------------


class TestDirectMatch:
    def test_module_matched_by_sd_file_reference(self, tmp_path: Path) -> None:
        """Module whose folder appears in sd_file_references should be returned."""
        nid, ndata = _make_node("login_handler", folder_path="auth", file_path="auth/login.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=[],
            sd_file_references=["auth/login.py"],
        )

        names = [m["name"] for m in result]
        assert "auth" in names

    def test_unrelated_module_not_returned(self, tmp_path: Path) -> None:
        """Modules not matching any strategy should be excluded."""
        n1id, n1data = _make_node("auth_handler", folder_path="auth", file_path="auth/login.py")
        n2id, n2data = _make_node("payment_service", folder_path="payments", file_path="payments/process.py")
        baseline = _write_baseline(tmp_path, [(n1id, n1data), (n2id, n2data)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=[],
            sd_file_references=["auth/login.py"],
        )

        names = [m["name"] for m in result]
        assert "auth" in names
        assert "payments" not in names

    def test_partial_folder_prefix_matches(self, tmp_path: Path) -> None:
        """Reference 'cobuilder/pipeline' should match module 'cobuilder'."""
        nid, ndata = _make_node("gen", folder_path="cobuilder", file_path="cobuilder/pipeline/gen.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=[],
            sd_file_references=["cobuilder/pipeline/gen.py"],
        )

        names = [m["name"] for m in result]
        assert "cobuilder" in names


# ---------------------------------------------------------------------------
# filter_relevant_modules — Strategy 2: Dependency expansion
# ---------------------------------------------------------------------------


class TestDependencyExpansion:
    def test_dependency_of_direct_match_included(self, tmp_path: Path) -> None:
        """Module depended on by a directly-matched module should be included."""
        # auth depends on database via INVOCATION edge
        auth_id, auth_data = _make_node("auth_service", folder_path="auth", file_path="auth/service.py")
        db_id, db_data = _make_node("db_models", folder_path="database", file_path="database/models.py")
        edge_id, edge_data = _make_edge(auth_id, db_id, edge_type="INVOCATION")

        baseline = _write_baseline(tmp_path, [(auth_id, auth_data), (db_id, db_data)], [(edge_id, edge_data)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=[],
            sd_file_references=["auth/service.py"],
        )

        names = [m["name"] for m in result]
        assert "auth" in names
        assert "database" in names

    def test_unrelated_module_not_pulled_by_dependency(self, tmp_path: Path) -> None:
        """Module not depended on by direct matches should not be included."""
        auth_id, auth_data = _make_node("auth_handler", folder_path="auth", file_path="auth/login.py")
        payments_id, payments_data = _make_node("payments", folder_path="payments", file_path="payments/proc.py")
        # No edge between auth and payments
        baseline = _write_baseline(tmp_path, [(auth_id, auth_data), (payments_id, payments_data)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=[],
            sd_file_references=["auth/login.py"],
        )

        names = [m["name"] for m in result]
        assert "payments" not in names

    def test_data_flow_edge_counts_as_dependency(self, tmp_path: Path) -> None:
        """DATA_FLOW edges should trigger dependency expansion."""
        src_id, src_data = _make_node("pipeline", folder_path="pipeline", file_path="pipeline/run.py")
        tgt_id, tgt_data = _make_node("models", folder_path="models", file_path="models/base.py")
        edge_id, edge_data = _make_edge(src_id, tgt_id, edge_type="DATA_FLOW")

        baseline = _write_baseline(tmp_path, [(src_id, src_data), (tgt_id, tgt_data)], [(edge_id, edge_data)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=[],
            sd_file_references=["pipeline/run.py"],
        )

        names = [m["name"] for m in result]
        assert "models" in names


# ---------------------------------------------------------------------------
# filter_relevant_modules — Strategy 3: Keyword match
# ---------------------------------------------------------------------------


class TestKeywordMatch:
    def test_module_matched_by_prd_keyword(self, tmp_path: Path) -> None:
        """Module name containing a prd_keyword should be returned."""
        nid, ndata = _make_node("auth_handler", folder_path="auth", file_path="auth/handler.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=["auth"],
            sd_file_references=[],
        )

        names = [m["name"] for m in result]
        assert "auth" in names

    def test_partial_keyword_does_not_match(self, tmp_path: Path) -> None:
        """Keyword 'aut' should not match module 'auth' (word boundary required)."""
        nid, ndata = _make_node("auth_handler", folder_path="auth", file_path="auth/handler.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=["aut"],  # partial — no word boundary
            sd_file_references=[],
        )

        # 'auth' contains 'aut' but not at a word boundary — should NOT match
        names = [m["name"] for m in result]
        assert "auth" not in names

    def test_multiple_keywords_any_match_sufficient(self, tmp_path: Path) -> None:
        """Any keyword match is sufficient to include the module."""
        nid, ndata = _make_node("payments", folder_path="payments", file_path="payments/proc.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=["auth", "payments", "jwt"],
            sd_file_references=[],
        )

        names = [m["name"] for m in result]
        assert "payments" in names


# ---------------------------------------------------------------------------
# filter_relevant_modules — Combined: deduplication and sorting
# ---------------------------------------------------------------------------


class TestCombinedResults:
    def test_no_duplicates_when_matched_by_multiple_strategies(self, tmp_path: Path) -> None:
        """A module matched by both direct and keyword strategies should appear once."""
        nid, ndata = _make_node("auth", folder_path="auth", file_path="auth/service.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=["auth"],
            sd_file_references=["auth/service.py"],
        )

        names = [m["name"] for m in result]
        assert names.count("auth") == 1

    def test_new_modified_sorted_before_existing(self, tmp_path: Path) -> None:
        """Modules with delta NEW/MODIFIED should appear before existing ones."""
        n1id, n1data = _make_node("existing_mod", folder_path="existing", delta_status="existing")
        n2id, n2data = _make_node("new_mod", folder_path="new", delta_status="NEW")
        n3id, n3data = _make_node("modified_mod", folder_path="modified", delta_status="MODIFIED")
        baseline = _write_baseline(tmp_path, [(n1id, n1data), (n2id, n2data), (n3id, n3data)])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=["existing", "new", "modified"],
            sd_file_references=[],
        )

        names = [m["name"] for m in result]
        # NEW or MODIFIED must appear before existing
        existing_idx = names.index("existing") if "existing" in names else len(names)
        for changed in ("new", "modified"):
            if changed in names:
                assert names.index(changed) < existing_idx, (
                    f"'{changed}' should appear before 'existing' in sorted output"
                )

    def test_max_results_cap(self, tmp_path: Path) -> None:
        """Results should be capped at max_results."""
        nodes = [
            _make_node(f"mod{i}", folder_path=f"mod{i}", file_path=f"mod{i}/f.py")
            for i in range(10)
        ]
        baseline = _write_baseline(tmp_path, nodes)

        keywords = [f"mod{i}" for i in range(10)]
        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=keywords,
            sd_file_references=[],
            max_results=4,
        )

        assert len(result) <= 4

    def test_empty_baseline_returns_empty(self, tmp_path: Path) -> None:
        """Empty baseline should yield an empty result."""
        baseline = _write_baseline(tmp_path, [])

        result = filter_relevant_modules(
            baseline_path=baseline,
            prd_keywords=["auth"],
            sd_file_references=["auth/service.py"],
        )

        assert result == []


# ---------------------------------------------------------------------------
# extract_dependency_graph
# ---------------------------------------------------------------------------


class TestExtractDependencyGraph:
    def test_returns_edges_between_named_modules(self, tmp_path: Path) -> None:
        """Edges between modules in the provided list should be returned."""
        src_id, src_data = _make_node("source", folder_path="src", file_path="src/main.py")
        tgt_id, tgt_data = _make_node("target", folder_path="tgt", file_path="tgt/util.py")
        edge_id, edge_data = _make_edge(src_id, tgt_id, edge_type="INVOCATION")
        baseline = _write_baseline(tmp_path, [(src_id, src_data), (tgt_id, tgt_data)], [(edge_id, edge_data)])

        result = extract_dependency_graph(baseline, ["src", "tgt"])

        assert len(result) == 1
        assert result[0]["from"] == "src"
        assert result[0]["to"] == "tgt"
        assert result[0]["type"] == "depends"

    def test_excludes_modules_not_in_list(self, tmp_path: Path) -> None:
        """Edges involving modules not in module_names should be excluded."""
        src_id, src_data = _make_node("source", folder_path="src", file_path="src/main.py")
        tgt_id, tgt_data = _make_node("external", folder_path="ext", file_path="ext/util.py")
        edge_id, edge_data = _make_edge(src_id, tgt_id, edge_type="INVOCATION")
        baseline = _write_baseline(tmp_path, [(src_id, src_data), (tgt_id, tgt_data)], [(edge_id, edge_data)])

        result = extract_dependency_graph(baseline, ["src"])  # "ext" excluded

        assert result == []

    def test_deduplicates_edges(self, tmp_path: Path) -> None:
        """Multiple edges between the same module pair should produce one entry."""
        n1id, n1data = _make_node("a_handler", folder_path="a", file_path="a/h.py")
        n2id, n2data = _make_node("b_handler", folder_path="b", file_path="b/h.py")
        e1id, e1data = _make_edge(n1id, n2id, edge_type="INVOCATION")
        e2id, e2data = _make_edge(n1id, n2id, edge_type="INVOCATION")  # duplicate type
        baseline = _write_baseline(tmp_path, [(n1id, n1data), (n2id, n2data)], [(e1id, e1data), (e2id, e2data)])

        result = extract_dependency_graph(baseline, ["a", "b"])

        # Should be deduplicated to 1 entry
        assert len(result) == 1

    def test_empty_when_no_edges(self, tmp_path: Path) -> None:
        """No edges → empty dependency graph."""
        nid, ndata = _make_node("solo", folder_path="solo", file_path="solo/main.py")
        baseline = _write_baseline(tmp_path, [(nid, ndata)])

        result = extract_dependency_graph(baseline, ["solo"])

        assert result == []
