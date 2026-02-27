"""Stage 2: LLM-based semantic validation with majority voting.

Uses multiple LLM calls to validate whether generated functions
match task requirements, following a 2-round majority voting scheme.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from cobuilder.repomap.evaluation.models import (
    BenchmarkTask,
    FunctionSignature,
    ValidationResult,
    Vote,
    VoteResult,
)

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are a code reviewer validating whether a function implements the required functionality.

**Task Requirements**:
{task_description}

**Generated Function**:
```python
{function_code}
```

**Question**: Does this function correctly implement the required functionality?

Answer ONLY with:
- "YES" if the function implements all requirements
- "NO" if the function is missing requirements or has incorrect logic
- "PARTIAL" if the function implements some but not all requirements

Provide a brief 1-sentence justification.

Answer:"""


class LLMClient(Protocol):
    """Protocol for LLM completion. Compatible with LLMGateway.complete()."""

    def complete(
        self, messages: list[dict[str, Any]], model: str, **kwargs: Any
    ) -> str: ...


class SemanticValidator:
    """LLM-based semantic validation with 2-round majority voting."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "gpt-4o-mini",
        num_voters: int = 3,
        num_rounds: int = 2,
    ):
        self.llm = llm_client
        self.model = model
        self.num_voters = num_voters
        self.num_rounds = num_rounds

    def validate_function(
        self,
        task: BenchmarkTask,
        function: FunctionSignature,
    ) -> ValidationResult:
        """Run majority-vote validation across rounds.

        Round 1: num_voters votes
        If clear majority -> return immediately
        Round 2: num_voters more votes, combine all
        """
        all_votes: list[Vote] = []

        # Round 1
        round1_votes = self._collect_votes(task, function, round_num=1)
        all_votes.extend(round1_votes)

        r1_result = self._check_majority(round1_votes)
        if r1_result is not None:
            return ValidationResult(
                passed=(r1_result == VoteResult.YES),
                confidence="high",
                votes=all_votes,
                candidate_function=function.name,
            )

        # Round 2 (if no clear majority)
        if self.num_rounds >= 2:
            round2_votes = self._collect_votes(task, function, round_num=2)
            all_votes.extend(round2_votes)

        # Final decision on all votes
        final_result = self._majority_vote(all_votes)
        has_majority = self._check_majority(all_votes) is not None

        return ValidationResult(
            passed=(final_result == VoteResult.YES),
            confidence="medium" if has_majority else "low",
            votes=all_votes,
            candidate_function=function.name,
        )

    def _collect_votes(
        self,
        task: BenchmarkTask,
        function: FunctionSignature,
        round_num: int,
    ) -> list[Vote]:
        """Collect votes from num_voters LLM calls."""
        votes = []
        for _ in range(self.num_voters):
            vote = self._single_vote(task, function, round_num)
            votes.append(vote)
        return votes

    def _single_vote(
        self,
        task: BenchmarkTask,
        function: FunctionSignature,
        round_num: int,
    ) -> Vote:
        """Execute a single LLM validation vote."""
        prompt = VALIDATION_PROMPT.format(
            task_description=task.description,
            function_code=function.body or function.signature,
        )

        try:
            response = self.llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=150,
                temperature=0.7,  # Some variance for voting diversity
            )
            result, justification = self._parse_vote(response)
        except Exception as e:
            logger.warning(f"Vote failed: {e}")
            result = VoteResult.NO
            justification = f"Error: {e}"

        return Vote(
            result=result,
            justification=justification,
            model=self.model,
            round_num=round_num,
        )

    @staticmethod
    def _parse_vote(response: str) -> tuple[VoteResult, str]:
        """Parse LLM response into VoteResult and justification."""
        response = response.strip()
        upper = response.upper()

        # Try to extract result from beginning
        if upper.startswith("YES"):
            result = VoteResult.YES
        elif upper.startswith("NO"):
            result = VoteResult.NO
        elif upper.startswith("PARTIAL"):
            result = VoteResult.PARTIAL
        else:
            # Fallback: search for keywords
            if "YES" in upper.split(".")[0]:
                result = VoteResult.YES
            elif "PARTIAL" in upper.split(".")[0]:
                result = VoteResult.PARTIAL
            else:
                result = VoteResult.NO

        # Extract justification (everything after the result keyword)
        justification = response
        for prefix in ("YES", "NO", "PARTIAL", "yes", "no", "partial"):
            if response.startswith(prefix):
                justification = response[len(prefix) :].strip().lstrip(".:,- ")
                break

        return result, justification

    @staticmethod
    def _check_majority(votes: list[Vote]) -> VoteResult | None:
        """Check if there's a clear majority (>50%) for any result."""
        if not votes:
            return None

        counts: dict[VoteResult, int] = {}
        for v in votes:
            counts[v.result] = counts.get(v.result, 0) + 1

        threshold = len(votes) / 2
        for result, count in counts.items():
            if count > threshold:
                return result

        return None

    @staticmethod
    def _majority_vote(votes: list[Vote]) -> VoteResult:
        """Return the most common vote result."""
        if not votes:
            return VoteResult.NO

        counts: dict[VoteResult, int] = {}
        for v in votes:
            counts[v.result] = counts.get(v.result, 0) + 1

        return max(counts, key=counts.get)  # type: ignore[arg-type]
