"""Unit tests for CodebaseWalker.walk_paths() — F4.1.

Tests cover:
- Walking specific Python files returns exactly those nodes
- Missing paths are skipped (warning, no exception)
- Directory paths are walked recursively
- TypeScript/JS file paths produce COMPONENT nodes
- Node ID generation uses the same relative-path logic as walk()
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.serena.session import FileBasedCodebaseAnalyzer
from cobuilder.repomap.serena.walker import CodebaseWalker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def walker() -> CodebaseWalker:
    """Return a CodebaseWalker with a FileBasedCodebaseAnalyzer."""
    analyzer = FileBasedCodebaseAnalyzer()
    return CodebaseWalker(analyzer)


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    """Create a minimal Python project with 3 files in a package.

    Layout::

        tmp_path/
        └── mylib/
            ├── __init__.py
            ├── alpha.py   — contains class Alpha
            ├── beta.py    — contains def beta_fn
            └── gamma.py   — contains def gamma_fn
    """
    mylib = tmp_path / "mylib"
    mylib.mkdir()
    (mylib / "__init__.py").write_text('"""My library."""\n')
    (mylib / "alpha.py").write_text(
        textwrap.dedent("""\
        \"\"\"Alpha module.\"\"\"


        class Alpha:
            \"\"\"Alpha class.\"\"\"
            pass
        """)
    )
    (mylib / "beta.py").write_text(
        textwrap.dedent("""\
        \"\"\"Beta module.\"\"\"


        def beta_fn() -> str:
            \"\"\"Return beta.\"\"\"
            return "beta"
        """)
    )
    (mylib / "gamma.py").write_text(
        textwrap.dedent("""\
        \"\"\"Gamma module.\"\"\"


        def gamma_fn() -> str:
            \"\"\"Return gamma.\"\"\"
            return "gamma"
        """)
    )
    return tmp_path


@pytest.fixture
def ts_project(tmp_path: Path) -> Path:
    """Create a minimal TypeScript project directory.

    Layout::

        tmp_path/
        └── src/
            ├── App.tsx
            ├── index.ts
            └── utils.js
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export const App = () => <div>App</div>;")
    (src / "index.ts").write_text("export { App } from './App';")
    (src / "utils.js").write_text("export function noop() {}")
    return tmp_path


# ---------------------------------------------------------------------------
# TestWalkPaths
# ---------------------------------------------------------------------------


