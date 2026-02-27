"""Unit tests for the codegen traversal engine."""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from cobuilder.repomap.codegen.state import GenerationState, GenerationStatus
from cobuilder.repomap.codegen.traversal import TraversalEngine, TraversalReport
from cobuilder.repomap.graph_ops.exceptions import CycleDetectedError
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
    interface_type: InterfaceType | None = None,
    folder_path: str | None = None,
    file_path: str | None = None,
    signature: str | None = None,
) -> RPGNode:
    """Create an RPGNode with sensible defaults for testing."""
    kwargs: dict = dict(
        name=name,
        level=level,
        node_type=node_type,
        test_status=test_status,
    )
    if node_id is not None:
        kwargs["id"] = node_id
    if parent_id is not None:
        kwargs["parent_id"] = parent_id
    if interface_type is not None:
        kwargs["interface_type"] = interface_type
    if folder_path is not None:
        kwargs["folder_path"] = folder_path
    if file_path is not None:
        kwargs["file_path"] = file_path
    if signature is not None:
        kwargs["signature"] = signature
    return RPGNode(**kwargs)


def _make_func_node(
    *,
    name: str = "func_node",
    node_id: UUID | None = None,
    parent_id: UUID | None = None,
) -> RPGNode:
    """Create a FUNCTION_AUGMENTED node (leaf node for code generation)."""
    return _make_node(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        node_id=node_id,
        parent_id=parent_id,
        interface_type=InterfaceType.FUNCTION,
        folder_path="src",
        file_path="src/module.py",
        signature=f"def {name}() -> None",
    )


def _make_edge(
    source_id: UUID,
    target_id: UUID,
    edge_type: EdgeType = EdgeType.HIERARCHY,
    *,
    edge_id: UUID | None = None,
) -> RPGEdge:
    """Create an RPGEdge with sensible defaults for testing."""
    kwargs: dict = dict(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
    )
    if edge_id is not None:
        kwargs["id"] = edge_id
    return RPGEdge(**kwargs)


