"""Outcome model for handler execution results.

Every Handler.execute() call returns an Outcome.  The engine uses the
outcome to update PipelineContext and select the next edge via EdgeSelector.

Design notes:
- Frozen dataclass (not Pydantic) because Outcome is an in-memory value
  object — immutable after construction, no serialisation needed directly.
  The runner serialises via NodeRecord (Pydantic) which copies relevant fields.
- ``raw_messages`` is an extension point (AMD-7) for CodergenHandler (SDK
  dispatch) to pass raw LLM messages to TokenCountingMiddleware in Epic 4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutcomeStatus(str, Enum):
    """Normalised execution result for a single node.

    Values are lower-case strings so that simple equality conditions in DOT
    edge attributes can be evaluated without case conversion::

        edge.condition = "outcome = success"
    """

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    WAITING = "waiting"    # WaitHumanHandler: human approval pending
    SKIPPED = "skipped"    # StartHandler: no-op node


@dataclass(frozen=True)
class Outcome:
    """Immutable result returned by every Handler.execute() call.

    Attributes:
        status:          Normalised execution result (see OutcomeStatus).
        context_updates: Key-value pairs to merge into PipelineContext after
                         this node completes.  Keys beginning with ``$`` are
                         reserved for engine built-ins.
        preferred_label: If set, EdgeSelector Step 2 preferentially matches
                         an outgoing edge whose ``label`` equals this value.
        suggested_next:  If set, EdgeSelector Step 3 preferentially routes
                         to the outgoing edge whose ``target`` equals this node ID.
        metadata:        Arbitrary per-handler data (token counts, exit codes,
                         signal names, etc.) stored in checkpoint for
                         observability but not used for routing.
        raw_messages:    Populated by CodergenHandler (SDK dispatch) with raw
                         LLM response messages.  Read by TokenCountingMiddleware
                         (Epic 4) for token usage accounting.  Empty for all
                         non-LLM handlers.  Reserved extension point — AMD-7.
    """

    status: OutcomeStatus
    context_updates: dict[str, Any] = field(default_factory=dict)
    preferred_label: str | None = None
    suggested_next: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_messages: list[Any] = field(default_factory=list)
