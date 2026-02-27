"""Profiling and cost tracking for the evaluation pipeline.

Instruments LLM calls and pipeline stages for token usage and timing.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

from cobuilder.repomap.evaluation.models import ProfilingData, TokenStats

logger = logging.getLogger(__name__)


class ProfilingCollector:
    """Collects token usage and timing data across pipeline stages."""

    def __init__(self) -> None:
        self._data = ProfilingData()
        self._active_timers: dict[str, float] = {}

    def record_llm_call(
        self,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record token usage for an LLM call."""
        if stage not in self._data.stage_tokens:
            self._data.stage_tokens[stage] = TokenStats()

        stats = self._data.stage_tokens[stage]
        stats.prompt_tokens += prompt_tokens
        stats.completion_tokens += completion_tokens
        stats.total_calls += 1

    @contextmanager
    def time_stage(self, stage: str) -> Generator[None, None, None]:
        """Context manager to time a pipeline stage."""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            self._data.stage_timings[stage] = (
                self._data.stage_timings.get(stage, 0.0) + elapsed
            )
            self._data.total_duration_s += elapsed

    def start_timer(self, stage: str) -> None:
        """Manually start a timer for a stage."""
        self._active_timers[stage] = time.monotonic()

    def stop_timer(self, stage: str) -> float:
        """Stop a timer and record the elapsed time. Returns seconds."""
        if stage not in self._active_timers:
            logger.warning(f"No active timer for stage: {stage}")
            return 0.0

        elapsed = time.monotonic() - self._active_timers.pop(stage)
        self._data.stage_timings[stage] = (
            self._data.stage_timings.get(stage, 0.0) + elapsed
        )
        self._data.total_duration_s += elapsed
        return elapsed

    def get_stage_summary(self, stage: str) -> dict[str, Any]:
        """Get summary for a specific stage."""
        tokens = self._data.stage_tokens.get(stage, TokenStats())
        timing = self._data.stage_timings.get(stage, 0.0)
        return {
            "stage": stage,
            "prompt_tokens": tokens.prompt_tokens,
            "completion_tokens": tokens.completion_tokens,
            "total_tokens": tokens.total_tokens,
            "total_calls": tokens.total_calls,
            "duration_s": timing,
        }

    def get_profiling_data(self) -> ProfilingData:
        """Return the collected profiling data."""
        return self._data.model_copy(deep=True)

    def reset(self) -> None:
        """Reset all collected data."""
        self._data = ProfilingData()
        self._active_timers.clear()