class TestWalkPaths:
    """Tests for CodebaseWalker.walk_paths()."""

    # ------------------------------------------------------------------
    # Basic file selection
    # ------------------------------------------------------------------

    def test_walk_specific_files_returns_only_those(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths with 2 of 3 files should produce nodes only for those 2."""
        alpha = py_project / "mylib" / "alpha.py"
        beta = py_project / "mylib" / "beta.py"

        graph = walker.walk_paths(
            paths=[str(alpha), str(beta)],
            project_root=py_project,
        )

        assert isinstance(graph, RPGGraph)

        component_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        # alpha and beta components should be present
        assert "alpha" in component_names
        assert "beta" in component_names
        # gamma should NOT be present
        assert "gamma" not in component_names

    def test_walk_specific_files_exact_component_count(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths of exactly 2 Python files → exactly 2 COMPONENT nodes."""
        alpha = py_project / "mylib" / "alpha.py"
        beta = py_project / "mylib" / "beta.py"

        graph = walker.walk_paths(
            paths=[str(alpha), str(beta)],
            project_root=py_project,
        )

        components = [
            n for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        ]
        assert len(components) == 2

    def test_walk_single_file_single_component(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths of one file → exactly 1 COMPONENT node (plus module + features)."""
        alpha = py_project / "mylib" / "alpha.py"

        graph = walker.walk_paths(paths=[str(alpha)], project_root=py_project)

        components = [
            n for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        ]
        assert len(components) == 1
        assert components[0].name == "alpha"

    def test_walk_file_extracts_features(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths extracts FEATURE nodes (classes/functions) from Python files."""
        alpha = py_project / "mylib" / "alpha.py"

        graph = walker.walk_paths(paths=[str(alpha)], project_root=py_project)

        feature_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.FEATURE
        }
        assert "Alpha" in feature_names

    # ------------------------------------------------------------------
    # Missing path handling
    # ------------------------------------------------------------------

    def test_walk_missing_path_no_exception(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths with a non-existent path logs a warning and returns empty graph."""
        missing = py_project / "nonexistent" / "file.py"

        # Must not raise
        graph = walker.walk_paths(paths=[str(missing)], project_root=py_project)
        assert isinstance(graph, RPGGraph)

    def test_walk_missing_path_returns_zero_nodes(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """A non-existent path contributes 0 nodes to the result."""
        missing = py_project / "ghost.py"

        graph = walker.walk_paths(paths=[str(missing)], project_root=py_project)
        assert graph.node_count == 0

    def test_walk_mixed_valid_and_missing(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """Valid paths are processed even when mixed with missing paths."""
        alpha = py_project / "mylib" / "alpha.py"
        missing = py_project / "does_not_exist.py"

        graph = walker.walk_paths(
            paths=[str(alpha), str(missing)],
            project_root=py_project,
        )

        component_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        assert "alpha" in component_names

    # ------------------------------------------------------------------
    # Directory paths
    # ------------------------------------------------------------------

    def test_walk_directory_includes_all_files(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths with a directory path walks it recursively."""
        mylib_dir = py_project / "mylib"

        graph = walker.walk_paths(
            paths=[str(mylib_dir)],
            project_root=py_project,
        )

        component_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        # All 4 files (__init__, alpha, beta, gamma) should appear
        assert "alpha" in component_names
        assert "beta" in component_names
        assert "gamma" in component_names

    def test_walk_directory_returns_rpggraph(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """Directory-based walk_paths returns an RPGGraph."""
        mylib_dir = py_project / "mylib"
        graph = walker.walk_paths(paths=[str(mylib_dir)], project_root=py_project)
        assert isinstance(graph, RPGGraph)
        assert graph.node_count > 0

    def test_walk_directory_minimum_three_components(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """Directory with 3 source files should yield at least 3 COMPONENT nodes."""
        mylib_dir = py_project / "mylib"

        graph = walker.walk_paths(
            paths=[str(mylib_dir)],
            project_root=py_project,
        )

        components = [
            n for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        ]
        # __init__.py, alpha.py, beta.py, gamma.py = 4 components
        assert len(components) >= 3

    # ------------------------------------------------------------------
    # TypeScript / JS files
    # ------------------------------------------------------------------

    def test_walk_ts_file_creates_component(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        """walk_paths on a .tsx file produces a COMPONENT node."""
        app_tsx = ts_project / "src" / "App.tsx"

        graph = walker.walk_paths(paths=[str(app_tsx)], project_root=ts_project)

        component_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        assert "App" in component_names

    def test_walk_ts_directory_creates_multiple_components(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        """walk_paths on a TypeScript directory produces COMPONENT nodes."""
        src_dir = ts_project / "src"

        graph = walker.walk_paths(paths=[str(src_dir)], project_root=ts_project)

        component_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        assert "App" in component_names
        assert "index" in component_names
        assert "utils" in component_names

    # ------------------------------------------------------------------
    # Non-source file is skipped
    # ------------------------------------------------------------------

    def test_non_source_file_skipped(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """Non-source files (e.g. .md, .txt) are skipped gracefully."""
        readme = tmp_path / "README.md"
        readme.write_text("# My project")

        graph = walker.walk_paths(paths=[str(readme)], project_root=tmp_path)

        assert graph.node_count == 0

    # ------------------------------------------------------------------
    # Relative paths resolved against project_root
    # ------------------------------------------------------------------

    def test_relative_path_resolved(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """Relative paths are resolved against project_root."""
        graph = walker.walk_paths(
            paths=["mylib/alpha.py"],
            project_root=py_project,
        )

        component_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        assert "alpha" in component_names

    # ------------------------------------------------------------------
    # Produced paths are relative (same as walk())
    # ------------------------------------------------------------------

    def test_component_file_path_is_relative(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """file_path on COMPONENT nodes should be relative, not absolute."""
        alpha = py_project / "mylib" / "alpha.py"
        graph = walker.walk_paths(paths=[str(alpha)], project_root=py_project)

        for node in graph.nodes.values():
            if node.file_path:
                assert not node.file_path.startswith("/"), (
                    f"file_path should be relative: {node.file_path}"
                )

    def test_file_path_starts_with_folder_path(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """file_path must start with folder_path (RPGNode invariant)."""
        alpha = py_project / "mylib" / "alpha.py"
        graph = walker.walk_paths(paths=[str(alpha)], project_root=py_project)

        for node in graph.nodes.values():
            if node.file_path and node.folder_path:
                assert node.file_path.startswith(node.folder_path), (
                    f"file_path '{node.file_path}' must start with "
                    f"folder_path '{node.folder_path}'"
                )

    # ------------------------------------------------------------------
    # Empty paths list
    # ------------------------------------------------------------------

    def test_empty_paths_returns_empty_graph(
        self, walker: CodebaseWalker, py_project: Path
    ) -> None:
        """walk_paths with an empty list returns an empty RPGGraph."""
        graph = walker.walk_paths(paths=[], project_root=py_project)
        assert isinstance(graph, RPGGraph)
        assert graph.node_count == 0
