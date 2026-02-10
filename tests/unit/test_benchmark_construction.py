"""Tests for benchmark construction: harvesting, categorization, filtering.

Validates the full benchmark construction pipeline including:
- Test harvesting from Python repositories via AST parsing
- Hierarchical categorization and taxonomy construction
- Stratified sampling across categories
- Test filtering for quality assurance
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from zerorepo.evaluation.categorizer import Categorizer
from zerorepo.evaluation.models import BenchmarkTask, DifficultyLevel, Taxonomy, TaxonomyNode
from zerorepo.evaluation.test_filter import TestFilter

# Import the harvester from scripts/benchmark which is on sys.path via conftest
# or PYTHONPATH. We use a lazy import inside the test class to handle this.
try:
    from scripts.benchmark.harvest_tests import TestHarvester
except ImportError:
    # Fallback: add scripts to path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from benchmark.harvest_tests import TestHarvester


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------


def _make_task(
    id: str = "proj-cat-sub-001",
    project: str = "proj",
    category: str = "cat",
    subcategory: str = "sub",
    description: str = "A test task",
    test_code: str = "def test_foo():\n    assert True",
    loc: int = 20,
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
    **kwargs,
) -> BenchmarkTask:
    """Helper to create a BenchmarkTask with sensible defaults."""
    return BenchmarkTask(
        id=id,
        project=project,
        category=category,
        subcategory=subcategory,
        description=description,
        test_code=test_code,
        loc=loc,
        difficulty=difficulty,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# TestHarvester
# ---------------------------------------------------------------------------


class TestTestHarvester:
    """Tests for the TestHarvester class."""

    def test_extract_simple_test(self, tmp_path: Path) -> None:
        """Extract a single simple test function from a test file."""
        test_file = tmp_path / "tests" / "test_basic.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text(textwrap.dedent("""\
            import os

            def test_addition():
                x = 1 + 2
                assert x == 3
        """))

        harvester = TestHarvester(project_name="myproj")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].project == "myproj"
        assert "test_addition" in tasks[0].test_code
        assert "assert x == 3" in tasks[0].test_code

    def test_extract_multiple_tests(self, tmp_path: Path) -> None:
        """Extract multiple test functions from a single file."""
        test_file = tmp_path / "tests" / "test_math.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text(textwrap.dedent("""\
            def test_add():
                assert 1 + 1 == 2

            def test_subtract():
                assert 3 - 1 == 2

            def test_multiply():
                assert 2 * 3 == 6
        """))

        harvester = TestHarvester(project_name="calc")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 3
        names = {t.subcategory for t in tasks}
        assert names == {"add", "subtract", "multiply"}

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Gracefully skip files with syntax errors."""
        test_file = tmp_path / "tests" / "test_broken.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_bad(\n    # missing closing paren and body")

        harvester = TestHarvester(project_name="broken")
        tasks = harvester.extract_tests(tmp_path)

        assert tasks == []

    def test_category_from_path(self, tmp_path: Path) -> None:
        """Category is derived from relative path within tests/."""
        test_file = tmp_path / "tests" / "linear_model" / "test_ridge.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text(textwrap.dedent("""\
            def test_fit():
                assert True
        """))

        harvester = TestHarvester(project_name="sklearn")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].category == "linear_model.ridge"

    def test_category_flat_test_dir(self, tmp_path: Path) -> None:
        """Category from file directly in tests/ dir strips test prefix."""
        test_file = tmp_path / "tests" / "test_utils.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_one():\n    assert 1\n")

        harvester = TestHarvester(project_name="proj")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].category == "utils"

    def test_loc_calculation(self, tmp_path: Path) -> None:
        """LOC excludes blank lines and comments."""
        test_file = tmp_path / "test_loc.py"
        test_file.write_text(textwrap.dedent("""\
            def test_something():
                # This is a comment
                x = 1

                y = 2
                # Another comment
                assert x + y == 3
        """))

        harvester = TestHarvester(project_name="loc")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        # Non-empty, non-comment lines: def, x=1, y=2, assert = 4
        assert tasks[0].loc == 4

    def test_difficulty_easy(self, tmp_path: Path) -> None:
        """Short tests are classified as EASY."""
        test_file = tmp_path / "test_easy.py"
        test_file.write_text("def test_tiny():\n    assert True\n")

        harvester = TestHarvester(project_name="easy")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].difficulty == DifficultyLevel.EASY

    def test_difficulty_medium(self, tmp_path: Path) -> None:
        """Medium-length tests are classified as MEDIUM."""
        lines = ["def test_medium():"]
        for i in range(20):
            lines.append(f"    x{i} = {i}")
        lines.append("    assert True")
        test_file = tmp_path / "test_med.py"
        test_file.write_text("\n".join(lines) + "\n")

        harvester = TestHarvester(project_name="med")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].difficulty == DifficultyLevel.MEDIUM

    def test_difficulty_hard(self, tmp_path: Path) -> None:
        """Long tests are classified as HARD."""
        lines = ["def test_hard():"]
        for i in range(50):
            lines.append(f"    x{i} = {i}")
        lines.append("    assert True")
        test_file = tmp_path / "test_hard.py"
        test_file.write_text("\n".join(lines) + "\n")

        harvester = TestHarvester(project_name="hard")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].difficulty == DifficultyLevel.HARD

    def test_import_extraction_file_level(self, tmp_path: Path) -> None:
        """File-level imports are captured in the task."""
        test_file = tmp_path / "test_imports.py"
        test_file.write_text(textwrap.dedent("""\
            import os
            from pathlib import Path

            def test_imports():
                assert True
        """))

        harvester = TestHarvester(project_name="imp")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert "import os" in tasks[0].imports
        assert "from pathlib import Path" in tasks[0].imports

    def test_import_extraction_function_level(self, tmp_path: Path) -> None:
        """Function-level imports are also captured."""
        test_file = tmp_path / "test_func_imp.py"
        test_file.write_text(textwrap.dedent("""\
            def test_local_import():
                import json
                assert json.dumps({}) == '{}'
        """))

        harvester = TestHarvester(project_name="imp")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert "import json" in tasks[0].imports

    def test_assertion_detection_assert_keyword(self, tmp_path: Path) -> None:
        """Detects bare assert statements."""
        test_file = tmp_path / "test_assert.py"
        test_file.write_text("def test_a():\n    assert 1 == 1\n")

        harvester = TestHarvester(project_name="a")
        tasks = harvester.extract_tests(tmp_path)

        assert tasks[0].metadata["has_assertions"] is True

    def test_assertion_detection_unittest_style(self, tmp_path: Path) -> None:
        """Detects unittest-style self.assertEqual calls."""
        test_file = tmp_path / "test_unittest.py"
        test_file.write_text(textwrap.dedent("""\
            def test_eq(self):
                self.assertEqual(1, 1)
        """))

        harvester = TestHarvester(project_name="u")
        tasks = harvester.extract_tests(tmp_path)

        assert tasks[0].metadata["has_assertions"] is True

    def test_no_assertions(self, tmp_path: Path) -> None:
        """Test without assertions is detected."""
        test_file = tmp_path / "test_no_assert.py"
        test_file.write_text("def test_noop():\n    x = 1\n")

        harvester = TestHarvester(project_name="n")
        tasks = harvester.extract_tests(tmp_path)

        assert tasks[0].metadata["has_assertions"] is False

    def test_docstring_description(self, tmp_path: Path) -> None:
        """Description comes from docstring when available."""
        test_file = tmp_path / "test_doc.py"
        test_file.write_text(textwrap.dedent('''\
            def test_with_doc():
                """Validate the addition operation."""
                assert 1 + 1 == 2
        '''))

        harvester = TestHarvester(project_name="doc")
        tasks = harvester.extract_tests(tmp_path)

        assert tasks[0].description == "Validate the addition operation."

    def test_name_fallback_description(self, tmp_path: Path) -> None:
        """Description is derived from function name when no docstring."""
        test_file = tmp_path / "test_name.py"
        test_file.write_text("def test_data_validation():\n    assert True\n")

        harvester = TestHarvester(project_name="nm")
        tasks = harvester.extract_tests(tmp_path)

        assert tasks[0].description == "Test that data validation"

    def test_empty_repo(self, tmp_path: Path) -> None:
        """Empty repository produces no tasks."""
        harvester = TestHarvester(project_name="empty")
        tasks = harvester.extract_tests(tmp_path)
        assert tasks == []

    def test_non_test_functions_ignored(self, tmp_path: Path) -> None:
        """Functions not starting with test_ are skipped."""
        test_file = tmp_path / "test_mixed.py"
        test_file.write_text(textwrap.dedent("""\
            def helper():
                return 42

            def test_actual():
                assert helper() == 42
        """))

        harvester = TestHarvester(project_name="mix")
        tasks = harvester.extract_tests(tmp_path)

        assert len(tasks) == 1
        assert tasks[0].subcategory == "actual"

    def test_metadata_has_lineno(self, tmp_path: Path) -> None:
        """Metadata includes line number information."""
        test_file = tmp_path / "test_meta.py"
        test_file.write_text("def test_first():\n    assert True\n")

        harvester = TestHarvester(project_name="m")
        tasks = harvester.extract_tests(tmp_path)

        assert "lineno" in tasks[0].metadata
        assert "end_lineno" in tasks[0].metadata
        assert tasks[0].metadata["lineno"] == 1

    def test_unique_task_ids(self, tmp_path: Path) -> None:
        """Each task gets a unique ID."""
        test_file = tmp_path / "test_ids.py"
        test_file.write_text(textwrap.dedent("""\
            def test_a():
                assert True

            def test_b():
                assert True
        """))

        harvester = TestHarvester(project_name="ids")
        tasks = harvester.extract_tests(tmp_path)

        ids = [t.id for t in tasks]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Categorizer - Taxonomy Building
# ---------------------------------------------------------------------------


class TestCategorizer:
    """Tests for the Categorizer.build_taxonomy method."""

    def test_build_taxonomy_basic(self) -> None:
        """Build taxonomy from tasks with distinct categories."""
        tasks = [
            _make_task(id="t1", category="linear_model.ridge"),
            _make_task(id="t2", category="linear_model.lasso"),
            _make_task(id="t3", category="tree.decision"),
        ]
        cat = Categorizer()
        taxonomy = cat.build_taxonomy(tasks)

        assert taxonomy.total_tasks == 3
        assert taxonomy.total_categories == 3
        assert "linear_model" in taxonomy.roots
        assert "tree" in taxonomy.roots

    def test_taxonomy_counts(self) -> None:
        """Root node counts reflect all tasks in subtree."""
        tasks = [
            _make_task(id="t1", category="a.b"),
            _make_task(id="t2", category="a.c"),
            _make_task(id="t3", category="a.b"),
        ]
        cat = Categorizer()
        taxonomy = cat.build_taxonomy(tasks)

        assert taxonomy.roots["a"].count == 3
        assert taxonomy.roots["a"].children["b"].count == 2
        assert taxonomy.roots["a"].children["c"].count == 1

    def test_nested_categories(self) -> None:
        """Deep nesting creates corresponding tree depth."""
        tasks = [_make_task(id="t1", category="a.b.c.d")]
        cat = Categorizer()
        taxonomy = cat.build_taxonomy(tasks)

        node = taxonomy.roots["a"]
        assert node.count == 1
        node = node.children["b"]
        assert node.count == 1
        node = node.children["c"]
        assert node.count == 1
        node = node.children["d"]
        assert node.count == 1

    def test_empty_task_list(self) -> None:
        """Empty input produces empty taxonomy."""
        cat = Categorizer()
        taxonomy = cat.build_taxonomy([])

        assert taxonomy.total_tasks == 0
        assert taxonomy.total_categories == 0
        assert taxonomy.roots == {}

    def test_single_category(self) -> None:
        """All tasks in one category."""
        tasks = [
            _make_task(id=f"t{i}", category="only") for i in range(5)
        ]
        cat = Categorizer()
        taxonomy = cat.build_taxonomy(tasks)

        assert taxonomy.total_tasks == 5
        assert taxonomy.total_categories == 1
        assert taxonomy.roots["only"].count == 5


# ---------------------------------------------------------------------------
# Categorizer - Stratified Sampling
# ---------------------------------------------------------------------------


class TestStratifiedSampling:
    """Tests for the Categorizer.stratified_sample method."""

    def test_proportional_sampling(self) -> None:
        """Sampling respects category proportions approximately."""
        tasks = (
            [_make_task(id=f"a-{i}", category="big") for i in range(80)]
            + [_make_task(id=f"b-{i}", category="small") for i in range(20)]
        )
        cat = Categorizer()
        sample = cat.stratified_sample(tasks, n=10, seed=42)

        assert len(sample) == 10
        cats = [t.category for t in sample]
        # Both categories should be represented
        assert "big" in cats
        assert "small" in cats

    def test_minimum_one_per_category(self) -> None:
        """Every category gets at least one representative."""
        tasks = [
            _make_task(id=f"c{i}-0", category=f"cat{i}") for i in range(5)
        ]
        cat = Categorizer()
        sample = cat.stratified_sample(tasks, n=5, seed=42)

        cats = {t.category for t in sample}
        assert len(cats) == 5

    def test_sample_n_exceeds_total(self) -> None:
        """When n >= len(tasks), return all tasks."""
        tasks = [_make_task(id=f"t{i}", category="x") for i in range(3)]
        cat = Categorizer()
        sample = cat.stratified_sample(tasks, n=10, seed=42)

        assert len(sample) == 3

    def test_seed_reproducibility(self) -> None:
        """Same seed produces same sample."""
        tasks = [
            _make_task(id=f"t{i}", category=f"c{i % 3}") for i in range(30)
        ]
        cat = Categorizer()
        s1 = cat.stratified_sample(tasks, n=10, seed=123)
        s2 = cat.stratified_sample(tasks, n=10, seed=123)

        assert [t.id for t in s1] == [t.id for t in s2]

    def test_fewer_slots_than_categories(self) -> None:
        """When n < num_categories, pick n random categories."""
        tasks = [
            _make_task(id=f"t{i}", category=f"cat{i}") for i in range(10)
        ]
        cat = Categorizer()
        sample = cat.stratified_sample(tasks, n=3, seed=42)

        assert len(sample) == 3
        cats = {t.category for t in sample}
        assert len(cats) == 3

    def test_sample_single_task(self) -> None:
        """Sampling n=1 returns exactly one task."""
        tasks = [_make_task(id=f"t{i}", category="a") for i in range(5)]
        cat = Categorizer()
        sample = cat.stratified_sample(tasks, n=1, seed=42)

        assert len(sample) == 1

    def test_sample_with_many_categories(self) -> None:
        """Stress test: many categories, small sample."""
        tasks = [
            _make_task(id=f"t{i}", category=f"cat{i}") for i in range(100)
        ]
        cat = Categorizer()
        sample = cat.stratified_sample(tasks, n=20, seed=42)

        assert len(sample) == 20
        cats = {t.category for t in sample}
        assert len(cats) == 20


# ---------------------------------------------------------------------------
# TestFilter
# ---------------------------------------------------------------------------


class TestTestFilter:
    """Tests for the TestFilter class."""

    def test_trivial_filter_removes_short(self) -> None:
        """Tests below min_loc are removed."""
        task = _make_task(loc=5, test_code="def test_x():\n    assert True")
        f = TestFilter(min_loc=10, require_assertions=False, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert result == []

    def test_trivial_filter_keeps_long(self) -> None:
        """Tests at or above min_loc are kept."""
        task = _make_task(loc=15, test_code="def test_x():\n    assert True")
        f = TestFilter(min_loc=10, require_assertions=False, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_assertion_filter_removes_no_assert(self) -> None:
        """Tests without assertions are removed."""
        task = _make_task(loc=20, test_code="def test_x():\n    x = 1\n    y = 2")
        f = TestFilter(min_loc=1, require_assertions=True, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert result == []

    def test_assertion_filter_keeps_assert(self) -> None:
        """Tests with assert keyword pass the filter."""
        task = _make_task(loc=20, test_code="def test_x():\n    assert 1 == 1")
        f = TestFilter(min_loc=1, require_assertions=True, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_assertion_filter_unittest_style(self) -> None:
        """Tests with assertEqual pass the filter."""
        task = _make_task(loc=20, test_code="def test_x(self):\n    self.assertEqual(1, 1)")
        f = TestFilter(min_loc=1, require_assertions=True, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_assertion_filter_pytest_raises(self) -> None:
        """Tests with pytest.raises pass the filter."""
        task = _make_task(loc=20, test_code="def test_x():\n    with pytest.raises(ValueError):\n        pass")
        f = TestFilter(min_loc=1, require_assertions=True, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_flaky_pattern_requests(self) -> None:
        """Tests using requests.get are flagged as flaky."""
        task = _make_task(loc=20, test_code="def test_x():\n    r = requests.get('http://example.com')")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=True, filter_skipped=False)
        result = f.filter_tasks([task])
        assert result == []

    def test_flaky_pattern_subprocess(self) -> None:
        """Tests using subprocess are flagged as flaky."""
        task = _make_task(loc=20, test_code="def test_x():\n    subprocess.run(['ls'])")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=True, filter_skipped=False)
        result = f.filter_tasks([task])
        assert result == []

    def test_flaky_pattern_sleep(self) -> None:
        """Tests using time.sleep are flagged as flaky."""
        task = _make_task(loc=20, test_code="def test_x():\n    time.sleep(1)")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=True, filter_skipped=False)
        result = f.filter_tasks([task])
        assert result == []

    def test_clean_code_not_flaky(self) -> None:
        """Tests without IO patterns pass flaky filter."""
        task = _make_task(loc=20, test_code="def test_x():\n    assert 1 + 1 == 2")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=True, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_skip_decorator_bare(self) -> None:
        """Tests with @skip are removed."""
        task = _make_task(loc=20, test_code="@skip\ndef test_x():\n    assert True")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=True)
        result = f.filter_tasks([task])
        assert result == []

    def test_skip_decorator_pytest_mark(self) -> None:
        """Tests with @pytest.mark.skip are removed."""
        task = _make_task(loc=20, test_code="@pytest.mark.skip\ndef test_x():\n    assert True")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=True)
        result = f.filter_tasks([task])
        assert result == []

    def test_skip_decorator_xfail(self) -> None:
        """Tests with @xfail are removed."""
        task = _make_task(loc=20, test_code="@xfail\ndef test_x():\n    assert True")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=True)
        result = f.filter_tasks([task])
        assert result == []

    def test_no_skip_decorator_passes(self) -> None:
        """Tests without skip decorators pass the filter."""
        task = _make_task(loc=20, test_code="def test_x():\n    assert True")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=True)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_combined_filter_pipeline(self) -> None:
        """All filters applied together."""
        tasks = [
            _make_task(id="t1", loc=5, test_code="def test_short():\n    assert True"),
            _make_task(id="t2", loc=20, test_code="def test_no_assert():\n    x = 1"),
            _make_task(id="t3", loc=20, test_code="def test_flaky():\n    requests.get('url')\n    assert True"),
            _make_task(id="t4", loc=20, test_code="@skip\ndef test_skip():\n    assert True"),
            _make_task(id="t5", loc=20, test_code="def test_good():\n    assert 1 == 1"),
        ]
        f = TestFilter(min_loc=10, require_assertions=True, filter_flaky=True, filter_skipped=True)
        result = f.filter_tasks(tasks)

        assert len(result) == 1
        assert result[0].id == "t5"

    def test_all_tasks_pass(self) -> None:
        """When all tasks are clean, nothing is removed."""
        tasks = [
            _make_task(id=f"t{i}", loc=20, test_code="def test_x():\n    assert True")
            for i in range(5)
        ]
        f = TestFilter(min_loc=1, require_assertions=True, filter_flaky=True, filter_skipped=True)
        result = f.filter_tasks(tasks)

        assert len(result) == 5

    def test_all_tasks_removed(self) -> None:
        """When no tasks pass, result is empty."""
        tasks = [
            _make_task(id=f"t{i}", loc=2, test_code="def test_x():\n    pass")
            for i in range(5)
        ]
        f = TestFilter(min_loc=10)
        result = f.filter_tasks(tasks)

        assert result == []

    def test_custom_min_loc(self) -> None:
        """Custom min_loc threshold is respected."""
        task = _make_task(loc=25, test_code="def test_x():\n    assert True")
        f = TestFilter(min_loc=30, require_assertions=False, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert result == []

    def test_disabled_assertion_filter(self) -> None:
        """With require_assertions=False, tests without asserts pass."""
        task = _make_task(loc=20, test_code="def test_x():\n    x = 1")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_disabled_flaky_filter(self) -> None:
        """With filter_flaky=False, IO tests pass."""
        task = _make_task(loc=20, test_code="def test_x():\n    requests.get('url')")
        f = TestFilter(min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_is_trivial_boundary(self) -> None:
        """Boundary: loc == min_loc should NOT be trivial."""
        f = TestFilter(min_loc=10)
        assert f.is_trivial(_make_task(loc=10)) is False
        assert f.is_trivial(_make_task(loc=9)) is True

    def test_has_assertions_assertIn(self) -> None:
        """Detects assertIn as an assertion."""
        task = _make_task(test_code="def test_x(self):\n    self.assertIn(1, [1, 2])")
        f = TestFilter()
        assert f.has_assertions(task) is True

    def test_empty_task_list(self) -> None:
        """Filtering empty list returns empty list."""
        f = TestFilter()
        result = f.filter_tasks([])
        assert result == []
