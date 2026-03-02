"""AST-based test harvester for the RepoCraft benchmark pipeline.

Traverses a Python repository, locates all test files, parses test
functions using the AST, and emits :class:`BenchmarkTask` instances
suitable for inclusion in the RepoCraft benchmark suite.
"""

from __future__ import annotations

import ast
import logging
import textwrap
from pathlib import Path
from typing import Any

from cobuilder.repomap.evaluation.models import BenchmarkTask, DifficultyLevel

logger = logging.getLogger(__name__)

# Difficulty thresholds (non-blank, non-comment LOC).
_EASY_MAX = 15
_MEDIUM_MAX = 40


class TestHarvester:
    """Extract :class:`BenchmarkTask` objects from a Python repository.

    The harvester performs a recursive scan of the repository looking for
    files that match the ``test_*.py`` glob pattern, parses them with the
    standard ``ast`` module, and emits one task per ``test_`` function.

    Args:
        project_name: Name of the source project (e.g. ``"scikit-learn"``).
            Used as prefix for generated task IDs.
    """

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name
        self._counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_tests(self, repo_path: Path) -> list[BenchmarkTask]:
        """Recursively harvest test functions from *repo_path*.

        Args:
            repo_path: Root of the repository to scan.

        Returns:
            A list of :class:`BenchmarkTask` instances, one per
            ``test_`` function found.  Files with syntax errors are
            skipped silently.
        """
        self._counter = 0
        tasks: list[BenchmarkTask] = []

        for test_file in sorted(repo_path.rglob("test_*.py")):
            tasks.extend(self._process_file(test_file, repo_path))

        return tasks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_file(
        self,
        file_path: Path,
        repo_root: Path,
    ) -> list[BenchmarkTask]:
        """Parse a single test file and emit tasks for each test function.

        Syntax errors are caught and logged; the file is then skipped.
        """
        source = file_path.read_text(encoding="utf-8", errors="replace")

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            logger.warning("Skipping %s due to SyntaxError: %s", file_path, exc)
            return []

        # Collect file-level imports.
        file_imports = _collect_file_imports(tree, source)
        category = self._path_to_category(file_path, repo_root)
        rel_path = str(file_path.relative_to(repo_root))

        tasks: list[BenchmarkTask] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue

            task = self._parse_test_function(
                node=node,
                source=source,
                file_path=rel_path,
                category=category,
                file_imports=file_imports,
            )
            if task is not None:
                tasks.append(task)

        return tasks

    def _parse_test_function(
        self,
        node: ast.FunctionDef,
        source: str,
        file_path: str,
        category: str,
        file_imports: list[str],
    ) -> BenchmarkTask | None:
        """Build a :class:`BenchmarkTask` from a single AST function node."""
        func_source = _extract_source(node, source)
        if not func_source:
            return None

        subcategory = node.name[len("test_"):]  # strip "test_" prefix
        description = _extract_description(node, source)
        loc = _count_loc(func_source)
        difficulty = _estimate_difficulty(loc)
        func_imports = _collect_function_imports(node, source)
        all_imports = _merge_imports(file_imports, func_imports)
        has_assertions = _has_assertions(node, source)

        self._counter += 1
        task_id = f"{self.project_name}-{subcategory}-{self._counter:03d}"

        return BenchmarkTask(
            id=task_id,
            project=self.project_name,
            category=category,
            subcategory=subcategory,
            description=description,
            test_code=func_source,
            imports=all_imports,
            loc=loc,
            difficulty=difficulty,
            metadata={
                "file_path": file_path,
                "has_assertions": has_assertions,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
            },
        )

    def _path_to_category(self, file_path: Path, repo_root: Path) -> str:
        """Derive a dotted category string from the file path.

        Examples:
            ``tests/test_basic.py`` → ``"basic"``
            ``tests/linear_model/test_ridge.py`` → ``"linear_model.ridge"``
        """
        rel = file_path.relative_to(repo_root)
        parts = list(rel.parts)

        # Strip the leading 'tests' directory if present.
        if parts and parts[0] == "tests":
            parts = parts[1:]

        # Strip all intermediate 'tests' directories (shouldn't normally happen
        # but handle defensively).
        parts = [p for p in parts[:-1] if p != "tests"] + (parts[-1:] if parts else [])

        if not parts:
            return "unknown"

        # Build the dotted path.  The last element is the filename.
        filename = parts[-1]
        # Remove .py extension.
        if filename.endswith(".py"):
            filename = filename[:-3]
        # Remove leading 'test_' prefix from filename.
        if filename.startswith("test_"):
            filename = filename[len("test_"):]

        category_parts = parts[:-1] + [filename]
        return ".".join(category_parts)


