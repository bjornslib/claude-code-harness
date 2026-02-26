"""Regression detection engine for graph-guided code generation.

Compares test results across generation iterations to detect regressions
(tests that previously passed but now fail). Supports per-node and
cross-node regression analysis with configurable thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                              Models                                          #
# --------------------------------------------------------------------------- #


class RegressionSeverity(str, Enum):
    """Severity levels for detected regressions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RegressionType(str, Enum):
    """Types of regressions that can be detected."""

    TEST_FAILURE = "test_failure"
    NEW_ERROR = "new_error"
    PASS_RATE_DROP = "pass_rate_drop"
    TEST_COUNT_DROP = "test_count_drop"
    DURATION_SPIKE = "duration_spike"


@dataclass
class TestSnapshot:
    """A snapshot of test results at a specific iteration.

    Attributes:
        iteration: The generation iteration number.
        node_id: The UUID of the node.
        passed: Number of passed tests.
        failed: Number of failed tests.
        errors: Number of errored tests.
        total: Total number of tests.
        duration_ms: Total test execution time in milliseconds.
        test_names_passed: Set of test names that passed.
        test_names_failed: Set of test names that failed.
        timestamp: When this snapshot was taken.
    """

    iteration: int
    node_id: UUID
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total: int = 0
    duration_ms: float = 0.0
    test_names_passed: set[str] = field(default_factory=set)
    test_names_failed: set[str] = field(default_factory=set)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def pass_rate(self) -> float:
        """Compute the pass rate as a percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100.0


@dataclass
class Regression:
    """A single detected regression.

    Attributes:
        node_id: The UUID of the node with the regression.
        regression_type: The type of regression detected.
        severity: The severity level.
        description: Human-readable description of the regression.
        previous_value: The value before the regression.
        current_value: The current (regressed) value.
        affected_tests: Names of tests affected by this regression.
        iteration: The iteration where the regression was detected.
    """

    node_id: UUID
    regression_type: RegressionType
    severity: RegressionSeverity
    description: str
    previous_value: Any = None
    current_value: Any = None
    affected_tests: list[str] = field(default_factory=list)
    iteration: int = 0


@dataclass
class RegressionReport:
    """Aggregate regression report across all nodes.

    Attributes:
        regressions: All detected regressions.
        nodes_checked: Number of nodes analyzed.
        nodes_regressed: Number of nodes with regressions.
        total_regressions: Total number of regressions found.
        has_critical: Whether any critical regressions were found.
        timestamp: When the report was generated.
    """

    regressions: list[Regression] = field(default_factory=list)
    nodes_checked: int = 0
    nodes_regressed: int = 0
    total_regressions: int = 0
    has_critical: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RegressionDetectorConfig(BaseModel):
    """Configuration for the RegressionDetector.

    Attributes:
        pass_rate_threshold: Minimum pass rate drop (percentage points) to flag.
        duration_spike_factor: Factor increase in duration to flag as a spike.
        min_tests_for_rate: Minimum tests before pass rate comparisons apply.
        track_individual_tests: Whether to track per-test pass/fail history.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    pass_rate_threshold: float = Field(
        default=5.0,
        ge=0.0,
        description="Minimum pass rate drop (pct pts) to flag as regression",
    )
    duration_spike_factor: float = Field(
        default=3.0,
        ge=1.0,
        description="Factor increase in duration to flag as regression",
    )
    min_tests_for_rate: int = Field(
        default=2,
        ge=1,
        description="Minimum test count before rate comparisons apply",
    )
    track_individual_tests: bool = Field(
        default=True,
        description="Track per-test pass/fail history",
    )


# --------------------------------------------------------------------------- #
#                           Regression Detector                                #
# --------------------------------------------------------------------------- #


