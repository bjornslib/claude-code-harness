"""Majority voting for test result consensus in code generation.

Implements a majority voting scheme where multiple test runs are compared
to determine consensus on test outcomes. This helps identify flaky tests
and establish reliable pass/fail verdicts.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                              Models                                          #
# --------------------------------------------------------------------------- #


class VoteOutcome(str, Enum):
    """Outcome from a majority vote."""

    CONSENSUS_PASS = "consensus_pass"
    CONSENSUS_FAIL = "consensus_fail"
    NO_CONSENSUS = "no_consensus"
    FLAKY = "flaky"


class VoteConfidence(str, Enum):
    """Confidence level of a majority vote."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestRunVote:
    """A single test run contributing to the majority vote.

    Attributes:
        run_id: Unique identifier for this run.
        passed: Whether the test passed in this run.
        duration_ms: Execution time in milliseconds.
        error_message: Error details if the test failed.
    """

    run_id: int
    passed: bool
    duration_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class TestVerdictDetail:
    """Per-test verdict from majority voting.

    Attributes:
        test_name: The fully qualified test name.
        outcome: The majority vote outcome.
        confidence: Confidence level in the verdict.
        pass_count: Number of runs where this test passed.
        fail_count: Number of runs where this test failed.
        total_runs: Total number of runs.
        is_flaky: Whether the test showed inconsistent behavior.
        error_messages: All unique error messages from failures.
    """

    test_name: str
    outcome: VoteOutcome
    confidence: VoteConfidence
    pass_count: int = 0
    fail_count: int = 0
    total_runs: int = 0
    is_flaky: bool = False
    error_messages: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Pass rate as a percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.pass_count / self.total_runs) * 100.0


@dataclass
class NodeVoteResult:
    """Aggregate vote result for a single node.

    Attributes:
        node_id: The UUID of the node.
        outcome: The overall majority vote outcome.
        confidence: Overall confidence level.
        total_tests: Number of distinct tests voted on.
        consensus_passed: Tests with consensus pass.
        consensus_failed: Tests with consensus fail.
        flaky_tests: Tests showing inconsistent behavior.
        no_consensus_tests: Tests with no clear majority.
        test_verdicts: Per-test verdict details.
        total_runs: Number of test runs performed.
    """

    node_id: UUID
    outcome: VoteOutcome
    confidence: VoteConfidence
    total_tests: int = 0
    consensus_passed: int = 0
    consensus_failed: int = 0
    flaky_tests: int = 0
    no_consensus_tests: int = 0
    test_verdicts: list[TestVerdictDetail] = field(default_factory=list)
    total_runs: int = 0


