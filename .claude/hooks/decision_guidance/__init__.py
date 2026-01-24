"""Decision-time guidance system for Claude Code harness.

Adapts Replit's decision-time guidance approach:
- Selective injection of guidance at decision points
- Lightweight signal tracking (error patterns, doom loops)
- Ephemeral reminders that don't persist in context
- Goal-aware validation against System3 instructions
"""

from .state_manager import ErrorTracker, EditHistory
from .classifier import SignalClassifier
from .guidance_bank import GuidanceBank
from .goal_validator import GoalValidator, ValidationResult, CompletionState

__all__ = [
    "ErrorTracker",
    "EditHistory",
    "SignalClassifier",
    "GuidanceBank",
    "GoalValidator",
    "ValidationResult",
    "CompletionState",
]
