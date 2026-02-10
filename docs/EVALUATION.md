# ZeroRepo Evaluation Framework

## Overview

The `evaluation` package (`src/zerorepo/evaluation/`) implements a comprehensive
benchmarking and evaluation pipeline for measuring the quality of generated
repositories against the **RepoCraft** benchmark suite. It uses a three-stage
evaluation pipeline with function localization, semantic validation via LLM
majority voting, and Docker sandbox test execution.

```
evaluation/
├── __init__.py                 # Package exports
├── models.py                   # Pydantic data models (22 classes)
├── pipeline.py                 # 3-stage EvaluationPipeline
├── benchmark_runner.py         # End-to-end benchmark orchestrator
├── localization.py             # Stage 1: Embedding-based function matching
├── semantic_validation.py      # Stage 2: LLM majority voting
├── execution_testing.py        # Stage 3: Docker sandbox test execution
├── metrics.py                  # MetricsCalculator (paper metrics)
├── categorizer.py              # Taxonomy construction + stratified sampling
├── report.py                   # ReportGenerator (Markdown + JSON)
├── failure_analysis.py         # FailureAnalyzer + PromptABTest
├── profiling.py                # ProfilingCollector (token/timing tracking)
├── test_filter.py              # TestFilter (quality control)
└── caching.py                  # EmbeddingCache + LLMResponseCache + batching
```

---

## Three-Stage Evaluation Pipeline

The core evaluation pipeline processes each benchmark task through three
successive stages. A task that fails at any stage is marked with the
corresponding `StageFailed` value and does not proceed.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EvaluationPipeline                               │
│                                                                     │
│  BenchmarkTask ──┐                                                  │
│                  │                                                   │
│                  ▼                                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 1: LOCALIZATION (FunctionLocalizer)                     │ │
│  │                                                                │ │
│  │  1. Extract all FunctionSignature objects from repo via AST    │ │
│  │  2. Embed task description + candidate names using             │ │
│  │     sentence-transformers (all-MiniLM-L6-v2)                   │ │
│  │  3. Compute cosine similarity                                  │ │
│  │  4. Return top-k candidates ranked by score                    │ │
│  │                                                                │ │
│  │  Failure: StageFailed.LOCALIZATION (no candidates found)       │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │ Top candidates                        │
│                             ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 2: SEMANTIC VALIDATION (SemanticValidator)              │ │
│  │                                                                │ │
│  │  For each candidate (up to validation_candidates=3):           │ │
│  │    Round 1: num_voters (default 3) LLM votes                  │ │
│  │      → Clear majority? → Return immediately                   │ │
│  │    Round 2: num_voters more votes (if no clear majority)       │ │
│  │      → Combined majority vote                                  │ │
│  │                                                                │ │
│  │  Vote outcomes: YES / NO / PARTIAL                             │ │
│  │  Confidence: high (R1 majority) / medium (R2 majority) / low  │ │
│  │                                                                │ │
│  │  Failure: StageFailed.VALIDATION (no candidate passes)         │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │ Validated function                    │
│                             ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 3: EXECUTION TESTING (ExecutionTester)                  │ │
│  │                                                                │ │
│  │  1. Adapt ground-truth test (rewrite imports)                  │ │
│  │  2. Copy generated repo into temp workspace                    │ │
│  │  3. Start Docker container via SandboxProtocol                 │ │
│  │  4. Install dependencies (pytest, numpy, ...)                  │ │
│  │  5. Execute adapted test                                       │ │
│  │  6. Parse "TEST_PASSED" / "TEST_FAILED" from stdout            │ │
│  │                                                                │ │
│  │  Failure: StageFailed.EXECUTION (test fails or errors)         │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │                                       │
│                             ▼                                       │
│                        TaskResult                                   │
│  (localized=True, validated=True, passed=True/False)                │
└─────────────────────────────────────────────────────────────────────┘
```

### Pipeline Usage

```python
from zerorepo.evaluation import (
    EvaluationPipeline,
    FunctionLocalizer,
    SemanticValidator,
    ExecutionTester,
)

# Create components
localizer = FunctionLocalizer(model_name="all-MiniLM-L6-v2")
validator = SemanticValidator(llm_client=gateway, model="gpt-4o-mini", num_voters=3)
tester = ExecutionTester(timeout=30)

# Build pipeline
pipeline = EvaluationPipeline(
    localizer=localizer,
    validator=validator,
    tester=tester,
    top_k=5,                   # Stage 1: top 5 candidates
    validation_candidates=3,    # Stage 2: try top 3
)

# Evaluate a single task
result = pipeline.evaluate_task(task, repo_path="/path/to/generated/repo")
print(f"Passed: {result.passed}, Stage failed: {result.stage_failed}")

# Evaluate all tasks for a repository
repo_result = pipeline.evaluate_repository(tasks, repo_path="/path/to/repo")
print(f"Pass rate: {repo_result.pass_rate:.1%}")
print(f"Coverage: {repo_result.coverage:.1%}")
```

---

## Stage 1: Function Localization

### FunctionLocalizer (`localization.py`)

Finds candidate functions in the generated repository that may implement the
benchmark task requirements.

**How it works:**

```
BenchmarkTask.description ─┐
BenchmarkTask.category ────┤──▶ Embed ──▶ task_embedding (384-dim)
BenchmarkTask.subcategory ─┘

