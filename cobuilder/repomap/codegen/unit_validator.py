"""Unit test validation runner for graph-guided code generation.

Provides staged validation of generated test code by running pytest
inside Docker sandbox containers and parsing structured results.
Supports per-node validation with configurable timeouts and retry limits.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cobuilder.repomap.codegen.state import GenerationState, GenerationStatus

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                              Protocols                                       #
# --------------------------------------------------------------------------- #


class SandboxProtocol(Protocol):
    """Protocol for sandbox execution (Docker or mock)."""

    def run_code(
        self,
        container_id: str,
        code: str,
        entrypoint: str = "main.py",
    ) -> Any:
        """Run code in the sandbox and return an ExecutionResult-like object."""
        ...


# --------------------------------------------------------------------------- #
#                              Models                                          #
# --------------------------------------------------------------------------- #


class ValidationStage(str, Enum):
    """Stages in the unit validation pipeline."""

    SYNTAX_CHECK = "syntax_check"
    IMPORT_CHECK = "import_check"
    UNIT_TEST = "unit_test"


class TestOutcome(str, Enum):
    """Outcome of running a single test."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class SingleTestResult:
    """Result of a single test case execution.

    Attributes:
        test_name: Fully qualified test name (e.g., 'test_foo::TestBar::test_baz').
        outcome: Whether the test passed, failed, or errored.
        duration_ms: Execution time in milliseconds.
        error_message: Error details if the test failed or errored.
    """

    test_name: str
    outcome: TestOutcome
    duration_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Aggregate result of validating a single node's test code.

    Attributes:
        node_id: The UUID of the validated node.
        stage: Which validation stage produced this result.
        passed: Whether validation passed overall.
        total_tests: Total number of tests discovered.
        passed_tests: Number of tests that passed.
        failed_tests: Number of tests that failed.
        error_tests: Number of tests that errored.
        skipped_tests: Number of tests that were skipped.
        test_results: Per-test breakdown.
        stdout: Raw stdout from the test runner.
        stderr: Raw stderr from the test runner.
        duration_ms: Total validation time in milliseconds.
        error_message: Top-level error (e.g. syntax error before tests ran).
        timestamp: When the validation was performed.
    """

    node_id: UUID
    stage: ValidationStage
    passed: bool = False
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    skipped_tests: int = 0
    test_results: list[SingleTestResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UnitValidatorConfig(BaseModel):
    """Configuration for the UnitValidator.

    Attributes:
        timeout_seconds: Maximum time per test run.
        max_retries: Maximum retry attempts for flaky tests.
        fail_fast: Stop on first failure.
        collect_coverage: Whether to collect coverage data.
        pytest_args: Additional pytest command-line arguments.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    timeout_seconds: int = Field(
        default=60,
        ge=5,
        description="Maximum seconds per test run",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for flaky tests",
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop on first test failure",
    )
    collect_coverage: bool = Field(
        default=False,
        description="Whether to collect coverage data",
    )
    pytest_args: list[str] = Field(
        default_factory=list,
        description="Additional pytest command-line arguments",
    )


# --------------------------------------------------------------------------- #
#                           Pytest Output Parser                               #
# --------------------------------------------------------------------------- #

# Pattern for pytest's short test summary line: "PASSED tests/test_foo.py::test_bar"
_RESULT_LINE_RE = re.compile(
    r"^(PASSED|FAILED|ERROR|SKIPPED)\s+(.+?)(?:\s+-\s+(.+))?$"
)

# Pattern for pytest summary: "3 passed, 1 failed, 1 error in 2.45s"
_SUMMARY_RE = re.compile(
    r"(\d+)\s+(passed|failed|error|errors|skipped)"
)

# Pattern for individual test durations: "test_foo PASSED [ 12%]"
_DURATION_RE = re.compile(
    r"(.+?)\s+(PASSED|FAILED|ERROR|SKIPPED)\s+\[\s*\d+%\]"
)


