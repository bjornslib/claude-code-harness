"""Unit tests for the Categorizer class.

Tests cover:
- Taxonomy construction from benchmark tasks
- Hierarchical node creation and counting
- Stratified sampling with category proportions
- Edge cases: empty input, single category, oversized samples
"""

from __future__ import annotations

import pytest

from cobuilder.repomap.evaluation.categorizer import Categorizer
from cobuilder.repomap.evaluation.models import BenchmarkTask, DifficultyLevel, TaxonomyNode


def _make_task(task_id: str, category: str) -> BenchmarkTask:
    """Helper to create a BenchmarkTask with minimal required fields."""
    return BenchmarkTask(
        id=task_id,
        project="test-project",
        category=category,
        description="A test task",
        test_code="def test_x():\n    assert True",
    )


@pytest.fixture()
def categorizer() -> Categorizer:
    """Create a Categorizer instance."""
    return Categorizer()


@pytest.fixture()
def diverse_tasks() -> list[BenchmarkTask]:
    """Create a diverse set of tasks across categories."""
    return [
        _make_task("task-001", "sklearn.linear_model.ridge"),
        _make_task("task-002", "sklearn.linear_model.lasso"),
        _make_task("task-003", "sklearn.linear_model.ridge"),
        _make_task("task-004", "sklearn.tree.decision_tree"),
        _make_task("task-005", "sklearn.tree.random_forest"),
        _make_task("task-006", "numpy.array"),
        _make_task("task-007", "numpy.linalg"),
        _make_task("task-008", "numpy.linalg"),
        _make_task("task-009", "pandas.dataframe"),
        _make_task("task-010", "pandas.series"),
    ]


# ---------------------------------------------------------------------------
# Taxonomy construction
# ---------------------------------------------------------------------------


class TestBuildTaxonomy:
    """Tests for build_taxonomy()."""

    def test_empty_input(self, categorizer: Categorizer) -> None:
        """Empty task list should produce an empty taxonomy."""
        taxonomy = categorizer.build_taxonomy([])
        assert taxonomy.roots == {}
        assert taxonomy.total_tasks == 0
        assert taxonomy.total_categories == 0

    def test_single_task(self, categorizer: Categorizer) -> None:
        """Single task should create a root node."""
        task = _make_task("task-001", "sklearn.linear_model")
        taxonomy = categorizer.build_taxonomy([task])
        assert "sklearn" in taxonomy.roots
        assert taxonomy.total_tasks == 1
        assert taxonomy.total_categories == 1

    def test_root_count(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Should create one root per top-level name."""
        taxonomy = categorizer.build_taxonomy(diverse_tasks)
        assert len(taxonomy.roots) == 3  # sklearn, numpy, pandas

    def test_total_tasks(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """total_tasks should match input length."""
        taxonomy = categorizer.build_taxonomy(diverse_tasks)
        assert taxonomy.total_tasks == 10

    def test_total_categories(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """total_categories should count unique categories."""
        taxonomy = categorizer.build_taxonomy(diverse_tasks)
        # Categories: sklearn.linear_model.ridge, sklearn.linear_model.lasso,
        # sklearn.tree.decision_tree, sklearn.tree.random_forest,
        # numpy.array, numpy.linalg, pandas.dataframe, pandas.series
        assert taxonomy.total_categories == 8

    def test_nested_children(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Intermediate nodes should have correct children."""
        taxonomy = categorizer.build_taxonomy(diverse_tasks)
        sklearn = taxonomy.roots["sklearn"]
        assert "linear_model" in sklearn.children
        assert "tree" in sklearn.children

    def test_leaf_counts(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Leaf node counts should reflect the number of tasks."""
        taxonomy = categorizer.build_taxonomy(diverse_tasks)
        sklearn = taxonomy.roots["sklearn"]
        ridge = sklearn.children["linear_model"].children["ridge"]
        assert ridge.count == 2  # task-001 and task-003

    def test_root_count_aggregates(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Root count should aggregate all descendant tasks."""
        taxonomy = categorizer.build_taxonomy(diverse_tasks)
        sklearn = taxonomy.roots["sklearn"]
        # 5 sklearn tasks total (001, 002, 003, 004, 005)
        assert sklearn.count == 5


# ---------------------------------------------------------------------------
# Stratified sampling
# ---------------------------------------------------------------------------


class TestStratifiedSample:
    """Tests for stratified_sample()."""

    def test_sample_less_than_total(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Sampling fewer than total should return exactly n tasks."""
        sample = categorizer.stratified_sample(diverse_tasks, n=5, seed=42)
        assert len(sample) == 5

    def test_sample_returns_benchmark_tasks(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """All returned items should be BenchmarkTask instances."""
        sample = categorizer.stratified_sample(diverse_tasks, n=5, seed=42)
        for task in sample:
            assert isinstance(task, BenchmarkTask)

    def test_sample_exceeds_total(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Requesting more than available should return all tasks."""
        sample = categorizer.stratified_sample(diverse_tasks, n=100, seed=42)
        assert len(sample) == len(diverse_tasks)

    def test_sample_equal_to_total(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Requesting exactly total should return all tasks."""
        sample = categorizer.stratified_sample(
            diverse_tasks, n=len(diverse_tasks), seed=42
        )
        assert len(sample) == len(diverse_tasks)

    def test_reproducibility_with_seed(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Same seed should produce same sample."""
        s1 = categorizer.stratified_sample(diverse_tasks, n=5, seed=42)
        s2 = categorizer.stratified_sample(diverse_tasks, n=5, seed=42)
        assert [t.id for t in s1] == [t.id for t in s2]

    def test_different_seeds_may_differ(
        self, categorizer: Categorizer, diverse_tasks: list[BenchmarkTask]
    ) -> None:
        """Different seeds should likely produce different samples."""
        s1 = categorizer.stratified_sample(diverse_tasks, n=5, seed=42)
        s2 = categorizer.stratified_sample(diverse_tasks, n=5, seed=99)
        # Not guaranteed to differ, but very likely with different seeds
        ids1 = set(t.id for t in s1)
        ids2 = set(t.id for t in s2)
        # Just verify they are valid - actual difference isn't guaranteed
        assert len(ids1) == 5
        assert len(ids2) == 5

    def test_empty_input(self, categorizer: Categorizer) -> None:
        """Empty input should return empty output."""
        sample = categorizer.stratified_sample([], n=5, seed=42)
        assert sample == []

    def test_single_task_sample(self, categorizer: Categorizer) -> None:
        """Sampling 1 from 1 task should return that task."""
        task = _make_task("task-001", "cat.a")
        sample = categorizer.stratified_sample([task], n=1, seed=42)
        assert len(sample) == 1
        assert sample[0].id == "task-001"
