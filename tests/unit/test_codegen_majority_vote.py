"""Unit tests for the codegen majority_vote module."""

from __future__ import annotations

from uuid import uuid4

import pytest

from zerorepo.codegen.majority_vote import (
    MajorityVoteConfig,
    MajorityVoter,
    NodeVoteResult,
    TestRunVote,
    TestVerdictDetail,
    VoteConfidence,
    VoteOutcome,
)


# --------------------------------------------------------------------------- #
#                         Test: VoteOutcome Enum                               #
# --------------------------------------------------------------------------- #


class TestVoteOutcome:
    """Test VoteOutcome enum values."""

    def test_all_values(self) -> None:
        assert VoteOutcome.CONSENSUS_PASS == "consensus_pass"
        assert VoteOutcome.CONSENSUS_FAIL == "consensus_fail"
        assert VoteOutcome.NO_CONSENSUS == "no_consensus"
        assert VoteOutcome.FLAKY == "flaky"

    def test_is_string_enum(self) -> None:
        assert isinstance(VoteOutcome.CONSENSUS_PASS, str)

    def test_from_value(self) -> None:
        assert VoteOutcome("consensus_pass") == VoteOutcome.CONSENSUS_PASS

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            VoteOutcome("bad")


# --------------------------------------------------------------------------- #
#                         Test: VoteConfidence Enum                            #
# --------------------------------------------------------------------------- #


class TestVoteConfidence:
    """Test VoteConfidence enum values."""

    def test_all_values(self) -> None:
        assert VoteConfidence.HIGH == "high"
        assert VoteConfidence.MEDIUM == "medium"
        assert VoteConfidence.LOW == "low"


# --------------------------------------------------------------------------- #
#                         Test: TestRunVote                                    #
# --------------------------------------------------------------------------- #


class TestTestRunVote:
    """Test TestRunVote dataclass."""

    def test_creation(self) -> None:
        vote = TestRunVote(run_id=1, passed=True)
        assert vote.run_id == 1
        assert vote.passed is True
        assert vote.duration_ms == 0.0
        assert vote.error_message is None

    def test_with_error(self) -> None:
        vote = TestRunVote(
            run_id=2,
            passed=False,
            duration_ms=50.0,
            error_message="AssertionError",
        )
        assert vote.passed is False
        assert vote.error_message == "AssertionError"


# --------------------------------------------------------------------------- #
#                         Test: TestVerdictDetail                              #
# --------------------------------------------------------------------------- #


class TestTestVerdictDetail:
    """Test TestVerdictDetail dataclass."""

    def test_defaults(self) -> None:
        v = TestVerdictDetail(
            test_name="test_foo",
            outcome=VoteOutcome.CONSENSUS_PASS,
            confidence=VoteConfidence.HIGH,
        )
        assert v.pass_count == 0
        assert v.fail_count == 0
        assert v.total_runs == 0
        assert v.is_flaky is False
        assert v.error_messages == []

    def test_pass_rate_zero(self) -> None:
        v = TestVerdictDetail(
            test_name="t", outcome=VoteOutcome.NO_CONSENSUS,
            confidence=VoteConfidence.LOW,
        )
        assert v.pass_rate == 0.0

    def test_pass_rate_computed(self) -> None:
        v = TestVerdictDetail(
            test_name="t",
            outcome=VoteOutcome.CONSENSUS_PASS,
            confidence=VoteConfidence.HIGH,
            pass_count=3,
            fail_count=1,
            total_runs=4,
        )
        assert v.pass_rate == 75.0

    def test_flaky_marking(self) -> None:
        v = TestVerdictDetail(
            test_name="t",
            outcome=VoteOutcome.FLAKY,
            confidence=VoteConfidence.LOW,
            is_flaky=True,
        )
        assert v.is_flaky is True


# --------------------------------------------------------------------------- #
#                         Test: NodeVoteResult                                 #
# --------------------------------------------------------------------------- #


class TestNodeVoteResult:
    """Test NodeVoteResult dataclass."""

    def test_defaults(self) -> None:
        node_id = uuid4()
        result = NodeVoteResult(
            node_id=node_id,
            outcome=VoteOutcome.CONSENSUS_PASS,
            confidence=VoteConfidence.HIGH,
        )
        assert result.total_tests == 0
        assert result.consensus_passed == 0
        assert result.consensus_failed == 0
        assert result.flaky_tests == 0
        assert result.test_verdicts == []

    def test_with_data(self) -> None:
        result = NodeVoteResult(
            node_id=uuid4(),
            outcome=VoteOutcome.CONSENSUS_FAIL,
            confidence=VoteConfidence.MEDIUM,
            total_tests=5,
            consensus_passed=3,
            consensus_failed=2,
            total_runs=3,
        )
        assert result.total_tests == 5
        assert result.total_runs == 3


# --------------------------------------------------------------------------- #
#                         Test: MajorityVoteConfig                             #
# --------------------------------------------------------------------------- #


