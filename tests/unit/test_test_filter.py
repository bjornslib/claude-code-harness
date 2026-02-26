"""Unit tests for the TestFilter class (bead bsh).

Tests cover:
- Trivial test detection (LOC threshold)
- Assertion detection (pytest-style, unittest-style, pytest.raises)
- Flaky test detection (external I/O patterns)
- Skip decorator detection
- Full filter pipeline with combined rules
- Edge cases and configuration overrides
"""

from __future__ import annotations

import pytest

from cobuilder.repomap.evaluation.models import BenchmarkTask, DifficultyLevel
from cobuilder.repomap.evaluation.test_filter import FLAKY_PATTERNS, SKIP_DECORATORS, TestFilter


def _make_task(
    test_code: str = "def test_x():\n    assert True",
    loc: int = 15,
    **kwargs: object,
) -> BenchmarkTask:
    """Helper to create a BenchmarkTask with sensible defaults."""
    return BenchmarkTask(
        id=kwargs.get("id", "proj-cat-sub-001"),
        project=kwargs.get("project", "test-project"),
        category=kwargs.get("category", "test.category"),
        description=kwargs.get("description", "A test"),
        test_code=test_code,
        loc=loc,
        difficulty=kwargs.get("difficulty", DifficultyLevel.MEDIUM),
    )


# ---------------------------------------------------------------------------
# Trivial test detection
# ---------------------------------------------------------------------------


class TestIsTrivial:
    """Tests for the is_trivial() predicate."""

    def test_below_threshold_is_trivial(self) -> None:
        """Tasks with LOC < min_loc should be trivial."""
        f = TestFilter(min_loc=10)
        task = _make_task(loc=5)
        assert f.is_trivial(task) is True

    def test_at_threshold_not_trivial(self) -> None:
        """Tasks with LOC == min_loc should NOT be trivial."""
        f = TestFilter(min_loc=10)
        task = _make_task(loc=10)
        assert f.is_trivial(task) is False

    def test_above_threshold_not_trivial(self) -> None:
        """Tasks with LOC > min_loc should NOT be trivial."""
        f = TestFilter(min_loc=10)
        task = _make_task(loc=50)
        assert f.is_trivial(task) is False

    def test_custom_threshold(self) -> None:
        """Custom min_loc threshold should be respected."""
        f = TestFilter(min_loc=20)
        assert f.is_trivial(_make_task(loc=15)) is True
        assert f.is_trivial(_make_task(loc=25)) is False

    def test_zero_loc(self) -> None:
        """Zero LOC should always be trivial."""
        f = TestFilter(min_loc=1)
        task = _make_task(loc=0)
        assert f.is_trivial(task) is True


# ---------------------------------------------------------------------------
# Assertion detection
# ---------------------------------------------------------------------------


class TestHasAssertions:
    """Tests for the has_assertions() predicate."""

    def test_pytest_assert(self) -> None:
        """Detect bare assert keyword."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    assert x == 1")
        assert f.has_assertions(task) is True

    def test_unittest_assertEqual(self) -> None:
        """Detect unittest-style assertEqual."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    self.assertEqual(1, 1)")
        assert f.has_assertions(task) is True

    def test_unittest_assertTrue(self) -> None:
        """Detect unittest-style assertTrue."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    self.assertTrue(True)")
        assert f.has_assertions(task) is True

    def test_unittest_assertRaises(self) -> None:
        """Detect unittest-style assertRaises."""
        f = TestFilter()
        task = _make_task(
            test_code="def test_x():\n    with self.assertRaises(ValueError):\n        pass"
        )
        assert f.has_assertions(task) is True

    def test_unittest_assertIn(self) -> None:
        """Detect unittest-style assertIn."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    self.assertIn(1, [1, 2])")
        assert f.has_assertions(task) is True

    def test_pytest_raises(self) -> None:
        """Detect pytest.raises context manager."""
        f = TestFilter()
        task = _make_task(
            test_code="def test_x():\n    with pytest.raises(ValueError):\n        pass"
        )
        assert f.has_assertions(task) is True

    def test_no_assertions(self) -> None:
        """Code without any assertion should return False."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    x = 1 + 1\n    print(x)")
        assert f.has_assertions(task) is False

    def test_assert_in_comment_still_matches(self) -> None:
        """Regex-based detection may match 'assert' even in comments.

        This is a known limitation - the filter uses regex, not AST.
        """
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    # assert this works\n    pass")
        # Regex picks up 'assert' in comment - this is expected behaviour
        assert f.has_assertions(task) is True


# ---------------------------------------------------------------------------
# Flaky test detection
# ---------------------------------------------------------------------------


class TestIsFlaky:
    """Tests for the is_flaky() predicate."""

    def test_requests_get_is_flaky(self) -> None:
        """Code using requests.get should be flagged."""
        f = TestFilter()
        task = _make_task(
            test_code="def test_x():\n    resp = requests.get('http://example.com')"
        )
        assert f.is_flaky(task) is True

    def test_socket_is_flaky(self) -> None:
        """Code using socket should be flagged."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    s = socket.socket()")
        assert f.is_flaky(task) is True

    def test_time_sleep_is_flaky(self) -> None:
        """Code using time.sleep should be flagged."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    time.sleep(1)")
        assert f.is_flaky(task) is True

    def test_subprocess_is_flaky(self) -> None:
        """Code using subprocess should be flagged."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    subprocess.run(['ls'])")
        assert f.is_flaky(task) is True

    def test_open_is_flaky(self) -> None:
        """Code using open() should be flagged."""
        f = TestFilter()
        task = _make_task(
            test_code="def test_x():\n    with open('file.txt') as f:\n        pass"
        )
        assert f.is_flaky(task) is True

    def test_clean_code_not_flaky(self) -> None:
        """Pure computation code should NOT be flagged."""
        f = TestFilter()
        task = _make_task(
            test_code="def test_x():\n    result = 1 + 1\n    assert result == 2"
        )
        assert f.is_flaky(task) is False

    def test_tempfile_is_flaky(self) -> None:
        """Code using tempfile should be flagged."""
        f = TestFilter()
        task = _make_task(
            test_code="def test_x():\n    tmpdir = tempfile.mkdtemp()"
        )
        assert f.is_flaky(task) is True


