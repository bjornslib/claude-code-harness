"""Unit tests for CodebaseWalker TypeScript/React support.

Tests cover:
- .ts, .tsx, .js, .jsx files produce MODULE + COMPONENT nodes
- Component names are derived from file stem (strip extension)
- TypeScript directories without __init__.py become MODULE nodes
- Nested TypeScript directory hierarchy
- Mixed Python + TypeScript projects
- No FEATURE nodes for TS files (graceful no-op with FileBasedCodebaseAnalyzer)
- TS component metadata (language: typescript)
- file_path / folder_path correctness for TS nodes
- Standalone TS files outside any TS/package directory are skipped
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.serena.session import FileBasedCodebaseAnalyzer
from cobuilder.repomap.serena.walker import (
    CodebaseWalker,
    DEFAULT_EXCLUDE_PATTERNS,
    TS_EXTENSIONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def walker() -> CodebaseWalker:
    """Return a CodebaseWalker with a FileBasedCodebaseAnalyzer."""
    analyzer = FileBasedCodebaseAnalyzer()
    return CodebaseWalker(analyzer)


@pytest.fixture
def ts_project(tmp_path: Path) -> Path:
    """Create a minimal TypeScript/React project for walker testing.

    Layout::

        tmp_path/
        ├── src/
        │   ├── App.tsx          # React component
        │   ├── index.ts         # entry point
        │   ├── utils.ts         # utility module
        │   └── components/
        │       ├── Button.tsx
        │       └── Modal.tsx
        ├── scripts/
        │   └── build.js         # JavaScript file
        └── README.md            # Not a source file - should be ignored
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text(
        textwrap.dedent("""\
        import React from 'react';

        interface AppProps {
          title: string;
        }

        const App: React.FC<AppProps> = ({ title }) => {
          return <div>{title}</div>;
        };

        export default App;
        """)
    )
    (src / "index.ts").write_text(
        textwrap.dedent("""\
        import App from './App';
        export { App };
        """)
    )
    (src / "utils.ts").write_text(
        textwrap.dedent("""\
        export function formatDate(date: Date): string {
          return date.toISOString();
        }
        """)
    )

    components = src / "components"
    components.mkdir()
    (components / "Button.tsx").write_text(
        "export const Button = () => <button>Click</button>;\n"
    )
    (components / "Modal.tsx").write_text(
        "export const Modal = () => <div className='modal'></div>;\n"
    )

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "build.js").write_text(
        textwrap.dedent("""\
        const path = require('path');
        module.exports = { entry: './src/index.ts' };
        """)
    )

    (tmp_path / "README.md").write_text("# My Project\n")

    return tmp_path


@pytest.fixture
def mixed_project(tmp_path: Path) -> Path:
    """Create a project with both Python and TypeScript source.

    Layout::

        tmp_path/
        ├── backend/              # Python package
        │   ├── __init__.py
        │   └── api.py
        └── frontend/             # TypeScript directory
            ├── App.tsx
            └── types.ts
    """
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "__init__.py").write_text("")
    (backend / "api.py").write_text(
        textwrap.dedent("""\
        def get_users() -> list:
            return []
        """)
    )

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "App.tsx").write_text("export const App = () => null;\n")
    (frontend / "types.ts").write_text(
        "export interface User { id: number; name: string; }\n"
    )

    return tmp_path