class MajorityVoteConfig(BaseModel):
    """Configuration for the MajorityVoter.

    Attributes:
        min_runs: Minimum number of runs before voting.
        consensus_threshold: Fraction of runs required for consensus.
        flaky_threshold: If pass rate is between this and (1 - this), mark flaky.
        max_runs: Maximum runs to perform.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    min_runs: int = Field(
        default=3,
        ge=1,
        description="Minimum test runs before voting",
    )
    consensus_threshold: float = Field(
        default=0.6,
        ge=0.5,
        le=1.0,
        description="Fraction of runs needed for consensus",
    )
    flaky_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=0.5,
        description="Pass rate range that indicates flakiness",
    )
    max_runs: int = Field(
        default=5,
        ge=1,
        description="Maximum test runs to perform",
    )


# --------------------------------------------------------------------------- #
#                           Majority Voter                                     #
# --------------------------------------------------------------------------- #


class MajorityVoter:
    """Determines test pass/fail consensus through multiple runs.

    Records individual test run votes and computes majority verdicts
    using configurable consensus thresholds.

    Args:
        config: Majority voting configuration.
    """

    def __init__(self, config: MajorityVoteConfig | None = None) -> None:
        self._config = config or MajorityVoteConfig()
        # node_id (str) -> test_name -> list of votes
        self._votes: dict[str, dict[str, list[TestRunVote]]] = {}

    @property
    def config(self) -> MajorityVoteConfig:
        """The voter configuration."""
        return self._config

    @property
    def votes(self) -> dict[str, dict[str, list[TestRunVote]]]:
        """All recorded votes, keyed by node UUID then test name."""
        return self._votes

    def record_vote(
        self,
        node_id: UUID,
        test_name: str,
        vote: TestRunVote,
    ) -> None:
        """Record a single test run vote.

        Args:
            node_id: The UUID of the node.
            test_name: The fully qualified test name.
            vote: The test run vote to record.
        """
        key = str(node_id)
        if key not in self._votes:
            self._votes[key] = {}
        if test_name not in self._votes[key]:
            self._votes[key][test_name] = []
        self._votes[key][test_name].append(vote)
        logger.debug(
            "Recorded vote for node %s test %s: passed=%s",
            node_id,
            test_name,
            vote.passed,
        )

    def record_run(
        self,
        node_id: UUID,
        test_results: dict[str, bool],
        run_id: int,
        durations: dict[str, float] | None = None,
        errors: dict[str, str] | None = None,
    ) -> None:
        """Record votes from a full test run.

        Convenience method that records a vote for each test in the run.

        Args:
            node_id: The UUID of the node.
            test_results: Mapping of test name to pass/fail boolean.
            run_id: The run identifier.
            durations: Optional per-test durations in ms.
            errors: Optional per-test error messages.
        """
        durations = durations or {}
        errors = errors or {}
        for test_name, passed in test_results.items():
            vote = TestRunVote(
                run_id=run_id,
                passed=passed,
                duration_ms=durations.get(test_name, 0.0),
                error_message=errors.get(test_name),
            )
            self.record_vote(node_id, test_name, vote)

    def get_verdict(
        self,
        node_id: UUID,
        test_name: str,
    ) -> TestVerdictDetail:
        """Compute the majority vote verdict for a single test.

        Args:
            node_id: The UUID of the node.
            test_name: The fully qualified test name.

        Returns:
            A TestVerdictDetail with the voting outcome.
        """
        key = str(node_id)
        votes = self._votes.get(key, {}).get(test_name, [])
        total = len(votes)

        if total == 0:
            return TestVerdictDetail(
                test_name=test_name,
                outcome=VoteOutcome.NO_CONSENSUS,
                confidence=VoteConfidence.LOW,
            )

        pass_count = sum(1 for v in votes if v.passed)
        fail_count = total - pass_count
        pass_rate = pass_count / total

        # Determine outcome
        threshold = self._config.consensus_threshold
        flaky_lo = self._config.flaky_threshold
        flaky_hi = 1.0 - flaky_lo

        if pass_rate >= threshold:
            outcome = VoteOutcome.CONSENSUS_PASS
        elif (1.0 - pass_rate) >= threshold:
            outcome = VoteOutcome.CONSENSUS_FAIL
        elif flaky_lo <= pass_rate <= flaky_hi:
            outcome = VoteOutcome.FLAKY
        else:
            outcome = VoteOutcome.NO_CONSENSUS

        # Determine confidence
        if total >= self._config.min_runs:
            if pass_rate >= 0.9 or pass_rate <= 0.1:
                confidence = VoteConfidence.HIGH
            elif pass_rate >= 0.7 or pass_rate <= 0.3:
                confidence = VoteConfidence.MEDIUM
            else:
                confidence = VoteConfidence.LOW
        else:
            confidence = VoteConfidence.LOW

        # Collect error messages
        error_msgs = list(
            {v.error_message for v in votes if v.error_message is not None}
        )

        is_flaky = (
            outcome == VoteOutcome.FLAKY
            or (pass_count > 0 and fail_count > 0 and outcome != VoteOutcome.CONSENSUS_PASS)
        )

        return TestVerdictDetail(
            test_name=test_name,
            outcome=outcome,
            confidence=confidence,
            pass_count=pass_count,
            fail_count=fail_count,
            total_runs=total,
            is_flaky=is_flaky,
            error_messages=sorted(error_msgs),
        )

    def get_node_result(self, node_id: UUID) -> NodeVoteResult:
        """Compute the aggregate vote result for a node.

        Args:
            node_id: The UUID of the node.

        Returns:
            A NodeVoteResult with overall voting statistics.
        """
        key = str(node_id)
        test_names = list(self._votes.get(key, {}).keys())

        verdicts: list[TestVerdictDetail] = []
        consensus_passed = 0
        consensus_failed = 0
        flaky = 0
        no_consensus = 0

        for test_name in test_names:
            verdict = self.get_verdict(node_id, test_name)
            verdicts.append(verdict)
            if verdict.outcome == VoteOutcome.CONSENSUS_PASS:
                consensus_passed += 1
            elif verdict.outcome == VoteOutcome.CONSENSUS_FAIL:
                consensus_failed += 1
            elif verdict.outcome == VoteOutcome.FLAKY:
                flaky += 1
            else:
                no_consensus += 1

        # Determine overall outcome
        total = len(test_names)
        if total == 0:
            outcome = VoteOutcome.NO_CONSENSUS
            confidence = VoteConfidence.LOW
        elif consensus_failed > 0:
            outcome = VoteOutcome.CONSENSUS_FAIL
            confidence = VoteConfidence.HIGH if flaky == 0 else VoteConfidence.MEDIUM
        elif flaky > 0:
            outcome = VoteOutcome.FLAKY
            confidence = VoteConfidence.LOW
        elif no_consensus > 0:
            outcome = VoteOutcome.NO_CONSENSUS
            confidence = VoteConfidence.LOW
        else:
            outcome = VoteOutcome.CONSENSUS_PASS
            confidence = VoteConfidence.HIGH

        # Total runs: max across all tests
        max_runs = 0
        for test_name in test_names:
            runs = len(self._votes.get(key, {}).get(test_name, []))
            if runs > max_runs:
                max_runs = runs

        return NodeVoteResult(
            node_id=node_id,
            outcome=outcome,
            confidence=confidence,
            total_tests=total,
            consensus_passed=consensus_passed,
            consensus_failed=consensus_failed,
            flaky_tests=flaky,
            no_consensus_tests=no_consensus,
            test_verdicts=verdicts,
            total_runs=max_runs,
        )

    def needs_more_runs(self, node_id: UUID) -> bool:
        """Check if more test runs are needed for reliable consensus.

        Args:
            node_id: The UUID of the node.

        Returns:
            True if more runs would improve consensus reliability.
        """
        key = str(node_id)
        node_votes = self._votes.get(key, {})
        if not node_votes:
            return True

        for test_name, votes in node_votes.items():
            if len(votes) < self._config.min_runs:
                return True
            # If any test has no consensus, more runs might help
            verdict = self.get_verdict(node_id, test_name)
            if (
                verdict.outcome in (VoteOutcome.NO_CONSENSUS, VoteOutcome.FLAKY)
                and len(votes) < self._config.max_runs
            ):
                return True

        return False

    def clear_votes(self, node_id: UUID | None = None) -> None:
        """Clear recorded votes.

        Args:
            node_id: If provided, clear only this node's votes.
                If None, clear all votes.
        """
        if node_id is not None:
            self._votes.pop(str(node_id), None)
        else:
            self._votes.clear()
