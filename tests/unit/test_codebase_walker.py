"""Unit tests for CodebaseWalker.

Tests cover:
- Correct MODULE → COMPONENT → FEATURE node hierarchy
- HIERARCHY edge creation
- Exclude pattern support
- Empty directory handling
- Metadata and stats
- Walking zerorepo's own models/ directory as a real-world test
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.serena.session import FileBasedCodebaseAnalyzer
from zerorepo.serena.walker import CodebaseWalker, DEFAULT_EXCLUDE_PATTERNS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project for walker testing.

    Layout::

        tmp_path/
        ├── mylib/
        │   ├── __init__.py
        │   ├── core.py          # 2 classes + 1 function
        │   └── sub/
        │       ├── __init__.py
        │       └── helpers.py   # 1 function
        └── setup.py              # Standalone file (outside package)
    """
    mylib = tmp_path / "mylib"
    mylib.mkdir()
    (mylib / "__init__.py").write_text('"""My library."""\n')
    (mylib / "core.py").write_text(
        textwrap.dedent("""\
        \"\"\"Core module.\"\"\"


        class Engine:
            \"\"\"The main engine.\"\"\"

            def run(self) -> None:
                pass


        class Config:
            \"\"\"Configuration holder.\"\"\"
            pass


        def bootstrap() -> Engine:
            \"\"\"Create and return a configured Engine.\"\"\"
            return Engine()
        """)
    )

    sub = mylib / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "helpers.py").write_text(
        textwrap.dedent("""\
        \"\"\"Helper functions.\"\"\"


        def format_data(data: list) -> str:
            return str(data)
        """)
    )

    (tmp_path / "setup.py").write_text(
        textwrap.dedent("""\
        \"\"\"Setup script.\"\"\"
        from setuptools import setup

        setup(name="mylib")
        """)
    )

    return tmp_path


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Create an empty project (directory with no Python files)."""
    return tmp_path


@pytest.fixture
def walker() -> CodebaseWalker:
    """Return a CodebaseWalker with a FileBasedCodebaseAnalyzer."""
    analyzer = FileBasedCodebaseAnalyzer()
    return CodebaseWalker(analyzer)


# ---------------------------------------------------------------------------
# Basic walker functionality
# ---------------------------------------------------------------------------


class TestCodebaseWalkerBasic:
    """Basic walker tests."""

    def test_walk_produces_rpggraph(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        assert isinstance(graph, RPGGraph)
        assert graph.node_count > 0

    def test_walk_empty_project(
        self, walker: CodebaseWalker, empty_project: Path
    ) -> None:
        graph = walker.walk(empty_project)
        assert isinstance(graph, RPGGraph)
        assert graph.node_count == 0
        assert graph.edge_count == 0


# ---------------------------------------------------------------------------
# Node hierarchy
# ---------------------------------------------------------------------------


class TestNodeHierarchy:
    """Test MODULE → COMPONENT → FEATURE hierarchy."""

    def test_module_nodes_created(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        modules = [
            n for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        ]
        module_names = {n.name for n in modules}
        # mylib and sub should be modules
        assert "mylib" in module_names
        assert "sub" in module_names

    def test_component_nodes_created(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        components = [
            n for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        ]
        comp_names = {n.name for n in components}
        # __init__, core, helpers should be components
        assert "core" in comp_names
        assert "helpers" in comp_names

    def test_feature_nodes_created(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        features = [
            n for n in graph.nodes.values() if n.level == NodeLevel.FEATURE
        ]
        feature_names = {n.name for n in features}
        # Classes and functions
        assert "Engine" in feature_names
        assert "Config" in feature_names
        assert "bootstrap" in feature_names
        assert "format_data" in feature_names

    def test_all_nodes_are_functionality_type(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        """Baseline nodes should use FUNCTIONALITY, not FUNCTION_AUGMENTED."""
        graph = walker.walk(sample_project)
        for node in graph.nodes.values():
            assert node.node_type == NodeType.FUNCTIONALITY

    def test_parent_ids_set_correctly(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        # Features should have a parent_id pointing to a COMPONENT
        features = [
            n for n in graph.nodes.values() if n.level == NodeLevel.FEATURE
        ]
        for feature in features:
            assert feature.parent_id is not None
            parent = graph.get_node(feature.parent_id)
            assert parent is not None
            assert parent.level == NodeLevel.COMPONENT

    def test_component_parent_is_module(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        components = [
            n for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        ]
        for comp in components:
            if comp.parent_id is not None:
                parent = graph.get_node(comp.parent_id)
                assert parent is not None
                assert parent.level == NodeLevel.MODULE


# ---------------------------------------------------------------------------
# HIERARCHY edges
# ---------------------------------------------------------------------------


class TestHierarchyEdges:
    """Test HIERARCHY edge creation."""

    def test_hierarchy_edges_exist(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        hierarchy_edges = [
            e
            for e in graph.edges.values()
            if e.edge_type == EdgeType.HIERARCHY
        ]
        assert len(hierarchy_edges) > 0

    def test_module_to_component_edges(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        # Find the mylib MODULE
        mylib_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "mylib" and n.level == NodeLevel.MODULE
        )
        # Find edges from this module
        child_edges = [
            e
            for e in graph.edges.values()
            if e.source_id == mylib_module.id
            and e.edge_type == EdgeType.HIERARCHY
        ]
        # Should have edges to its COMPONENT children and the sub MODULE
        assert len(child_edges) >= 2

    def test_component_to_feature_edges(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        # Find the core COMPONENT
        core_comp = next(
            n
            for n in graph.nodes.values()
            if n.name == "core" and n.level == NodeLevel.COMPONENT
        )
        # Find edges from core to its features
        feature_edges = [
            e
            for e in graph.edges.values()
            if e.source_id == core_comp.id
            and e.edge_type == EdgeType.HIERARCHY
        ]
        # Should have edges to Engine, Config, bootstrap
        assert len(feature_edges) == 3

    def test_all_edges_reference_existing_nodes(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        for edge in graph.edges.values():
            assert edge.source_id in graph.nodes
            assert edge.target_id in graph.nodes

    def test_no_self_loops(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        for edge in graph.edges.values():
            assert edge.source_id != edge.target_id


# ---------------------------------------------------------------------------
# File paths and folder paths
# ---------------------------------------------------------------------------


class TestPaths:
    """Test that file_path and folder_path are set correctly."""

    def test_file_paths_are_relative(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        for node in graph.nodes.values():
            if node.file_path:
                assert not node.file_path.startswith(
                    "/"
                ), f"file_path should be relative: {node.file_path}"

    def test_folder_paths_are_relative(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        for node in graph.nodes.values():
            if node.folder_path:
                assert not node.folder_path.startswith(
                    "/"
                ), f"folder_path should be relative: {node.folder_path}"

    def test_file_path_starts_with_folder_path(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        """RPGNode validator requires file_path starts with folder_path."""
        graph = walker.walk(sample_project)
        for node in graph.nodes.values():
            if node.file_path and node.folder_path:
                assert node.file_path.startswith(
                    node.folder_path
                ), (
                    f"file_path '{node.file_path}' must start with "
                    f"folder_path '{node.folder_path}'"
                )

    def test_module_has_folder_path(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        modules = [
            n for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        ]
        for module in modules:
            assert module.folder_path is not None

    def test_component_has_file_path(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        components = [
            n for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        ]
        for comp in components:
            assert comp.file_path is not None
            assert comp.file_path.endswith(".py")


# ---------------------------------------------------------------------------
# Serena validated flag
# ---------------------------------------------------------------------------


class TestSerenaValidated:
    """Test that nodes are marked as serena_validated."""

    def test_all_nodes_serena_validated(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        for node in graph.nodes.values():
            assert node.serena_validated is True

    def test_all_nodes_have_baseline_metadata(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        for node in graph.nodes.values():
            assert node.metadata.get("baseline") is True


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    """Test graph-level metadata."""

    def test_has_baseline_generated_at(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        assert "baseline_generated_at" in graph.metadata

    def test_has_project_root(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        assert "project_root" in graph.metadata
        assert str(sample_project.resolve()) in graph.metadata["project_root"]

    def test_has_baseline_stats(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        graph = walker.walk(sample_project)
        stats = graph.metadata.get("baseline_stats")
        assert stats is not None
        assert stats["total_nodes"] == graph.node_count
        assert stats["total_edges"] == graph.edge_count
        assert stats["modules"] >= 2  # mylib, sub
        assert stats["components"] >= 2  # core.py, helpers.py (plus __init__.py's)
        assert stats["features"] >= 4  # Engine, Config, bootstrap, format_data


# ---------------------------------------------------------------------------
# Exclude patterns
# ---------------------------------------------------------------------------


class TestExcludePatterns:
    """Test exclude pattern handling."""

    def test_default_excludes_pycache(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        # Create a __pycache__ directory
        cache_dir = sample_project / "mylib" / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "core.cpython-312.pyc").write_bytes(b"fake")

        graph = walker.walk(sample_project)
        # No node should reference __pycache__
        for node in graph.nodes.values():
            if node.folder_path:
                assert "__pycache__" not in node.folder_path
            if node.file_path:
                assert "__pycache__" not in node.file_path

    def test_custom_exclude_pattern(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        # Exclude the entire sub package
        graph = walker.walk(
            sample_project, exclude_patterns=["sub", "__pycache__"]
        )
        module_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.MODULE
        }
        assert "sub" not in module_names

    def test_glob_style_exclude(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        # Create an egg-info directory
        egg_dir = sample_project / "mylib.egg-info"
        egg_dir.mkdir()
        (egg_dir / "__init__.py").write_text("")
        (egg_dir / "PKG-INFO").write_text("Name: mylib")

        graph = walker.walk(sample_project)
        # The egg-info should be excluded by default *.egg-info pattern
        for node in graph.nodes.values():
            if node.folder_path:
                assert "egg-info" not in node.folder_path


# ---------------------------------------------------------------------------
# Edge case: project with no packages
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_directory_with_no_init(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """A directory without __init__.py is not a Python package."""
        d = tmp_path / "notapackage"
        d.mkdir()
        (d / "script.py").write_text("x = 1")
        graph = walker.walk(tmp_path)
        # No MODULE or COMPONENT nodes should be created for a non-package dir
        # (standalone files outside packages are skipped)
        assert graph.node_count == 0

    def test_nested_package_hierarchy(
        self, walker: CodebaseWalker, sample_project: Path
    ) -> None:
        """Verify nested packages produce a multi-level hierarchy."""
        graph = walker.walk(sample_project)
        # sub MODULE should have mylib MODULE as ancestor
        sub_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "sub" and n.level == NodeLevel.MODULE
        )
        mylib_module = next(
            n
            for n in graph.nodes.values()
            if n.name == "mylib" and n.level == NodeLevel.MODULE
        )
        # There should be a HIERARCHY edge from mylib to sub
        edge = next(
            (
                e
                for e in graph.edges.values()
                if e.source_id == mylib_module.id
                and e.target_id == sub_module.id
                and e.edge_type == EdgeType.HIERARCHY
            ),
            None,
        )
        assert edge is not None

    def test_syntax_error_file_skipped_gracefully(
        self, walker: CodebaseWalker, tmp_path: Path
    ) -> None:
        """Files with syntax errors should not crash the walker."""
        pkg = tmp_path / "broken"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "bad.py").write_text("def broken(\n")  # syntax error
        (pkg / "good.py").write_text("def ok(): pass")

        graph = walker.walk(tmp_path)
        # The component for bad.py should exist but have no features
        comp_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        assert "bad" in comp_names
        assert "good" in comp_names
        # The good.py feature should be extracted
        feature_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.FEATURE
        }
        assert "ok" in feature_names


# ---------------------------------------------------------------------------
# Real-world test: walk zerorepo's own models/ directory
# ---------------------------------------------------------------------------


class TestRealWorldWalk:
    """Walk zerorepo's own source code as a smoke test."""

    def test_walk_zerorepo_models(self) -> None:
        """Walk src/zerorepo/models/ and verify it produces expected nodes."""
        project_root = Path(__file__).parent.parent.parent / "src" / "zerorepo"
        if not (project_root / "models" / "__init__.py").exists():
            pytest.skip("Cannot find zerorepo source tree")

        analyzer = FileBasedCodebaseAnalyzer()
        walker = CodebaseWalker(analyzer)
        graph = walker.walk(project_root)

        # Should find at least the models package
        module_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.MODULE
        }
        assert "models" in module_names

        # Should find RPGNode, RPGEdge, RPGGraph as features
        feature_names = {
            n.name
            for n in graph.nodes.values()
            if n.level == NodeLevel.FEATURE
        }
        assert "RPGNode" in feature_names
        assert "RPGEdge" in feature_names
        assert "RPGGraph" in feature_names

        # All nodes should pass RPGNode validation (since they're in the graph)
        for node in graph.nodes.values():
            assert node.node_type == NodeType.FUNCTIONALITY
            if node.file_path and node.folder_path:
                assert node.file_path.startswith(node.folder_path)

    def test_graph_serialization_roundtrip(self) -> None:
        """Verify the baseline graph can be serialized and deserialized."""
        project_root = Path(__file__).parent.parent.parent / "src" / "zerorepo"
        if not (project_root / "models" / "__init__.py").exists():
            pytest.skip("Cannot find zerorepo source tree")

        analyzer = FileBasedCodebaseAnalyzer()
        walker = CodebaseWalker(analyzer)
        graph = walker.walk(project_root)

        # Serialize
        json_str = graph.to_json()

        # Deserialize
        restored = RPGGraph.from_json(json_str)

        # Verify counts match
        assert restored.node_count == graph.node_count
        assert restored.edge_count == graph.edge_count
        assert "baseline_generated_at" in restored.metadata
