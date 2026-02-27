"""Unit tests for graph_ops module."""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from cobuilder.repomap.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode

from cobuilder.repomap.graph_ops.exceptions import CycleDetectedError
from cobuilder.repomap.graph_ops.topological import topological_sort, detect_cycles
from cobuilder.repomap.graph_ops.subgraph import (
    extract_subgraph_by_module,
    extract_subgraph_by_level,
    extract_subgraph_by_type,
)
from cobuilder.repomap.graph_ops.traversal import (
    get_ancestors,
    get_descendants,
    get_direct_dependencies,
)
from cobuilder.repomap.graph_ops.filtering import (
    filter_nodes,
    filter_by_status,
    filter_by_validation,
    filter_by_level,
)
from cobuilder.repomap.graph_ops.diff import diff_dependencies
from cobuilder.repomap.graph_ops.serialization import serialize_graph, deserialize_graph


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_node(
    *,
    name: str = "node",
    level: NodeLevel = NodeLevel.COMPONENT,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    node_id: UUID | None = None,
    parent_id: UUID | None = None,
    test_status: TestStatus = TestStatus.PENDING,
    serena_validated: bool = False,
    actual_dependencies: list[UUID] | None = None,
) -> RPGNode:
    kwargs: dict = dict(
        name=name,
        level=level,
        node_type=node_type,
        test_status=test_status,
        serena_validated=serena_validated,
        actual_dependencies=actual_dependencies or [],
    )
    if node_id is not None:
        kwargs["id"] = node_id
    if parent_id is not None:
        kwargs["parent_id"] = parent_id
    return RPGNode(**kwargs)


def _make_edge(
    source_id: UUID,
    target_id: UUID,
    edge_type: EdgeType = EdgeType.HIERARCHY,
    *,
    edge_id: UUID | None = None,
    data_id: str | None = None,
    data_type: str | None = None,
) -> RPGEdge:
    kwargs: dict = dict(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
    )
    if edge_id is not None:
        kwargs["id"] = edge_id
    if data_id is not None:
        kwargs["data_id"] = data_id
    if data_type is not None:
        kwargs["data_type"] = data_type
    return RPGEdge(**kwargs)


def _build_linear_graph() -> tuple[RPGGraph, list[UUID]]:
    """Build a simple linear DAG: A -> B -> C (HIERARCHY edges)."""
    ids = [uuid4() for _ in range(3)]
    graph = RPGGraph()
    for i, uid in enumerate(ids):
        graph.add_node(
            _make_node(name=f"node_{i}", node_id=uid, level=NodeLevel.MODULE)
        )
    graph.add_edge(_make_edge(ids[0], ids[1], EdgeType.HIERARCHY))
    graph.add_edge(_make_edge(ids[1], ids[2], EdgeType.HIERARCHY))
    return graph, ids


def _build_diamond_graph() -> tuple[RPGGraph, list[UUID]]:
    """Build a diamond DAG:
       A
      / \\
     B   C
      \\ /
       D
    All edges are DATA_FLOW.
    """
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    graph = RPGGraph()
    for uid, name in [(a, "A"), (b, "B"), (c, "C"), (d, "D")]:
        graph.add_node(_make_node(name=name, node_id=uid))
    graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
    graph.add_edge(_make_edge(a, c, EdgeType.DATA_FLOW))
    graph.add_edge(_make_edge(b, d, EdgeType.DATA_FLOW))
    graph.add_edge(_make_edge(c, d, EdgeType.DATA_FLOW))
    return graph, [a, b, c, d]


# =========================================================================== #
#                            Task 1.2.1: Topological Sort                      #
# =========================================================================== #


