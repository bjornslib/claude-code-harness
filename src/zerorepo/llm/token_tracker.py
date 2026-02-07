"""Token usage tracking with cost estimation for the LLM Gateway."""

from __future__ import annotations

from dataclasses import dataclass, field

from zerorepo.llm.models import TOKEN_PRICING


@dataclass
class _ModelUsage:
    """Accumulated token usage for a single model."""

    prompt_tokens: int = 0
    completion_tokens: int = 0


class TokenTracker:
    """Accumulates token usage and estimates cost across LLM requests.

    Thread-safety note: This class is **not** thread-safe.  For concurrent
    access, wrap calls in a lock externally.

    Example::

        tracker = TokenTracker()
        tracker.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        print(tracker.get_total_tokens())   # 150
        print(tracker.get_total_cost())     # ~0.000045
    """

    def __init__(self) -> None:
        self._usage: dict[str, _ModelUsage] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record token usage for a request.

        Args:
            model: The model identifier (e.g. ``"gpt-4o-mini"``).
            prompt_tokens: Number of prompt/input tokens.
            completion_tokens: Number of completion/output tokens.
        """
        if model not in self._usage:
            self._usage[model] = _ModelUsage()
        entry = self._usage[model]
        entry.prompt_tokens += prompt_tokens
        entry.completion_tokens += completion_tokens

    def get_total_tokens(self) -> int:
        """Return total tokens (prompt + completion) across all models."""
        return sum(
            u.prompt_tokens + u.completion_tokens for u in self._usage.values()
        )

    def get_total_cost(self) -> float:
        """Return estimated total cost in USD across all models.

        Models not found in the pricing table are counted as $0.
        """
        total = 0.0
        for model, usage in self._usage.items():
            pricing = TOKEN_PRICING.get(model)
            if pricing is None:
                continue
            total += (usage.prompt_tokens / 1_000_000) * pricing["input"]
            total += (usage.completion_tokens / 1_000_000) * pricing["output"]
        return total

    def get_breakdown_by_model(self) -> dict[str, dict[str, int]]:
        """Return per-model breakdown of token usage.

        Returns:
            Dict mapping model name → ``{"prompt_tokens": …, "completion_tokens": …, "total_tokens": …}``
        """
        result: dict[str, dict[str, int]] = {}
        for model, usage in self._usage.items():
            result[model] = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.prompt_tokens + usage.completion_tokens,
            }
        return result

    def reset(self) -> None:
        """Clear all accumulated usage data."""
        self._usage.clear()
