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
- :class:`TDDLoop` -- Test-driven development generation loop
- :class:`LLMImplementationGenerator` -- LLM-backed code generation
- :class:`DockerSandboxExecutor` -- Docker sandbox test executor
- :class:`MajorityVoteDiagnoser` -- Majority-vote failure diagnosis
- :class:`CodegenOrchestrator` -- Main code generation orchestrator
- :class:`UnitValidator` -- Staged unit test validation
- :class:`RegressionDetector` -- Cross-iteration regression detection
- :class:`IntegrationGenerator` -- Cross-node integration test generation
- :class:`MajorityVoter` -- Majority voting for test result consensus
- :class:`TestArtifactStore` -- Test artifact lifecycle management
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

# Epic 4.2: TDD Generation Loop
from zerorepo.codegen.codegen_orchestrator import (
    CodegenOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
)
from zerorepo.codegen.debugging_loop import (
    MajorityVoteDiagnoser,
)
from zerorepo.codegen.impl_generator import (
    GeneratedCode,
    LLMImplementationGenerator,
)
from zerorepo.codegen.sandbox_executor import (
    DockerSandboxExecutor,
    InProcessSandboxExecutor,
    SandboxExecutorConfig,
)
from zerorepo.codegen.tdd_loop import (
    DiagnosisResult,
    SandboxResult,
    TDDIterationResult,
    TDDLoop,
    TDDLoopResult,
)

# Epic 4.5: Staged Test Validation
from zerorepo.codegen.integration_generator import (
    DependencyEdge,
    IntegrationGenerator,
    IntegrationGeneratorConfig,
    IntegrationTestCase,
    IntegrationTestSuite,
    IntegrationTestType,
    NodeInterface,
)
from zerorepo.codegen.majority_vote import (
    MajorityVoteConfig,
    MajorityVoter,
    NodeVoteResult,
    TestRunVote,
    TestVerdictDetail,
    VoteConfidence,
    VoteOutcome,
)
from zerorepo.codegen.regression_detector import (
    Regression,
    RegressionDetector,
    RegressionDetectorConfig,
    RegressionReport,
    RegressionSeverity,
    RegressionType,
    TestSnapshot,
)
from zerorepo.codegen.test_artifacts import (
    ArtifactQuery,
    ArtifactStatus,
    ArtifactStoreConfig,
    ArtifactSummary,
    ArtifactType,
    TestArtifact,
    TestArtifactStore,
)
from zerorepo.codegen.unit_validator import (
    SingleTestResult,
    TestOutcome,
    UnitValidator,
    UnitValidatorConfig,
    ValidationResult,
    ValidationStage,
)

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
    # Epic 4.2: TDD Generation Loop
    "CodegenOrchestrator",
    "DiagnosisResult",
    "DockerSandboxExecutor",
    "GeneratedCode",
    "InProcessSandboxExecutor",
    "LLMImplementationGenerator",
    "MajorityVoteDiagnoser",
    "OrchestratorConfig",
    "OrchestratorResult",
    "SandboxExecutorConfig",
    "SandboxResult",
    "TDDIterationResult",
    "TDDLoop",
    "TDDLoopResult",
    # Epic 4.5: Staged Test Validation - Unit Validator
    "SingleTestResult",
    "TestOutcome",
    "UnitValidator",
    "UnitValidatorConfig",
    "ValidationResult",
    "ValidationStage",
    # Epic 4.5: Staged Test Validation - Regression Detector
    "Regression",
    "RegressionDetector",
    "RegressionDetectorConfig",
    "RegressionReport",
    "RegressionSeverity",
    "RegressionType",
    "TestSnapshot",
    # Epic 4.5: Staged Test Validation - Integration Generator
    "DependencyEdge",
    "IntegrationGenerator",
    "IntegrationGeneratorConfig",
    "IntegrationTestCase",
    "IntegrationTestSuite",
    "IntegrationTestType",
    "NodeInterface",
    # Epic 4.5: Staged Test Validation - Majority Vote
    "MajorityVoteConfig",
    "MajorityVoter",
    "NodeVoteResult",
    "TestRunVote",
    "TestVerdictDetail",
    "VoteConfidence",
    "VoteOutcome",
    # Epic 4.5: Staged Test Validation - Test Artifacts
    "ArtifactQuery",
    "ArtifactStatus",
    "ArtifactStoreConfig",
    "ArtifactSummary",
    "ArtifactType",
    "TestArtifact",
    "TestArtifactStore",
    # Epic 4.7: Workspace Management
    "BatchedFileWriter",
    "GracefulShutdownHandler",
    "ProgressLogger",
    "RepositoryStateManager",
    "SerenaReindexer",
]