# ---------------------------------------------------------------------------
# Module-level pure helper functions
# ---------------------------------------------------------------------------


def _extract_source(node: ast.FunctionDef, source: str) -> str:
    """Extract raw source lines for a function node and dedent them.

    Includes any decorator lines that appear before the ``def`` keyword.
    """
    lines = source.splitlines(keepends=True)

    # Determine the start line: use the first decorator if any, else the def line.
    if node.decorator_list:
        start = node.decorator_list[0].lineno - 1  # 0-based
    else:
        start = node.lineno - 1  # 0-based

    end = getattr(node, "end_lineno", None)

    if end is not None:
        func_lines = lines[start:end]
    else:
        # Fallback: scan until indent drops back to 0.
        func_lines = []
        for line in lines[start:]:
            func_lines.append(line)
            if func_lines and line and not line[0].isspace() and len(func_lines) > 1:
                break

    return textwrap.dedent("".join(func_lines))


def _extract_description(node: ast.FunctionDef, source: str) -> str:
    """Return the first docstring line, or a human-readable fallback."""
    docstring = ast.get_docstring(node)
    if docstring:
        return docstring.splitlines()[0].strip()

    # Build description from function name: "test_data_validation" →
    # "Test that data validation"
    name_without_prefix = node.name[len("test_"):] if node.name.startswith("test_") else node.name
    readable = name_without_prefix.replace("_", " ")
    return f"Test that {readable}"


def _count_loc(source: str) -> int:
    """Count non-blank, non-comment lines in *source*."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _estimate_difficulty(loc: int) -> DifficultyLevel:
    """Map a LOC count to a :class:`DifficultyLevel`."""
    if loc < _EASY_MAX:
        return DifficultyLevel.EASY
    if loc < _MEDIUM_MAX:
        return DifficultyLevel.MEDIUM
    return DifficultyLevel.HARD


def _collect_file_imports(tree: ast.Module, source: str) -> list[str]:
    """Return import strings for all module-level imports."""
    imports: list[str] = []
    lines = source.splitlines()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    imports.append(f"import {alias.name} as {alias.asname}")
                else:
                    imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(
                f"{a.name} as {a.asname}" if a.asname else a.name
                for a in node.names
            )
            imports.append(f"from {module} import {names}")

    return imports


def _collect_function_imports(node: ast.FunctionDef, source: str) -> list[str]:
    """Return import strings for imports inside a function body."""
    imports: list[str] = []

    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, ast.Import):
            for alias in child.names:
                if alias.asname:
                    imports.append(f"import {alias.name} as {alias.asname}")
                else:
                    imports.append(f"import {alias.name}")
        elif isinstance(child, ast.ImportFrom):
            module = child.module or ""
            names = ", ".join(
                f"{a.name} as {a.asname}" if a.asname else a.name
                for a in child.names
            )
            imports.append(f"from {module} import {names}")

    return imports


def _merge_imports(file_imports: list[str], func_imports: list[str]) -> list[str]:
    """Combine and deduplicate import lists preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for imp in file_imports + func_imports:
        if imp not in seen:
            seen.add(imp)
            result.append(imp)
    return result


def _has_assertions(node: ast.FunctionDef, source: str) -> bool:
    """Return True if the function contains any assertion-like construct."""
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        # self.assertXxx(...) and pytest.raises(...)
        if isinstance(child, ast.Attribute):
            if child.attr.startswith("assert") or child.attr == "raises":
                return True
    return False