For each .py file in repo (excluding tests):
    AST parse ──▶ Extract FunctionDef / ClassDef.methods
                   ──▶ FunctionSignature(name, module, signature, docstring, body)
                        ──▶ Embed ──▶ func_embedding (384-dim)

Cosine similarity(task_embedding, func_embeddings)
    ──▶ Sort descending ──▶ Return top-k (function, score) pairs
```

**Key methods:**

| Method              | Description                                    |
|---------------------|------------------------------------------------|
| `extract_functions()` | AST-parse all Python files into `FunctionSignature` objects |
| `localize()`        | Embed task + candidates, return top-k by cosine similarity |

**Embedding model:** `all-MiniLM-L6-v2` from `sentence-transformers` (384-dim).
Loaded lazily on first use.

---

## Stage 2: Semantic Validation

### SemanticValidator (`semantic_validation.py`)

Uses multiple LLM calls (majority voting) to validate whether a candidate
function correctly implements the task requirements.

**Two-round voting protocol:**

```
Round 1: 3 votes (default)
   ┌─────────────────────────────────────────────┐
   │  LLM Vote 1: YES  │  LLM Vote 2: YES  │ ... │
   └────────────────────┴───────────────────┴─────┘
   Clear majority (>50%)? ──▶ YES → Return high confidence
                              NO  → Proceed to Round 2

Round 2: 3 more votes
   Combine all 6 votes
   Majority vote ──▶ Return medium/low confidence
```

**Vote outcomes:**
- `YES` -- Function implements all requirements
- `NO` -- Function missing requirements or has incorrect logic
- `PARTIAL` -- Function implements some but not all requirements

**Configuration:**

| Parameter     | Default    | Description                      |
|---------------|------------|----------------------------------|
| `model`       | `gpt-4o-mini` | LLM model for voting          |
| `num_voters`  | `3`        | Votes per round                  |
| `num_rounds`  | `2`        | Maximum voting rounds            |
| `temperature` | `0.7`      | LLM temperature (voting diversity)|

The validator uses the `LLMClient` protocol, compatible with `LLMGateway.complete()`.

---

## Stage 3: Execution Testing

### ExecutionTester (`execution_testing.py`)

Runs ground-truth benchmark tests against the generated code in an isolated
Docker sandbox.

**Execution flow:**

```
1. Adapt ground-truth test
   ├── Rewrite import statements (e.g., sklearn → ml_lib)
   ├── Inject sys.path for workspace
   └── Add test runner harness (prints TEST_PASSED/TEST_FAILED)

2. Prepare workspace
   ├── Copy generated repo to temp directory
   └── Write adapted test file

3. Execute in Docker
   ├── Start container (SandboxProtocol)
   ├── Install dependencies (pytest, numpy, ...)
   ├── Run adapted test
   └── Parse stdout for "TEST_PASSED"

4. Return ExecutionResult
   ├── passed: bool
   ├── exit_code: int
   ├── stdout / stderr: str
   ├── error: str?
   └── duration_ms: float
```

**Import adaptation:** The test adapter rewrites import statements to map from
the reference repository's module structure to the generated repository's
structure. For example:

```python
# Original test import:
from sklearn.linear_model import Ridge

