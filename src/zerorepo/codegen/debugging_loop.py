"""Debugging loop with majority-vote diagnosis for code generation failures.

Implements a 5-round LLM diagnosis strategy where each round classifies
the failure cause as one of:
- ``implementation_bug``: The generated implementation has a bug.
- ``test_bug``: The generated tests are incorrect.
- ``environment``: The sandbox environment caused the failure.

A majority vote (>= 3/5 agreeing) determines the final classification,
and the LLM also generates a fix for the identified cause.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from zerorepo.codegen.tdd_loop import DiagnosisResult
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIAGNOSIS_ROUNDS = 5
MAJORITY_THRESHOLD = 3
VALID_CLASSIFICATIONS = {"implementation_bug", "test_bug", "environment"}
BASE_TEMPERATURE = 0.3
TEMPERATURE_INCREMENT = 0.1


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_DIAGNOSIS_SYSTEM_PROMPT = """\
You are a Python debugging expert. Analyze the test failure and classify
the root cause as exactly ONE of:
- implementation_bug: The implementation code has a bug
- test_bug: The test code is incorrect or has wrong expectations
- environment: The sandbox environment caused the failure (missing deps, etc.)

Then provide a fix for the identified cause.

Respond with ONLY valid JSON matching the schema below, no markdown fences.
"""

_DIAGNOSIS_USER_TEMPLATE = """\
Analyze this test failure:

Function signature: {signature}
Docstring: {docstring}

Implementation:
```python
{implementation}
```

Test code:
```python
{test_code}
```

Error output:
```
{error_output}
```

