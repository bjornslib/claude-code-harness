"""Tests for DeltaReportGenerator and DeltaSummary.

Tests cover:
- Delta summarization with various node status combinations
- Implementation ordering logic
- Dependency tracking (existing → new)
- Markdown report generation
- Defensive handling of missing/invalid delta_status metadata
- CLI integration of delta report
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import (
    DeltaStatus,
    EdgeType,
    NodeLevel,
    NodeType,
)
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.serena.delta_report import (
    DeltaReportGenerator,
    DeltaSummary,
    ImplementationItem,
    _get_delta_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    name: str,
    level: NodeLevel = NodeLevel.FEATURE,
    delta_status: str | None = None,
    folder_path: str | None = None,
    file_path: str | None = None,
    node_type: NodeType = NodeType.FUNCTIONALITY,
) -> RPGNode:
    """Create a minimal RPGNode with optional delta_status metadata."""
    metadata: dict = {}
    if delta_status is not None:
        metadata["delta_status"] = delta_status
    return RPGNode(
        name=name,
        level=level,
        node_type=node_type,
        folder_path=folder_path,
        file_path=file_path,
        metadata=metadata,
    )


def _make_edge(
    source_id, target_id, edge_type: EdgeType = EdgeType.DATA_FLOW
) -> RPGEdge:
    """Create a minimal RPGEdge."""
    return RPGEdge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
    )


def _build_graph_with_delta(
    existing: int = 2,
    modified: int = 1,
    new: int = 3,
    include_edges: bool = False,
) -> RPGGraph:
    """Build a test RPGGraph with specified delta status counts.

    Returns a graph with MODULE-level existing nodes, COMPONENT-level
    modified nodes, and FEATURE-level new nodes for variety.
    """
    graph = RPGGraph()
    nodes: list[RPGNode] = []

    for i in range(existing):
        n = _make_node(
            f"existing_mod_{i}",
            level=NodeLevel.MODULE,
            delta_status="existing",
            folder_path=f"src/existing_{i}",
        )
        graph.add_node(n)
        nodes.append(n)

    for i in range(modified):
        n = _make_node(
            f"modified_comp_{i}",
            level=NodeLevel.COMPONENT,
            delta_status="modified",
            folder_path=f"src/modified_{i}",
            file_path=f"src/modified_{i}/mod.py",
        )
        graph.add_node(n)
        nodes.append(n)

    for i in range(new):
        n = _make_node(
            f"new_feature_{i}",
            level=NodeLevel.FEATURE,
            delta_status="new",
            folder_path=f"src/new_{i}",
            file_path=f"src/new_{i}/feat.py",
        )
        graph.add_node(n)
        nodes.append(n)

    if include_edges and len(nodes) >= 4:
        # Create edge from new node → existing node (DATA_FLOW)
        graph.add_edge(
            _make_edge(nodes[3].id, nodes[0].id, EdgeType.DATA_FLOW)
        )
        # Create HIERARCHY edge from existing module → modified component
        graph.add_edge(
            _make_edge(nodes[0].id, nodes[2].id, EdgeType.HIERARCHY)
        )

    return graph


# ---------------------------------------------------------------------------
# DeltaSummary dataclass tests
# ---------------------------------------------------------------------------


class TestDeltaSummary:
    """Tests for the DeltaSummary dataclass."""

    def test_total_property(self):
        summary = DeltaSummary(existing=5, modified=3, new=7)
        assert summary.total == 15

    def test_actionable_property(self):
        summary = DeltaSummary(existing=5, modified=3, new=7)
        assert summary.actionable == 10

    def test_zero_defaults(self):
        summary = DeltaSummary()
        assert summary.existing == 0
        assert summary.modified == 0
        assert summary.new == 0
        assert summary.new_edges == 0
        assert summary.total == 0
        assert summary.actionable == 0

    def test_frozen(self):
        summary = DeltaSummary(existing=1)
        with pytest.raises(AttributeError):
            summary.existing = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _get_delta_status helper tests
# ---------------------------------------------------------------------------


class TestGetDeltaStatus:
    """Tests for the _get_delta_status helper function."""

    def test_existing_status(self):
        node = _make_node("n", delta_status="existing")
        assert _get_delta_status(node) == DeltaStatus.EXISTING

    def test_modified_status(self):
        node = _make_node("n", delta_status="modified")
        assert _get_delta_status(node) == DeltaStatus.MODIFIED

    def test_new_status(self):
        node = _make_node("n", delta_status="new")
        assert _get_delta_status(node) == DeltaStatus.NEW

    def test_missing_defaults_to_new(self):
        node = _make_node("n")
        assert _get_delta_status(node) == DeltaStatus.NEW

    def test_invalid_value_defaults_to_new(self):
        node = _make_node("n")
        node.metadata["delta_status"] = "bogus"
        assert _get_delta_status(node) == DeltaStatus.NEW


# ---------------------------------------------------------------------------
# DeltaReportGenerator.summarize tests
# ---------------------------------------------------------------------------


class TestSummarize:
    """Tests for DeltaReportGenerator.summarize()."""

    def test_empty_graph(self):
        gen = DeltaReportGenerator()
        summary = gen.summarize(RPGGraph())
        assert summary.total == 0
        assert summary.by_level == {}

    def test_all_existing(self):
        graph = _build_graph_with_delta(existing=5, modified=0, new=0)
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.existing == 5
        assert summary.modified == 0
        assert summary.new == 0
        assert summary.actionable == 0

    def test_all_new(self):
        graph = _build_graph_with_delta(existing=0, modified=0, new=4)
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.existing == 0
        assert summary.new == 4
        assert summary.actionable == 4

    def test_mixed_statuses(self):
        graph = _build_graph_with_delta(existing=2, modified=1, new=3)
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.existing == 2
        assert summary.modified == 1
        assert summary.new == 3
        assert summary.total == 6

    def test_by_level_breakdown(self):
        graph = _build_graph_with_delta(
            existing=2, modified=1, new=3
        )
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)

        # Existing nodes are MODULE level
        assert "MODULE" in summary.by_level
        assert summary.by_level["MODULE"]["existing"] == 2

        # Modified nodes are COMPONENT level
        assert "COMPONENT" in summary.by_level
        assert summary.by_level["COMPONENT"]["modified"] == 1

        # New nodes are FEATURE level
        assert "FEATURE" in summary.by_level
        assert summary.by_level["FEATURE"]["new"] == 3

    def test_edge_count_included(self):
        graph = _build_graph_with_delta(
            existing=2, modified=1, new=3, include_edges=True
        )
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.new_edges == 2

    def test_missing_delta_status_treated_as_new(self):
        """Nodes without delta_status should be counted as 'new'."""
        graph = RPGGraph()
        graph.add_node(_make_node("bare_node"))  # No delta_status
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.new == 1
        assert summary.existing == 0


# ---------------------------------------------------------------------------
# DeltaReportGenerator.implementation_order tests
# ---------------------------------------------------------------------------


class TestImplementationOrder:
    """Tests for DeltaReportGenerator.implementation_order()."""

    def test_empty_graph(self):
        gen = DeltaReportGenerator()
        order = gen.implementation_order(RPGGraph())
        assert order == []

    def test_only_existing_returns_empty(self):
        graph = _build_graph_with_delta(existing=5, modified=0, new=0)
        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert order == []

    def test_includes_new_and_modified(self):
        graph = _build_graph_with_delta(existing=1, modified=2, new=3)
        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert len(order) == 5  # 2 modified + 3 new

    def test_excludes_existing(self):
        graph = _build_graph_with_delta(existing=3, modified=0, new=2)
        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert len(order) == 2
        for item in order:
            assert item.delta_status != "existing"

    def test_level_ordering(self):
        """MODULE nodes before COMPONENT before FEATURE."""
        graph = RPGGraph()
        graph.add_node(
            _make_node("feat", NodeLevel.FEATURE, "new")
        )
        graph.add_node(
            _make_node("mod", NodeLevel.MODULE, "new")
        )
        graph.add_node(
            _make_node("comp", NodeLevel.COMPONENT, "new")
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert [item.level for item in order] == [
            "MODULE",
            "COMPONENT",
            "FEATURE",
        ]

    def test_modified_before_new_within_same_level(self):
        """Modified nodes should come before new within same level."""
        graph = RPGGraph()
        graph.add_node(
            _make_node("new_feat", NodeLevel.FEATURE, "new")
        )
        graph.add_node(
            _make_node("mod_feat", NodeLevel.FEATURE, "modified")
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert order[0].delta_status == "modified"
        assert order[1].delta_status == "new"

    def test_alphabetical_within_same_group(self):
        """Items with same level and status are ordered alphabetically."""
        graph = RPGGraph()
        graph.add_node(
            _make_node("zebra_feat", NodeLevel.FEATURE, "new")
        )
        graph.add_node(
            _make_node("alpha_feat", NodeLevel.FEATURE, "new")
        )
        graph.add_node(
            _make_node("middle_feat", NodeLevel.FEATURE, "new")
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        names = [item.name for item in order]
        assert names == ["alpha_feat", "middle_feat", "zebra_feat"]

    def test_dependency_tracking(self):
        """New nodes depending on existing nodes should list them."""
        graph = RPGGraph()
        existing = _make_node(
            "ExistingService", NodeLevel.MODULE, "existing"
        )
        new_node = _make_node(
            "NewFeature", NodeLevel.FEATURE, "new"
        )
        graph.add_node(existing)
        graph.add_node(new_node)
        graph.add_edge(
            _make_edge(new_node.id, existing.id, EdgeType.DATA_FLOW)
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert len(order) == 1
        assert order[0].name == "NewFeature"
        assert "ExistingService" in order[0].depends_on_existing

    def test_hierarchy_dependency_tracking(self):
        """HIERARCHY from existing parent → new child tracks dependency."""
        graph = RPGGraph()
        parent = _make_node(
            "ExistingModule", NodeLevel.MODULE, "existing"
        )
        child = _make_node(
            "NewComponent", NodeLevel.COMPONENT, "new"
        )
        graph.add_node(parent)
        graph.add_node(child)
        graph.add_edge(
            _make_edge(parent.id, child.id, EdgeType.HIERARCHY)
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert len(order) == 1
        assert "ExistingModule" in order[0].depends_on_existing

    def test_implementation_item_paths(self):
        """ImplementationItem should carry folder_path and file_path."""
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                "MyFeat",
                NodeLevel.FEATURE,
                "new",
                folder_path="src/pkg",
                file_path="src/pkg/feat.py",
            )
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert order[0].folder_path == "src/pkg"
        assert order[0].file_path == "src/pkg/feat.py"


# ---------------------------------------------------------------------------
# DeltaReportGenerator.generate (markdown) tests
# ---------------------------------------------------------------------------


class TestGenerateMarkdown:
    """Tests for DeltaReportGenerator.generate()."""

    def test_empty_graph_report(self):
        gen = DeltaReportGenerator()
        report = gen.generate(RPGGraph())
        assert "# Delta Report" in report
        assert "**Existing (unchanged)**: 0 nodes" in report
        assert "**New**: 0 nodes" in report

    def test_custom_title(self):
        gen = DeltaReportGenerator()
        report = gen.generate(RPGGraph(), title="My Custom Report")
        assert "# My Custom Report" in report

    def test_delta_counts_in_report(self):
        graph = _build_graph_with_delta(existing=5, modified=2, new=8)
        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "**Existing (unchanged)**: 5 nodes" in report
        assert "**Modified**: 2 nodes" in report
        assert "**New**: 8 nodes" in report

    def test_level_table_in_report(self):
        graph = _build_graph_with_delta(existing=1, modified=1, new=1)
        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "| Level | Existing | Modified | New |" in report
        assert "MODULE" in report
        assert "COMPONENT" in report
        assert "FEATURE" in report

    def test_implementation_order_in_report(self):
        graph = _build_graph_with_delta(
            existing=1, modified=1, new=2
        )
        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "## Implementation Order" in report
        assert "[MODIFIED]" in report
        assert "[NEW]" in report

    def test_no_implementation_order_when_disabled(self):
        graph = _build_graph_with_delta(existing=0, modified=0, new=3)
        gen = DeltaReportGenerator()
        report = gen.generate(
            graph, include_implementation_order=False
        )
        assert "## Implementation Order" not in report

    def test_up_to_date_message(self):
        """When all existing, report should say baseline is up to date."""
        graph = _build_graph_with_delta(existing=3, modified=0, new=0)
        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "baseline is up to date" in report

    def test_dependency_in_report(self):
        graph = RPGGraph()
        existing = _make_node(
            "SupabaseClient", NodeLevel.MODULE, "existing"
        )
        new_node = _make_node(
            "CreateCase", NodeLevel.FEATURE, "new"
        )
        graph.add_node(existing)
        graph.add_node(new_node)
        graph.add_edge(
            _make_edge(new_node.id, existing.id, EdgeType.DATA_FLOW)
        )

        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "[EXISTING] SupabaseClient" in report
        assert "depends on" in report

    def test_file_path_hint_in_report(self):
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                "SomeFeat",
                NodeLevel.FEATURE,
                "new",
                folder_path="src/feat",
                file_path="src/feat/main.py",
            )
        )

        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "(src/feat/main.py)" in report

    def test_folder_path_fallback_in_report(self):
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                "SomeMod",
                NodeLevel.MODULE,
                "new",
                folder_path="src/module",
            )
        )

        gen = DeltaReportGenerator()
        report = gen.generate(graph)
        assert "(src/module)" in report

    def test_footer_present(self):
        gen = DeltaReportGenerator()
        report = gen.generate(RPGGraph())
        assert "Generated by ZeroRepo DeltaReportGenerator" in report


# ---------------------------------------------------------------------------
# Edge case / robustness tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and defensive behaviour."""

    def test_node_with_no_metadata(self):
        """Node with completely empty metadata should be treated as new."""
        graph = RPGGraph()
        node = RPGNode(
            name="bare",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(node)
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.new == 1

    def test_node_with_invalid_delta_status(self):
        """Node with unrecognised delta_status value defaults to new."""
        graph = RPGGraph()
        node = RPGNode(
            name="bad_status",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            metadata={"delta_status": "unknown_value"},
        )
        graph.add_node(node)
        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.new == 1

    def test_large_graph_performance(self):
        """Summary of a 1000-node graph completes without error."""
        graph = RPGGraph()
        for i in range(1000):
            status = ["new", "existing", "modified"][i % 3]
            graph.add_node(_make_node(f"node_{i}", delta_status=status))

        gen = DeltaReportGenerator()
        summary = gen.summarize(graph)
        assert summary.total == 1000
        # ~333 each (334 new due to 0-indexing)
        assert summary.existing == 333
        assert summary.modified == 333
        assert summary.new == 334

    def test_edges_between_only_new_nodes(self):
        """Edges between two new nodes should not appear as existing deps."""
        graph = RPGGraph()
        n1 = _make_node("newA", delta_status="new")
        n2 = _make_node("newB", delta_status="new")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(_make_edge(n1.id, n2.id, EdgeType.DATA_FLOW))

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        for item in order:
            assert item.depends_on_existing == []

    def test_no_duplicate_dependency_names(self):
        """Multiple edges to same existing node should not duplicate name."""
        graph = RPGGraph()
        existing = _make_node("SharedService", NodeLevel.MODULE, "existing")
        new_node = _make_node("Consumer", NodeLevel.FEATURE, "new")
        graph.add_node(existing)
        graph.add_node(new_node)

        # Two edges from new → existing
        graph.add_edge(
            _make_edge(new_node.id, existing.id, EdgeType.DATA_FLOW)
        )
        graph.add_edge(
            _make_edge(new_node.id, existing.id, EdgeType.INVOCATION)
        )

        gen = DeltaReportGenerator()
        order = gen.implementation_order(graph)
        assert order[0].depends_on_existing.count("SharedService") == 1