# Adapted import (with mapping {"sklearn": "ml_lib"}):
from ml_lib.linear_model import Ridge
```

Uses the `SandboxProtocol` interface, compatible with `DockerSandbox` from the
`sandbox` package.

---

## Data Models

### Task and Result Hierarchy

```
BenchmarkTask
│  id, project, category, subcategory
│  description, test_code, imports, fixtures
│  auxiliary_code, loc, difficulty
│
├──▶ TaskResult (per-task)
│    │  task_id, localized, validated, passed
│    │  stage_failed, candidate_function, candidate_score
│    │  validation_result?, execution_result?, execution_error?
│    │
│    ├── ValidationResult
│    │   │  passed, confidence, candidate_function
│    │   └── votes: list[Vote]
│    │       └── Vote(result, justification, model, round_num)
│    │
│    └── ExecutionResult
│        └── passed, exit_code, stdout, stderr, error, duration_ms
│
├──▶ RepositoryResult (per-repository)
│    │  project_name, total_tasks
│    │  localized, validated, passed, coverage, novelty
│    │  task_results: list[TaskResult]
│    │
│    │  Properties: pass_rate, voting_rate, localization_rate
│    │
│    └──▶ BenchmarkResult (per-project run)
│         │  project, paraphrased_name
│         │  evaluation: RepositoryResult
│         │  profiling: ProfilingData
│         │  repo_path, timestamp
│         │
│         └──▶ RunSummary (aggregate)
│              └── total_projects, total_tasks, total_passed
│                  overall_pass_rate, per_project, duration_s
```

### Enumerations

| Enum              | Values                                        |
|-------------------|-----------------------------------------------|
| `DifficultyLevel` | `easy`, `medium`, `hard`                      |
| `VoteResult`      | `YES`, `NO`, `PARTIAL`                        |
| `StageFailed`     | `localization`, `validation`, `execution`     |
| `FailureCategory` | `planning`, `generation`, `localization`, `validation`, `execution`, `unknown` |

### Statistics Models

| Model          | Fields                                              |
|----------------|-----------------------------------------------------|
| `CodeStats`    | files, loc, estimated_tokens                        |
| `TokenStats`   | prompt_tokens, completion_tokens, total_calls       |
| `ProfilingData`| stage_tokens, stage_timings, total_duration_s       |

### Taxonomy Models

| Model          | Description                                         |
|----------------|-----------------------------------------------------|
| `TaxonomyNode` | name, count, children (recursive dict)              |
| `Taxonomy`     | roots (dict of TaxonomyNode), total_tasks, total_categories |

---

## Benchmark Runner

### BenchmarkRunner (`benchmark_runner.py`)

End-to-end orchestrator for running evaluations across one or multiple projects.

```
┌──────────────────────────────────────────────────────────┐
│  BenchmarkRunner                                         │
│                                                          │
│  run_project(name, tasks, repo_path)                     │
│    ├── pipeline.evaluate_repository(tasks, repo_path)    │
│    ├── metrics.calculate_code_stats(repo_path)           │
│    ├── Collect profiling data                            │
│    └── Return BenchmarkResult                            │
│                                                          │
│  run_batch(projects: list[ProjectConfig])                │
│    ├── For each project: run_project(...)                │
│    ├── Aggregate: total_tasks, total_passed, pass_rate   │
│    └── Return RunSummary                                 │
│                                                          │
│  save_result(result) ──▶ {project}-benchmark-result.json │
│  save_summary(summary) ──▶ benchmark-summary.json        │
│  save_results(summary) ──▶ All files                     │
└──────────────────────────────────────────────────────────┘
```

**Usage:**

```python
from zerorepo.evaluation.benchmark_runner import (
    BenchmarkRunner,
    ProjectConfig,
    RunnerConfig,
)

runner = BenchmarkRunner(
    evaluation_pipeline=pipeline,
    metrics_calculator=MetricsCalculator(),
    config=RunnerConfig(
        output_dir="./benchmark-results",
        save_individual=True,
        save_aggregate=True,
    ),
)

# Single project
result = runner.run_project("scikit-learn", tasks, "/path/to/repo")

# Multi-project batch
summary = runner.run_batch([
    ProjectConfig(project_name="scikit-learn", tasks=sklearn_tasks, repo_path="..."),
    ProjectConfig(project_name="flask", tasks=flask_tasks, repo_path="..."),
])

# Save results
runner.save_results(summary)
```

---

## Metrics

### MetricsCalculator (`metrics.py`)

Computes evaluation metrics matching the ZeroRepo paper:

| Metric                | Formula                                     | Paper Target |
|-----------------------|---------------------------------------------|--------------|
| **Functionality Coverage** | Categories with >= 1 passed test / total categories | 81.5%     |
| **Pass Rate**         | Tests passed / total tests                  | 69.7%        |
| **Voting Rate**       | Tests validated (majority YES) / total tests | 75.0%       |
| **Functionality Novelty** | Categories outside reference taxonomy / total generated | N/A |
| **Code Stats**        | LOC, file count, estimated tokens (~4 chars/token) | N/A    |

```python
from zerorepo.evaluation.metrics import MetricsCalculator

metrics = MetricsCalculator()

coverage = metrics.calculate_coverage(tasks, results)
novelty = metrics.calculate_novelty(tasks, generated_categories)
pass_rate = metrics.calculate_pass_rate(results)
voting_rate = metrics.calculate_voting_rate(results)
code_stats = metrics.calculate_code_stats("/path/to/repo")
```

---

## Report Generation

### ReportGenerator (`report.py`)

Generates evaluation reports in Markdown and JSON formats:

**Markdown report includes:**
- Summary statistics (projects evaluated, total tasks, pass rate)
- Metrics comparison table (Ours vs Paper targets with delta)
- Per-project results table
- Token usage breakdown (if profiling data available)

**Paper reference metrics (built-in defaults):**
```python
PAPER_METRICS = {
    "coverage": 0.815,
    "pass_rate": 0.697,
    "voting_rate": 0.750,
}
```

```python
from zerorepo.evaluation.report import ReportGenerator

reporter = ReportGenerator()

# Markdown comparison report
markdown = reporter.generate_comparison_report(results, "report.md")

# JSON report for programmatic consumption
json_report = reporter.generate_json_report(results, "report.json")
```

---

## Failure Analysis

### FailureAnalyzer (`failure_analysis.py`)

Categorizes evaluation failures and generates actionable recommendations:

```
Failed TaskResult
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  Categorization Logic                                 │
│                                                       │
│  Has stage_failed?                                    │
│    LOCALIZATION → FailureCategory.LOCALIZATION        │
│    VALIDATION   → FailureCategory.VALIDATION          │
│    EXECUTION    → FailureCategory.EXECUTION           │
│                                                       │
│  Not localized?                                       │
│    Score > 0.3 → LOCALIZATION (function exists)       │
│    Otherwise   → GENERATION (function missing)        │
│                                                       │
│  Not validated? → VALIDATION                          │
│  Execution error contains "import"? → EXECUTION       │
│  Otherwise → UNKNOWN                                  │
└──────────────────────────────────────────────────────┘
```

**Recommendation rules (threshold-based):**

| Category     | Threshold | Recommendation                                    |
|--------------|-----------|---------------------------------------------------|
| PLANNING     | > 20%     | Improve task descriptions and planning prompts    |
| GENERATION   | > 15%     | Review code generation templates                  |
| LOCALIZATION | > 25%     | Improve embedding model or add re-ranking         |
| VALIDATION   | > 20%     | Tune validation prompts or voting threshold       |
| EXECUTION    | > 15%     | Fix import mapping or sandbox configuration       |

```python
from zerorepo.evaluation.failure_analysis import FailureAnalyzer