class TestMajorityVoteConfig:
    """Test MajorityVoteConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = MajorityVoteConfig()
        assert config.min_runs == 3
        assert config.consensus_threshold == 0.6
        assert config.flaky_threshold == 0.2
        assert config.max_runs == 5

    def test_custom_values(self) -> None:
        config = MajorityVoteConfig(
            min_runs=5,
            consensus_threshold=0.75,
            flaky_threshold=0.3,
            max_runs=10,
        )
        assert config.min_runs == 5
        assert config.consensus_threshold == 0.75

    def test_validation(self) -> None:
        with pytest.raises(Exception):
            MajorityVoteConfig(min_runs=0)
        with pytest.raises(Exception):
            MajorityVoteConfig(consensus_threshold=0.3)
        with pytest.raises(Exception):
            MajorityVoteConfig(consensus_threshold=1.5)
        with pytest.raises(Exception):
            MajorityVoteConfig(flaky_threshold=0.6)


# --------------------------------------------------------------------------- #
#                         Test: MajorityVoter                                  #
# --------------------------------------------------------------------------- #


class TestMajorityVoter:
    """Test MajorityVoter voting logic."""

    def setup_method(self) -> None:
        self.node_id = uuid4()
        self.voter = MajorityVoter()

    def test_no_votes_no_consensus(self) -> None:
        verdict = self.voter.get_verdict(self.node_id, "test_foo")
        assert verdict.outcome == VoteOutcome.NO_CONSENSUS
        assert verdict.confidence == VoteConfidence.LOW

    def test_record_single_vote(self) -> None:
        vote = TestRunVote(run_id=1, passed=True)
        self.voter.record_vote(self.node_id, "test_foo", vote)
        assert len(self.voter.votes[str(self.node_id)]["test_foo"]) == 1

    def test_consensus_pass_all_pass(self) -> None:
        for i in range(3):
            self.voter.record_vote(
                self.node_id, "test_foo",
                TestRunVote(run_id=i, passed=True),
            )
        verdict = self.voter.get_verdict(self.node_id, "test_foo")
        assert verdict.outcome == VoteOutcome.CONSENSUS_PASS
        assert verdict.pass_count == 3
        assert verdict.fail_count == 0

    def test_consensus_fail_all_fail(self) -> None:
        for i in range(3):
            self.voter.record_vote(
                self.node_id, "test_foo",
                TestRunVote(run_id=i, passed=False, error_message="Failed"),
            )
        verdict = self.voter.get_verdict(self.node_id, "test_foo")
        assert verdict.outcome == VoteOutcome.CONSENSUS_FAIL
        assert verdict.fail_count == 3
        assert len(verdict.error_messages) == 1

    def test_consensus_pass_majority(self) -> None:
        """2/3 pass => consensus pass at 0.6 threshold."""
        self.voter.record_vote(
            self.node_id, "t", TestRunVote(run_id=1, passed=True)
        )
        self.voter.record_vote(
            self.node_id, "t", TestRunVote(run_id=2, passed=True)
        )
        self.voter.record_vote(
            self.node_id, "t", TestRunVote(run_id=3, passed=False)
        )
        verdict = self.voter.get_verdict(self.node_id, "t")
        assert verdict.outcome == VoteOutcome.CONSENSUS_PASS

    def test_flaky_detection(self) -> None:
        """50/50 split should be flaky."""
        config = MajorityVoteConfig(min_runs=4, consensus_threshold=0.75)
        voter = MajorityVoter(config=config)
        for i in range(4):
            voter.record_vote(
                self.node_id, "t",
                TestRunVote(run_id=i, passed=i % 2 == 0),
            )
        verdict = voter.get_verdict(self.node_id, "t")
        assert verdict.outcome == VoteOutcome.FLAKY
        assert verdict.is_flaky is True

    def test_record_run_convenience(self) -> None:
        self.voter.record_run(
            self.node_id,
            test_results={"test_a": True, "test_b": False},
            run_id=1,
            durations={"test_a": 10.0, "test_b": 20.0},
            errors={"test_b": "AssertionError"},
        )
        assert len(self.voter.votes[str(self.node_id)]) == 2
        b_votes = self.voter.votes[str(self.node_id)]["test_b"]
        assert b_votes[0].passed is False
        assert b_votes[0].error_message == "AssertionError"
        assert b_votes[0].duration_ms == 20.0

    def test_get_node_result_all_pass(self) -> None:
        for i in range(3):
            self.voter.record_run(
                self.node_id,
                test_results={"test_a": True, "test_b": True},
                run_id=i,
            )
        result = self.voter.get_node_result(self.node_id)
        assert result.outcome == VoteOutcome.CONSENSUS_PASS
        assert result.confidence == VoteConfidence.HIGH
        assert result.total_tests == 2
        assert result.consensus_passed == 2
        assert result.consensus_failed == 0

    def test_get_node_result_one_failing(self) -> None:
        for i in range(3):
            self.voter.record_run(
                self.node_id,
                test_results={"test_a": True, "test_b": False},
                run_id=i,
            )
        result = self.voter.get_node_result(self.node_id)
        assert result.outcome == VoteOutcome.CONSENSUS_FAIL
        assert result.consensus_passed == 1
        assert result.consensus_failed == 1

    def test_get_node_result_empty(self) -> None:
        result = self.voter.get_node_result(self.node_id)
        assert result.outcome == VoteOutcome.NO_CONSENSUS
        assert result.total_tests == 0

    def test_get_node_result_with_flaky(self) -> None:
        config = MajorityVoteConfig(min_runs=4, consensus_threshold=0.75)
        voter = MajorityVoter(config=config)
        # test_a always passes
        for i in range(4):
            voter.record_vote(
                self.node_id, "test_a",
                TestRunVote(run_id=i, passed=True),
            )
        # test_b is flaky
        for i in range(4):
            voter.record_vote(
                self.node_id, "test_b",
                TestRunVote(run_id=i, passed=i % 2 == 0),
            )
        result = voter.get_node_result(self.node_id)
        assert result.outcome == VoteOutcome.FLAKY
        assert result.flaky_tests == 1
        assert result.consensus_passed == 1

    def test_needs_more_runs_no_votes(self) -> None:
        assert self.voter.needs_more_runs(self.node_id) is True

    def test_needs_more_runs_below_min(self) -> None:
        self.voter.record_vote(
            self.node_id, "test_foo",
            TestRunVote(run_id=1, passed=True),
        )
        assert self.voter.needs_more_runs(self.node_id) is True

    def test_needs_more_runs_sufficient(self) -> None:
        for i in range(3):
            self.voter.record_vote(
                self.node_id, "test_foo",
                TestRunVote(run_id=i, passed=True),
            )
        assert self.voter.needs_more_runs(self.node_id) is False

    def test_needs_more_runs_flaky(self) -> None:
        """Flaky test below max_runs still needs more."""
        config = MajorityVoteConfig(min_runs=3, max_runs=5)
        voter = MajorityVoter(config=config)
        # 3 runs: 2 pass, 1 fail => no consensus at default 0.6 threshold
        # Actually 2/3 = 0.67 >= 0.6, so this is consensus_pass
        # Let's use 1 pass, 2 fail => 1/3 pass, 2/3 fail => consensus_fail
        # We want flaky, so use equal: 2 pass, 1 fail at higher threshold
        config2 = MajorityVoteConfig(min_runs=3, max_runs=5, consensus_threshold=0.8)
        voter2 = MajorityVoter(config=config2)
        for i in range(3):
            voter2.record_vote(
                self.node_id, "t",
                TestRunVote(run_id=i, passed=i < 2),  # 2 pass, 1 fail
            )
        # 2/3 = 0.67 < 0.8 threshold => not consensus
        assert voter2.needs_more_runs(self.node_id) is True

    def test_clear_votes_specific(self) -> None:
        n1, n2 = uuid4(), uuid4()
        self.voter.record_vote(n1, "t", TestRunVote(run_id=1, passed=True))
        self.voter.record_vote(n2, "t", TestRunVote(run_id=1, passed=True))
        self.voter.clear_votes(n1)
        assert str(n1) not in self.voter.votes
        assert str(n2) in self.voter.votes

    def test_clear_all_votes(self) -> None:
        self.voter.record_vote(
            self.node_id, "t", TestRunVote(run_id=1, passed=True)
        )
        self.voter.clear_votes()
        assert self.voter.votes == {}

    def test_config_property(self) -> None:
        config = MajorityVoteConfig(min_runs=5)
        voter = MajorityVoter(config=config)
        assert voter.config is config

    def test_high_confidence(self) -> None:
        """All passes -> high confidence."""
        for i in range(5):
            self.voter.record_vote(
                self.node_id, "t",
                TestRunVote(run_id=i, passed=True),
            )
        verdict = self.voter.get_verdict(self.node_id, "t")
        assert verdict.confidence == VoteConfidence.HIGH

    def test_multiple_error_messages(self) -> None:
        self.voter.record_vote(
            self.node_id, "t",
            TestRunVote(run_id=1, passed=False, error_message="Error A"),
        )
        self.voter.record_vote(
            self.node_id, "t",
            TestRunVote(run_id=2, passed=False, error_message="Error B"),
        )
        self.voter.record_vote(
            self.node_id, "t",
            TestRunVote(run_id=3, passed=False, error_message="Error A"),
        )
        verdict = self.voter.get_verdict(self.node_id, "t")
        # Should deduplicate error messages
        assert len(verdict.error_messages) == 2
        assert "Error A" in verdict.error_messages
        assert "Error B" in verdict.error_messages

    def test_node_result_total_runs(self) -> None:
        for i in range(4):
            self.voter.record_run(
                self.node_id,
                test_results={"t1": True, "t2": True},
                run_id=i,
            )
        result = self.voter.get_node_result(self.node_id)
        assert result.total_runs == 4
