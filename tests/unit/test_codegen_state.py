"""Unit tests for the codegen generation state module."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from cobuilder.repomap.codegen.state import (
    GenerationState,
    GenerationStatus,
    NodeGenerationState,
    TestResults,
)


# --------------------------------------------------------------------------- #
#                         Test: GenerationStatus Enum                          #
# --------------------------------------------------------------------------- #


class TestGenerationStatus:
    """Test GenerationStatus enum values and behavior."""

    def test_all_values_present(self) -> None:
        assert GenerationStatus.PENDING == "pending"
        assert GenerationStatus.IN_PROGRESS == "in_progress"
        assert GenerationStatus.PASSED == "passed"
        assert GenerationStatus.FAILED == "failed"
        assert GenerationStatus.SKIPPED == "skipped"

    def test_is_string_enum(self) -> None:
        assert isinstance(GenerationStatus.PENDING, str)
        assert isinstance(GenerationStatus.FAILED, str)

    def test_from_value(self) -> None:
        assert GenerationStatus("pending") == GenerationStatus.PENDING
        assert GenerationStatus("failed") == GenerationStatus.FAILED

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            GenerationStatus("invalid_status")


# --------------------------------------------------------------------------- #
#                         Test: TestResults Model                              #
# --------------------------------------------------------------------------- #


class TestTestResults:
    """Test TestResults Pydantic model."""

    def test_default_values(self) -> None:
        results = TestResults()
        assert results.passed == 0
        assert results.failed == 0

    def test_custom_values(self) -> None:
        results = TestResults(passed=5, failed=2)
        assert results.passed == 5
        assert results.failed == 2

    def test_negative_values_rejected(self) -> None:
        with pytest.raises(Exception):  # Pydantic validation error
            TestResults(passed=-1)

    def test_update_values(self) -> None:
        results = TestResults()
        results.passed = 10
        results.failed = 3
        assert results.passed == 10
        assert results.failed == 3


# --------------------------------------------------------------------------- #
#                         Test: NodeGenerationState Model                      #
# --------------------------------------------------------------------------- #


class TestNodeGenerationState:
    """Test NodeGenerationState model defaults and behavior."""

    def test_default_status_is_pending(self) -> None:
        state = NodeGenerationState()
        assert state.status == GenerationStatus.PENDING

    def test_default_retry_count_is_zero(self) -> None:
        state = NodeGenerationState()
        assert state.retry_count == 0

    def test_default_failure_reason_is_none(self) -> None:
        state = NodeGenerationState()
        assert state.failure_reason is None

    def test_default_test_results(self) -> None:
        state = NodeGenerationState()
        assert state.test_results.passed == 0
        assert state.test_results.failed == 0

    def test_timestamp_is_set(self) -> None:
        state = NodeGenerationState()
        assert isinstance(state.timestamp, datetime)

    def test_custom_values(self) -> None:
        state = NodeGenerationState(
            status=GenerationStatus.FAILED,
            retry_count=3,
            failure_reason="timeout",
        )
        assert state.status == GenerationStatus.FAILED
        assert state.retry_count == 3
        assert state.failure_reason == "timeout"


# --------------------------------------------------------------------------- #
#                         Test: GenerationState                                #
# --------------------------------------------------------------------------- #


class TestGenerationState:
    """Test GenerationState aggregate state management."""

    def test_default_checkpoint_path(self) -> None:
        state = GenerationState()
        assert state.checkpoint_path == "generation_checkpoint.json"

    def test_default_max_retries(self) -> None:
        state = GenerationState()
        assert state.max_retries == 8

    def test_custom_max_retries(self) -> None:
        state = GenerationState(max_retries=3)
        assert state.max_retries == 3

    def test_get_node_state_creates_if_missing(self) -> None:
        state = GenerationState()
        nid = uuid4()
        node_state = state.get_node_state(nid)
        assert isinstance(node_state, NodeGenerationState)
        assert node_state.status == GenerationStatus.PENDING

    def test_get_node_state_returns_existing(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state1 = state.get_node_state(nid)
        state2 = state.get_node_state(nid)
        assert state1 is state2

    def test_set_status(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.IN_PROGRESS)
        assert state.get_node_state(nid).status == GenerationStatus.IN_PROGRESS

    def test_set_status_with_failure_reason(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(
            nid, GenerationStatus.FAILED, failure_reason="syntax error"
        )
        node_state = state.get_node_state(nid)
        assert node_state.status == GenerationStatus.FAILED
        assert node_state.failure_reason == "syntax error"

    def test_increment_retry(self) -> None:
        state = GenerationState()
        nid = uuid4()
        assert state.increment_retry(nid) == 1
        assert state.increment_retry(nid) == 2
        assert state.increment_retry(nid) == 3

    def test_update_test_results(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.update_test_results(nid, passed=5, failed=2)
        node_state = state.get_node_state(nid)
        assert node_state.test_results.passed == 5
        assert node_state.test_results.failed == 2

    def test_is_complete_passed(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.PASSED)
        assert state.is_complete(nid) is True

    def test_is_complete_skipped(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.SKIPPED)
        assert state.is_complete(nid) is True

    def test_is_complete_pending(self) -> None:
        state = GenerationState()
        nid = uuid4()
        assert state.is_complete(nid) is False

    def test_is_failed(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.FAILED)
        assert state.is_failed(nid) is True

    def test_is_not_failed(self) -> None:
        state = GenerationState()
        nid = uuid4()
        assert state.is_failed(nid) is False

    def test_get_summary(self) -> None:
        state = GenerationState()
        ids = [uuid4() for _ in range(5)]
        state.set_status(ids[0], GenerationStatus.PASSED)
        state.set_status(ids[1], GenerationStatus.PASSED)
        state.set_status(ids[2], GenerationStatus.FAILED)
        state.set_status(ids[3], GenerationStatus.SKIPPED)
        state.set_status(ids[4], GenerationStatus.IN_PROGRESS)

        summary = state.get_summary()
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["in_progress"] == 1
        assert summary["pending"] == 0


# --------------------------------------------------------------------------- #
#                         Test: Serialization                                  #
# --------------------------------------------------------------------------- #


class TestGenerationStateSerialization:
    """Test to_dict/from_dict round-trip serialization."""

    def test_round_trip_empty_state(self) -> None:
        state = GenerationState()
        data = state.to_dict()
        restored = GenerationState.from_dict(data)
        assert restored.max_retries == state.max_retries
        assert len(restored.node_states) == 0

    def test_round_trip_with_nodes(self) -> None:
        state = GenerationState(max_retries=5)
        nid = uuid4()
        state.set_status(nid, GenerationStatus.PASSED)
        state.update_test_results(nid, passed=10, failed=0)

        data = state.to_dict()
        restored = GenerationState.from_dict(data)

        assert restored.max_retries == 5
        node_state = restored.get_node_state(nid)
        assert node_state.status == GenerationStatus.PASSED
        assert node_state.test_results.passed == 10

    def test_round_trip_preserves_timestamps(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.IN_PROGRESS)
        original_ts = state.get_node_state(nid).timestamp

        data = state.to_dict()
        restored = GenerationState.from_dict(data)

        restored_ts = restored.get_node_state(nid).timestamp
        assert restored_ts.isoformat() == original_ts.isoformat()

    def test_round_trip_preserves_failure_reason(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(
            nid, GenerationStatus.FAILED, failure_reason="test error"
        )

        data = state.to_dict()
        restored = GenerationState.from_dict(data)

        node_state = restored.get_node_state(nid)
        assert node_state.failure_reason == "test error"

    def test_to_dict_is_json_serializable(self) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.PASSED)
        state.update_test_results(nid, passed=5, failed=1)

        data = state.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert json.loads(json_str) == data


# --------------------------------------------------------------------------- #
#                         Test: Persistence (save/load)                        #
# --------------------------------------------------------------------------- #


class TestGenerationStatePersistence:
    """Test checkpoint save and load with atomic writes."""

    def test_save_creates_file(self, tmp_path) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.PASSED)

        checkpoint_path = str(tmp_path / "checkpoint.json")
        result_path = state.save(checkpoint_path)

        assert os.path.exists(result_path)
        assert result_path == checkpoint_path

    def test_save_load_round_trip(self, tmp_path) -> None:
        state = GenerationState(max_retries=4)
        ids = [uuid4() for _ in range(3)]
        state.set_status(ids[0], GenerationStatus.PASSED)
        state.set_status(ids[1], GenerationStatus.FAILED, failure_reason="err")
        state.set_status(ids[2], GenerationStatus.SKIPPED)
        state.update_test_results(ids[0], passed=8, failed=0)

        checkpoint_path = str(tmp_path / "checkpoint.json")
        state.save(checkpoint_path)

        loaded = GenerationState.load(checkpoint_path)
        assert loaded.max_retries == 4
        assert loaded.get_node_state(ids[0]).status == GenerationStatus.PASSED
        assert loaded.get_node_state(ids[0]).test_results.passed == 8
        assert loaded.get_node_state(ids[1]).failure_reason == "err"
        assert loaded.get_node_state(ids[2]).status == GenerationStatus.SKIPPED

    def test_save_uses_default_path(self, tmp_path) -> None:
        checkpoint_path = str(tmp_path / "default.json")
        state = GenerationState(checkpoint_path=checkpoint_path)
        state.save()
        assert os.path.exists(checkpoint_path)

    def test_load_nonexistent_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            GenerationState.load("/nonexistent/path/checkpoint.json")

    def test_save_creates_parent_directories(self, tmp_path) -> None:
        checkpoint_path = str(tmp_path / "nested" / "dir" / "checkpoint.json")
        state = GenerationState()
        state.save(checkpoint_path)
        assert os.path.exists(checkpoint_path)

    def test_save_is_valid_json(self, tmp_path) -> None:
        state = GenerationState()
        nid = uuid4()
        state.set_status(nid, GenerationStatus.PASSED)

        checkpoint_path = str(tmp_path / "checkpoint.json")
        state.save(checkpoint_path)

        with open(checkpoint_path) as f:
            data = json.load(f)
        assert "node_states" in data
        assert "max_retries" in data

    def test_save_overwrites_existing(self, tmp_path) -> None:
        checkpoint_path = str(tmp_path / "checkpoint.json")

        # Save initial state
        state1 = GenerationState()
        nid = uuid4()
        state1.set_status(nid, GenerationStatus.PENDING)
        state1.save(checkpoint_path)

        # Save updated state
        state2 = GenerationState()
        state2.set_status(nid, GenerationStatus.PASSED)
        state2.save(checkpoint_path)

        loaded = GenerationState.load(checkpoint_path)
        assert loaded.get_node_state(nid).status == GenerationStatus.PASSED

    def test_idempotent_save_load(self, tmp_path) -> None:
        """Saving and loading twice produces the same result."""
        state = GenerationState(max_retries=6)
        nid = uuid4()
        state.set_status(nid, GenerationStatus.PASSED)
        state.update_test_results(nid, passed=3, failed=1)

        path = str(tmp_path / "checkpoint.json")
        state.save(path)
        loaded1 = GenerationState.load(path)
        loaded1.save(path)
        loaded2 = GenerationState.load(path)

        assert loaded2.max_retries == 6
        ns1 = loaded1.get_node_state(nid)
        ns2 = loaded2.get_node_state(nid)
        assert ns1.status == ns2.status
        assert ns1.test_results.passed == ns2.test_results.passed
        assert ns1.test_results.failed == ns2.test_results.failed
