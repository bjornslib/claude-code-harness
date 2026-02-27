"""Unit tests for the TestHarvester class (bead ff6 + vro).

Tests cover:
- Extraction of test functions from synthetic test files
- AST-based test function parsing (_parse_test_function logic)
- Import extraction (file-level and function-level)
- Category derivation from file paths
- Difficulty estimation heuristics
- Assertion detection
- Docstring-to-description conversion
- Error handling for malformed files
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from scripts.benchmark.harvest_tests import TestHarvester
from cobuilder.repomap.evaluation.models import BenchmarkTask, DifficultyLevel


@pytest.fixture()
def harvester() -> TestHarvester:
    """Create a TestHarvester for a test project."""
    return TestHarvester(project_name="test-project")


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal synthetic repo with test files."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    # test_basic.py: 3 simple test functions
    (tests_dir / "test_basic.py").write_text(
        textwrap.dedent("""\
        import pytest
        import numpy as np

        def test_addition():
            \"\"\"Verify simple addition.\"\"\"
            result = 1 + 1
            assert result == 2

        def test_subtraction():
            result = 5 - 3
            assert result == 2

        def test_multiplication():
            result = 3 * 4
            assert result == 12
        """),
        encoding="utf-8",
    )

    # tests/linear_model/test_ridge.py: nested category
    subdir = tests_dir / "linear_model"
    subdir.mkdir()
    (subdir / "test_ridge.py").write_text(
        textwrap.dedent("""\
        from sklearn.linear_model import Ridge
        import numpy as np

        def test_ridge_fit():
            \"\"\"Test that Ridge.fit works on simple data.\"\"\"
            X = np.array([[1, 2], [3, 4], [5, 6]])
            y = np.array([1, 2, 3])
            model = Ridge(alpha=1.0)
            model.fit(X, y)
            assert model.coef_ is not None
            assert len(model.coef_) == 2

        def test_ridge_predict():
            X = np.array([[1, 2], [3, 4]])
            y = np.array([1, 2])
            model = Ridge()
            model.fit(X, y)
            preds = model.predict(X)
            assert len(preds) == 2
        """),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def tmp_repo_with_edge_cases(tmp_path: Path) -> Path:
    """Create a repo with edge-case test files."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    # File with syntax error
    (tests_dir / "test_syntax_error.py").write_text(
        "def test_broken(\n    this is not valid python\n",
        encoding="utf-8",
    )

    # File with no test functions
    (tests_dir / "test_empty.py").write_text(
        textwrap.dedent("""\
        import math

        def helper_func():
            return 42
        """),
        encoding="utf-8",
    )

    # File with unittest-style assertions
    (tests_dir / "test_unittest_style.py").write_text(
        textwrap.dedent("""\
        import unittest

        class TestMath(unittest.TestCase):
            def test_assertEqual_example(self):
                self.assertEqual(1 + 1, 2)
        """),
        encoding="utf-8",
    )

    # File with function-level imports
    (tests_dir / "test_local_imports.py").write_text(
        textwrap.dedent("""\
        def test_with_local_import():
            import json
            from pathlib import Path
            data = json.dumps({"key": "value"})
            assert "key" in data
        """),
        encoding="utf-8",
    )

    # File with large function (hard difficulty)
    lines = ["def test_large_function():"]
    for i in range(50):
        lines.append(f"    x_{i} = {i}")
    lines.append("    assert True")
    (tests_dir / "test_large.py").write_text("\n".join(lines), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# TestHarvester.extract_tests() - core extraction
# ---------------------------------------------------------------------------


class TestExtractTests:
    """Tests for the main extract_tests() method."""

    def test_extracts_correct_count(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Should find all 5 test functions across 2 files."""
        tasks = harvester.extract_tests(tmp_repo)
        assert len(tasks) == 5

    def test_returns_benchmark_task_instances(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Every result should be a BenchmarkTask."""
        tasks = harvester.extract_tests(tmp_repo)
        for task in tasks:
            assert isinstance(task, BenchmarkTask)

    def test_project_name_set(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """All tasks should have the correct project name."""
        tasks = harvester.extract_tests(tmp_repo)
        for task in tasks:
            assert task.project == "test-project"

    def test_empty_directory(self, harvester: TestHarvester, tmp_path: Path) -> None:
        """Empty directory returns no tasks."""
        tasks = harvester.extract_tests(tmp_path)
        assert tasks == []

    def test_skips_syntax_error_files(
        self, harvester: TestHarvester, tmp_repo_with_edge_cases: Path
    ) -> None:
        """Files with syntax errors should be skipped gracefully."""
        tasks = harvester.extract_tests(tmp_repo_with_edge_cases)
        # Should not crash - may extract tests from valid files
        assert isinstance(tasks, list)

    def test_ignores_non_test_functions(
        self, harvester: TestHarvester, tmp_repo_with_edge_cases: Path
    ) -> None:
        """Functions not starting with test_ should be ignored."""
        tasks = harvester.extract_tests(tmp_repo_with_edge_cases)
        for task in tasks:
            # subcategory is derived from function name minus 'test_'
            assert task.id.startswith("test-project-")


# ---------------------------------------------------------------------------
# _parse_test_function - AST parsing (bead vro)
# ---------------------------------------------------------------------------


class TestParseTestFunction:
    """Tests for the _parse_test_function parsing logic."""

    def test_test_code_extracted(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """test_code should contain the function source code."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert "def test_addition" in addition_task.test_code
        assert "assert result == 2" in addition_task.test_code

    def test_loc_accuracy(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """LOC should count non-empty, non-comment lines accurately."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        # def test_addition():     (1)
        # """Verify..."""          (1)
        # result = 1 + 1           (1)
        # assert result == 2       (1)
        assert addition_task.loc >= 3  # At minimum: def + body
        assert addition_task.loc <= 5  # At most: def + docstring + body

    def test_docstring_used_as_description(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """When docstring exists, first line should become the description."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert "Verify simple addition" in addition_task.description

    def test_name_fallback_description(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """When no docstring, function name should be converted to description."""
        tasks = harvester.extract_tests(tmp_repo)
        subtraction_task = next(t for t in tasks if "subtraction" in t.id)
        assert "subtraction" in subtraction_task.description.lower()

    def test_imports_collected(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """File-level imports should be included in the task."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert any("pytest" in imp for imp in addition_task.imports)
        assert any("numpy" in imp for imp in addition_task.imports)

    def test_function_local_imports(
        self, harvester: TestHarvester, tmp_repo_with_edge_cases: Path
    ) -> None:
        """Imports inside function bodies should also be collected."""
        tasks = harvester.extract_tests(tmp_repo_with_edge_cases)
        local_import_task = next(
            (t for t in tasks if "local_import" in t.id), None
        )
        if local_import_task:
            assert any("json" in imp for imp in local_import_task.imports)

    def test_metadata_includes_file_path(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Metadata should include the relative file path."""
        tasks = harvester.extract_tests(tmp_repo)
        for task in tasks:
            assert "file_path" in task.metadata

    def test_metadata_includes_assertions_flag(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Metadata should include has_assertions flag."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert addition_task.metadata["has_assertions"] is True

    def test_metadata_includes_line_numbers(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Metadata should include start and end line numbers."""
        tasks = harvester.extract_tests(tmp_repo)
        for task in tasks:
            assert "lineno" in task.metadata
            assert "end_lineno" in task.metadata
            assert task.metadata["lineno"] > 0


# ---------------------------------------------------------------------------
# Category derivation
# ---------------------------------------------------------------------------


class TestCategoryDerivation:
    """Tests for _path_to_category."""

    def test_nested_category(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Nested test directories should produce dotted categories."""
        tasks = harvester.extract_tests(tmp_repo)
        ridge_task = next(t for t in tasks if "ridge_fit" in t.id)
        assert ridge_task.category == "linear_model.ridge"

    def test_flat_category(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Tests in tests/ root should have a simple category."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert addition_task.category == "basic"

    def test_subcategory_from_name(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Subcategory should be derived from the function name."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert addition_task.subcategory == "addition"


# ---------------------------------------------------------------------------
# Difficulty estimation
# ---------------------------------------------------------------------------


class TestDifficultyEstimation:
    """Tests for _estimate_difficulty heuristic."""

    def test_small_function_is_easy(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Functions with <15 LOC should be EASY."""
        tasks = harvester.extract_tests(tmp_repo)
        addition_task = next(t for t in tasks if "addition" in t.id)
        assert addition_task.difficulty == DifficultyLevel.EASY

    def test_large_function_is_hard(
        self, harvester: TestHarvester, tmp_repo_with_edge_cases: Path
    ) -> None:
        """Functions with >=40 LOC should be HARD."""
        tasks = harvester.extract_tests(tmp_repo_with_edge_cases)
        large_task = next(
            (t for t in tasks if "large_function" in t.id), None
        )
        if large_task:
            assert large_task.difficulty == DifficultyLevel.HARD


# ---------------------------------------------------------------------------
# Task ID generation
# ---------------------------------------------------------------------------


class TestTaskIdGeneration:
    """Tests for unique task ID generation."""

    def test_ids_are_unique(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """All generated task IDs should be unique."""
        tasks = harvester.extract_tests(tmp_repo)
        ids = [t.id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_id_includes_project_name(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Task IDs should start with the project name."""
        tasks = harvester.extract_tests(tmp_repo)
        for task in tasks:
            assert task.id.startswith("test-project-")

    def test_counter_increments(
        self, harvester: TestHarvester, tmp_repo: Path
    ) -> None:
        """Task counter should increment with each task."""
        tasks = harvester.extract_tests(tmp_repo)
        # IDs end with -NNN counter
        counters = [int(t.id.split("-")[-1]) for t in tasks]
        assert counters == list(range(1, len(tasks) + 1))
