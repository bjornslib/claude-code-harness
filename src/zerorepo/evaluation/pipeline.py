"""Evaluation pipeline orchestrating the 3-stage evaluation process.

Stage 1: Localization (embedding similarity)
Stage 2: Semantic Validation (LLM majority voting)
Stage 3: Execution Testing (Docker sandbox)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from zerorepo.evaluation.models import (
    BenchmarkTask,
    FunctionSignature,
    RepositoryResult,
    StageFailed,
    TaskResult,
)

logger = logging.getLogger(__name__)


class EvaluationPipeline:
    """Orchestrates 3-stage evaluation: localization, validation, execution."""

    def __init__(
        self,
        localizer: Any,  # FunctionLocalizer
        validator: Any,  # SemanticValidator
        tester: Any,  # ExecutionTester
        top_k: int = 5,
        validation_candidates: int = 3,
    ):
        self.localizer = localizer
        self.validator = validator
        self.tester = tester
        self.top_k = top_k
        self.validation_candidates = validation_candidates

    def evaluate_task(
        self,
        task: BenchmarkTask,
        repo_path: str,
        functions: list[FunctionSignature] | None = None,
    ) -> TaskResult:
        """Run full 3-stage evaluation on a single task."""

        # Stage 1: Localization
        candidates = self.localizer.localize(
            task, repo_path, top_k=self.top_k, functions=functions
        )

        if not candidates:
            return TaskResult(
                task_id=task.id,
                localized=False,
                stage_failed=StageFailed.LOCALIZATION,
            )

        # Stage 2: Semantic Validation (try top candidates)
        validated_function = None
        validation_result = None
        best_score = 0.0

        for candidate, score in candidates[: self.validation_candidates]:
            result = self.validator.validate_function(task, candidate)
            if result.passed:
                validated_function = candidate
                validation_result = result
                best_score = score
                break

        if not validated_function:
            return TaskResult(
                task_id=task.id,
                localized=True,
                validated=False,
                stage_failed=StageFailed.VALIDATION,
                candidate_function=candidates[0][0].name if candidates else None,
                candidate_score=candidates[0][1] if candidates else 0.0,
            )

        # Stage 3: Execution Testing
        execution = self.tester.execute_test(task, repo_path)

        return TaskResult(
            task_id=task.id,
            localized=True,
            validated=True,
            passed=execution.passed,
            stage_failed=None if execution.passed else StageFailed.EXECUTION,
            candidate_function=validated_function.name,
            candidate_score=best_score,
            validation_result=validation_result,
            execution_result=execution,
            execution_error=execution.error,
        )

    def evaluate_repository(
        self,
        tasks: list[BenchmarkTask],
        repo_path: str,
    ) -> RepositoryResult:
        """Evaluate all tasks for a generated repository."""
        # Pre-extract functions once
        functions = self.localizer.extract_functions(repo_path)

        results: list[TaskResult] = []
        for i, task in enumerate(tasks):
            logger.info(f"Evaluating task {i+1}/{len(tasks)}: {task.id}")
            result = self.evaluate_task(task, repo_path, functions=functions)
            results.append(result)

        # Calculate coverage
        categories = set(t.category for t in tasks)
        passed_categories = set()
        for task, result in zip(tasks, results):
            if result.passed:
                passed_categories.add(task.category)

        coverage = (
            len(passed_categories) / len(categories) if categories else 0.0
        )

        return RepositoryResult(
            project_name=tasks[0].project if tasks else "unknown",
            total_tasks=len(tasks),
            localized=sum(r.localized for r in results),
            validated=sum(r.validated for r in results),
            passed=sum(r.passed for r in results),
            coverage=coverage,
            task_results=results,
        )
