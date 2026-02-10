# PRD-RPG-P2-001: Repository Planning Graph - Phase 2: Proposal-Level Construction

**Version:** 1.0
**Status:** Draft
**Created:** 2026-02-07
**Owner:** ZeroRepo Development Team
**Phase:** 2 of 4 (Feature Planning Pipeline)

---

## Executive Summary

Phase 2 implements the core feature planning pipeline that translates natural language repository specifications into structured functionality graphs. This phase builds on Phase 1 (Foundation) and delivers the three-step RPG process: (1) Feature ontology grounding, (2) Explore-exploit subtree selection, and (3) Functionality graph construction through LLM-driven refactoring.

**Key Deliverables:**
- Pluggable feature ontology service with 50K-100K nodes
- Diversity-aware explore-exploit search algorithm (Algorithm 2 from paper)
- LLM-driven functionality graph construction
- User specification parser with iterative refinement support

**Success Metrics:**
- 70% feature coverage by iteration 5, 95%+ by iteration 30
- Functionality graphs with 3+ cohesive modules
- Sub-5s ontology query latency for 1M+ node trees

---

## Background & Context

### Research Foundation
The EpiCoder paper demonstrates that grounding features in a large-scale ontology (1.5M+ nodes, 7 hierarchical levels) and using explore-exploit search achieves superior repository planning compared to direct LLM generation. Key findings:

- **Feature grounding reduces hallucination**: Ontology anchoring prevents LLM from inventing non-existent capabilities
- **Diversity beats greedy selection**: Explore-exploit achieves 18% higher feature coverage than pure exploitation
- **Modular refactoring enables evolution**: Functionality graphs provide clear extension points

### Phase Dependencies
- **Depends on Phase 1**: LLM abstraction layer, vector store infrastructure, prompt templates
- **Enables Phase 3**: File-level construction uses functionality graph as blueprint
- **Enables Phase 4**: Evolution uses graph structure to identify extension points

### Design Philosophy
**Pluggability over perfection**: Since EpiCoder's ontology is proprietary, we prioritize:
1. Swappable ontology backends (custom-built, LLM-generated, hybrid)
2. Incremental improvement path (start small, grow to 1M+ nodes)
3. Domain extensibility (users can augment with domain-specific features)

---

## Epic 2.1: Feature Ontology Service

### Overview
Build a pluggable feature ontology backend that provides hierarchical feature trees with vector embeddings for semantic search. Since EpiCoder's ontology is not open-source, we implement multiple backend options.

### Requirements

#### Functional Requirements

**FR-2.1.1: Ontology Backend Interface**
- Abstract base class `OntologyBackend` with methods:
  - `search(query: str, top_k: int) -> List[FeaturePath]`
  - `get_node(feature_id: str) -> FeatureNode`
  - `get_children(feature_id: str) -> List[FeatureNode]`
  - `get_statistics() -> OntologyStats`
- Support for pluggable implementations

**FR-2.1.2: Built-In Backend: GitHub Topics Ontology**
- Scrape GitHub topics hierarchy (e.g., "machine-learning" → "deep-learning" → "transformers")
- Scrape Stack Overflow tags with parent-child relationships
- Scrape popular library documentation hierarchies (scikit-learn, TensorFlow, React)
- Target: 50K-100K feature nodes minimum
- Hierarchical levels: 4-7 (e.g., Domain → Category → Subcategory → Feature → Variant)

**FR-2.1.3: Built-In Backend: LLM-Generated Ontology**
- On-demand generation: Given user spec, LLM generates relevant feature tree
- Caching: Store generated trees for reuse across similar projects
- Hybrid mode: Start with GitHub/SO, augment with LLM for gaps

**FR-2.1.4: Vector Embeddings**
- Embed each feature node using `text-embedding-3-small` (1536 dimensions)
- Embedding input: `{full_hierarchical_path} | {description} | {tags}`
- Example: "Software → Web Development → Frontend → State Management → React Hooks | Managing component state in React applications | react, hooks, useState, useEffect"
- Store in ChromaDB with metadata: `{feature_id, level, parent_id, full_path, tags}`

**FR-2.1.5: Domain Extension API**
- Users can upload custom feature CSVs: `feature_id,parent_id,name,description,tags`
- System merges custom features into ontology
- Conflict resolution: user features override defaults

#### Non-Functional Requirements

**NFR-2.1.1: Performance**
- Vector search latency: <100ms for top-100 results
- Ontology load time: <5s for 1M+ node tree
- Embedding generation: batch mode for initial build, on-demand for extensions

