"""Unit tests for the debugging loop with majority-vote diagnosis."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from cobuilder.repomap.codegen.debugging_loop import (
    BASE_TEMPERATURE,
    DIAGNOSIS_ROUNDS,
    MAJORITY_THRESHOLD,
    TEMPERATURE_INCREMENT,
    VALID_CLASSIFICATIONS,
    DiagnosisResponse,
    MajorityVoteDiagnoser,
)
from cobuilder.repomap.codegen.tdd_loop import DiagnosisResult
from cobuilder.repomap.models.enums import InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.node import RPGNode


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_func_node(
    *,
    name: str = "calculate_mean",
    signature: str = "def calculate_mean(numbers: list[float]) -> float",
    docstring: str = "Calculate the mean of a list of numbers.",
) -> RPGNode:
    """Create a FUNCTION_AUGMENTED node for testing."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        folder_path="src",
        file_path="src/module.py",
        signature=signature,
        docstring=docstring,
    )


def _make_json_response(
    classification: str = "implementation_bug",
    fixed_code: str = "def foo(): return 42",
    explanation: str = "Fixed the bug",
) -> str:
    """Create a valid JSON diagnosis response string."""
    return json.dumps(
        {
            "classification": classification,
            "fixed_code": fixed_code,
            "explanation": explanation,
        }
    )


def _make_mock_gateway(responses: list[str] | None = None) -> MagicMock:
    """Create a mock LLM gateway that returns fixed responses.

    If responses is provided, returns them in order (cycling if needed).
    """
    gateway = MagicMock()
    if responses is None:
        responses = [_make_json_response()] * DIAGNOSIS_ROUNDS
    gateway.complete.side_effect = responses
    return gateway


# --------------------------------------------------------------------------- #
#                              Tests: Constants                                #
# --------------------------------------------------------------------------- #


class TestConstants:
    """Tests for module-level constants."""

    def test_diagnosis_rounds(self):
        assert DIAGNOSIS_ROUNDS == 5

    def test_majority_threshold(self):
        assert MAJORITY_THRESHOLD == 3

    def test_valid_classifications(self):
        assert "implementation_bug" in VALID_CLASSIFICATIONS
        assert "test_bug" in VALID_CLASSIFICATIONS
        assert "environment" in VALID_CLASSIFICATIONS

    def test_temperature_config(self):
        assert BASE_TEMPERATURE == 0.3
        assert TEMPERATURE_INCREMENT == 0.1


# --------------------------------------------------------------------------- #
#                              Tests: DiagnosisResponse                        #
# --------------------------------------------------------------------------- #


class TestDiagnosisResponse:
    """Tests for the DiagnosisResponse model."""

    def test_defaults(self):
        dr = DiagnosisResponse()
        assert dr.classification == "implementation_bug"
        assert dr.fixed_code == ""
        assert dr.explanation == ""

    def test_with_values(self):
        dr = DiagnosisResponse(
            classification="test_bug",
            fixed_code="def test_it(): assert True",
            explanation="Test had wrong expectation",
        )
        assert dr.classification == "test_bug"


# --------------------------------------------------------------------------- #
#                              Tests: MajorityVoteDiagnoser                    #
# --------------------------------------------------------------------------- #


