"""TDD Generation Loop for graph-guided code generation.

Implements the core test-driven development loop:
test_generation -> implementation -> sandbox_execution -> debugging.

Each node goes through up to ``max_retries`` iterations. On pass the node
is marked PASSED and committed. On exhaustion it is marked FAILED and
downstream nodes are skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol
from uuid import UUID

from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols for pluggable components
# ---------------------------------------------------------------------------


class TestGenerator(Protocol):
    """Protocol for generating pytest test code from an RPG node."""

    def generate_tests(self, node: RPGNode, context: dict[str, Any]) -> str:
        """Generate pytest test code for *node*.

        Args:
            node: The RPG node to generate tests for.
            context: Additional context (ancestor implementations, etc.).

        Returns:
            A string of valid pytest test code.
        """
        ...  # pragma: no cover


class ImplementationGenerator(Protocol):
    """Protocol for generating implementation code from an RPG node."""

    def generate_implementation(
        self, node: RPGNode, test_code: str, context: dict[str, Any]
    ) -> str:
        """Generate implementation code that should pass *test_code*.

        Args:
            node: The RPG node to implement.
            test_code: The pytest test code to satisfy.
            context: Additional context (ancestor implementations, etc.).

        Returns:
            A string of valid Python implementation code.
        """
        ...  # pragma: no cover


class SandboxExecutor(Protocol):
    """Protocol for executing tests in an isolated sandbox."""

    def run_tests(
        self, implementation: str, test_code: str, node: RPGNode
    ) -> "SandboxResult":
        """Run *test_code* against *implementation* in a sandbox.

        Args:
            implementation: The Python implementation code.
            test_code: The pytest test code to run.
            node: The RPG node being tested.

        Returns:
            A SandboxResult with pass/fail counts and output.
        """
        ...  # pragma: no cover


class DebugDiagnoser(Protocol):
    """Protocol for diagnosing test failures and suggesting fixes."""

    def diagnose_and_fix(
        self,
        node: RPGNode,
        implementation: str,
        test_code: str,
        error_output: str,
        context: dict[str, Any],
    ) -> "DiagnosisResult":
        """Diagnose a test failure and produce a fix.

        Args:
            node: The RPG node whose tests failed.
            implementation: Current implementation code.
            test_code: The failing test code.
            error_output: stderr/stdout from the test run.
            context: Additional context for diagnosis.

        Returns:
            A DiagnosisResult with diagnosis classification and fixed code.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    """Result of running tests in the sandbox.

    Attributes:
        passed: Number of tests that passed.
        failed: Number of tests that failed.
        errors: Number of collection/runtime errors.
        stdout: Standard output from the test run.
        stderr: Standard error from the test run.
        duration_ms: Execution duration in milliseconds.
    """

    passed: int = 0
    failed: int = 0
    errors: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0

    @property
    def all_passed(self) -> bool:
        """Return True if all tests passed and no errors occurred."""
        return self.failed == 0 and self.errors == 0 and self.passed > 0


@dataclass
class DiagnosisResult:
    """Result of diagnosing a test failure.

    Attributes:
        classification: Failure classification
            ('implementation_bug', 'test_bug', 'environment').
        fixed_implementation: Updated implementation code (if impl bug).
        fixed_test_code: Updated test code (if test bug).
        explanation: Human-readable explanation of the diagnosis.
    """

    classification: str = "implementation_bug"
    fixed_implementation: str = ""
    fixed_test_code: str = ""
    explanation: str = ""


@dataclass
class TDDIterationResult:
    """Result of a single TDD loop iteration.

    Attributes:
        iteration: The iteration number (1-based).
        sandbox_result: The sandbox execution result.
        diagnosis: Diagnosis result if tests failed, else None.
        implementation: The implementation code used.
        test_code: The test code used.
    """

    iteration: int = 0
    sandbox_result: SandboxResult = field(default_factory=SandboxResult)
    diagnosis: Optional[DiagnosisResult] = None
    implementation: str = ""
    test_code: str = ""


@dataclass
class TDDLoopResult:
    """Aggregate result of the full TDD loop for a node.

    Attributes:
        node_id: UUID of the processed node.
        success: Whether the node ultimately passed.
        iterations: Number of iterations attempted.
        final_implementation: The final implementation code.
        final_test_code: The final test code.
        iteration_results: Per-iteration results.
        failure_reason: Reason for failure if not successful.
    """

    node_id: UUID = field(default_factory=lambda: UUID(int=0))
    success: bool = False
    iterations: int = 0
    final_implementation: str = ""
    final_test_code: str = ""
    iteration_results: list[TDDIterationResult] = field(default_factory=list)
    failure_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# TDD Loop Engine
# ---------------------------------------------------------------------------


