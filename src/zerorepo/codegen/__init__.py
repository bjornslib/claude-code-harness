"""ZeroRepo Code Generation -- graph-guided code generation pipeline.

This package implements Phase 4 of the RPG system, providing:

- :class:`LocalizationResult` -- Localization search result model
- :class:`DependencyMap` -- N-hop dependency neighbourhood model
- :class:`LocalizationExhaustedError` -- Query limit exceeded error
- :class:`RPGFuzzySearch` -- Embedding-based search over RPG nodes
- :class:`RepositoryCodeView` -- Source code reading and AST extraction
- :class:`DependencyExplorer` -- N-hop neighbourhood exploration
- :class:`LocalizationTracker` -- Query logging with repetition avoidance
- :class:`SerenaEditor` -- Structural code editing via Serena MCP
- :class:`LocalizationOrchestrator` -- Coordinated Serena+RPG localization
- :class:`BatchedFileWriter` -- Atomic batched file writing
- :class:`SerenaReindexer` -- Serena LSP re-indexing
- :class:`RepositoryStateManager` -- File state tracking and validation
- :class:`ProgressLogger` -- Progress logging with ETA
- :class:`GracefulShutdownHandler` -- Signal-based graceful shutdown
"""

from zerorepo.codegen.checkpoint import CheckpointManager
from zerorepo.codegen.file_writer import BatchedFileWriter
from zerorepo.codegen.localization import (
    DependencyExplorer,
    LocalizationTracker,
    RPGFuzzySearch,
    RepositoryCodeView,
)
from zerorepo.codegen.localization_models import (
    DependencyMap,
    LocalizationExhaustedError,
    LocalizationResult,
)
from zerorepo.codegen.localization_orchestrator import LocalizationOrchestrator

# Epic 4.6: Repository Assembly
from zerorepo.codegen.coverage_report import (
    build_coverage_report,
    render_coverage_markdown,
)
from zerorepo.codegen.exceptions import (
    AssemblyError,
    CircularImportError,
    FileStructureError,
    ImportResolutionError,
    MetadataExtractionError,
)
from zerorepo.codegen.file_structure import (
    build_file_map,
    create_directory_structure,
    extract_directories,
    extract_file_entries,
    validate_file_structure,
)
from zerorepo.codegen.import_manager import (
    classify_import,
    detect_circular_imports,
    render_import_block,
    resolve_imports_for_file,
)
from zerorepo.codegen.init_generator import (
    collect_init_files,
    generate_init_content,
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
from zerorepo.codegen.project_generator import (
    extract_project_metadata,
    render_pyproject_toml,
    render_setup_py,
)
from zerorepo.codegen.readme_generator import generate_readme
from zerorepo.codegen.requirements_generator import (
    detect_requirements,
    render_requirements_dev_txt,
    render_requirements_txt,
)
from zerorepo.codegen.rpg_exporter import (
    export_rpg_artifact,
    export_rpg_summary,
)

# Epic 4.7: Workspace Management
from zerorepo.codegen.progress import ProgressLogger
from zerorepo.codegen.reindexer import SerenaReindexer
from zerorepo.codegen.repo_state import RepositoryStateManager
from zerorepo.codegen.serena_editing import SerenaEditor
from zerorepo.codegen.signal_handler import GracefulShutdownHandler
from zerorepo.codegen.state import (
    GenerationState,
    GenerationStatus,
    NodeGenerationState,
    TestResults,
)
from zerorepo.codegen.traversal import TraversalEngine, TraversalReport

__all__ = [
    # Epic 4.1: Traversal
    "CheckpointManager",
    "GenerationState",
    "GenerationStatus",
    "NodeGenerationState",
    "TestResults",
    "TraversalEngine",
    "TraversalReport",
    # Epic 4.3/4.4: Localization & Serena
    "DependencyExplorer",
    "DependencyMap",
    "LocalizationExhaustedError",
    "LocalizationOrchestrator",
    "LocalizationResult",
    "LocalizationTracker",
    "RPGFuzzySearch",
    "RepositoryCodeView",
    "SerenaEditor",
    # Epic 4.6: Repository Assembly - Exceptions
    "AssemblyError",
    "CircularImportError",
    "FileStructureError",
    "ImportResolutionError",
    "MetadataExtractionError",
    # Epic 4.6: Repository Assembly - Models
    "CoverageReport",
    "DirectoryEntry",
    "FileEntry",
    "ImportGroup",
    "ImportStatement",
    "NodeCoverageEntry",
    "RepositoryManifest",
    "RequirementEntry",
    "SubgraphCoverage",
    # Epic 4.6: Repository Assembly - Functions
    "build_coverage_report",
    "build_file_map",
    "classify_import",
    "collect_init_files",
    "create_directory_structure",
    "detect_circular_imports",
    "detect_requirements",
    "export_rpg_artifact",
    "export_rpg_summary",
    "extract_directories",
    "extract_file_entries",
    "extract_project_metadata",
    "generate_init_content",
    "generate_readme",
    "render_coverage_markdown",
    "render_import_block",
    "render_pyproject_toml",
    "render_requirements_dev_txt",
    "render_requirements_txt",
    "render_setup_py",
    "resolve_imports_for_file",
    "validate_file_structure",
    # Epic 4.7: Workspace Management
    "BatchedFileWriter",
    "GracefulShutdownHandler",
    "ProgressLogger",
    "RepositoryStateManager",
    "SerenaReindexer",
]