class TestMajorityVoteDiagnoser:
    """Tests for the majority-vote diagnosis engine."""

    def test_majority_vote_implementation_bug(self):
        """4/5 'implementation_bug' -> implementation_bug classification."""
        responses = [
            _make_json_response("implementation_bug", "def fix(): pass", "Impl bug"),
            _make_json_response("implementation_bug", "def fix(): pass", "Impl bug"),
            _make_json_response("implementation_bug", "def fix(): pass", "Impl bug"),
            _make_json_response("implementation_bug", "def fix(): pass", "Impl bug"),
            _make_json_response("test_bug", "def test_fix(): pass", "Test bug"),
        ]
        gateway = _make_mock_gateway(responses)
        diagnoser = MajorityVoteDiagnoser(gateway)

        node = _make_func_node()
        result = diagnoser.diagnose_and_fix(
            node, "def foo(): pass", "def test_it(): assert False", "AssertionError", {}
        )

        assert result.classification == "implementation_bug"
        assert result.fixed_implementation != ""
        assert result.fixed_test_code == ""

    def test_majority_vote_test_bug(self):
        """3/5 'test_bug' -> test_bug classification."""
        responses = [
            _make_json_response("test_bug", "def test_fixed(): assert True", "Test bug"),
            _make_json_response("implementation_bug", "def fix(): pass", "Impl"),
            _make_json_response("test_bug", "def test_fixed(): assert True", "Test bug"),
            _make_json_response("test_bug", "def test_fixed(): assert True", "Test bug"),
            _make_json_response("environment", "", "Env issue"),
        ]
        gateway = _make_mock_gateway(responses)
        diagnoser = MajorityVoteDiagnoser(gateway)

        node = _make_func_node()
        result = diagnoser.diagnose_and_fix(
            node, "def foo(): pass", "def test_it(): assert False", "AssertionError", {}
        )

        assert result.classification == "test_bug"
        assert result.fixed_test_code != ""
        assert result.fixed_implementation == ""

    def test_majority_vote_environment(self):
        """3/5 'environment' -> environment classification."""
        responses = [
            _make_json_response("environment", "", "Missing deps"),
            _make_json_response("environment", "", "Missing deps"),
            _make_json_response("environment", "", "Missing deps"),
            _make_json_response("implementation_bug", "def fix(): pass", "Impl"),
            _make_json_response("test_bug", "def test(): pass", "Test"),
        ]
        gateway = _make_mock_gateway(responses)
        diagnoser = MajorityVoteDiagnoser(gateway)

        node = _make_func_node()
        result = diagnoser.diagnose_and_fix(
            node, "def foo(): pass", "def test_it(): pass", "ModuleNotFoundError", {}
        )

        assert result.classification == "environment"
        assert result.fixed_implementation == ""
        assert result.fixed_test_code == ""

    def test_increasing_temperature(self):
        """Each round uses increasing temperature."""
        responses = [_make_json_response()] * 5
        gateway = _make_mock_gateway(responses)
        diagnoser = MajorityVoteDiagnoser(gateway)

        node = _make_func_node()
        diagnoser.diagnose_and_fix(node, "impl", "test", "error", {})

        assert gateway.complete.call_count == 5
        for i, c in enumerate(gateway.complete.call_args_list):
            expected_temp = BASE_TEMPERATURE + i * TEMPERATURE_INCREMENT
            actual_temp = c.kwargs.get("temperature", c[1].get("temperature", None))
            assert abs(actual_temp - expected_temp) < 0.01, (
                f"Round {i}: expected temp {expected_temp}, got {actual_temp}"
            )

    def test_llm_error_defaults_to_implementation_bug(self):
        """LLM error in a round defaults to 'implementation_bug'."""
        gateway = MagicMock()
        gateway.complete.side_effect = [
            RuntimeError("API error"),
            _make_json_response("implementation_bug"),
            _make_json_response("implementation_bug"),
            RuntimeError("API error"),
            _make_json_response("implementation_bug"),
        ]
        diagnoser = MajorityVoteDiagnoser(gateway)

        node = _make_func_node()
        result = diagnoser.diagnose_and_fix(node, "impl", "test", "error", {})

        # 5 votes: 2 errors (default impl_bug) + 3 impl_bug = 5 impl_bug
        assert result.classification == "implementation_bug"

    def test_parse_diagnosis_valid_json(self):
        """Valid JSON response is parsed correctly."""
        text = _make_json_response("test_bug", "def test(): pass", "Wrong expect")
        result = MajorityVoteDiagnoser._parse_diagnosis(text)
        assert result.classification == "test_bug"
        assert result.fixed_code == "def test(): pass"
        assert result.explanation == "Wrong expect"

    def test_parse_diagnosis_with_fences(self):
        """JSON wrapped in markdown fences is parsed correctly."""
        inner = _make_json_response("implementation_bug", "def fix(): pass", "Bug")
        text = f"```json\n{inner}\n```"
        result = MajorityVoteDiagnoser._parse_diagnosis(text)
        assert result.classification == "implementation_bug"

    def test_parse_diagnosis_invalid_json_keyword_fallback(self):
        """Invalid JSON falls back to keyword detection."""
        text = "The issue is a test_bug - the assertions are wrong"
        result = MajorityVoteDiagnoser._parse_diagnosis(text)
        assert result.classification == "test_bug"

    def test_parse_diagnosis_invalid_json_environment_fallback(self):
        """Invalid JSON with 'environment' keyword detected."""
        text = "This is an environment issue with missing packages"
        result = MajorityVoteDiagnoser._parse_diagnosis(text)
        assert result.classification == "environment"

    def test_parse_diagnosis_invalid_json_default_fallback(self):
        """Invalid JSON with no keywords defaults to implementation_bug."""
        text = "Something is wrong with the code"
        result = MajorityVoteDiagnoser._parse_diagnosis(text)
        assert result.classification == "implementation_bug"

    def test_parse_diagnosis_invalid_classification_corrected(self):
        """Invalid classification in JSON is corrected to implementation_bug."""
        text = json.dumps({
            "classification": "invalid_type",
            "fixed_code": "",
            "explanation": "",
        })
        result = MajorityVoteDiagnoser._parse_diagnosis(text)
        assert result.classification == "implementation_bug"

    def test_select_best_diagnosis_prefers_complete(self):
        """Best diagnosis prefers entries with both fixed_code and explanation."""
        diagnoses = [
            DiagnosisResponse(
                classification="implementation_bug",
                fixed_code="",
                explanation="",
            ),
            DiagnosisResponse(
                classification="implementation_bug",
                fixed_code="def fix(): pass",
                explanation="Found the bug",
            ),
        ]
        result = MajorityVoteDiagnoser._select_best_diagnosis(
            diagnoses, "implementation_bug"
        )
        assert result.fixed_code == "def fix(): pass"
        assert result.explanation == "Found the bug"

    def test_select_best_diagnosis_falls_back_to_fixed_code(self):
        """Falls back to diagnosis with just fixed_code."""
        diagnoses = [
            DiagnosisResponse(
                classification="implementation_bug",
                fixed_code="def fix(): pass",
                explanation="",
            ),
        ]
        result = MajorityVoteDiagnoser._select_best_diagnosis(
            diagnoses, "implementation_bug"
        )
        assert result.fixed_code == "def fix(): pass"

    def test_select_best_diagnosis_no_matching(self):
        """No matching diagnosis returns default."""
        result = MajorityVoteDiagnoser._select_best_diagnosis([], "test_bug")
        assert result.classification == "test_bug"

    def test_custom_rounds_and_threshold(self):
        """Custom rounds and threshold are respected."""
        responses = [_make_json_response()] * 3
        gateway = _make_mock_gateway(responses)
        diagnoser = MajorityVoteDiagnoser(
            gateway, rounds=3, majority_threshold=2
        )

        assert diagnoser.rounds == 3
        assert diagnoser.majority_threshold == 2

        node = _make_func_node()
        diagnoser.diagnose_and_fix(node, "impl", "test", "error", {})

        assert gateway.complete.call_count == 3

    def test_tie_breaker_most_common(self):
        """When votes are tied, most_common picks one consistently."""
        responses = [
            _make_json_response("implementation_bug"),
            _make_json_response("implementation_bug"),
            _make_json_response("test_bug"),
            _make_json_response("test_bug"),
            _make_json_response("environment"),
        ]
        gateway = _make_mock_gateway(responses)
        diagnoser = MajorityVoteDiagnoser(gateway)

        node = _make_func_node()
        result = diagnoser.diagnose_and_fix(node, "impl", "test", "error", {})

        # 2 impl_bug, 2 test_bug, 1 environment - Counter.most_common picks first encountered
        assert result.classification in {"implementation_bug", "test_bug"}
