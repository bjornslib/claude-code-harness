"""Unit tests for the codegen unit_validator module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from zerorepo.codegen.state import GenerationState, GenerationStatus
from zerorepo.codegen.unit_validator import (
    SingleTestResult,
    TestOutcome,
    UnitValidator,
    UnitValidatorConfig,
    ValidationResult,
    ValidationStage,
    parse_pytest_output,
    _extract_import_lines,
    _escape_triple_quotes,
)


# --------------------------------------------------------------------------- #
#                              Mock Sandbox                                    #
# --------------------------------------------------------------------------- #


@dataclass
class MockExecutionResult:
    """Mock execution result matching sandbox.ExecutionResult interface."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: float = 10.0


class MockSandbox:
    """Mock sandbox for testing the UnitValidator without Docker."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._responses: list[MockExecutionResult] = []
        self._default_result = MockExecutionResult()

    def set_responses(self, responses: list[MockExecutionResult]) -> None:
        """Queue up responses for successive calls."""
        self._responses = list(responses)

    def set_default(self, result: MockExecutionResult) -> None:
        """Set the default response when no queued responses remain."""
        self._default_result = result

    def run_code(
        self,
        container_id: str,
        code: str,
        entrypoint: str = "main.py",
    ) -> MockExecutionResult:
        self.calls.append(
            {"container_id": container_id, "code": code, "entrypoint": entrypoint}
        )
        if self._responses:
            return self._responses.pop(0)
        return self._default_result


# --------------------------------------------------------------------------- #
#                         Test: ValidationStage Enum                           #
# --------------------------------------------------------------------------- #


class TestValidationStage:
    """Test ValidationStage enum values."""

    def test_all_values_present(self) -> None:
        assert ValidationStage.SYNTAX_CHECK == "syntax_check"
        assert ValidationStage.IMPORT_CHECK == "import_check"
        assert ValidationStage.UNIT_TEST == "unit_test"

    def test_is_string_enum(self) -> None:
        assert isinstance(ValidationStage.SYNTAX_CHECK, str)

    def test_from_value(self) -> None:
        assert ValidationStage("syntax_check") == ValidationStage.SYNTAX_CHECK

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ValidationStage("invalid")


# --------------------------------------------------------------------------- #
#                         Test: TestOutcome Enum                               #
# --------------------------------------------------------------------------- #


class TestTestOutcome:
    """Test TestOutcome enum values."""

    def test_all_values_present(self) -> None:
        assert TestOutcome.PASSED == "passed"
        assert TestOutcome.FAILED == "failed"
        assert TestOutcome.ERROR == "error"
        assert TestOutcome.SKIPPED == "skipped"

    def test_from_value(self) -> None:
        assert TestOutcome("passed") == TestOutcome.PASSED

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            TestOutcome("unknown")


# --------------------------------------------------------------------------- #
#                         Test: SingleTestResult                               #
# --------------------------------------------------------------------------- #


class TestSingleTestResult:
    """Test SingleTestResult dataclass."""

    def test_default_values(self) -> None:
        result = SingleTestResult(test_name="test_foo", outcome=TestOutcome.PASSED)
        assert result.test_name == "test_foo"
        assert result.outcome == TestOutcome.PASSED
        assert result.duration_ms == 0.0
        assert result.error_message is None

    def test_with_error(self) -> None:
        result = SingleTestResult(
            test_name="test_bar",
            outcome=TestOutcome.FAILED,
            error_message="AssertionError",
        )
        assert result.error_message == "AssertionError"

    def test_with_duration(self) -> None:
        result = SingleTestResult(
            test_name="test_baz",
            outcome=TestOutcome.PASSED,
            duration_ms=42.5,
        )
        assert result.duration_ms == 42.5


# --------------------------------------------------------------------------- #
#                         Test: ValidationResult                               #
# --------------------------------------------------------------------------- #


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_default_values(self) -> None:
        node_id = uuid4()
        result = ValidationResult(
            node_id=node_id, stage=ValidationStage.UNIT_TEST
        )
        assert result.node_id == node_id
        assert result.stage == ValidationStage.UNIT_TEST
        assert result.passed is False
        assert result.total_tests == 0
        assert result.passed_tests == 0
        assert result.failed_tests == 0
        assert result.error_tests == 0
        assert result.skipped_tests == 0
        assert result.test_results == []
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.error_message is None

    def test_with_counts(self) -> None:
        result = ValidationResult(
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
            passed=True,
            total_tests=10,
            passed_tests=8,
            failed_tests=1,
            skipped_tests=1,
        )
        assert result.total_tests == 10
        assert result.passed_tests == 8

    def test_timestamp_is_set(self) -> None:
        result = ValidationResult(
            node_id=uuid4(), stage=ValidationStage.SYNTAX_CHECK
        )
        assert isinstance(result.timestamp, datetime)


# --------------------------------------------------------------------------- #
#                         Test: UnitValidatorConfig                            #
# --------------------------------------------------------------------------- #


class TestUnitValidatorConfig:
    """Test UnitValidatorConfig Pydantic model."""

    def test_default_values(self) -> None:
        config = UnitValidatorConfig()
        assert config.timeout_seconds == 60
        assert config.max_retries == 3
        assert config.fail_fast is False
        assert config.collect_coverage is False
        assert config.pytest_args == []

    def test_custom_values(self) -> None:
        config = UnitValidatorConfig(
            timeout_seconds=120,
            max_retries=5,
            fail_fast=True,
            pytest_args=["--cov"],
        )
        assert config.timeout_seconds == 120
        assert config.max_retries == 5
        assert config.fail_fast is True
        assert config.pytest_args == ["--cov"]

    def test_timeout_minimum(self) -> None:
        with pytest.raises(Exception):
            UnitValidatorConfig(timeout_seconds=2)

    def test_retries_minimum(self) -> None:
        with pytest.raises(Exception):
            UnitValidatorConfig(max_retries=-1)


# --------------------------------------------------------------------------- #
#                         Test: parse_pytest_output                            #
# --------------------------------------------------------------------------- #


class TestParsePytestOutput:
    """Test the pytest output parser."""

    def test_all_passed(self) -> None:
        stdout = "3 passed in 0.45s"
        result = parse_pytest_output(
            stdout=stdout,
            stderr="",
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
        )
        assert result.passed is True
        assert result.passed_tests == 3
        assert result.total_tests == 3
        assert result.failed_tests == 0

    def test_mixed_results(self) -> None:
        stdout = "2 passed, 1 failed, 1 error in 1.23s"
        result = parse_pytest_output(
            stdout=stdout,
            stderr="",
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
        )
        assert result.passed is False
        assert result.passed_tests == 2
        assert result.failed_tests == 1
        assert result.error_tests == 1
        assert result.total_tests == 4

    def test_syntax_error_detected(self) -> None:
        stderr = "SyntaxError: invalid syntax (test_foo.py, line 5)"
        result = parse_pytest_output(
            stdout="",
            stderr=stderr,
            node_id=uuid4(),
            stage=ValidationStage.SYNTAX_CHECK,
        )
        assert result.passed is False
        assert result.error_message is not None
        assert "SyntaxError" in result.error_message

    def test_import_error_detected(self) -> None:
        stderr = "ImportError: No module named 'nonexistent'"
        result = parse_pytest_output(
            stdout="",
            stderr=stderr,
            node_id=uuid4(),
            stage=ValidationStage.IMPORT_CHECK,
        )
        assert result.passed is False
        assert "ImportError" in (result.error_message or "")

    def test_module_not_found_error(self) -> None:
        stderr = "ModuleNotFoundError: No module named 'missing_pkg'"
        result = parse_pytest_output(
            stdout="",
            stderr=stderr,
            node_id=uuid4(),
            stage=ValidationStage.IMPORT_CHECK,
        )
        assert result.passed is False
        assert "ModuleNotFoundError" in (result.error_message or "")

    def test_empty_output(self) -> None:
        result = parse_pytest_output(
            stdout="",
            stderr="",
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
        )
        assert result.passed is False
        assert result.total_tests == 0

    def test_individual_results_parsed(self) -> None:
        stdout = (
            "PASSED tests/test_foo.py::test_one\n"
            "PASSED tests/test_foo.py::test_two\n"
            "FAILED tests/test_foo.py::test_three - AssertionError\n"
            "2 passed, 1 failed in 0.5s"
        )
        result = parse_pytest_output(
            stdout=stdout,
            stderr="",
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
        )
        assert len(result.test_results) == 3
        assert result.test_results[0].outcome == TestOutcome.PASSED
        assert result.test_results[2].outcome == TestOutcome.FAILED
        assert result.test_results[2].error_message == "AssertionError"

    def test_only_skipped(self) -> None:
        stdout = "3 skipped in 0.1s"
        result = parse_pytest_output(
            stdout=stdout,
            stderr="",
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
        )
        assert result.passed is False
        assert result.skipped_tests == 3
        assert result.total_tests == 3

    def test_duration_preserved(self) -> None:
        result = parse_pytest_output(
            stdout="1 passed in 0.1s",
            stderr="",
            node_id=uuid4(),
            stage=ValidationStage.UNIT_TEST,
            duration_ms=150.0,
        )
        assert result.duration_ms == 150.0


# --------------------------------------------------------------------------- #
#                         Test: Helper Functions                               #
# --------------------------------------------------------------------------- #


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_extract_import_lines(self) -> None:
        code = (
            "import os\n"
            "from pathlib import Path\n"
            "\n"
            "# comment\n"
            "x = 1\n"
            "from collections import defaultdict\n"
        )
        result = _extract_import_lines(code)
        assert result == [
            "import os",
            "from pathlib import Path",
            "from collections import defaultdict",
        ]

    def test_extract_import_lines_empty(self) -> None:
        assert _extract_import_lines("x = 1\ny = 2\n") == []

    def test_escape_triple_quotes(self) -> None:
        assert "'''" not in _escape_triple_quotes("hello '''world'''")


# --------------------------------------------------------------------------- #
#                         Test: UnitValidator                                  #
# --------------------------------------------------------------------------- #


class TestUnitValidator:
    """Test UnitValidator orchestration."""

    def setup_method(self) -> None:
        self.sandbox = MockSandbox()
        self.node_id = uuid4()
        self.container_id = "test-container-001"

    def test_validate_syntax_pass(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(stdout="SYNTAX_OK", exit_code=0, duration_ms=5.0)
        )
        validator = UnitValidator(self.sandbox)
        result = validator.validate_syntax(
            self.node_id, "print('hello')", self.container_id
        )
        assert result.passed is True
        assert result.stage == ValidationStage.SYNTAX_CHECK
        assert len(self.sandbox.calls) == 1

    def test_validate_syntax_fail(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(
                stderr="SyntaxError: invalid syntax",
                exit_code=1,
                duration_ms=3.0,
            )
        )
        validator = UnitValidator(self.sandbox)
        result = validator.validate_syntax(
            self.node_id, "def foo(:", self.container_id
        )
        assert result.passed is False
        assert result.error_message is not None

    def test_validate_imports_pass(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(stdout="IMPORTS_OK", exit_code=0)
        )
        validator = UnitValidator(self.sandbox)
        result = validator.validate_imports(
            self.node_id, "import os\nimport sys\n", self.container_id
        )
        assert result.passed is True
        assert result.stage == ValidationStage.IMPORT_CHECK

    def test_validate_imports_fail(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(
                stderr="ModuleNotFoundError: No module named 'nonexistent'",
                exit_code=1,
            )
        )
        validator = UnitValidator(self.sandbox)
        result = validator.validate_imports(
            self.node_id,
            "import nonexistent\n",
            self.container_id,
        )
        assert result.passed is False

    def test_validate_imports_no_imports(self) -> None:
        validator = UnitValidator(self.sandbox)
        result = validator.validate_imports(
            self.node_id, "x = 1\ny = 2\n", self.container_id
        )
        assert result.passed is True
        assert len(self.sandbox.calls) == 0  # No sandbox call needed

    def test_run_tests_pass(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(
                stdout="3 passed in 0.5s",
                exit_code=0,
                duration_ms=500.0,
            )
        )
        validator = UnitValidator(self.sandbox)
        result = validator.run_tests(
            self.node_id,
            "def test_ok(): assert True\n",
            self.container_id,
        )
        assert result.passed is True
        assert result.passed_tests == 3
        assert result.stage == ValidationStage.UNIT_TEST

    def test_run_tests_fail(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(
                stdout="1 passed, 2 failed in 0.5s",
                exit_code=1,
                duration_ms=500.0,
            )
        )
        validator = UnitValidator(self.sandbox)
        result = validator.run_tests(
            self.node_id,
            "def test_fail(): assert False\n",
            self.container_id,
        )
        assert result.passed is False
        assert result.failed_tests == 2

    def test_run_tests_updates_generation_state(self) -> None:
        state = GenerationState()
        self.sandbox.set_default(
            MockExecutionResult(stdout="5 passed in 0.2s", exit_code=0)
        )
        validator = UnitValidator(self.sandbox, generation_state=state)
        validator.run_tests(
            self.node_id,
            "def test_ok(): pass\n",
            self.container_id,
        )
        node_state = state.get_node_state(self.node_id)
        assert node_state.status == GenerationStatus.PASSED
        assert node_state.test_results.passed == 5

    def test_run_tests_fail_updates_generation_state(self) -> None:
        state = GenerationState()
        self.sandbox.set_default(
            MockExecutionResult(
                stdout="1 passed, 1 failed in 0.3s",
                exit_code=1,
            )
        )
        validator = UnitValidator(self.sandbox, generation_state=state)
        validator.run_tests(
            self.node_id,
            "def test_fail(): assert False\n",
            self.container_id,
        )
        node_state = state.get_node_state(self.node_id)
        assert node_state.status == GenerationStatus.FAILED

    def test_run_tests_with_source_code(self) -> None:
        self.sandbox.set_default(
            MockExecutionResult(stdout="1 passed in 0.1s", exit_code=0)
        )
        validator = UnitValidator(self.sandbox)
        result = validator.run_tests(
            self.node_id,
            "def test_ok(): pass",
            self.container_id,
            source_code="def add(a, b): return a + b",
        )
        assert result.passed is True
        # Verify source_code was included in the runner script
        call = self.sandbox.calls[0]
        assert "source_module.py" in call["code"]

    def test_validate_node_all_stages_pass(self) -> None:
        responses = [
            MockExecutionResult(stdout="SYNTAX_OK", exit_code=0),
            MockExecutionResult(stdout="IMPORTS_OK", exit_code=0),
            MockExecutionResult(stdout="2 passed in 0.3s", exit_code=0),
        ]
        self.sandbox.set_responses(responses)
        state = GenerationState()
        validator = UnitValidator(self.sandbox, generation_state=state)
        result = validator.validate_node(
            self.node_id,
            "import os\ndef test_ok(): pass\n",
            self.container_id,
        )
        assert result.passed is True
        assert result.stage == ValidationStage.UNIT_TEST
        assert len(self.sandbox.calls) == 3
        node_state = state.get_node_state(self.node_id)
        assert node_state.status == GenerationStatus.PASSED

    def test_validate_node_syntax_fail_stops(self) -> None:
        self.sandbox.set_responses([
            MockExecutionResult(
                stderr="SyntaxError: invalid syntax",
                exit_code=1,
            ),
        ])
        state = GenerationState()
        validator = UnitValidator(self.sandbox, generation_state=state)
        result = validator.validate_node(
            self.node_id,
            "def foo(:",
            self.container_id,
        )
        assert result.passed is False
        assert result.stage == ValidationStage.SYNTAX_CHECK
        # Only one call - stopped at syntax
        assert len(self.sandbox.calls) == 1
        assert state.get_node_state(self.node_id).status == GenerationStatus.FAILED

    def test_validate_node_import_fail_stops(self) -> None:
        self.sandbox.set_responses([
            MockExecutionResult(stdout="SYNTAX_OK", exit_code=0),
            MockExecutionResult(
                stderr="ImportError: No module named 'bad'",
                exit_code=1,
            ),
        ])
        state = GenerationState()
        validator = UnitValidator(self.sandbox, generation_state=state)
        result = validator.validate_node(
            self.node_id,
            "import bad\ndef test_ok(): pass\n",
            self.container_id,
        )
        assert result.passed is False
        assert result.stage == ValidationStage.IMPORT_CHECK
        assert len(self.sandbox.calls) == 2
        assert state.get_node_state(self.node_id).status == GenerationStatus.FAILED

    def test_validate_node_sets_in_progress(self) -> None:
        self.sandbox.set_responses([
            MockExecutionResult(stdout="SYNTAX_OK", exit_code=0),
            MockExecutionResult(stdout="IMPORTS_OK", exit_code=0),
            MockExecutionResult(stdout="1 passed in 0.1s", exit_code=0),
        ])
        state = GenerationState()
        validator = UnitValidator(self.sandbox, generation_state=state)
        # We can't easily check mid-execution, but we can verify final state
        validator.validate_node(
            self.node_id,
            "import os\ndef test_ok(): pass\n",
            self.container_id,
        )
        # Final state should be PASSED (went through IN_PROGRESS)
        assert state.get_node_state(self.node_id).status == GenerationStatus.PASSED

    def test_config_fail_fast(self) -> None:
        config = UnitValidatorConfig(fail_fast=True)
        self.sandbox.set_default(
            MockExecutionResult(stdout="1 passed in 0.1s", exit_code=0)
        )
        validator = UnitValidator(self.sandbox, config=config)
        validator.run_tests(self.node_id, "def test_ok(): pass", self.container_id)
        # Verify -x flag was included in the runner
        call = self.sandbox.calls[0]
        assert '"-x"' in call["code"]

    def test_config_custom_pytest_args(self) -> None:
        config = UnitValidatorConfig(pytest_args=["--cov", "--no-header"])
        self.sandbox.set_default(
            MockExecutionResult(stdout="1 passed in 0.1s", exit_code=0)
        )
        validator = UnitValidator(self.sandbox, config=config)
        validator.run_tests(self.node_id, "def test_ok(): pass", self.container_id)
        call = self.sandbox.calls[0]
        assert '"--cov"' in call["code"]

    def test_properties(self) -> None:
        config = UnitValidatorConfig()
        validator = UnitValidator(self.sandbox, config=config)
        assert validator.config is config
        assert validator.sandbox is self.sandbox
