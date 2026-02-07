"""Unit tests for the codegen checkpoint manager."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest

from zerorepo.codegen.checkpoint import CheckpointManager
from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.edge import RPGEdge
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_node(
    *,
    name: str = "node",
    level: NodeLevel = NodeLevel.COMPONENT,
    node_type: NodeType = NodeType.FUNCTIONALITY,
    node_id: UUID | None = None,
) -> RPGNode:
    """Create an RPGNode with sensible defaults."""
    kwargs: dict = dict(name=name, level=level, node_type=node_type)
    if node_id is not None:
        kwargs["id"] = node_id
    return RPGNode(**kwargs)


def _make_edge(
    source_id: UUID,
    target_id: UUID,
    edge_type: EdgeType = EdgeType.HIERARCHY,
) -> RPGEdge:
    """Create an RPGEdge with sensible defaults."""
    return RPGEdge(source_id=source_id, target_id=target_id, edge_type=edge_type)


def _build_chain_graph(n: int = 5) -> tuple[RPGGraph, list[UUID]]:
    """Build a linear chain A->B->C->... of n nodes with DATA_FLOW edges.

    Returns:
        (graph, [id_0, id_1, ..., id_{n-1}])
    """
    ids = [uuid4() for _ in range(n)]
    graph = RPGGraph()
    for i, uid in enumerate(ids):
        graph.add_node(
            _make_node(name=f"node_{i}", node_id=uid, level=NodeLevel.MODULE)
        )
    for i in range(n - 1):
        graph.add_edge(_make_edge(ids[i], ids[i + 1], EdgeType.DATA_FLOW))
    return graph, ids


# --------------------------------------------------------------------------- #
#                         Test: CheckpointManager Init                         #
# --------------------------------------------------------------------------- #


class TestCheckpointManagerInit:
    """Test CheckpointManager initialization and properties."""

    def test_properties(self) -> None:
        graph = RPGGraph()
        state = GenerationState()
        mgr = CheckpointManager(state=state, graph=graph)

        assert mgr.state is state
        assert mgr.graph is graph

    def test_default_state(self) -> None:
        graph = RPGGraph()
        state = GenerationState(max_retries=5)
        mgr = CheckpointManager(state=state, graph=graph)
        assert mgr.state.max_retries == 5


# --------------------------------------------------------------------------- #
#                         Test: Save / Load Checkpoint                         #
# --------------------------------------------------------------------------- #


class TestCheckpointSaveLoad:
    """Test save and load checkpoint functionality."""

    def test_save_checkpoint(self, tmp_path) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        path = str(tmp_path / "checkpoint.json")
        result = mgr.save_checkpoint(path)

        assert os.path.exists(result)
        assert result == path

    def test_load_checkpoint(self, tmp_path) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState(max_retries=4)
        state.set_status(ids[0], GenerationStatus.PASSED)
        state.set_status(ids[1], GenerationStatus.FAILED, failure_reason="err")

        path = str(tmp_path / "checkpoint.json")
        state.save(path)

        mgr = CheckpointManager.load_checkpoint(path, graph)
        assert mgr.state.max_retries == 4
        assert mgr.state.get_node_state(ids[0]).status == GenerationStatus.PASSED
        assert mgr.state.get_node_state(ids[1]).failure_reason == "err"

    def test_load_nonexistent_raises(self) -> None:
        graph = RPGGraph()
        with pytest.raises(FileNotFoundError):
            CheckpointManager.load_checkpoint("/nonexistent.json", graph)


# --------------------------------------------------------------------------- #
#                         Test: Get Nodes to Process                           #
# --------------------------------------------------------------------------- #


class TestGetNodesToProcess:
    """Test determining which nodes need processing."""

    def test_all_pending_all_processed(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        mgr = CheckpointManager(state=state, graph=graph)

        to_process = mgr.get_nodes_to_process()
        assert set(to_process) == set(ids)

    def test_passed_nodes_excluded(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        to_process = mgr.get_nodes_to_process()
        assert ids[0] not in to_process
        assert ids[1] in to_process
        assert ids[2] in to_process

    def test_skipped_nodes_excluded(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.SKIPPED)

        mgr = CheckpointManager(state=state, graph=graph)
        to_process = mgr.get_nodes_to_process()
        assert ids[0] not in to_process

    def test_failed_within_retries_included(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState(max_retries=5)
        state.set_status(ids[0], GenerationStatus.FAILED)
        state.get_node_state(ids[0]).retry_count = 3  # < max_retries

        mgr = CheckpointManager(state=state, graph=graph)
        to_process = mgr.get_nodes_to_process()
        assert ids[0] in to_process

    def test_failed_beyond_retries_excluded(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState(max_retries=5)
        state.set_status(ids[0], GenerationStatus.FAILED)
        state.get_node_state(ids[0]).retry_count = 5  # == max_retries

        mgr = CheckpointManager(state=state, graph=graph)
        to_process = mgr.get_nodes_to_process()
        assert ids[0] not in to_process

    def test_in_progress_included(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.IN_PROGRESS)

        mgr = CheckpointManager(state=state, graph=graph)
        to_process = mgr.get_nodes_to_process()
        assert ids[0] in to_process


# --------------------------------------------------------------------------- #
#                         Test: Validate Start From                            #
# --------------------------------------------------------------------------- #


class TestValidateStartFrom:
    """Test validation of --start-from-node."""

    def test_all_deps_passed_returns_empty(self) -> None:
        graph, ids = _build_chain_graph(5)
        state = GenerationState()
        # Mark first 3 nodes as passed
        for i in range(3):
            state.set_status(ids[i], GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        # Starting from node 3 (index 3) - deps are 0, 1, 2 which are passed
        blockers = mgr.validate_start_from(ids[3])
        assert blockers == []

    def test_missing_deps_returned_as_blockers(self) -> None:
        graph, ids = _build_chain_graph(5)
        state = GenerationState()
        # Only mark first node as passed, but start from node 3
        state.set_status(ids[0], GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        blockers = mgr.validate_start_from(ids[3])
        # Nodes 1 and 2 are ancestors of node 3 and NOT passed
        assert ids[1] in blockers
        assert ids[2] in blockers

    def test_start_from_root_node(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()

        mgr = CheckpointManager(state=state, graph=graph)
        # Root node has no ancestors
        blockers = mgr.validate_start_from(ids[0])
        assert blockers == []

    def test_invalid_node_raises(self) -> None:
        graph, _ = _build_chain_graph(3)
        state = GenerationState()
        mgr = CheckpointManager(state=state, graph=graph)

        with pytest.raises(ValueError, match="not found"):
            mgr.validate_start_from(uuid4())


# --------------------------------------------------------------------------- #
#                         Test: Resume From Node                               #
# --------------------------------------------------------------------------- #


class TestResumeFromNode:
    """Test checkpoint resume from a specific node."""

    def test_resume_resets_target_and_descendants(self) -> None:
        graph, ids = _build_chain_graph(5)
        state = GenerationState()
        # Mark all as passed
        for uid in ids:
            state.set_status(uid, GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        # Resume from node 2 - should reset 2, 3, 4
        reset = mgr.resume_from_node(ids[2])

        assert ids[2] in reset
        assert ids[3] in reset
        assert ids[4] in reset
        assert ids[0] not in reset
        assert ids[1] not in reset

        for nid in [ids[2], ids[3], ids[4]]:
            assert state.get_node_state(nid).status == GenerationStatus.PENDING
            assert state.get_node_state(nid).retry_count == 0

    def test_resume_with_unmet_deps_raises(self) -> None:
        graph, ids = _build_chain_graph(5)
        state = GenerationState()
        # Only node 0 passed, try to resume from node 3
        state.set_status(ids[0], GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        with pytest.raises(ValueError, match="dependencies not passed"):
            mgr.resume_from_node(ids[3])

    def test_resume_from_root_works(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        for uid in ids:
            state.set_status(uid, GenerationStatus.PASSED)

        mgr = CheckpointManager(state=state, graph=graph)
        reset = mgr.resume_from_node(ids[0])

        # All nodes should be reset
        assert set(reset) == set(ids)

    def test_resume_clears_failure_info(self) -> None:
        graph, ids = _build_chain_graph(3)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.PASSED)
        state.set_status(ids[1], GenerationStatus.PASSED)
        state.set_status(ids[2], GenerationStatus.FAILED, failure_reason="err")
        state.get_node_state(ids[2]).retry_count = 5

        mgr = CheckpointManager(state=state, graph=graph)
        mgr.resume_from_node(ids[2])

        node_state = state.get_node_state(ids[2])
        assert node_state.status == GenerationStatus.PENDING
        assert node_state.retry_count == 0
        assert node_state.failure_reason is None


# --------------------------------------------------------------------------- #
#                         Test: Checkpoint Resume (e2e flow)                   #
# --------------------------------------------------------------------------- #


class TestCheckpointResume:
    """End-to-end test: can restart from node #5 of 10."""

    def test_checkpoint_resume_from_node_5_of_10(self, tmp_path) -> None:
        """Create a 10-node chain, save checkpoint at node 5, resume."""
        graph, ids = _build_chain_graph(10)
        state = GenerationState(max_retries=3)

        # Simulate processing first 5 nodes
        for i in range(5):
            state.set_status(ids[i], GenerationStatus.PASSED)
            state.update_test_results(ids[i], passed=3, failed=0)

        # Save checkpoint
        path = str(tmp_path / "checkpoint.json")
        state.save(path)

        # Load checkpoint and verify resume
        mgr = CheckpointManager.load_checkpoint(path, graph)

        # Validate we can start from node 5
        blockers = mgr.validate_start_from(ids[5])
        assert blockers == []

        # Nodes 5-9 should need processing
        to_process = mgr.get_nodes_to_process()
        for i in range(5, 10):
            assert ids[i] in to_process
        for i in range(5):
            assert ids[i] not in to_process


