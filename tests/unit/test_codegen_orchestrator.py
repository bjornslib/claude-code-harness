"""Unit tests for the main code generation orchestrator."""

from __future__ import annotations

import tempfile
from typing import Any
from uuid import UUID, uuid4

import pytest

from zerorepo.codegen.codegen_orchestrator import (
    CodegenOrchestrator,
    NodeResult,
    OrchestratorConfig,
    OrchestratorResult,
)
from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.codegen.tdd_loop import (
    DiagnosisResult,
    SandboxResult,
    TDDLoopResult,
)
from zerorepo.codegen.traversal import TraversalEngine
from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
)
from zerorepo.models.edge import RPGEdge
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_func_node(
    *,
    name: str = "func_node",
    node_id: UUID | None = None,
    parent_id: UUID | None = None,
) -> RPGNode:
    """Create a FUNCTION_AUGMENTED node (leaf node for code generation)."""
    kwargs: dict[str, Any] = dict(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        folder_path="src",
        file_path="src/module.py",
        signature=f"def {name}() -> None",
        docstring=f"Implementation for {name}.",
    )
    if node_id is not None:
        kwargs["id"] = node_id
    if parent_id is not None:
        kwargs["parent_id"] = parent_id
    return RPGNode(**kwargs)


def _build_simple_graph(num_nodes: int = 3) -> tuple[RPGGraph, list[RPGNode]]:
    """Build a simple linear chain graph of FUNCTION_AUGMENTED nodes.

    Returns the graph and the list of nodes in order.
    """
    graph = RPGGraph()
    nodes: list[RPGNode] = []

    for i in range(num_nodes):
        node = _make_func_node(name=f"func_{i}", node_id=uuid4())
        graph.nodes[node.id] = node
        nodes.append(node)

    # Create HIERARCHY edges to form a chain
    for i in range(len(nodes) - 1):
        edge = RPGEdge(
            source_id=nodes[i].id,
            target_id=nodes[i + 1].id,
            edge_type=EdgeType.HIERARCHY,
        )
        graph.edges[edge.id] = edge

    return graph, nodes


class MockTestGenerator:
    """Mock test generator."""

    def generate_tests(self, node: RPGNode, context: dict[str, Any]) -> str:
        return f"def test_{node.name}(): assert True"


class MockImplGenerator:
    """Mock implementation generator."""

    def generate_implementation(
        self, node: RPGNode, test_code: str, context: dict[str, Any]
    ) -> str:
        return f"def {node.name}(): return 42"


class MockSandboxExecutor:
    """Mock sandbox executor that always passes."""

    def __init__(self, pass_all: bool = True, fail_nodes: set[UUID] | None = None):
        self._pass_all = pass_all
        self._fail_nodes = fail_nodes or set()

    def run_tests(
        self, implementation: str, test_code: str, node: RPGNode
    ) -> SandboxResult:
        if node.id in self._fail_nodes:
            return SandboxResult(passed=0, failed=1, stderr="Intentional failure")
        if self._pass_all:
            return SandboxResult(passed=3, failed=0)
        return SandboxResult(passed=0, failed=1, stderr="Generic failure")


class MockDebugDiagnoser:
    """Mock diagnoser."""

    def diagnose_and_fix(
        self, node, implementation, test_code, error_output, context
    ) -> DiagnosisResult:
        return DiagnosisResult(
            classification="implementation_bug",
            fixed_implementation="def fixed(): pass",
        )


# --------------------------------------------------------------------------- #
#                              Tests: OrchestratorConfig                       #
# --------------------------------------------------------------------------- #


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_defaults(self):
        config = OrchestratorConfig()
        assert config.max_retries == 8
        assert config.checkpoint_interval == 5
        assert config.progress_log_interval == 10
        assert config.fail_fast is False
        assert config.skip_non_leaf is True

    def test_custom_values(self):
        config = OrchestratorConfig(
            max_retries=3,
            checkpoint_interval=2,
            progress_log_interval=5,
            fail_fast=True,
            skip_non_leaf=False,
        )
        assert config.max_retries == 3
        assert config.fail_fast is True


# --------------------------------------------------------------------------- #
#                              Tests: OrchestratorResult                       #
# --------------------------------------------------------------------------- #


class TestOrchestratorResult:
    """Tests for OrchestratorResult."""

    def test_defaults(self):
        result = OrchestratorResult()
        assert result.total_nodes == 0
        assert result.processed_nodes == 0
        assert result.passed_nodes == 0
        assert result.failed_nodes == 0
        assert result.skipped_nodes == 0

    def test_pass_rate(self):
        result = OrchestratorResult(total_nodes=10, passed_nodes=7)
        assert result.pass_rate == 70.0

    def test_pass_rate_zero_nodes(self):
        result = OrchestratorResult(total_nodes=0)
        assert result.pass_rate == 0.0


# --------------------------------------------------------------------------- #
#                              Tests: NodeResult                               #
# --------------------------------------------------------------------------- #


