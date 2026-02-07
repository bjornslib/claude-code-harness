"""Unit tests for the codegen regression_detector module."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from zerorepo.codegen.regression_detector import (
    Regression,
    RegressionDetector,
    RegressionDetectorConfig,
    RegressionReport,
    RegressionSeverity,
    RegressionType,
    TestSnapshot,
)


# --------------------------------------------------------------------------- #
#                         Test: RegressionSeverity Enum                        #
# --------------------------------------------------------------------------- #


class TestRegressionSeverity:
    """Test RegressionSeverity enum values."""

    def test_all_values(self) -> None:
        assert RegressionSeverity.CRITICAL == "critical"
        assert RegressionSeverity.HIGH == "high"
        assert RegressionSeverity.MEDIUM == "medium"
        assert RegressionSeverity.LOW == "low"

    def test_is_string_enum(self) -> None:
        assert isinstance(RegressionSeverity.CRITICAL, str)

    def test_from_value(self) -> None:
        assert RegressionSeverity("critical") == RegressionSeverity.CRITICAL

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            RegressionSeverity("unknown")


# --------------------------------------------------------------------------- #
#                         Test: RegressionType Enum                            #
# --------------------------------------------------------------------------- #


class TestRegressionType:
    """Test RegressionType enum values."""

    def test_all_values(self) -> None:
        assert RegressionType.TEST_FAILURE == "test_failure"
        assert RegressionType.NEW_ERROR == "new_error"
        assert RegressionType.PASS_RATE_DROP == "pass_rate_drop"
        assert RegressionType.TEST_COUNT_DROP == "test_count_drop"
        assert RegressionType.DURATION_SPIKE == "duration_spike"


# --------------------------------------------------------------------------- #
#                         Test: TestSnapshot                                   #
# --------------------------------------------------------------------------- #


class TestTestSnapshot:
    """Test TestSnapshot dataclass."""

    def test_defaults(self) -> None:
        node_id = uuid4()
        snap = TestSnapshot(iteration=1, node_id=node_id)
        assert snap.iteration == 1
        assert snap.node_id == node_id
        assert snap.passed == 0
        assert snap.failed == 0
        assert snap.total == 0
        assert snap.test_names_passed == set()
        assert snap.test_names_failed == set()

    def test_pass_rate_zero_total(self) -> None:
        snap = TestSnapshot(iteration=1, node_id=uuid4())
        assert snap.pass_rate == 0.0

    def test_pass_rate_computed(self) -> None:
        snap = TestSnapshot(iteration=1, node_id=uuid4(), passed=3, total=4)
        assert snap.pass_rate == 75.0

    def test_pass_rate_perfect(self) -> None:
        snap = TestSnapshot(iteration=1, node_id=uuid4(), passed=10, total=10)
        assert snap.pass_rate == 100.0

    def test_with_test_names(self) -> None:
        snap = TestSnapshot(
            iteration=1,
            node_id=uuid4(),
            passed=2,
            total=3,
            test_names_passed={"test_a", "test_b"},
            test_names_failed={"test_c"},
        )
        assert len(snap.test_names_passed) == 2
        assert "test_c" in snap.test_names_failed


# --------------------------------------------------------------------------- #
#                         Test: Regression                                     #
# --------------------------------------------------------------------------- #


class TestRegression:
    """Test Regression dataclass."""

    def test_creation(self) -> None:
        node_id = uuid4()
        reg = Regression(
            node_id=node_id,
            regression_type=RegressionType.TEST_FAILURE,
            severity=RegressionSeverity.HIGH,
            description="test_foo now fails",
            previous_value=["test_foo"],
            current_value=["test_foo", "test_bar"],
            affected_tests=["test_foo"],
            iteration=3,
        )
        assert reg.node_id == node_id
        assert reg.regression_type == RegressionType.TEST_FAILURE
        assert reg.severity == RegressionSeverity.HIGH
        assert "test_foo" in reg.description
        assert reg.iteration == 3
        assert len(reg.affected_tests) == 1

    def test_defaults(self) -> None:
        reg = Regression(
            node_id=uuid4(),
            regression_type=RegressionType.NEW_ERROR,
            severity=RegressionSeverity.LOW,
            description="test",
        )
        assert reg.previous_value is None
        assert reg.current_value is None
        assert reg.affected_tests == []
        assert reg.iteration == 0


# --------------------------------------------------------------------------- #
#                         Test: RegressionReport                               #
# --------------------------------------------------------------------------- #


class TestRegressionReport:
    """Test RegressionReport dataclass."""

    def test_defaults(self) -> None:
        report = RegressionReport()
        assert report.regressions == []
        assert report.nodes_checked == 0
        assert report.nodes_regressed == 0
        assert report.total_regressions == 0
        assert report.has_critical is False

    def test_with_data(self) -> None:
        report = RegressionReport(
            nodes_checked=5,
            nodes_regressed=2,
            total_regressions=3,
            has_critical=True,
        )
        assert report.nodes_checked == 5
        assert report.has_critical is True


# --------------------------------------------------------------------------- #
#                         Test: RegressionDetectorConfig                       #
# --------------------------------------------------------------------------- #


class TestRegressionDetectorConfig:
    """Test RegressionDetectorConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = RegressionDetectorConfig()
        assert config.pass_rate_threshold == 5.0
        assert config.duration_spike_factor == 3.0
        assert config.min_tests_for_rate == 2
        assert config.track_individual_tests is True

    def test_custom_values(self) -> None:
        config = RegressionDetectorConfig(
            pass_rate_threshold=10.0,
            duration_spike_factor=5.0,
            min_tests_for_rate=5,
            track_individual_tests=False,
        )
        assert config.pass_rate_threshold == 10.0
        assert config.track_individual_tests is False

    def test_validation(self) -> None:
        with pytest.raises(Exception):
            RegressionDetectorConfig(pass_rate_threshold=-1.0)
        with pytest.raises(Exception):
            RegressionDetectorConfig(duration_spike_factor=0.5)
        with pytest.raises(Exception):
            RegressionDetectorConfig(min_tests_for_rate=0)


