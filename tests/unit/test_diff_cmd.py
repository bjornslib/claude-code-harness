"""Unit tests for the zerorepo diff command (regression detection).

Tests cover:
    1. compare_graphs — core regression detection logic
    2. _extract_pipeline_file_paths — DOT codergen file path extraction
    3. generate_regression_dot — DOT output generation
    4. Integration: full diff workflow
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from zerorepo.cli.diff_cmd import (
    RegressionResult,
    _extract_pipeline_file_paths,
    _sanitize_dot_id,
    compare_graphs,
    generate_regression_dot,
)
from zerorepo.models.enums import NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    delta_status: str = "existing",
    file_path: str | None = None,
) -> RPGNode:
    """Create an RPGNode with the given name and delta_status."""
    kwargs: dict = dict(
        name=name,
        level=NodeLevel.COMPONENT,
        node_type=NodeType.FILE_AUGMENTED,
        metadata={"delta_status": delta_status},
    )
    if file_path:
        kwargs["folder_path"] = file_path.rsplit("/", 1)[0] if "/" in file_path else "."
        kwargs["file_path"] = file_path
    return RPGNode(**kwargs)


def _make_graph(*nodes: RPGNode) -> RPGGraph:
    """Build an RPGGraph from nodes."""
    g = RPGGraph()
    for n in nodes:
        g.add_node(n)
    return g


# ---------------------------------------------------------------------------
# 1. compare_graphs — regression detection
# ---------------------------------------------------------------------------


class TestCompareGraphs:
    """Core regression detection logic."""

    def test_no_regressions_when_all_existing(self):
        """All nodes existing in both graphs → no regressions."""
        before = _make_graph(
            _make_node("Alpha", delta_status="existing"),
            _make_node("Beta", delta_status="existing"),
        )
        after = _make_graph(
            _make_node("Alpha", delta_status="existing"),
            _make_node("Beta", delta_status="existing"),
        )
        result = compare_graphs(before, after)
        assert not result.has_regressions
        assert result.regressions == []
        assert result.unexpected_new == []

    def test_regression_existing_to_modified(self):
        """Node was EXISTING in before, MODIFIED in after → regression."""
        before = _make_graph(_make_node("Service", delta_status="existing"))
        after = _make_graph(_make_node("Service", delta_status="modified"))
        result = compare_graphs(before, after)
        assert result.has_regressions
        assert len(result.regressions) == 1
        assert result.regressions[0].name == "Service"

    def test_regression_existing_to_new(self):
        """Node was EXISTING in before, tagged NEW in after → regression."""
        before = _make_graph(_make_node("Module", delta_status="existing"))
        after = _make_graph(_make_node("Module", delta_status="new"))
        result = compare_graphs(before, after)
        assert len(result.regressions) == 1

    def test_no_regression_when_new_to_modified(self):
        """Node was NEW in before and MODIFIED in after → not a regression (already tracked)."""
        before = _make_graph(_make_node("Feature", delta_status="new"))
        after = _make_graph(_make_node("Feature", delta_status="modified"))
        result = compare_graphs(before, after)
        assert result.regressions == []

    def test_unexpected_new_node(self):
        """Node appears in after but not in before → unexpected_new."""
        before = _make_graph(_make_node("OldNode", delta_status="existing"))
        after = _make_graph(
            _make_node("OldNode", delta_status="existing"),
            _make_node("BrandNew", delta_status="new", file_path="src/brand_new.py"),
        )
        result = compare_graphs(before, after)
        assert len(result.unexpected_new) == 1
        assert result.unexpected_new[0].name == "BrandNew"
        assert result.regressions == []

    def test_unexpected_modified_not_in_before(self):
        """Node with status=modified that wasn't in before is also unexpected_new."""
        before = _make_graph(_make_node("Known", delta_status="existing"))
        after = _make_graph(
            _make_node("Known", delta_status="existing"),
            _make_node("Mystery", delta_status="modified"),
        )
        result = compare_graphs(before, after)
        assert len(result.unexpected_new) == 1
        assert result.unexpected_new[0].name == "Mystery"

    def test_multiple_regressions(self):
        """Multiple nodes regress simultaneously."""
        before = _make_graph(
            _make_node("A", delta_status="existing"),
            _make_node("B", delta_status="existing"),
            _make_node("C", delta_status="existing"),
        )
        after = _make_graph(
            _make_node("A", delta_status="modified"),
            _make_node("B", delta_status="existing"),  # stable — no regression
            _make_node("C", delta_status="new"),
        )
        result = compare_graphs(before, after)
        assert len(result.regressions) == 2
        names = {n.name for n in result.regressions}
        assert names == {"A", "C"}

    def test_total_count(self):
        """total_count sums regressions + unexpected_new."""
        before = _make_graph(_make_node("X", delta_status="existing"))
        after = _make_graph(
            _make_node("X", delta_status="modified"),
            _make_node("Y", delta_status="new"),
        )
        result = compare_graphs(before, after)
        assert result.total_count == 2  # 1 regression + 1 unexpected

    def test_empty_graphs_produce_no_result(self):
        """Both graphs empty → no regressions."""
        result = compare_graphs(RPGGraph(), RPGGraph())
        assert not result.has_regressions

    def test_empty_before_all_new_after(self):
        """All nodes in after are new; before is empty → all unexpected_new."""
        before = RPGGraph()
        after = _make_graph(
            _make_node("NewA", delta_status="new"),
            _make_node("NewB", delta_status="new"),
        )
        result = compare_graphs(before, after)
        assert result.regressions == []
        assert len(result.unexpected_new) == 2