analyzer = FailureAnalyzer(max_samples_per_category=10)
report = analyzer.analyze_failures(results, tasks)

print(f"Total failures: {report.total_failures}")
for category, count in report.category_counts.items():
    print(f"  {category}: {count}")
for rec in report.recommendations:
    print(f"  - {rec}")
```

### PromptABTest (`failure_analysis.py`)

Framework for A/B testing prompt variants with statistical significance:

```python
from zerorepo.evaluation.failure_analysis import PromptABTest

ab_test = PromptABTest(
    baseline_prompt="Generate a Python function...",
    variant_prompt="You are an expert Python developer. Generate...",
)

result = ab_test.run_test(
    baseline_results=[True, False, True, True, ...],
    variant_results=[True, True, True, False, ...],
)

print(f"Baseline: {result.baseline_pass_rate:.1%}")
print(f"Variant: {result.variant_pass_rate:.1%}")
print(f"p-value: {result.p_value:.3f}")
print(f"Recommendation: {result.recommendation}")
# → "USE VARIANT" / "KEEP BASELINE" / "NO SIGNIFICANT DIFFERENCE"
```

Uses a Z-test for two proportions with approximate p-value computation.

---

## Task Categorization

### Categorizer (`categorizer.py`)

Builds hierarchical taxonomies and performs stratified sampling:

**Taxonomy construction:**
```python
from zerorepo.evaluation.categorizer import Categorizer

categorizer = Categorizer()
taxonomy = categorizer.build_taxonomy(tasks)

# Example: tasks with category "sklearn.linear_model.ridge"
# Produces tree: sklearn → linear_model → ridge (with counts)

print(f"Total tasks: {taxonomy.total_tasks}")
print(f"Total categories: {taxonomy.total_categories}")
```

**Stratified sampling:**
```python
# Draw 50 tasks proportionally across categories
# Guarantees at least 1 task per category (when possible)
sample = categorizer.stratified_sample(tasks, n=50, seed=42)
```

Algorithm:
1. If `n < num_categories`: select `n` random categories, one task each
2. Otherwise: one guaranteed task per category, distribute remaining
   slots proportionally via weighted random sampling without replacement

---

## Test Filtering

### TestFilter (`test_filter.py`)

Quality control for benchmark tasks -- removes trivial, flaky, and skipped tests:

```
All Benchmark Tasks
       │
       ▼
┌──────────────────────────────────────────────┐
│  TestFilter Pipeline                          │
│                                               │
│  1. Trivial filter (LOC < min_loc=10)         │
│  2. Assertion filter (no assert/assertEqual)  │
│  3. Flaky filter (requests, socket, sleep...) │
│  4. Skip filter (@skip, @xfail, @skipIf)      │
│                                               │
│  Each filter independently configurable       │
└──────────────────────────────────────────────┘
       │
       ▼