Classify the root cause and provide a fix.
Respond with JSON: {{"classification": "...", "fixed_code": "...", "explanation": "..."}}
"""


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class DiagnosisResponse(BaseModel):
    """Structured LLM response for failure diagnosis.

    Attributes:
        classification: One of 'implementation_bug', 'test_bug', 'environment'.
        fixed_code: The corrected code for the identified issue.
        explanation: Human-readable explanation of the diagnosis.
    """

    classification: str = Field(
        default="implementation_bug",
        description="Failure classification",
    )
    fixed_code: str = Field(
        default="",
        description="Corrected code for the identified issue",
    )
    explanation: str = Field(
        default="",
        description="Human-readable explanation",
    )


# ---------------------------------------------------------------------------
# Majority-vote debugging loop
# ---------------------------------------------------------------------------


class MajorityVoteDiagnoser:
    """Diagnose test failures using majority-vote LLM consensus.

    Runs ``DIAGNOSIS_ROUNDS`` (default 5) LLM diagnosis calls with
    increasing temperature, then takes a majority vote to determine
    the failure classification.

    Args:
        llm_gateway: The LLM gateway for making completion requests.
        model: The model identifier to use for diagnosis.
        rounds: Number of diagnosis rounds (default 5).
        majority_threshold: Minimum votes for consensus (default 3).
    """

    def __init__(
        self,
        llm_gateway: Any,
        model: str = "gpt-4o-mini",
        *,
        rounds: int = DIAGNOSIS_ROUNDS,
        majority_threshold: int = MAJORITY_THRESHOLD,
    ) -> None:
        self._gateway = llm_gateway
        self._model = model
        self._rounds = rounds
        self._majority_threshold = majority_threshold

    @property
    def rounds(self) -> int:
        """Number of diagnosis rounds."""
        return self._rounds

    @property
    def majority_threshold(self) -> int:
        """Minimum votes for majority consensus."""
        return self._majority_threshold

    def diagnose_and_fix(
        self,
        node: RPGNode,
        implementation: str,
        test_code: str,
        error_output: str,
        context: dict[str, Any],
    ) -> DiagnosisResult:
        """Run majority-vote diagnosis on a test failure.

        Performs ``self._rounds`` LLM calls with increasing temperature
        (base + i * increment), collects classifications, and determines
        the majority vote.

        Args:
            node: The RPG node whose tests failed.
            implementation: Current implementation code.
            test_code: The failing test code.
            error_output: stderr/stdout from the test run.
            context: Additional context for diagnosis.

        Returns:
            A DiagnosisResult with the majority classification and fix.
        """
        signature = node.signature or ""
        docstring = node.docstring or ""

        prompt = _DIAGNOSIS_USER_TEMPLATE.format(
            signature=signature,
            docstring=docstring,
            implementation=implementation,
            test_code=test_code,
            error_output=error_output,
        )

        messages = [
            {"role": "system", "content": _DIAGNOSIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Collect diagnoses across rounds
        diagnoses: list[DiagnosisResponse] = []
        classifications: list[str] = []

        for i in range(self._rounds):
            temperature = BASE_TEMPERATURE + i * TEMPERATURE_INCREMENT

            logger.info(
                "Diagnosis round %d/%d for node %s (temp=%.1f)",
                i + 1,
                self._rounds,
                node.id,
                temperature,
            )

            try:
                response_text = self._gateway.complete(
                    messages=messages,
                    model=self._model,
                    temperature=temperature,
                )
                diagnosis = self._parse_diagnosis(response_text)
                diagnoses.append(diagnosis)
                classifications.append(diagnosis.classification)

            except Exception as exc:
                logger.warning("Diagnosis round %d failed: %s", i + 1, exc)
                # Default to implementation_bug on parse failure
                diagnoses.append(DiagnosisResponse())
                classifications.append("implementation_bug")

        # Majority vote
        vote_counts = Counter(classifications)
        winner, winner_count = vote_counts.most_common(1)[0]

        logger.info(
            "Diagnosis vote for node %s: %s (votes: %s)",
            node.id,
            winner,
            dict(vote_counts),
        )

        # Find the best diagnosis with the winning classification
        best_diagnosis = self._select_best_diagnosis(diagnoses, winner)

        # Build result
        result = DiagnosisResult(
            classification=winner,
            explanation=best_diagnosis.explanation,
        )

        if winner == "implementation_bug":
            result.fixed_implementation = best_diagnosis.fixed_code
        elif winner == "test_bug":
            result.fixed_test_code = best_diagnosis.fixed_code

        return result

    @staticmethod
    def _parse_diagnosis(response_text: str) -> DiagnosisResponse:
        """Parse an LLM response into a DiagnosisResponse.

        Attempts JSON parsing, falling back to keyword detection.

        Args:
            response_text: Raw LLM response text.

        Returns:
            A DiagnosisResponse parsed from the text.
        """
        import json

        # Strip markdown fences
        text = response_text.strip()
        if text.startswith("```"):
            # Remove opening fence
            first_newline = text.index("\n")
            text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[: -len("```")]
            text = text.strip()

        try:
            data = json.loads(text)
            classification = data.get("classification", "implementation_bug")
            if classification not in VALID_CLASSIFICATIONS:
                classification = "implementation_bug"
            return DiagnosisResponse(
                classification=classification,
                fixed_code=data.get("fixed_code", ""),
                explanation=data.get("explanation", ""),
            )
        except (json.JSONDecodeError, AttributeError):
            # Fall back to keyword detection
            text_lower = response_text.lower()
            if "test_bug" in text_lower:
                classification = "test_bug"
            elif "environment" in text_lower:
                classification = "environment"
            else:
                classification = "implementation_bug"

            return DiagnosisResponse(
                classification=classification,
                explanation="Parsed from unstructured response",
            )

    @staticmethod
    def _select_best_diagnosis(
        diagnoses: list[DiagnosisResponse],
        winner: str,
    ) -> DiagnosisResponse:
        """Select the best diagnosis with the winning classification.

        Prefers diagnoses that have non-empty fixed_code and explanation.

        Args:
            diagnoses: All collected diagnoses.
            winner: The winning classification.

        Returns:
            The best matching DiagnosisResponse.
        """
        matching = [d for d in diagnoses if d.classification == winner]

        # Prefer ones with fixed_code and explanation
        for diag in matching:
            if diag.fixed_code and diag.explanation:
                return diag

        # Fall back to any with fixed_code
        for diag in matching:
            if diag.fixed_code:
                return diag

        # Fall back to first matching
        return matching[0] if matching else DiagnosisResponse(classification=winner)