class TestInScopeFilter:
    """Pipeline in-scope filter restricts which nodes are checked."""

    def test_filter_excludes_out_of_scope_nodes(self):
        """Nodes not in the in-scope filter are not reported as regressions."""
        before = _make_graph(
            _make_node("InScope", delta_status="existing", file_path="src/in_scope.py"),
            _make_node("OutScope", delta_status="existing", file_path="src/out.py"),
        )
        after = _make_graph(
            _make_node("InScope", delta_status="modified", file_path="src/in_scope.py"),
            _make_node("OutScope", delta_status="modified", file_path="src/out.py"),
        )
        # Only InScope is in the filter
        result = compare_graphs(before, after, in_scope_paths={"src/in_scope.py"})
        assert len(result.regressions) == 1
        assert result.regressions[0].name == "InScope"

    def test_empty_filter_disables_scope_check(self):
        """Passing None or empty set disables filtering (all nodes checked)."""
        before = _make_graph(
            _make_node("A", delta_status="existing", file_path="src/a.py"),
        )
        after = _make_graph(
            _make_node("A", delta_status="modified", file_path="src/a.py"),
        )
        result_none = compare_graphs(before, after, in_scope_paths=None)
        result_empty = compare_graphs(before, after, in_scope_paths=set())
        assert len(result_none.regressions) == 1
        assert len(result_empty.regressions) == 1

    def test_filter_ignores_nodes_without_file_path(self):
        """Nodes with no file_path have an empty string, which won't match any filter."""
        before = _make_graph(_make_node("NoPath", delta_status="existing"))
        after = _make_graph(_make_node("NoPath", delta_status="modified"))
        # NoPath has no file_path so "" not in {"src/a.py"} → excluded
        result = compare_graphs(before, after, in_scope_paths={"src/a.py"})
        assert result.regressions == []


# ---------------------------------------------------------------------------
# 2. _extract_pipeline_file_paths
# ---------------------------------------------------------------------------