class TestTopologicalSort:
    """Tests for topological_sort and detect_cycles."""

    def test_linear_graph_order(self) -> None:
        graph, ids = _build_linear_graph()
        result = topological_sort(graph)
        assert result.index(ids[0]) < result.index(ids[1])
        assert result.index(ids[1]) < result.index(ids[2])

    def test_diamond_graph_order(self) -> None:
        graph, ids = _build_diamond_graph()
        a, b, c, d = ids
        result = topological_sort(graph)
        assert result.index(a) < result.index(b)
        assert result.index(a) < result.index(c)
        assert result.index(b) < result.index(d)
        assert result.index(c) < result.index(d)

    def test_single_node(self) -> None:
        graph = RPGGraph()
        uid = uuid4()
        graph.add_node(_make_node(name="single", node_id=uid))
        result = topological_sort(graph)
        assert result == [uid]

    def test_empty_graph(self) -> None:
        graph = RPGGraph()
        result = topological_sort(graph)
        assert result == []

    def test_disconnected_nodes(self) -> None:
        graph = RPGGraph()
        ids = [uuid4() for _ in range(3)]
        for i, uid in enumerate(ids):
            graph.add_node(_make_node(name=f"n{i}", node_id=uid))
        result = topological_sort(graph)
        assert set(result) == set(ids)
        assert len(result) == 3

    def test_ignores_non_relevant_edge_types(self) -> None:
        """ORDERING, INHERITANCE, INVOCATION edges should be ignored."""
        graph, ids = _build_linear_graph()
        # Add a reverse INVOCATION edge (C -> A)
        graph.add_edge(_make_edge(ids[2], ids[0], EdgeType.INVOCATION))
        result = topological_sort(graph)
        # Should still succeed – INVOCATION is not considered
        assert result.index(ids[0]) < result.index(ids[2])

    def test_cycle_raises_error(self) -> None:
        graph = RPGGraph()
        a, b, c = uuid4(), uuid4(), uuid4()
        for uid, name in [(a, "A"), (b, "B"), (c, "C")]:
            graph.add_node(_make_node(name=name, node_id=uid))
        graph.add_edge(_make_edge(a, b, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(b, c, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(c, a, EdgeType.HIERARCHY))

        with pytest.raises(CycleDetectedError):
            topological_sort(graph)

    def test_detect_cycles_no_cycle(self) -> None:
        graph, _ = _build_linear_graph()
        cycles = detect_cycles(graph)
        assert cycles == []

    def test_detect_cycles_finds_cycle(self) -> None:
        graph = RPGGraph()
        a, b = uuid4(), uuid4()
        graph.add_node(_make_node(name="A", node_id=a))
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(b, a, EdgeType.DATA_FLOW))
        cycles = detect_cycles(graph)
        assert len(cycles) >= 1
        assert set(cycles[0]) == {a, b}

    def test_detect_cycles_self_loop_not_possible(self) -> None:
        """Self-loops are rejected by RPGEdge validation, so no test needed for
        cycle detection. Just verify the model rejects them."""
        uid = uuid4()
        with pytest.raises(ValueError, match="Self-loop"):
            RPGEdge(source_id=uid, target_id=uid, edge_type=EdgeType.HIERARCHY)

    def test_all_nodes_in_result(self) -> None:
        graph, ids = _build_diamond_graph()
        result = topological_sort(graph)
        assert set(result) == set(ids)


# =========================================================================== #
#                       Task 1.2.2: Subgraph Extraction                        #
# =========================================================================== #


class TestSubgraphExtraction:
    """Tests for subgraph extraction functions."""

    def test_extract_by_module_basic(self) -> None:
        graph = RPGGraph()
        mod = uuid4()
        comp1, comp2, other = uuid4(), uuid4(), uuid4()
        graph.add_node(
            _make_node(name="module", node_id=mod, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="comp1", node_id=comp1, parent_id=mod)
        )
        graph.add_node(
            _make_node(name="comp2", node_id=comp2, parent_id=comp1)
        )
        graph.add_node(
            _make_node(name="other", node_id=other, level=NodeLevel.MODULE)
        )
        graph.add_edge(_make_edge(mod, comp1, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(comp1, comp2, EdgeType.HIERARCHY))
        # Edge not in subgraph
        graph.add_edge(_make_edge(other, mod, EdgeType.DATA_FLOW))

        sub = extract_subgraph_by_module(graph, mod)
        assert set(sub.nodes.keys()) == {mod, comp1, comp2}
        assert sub.edge_count == 2  # Only the two HIERARCHY edges

    def test_extract_by_module_preserves_cross_edges(self) -> None:
        """Non-HIERARCHY edges between extracted nodes should be preserved."""
        graph = RPGGraph()
        mod, child1, child2 = uuid4(), uuid4(), uuid4()
        graph.add_node(
            _make_node(name="mod", node_id=mod, level=NodeLevel.MODULE)
        )
        graph.add_node(_make_node(name="c1", node_id=child1))
        graph.add_node(_make_node(name="c2", node_id=child2))
        graph.add_edge(_make_edge(mod, child1, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(mod, child2, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(child1, child2, EdgeType.DATA_FLOW))

        sub = extract_subgraph_by_module(graph, mod)
        assert sub.edge_count == 3

    def test_extract_by_module_not_found(self) -> None:
        graph = RPGGraph()
        with pytest.raises(ValueError, match="not found"):
            extract_subgraph_by_module(graph, uuid4())

    def test_extract_by_module_leaf_node(self) -> None:
        """A leaf node with no HIERARCHY children returns just itself."""
        graph = RPGGraph()
        leaf = uuid4()
        graph.add_node(_make_node(name="leaf", node_id=leaf))
        sub = extract_subgraph_by_module(graph, leaf)
        assert set(sub.nodes.keys()) == {leaf}
        assert sub.edge_count == 0

    def test_extract_by_level(self) -> None:
        graph = RPGGraph()
        m1, m2, c1 = uuid4(), uuid4(), uuid4()
        graph.add_node(
            _make_node(name="m1", node_id=m1, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="m2", node_id=m2, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="c1", node_id=c1, level=NodeLevel.COMPONENT)
        )
        graph.add_edge(_make_edge(m1, m2, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(m1, c1, EdgeType.HIERARCHY))

        sub = extract_subgraph_by_level(graph, NodeLevel.MODULE)
        assert set(sub.nodes.keys()) == {m1, m2}
        assert sub.edge_count == 1  # Only m1->m2 edge

    def test_extract_by_level_empty(self) -> None:
        graph, _ = _build_linear_graph()  # All MODULE nodes
        sub = extract_subgraph_by_level(graph, NodeLevel.FEATURE)
        assert sub.node_count == 0
        assert sub.edge_count == 0

    def test_extract_by_type(self) -> None:
        graph = RPGGraph()
        f1, f2, fa = uuid4(), uuid4(), uuid4()
        graph.add_node(
            _make_node(
                name="f1",
                node_id=f1,
                node_type=NodeType.FUNCTIONALITY,
            )
        )
        graph.add_node(
            _make_node(
                name="f2",
                node_id=f2,
                node_type=NodeType.FUNCTIONALITY,
            )
        )
        graph.add_node(
            _make_node(
                name="fa",
                node_id=fa,
                node_type=NodeType.FOLDER_AUGMENTED,
            )
        )
        graph.add_edge(_make_edge(f1, f2, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(f1, fa, EdgeType.DATA_FLOW))

        sub = extract_subgraph_by_type(graph, NodeType.FUNCTIONALITY)
        assert set(sub.nodes.keys()) == {f1, f2}
        assert sub.edge_count == 1

    def test_extract_preserves_metadata(self) -> None:
        graph, ids = _build_linear_graph()
        graph.metadata["project"] = "test"
        sub = extract_subgraph_by_module(graph, ids[0])
        assert sub.metadata["project"] == "test"


# =========================================================================== #
#                      Task 1.2.3: Dependency Traversal                        #
# =========================================================================== #


class TestTraversal:
    """Tests for ancestor/descendant traversal and direct dependencies."""

    def test_get_ancestors_linear(self) -> None:
        graph, ids = _build_linear_graph()
        # ids[2] ancestors via HIERARCHY should be ids[0], ids[1]
        ancestors = get_ancestors(graph, ids[2], [EdgeType.HIERARCHY])
        assert ancestors == {ids[0], ids[1]}

    def test_get_ancestors_root_has_none(self) -> None:
        graph, ids = _build_linear_graph()
        ancestors = get_ancestors(graph, ids[0], [EdgeType.HIERARCHY])
        assert ancestors == set()

    def test_get_ancestors_diamond(self) -> None:
        graph, ids = _build_diamond_graph()
        a, b, c, d = ids
        ancestors = get_ancestors(graph, d, [EdgeType.DATA_FLOW])
        assert ancestors == {a, b, c}

    def test_get_ancestors_not_found(self) -> None:
        graph = RPGGraph()
        with pytest.raises(ValueError, match="not found"):
            get_ancestors(graph, uuid4(), [EdgeType.HIERARCHY])

    def test_get_ancestors_specific_edge_type(self) -> None:
        """Only follows specified edge types."""
        graph, ids = _build_linear_graph()
        # HIERARCHY edges exist but we query DATA_FLOW -> no ancestors
        ancestors = get_ancestors(graph, ids[2], [EdgeType.DATA_FLOW])
        assert ancestors == set()

    def test_get_descendants_linear(self) -> None:
        graph, ids = _build_linear_graph()
        desc = get_descendants(graph, ids[0], [EdgeType.HIERARCHY])
        assert desc == {ids[1], ids[2]}

    def test_get_descendants_leaf_has_none(self) -> None:
        graph, ids = _build_linear_graph()
        desc = get_descendants(graph, ids[2], [EdgeType.HIERARCHY])
        assert desc == set()

    def test_get_descendants_diamond(self) -> None:
        graph, ids = _build_diamond_graph()
        a, b, c, d = ids
        desc = get_descendants(graph, a, [EdgeType.DATA_FLOW])
        assert desc == {b, c, d}

    def test_get_descendants_not_found(self) -> None:
        graph = RPGGraph()
        with pytest.raises(ValueError, match="not found"):
            get_descendants(graph, uuid4(), [EdgeType.HIERARCHY])

    def test_get_direct_dependencies(self) -> None:
        graph = RPGGraph()
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
        for uid, name in [(a, "A"), (b, "B"), (c, "C"), (d, "D")]:
            graph.add_node(_make_node(name=name, node_id=uid))
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(a, c, EdgeType.INVOCATION))
        graph.add_edge(_make_edge(a, d, EdgeType.HIERARCHY))  # Not a dependency

        deps = get_direct_dependencies(graph, a)
        assert set(deps) == {b, c}

    def test_get_direct_dependencies_none(self) -> None:
        graph = RPGGraph()
        uid = uuid4()
        graph.add_node(_make_node(name="lonely", node_id=uid))
        assert get_direct_dependencies(graph, uid) == []

    def test_get_direct_dependencies_not_found(self) -> None:
        graph = RPGGraph()
        with pytest.raises(ValueError, match="not found"):
            get_direct_dependencies(graph, uuid4())

    def test_get_ancestors_multiple_edge_types(self) -> None:
        """Can specify multiple edge types to follow."""
        graph = RPGGraph()
        a, b, c = uuid4(), uuid4(), uuid4()
        for uid, name in [(a, "A"), (b, "B"), (c, "C")]:
            graph.add_node(_make_node(name=name, node_id=uid))
        graph.add_edge(_make_edge(a, b, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(b, c, EdgeType.DATA_FLOW))

        # C's ancestors via HIERARCHY+DATA_FLOW
        ancestors = get_ancestors(
            graph, c, [EdgeType.HIERARCHY, EdgeType.DATA_FLOW]
        )
        assert ancestors == {a, b}


# =========================================================================== #
#                        Task 1.2.4: Node Filtering                            #
# =========================================================================== #


class TestFiltering:
    """Tests for node filtering functions."""

    def _build_filter_graph(self) -> RPGGraph:
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                name="passed_mod",
                level=NodeLevel.MODULE,
                test_status=TestStatus.PASSED,
                serena_validated=True,
            )
        )
        graph.add_node(
            _make_node(
                name="failed_comp",
                level=NodeLevel.COMPONENT,
                test_status=TestStatus.FAILED,
                serena_validated=False,
            )
        )
        graph.add_node(
            _make_node(
                name="pending_feat",
                level=NodeLevel.FEATURE,
                test_status=TestStatus.PENDING,
                serena_validated=False,
            )
        )
        graph.add_node(
            _make_node(
                name="passed_comp",
                level=NodeLevel.COMPONENT,
                test_status=TestStatus.PASSED,
                serena_validated=True,
            )
        )
        return graph

    def test_filter_nodes_custom_predicate(self) -> None:
        graph = self._build_filter_graph()
        result = filter_nodes(graph, lambda n: "comp" in n.name)
        assert len(result) == 2
        names = {n.name for n in result}
        assert names == {"failed_comp", "passed_comp"}

    def test_filter_nodes_empty_result(self) -> None:
        graph = self._build_filter_graph()
        result = filter_nodes(graph, lambda n: n.name == "nonexistent")
        assert result == []

    def test_filter_by_status_passed(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_status(graph, TestStatus.PASSED)
        assert len(result) == 2
        assert all(n.test_status == TestStatus.PASSED for n in result)

    def test_filter_by_status_failed(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_status(graph, TestStatus.FAILED)
        assert len(result) == 1
        assert result[0].name == "failed_comp"

    def test_filter_by_status_skipped(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_status(graph, TestStatus.SKIPPED)
        assert result == []

    def test_filter_by_validation_true(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_validation(graph, True)
        assert len(result) == 2
        assert all(n.serena_validated for n in result)

    def test_filter_by_validation_false(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_validation(graph, False)
        assert len(result) == 2
        assert all(not n.serena_validated for n in result)

    def test_filter_by_level_module(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_level(graph, NodeLevel.MODULE)
        assert len(result) == 1
        assert result[0].name == "passed_mod"

    def test_filter_by_level_component(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_level(graph, NodeLevel.COMPONENT)
        assert len(result) == 2

    def test_filter_by_level_feature(self) -> None:
        graph = self._build_filter_graph()
        result = filter_by_level(graph, NodeLevel.FEATURE)
        assert len(result) == 1
        assert result[0].name == "pending_feat"

    def test_filter_on_empty_graph(self) -> None:
        graph = RPGGraph()
        assert filter_by_status(graph, TestStatus.PASSED) == []
        assert filter_by_validation(graph, True) == []
        assert filter_by_level(graph, NodeLevel.MODULE) == []


# =========================================================================== #
#                        Task 1.2.5: Dependency Diff                           #
# =========================================================================== #


class TestDiff:
    """Tests for dependency diff function."""

    def test_diff_perfect_match(self) -> None:
        graph = RPGGraph()
        a, b, c = uuid4(), uuid4(), uuid4()
        node_a = _make_node(
            name="A", node_id=a, actual_dependencies=[b, c]
        )
        graph.add_node(node_a)
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_node(_make_node(name="C", node_id=c))
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(a, c, EdgeType.INVOCATION))

        result = diff_dependencies(node_a, graph)
        assert set(result["planned"]) == {b, c}
        assert set(result["actual"]) == {b, c}
        assert result["missing"] == []
        assert result["extra"] == []

    def test_diff_missing_dependencies(self) -> None:
        graph = RPGGraph()
        a, b, c = uuid4(), uuid4(), uuid4()
        node_a = _make_node(name="A", node_id=a, actual_dependencies=[])
        graph.add_node(node_a)
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_node(_make_node(name="C", node_id=c))
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(a, c, EdgeType.DATA_FLOW))

        result = diff_dependencies(node_a, graph)
        assert set(result["missing"]) == {b, c}
        assert result["extra"] == []

    def test_diff_extra_dependencies(self) -> None:
        graph = RPGGraph()
        a, b, extra = uuid4(), uuid4(), uuid4()
        node_a = _make_node(
            name="A", node_id=a, actual_dependencies=[b, extra]
        )
        graph.add_node(node_a)
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))

        result = diff_dependencies(node_a, graph)
        assert set(result["planned"]) == {b}
        assert set(result["actual"]) == {b, extra}
        assert result["missing"] == []
        assert set(result["extra"]) == {extra}

    def test_diff_both_missing_and_extra(self) -> None:
        graph = RPGGraph()
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
        node_a = _make_node(
            name="A", node_id=a, actual_dependencies=[c, d]
        )
        graph.add_node(node_a)
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_node(_make_node(name="C", node_id=c))
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(a, c, EdgeType.INVOCATION))

        result = diff_dependencies(node_a, graph)
        assert set(result["planned"]) == {b, c}
        assert set(result["actual"]) == {c, d}
        assert set(result["missing"]) == {b}
        assert set(result["extra"]) == {d}

    def test_diff_no_edges_no_actual(self) -> None:
        graph = RPGGraph()
        a = uuid4()
        node_a = _make_node(name="A", node_id=a)
        graph.add_node(node_a)
        result = diff_dependencies(node_a, graph)
        assert result["planned"] == []
        assert result["actual"] == []
        assert result["missing"] == []
        assert result["extra"] == []

    def test_diff_ignores_hierarchy_edges(self) -> None:
        """HIERARCHY edges should not count as planned dependencies."""
        graph = RPGGraph()
        a, b = uuid4(), uuid4()
        node_a = _make_node(name="A", node_id=a)
        graph.add_node(node_a)
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_edge(_make_edge(a, b, EdgeType.HIERARCHY))
        result = diff_dependencies(node_a, graph)
        assert result["planned"] == []


# =========================================================================== #
#                     Task 1.2.6: JSON Serialization                           #
# =========================================================================== #


class TestSerialization:
    """Tests for file-based JSON serialization."""

    def test_round_trip_empty_graph(self, tmp_path) -> None:
        graph = RPGGraph()
        path = tmp_path / "empty.json"
        serialize_graph(graph, path)
        loaded = deserialize_graph(path)
        assert loaded == graph

    def test_round_trip_with_nodes_and_edges(self, tmp_path) -> None:
        graph, ids = _build_diamond_graph()
        graph.metadata["project"] = "test-project"
        path = tmp_path / "diamond.json"

        serialize_graph(graph, path)
        loaded = deserialize_graph(path)

        assert loaded.node_count == graph.node_count
        assert loaded.edge_count == graph.edge_count
        assert loaded.metadata == graph.metadata
        assert loaded == graph

    def test_round_trip_with_all_node_fields(self, tmp_path) -> None:
        graph = RPGGraph()
        node = RPGNode(
            name="full_node",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/pkg",
            file_path="src/pkg/main.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def main() -> None",
            docstring="Entry point",
            implementation="print('hello')",
            test_code="def test_main(): ...",
            test_status=TestStatus.PASSED,
            serena_validated=True,
            actual_dependencies=[uuid4()],
            metadata={"key": "value"},
        )
        graph.add_node(node)
        path = tmp_path / "full.json"

        serialize_graph(graph, path)
        loaded = deserialize_graph(path)
        assert loaded == graph

    def test_creates_parent_directories(self, tmp_path) -> None:
        graph = RPGGraph()
        path = tmp_path / "a" / "b" / "c" / "graph.json"
        serialize_graph(graph, path)
        assert path.exists()

    def test_deserialize_nonexistent_file(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            deserialize_graph(tmp_path / "nope.json")

    def test_deserialize_invalid_json(self, tmp_path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json at all")
        with pytest.raises(ValueError, match="Invalid JSON"):
            deserialize_graph(path)

    def test_serialized_file_is_pretty_printed(self, tmp_path) -> None:
        graph = RPGGraph()
        graph.add_node(_make_node(name="test"))
        path = tmp_path / "pretty.json"
        serialize_graph(graph, path)
        content = path.read_text()
        # Pretty-printed JSON should have newlines
        assert "\n" in content

    def test_round_trip_with_data_flow_edge(self, tmp_path) -> None:
        graph = RPGGraph()
        a, b = uuid4(), uuid4()
        graph.add_node(_make_node(name="A", node_id=a))
        graph.add_node(_make_node(name="B", node_id=b))
        graph.add_edge(
            _make_edge(
                a,
                b,
                EdgeType.DATA_FLOW,
                data_id="config",
                data_type="dict[str, Any]",
            )
        )
        path = tmp_path / "dataflow.json"
        serialize_graph(graph, path)
        loaded = deserialize_graph(path)
        assert loaded == graph


# =========================================================================== #
#                        CycleDetectedError Tests                              #
# =========================================================================== #


class TestCycleDetectedError:
    """Tests for the CycleDetectedError exception."""

    def test_default_message(self) -> None:
        ids = [uuid4(), uuid4()]
        err = CycleDetectedError(ids)
        assert "Cycle detected" in str(err)
        assert str(ids[0]) in str(err)

    def test_custom_message(self) -> None:
        err = CycleDetectedError([uuid4()], message="Custom cycle error")
        assert str(err) == "Custom cycle error"

    def test_cycle_attribute(self) -> None:
        ids = [uuid4(), uuid4(), uuid4()]
        err = CycleDetectedError(ids)
        assert err.cycle == ids