class TDDLoop:
    """Orchestrates the test-driven development loop for a single RPG node.

    The loop follows the pattern:
    1. Generate test code from the node's docstring/specification
    2. Generate implementation code to satisfy the tests
    3. Run tests in sandbox
    4. If tests pass -> mark PASSED, return
    5. If tests fail -> diagnose, apply fix, retry (up to max_retries)
    6. If max retries exhausted -> mark FAILED

    Args:
        test_generator: Component for generating test code.
        impl_generator: Component for generating implementation code.
        sandbox_executor: Component for running tests in sandbox.
        debug_diagnoser: Component for diagnosing failures.
        state: GenerationState for tracking per-node progress.
        max_retries: Maximum retry iterations (default 8).
    """

    def __init__(
        self,
        test_generator: TestGenerator,
        impl_generator: ImplementationGenerator,
        sandbox_executor: SandboxExecutor,
        debug_diagnoser: DebugDiagnoser,
        state: GenerationState,
        *,
        max_retries: int = 8,
    ) -> None:
        self._test_gen = test_generator
        self._impl_gen = impl_generator
        self._sandbox = sandbox_executor
        self._diagnoser = debug_diagnoser
        self._state = state
        self._max_retries = max_retries

    @property
    def state(self) -> GenerationState:
        """The generation state tracker."""
        return self._state

    @property
    def max_retries(self) -> int:
        """Maximum retry iterations."""
        return self._max_retries

    def run(
        self,
        node: RPGNode,
        context: dict[str, Any] | None = None,
    ) -> TDDLoopResult:
        """Execute the TDD loop for a single node.

        Args:
            node: The RPG node to process.
            context: Additional context (ancestor implementations, etc.).

        Returns:
            A TDDLoopResult with the outcome of the loop.
        """
        ctx = context or {}
        result = TDDLoopResult(node_id=node.id)

        # Mark node as in-progress
        self._state.set_status(node.id, GenerationStatus.IN_PROGRESS)

        # Step 1: Generate tests
        logger.info("Generating tests for node %s (%s)", node.id, node.name)
        try:
            test_code = self._test_gen.generate_tests(node, ctx)
        except Exception as exc:
            logger.error("Test generation failed for %s: %s", node.id, exc)
            self._state.set_status(
                node.id,
                GenerationStatus.FAILED,
                failure_reason=f"Test generation error: {exc}",
            )
            result.failure_reason = f"Test generation error: {exc}"
            return result

        current_test_code = test_code
        current_impl = ""

        # Step 2: Generate initial implementation
        logger.info("Generating implementation for node %s", node.id)
        try:
            current_impl = self._impl_gen.generate_implementation(
                node, current_test_code, ctx
            )
        except Exception as exc:
            logger.error("Impl generation failed for %s: %s", node.id, exc)
            self._state.set_status(
                node.id,
                GenerationStatus.FAILED,
                failure_reason=f"Implementation generation error: {exc}",
            )
            result.failure_reason = f"Implementation generation error: {exc}"
            return result

        # Step 3: Iterate: run tests -> diagnose -> fix -> repeat
        for iteration in range(1, self._max_retries + 1):
            logger.info(
                "TDD iteration %d/%d for node %s",
                iteration,
                self._max_retries,
                node.id,
            )

            # Run tests in sandbox
            try:
                sandbox_result = self._sandbox.run_tests(
                    current_impl, current_test_code, node
                )
            except Exception as exc:
                logger.error("Sandbox execution failed: %s", exc)
                sandbox_result = SandboxResult(
                    failed=1,
                    stderr=f"Sandbox error: {exc}",
                )

            iter_result = TDDIterationResult(
                iteration=iteration,
                sandbox_result=sandbox_result,
                implementation=current_impl,
                test_code=current_test_code,
            )

            # Check if all tests passed
            if sandbox_result.all_passed:
                logger.info(
                    "Node %s passed on iteration %d (%d tests)",
                    node.id,
                    iteration,
                    sandbox_result.passed,
                )
                self._state.set_status(node.id, GenerationStatus.PASSED)
                self._state.update_test_results(
                    node.id,
                    passed=sandbox_result.passed,
                    failed=0,
                )
                result.success = True
                result.iterations = iteration
                result.final_implementation = current_impl
                result.final_test_code = current_test_code
                result.iteration_results.append(iter_result)
                return result

            # Tests failed -- diagnose and attempt fix
            error_output = sandbox_result.stderr or sandbox_result.stdout
            logger.info(
                "Node %s failed iteration %d: %d passed, %d failed",
                node.id,
                iteration,
                sandbox_result.passed,
                sandbox_result.failed,
            )

            # Record the retry
            self._state.increment_retry(node.id)

            if iteration < self._max_retries:
                try:
                    diagnosis = self._diagnoser.diagnose_and_fix(
                        node,
                        current_impl,
                        current_test_code,
                        error_output,
                        ctx,
                    )
                    iter_result.diagnosis = diagnosis

                    # Apply fix based on diagnosis
                    if (
                        diagnosis.classification == "implementation_bug"
                        and diagnosis.fixed_implementation
                    ):
                        current_impl = diagnosis.fixed_implementation
                    elif (
                        diagnosis.classification == "test_bug"
                        and diagnosis.fixed_test_code
                    ):
                        current_test_code = diagnosis.fixed_test_code
                    # environment errors: retry without change

                except Exception as exc:
                    logger.error("Diagnosis failed: %s", exc)

            result.iteration_results.append(iter_result)

        # Max retries exhausted -- mark as FAILED
        logger.warning(
            "Node %s exhausted %d retries, marking FAILED",
            node.id,
            self._max_retries,
        )
        self._state.set_status(
            node.id,
            GenerationStatus.FAILED,
            failure_reason=f"Exhausted {self._max_retries} retries",
        )
        self._state.update_test_results(
            node.id,
            passed=sandbox_result.passed,
            failed=sandbox_result.failed,
        )
        result.iterations = self._max_retries
        result.final_implementation = current_impl
        result.final_test_code = current_test_code
        result.failure_reason = f"Exhausted {self._max_retries} retries"
        return result