@pytest.fixture
def jsx_project(tmp_path: Path) -> Path:
    """.jsx project to verify JS support."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.jsx").write_text(
        "import React from 'react';\nexport default () => <div/>;\n"
    )
    (app_dir / "helper.js").write_text("export const noop = () => {};\n")
    return tmp_path


# ---------------------------------------------------------------------------
# TS_EXTENSIONS constant
# ---------------------------------------------------------------------------


class TestTsExtensionsConstant:
    """Verify the exported constant contains all expected extensions."""

    def test_ts_extensions_contains_ts(self) -> None:
        assert ".ts" in TS_EXTENSIONS

    def test_ts_extensions_contains_tsx(self) -> None:
        assert ".tsx" in TS_EXTENSIONS

    def test_ts_extensions_contains_js(self) -> None:
        assert ".js" in TS_EXTENSIONS

    def test_ts_extensions_contains_jsx(self) -> None:
        assert ".jsx" in TS_EXTENSIONS

    def test_ts_extensions_does_not_contain_py(self) -> None:
        assert ".py" not in TS_EXTENSIONS


# ---------------------------------------------------------------------------
# Module node creation for TypeScript directories
# ---------------------------------------------------------------------------


class TestTypeScriptModuleNodes:
    """TypeScript directories (without __init__.py) become MODULE nodes."""

    def test_src_dir_becomes_module(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        module_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        }
        assert "src" in module_names

    def test_components_subdir_becomes_module(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        module_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        }
        assert "components" in module_names

    def test_scripts_dir_becomes_module(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        module_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        }
        assert "scripts" in module_names

    def test_ts_module_metadata_is_ts_dir(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        src_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "src" and n.level == NodeLevel.MODULE
        )
        assert src_module.metadata.get("is_ts_dir") is True
        assert src_module.metadata.get("is_package") is False

    def test_ts_module_not_python_package(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for node in graph.nodes.values():
            if node.level == NodeLevel.MODULE and node.metadata.get("is_ts_dir"):
                # TS dirs should not also claim to be Python packages
                assert node.metadata.get("is_package") is False


# ---------------------------------------------------------------------------
# Component node creation for TypeScript/JS files
# ---------------------------------------------------------------------------


class TestTypeScriptComponentNodes:
    """TS/JS source files become COMPONENT nodes with correct names."""

    def test_tsx_file_becomes_component(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "App" in comp_names

    def test_ts_file_becomes_component(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "index" in comp_names
        assert "utils" in comp_names

    def test_js_file_becomes_component(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "build" in comp_names

    def test_jsx_file_becomes_component(
        self, walker: CodebaseWalker, jsx_project: Path
    ) -> None:
        graph = walker.walk(jsx_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "main" in comp_names
        assert "helper" in comp_names

    def test_component_name_is_stem_not_full_filename(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        """Ensure extension is stripped: 'App.tsx' → 'App', not 'App.tsx'."""
        graph = walker.walk(ts_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        # Must not contain the extension in the name
        for name in comp_names:
            for ext in TS_EXTENSIONS:
                assert not name.endswith(ext), (
                    f"Component name '{name}' should not include extension"
                )

    def test_ts_component_has_language_metadata(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        ts_comps = [
            n
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
            and n.metadata.get("language") == "typescript"
        ]
        assert len(ts_comps) > 0

    def test_ts_component_serena_validated(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for node in graph.nodes.values():
            if node.level == NodeLevel.COMPONENT and node.metadata.get(
                "language"
            ) == "typescript":
                assert node.serena_validated is True

    def test_ts_component_baseline_metadata(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for node in graph.nodes.values():
            if node.level == NodeLevel.COMPONENT and node.metadata.get(
                "language"
            ) == "typescript":
                assert node.metadata.get("baseline") is True

    def test_markdown_files_not_included(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        """README.md should not appear as a component node."""
        graph = walker.walk(ts_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "README" not in comp_names


# ---------------------------------------------------------------------------
# File paths and folder paths for TS nodes
# ---------------------------------------------------------------------------


class TestTypeScriptPaths:
    """TS nodes have correct relative file_path and folder_path."""

    def test_ts_component_has_file_path(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        ts_comps = [
            n
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
            and n.metadata.get("language") == "typescript"
        ]
        for comp in ts_comps:
            assert comp.file_path is not None, f"Component '{comp.name}' missing file_path"

    def test_ts_component_file_path_has_ts_extension(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        ts_comps = [
            n
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
            and n.metadata.get("language") == "typescript"
        ]
        for comp in ts_comps:
            assert comp.file_path is not None
            ext = Path(comp.file_path).suffix
            assert ext in TS_EXTENSIONS, (
                f"file_path '{comp.file_path}' does not end with a TS extension"
            )

    def test_ts_file_path_is_relative(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for node in graph.nodes.values():
            if node.file_path and node.metadata.get("language") == "typescript":
                assert not node.file_path.startswith("/"), (
                    f"file_path should be relative: {node.file_path}"
                )

    def test_ts_file_path_starts_with_folder_path(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for node in graph.nodes.values():
            if (
                node.level == NodeLevel.COMPONENT
                and node.file_path
                and node.folder_path
                and node.metadata.get("language") == "typescript"
            ):
                assert node.file_path.startswith(node.folder_path), (
                    f"file_path '{node.file_path}' must start with "
                    f"folder_path '{node.folder_path}'"
                )


# ---------------------------------------------------------------------------
# Hierarchy edges for TypeScript
# ---------------------------------------------------------------------------


class TestTypeScriptHierarchyEdges:
    """HIERARCHY edges are created correctly for TS nodes."""

    def test_module_to_ts_component_edge_exists(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        src_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "src" and n.level == NodeLevel.MODULE
        )
        child_edges = [
            e
            for e in graph.edges.values()
            if e.source_id == src_module.id and e.edge_type == EdgeType.HIERARCHY
        ]
        # Should have edges to App, index, utils, and the components sub-module
        assert len(child_edges) >= 3

    def test_nested_ts_module_hierarchy(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        """src/ → components/ edge should exist."""
        graph = walker.walk(ts_project)
        src_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "src" and n.level == NodeLevel.MODULE
        )
        components_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "components" and n.level == NodeLevel.MODULE
        )
        edge = next(
            (
                e
                for e in graph.edges.values()
                if e.source_id == src_module.id
                and e.target_id == components_module.id
                and e.edge_type == EdgeType.HIERARCHY
            ),
            None,
        )
        assert edge is not None, "Expected HIERARCHY edge from src to components"

    def test_all_edges_reference_valid_nodes(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for edge in graph.edges.values():
            assert edge.source_id in graph.nodes
            assert edge.target_id in graph.nodes

    def test_no_self_loops(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        for edge in graph.edges.values():
            assert edge.source_id != edge.target_id


# ---------------------------------------------------------------------------
# No FEATURE nodes for TypeScript files (graceful no-op)
# ---------------------------------------------------------------------------


class TestTypeScriptNoFeatureNodes:
    """FileBasedCodebaseAnalyzer returns [] for TS files, so no FEATUREs."""

    def test_ts_components_have_no_feature_children(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        ts_comp_ids = {
            n.id
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
            and n.metadata.get("language") == "typescript"
        }
        # No FEATURE node should have a ts component as parent
        for node in graph.nodes.values():
            if node.level == NodeLevel.FEATURE:
                assert node.parent_id not in ts_comp_ids, (
                    f"FEATURE node '{node.name}' should not be child of a TS component"
                )


# ---------------------------------------------------------------------------
# Mixed Python + TypeScript projects
# ---------------------------------------------------------------------------


class TestMixedProject:
    """Python and TypeScript can coexist in the same project root."""

    def test_python_module_present(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        module_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        }
        assert "backend" in module_names

    def test_ts_module_present(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        module_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        }
        assert "frontend" in module_names

    def test_python_component_present(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "api" in comp_names

    def test_ts_component_present(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "App" in comp_names
        assert "types" in comp_names

    def test_python_feature_present(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        """Python features should still be extracted normally."""
        graph = walker.walk(mixed_project)
        feature_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.FEATURE
        }
        assert "get_users" in feature_names

    def test_python_module_has_is_package_true(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        backend = next(
            n
            for n in graph.nodes.values()
            if n.name == "backend" and n.level == NodeLevel.MODULE
        )
        assert backend.metadata.get("is_package") is True

    def test_ts_module_has_is_ts_dir_true(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        frontend = next(
            n
            for n in graph.nodes.values()
            if n.name == "frontend" and n.level == NodeLevel.MODULE
        )
        assert frontend.metadata.get("is_ts_dir") is True

    def test_all_nodes_functionality_type(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        """All nodes should use NodeType.FUNCTIONALITY."""
        graph = walker.walk(mixed_project)
        for node in graph.nodes.values():
            assert node.node_type == NodeType.FUNCTIONALITY

    def test_all_nodes_serena_validated(
        self, walker: CodebaseWalker, mixed_project: Path
    ) -> None:
        graph = walker.walk(mixed_project)
        for node in graph.nodes.values():
            assert node.serena_validated is True


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


class TestTypeScriptEdgeCases:
    """Edge cases for TypeScript walker support."""

    def test_empty_project_no_nodes(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        graph = walker.walk(tmp_path)
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_dir_with_only_markdown_not_a_module(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """A directory with only .md files should not produce a module node."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("# Guide\n")
        graph = walker.walk(tmp_path)
        assert graph.node_count == 0

    def test_ts_files_in_excluded_dir_skipped(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """TS files inside excluded dirs should be ignored."""
        excluded = tmp_path / "node_modules"
        excluded.mkdir()
        (excluded / "react.ts").write_text("export {};\n")
        graph = walker.walk(tmp_path)
        assert graph.node_count == 0

    def test_hidden_dir_ts_files_skipped(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """TS files inside hidden directories (.git etc.) should be ignored."""
        hidden = tmp_path / ".vscode"
        hidden.mkdir()
        (hidden / "settings.ts").write_text("const x = 1;\n")
        graph = walker.walk(tmp_path)
        assert graph.node_count == 0

    def test_all_ts_extensions_produce_components(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """All four TS/JS extensions should produce COMPONENT nodes."""
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "a.ts").write_text("export const a = 1;\n")
        (app_dir / "b.tsx").write_text("export const B = () => null;\n")
        (app_dir / "c.js").write_text("module.exports = {};\n")
        (app_dir / "d.jsx").write_text("export default () => null;\n")

        graph = walker.walk(tmp_path)
        comp_names = {
            n.name for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        assert "a" in comp_names
        assert "b" in comp_names
        assert "c" in comp_names
        assert "d" in comp_names

    def test_graph_stats_include_ts_nodes(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        graph = walker.walk(ts_project)
        stats = graph.metadata.get("baseline_stats", {})
        assert stats.get("total_nodes", 0) == graph.node_count
        assert stats.get("components", 0) >= 5  # App, index, utils, Button, Modal, build

    def test_ts_project_graph_is_rpggraph(
        self, walker: CodebaseWalker, ts_project: Path
    ) -> None:
        from cobuilder.repomap.models.graph import RPGGraph
        graph = walker.walk(ts_project)
        assert isinstance(graph, RPGGraph)
        assert graph.node_count > 0