# --------------------------------------------------------------------------- #
#                         Test: RegressionDetector                             #
# --------------------------------------------------------------------------- #


class TestRegressionDetector:
    """Test RegressionDetector regression detection logic."""

    def setup_method(self) -> None:
        self.node_id = uuid4()
        self.detector = RegressionDetector()

    def test_no_history_no_regressions(self) -> None:
        regressions = self.detector.detect_regressions(self.node_id)
        assert regressions == []

    def test_single_snapshot_no_regressions(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=self.node_id, passed=5, total=5)
        )
        regressions = self.detector.detect_regressions(self.node_id)
        assert regressions == []

    def test_stable_results_no_regressions(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=self.node_id, passed=5, total=5)
        )
        self.detector.record_snapshot(
            TestSnapshot(iteration=2, node_id=self.node_id, passed=5, total=5)
        )
        regressions = self.detector.detect_regressions(self.node_id)
        assert regressions == []

    def test_detect_test_failure_regression(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=3,
                total=3,
                test_names_passed={"test_a", "test_b", "test_c"},
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=1,
                failed=2,
                total=3,
                test_names_passed={"test_a"},
                test_names_failed={"test_b", "test_c"},
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        failure_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.TEST_FAILURE
        ]
        assert len(failure_regs) == 1
        assert set(failure_regs[0].affected_tests) == {"test_b", "test_c"}

    def test_detect_pass_rate_drop(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=10,
                total=10,
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=8,
                failed=2,
                total=10,
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        rate_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.PASS_RATE_DROP
        ]
        assert len(rate_regs) == 1
        assert rate_regs[0].previous_value == 100.0
        assert rate_regs[0].current_value == 80.0

    def test_no_pass_rate_regression_below_threshold(self) -> None:
        config = RegressionDetectorConfig(pass_rate_threshold=25.0)
        detector = RegressionDetector(config=config)
        detector.record_snapshot(
            TestSnapshot(
                iteration=1, node_id=self.node_id, passed=10, total=10
            )
        )
        detector.record_snapshot(
            TestSnapshot(
                iteration=2, node_id=self.node_id, passed=8, failed=2, total=10
            )
        )
        regressions = detector.detect_regressions(self.node_id)
        rate_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.PASS_RATE_DROP
        ]
        assert len(rate_regs) == 0  # 20% drop < 25% threshold

    def test_detect_test_count_drop(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1, node_id=self.node_id, passed=10, total=10
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2, node_id=self.node_id, passed=5, total=5
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        count_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.TEST_COUNT_DROP
        ]
        assert len(count_regs) == 1
        assert count_regs[0].previous_value == 10
        assert count_regs[0].current_value == 5

    def test_detect_duration_spike(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=5,
                total=5,
                duration_ms=100.0,
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=5,
                total=5,
                duration_ms=500.0,
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        dur_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.DURATION_SPIKE
        ]
        assert len(dur_regs) == 1
        assert dur_regs[0].previous_value == 100.0
        assert dur_regs[0].current_value == 500.0

    def test_no_duration_spike_below_factor(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=5,
                total=5,
                duration_ms=100.0,
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=5,
                total=5,
                duration_ms=200.0,  # 2x, below default 3x threshold
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        dur_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.DURATION_SPIKE
        ]
        assert len(dur_regs) == 0

    def test_detect_new_errors(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=5,
                errors=0,
                total=5,
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=3,
                errors=2,
                total=5,
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        error_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.NEW_ERROR
        ]
        assert len(error_regs) == 1

    def test_critical_severity_many_test_failures(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=5,
                total=5,
                test_names_passed={"t1", "t2", "t3", "t4", "t5"},
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=1,
                failed=4,
                total=5,
                test_names_passed={"t1"},
                test_names_failed={"t2", "t3", "t4", "t5"},
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        failure_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.TEST_FAILURE
        ]
        assert len(failure_regs) == 1
        assert failure_regs[0].severity == RegressionSeverity.CRITICAL

    def test_critical_severity_large_pass_rate_drop(self) -> None:
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=10,
                total=10,
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=5,
                failed=5,
                total=10,
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        rate_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.PASS_RATE_DROP
        ]
        assert len(rate_regs) == 1
        assert rate_regs[0].severity == RegressionSeverity.CRITICAL

    def test_multiple_regressions_detected(self) -> None:
        """A single node can have multiple regression types at once."""
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=self.node_id,
                passed=10,
                errors=0,
                total=10,
                duration_ms=50.0,
                test_names_passed={"t1", "t2", "t3"},
            )
        )
        self.detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=self.node_id,
                passed=3,
                failed=2,
                errors=2,
                total=7,
                duration_ms=200.0,
                test_names_passed={"t1"},
                test_names_failed={"t2", "t3"},
            )
        )
        regressions = self.detector.detect_regressions(self.node_id)
        types = {r.regression_type for r in regressions}
        # Should have: test_failure, pass_rate_drop, test_count_drop, new_error,
        # duration_spike
        assert RegressionType.TEST_FAILURE in types
        assert RegressionType.PASS_RATE_DROP in types
        assert RegressionType.TEST_COUNT_DROP in types
        assert RegressionType.NEW_ERROR in types
        assert RegressionType.DURATION_SPIKE in types

    def test_record_and_get_history(self) -> None:
        snap = TestSnapshot(iteration=1, node_id=self.node_id, passed=5, total=5)
        self.detector.record_snapshot(snap)
        history = self.detector.get_history(self.node_id)
        assert len(history) == 1
        assert history[0] is snap

    def test_get_history_unknown_node(self) -> None:
        history = self.detector.get_history(uuid4())
        assert history == []


