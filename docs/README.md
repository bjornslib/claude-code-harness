# ZeroRepo

**Repository Planning Graph (RPG) for generating complete software repositories from natural language specifications.**

ZeroRepo transforms a plain-text description of a software project into a fully structured, dependency-aware planning graph and then generates the complete repository -- source files, tests, configuration, and documentation -- using LLM-driven pipelines.

## Key Features

- **Natural Language Specification Parsing** -- Describe your project in plain text; ZeroRepo extracts languages, frameworks, constraints, and quality attributes into a structured `RepositorySpec`.
- **Feature Ontology Service** -- Builds a 50,000+ node feature taxonomy from GitHub Topics, StackOverflow Tags, and library documentation, stored in ChromaDB with vector embeddings.
- **Explore-Exploit Subtree Selection** -- Uses a novel explore/exploit loop with diversity sampling and convergence monitoring to select the most relevant features for your project.
- **Functionality Graph Construction** -- Partitions features into modules, infers inter-module dependencies, computes cohesion/coupling/modularity metrics, and iteratively refines the graph.
- **RPG Enrichment Pipeline** -- Encoder-based pipeline that enriches graph nodes with folder structures, file paths, interface designs, base classes, data flows, and execution ordering.
- **Serena MCP Integration** -- Workspace validation and symbol analysis via the Model Context Protocol for type-safe dependency extraction.
- **TDD Code Generation** -- Test-driven development loop with LLM implementation generation, Docker sandbox execution, majority-vote failure diagnosis, and regression detection.
- **Repository Assembly** -- Generates complete Python packages: file structures, import management, `__init__.py` files, `pyproject.toml`, `requirements.txt`, README, and RPG artifacts.
- **Evaluation Framework** -- Benchmarks generated repositories against the RepoCraft suite with execution testing, semantic validation, profiling, and failure analysis.

## Architecture

ZeroRepo follows a multi-stage pipeline architecture:

```
Specification   Feature      Explore-Exploit   Graph          RPG
  Parsing    -> Ontology  ->   Selection    -> Construction -> Enrichment
                                                                  |
                                                                  v
              Evaluation  <-  Repository   <-  Code         <- Serena
              Framework      Assembly         Generation       Validation
```

### Core Data Model

The **Repository Planning Graph (RPG)** is a directed graph of `RPGNode` and `RPGEdge` objects:

| Model | Description |
|-------|-------------|
| `RPGNode` | A unit of planning at one of three levels (`MODULE`, `COMPONENT`, `FEATURE`) with type classification (`FUNCTIONALITY`, `FOLDER_AUGMENTED`, `FILE_AUGMENTED`, `FUNCTION_AUGMENTED`) |
| `RPGEdge` | A directed relationship (`HIERARCHY`, `DATA_FLOW`, `ORDERING`, `INHERITANCE`, `INVOCATION`) between two nodes |
| `RPGGraph` | Container managing nodes and edges with referential integrity, JSON serialization, and query methods |

## Installation

### Requirements

