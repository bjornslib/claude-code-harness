"""Enrichment-specific helper models for the RPG enrichment pipeline.

These models support the encoder pipeline with validation results,
step metadata, and enrichment configuration.  They do NOT duplicate
RPGNode/RPGEdge from ``zerorepo.models``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    """Result of an RPGEncoder.validate() call.

    Attributes:
        passed: Whether validation passed with no errors.
        errors: List of error messages that caused validation failure.
        warnings: List of non-blocking warnings.
    """

    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Enforce consistency: passed must be False if there are errors."""
        if self.errors and self.passed:
            object.__setattr__(self, "passed", False)


@dataclass(frozen=True)
class EncoderStep:
    """Metadata for a single encoder execution within the pipeline.

    Attributes:
        encoder_name: The name of the encoder class.
        started_at: UTC timestamp when the step started.
        finished_at: UTC timestamp when the step finished (None if in progress).
        duration_ms: Duration of the step in milliseconds.
        nodes_modified: Number of nodes modified by this step.
        validation: Validation result for this step (None if not yet validated).
        metadata: Additional step-specific metadata.
    """

    encoder_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    duration_ms: float = 0.0
    nodes_modified: int = 0
    validation: ValidationResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_finish(
        self,
        finished_at: datetime,
        duration_ms: float,
        nodes_modified: int = 0,
        validation: ValidationResult | None = None,
    ) -> EncoderStep:
        """Return a new EncoderStep with completion data filled in.

        Since EncoderStep is frozen, this creates a new instance with
        the specified finish-time fields populated.

        Args:
            finished_at: When the step completed (UTC).
            duration_ms: How long the step took in milliseconds.
            nodes_modified: Count of nodes that were modified.
            validation: Optional validation result.

        Returns:
            A new EncoderStep with the completion data.
        """
        return EncoderStep(
            encoder_name=self.encoder_name,
            started_at=self.started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            nodes_modified=nodes_modified,
            validation=validation,
            metadata=self.metadata,
        )
