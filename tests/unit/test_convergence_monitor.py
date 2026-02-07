"""Tests for the Convergence Monitor (Task 2.2.5).

Tests cover:
- ConvergenceConfig validation and defaults
- ConvergenceSnapshot model
- ConvergenceMonitor recording and tracking
- Convergence detection (target coverage reached)
- Plateau detection (< 2% over 5 iterations)
- Early stopping logic
- Progress rate and iteration estimation
- Coverage history for visualization
- ConvergenceSummary generation
- Edge cases: empty monitor, single iteration, max iterations
"""

from __future__ import annotations

from typing import Any

import pytest

from zerorepo.selection.convergence import (
    ConvergenceConfig,
    ConvergenceMonitor,
    ConvergenceSnapshot,
    ConvergenceSummary,
)


# ---------------------------------------------------------------------------
# ConvergenceConfig tests
# ---------------------------------------------------------------------------


class TestConvergenceConfig:
    """Tests for ConvergenceConfig."""

    def test_defaults(self) -> None:
        cfg = ConvergenceConfig()
        assert cfg.plateau_window == 5
        assert cfg.plateau_threshold == 0.02
        assert cfg.target_coverage == 0.95
        assert cfg.max_iterations == 30
        assert cfg.early_coverage_target == 0.70
        assert cfg.early_target_iteration == 5

    def test_custom(self) -> None:
        cfg = ConvergenceConfig(
            plateau_window=10,
            plateau_threshold=0.05,
            target_coverage=0.8,
            max_iterations=50,
        )
        assert cfg.plateau_window == 10
        assert cfg.max_iterations == 50

    def test_invalid_window(self) -> None:
        with pytest.raises(Exception):
            ConvergenceConfig(plateau_window=1)

    def test_invalid_max_iterations(self) -> None:
        with pytest.raises(Exception):
            ConvergenceConfig(max_iterations=0)


# ---------------------------------------------------------------------------
# ConvergenceSnapshot tests
# ---------------------------------------------------------------------------


class TestConvergenceSnapshot:
    """Tests for ConvergenceSnapshot model."""

    def test_basic(self) -> None:
        s = ConvergenceSnapshot(
            iteration=1,
            coverage=0.15,
            coverage_delta=0.15,
            newly_selected=10,
            cumulative_selected=10,
        )
        assert s.iteration == 1
        assert s.coverage == 0.15
        assert s.is_plateau is False

    def test_frozen(self) -> None:
        s = ConvergenceSnapshot(iteration=1, coverage=0.1)
        with pytest.raises(Exception):
            s.coverage = 0.5  # type: ignore


# ---------------------------------------------------------------------------
# ConvergenceMonitor basic tests
# ---------------------------------------------------------------------------


class TestConvergenceMonitor:
    """Tests for ConvergenceMonitor."""

    def test_empty_monitor(self) -> None:
        m = ConvergenceMonitor()
        assert m.iteration_count == 0
        assert m.current_coverage == 0.0
        assert not m.has_converged
        assert not m.has_plateaued
        assert not m.should_stop

    def test_properties(self) -> None:
        cfg = ConvergenceConfig(target_coverage=0.9)
        m = ConvergenceMonitor(config=cfg)
        assert m.config.target_coverage == 0.9

    def test_record_iteration(self) -> None:
        m = ConvergenceMonitor()
        snap = m.record(iteration=1, coverage=0.15, newly_selected=10)
        assert snap.iteration == 1
        assert snap.coverage == 0.15
        assert snap.coverage_delta == 0.15
        assert snap.cumulative_selected == 10
        assert m.iteration_count == 1
        assert m.current_coverage == 0.15

    def test_record_multiple(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.2, newly_selected=15)
        m.record(iteration=2, coverage=0.4, newly_selected=12)
        m.record(iteration=3, coverage=0.55, newly_selected=8)
        assert m.iteration_count == 3
        assert m.current_coverage == 0.55

    def test_record_invalid_iteration(self) -> None:
        m = ConvergenceMonitor()
        with pytest.raises(ValueError, match="iteration"):
            m.record(iteration=0, coverage=0.1)

    def test_record_invalid_coverage(self) -> None:
        m = ConvergenceMonitor()
        with pytest.raises(ValueError, match="coverage"):
            m.record(iteration=1, coverage=1.5)

    def test_record_negative_selected(self) -> None:
        m = ConvergenceMonitor()
        with pytest.raises(ValueError, match="newly_selected"):
            m.record(iteration=1, coverage=0.1, newly_selected=-1)

    def test_coverage_delta(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.2)
        snap = m.record(iteration=2, coverage=0.5)
        assert snap.coverage_delta == pytest.approx(0.3)

    def test_metadata(self) -> None:
        m = ConvergenceMonitor()
        snap = m.record(
            iteration=1, coverage=0.1, metadata={"query_count": 5}
        )
        assert snap.metadata["query_count"] == 5