Filtered Tasks (quality-assured)
```

**Flaky patterns detected:**
- `requests.get`, `requests.post`, `urllib.request`
- `socket.`, `time.sleep`, `open(`, `tempfile.`
- `subprocess.`, `os.system`

```python
from zerorepo.evaluation.test_filter import TestFilter

tf = TestFilter(
    min_loc=10,
    require_assertions=True,
    filter_flaky=True,
    filter_skipped=True,
)

filtered = tf.filter_tasks(all_tasks)
# Logs: "Filtered 250 -> 180 tasks. Removed: {'trivial': 30, ...}"
```

---

## Caching

### EmbeddingCache (`caching.py`)

Deterministic cache for embedding vectors, keyed by MD5 of input text:

```python
from zerorepo.evaluation.caching import EmbeddingCache

cache = EmbeddingCache(cache_dir=".cache/embeddings")

# Lookup
embedding = cache.get("function signature text")
if embedding is None:
    embedding = model.encode(["function signature text"])[0]
    cache.put("function signature text", embedding)

print(cache.stats)
# {"hits": 42, "misses": 8, "hit_rate": 0.84, "cache_files": 50}
```

Storage: pickle files in `.cache/embeddings/`, named by MD5 hash.

### LLMResponseCache (`caching.py`)

Cache for LLM responses, keyed by model + prompt hash:

```python
from zerorepo.evaluation.caching import LLMResponseCache

cache = LLMResponseCache(cache_dir=".cache/llm_responses")

response = cache.get("gpt-4o-mini", prompt_text)
if response is None:
    response = gateway.complete(messages=[...], model="gpt-4o-mini")
    cache.put("gpt-4o-mini", prompt_text, response)
```

Storage: text files in `.cache/llm_responses/`, named by MD5 hash.

### BatchedFunctionGenerator (`caching.py`)

Optimizes LLM token usage by generating multiple functions per request:

```python
from zerorepo.evaluation.caching import BatchedFunctionGenerator

batcher = BatchedFunctionGenerator(max_batch_size=5, separator="---FUNCTION---")

# Create batches
batches = batcher.create_batches(requirements)

for batch in batches:
    prompt = batcher.create_batch_prompt(batch)
    response = gateway.complete(messages=[{"role": "user", "content": prompt}])
    functions = batcher.parse_batch_response(response)
```

---

## Profiling

### ProfilingCollector (`profiling.py`)

Instruments pipeline stages for token usage and wall-clock timing:

```python
from zerorepo.evaluation.profiling import ProfilingCollector

profiler = ProfilingCollector()

# Context manager for timing
with profiler.time_stage("localization"):
    candidates = localizer.localize(task, repo_path)

# Manual timer
profiler.start_timer("validation")
result = validator.validate_function(task, candidate)
elapsed = profiler.stop_timer("validation")

# Record LLM call tokens
profiler.record_llm_call("validation", prompt_tokens=500, completion_tokens=50)

# Get results
data = profiler.get_profiling_data()
print(f"Total tokens: {data.total_tokens}")
print(f"Estimated cost: ${data.total_cost_usd:.2f}")
print(f"Total duration: {data.total_duration_s:.1f}s")

summary = profiler.get_stage_summary("validation")
# {"stage": "validation", "prompt_tokens": 500, "total_calls": 1, ...}
```

Cost estimation uses a rough $10 per million tokens rate.

---

## Complete Evaluation Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  1. PREPARE: Load benchmark tasks                                   │
│     BenchmarkTask(id, project, category, description, test_code)    │
│                                                                     │
│  2. FILTER: Quality control                                         │
│     TestFilter.filter_tasks(tasks) → filtered_tasks                 │
│                                                                     │
│  3. SAMPLE (optional): Stratified selection                         │
│     Categorizer.stratified_sample(filtered_tasks, n=100)            │
│                                                                     │
│  4. EVALUATE: 3-stage pipeline                                      │
│     EvaluationPipeline.evaluate_repository(tasks, repo_path)        │
│       Stage 1: FunctionLocalizer.localize()                         │
│       Stage 2: SemanticValidator.validate_function()                │
│       Stage 3: ExecutionTester.execute_test()                       │
│                                                                     │
│  5. MEASURE: Compute metrics                                        │
│     MetricsCalculator.calculate_coverage()                          │
│     MetricsCalculator.calculate_pass_rate()                         │
│     MetricsCalculator.calculate_voting_rate()                       │
│                                                                     │
│  6. ANALYZE: Failure patterns                                       │
│     FailureAnalyzer.analyze_failures() → FailureReport              │
│                                                                     │
│  7. REPORT: Generate outputs                                        │
│     ReportGenerator.generate_comparison_report()                    │
│     BenchmarkRunner.save_results() → JSON files                     │
│                                                                     │
│  8. OPTIMIZE (optional): A/B test prompt variants                   │
│     PromptABTest.run_test() → ABTestResult                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Protocol-Based Extension Points

The evaluation framework uses Python `Protocol` classes for pluggable components:

| Protocol                   | Method                   | Used By               |
|----------------------------|--------------------------|-----------------------|
| `LLMClient`               | `complete(messages, model)` | `SemanticValidator` |
| `SandboxProtocol`          | `start()`, `run_code()`, `stop()` | `ExecutionTester` |
| `EvaluationPipelineProtocol` | `evaluate_repository()` | `BenchmarkRunner`  |
| `MetricsCalculatorProtocol` | `calculate_code_stats()`, `calculate_coverage()` | `BenchmarkRunner` |

To provide a custom implementation, implement the protocol and pass it to the
corresponding consumer class.

---

## ABTestResult Model

The `ABTestResult` model captures prompt comparison results:

| Field               | Type    | Description                              |
|---------------------|---------|------------------------------------------|
| `baseline_pass_rate`| `float` | Pass rate using baseline prompt           |
| `variant_pass_rate` | `float` | Pass rate using variant prompt            |
| `delta`             | `float` | Difference (variant - baseline)           |
| `p_value`           | `float` | Statistical p-value                       |
| `significant`       | `bool`  | Whether p < 0.05                         |
| `sample_size`       | `int`   | Total tasks (both groups)                |
| `recommendation`    | `str`   | `USE VARIANT` / `KEEP BASELINE` / `NO SIGNIFICANT DIFFERENCE` |

---

## Output Formats

### Benchmark Result JSON

```json
{
  "project": "scikit-learn",
  "paraphrased_name": "ml_lib",
  "evaluation": {
    "project_name": "scikit-learn",
    "total_tasks": 50,
    "localized": 45,
    "validated": 38,
    "passed": 35,
    "coverage": 0.82,
    "task_results": [...]
  },
  "profiling": {
    "stage_tokens": {"validation": {"prompt_tokens": 15000, ...}},
    "stage_timings": {"evaluation": 120.5},
    "total_duration_s": 120.5
  },
  "repo_path": "/path/to/generated/repo",
  "timestamp": "2026-02-07T12:00:00"
}
```

### Benchmark Summary JSON

```json
{
  "total_projects": 3,
  "total_tasks": 150,
  "total_passed": 105,
  "overall_pass_rate": 0.70,
  "duration_s": 360.2,
  "timestamp": "2026-02-07T12:06:00",
  "projects": {
    "scikit-learn": {"pass_rate": 0.70, "passed": 35, "total_tasks": 50},
    "flask": {"pass_rate": 0.72, "passed": 36, "total_tasks": 50},
    "requests": {"pass_rate": 0.68, "passed": 34, "total_tasks": 50}
  }
}
```

### Markdown Report

```markdown
# ZeroRepo Benchmark Evaluation Report

## Metrics vs Paper
| Metric        | Ours  | Paper | Delta  |
|---------------|-------|-------|--------|
| Coverage      | 82.0% | 81.5% | +0.5%  |
| Pass Rate     | 70.0% | 69.7% | +0.3%  |
| Voting Rate   | 76.0% | 75.0% | +1.0%  |
```

---

## Benchmark Construction Pipeline

### BenchmarkPipeline (`scripts/benchmark/build_repocraft.py`)

The `BenchmarkPipeline` constructs RepoCraft benchmark tasks from a Python
repository through a 4-step pipeline:

```
Repository source code
       │
       ▼
┌──────────────────────────────────────────────┐
│  Step 1: HARVEST (TestHarvester)             │
│  AST-parse test_*.py files                   │
│  Extract test functions → BenchmarkTask      │
├──────────────────────────────────────────────┤
│  Step 2: FILTER (TestFilter)                 │
│  Remove trivial, flaky, skipped tests        │
├──────────────────────────────────────────────┤
│  Step 3: CATEGORIZE (Categorizer)            │
│  Build hierarchical taxonomy from categories │
├──────────────────────────────────────────────┤
│  Step 4: SAMPLE (Categorizer)                │
│  Stratified sampling for balanced subset     │
└──────────────────────────────────────────────┘
       │
       ▼
  {project}-tasks.json
```

**Configuration (`PipelineConfig`):**

| Field               | Default | Description                                   |
|---------------------|---------|-----------------------------------------------|
| `project_name`      | `""`    | Human-readable project name                   |
| `sample_size`       | `200`   | Target tasks after sampling (0 = keep all)    |
| `seed`              | `42`    | RNG seed for reproducible sampling            |
| `min_loc`           | `10`    | Minimum LOC for test filtering                |
| `require_assertions`| `True`  | Drop tests without assertions                 |
| `filter_flaky`      | `True`  | Drop tests with external IO patterns          |
| `filter_skipped`    | `True`  | Drop tests with skip decorators               |

**Result (`PipelineResult`):**

| Field             | Description                                 |
|-------------------|---------------------------------------------|
| `project_name`    | Name of the processed project               |
| `harvested_count` | Total test functions extracted               |
| `filtered_count`  | Tasks remaining after quality filtering      |
| `sampled_count`   | Tasks in the final sample                    |
| `tasks`           | Final list of `BenchmarkTask` instances      |
| `taxonomy`        | Hierarchical `Taxonomy` built from the tasks |

**Single project:**
```python
from scripts.benchmark.build_repocraft import BenchmarkPipeline, PipelineConfig

config = PipelineConfig(project_name="scikit-learn", sample_size=200, seed=42)
pipeline = BenchmarkPipeline(config)
result = pipeline.run("/path/to/scikit-learn")

print(f"Harvested: {result.harvested_count}")
print(f"Filtered:  {result.filtered_count}")
print(f"Sampled:   {result.sampled_count}")

output_path = pipeline.save_tasks(result, "./benchmark-tasks")
# Creates: ./benchmark-tasks/scikit-learn-tasks.json
```

**Multiple projects:**
```python
from scripts.benchmark.build_repocraft import run_multiple

results = run_multiple(
    projects={
        "scikit-learn": "/repos/scikit-learn",
        "pandas": "/repos/pandas",
        "sympy": "/repos/sympy",
    },
    output_dir="./benchmark-tasks",
    sample_size=200,
    seed=42,
)
```

---

## Test Harvesting

### TestHarvester (`scripts/benchmark/harvest_tests.py`)

Extracts test functions from Python repositories using AST parsing to produce
`BenchmarkTask` objects.

**Extraction process:**

```
Repository
  └── test_*.py files (recursive glob)
        │
        ▼ ast.parse()
        │
        ├── File-level imports extracted
        │
        └── For each test_* FunctionDef:
              ├── Test code (including decorators)
              ├── Function-local imports
              ├── Docstring → task description (or auto-generated from name)
              ├── LOC count (non-empty, non-comment lines)
              ├── Category from file path:
              │     tests/linear_model/test_ridge.py → linear_model.ridge
              ├── Difficulty estimate:
              │     LOC < 15 → EASY
              │     LOC < 40 → MEDIUM
              │     LOC >= 40 → HARD
              └── Unique task ID:
                    {project}-{category}-{subcategory}-{counter:03d}
```

**Key methods:**

| Method                  | Description                                          |
|-------------------------|------------------------------------------------------|
| `extract_tests(path)`   | Extract all `test_*` functions from repository       |
| `_parse_test_function()`| Parse AST `FunctionDef` into `BenchmarkTask`         |
| `_path_to_category()`   | Convert file path to dotted category string          |
| `_extract_file_imports()`| Collect top-level import statements from module     |
| `_extract_function_imports()` | Collect imports inside a function body          |
| `_has_assertions()`     | Detect `assert`, `self.assertXxx()` in function body |
| `_name_to_description()`| Convert `test_*` name to natural language            |
| `_estimate_difficulty()` | LOC-based difficulty heuristic                      |

**Usage:**
```python
from scripts.benchmark.harvest_tests import TestHarvester

harvester = TestHarvester(project_name="scikit-learn")
tasks = harvester.extract_tests("/path/to/scikit-learn")
print(f"Extracted {len(tasks)} test functions")
```

---

## Full Benchmark Runner Script

### BenchmarkRunner (`scripts/benchmark/run_full_benchmark.py`)

Integrates ZeroRepo generation with evaluation for end-to-end benchmark runs.

**Configuration (`BenchmarkConfig`):**

| Field                   | Default                                   | Description                          |
|-------------------------|-------------------------------------------|--------------------------------------|
| `projects`              | `["scikit-learn", "pandas", "sympy"]`     | Projects to benchmark                |
| `tasks_dir`             | `"benchmarks/repocraft/tasks"`            | Directory containing task JSON files |
| `output_dir`            | `"benchmarks/results"`                    | Directory for result output          |
| `max_tasks_per_project` | `200`                                     | Cap on tasks loaded per project      |
| `paraphrase_names`      | `True`                                    | Use paraphrased project names        |

**Built-in paraphrase mappings:**

| Project        | Paraphrased Name |
|----------------|------------------|
| `scikit-learn` | `ml_lib`         |
| `pandas`       | `data_frames`    |
| `sympy`        | `math_engine`    |
| `statsmodels`  | `stat_toolkit`   |
| `requests`     | `http_client`    |
| `django`       | `web_framework`  |

**Key functions:**

| Function                | Description                                           |
|-------------------------|-------------------------------------------------------|
| `BenchmarkRunner.run_project(project)` | Run full benchmark for a single project  |
| `BenchmarkRunner.run_all()`            | Run benchmark for all configured projects|
| `load_project_tasks(tasks_dir, name)`  | Load tasks from a `*-tasks.json` file    |
| `build_project_configs(projects, ...)`  | Build config dicts from project list    |
| `generate_report(summary)`             | Generate Markdown report from `RunSummary` |

**Usage:**
```python
from scripts.benchmark.run_full_benchmark import BenchmarkRunner, BenchmarkConfig

runner = BenchmarkRunner(
    config=BenchmarkConfig(
        projects=["scikit-learn", "pandas"],
        max_tasks_per_project=100,
    ),
    zerorepo_pipeline=my_generator,     # Optional: ZeroRepoPipeline
    evaluation_pipeline=my_evaluator,    # Optional: EvaluationPipeline
    profiling_collector=my_profiler,     # Optional: ProfilingCollector
)

# Single project
result = runner.run_project("scikit-learn")

# All projects
results = runner.run_all()
```

---

## CLI Reference

### Build benchmark tasks from a repository

```bash
python -m scripts.benchmark.build_repocraft \
    --repo-path /path/to/python-repo \
    --project-name scikit-learn \
    --output-dir ./benchmark-tasks \
    --sample-size 200 \
    --seed 42 \
    --min-loc 10 \
    -v
```

| Flag                 | Default            | Description                            |
|----------------------|--------------------|----------------------------------------|
| `--repo-path`        | *(required)*       | Path to the Python repository          |
| `--project-name`     | `"project"`        | Human-readable project name            |
| `--output-dir`       | `./benchmark-tasks`| Output directory for JSON              |
| `--sample-size`      | `200`              | Tasks to sample (0 = no sampling)      |
| `--seed`             | `42`               | RNG seed for reproducibility           |
| `--min-loc`          | `10`               | Minimum LOC threshold for filtering    |
| `--no-filter-flaky`  | *(off)*            | Disable flaky test detection           |
| `--no-filter-skipped`| *(off)*            | Disable skip decorator detection       |
| `-v, --verbose`      | *(off)*            | Enable DEBUG logging                   |

**Output:** `{output-dir}/{project-name}-tasks.json` containing:
```json
{
  "project": "scikit-learn",
  "summary": {
    "harvested": 1200,
    "filtered": 450,
    "sampled": 200
  },
  "tasks": [
    {
      "id": "scikit-learn-linear_model_ridge-fit_intercept-001",
      "project": "scikit-learn",
      "category": "linear_model.ridge",
      "subcategory": "fit_intercept",
      "description": "Test that fit intercept works correctly",
      "test_code": "def test_fit_intercept(): ...",
      "imports": ["from sklearn.linear_model import Ridge"],
      "loc": 15,
      "difficulty": "medium"
    }
  ]
}
```

### Run end-to-end benchmark

```bash
python -m scripts.benchmark.run_full_benchmark \
    --projects scikit-learn pandas sympy
```

Loads tasks from `benchmarks/repocraft/tasks/`, runs generation and evaluation,
saves results to `benchmarks/results/`.

---

## Benchmark Data Directory

```
benchmarks/
  repocraft/
    metadata.json         # Benchmark suite metadata (name, version, description)
    taxonomy.json         # Hierarchical task taxonomy (roots, categories, counts)
    tasks/                # Per-project task JSON files (created by build_repocraft)
      .gitkeep
      scikit-learn-tasks.json
      pandas-tasks.json
      ...
```

**`metadata.json`**: Contains benchmark suite metadata including `name`,
`version`, `description`, and aggregate task/project counts.

**`taxonomy.json`**: Stores the hierarchical taxonomy built by `Categorizer`,
with nested `TaxonomyNode` roots and totals.

---

## Result Interpretation Guide

### Understanding the Evaluation Funnel

Results follow a narrowing funnel. Each stage reduces the count of passing tasks:

```
Total Tasks:     200  (100%)
  ↓
Localized:       185  (92.5%)  ← Functions found in generated repo
  ↓
Validated:       160  (80.0%)  ← LLM confirms correct implementation
  ↓
Passed:          140  (70.0%)  ← Tests actually pass in Docker sandbox
```

**Healthy profile**: Gradual narrowing (e.g., 92% → 80% → 70%). Large drops
indicate specific problems:

| Drop Location          | Symptom                              | Likely Cause                                  | Recommended Fix                              |
|------------------------|--------------------------------------|-----------------------------------------------|----------------------------------------------|
| Localization → low     | Many tasks find no candidate         | Generated repo missing functions              | Improve generation prompts, check coverage   |
| Localization → Validation | Large drop (>15pp)               | Functions exist but are wrong                 | Improve code generation quality              |
| Validation → Execution | Large drop (>10pp)                   | Semantic review passes but tests fail         | Fix import mappings, sandbox config, deps    |

### Key Metrics Explained

| Metric             | What It Measures                                   | How to Improve                                |
|--------------------|----------------------------------------------------|-----------------------------------------------|
| **Pass Rate**      | End-to-end success (all 3 stages passed)           | Improve weakest stage (see funnel analysis)   |
| **Coverage**       | Category breadth (% categories with >=1 pass)      | Generate more diverse functionality           |
| **Voting Rate**    | LLM-assessed correctness (Stage 2 pass rate)       | Improve generation quality or tune validation |
| **Novelty**        | % of categories not in reference taxonomy           | Encourage creative generation beyond training |
| **Localization Rate** | Function matching success (Stage 1 pass rate)   | Better embeddings or function naming          |

### Comparing Against Paper Targets

The `ReportGenerator` produces a delta table:

| Metric       | Ours  | Paper  | Delta  | Interpretation               |
|--------------|-------|--------|--------|------------------------------|
| Coverage     | 82.0% | 81.5%  | +0.5%  | On par with paper            |
| Pass Rate    | 65.0% | 69.7%  | -4.7%  | Below target -- investigate  |
| Voting Rate  | 76.0% | 75.0%  | +1.0%  | Slightly above target        |

**Positive deltas** (your pipeline outperforms the paper):
- Indicates strong generation or evaluation improvements.

**Negative deltas** (below paper targets):
- Use `FailureAnalyzer` to identify which stage is the bottleneck.
- Check `category_counts` to see if failures cluster in specific categories.

### Reading Failure Reports

The `FailureReport` from `FailureAnalyzer.analyze_failures()` provides:

1. **`total_failures`**: Count of tasks that did not pass end-to-end.
2. **`category_counts`**: Breakdown by `FailureCategory` (planning, generation,
   localization, validation, execution, unknown).
3. **`samples`**: Up to `max_samples_per_category` representative failures per
   category -- examine these to understand common patterns.
4. **`recommendations`**: Threshold-based actionable suggestions. If a category
   exceeds its threshold, a specific recommendation is generated.

**Example interpretation:**
```
Total failures: 60/200
Categories:
  generation: 25    (12.5%)  ← Below 15% threshold, OK
  localization: 15  (7.5%)   ← Below 25% threshold, OK
  validation: 12    (6.0%)   ← Below 20% threshold, OK
  execution: 8      (4.0%)   ← Below 15% threshold, OK

Recommendation: "Failure distribution is within acceptable thresholds."
```

If any category exceeds its threshold, the report generates a specific
recommendation explaining what to fix.

### Profiling Insights

| Metric                  | What to Look For                                  |
|-------------------------|---------------------------------------------------|
| **Token usage by stage**| Which stage consumes the most tokens (= most cost)|
| **Stage timings**       | Which stage is the bottleneck for wall-clock time  |
| **Total cost (USD)**    | Estimated at $10/million tokens (rough)            |
| **Cache hit rate**      | High hit rate = savings from repeated runs         |

Common optimizations:
- High validation tokens → reduce `num_voters` or `num_rounds`
- Low cache hit rate → enable `EmbeddingCache` and `LLMResponseCache`
- Slow localization → pre-extract functions once, reuse across tasks
- High generation cost → use `BatchedFunctionGenerator` for batch prompts
