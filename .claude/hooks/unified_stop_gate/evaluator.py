"""Priority evaluator for unified stop gate hook."""

from dataclasses import dataclass, field
from typing import List, Optional

from .checkers import (
    BeadsSyncChecker,
    BusinessOutcomeChecker,
    CompletionPromiseChecker,
    GitStatusChecker,
    MaxIterationsChecker,
    SessionInfo,
    TodoContinuationChecker,
)
from .communicator_checker import CommunicatorActiveChecker
from .config import CheckResult, EnvironmentConfig, PathResolver, Priority


@dataclass
class EvaluationResult:
    """Result of evaluating all priority checks.

    Attributes:
        decision: Final decision - 'ALLOW', 'BLOCK', 'WARN', or 'PASS'
        priority_breaker: Which priority caused the decision (if any)
        results: All check results in priority order
        blocking_checks: Failed checks that are blocking
        warnings: Failed checks that are non-blocking (advisory)
    """

    decision: str  # 'ALLOW' | 'BLOCK' | 'WARN' | 'PASS'
    priority_breaker: Optional[Priority]
    results: List[CheckResult] = field(default_factory=list)
    blocking_checks: List[CheckResult] = field(default_factory=list)
    warnings: List[CheckResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """Generate a human-readable summary of the evaluation."""
        lines = [f"Decision: {self.decision}"]
        if self.priority_breaker is not None:
            lines.append(f"Determined by: {self.priority_breaker.name}")
        if self.blocking_checks:
            lines.append(f"Blocking issues: {len(self.blocking_checks)}")
            for check in self.blocking_checks:
                lines.append(f"  - [{check.priority.name}] {check.message}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
            for check in self.warnings:
                lines.append(f"  - [{check.priority.name}] {check.message}")
        return "\n".join(lines)


class PriorityEvaluator:
    """Orchestrates all checkers and evaluates by priority.

    Runs all checkers (P0-P5) in priority order and determines
    the final decision based on:
    - P0 circuit breaker forces ALLOW if triggered
    - Highest-priority blocking failure causes BLOCK
    - Non-blocking failures cause WARN
    - All passed causes PASS
    """

    def __init__(self, config: EnvironmentConfig, session: SessionInfo):
        """Initialize the evaluator.

        Args:
            config: Environment configuration.
            session: Session information from hook input.
        """
        self.config = config
        self.session = session
        self.paths = PathResolver(config)

    def evaluate(self) -> EvaluationResult:
        """Run all checkers and evaluate results by priority.

        Returns:
            EvaluationResult with final decision and all check details.
        """
        results: List[CheckResult] = []
        blocking_checks: List[CheckResult] = []
        warnings: List[CheckResult] = []

        # P0: Circuit Breaker
        p0_result = MaxIterationsChecker(self.config, self.session).check()
        results.append(p0_result)

        # If circuit breaker triggers (passed=True), force ALLOW immediately
        if p0_result.passed:
            return EvaluationResult(
                decision='ALLOW',
                priority_breaker=Priority.P0_CIRCUIT_BREAKER,
                results=results,
                blocking_checks=[],
                warnings=[],
            )

        # P1: Completion Promise (only if enforced)
        if self.config.enforce_promise:
            p1_result = CompletionPromiseChecker(self.config, self.paths).check()
            results.append(p1_result)
            if not p1_result.passed:
                if p1_result.blocking:
                    blocking_checks.append(p1_result)
                else:
                    warnings.append(p1_result)

        # P1.5: Communicator Active (System 3 only)
        p1_5_result = CommunicatorActiveChecker(self.config).check()
        results.append(p1_5_result)
        if not p1_5_result.passed:
            if p1_5_result.blocking:
                blocking_checks.append(p1_5_result)
            else:
                warnings.append(p1_5_result)

        # P2: Beads Sync
        p2_result = BeadsSyncChecker(self.config).check()
        results.append(p2_result)
        if not p2_result.passed:
            if p2_result.blocking:
                blocking_checks.append(p2_result)
            else:
                warnings.append(p2_result)

        # P3: Todo Continuation
        p3_result = TodoContinuationChecker(self.config, self.session).check()
        results.append(p3_result)
        if not p3_result.passed:
            if p3_result.blocking:
                blocking_checks.append(p3_result)
            else:
                warnings.append(p3_result)

        # P4: Git Status (advisory, non-blocking)
        p4_result = GitStatusChecker(self.config).check()
        results.append(p4_result)
        if not p4_result.passed:
            # P4 is always non-blocking (advisory)
            warnings.append(p4_result)

        # P5: Business Outcomes (only if enforced)
        p5_result = BusinessOutcomeChecker(self.config).check()
        results.append(p5_result)
        if not p5_result.passed:
            if p5_result.blocking:
                blocking_checks.append(p5_result)
            else:
                warnings.append(p5_result)

        # Determine final decision
        if blocking_checks:
            # Find highest priority blocking failure
            highest_priority_blocker = min(
                blocking_checks, key=lambda r: r.priority
            )
            return EvaluationResult(
                decision='BLOCK',
                priority_breaker=highest_priority_blocker.priority,
                results=results,
                blocking_checks=blocking_checks,
                warnings=warnings,
            )

        if warnings:
            # Only non-blocking failures
            highest_priority_warning = min(warnings, key=lambda r: r.priority)
            return EvaluationResult(
                decision='WARN',
                priority_breaker=highest_priority_warning.priority,
                results=results,
                blocking_checks=[],
                warnings=warnings,
            )

        # All checks passed
        return EvaluationResult(
            decision='PASS',
            priority_breaker=None,
            results=results,
            blocking_checks=[],
            warnings=[],
        )
