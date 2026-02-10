# ZeroRepo Usage Guide

Complete guide to using ZeroRepo for generating software repositories from natural language specifications.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Initialization](#project-initialization)
- [CLI Reference](#cli-reference)
  - [Global Options](#global-options)
  - [zerorepo init](#zerorepo-init)
  - [zerorepo generate](#zerorepo-generate)
  - [zerorepo spec](#zerorepo-spec)
  - [zerorepo ontology](#zerorepo-ontology)
- [Python API Reference](#python-api-reference)
  - [LLM Gateway](#llm-gateway)
  - [Specification Parsing](#specification-parsing)
  - [Feature Ontology](#feature-ontology)
  - [Graph Construction](#graph-construction)
  - [Subtree Selection](#subtree-selection)
  - [Generate Pipeline with Delta Classification](#generate-pipeline-with-delta-classification)
  - [Code Generation](#code-generation)
  - [Evaluation Pipeline](#evaluation-pipeline)
- [End-to-End Walkthrough](#end-to-end-walkthrough)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | >= 3.11 | Runtime (uses `tomllib`, modern type hints) |
| Docker | >= 24.0 | Sandbox test execution (optional) |
| ChromaDB | >= 0.5 | Vector store for ontology search (optional) |
| Git | any | Recommended for project tracking |

You will also need API keys for at least one LLM provider:

- **OpenAI**: Set `OPENAI_API_KEY` environment variable
- **Anthropic**: Set `ANTHROPIC_API_KEY` environment variable
- **Ollama**: Run a local Ollama instance (no API key needed)

## Installation

### Basic Installation

```bash
pip install zerorepo
```

### With Optional Dependencies

```bash
# Docker sandbox support (for running generated tests)
pip install "zerorepo[sandbox]"

# Vector database support (for ontology search)
pip install "zerorepo[vectordb]"

# Development tools (pytest, coverage)
pip install "zerorepo[dev]"

# All optional dependencies
pip install "zerorepo[sandbox,vectordb,dev]"
```

### From Source

```bash
git clone <repository-url>
cd zerorepo
pip install -e ".[dev,sandbox,vectordb]"
```

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | >= 2.0, < 3.0 | Data validation and settings |
| `litellm` | >= 1.0 | Multi-provider LLM access |
| `jinja2` | >= 3.1 | Prompt templates |
| `chromadb` | >= 0.5 | Vector database |

### Optional Dependencies

| Group | Packages | Purpose |
|-------|----------|---------|
| `sandbox` | `docker >= 7.0` | Docker container management |
| `vectordb` | `chromadb >= 0.4.0`, `sentence-transformers >= 2.0` | Embedding and similarity search |
| `dev` | `pytest >= 8.0`, `pytest-cov >= 5.0`, `pytest-mock >= 3.12` | Testing |

---

## Project Initialization

Initialize a new ZeroRepo project to create the configuration directory structure:

```bash
zerorepo init
```

This creates:

```
.zerorepo/
├── config.toml      # Default configuration file
├── graphs/          # Generated graph outputs
└── sandbox/         # Sandbox workspace
```

The default `config.toml`:

```toml
# ZeroRepo configuration

[general]
llm_provider = "openai"
llm_model = "gpt-4o-mini"
log_level = "INFO"
```

---

## CLI Reference

ZeroRepo provides a Typer-based CLI with Rich-formatted output.

### Global Options

```bash
zerorepo [OPTIONS] COMMAND [ARGS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-V` | Show version and exit |
| `--verbose` | `-v` | Enable DEBUG-level logging |
| `--config PATH` | `-c` | Path to configuration TOML file |

### zerorepo init

Initialize a new ZeroRepo project.

```bash
zerorepo init [PATH]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `PATH` | No | Current directory | Target directory to initialize |

**Behavior:**
- Creates the `.zerorepo/` directory structure with `graphs/` and `sandbox/` subdirectories
- Writes the default `config.toml`
- Warns if the target is not inside a git repository
- Fails if `.zerorepo/` already exists (prevents accidental overwrite)

**Examples:**

```bash
# Initialize in current directory
zerorepo init

# Initialize in a specific directory
zerorepo init /path/to/my-project
```

---

### zerorepo spec

Specification parser sub-commands for parsing, refining, and validating natural language repository descriptions.

#### spec parse

Parse a natural language specification into structured JSON.

```bash
zerorepo spec parse INPUT_FILE [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | None | Output JSON file for parsed spec |
| `--model TEXT` | `-m` | `gpt-4o-mini` | LLM model to use for parsing |
| `--conflicts/--no-conflicts` | | `--conflicts` | Run conflict detection after parsing |
| `--json` | `-j` | False | Output raw JSON to stdout |

**Examples:**

```bash
# Parse a spec file and display a summary
zerorepo spec parse my-app-spec.txt

# Parse and save to JSON
zerorepo spec parse my-app-spec.txt --output spec.json

# Parse with a specific model, skip conflict detection
zerorepo spec parse spec.txt -m gpt-4o --no-conflicts

# Output raw JSON to stdout (for piping)
zerorepo spec parse spec.txt --json
```

#### spec refine

Refine an existing specification with additional requirements or clarifications.

```bash
zerorepo spec refine SPEC_FILE [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--add TEXT` | `-a` | None | Add a requirement (natural language) |
| `--clarify TEXT` | `-q` | None | Clarification in `"question\|answer"` format |
| `--context TEXT` | `-c` | None | Additional context for refinement |
| `--output PATH` | `-o` | None | Output file (default: overwrite input) |
| `--json` | `-j` | False | Output refined spec as JSON |

**Examples:**

```bash
# Add a new requirement
zerorepo spec refine spec.json --add "Add WebSocket support for real-time updates"

# Clarify an ambiguous requirement
zerorepo spec refine spec.json --clarify "What database?|PostgreSQL with Redis caching"

# Add with context and save to new file
zerorepo spec refine spec.json \
  --add "Support OAuth2 authentication" \
  --context "Use Google and GitHub providers" \
  --output spec-v2.json
```

#### spec conflicts

Detect conflicting requirements in a specification.

```bash
zerorepo spec conflicts SPEC_FILE [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--attach` | | False | Attach conflicts to spec and save |
| `--llm/--no-llm` | | `--llm` | Use LLM for nuanced detection |
| `--json` | `-j` | False | Output conflicts as JSON |

**Examples:**

```bash
# Check for conflicts (display only)
zerorepo spec conflicts spec.json

# Check and attach conflicts to the spec file
zerorepo spec conflicts spec.json --attach

# Rule-based only (no LLM calls)
zerorepo spec conflicts spec.json --no-llm
```

#### spec suggest

Get LLM-powered improvement suggestions for a specification.

```bash
zerorepo spec suggest SPEC_FILE [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--json` | `-j` | False | Output suggestions as JSON |

**Examples:**

```bash
# Get improvement suggestions
zerorepo spec suggest spec.json

# Get suggestions as JSON
zerorepo spec suggest spec.json --json
```

#### spec export

Export a specification to various formats.

```bash
zerorepo spec export SPEC_FILE --output PATH [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | (required) | Output file path |
| `--format TEXT` | `-f` | `json` | Export format: `json`, `summary` |

**Examples:**

```bash
# Export as JSON
zerorepo spec export spec.json --output export.json --format json

# Export as plain text summary
zerorepo spec export spec.json --output summary.txt --format summary
```

#### spec history

Show refinement history for a specification.

```bash
zerorepo spec history SPEC_FILE [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--json` | `-j` | False | Output history as JSON |

---

### zerorepo generate

Run the full planning pipeline from a PRD/specification document through graph construction,
with optional baseline comparison for delta classification.

```bash
zerorepo generate PRD [OPTIONS]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `PRD` | Yes | - | Path to the PRD or specification document |
| `--model TEXT` | No | `gpt-4o-mini` | LLM model to use for planning |
| `--output PATH` | No | `./output` | Output directory for generated artifacts |
| `--baseline PATH` | No | None | Baseline RPG graph JSON for delta classification |
| `--skip-enrichment` | No | False | Skip the enrichment stage (faster, planning-only) |

**Examples:**

```bash
# Basic generation from a PRD
zerorepo generate my-app-prd.md --model gpt-4o --output ./planning-output

# Generate with delta classification against existing codebase graph
zerorepo generate my-app-prd.md --model gpt-4o --output ./planning-output \
  --baseline ./previous-run/rpg-graph.json

# Quick planning pass (skip enrichment for faster iteration)
zerorepo generate my-app-prd.md --model gpt-4o-mini --output ./draft \
  --skip-enrichment
```

**Output artifacts:**

| File | Description |
|------|-------------|
| `01-spec.json` | Parsed specification |
| `02-ontology.json` | Feature ontology |
| `03-graph.json` | Functionality graph |
| `04-enriched-graph.json` | Enriched RPG graph (skipped with `--skip-enrichment`) |
| `05-delta-report.md` | Delta classification report (only with `--baseline`) |

---

### zerorepo ontology

Feature ontology sub-commands for building, searching, extending, and exporting the feature taxonomy.

#### ontology build

Build the feature ontology from seed generators.

```bash
zerorepo ontology build [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project-dir PATH` | `-p` | `.` | Project root directory |
| `--no-github` | | False | Exclude GitHub Topics generator |
| `--no-stackoverflow` | | False | Exclude StackOverflow Tags generator |
| `--no-libraries` | | False | Exclude Library Docs generator |
| `--no-expander` | | False | Exclude combinatorial taxonomy expander |
| `--target-count INT` | `-t` | `50000` | Target node count for taxonomy expander |
| `--output PATH` | `-o` | None | Export ontology to CSV after building |

**Examples:**

```bash
# Build full ontology
zerorepo ontology build

# Build without GitHub and StackOverflow sources
zerorepo ontology build --no-github --no-stackoverflow

# Build with lower target count and export
zerorepo ontology build --target-count 10000 --output ontology.csv
```

#### ontology search

Search the feature ontology for matching features.

```bash
zerorepo ontology search QUERY [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project-dir PATH` | `-p` | `.` | Project root directory |
| `--top-k INT` | `-k` | `10` | Maximum number of results |
| `--level INT` | `-l` | None | Filter by hierarchical level |
| `--parent TEXT` | | None | Filter by parent node ID |
| `--tags TEXT` | | None | Filter by tags (comma-separated) |
| `--json` | `-j` | False | Output results as JSON |

**Examples:**

```bash
# Search for authentication features
zerorepo ontology search "authentication"

# Search with filters
zerorepo ontology search "database" --top-k 20 --level 2

# Get JSON output
zerorepo ontology search "real-time" --json
```

#### ontology stats

Display ontology statistics.

```bash
zerorepo ontology stats [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project-dir PATH` | `-p` | `.` | Project root directory |
| `--json` | `-j` | False | Output statistics as JSON |

#### ontology extend

Extend the ontology with custom features from a CSV file.

```bash
zerorepo ontology extend --csv PATH [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project-dir PATH` | `-p` | `.` | Project root directory |
| `--csv PATH` | `-f` | (required) | CSV file with custom features |
| `--conflict TEXT` | `-c` | `override` | Conflict resolution: `override`, `skip`, `error` |
| `--no-embed` | | False | Skip automatic embedding of new features |

CSV format: `feature_id,parent_id,name,description,tags,level`

#### ontology export

Export the ontology to CSV format.

```bash
zerorepo ontology export --output PATH [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project-dir PATH` | `-p` | `.` | Project root directory |
| `--output PATH` | `-o` | (required) | Output CSV file path |

---

## Python API Reference

For programmatic usage, ZeroRepo exposes a clean Python API across its modules.

### LLM Gateway

The `LLMGateway` provides a unified interface to multiple LLM providers via LiteLLM.

```python
from zerorepo.llm.gateway import LLMGateway
from zerorepo.llm.models import GatewayConfig, ModelTier

# Default configuration (uses environment variables for API keys)
gateway = LLMGateway()

# Custom configuration
config = GatewayConfig()
gateway = LLMGateway(config=config)

# Basic completion
response = gateway.complete(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4o-mini",
)

# Structured JSON output with Pydantic schema
from pydantic import BaseModel

class Answer(BaseModel):
    answer: str

result = gateway.complete_json(
    messages=[{"role": "user", "content": "What is 2+2?"}],
    model="gpt-4o-mini",
    response_schema=Answer,
)

# Tiered model selection
response = gateway.complete(
    messages=[{"role": "user", "content": "Complex reasoning task..."}],
    tier=ModelTier.STRONG,  # Uses best available model
)

# Access token usage tracking
print(gateway.tracker.total_tokens)
print(gateway.tracker.total_cost)
```

**Supported Models:**

| Provider | Models | Tier |
|----------|--------|------|
| OpenAI | `gpt-4o-mini` | CHEAP |
| OpenAI | `gpt-4o` | MEDIUM / STRONG |
| Anthropic | `claude-3-haiku-20240307` | CHEAP |
| Anthropic | `claude-3-5-sonnet-20241022` | MEDIUM |
| Anthropic | `claude-sonnet-4-20250514` | STRONG |
| Ollama | `ollama/llama3.2` | All tiers (local) |

### Specification Parsing

Parse natural language descriptions into structured `RepositorySpec` objects.

```python
from zerorepo.spec_parser.parser import SpecParser, ParserConfig
from zerorepo.llm.gateway import LLMGateway

# Basic usage (auto-creates gateway)
parser = SpecParser()
spec = parser.parse(
    "Build a real-time chat application with React, WebSocket, "
    "and PostgreSQL. Must support 10K concurrent users."
)

# Access parsed data
print(spec.core_functionality)
print(spec.technical_requirements.languages)    # ['TypeScript', 'Python', ...]
print(spec.technical_requirements.frameworks)   # ['React', 'WebSocket', ...]
print(spec.quality_attributes.scalability)      # '10K concurrent users'

# Custom configuration
config = ParserConfig(
    model="gpt-4o",           # Use a stronger model
    max_description_length=50000,
    use_json_mode=True,
)
gateway = LLMGateway()
parser = SpecParser(config=config, gateway=gateway)
spec = parser.parse(description)

# Conflict detection
from zerorepo.spec_parser.conflict_detector import ConflictDetector, DetectorConfig

detector = ConflictDetector(config=DetectorConfig(use_llm=True))
conflicts = detector.detect(spec)
for conflict in conflicts:
    print(f"[{conflict.severity.value}] {conflict.description}")
    print(f"  Suggestion: {conflict.suggestion}")

# Refinement
from zerorepo.spec_parser.refinement import SpecRefiner

refiner = SpecRefiner(gateway=gateway)
spec = refiner.add_requirement(
    spec,
    "Add OAuth2 authentication with Google and GitHub",
    context="Enterprise SSO integration"
)

# Get improvement suggestions
response = refiner.suggest_improvements(spec)
for suggestion in response.suggestions:
    print(f"[{suggestion.priority}] {suggestion.area}: {suggestion.suggestion}")

# Serialization
json_str = spec.to_json(indent=2)
spec_loaded = RepositorySpec.from_json(json_str)
```

### Feature Ontology

Build and search a hierarchical feature taxonomy.

```python
from zerorepo.ontology.service import OntologyService

# Create service from project directory
service = OntologyService.create(project_dir=Path("."))

# Build the ontology
result = service.build(
    include_github=True,
    include_stackoverflow=True,
    include_libraries=True,
    include_expander=True,
    target_count=50000,
)
print(f"Total nodes: {result.total_nodes}")
print(f"Max depth: {result.max_depth}")

# Search for features
search_result = service.search(
    query="user authentication",
    top_k=10,
    level=None,
    parent_id=None,
    tags=None,
)
for path in search_result.paths:
    print(f"  [{path.score:.3f}] {path.leaf.name} ({path.path_string})")

# Get statistics
stats = service.stats()
print(f"Total nodes: {stats.total_nodes}")
print(f"Embedding coverage: {stats.embedding_coverage:.1%}")

# Extend with custom features
result = service.extend(
    csv_path=Path("custom_features.csv"),
    conflict_resolution="override",
    embed=True,
)

# Export to CSV
service.export_csv(Path("ontology_export.csv"))
```

### Graph Construction

Build a functionality graph from selected features, including module partitioning, dependency inference, and quality metrics.

```python
from zerorepo.graph_construction.builder import (
    FunctionalityGraphBuilder,
    BuilderConfig,
)
from zerorepo.llm.gateway import LLMGateway

gateway = LLMGateway()

# Configure the builder
config = BuilderConfig()  # Uses defaults for partitioner, dependencies, metrics
builder = FunctionalityGraphBuilder(llm_gateway=gateway, config=config)

# Build graph from features (list of FeatureNode objects)
result = builder.build(features)

# Export the graph
result.to_json("graph.json")
result.to_graphml("graph.graphml")

# Access partition quality metrics
from zerorepo.graph_construction.metrics import compute_all_metrics

metrics = compute_all_metrics(result.partition, result.graph)
print(f"Cohesion: {metrics.avg_cohesion:.3f}")
print(f"Coupling: {metrics.avg_coupling:.3f}")
print(f"Modularity: {metrics.modularity_score:.3f}")

# Refine the graph iteratively
from zerorepo.graph_construction.refinement import GraphRefinement, RefinementConfig

refinement = GraphRefinement(config=RefinementConfig())
refined = refinement.refine(result)
```

### Subtree Selection

Select features from the ontology using an explore-exploit strategy with diversity sampling and convergence monitoring.

```python
from zerorepo.selection.orchestrator import (
    ExploreExploitOrchestrator,
    OrchestratorConfig,
)
from zerorepo.ontology.backend import OntologyBackend
from zerorepo.llm.gateway import LLMGateway

gateway = LLMGateway()
store = build_store(...)  # OntologyBackend instance

# Configure the orchestrator
config = OrchestratorConfig()
orch = ExploreExploitOrchestrator(
    store=store,
    llm_gateway=gateway,
    config=config,
)

# Run the selection loop
result = orch.run(spec_description="Build a real-time chat application")
print(f"Selected {result.count} features in {result.iterations_run} iterations")
print(f"Diversity score: {result.diversity_metrics.silhouette_score:.3f}")

# Access per-iteration data
for snapshot in result.iteration_snapshots:
    print(f"  Iteration {snapshot.iteration}: {snapshot.total_selected} features")
```

The orchestrator implements Algorithm 2 from the RPG paper:
1. **Exploitation**: LLM-augmented vector search over the ontology
2. **Exploration**: Coverage-gap-based exploratory queries
3. **Diversity sampling**: Rejection sampling with cosine similarity (threshold 0.85)
4. **LLM filtering**: Periodic relevance filtering (every 5 iterations)
5. **Convergence monitoring**: Coverage plateau detection (window of 5)

### Code Generation

Generate code for each node in the RPG graph using a test-driven development loop.

```python
from zerorepo.codegen.codegen_orchestrator import (
    CodegenOrchestrator,
    OrchestratorConfig,
)
from zerorepo.models.graph import RPGGraph

# Load or construct an RPG graph
graph = RPGGraph(...)

# Create the orchestrator with required components
orchestrator = CodegenOrchestrator(
    graph=graph,
    test_generator=test_gen,          # TestGenerator protocol
    impl_generator=impl_gen,          # ImplementationGenerator protocol
    sandbox_executor=sandbox_exec,    # SandboxExecutor protocol
    debug_diagnoser=diagnoser,        # DebugDiagnoser protocol
    config=OrchestratorConfig(
        max_retries=8,                # TDD loop retry limit per node
        checkpoint_interval=5,        # Save state every N nodes
        progress_log_interval=10,     # Log progress every N nodes
        fail_fast=False,              # Continue on node failure
        skip_non_leaf=True,           # Skip non-FUNCTION_AUGMENTED nodes
    ),
)

# Run the full pipeline
result = orchestrator.run()
print(f"Processed: {result.processed_nodes}/{result.total_nodes}")
print(f"Pass rate: {result.pass_rate:.1f}%")
print(f"Duration: {result.elapsed_seconds:.1f}s")

# Inspect per-node results
for node_result in result.node_results:
    status = "PASS" if node_result.success else "FAIL"
    print(f"  [{status}] {node_result.node_name}")

# Graceful shutdown
orchestrator.request_shutdown()  # Finishes current node, then stops
```

The code generation pipeline follows this flow:
1. **Topological traversal**: Processes nodes in dependency order
2. **TDD loop per node**: Generates tests, then implementation, runs in sandbox
3. **Failure diagnosis**: Uses majority-vote diagnosis on test failures
4. **Checkpointing**: Saves state periodically for resume capability
5. **Signal handling**: Supports graceful shutdown via `SIGTERM`/`SIGINT`

### Generate Pipeline with Delta Classification

Run the full planning pipeline programmatically, with optional baseline comparison.

```python
from pathlib import Path
from zerorepo.spec_parser.parser import SpecParser
from zerorepo.graph_construction.converter import GraphConverter
from zerorepo.models.graph import RPGGraph
from zerorepo.llm.gateway import LLMGateway

gateway = LLMGateway()

# Load a baseline graph (from a previous run)
baseline_json = Path("previous-run/rpg-graph.json").read_text()
baseline_graph = RPGGraph.from_json(baseline_json)

# Parse spec with baseline context
parser = SpecParser(gateway=gateway)
spec = parser.parse(
    description=open("my-app-prd.md").read(),
    baseline_graph=baseline_graph,  # Enables delta classification
)

# The converter tags delta status on each component
converter = GraphConverter(gateway=gateway)
graph = converter.convert(spec, baseline_graph=baseline_graph)

# Inspect delta classifications
from zerorepo.models.node import DeltaClassification

for node in graph.nodes.values():
    if node.delta_status:
        print(f"[{node.delta_status.value}] {node.name}")
        if node.delta_status == DeltaClassification.MODIFIED:
            print(f"  Changed: {node.change_summary}")
        if node.baseline_match_name:
            print(f"  Baseline match: {node.baseline_match_name}")

# Generate delta report
from zerorepo.serena.delta_report import DeltaReportGenerator

reporter = DeltaReportGenerator()
report_md = reporter.generate(graph, baseline_graph)
Path("output/05-delta-report.md").write_text(report_md)
```

#### Delta Classification Workflow

The typical workflow for incremental repository planning:

```bash
# Step 1: Initialize project
zerorepo init

# Step 2: First run (no baseline -- all components are NEW)
zerorepo generate prd-v1.md --model gpt-4o --output ./v1

# Step 3: Update PRD with new requirements
# ... edit prd-v2.md ...

# Step 4: Re-generate with baseline (enables delta classification)
zerorepo generate prd-v2.md --model gpt-4o --output ./v2 \
  --baseline ./v1/03-graph.json

# Step 5: Review delta report
cat ./v2/05-delta-report.md
# Shows: 15 EXISTING, 3 MODIFIED, 8 NEW components
```

The delta report helps you understand exactly what changed between PRD versions,
enabling focused code generation on only the modified and new components.

### Evaluation Pipeline

Evaluate generated repositories against benchmark tasks using a 3-stage pipeline.

```python
from zerorepo.evaluation.pipeline import EvaluationPipeline
from zerorepo.evaluation.localization import FunctionLocalizer
from zerorepo.evaluation.semantic_validation import SemanticValidator
from zerorepo.evaluation.execution_testing import ExecutionTester

# Create the evaluation components
localizer = FunctionLocalizer(...)
validator = SemanticValidator(...)
tester = ExecutionTester(...)

# Build the pipeline
pipeline = EvaluationPipeline(
    localizer=localizer,
    validator=validator,
    tester=tester,
    top_k=5,                    # Localization candidates
    validation_candidates=3,    # Validation attempts per task
)

# Evaluate a single task
from zerorepo.evaluation.models import BenchmarkTask

task = BenchmarkTask(id="task_001", ...)
result = pipeline.evaluate_task(task, repo_path="/path/to/generated/repo")
print(f"Passed: {result.passed}")
print(f"Stage failed: {result.stage_failed}")

# Evaluate all tasks for a repository
results = pipeline.evaluate_repository(tasks, repo_path="/path/to/repo")
print(f"Total: {results.total_tasks}")
print(f"Passed: {results.passed}/{results.total_tasks}")
print(f"Coverage: {results.coverage:.1%}")
```

The 3-stage evaluation pipeline:
1. **Localization** (embedding similarity): Finds candidate functions matching the task
2. **Semantic Validation** (LLM majority voting): Validates function correctness via LLM
3. **Execution Testing** (Docker sandbox): Runs tests in an isolated Docker container

---

## End-to-End Walkthrough

This walkthrough takes you from a natural language specification to a generated and evaluated repository.

### Step 1: Initialize Project

```bash
mkdir my-new-app && cd my-new-app
git init
zerorepo init
```

### Step 2: Write Your Specification

Create a file `spec.txt` with your natural language description:

```text
Build a task management API with the following features:
- RESTful API with FastAPI
- PostgreSQL database with SQLAlchemy ORM
- User authentication with JWT tokens
- CRUD operations for tasks and projects
- Task assignment and status tracking
- Email notifications for task updates
- Rate limiting and input validation
- Docker deployment support

The API should support at least 1000 concurrent users and include
comprehensive error handling with structured error responses.
```

### Step 3: Parse the Specification

```bash
# Parse and save to JSON
zerorepo spec parse spec.txt --output spec.json

# Review and refine
zerorepo spec suggest spec.json
zerorepo spec refine spec.json --add "Add WebSocket support for real-time task updates"

# Check for conflicts
zerorepo spec conflicts spec.json
```

### Step 4: Build the Feature Ontology

```bash
# Build the ontology (populates ChromaDB)
zerorepo ontology build

# Verify the ontology
zerorepo ontology stats
zerorepo ontology search "task management"
```

### Step 5: Run the Pipeline (Python API)

```python
from zerorepo.llm.gateway import LLMGateway
from zerorepo.spec_parser.parser import SpecParser
from zerorepo.selection.orchestrator import ExploreExploitOrchestrator
from zerorepo.graph_construction.builder import FunctionalityGraphBuilder
from zerorepo.codegen.codegen_orchestrator import CodegenOrchestrator

# 1. Parse specification
gateway = LLMGateway()
parser = SpecParser(gateway=gateway)
spec = parser.parse(open("spec.txt").read())

# 2. Select features from ontology
orch = ExploreExploitOrchestrator(store=store, llm_gateway=gateway)
selection = orch.run(spec_description=spec.description)

# 3. Build functionality graph
builder = FunctionalityGraphBuilder(llm_gateway=gateway)
graph = builder.build(selection.selected_features)

# 4. Generate code (TDD loop)
codegen = CodegenOrchestrator(
    graph=graph.rpg_graph,
    test_generator=test_gen,
    impl_generator=impl_gen,
    sandbox_executor=sandbox_exec,
    debug_diagnoser=diagnoser,
)
result = codegen.run()
print(f"Code generation complete: {result.pass_rate:.1f}% pass rate")

# 5. Evaluate
from zerorepo.evaluation.pipeline import EvaluationPipeline

pipeline = EvaluationPipeline(
    localizer=localizer,
    validator=validator,
    tester=tester,
)
eval_result = pipeline.evaluate_repository(tasks, repo_path="./output")
print(f"Evaluation: {eval_result.passed}/{eval_result.total_tasks} tasks passed")
```

---

## Testing

ZeroRepo has a comprehensive test suite organized into three categories.

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=zerorepo --cov-report=term-missing

# Run specific test categories
pytest tests/unit/              # Unit tests (fast, mocked)
pytest tests/functional/        # Functional tests (end-to-end)
pytest tests/regression/        # Regression tests

# Run tests matching a pattern
pytest tests/ -k "test_spec_parser"

# Run with verbose output
pytest tests/ -v
```

### Test Categories

| Directory | Purpose | Speed |
|-----------|---------|-------|
| `tests/unit/` | Isolated unit tests with mocks | Fast |
| `tests/functional/` | End-to-end integration tests | Slow |
| `tests/regression/` | Regression prevention tests | Medium |

### Benchmark Scripts

Located in `scripts/benchmark/`:

| Script | Purpose |
|--------|---------|
| `run_full_benchmark.py` | Execute the full evaluation benchmark suite |
| `build_repocraft.py` | Build the RepoCraft benchmark dataset |
| `harvest_tests.py` | Harvest test cases from generated repositories |

```bash
# Run the full benchmark
python scripts/benchmark/run_full_benchmark.py

# Build benchmark dataset
python scripts/benchmark/build_repocraft.py

# Harvest test cases
python scripts/benchmark/harvest_tests.py
```

---

## Troubleshooting

### Common Issues

**`ConfigurationError: litellm is not installed`**

LiteLLM is a core dependency. Reinstall:

```bash
pip install "zerorepo[all]" --force-reinstall
```

**`CLIError: Already initialised: .zerorepo exists`**

Remove the existing directory and re-initialize:

```bash
rm -rf .zerorepo
zerorepo init
```

**`typer.BadParameter: File not found`**

Ensure file paths are correct. The CLI validates file existence before processing.

**LLM API errors**

- Verify your API key is set: `echo $OPENAI_API_KEY`
- Check model availability: not all providers support all models
- LiteLLM retries automatically with exponential backoff for rate limits and connection errors

**LLM timeout errors during `zerorepo generate`**

Large PRDs or baseline graphs can cause LLM requests to exceed default timeouts.
Two solutions:

```bash
# Option 1: Set the timeout environment variable before running
export LITELLM_REQUEST_TIMEOUT=1200
zerorepo generate large-prd.md --model gpt-4o --output ./output --baseline baseline.json

# Option 2: Use the zerorepo-run-pipeline.py runner script (handles timeouts automatically)
python .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py \
  --prd large-prd.md \
  --model gpt-4o \
  --output ./output \
  --baseline baseline.json
```

The `zerorepo-run-pipeline.py` runner script applies a belt-and-suspenders timeout fix:
it sets the `LITELLM_REQUEST_TIMEOUT` environment variable before importing litellm,
then monkey-patches `litellm.request_timeout` as a fallback.

**Docker sandbox failures**

- Ensure Docker is running: `docker info`
- Verify the `sandbox` extra is installed: `pip install "zerorepo[sandbox]"`
- Check Docker resource limits and network connectivity

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Configuration error |
| `130` | Interrupted (Ctrl+C) |

### Logging

Enable verbose logging for debugging:

```bash
zerorepo --verbose spec parse spec.txt
```

Or set it via environment variable:

```bash
export ZEROREPO_LOG_LEVEL=DEBUG
```

Log output uses Rich formatting and writes to stderr. To log to a file, configure `log_file` in `config.toml` or set `ZEROREPO_LOG_FILE`.

### Environment Variable Overrides

All configuration fields can be overridden via environment variables with the `ZEROREPO_` prefix:

| Variable | Config Field | Example |
|----------|-------------|---------|
| `ZEROREPO_LLM_PROVIDER` | `llm_provider` | `anthropic` |
| `ZEROREPO_LLM_MODEL` | `llm_model` | `claude-sonnet-4-20250514` |
| `ZEROREPO_LOG_LEVEL` | `log_level` | `DEBUG` |
| `ZEROREPO_LOG_FILE` | `log_file` | `/tmp/zerorepo.log` |

---

*See also: [README](README.md) | [Architecture](ARCHITECTURE.md) | [Configuration](CONFIGURATION.md) | [Modules](MODULES.md) | [Evaluation](EVALUATION.md) | [Production Readiness](PRODUCTION_READINESS.md)*