# --------------------------------------------------------------------------- #
#                         Test: Idempotent Safe                                #
# --------------------------------------------------------------------------- #


class TestIdempotentSafe:
    """Test idempotency safety check."""

    def test_passed_is_safe(self) -> None:
        graph, ids = _build_chain_graph(1)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.PASSED)
        mgr = CheckpointManager(state=state, graph=graph)
        assert mgr.is_idempotent_safe(ids[0]) is True

    def test_pending_is_safe(self) -> None:
        graph, ids = _build_chain_graph(1)
        state = GenerationState()
        mgr = CheckpointManager(state=state, graph=graph)
        assert mgr.is_idempotent_safe(ids[0]) is True

    def test_skipped_is_safe(self) -> None:
        graph, ids = _build_chain_graph(1)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.SKIPPED)
        mgr = CheckpointManager(state=state, graph=graph)
        assert mgr.is_idempotent_safe(ids[0]) is True

    def test_failed_is_not_safe(self) -> None:
        graph, ids = _build_chain_graph(1)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.FAILED)
        mgr = CheckpointManager(state=state, graph=graph)
        assert mgr.is_idempotent_safe(ids[0]) is False

    def test_in_progress_is_not_safe(self) -> None:
        graph, ids = _build_chain_graph(1)
        state = GenerationState()
        state.set_status(ids[0], GenerationStatus.IN_PROGRESS)
        mgr = CheckpointManager(state=state, graph=graph)
        assert mgr.is_idempotent_safe(ids[0]) is False