# ---------------------------------------------------------------------------
# Convergence detection tests
# ---------------------------------------------------------------------------


class TestConvergenceDetection:
    """Tests for convergence (target coverage reached)."""

    def test_convergence_at_target(self) -> None:
        cfg = ConvergenceConfig(target_coverage=0.9)
        m = ConvergenceMonitor(config=cfg)
        m.record(iteration=1, coverage=0.5)
        assert not m.has_converged

        m.record(iteration=2, coverage=0.9)
        assert m.has_converged
        assert m.should_stop

    def test_convergence_above_target(self) -> None:
        cfg = ConvergenceConfig(target_coverage=0.8)
        m = ConvergenceMonitor(config=cfg)
        m.record(iteration=1, coverage=0.95)
        assert m.has_converged


# ---------------------------------------------------------------------------
# Plateau detection tests
# ---------------------------------------------------------------------------


class TestPlateauDetection:
    """Tests for plateau detection."""

    def test_no_plateau_early(self) -> None:
        """Too few iterations for plateau check."""
        m = ConvergenceMonitor()
        for i in range(3):
            m.record(iteration=i + 1, coverage=0.1 + i * 0.01)
        assert not m.has_plateaued

    def test_plateau_detected(self) -> None:
        """< 2% increase over 5 iterations triggers plateau.

        Note: _check_plateau uses history[-window] *before* appending the
        current snapshot, so the look-back is relative to the pre-append
        history length.
        """
        cfg = ConvergenceConfig(plateau_window=5, plateau_threshold=0.02)
        m = ConvergenceMonitor(config=cfg)

        # First few iterations with good progress
        m.record(iteration=1, coverage=0.3)
        m.record(iteration=2, coverage=0.5)
        m.record(iteration=3, coverage=0.6)
        m.record(iteration=4, coverage=0.65)
        m.record(iteration=5, coverage=0.66)

        # Stagnation begins
        m.record(iteration=6, coverage=0.665)
        assert not m.has_plateaued

        m.record(iteration=7, coverage=0.666)
        assert not m.has_plateaued

        m.record(iteration=8, coverage=0.667)
        assert not m.has_plateaued  # history[-5]=iter3 (0.6), 0.667-0.6=0.067 > 0.02

        # One more stagnation: history[-5]=iter4 (0.65), 0.668-0.65=0.018 < 0.02
        m.record(iteration=9, coverage=0.668)
        assert m.has_plateaued

    def test_plateau_triggers_stop(self) -> None:
        cfg = ConvergenceConfig(
            plateau_window=3,
            plateau_threshold=0.01,
            target_coverage=0.95,
        )
        m = ConvergenceMonitor(config=cfg)

        m.record(iteration=1, coverage=0.5)
        m.record(iteration=2, coverage=0.505)
        m.record(iteration=3, coverage=0.508)
        # Window [1,2,3]: 0.5 → 0.508 = 0.008 < 0.01
        m.record(iteration=4, coverage=0.509)
        assert m.has_plateaued
        assert m.should_stop


# ---------------------------------------------------------------------------
# Max iterations tests
# ---------------------------------------------------------------------------


class TestMaxIterations:
    """Tests for max iterations stopping."""

    def test_max_iterations_stop(self) -> None:
        cfg = ConvergenceConfig(max_iterations=5, target_coverage=0.99)
        m = ConvergenceMonitor(config=cfg)

        for i in range(5):
            m.record(iteration=i + 1, coverage=0.1 * (i + 1))

        assert m.should_stop  # Max iterations reached


# ---------------------------------------------------------------------------
# Progress rate and estimation tests
# ---------------------------------------------------------------------------


