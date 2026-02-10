# Configuration Reference

ZeroRepo uses a layered configuration system: a TOML file in the project directory, environment variable overrides, and per-module Pydantic configuration models.

## Table of Contents

- [Project Configuration File](#project-configuration-file)
- [Environment Variable Overrides](#environment-variable-overrides)
- [ZeroRepoConfig Model](#zerorepoconfig-model)
- [LLM Gateway Configuration](#llm-gateway-configuration)
- [Spec Parser Configuration](#spec-parser-configuration)
- [Ontology Service Configuration](#ontology-service-configuration)
- [Vector Database Configuration](#vector-database-configuration)
- [Docker Sandbox Configuration](#docker-sandbox-configuration)
- [Code Generation Configuration](#code-generation-configuration)
- [Selection Configuration](#selection-configuration)
- [Graph Construction Configuration](#graph-construction-configuration)
- [Logging Configuration](#logging-configuration)

---

## Project Configuration File

After running `zerorepo init`, configuration lives in `.zerorepo/config.toml`:

```toml
# .zerorepo/config.toml

[general]
llm_provider = "openai"       # LLM provider: "openai", "anthropic", "ollama"
llm_model = "gpt-4o-mini"     # Default LLM model identifier
log_level = "INFO"             # Logging level: DEBUG, INFO, WARNING, ERROR
```

**Location resolution order:**

1. Explicit `--config PATH` CLI flag
2. `<project_dir>/.zerorepo/config.toml`
3. Defaults from the `ZeroRepoConfig` model

The configuration file uses nested TOML sections which are flattened automatically. Both flat and nested formats are supported:

```toml
# Flat format
llm_provider = "anthropic"

# Nested format (equivalent)
[general]
llm_provider = "anthropic"
```

---

## Environment Variable Overrides

All `ZeroRepoConfig` fields can be overridden via environment variables using the `ZEROREPO_` prefix. Environment variables take precedence over TOML values.

| Environment Variable | Config Field | Example Value |
|---------------------|--------------|---------------|
| `ZEROREPO_LLM_PROVIDER` | `llm_provider` | `anthropic` |
| `ZEROREPO_LLM_MODEL` | `llm_model` | `claude-sonnet-4-5-20250929` |
| `ZEROREPO_LOG_LEVEL` | `log_level` | `DEBUG` |
| `ZEROREPO_LOG_FILE` | `log_file` | `/var/log/zerorepo.log` |
| `ZEROREPO_PROJECT_DIR` | `project_dir` | `/path/to/project` |
| `ZEROREPO_VECTOR_DB_PATH` | `vector_db_path` | `/path/to/vectordb` |

**How it works** (`cli/config.py:_apply_env_overrides`): The loader iterates over all environment variables starting with `ZEROREPO_`, strips the prefix, lowercases the remainder, and checks if it matches a `ZeroRepoConfig` field name. Matching values are inserted into the config data dict before Pydantic validation.

---

## ZeroRepoConfig Model

**Module:** `zerorepo.cli.config.ZeroRepoConfig`

The root configuration model. All fields have sensible defaults.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `project_dir` | `Path` | `Path.cwd()` | Project root directory |
| `llm_provider` | `str` | `"openai"` | LLM provider identifier |
| `llm_model` | `str` | `"gpt-4o-mini"` | Default LLM model name |
| `vector_db_path` | `Path` | `.zerorepo/vectordb` | Path to vector database storage |
| `log_level` | `str` | `"INFO"` | Logging level |
| `log_file` | `Path \| None` | `None` | Optional log file path |

**Usage:**

```python
from zerorepo.cli.config import load_config

# Load from default location
config = load_config()

# Load from explicit TOML file
config = load_config(config_path=Path("custom.toml"))

# Load with specific project directory
config = load_config(project_dir=Path("/my/project"))

# Generate default TOML content
from zerorepo.cli.config import default_config_toml
print(default_config_toml())
```

---

## LLM Gateway Configuration

**Module:** `zerorepo.llm.models.GatewayConfig`

Controls the multi-provider LLM gateway powered by LiteLLM.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tier_models` | `dict[ModelTier, dict[str, str]]` | See below | Mapping of tier to provider to model name |
| `max_retries` | `int` | `4` | Maximum retry attempts on transient errors (0-10) |
| `base_retry_delay` | `float` | `1.0` | Base delay in seconds for exponential backoff |
| `default_provider` | `str` | `"openai"` | Default LLM provider when none specified |

### Model Tiers

ZeroRepo uses a three-tier model selection system for cost/quality optimization:

| Tier | Purpose | OpenAI | Anthropic | Ollama |
|------|---------|--------|-----------|--------|
| `CHEAP` | Fast, low-cost tasks | `gpt-4o-mini` | `claude-3-haiku-20240307` | `ollama/llama3.2` |
| `MEDIUM` | General-purpose tasks | `gpt-4o` | `claude-3-5-sonnet-20241022` | `ollama/llama3.2` |
| `STRONG` | Complex reasoning | `gpt-4o` | `claude-sonnet-4-20250514` | `ollama/llama3.2` |

**Provider fallback order:** `openai` -> `anthropic` -> `ollama`

### Token Pricing (USD per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| `gpt-4o-mini` | $0.15 | $0.60 |
| `gpt-4o` | $2.50 | $10.00 |
| `claude-3-haiku-20240307` | $0.25 | $1.25 |
| `claude-3-5-sonnet-20241022` | $3.00 | $15.00 |
| `claude-sonnet-4-20250514` | $3.00 | $15.00 |

### Required API Keys

Set the appropriate environment variable(s) for your chosen provider:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Ollama (local, no key required)
# Ensure ollama is running: ollama serve
```

**Usage:**

```python
from zerorepo.llm import LLMGateway, GatewayConfig, ModelTier

config = GatewayConfig(
    default_provider="anthropic",
    max_retries=3,
    base_retry_delay=2.0,
)
gateway = LLMGateway(config=config)
```

---

## Spec Parser Configuration

**Module:** `zerorepo.spec_parser.parser.ParserConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | `"gpt-4o-mini"` | Model identifier for LLM calls |
| `tier` | `ModelTier` | `CHEAP` | Model tier for cost/quality selection |
| `template_name` | `str` | `"spec_parsing"` | Prompt template name |
| `max_description_length` | `int` | `50000` | Maximum description length in characters |
| `use_json_mode` | `bool` | `True` | Request JSON response format from the LLM |

### Conflict Detector Configuration

**Module:** `zerorepo.spec_parser.conflict_detector.DetectorConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_llm` | `bool` | `True` | Enable LLM-based nuanced conflict detection |

### Refinement Configuration

**Module:** `zerorepo.spec_parser.refinement.RefinerConfig`

Configures the specification refinement engine that handles adding requirements, clarification, and improvement suggestions.

### Reference Processor Configuration

**Module:** `zerorepo.spec_parser.reference_processor.ProcessorConfig`

Configures the reference material processor with content extractors for code, inline, and PDF sources.

---

## Ontology Service Configuration

**Module:** `zerorepo.ontology.service.OntologyServiceConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `store_config` | `OntologyStoreConfig` | (defaults) | ChromaDB store configuration |
| `embedder_config` | `EmbedderConfig` | (defaults) | Embedding pipeline configuration |
| `include_github` | `bool` | `True` | Include GitHub Topics seed generator |
| `include_stackoverflow` | `bool` | `True` | Include StackOverflow Tags seed generator |
| `include_libraries` | `bool` | `True` | Include Library Docs seed generator |
| `include_expander` | `bool` | `True` | Include combinatorial taxonomy expander |
| `expander_target_count` | `int` | `50000` | Target node count for taxonomy expander (min: 100) |
| `auto_embed_on_build` | `bool` | `True` | Automatically embed nodes after building |
| `auto_store_on_build` | `bool` | `True` | Automatically store nodes after building |

### Ontology Store Configuration

**Module:** `zerorepo.ontology.chromadb_store.OntologyStoreConfig`

Configures the ChromaDB-backed ontology storage.

### LLM Backend Configuration

**Module:** `zerorepo.ontology.llm_backend.LLMBackendConfig`

Configures the LLM-generated ontology backend for feature generation.

### Embedder Configuration

**Module:** `zerorepo.ontology.embeddings.EmbedderConfig`

Configures the batch embedding pipeline for converting feature nodes to vectors.

---

## Vector Database Configuration

**Module:** `zerorepo.vectordb.models.VectorStoreConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `persist_dir` | `str` | `".zerorepo/chroma"` | Directory for persistent ChromaDB storage |
| `collection_name` | `str` | `"feature_trees"` | Name of the ChromaDB collection |
| `embedding_model` | `str` | `"all-MiniLM-L6-v2"` | Sentence-transformer model for embeddings |
| `batch_size` | `int` | `100` | Maximum batch size for bulk operations (min: 1) |

**Usage:**

```python
from zerorepo.vectordb import VectorStore, VectorStoreConfig

config = VectorStoreConfig(
    persist_dir="/custom/path/chroma",
    collection_name="my_collection",
    embedding_model="all-mpnet-base-v2",
    batch_size=200,
)
store = VectorStore(config=config)
```

---

## Docker Sandbox Configuration

**Module:** `zerorepo.sandbox.models.SandboxConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | `str` | `"python:3.11-slim"` | Docker image for the sandbox container |
| `memory_limit` | `str` | `"512m"` | Memory limit (e.g., `"512m"`, `"1g"`) |
| `cpu_count` | `int` | `1` | Number of CPU cores to allocate (1-8) |
| `timeout` | `int` | `300` | Default timeout in seconds for operations |

### Sandbox Executor Configuration

**Module:** `zerorepo.codegen.sandbox_executor.SandboxExecutorConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout_seconds` | `int` | `30` | Maximum time for a single test run (min: 1) |
| `install_dependencies` | `bool` | `True` | Whether to install pip dependencies |
| `default_requirements` | `list[str]` | `["pytest", "pytest-json-report"]` | Default pip packages to install |
| `cleanup_on_finish` | `bool` | `True` | Clean up sandbox after each run |

**Prerequisites:** Docker must be installed and running. Install the sandbox extras:

```bash
pip install zerorepo[sandbox]
```

---

## Code Generation Configuration

### Codegen Orchestrator

**Module:** `zerorepo.codegen.codegen_orchestrator.OrchestratorConfig`

Main orchestrator configuration for the TDD generation loop.

### Unit Validator

**Module:** `zerorepo.codegen.unit_validator.UnitValidatorConfig`

Configuration for staged unit test validation.

### Regression Detector

**Module:** `zerorepo.codegen.regression_detector.RegressionDetectorConfig`

Configuration for cross-iteration regression detection.

### Majority Vote

**Module:** `zerorepo.codegen.majority_vote.MajorityVoteConfig`

Configuration for majority voting on test result consensus.

### Integration Generator

**Module:** `zerorepo.codegen.integration_generator.IntegrationGeneratorConfig`

Configuration for cross-node integration test generation.

### Test Artifact Store

**Module:** `zerorepo.codegen.test_artifacts.ArtifactStoreConfig`

Configuration for test artifact lifecycle management.

---

## Selection Configuration

### Exploitation Retriever

**Module:** `zerorepo.selection.exploitation.ExploitationConfig`

Configuration for vector search with LLM query augmentation.

### Exploration Strategy

**Module:** `zerorepo.selection.exploration.ExplorationConfig`

Configuration for gap-based exploratory query generation.

### Diversity Sampler

**Module:** `zerorepo.selection.diversity_sampler.DiversityConfig`

Configuration for rejection sampling with cosine similarity thresholds.

### LLM Filter

**Module:** `zerorepo.selection.llm_filter.LLMFilterConfig`

Configuration for LLM-based feature relevance filtering.

### Convergence Monitor

**Module:** `zerorepo.selection.convergence.ConvergenceConfig`

Configuration for iteration convergence tracking.

### Explore-Exploit Orchestrator

**Module:** `zerorepo.selection.orchestrator.OrchestratorConfig`

Main orchestrator configuration for the explore-exploit selection loop.

---

## Graph Construction Configuration

### Module Partitioner

**Module:** `zerorepo.graph_construction.partitioner.PartitionerConfig`

Configuration for LLM-driven feature clustering into modules.

### Dependency Inference

**Module:** `zerorepo.graph_construction.dependencies.DependencyConfig`

Configuration for LLM-driven module dependency detection.

### Metrics Configuration

**Module:** `zerorepo.graph_construction.metrics.MetricsConfig`

Configuration for cohesion, coupling, and modularity metric computation.

### Graph Builder

**Module:** `zerorepo.graph_construction.builder.BuilderConfig`

Full pipeline graph builder configuration.

### Graph Refinement

**Module:** `zerorepo.graph_construction.refinement.RefinementConfig`

Configuration for iterative graph refinement with undo support.

### Graph Export

**Module:** `zerorepo.graph_construction.export.ExportConfig`

Configuration for graph export to various formats (JSON, DOT, Mermaid).

---

## Logging Configuration

ZeroRepo uses Python's `logging` module with Rich-formatted console output.

### CLI Logging

Controlled via the `--verbose` / `-v` flag or the `log_level` configuration field:

```bash
# Normal output (INFO level)
zerorepo spec parse description.txt

# Debug output
zerorepo --verbose spec parse description.txt
```

### Programmatic Logging

```python
from zerorepo.cli.logging_setup import setup_logging

# Basic setup
logger = setup_logging(level="DEBUG")

# With file logging
logger = setup_logging(
    level="INFO",
    log_file=Path("/var/log/zerorepo.log"),
)
```

The logging infrastructure uses:
- **Console handler:** Rich `RichHandler` on stderr with timestamps
- **File handler** (optional): Standard `FileHandler` with `%(asctime)s | %(name)s | %(levelname)s | %(message)s` format
- **Logger name:** `zerorepo`

### Log Levels

| Level | CLI Flag | Config Value | Description |
|-------|----------|-------------|-------------|
| DEBUG | `-v` / `--verbose` | `"DEBUG"` | All messages including internal details |
| INFO | (default) | `"INFO"` | Standard operational messages |
| WARNING | -- | `"WARNING"` | Potential issues |
| ERROR | -- | `"ERROR"` | Errors only |

---

## Configuration Hierarchy Summary

Configuration resolution follows this priority (highest to lowest):

1. **CLI flags** (`--verbose`, `--config PATH`, etc.)
2. **Environment variables** (`ZEROREPO_*` prefix)
3. **TOML configuration file** (`.zerorepo/config.toml`)
4. **Pydantic model defaults** (defined in each config class)

Each module's configuration class can be instantiated independently for programmatic use, or configured through the global `ZeroRepoConfig` and TOML file for CLI usage.