def parse_pytest_output(
    stdout: str,
    stderr: str,
    node_id: UUID,
    stage: ValidationStage,
    duration_ms: float = 0.0,
) -> ValidationResult:
    """Parse pytest output into a structured ValidationResult.

    Handles standard pytest output format including verbose mode
    and short test summary sections.

    Args:
        stdout: Raw standard output from pytest.
        stderr: Raw standard error from pytest.
        node_id: The node UUID being validated.
        stage: Which validation stage this represents.
        duration_ms: Total execution time in milliseconds.

    Returns:
        A ValidationResult with parsed test outcomes.
    """
    test_results: list[SingleTestResult] = []
    passed_count = 0
    failed_count = 0
    error_count = 0
    skipped_count = 0

    # Parse summary line for counts
    combined = stdout + "\n" + stderr
    for match in _SUMMARY_RE.finditer(combined):
        count = int(match.group(1))
        status = match.group(2).lower()
        if status == "passed":
            passed_count = count
        elif status == "failed":
            failed_count = count
        elif status in ("error", "errors"):
            error_count = count
        elif status == "skipped":
            skipped_count = count

    # Parse individual test results from verbose output
    for line in stdout.splitlines():
        line = line.strip()
        match = _RESULT_LINE_RE.match(line)
        if match:
            outcome_str = match.group(1)
            test_name = match.group(2)
            error_msg = match.group(3)
            outcome = TestOutcome(outcome_str.lower())
            test_results.append(
                SingleTestResult(
                    test_name=test_name,
                    outcome=outcome,
                    error_message=error_msg,
                )
            )

    # If we got individual results but no summary, compute from results
    if not passed_count and not failed_count and test_results:
        for tr in test_results:
            if tr.outcome == TestOutcome.PASSED:
                passed_count += 1
            elif tr.outcome == TestOutcome.FAILED:
                failed_count += 1
            elif tr.outcome == TestOutcome.ERROR:
                error_count += 1
            elif tr.outcome == TestOutcome.SKIPPED:
                skipped_count += 1

    total = passed_count + failed_count + error_count + skipped_count
    overall_passed = (
        failed_count == 0
        and error_count == 0
        and passed_count > 0
    )

    # Check for top-level errors (syntax, import)
    error_message: Optional[str] = None
    if "SyntaxError" in combined:
        error_message = _extract_error(combined, "SyntaxError")
        overall_passed = False
    elif "ModuleNotFoundError" in combined:
        error_message = _extract_error(combined, "ModuleNotFoundError")
        overall_passed = False
    elif "ImportError" in combined:
        error_message = _extract_error(combined, "ImportError")
        overall_passed = False

    return ValidationResult(
        node_id=node_id,
        stage=stage,
        passed=overall_passed,
        total_tests=total,
        passed_tests=passed_count,
        failed_tests=failed_count,
        error_tests=error_count,
        skipped_tests=skipped_count,
        test_results=test_results,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        error_message=error_message,
    )


def _extract_error(text: str, error_type: str) -> str:
    """Extract the first error line of a given type from output text.

    Args:
        text: The raw output text.
        error_type: The error class name to look for.

    Returns:
        The error line, or a generic message if not found inline.
    """
    for line in text.splitlines():
        if error_type in line:
            return line.strip()
    return f"{error_type} detected in output"


# --------------------------------------------------------------------------- #
#                           Unit Validator                                     #
# --------------------------------------------------------------------------- #


