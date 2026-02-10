# PRD-RPG-P3-001: Phase 3 - Implementation-Level Construction (RPG Enrichment)

**Version:** 1.0
**Status:** Draft
**Author:** System
**Date:** 2026-02-07
**Project:** ZeroRepo - From Spec to Executable in One Shot

---

## Executive Summary

Phase 3 transforms the functionality graph produced in Phase 2 into a complete **Repository Planning Graph (RPG)** by encoding concrete implementation details. This phase bridges the gap between semantic feature decomposition and executable code structure by adding:

- Folder/file-level structural encoding
- Inter-module and intra-module data flow dependencies
- Base class abstractions for shared patterns
- Adaptive interface design (functions vs classes)
- Validation against existing code structure (via Serena)

The RPG serves as the complete blueprint for Phase 4's code generation, ensuring every feature maps to a specific file, function/class, and dependency context.

---

## Problem Statement

### Current State
After Phase 2, we have:
- ✅ Functionality graph with semantic decomposition (features → subfeatures → leaf nodes)
- ✅ Complexity estimates and dependency relationships
- ✅ Topologically sorted implementation order

### Gaps
- ❌ **No structural mapping**: Features exist in semantic space, not file-system space
- ❌ **No interface specifications**: Unknown if leaf features become functions, methods, or classes
- ❌ **No data flow types**: Dependencies lack typed input-output contracts
- ❌ **No abstraction layer**: Shared patterns not identified or factored out
- ❌ **No validation**: No check against partially-generated skeleton code

### Impact
Without Phase 3, Phase 4 would:
- Generate code with arbitrary file organization
- Duplicate interfaces across similar features
- Miss opportunities for base class abstraction
- Violate dependency order within modules
- Risk divergence from existing partial implementations

---

## Goals and Non-Goals

### Goals
1. **G1**: Encode complete folder/file structure mapping for every feature
2. **G2**: Design typed data flow interfaces between modules
3. **G3**: Identify and encode base class abstractions for shared patterns
4. **G4**: Assign adaptive interfaces (function vs class) based on semantic clustering
5. **G5**: Validate RPG structure against existing code (via Serena MCP)
6. **G6**: Produce serializable RPG ready for Phase 4 code generation

