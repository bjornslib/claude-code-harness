"""Convergence Monitor – track coverage per iteration and detect plateau.

Implements Task 2.2.5 of PRD-RPG-P2-001 (Epic 2.2: Explore-Exploit Subtree
Selection). Tracks coverage ratio per iteration, detects convergence plateau
(< 2% increase over a sliding window), and provides early stopping logic.

Performance targets from PRD:
- 70% coverage by iteration 5
- 95% coverage by iteration 30
- Plateau detection: < 2% increase over 5 iterations

Example::

    from zerorepo.selection.convergence import (
        ConvergenceMonitor,
        ConvergenceConfig,
    )

    monitor = ConvergenceMonitor()
    monitor.record(iteration=1, coverage=0.15, newly_selected=20)
    monitor.record(iteration=2, coverage=0.35, newly_selected=15)

    if monitor.has_converged:
        print("Selection has converged!")
    if monitor.should_stop:
        print("Early stopping recommended.")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConvergenceConfig(BaseModel):
    """Configuration for the ConvergenceMonitor.

    Attributes:
        plateau_window: Number of recent iterations to check for plateau.
        plateau_threshold: Maximum coverage increase within the window
            to be considered a plateau (as a fraction, e.g. 0.02 = 2%).
        target_coverage: Coverage ratio at which convergence is declared.
        max_iterations: Hard stop after this many iterations.
        early_coverage_target: Expected coverage by early_target_iteration.
        early_target_iteration: Iteration by which early_coverage_target
            should be reached (for health checks).
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    plateau_window: int = Field(
        default=5,
        ge=2,
        le=50,
        description="Sliding window size for plateau detection",
    )
    plateau_threshold: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Max coverage increase to trigger plateau (2%)",
    )
    target_coverage: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Coverage ratio at which convergence is declared",
    )
    max_iterations: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Hard stop iteration limit",
    )
    early_coverage_target: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Expected coverage by early target iteration",
    )
    early_target_iteration: int = Field(
        default=5,
        ge=1,
        description="Iteration by which early target should be reached",
    )


# ---------------------------------------------------------------------------
# Convergence Snapshot
# ---------------------------------------------------------------------------


class ConvergenceSnapshot(BaseModel):
    """A single iteration's convergence data.

    Attributes:
        iteration: Iteration number (1-based).
        coverage: Coverage ratio at this iteration.
        coverage_delta: Change in coverage from previous iteration.
        newly_selected: Number of new features selected this iteration.
        cumulative_selected: Total features selected so far.
        is_plateau: Whether this iteration is part of a plateau.
        metadata: Additional iteration-specific data.
    """

    model_config = ConfigDict(frozen=True)

    iteration: int = Field(ge=1, description="Iteration number")
    coverage: float = Field(ge=0.0, le=1.0, description="Coverage ratio")
    coverage_delta: float = Field(
        default=0.0, description="Coverage change from previous"
    )
    newly_selected: int = Field(
        default=0, ge=0, description="New features this iteration"
    )
    cumulative_selected: int = Field(
        default=0, ge=0, description="Total features so far"
    )
    is_plateau: bool = Field(
        default=False, description="Part of a plateau"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extra metadata"
    )


# ---------------------------------------------------------------------------
# Convergence Summary
# ---------------------------------------------------------------------------


class ConvergenceSummary(BaseModel):
    """Summary of convergence monitoring across all iterations.

    Attributes:
        total_iterations: Number of iterations recorded.
        final_coverage: Coverage at the last iteration.
        has_converged: Whether target coverage was reached.
        has_plateaued: Whether a plateau was detected.
        plateau_detected_at: Iteration where plateau was first detected.
        met_early_target: Whether early coverage target was met on time.
        max_coverage_delta: Largest single-iteration coverage jump.
        history: All recorded snapshots.
    """

    model_config = ConfigDict(frozen=True)

    total_iterations: int = Field(ge=0, description="Iterations recorded")
    final_coverage: float = Field(
        ge=0.0, le=1.0, description="Final coverage"
    )
    has_converged: bool = Field(
        default=False, description="Reached target coverage"
    )
    has_plateaued: bool = Field(
        default=False, description="Plateau detected"
    )
    plateau_detected_at: int | None = Field(
        default=None, description="Iteration of first plateau"
    )
    met_early_target: bool = Field(
        default=False, description="Met early coverage target"
    )
    max_coverage_delta: float = Field(
        default=0.0, description="Largest coverage jump"
    )
    history: list[ConvergenceSnapshot] = Field(
        default_factory=list, description="All snapshots"
    )


# ---------------------------------------------------------------------------
# Convergence Monitor
# ---------------------------------------------------------------------------


