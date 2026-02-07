"""Test harvesting module for RepoCraft benchmark construction.

Extracts test functions from Python repositories using AST parsing,
categorizes them hierarchically, and produces BenchmarkTask objects.
"""

from __future__ import annotations

import ast
import logging
import textwrap
from pathlib import Path
from typing import Any

from zerorepo.evaluation.models import BenchmarkTask, DifficultyLevel

logger = logging.getLogger(__name__)


class TestHarvester:
    """Extracts test functions from pytest/unittest codebases using AST.

    Walks a repository directory, parses ``test_*.py`` files with the
    :mod:`ast` module, and produces :class:`BenchmarkTask` instances for
    every ``test_*`` function found.

    Args:
        project_name: Human-readable name of the project being harvested.
    """

    def __init__(self, project_name: str = "") -> None:
        self.project_name = project_name
        self._task_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_tests(self, repo_path: str | Path) -> list[BenchmarkTask]:
        """Extract all test functions from test files in *repo_path*.

        Walks *repo_path* looking for ``test_*.py`` files, parses each
        with :func:`ast.parse`, and collects every
        :class:`ast.FunctionDef` whose name starts with ``test_``.

        Returns:
            A list of :class:`BenchmarkTask` instances, one per test
            function found.
        """
        repo_path = Path(repo_path)
        tasks: list[BenchmarkTask] = []

        for test_file in sorted(repo_path.rglob("test_*.py")):
            try:
                source = test_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(test_file))
            except (SyntaxError, UnicodeDecodeError) as exc:
                logger.warning("Skipping %s: %s", test_file, exc)
                continue

            # Determine category from file path relative to repo root.
            rel_path = test_file.relative_to(repo_path)
            category = self._path_to_category(rel_path)

            # Collect file-level imports for later injection.
            file_imports = self._extract_file_imports(tree)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    task = self._parse_test_function(
                        node, source, category, file_imports, str(rel_path)
                    )
                    if task is not None:
                        tasks.append(task)

        logger.info("Extracted %d tests from %s", len(tasks), repo_path)
        return tasks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_test_function(
        self,
        node: ast.FunctionDef,
        source: str,
        category: str,
        file_imports: list[str],
        file_path: str,
    ) -> BenchmarkTask | None:
        """Parse an AST :class:`ast.FunctionDef` into a :class:`BenchmarkTask`."""
        try:
            # Extract source code for this function, including decorators.
            source_lines = source.splitlines()
            start_line = node.lineno
            if node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)
            func_lines = source_lines[start_line - 1 : node.end_lineno]
            test_code = "\n".join(func_lines)

            # LOC = non-empty, non-comment lines.
            loc = sum(
                1
                for line in func_lines
                if line.strip() and not line.strip().startswith("#")
            )

            # Extract docstring.
            docstring = ast.get_docstring(node) or ""

            # Generate a human-readable description.
            if docstring:
                description = docstring.split("\n")[0]
            else:
                description = self._name_to_description(node.name)

            # Assertion detection.
            has_assertions = self._has_assertions(node)

            # Merge file-level and function-local imports.
            func_imports = self._extract_function_imports(node)
            all_imports = file_imports + func_imports

            # Difficulty heuristic.
            difficulty = self._estimate_difficulty(loc, node)

            # Unique task identifier.
            self._task_counter += 1
            subcategory = node.name.replace("test_", "", 1)
            task_id = (
                f"{self.project_name}-"
                f"{category.replace('.', '_')}-"
                f"{subcategory}-"
                f"{self._task_counter:03d}"
            )

            return BenchmarkTask(
                id=task_id,
                project=self.project_name,
                category=category,
                subcategory=subcategory,
                description=description,
                test_code=test_code,
                imports=all_imports,
                loc=loc,
                difficulty=difficulty,
                metadata={
                    "file_path": file_path,
                    "has_assertions": has_assertions,
                    "lineno": node.lineno,
                    "end_lineno": node.end_lineno or node.lineno,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error parsing %s: %s", node.name, exc)
            return None

    def _path_to_category(self, rel_path: Path) -> str:
        """Convert a file path to a dotted category string.

        Example::

            tests/linear_model/test_ridge.py  ->  linear_model.ridge
        """
        parts = list(rel_path.parts)
        # Strip leading ``tests`` / ``test`` directory components.
        while parts and parts[0] in ("tests", "test"):
            parts.pop(0)
        # Replace the filename with its stem minus the ``test_`` prefix.
        if parts:
            filename = parts.pop()
            stem = Path(filename).stem
            if stem.startswith("test_"):
                stem = stem[5:]
            parts.append(stem)
        return ".".join(parts) if parts else "uncategorized"

    def _extract_file_imports(self, tree: ast.Module) -> list[str]:
        """Return top-level import statements from an AST module."""
        imports: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(a.name for a in node.names)
                imports.append(f"from {module} import {names}")
        return imports

    def _extract_function_imports(self, func_node: ast.FunctionDef) -> list[str]:
        """Return import statements found inside a function body."""
        imports: list[str] = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(a.name for a in node.names)
                imports.append(f"from {module} import {names}")
        return imports

    def _has_assertions(self, node: ast.FunctionDef) -> bool:
        """Return ``True`` if the function contains any assertion statements."""
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                return True
            # Detect unittest-style ``self.assertXxx(...)`` calls.
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr.startswith(
                    (
                        "assert",
                        "assertEqual",
                        "assertTrue",
                        "assertFalse",
                        "assertRaises",
                        "assertIn",
                    )
                ):
                    return True
        return False

    def _name_to_description(self, name: str) -> str:
        """Convert a ``test_*`` function name to a natural-language description."""
        desc = name.replace("test_", "", 1).replace("_", " ")
        return f"Test that {desc}"

    def _estimate_difficulty(
        self, loc: int, node: ast.FunctionDef
    ) -> DifficultyLevel:
        """Estimate difficulty from LOC count and AST complexity."""
        if loc < 15:
            return DifficultyLevel.EASY
        elif loc < 40:
            return DifficultyLevel.MEDIUM
        else:
            return DifficultyLevel.HARD
