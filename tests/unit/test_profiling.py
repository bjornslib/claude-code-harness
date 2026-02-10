"""Unit tests for the ProfilingCollector class.

Tests cover:
- Recording LLM calls (token usage)
- Context-manager stage timing
- Manual start/stop timers
- Stage summary generation
- Data retrieval and reset
- Multiple calls accumulate
"""

from __future__ import annotations

import time

import pytest

from zerorepo.evaluation.models import ProfilingData, TokenStats
from zerorepo.evaluation.profiling import ProfilingCollector


# ---------------------------------------------------------------------------
# Token recording
# ---------------------------------------------------------------------------


class TestRecordLlmCall:
    """Tests for record_llm_call()."""

    def test_single_call(self) -> None:
        """Single LLM call should record token counts."""
        collector = ProfilingCollector()
        collector.record_llm_call("validation", prompt_tokens=100, completion_tokens=50)

        data = collector.get_profiling_data()
        stats = data.stage_tokens["validation"]
        assert stats.prompt_tokens == 100
        assert stats.completion_tokens == 50
        assert stats.total_calls == 1

    def test_multiple_calls_accumulate(self) -> None:
        """Multiple calls to same stage should accumulate."""
        collector = ProfilingCollector()
        collector.record_llm_call("validation", prompt_tokens=100, completion_tokens=50)
        collector.record_llm_call("validation", prompt_tokens=200, completion_tokens=75)

        data = collector.get_profiling_data()
        stats = data.stage_tokens["validation"]
        assert stats.prompt_tokens == 300
        assert stats.completion_tokens == 125
        assert stats.total_calls == 2

    def test_different_stages(self) -> None:
        """Different stages should track independently."""
        collector = ProfilingCollector()
        collector.record_llm_call("validation", prompt_tokens=100, completion_tokens=50)
        collector.record_llm_call("localization", prompt_tokens=200, completion_tokens=75)

        data = collector.get_profiling_data()
        assert "validation" in data.stage_tokens
        assert "localization" in data.stage_tokens
        assert data.stage_tokens["validation"].prompt_tokens == 100
        assert data.stage_tokens["localization"].prompt_tokens == 200

    def test_total_tokens_computed(self) -> None:
        """TokenStats.total_tokens should be prompt + completion."""
        collector = ProfilingCollector()
        collector.record_llm_call("test", prompt_tokens=100, completion_tokens=50)

        stats = collector.get_profiling_data().stage_tokens["test"]
        assert stats.total_tokens == 150


# ---------------------------------------------------------------------------
# Context-manager timing
# ---------------------------------------------------------------------------


class TestTimeStage:
    """Tests for time_stage() context manager."""

    def test_records_timing(self) -> None:
        """time_stage should record elapsed time."""
        collector = ProfilingCollector()
        with collector.time_stage("validation"):
            time.sleep(0.01)

        data = collector.get_profiling_data()
        assert "validation" in data.stage_timings
        assert data.stage_timings["validation"] >= 0.01

    def test_accumulates_timing(self) -> None:
        """Multiple timed blocks for same stage should accumulate."""
        collector = ProfilingCollector()
        with collector.time_stage("validation"):
            time.sleep(0.01)
        with collector.time_stage("validation"):
            time.sleep(0.01)

        data = collector.get_profiling_data()
        assert data.stage_timings["validation"] >= 0.02

    def test_updates_total_duration(self) -> None:
        """total_duration_s should be updated."""
        collector = ProfilingCollector()
        with collector.time_stage("test"):
            time.sleep(0.01)

        data = collector.get_profiling_data()
        assert data.total_duration_s >= 0.01

    def test_exception_still_records(self) -> None:
        """Timing should still be recorded if an exception occurs."""
        collector = ProfilingCollector()
        with pytest.raises(ValueError):
            with collector.time_stage("test"):
                time.sleep(0.01)
                raise ValueError("test error")

        data = collector.get_profiling_data()
        assert data.stage_timings["test"] >= 0.01


# ---------------------------------------------------------------------------
# Manual start/stop timers
# ---------------------------------------------------------------------------


class TestManualTimers:
    """Tests for start_timer() and stop_timer()."""

    def test_basic_timer(self) -> None:
        """Manual start/stop should record elapsed time."""
        collector = ProfilingCollector()
        collector.start_timer("test")
        time.sleep(0.01)
        elapsed = collector.stop_timer("test")

        assert elapsed >= 0.01
        data = collector.get_profiling_data()
        assert data.stage_timings["test"] >= 0.01

    def test_stop_nonexistent_timer(self) -> None:
        """Stopping a non-existent timer should return 0.0."""
        collector = ProfilingCollector()
        elapsed = collector.stop_timer("nonexistent")
        assert elapsed == 0.0

    def test_timer_removed_after_stop(self) -> None:
        """Active timer should be removed after stop."""
        collector = ProfilingCollector()
        collector.start_timer("test")
        collector.stop_timer("test")
        # Second stop should return 0.0
        elapsed = collector.stop_timer("test")
        assert elapsed == 0.0


# ---------------------------------------------------------------------------
# Stage summary
# ---------------------------------------------------------------------------


class TestGetStageSummary:
    """Tests for get_stage_summary()."""

    def test_with_data(self) -> None:
        """Summary should include token and timing data."""
        collector = ProfilingCollector()
        collector.record_llm_call("validation", prompt_tokens=100, completion_tokens=50)
        with collector.time_stage("validation"):
            pass

        summary = collector.get_stage_summary("validation")
        assert summary["stage"] == "validation"
        assert summary["prompt_tokens"] == 100
        assert summary["completion_tokens"] == 50
        assert summary["total_tokens"] == 150
        assert summary["total_calls"] == 1
        assert summary["duration_s"] >= 0.0

    def test_empty_stage(self) -> None:
        """Summary for unknown stage should return zeroes."""
        collector = ProfilingCollector()
        summary = collector.get_stage_summary("nonexistent")
        assert summary["prompt_tokens"] == 0
        assert summary["completion_tokens"] == 0
        assert summary["total_calls"] == 0
        assert summary["duration_s"] == 0.0


# ---------------------------------------------------------------------------
# Data retrieval and reset
# ---------------------------------------------------------------------------


class TestDataRetrieval:
    """Tests for get_profiling_data() and reset()."""

    def test_returns_profiling_data(self) -> None:
        """Should return a ProfilingData instance."""
        collector = ProfilingCollector()
        data = collector.get_profiling_data()
        assert isinstance(data, ProfilingData)

    def test_deep_copy(self) -> None:
        """Returned data should be a deep copy (modifying it doesn't affect collector)."""
        collector = ProfilingCollector()
        collector.record_llm_call("test", prompt_tokens=100, completion_tokens=50)

        data = collector.get_profiling_data()
        data.stage_tokens["test"].prompt_tokens = 999

        fresh = collector.get_profiling_data()
        assert fresh.stage_tokens["test"].prompt_tokens == 100

    def test_reset_clears_data(self) -> None:
        """Reset should clear all collected data."""
        collector = ProfilingCollector()
        collector.record_llm_call("test", prompt_tokens=100, completion_tokens=50)
        collector.start_timer("active")

        collector.reset()
        data = collector.get_profiling_data()
        assert len(data.stage_tokens) == 0
        assert len(data.stage_timings) == 0
        assert data.total_duration_s == 0.0

    def test_reset_clears_active_timers(self) -> None:
        """Reset should clear active timers too."""
        collector = ProfilingCollector()
        collector.start_timer("test")
        collector.reset()
        # stop_timer should return 0.0 because timer was cleared
        assert collector.stop_timer("test") == 0.0
