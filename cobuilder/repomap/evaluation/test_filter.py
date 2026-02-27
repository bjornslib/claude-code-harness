"""Test filtering pipeline for RepoCraft benchmark construction.

Removes trivial, flaky, and skipped tests to ensure benchmark quality.
Each filter is independently configurable so callers can tune the
trade-off between inclusiveness and signal-to-noise ratio.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from cobuilder.repomap.evaluation.models import BenchmarkTask

logger = logging.getLogger(__name__)

# Regex patterns indicating external / non-deterministic dependencies.
FLAKY_PATTERNS: list[str] = [
    r"requests\.get",
    r"requests\.post",
    r"urllib\.request",
    r"socket\.",
    r"time\.sleep",
    r"open\s*\(",
    r"tempfile\.",
    r"subprocess\.",
    r"os\.system",
]

# Decorator names that indicate a test should be skipped.
SKIP_DECORATORS: set[str] = {
    "skip",
    "skipIf",
    "skipUnless",
    "xfail",
    "mark.skip",
}


class TestFilter:
    """Filters benchmark tasks to remove trivial, flaky, and skipped tests.

    Args:
        min_loc: Minimum non-empty LOC for a test to be kept.
        require_assertions: Drop tests that lack assertion statements.
        filter_flaky: Drop tests that reference external / IO patterns.
        filter_skipped: Drop tests that carry skip decorators.
    """

    def __init__(
        self,
        min_loc: int = 10,
        require_assertions: bool = True,
        filter_flaky: bool = True,
        filter_skipped: bool = True,
    ) -> None:
        self.min_loc = min_loc
        self.require_assertions = require_assertions
        self.filter_flaky = filter_flaky
        self.filter_skipped = filter_skipped
        self._flaky_re = [re.compile(p) for p in FLAKY_PATTERNS]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter_tasks(self, tasks: list[BenchmarkTask]) -> list[BenchmarkTask]:
        """Apply all enabled filters and return passing tasks.

        Args:
            tasks: Input benchmark tasks to filter.

        Returns:
            A list of tasks that survived every enabled filter.
        """
        original = len(tasks)
        result: list[BenchmarkTask] = []
        removed: dict[str, int] = {
            "trivial": 0,
            "no_assertions": 0,
            "flaky": 0,
            "skipped": 0,
        }

        for task in tasks:
            if self.is_trivial(task):
                removed["trivial"] += 1
                continue
            if self.require_assertions and not self.has_assertions(task):
                removed["no_assertions"] += 1
                continue
            if self.filter_flaky and self.is_flaky(task):
                removed["flaky"] += 1
                continue
            if self.filter_skipped and self.is_skipped(task):
                removed["skipped"] += 1
                continue
            result.append(task)

        logger.info(
            "Filtered %d -> %d tasks. Removed: %s",
            original,
            len(result),
            dict(removed),
        )
        return result

    # ------------------------------------------------------------------
    # Individual filter predicates
    # ------------------------------------------------------------------

    def is_trivial(self, task: BenchmarkTask) -> bool:
        """Return ``True`` if the task has fewer than *min_loc* lines."""
        return task.loc < self.min_loc

    def has_assertions(self, task: BenchmarkTask) -> bool:
        """Return ``True`` if the test code contains assertion statements."""
        code = task.test_code
        # ``assert`` keyword (pytest-style).
        if re.search(r"\bassert\b", code):
            return True
        # unittest-style ``self.assertXxx(...)`` calls.
        if re.search(
            r"\b(assertEqual|assertTrue|assertFalse|assertRaises"
            r"|assertIn|assertIsNone|assertIsNotNone|assertAlmostEqual)\b",
            code,
        ):
            return True
        # ``pytest.raises`` context manager.
        if "pytest.raises" in code:
            return True
        return False

    def is_flaky(self, task: BenchmarkTask) -> bool:
        """Return ``True`` if the test references external / IO patterns."""
        code = task.test_code
        return any(pattern.search(code) for pattern in self._flaky_re)

    def is_skipped(self, task: BenchmarkTask) -> bool:
        """Return ``True`` if the test carries a skip decorator."""
        code = task.test_code
        for decorator in SKIP_DECORATORS:
            if f"@{decorator}" in code or f"@pytest.mark.{decorator}" in code:
                return True
        return False
