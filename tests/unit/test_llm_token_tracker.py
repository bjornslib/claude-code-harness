"""Unit tests for TokenTracker."""

from __future__ import annotations

import pytest

from cobuilder.repomap.llm.token_tracker import TokenTracker


class TestTokenTrackerRecord:
    """Tests for recording token usage."""

    def test_record_single_model(self) -> None:
        """Recording usage for a single model increases totals."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        assert tracker.get_total_tokens() == 150

    def test_record_multiple_calls_same_model(self) -> None:
        """Multiple calls for the same model accumulate."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        tracker.record("gpt-4o-mini", prompt_tokens=200, completion_tokens=100)
        assert tracker.get_total_tokens() == 450

    def test_record_multiple_models(self) -> None:
        """Recording usage for different models tracks separately."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        tracker.record("gpt-4o", prompt_tokens=200, completion_tokens=100)
        assert tracker.get_total_tokens() == 450

    def test_record_zero_tokens(self) -> None:
        """Recording zero tokens doesn't fail."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=0, completion_tokens=0)
        assert tracker.get_total_tokens() == 0

    def test_empty_tracker_totals(self) -> None:
        """Empty tracker returns zero totals."""
        tracker = TokenTracker()
        assert tracker.get_total_tokens() == 0
        assert tracker.get_total_cost() == 0.0


class TestTokenTrackerCost:
    """Tests for cost estimation."""

    def test_cost_gpt4o_mini(self) -> None:
        """Cost calculation for gpt-4o-mini (known pricing)."""
        tracker = TokenTracker()
        # 1M input tokens at $0.15, 1M output at $0.60
        tracker.record("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = tracker.get_total_cost()
        assert abs(cost - 0.75) < 0.01  # $0.15 + $0.60

    def test_cost_gpt4o(self) -> None:
        """Cost calculation for gpt-4o (known pricing)."""
        tracker = TokenTracker()
        # 1M input at $2.50, 1M output at $10.00
        tracker.record("gpt-4o", prompt_tokens=1_000_000, completion_tokens=1_000_000)
        cost = tracker.get_total_cost()
        assert abs(cost - 12.50) < 0.01

    def test_cost_claude_haiku(self) -> None:
        """Cost calculation for claude-3-haiku."""
        tracker = TokenTracker()
        tracker.record(
            "claude-3-haiku-20240307",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        cost = tracker.get_total_cost()
        assert abs(cost - 1.50) < 0.01  # $0.25 + $1.25

    def test_cost_claude_sonnet(self) -> None:
        """Cost calculation for claude-3.5-sonnet."""
        tracker = TokenTracker()
        tracker.record(
            "claude-3-5-sonnet-20241022",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        cost = tracker.get_total_cost()
        assert abs(cost - 18.0) < 0.01  # $3.0 + $15.0

    def test_cost_unknown_model_is_zero(self) -> None:
        """Unknown model pricing counted as $0."""
        tracker = TokenTracker()
        tracker.record("unknown-model", prompt_tokens=1_000_000, completion_tokens=1_000_000)
        assert tracker.get_total_cost() == 0.0

    def test_cost_mixed_models(self) -> None:
        """Cost across multiple models sums correctly."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0)
        tracker.record("gpt-4o", prompt_tokens=1_000_000, completion_tokens=0)
        cost = tracker.get_total_cost()
        assert abs(cost - 2.65) < 0.01  # $0.15 + $2.50

    def test_cost_small_usage(self) -> None:
        """Small token counts produce tiny cost."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        cost = tracker.get_total_cost()
        # 100/1M * $0.15 + 50/1M * $0.60 = $0.000015 + $0.000030 = $0.000045
        assert cost > 0
        assert cost < 0.001


class TestTokenTrackerBreakdown:
    """Tests for per-model breakdown."""

    def test_breakdown_single_model(self) -> None:
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        breakdown = tracker.get_breakdown_by_model()
        assert "gpt-4o-mini" in breakdown
        assert breakdown["gpt-4o-mini"]["prompt_tokens"] == 100
        assert breakdown["gpt-4o-mini"]["completion_tokens"] == 50
        assert breakdown["gpt-4o-mini"]["total_tokens"] == 150

    def test_breakdown_multiple_models(self) -> None:
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        tracker.record("gpt-4o", prompt_tokens=200, completion_tokens=100)
        breakdown = tracker.get_breakdown_by_model()
        assert len(breakdown) == 2
        assert "gpt-4o-mini" in breakdown
        assert "gpt-4o" in breakdown

    def test_breakdown_accumulated(self) -> None:
        """Multiple records for same model are accumulated."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        tracker.record("gpt-4o-mini", prompt_tokens=200, completion_tokens=100)
        breakdown = tracker.get_breakdown_by_model()
        assert breakdown["gpt-4o-mini"]["prompt_tokens"] == 300
        assert breakdown["gpt-4o-mini"]["completion_tokens"] == 150

    def test_breakdown_empty_tracker(self) -> None:
        tracker = TokenTracker()
        assert tracker.get_breakdown_by_model() == {}


class TestTokenTrackerReset:
    """Tests for the reset method."""

    def test_reset_clears_totals(self) -> None:
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        tracker.reset()
        assert tracker.get_total_tokens() == 0
        assert tracker.get_total_cost() == 0.0
        assert tracker.get_breakdown_by_model() == {}

    def test_reset_then_record(self) -> None:
        """After reset, new records start fresh."""
        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        tracker.reset()
        tracker.record("gpt-4o", prompt_tokens=200, completion_tokens=100)
        assert tracker.get_total_tokens() == 300
        breakdown = tracker.get_breakdown_by_model()
        assert "gpt-4o-mini" not in breakdown
        assert "gpt-4o" in breakdown
