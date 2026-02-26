"""Generation state tracking for graph-guided code generation.

Provides per-node generation status tracking with persistence support
for checkpoint/resume workflows.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenerationStatus(str, Enum):
    """Status of code generation for a single node."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TestResults(BaseModel):
    """Aggregated test results for a generated node."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    passed: int = Field(default=0, ge=0, description="Number of passed tests")
    failed: int = Field(default=0, ge=0, description="Number of failed tests")


class NodeGenerationState(BaseModel):
    """Per-node generation state tracking.

    Tracks the status, test results, retry count, and failure reason
    for a single node's code generation lifecycle.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    status: GenerationStatus = Field(
        default=GenerationStatus.PENDING,
        description="Current generation status",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last status change timestamp (UTC)",
    )
    test_results: TestResults = Field(
        default_factory=TestResults,
        description="Aggregated test results",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of generation retry attempts",
    )
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for failure, if status is FAILED",
    )


class GenerationState(BaseModel):
    """Aggregate generation state for all nodes in a graph.

    Provides methods for updating per-node status, querying state,
    and persisting to/from JSON checkpoint files with atomic writes.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    node_states: dict[str, NodeGenerationState] = Field(
        default_factory=dict,
        description="Per-node generation state, keyed by UUID string",
    )
    checkpoint_path: str = Field(
        default="generation_checkpoint.json",
        description="Path for checkpoint persistence",
    )
    max_retries: int = Field(
        default=8,
        ge=1,
        description="Maximum retry attempts before marking a node as failed",
    )

    def get_node_state(self, node_id: UUID) -> NodeGenerationState:
        """Get or create the generation state for a node.

        Args:
            node_id: The UUID of the node.

        Returns:
            The NodeGenerationState for the node.
        """
        key = str(node_id)
        if key not in self.node_states:
            self.node_states[key] = NodeGenerationState()
        return self.node_states[key]

    def set_status(
        self,
        node_id: UUID,
        status: GenerationStatus,
        *,
        failure_reason: Optional[str] = None,
    ) -> None:
        """Update the generation status for a node.

        Args:
            node_id: The UUID of the node.
            status: The new generation status.
            failure_reason: Optional reason when status is FAILED.
        """
        state = self.get_node_state(node_id)
        state.status = status
        state.timestamp = datetime.now(timezone.utc)
        if failure_reason is not None:
            state.failure_reason = failure_reason

    def increment_retry(self, node_id: UUID) -> int:
        """Increment the retry count for a node.

        Args:
            node_id: The UUID of the node.

        Returns:
            The new retry count after incrementing.
        """
        state = self.get_node_state(node_id)
        state.retry_count += 1
        return state.retry_count

    def update_test_results(
        self, node_id: UUID, *, passed: int = 0, failed: int = 0
    ) -> None:
        """Update test results for a node.

        Args:
            node_id: The UUID of the node.
            passed: Number of passed tests.
            failed: Number of failed tests.
        """
        state = self.get_node_state(node_id)
        state.test_results.passed = passed
        state.test_results.failed = failed

    def is_complete(self, node_id: UUID) -> bool:
        """Check if a node's generation is complete (passed or skipped).

        Args:
            node_id: The UUID of the node.

        Returns:
            True if the node's status is PASSED or SKIPPED.
        """
        state = self.get_node_state(node_id)
        return state.status in {GenerationStatus.PASSED, GenerationStatus.SKIPPED}

    def is_failed(self, node_id: UUID) -> bool:
        """Check if a node's generation has permanently failed.

        Args:
            node_id: The UUID of the node.

        Returns:
            True if the node's status is FAILED.
        """
        return self.get_node_state(node_id).status == GenerationStatus.FAILED

    def get_summary(self) -> dict[str, int]:
        """Get a summary of node statuses.

        Returns:
            A dict mapping status names to counts.
        """
        summary: dict[str, int] = {s.value: 0 for s in GenerationStatus}
        for state in self.node_states.values():
            summary[state.status.value] += 1
        return summary

    def to_dict(self) -> dict[str, Any]:
        """Serialize the generation state to a dictionary.

        Returns:
            A JSON-serializable dictionary of the generation state.
        """
        return {
            "checkpoint_path": self.checkpoint_path,
            "max_retries": self.max_retries,
            "node_states": {
                node_id: {
                    "status": state.status.value,
                    "timestamp": state.timestamp.isoformat(),
                    "test_results": {
                        "passed": state.test_results.passed,
                        "failed": state.test_results.failed,
                    },
                    "retry_count": state.retry_count,
                    "failure_reason": state.failure_reason,
                }
                for node_id, state in self.node_states.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationState:
        """Deserialize a generation state from a dictionary.

        Args:
            data: A dictionary previously produced by to_dict().

        Returns:
            A new GenerationState instance.

        Raises:
            ValueError: If the data is malformed.
        """
        node_states: dict[str, NodeGenerationState] = {}
        for node_id, state_data in data.get("node_states", {}).items():
            node_states[node_id] = NodeGenerationState(
                status=GenerationStatus(state_data["status"]),
                timestamp=datetime.fromisoformat(state_data["timestamp"]),
                test_results=TestResults(
                    passed=state_data["test_results"]["passed"],
                    failed=state_data["test_results"]["failed"],
                ),
                retry_count=state_data["retry_count"],
                failure_reason=state_data.get("failure_reason"),
            )

        return cls(
            node_states=node_states,
            checkpoint_path=data.get("checkpoint_path", "generation_checkpoint.json"),
            max_retries=data.get("max_retries", 8),
        )

    def save(self, path: Optional[str] = None) -> str:
        """Persist the generation state to a JSON file atomically.

        Uses a temp file + rename strategy to ensure atomic writes
        (no partial/corrupt checkpoint files).

        Args:
            path: Optional override path. Defaults to self.checkpoint_path.

        Returns:
            The path the checkpoint was saved to.
        """
        target_path = path or self.checkpoint_path
        data = self.to_dict()

        # Atomic write: write to temp file in same directory, then rename
        dir_name = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, target_path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return target_path

    @classmethod
    def load(cls, path: str) -> GenerationState:
        """Load a generation state from a JSON checkpoint file.

        Args:
            path: The path to the checkpoint JSON file.

        Returns:
            A new GenerationState instance.

        Raises:
            FileNotFoundError: If the checkpoint file doesn't exist.
            ValueError: If the checkpoint data is malformed.
        """
        with open(path) as f:
            data = json.load(f)
        state = cls.from_dict(data)
        state.checkpoint_path = path
        return state