### Non-Goals
- **NG1**: Actual code generation (that's Phase 4)
- **NG2**: Runtime performance optimization of generated code
- **NG3**: UI/UX design for RPG visualization (future enhancement)
- **NG4**: Support for non-Python languages in this phase
- **NG5**: Auto-refactoring of existing code to match RPG

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Structural Coverage** | 100% of leaf nodes have `file_path` | Count nodes with file assignments / total leaf nodes |
| **Interface Coverage** | 100% of leaf nodes have `interface_type` + `signature` | Count nodes with interfaces / total leaf nodes |
| **Data Flow Validity** | 0 cycles in inter-module flow DAG | Topological sort succeeds on flow edges |
| **Abstraction Ratio** | ≥1 base class per 5 similar leaf features | Count base classes / count leaf nodes with shared patterns |
| **Serena Validation** | ≥95% match between RPG and existing symbols (if any) | Compare `get_symbols_overview` to RPG file structure |
| **Serialization Fidelity** | 100% round-trip success (RPG → JSON → RPG) | Graph equality after serialize → deserialize |

---

## User Stories

### US-3.1: Folder Structure Encoding
**As a** Phase 4 code generator
**I want** every functional subgraph mapped to a directory namespace
**So that** I can generate files in semantically coherent folders

**Acceptance Criteria:**
- Root nodes (modules) have `folder_path` attribute (e.g., `algorithms/`, `evaluation/`)
- Descendant features inherit parent folder namespace
- No folder has >15 files (trigger submodule split if exceeded)
- Folder names follow Python package conventions (lowercase, underscores)

---

### US-3.2: File Assignment
**As a** Phase 4 code generator
**I want** related leaf features grouped into the same file
**So that** I minimize cross-file imports and maximize cohesion

**Acceptance Criteria:**
- Each leaf node has `file_path` (e.g., `algorithms/linear_models.py`)
- Features with shared data dependencies prefer same file
- File size estimate (LOC) stays within 200-500 lines per file
- File names are descriptive of contained functionality

---

### US-3.3: Inter-Module Data Flow
**As a** dependency analyzer
**I want** typed input-output contracts between modules
**So that** I can validate data flow correctness before code generation

**Acceptance Criteria:**
- Data flow edges have `input_schema` and `output_schema` (type annotations)
- Example: `data_loading` → `preprocessing` edge specifies `np.ndarray[float, (N, M)]`
- Flow DAG has no cycles (validated by topological sort)
- Flows impose hierarchical topological order on modules

---

### US-3.4: Intra-Module Dependency Order
**As a** code generator
**I want** files within a module ordered by dependency
**So that** I can generate them in import-safe sequence

**Acceptance Criteria:**
- Each module node has `file_order: List[str]` attribute
- Example: `['load_data.py', 'preprocess.py', 'feature_engineer.py']`
- Order respects internal import dependencies
- No circular file dependencies within a module

---

### US-3.5: Base Class Abstraction
**As a** architecture designer
**I want** shared patterns extracted into base classes
**So that** I reduce code duplication and enforce interface consistency

**Acceptance Criteria:**
- Pattern detection algorithm identifies ≥3 similar leaf features
- Base class node created with abstract methods
- Example: `BaseEstimator` with `fit(X, y)`, `predict(X)` methods
- Derived features reference base class in `inherits_from` attribute
- Base class lives in `module/base.py` by convention

---

### US-3.6: Adaptive Interface Design
**As a** interface designer
**I want** leaf features clustered into functions or classes based on semantic relatedness
**So that** I balance granularity with cohesion

**Acceptance Criteria:**
- Independent features → standalone functions (e.g., `load_json(path)`)
- Interdependent features → class methods (e.g., `DataLoader.load_json()`, `.load_csv()`)
- Each leaf has `interface_type: 'function' | 'method' | 'class'`
- Each leaf has `signature: str` with type annotations
- Each leaf has `docstring: str` following Google style

---

### US-3.7: Serena Structure Validation
**As a** validation engineer
**I want** RPG compared against existing code symbols
**So that** I detect drift between plan and reality

**Acceptance Criteria:**
- After RPG construction, invoke `serena:get_symbols_overview`
- Compare planned file paths to actual files
- Compare planned interfaces to actual function/class signatures
- Report drift: missing files, extra files, signature mismatches
- Use `serena:find_referencing_symbols` to validate import dependencies

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 3: RPG ENRICHMENT                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  INPUT: Functionality Graph (from Phase 2)                           │
│    ├─ Semantic decomposition tree                                    │
│    ├─ Complexity estimates                                           │
│    └─ Dependency edges                                               │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.1: Folder-Level Encoding                             │   │
│  │  • Map root nodes → directories                              │   │
│  │  • Namespace inheritance down tree                           │   │
│  │  • Output: folder_path attributes                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                         ↓                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.2: File-Level Encoding                               │   │
│  │  • Cluster leaf features by semantic similarity              │   │
│  │  • Assign file_path to each node                             │   │
│  │  • Balance cohesion vs file size                             │   │
│  │  • Output: file_path attributes                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                         ↓                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.3: Inter-Module Data Flow Encoding                   │   │
│  │  • Build typed flow DAG between subgraph roots               │   │
│  │  • Example: data_loading → algorithms (np.ndarray)           │   │
│  │  • Validate acyclic property                                 │   │
│  │  • Output: flow_edges with schemas                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                         ↓                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.4: Intra-Module Ordering                             │   │
│  │  • Topological sort of files within each module              │   │
│  │  • Respect import dependencies                               │   │
│  │  • Output: file_order attribute per module                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                         ↓                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.5: Base Class Abstraction                            │   │
│  │  • Pattern detection across leaf features                    │   │
│  │  • Generate abstract base classes                            │   │
│  │  • Link derived features via inherits_from                   │   │
│  │  • Output: base class nodes + inheritance edges              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                         ↓                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.6: Adaptive Interface Design                         │   │
│  │  • Cluster features: independent → functions                 │   │
│  │  •                   interdependent → class methods          │   │
│  │  • Generate signatures with type annotations                 │   │
│  │  • Output: interface_type, signature, docstring              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                         ↓                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  EPIC 3.7: Serena Structure Validation                       │   │
│  │  • get_symbols_overview → actual code structure              │   │
│  │  • Compare RPG plan vs reality                               │   │
│  │  • Report drift (missing, extra, mismatched)                 │   │
│  │  • Output: validation report                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  OUTPUT: Repository Planning Graph (RPG)                             │
│    ├─ folder_path for all modules                                    │
│    ├─ file_path for all leaves                                       │
│    ├─ Typed data flow DAG                                            │
│    ├─ file_order within modules                                      │
│    ├─ Base class abstractions                                        │
│    ├─ interface_type, signature, docstring for all leaves            │
│    └─ Validation report against existing code                        │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Data Structures

#### Enhanced Graph Node Schema

```python
@dataclass
class RPGNode:
    """Extended node for Repository Planning Graph"""

    # From Phase 2 (functionality graph)
    id: str
    name: str
    description: str
    node_type: Literal['root', 'feature', 'subfeature', 'leaf']
    parent_id: Optional[str]
    children: List[str]
    dependencies: List[str]
    complexity_estimate: int

    # Phase 3 additions: Structural
    folder_path: Optional[str] = None  # e.g., "algorithms/"
    file_path: Optional[str] = None    # e.g., "algorithms/linear_models.py"
    file_order: Optional[List[str]] = None  # For modules only

    # Phase 3 additions: Interface
    interface_type: Optional[Literal['function', 'method', 'class']] = None
    signature: Optional[str] = None  # Type-annotated function/method signature
    docstring: Optional[str] = None  # Google-style docstring

    # Phase 3 additions: Abstraction
    inherits_from: Optional[str] = None  # Base class node ID
    is_abstract: bool = False
    abstract_methods: Optional[List[str]] = None

    # Phase 3 additions: Data flow
    input_schema: Optional[Dict[str, str]] = None   # {'X': 'np.ndarray', 'y': 'np.ndarray'}
    output_schema: Optional[Dict[str, str]] = None  # {'predictions': 'np.ndarray'}
```

#### Data Flow Edge Schema

```python
@dataclass
class DataFlowEdge:
    """Typed data flow between modules"""
    source_module: str  # Module node ID
    target_module: str  # Module node ID
    flow_type: str      # Description of what flows
    input_schema: Dict[str, str]   # Type annotations
    output_schema: Dict[str, str]  # Type annotations
    required: bool = True  # Can target function without this input?
```

---

### Epic Breakdown

---

## Epic 3.1: Folder-Level Encoding

### Objective
Map functional subgraphs (modules) to directory namespaces with consistent inheritance down the tree.

### Implementation Steps

1. **Identify module roots**: Traverse functionality graph, mark nodes with `node_type='feature'` as module roots
2. **Assign folder names**:
   - Use `name.lower().replace(' ', '_')` for folder name
   - Validate Python package name rules (no hyphens, no leading digits)
   - Check for collisions, append `_module` suffix if needed
3. **Propagate namespaces**:
   - Set `folder_path = parent.folder_path + folder_name + '/'` for all descendants
   - Root node gets `folder_path = ''` (project root)
4. **Validate folder size**:
   - If module has >15 estimated files, flag for submodule split
   - Heuristic: count leaf nodes / 3 (assume ~3 features per file)

### Acceptance Criteria
- [ ] Every node with `node_type='feature'` has `folder_path` attribute
- [ ] All descendant nodes inherit parent's folder namespace
- [ ] No folder estimated to have >15 files
- [ ] Folder names pass Python package validation (`str.isidentifier()`)
- [ ] Unit test: Mock graph with 3 levels → verify namespace propagation

### Test Cases

```python
def test_folder_encoding():
    # Given: 3-level graph (root → algorithms → linear_models)
    graph = create_mock_graph()

    # When: Apply folder encoding
    encoder = FolderEncoder()
    enriched = encoder.encode(graph)

    # Then: Check namespace inheritance
    root = enriched.get_node('root')
    assert root.folder_path == ''

    algorithms = enriched.get_node('algorithms')
    assert algorithms.folder_path == 'algorithms/'

    linear_models = enriched.get_node('linear_models')
    assert linear_models.folder_path == 'algorithms/linear_models/'
```

---

## Epic 3.2: File-Level Encoding

### Objective
Assign each leaf feature to a specific Python file, balancing semantic cohesion with file size constraints.

### Implementation Steps

1. **Clustering algorithm**:
   - For each module, collect leaf features
   - Compute pairwise semantic similarity (TF-IDF on descriptions)
   - Use hierarchical clustering (linkage='average', threshold=0.6)
   - Each cluster → one file
2. **File naming**:
   - Cluster centroid feature name → file name
   - Example: features ['load_json', 'load_csv'] → `data_loaders.py`
   - Validate uniqueness within folder
3. **Size estimation**:
   - Sum `complexity_estimate` for features in file
   - If total >500 LOC, split cluster (re-cluster with lower threshold)
4. **Assignment**:
   - Set `file_path = folder_path + file_name` for each leaf
   - Validate no orphan leaves (all must have file assignment)

### Acceptance Criteria
- [ ] Every leaf node has `file_path` attribute
- [ ] No file estimated to exceed 500 LOC
- [ ] File names are descriptive (not generic like `utils.py`)
- [ ] Features in same file share semantic relatedness (similarity >0.5)
- [ ] Unit test: Given 10 leaf features → produces 2-4 files with balanced distribution

### Test Cases

```python
def test_file_assignment():
    # Given: Module with 6 leaf features (3 data loading, 3 preprocessing)
    module = create_module_with_leaves([
        'load_json', 'load_csv', 'load_parquet',  # Cluster 1
        'normalize', 'scale', 'encode_categorical'  # Cluster 2
    ])

    # When: Apply file encoding
    encoder = FileEncoder()
    enriched = encoder.encode(module)

    # Then: Check clustering into 2 files
    file_paths = {node.file_path for node in enriched.get_leaves()}
    assert len(file_paths) == 2
    assert 'loaders.py' in str(file_paths)
    assert 'preprocessing.py' in str(file_paths)
```

---

## Epic 3.3: Inter-Module Data Flow Encoding

### Objective
Build a typed DAG of data flows between modules, imposing hierarchical topological order.

### Implementation Steps

1. **Flow extraction**:
   - For each dependency edge between modules (not leaf features)
   - Infer data type from source feature descriptions
   - Example: "load training data" → likely outputs `np.ndarray`
2. **Schema inference**:
   - Use LLM prompt: "Given feature '{name}' with description '{desc}', what are the input and output types?"
   - Parse response into `{'param': 'type'}` dict
   - Validate types are importable (check against `typing`, `numpy`, etc.)
3. **DAG construction**:
   - Create `DataFlowEdge` for each inter-module dependency
   - Add to graph as special edge type
4. **Cycle detection**:
   - Run topological sort on flow edges
   - If cycle found, flag as error (manual resolution needed)

### Acceptance Criteria
- [ ] Every inter-module dependency has `DataFlowEdge` with schemas
- [ ] Topological sort succeeds (no cycles)
- [ ] Type annotations use valid Python types
- [ ] At least one flow edge for each module pair with direct dependency
- [ ] Functional test: Given Module A (data loading) → Module B (preprocessing), validate typed flow exists

### Test Cases

```python
def test_data_flow_encoding():
    # Given: Two modules with dependency
    graph = create_graph_with_modules(['data_loading', 'preprocessing'])
    graph.add_dependency('preprocessing', 'data_loading')

    # When: Encode data flows
    encoder = DataFlowEncoder()
    enriched = encoder.encode(graph)

    # Then: Check flow edge exists with types
    flow_edge = enriched.get_flow_edge('data_loading', 'preprocessing')
    assert flow_edge is not None
    assert 'np.ndarray' in flow_edge.output_schema.values()

    # And: Topological sort succeeds
    order = enriched.topological_sort()
    assert order.index('data_loading') < order.index('preprocessing')
```

---

## Epic 3.4: Intra-Module Ordering

### Objective
Order files within each module according to internal import dependencies.

### Implementation Steps

1. **Intra-module dependency graph**:
   - For each module, extract leaf features grouped by file
   - Check cross-file dependencies within module
   - Example: `preprocess.py` depends on `load_data.py` (both in `data/`)
2. **File-level topological sort**:
   - Build graph where nodes = files, edges = import dependencies
   - Run topological sort
   - Result: `file_order = ['load_data.py', 'preprocess.py', 'feature_engineer.py']`
3. **Circular dependency detection**:
   - If sort fails, report circular imports
   - Suggest refactoring (extract shared code to `common.py`)
4. **Assignment**:
   - Set `file_order` attribute on module node

### Acceptance Criteria
- [ ] Every module node has `file_order: List[str]` attribute
- [ ] File order respects import dependencies (no forward imports)
- [ ] Topological sort succeeds for all modules
- [ ] Unit test: Module with 3 files in dependency chain → correct order

### Test Cases

```python
def test_intra_module_ordering():
    # Given: Module with 3 files (A depends on B, B depends on C)
    module = create_module_with_files({
        'file_a.py': ['feature_1'],  # depends on file_b
        'file_b.py': ['feature_2'],  # depends on file_c
        'file_c.py': ['feature_3']   # no deps
    })
    module.add_file_dependency('file_a.py', 'file_b.py')
    module.add_file_dependency('file_b.py', 'file_c.py')

    # When: Compute file order
    encoder = IntraModuleOrderEncoder()
    enriched = encoder.encode(module)

    # Then: Check topological order
    assert enriched.file_order == ['file_c.py', 'file_b.py', 'file_a.py']
```

---

## Epic 3.5: Base Class Abstraction

### Objective
Identify shared patterns across leaf features and extract abstract base classes.

### Implementation Steps

1. **Pattern detection**:
   - Group leaf features by similarity (reuse clustering from Epic 3.2)
   - If cluster has ≥3 features with similar signatures, flag for abstraction
   - Example: `LinearRegression`, `RidgeRegression`, `LassoRegression` → `BaseEstimator`
2. **Abstract method inference**:
   - Compare signatures across cluster
   - Extract common methods: `fit(X, y)`, `predict(X)`
   - Create abstract base class node
3. **Base class node creation**:
   - `node_type = 'leaf'` (it generates code)
   - `interface_type = 'class'`
   - `is_abstract = True`
   - `abstract_methods = ['fit', 'predict']`
   - `file_path = module_folder + 'base.py'`
4. **Link derived features**:
   - Set `inherits_from = base_class_node_id` for all cluster members
   - Update their signatures to reference base class

### Acceptance Criteria
- [ ] At least one base class created for every 5 similar leaf features
- [ ] Base class has `is_abstract=True` and `abstract_methods` list
- [ ] Derived features have `inherits_from` pointing to base class
- [ ] Base classes live in `module/base.py` by convention
- [ ] Functional test: Given 5 regression features → produces `BaseEstimator`

### Test Cases

```python
def test_base_class_abstraction():
    # Given: 4 similar regression features
    features = create_features([
        'linear_regression',
        'ridge_regression',
        'lasso_regression',
        'elasticnet_regression'
    ])

    # When: Detect patterns and create base class
    encoder = BaseClassEncoder()
    enriched = encoder.encode(features)

    # Then: Check base class created
    base_class = enriched.get_node('base_estimator')
    assert base_class.is_abstract
    assert 'fit' in base_class.abstract_methods
    assert 'predict' in base_class.abstract_methods

    # And: Derived features reference base
    for feature in features:
        node = enriched.get_node(feature)
        assert node.inherits_from == 'base_estimator'
```

---

## Epic 3.6: Adaptive Interface Design

### Objective
Cluster leaf features into functions or class methods based on semantic relatedness and interdependencies.

### Implementation Steps

1. **Independence analysis**:
   - For each leaf feature, check if it has dependencies on other leaves in same file
   - Independent (no deps) → candidate for standalone function
   - Interdependent (shared deps or data) → candidate for class methods
2. **Class grouping**:
   - Within each file, cluster interdependent features
   - Each cluster → one class
   - Example: `load_json`, `load_csv` share data loading logic → `DataLoader` class
3. **Signature generation**:
   - Use LLM prompt: "Generate Python signature with type hints for: {feature description}"
   - Parse response, validate syntax
   - Example: `def load_json(path: Path) -> pd.DataFrame:`
4. **Docstring generation**:
   - Convert feature description to Google-style docstring
   - Include Args, Returns, Raises sections
5. **Assignment**:
   - Set `interface_type`, `signature`, `docstring` for each leaf

### Acceptance Criteria
- [ ] Every leaf has `interface_type` ('function', 'method', or 'class')
- [ ] Every leaf has `signature` with type annotations
- [ ] Every leaf has Google-style `docstring`
- [ ] Independent features are standalone functions
- [ ] Interdependent features (≥2 in same file) grouped into classes
- [ ] Functional test: Given file with 2 independent + 3 interdependent features → 2 functions + 1 class with 3 methods

### Test Cases

```python
def test_adaptive_interface_design():
    # Given: File with independent and interdependent features
    file_features = {
        'load_json': {'deps': []},              # Independent
        'load_csv': {'deps': ['_parse_csv']},   # Interdependent
        '_parse_csv': {'deps': []},             # Interdependent (private helper)
    }

    # When: Design interfaces
    encoder = InterfaceDesignEncoder()
    enriched = encoder.encode(file_features)

    # Then: Check interface types
    load_json = enriched.get_node('load_json')
    assert load_json.interface_type == 'function'
    assert 'def load_json(path: Path)' in load_json.signature

    load_csv = enriched.get_node('load_csv')
    assert load_csv.interface_type == 'method'
    assert 'class DataLoader' in enriched.get_parent(load_csv).signature
```

---

## Epic 3.7: Serena Structure Validation

### Objective
Compare the planned RPG structure against existing code (if any) to detect drift.

### Implementation Steps

1. **Symbol extraction**:
   - Call `serena:get_symbols_overview` for target project directory
   - Parse response to extract file paths, function/class names, signatures
2. **Planned vs actual comparison**:
   - **Files**: Compare RPG `file_path` set vs Serena file list
     - Missing in code: Report as "TODO" (Phase 4 will generate)
     - Extra in code: Report as "drift" (manual code not in spec)
   - **Interfaces**: For matching files, compare signatures
     - Use `serena:find_referencing_symbols` to check dependencies
3. **Drift report generation**:
   - JSON report with:
     - `missing_files: List[str]`
     - `extra_files: List[str]`
     - `signature_mismatches: List[{file, planned, actual}]`
     - `dependency_violations: List[{expected, actual}]`
4. **Recommendation**:
   - If drift >10% of files, suggest manual reconciliation before Phase 4
   - If drift <10%, proceed with code generation (Phase 4 will overwrite/merge)

### Acceptance Criteria
- [ ] Validation invokes `serena:get_symbols_overview` successfully
- [ ] Report shows file-level comparison (missing, extra)
- [ ] Report shows signature-level comparison for matching files
- [ ] Dependency validation uses `serena:find_referencing_symbols`
- [ ] Final report includes drift percentage and recommendation
- [ ] Functional test: Given RPG + mock Serena response → produces accurate drift report

### Test Cases

```python
def test_serena_validation():
    # Given: RPG with 3 planned files
    rpg = create_rpg_with_files([
        'algorithms/linear_models.py',
        'algorithms/tree_models.py',
        'evaluation/metrics.py'
    ])

    # And: Mock Serena response showing 2 existing files + 1 extra
    mock_serena_response = {
        'files': [
            'algorithms/linear_models.py',  # Match
            'algorithms/deprecated_models.py',  # Extra (not in RPG)
            # Missing: tree_models.py, metrics.py
        ],
        'symbols': {
            'algorithms/linear_models.py': ['LinearRegression', 'RidgeRegression']
        }
    }

    # When: Validate structure
    validator = SerenaValidator(serena_client=mock_serena)
    report = validator.validate(rpg)

    # Then: Check drift report
    assert 'algorithms/tree_models.py' in report['missing_files']
    assert 'evaluation/metrics.py' in report['missing_files']
    assert 'algorithms/deprecated_models.py' in report['extra_files']
    assert report['drift_percentage'] == 33.3  # 1/3 files have drift
    assert report['recommendation'] == 'PROCEED_WITH_CAUTION'
```

---

## Integration Tests

### Test 1: End-to-End RPG Construction

```python
def test_e2e_rpg_construction():
    """
    Given: Complete functionality graph from Phase 2 (mock fixture)
    When: Run all 7 epic encoders in sequence
    Then: Produces valid RPG with all attributes populated
    """
    # Setup
    functionality_graph = load_fixture('phase2_output.json')

    # Execute
    rpg_builder = RPGBuilder([
        FolderEncoder(),
        FileEncoder(),
        DataFlowEncoder(),
        IntraModuleOrderEncoder(),
        BaseClassEncoder(),
        InterfaceDesignEncoder(),
        SerenaValidator()
    ])
    rpg = rpg_builder.build(functionality_graph)

    # Validate
    assert all(node.folder_path for node in rpg.get_modules())
    assert all(node.file_path for node in rpg.get_leaves())
    assert rpg.data_flow_dag.is_acyclic()
    assert all(node.file_order for node in rpg.get_modules())
    assert len(rpg.get_base_classes()) >= 1
    assert all(node.interface_type for node in rpg.get_leaves())
    assert all(node.signature for node in rpg.get_leaves())
    assert rpg.validation_report['drift_percentage'] < 15
```

### Test 2: Serialization Round-Trip

```python
def test_rpg_serialization():
    """
    Given: Constructed RPG
    When: Serialize to JSON and deserialize back
    Then: Graphs are identical (structure + attributes)
    """
    original_rpg = create_complete_rpg()

    # Serialize
    json_str = original_rpg.to_json()

    # Deserialize
    restored_rpg = RPG.from_json(json_str)

    # Compare
    assert original_rpg.nodes == restored_rpg.nodes
    assert original_rpg.edges == restored_rpg.edges
    assert original_rpg.data_flow_edges == restored_rpg.data_flow_edges
```

### Test 3: Topological Sort Success

```python
def test_topological_sort():
    """
    Given: RPG with complex inter-module and intra-module dependencies
    When: Run topological sort on complete graph
    Then: Sort succeeds with valid dependency order
    """
    rpg = create_rpg_with_dependencies()

    # Full graph sort
    full_order = rpg.topological_sort()
    assert len(full_order) == len(rpg.get_all_nodes())

    # Per-module file order
    for module in rpg.get_modules():
        for i, file in enumerate(module.file_order[:-1]):
            next_file = module.file_order[i + 1]
            # Verify next file doesn't import current file (no backward deps)
            deps = rpg.get_file_dependencies(next_file)
            assert file not in deps
```

---

## Implementation Plan

### Phase 3.1: Core Infrastructure (Week 1)
- [ ] Extend `FunctionalityGraph` class to `RPG` with new node attributes
- [ ] Implement `DataFlowEdge` class and integration
- [ ] Create base encoder interface: `RPGEncoder(ABC)`
- [ ] Set up Serena MCP client wrapper
- [ ] Write serialization/deserialization logic

### Phase 3.2: Structural Encoders (Week 2)
- [ ] Implement `FolderEncoder` (Epic 3.1)
- [ ] Implement `FileEncoder` with clustering (Epic 3.2)
- [ ] Write unit tests for folder/file encoding
- [ ] Integration test: Phase 2 output → folder/file augmented graph

### Phase 3.3: Data Flow & Ordering (Week 3)
- [ ] Implement `DataFlowEncoder` with LLM type inference (Epic 3.3)
- [ ] Implement `IntraModuleOrderEncoder` (Epic 3.4)
- [ ] Write topological sort tests (cycle detection)
- [ ] Integration test: Data flow DAG validation

### Phase 3.4: Abstraction & Interface (Week 4)
- [ ] Implement `BaseClassEncoder` with pattern detection (Epic 3.5)
- [ ] Implement `InterfaceDesignEncoder` with signature generation (Epic 3.6)
- [ ] Write LLM prompts for signature/docstring generation
- [ ] Unit tests for abstraction and interface design

### Phase 3.5: Validation & Integration (Week 5)
- [ ] Implement `SerenaValidator` (Epic 3.7)
- [ ] Write Serena integration tests with mock responses
- [ ] End-to-end RPG construction test
- [ ] Performance benchmarking (target: <60s for 100-node graph)
- [ ] Documentation: RPG schema, encoder pipeline, validation rules

---

## Dependencies

### Upstream (Phase 2)
- **Functionality graph** with:
  - Semantic decomposition tree
  - Complexity estimates
  - Dependency edges
  - Topological order
- **Output format**: JSON serialized graph

### Downstream (Phase 4)
- **RPG** consumed by code generator:
  - File structure → directory creation + file generation
  - Interfaces → function/class skeletons
  - Data flows → import statements
  - Base classes → inheritance hierarchies

### External Tools
- **Serena MCP**: Symbol extraction and dependency analysis
- **LLM (Claude)**: Type inference, signature generation, docstring creation
- **Clustering library**: scikit-learn for semantic clustering

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Type inference inaccuracies** | Wrong signatures → compilation errors | Medium | Validate inferred types against `typing` module; fallback to `Any` |
| **Circular dependencies in data flow** | Topological sort fails | Low | Early cycle detection; suggest architectural refactoring |
| **Serena MCP unavailable** | No validation against existing code | Low | Graceful degradation: skip validation, log warning |
| **File clustering too coarse** | 1000-line files, hard to maintain | Medium | Enforce file size limits (500 LOC); re-cluster if exceeded |
| **Base class over-abstraction** | Too many layers, complexity | Low | Require ≥3 similar features for abstraction; manual review flag |
| **Signature generation hallucination** | Invalid Python syntax | Medium | AST parse validation; reject unparseable signatures |

---

## Success Criteria Summary

### Epic-Level Acceptance
- [ ] **Epic 3.1**: All modules have folder paths, namespace inheritance works
- [ ] **Epic 3.2**: All leaves have file paths, no >500 LOC files
- [ ] **Epic 3.3**: Data flow DAG is acyclic with typed schemas
- [ ] **Epic 3.4**: All modules have valid file ordering
- [ ] **Epic 3.5**: ≥1 base class per 5 similar features, inheritance links correct
- [ ] **Epic 3.6**: All leaves have interface_type + signature + docstring
- [ ] **Epic 3.7**: Validation report generated with <15% drift

### Phase-Level Success
- [ ] **100% structural coverage**: Every node has complete structural attributes
- [ ] **100% interface coverage**: Every leaf has complete interface specification
- [ ] **0 cycles**: Both inter-module and intra-module dependency graphs are acyclic
- [ ] **≥95% Serena alignment**: Minimal drift between RPG plan and existing code
- [ ] **Serialization fidelity**: JSON round-trip preserves all graph data
- [ ] **Performance**: <60 seconds to process 100-node graph
- [ ] **Documentation**: Complete RPG schema reference, encoder guide, validation runbook

---

## Appendix A: Example RPG Output

```json
{
  "nodes": [
    {
      "id": "mod_algorithms",
      "name": "algorithms",
      "node_type": "feature",
      "folder_path": "algorithms/",
      "file_order": ["base.py", "linear_models.py", "tree_models.py"],
      "children": ["base_estimator", "linear_regression", "decision_tree"]
    },
    {
      "id": "base_estimator",
      "name": "BaseEstimator",
      "node_type": "leaf",
      "parent_id": "mod_algorithms",
      "folder_path": "algorithms/",
      "file_path": "algorithms/base.py",
      "interface_type": "class",
      "is_abstract": true,
      "abstract_methods": ["fit", "predict"],
      "signature": "class BaseEstimator(ABC):",
      "docstring": "Abstract base class for all estimators.\n\nProvides common interface for model fitting and prediction."
    },
    {
      "id": "linear_regression",
      "name": "LinearRegression",
      "node_type": "leaf",
      "parent_id": "mod_algorithms",
      "folder_path": "algorithms/",
      "file_path": "algorithms/linear_models.py",
      "interface_type": "class",
      "inherits_from": "base_estimator",
      "signature": "class LinearRegression(BaseEstimator):",
      "docstring": "Linear regression using ordinary least squares.\n\nArgs:\n    fit_intercept: Whether to calculate intercept.",
      "input_schema": {"X": "np.ndarray", "y": "np.ndarray"},
      "output_schema": {"predictions": "np.ndarray"}
    }
  ],
  "data_flow_edges": [
    {
      "source_module": "data_loading",
      "target_module": "algorithms",
      "flow_type": "training_data",
      "input_schema": {},
      "output_schema": {"X": "np.ndarray", "y": "np.ndarray"},
      "required": true
    }
  ],
  "validation_report": {
    "missing_files": ["algorithms/tree_models.py"],
    "extra_files": [],
    "signature_mismatches": [],
    "drift_percentage": 5.0,
    "recommendation": "PROCEED"
  }
}
```

---

## Appendix B: Encoder Pipeline Configuration

```python
# rpg_pipeline.py

from encoders import (
    FolderEncoder,
    FileEncoder,
    DataFlowEncoder,
    IntraModuleOrderEncoder,
    BaseClassEncoder,
    InterfaceDesignEncoder,
    SerenaValidator
)

class RPGBuilder:
    """Orchestrates all encoding steps to build complete RPG"""

    def __init__(self, config: Dict[str, Any]):
        self.encoders = [
            FolderEncoder(max_files_per_folder=config.get('max_files', 15)),
            FileEncoder(
                max_loc_per_file=config.get('max_loc', 500),
                similarity_threshold=config.get('similarity', 0.6)
            ),
            DataFlowEncoder(llm_client=config['llm_client']),
            IntraModuleOrderEncoder(),
            BaseClassEncoder(
                min_features_for_abstraction=config.get('min_abstraction', 3)
            ),
            InterfaceDesignEncoder(llm_client=config['llm_client']),
            SerenaValidator(
                serena_client=config.get('serena_client'),
                drift_threshold=config.get('drift_threshold', 0.15)
            )
        ]

    def build(self, functionality_graph: FunctionalityGraph) -> RPG:
        """Run all encoders in sequence"""
        rpg = RPG(functionality_graph)

        for encoder in self.encoders:
            logger.info(f"Running {encoder.__class__.__name__}...")
            rpg = encoder.encode(rpg)
            encoder.validate(rpg)  # Self-check after encoding

        return rpg
```

---

## Appendix C: LLM Prompts

### Type Inference Prompt

```
Given the following software feature description, infer the Python type annotations for its inputs and outputs.

Feature Name: {feature_name}
Description: {feature_description}

Respond ONLY with valid JSON in this format:
{
  "input_schema": {"param1": "type1", "param2": "type2"},
  "output_schema": {"return_name": "return_type"}
}

Use standard Python types (str, int, float, bool, List, Dict, Optional, etc.) and common library types (np.ndarray, pd.DataFrame, Path).

Example:
Feature: "Load training data from CSV file"
Response: {"input_schema": {"file_path": "Path"}, "output_schema": {"data": "pd.DataFrame"}}
```

### Signature Generation Prompt

```
Generate a Python function signature with type hints for the following feature.

Feature Name: {feature_name}
Description: {feature_description}
Interface Type: {interface_type}  # 'function' or 'method'
{inherits_from}  # If applicable: "Inherits from: BaseEstimator"

Requirements:
1. Use PEP 484 type hints for all parameters and return type
2. Follow PEP 8 naming conventions
3. If interface_type='method', use 'self' as first parameter
4. If inherits_from is set, include appropriate parent class

Respond ONLY with the signature line (no body, no docstring).

Example:
Feature: "Fit linear regression model"
Interface Type: method
Inherits from: BaseEstimator
Response: def fit(self, X: np.ndarray, y: np.ndarray) -> 'LinearRegression':
```

---

**END OF PRD-RPG-P3-001**
