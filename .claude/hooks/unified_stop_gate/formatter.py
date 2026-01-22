"""Decision formatter for unified stop gate hook output."""

from typing import Any, Dict, List

from .evaluator import EvaluationResult


class DecisionFormatter:
    """Formats evaluation results for hook output.

    Produces JSON output matching the existing stop-gate.py format
    for compatibility with Claude Code hooks.
    """

    @staticmethod
    def format(result: EvaluationResult) -> Dict[str, Any]:
        """Format evaluation result as JSON-serializable dict.

        Args:
            result: The evaluation result from PriorityEvaluator.

        Returns:
            Dict matching existing stop-gate.py output format:
            - BLOCK: {"decision": "block", "reason": "...", "blocking_checks": [...], "warnings": [...]}
            - PASS/WARN/ALLOW: {"decision": "approve", "reason": "...", "warnings": [...]}
        """
        # Format warnings list
        warnings: List[Dict[str, str]] = [
            {
                "priority": check.priority.name,
                "message": check.message,
            }
            for check in result.warnings
        ]

        if result.decision == "BLOCK":
            # Format blocking checks list
            blocking_checks: List[Dict[str, str]] = [
                {
                    "priority": check.priority.name,
                    "message": check.message,
                }
                for check in result.blocking_checks
            ]

            # Build reason from highest priority blocker
            if result.priority_breaker:
                primary_blocker = next(
                    (c for c in result.blocking_checks if c.priority == result.priority_breaker),
                    None
                )
                reason = primary_blocker.message if primary_blocker else "Blocked by priority check"
            else:
                reason = "Blocked by priority check"

            return {
                "decision": "block",
                "reason": reason,
                "blocking_checks": blocking_checks,
                "warnings": warnings,
            }

        # PASS, WARN, or ALLOW all result in "approve"
        if result.decision == "ALLOW":
            reason = "Circuit breaker triggered - forcing approval"
        elif result.decision == "WARN":
            reason = f"Approved with {len(warnings)} warning(s)"
        else:  # PASS
            reason = "All checks passed"

        return {
            "decision": "approve",
            "reason": reason,
            "warnings": warnings,
        }

    @staticmethod
    def format_error(error: Exception) -> Dict[str, Any]:
        """Format an error as JSON-serializable dict.

        Args:
            error: The exception that occurred.

        Returns:
            Dict with error information, approving to avoid blocking on errors.
        """
        return {
            "decision": "approve",
            "reason": f"Error in stop gate evaluation: {error}",
            "warnings": [
                {
                    "priority": "ERROR",
                    "message": str(error),
                }
            ],
        }