class ConvergenceMonitor:
    """Monitors iteration convergence for the explore-exploit selection loop.

    Tracks coverage ratio per iteration, detects convergence (reaching
    target coverage) and plateau (insufficient progress over a sliding
    window). Provides early stopping recommendations.

    Args:
        config: Optional configuration.

    Example::

        monitor = ConvergenceMonitor()
        for i in range(30):
            # ... run exploration/exploitation iteration ...
            monitor.record(
                iteration=i+1,
                coverage=tracker.coverage_ratio,
                newly_selected=new_count,
            )
            if monitor.should_stop:
                break
    """

    def __init__(self, config: ConvergenceConfig | None = None) -> None:
        self._config = config or ConvergenceConfig()
        self._history: list[ConvergenceSnapshot] = []
        self._cumulative_selected = 0
        self._plateau_detected_at: int | None = None

    @property
    def config(self) -> ConvergenceConfig:
        """Return the monitor configuration."""
        return self._config

    @property
    def iteration_count(self) -> int:
        """Number of iterations recorded."""
        return len(self._history)

    @property
    def current_coverage(self) -> float:
        """Current coverage ratio (0.0 if no iterations)."""
        if not self._history:
            return 0.0
        return self._history[-1].coverage

    @property
    def has_converged(self) -> bool:
        """Whether target coverage has been reached."""
        return self.current_coverage >= self._config.target_coverage

    @property
    def has_plateaued(self) -> bool:
        """Whether a plateau has been detected."""
        return self._plateau_detected_at is not None

    @property
    def should_stop(self) -> bool:
        """Whether early stopping is recommended.

        Stops if:
        - Target coverage reached (converged)
        - Plateau detected (no meaningful progress)
        - Max iterations exceeded
        """
        if self.has_converged:
            return True
        if self.has_plateaued:
            return True
        if self.iteration_count >= self._config.max_iterations:
            return True
        return False

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        iteration: int,
        coverage: float,
        newly_selected: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ConvergenceSnapshot:
        """Record a single iteration's convergence data.

        Args:
            iteration: Iteration number (1-based).
            coverage: Current coverage ratio (0.0 to 1.0).
            newly_selected: Number of new features selected this iteration.
            metadata: Optional extra data for this iteration.

        Returns:
            The recorded ConvergenceSnapshot.

        Raises:
            ValueError: If iteration number is invalid or coverage out of range.
        """
        if iteration < 1:
            raise ValueError("iteration must be >= 1")
        if coverage < 0.0 or coverage > 1.0:
            raise ValueError(f"coverage must be in [0.0, 1.0], got {coverage}")
        if newly_selected < 0:
            raise ValueError("newly_selected must be >= 0")

        # Compute delta
        prev_coverage = (
            self._history[-1].coverage if self._history else 0.0
        )
        delta = coverage - prev_coverage

        # Update cumulative
        self._cumulative_selected += newly_selected

        # Check plateau
        is_plateau = self._check_plateau(coverage)

        snapshot = ConvergenceSnapshot(
            iteration=iteration,
            coverage=coverage,
            coverage_delta=delta,
            newly_selected=newly_selected,
            cumulative_selected=self._cumulative_selected,
            is_plateau=is_plateau,
            metadata=metadata or {},
        )

        self._history.append(snapshot)

        logger.debug(
            "Convergence iter=%d, coverage=%.3f (Δ%.3f), "
            "selected=%d, plateau=%s",
            iteration,
            coverage,
            delta,
            newly_selected,
            is_plateau,
        )

        return snapshot

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_summary(self) -> ConvergenceSummary:
        """Compute a convergence summary over all recorded iterations.

        Returns:
            A ConvergenceSummary.
        """
        if not self._history:
            return ConvergenceSummary(
                total_iterations=0,
                final_coverage=0.0,
            )

        deltas = [s.coverage_delta for s in self._history]
        max_delta = max(deltas) if deltas else 0.0

        # Check early target
        met_early = False
        early_iter = self._config.early_target_iteration
        for s in self._history:
            if s.iteration <= early_iter and s.coverage >= self._config.early_coverage_target:
                met_early = True
                break

        return ConvergenceSummary(
            total_iterations=len(self._history),
            final_coverage=self._history[-1].coverage,
            has_converged=self.has_converged,
            has_plateaued=self.has_plateaued,
            plateau_detected_at=self._plateau_detected_at,
            met_early_target=met_early,
            max_coverage_delta=max_delta,
            history=list(self._history),
        )

    def get_coverage_history(self) -> list[tuple[int, float]]:
        """Return iteration-coverage pairs for visualization.

        Returns:
            List of (iteration, coverage) tuples.
        """
        return [(s.iteration, s.coverage) for s in self._history]

    def get_progress_rate(self, window: int = 5) -> float:
        """Compute the average coverage increase over recent iterations.

        Args:
            window: Number of recent iterations to average over.

        Returns:
            Average coverage delta per iteration. 0.0 if insufficient data.
        """
        if len(self._history) < 2:
            return 0.0

        recent = self._history[-window:]
        if len(recent) < 2:
            return recent[-1].coverage_delta if recent else 0.0

        total_delta = recent[-1].coverage - recent[0].coverage
        return total_delta / (len(recent) - 1)

    def estimate_iterations_remaining(self) -> int | None:
        """Estimate how many more iterations to reach target coverage.

        Based on recent progress rate. Returns None if rate is zero
        or coverage is already at target.

        Returns:
            Estimated remaining iterations, or None.
        """
        if self.has_converged:
            return 0

        rate = self.get_progress_rate()
        if rate <= 0.0:
            return None

        remaining_coverage = self._config.target_coverage - self.current_coverage
        estimated = int(remaining_coverage / rate) + 1
        return min(estimated, self._config.max_iterations - self.iteration_count)

    def reset(self) -> None:
        """Reset the monitor to initial state."""
        self._history.clear()
        self._cumulative_selected = 0
        self._plateau_detected_at = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_plateau(self, current_coverage: float) -> bool:
        """Check if current state represents a plateau.

        A plateau is detected when the total coverage increase over the
        last `plateau_window` iterations is below `plateau_threshold`.

        Args:
            current_coverage: The coverage to check.

        Returns:
            True if in plateau.
        """
        window = self._config.plateau_window
        if len(self._history) < window:
            return False

        # Get coverage from `window` iterations ago
        old_coverage = self._history[-window].coverage
        total_increase = current_coverage - old_coverage

        if total_increase < self._config.plateau_threshold:
            if self._plateau_detected_at is None:
                self._plateau_detected_at = len(self._history) + 1
                logger.info(
                    "Plateau detected at iteration %d: "
                    "%.3f increase over %d iterations",
                    self._plateau_detected_at,
                    total_increase,
                    window,
                )
            return True

        return False