**NFR-2.1.2: Scalability**
- Support up to 5M feature nodes (3x EpiCoder's size)
- ChromaDB collection partitioning for large ontologies

**NFR-2.1.3: Extensibility**
- Clear plugin interface for custom backends
- Example: user provides Elasticsearch endpoint, system adapts

### Tasks

#### Task 2.1.1: Define Ontology Data Model
- **Estimated Effort:** 2 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `models/feature_ontology.py` with Pydantic models:
    - `FeatureNode(id, name, description, parent_id, level, tags, embedding)`
    - `FeaturePath(nodes: List[FeatureNode], score: float)`
    - `OntologyStats(total_nodes, total_levels, avg_children, max_depth)`
  - `interfaces/ontology_backend.py` with abstract base class
- **Acceptance Criteria:**
  - All models pass schema validation tests
  - Backend interface has 100% type coverage

#### Task 2.1.2: Implement GitHub Topics Scraper
- **Estimated Effort:** 5 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `scrapers/github_topics.py`: Scrapes GitHub GraphQL API for topic hierarchy
  - `scrapers/stackoverflow_tags.py`: Scrapes SO tag wiki for parent-child links
  - `scrapers/library_docs.py`: Parses library docs (scikit-learn, React, Django) for API hierarchies
  - `scripts/build_ontology.py`: Orchestrates scraping, deduplicates, builds unified tree
- **Acceptance Criteria:**
  - Scrapes at least 50K unique features
  - Hierarchical depth of 4-7 levels
  - No orphan nodes (all nodes except root have parents)
  - Output CSV with columns: `feature_id,parent_id,name,description,tags,level`

#### Task 2.1.3: Implement Vector Embedding Pipeline
- **Estimated Effort:** 3 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `embeddings/feature_embedder.py`: Batch embeds features using OpenAI API
  - `embeddings/chromadb_store.py`: Stores embeddings in ChromaDB with metadata
  - Rate limiting and retry logic for API calls
- **Acceptance Criteria:**
  - Embeds 50K features in <30 minutes (batch mode)
  - ChromaDB collection created with metadata filters enabled
  - Vector search returns semantically similar features (manual spot-check: "authentication" returns "OAuth", "JWT", "session management")

#### Task 2.1.4: Implement LLM-Generated Ontology Backend
- **Estimated Effort:** 4 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `backends/llm_ontology.py`: On-demand ontology generation
  - Prompt template: "Given user spec: {spec}, generate a hierarchical feature tree with 4-7 levels covering all required capabilities"
  - Caching layer: Store generated trees in SQLite keyed by spec hash
  - Hybrid mode: Merge LLM-generated features with GitHub/SO base
- **Acceptance Criteria:**
  - LLM backend generates 20-50 features for simple specs (e.g., "TODO app")
  - Hybrid mode augments GitHub ontology without duplication
  - Cache hit reduces generation time from 10s to <100ms

#### Task 2.1.5: Implement Domain Extension API
- **Estimated Effort:** 3 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `api/ontology_extension.py`: Accepts CSV uploads, merges into ontology
  - Conflict resolution: User features override defaults with same `feature_id`
  - Re-embedding: Automatically embeds new features
- **Acceptance Criteria:**
  - User uploads 100 custom features, all appear in search results
  - Override test: Upload feature with same ID, verify new description takes precedence

#### Task 2.1.6: Build Ontology Service CLI
- **Estimated Effort:** 2 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `cli/ontology.py`: Command-line tool for ontology management
  - Commands: `build`, `search`, `stats`, `extend`, `export`
  - Example: `python -m cli.ontology search "machine learning" --top-k 10`
- **Acceptance Criteria:**
  - CLI successfully builds ontology from scratch
  - Search command returns ranked results with scores
  - Stats command shows node count, depth, coverage

### Acceptance Criteria (Epic 2.1)

**Functional Tests:**
1. **Ontology Build Test**
   - Run `python -m cli.ontology build --backend github`
   - Verify: At least 50K features, 4-7 levels, no orphans
   - Verify: All features have embeddings in ChromaDB

2. **Semantic Search Test**
   - Query: "user authentication"
   - Expected top-5 results include: OAuth, JWT, session management, password hashing, 2FA
   - Query: "data visualization"
   - Expected top-5 results include: charts, graphs, plotting, dashboards, D3.js

3. **Domain Extension Test**
   - Upload custom CSV with 50 medical imaging features
   - Search for "MRI processing"
   - Verify: Custom features appear in results

4. **LLM Ontology Test**
   - Input spec: "Build a real-time chat application"
   - LLM generates features: WebSocket, message queue, presence tracking, typing indicators
   - Verify: All features embedded and searchable

**Performance Tests:**
1. Vector search for top-100 results: <100ms (p95)
2. Ontology load time for 100K nodes: <5s
3. Embedding batch job for 10K features: <10 minutes

**Integration Tests:**
1. Plug in custom backend (mock Elasticsearch)
2. Verify: All interface methods work correctly

---

## Epic 2.2: Explore-Exploit Subtree Selection

### Overview
Implement Algorithm 2 from the paper: diversity-aware explore-exploit search that selects a repository-aligned subtree from the feature ontology. This algorithm balances exploitation (selecting features most aligned with user goal) and exploration (ensuring diversity across ontology branches).

### Requirements

#### Functional Requirements

**FR-2.2.1: Exploitation Phase**
- Retrieve top-k feature paths aligned with user specification using vector search
- LLM augments user spec with related keywords (e.g., "web app" → "REST API", "database", "frontend")
- Configurable k (default 50, range 10-200)

**FR-2.2.2: Exploration Phase**
- Track visited ontology regions using bit vector or bloom filter
- Deliberately expand into unvisited branches for diversity
- LLM proposes exploratory queries based on coverage gaps
- Example: If all features are "backend", explore "frontend" and "DevOps"

**FR-2.2.3: Diversity-Aware Rejection Sampling (Algorithm 1)**
- Sample candidate features from top-k results
- Reject candidates too similar to already-selected features (cosine similarity > 0.85)
- Iteratively sample until diversity threshold met or max iterations reached
- Track diversity metrics: silhouette score, branch coverage

**FR-2.2.4: LLM-Driven Filtering**
- LLM reviews selected features against user specification
- Prunes irrelevant features (e.g., "mobile development" for a backend-only spec)
- Self-check pipeline: LLM explains why each feature is relevant
- User can override LLM decisions

**FR-2.2.5: Convergence Monitoring**
- Track coverage per iteration: % of ontology branches visited
- Stop early if coverage plateaus (< 2% increase over 5 iterations)
- Default: 30 iterations (paper's default)
- Configurable range: 5-50 iterations

#### Non-Functional Requirements

**NFR-2.2.1: Reproducibility**
- Seed random number generator for sampling
- Log all LLM calls with prompts and responses
- Version control for prompts

**NFR-2.2.2: Performance**
- Full explore-exploit cycle (30 iterations): <5 minutes
- Per-iteration latency: <10s (mostly LLM calls)

**NFR-2.2.3: Observability**
- Log coverage metrics per iteration
- Visualize feature selection over iterations (coverage curve)
- Export selected features to JSON/CSV

### Tasks

#### Task 2.2.1: Implement Exploitation Retriever
- **Estimated Effort:** 3 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `retrieval/exploitation.py`: Vector search wrapper for ontology
  - `retrieval/query_augmentation.py`: LLM generates related keywords from spec
  - Prompt template: "User wants: {spec}. What related features might they need? Output keywords only."
- **Acceptance Criteria:**
  - Query augmentation expands "web app" to include "database", "API", "authentication"
  - Retriever returns top-k features with similarity scores
  - Results sorted by relevance

#### Task 2.2.2: Implement Exploration Strategy
- **Estimated Effort:** 4 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `retrieval/exploration.py`: Tracks visited ontology regions, proposes exploratory queries
  - Bit vector for branch coverage (one bit per top-level category)
  - LLM generates exploratory queries: "Coverage gaps: {missing_branches}. Suggest features to explore."
- **Acceptance Criteria:**
  - Exploration identifies at least 3 uncovered branches by iteration 10
  - Exploratory queries retrieve features from new branches
  - Coverage increases monotonically

#### Task 2.2.3: Implement Diversity-Aware Sampling (Algorithm 1)
- **Estimated Effort:** 4 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `sampling/diversity_sampler.py`: Rejection sampling with similarity threshold
  - Cosine similarity computation using cached embeddings
  - Diversity metrics: silhouette score, average pairwise distance
- **Acceptance Criteria:**
  - Sampler rejects candidates with similarity > 0.85 to existing features
  - Selected features have average pairwise distance > 0.5
  - Silhouette score > 0.3 (moderate diversity)

#### Task 2.2.4: Implement LLM Filtering Pipeline
- **Estimated Effort:** 3 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `filtering/llm_filter.py`: LLM reviews features, prunes irrelevant ones
  - Prompt template: "User spec: {spec}. Selected features: {features}. For each feature, explain relevance or mark IRRELEVANT."
  - Self-check: LLM re-evaluates its own decisions
- **Acceptance Criteria:**
  - LLM correctly prunes "mobile development" from backend-only spec
  - LLM retains all relevant features (manual validation on 10 test specs)
  - Self-check reduces false negatives by 20%

#### Task 2.2.5: Implement Convergence Monitor
- **Estimated Effort:** 2 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `monitoring/convergence.py`: Tracks coverage per iteration, detects plateau
  - Early stopping: If coverage increase < 2% for 5 consecutive iterations, stop
  - Visualization: matplotlib chart of coverage over iterations
- **Acceptance Criteria:**
  - Monitor logs coverage metrics per iteration
  - Early stopping triggers correctly (manual test: force plateau)
  - Chart shows coverage curve reaching 70% by iteration 5, 95% by iteration 30

#### Task 2.2.6: Implement Explore-Exploit Orchestrator (Algorithm 2)
- **Estimated Effort:** 5 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `orchestration/explore_exploit.py`: Main loop integrating all components
  - Configurable parameters: iterations, top_k, diversity_threshold, similarity_threshold
  - Output: Selected feature subtree as JSON
- **Acceptance Criteria:**
  - Full pipeline runs for 30 iterations in <5 minutes
  - Output JSON contains 20-50 features with diversity score > 0.3
  - Coverage reaches 95% by iteration 30 (on test ontology)

### Acceptance Criteria (Epic 2.2)

**Functional Tests:**
1. **Exploitation Test**
   - Input spec: "Build a machine learning library"
   - Exploitation phase retrieves: "linear regression", "neural networks", "data preprocessing"
   - Verify: Top-10 results are all ML-related

2. **Exploration Test**
   - After 10 exploitation iterations, all features are "supervised learning"
   - Exploration phase queries "unsupervised learning", "reinforcement learning"
   - Verify: New features from different branches added

3. **Diversity Test**
   - Run algorithm with diversity threshold 0.5
   - Verify: No two selected features have cosine similarity > 0.85
   - Verify: Silhouette score > 0.3

4. **Convergence Test**
   - Run algorithm for 30 iterations
   - Verify: Coverage reaches 70% by iteration 5
   - Verify: Coverage reaches 95% by iteration 30
   - Verify: Early stopping triggers if coverage plateaus

5. **LLM Filtering Test**
   - Input spec: "Backend API for e-commerce"
   - Features include: "database", "REST API", "mobile UI" (irrelevant)
   - LLM prunes "mobile UI", retains others
   - Verify: Output only contains relevant features

**Performance Tests:**
1. Full 30-iteration cycle: <5 minutes (p95)
2. Per-iteration latency: <10s (p95)
3. Vector search per iteration: <100ms (p95)

**Integration Tests:**
1. Run with LLM-generated ontology (Epic 2.1.4)
2. Run with custom domain extension (Epic 2.1.5)
3. Verify: Algorithm works with any ontology backend

**Benchmark Tests (Paper Replication):**
1. Input spec: "Build a data visualization library"
2. Expected features: "charts", "graphs", "plotting", "interactivity", "export"
3. Verify: Coverage curve matches paper's Figure 3 (70% @ iter 5, 95% @ iter 30)

---

## Epic 2.3: Functionality Graph Construction

### Overview
Implement LLM-driven refactoring that partitions selected features into cohesive modules following software engineering principles. The output is a functionality graph with clear functional boundaries and minimal coupling.

### Requirements

#### Functional Requirements

**FR-2.3.1: Module Partitioning**
- LLM analyzes selected features and groups them into modules based on:
  - Functional cohesion (features serving similar purposes)
  - Data coupling (features sharing data structures)
  - Workflow dependencies (features called in sequence)
- Example: "metrics" module contains silhouette_score, davies_bouldin_index, calinski_harabasz_score
- Configurable: Target 3-10 modules per graph

**FR-2.3.2: Module Boundary Definition**
- Each module has:
  - Name (e.g., "Evaluation", "Preprocessing", "Modeling")
  - Description (functional purpose)
  - Public interface (exported functions/classes)
  - Internal features (private to module)
- Modules expose minimal public interfaces (information hiding)

**FR-2.3.3: Cohesion and Coupling Optimization**
- Maximize intra-module cohesion (features within module are tightly related)
- Minimize inter-module coupling (modules depend on few external modules)
- Metrics:
  - **Cohesion**: Average pairwise cosine similarity of features within module (target > 0.6)
  - **Coupling**: Number of inter-module dependencies per module (target < 3)
  - **Modularity (Q-score)**: Network modularity metric (target > 0.4)

**FR-2.3.4: Dependency Graph Construction**
- Build directed graph where:
  - Nodes = modules
  - Edges = dependencies (module A uses module B)
  - Edge weights = strength of dependency (number of calls)
- Detect circular dependencies (error condition)
- Output: NetworkX graph with module metadata

**FR-2.3.5: Iterative Refinement**
- User reviews initial partitioning, requests changes
- Example: "Move feature X from module A to module B"
- LLM re-optimizes modules after user edits
- Track refinement history

#### Non-Functional Requirements

**NFR-2.3.1: Graph Visualization**
- Export graph to GraphML, DOT, JSON formats
- Web UI for interactive visualization (D3.js force-directed layout)

**NFR-2.3.2: Explainability**
- LLM explains each module boundary decision
- Example: "silhouette_score belongs to Evaluation module because it measures clustering quality, not implements clustering"

**NFR-2.3.3: Scalability**
- Support up to 200 features per graph
- Partition into 3-20 modules

### Tasks

#### Task 2.3.1: Implement Module Partitioning Algorithm
- **Estimated Effort:** 5 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `refactoring/module_partitioner.py`: LLM-driven clustering of features into modules
  - Prompt template: "Features: {features}. Partition into 3-10 cohesive modules. For each module, provide name, description, and member features."
  - Fallback: If LLM fails, use k-means clustering on feature embeddings
- **Acceptance Criteria:**
  - LLM partitions 30 features into 5 modules with cohesion > 0.6
  - Each module has a descriptive name (not "Module 1")
  - No module has < 2 features or > 15 features

#### Task 2.3.2: Implement Cohesion and Coupling Metrics
- **Estimated Effort:** 3 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `metrics/cohesion.py`: Computes average pairwise similarity within modules
  - `metrics/coupling.py`: Counts inter-module dependencies
  - `metrics/modularity.py`: Computes Q-score (Newman's modularity)
- **Acceptance Criteria:**
  - Cohesion metric correctly identifies tight modules (manual validation)
  - Coupling metric counts dependencies (manual test: 3-module graph with 2 dependencies)
  - Modularity Q-score > 0.4 for well-partitioned graphs

#### Task 2.3.3: Implement Dependency Inference
- **Estimated Effort:** 4 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `dependencies/dependency_inference.py`: LLM infers dependencies between modules
  - Prompt template: "Modules: {modules}. For each module, list which other modules it depends on and why."
  - Circular dependency detection: Use NetworkX cycle detection
- **Acceptance Criteria:**
  - LLM correctly infers: "Modeling module depends on Preprocessing module"
  - Circular dependency detection raises error
  - Dependency graph is acyclic (DAG)

#### Task 2.3.4: Implement Functionality Graph Builder
- **Estimated Effort:** 4 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `graph/functionality_graph.py`: Builds NetworkX graph from modules and dependencies
  - Node attributes: `{name, description, features, public_interface}`
  - Edge attributes: `{dependency_type, weight, rationale}`
  - Export methods: `to_json()`, `to_graphml()`, `to_dot()`
- **Acceptance Criteria:**
  - Graph contains 5 modules with 7 dependencies
  - Export to JSON preserves all metadata
  - GraphML import into Gephi for visualization works

#### Task 2.3.5: Implement Iterative Refinement
- **Estimated Effort:** 3 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `refactoring/refinement.py`: Accepts user edits, re-optimizes modules
  - User commands: `move_feature(feature_id, from_module, to_module)`, `merge_modules(module_a, module_b)`, `split_module(module_id)`
  - LLM re-evaluates cohesion after each edit
- **Acceptance Criteria:**
  - User moves feature X from module A to module B
  - Cohesion metrics update correctly
  - LLM suggests: "This decreases cohesion in module A. Consider moving related features."

#### Task 2.3.6: Build Graph Visualization UI
- **Estimated Effort:** 5 days
- **Assigned To:** Frontend Engineer
- **Deliverables:**
  - `ui/graph_viewer.html`: D3.js force-directed graph visualization
  - Interactive: Click module to see features, click edge to see dependency rationale
  - Controls: Zoom, pan, layout adjustment
- **Acceptance Criteria:**
  - Visualizes 10-module graph with readable labels
  - Click module "Evaluation" → shows features: silhouette_score, davies_bouldin_index
  - Click edge "Modeling → Preprocessing" → shows rationale: "Modeling requires cleaned data"

### Acceptance Criteria (Epic 2.3)

**Functional Tests:**
1. **Module Partitioning Test**
   - Input: 30 ML features (linear_regression, kmeans, silhouette_score, etc.)
   - Output: 5 modules (Regression, Clustering, Evaluation, Preprocessing, Utilities)
   - Verify: silhouette_score in Evaluation, NOT in Clustering
   - Verify: Cohesion > 0.6 for all modules

2. **Coupling Test**
   - Partitioned graph has 5 modules
   - Verify: Each module has < 3 inter-module dependencies
   - Verify: No circular dependencies

3. **Dependency Inference Test**
   - Modules: Modeling, Preprocessing, Evaluation
   - LLM infers: Modeling → Preprocessing, Evaluation → Modeling
   - Verify: Dependencies match expected workflow

4. **Refinement Test**
   - User moves feature X from module A to module B
   - Cohesion in A decreases from 0.7 to 0.6
   - LLM suggests: "Consider moving related features to maintain cohesion"

5. **Visualization Test**
   - Load graph with 8 modules into UI
   - Verify: All modules and edges visible
   - Verify: Click interactions work

**Quality Tests:**
1. Modularity Q-score > 0.4 for all generated graphs
2. Average cohesion > 0.6 across modules
3. Average coupling < 3 dependencies per module

**Integration Tests:**
1. Run full pipeline: Epic 2.2 output → Epic 2.3 partitioning → Graph export
2. Verify: Graph contains all features from Epic 2.2
3. Verify: Graph is acyclic

---

## Epic 2.4: User Specification Parser

### Overview
Build a natural language parser that accepts repository descriptions, constraints, and reference materials, then structures them for downstream consumption by the feature planning pipeline.

### Requirements

#### Functional Requirements

**FR-2.4.1: Natural Language Input**
- Accept repository description: 50-5000 words
- Accept optional constraints:
  - Target language(s): Python, JavaScript, Rust, etc.
  - Framework preferences: React, Django, FastAPI, etc.
  - Scope boundaries: Backend-only, frontend-only, full-stack
  - Deployment targets: Cloud, on-premises, edge
- Accept optional reference materials:
  - API documentation (URLs or PDFs)
  - Code samples (GitHub repos, snippets)
  - Research papers (URLs or PDFs)

**FR-2.4.2: Specification Structuring**
- LLM extracts:
  - Core functionality (what the repository does)
  - Technical requirements (languages, frameworks, platforms)
  - Quality attributes (performance, security, scalability)
  - Constraints (must-haves vs. nice-to-haves)
- Output: Structured JSON with schema validation

**FR-2.4.3: Iterative Refinement**
- User reviews parsed specification, provides feedback
- LLM refines based on feedback
- Example: User says "Add real-time collaboration", LLM updates spec to include WebSocket requirements
- Track refinement history

**FR-2.4.4: Reference Material Processing**
- Extract key concepts from API docs, papers, code samples
- Example: Upload scikit-learn docs → Extract features like "cross_validation", "pipeline"
- Augment user spec with extracted concepts

**FR-2.4.5: Validation**
- Detect conflicting requirements (e.g., "backend-only" + "React frontend")
- Detect incomplete specs (e.g., "build an app" with no domain specified)
- Suggest clarifying questions: "What type of application? Web, mobile, desktop?"

#### Non-Functional Requirements

**NFR-2.4.1: Usability**
- CLI interface for quick input
- Web UI for rich editing with live preview

**NFR-2.4.2: Robustness**
- Handle vague specs gracefully (ask clarifying questions)
- Handle overly detailed specs (summarize into key requirements)

**NFR-2.4.3: Performance**
- Parse specification in <30s
- Reference material processing: <2 minutes for 100-page PDF

### Tasks

#### Task 2.4.1: Define Specification Schema
- **Estimated Effort:** 2 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `models/specification.py`: Pydantic models
    - `RepositorySpec(description, core_functionality, technical_requirements, quality_attributes, constraints, references)`
    - `TechnicalRequirement(languages, frameworks, platforms, deployment_targets)`
    - `ReferenceMaterial(type, url, extracted_concepts)`
  - JSON schema for validation
- **Acceptance Criteria:**
  - All models pass schema validation tests
  - Schema supports optional fields (constraints, references)

#### Task 2.4.2: Implement NLP Parser
- **Estimated Effort:** 5 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `parsing/nlp_parser.py`: LLM extracts structured data from natural language
  - Prompt template: "User description: {description}. Extract: core functionality, technical requirements (languages, frameworks), quality attributes (performance, security), constraints (must-haves, nice-to-haves)."
  - Output: JSON matching `RepositorySpec` schema
- **Acceptance Criteria:**
  - Input: "Build a real-time chat app with React and WebSocket"
  - Output: `core_functionality: "real-time messaging"`, `frameworks: ["React"]`, `technical_requirements: ["WebSocket"]`
  - Schema validation passes

#### Task 2.4.3: Implement Reference Material Processor
- **Estimated Effort:** 5 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `parsing/reference_processor.py`: Extracts key concepts from docs/papers/code
  - PDF parser: PyPDF2 or pdfplumber for text extraction
  - Code parser: Tree-sitter for syntax-aware concept extraction
  - LLM summarization: "Key concepts in this document: {text}" → List of concepts
- **Acceptance Criteria:**
  - Upload scikit-learn API docs → Extract "GridSearchCV", "Pipeline", "cross_val_score"
  - Upload React docs → Extract "useState", "useEffect", "Context"
  - Extracted concepts augment user spec

#### Task 2.4.4: Implement Conflict Detector
- **Estimated Effort:** 3 days
- **Assigned To:** ML Engineer
- **Deliverables:**
  - `validation/conflict_detector.py`: LLM checks for conflicting requirements
  - Example conflicts:
    - "Backend-only" + "React frontend"
    - "Python" + "JVM deployment"
    - "Serverless" + "Long-running processes"
  - Severity levels: ERROR (blocking), WARNING (questionable), INFO (suggestion)
- **Acceptance Criteria:**
  - Detect conflict: "Backend-only" + "React frontend" → ERROR
  - Suggest: "Did you mean backend API + separate React app?"
  - No false positives on valid specs

#### Task 2.4.5: Implement Iterative Refinement
- **Estimated Effort:** 3 days
- **Assigned To:** Backend Engineer
- **Deliverables:**
  - `refinement/spec_refiner.py`: Accepts user feedback, updates specification
  - User commands: `add_requirement(text)`, `remove_requirement(id)`, `clarify(question, answer)`
  - LLM re-parses after each edit
- **Acceptance Criteria:**
  - User adds: "Support offline mode"
  - LLM updates spec: `technical_requirements: ["service worker", "IndexedDB"]`
  - Refinement history logged

#### Task 2.4.6: Build CLI and Web UI
- **Estimated Effort:** 5 days
- **Assigned To:** Frontend Engineer
- **Deliverables:**
  - `cli/spec_parser.py`: Command-line interface
    - `parse --input spec.txt --output spec.json`
    - `refine --spec spec.json --add "real-time collaboration"`
  - `ui/spec_editor.html`: Web UI with live preview
    - Input: Textarea for description
    - Output: JSON preview with syntax highlighting
    - Buttons: Parse, Refine, Export
- **Acceptance Criteria:**
  - CLI parses spec.txt and outputs valid spec.json
  - Web UI updates preview in real-time as user types
  - Export downloads spec.json

### Acceptance Criteria (Epic 2.4)

**Functional Tests:**
1. **Parsing Test**
   - Input: "Build a real-time chat application with React, WebSocket, and PostgreSQL. Must support 10K concurrent users."
   - Output JSON contains:
     - `core_functionality: "real-time messaging"`
     - `frameworks: ["React"]`
     - `technical_requirements: ["WebSocket", "PostgreSQL"]`
     - `quality_attributes: {"scalability": "10K concurrent users"}`

2. **Reference Material Test**
   - Upload scikit-learn API docs (100 pages)
   - Extract at least 20 key concepts (GridSearchCV, Pipeline, etc.)
   - Augment spec with extracted concepts

3. **Conflict Detection Test**
   - Input: "Backend-only API with React frontend"
   - Detect conflict, suggest resolution
   - Input: "Python backend with serverless deployment"
   - No conflict detected (valid)

4. **Refinement Test**
   - User adds: "Support offline mode"
   - LLM updates spec to include: service worker, IndexedDB
   - Refinement history logged

5. **Validation Test**
   - Input: "Build an app" (vague)
   - Suggest clarifying questions: "What type of app? What domain?"
   - Input: "Build a web app with React, Vue, and Angular" (overspecified)
   - Suggest: "Choose one frontend framework"

**Performance Tests:**
1. Parse 5000-word spec in <30s
2. Process 100-page PDF in <2 minutes
3. Refinement update in <10s

**Integration Tests:**
1. Run full pipeline: Parse spec → Epic 2.2 explore-exploit → Epic 2.3 graph construction
2. Verify: Graph contains features aligned with spec
3. Verify: No irrelevant features in graph

---

## Success Metrics

### Coverage Metrics (Paper Replication)
- **Epic 2.2**: 70% ontology coverage by iteration 5, 95% by iteration 30
- **Epic 2.3**: Modularity Q-score > 0.4 for all graphs

### Quality Metrics
- **Epic 2.1**: Ontology size ≥ 50K features, depth 4-7 levels
- **Epic 2.2**: Diversity silhouette score > 0.3
- **Epic 2.3**: Average module cohesion > 0.6, coupling < 3 dependencies per module
- **Epic 2.4**: Parser accuracy ≥ 90% on manual test set (20 specs)

### Performance Metrics
- **Epic 2.1**: Vector search latency < 100ms (p95)
- **Epic 2.2**: Full explore-exploit cycle < 5 minutes
- **Epic 2.3**: Graph construction < 2 minutes for 50 features
- **Epic 2.4**: Spec parsing < 30s

### User Experience Metrics
- **Epic 2.4**: User refinement cycles < 3 per spec (on average)
- **Graph Visualization**: UI loads 10-module graph in < 2s

---

## Dependencies

### Inbound Dependencies (Required from Phase 1)
- LLM abstraction layer (`llm/provider.py`)
- Vector store infrastructure (ChromaDB setup)
- Prompt template system (`prompts/templates.py`)
- Configuration management (`config/settings.py`)

### Outbound Dependencies (Enables Phase 3)
- Functionality graph format (NetworkX JSON)
- Module interface specifications
- Feature-to-module mappings

---

## Testing Strategy

### Unit Tests
- Epic 2.1: Test ontology backends in isolation with mock data
- Epic 2.2: Test diversity sampling with synthetic embeddings
- Epic 2.3: Test cohesion/coupling metrics with hand-crafted modules
- Epic 2.4: Test parser with 20 curated specs (simple, complex, vague, conflicting)

### Integration Tests
- Epic 2.1 → 2.2: Ontology search feeds explore-exploit
- Epic 2.2 → 2.3: Selected features feed graph construction
- Epic 2.4 → 2.2: Parsed spec feeds explore-exploit

### End-to-End Tests
1. **ML Library Test**
   - Input spec: "Build a machine learning library with regression, clustering, and evaluation metrics"
   - Expected output: Functionality graph with 3 modules (Regression, Clustering, Evaluation), 20-30 features
   - Verify: No irrelevant features (e.g., "web development")

2. **Web App Test**
   - Input spec: "Build a real-time chat application with user authentication and message persistence"
   - Expected output: Functionality graph with 4 modules (Auth, Messaging, Persistence, Real-time), 15-25 features
   - Verify: All modules connected via dependencies

3. **Domain-Specific Test**
   - Upload medical imaging ontology extension (50 features)
   - Input spec: "Build an MRI analysis tool"
   - Expected output: Graph includes custom features (MRI preprocessing, DICOM parsing)

### Performance Tests
- Load testing: Run explore-exploit with 1M-node ontology
- Stress testing: Parse 10,000-word specification
- Scalability testing: Build graph with 200 features, 20 modules

---

## Risks & Mitigations

### Risk 1: Proprietary Ontology Gap
**Risk:** EpiCoder's 1.5M-node ontology is not available; custom ontology may be smaller/lower quality.
**Impact:** Reduced feature coverage, less accurate grounding.
**Mitigation:**
- Start with 50K-node GitHub/SO ontology (sufficient for common domains)
- Implement LLM-generated ontology as fallback
- Allow domain extension by users
- Monitor coverage metrics; iterate on ontology quality

### Risk 2: LLM Hallucination in Feature Selection
**Risk:** LLM invents non-existent features or misclassifies relevance.
**Impact:** Functionality graph contains irrelevant features.
**Mitigation:**
- Ontology grounding constrains LLM to known features
- Self-check pipeline: LLM re-evaluates its own decisions
- User review step: User can override LLM selections
- Validation tests: Manual review of 20 test cases

### Risk 3: Graph Partitioning Quality
**Risk:** LLM produces modules with low cohesion or high coupling.
**Impact:** Poor repository structure, hard to maintain.
**Mitigation:**
- Implement cohesion/coupling metrics with thresholds
- Iterative refinement: Re-partition if metrics fail
- Fallback to k-means clustering on embeddings
- User override: Manual module editing

### Risk 4: Performance with Large Ontologies
**Risk:** Vector search slows down with 1M+ nodes.
**Impact:** Explore-exploit takes > 10 minutes.
**Mitigation:**
- ChromaDB partitioning for large collections
- Hierarchical search: Search top-level categories first, then drill down
- Caching: Pre-compute common queries
- Early stopping: If coverage plateaus, stop iterations

### Risk 5: User Specification Ambiguity
**Risk:** Vague specs lead to poor feature selection.
**Impact:** Graph missing critical features.
**Mitigation:**
- Conflict detector suggests clarifying questions
- Iterative refinement: User adds missing requirements
- Reference material processing: Augment spec with docs/code
- Default templates: Provide example specs for common domains

---

## Rollout Plan

### Phase 2.1: Foundation (Weeks 1-3)
- Deliver Epic 2.1 (Ontology Service)
- Deliver Epic 2.4 (Spec Parser)
- Internal testing with 5 sample specs

### Phase 2.2: Core Pipeline (Weeks 4-6)
- Deliver Epic 2.2 (Explore-Exploit)
- Integration testing with Epic 2.1 output
- Benchmark against paper's coverage metrics

### Phase 2.3: Refinement (Weeks 7-8)
- Deliver Epic 2.3 (Graph Construction)
- End-to-end testing with 10 real-world specs
- Performance optimization

### Phase 2.4: Production Readiness (Week 9)
- CLI and Web UI deployment
- Documentation and user guides
- Beta testing with 5 external users

---

## Open Questions

1. **Ontology Licensing**: Can we scrape GitHub topics / Stack Overflow tags without legal issues?
   - **Answer needed by:** Week 1
   - **Owner:** Legal team

2. **LLM Cost**: How much will 30-iteration explore-exploit cost per spec?
   - **Answer needed by:** Week 2
   - **Owner:** ML team (benchmark with GPT-4 vs. Claude)

3. **Graph Visualization**: D3.js vs. Cytoscape.js for interactive graphs?
   - **Answer needed by:** Week 5
   - **Owner:** Frontend team

4. **Ontology Update Frequency**: How often to rebuild GitHub/SO ontology?
   - **Answer needed by:** Week 3
   - **Owner:** Backend team (recommend quarterly updates)

---

## Appendix: Algorithms from Paper

### Algorithm 1: Diversity-Aware Rejection Sampling

```
Input: Candidate features C, selected features S, similarity threshold θ
Output: New feature f

1. WHILE attempts < max_attempts:
2.   Sample f ~ C
3.   IF similarity(f, s) < θ for all s in S:
4.     RETURN f
5.   attempts += 1
6. RETURN None  // Failed to find diverse candidate
```

### Algorithm 2: Explore-Exploit Subtree Selection

```
Input: User spec U, ontology O, iterations N
Output: Selected features F

1. F = ∅
2. FOR i = 1 to N:
3.   // Exploitation
4.   keywords = LLM_augment(U)
5.   candidates_exploit = O.search(keywords, top_k=50)
6.
7.   // Exploration
8.   uncovered = O.branches \ visited_branches
9.   IF len(uncovered) > 0:
10.    exploratory_query = LLM_explore(uncovered)
11.    candidates_explore = O.search(exploratory_query, top_k=20)
12.  ELSE:
13.    candidates_explore = ∅
14.
15.  // Diversity sampling
16.  candidates = candidates_exploit ∪ candidates_explore
17.  f = diversity_sample(candidates, F, θ=0.85)
18.  IF f is not None:
19.    F = F ∪ {f}
20.    visited_branches.add(f.branch)
21.
22.  // LLM filtering
23.  IF i % 5 == 0:
24.    F = LLM_filter(F, U)
25.
26.  // Convergence check
27.  IF coverage_plateau(F, window=5):
28.    BREAK
29.
30. RETURN F
```

---

## Changelog

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-02-07 | Initial PRD creation | ZeroRepo Team |

---

**End of PRD-RPG-P2-001**
