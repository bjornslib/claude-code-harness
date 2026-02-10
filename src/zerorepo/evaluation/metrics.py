"""Metrics calculation matching the ZeroRepo paper's evaluation criteria."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from zerorepo.evaluation.models import (
    BenchmarkTask,
    CodeStats,
    RepositoryResult,
    TaskResult,
)

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates evaluation metrics matching the ZeroRepo paper."""

    def calculate_coverage(
        self,
        tasks: list[BenchmarkTask],
        results: list[TaskResult],
    ) -> float:
        """Functionality Coverage: % of categories with >=1 passed test."""
        if not tasks:
            return 0.0

        categories = set(t.category for t in tasks)
        passed_categories = set()

        task_map = {t.id: t for t in tasks}
        for r in results:
            if r.passed and r.task_id in task_map:
                passed_categories.add(task_map[r.task_id].category)

        return len(passed_categories) / len(categories) if categories else 0.0

    def calculate_novelty(
        self,
        tasks: list[BenchmarkTask],
        generated_categories: set[str],
    ) -> float:
        """Functionality Novelty: % of categories outside reference taxonomy."""
        if not generated_categories:
            return 0.0

        reference_categories = set(t.category for t in tasks)
        novel = generated_categories - reference_categories
        return len(novel) / len(generated_categories)

    def calculate_pass_rate(self, results: list[TaskResult]) -> float:
        """Pass Rate: fraction of tests passed."""
        if not results:
            return 0.0
        return sum(r.passed for r in results) / len(results)

    def calculate_voting_rate(self, results: list[TaskResult]) -> float:
        """Voting Rate: fraction validated by majority-vote."""
        if not results:
            return 0.0
        return sum(r.validated for r in results) / len(results)

    def calculate_code_stats(self, repo_path: str | Path) -> CodeStats:
        """Calculate LOC, file count, and estimated tokens for a repo."""
        repo_path = Path(repo_path)
        total_loc = 0
        total_files = 0
        total_chars = 0

        for py_file in repo_path.rglob("*.py"):
            total_files += 1
            content = py_file.read_text(encoding="utf-8", errors="replace")
            total_loc += len(content.splitlines())
            total_chars += len(content)

        # Rough token estimate: ~4 chars per token
        estimated_tokens = total_chars // 4

        return CodeStats(
            files=total_files,
            loc=total_loc,
            estimated_tokens=estimated_tokens,
        )