# --------------------------------------------------------------------------- #
#                         Test: RegressionReport Generation                    #
# --------------------------------------------------------------------------- #


class TestRegressionReportGeneration:
    """Test generate_report method."""

    def test_report_no_nodes(self) -> None:
        detector = RegressionDetector()
        report = detector.generate_report()
        assert report.nodes_checked == 0
        assert report.total_regressions == 0

    def test_report_no_regressions(self) -> None:
        detector = RegressionDetector()
        node_id = uuid4()
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=node_id, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=2, node_id=node_id, passed=5, total=5)
        )
        report = detector.generate_report()
        assert report.nodes_checked == 1
        assert report.total_regressions == 0
        assert report.has_critical is False

    def test_report_with_regressions(self) -> None:
        detector = RegressionDetector()
        node_id = uuid4()
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=node_id, passed=10, total=10)
        )
        detector.record_snapshot(
            TestSnapshot(
                iteration=2, node_id=node_id, passed=5, failed=5, total=10
            )
        )
        report = detector.generate_report()
        assert report.nodes_checked == 1
        assert report.nodes_regressed == 1
        assert report.total_regressions > 0
        assert report.has_critical is True  # 50% drop is critical

    def test_report_multiple_nodes(self) -> None:
        detector = RegressionDetector()
        n1, n2 = uuid4(), uuid4()
        # Node 1: stable
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n1, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=2, node_id=n1, passed=5, total=5)
        )
        # Node 2: regressed
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n2, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=2, node_id=n2, passed=1, failed=4, total=5)
        )
        report = detector.generate_report()
        assert report.nodes_checked == 2
        assert report.nodes_regressed == 1

    def test_report_specific_nodes(self) -> None:
        detector = RegressionDetector()
        n1, n2 = uuid4(), uuid4()
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n1, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=2, node_id=n1, passed=1, failed=4, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n2, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=2, node_id=n2, passed=1, failed=4, total=5)
        )
        # Only check n1
        report = detector.generate_report(node_ids=[n1])
        assert report.nodes_checked == 1

    def test_clear_history_specific_node(self) -> None:
        detector = RegressionDetector()
        n1, n2 = uuid4(), uuid4()
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n1, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n2, passed=3, total=3)
        )
        detector.clear_history(n1)
        assert detector.get_history(n1) == []
        assert len(detector.get_history(n2)) == 1

    def test_clear_all_history(self) -> None:
        detector = RegressionDetector()
        n1, n2 = uuid4(), uuid4()
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n1, passed=5, total=5)
        )
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=n2, passed=3, total=3)
        )
        detector.clear_history()
        assert detector.history == {}

    def test_config_property(self) -> None:
        config = RegressionDetectorConfig(pass_rate_threshold=15.0)
        detector = RegressionDetector(config=config)
        assert detector.config is config
        assert detector.config.pass_rate_threshold == 15.0

    def test_disable_individual_test_tracking(self) -> None:
        config = RegressionDetectorConfig(track_individual_tests=False)
        detector = RegressionDetector(config=config)
        node_id = uuid4()
        detector.record_snapshot(
            TestSnapshot(
                iteration=1,
                node_id=node_id,
                passed=3,
                total=3,
                test_names_passed={"t1", "t2", "t3"},
            )
        )
        detector.record_snapshot(
            TestSnapshot(
                iteration=2,
                node_id=node_id,
                passed=1,
                failed=2,
                total=3,
                test_names_passed={"t1"},
                test_names_failed={"t2", "t3"},
            )
        )
        regressions = detector.detect_regressions(node_id)
        failure_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.TEST_FAILURE
        ]
        # Individual tracking disabled, so no TEST_FAILURE regressions
        assert len(failure_regs) == 0
        # But pass rate drop should still be detected
        rate_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.PASS_RATE_DROP
        ]
        assert len(rate_regs) == 1

    def test_min_tests_for_rate_check(self) -> None:
        """Pass rate regression should not fire when below min test threshold."""
        config = RegressionDetectorConfig(min_tests_for_rate=5)
        detector = RegressionDetector(config=config)
        node_id = uuid4()
        detector.record_snapshot(
            TestSnapshot(iteration=1, node_id=node_id, passed=3, total=3)
        )
        detector.record_snapshot(
            TestSnapshot(
                iteration=2, node_id=node_id, passed=1, failed=2, total=3
            )
        )
        regressions = detector.detect_regressions(node_id)
        rate_regs = [
            r for r in regressions
            if r.regression_type == RegressionType.PASS_RATE_DROP
        ]
        assert len(rate_regs) == 0  # 3 tests < 5 min threshold