def _build_linear_graph() -> tuple[RPGGraph, list[UUID]]:
    """Build a simple linear DAG: A -> B -> C (HIERARCHY edges).

    Returns:
        (graph, [id_A, id_B, id_C])
    """
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

    Returns:
        (graph, [id_A, id_B, id_C, id_D])
    """
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    graph = RPGGraph()
    for uid, name in [(a, "A"), (b, "B"), (c, "C"), (d, "D")]:
        graph.add_node(
            _make_node(name=name, node_id=uid, level=NodeLevel.MODULE)
        )
    graph.add_edge(
        _make_edge(a, b, EdgeType.DATA_FLOW)
    )
    graph.add_edge(
        _make_edge(a, c, EdgeType.DATA_FLOW)
    )
    graph.add_edge(
        _make_edge(b, d, EdgeType.DATA_FLOW)
    )
    graph.add_edge(
        _make_edge(c, d, EdgeType.DATA_FLOW)
    )
    return graph, [a, b, c, d]


# --------------------------------------------------------------------------- #
#                         Test: Topological Sort                               #
# --------------------------------------------------------------------------- #


class TestTopologicalSortLinearChain:
    """Test topological sort with a linear A->B->C chain."""

    def test_linear_chain_produces_abc_order(self) -> None:
        graph, ids = _build_linear_graph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()

        ordered_ids = [n.id for n in ordered]
        assert ordered_ids.index(ids[0]) < ordered_ids.index(ids[1])
        assert ordered_ids.index(ids[1]) < ordered_ids.index(ids[2])

    def test_linear_chain_returns_all_nodes(self) -> None:
        graph, ids = _build_linear_graph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        assert len(ordered) == 3

    def test_linear_chain_returns_rpg_nodes(self) -> None:
        graph, ids = _build_linear_graph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        assert all(isinstance(n, RPGNode) for n in ordered)


class TestTopologicalSortDiamond:
    """Test topological sort with a diamond A->{B,C}->D shape."""

    def test_diamond_a_before_b_and_c(self) -> None:
        graph, [a, b, c, d] = _build_diamond_graph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        ordered_ids = [n.id for n in ordered]

        assert ordered_ids.index(a) < ordered_ids.index(b)
        assert ordered_ids.index(a) < ordered_ids.index(c)

    def test_diamond_b_and_c_before_d(self) -> None:
        graph, [a, b, c, d] = _build_diamond_graph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        ordered_ids = [n.id for n in ordered]

        assert ordered_ids.index(b) < ordered_ids.index(d)
        assert ordered_ids.index(c) < ordered_ids.index(d)

    def test_diamond_returns_all_four_nodes(self) -> None:
        graph, _ = _build_diamond_graph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        assert len(ordered) == 4


class TestCycleDetection:
    """Test that cycles raise CycleDetectedError."""

    def test_cycle_raises_error(self) -> None:
        """A->B->A cycle should raise CycleDetectedError."""
        a, b = uuid4(), uuid4()
        graph = RPGGraph()
        graph.add_node(
            _make_node(name="A", node_id=a, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="B", node_id=b, level=NodeLevel.MODULE)
        )
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(b, a, EdgeType.DATA_FLOW))

        engine = TraversalEngine(graph)
        with pytest.raises(CycleDetectedError):
            engine.compute_order()

    def test_three_node_cycle_raises_error(self) -> None:
        """A->B->C->A cycle should raise CycleDetectedError."""
        a, b, c = uuid4(), uuid4(), uuid4()
        graph = RPGGraph()
        for uid, name in [(a, "A"), (b, "B"), (c, "C")]:
            graph.add_node(
                _make_node(name=name, node_id=uid, level=NodeLevel.MODULE)
            )
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(b, c, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(c, a, EdgeType.DATA_FLOW))

        engine = TraversalEngine(graph)
        with pytest.raises(CycleDetectedError):
            engine.compute_order()


# --------------------------------------------------------------------------- #
#                         Test: Deterministic Ordering                         #
# --------------------------------------------------------------------------- #


class TestDeterministicOrdering:
    """Test that same graph always produces the same order."""

    def test_same_graph_same_order(self) -> None:
        """Running compute_order multiple times should produce identical results."""
        graph, ids = _build_diamond_graph()
        engine = TraversalEngine(graph)

        order1 = [n.id for n in engine.compute_order()]
        order2 = [n.id for n in engine.compute_order()]
        order3 = [n.id for n in engine.compute_order()]

        assert order1 == order2 == order3

    def test_deterministic_tiebreak_by_uuid_string(self) -> None:
        """Nodes at the same topological level should be sorted by UUID string."""
        # Create two unconnected nodes (same topo level)
        id1 = UUID("00000000-0000-0000-0000-000000000001")
        id2 = UUID("00000000-0000-0000-0000-000000000002")
        graph = RPGGraph()
        graph.add_node(
            _make_node(name="N1", node_id=id1, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="N2", node_id=id2, level=NodeLevel.MODULE)
        )

        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        ordered_ids = [n.id for n in ordered]

        # id1 string sorts before id2 string
        assert ordered_ids[0] == id1
        assert ordered_ids[1] == id2

    def test_deterministic_with_parallel_branches(self) -> None:
        """Parallel branches should be deterministically ordered."""
        root = UUID("00000000-0000-0000-0000-000000000000")
        child_a = UUID("00000000-0000-0000-0000-00000000000a")
        child_b = UUID("00000000-0000-0000-0000-00000000000b")

        graph = RPGGraph()
        graph.add_node(
            _make_node(name="root", node_id=root, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="A", node_id=child_a, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="B", node_id=child_b, level=NodeLevel.MODULE)
        )
        graph.add_edge(_make_edge(root, child_a, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(root, child_b, EdgeType.HIERARCHY))

        engine = TraversalEngine(graph)
        order1 = [n.id for n in engine.compute_order()]
        order2 = [n.id for n in engine.compute_order()]

        assert order1 == order2
        # root should be first
        assert order1[0] == root
        # children should be alphabetically sorted by UUID string
        assert order1[1] == child_a
        assert order1[2] == child_b


# --------------------------------------------------------------------------- #
#                         Test: Leaf Node Filtering                            #
# --------------------------------------------------------------------------- #


class TestLeafNodeFiltering:
    """Test that only FUNCTION_AUGMENTED nodes are returned by generation order."""

    def test_only_function_augmented_returned(self) -> None:
        """compute_generation_order should only return FUNCTION_AUGMENTED nodes."""
        module_id = uuid4()
        func_id = uuid4()
        folder_id = uuid4()

        graph = RPGGraph()
        graph.add_node(
            _make_node(
                name="module", node_id=module_id,
                level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY,
            )
        )
        graph.add_node(
            _make_node(
                name="folder", node_id=folder_id,
                level=NodeLevel.COMPONENT, node_type=NodeType.FOLDER_AUGMENTED,
            )
        )
        graph.add_node(
            _make_func_node(name="func", node_id=func_id)
        )
        graph.add_edge(_make_edge(module_id, folder_id, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(folder_id, func_id, EdgeType.HIERARCHY))

        engine = TraversalEngine(graph)
        gen_order = engine.compute_generation_order()

        assert len(gen_order) == 1
        assert gen_order[0].id == func_id
        assert gen_order[0].node_type == NodeType.FUNCTION_AUGMENTED

    def test_empty_generation_order_no_function_nodes(self) -> None:
        """If no FUNCTION_AUGMENTED nodes, generation order should be empty."""
        graph = RPGGraph()
        graph.add_node(
            _make_node(
                name="module", level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
        )

        engine = TraversalEngine(graph)
        gen_order = engine.compute_generation_order()
        assert gen_order == []

    def test_multiple_function_nodes_in_order(self) -> None:
        """Multiple FUNCTION_AUGMENTED nodes should maintain topological order."""
        parent = uuid4()
        func_a = uuid4()
        func_b = uuid4()

        graph = RPGGraph()
        graph.add_node(
            _make_node(
                name="parent", node_id=parent,
                level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY,
            )
        )
        graph.add_node(_make_func_node(name="func_a", node_id=func_a))
        graph.add_node(_make_func_node(name="func_b", node_id=func_b))

        graph.add_edge(_make_edge(parent, func_a, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(func_a, func_b, EdgeType.DATA_FLOW))

        engine = TraversalEngine(graph)
        gen_order = engine.compute_generation_order()

        assert len(gen_order) == 2
        ordered_ids = [n.id for n in gen_order]
        assert ordered_ids.index(func_a) < ordered_ids.index(func_b)


# --------------------------------------------------------------------------- #
#                         Test: Failure Propagation                            #
# --------------------------------------------------------------------------- #


class TestFailedNodePropagation:
    """Test failure propagation to downstream dependents."""

    def test_failed_node_skips_descendants(self) -> None:
        """If B fails, C (depends on B) should be skipped."""
        a, b, c = uuid4(), uuid4(), uuid4()
        graph = RPGGraph()
        for uid, name in [(a, "A"), (b, "B"), (c, "C")]:
            graph.add_node(
                _make_node(name=name, node_id=uid, level=NodeLevel.MODULE)
            )
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(b, c, EdgeType.DATA_FLOW))

        engine = TraversalEngine(graph, max_retries=1)
        engine.mark_passed(a)

        # Fail B (1 retry, max_retries=1, so it becomes FAILED)
        skipped = engine.mark_failed(b, reason="compile error")

        assert engine.state.get_node_state(b).status == GenerationStatus.FAILED
        assert c in skipped
        assert engine.state.get_node_state(c).status == GenerationStatus.SKIPPED

    def test_failed_node_does_not_skip_passed_descendants(self) -> None:
        """Already-passed descendants should not be re-skipped."""
        a, b, c = uuid4(), uuid4(), uuid4()
        graph = RPGGraph()
        for uid, name in [(a, "A"), (b, "B"), (c, "C")]:
            graph.add_node(
                _make_node(name=name, node_id=uid, level=NodeLevel.MODULE)
            )
        graph.add_edge(_make_edge(a, b, EdgeType.DATA_FLOW))
        graph.add_edge(_make_edge(b, c, EdgeType.DATA_FLOW))

        engine = TraversalEngine(graph, max_retries=1)
        engine.mark_passed(a)
        engine.mark_passed(c)  # C already passed

        skipped = engine.mark_failed(b, reason="compile error")
        # C was already passed, should NOT be in skipped list
        assert c not in skipped
        assert engine.state.get_node_state(c).status == GenerationStatus.PASSED

    def test_retry_before_permanent_failure(self) -> None:
        """Node should be retried before permanent failure."""
        a = uuid4()
        graph = RPGGraph()
        graph.add_node(
            _make_node(name="A", node_id=a, level=NodeLevel.MODULE)
        )

        engine = TraversalEngine(graph, max_retries=3)

        # First two failures should allow retry (pending)
        skipped = engine.mark_failed(a, reason="attempt 1")
        assert skipped == []
        assert engine.state.get_node_state(a).status == GenerationStatus.PENDING

        skipped = engine.mark_failed(a, reason="attempt 2")
        assert skipped == []
        assert engine.state.get_node_state(a).status == GenerationStatus.PENDING

        # Third failure should mark as permanently failed
        skipped = engine.mark_failed(a, reason="attempt 3")
        assert engine.state.get_node_state(a).status == GenerationStatus.FAILED

    def test_failure_propagation_in_diamond(self) -> None:
        """In a diamond graph, failing B should skip D but not C."""
        graph, [a, b, c, d] = _build_diamond_graph()
        engine = TraversalEngine(graph, max_retries=1)
        engine.mark_passed(a)

        skipped = engine.mark_failed(b, reason="error")

        assert engine.state.get_node_state(b).status == GenerationStatus.FAILED
        # D is downstream of B via DATA_FLOW, should be skipped
        assert d in skipped
        assert engine.state.get_node_state(d).status == GenerationStatus.SKIPPED
        # C is NOT downstream of B, should remain PENDING
        assert c not in skipped


# --------------------------------------------------------------------------- #
#                         Test: Should Process                                 #
# --------------------------------------------------------------------------- #


class TestShouldProcess:
    """Test the should_process method."""

    def test_pending_should_process(self) -> None:
        a = uuid4()
        graph = RPGGraph()
        graph.add_node(_make_node(name="A", node_id=a, level=NodeLevel.MODULE))

        engine = TraversalEngine(graph)
        assert engine.should_process(a) is True

    def test_in_progress_should_process(self) -> None:
        a = uuid4()
        graph = RPGGraph()
        graph.add_node(_make_node(name="A", node_id=a, level=NodeLevel.MODULE))

        engine = TraversalEngine(graph)
        engine.state.set_status(a, GenerationStatus.IN_PROGRESS)
        assert engine.should_process(a) is True

    def test_passed_should_not_process(self) -> None:
        a = uuid4()
        graph = RPGGraph()
        graph.add_node(_make_node(name="A", node_id=a, level=NodeLevel.MODULE))

        engine = TraversalEngine(graph)
        engine.mark_passed(a)
        assert engine.should_process(a) is False

    def test_failed_should_not_process(self) -> None:
        a = uuid4()
        graph = RPGGraph()
        graph.add_node(_make_node(name="A", node_id=a, level=NodeLevel.MODULE))

        engine = TraversalEngine(graph, max_retries=1)
        engine.mark_failed(a)
        assert engine.should_process(a) is False

    def test_skipped_should_not_process(self) -> None:
        a = uuid4()
        graph = RPGGraph()
        graph.add_node(_make_node(name="A", node_id=a, level=NodeLevel.MODULE))

        engine = TraversalEngine(graph)
        engine.state.set_status(a, GenerationStatus.SKIPPED)
        assert engine.should_process(a) is False


# --------------------------------------------------------------------------- #
#                         Test: Generate Report                                #
# --------------------------------------------------------------------------- #


class TestGenerateReport:
    """Test the traversal report generation."""

    def test_report_counts(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        graph = RPGGraph()
        for uid, name in [(a, "A"), (b, "B"), (c, "C")]:
            graph.add_node(
                _make_node(name=name, node_id=uid, level=NodeLevel.MODULE)
            )
        graph.add_edge(_make_edge(a, b, EdgeType.HIERARCHY))
        graph.add_edge(_make_edge(b, c, EdgeType.HIERARCHY))

        engine = TraversalEngine(graph, max_retries=1)
        engine.mark_passed(a)
        engine.mark_failed(b, reason="error")
        # c gets auto-skipped by failure propagation

        report = engine.generate_report()
        assert isinstance(report, TraversalReport)
        assert report.passed == 1
        assert report.failed == 1
        assert report.skipped == 1
        assert report.total == 3

    def test_report_empty_graph(self) -> None:
        graph = RPGGraph()
        engine = TraversalEngine(graph)
        report = engine.generate_report()
        assert report.total == 0
        assert report.passed == 0
        assert report.failed == 0
        assert report.skipped == 0

    def test_report_has_subgraph_reports(self) -> None:
        a, b = uuid4(), uuid4()
        graph = RPGGraph()
        graph.add_node(
            _make_node(name="A", node_id=a, level=NodeLevel.MODULE)
        )
        graph.add_node(
            _make_node(name="B", node_id=b, level=NodeLevel.MODULE)
        )
        graph.add_edge(_make_edge(a, b, EdgeType.HIERARCHY))

        engine = TraversalEngine(graph)
        engine.mark_passed(a)
        engine.mark_passed(b)

        report = engine.generate_report()
        # 'a' is a root node
        assert str(a) in report.subgraph_reports


# --------------------------------------------------------------------------- #
#                         Test: Engine Properties                              #
# --------------------------------------------------------------------------- #


class TestEngineProperties:
    """Test TraversalEngine property accessors and initialization."""

    def test_graph_property(self) -> None:
        graph = RPGGraph()
        engine = TraversalEngine(graph)
        assert engine.graph is graph

    def test_state_property_default(self) -> None:
        graph = RPGGraph()
        engine = TraversalEngine(graph)
        assert isinstance(engine.state, GenerationState)

    def test_state_property_custom(self) -> None:
        graph = RPGGraph()
        state = GenerationState()
        engine = TraversalEngine(graph, state=state)
        assert engine.state is state

    def test_max_retries_set(self) -> None:
        graph = RPGGraph()
        engine = TraversalEngine(graph, max_retries=5)
        assert engine.state.max_retries == 5

    def test_empty_graph_order(self) -> None:
        graph = RPGGraph()
        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        assert ordered == []

    def test_single_node_order(self) -> None:
        nid = uuid4()
        graph = RPGGraph()
        graph.add_node(
            _make_node(name="single", node_id=nid, level=NodeLevel.MODULE)
        )

        engine = TraversalEngine(graph)
        ordered = engine.compute_order()
        assert len(ordered) == 1
        assert ordered[0].id == nid