class UnitValidator:
    """Validates generated unit tests by running them in a sandbox.

    Orchestrates a multi-stage validation pipeline:
    1. Syntax check (compile the test code)
    2. Import check (verify imports resolve)
    3. Full pytest run

    Args:
        sandbox: A sandbox instance (Docker or mock) implementing SandboxProtocol.
        config: Validation configuration.
        generation_state: Optional GenerationState for status tracking.
    """

    def __init__(
        self,
        sandbox: SandboxProtocol,
        config: UnitValidatorConfig | None = None,
        generation_state: GenerationState | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._config = config or UnitValidatorConfig()
        self._state = generation_state

    @property
    def config(self) -> UnitValidatorConfig:
        """The validator configuration."""
        return self._config

    @property
    def sandbox(self) -> SandboxProtocol:
        """The sandbox instance."""
        return self._sandbox

    def validate_syntax(
        self,
        node_id: UUID,
        test_code: str,
        container_id: str,
    ) -> ValidationResult:
        """Stage 1: Check if the test code is syntactically valid Python.

        Compiles the code using py_compile inside the sandbox.

        Args:
            node_id: The UUID of the node being validated.
            test_code: The Python test code to validate.
            container_id: The sandbox container to run in.

        Returns:
            A ValidationResult for the syntax check stage.
        """
        logger.info("Validating syntax for node %s", node_id)
        wrapper = (
            "import py_compile, sys, tempfile, os\n"
            "code = '''" + test_code.replace("'''", "\\'\\'\\'") + "'''\n"
            "fd, path = tempfile.mkstemp(suffix='.py')\n"
            "try:\n"
            "    with os.fdopen(fd, 'w') as f:\n"
            "        f.write(code)\n"
            "    py_compile.compile(path, doraise=True)\n"
            "    print('SYNTAX_OK')\n"
            "except py_compile.PyCompileError as e:\n"
            "    print(f'SyntaxError: {e}', file=sys.stderr)\n"
            "    sys.exit(1)\n"
            "finally:\n"
            "    os.unlink(path)\n"
        )

        result = self._sandbox.run_code(container_id, wrapper, "syntax_check.py")
        passed = getattr(result, "exit_code", 1) == 0
        duration = getattr(result, "duration_ms", 0.0)
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")

        error_msg = None
        if not passed:
            error_msg = stderr.strip() or "Syntax check failed"

        return ValidationResult(
            node_id=node_id,
            stage=ValidationStage.SYNTAX_CHECK,
            passed=passed,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration,
            error_message=error_msg,
        )

    def validate_imports(
        self,
        node_id: UUID,
        test_code: str,
        container_id: str,
    ) -> ValidationResult:
        """Stage 2: Check if the test code's imports resolve correctly.

        Extracts import lines and attempts to execute them in the sandbox.

        Args:
            node_id: The UUID of the node being validated.
            test_code: The Python test code to validate.
            container_id: The sandbox container to run in.

        Returns:
            A ValidationResult for the import check stage.
        """
        logger.info("Validating imports for node %s", node_id)
        import_lines = _extract_import_lines(test_code)

        if not import_lines:
            # No imports to validate
            return ValidationResult(
                node_id=node_id,
                stage=ValidationStage.IMPORT_CHECK,
                passed=True,
                stdout="No imports to validate",
            )

        import_script = "\n".join(import_lines) + "\nprint('IMPORTS_OK')\n"
        result = self._sandbox.run_code(container_id, import_script, "import_check.py")
        passed = getattr(result, "exit_code", 1) == 0
        duration = getattr(result, "duration_ms", 0.0)
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")

        error_msg = None
        if not passed:
            error_msg = stderr.strip() or "Import check failed"

        return ValidationResult(
            node_id=node_id,
            stage=ValidationStage.IMPORT_CHECK,
            passed=passed,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration,
            error_message=error_msg,
        )

    def run_tests(
        self,
        node_id: UUID,
        test_code: str,
        container_id: str,
        source_code: str = "",
    ) -> ValidationResult:
        """Stage 3: Run the full pytest suite for the node.

        Writes the test code and optional source code to the sandbox,
        then runs pytest with JSON output parsing.

        Args:
            node_id: The UUID of the node being validated.
            test_code: The Python test code to run.
            container_id: The sandbox container to run in.
            source_code: Optional source code the tests exercise.

        Returns:
            A ValidationResult for the unit test stage.
        """
        logger.info("Running tests for node %s", node_id)

        # Build pytest runner script
        pytest_args = ["-v", "--tb=short", "--no-header"]
        if self._config.fail_fast:
            pytest_args.append("-x")
        pytest_args.extend(self._config.pytest_args)

        args_str = ", ".join(f'"{a}"' for a in pytest_args)

        runner = (
            "import sys, os, tempfile\n"
            f"test_code = '''{_escape_triple_quotes(test_code)}'''\n"
        )

        if source_code:
            runner += (
                f"source_code = '''{_escape_triple_quotes(source_code)}'''\n"
                "with open('source_module.py', 'w') as f:\n"
                "    f.write(source_code)\n"
            )

        runner += (
            "with open('test_node.py', 'w') as f:\n"
            "    f.write(test_code)\n"
            "sys.exit(\n"
            f"    __import__('pytest').main(['test_node.py', {args_str}])\n"
            ")\n"
        )

        result = self._sandbox.run_code(container_id, runner, "test_runner.py")
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")
        duration = getattr(result, "duration_ms", 0.0)

        validation = parse_pytest_output(
            stdout=stdout,
            stderr=stderr,
            node_id=node_id,
            stage=ValidationStage.UNIT_TEST,
            duration_ms=duration,
        )

        # Update generation state if available
        if self._state:
            self._state.update_test_results(
                node_id,
                passed=validation.passed_tests,
                failed=validation.failed_tests + validation.error_tests,
            )
            if validation.passed:
                self._state.set_status(node_id, GenerationStatus.PASSED)
            else:
                self._state.set_status(
                    node_id,
                    GenerationStatus.FAILED,
                    failure_reason=validation.error_message or "Tests failed",
                )

        return validation

    def validate_node(
        self,
        node_id: UUID,
        test_code: str,
        container_id: str,
        source_code: str = "",
    ) -> ValidationResult:
        """Run the full multi-stage validation pipeline for a node.

        Stages run in order: syntax -> imports -> tests.
        Each stage must pass before proceeding to the next.

        Args:
            node_id: The UUID of the node being validated.
            test_code: The Python test code to validate.
            container_id: The sandbox container to run in.
            source_code: Optional source code the tests exercise.

        Returns:
            The ValidationResult from the last stage executed.
        """
        logger.info("Starting full validation for node %s", node_id)

        if self._state:
            self._state.set_status(node_id, GenerationStatus.IN_PROGRESS)

        # Stage 1: Syntax
        syntax_result = self.validate_syntax(node_id, test_code, container_id)
        if not syntax_result.passed:
            logger.warning(
                "Syntax check failed for node %s: %s",
                node_id,
                syntax_result.error_message,
            )
            if self._state:
                self._state.set_status(
                    node_id,
                    GenerationStatus.FAILED,
                    failure_reason=syntax_result.error_message,
                )
            return syntax_result

        # Stage 2: Imports
        import_result = self.validate_imports(node_id, test_code, container_id)
        if not import_result.passed:
            logger.warning(
                "Import check failed for node %s: %s",
                node_id,
                import_result.error_message,
            )
            if self._state:
                self._state.set_status(
                    node_id,
                    GenerationStatus.FAILED,
                    failure_reason=import_result.error_message,
                )
            return import_result

        # Stage 3: Full test run
        test_result = self.run_tests(
            node_id, test_code, container_id, source_code
        )
        return test_result


# --------------------------------------------------------------------------- #
#                           Helper Functions                                   #
# --------------------------------------------------------------------------- #


def _extract_import_lines(code: str) -> list[str]:
    """Extract import statements from Python source code.

    Args:
        code: Python source code.

    Returns:
        A list of import lines.
    """
    import_lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            import_lines.append(stripped)
    return import_lines


def _escape_triple_quotes(text: str) -> str:
    """Escape triple quotes in text for embedding in triple-quoted strings.

    Args:
        text: The text to escape.

    Returns:
        The escaped text.
    """
    return text.replace("'''", "\\'\\'\\'")
