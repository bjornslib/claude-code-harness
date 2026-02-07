"""Unit tests for the TDD generation loop."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.codegen.tdd_loop import (
    DebugDiagnoser,
    DiagnosisResult,
    ImplementationGenerator,
    SandboxExecutor,
    SandboxResult,
    TDDIterationResult,
    TDDLoop,
    TDDLoopResult,
    TestGenerator,
)
from zerorepo.models.enums import InterfaceType, NodeLevel, NodeType
from zerorepo.models.node import RPGNode


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_func_node(
    *,
    name: str = "calculate_mean",
    node_id=None,
    docstring: str | None = "Calculate the mean of a list of numbers.",
    signature: str | None = "def calculate_mean(numbers: list[float]) -> float",
) -> RPGNode:
    """Create a FUNCTION_AUGMENTED node for testing."""
    kwargs: dict[str, Any] = dict(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        folder_path="src",
        file_path="src/module.py",
        signature=signature,
        docstring=docstring,
    )
    if node_id is not None:
        kwargs["id"] = node_id
    return RPGNode(**kwargs)


class MockTestGenerator:
    """Mock test generator that returns a fixed test string."""

    def __init__(self, test_code: str = "def test_it(): assert True"):
        self._test_code = test_code
        self.call_count = 0

    def generate_tests(self, node: RPGNode, context: dict[str, Any]) -> str:
        self.call_count += 1
        return self._test_code


class MockImplGenerator:
    """Mock implementation generator that returns a fixed implementation."""

    def __init__(self, impl_code: str = "def calculate_mean(numbers): return sum(numbers) / len(numbers)"):
        self._impl_code = impl_code
        self.call_count = 0

    def generate_implementation(
        self, node: RPGNode, test_code: str, context: dict[str, Any]
    ) -> str:
        self.call_count += 1
        return self._impl_code


class MockSandboxExecutor:
    """Mock sandbox executor with configurable results per call."""

    def __init__(self, results: list[SandboxResult] | None = None):
        self._results = results or [SandboxResult(passed=1, failed=0)]
        self._call_idx = 0
        self.call_count = 0

    def run_tests(
        self, implementation: str, test_code: str, node: RPGNode
    ) -> SandboxResult:
        self.call_count += 1
        idx = min(self._call_idx, len(self._results) - 1)
        self._call_idx += 1
        return self._results[idx]


class MockDebugDiagnoser:
    """Mock diagnoser that returns a fixed diagnosis."""

    def __init__(
        self,
        classification: str = "implementation_bug",
        fixed_impl: str = "def calculate_mean(numbers): return sum(numbers) / max(len(numbers), 1)",
    ):
        self._classification = classification
        self._fixed_impl = fixed_impl
        self.call_count = 0

    def diagnose_and_fix(
        self,
        node: RPGNode,
        implementation: str,
        test_code: str,
        error_output: str,
        context: dict[str, Any],
    ) -> DiagnosisResult:
        self.call_count += 1
        result = DiagnosisResult(classification=self._classification)
        if self._classification == "implementation_bug":
            result.fixed_implementation = self._fixed_impl
        elif self._classification == "test_bug":
            result.fixed_test_code = "def test_it(): assert True"
        return result


class FailingTestGenerator:
    """Test generator that raises an exception."""

    def generate_tests(self, node: RPGNode, context: dict[str, Any]) -> str:
        raise RuntimeError("LLM unavailable")


class FailingImplGenerator:
    """Implementation generator that raises an exception."""

    def generate_implementation(
        self, node: RPGNode, test_code: str, context: dict[str, Any]
    ) -> str:
        raise RuntimeError("LLM unavailable")


# --------------------------------------------------------------------------- #
#                              Tests                                           #
# --------------------------------------------------------------------------- #


class TestSandboxResult:
    """Tests for SandboxResult data class."""

    def test_all_passed_true(self):
        result = SandboxResult(passed=5, failed=0, errors=0)
        assert result.all_passed is True

    def test_all_passed_false_with_failures(self):
        result = SandboxResult(passed=3, failed=2, errors=0)
        assert result.all_passed is False

    def test_all_passed_false_with_errors(self):
        result = SandboxResult(passed=3, failed=0, errors=1)
        assert result.all_passed is False

    def test_all_passed_false_when_zero_passed(self):
        result = SandboxResult(passed=0, failed=0, errors=0)
        assert result.all_passed is False


class TestTDDLoopResult:
    """Tests for TDDLoopResult data class."""

    def test_default_values(self):
        result = TDDLoopResult()
        assert result.success is False
        assert result.iterations == 0
        assert result.final_implementation == ""
        assert result.final_test_code == ""
        assert result.failure_reason is None
        assert result.iteration_results == []


class TestTDDLoop:
    """Tests for the TDDLoop engine."""

    def test_pass_on_first_iteration(self):
        """Simple node passes on first iteration."""
        node = _make_func_node()
        state = GenerationState()

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=3, failed=0),
            ]),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=8,
        )

        result = loop.run(node)

        assert result.success is True
        assert result.iterations == 1
        assert result.final_implementation != ""
        assert result.final_test_code != ""
        assert state.get_node_state(node.id).status == GenerationStatus.PASSED
        assert state.get_node_state(node.id).test_results.passed == 3

    def test_pass_after_retry(self):
        """Node fails first, then passes on second iteration."""
        node = _make_func_node()
        state = GenerationState()

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=1, failed=2, stderr="AssertionError"),
                SandboxResult(passed=3, failed=0),
            ]),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=8,
        )

        result = loop.run(node)

        assert result.success is True
        assert result.iterations == 2
        assert len(result.iteration_results) == 2

    def test_debugging_iteration_limit(self):
        """Node fails 8 times -> marks FAILED."""
        node = _make_func_node()
        state = GenerationState()

        # All 8 iterations fail
        failing_results = [
            SandboxResult(passed=0, failed=1, stderr="Error")
            for _ in range(8)
        ]

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor(failing_results),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=8,
        )

        result = loop.run(node)

        assert result.success is False
        assert result.iterations == 8
        assert result.failure_reason is not None
        assert "Exhausted 8 retries" in result.failure_reason
        assert state.get_node_state(node.id).status == GenerationStatus.FAILED

    def test_custom_max_retries(self):
        """Custom max_retries is respected."""
        node = _make_func_node()
        state = GenerationState()

        failing_results = [
            SandboxResult(passed=0, failed=1, stderr="Error")
            for _ in range(3)
        ]

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor(failing_results),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=3,
        )

        result = loop.run(node)

        assert result.success is False
        assert result.iterations == 3

    def test_test_generation_failure(self):
        """Test generation error marks node FAILED immediately."""
        node = _make_func_node()
        state = GenerationState()

        loop = TDDLoop(
            test_generator=FailingTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor(),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
        )

        result = loop.run(node)

        assert result.success is False
        assert "Test generation error" in result.failure_reason
        assert state.get_node_state(node.id).status == GenerationStatus.FAILED

    def test_impl_generation_failure(self):
        """Implementation generation error marks node FAILED immediately."""
        node = _make_func_node()
        state = GenerationState()

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=FailingImplGenerator(),
            sandbox_executor=MockSandboxExecutor(),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
        )

        result = loop.run(node)

        assert result.success is False
        assert "Implementation generation error" in result.failure_reason
        assert state.get_node_state(node.id).status == GenerationStatus.FAILED

    def test_sandbox_exception_treated_as_failure(self):
        """Sandbox exception is caught and treated as a test failure."""
        node = _make_func_node()
        state = GenerationState()

        class ExplodingSandbox:
            def run_tests(self, impl, test, node):
                raise RuntimeError("Docker crashed")

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=ExplodingSandbox(),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=2,
        )

        result = loop.run(node)

        # Should exhaust retries gracefully, not crash
        assert result.success is False
        assert result.iterations == 2

    def test_diagnosis_applies_implementation_fix(self):
        """Diagnoser fixes implementation bug: new impl used on retry."""
        node = _make_func_node()
        state = GenerationState()
        fixed_impl = "def calculate_mean(numbers): return sum(numbers) / max(len(numbers), 1)"

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(
                impl_code="def calculate_mean(numbers): return 0"
            ),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=0, failed=1, stderr="AssertionError"),
                SandboxResult(passed=3, failed=0),  # pass after fix
            ]),
            debug_diagnoser=MockDebugDiagnoser(
                classification="implementation_bug",
                fixed_impl=fixed_impl,
            ),
            state=state,
            max_retries=8,
        )

        result = loop.run(node)

        assert result.success is True
        assert result.iterations == 2
        assert result.final_implementation == fixed_impl

    def test_diagnosis_applies_test_fix(self):
        """Diagnoser fixes test bug: new tests used on retry."""
        node = _make_func_node()
        state = GenerationState()

        loop = TDDLoop(
            test_generator=MockTestGenerator("def test_broken(): assert False"),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=0, failed=1, stderr="AssertionError"),
                SandboxResult(passed=1, failed=0),
            ]),
            debug_diagnoser=MockDebugDiagnoser(
                classification="test_bug",
            ),
            state=state,
            max_retries=8,
        )

        result = loop.run(node)

        assert result.success is True
        assert result.iterations == 2

    def test_state_transitions(self):
        """Verify state transitions during TDD loop."""
        node = _make_func_node()
        state = GenerationState()

        # Starts PENDING
        assert state.get_node_state(node.id).status == GenerationStatus.PENDING

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=1, failed=0),
            ]),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
        )

        loop.run(node)

        # Ends PASSED
        assert state.get_node_state(node.id).status == GenerationStatus.PASSED

    def test_properties(self):
        """Test TDDLoop properties."""
        state = GenerationState()
        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor(),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=5,
        )

        assert loop.state is state
        assert loop.max_retries == 5

    def test_iteration_results_populated(self):
        """Each iteration populates an TDDIterationResult."""
        node = _make_func_node()
        state = GenerationState()

        loop = TDDLoop(
            test_generator=MockTestGenerator(),
            impl_generator=MockImplGenerator(),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=0, failed=1, stderr="fail"),
                SandboxResult(passed=0, failed=1, stderr="fail"),
                SandboxResult(passed=3, failed=0),
            ]),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
            max_retries=8,
        )

        result = loop.run(node)

        assert result.success is True
        assert result.iterations == 3
        assert len(result.iteration_results) == 3

        # First two should have diagnosis
        assert result.iteration_results[0].diagnosis is not None
        assert result.iteration_results[1].diagnosis is not None
        # Last one (success) should not
        assert result.iteration_results[2].diagnosis is None

    def test_context_passed_to_generators(self):
        """Context dict is forwarded to test and impl generators."""
        node = _make_func_node()
        state = GenerationState()
        context = {"ancestor_implementations": {"helper": "def helper(): pass"}}

        received_contexts: list[dict] = []

        class CapturingTestGen:
            def generate_tests(self, n, ctx):
                received_contexts.append(ctx)
                return "def test_it(): assert True"

        class CapturingImplGen:
            def generate_implementation(self, n, test_code, ctx):
                received_contexts.append(ctx)
                return "def calculate_mean(numbers): return 0"

        loop = TDDLoop(
            test_generator=CapturingTestGen(),
            impl_generator=CapturingImplGen(),
            sandbox_executor=MockSandboxExecutor([
                SandboxResult(passed=1, failed=0),
            ]),
            debug_diagnoser=MockDebugDiagnoser(),
            state=state,
        )

        loop.run(node, context)

        assert len(received_contexts) == 2
        for ctx in received_contexts:
            assert "ancestor_implementations" in ctx