class TestProgressRate:
    """Tests for progress rate and estimation."""

    def test_progress_rate_empty(self) -> None:
        m = ConvergenceMonitor()
        assert m.get_progress_rate() == 0.0

    def test_progress_rate_single(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.2)
        # Only 1 data point — rate requires at least 2 points.
        rate = m.get_progress_rate()
        assert rate == 0.0

    def test_progress_rate_linear(self) -> None:
        m = ConvergenceMonitor()
        for i in range(10):
            m.record(iteration=i + 1, coverage=0.1 * (i + 1))
        # Linear 0.1 per iteration
        rate = m.get_progress_rate(window=5)
        assert rate == pytest.approx(0.1)

    def test_estimate_remaining(self) -> None:
        cfg = ConvergenceConfig(target_coverage=1.0)
        m = ConvergenceMonitor(config=cfg)
        for i in range(5):
            m.record(iteration=i + 1, coverage=0.1 * (i + 1))
        est = m.estimate_iterations_remaining()
        assert est is not None
        assert est > 0

    def test_estimate_converged(self) -> None:
        cfg = ConvergenceConfig(target_coverage=0.5)
        m = ConvergenceMonitor(config=cfg)
        m.record(iteration=1, coverage=0.6)
        assert m.estimate_iterations_remaining() == 0

    def test_estimate_zero_rate(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.5)
        m.record(iteration=2, coverage=0.5)
        # Zero rate → None
        assert m.estimate_iterations_remaining() is None


# ---------------------------------------------------------------------------
# Coverage history tests
# ---------------------------------------------------------------------------


class TestCoverageHistory:
    """Tests for coverage history retrieval."""

    def test_empty_history(self) -> None:
        m = ConvergenceMonitor()
        assert m.get_coverage_history() == []

    def test_history_pairs(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.2)
        m.record(iteration=2, coverage=0.4)
        m.record(iteration=3, coverage=0.6)
        history = m.get_coverage_history()
        assert history == [(1, 0.2), (2, 0.4), (3, 0.6)]


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------


class TestConvergenceSummary:
    """Tests for convergence summary generation."""

    def test_empty_summary(self) -> None:
        m = ConvergenceMonitor()
        summary = m.get_summary()
        assert summary.total_iterations == 0
        assert summary.final_coverage == 0.0
        assert not summary.has_converged
        assert not summary.has_plateaued

    def test_full_summary(self) -> None:
        cfg = ConvergenceConfig(
            target_coverage=0.9,
            early_coverage_target=0.5,
            early_target_iteration=3,
        )
        m = ConvergenceMonitor(config=cfg)
        m.record(iteration=1, coverage=0.3, newly_selected=20)
        m.record(iteration=2, coverage=0.6, newly_selected=15)
        m.record(iteration=3, coverage=0.8, newly_selected=10)
        m.record(iteration=4, coverage=0.92, newly_selected=5)

        summary = m.get_summary()
        assert summary.total_iterations == 4
        assert summary.final_coverage == 0.92
        assert summary.has_converged  # 0.92 >= 0.9
        assert summary.met_early_target  # 0.6 >= 0.5 at iter 2 (≤ 3)
        assert summary.max_coverage_delta == pytest.approx(0.3)  # iter 1→2
        assert len(summary.history) == 4

    def test_summary_frozen(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.5)
        summary = m.get_summary()
        with pytest.raises(Exception):
            summary.total_iterations = 99  # type: ignore


# ---------------------------------------------------------------------------
# Reset tests
# ---------------------------------------------------------------------------


class TestReset:
    """Tests for monitor reset."""

    def test_reset(self) -> None:
        m = ConvergenceMonitor()
        m.record(iteration=1, coverage=0.5, newly_selected=10)
        m.record(iteration=2, coverage=0.7, newly_selected=8)
        assert m.iteration_count == 2

        m.reset()
        assert m.iteration_count == 0
        assert m.current_coverage == 0.0
        assert not m.has_converged
        assert not m.has_plateaued


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from zerorepo.selection import (
            ConvergenceConfig,
            ConvergenceMonitor,
            ConvergenceSnapshot,
        )
        assert ConvergenceMonitor is not None

    def test_import_from_module(self) -> None:
        from zerorepo.selection.convergence import (
            ConvergenceConfig,
            ConvergenceMonitor,
            ConvergenceSnapshot,
            ConvergenceSummary,
        )
        assert ConvergenceSummary is not None