# ---------------------------------------------------------------------------
# Skip decorator detection
# ---------------------------------------------------------------------------


class TestIsSkipped:
    """Tests for the is_skipped() predicate."""

    def test_pytest_mark_skip(self) -> None:
        """@pytest.mark.skip should be detected."""
        f = TestFilter()
        task = _make_task(
            test_code="@pytest.mark.skip\ndef test_x():\n    pass"
        )
        assert f.is_skipped(task) is True

    def test_pytest_mark_skipIf(self) -> None:
        """@pytest.mark.skipIf should be detected."""
        f = TestFilter()
        task = _make_task(
            test_code="@pytest.mark.skipIf\ndef test_x():\n    pass"
        )
        assert f.is_skipped(task) is True

    def test_xfail_detected(self) -> None:
        """@xfail decorator should be detected."""
        f = TestFilter()
        task = _make_task(
            test_code="@xfail\ndef test_x():\n    pass"
        )
        assert f.is_skipped(task) is True

    def test_no_skip_decorator(self) -> None:
        """Normal test should not be flagged as skipped."""
        f = TestFilter()
        task = _make_task(test_code="def test_x():\n    assert True")
        assert f.is_skipped(task) is False


# ---------------------------------------------------------------------------
# Full filter pipeline
# ---------------------------------------------------------------------------


class TestFilterPipeline:
    """Tests for the filter_tasks() pipeline method."""

    def test_all_filters_pass(self) -> None:
        """Good tasks should survive the full pipeline."""
        f = TestFilter(min_loc=5)
        task = _make_task(
            test_code="def test_x():\n    result = compute()\n    assert result == 42",
            loc=15,
        )
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_trivial_removed(self) -> None:
        """Trivial tasks should be removed."""
        f = TestFilter(min_loc=10)
        task = _make_task(loc=3)
        result = f.filter_tasks([task])
        assert len(result) == 0

    def test_no_assertions_removed(self) -> None:
        """Tasks without assertions should be removed when required."""
        f = TestFilter(min_loc=5, require_assertions=True)
        task = _make_task(
            test_code="def test_x():\n    x = 1\n    print(x)",
            loc=15,
        )
        result = f.filter_tasks([task])
        assert len(result) == 0

    def test_flaky_removed(self) -> None:
        """Flaky tasks should be removed."""
        f = TestFilter(min_loc=5, filter_flaky=True)
        task = _make_task(
            test_code="def test_x():\n    resp = requests.get('url')\n    assert resp.ok",
            loc=15,
        )
        result = f.filter_tasks([task])
        assert len(result) == 0

    def test_skipped_removed(self) -> None:
        """Skipped tasks should be removed."""
        f = TestFilter(min_loc=5, filter_skipped=True)
        task = _make_task(
            test_code="@pytest.mark.skip\ndef test_x():\n    assert True",
            loc=15,
        )
        result = f.filter_tasks([task])
        assert len(result) == 0

    def test_mixed_batch(self) -> None:
        """A mixed batch should only keep valid tasks."""
        f = TestFilter(min_loc=5, require_assertions=True)
        tasks = [
            _make_task(
                id="proj-cat-good-001",
                test_code="def test_good():\n    assert True",
                loc=15,
            ),
            _make_task(id="proj-cat-trivial-002", loc=2),
            _make_task(
                id="proj-cat-no_assert-003",
                test_code="def test_no_assert():\n    print('hi')",
                loc=15,
            ),
            _make_task(
                id="proj-cat-flaky-004",
                test_code="def test_flaky():\n    requests.get('url')\n    assert True",
                loc=15,
            ),
        ]
        result = f.filter_tasks(tasks)
        assert len(result) == 1
        assert result[0].id == "proj-cat-good-001"

    def test_disable_assertion_filter(self) -> None:
        """Disabling require_assertions should keep assertion-free tasks."""
        f = TestFilter(min_loc=5, require_assertions=False)
        task = _make_task(
            test_code="def test_x():\n    x = 1\n    print(x)",
            loc=15,
        )
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_disable_flaky_filter(self) -> None:
        """Disabling filter_flaky should keep IO-heavy tasks."""
        f = TestFilter(min_loc=5, filter_flaky=False)
        task = _make_task(
            test_code="def test_x():\n    resp = requests.get('url')\n    assert resp.ok",
            loc=15,
        )
        result = f.filter_tasks([task])
        assert len(result) == 1

    def test_empty_input(self) -> None:
        """Empty input should return empty output."""
        f = TestFilter()
        assert f.filter_tasks([]) == []

    def test_all_removed(self) -> None:
        """When all tasks are filtered, return empty list."""
        f = TestFilter(min_loc=100)
        tasks = [_make_task(loc=5) for _ in range(10)]
        assert f.filter_tasks(tasks) == []


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestFilterConstants:
    """Tests for module-level constants."""

    def test_flaky_patterns_populated(self) -> None:
        """FLAKY_PATTERNS should have multiple patterns."""
        assert len(FLAKY_PATTERNS) >= 5

    def test_skip_decorators_populated(self) -> None:
        """SKIP_DECORATORS should contain common skip markers."""
        assert "skip" in SKIP_DECORATORS
        assert "xfail" in SKIP_DECORATORS
        assert "skipIf" in SKIP_DECORATORS
