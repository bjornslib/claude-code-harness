"""RPGBuilder – sequential encoder pipeline for RPG enrichment.

The builder accepts a list of :class:`RPGEncoder` instances, executes
them in order on an :class:`RPGGraph`, and collects timing / validation
metadata for each step.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import EncoderStep, ValidationResult

logger = logging.getLogger(__name__)


class RPGBuilder:
    """Sequential pipeline that chains :class:`RPGEncoder` stages.

    Each encoder is executed in the order it was registered.  After
    each step the builder optionally runs validation and logs timing
    information via the standard :mod:`logging` library.

    Example::

        builder = RPGBuilder()
        builder.add_encoder(TypeInferenceEncoder())
        builder.add_encoder(SignatureEncoder())
        result_graph = builder.run(graph)

        for step in builder.steps:
            print(f"{step.encoder_name}: {step.duration_ms:.1f}ms")
    """

    def __init__(self, *, validate_after_each: bool = True) -> None:
        """Initialise the builder.

        Args:
            validate_after_each: If ``True`` (default), run each encoder's
                :meth:`validate` method after its :meth:`encode` call and
                record the result in the step metadata.
        """
        self._encoders: list[RPGEncoder] = []
        self._steps: list[EncoderStep] = []
        self._validate_after_each = validate_after_each

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_encoder(self, encoder: RPGEncoder) -> RPGBuilder:
        """Append an encoder to the pipeline.

        Args:
            encoder: An :class:`RPGEncoder` instance.

        Returns:
            ``self`` for fluent chaining.

        Raises:
            TypeError: If *encoder* is not an :class:`RPGEncoder`.
        """
        if not isinstance(encoder, RPGEncoder):
            raise TypeError(
                f"Expected RPGEncoder instance, got {type(encoder).__name__}"
            )
        self._encoders.append(encoder)
        return self

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def encoders(self) -> list[RPGEncoder]:
        """Return a copy of the registered encoders."""
        return list(self._encoders)

    @property
    def steps(self) -> list[EncoderStep]:
        """Return a copy of the recorded execution steps."""
        return list(self._steps)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        """Execute the full pipeline on *graph*.

        Runs each encoder sequentially, recording timing and (optionally)
        validation results for every step.

        Args:
            graph: The :class:`RPGGraph` to enrich.
            spec: Optional parsed :class:`RepositorySpec` to pass through
                to each encoder for context-aware enrichment.

        Returns:
            The enriched graph (same instance, mutated in-place by the
            encoders).
        """
        self._steps.clear()

        if not self._encoders:
            logger.warning("RPGBuilder.run() called with no encoders registered")
            return graph

        logger.info(
            "Starting RPG enrichment pipeline with %d encoder(s)",
            len(self._encoders),
        )

        for encoder in self._encoders:
            step = self._run_encoder(encoder, graph, spec=spec)
            self._steps.append(step)

        logger.info(
            "RPG enrichment pipeline completed: %d step(s), total %.1f ms",
            len(self._steps),
            sum(s.duration_ms for s in self._steps),
        )

        return graph

    def validate_all(self, graph: RPGGraph) -> ValidationResult:
        """Run all encoder validations and aggregate results.

        This runs every registered encoder's :meth:`validate` method
        and merges the errors and warnings into a single result.

        Args:
            graph: The :class:`RPGGraph` to validate.

        Returns:
            An aggregated :class:`ValidationResult`.
        """
        all_errors: list[str] = []
        all_warnings: list[str] = []

        for encoder in self._encoders:
            result = encoder.validate(graph)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        return ValidationResult(
            passed=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_encoder(
        self,
        encoder: RPGEncoder,
        graph: RPGGraph,
        spec: Any | None = None,
    ) -> EncoderStep:
        """Execute a single encoder and record its step metadata."""
        encoder_name = encoder.name
        logger.info("Running encoder: %s", encoder_name)

        node_count_before = graph.node_count
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        graph = encoder.encode(graph, spec=spec)

        t1 = time.perf_counter()
        duration_ms = (t1 - t0) * 1000
        finished_at = datetime.now(timezone.utc)

        nodes_modified = abs(graph.node_count - node_count_before)

        validation: ValidationResult | None = None
        if self._validate_after_each:
            validation = encoder.validate(graph)
            if not validation.passed:
                logger.warning(
                    "Encoder %s validation failed: %s",
                    encoder_name,
                    validation.errors,
                )
            else:
                logger.debug("Encoder %s validation passed", encoder_name)

        step = EncoderStep(
            encoder_name=encoder_name,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            nodes_modified=nodes_modified,
            validation=validation,
        )

        logger.info(
            "Encoder %s completed in %.1f ms",
            encoder_name,
            duration_ms,
        )

        return step