- Python 3.11+
- [Docker](https://www.docker.com/) (optional, for sandbox execution)

### Install from Source

```bash
git clone <repository-url>
cd zerorepo
pip install -e .
```

### Optional Dependencies

```bash
# Development tools (pytest, coverage, mocking)
pip install -e ".[dev]"

# Docker sandbox support
pip install -e ".[sandbox]"

# Vector database support (ChromaDB + sentence-transformers)
pip install -e ".[vectordb]"

# All optional dependencies
pip install -e ".[dev,sandbox,vectordb]"
```

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | >=2.0, <3.0 | Data validation and configuration models |
| `litellm` | >=1.0 | Multi-provider LLM gateway |
| `jinja2` | >=3.1 | Prompt template rendering |
| `chromadb` | >=0.5 | Vector embedding storage |

## Quick Start

### 1. Initialize a Project

```bash
zerorepo init [path]
```

Creates a `.zerorepo/` directory with:
- `config.toml` -- project configuration
- `graphs/` -- stored RPG graphs
- `sandbox/` -- sandbox working directory

### 2. Parse a Specification

```bash
# Parse a natural language description
zerorepo spec parse description.txt

# Save structured output to JSON
zerorepo spec parse description.txt --output spec.json

# Include conflict detection (enabled by default)
zerorepo spec parse description.txt --output spec.json --conflicts
```

### 3. Refine the Specification

```bash
# Add a new requirement
zerorepo spec refine spec.json --add "Add WebSocket support for real-time updates"

# Answer a clarification question
zerorepo spec refine spec.json --clarify "Which database?|PostgreSQL with SQLAlchemy ORM"

# View refinement history
zerorepo spec history spec.json
```

### 4. Build the Feature Ontology

```bash
# Build from all seed generators
zerorepo ontology build

# Build with custom target count
zerorepo ontology build --target-count 100000

# Search the ontology
zerorepo ontology search "authentication"

# View ontology statistics
zerorepo ontology stats

# Extend with custom features
zerorepo ontology extend --csv custom_features.csv

# Export to CSV
zerorepo ontology export --output ontology.csv
```

### 5. Detect Conflicts

```bash
# Rule-based + LLM conflict detection
zerorepo spec conflicts spec.json

# Rule-based only (no LLM)
zerorepo spec conflicts spec.json --no-llm

# Attach conflicts to the spec file
zerorepo spec conflicts spec.json --attach
```

### 6. Get Improvement Suggestions

```bash
zerorepo spec suggest spec.json
zerorepo spec suggest spec.json --json
```

## Python API

ZeroRepo modules can also be used programmatically:

```python
from zerorepo.spec_parser import SpecParser, ParserConfig
from zerorepo.llm import LLMGateway

# Parse a specification
gateway = LLMGateway()
parser = SpecParser(gateway=gateway, config=ParserConfig(model="gpt-4o-mini"))
spec = parser.parse("Build a REST API with user authentication and PostgreSQL storage")

# Access structured data
print(spec.technical_requirements.languages)   # ['Python']
print(spec.technical_requirements.frameworks)   # ['FastAPI', ...]
print(spec.quality_attributes.security)         # 'JWT authentication ...'
```

```python
from zerorepo.models import RPGGraph, RPGNode, RPGEdge, NodeLevel, NodeType, EdgeType

# Build a graph programmatically
graph = RPGGraph(metadata={"project": "my-api"})
module = RPGNode(name="auth", level=NodeLevel.MODULE, node_type=NodeType.FUNCTIONALITY)
graph.add_node(module)

# Serialize and deserialize
json_str = graph.to_json()
restored = RPGGraph.from_json(json_str)
```

```python
from zerorepo.graph_ops import topological_sort, detect_cycles, filter_by_level
from zerorepo.models import NodeLevel

# Topological ordering for code generation
ordered_nodes = topological_sort(graph)

# Check for circular dependencies
cycles = detect_cycles(graph)

# Filter nodes by hierarchy level
modules = filter_by_level(graph, NodeLevel.MODULE)
```

## Module Overview

ZeroRepo is organized into 14 packages under `src/zerorepo/`:

| Module | Purpose |
|--------|---------|
| `cli` | Typer CLI with `init`, `spec`, and `ontology` sub-command groups |
| `models` | Core `RPGNode`, `RPGEdge`, `RPGGraph` Pydantic models and enums |
| `spec_parser` | LLM-driven specification parsing, conflict detection, refinement, and reference processing |
| `ontology` | Feature ontology with LLM backend, ChromaDB storage, embeddings, and domain extension |
| `selection` | Explore-exploit subtree selection with diversity sampling and convergence monitoring |
| `graph_construction` | Module partitioning, dependency inference, metrics, graph building, refinement, and export |
| `rpg_enrichment` | Encoder pipeline: folder, file, interface design, base class, data flow, and ordering encoders |
| `graph_ops` | Graph operations: topological sort, cycle detection, filtering, subgraph extraction, serialization |
| `codegen` | TDD generation loop, localization, Serena editing, repository assembly, test validation |
| `llm` | Multi-provider LLM gateway via LiteLLM with tiered model selection and token tracking |
| `vectordb` | ChromaDB wrapper with sentence-transformer embedding generation |
| `serena` | MCP server lifecycle, JSON-RPC client, workspace management, symbol lookup, dependency extraction |
| `sandbox` | Docker sandbox for isolated code execution and test running |
| `evaluation` | Benchmark pipeline with execution testing, semantic validation, profiling, and failure analysis |

## CLI Reference

### Global Options

```
zerorepo [OPTIONS] COMMAND

Options:
  -V, --version          Show version and exit
  -v, --verbose          Enable verbose (DEBUG) output
  -c, --config PATH      Path to configuration TOML file
```

### Commands

| Command | Description |
|---------|-------------|
| `zerorepo init [PATH]` | Initialize a new ZeroRepo project |
| `zerorepo spec parse FILE` | Parse a natural language specification |
| `zerorepo spec refine FILE` | Refine an existing specification |
| `zerorepo spec conflicts FILE` | Detect conflicting requirements |
| `zerorepo spec suggest FILE` | Get improvement suggestions |
| `zerorepo spec export FILE` | Export specification to JSON or summary |
| `zerorepo spec history FILE` | Show refinement history |
| `zerorepo ontology build` | Build the feature ontology |
| `zerorepo ontology search QUERY` | Search the feature ontology |
| `zerorepo ontology stats` | Display ontology statistics |
| `zerorepo ontology extend` | Extend ontology with custom features |
| `zerorepo ontology export` | Export ontology to CSV |

## Configuration

ZeroRepo is configured via `.zerorepo/config.toml` with environment variable overrides using the `ZEROREPO_` prefix. See [CONFIGURATION.md](CONFIGURATION.md) for the full reference.

```toml
# .zerorepo/config.toml
[general]
llm_provider = "openai"
llm_model = "gpt-4o-mini"
log_level = "INFO"
```

```bash
# Environment variable overrides
export ZEROREPO_LLM_PROVIDER=anthropic
export ZEROREPO_LLM_MODEL=claude-sonnet-4-5-20250929
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=zerorepo

# Run only functional (end-to-end) tests
pytest -m functional
```

## Further Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture and data flow diagrams
- [CONFIGURATION.md](CONFIGURATION.md) -- Full configuration reference
- [MODULES.md](MODULES.md) -- Detailed module documentation
- [USAGE_GUIDE.md](USAGE_GUIDE.md) -- Step-by-step usage guide
- [EVALUATION.md](EVALUATION.md) -- Evaluation framework documentation

## License

See the repository root for license information.
