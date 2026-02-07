"""Main code generation orchestrator for graph-guided code generation.

Coordinates the full pipeline: topological traversal -> TDD loop ->
test validation -> assembly. Manages progress logging, checkpointing,
and graceful shutdown.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.codegen.tdd_loop import (
    DebugDiagnoser,
    ImplementationGenerator,
    SandboxExecutor,
    TDDLoop,
    TDDLoopResult,
    TestGenerator,
)
from zerorepo.codegen.traversal import TraversalEngine, TraversalReport
from zerorepo.models.enums import NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorConfig:
    """Configuration for the code generation orchestrator.

    Attributes:
        max_retries: Maximum TDD loop retries per node.
        checkpoint_interval: Save checkpoint every N nodes.
        progress_log_interval: Log progress every N nodes.
        fail_fast: Stop on first node failure.
        skip_non_leaf: Whether to skip non-FUNCTION_AUGMENTED nodes.
    """

    max_retries: int = 8
    checkpoint_interval: int = 5
    progress_log_interval: int = 10
    fail_fast: bool = False
    skip_non_leaf: bool = True


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class NodeResult:
    """Result of processing a single node.

    Attributes:
        node_id: UUID of the processed node.
        node_name: Human-readable name of the node.
        success: Whether the node passed.
        tdd_result: The TDD loop result, if a TDD loop was run.
        skipped: Whether the node was skipped.
        skip_reason: Reason for skipping.
    """

    node_id: UUID = field(default_factory=lambda: UUID(int=0))
    node_name: str = ""
    success: bool = False
    tdd_result: Optional[TDDLoopResult] = None
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class OrchestratorResult:
    """Aggregate result of the full code generation run.

    Attributes:
        total_nodes: Total number of nodes in the graph.
        processed_nodes: Number of nodes actually processed.
        passed_nodes: Number of nodes that passed.
        failed_nodes: Number of nodes that failed.
        skipped_nodes: Number of nodes that were skipped.
        node_results: Per-node results.
        traversal_report: Final traversal report.
        elapsed_seconds: Total wall-clock time.
        checkpoint_path: Path to the final checkpoint.
    """

    total_nodes: int = 0
    processed_nodes: int = 0
    passed_nodes: int = 0
    failed_nodes: int = 0
    skipped_nodes: int = 0
    node_results: list[NodeResult] = field(default_factory=list)
    traversal_report: Optional[TraversalReport] = None
    elapsed_seconds: float = 0.0
    checkpoint_path: str = ""

    @property
    def pass_rate(self) -> float:
        """Compute the pass rate as a percentage."""
        if self.total_nodes == 0:
            return 0.0
        return (self.passed_nodes / self.total_nodes) * 100.0


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


class CodegenOrchestrator:
    """Orchestrate the full code generation pipeline.

    Coordinates:
    1. Topological traversal order computation
    2. Per-node TDD loop execution
    3. Progress logging and checkpointing
    4. Failure propagation to downstream nodes
    5. Final report generation

    Args:
        graph: The RPGGraph to generate code for.
        test_generator: Component for generating test code.
        impl_generator: Component for generating implementation code.
        sandbox_executor: Component for running tests in sandbox.
        debug_diagnoser: Component for diagnosing failures.
        config: Orchestrator configuration.
        state: Optional pre-existing GenerationState (for resume).
    """

    def __init__(
        self,
        graph: RPGGraph,
        test_generator: TestGenerator,
        impl_generator: ImplementationGenerator,
        sandbox_executor: SandboxExecutor,
        debug_diagnoser: DebugDiagnoser,
        config: OrchestratorConfig | None = None,
        state: GenerationState | None = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._state = state or GenerationState(
            max_retries=self._config.max_retries
        )
        self._traversal = TraversalEngine(
            graph, self._state, max_retries=self._config.max_retries
        )
        self._tdd_loop = TDDLoop(
            test_generator=test_generator,
            impl_generator=impl_generator,
            sandbox_executor=sandbox_executor,
            debug_diagnoser=debug_diagnoser,
            state=self._state,
            max_retries=self._config.max_retries,
        )
        self._shutdown_requested = False

    @property
    def graph(self) -> RPGGraph:
        """The RPGGraph being processed."""
        return self._traversal.graph

    @property
    def state(self) -> GenerationState:
        """The generation state tracker."""
        return self._state

    @property
    def traversal(self) -> TraversalEngine:
        """The traversal engine."""
        return self._traversal

    def request_shutdown(self) -> None:
        """Request graceful shutdown after the current node completes."""
        logger.info("Graceful shutdown requested")
        self._shutdown_requested = True

    def run(self) -> OrchestratorResult:
        """Execute the full code generation pipeline.

        Returns:
            An OrchestratorResult with the outcome of the run.
        """
        start_time = time.monotonic()
        result = OrchestratorResult()

        # Compute traversal order
        if self._config.skip_non_leaf:
            ordered_nodes = self._traversal.compute_generation_order()
        else:
            ordered_nodes = self._traversal.compute_order()

        result.total_nodes = len(ordered_nodes)
        logger.info(
            "Starting code generation for %d nodes", result.total_nodes
        )

        # Process each node in topological order
        for idx, node in enumerate(ordered_nodes, 1):
            if self._shutdown_requested:
                logger.info("Shutdown requested, stopping after %d nodes", idx - 1)
                break

            # Check if node should be processed
            if not self._traversal.should_process(node.id):
                node_state = self._state.get_node_state(node.id)
                result.node_results.append(
                    NodeResult(
                        node_id=node.id,
                        node_name=node.name,
                        success=node_state.status == GenerationStatus.PASSED,
                        skipped=node_state.status == GenerationStatus.SKIPPED,
                        skip_reason=f"Status: {node_state.status.value}",
                    )
                )
                if node_state.status == GenerationStatus.PASSED:
                    result.passed_nodes += 1
                elif node_state.status == GenerationStatus.SKIPPED:
                    result.skipped_nodes += 1
                continue

            # Process the node
            node_result = self._process_node(node)
            result.node_results.append(node_result)
            result.processed_nodes += 1

            if node_result.success:
                result.passed_nodes += 1
            elif node_result.skipped:
                result.skipped_nodes += 1
            else:
                result.failed_nodes += 1

                # Propagate failure to downstream nodes
                skipped_ids = self._traversal.mark_failed(
                    node.id,
                    reason=node_result.tdd_result.failure_reason
                    if node_result.tdd_result
                    else "Unknown failure",
                )
                if skipped_ids:
                    logger.info(
                        "Skipped %d downstream nodes due to failure of %s",
                        len(skipped_ids),
                        node.id,
                    )

                # Fail fast if configured
                if self._config.fail_fast:
                    logger.info("Fail-fast enabled, stopping pipeline")
                    break

            # Progress logging
            if idx % self._config.progress_log_interval == 0:
                self._log_progress(idx, result)

            # Checkpoint
            if idx % self._config.checkpoint_interval == 0:
                self._save_checkpoint()

        # Final checkpoint
        checkpoint_path = self._save_checkpoint()
        result.checkpoint_path = checkpoint_path

        # Generate traversal report
        result.traversal_report = self._traversal.generate_report()
        result.elapsed_seconds = time.monotonic() - start_time

        logger.info(
            "Code generation complete: %d/%d passed (%.1f%%) in %.1fs",
            result.passed_nodes,
            result.total_nodes,
            result.pass_rate,
            result.elapsed_seconds,
        )

        return result

    def _process_node(self, node: RPGNode) -> NodeResult:
        """Process a single node through the TDD loop.

        Args:
            node: The RPG node to process.

        Returns:
            A NodeResult with the outcome.
        """
        logger.info("Processing node %s (%s)", node.id, node.name)

        # Build context from ancestor implementations
        context = self._build_node_context(node)

        # Run TDD loop
        tdd_result = self._tdd_loop.run(node, context)

        # Update node with generated code if successful
        if tdd_result.success:
            node.implementation = tdd_result.final_implementation
            node.test_code = tdd_result.final_test_code

        return NodeResult(
            node_id=node.id,
            node_name=node.name,
            success=tdd_result.success,
            tdd_result=tdd_result,
        )

    def _build_node_context(self, node: RPGNode) -> dict[str, Any]:
        """Build context from ancestor nodes for code generation.

        Collects implementations from ancestor nodes that have already
        been generated, so the current node can reference them.

        Args:
            node: The node to build context for.

        Returns:
            A context dict with ancestor_implementations.
        """
        from zerorepo.graph_ops.traversal import get_ancestors
        from zerorepo.models.enums import EdgeType

        ancestor_impls: dict[str, str] = {}

        try:
            ancestors = get_ancestors(
                self._traversal.graph,
                node.id,
                [EdgeType.DATA_FLOW, EdgeType.HIERARCHY],
            )
            for anc_id in ancestors:
                anc_node = self._traversal.graph.nodes.get(anc_id)
                if anc_node and anc_node.implementation:
                    ancestor_impls[anc_node.name] = anc_node.implementation
        except Exception:
            logger.warning(
                "Failed to collect ancestor context for node %s", node.id
            )

        return {"ancestor_implementations": ancestor_impls}

    def _log_progress(self, processed: int, result: OrchestratorResult) -> None:
        """Log progress at regular intervals.

        Args:
            processed: Number of nodes processed so far.
            result: Current aggregate result.
        """
        logger.info(
            "Progress: %d/%d nodes | passed=%d, failed=%d, skipped=%d",
            processed,
            result.total_nodes,
            result.passed_nodes,
            result.failed_nodes,
            result.skipped_nodes,
        )

    def _save_checkpoint(self) -> str:
        """Save the current generation state checkpoint.

        Returns:
            The path the checkpoint was saved to.
        """
        try:
            path = self._state.save()
            logger.debug("Checkpoint saved to %s", path)
            return path
        except Exception as exc:
            logger.error("Failed to save checkpoint: %s", exc)
            return ""
