"""Unit tests for Epic 4.6: Repository Assembly.

Tests cover:
- File structure generation (extract_directories, extract_file_entries, build_file_map)
- __init__.py generation (generate_init_content, collect_init_files)
- Import management (classify_import, resolve_imports_for_file, render_import_block, detect_circular_imports)
- Requirements generation (detect_requirements, render_requirements_txt)
- Project generation (extract_project_metadata, render_pyproject_toml, render_setup_py)
- README generation (generate_readme)
- RPG artifact export (export_rpg_artifact, export_rpg_summary)
- Coverage report (build_coverage_report, render_coverage_markdown)
- Exception classes
- Pydantic models validation
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import PurePosixPath
from uuid import UUID, uuid4

import pytest

from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from zerorepo.models.edge import RPGEdge
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode

from zerorepo.codegen.exceptions import (
    AssemblyError,
    CircularImportError,
    FileStructureError,
    ImportResolutionError,
    MetadataExtractionError,
)
from zerorepo.codegen.models import (
    CoverageReport,
    DirectoryEntry,
    FileEntry,
    ImportGroup,
    ImportStatement,
    NodeCoverageEntry,
    RepositoryManifest,
    RequirementEntry,
    SubgraphCoverage,
)
from zerorepo.codegen.state import GenerationStatus
from zerorepo.codegen.file_structure import (
    build_file_map,
    create_directory_structure,
    extract_directories,
    extract_file_entries,
    validate_file_structure,
)
from zerorepo.codegen.init_generator import (
    collect_init_files,
    generate_init_content,
)
from zerorepo.codegen.import_manager import (
    classify_import,
    detect_circular_imports,
    render_import_block,
    resolve_imports_for_file,
)
from zerorepo.codegen.requirements_generator import (
    detect_requirements,
    render_requirements_dev_txt,
    render_requirements_txt,
    scan_node_imports,
)
from zerorepo.codegen.project_generator import (
    extract_project_metadata,
    render_pyproject_toml,
    render_setup_py,
)
from zerorepo.codegen.readme_generator import generate_readme
from zerorepo.codegen.rpg_exporter import (
    export_rpg_artifact,
    export_rpg_summary,
)
from zerorepo.codegen.coverage_report import (
    build_coverage_report,
    render_coverage_markdown,
)


# --- Helpers ---

def make_node(
    name: str = "test_func",
    level: NodeLevel = NodeLevel.FEATURE,
    node_type: NodeType = NodeType.FUNCTION_AUGMENTED,
    file_path: str | None = "src/data/processors.py",
    folder_path: str | None = "src/data",
    interface_type: InterfaceType | None = InterfaceType.FUNCTION,
    signature: str | None = "test_func(x: int) -> int",
    docstring: str | None = "A test function.",
    **kwargs,
) -> RPGNode:
    """Create an RPG node with sensible defaults for assembly testing."""
    return RPGNode(
        name=name,
        level=level,
        node_type=node_type,
        file_path=file_path,
        folder_path=folder_path,
        interface_type=interface_type,
        signature=signature,
        docstring=docstring,
        **kwargs,
    )


def make_edge(
    source_id: UUID,
    target_id: UUID,
    edge_type: EdgeType = EdgeType.INVOCATION,
) -> RPGEdge:
    """Create an RPG edge with sensible defaults."""
    return RPGEdge(source_id=source_id, target_id=target_id, edge_type=edge_type)


def build_test_graph() -> RPGGraph:
    """Build a small test graph with 5 nodes across 2 files in 2 packages."""
    graph = RPGGraph(
        metadata={
            "project_name": "test-project",
            "project_description": "A test project for assembly",
            "version": "1.0.0",
        }
    )

    # Package: src/data/
    n1 = make_node(name="load_data", file_path="src/data/loaders.py", folder_path="src/data")
    n2 = make_node(name="validate_data", file_path="src/data/loaders.py", folder_path="src/data")

    # Package: src/processing/
    n3 = make_node(
        name="process_records",
        file_path="src/processing/engine.py",
        folder_path="src/processing",
        implementation="import numpy\ndef process_records(data): pass",
    )
    n4 = make_node(
        name="filter_records",
        file_path="src/processing/engine.py",
        folder_path="src/processing",
    )

    # Package: src/output/
    n5 = make_node(
        name="write_output",
        file_path="src/output/writer.py",
        folder_path="src/output",
    )

    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_node(n4)
    graph.add_node(n5)

    # Edges: n3 depends on n1 (cross-file), n4 depends on n2 (cross-file)
    e1 = make_edge(n3.id, n1.id, EdgeType.INVOCATION)
    e2 = make_edge(n4.id, n2.id, EdgeType.INVOCATION)
    # n5 depends on n3 (cross-file)
    e3 = make_edge(n5.id, n3.id, EdgeType.DATA_FLOW)

    graph.add_edge(e1)
    graph.add_edge(e2)
    graph.add_edge(e3)

    return graph


# =================================================================
# Test Exceptions
# =================================================================

class TestExceptions:
    """Test custom exception classes."""

    def test_assembly_error_is_exception(self) -> None:
        with pytest.raises(AssemblyError):
            raise AssemblyError("test error")

    def test_file_structure_error_attributes(self) -> None:
        err = FileStructureError("/invalid/path", "permission denied")
        assert err.path == "/invalid/path"
        assert err.reason == "permission denied"
        assert "permission denied" in str(err)

    def test_import_resolution_error_attributes(self) -> None:
        err = ImportResolutionError("module_a", "func_b", "not found")
        assert err.source_module == "module_a"
        assert err.target_symbol == "func_b"
        assert "func_b" in str(err)

    def test_circular_import_error_cycle(self) -> None:
        err = CircularImportError(["a.py", "b.py", "a.py"])
        assert err.cycle == ["a.py", "b.py", "a.py"]
        assert "a.py -> b.py -> a.py" in str(err)

    def test_metadata_extraction_error(self) -> None:
        err = MetadataExtractionError("missing project name")
        assert "missing project name" in str(err)

    def test_exception_hierarchy(self) -> None:
        """All custom exceptions inherit from AssemblyError."""
        assert issubclass(FileStructureError, AssemblyError)
        assert issubclass(ImportResolutionError, AssemblyError)
        assert issubclass(CircularImportError, AssemblyError)
        assert issubclass(MetadataExtractionError, AssemblyError)


# =================================================================
# Test Pydantic Models
# =================================================================

class TestImportStatement:
    """Test ImportStatement model."""

    def test_render_from_import(self) -> None:
        stmt = ImportStatement(
            module_path="os.path",
            imported_names=["join", "exists"],
            group=ImportGroup.STDLIB,
        )
        rendered = stmt.render()
        assert rendered == "from os.path import exists, join"

    def test_render_import_module(self) -> None:
        stmt = ImportStatement(
            module_path="json",
            imported_names=[],
            group=ImportGroup.STDLIB,
            is_from_import=False,
        )
        assert stmt.render() == "import json"

    def test_render_with_alias(self) -> None:
        stmt = ImportStatement(
            module_path="numpy",
            imported_names=[],
            group=ImportGroup.THIRD_PARTY,
            is_from_import=False,
            alias="np",
        )
        assert stmt.render() == "import numpy as np"


class TestFileEntry:
    """Test FileEntry model."""

    def test_valid_relative_path(self) -> None:
        entry = FileEntry(path="src/module.py", content="# code")
        assert entry.path == "src/module.py"

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            FileEntry(path="/absolute/path.py")

    def test_backslash_normalization(self) -> None:
        entry = FileEntry(path="src\\data\\module.py")
        assert entry.path == "src/data/module.py"


class TestDirectoryEntry:
    """Test DirectoryEntry model."""

    def test_valid_directory(self) -> None:
        entry = DirectoryEntry(path="src/data")
        assert entry.path == "src/data"

    def test_trailing_slash_stripped(self) -> None:
        entry = DirectoryEntry(path="src/data/")
        assert entry.path == "src/data"

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="relative"):
            DirectoryEntry(path="/absolute/dir")


class TestRequirementEntry:
    """Test RequirementEntry model."""

    def test_render_with_version(self) -> None:
        req = RequirementEntry(
            package_name="numpy",
            version_spec=">=1.24.0,<2.0.0",
        )
        assert req.render() == "numpy>=1.24.0,<2.0.0"

    def test_render_without_version(self) -> None:
        req = RequirementEntry(package_name="requests")
        assert req.render() == "requests"


class TestCoverageReport:
    """Test CoverageReport model."""

    def test_pass_rate_computation(self) -> None:
        report = CoverageReport(
            total_nodes=10,
            passed_nodes=7,
            failed_nodes=2,
            skipped_nodes=1,
        )
        assert report.pass_rate == 70.0

    def test_pass_rate_zero_nodes(self) -> None:
        report = CoverageReport(total_nodes=0)
        assert report.pass_rate == 0.0

    def test_timestamp_auto_generated(self) -> None:
        report = CoverageReport(total_nodes=5, passed_nodes=5)
        assert report.timestamp is not None


class TestSubgraphCoverage:
    """Test SubgraphCoverage model."""

    def test_pass_rate(self) -> None:
        sg = SubgraphCoverage(subgraph_id="data", total=10, passed=8, failed=1, skipped=1)
        assert sg.pass_rate == 80.0

    def test_pass_rate_zero_total(self) -> None:
        sg = SubgraphCoverage(subgraph_id="empty", total=0)
        assert sg.pass_rate == 0.0


class TestRepositoryManifest:
    """Test RepositoryManifest model."""

    def test_default_values(self) -> None:
        manifest = RepositoryManifest()
        assert manifest.project_name == "generated_repo"
        assert manifest.files == []
        assert manifest.directories == []


# =================================================================
# Test File Structure Generation
# =================================================================

class TestExtractDirectories:
    """Test extract_directories from RPG graph."""

    def test_standard_directories_always_included(self) -> None:
        graph = RPGGraph()
        dirs = extract_directories(graph)
        dir_paths = {d.path for d in dirs}
        assert "src" in dir_paths
        assert "tests" in dir_paths
        assert "docs" in dir_paths

    def test_extracts_intermediate_dirs(self) -> None:
        graph = build_test_graph()
        dirs = extract_directories(graph)
        dir_paths = {d.path for d in dirs}
        assert "src/data" in dir_paths
        assert "src/processing" in dir_paths
        assert "src/output" in dir_paths

    def test_src_dirs_need_init(self) -> None:
        graph = build_test_graph()
        dirs = extract_directories(graph)
        src_dirs = [d for d in dirs if d.path.startswith("src")]
        for d in src_dirs:
            assert d.needs_init is True

    def test_sorted_parents_first(self) -> None:
        graph = build_test_graph()
        dirs = extract_directories(graph)
        paths = [d.path for d in dirs]
        # 'src' should come before 'src/data'
        assert paths.index("src") < paths.index("src/data")


class TestExtractFileEntries:
    """Test extract_file_entries from RPG graph."""

    def test_groups_nodes_by_file(self) -> None:
        graph = build_test_graph()
        files = extract_file_entries(graph)
        file_map = {f.path: f for f in files}
        # loaders.py should have 2 source nodes
        assert len(file_map["src/data/loaders.py"].source_node_ids) == 2
        # engine.py should have 2 source nodes
        assert len(file_map["src/processing/engine.py"].source_node_ids) == 2

    def test_sorted_by_path(self) -> None:
        graph = build_test_graph()
        files = extract_file_entries(graph)
        paths = [f.path for f in files]
        assert paths == sorted(paths)

    def test_empty_graph_returns_empty(self) -> None:
        graph = RPGGraph()
        files = extract_file_entries(graph)
        assert files == []


class TestBuildFileMap:
    """Test build_file_map."""

    def test_maps_nodes_to_files(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        assert "src/data/loaders.py" in file_map
        assert len(file_map["src/data/loaders.py"]) == 2

    def test_nodes_sorted_by_name(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        names = [n.name for n in file_map["src/data/loaders.py"]]
        assert names == sorted(names)

    def test_skips_nodes_without_file_path(self) -> None:
        graph = RPGGraph()
        node = RPGNode(
            name="orphan",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(node)
        file_map = build_file_map(graph)
        assert file_map == {}


class TestValidateFileStructure:
    """Test validate_file_structure."""

    def test_valid_structure_no_warnings(self) -> None:
        dirs = [DirectoryEntry(path="src"), DirectoryEntry(path="src/data")]
        files = [FileEntry(path="src/data/module.py")]
        warnings = validate_file_structure(dirs, files)
        assert warnings == []

    def test_duplicate_file_path_warning(self) -> None:
        dirs = [DirectoryEntry(path="src")]
        files = [
            FileEntry(path="src/module.py"),
            FileEntry(path="src/module.py"),
        ]
        warnings = validate_file_structure(dirs, files)
        assert any("Duplicate" in w for w in warnings)

    def test_missing_parent_directory_warning(self) -> None:
        dirs = [DirectoryEntry(path="src")]
        files = [FileEntry(path="src/nested/deep/module.py")]
        warnings = validate_file_structure(dirs, files)
        assert any("parent directory" in w for w in warnings)

    def test_path_conflict_warning(self) -> None:
        dirs = [DirectoryEntry(path="src"), DirectoryEntry(path="src/data")]
        files = [FileEntry(path="src/data")]  # Same as a directory
        warnings = validate_file_structure(dirs, files)
        assert any("conflict" in w.lower() for w in warnings)


class TestCreateDirectoryStructure:
    """Test create_directory_structure on disk."""

    def test_creates_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dirs = [
                DirectoryEntry(path="src"),
                DirectoryEntry(path="src/data"),
                DirectoryEntry(path="tests"),
            ]
            created = create_directory_structure(tmpdir, dirs)
            assert len(created) == 3
            for d in created:
                assert os.path.isdir(d)

    def test_existing_directories_no_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dirs = [DirectoryEntry(path="src")]
            create_directory_structure(tmpdir, dirs)
            # Call again - should not raise
            create_directory_structure(tmpdir, dirs)


# =================================================================
# Test Init Generator
# =================================================================

class TestGenerateInitContent:
    """Test __init__.py generation."""

    def test_generates_imports_from_nodes(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        content = generate_init_content("src/data", file_map)
        assert "from .loaders import" in content
        assert "load_data" in content
        assert "validate_data" in content

    def test_generates_all_list(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        content = generate_init_content("src/data", file_map)
        assert "__all__" in content

    def test_empty_package_no_exports(self) -> None:
        content = generate_init_content("src/empty", {})
        assert "No public exports" in content

    def test_private_names_excluded(self) -> None:
        graph = RPGGraph()
        node = make_node(name="_private_func", file_path="src/pkg/module.py", folder_path="src/pkg")
        graph.add_node(node)
        file_map = build_file_map(graph)
        content = generate_init_content("src/pkg", file_map)
        assert "_private_func" not in content


class TestCollectInitFiles:
    """Test collect_init_files."""

    def test_generates_init_for_each_dir(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        dirs = ["src/data", "src/processing"]
        inits = collect_init_files(dirs, file_map)
        assert len(inits) == 2
        assert all(f.is_package_init for f in inits)
        paths = {f.path for f in inits}
        assert "src/data/__init__.py" in paths
        assert "src/processing/__init__.py" in paths


# =================================================================
# Test Import Manager
# =================================================================

class TestClassifyImport:
    """Test import classification."""

    def test_stdlib_classified(self) -> None:
        assert classify_import("os") == ImportGroup.STDLIB
        assert classify_import("json") == ImportGroup.STDLIB
        assert classify_import("typing") == ImportGroup.STDLIB

    def test_third_party_classified(self) -> None:
        assert classify_import("numpy") == ImportGroup.THIRD_PARTY
        assert classify_import("pandas") == ImportGroup.THIRD_PARTY
        assert classify_import("requests") == ImportGroup.THIRD_PARTY

    def test_local_classified(self) -> None:
        assert classify_import("my_project") == ImportGroup.LOCAL
        assert classify_import("custom_module") == ImportGroup.LOCAL


class TestResolveImportsForFile:
    """Test cross-file import resolution."""

    def test_resolves_cross_file_imports(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        # engine.py depends on loaders.py via INVOCATION edges
        engine_nodes = file_map["src/processing/engine.py"]
        imports = resolve_imports_for_file(
            "src/processing/engine.py", engine_nodes, graph
        )
        # Should have import from src.data.loaders
        import_modules = [i.module_path for i in imports]
        assert any("src.data.loaders" in m for m in import_modules)

    def test_no_self_imports(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        loaders_nodes = file_map["src/data/loaders.py"]
        imports = resolve_imports_for_file(
            "src/data/loaders.py", loaders_nodes, graph
        )
        # Should not import from same file
        for imp in imports:
            assert imp.module_path != "src.data.loaders"

    def test_empty_graph_no_imports(self) -> None:
        graph = RPGGraph()
        imports = resolve_imports_for_file("src/test.py", [], graph)
        assert imports == []


class TestRenderImportBlock:
    """Test PEP 8 import block rendering."""

    def test_groups_with_blank_lines(self) -> None:
        imports = [
            ImportStatement(module_path="os", imported_names=["path"], group=ImportGroup.STDLIB),
            ImportStatement(module_path="numpy", imported_names=["array"], group=ImportGroup.THIRD_PARTY),
            ImportStatement(module_path="mymod", imported_names=["func"], group=ImportGroup.LOCAL),
        ]
        block = render_import_block(imports)
        lines = block.split("\n")
        # Should have blank lines between groups
        assert "" in lines

    def test_empty_imports(self) -> None:
        assert render_import_block([]) == ""

    def test_sorted_within_groups(self) -> None:
        imports = [
            ImportStatement(module_path="sys", imported_names=["exit"], group=ImportGroup.STDLIB),
            ImportStatement(module_path="os", imported_names=["path"], group=ImportGroup.STDLIB),
        ]
        block = render_import_block(imports)
        # 'os' should come before 'sys'
        assert block.index("os") < block.index("sys")


class TestDetectCircularImports:
    """Test circular import detection."""

    def test_no_cycles_in_dag(self) -> None:
        graph = build_test_graph()
        file_map = build_file_map(graph)
        cycles = detect_circular_imports(file_map, graph)
        assert cycles == []

    def test_detects_cycle(self) -> None:
        """Two files that mutually depend on each other."""
        graph = RPGGraph()
        n1 = make_node(name="func_a", file_path="src/a.py", folder_path="src")
        n2 = make_node(name="func_b", file_path="src/b.py", folder_path="src")
        graph.add_node(n1)
        graph.add_node(n2)
        # Mutual invocation edges
        e1 = make_edge(n1.id, n2.id, EdgeType.INVOCATION)
        e2 = make_edge(n2.id, n1.id, EdgeType.INVOCATION)
        graph.add_edge(e1)
        graph.add_edge(e2)

        file_map = build_file_map(graph)
        cycles = detect_circular_imports(file_map, graph)
        assert len(cycles) >= 1
        # The cycle should include both files
        flat = [item for cycle in cycles for item in cycle]
        assert "src/a.py" in flat
        assert "src/b.py" in flat


# =================================================================
# Test Requirements Generator
# =================================================================

class TestScanNodeImports:
    """Test scanning nodes for import statements."""

    def test_detects_import_in_implementation(self) -> None:
        node = make_node(
            implementation="import numpy\nfrom pandas import DataFrame\ndef f(): pass"
        )
        modules = scan_node_imports(node)
        assert "numpy" in modules
        assert "pandas" in modules

    def test_detects_import_in_test_code(self) -> None:
        node = make_node(test_code="import pytest\ndef test_f(): pass")
        modules = scan_node_imports(node)
        assert "pytest" in modules

    def test_no_imports_returns_empty(self) -> None:
        node = make_node(implementation="def f(): return 42")
        modules = scan_node_imports(node)
        # 'def' is not a module
        assert "def" not in modules


class TestDetectRequirements:
    """Test detect_requirements from RPG."""

    def test_detects_numpy(self) -> None:
        graph = RPGGraph()
        node = make_node(
            implementation="import numpy as np\ndef f(): pass"
        )
        graph.add_node(node)
        reqs = detect_requirements(graph)
        pkg_names = [r.package_name for r in reqs]
        assert "numpy" in pkg_names

    def test_skips_stdlib(self) -> None:
        graph = RPGGraph()
        node = make_node(implementation="import os\nimport json\ndef f(): pass")
        graph.add_node(node)
        reqs = detect_requirements(graph)
        pkg_names = [r.package_name for r in reqs]
        assert "os" not in pkg_names
        assert "json" not in pkg_names

    def test_deduplicated_requirements(self) -> None:
        graph = RPGGraph()
        n1 = make_node(name="f1", implementation="import numpy\ndef f1(): pass")
        n2 = make_node(name="f2", implementation="import numpy\ndef f2(): pass",
                       file_path="src/data/other.py")
        graph.add_node(n1)
        graph.add_node(n2)
        reqs = detect_requirements(graph)
        numpy_reqs = [r for r in reqs if r.package_name == "numpy"]
        assert len(numpy_reqs) == 1


class TestRenderRequirementsTxt:
    """Test requirements.txt rendering."""

    def test_renders_runtime_only(self) -> None:
        reqs = [
            RequirementEntry(package_name="numpy", version_spec=">=1.24.0,<2.0.0"),
            RequirementEntry(package_name="pytest", version_spec=">=8.0.0", is_dev=True),
        ]
        content = render_requirements_txt(reqs)
        assert "numpy>=1.24.0,<2.0.0" in content
        assert "pytest" not in content

    def test_includes_comment_header(self) -> None:
        content = render_requirements_txt([])
        assert "Auto-generated" in content


class TestRenderRequirementsDevTxt:
    """Test requirements-dev.txt rendering."""

    def test_includes_r_requirements(self) -> None:
        content = render_requirements_dev_txt([])
        assert "-r requirements.txt" in content

    def test_includes_default_dev_deps(self) -> None:
        content = render_requirements_dev_txt([])
        assert "pytest" in content
        assert "black" in content
        assert "mypy" in content


# =================================================================
# Test Project Generator
# =================================================================

class TestExtractProjectMetadata:
    """Test project metadata extraction."""

    def test_extracts_from_graph_metadata(self) -> None:
        graph = RPGGraph(
            metadata={
                "project_name": "my-project",
                "project_description": "A cool project",
                "version": "2.0.0",
            }
        )
        meta = extract_project_metadata(graph)
        assert meta["name"] == "my-project"
        assert meta["description"] == "A cool project"
        assert meta["version"] == "2.0.0"

    def test_defaults_for_missing_fields(self) -> None:
        graph = RPGGraph()
        meta = extract_project_metadata(graph)
        assert meta["name"] == "generated-project"
        assert meta["version"] == "0.1.0"
        assert meta["python_requires"] == ">=3.11"


class TestRenderPyprojectToml:
    """Test pyproject.toml rendering."""

    def test_contains_build_system(self) -> None:
        meta = {"name": "test", "version": "1.0.0"}
        content = render_pyproject_toml(meta, [])
        assert "[build-system]" in content
        assert "hatchling" in content

    def test_contains_project_section(self) -> None:
        meta = {"name": "test-proj", "version": "1.0.0", "description": "A test"}
        content = render_pyproject_toml(meta, [])
        assert '[project]' in content
        assert 'name = "test-proj"' in content

    def test_includes_dependencies(self) -> None:
        meta = {"name": "test"}
        reqs = [RequirementEntry(package_name="numpy", version_spec=">=1.24.0")]
        content = render_pyproject_toml(meta, reqs)
        assert "numpy>=1.24.0" in content


class TestRenderSetupPy:
    """Test setup.py rendering."""

    def test_contains_setup_call(self) -> None:
        meta = {"name": "test", "version": "1.0.0"}
        content = render_setup_py(meta, [])
        assert "setup(" in content
        assert "find_packages" in content

    def test_includes_requirements(self) -> None:
        meta = {"name": "test"}
        reqs = [RequirementEntry(package_name="pandas", version_spec=">=2.0.0")]
        content = render_setup_py(meta, reqs)
        assert "pandas>=2.0.0" in content


# =================================================================
# Test README Generator
# =================================================================

class TestGenerateReadme:
    """Test README.md generation."""

    def test_includes_project_name(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta)
        assert "# test-project" in readme

    def test_includes_installation_instructions(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta)
        assert "pip install -e ." in readme

    def test_includes_testing_instructions(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta)
        assert "pytest tests/" in readme

    def test_includes_modules_table(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta)
        assert "## Modules" in readme
        assert "| Module |" in readme

    def test_includes_nl_spec_overview(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta, nl_spec="This is a machine learning project.")
        assert "## Overview" in readme
        assert "machine learning" in readme

    def test_includes_coverage_summary(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        coverage = CoverageReport(
            total_nodes=20, passed_nodes=15, failed_nodes=3, skipped_nodes=2,
        )
        readme = generate_readme(graph, meta, coverage=coverage)
        assert "## Generation Summary" in readme
        assert "15" in readme

    def test_includes_rpg_artifact_reference(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta)
        assert "docs/rpg.json" in readme

    def test_includes_zerorepo_attribution(self) -> None:
        graph = build_test_graph()
        meta = extract_project_metadata(graph)
        readme = generate_readme(graph, meta)
        assert "ZeroRepo" in readme


# =================================================================
# Test RPG Exporter
# =================================================================

class TestExportRpgArtifact:
    """Test RPG artifact export to JSON."""

    def test_produces_valid_json(self) -> None:
        graph = build_test_graph()
        json_str = export_rpg_artifact(graph)
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_includes_all_nodes(self) -> None:
        graph = build_test_graph()
        json_str = export_rpg_artifact(graph)
        data = json.loads(json_str)
        assert data["node_count"] == 5

    def test_includes_all_edges(self) -> None:
        graph = build_test_graph()
        json_str = export_rpg_artifact(graph)
        data = json.loads(json_str)
        assert data["edge_count"] == 3

    def test_includes_metadata(self) -> None:
        graph = build_test_graph()
        json_str = export_rpg_artifact(
            graph,
            generation_metadata={"model": "gpt-4", "phase": 4},
        )
        data = json.loads(json_str)
        assert data["metadata"]["model"] == "gpt-4"

    def test_includes_timestamp(self) -> None:
        graph = build_test_graph()
        json_str = export_rpg_artifact(graph)
        data = json.loads(json_str)
        assert "export_timestamp" in data

    def test_pretty_printed(self) -> None:
        graph = build_test_graph()
        json_str = export_rpg_artifact(graph)
        # Pretty-printed JSON has newlines
        assert "\n" in json_str


class TestExportRpgSummary:
    """Test RPG summary export."""

    def test_summary_structure(self) -> None:
        graph = build_test_graph()
        summary = export_rpg_summary(graph)
        assert "total_nodes" in summary
        assert "total_edges" in summary
        assert "nodes" in summary
        assert "edges" in summary

    def test_node_summary_fields(self) -> None:
        graph = build_test_graph()
        summary = export_rpg_summary(graph)
        node = summary["nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "status" in node


# =================================================================
# Test Coverage Report
# =================================================================

class TestBuildCoverageReport:
    """Test coverage report building from RPG."""

    def test_counts_statuses(self) -> None:
        graph = RPGGraph()
        n1 = make_node(name="passed_func")
        n1.test_status = TestStatus.PASSED
        n2 = make_node(name="failed_func", file_path="src/data/other.py")
        n2.test_status = TestStatus.FAILED
        n3 = make_node(name="skipped_func", file_path="src/data/third.py")
        n3.test_status = TestStatus.SKIPPED
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        report = build_coverage_report(graph)
        assert report.total_nodes == 3
        assert report.passed_nodes == 1
        assert report.failed_nodes == 1
        assert report.skipped_nodes == 1

    def test_subgraph_breakdown(self) -> None:
        graph = RPGGraph()
        n1 = make_node(name="func_a", file_path="src/data/mod.py", folder_path="src/data")
        n1.test_status = TestStatus.PASSED
        n2 = make_node(name="func_b", file_path="src/proc/mod.py", folder_path="src/proc")
        n2.test_status = TestStatus.FAILED
        graph.add_node(n1)
        graph.add_node(n2)

        report = build_coverage_report(graph)
        assert len(report.subgraph_breakdown) == 2
        sg_ids = {sg.subgraph_id for sg in report.subgraph_breakdown}
        assert "data" in sg_ids
        assert "proc" in sg_ids

    def test_generation_time_stored(self) -> None:
        graph = RPGGraph()
        report = build_coverage_report(graph, generation_time_seconds=120.5)
        assert report.generation_time_seconds == 120.5

    def test_pass_rate(self) -> None:
        graph = RPGGraph()
        for i in range(10):
            n = make_node(name=f"func_{i}", file_path=f"src/data/mod{i}.py")
            if i < 6:
                n.test_status = TestStatus.PASSED
            else:
                n.test_status = TestStatus.FAILED
            graph.add_node(n)

        report = build_coverage_report(graph)
        assert report.pass_rate == 60.0


class TestRenderCoverageMarkdown:
    """Test coverage report Markdown rendering."""

    def test_includes_summary_section(self) -> None:
        graph = build_test_graph()
        report = build_coverage_report(graph)
        md = render_coverage_markdown(report)
        assert "# Code Generation Report" in md
        assert "## Summary" in md

    def test_includes_subgraph_table(self) -> None:
        graph = build_test_graph()
        report = build_coverage_report(graph)
        md = render_coverage_markdown(report)
        assert "## Breakdown by Subgraph" in md
        assert "| Subgraph |" in md

    def test_includes_failed_details(self) -> None:
        graph = RPGGraph()
        n = make_node(name="buggy_func")
        n.test_status = TestStatus.FAILED
        n.metadata["failure_reason"] = "AssertionError"
        n.metadata["retry_count"] = 8
        graph.add_node(n)

        report = build_coverage_report(graph)
        md = render_coverage_markdown(report)
        assert "## Failed Nodes" in md
        assert "buggy_func" in md
        assert "AssertionError" in md

    def test_includes_performance_section(self) -> None:
        graph = RPGGraph()
        report = build_coverage_report(graph, generation_time_seconds=600.0)
        md = render_coverage_markdown(report)
        assert "## Performance" in md
        assert "10.0 minutes" in md

    def test_includes_recommendations(self) -> None:
        graph = build_test_graph()
        report = build_coverage_report(graph)
        md = render_coverage_markdown(report)
        assert "## Recommendations" in md

    def test_coverage_report_shows_percentage(self) -> None:
        """Coverage report shows 15/20 passed (75%)."""
        graph = RPGGraph()
        for i in range(20):
            n = make_node(name=f"node_{i}", file_path=f"src/pkg/mod{i}.py", folder_path="src/pkg")
            if i < 15:
                n.test_status = TestStatus.PASSED
            elif i < 18:
                n.test_status = TestStatus.FAILED
            else:
                n.test_status = TestStatus.SKIPPED
            graph.add_node(n)

        report = build_coverage_report(graph)
        md = render_coverage_markdown(report)
        assert "75.0%" in md
        assert "15" in md
        assert "20" in md


# =================================================================
# Test __init__.py Package Exports
# =================================================================

class TestPackageExports:
    """Test that all public API is available from zerorepo.codegen."""

    def test_assembly_error_exported(self) -> None:
        from zerorepo.codegen import AssemblyError
        assert AssemblyError is not None

    def test_file_structure_functions_exported(self) -> None:
        from zerorepo.codegen import (
            extract_directories,
            extract_file_entries,
            build_file_map,
            validate_file_structure,
            create_directory_structure,
        )
        assert callable(extract_directories)

    def test_import_management_exported(self) -> None:
        from zerorepo.codegen import (
            classify_import,
            resolve_imports_for_file,
            render_import_block,
            detect_circular_imports,
        )
        assert callable(classify_import)

    def test_project_generation_exported(self) -> None:
        from zerorepo.codegen import (
            extract_project_metadata,
            render_pyproject_toml,
            render_setup_py,
        )
        assert callable(render_pyproject_toml)

    def test_readme_exported(self) -> None:
        from zerorepo.codegen import generate_readme
        assert callable(generate_readme)

    def test_requirements_exported(self) -> None:
        from zerorepo.codegen import (
            detect_requirements,
            render_requirements_txt,
            render_requirements_dev_txt,
        )
        assert callable(detect_requirements)

    def test_rpg_export_functions_exported(self) -> None:
        from zerorepo.codegen import export_rpg_artifact, export_rpg_summary
        assert callable(export_rpg_artifact)

    def test_coverage_functions_exported(self) -> None:
        from zerorepo.codegen import build_coverage_report, render_coverage_markdown
        assert callable(build_coverage_report)

    def test_models_exported(self) -> None:
        from zerorepo.codegen import (
            CoverageReport,
            DirectoryEntry,
            FileEntry,
            ImportGroup,
            ImportStatement,
            NodeCoverageEntry,
            RepositoryManifest,
            RequirementEntry,
            SubgraphCoverage,
        )
        assert CoverageReport is not None
