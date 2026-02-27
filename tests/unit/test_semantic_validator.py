"""Unit tests for the SemanticValidator class (bead ek7).

Tests cover:
- Vote parsing from LLM responses
- Majority vote computation
- Single-vote collection with mocked LLM client
- Multi-round validation flow
- Early exit on clear first-round majority
- Confidence levels (high, medium, low)
- Error handling for LLM failures
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from cobuilder.repomap.evaluation.models import (
    BenchmarkTask,
    FunctionSignature,
    ValidationResult,
    Vote,
    VoteResult,
)
from cobuilder.repomap.evaluation.semantic_validation import SemanticValidator


def _make_task() -> BenchmarkTask:
    """Create a minimal BenchmarkTask."""
    return BenchmarkTask(
        id="task-001",
        project="test",
        category="test.cat",
        description="Test ridge regression",
        test_code="def test_ridge(): pass",
    )


def _make_function() -> FunctionSignature:
    """Create a minimal FunctionSignature."""
    return FunctionSignature(
        name="ridge_regression",
        module="ml_lib.linear_model",
        signature="def ridge_regression(X, y, alpha=1.0)",
        docstring="Fit a ridge regression model.",
        file_path="ml_lib/linear_model.py",
        body="def ridge_regression(X, y, alpha=1.0):\n    return X @ y",
    )


def _make_mock_llm(responses: list[str]) -> MagicMock:
    """Create a mock LLM client that returns responses in sequence."""
    mock = MagicMock()
    mock.complete = MagicMock(side_effect=responses)
    return mock


# ---------------------------------------------------------------------------
# Vote parsing
# ---------------------------------------------------------------------------


class TestParseVote:
    """Tests for _parse_vote static method."""

    def test_yes_response(self) -> None:
        """'YES' response should parse as VoteResult.YES."""
        result, justification = SemanticValidator._parse_vote("YES. The function is correct.")
        assert result == VoteResult.YES
        assert "function is correct" in justification

    def test_no_response(self) -> None:
        """'NO' response should parse as VoteResult.NO."""
        result, _ = SemanticValidator._parse_vote("NO. Missing error handling.")
        assert result == VoteResult.NO

    def test_partial_response(self) -> None:
        """'PARTIAL' response should parse as VoteResult.PARTIAL."""
        result, _ = SemanticValidator._parse_vote("PARTIAL. Some features missing.")
        assert result == VoteResult.PARTIAL

    def test_lowercase_yes(self) -> None:
        """Lowercase 'yes' should parse as YES."""
        result, _ = SemanticValidator._parse_vote("yes, it works.")
        assert result == VoteResult.YES

    def test_ambiguous_defaults_to_no(self) -> None:
        """Ambiguous response should default to NO."""
        result, _ = SemanticValidator._parse_vote("I'm not sure about this implementation.")
        assert result == VoteResult.NO

    def test_yes_embedded_in_sentence(self) -> None:
        """YES keyword in first sentence should be detected."""
        result, _ = SemanticValidator._parse_vote("The answer is YES. It works correctly.")
        assert result == VoteResult.YES

    def test_empty_justification(self) -> None:
        """Bare keyword should work with empty justification."""
        result, justification = SemanticValidator._parse_vote("YES")
        assert result == VoteResult.YES


# ---------------------------------------------------------------------------
# Majority vote computation
# ---------------------------------------------------------------------------


class TestCheckMajority:
    """Tests for _check_majority static method."""

    def test_clear_yes_majority(self) -> None:
        """3/3 YES votes should return YES."""
        votes = [Vote(result=VoteResult.YES) for _ in range(3)]
        assert SemanticValidator._check_majority(votes) == VoteResult.YES

    def test_clear_no_majority(self) -> None:
        """2/3 NO votes should return NO."""
        votes = [
            Vote(result=VoteResult.NO),
            Vote(result=VoteResult.NO),
            Vote(result=VoteResult.YES),
        ]
        assert SemanticValidator._check_majority(votes) == VoteResult.NO

    def test_no_majority(self) -> None:
        """Even split should return None."""
        votes = [
            Vote(result=VoteResult.YES),
            Vote(result=VoteResult.NO),
        ]
        assert SemanticValidator._check_majority(votes) is None

    def test_three_way_split(self) -> None:
        """Three-way split should return None."""
        votes = [
            Vote(result=VoteResult.YES),
            Vote(result=VoteResult.NO),
            Vote(result=VoteResult.PARTIAL),
        ]
        assert SemanticValidator._check_majority(votes) is None

    def test_empty_votes(self) -> None:
        """Empty vote list should return None."""
        assert SemanticValidator._check_majority([]) is None


class TestMajorityVote:
    """Tests for _majority_vote static method."""

    def test_most_common_wins(self) -> None:
        """Most common vote should win."""
        votes = [
            Vote(result=VoteResult.YES),
            Vote(result=VoteResult.YES),
            Vote(result=VoteResult.NO),
        ]
        assert SemanticValidator._majority_vote(votes) == VoteResult.YES

    def test_empty_defaults_to_no(self) -> None:
        """Empty list should default to NO."""
        assert SemanticValidator._majority_vote([]) == VoteResult.NO


# ---------------------------------------------------------------------------
# validate_function - full flow
# ---------------------------------------------------------------------------


class TestValidateFunction:
    """Tests for the validate_function() method with mocked LLM."""

    def test_unanimous_yes_first_round(self) -> None:
        """Unanimous YES in round 1 should return immediately with high confidence."""
        mock_llm = _make_mock_llm(["YES. Correct.", "YES. Looks good.", "YES. Works."])
        validator = SemanticValidator(llm_client=mock_llm, num_voters=3, num_rounds=2)

        result = validator.validate_function(_make_task(), _make_function())

        assert result.passed is True
        assert result.confidence == "high"
        assert len(result.votes) == 3  # Only round 1 votes
        assert result.candidate_function == "ridge_regression"

    def test_unanimous_no_first_round(self) -> None:
        """Unanimous NO in round 1 should return immediately."""
        mock_llm = _make_mock_llm(["NO. Wrong.", "NO. Incorrect.", "NO. Bad."])
        validator = SemanticValidator(llm_client=mock_llm, num_voters=3, num_rounds=2)

        result = validator.validate_function(_make_task(), _make_function())

        assert result.passed is False
        assert result.confidence == "high"
        assert len(result.votes) == 3

    def test_split_triggers_round_2(self) -> None:
        """Split vote in round 1 should trigger round 2."""
        # Round 1: YES, NO, PARTIAL (no majority)
        # Round 2: YES, YES, YES (clear majority)
        responses = [
            "YES. OK.", "NO. Bad.", "PARTIAL. Some.",  # Round 1
            "YES. Better.", "YES. Good.", "YES. Fine.",  # Round 2
        ]
        mock_llm = _make_mock_llm(responses)
        validator = SemanticValidator(llm_client=mock_llm, num_voters=3, num_rounds=2)

        result = validator.validate_function(_make_task(), _make_function())

        assert len(result.votes) == 6  # 3 from each round
        # Round 1 has round_num=1, round 2 has round_num=2
        round_1_votes = [v for v in result.votes if v.round_num == 1]
        round_2_votes = [v for v in result.votes if v.round_num == 2]
        assert len(round_1_votes) == 3
        assert len(round_2_votes) == 3

    def test_llm_error_counts_as_no(self) -> None:
        """LLM failures should count as NO votes."""
        mock_llm = MagicMock()
        mock_llm.complete = MagicMock(side_effect=RuntimeError("API error"))
        validator = SemanticValidator(llm_client=mock_llm, num_voters=3, num_rounds=1)

        result = validator.validate_function(_make_task(), _make_function())

        assert result.passed is False
        for vote in result.votes:
            assert vote.result == VoteResult.NO
            assert "Error" in vote.justification

    def test_result_type(self) -> None:
        """Should return a ValidationResult instance."""
        mock_llm = _make_mock_llm(["YES"] * 3)
        validator = SemanticValidator(llm_client=mock_llm, num_voters=3)

        result = validator.validate_function(_make_task(), _make_function())
        assert isinstance(result, ValidationResult)

    def test_single_voter(self) -> None:
        """Should work with a single voter."""
        mock_llm = _make_mock_llm(["YES. Correct."])
        validator = SemanticValidator(llm_client=mock_llm, num_voters=1, num_rounds=1)

        result = validator.validate_function(_make_task(), _make_function())
        assert result.passed is True
        assert len(result.votes) == 1