class TestExtractPipelineFilePaths:
    """Extract file_path values from codergen nodes in a DOT pipeline."""

    def test_extracts_file_paths_from_codergen(self, tmp_path: Path):
        """file_path attributes from handler="codergen" nodes are extracted."""
        dot_content = textwrap.dedent("""\
            digraph "test" {
                impl_auth [
                    shape=box
                    handler="codergen"
                    file_path="src/auth/routes.py"
                    status="pending"
                ];
                impl_models [
                    shape=box
                    handler="codergen"
                    file_path="src/models/user.py"
                    status="pending"
                ];
            }
        """)
        dot_file = tmp_path / "pipeline.dot"
        dot_file.write_text(dot_content)

        paths = _extract_pipeline_file_paths(dot_file)
        assert paths == {"src/auth/routes.py", "src/models/user.py"}

    def test_ignores_non_codergen_nodes(self, tmp_path: Path):
        """Hexagon validation nodes (wait.human) are ignored."""
        dot_content = textwrap.dedent("""\
            digraph "test" {
                val_auth_tech [
                    shape=hexagon
                    handler="wait.human"
                    file_path="src/auth/routes.py"
                ];
                impl_auth [
                    shape=box
                    handler="codergen"
                    file_path="src/auth/impl.py"
                ];
            }
        """)
        dot_file = tmp_path / "pipeline.dot"
        dot_file.write_text(dot_content)

        paths = _extract_pipeline_file_paths(dot_file)
        assert paths == {"src/auth/impl.py"}

    def test_missing_file_returns_empty_set(self, tmp_path: Path):
        """Non-existent pipeline file returns empty set (logged, not raised)."""
        paths = _extract_pipeline_file_paths(tmp_path / "missing.dot")
        assert paths == set()

    def test_codergen_without_file_path_skipped(self, tmp_path: Path):
        """Codergen node missing file_path attribute is silently skipped."""
        dot_content = textwrap.dedent("""\
            digraph "test" {
                impl_no_fp [
                    shape=box
                    handler="codergen"
                ];
            }
        """)
        dot_file = tmp_path / "pipeline.dot"
        dot_file.write_text(dot_content)
        paths = _extract_pipeline_file_paths(dot_file)
        assert paths == set()

    def test_multiple_codergen_nodes(self, tmp_path: Path):
        """Multiple codergen nodes all contribute their paths."""
        dot_content = textwrap.dedent("""\
            digraph "test" {
                impl_a [ handler="codergen" file_path="a.py" ]
                impl_b [ handler="codergen" file_path="b.py" ]
                impl_c [ handler="codergen" file_path="c.py" ]
            }
        """)
        dot_file = tmp_path / "pipeline.dot"
        dot_file.write_text(dot_content)
        paths = _extract_pipeline_file_paths(dot_file)
        assert paths == {"a.py", "b.py", "c.py"}


# ---------------------------------------------------------------------------
# 3. generate_regression_dot
# ---------------------------------------------------------------------------


