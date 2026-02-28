"""Pipeline event type definitions and factory class.

This module is the canonical source for all PipelineEvent types. It has no
runtime dependencies beyond the standard library — everything else in the
event bus imports from here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Event type alias — exactly 14 string literals
# ---------------------------------------------------------------------------

EventType = Literal[
    "pipeline.started",
    "pipeline.completed",
    "pipeline.failed",
    "pipeline.resumed",
    "node.started",
    "node.completed",
    "node.failed",
    "edge.selected",
    "checkpoint.saved",
    "context.updated",
    "retry.triggered",
    "loop.detected",
    "validation.started",
    "validation.completed",
]

# Frozenset used for runtime membership checks without importing typing internals.
_ALL_EVENT_TYPES: frozenset[str] = frozenset([
    "pipeline.started",
    "pipeline.completed",
    "pipeline.failed",
    "pipeline.resumed",
    "node.started",
    "node.completed",
    "node.failed",
    "edge.selected",
    "checkpoint.saved",
    "context.updated",
    "retry.triggered",
    "loop.detected",
    "validation.started",
    "validation.completed",
])


# ---------------------------------------------------------------------------
# PipelineEvent — immutable, slotted for minimal overhead
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """An immutable record of a single lifecycle event in a pipeline run.

    ``type`` is one of the 14 canonical event type strings defined in
    ``EventType``.  ``data`` carries event-type-specific payload fields.
    ``sequence`` is a process-global monotonic counter assigned by
    ``EventBuilder._build()`` — it is NOT reset between pipeline runs in the
    same process.
    """

    type: EventType
    timestamp: datetime        # Always timezone-aware UTC
    pipeline_id: str           # DOT graph identifier
    node_id: str | None        # None for pipeline-level events
    data: dict[str, Any]       # Event-type-specific payload
    span_id: str | None = None # Logfire span ID for correlation
    sequence: int = 0          # Monotonic counter per process


# ---------------------------------------------------------------------------
# SpanConfig — configuration for Logfire span naming and attribute mapping
# ---------------------------------------------------------------------------

@dataclass
class SpanConfig:
    """Configuration for Logfire span naming and attribute mapping."""

    pipeline_span_name: str = "pipeline.{pipeline_id}"
    node_span_name: str = "node.{node_id}"
    # Attributes set on the pipeline-level span
    pipeline_attrs: tuple[str, ...] = (
        "pipeline_id", "dot_path", "node_count", "resume"
    )
    # Attributes set on each node-level span
    node_attrs: tuple[str, ...] = (
        "node_id", "handler_type", "visit_count",
        "outcome_status", "duration_ms", "tokens_used", "goal_gate",
    )


# ---------------------------------------------------------------------------
# EventBuilder — centralised factory for all 14 event types
# ---------------------------------------------------------------------------

class EventBuilder:
    """Factory methods that produce valid PipelineEvent instances.

    Centralises event schema knowledge.  Call sites in runner.py and
    middleware modules use these methods rather than constructing
    PipelineEvent directly.

    ``_counter`` is a class-level monotonic integer; it increments on every
    call to ``_build()`` and is never reset within a process lifetime.
    """

    _counter: int = 0

    @classmethod
    def _build(
        cls,
        event_type: EventType,
        pipeline_id: str,
        node_id: str | None,
        data: dict[str, Any],
        span_id: str | None = None,
    ) -> PipelineEvent:
        """Construct a PipelineEvent with an auto-incremented sequence number."""
        cls._counter += 1
        return PipelineEvent(
            type=event_type,
            timestamp=datetime.now(timezone.utc),
            pipeline_id=pipeline_id,
            node_id=node_id,
            data=data,
            span_id=span_id,
            sequence=cls._counter,
        )

    # ------------------------------------------------------------------
    # Pipeline-level events
    # ------------------------------------------------------------------

    @classmethod
    def pipeline_started(
        cls,
        pipeline_id: str,
        dot_path: str,
        node_count: int,
    ) -> PipelineEvent:
        """Emit when the execution loop is about to begin."""
        return cls._build(
            "pipeline.started",
            pipeline_id,
            None,
            {"dot_path": dot_path, "node_count": node_count},
        )

    @classmethod
    def pipeline_completed(
        cls,
        pipeline_id: str,
        duration_ms: float,
        total_tokens: int = 0,
    ) -> PipelineEvent:
        """Emit after the exit handler returns successfully."""
        return cls._build(
            "pipeline.completed",
            pipeline_id,
            None,
            {"duration_ms": duration_ms, "total_tokens": total_tokens},
        )

    @classmethod
    def pipeline_failed(
        cls,
        pipeline_id: str,
        error_type: str,
        error_message: str,
        last_node_id: str | None = None,
    ) -> PipelineEvent:
        """Emit on a fatal pipeline error."""
        return cls._build(
            "pipeline.failed",
            pipeline_id,
            None,
            {
                "error_type": error_type,
                "error_message": error_message,
                "last_node_id": last_node_id,
            },
        )

    @classmethod
    def pipeline_resumed(
        cls,
        pipeline_id: str,
        checkpoint_path: str,
        completed_node_count: int,
    ) -> PipelineEvent:
        """Emit when execution resumes from a checkpoint."""
        return cls._build(
            "pipeline.resumed",
            pipeline_id,
            None,
            {
                "checkpoint_path": checkpoint_path,
                "completed_node_count": completed_node_count,
            },
        )

    # ------------------------------------------------------------------
    # Node-level events
    # ------------------------------------------------------------------

    @classmethod
    def node_started(
        cls,
        pipeline_id: str,
        node_id: str,
        handler_type: str,
        visit_count: int,
    ) -> PipelineEvent:
        """Emit before a node handler is invoked."""
        return cls._build(
            "node.started",
            pipeline_id,
            node_id,
            {"handler_type": handler_type, "visit_count": visit_count},
        )

    @classmethod
    def node_completed(
        cls,
        pipeline_id: str,
        node_id: str,
        outcome_status: str,
        duration_ms: float,
        tokens_used: int = 0,
        span_id: str | None = None,
    ) -> PipelineEvent:
        """Emit after a node handler returns a successful outcome."""
        return cls._build(
            "node.completed",
            pipeline_id,
            node_id,
            {
                "outcome_status": outcome_status,
                "duration_ms": duration_ms,
                "tokens_used": tokens_used,
            },
            span_id=span_id,
        )

    @classmethod
    def node_failed(
        cls,
        pipeline_id: str,
        node_id: str,
        error_type: str,
        goal_gate: bool = False,
        retry_target: str | None = None,
    ) -> PipelineEvent:
        """Emit when a node handler returns FAILURE."""
        return cls._build(
            "node.failed",
            pipeline_id,
            node_id,
            {
                "error_type": error_type,
                "goal_gate": goal_gate,
                "retry_target": retry_target,
            },
        )

    # ------------------------------------------------------------------
    # Edge / routing events
    # ------------------------------------------------------------------

    @classmethod
    def edge_selected(
        cls,
        pipeline_id: str,
        from_node_id: str,
        to_node_id: str,
        selection_step: int,
        condition: str | None = None,
    ) -> PipelineEvent:
        """Emit after the edge selector determines the next node."""
        return cls._build(
            "edge.selected",
            pipeline_id,
            from_node_id,
            {
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "selection_step": selection_step,
                "condition": condition,
            },
        )

    # ------------------------------------------------------------------
    # Checkpoint events
    # ------------------------------------------------------------------

    @classmethod
    def checkpoint_saved(
        cls,
        pipeline_id: str,
        node_id: str,
        checkpoint_path: str,
    ) -> PipelineEvent:
        """Emit after a checkpoint is atomically written."""
        return cls._build(
            "checkpoint.saved",
            pipeline_id,
            node_id,
            {
                "pipeline_id": pipeline_id,
                "checkpoint_path": checkpoint_path,
                "node_id": node_id,
            },
        )

    # ------------------------------------------------------------------
    # Context events
    # ------------------------------------------------------------------

    @classmethod
    def context_updated(
        cls,
        pipeline_id: str,
        node_id: str,
        keys_added: list[str],
        keys_modified: list[str],
    ) -> PipelineEvent:
        """Emit once per completed node after merging outcome.context_updates."""
        return cls._build(
            "context.updated",
            pipeline_id,
            node_id,
            {
                "pipeline_id": pipeline_id,
                "node_id": node_id,
                "keys_added": keys_added,
                "keys_modified": keys_modified,
            },
        )

    # ------------------------------------------------------------------
    # Retry events
    # ------------------------------------------------------------------

    @classmethod
    def retry_triggered(
        cls,
        pipeline_id: str,
        node_id: str,
        attempt_number: int,
        backoff_ms: float,
        error_type: str,
    ) -> PipelineEvent:
        """Emit before a retry attempt is made."""
        return cls._build(
            "retry.triggered",
            pipeline_id,
            node_id,
            {
                "attempt_number": attempt_number,
                "backoff_ms": backoff_ms,
                "error_type": error_type,
            },
        )

    # ------------------------------------------------------------------
    # Loop detection events
    # ------------------------------------------------------------------

    @classmethod
    def loop_detected(
        cls,
        pipeline_id: str,
        node_id: str,
        visit_count: int,
        limit: int,
        pattern_detected: str | None = None,
    ) -> PipelineEvent:
        """Emit when a node visit limit is exceeded."""
        return cls._build(
            "loop.detected",
            pipeline_id,
            node_id,
            {
                "visit_count": visit_count,
                "limit": limit,
                "pattern_detected": pattern_detected,
            },
        )

    # ------------------------------------------------------------------
    # Validation events
    # ------------------------------------------------------------------

    @classmethod
    def validation_started(
        cls,
        pipeline_id: str,
        rule_count: int,
    ) -> PipelineEvent:
        """Emit when validation begins."""
        return cls._build(
            "validation.started",
            pipeline_id,
            None,
            {"pipeline_id": pipeline_id, "rule_count": rule_count},
        )

    @classmethod
    def validation_completed(
        cls,
        pipeline_id: str,
        errors: list[str],
        warnings: list[str],
        passed: bool,
    ) -> PipelineEvent:
        """Emit when validation finishes."""
        return cls._build(
            "validation.completed",
            pipeline_id,
            None,
            {
                "pipeline_id": pipeline_id,
                "errors": errors,
                "warnings": warnings,
                "passed": passed,
            },
        )
