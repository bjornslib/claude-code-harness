"""Regression test suite for ZeroRepo prompt changes.

Uses golden tasks to ensure pipeline quality doesn't degrade.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from zerorepo.evaluation.models import BenchmarkTask, DifficultyLevel


GOLDEN_TASKS_PATH = Path(__file__).parent / "golden_tasks.json"


@pytest.fixture
def golden_tasks():
    """Load golden tasks from JSON."""
    with open(GOLDEN_TASKS_PATH) as f:
        data = json.load(f)
    return [BenchmarkTask.model_validate(t) for t in data["tasks"]]


@pytest.fixture
def golden_data():
    """Load raw golden tasks data."""
    with open(GOLDEN_TASKS_PATH) as f:
        return json.load(f)


class TestGoldenTasksIntegrity:
    """Verify golden tasks are valid and well-formed."""

    def test_golden_tasks_load(self, golden_tasks):
        assert len(golden_tasks) >= 10

    def test_all_tasks_have_test_code(self, golden_tasks):
        for task in golden_tasks:
            assert task.test_code, f"Task {task.id} has no test code"

    def test_all_tasks_have_description(self, golden_tasks):
        for task in golden_tasks:
            assert task.description, f"Task {task.id} has no description"

    def test_projects_coverage(self, golden_tasks):
        projects = set(t.project for t in golden_tasks)
        assert len(projects) >= 3, f"Expected >=3 projects, got {projects}"

    def test_five_projects(self, golden_tasks):
        projects = set(t.project for t in golden_tasks)
        expected = {"scikit-learn", "pandas", "sympy", "statsmodels", "requests"}
        assert projects == expected

    def test_difficulty_distribution(self, golden_tasks):
        difficulties = set(t.difficulty for t in golden_tasks)
        assert len(difficulties) >= 2, "Need at least 2 difficulty levels"

    def test_task_ids_unique(self, golden_tasks):
        ids = [t.id for t in golden_tasks]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_categories_populated(self, golden_tasks):
        for task in golden_tasks:
            assert task.category, f"Task {task.id} has no category"

    def test_subcategories_populated(self, golden_tasks):
        for task in golden_tasks:
            assert task.subcategory, f"Task {task.id} has no subcategory"

    def test_loc_positive(self, golden_tasks):
        for task in golden_tasks:
            assert task.loc > 0, f"Task {task.id} has loc=0"

    def test_golden_json_has_version(self, golden_data):
        assert "version" in golden_data
        assert golden_data["version"] == "1.0"

    def test_golden_json_has_description(self, golden_data):
        assert "description" in golden_data
        assert len(golden_data["description"]) > 0

    def test_two_tasks_per_project(self, golden_tasks):
        from collections import Counter
        project_counts = Counter(t.project for t in golden_tasks)
        for project, count in project_counts.items():
            assert count >= 2, f"Project {project} has only {count} tasks"

    def test_task_ids_follow_convention(self, golden_tasks):
        for task in golden_tasks:
            parts = task.id.split("-")
            assert len(parts) >= 3, f"Task ID {task.id} doesn't follow convention"
            # Last part should be numeric
            assert parts[-1].isdigit(), f"Task ID {task.id} last part not numeric"

    def test_difficulty_enum_values(self, golden_tasks):
        for task in golden_tasks:
            assert task.difficulty in (
                DifficultyLevel.EASY,
                DifficultyLevel.MEDIUM,
                DifficultyLevel.HARD,
            )

    def test_test_code_contains_def(self, golden_tasks):
        for task in golden_tasks:
            assert "def test_" in task.test_code, (
                f"Task {task.id} test_code missing 'def test_'"
            )

    def test_test_code_contains_assert(self, golden_tasks):
        for task in golden_tasks:
            assert "assert" in task.test_code, (
                f"Task {task.id} test_code missing assert"
            )