class TestGenerateRegressionDot:
    """DOT output generation from RegressionResult."""

    def test_no_regressions_emits_green_node(self):
        """When no regressions, a 'no_regressions' node with green fill is emitted."""
        result = RegressionResult(
            regressions=[], unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert "no_regressions" in dot
        assert "lightgreen" in dot
        assert "digraph" in dot

    def test_regression_nodes_are_red(self):
        """Regression nodes use fillcolor=red."""
        node = _make_node("RegService", delta_status="modified", file_path="src/svc.py")
        result = RegressionResult(
            regressions=[node], unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert "fillcolor=red" in dot
        assert "RegService" in dot
        assert "existing" in dot
        assert "modified" in dot

    def test_unexpected_new_nodes_present(self):
        """Unexpected new nodes appear in DOT output."""
        node = _make_node("NewComp", delta_status="new")
        result = RegressionResult(
            regressions=[], unexpected_new=[node], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert "NewComp" in dot
        assert "unexpected new component" in dot

    def test_dot_has_digraph_wrapper(self):
        """Output starts with digraph and ends with }."""
        result = RegressionResult(
            regressions=[], unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert dot.startswith("digraph")
        assert dot.strip().endswith("}")

    def test_file_path_in_output(self):
        """Node file_path appears in the DOT output when set."""
        node = _make_node("Svc", delta_status="modified", file_path="src/api/svc.py")
        result = RegressionResult(
            regressions=[node], unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert "src/api/svc.py" in dot

    def test_custom_label_used(self):
        """Custom label is included in the graph header."""
        result = RegressionResult(
            regressions=[], unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result, label="Epic 6 Regression Check")
        assert "Epic 6 Regression Check" in dot

    def test_multiple_regressions_all_present(self):
        """All regression nodes appear in DOT output."""
        nodes = [
            _make_node("Alpha", delta_status="modified"),
            _make_node("Beta", delta_status="new"),
        ]
        result = RegressionResult(
            regressions=nodes, unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert "Alpha" in dot
        assert "Beta" in dot

    def test_regression_type_attribute(self):
        """Status-change regressions have regression_type="status_change"."""
        node = _make_node("Svc", delta_status="modified")
        result = RegressionResult(
            regressions=[node], unexpected_new=[], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert 'regression_type="status_change"' in dot

    def test_unexpected_regression_type_attribute(self):
        """Unexpected new nodes have regression_type="unexpected_new"."""
        node = _make_node("New", delta_status="new")
        result = RegressionResult(
            regressions=[], unexpected_new=[node], in_scope_filter=set()
        )
        dot = generate_regression_dot(result)
        assert 'regression_type="unexpected_new"' in dot


# ---------------------------------------------------------------------------
# 4. _sanitize_dot_id
# ---------------------------------------------------------------------------


class TestSanitizeDotId:
    """DOT identifier sanitization."""

    def test_basic_name(self):
        assert _sanitize_dot_id("MyService") == "myservice"

    def test_spaces_replaced(self):
        assert _sanitize_dot_id("my service") == "my_service"

    def test_hyphens_replaced(self):
        assert _sanitize_dot_id("my-service") == "my_service"

    def test_leading_digit_prefixed(self):
        result = _sanitize_dot_id("123abc")
        assert result.startswith("n_")

    def test_empty_string(self):
        assert _sanitize_dot_id("") == "unnamed"

    def test_all_special_chars(self):
        assert _sanitize_dot_id("@#$%") == "unnamed"


# ---------------------------------------------------------------------------
# 5. Integration: load + compare using temp files
# ---------------------------------------------------------------------------


class TestDiffIntegration:
    """End-to-end: load JSON files, compare, produce DOT output."""

    def test_regression_detected_from_json_files(self, tmp_path: Path):
        """Full integration: load two JSON graphs, detect regression."""
        from zerorepo.cli.diff_cmd import _load_graph

        before_graph = _make_graph(
            _make_node("AuthService", delta_status="existing", file_path="src/auth.py"),
        )
        after_graph = _make_graph(
            _make_node("AuthService", delta_status="modified", file_path="src/auth.py"),
        )

        before_file = tmp_path / "before.json"
        after_file = tmp_path / "after.json"
        before_file.write_text(before_graph.to_json(), encoding="utf-8")
        after_file.write_text(after_graph.to_json(), encoding="utf-8")

        loaded_before = _load_graph(before_file)
        loaded_after = _load_graph(after_file)

        result = compare_graphs(loaded_before, loaded_after)
        assert result.has_regressions
        assert len(result.regressions) == 1
        assert result.regressions[0].name == "AuthService"

    def test_missing_file_raises_bad_parameter(self, tmp_path: Path):
        """Loading a missing file raises typer.BadParameter."""
        import typer
        from zerorepo.cli.diff_cmd import _load_graph

        with pytest.raises(typer.BadParameter):
            _load_graph(tmp_path / "nonexistent.json")

    def test_output_written_to_file(self, tmp_path: Path):
        """When output path is provided, DOT file is written there."""
        from rich.console import Console
        from zerorepo.cli.diff_cmd import run_diff

        before_graph = _make_graph(
            _make_node("A", delta_status="existing"),
        )
        after_graph = _make_graph(
            _make_node("A", delta_status="existing"),
        )

        before_file = tmp_path / "before.json"
        after_file = tmp_path / "after.json"
        output_file = tmp_path / "regression-check.dot"
        before_file.write_text(before_graph.to_json(), encoding="utf-8")
        after_file.write_text(after_graph.to_json(), encoding="utf-8")

        console = Console(stderr=True)
        result = run_diff(
            before_path=before_file,
            after_path=after_file,
            pipeline_path=None,
            output_path=output_file,
            console=console,
        )

        assert output_file.exists()
        content = output_file.read_text()
        assert "digraph" in content
        assert not result.has_regressions

    def test_pipeline_filter_integration(self, tmp_path: Path):
        """Pipeline DOT filter correctly restricts regression detection."""
        from rich.console import Console
        from zerorepo.cli.diff_cmd import run_diff

        pipeline_dot = textwrap.dedent("""\
            digraph "test" {
                impl_a [handler="codergen" file_path="src/a.py"]
            }
        """)
        pipeline_file = tmp_path / "pipeline.dot"
        pipeline_file.write_text(pipeline_dot)

        before_graph = _make_graph(
            _make_node("A", delta_status="existing", file_path="src/a.py"),
            _make_node("B", delta_status="existing", file_path="src/b.py"),
        )
        after_graph = _make_graph(
            _make_node("A", delta_status="modified", file_path="src/a.py"),
            _make_node("B", delta_status="modified", file_path="src/b.py"),
        )

        before_file = tmp_path / "before.json"
        after_file = tmp_path / "after.json"
        output_file = tmp_path / "out.dot"
        before_file.write_text(before_graph.to_json(), encoding="utf-8")
        after_file.write_text(after_graph.to_json(), encoding="utf-8")

        console = Console(stderr=True)
        result = run_diff(
            before_path=before_file,
            after_path=after_file,
            pipeline_path=pipeline_file,
            output_path=output_file,
            console=console,
        )

        # Only A is in scope; B is filtered out
        assert len(result.regressions) == 1
        assert result.regressions[0].name == "A"