class RegressionDetector:
    """Detects regressions across generation iterations.

    Maintains a history of test snapshots per node and compares successive
    iterations to detect regressions in pass rate, individual tests, test
    counts, and execution duration.

    Args:
        config: Regression detection configuration.
    """

    def __init__(self, config: RegressionDetectorConfig | None = None) -> None:
        self._config = config or RegressionDetectorConfig()
        # node_id (str) -> list of snapshots in iteration order
        self._history: dict[str, list[TestSnapshot]] = {}

    @property
    def config(self) -> RegressionDetectorConfig:
        """The detector configuration."""
        return self._config

    @property
    def history(self) -> dict[str, list[TestSnapshot]]:
        """The snapshot history, keyed by node UUID string."""
        return self._history

    def record_snapshot(self, snapshot: TestSnapshot) -> None:
        """Record a test snapshot for a node.

        Args:
            snapshot: The test snapshot to record.
        """
        key = str(snapshot.node_id)
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(snapshot)
        logger.debug(
            "Recorded snapshot for node %s iteration %d: %d/%d passed",
            snapshot.node_id,
            snapshot.iteration,
            snapshot.passed,
            snapshot.total,
        )

    def get_history(self, node_id: UUID) -> list[TestSnapshot]:
        """Get all recorded snapshots for a node.

        Args:
            node_id: The UUID of the node.

        Returns:
            List of snapshots in iteration order, or empty list if none.
        """
        return self._history.get(str(node_id), [])

    def detect_regressions(self, node_id: UUID) -> list[Regression]:
        """Detect regressions for a specific node by comparing latest two snapshots.

        Args:
            node_id: The UUID of the node to check.

        Returns:
            A list of detected regressions (may be empty).
        """
        snapshots = self.get_history(node_id)
        if len(snapshots) < 2:
            return []

        prev = snapshots[-2]
        curr = snapshots[-1]
        regressions: list[Regression] = []

        # Check 1: Individual test failures (tests that passed before, now fail)
        if self._config.track_individual_tests:
            newly_failed = prev.test_names_passed & curr.test_names_failed
            if newly_failed:
                severity = (
                    RegressionSeverity.CRITICAL
                    if len(newly_failed) > 3
                    else RegressionSeverity.HIGH
                )
                regressions.append(
                    Regression(
                        node_id=node_id,
                        regression_type=RegressionType.TEST_FAILURE,
                        severity=severity,
                        description=(
                            f"{len(newly_failed)} test(s) that previously passed "
                            f"now fail"
                        ),
                        previous_value=sorted(newly_failed),
                        current_value=sorted(curr.test_names_failed),
                        affected_tests=sorted(newly_failed),
                        iteration=curr.iteration,
                    )
                )

        # Check 2: Pass rate drop
        if (
            prev.total >= self._config.min_tests_for_rate
            and curr.total >= self._config.min_tests_for_rate
        ):
            rate_drop = prev.pass_rate - curr.pass_rate
            if rate_drop >= self._config.pass_rate_threshold:
                severity = (
                    RegressionSeverity.CRITICAL
                    if rate_drop >= 20.0
                    else RegressionSeverity.MEDIUM
                )
                regressions.append(
                    Regression(
                        node_id=node_id,
                        regression_type=RegressionType.PASS_RATE_DROP,
                        severity=severity,
                        description=(
                            f"Pass rate dropped from {prev.pass_rate:.1f}% "
                            f"to {curr.pass_rate:.1f}% "
                            f"(-{rate_drop:.1f} percentage points)"
                        ),
                        previous_value=prev.pass_rate,
                        current_value=curr.pass_rate,
                        iteration=curr.iteration,
                    )
                )

        # Check 3: Test count drop (tests disappeared)
        if prev.total > 0 and curr.total < prev.total:
            drop_count = prev.total - curr.total
            severity = (
                RegressionSeverity.HIGH
                if drop_count > 2
                else RegressionSeverity.LOW
            )
            regressions.append(
                Regression(
                    node_id=node_id,
                    regression_type=RegressionType.TEST_COUNT_DROP,
                    severity=severity,
                    description=(
                        f"Test count dropped from {prev.total} to {curr.total} "
                        f"({drop_count} tests disappeared)"
                    ),
                    previous_value=prev.total,
                    current_value=curr.total,
                    iteration=curr.iteration,
                )
            )

        # Check 4: Duration spike
        if prev.duration_ms > 0 and curr.duration_ms > 0:
            ratio = curr.duration_ms / prev.duration_ms
            if ratio >= self._config.duration_spike_factor:
                regressions.append(
                    Regression(
                        node_id=node_id,
                        regression_type=RegressionType.DURATION_SPIKE,
                        severity=RegressionSeverity.LOW,
                        description=(
                            f"Test duration spiked from {prev.duration_ms:.0f}ms "
                            f"to {curr.duration_ms:.0f}ms "
                            f"({ratio:.1f}x increase)"
                        ),
                        previous_value=prev.duration_ms,
                        current_value=curr.duration_ms,
                        iteration=curr.iteration,
                    )
                )

        # Check 5: New errors (errors that didn't exist before)
        if curr.errors > prev.errors:
            new_errors = curr.errors - prev.errors
            regressions.append(
                Regression(
                    node_id=node_id,
                    regression_type=RegressionType.NEW_ERROR,
                    severity=RegressionSeverity.HIGH,
                    description=(
                        f"{new_errors} new error(s) appeared "
                        f"(was {prev.errors}, now {curr.errors})"
                    ),
                    previous_value=prev.errors,
                    current_value=curr.errors,
                    iteration=curr.iteration,
                )
            )

        return regressions

    def generate_report(self, node_ids: list[UUID] | None = None) -> RegressionReport:
        """Generate a full regression report for the specified nodes.

        Args:
            node_ids: List of node UUIDs to check. If None, checks all nodes
                with recorded history.

        Returns:
            A RegressionReport summarizing all detected regressions.
        """
        if node_ids is None:
            node_ids = [UUID(key) for key in self._history.keys()]

        all_regressions: list[Regression] = []
        nodes_with_regressions: set[str] = set()

        for nid in node_ids:
            regs = self.detect_regressions(nid)
            if regs:
                all_regressions.extend(regs)
                nodes_with_regressions.add(str(nid))

        has_critical = any(
            r.severity == RegressionSeverity.CRITICAL for r in all_regressions
        )

        report = RegressionReport(
            regressions=all_regressions,
            nodes_checked=len(node_ids),
            nodes_regressed=len(nodes_with_regressions),
            total_regressions=len(all_regressions),
            has_critical=has_critical,
        )

        logger.info(
            "Regression report: %d nodes checked, %d regressions found, "
            "critical=%s",
            report.nodes_checked,
            report.total_regressions,
            report.has_critical,
        )

        return report

    def clear_history(self, node_id: UUID | None = None) -> None:
        """Clear snapshot history for a node or all nodes.

        Args:
            node_id: If provided, clear only this node's history.
                If None, clear all history.
        """
        if node_id is not None:
            self._history.pop(str(node_id), None)
        else:
            self._history.clear()