class TestNodeResult:
    """Tests for NodeResult."""

    def test_defaults(self):
        result = NodeResult()
        assert result.success is False
        assert result.skipped is False
        assert result.tdd_result is None


# --------------------------------------------------------------------------- #
#                              Tests: CodegenOrchestrator                      #
# --------------------------------------------------------------------------- #


class TestCodegenOrchestrator:
    """Tests for the main code generation orchestrator."""

    def test_run_simple_graph_all_pass(self):
        """All nodes in a simple graph pass."""
        graph, nodes = _build_simple_graph(3)
        config = OrchestratorConfig(max_retries=2, checkpoint_interval=10)

        # Use tempdir for checkpoint
        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(pass_all=True),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        assert result.total_nodes == 3
        assert result.passed_nodes == 3
        assert result.failed_nodes == 0
        assert result.pass_rate == 100.0
        assert result.elapsed_seconds > 0
        assert result.traversal_report is not None

    def test_run_with_failure_and_propagation(self):
        """Failed node propagates to downstream nodes."""
        graph, nodes = _build_simple_graph(3)
        config = OrchestratorConfig(max_retries=1, checkpoint_interval=100)

        # First node fails
        fail_nodes = {nodes[0].id}

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(fail_nodes=fail_nodes),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        assert result.failed_nodes >= 1
        # Downstream nodes should be skipped or failed
        assert result.passed_nodes < 3

    def test_fail_fast_stops_on_first_failure(self):
        """Fail-fast config stops pipeline on first failure."""
        graph, nodes = _build_simple_graph(5)
        config = OrchestratorConfig(max_retries=1, fail_fast=True, checkpoint_interval=100)

        # First node fails
        fail_nodes = {nodes[0].id}

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(fail_nodes=fail_nodes),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        # Should have stopped after the first node failed
        assert result.processed_nodes <= 2  # At most processed the first + checked second

    def test_graceful_shutdown(self):
        """Graceful shutdown stops after current node."""
        graph, nodes = _build_simple_graph(5)
        config = OrchestratorConfig(max_retries=1, checkpoint_interval=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(pass_all=True),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            # Request shutdown immediately
            orch.request_shutdown()
            result = orch.run()

        # Should process 0 nodes (shutdown before first)
        assert result.processed_nodes == 0

    def test_resume_from_checkpoint(self):
        """Orchestrator respects already-passed nodes from checkpoint."""
        graph, nodes = _build_simple_graph(3)
        config = OrchestratorConfig(max_retries=2, checkpoint_interval=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            # Pre-mark first node as PASSED
            state.set_status(nodes[0].id, GenerationStatus.PASSED)

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(pass_all=True),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        # First node should not be reprocessed
        assert result.passed_nodes == 3  # All pass (1 from checkpoint + 2 processed)
        assert result.processed_nodes == 2  # Only 2 actually went through TDD

    def test_properties(self):
        """Test orchestrator properties."""
        graph, _ = _build_simple_graph(1)
        state = GenerationState()

        orch = CodegenOrchestrator(
            graph=graph,
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor(),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
        )

        assert orch.graph is graph
        assert orch.state is state
        assert orch.traversal is not None

    def test_checkpoint_saved(self):
        """Checkpoint file is created during run."""
        graph, nodes = _build_simple_graph(2)
        config = OrchestratorConfig(
            max_retries=1,
            checkpoint_interval=1,  # Save after every node
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = f"{tmpdir}/checkpoint.json"
            state = GenerationState(checkpoint_path=checkpoint_path)

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(pass_all=True),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        assert result.checkpoint_path != ""

    def test_empty_graph(self):
        """Empty graph produces zero results."""
        graph = RPGGraph()
        config = OrchestratorConfig(max_retries=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        assert result.total_nodes == 0
        assert result.processed_nodes == 0
        assert result.pass_rate == 0.0

    def test_skipped_nodes_counted(self):
        """Nodes already skipped in state are properly counted."""
        graph, nodes = _build_simple_graph(3)
        config = OrchestratorConfig(max_retries=1, checkpoint_interval=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            # Pre-mark some nodes
            state.set_status(nodes[0].id, GenerationStatus.PASSED)
            state.set_status(nodes[1].id, GenerationStatus.SKIPPED)

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(pass_all=True),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        assert result.passed_nodes >= 1
        assert result.skipped_nodes >= 1

    def test_node_implementation_updated_on_success(self):
        """Successful node gets implementation and test_code set."""
        graph, nodes = _build_simple_graph(1)
        config = OrchestratorConfig(max_retries=2, checkpoint_interval=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            state = GenerationState(
                checkpoint_path=f"{tmpdir}/checkpoint.json"
            )

            orch = CodegenOrchestrator(
                graph=graph,
                test_generator=MockTestGenerator(),
                impl_generator=MockImplGenerator(),
                sandbox_executor=MockSandboxExecutor(pass_all=True),
                debug_diagnoser=MockDebugDiagnoser(),
                config=config,
                state=state,
            )

            result = orch.run()

        assert result.passed_nodes == 1
        node = nodes[0]
        assert node.implementation is not None
        assert node.test_code is not None
