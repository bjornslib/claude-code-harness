# ZeroRepo Module Reference

Detailed documentation for all 14 modules in ZeroRepo, organized by pipeline stage order.

**Total**: 39.1K LOC across 14 modules, 4191 tests.

---

## Table of Contents

1. [models](#1-models) -- Core data models (RPGNode, RPGEdge, RPGGraph)
2. [spec_parser](#2-spec_parser) -- Natural language specification parsing
3. [ontology](#3-ontology) -- Feature taxonomy with LLM & ChromaDB backends
4. [graph_construction](#4-graph_construction) -- Functionality graph from features
5. [selection](#5-selection) -- Explore-exploit feature selection
6. [rpg_enrichment](#6-rpg_enrichment) -- RPG encoder pipeline for metadata
7. [codegen](#7-codegen) -- Code generation orchestration & TDD pipeline
8. [evaluation](#8-evaluation) -- Benchmarking, metrics, failure analysis
9. [graph_ops](#9-graph_ops) -- Graph traversal utilities
10. [llm](#10-llm) -- LLM gateway (LiteLLM wrapper)
11. [vectordb](#11-vectordb) -- ChromaDB wrapper
12. [sandbox](#12-sandbox) -- Docker sandbox for test execution
13. [serena](#13-serena) -- Serena MCP client for LSP validation
14. [cli](#14-cli) -- Typer-based CLI

---

## 1. models

**Purpose**: Core Pydantic data models that define the Repository Planning Graph structure. All other modules depend on these models.

**Files**: 5 files, 561 LOC

### Enumerations (`models/enums.py`)

| Enum | Values | Description |
|------|--------|-------------|
| `NodeLevel` | `MODULE`, `COMPONENT`, `FEATURE` | Hierarchical level of a node |
| `NodeType` | `FUNCTIONALITY`, `FOLDER_AUGMENTED`, `FILE_AUGMENTED`, `FUNCTION_AUGMENTED` | Type classification |
| `InterfaceType` | `FUNCTION`, `CLASS`, `METHOD` | Interface type for FUNCTION_AUGMENTED nodes |
| `TestStatus` | `PENDING`, `PASSED`, `FAILED`, `SKIPPED` | Test execution status |
| `EdgeType` | `HIERARCHY`, `DATA_FLOW`, `ORDERING`, `INHERITANCE`, `INVOCATION` | Edge relationship types |

### RPGNode (`models/node.py`)

A node in the Repository Planning Graph representing a unit of planning/implementation.

```python
class RPGNode(BaseModel):
    id: UUID                              # Unique node identifier (auto-generated)
    name: str                             # Human-readable name (1-200 chars)
    level: NodeLevel                      # MODULE, COMPONENT, or FEATURE
    node_type: NodeType                   # Functionality/augmentation type
    parent_id: Optional[UUID]             # Parent node in hierarchy
    folder_path: Optional[str]            # Relative folder path
    file_path: Optional[str]              # Relative file path
    interface_type: Optional[InterfaceType]  # Required for FUNCTION_AUGMENTED
    signature: Optional[str]              # Python function/method signature
    docstring: Optional[str]              # Documentation string
    implementation: Optional[str]         # Python implementation code
    test_code: Optional[str]              # Pytest test code
    test_status: TestStatus               # PENDING/PASSED/FAILED/SKIPPED
    serena_validated: bool                # Whether Serena has validated this node
    actual_dependencies: list[UUID]       # Runtime deps (populated by Serena)
    metadata: dict[str, Any]              # Arbitrary metadata
```

**Validation constraints**:
- `file_path` must be a child of `folder_path` when both are present
- `signature` is required when `interface_type` is set
- `implementation` cannot be set without `file_path`
- `interface_type` is required when `node_type` is `FUNCTION_AUGMENTED`
- Paths must be relative (no leading `/`)

### RPGEdge (`models/edge.py`)

A directed relationship between two RPGNode instances.

```python
class RPGEdge(BaseModel):
    id: UUID                     # Unique edge identifier
    source_id: UUID              # Source node UUID
    target_id: UUID              # Target node UUID
    edge_type: EdgeType          # HIERARCHY, DATA_FLOW, ORDERING, etc.
    data_id: Optional[str]       # Data identifier (DATA_FLOW only)
    data_type: Optional[str]     # Type annotation (DATA_FLOW only)
    transformation: Optional[str]  # Data transformation (DATA_FLOW only)
    validated: bool              # Whether this edge has been validated
```

**Validation constraints**:
- No self-loops (`source_id != target_id`)
- `data_id`, `data_type`, `transformation` only valid for `DATA_FLOW` edges

### RPGGraph (`models/graph.py`)

Container managing nodes and edges with referential integrity.

```python
class RPGGraph(BaseModel):
    nodes: dict[UUID, RPGNode]    # Nodes indexed by UUID
    edges: dict[UUID, RPGEdge]    # Edges indexed by UUID
    metadata: dict[str, Any]      # Graph-level metadata

    def add_node(self, node: RPGNode) -> UUID
    def add_edge(self, edge: RPGEdge) -> UUID
    def get_node(self, node_id: UUID) -> Optional[RPGNode]
    def get_edge(self, edge_id: UUID) -> Optional[RPGEdge]
    def remove_node(self, node_id: UUID) -> bool       # Cascades to connected edges
    def remove_edge(self, edge_id: UUID) -> bool
    def to_json(self, indent: int = 2) -> str
    @classmethod
    def from_json(cls, json_str: str) -> RPGGraph
    @property
    def node_count(self) -> int
    @property
    def edge_count(self) -> int
```

**Dependencies**: None (foundational module)

---

## 2. spec_parser

**Purpose**: Parse natural language repository descriptions into structured `RepositorySpec` instances using LLM-assisted extraction, conflict detection, iterative refinement, and reference material processing.

**Files**: 6 files, 3583 LOC

### Key Classes

#### SpecParser (`spec_parser/parser.py`)

Two-phase LLM-based parser: extraction (LLM -> intermediate JSON) then assembly (normalize + validate).

```python
class SpecParser:
    def __init__(
        self,
        config: ParserConfig | None = None,
        gateway: LLMGateway | None = None,
        templates: PromptTemplate | None = None,
    ) -> None

    def parse(
        self,
        description: str,              # 10-50000 chars natural language
        context: str | None = None,
    ) -> RepositorySpec
```

**Config**: `ParserConfig(model="gpt-4o-mini", tier=ModelTier.CHEAP, template_name="spec_parsing", max_description_length=50000, use_json_mode=True)`

#### ConflictDetector (`spec_parser/conflict_detector.py`)

Combines rule-based heuristics with LLM analysis for conflict detection.

```python
class ConflictDetector:
    def __init__(
        self,
        config: DetectorConfig | None = None,
        gateway: LLMGateway | None = None,
        templates: PromptTemplate | None = None,
    ) -> None

    def detect(self, spec: RepositorySpec) -> list[SpecConflict]
    def detect_and_attach(self, spec: RepositorySpec) -> list[SpecConflict]
```

**Rule-based checks**: scope vs. frameworks, language vs. deployment, serverless vs. long-running, scope vs. platforms.

**Modes**: rules + LLM (default), rules-only (`use_llm=False`), LLM-only (`use_rules=False`).

#### SpecRefiner (`spec_parser/refinement.py`)

Iterative specification refinement with full history tracking.

```python
class SpecRefiner:
    def add_requirement(self, spec, requirement_text, context=None) -> RepositorySpec
    def remove_requirement(self, spec, constraint_id: UUID) -> RepositorySpec
    def clarify(self, spec, question, answer, context=None) -> RepositorySpec
    def suggest_improvements(self, spec) -> SuggestionResponse
    def get_history(self, spec) -> list[RefinementEntry]
```

#### ReferenceProcessor (`spec_parser/reference_processor.py`)

Extracts concepts from reference materials using content extraction strategies + LLM.

```python
class ReferenceProcessor:
    def __init__(self, llm_gateway, config=None, extractors=None) -> None
    def extract_content(self, reference: ReferenceMaterial) -> ExtractionResult
    def extract_concepts(self, reference: ReferenceMaterial) -> list[str]
    def extract_concepts_from_text(self, text: str) -> list[str]
    def process_spec_references(self, spec: RepositorySpec) -> dict[str, list[str]]
```

**Content extractors** (strategy pattern):
- `InlineContentExtractor` -- handles any reference with inline content
- `CodeContentExtractor` -- regex-based identifier extraction from code samples
- `PDFContentExtractor` -- PDF text extraction via pdfplumber

### Data Models (`spec_parser/models.py`)

| Model | Description |
|-------|-------------|
| `RepositorySpec` | Top-level spec container (description, technical reqs, quality attrs, constraints, references, conflicts, refinement history) |
| `TechnicalRequirement` | Languages, frameworks, platforms, deployment targets, scope |
| `QualityAttributes` | Performance, security, scalability, reliability, maintainability |
| `Constraint` | Priority-classified requirement (MUST_HAVE / SHOULD_HAVE / NICE_TO_HAVE) |
| `ReferenceMaterial` | Reference docs with type (API_DOCUMENTATION, CODE_SAMPLE, RESEARCH_PAPER, GITHUB_REPO) |
| `SpecConflict` | Detected conflict with severity (ERROR / WARNING / INFO) |
| `RefinementEntry` | History entry for iterative refinement |

**Dependencies**: `llm` (LLMGateway, PromptTemplate)

---

## 3. ontology

**Purpose**: Build and manage a hierarchical feature taxonomy. Provides LLM-generated ontologies, ChromaDB-backed semantic search, batch embedding, domain extension, and a unified service facade.

**Files**: 15 files, 6552 LOC

### Key Classes

#### OntologyService (`ontology/service.py`)

Unified facade orchestrating all ontology subsystems.

```python
class OntologyService:
    @classmethod
    def create(cls, project_dir: Path) -> OntologyService
    def build(self) -> BuildResult                          # Generate seed ontology, embed, store
    def search(self, query: str, top_k: int = 10) -> list[SearchResult]
    def stats(self) -> OntologyStats
    def extend(self, features: list[FeatureNode], conflict: ConflictResolution = ...) -> ExtensionResult
    def export(self, path: Path, format: str = "csv") -> None
```

**Config**: `OntologyServiceConfig(store_config, embedder_config, include_github=True, include_stackoverflow=True, include_libraries=True, include_expander=True)`

#### LLMOntologyBackend (`ontology/llm_backend.py`)

LLM-generated ontology backend using structured output.

```python
class LLMOntologyBackend(OntologyBackend):
    def __init__(self, config: LLMBackendConfig, gateway: LLMGateway) -> None
    def build_ontology(self, spec: RepositorySpec) -> list[FeatureNode]
    def search(self, query: str, top_k: int) -> list[FeaturePath]
    def get_stats(self) -> OntologyStats
```

#### FeatureEmbedder (`ontology/embeddings.py`)

Batch embedding pipeline for feature nodes.

```python
class FeatureEmbedder:
    def __init__(self, config: EmbedderConfig) -> None
    def embed_nodes(self, nodes: list[FeatureNode]) -> EmbeddingResult
```

#### OntologyChromaStore (`ontology/chromadb_store.py`)

ChromaDB-backed persistent ontology storage.

```python
class OntologyChromaStore:
    def __init__(self, config: OntologyStoreConfig) -> None
    def store_nodes(self, nodes: list[FeatureNode]) -> None
    def search(self, query: str, top_k: int) -> list[FeaturePath]
```

#### OntologyExtensionAPI (`ontology/extension.py`)

Domain extension for adding custom features.

```python
class OntologyExtensionAPI:
    def extend(self, features: list[FeatureNode], conflict: ConflictResolution) -> ExtensionResult
```

### Data Models (`ontology/models.py`)

| Model | Description |
|-------|-------------|
| `FeatureNode` | Node in the feature ontology tree (id, name, description, parent_id, level, tags, embedding, metadata) |
| `FeaturePath` | Ranked search result -- ordered path from root to leaf with relevance score |
| `OntologyStats` | Aggregate statistics (total_nodes, total_levels, avg_children, max_depth, etc.) |

**Dependencies**: `llm`, `vectordb`, `spec_parser` (RepositorySpec)

---

## 4. graph_construction

**Purpose**: Build functionality graphs from feature sets by clustering features into modules, inferring inter-module dependencies, computing quality metrics, refining the graph, and exporting to multiple formats.

**Files**: 7 files, 4644 LOC

### Key Classes

#### FunctionalityGraphBuilder (`graph_construction/builder.py`)

Full pipeline: partition -> dependency inference -> metrics -> assembly into NetworkX graph.

```python
class FunctionalityGraphBuilder:
    def __init__(self, llm_gateway: LLMGateway, config: BuilderConfig | None = None) -> None
    def build(self, features: list[FeatureNode]) -> FunctionalityGraph
```

**Config**: `BuilderConfig(partitioner_config, dependency_config, metrics_config, require_acyclic=True, compute_metrics=True)`

#### FunctionalityGraph (result object)

Built graph with export methods.

```python
class FunctionalityGraph:
    graph: nx.DiGraph                                     # NetworkX directed graph
    modules: list[ModuleSpec]                             # Module specifications
    partition: PartitionResult                            # Partition result
    dependencies: DependencyResult                        # Dependency result
    metrics: Optional[PartitionMetrics]                   # Quality metrics
    def to_json(self, path: str) -> None
    def to_graphml(self, path: str) -> None
```

#### ModulePartitioner (`graph_construction/partitioner.py`)

LLM-driven feature clustering into modules.

```python
class ModulePartitioner:
    def __init__(self, config: PartitionerConfig, gateway: LLMGateway) -> None
    def partition(self, features: list[FeatureNode]) -> PartitionResult
```

#### DependencyInference (`graph_construction/dependencies.py`)

LLM-driven module dependency detection.

```python
class DependencyInference:
    def __init__(self, config: DependencyConfig, gateway: LLMGateway) -> None
    def infer(self, modules: list[ModuleSpec]) -> DependencyResult
```

#### Quality Metrics (`graph_construction/metrics.py`)

```python
def compute_cohesion(partition, config=None) -> list[CohesionResult]
def compute_coupling(partition, config=None) -> list[CouplingResult]
def compute_modularity(partition, config=None) -> ModularityResult   # Newman's Q-score
def compute_all_metrics(partition, config=None) -> PartitionMetrics
```

#### GraphRefinement (`graph_construction/refinement.py`)

Iterative refinement engine with undo support.

```python
class GraphRefinement:
    def __init__(self, config: RefinementConfig) -> None
    def refine(self, graph: FunctionalityGraph) -> RefinementResult
    def undo(self) -> RefinementResult
```

#### GraphExporter (`graph_construction/export.py`)

Unified export service.

```python
class GraphExporter:
    def export(self, graph, format: ExportFormat, path: Path) -> ExportResult
```

Supported formats: `JSON`, `GRAPHML`, `DOT`, `CSV`

**Dependencies**: `llm`, `ontology` (FeatureNode), `networkx`

---

## 5. selection

**Purpose**: Explore-exploit subtree selection implementing Algorithm 2 from the PRD. Alternates between exploitation (vector search), exploration (coverage-gap queries), diversity sampling, LLM filtering, and convergence monitoring.

**Files**: 7 files, 3966 LOC

### Key Classes

#### ExploreExploitOrchestrator (`selection/orchestrator.py`)

Main selection loop implementing Algorithm 2.

```python
class ExploreExploitOrchestrator:
    def __init__(
        self,
        store: OntologyBackend,
        llm_gateway: LLMGateway,
        config: OrchestratorConfig | None = None,
    ) -> None

    def run(self, spec_description: str) -> OrchestrationResult
```

**Config**: `OrchestratorConfig(max_iterations=100, exploit_top_k=50, explore_top_k=20, diversity_threshold=0.85, filter_interval=5, convergence_window=5)`

**Result**: `OrchestrationResult(selected_features, iterations_run, diversity_metrics, convergence_summary, coverage_stats)`

#### ExploitationRetriever (`selection/exploitation.py`)

Vector search with LLM query augmentation.

```python
class ExploitationRetriever:
    def __init__(self, config: ExploitationConfig, store, gateway) -> None
    def retrieve(self, spec_description: str) -> RetrievalResult
```

#### ExplorationStrategy / CoverageTracker (`selection/exploration.py`)

Gap-based exploratory query generation with bit-vector coverage tracking.

```python
class CoverageTracker:
    def update(self, feature: FeatureNode) -> None
    def get_uncovered(self) -> set[str]
    def get_stats(self) -> CoverageStats

class ExplorationStrategy:
    def explore(self, uncovered_branches: set[str]) -> ExplorationResult
```

#### DiversitySampler (`selection/diversity_sampler.py`)

Rejection sampling with cosine similarity.

```python
class DiversitySampler:
    def __init__(self, config: DiversityConfig) -> None
    def sample(self, candidates, selected, threshold: float) -> SamplingResult
    def compute_metrics(self, features) -> DiversityMetrics
```

#### LLMFilter (`selection/llm_filter.py`)

LLM-based feature relevance filtering.

```python
class LLMFilter:
    def __init__(self, config: LLMFilterConfig, gateway) -> None
    def filter(self, features, spec_description) -> FilterResult
```

#### ConvergenceMonitor (`selection/convergence.py`)

Iteration convergence tracking with plateau detection.

```python
class ConvergenceMonitor:
    def __init__(self, config: ConvergenceConfig) -> None
    def record(self, iteration_data: ConvergenceSnapshot) -> None
    def has_converged(self) -> bool
```

**Dependencies**: `llm`, `ontology` (OntologyBackend, FeatureNode, FeaturePath), `vectordb`

---

## 6. rpg_enrichment

**Purpose**: Encoder pipeline that processes an RPGGraph through sequential enrichment stages, adding type annotations, signatures, docstrings, file/folder structure, data flow, base classes, and intra-module ordering.

**Files**: 11 files, 2548 LOC

### Key Classes

#### RPGBuilder (`rpg_enrichment/pipeline.py`)

Sequential encoder pipeline with validation and timing.

```python
class RPGBuilder:
    def __init__(self, *, validate_after_each: bool = True) -> None
    def add_encoder(self, encoder: RPGEncoder) -> RPGBuilder    # Fluent API
    def run(self, graph: RPGGraph) -> RPGGraph
    @property
    def encoders(self) -> list[RPGEncoder]
    @property
    def steps(self) -> list[EncoderStep]
```

#### RPGEncoder (`rpg_enrichment/base.py`)

Abstract base class for enrichment stages.

```python
class RPGEncoder(ABC):
    @property
    def name(self) -> str                                       # Defaults to class name
    @abstractmethod
    def encode(self, graph: RPGGraph) -> RPGGraph               # Mutate in-place, return same
    @abstractmethod
    def validate(self, graph: RPGGraph) -> ValidationResult     # Post-condition check
```

### Built-in Encoders

| Encoder | File | Description |
|---------|------|-------------|
| `FileEncoder` | `file_encoder.py` | Assigns `file_path` to nodes based on naming conventions |
| `FolderEncoder` | `folder_encoder.py` | Assigns `folder_path` to nodes based on module structure |
| `InterfaceDesignEncoder` | `interface_design_encoder.py` | Generates `signature` and `interface_type` via LLM |
| `BaseClassEncoder` | `baseclass_encoder.py` | Adds `INHERITANCE` edges between classes |
| `DataFlowEncoder` | `dataflow_encoder.py` | Adds `DATA_FLOW` edges with data type annotations |
| `IntraModuleOrderEncoder` | `ordering_encoder.py` | Adds `ORDERING` edges for build order within modules |
| `SerenaValidator` | `serena_validator.py` | Validates enriched graph against Serena LSP server |

### Data Models (`rpg_enrichment/models.py`)

| Model | Description |
|-------|-------------|
| `EncoderStep` | Execution record (encoder_name, duration_ms, validation_result, metadata) |
| `ValidationResult` | Validation outcome (passed, errors: list[str]) |

**Dependencies**: `models` (RPGGraph, RPGNode), `llm`, `serena`

---

## 7. codegen

**Purpose**: The largest module -- orchestrates graph-guided code generation through topological traversal, TDD loops, repository assembly, workspace management, and staged test validation. Implements the complete pipeline from RPG graph to working source code.

**Files**: 33 files, 8877 LOC

### Sub-systems

#### 7.1 Traversal & State (Epic 4.1)

```python
class TraversalEngine:
    """Topological-order traversal of the RPG graph."""
    def __init__(self, graph: RPGGraph) -> None
    def traverse(self) -> TraversalReport

class CheckpointManager:
    """Periodic state checkpointing for crash recovery."""
    def save(self, state: GenerationState) -> Path
    def load(self, path: Path) -> GenerationState

class GenerationState(BaseModel):
    """Tracks per-node generation progress."""
    status: GenerationStatus       # PENDING, IN_PROGRESS, COMPLETED, FAILED
    nodes: dict[UUID, NodeGenerationState]
```

#### 7.2 TDD Generation Loop (Epic 4.2)

Core test-driven development loop: test generation -> implementation -> sandbox execution -> debugging.

```python
class TDDLoop:
    def __init__(
        self,
        test_gen: TestGenerator,
        impl_gen: ImplementationGenerator,
        executor: SandboxExecutor,
        diagnoser: DebugDiagnoser,
        max_retries: int = 8,
    ) -> None

    def run(self, node: RPGNode, context: dict) -> TDDLoopResult
```

**Protocols** (pluggable components):
- `TestGenerator.generate_tests(node, context) -> str`
- `ImplementationGenerator.generate_implementation(node, test_code, context) -> str`
- `SandboxExecutor.run_tests(implementation, test_code, node) -> SandboxResult`
- `DebugDiagnoser.diagnose_and_fix(node, impl, tests, error, context) -> DiagnosisResult`

**Concrete Implementations**:
- `LLMImplementationGenerator` -- LLM-backed code generation
- `DockerSandboxExecutor` / `InProcessSandboxExecutor` -- Sandbox test execution
- `MajorityVoteDiagnoser` -- Majority-vote failure diagnosis

#### 7.3 Localization (Epic 4.3/4.4)

```python
class RPGFuzzySearch:
    """Embedding-based search over RPG nodes."""
    def search(self, query: str, top_k: int) -> list[LocalizationResult]

class RepositoryCodeView:
    """Source code reading and AST extraction."""
    def get_code(self, file_path: str) -> str

class DependencyExplorer:
    """N-hop neighbourhood exploration."""
    def explore(self, node_id: UUID, hops: int) -> DependencyMap

class LocalizationOrchestrator:
    """Coordinated Serena + RPG localization."""
    def localize(self, query: str) -> list[LocalizationResult]

class SerenaEditor:
    """Structural code editing via Serena MCP."""
    def edit(self, file_path: str, edits: list) -> None
```

#### 7.4 Staged Test Validation (Epic 4.5)

```python
class UnitValidator:
    """Staged unit test validation."""
    def validate(self, node, implementation, tests) -> ValidationResult

class RegressionDetector:
    """Cross-iteration regression detection."""
    def detect(self, current: TestSnapshot, previous: TestSnapshot) -> RegressionReport

class IntegrationGenerator:
    """Cross-node integration test generation."""
    def generate(self, source: RPGNode, target: RPGNode) -> IntegrationTestSuite

class MajorityVoter:
    """Majority voting for test result consensus."""
    def vote(self, results: list[TestRunVote]) -> NodeVoteResult

class TestArtifactStore:
    """Test artifact lifecycle management."""
    def store(self, artifact: TestArtifact) -> None
    def query(self, query: ArtifactQuery) -> list[ArtifactSummary]
```

#### 7.5 Repository Assembly (Epic 4.6)

```python
# File structure
build_file_map(graph) -> dict[str, FileEntry]
create_directory_structure(graph) -> list[DirectoryEntry]
validate_file_structure(entries) -> list[str]

# Import management
classify_import(import_str) -> ImportGroup
detect_circular_imports(file_map) -> list[list[str]]
resolve_imports_for_file(file_path, graph) -> list[ImportStatement]

# Project generation
extract_project_metadata(graph) -> dict
render_pyproject_toml(metadata) -> str
render_setup_py(metadata) -> str
generate_readme(graph) -> str

# Coverage reporting
build_coverage_report(graph, results) -> CoverageReport
render_coverage_markdown(report) -> str

# RPG export
export_rpg_artifact(graph, path) -> None
export_rpg_summary(graph) -> str
```

#### 7.6 Workspace Management (Epic 4.7)

```python
class BatchedFileWriter:
    """Atomic batched file writing."""
    def write(self, files: dict[str, str]) -> None

class SerenaReindexer:
    """Serena LSP re-indexing after file changes."""
    def reindex(self, paths: list[str]) -> None

class RepositoryStateManager:
    """File state tracking and validation."""
    def get_state(self) -> dict[str, str]
    def validate(self) -> list[str]

class ProgressLogger:
    """Progress logging with ETA estimation."""
    def update(self, completed: int, total: int) -> None

class GracefulShutdownHandler:
    """Signal-based graceful shutdown (SIGINT/SIGTERM)."""
    def register(self) -> None
    @property
    def should_stop(self) -> bool
```

#### 7.7 CodegenOrchestrator (Top-level)

Main orchestrator coordinating the full pipeline.

```python
class CodegenOrchestrator:
    def __init__(
        self,
        graph: RPGGraph,
        tdd_loop: TDDLoop,
        config: OrchestratorConfig | None = None,
    ) -> None

    def run(self) -> OrchestratorResult
```

**Config**: `OrchestratorConfig(max_retries=8, checkpoint_interval=5, progress_log_interval=10, fail_fast=False, skip_non_leaf=True)`

**Result**: `OrchestratorResult(total_nodes, processed_nodes, passed_nodes, failed_nodes, skipped_nodes, node_results, traversal_report, elapsed_seconds, checkpoint_path)`

**Dependencies**: `models`, `llm`, `sandbox`, `serena`, `graph_ops`

---

## 8. evaluation

**Purpose**: Benchmarking and quality evaluation for generated repositories. Implements a 3-stage pipeline (localization -> semantic validation -> execution testing), metrics computation, failure analysis, and A/B testing.

**Files**: 14 files, 3113 LOC

### Key Classes

#### EvaluationPipeline (`evaluation/pipeline.py`)

Orchestrates the 3-stage evaluation process.

```python
class EvaluationPipeline:
    def __init__(
        self,
        localizer: FunctionLocalizer,
        validator: SemanticValidator,
        tester: ExecutionTester,
        top_k: int = 5,
        validation_candidates: int = 3,
    ) -> None

    def evaluate_task(self, task: BenchmarkTask, repo_path: str, functions=None) -> TaskResult
```

**Stages**:
1. **Localization** -- Embedding similarity search for candidate functions
2. **Semantic Validation** -- LLM majority voting to verify function correctness
3. **Execution Testing** -- Docker sandbox pytest execution

#### FunctionLocalizer (`evaluation/localization.py`)

```python
class FunctionLocalizer:
    def localize(self, task, repo_path, top_k, functions=None) -> list[tuple[FunctionSignature, float]]
```

#### SemanticValidator (`evaluation/semantic_validation.py`)

```python
class SemanticValidator:
    def validate_function(self, task, candidate) -> ValidationResult

class LLMClient:
    """LLM client for semantic validation voting."""
```

#### ExecutionTester (`evaluation/execution_testing.py`)

```python
class ExecutionTester:
    def execute_test(self, task: BenchmarkTask, repo_path: str) -> ExecutionResult

class SandboxProtocol(Protocol):
    """Protocol for sandbox backends."""
```

#### MetricsCalculator (`evaluation/metrics.py`)

```python
class MetricsCalculator:
    def compute(self, results: list[TaskResult]) -> dict[str, float]
```

#### Categorizer (`evaluation/categorizer.py`)

```python
class Categorizer:
    def categorize(self, tasks: list[BenchmarkTask]) -> Taxonomy
```

#### FailureAnalyzer / PromptABTest (`evaluation/failure_analysis.py`)

```python
class FailureAnalyzer:
    def analyze(self, results: list[TaskResult]) -> list[FailureReport]

class PromptABTest:
    def run(self, task, prompt_a, prompt_b) -> ABTestResult
```

#### Caching (`evaluation/caching.py`)

```python
class LLMResponseCache:
    """Disk-backed LLM response caching."""

class EmbeddingCache:
    """Disk-backed embedding caching."""

class BatchedFunctionGenerator:
    """Batched function generation with caching."""
```

### Data Models (`evaluation/models.py`)

| Model | Description |
|-------|-------------|
| `BenchmarkTask` | Task from RepoCraft benchmark (id, project, category, description, test_code, difficulty) |
| `FunctionSignature` | Extracted function (name, file_path, line_number, signature, docstring) |
| `TaskResult` | Per-task result (localized, validated, passed, stage_failed, scores) |
| `RepositoryResult` | Per-repository aggregated result |
| `BenchmarkResult` | Full benchmark result across all repositories |
| `FailureReport` | Failure analysis (category, description, root_cause) |
| `ABTestResult` | A/B test result (prompt_a_score, prompt_b_score, winner) |
| `ProfilingData` | Token usage and timing profiling |

**Dependencies**: `llm`, `sandbox`, `vectordb`

---

## 9. graph_ops

**Purpose**: Pure-function graph utilities for traversal, filtering, serialization, subgraph extraction, topological sorting, cycle detection, and dependency diffing.

**Files**: 8 files, 544 LOC

### Functions

#### Topological Sort & Cycle Detection (`graph_ops/topological.py`)

```python
def topological_sort(graph: RPGGraph) -> list[UUID]
    # Kahn's algorithm over HIERARCHY + DATA_FLOW edges
    # Raises CycleDetectedError if cycles exist

def detect_cycles(graph: RPGGraph) -> list[list[UUID]]
    # Returns all cycles found in the graph
```

#### Traversal (`graph_ops/traversal.py`)

```python
def get_ancestors(graph, node_id, edge_types) -> set[UUID]
    # Transitive closure traversal in reverse

def get_descendants(graph, node_id, edge_types) -> set[UUID]
    # Transitive closure traversal forward

def get_direct_dependencies(graph, node_id) -> set[UUID]
    # Single-hop forward neighbors
```

#### Filtering (`graph_ops/filtering.py`)

```python
def filter_nodes(graph, predicate) -> list[RPGNode]
def filter_by_level(graph, level: NodeLevel) -> list[RPGNode]
def filter_by_status(graph, status: TestStatus) -> list[RPGNode]
def filter_by_validation(graph, validated: bool) -> list[RPGNode]
```

#### Subgraph Extraction (`graph_ops/subgraph.py`)

```python
def extract_subgraph_by_level(graph, level: NodeLevel) -> RPGGraph
def extract_subgraph_by_module(graph, module_name: str) -> RPGGraph
def extract_subgraph_by_type(graph, node_type: NodeType) -> RPGGraph
```

#### Serialization (`graph_ops/serialization.py`)

```python
def serialize_graph(graph: RPGGraph) -> dict
def deserialize_graph(data: dict) -> RPGGraph
```

#### Diff (`graph_ops/diff.py`)

```python
def diff_dependencies(graph_a: RPGGraph, graph_b: RPGGraph) -> dict
```

**Dependencies**: `models` (RPGGraph, RPGNode, enums)

---

## 10. llm

**Purpose**: Unified multi-provider LLM interface via LiteLLM. Provides tiered model selection, token tracking with cost estimation, Jinja2 prompt templates, retry logic with exponential backoff, and structured logging.

**Files**: 6 files, 766 LOC

### Key Classes

#### LLMGateway (`llm/gateway.py`)

Core LLM interface with multi-provider support.

```python
class LLMGateway:
    def __init__(self, config: GatewayConfig | None = None) -> None

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tier: ModelTier | None = None,
        **kwargs,
    ) -> str

    def select_model(
        self,
        tier: ModelTier,
        provider_preference: str | None = None,
    ) -> str
```

**Features**:
- Exponential backoff retry for rate limits and connection errors
- Token usage tracking via `TokenTracker`
- Request/response logging via `LLMLogEntry`
- Non-retryable error detection (auth errors, bad requests)

#### ModelTier (`llm/models.py`)

```python
class ModelTier(str, Enum):
    CHEAP = "CHEAP"       # gpt-4o-mini, claude-3-haiku
    MEDIUM = "MEDIUM"     # gpt-4o, claude-3.5-sonnet
    STRONG = "STRONG"     # gpt-4o, claude-sonnet-4
```

**Provider priority**: OpenAI > Anthropic > Ollama

#### TokenTracker (`llm/token_tracker.py`)

```python
class TokenTracker:
    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None
    def get_total_tokens(self) -> int
    def get_total_cost(self) -> float        # USD estimate
    def get_breakdown_by_model(self) -> dict[str, dict[str, int]]
    def reset(self) -> None
```

#### PromptTemplate (`llm/prompt_templates.py`)

Jinja2-based prompt template management.

```python
class PromptTemplate:
    def __init__(self, template_dir: Path | None = None) -> None
    def render(self, template_name: str, **variables) -> str
    def list_templates(self) -> list[str]
```

Templates are stored as `*.jinja2` files in `llm/templates/`.

### Exceptions (`llm/exceptions.py`)

| Exception | Description |
|-----------|-------------|
| `LLMGatewayError` | Base exception for LLM errors |
| `ConfigurationError` | Invalid configuration |
| `RetryExhaustedError` | All retries failed |
| `TemplateError` | Template not found or rendering error |

**Dependencies**: `litellm`, `jinja2`

---

## 11. vectordb

**Purpose**: ChromaDB-backed embedding storage for feature trees. Provides persistent storage, similarity search with metadata filtering, and collection management.

**Files**: 5 files, 718 LOC

### Key Classes

#### VectorStore (`vectordb/store.py`)

ChromaDB wrapper with feature tree storage and search.

```python
class VectorStore:
    def __init__(self, config: VectorStoreConfig | None = None) -> None
    def initialize(self, project_dir: Path, embedding_model: str | None = None) -> None
    def add_node(self, node: RPGNode) -> None
    def add_nodes(self, nodes: list[RPGNode]) -> None
    def search(self, query: str, top_k: int = 10, where: dict | None = None) -> list[SearchResult]
    def delete(self, node_id: UUID) -> None
    def clear(self) -> None
    def get_stats(self) -> dict[str, int]
```

#### EmbeddingGenerator (`vectordb/embeddings.py`)

Sentence-transformer embedding generation.

```python
class EmbeddingGenerator:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None
    def embed(self, text: str) -> list[float]
    def embed_batch(self, texts: list[str]) -> list[list[float]]
```

### Data Models (`vectordb/models.py`)

```python
class VectorStoreConfig(BaseModel):
    collection_name: str = "zerorepo_features"
    persist_directory: str = ".zerorepo/chromadb"
    embedding_model: str = "all-MiniLM-L6-v2"
    distance_function: str = "cosine"

class SearchResult(BaseModel):
    id: str
    text: str
    score: float
    metadata: dict[str, Any]
```

### Exceptions (`vectordb/exceptions.py`)

| Exception | Description |
|-----------|-------------|
| `VectorStoreError` | Base exception |
| `CollectionError` | Collection not found or ChromaDB unavailable |
| `EmbeddingError` | Embedding generation failure |
| `StoreNotInitializedError` | Store used before `initialize()` |

**Dependencies**: `chromadb`, `sentence-transformers`

---

## 12. sandbox

**Purpose**: Docker-based isolated container environment for safely running generated code and tests. Manages container lifecycle, dependency installation, code execution, and pytest result parsing.

**Files**: 4 files, 729 LOC

### Key Classes

#### DockerSandbox (`sandbox/sandbox.py`)

```python
class DockerSandbox:
    LABEL = "zerorepo-sandbox"
    DEFAULT_IMAGE = "python:3.11-slim"

    def __init__(self, config: SandboxConfig | None = None) -> None

    # Lifecycle
    def create_container(self, **kwargs) -> str           # Returns container ID
    def stop_container(self, container_id: str) -> None
    def cleanup(self) -> None                              # Stops all active containers

    # Operations
    def install_dependencies(self, container_id: str, packages: list[str]) -> ExecutionResult
    def execute_code(self, container_id: str, code: str) -> ExecutionResult
    def run_tests(self, container_id: str, test_code: str) -> TestResult
    def write_file(self, container_id: str, path: str, content: str) -> None
    def read_file(self, container_id: str, path: str) -> str
    def list_files(self, container_id: str, directory: str) -> list[str]

    # Context manager
    def __enter__(self) -> DockerSandbox
    def __exit__(self, ...) -> None
```

### Data Models (`sandbox/models.py`)

```python
class SandboxConfig(BaseModel):
    image: str = "python:3.11-slim"
    timeout: int = 30                    # Seconds
    memory_limit: str = "512m"
    cpu_count: float = 1.0
    network_disabled: bool = True         # Isolated by default
    working_dir: str = "/workspace"

class ExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool

class TestResult(BaseModel):
    passed: int
    failed: int
    errors: int
    total: int
    failures: list[TestFailure]
    output: str

class TestFailure(BaseModel):
    test_name: str
    message: str
    traceback: str
```

### Exceptions (`sandbox/exceptions.py`)

| Exception | Description |
|-----------|-------------|
| `DockerError` | Docker daemon unavailable or API failure |
| `SandboxTimeoutError` | Execution exceeded timeout |

**Dependencies**: `docker` (Python Docker SDK)

---

## 13. serena

**Purpose**: Serena MCP client for Language Server Protocol (LSP) validation and symbol analysis. Manages the Serena MCP server process, provides JSON-RPC communication, workspace management, symbol lookup, Pyright configuration, and dependency extraction.

**Files**: 9 files, 722 LOC

### Key Classes

#### SerenaMCPServer (`serena/server.py`)

MCP server lifecycle management.

```python
class SerenaMCPServer:
    def start(self, workspace_dir: Path, pyright_config: Path | None = None) -> None
    def stop(self) -> None
    @property
    def is_running(self) -> bool
    def __enter__(self) -> SerenaMCPServer
    def __exit__(self, ...) -> None
```

Launches Serena via `npx -y @anthropic/serena-mcp --workspace <dir>`.

#### MCPClient (`serena/client.py`)

JSON-RPC client for MCP tool calls.

```python
class MCPClient:
    def __init__(self, server: SerenaMCPServer) -> None
    def call_tool(self, tool_name: str, arguments: dict) -> Any
    def list_tools(self) -> list[str]
```

#### WorkspaceManager (`serena/workspace.py`)

```python
class WorkspaceManager:
    def initialize(self, workspace_dir: Path) -> None
    def add_file(self, path: str, content: str) -> None
    def get_tracked_files(self) -> list[str]
```

#### SymbolLookup (`serena/symbols.py`)

```python
class SymbolLookup:
    def find_symbol(self, name: str) -> list[SymbolInfo]
    def get_overview(self, file_path: str) -> list[SymbolInfo]
```

#### PyrightConfigurator (`serena/pyright.py`)

```python
class PyrightConfigurator:
    def generate(self, workspace_dir: Path) -> PyrightConfig
    def write(self, config: PyrightConfig, path: Path) -> None
```

#### DependencyExtractor (`serena/dependencies.py`)

```python
class DependencyExtractor:
    def extract(self, file_path: str) -> list[str]
```

### Data Models (`serena/models.py`)

```python
class SymbolInfo(BaseModel):
    name: str
    kind: str                    # "class", "function", "method", etc.
    file_path: str
    line_number: int
    column: int
    container: Optional[str]     # Parent class/module name

class PyrightConfig(BaseModel):
    include: list[str]
    python_version: str
    python_platform: str
    type_checking_mode: str
```

### Exceptions (`serena/exceptions.py`)

| Exception | Description |
|-----------|-------------|
| `SerenaError` | Base exception |
| `MCPError` | MCP protocol/communication error |
| `ToolNotFoundError` | Requested MCP tool not available |

**Dependencies**: `subprocess` (npx), JSON-RPC protocol

---

## 14. cli

**Purpose**: Typer-based command-line interface with Rich console output. Provides project initialization, specification parsing, ontology management, configuration, logging, progress display, and error handling.

**Files**: 9 files, 1774 LOC

### Application (`cli/app.py`)

```python
app = typer.Typer(name="zerorepo", ...)

# Global options
@app.callback()
def main(version: bool, verbose: bool, config: Path | None) -> None

# Commands
@app.command()
def init(path: Path | None) -> None      # Initialize .zerorepo/ project structure
```

### Sub-command Groups

**Spec commands** (`cli/spec.py`):
```
zerorepo spec parse <file>          # Parse a specification file
zerorepo spec refine <spec-id>      # Interactive refinement
zerorepo spec conflicts <spec-id>   # Detect conflicts
zerorepo spec show <spec-id>        # Display specification
```

**Ontology commands** (`cli/ontology.py`):
```
zerorepo ontology build             # Build feature ontology
zerorepo ontology search <query>    # Semantic search
zerorepo ontology stats             # Show ontology statistics
zerorepo ontology extend <csv>      # Extend with custom features
zerorepo ontology export <path>     # Export to CSV
```

### Supporting Classes

#### ZeroRepoConfig (`cli/config.py`)

```python
class ZeroRepoConfig(BaseModel):
    project_dir: Path
    llm_config: dict
    vectordb_config: dict
    sandbox_config: dict

def load_config(config_path: Path | None = None) -> ZeroRepoConfig
```

#### Error Handling (`cli/errors.py`)

```python
class CLIError(Exception): ...
class ConfigError(CLIError): ...

@contextmanager
def error_handler(console: Console) -> Generator:
    """Context manager that catches errors and displays Rich-formatted output."""
```

#### Progress Display (`cli/progress.py`)

```python
class ProgressDisplay:
    """Rich-based progress bar wrapper."""

class StatusDisplay:
    """Rich-based status spinner wrapper."""

def progress_bar(...) -> ProgressDisplay
def progress_spinner(...) -> StatusDisplay
```

#### Logging (`cli/logging_setup.py`)

```python
def setup_logging(level: str = "INFO") -> None
```

**Dependencies**: `typer`, `rich`, all pipeline modules

---

## Module Dependency Graph

```
cli ──────────────┐
                  │
                  v
spec_parser ──> ontology ──> graph_construction ──> selection
    │              │                                     │
    │              │                                     v
    │              └───────────────────────> rpg_enrichment
    │                                            │
    v                                            v
  models <──── graph_ops                    codegen ──> evaluation
    ^                                         │  │
    │                                         v  v
    └─────── llm <──── vectordb          sandbox  serena
```

**Foundational** (no ZeroRepo deps): `models`, `llm`, `vectordb`, `sandbox`, `serena`, `graph_ops`

**Mid-level** (depend on foundational): `spec_parser`, `ontology`, `rpg_enrichment`

**High-level** (depend on mid-level): `graph_construction`, `selection`, `codegen`, `evaluation`

**Top-level** (depends on everything): `cli`
