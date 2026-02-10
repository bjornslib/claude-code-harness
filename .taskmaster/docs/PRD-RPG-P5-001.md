# PRD-RPG-P5-001: ZeroRepo Phase 5 - Evaluation, Benchmarking, and Refinement

**Version**: 1.0
**Date**: 2026-02-07
**Status**: Draft
**Phase**: 5 of 6 (Evaluation & Benchmarking)
**Dependencies**: PRD-RPG-P1-001 (Design), PRD-RPG-P2-001 (Core), PRD-RPG-P3-001 (Generation), PRD-RPG-P4-001 (Repo Synthesis)

---

## Executive Summary

Phase 5 implements the comprehensive evaluation framework described in the ZeroRepo paper, including the RepoCraft benchmark construction, multi-stage validation pipeline, and iterative refinement based on failure analysis. This phase validates that our implementation meets the paper's reported metrics (81.5% coverage, 69.7% pass rate) and establishes a regression testing framework for ongoing improvements.

**Key Deliverables**:
1. RepoCraft benchmark dataset (~1000 tasks across 6 Python projects)
2. Three-stage evaluation pipeline (localization, semantic validation, execution testing)
3. Complete benchmark run with published metrics
4. Failure analysis and prompt refinement recommendations
5. Performance optimization analysis and implementation

---

## Background

### Paper's Evaluation Methodology

The ZeroRepo paper introduces **RepoCraft**, a benchmark dataset constructed from 6 real-world Python repositories:
- **scikit-learn** (machine learning)
- **pandas** (data manipulation)
- **sympy** (symbolic mathematics)
- **statsmodels** (statistical modeling)
- **requests** (HTTP library)
- **django** (web framework)

**Benchmark Construction Process**:
1. Harvest test functions from reference repositories
2. Categorize hierarchically following project structure
3. Apply stratified sampling for representative coverage
4. Filter trivial/non-algorithmic tests
5. Package as natural language tasks with ground-truth tests

**Evaluation Stages**:
1. **Localization**: Map task requirements to candidate functions in generated repo
2. **Semantic Validation**: LLM-based majority voting (2 rounds) to confirm fidelity
3. **Execution Testing**: Adapt and run ground-truth tests against generated code

### Target Metrics (from Paper)

| Metric | Definition | ZeroRepo Result |
|--------|------------|-----------------|
| **Functionality Coverage** | % of functional categories covered | 81.5% |
| **Functionality Novelty** | % of categories outside reference taxonomy | 18.5% |
| **Pass Rate** | Fraction of tests passed | 69.7% |
| **Voting Rate** | Fraction validated by majority-vote | 75.0% |
| **Lines of Code** | Total LOC in generated repo | ~24K (o3-mini) |
| **Token Usage** | Total LLM tokens consumed | ~3-5M per repo |

### Why This Phase Matters

1. **Validation**: Confirms our implementation matches paper's architecture
2. **Benchmarking**: Establishes baseline metrics for future improvements
3. **Failure Analysis**: Identifies systematic weaknesses in prompts/algorithms
4. **Optimization**: Reduces cost and latency for production use
5. **Regression Testing**: Prevents quality degradation during iteration

---

## Goals and Non-Goals

### Goals

1. **Construct RepoCraft benchmark** matching paper's methodology
2. **Implement three-stage evaluation pipeline** with automated scoring
3. **Execute full benchmark run** on at least 3 projects, measure all metrics
4. **Analyze failures systematically** and identify improvement opportunities
5. **Optimize token usage** to <5M tokens per repository
6. **Establish regression testing** framework for prompt changes

### Non-Goals

1. **Novel benchmark datasets** beyond RepoCraft (future work)
2. **Support for non-Python languages** (Phase 6 scope)
3. **Human evaluation studies** (resource-intensive, paper uses automated metrics)
4. **Production deployment** (Phase 6 scope)
5. **UI/UX for benchmark browsing** (out of scope)

---

## Epic Breakdown

## Epic 5.1: RepoCraft Benchmark Construction

**Goal**: Build a dataset of 1,000+ evaluation tasks from 6 Python repositories, following the paper's methodology.

### User Stories

**As a researcher**, I want to harvest test functions from reference repositories so that I can create ground-truth evaluation tasks.

**As a benchmark curator**, I want to categorize tasks hierarchically so that evaluation coverage is representative across functional categories.

**As an evaluator**, I want to filter trivial tests so that benchmarks measure meaningful algorithmic capabilities.

### Acceptance Criteria

- [ ] Test harvesting script extracts functions from pytest/unittest codebases
- [ ] Hierarchical categorization follows project directory structure (e.g., `pandas.core.groupby`, `sklearn.linear_model`)
- [ ] Stratified sampling ensures proportional representation across categories
- [ ] Filtering removes tests with <10 LOC, no assertions, or trivial logic
- [ ] Each task includes:
  - Natural language description (extracted from docstrings/comments)
  - Ground-truth test function (executable Python)
  - Auxiliary materials (imports, fixtures, sample data)
- [ ] Minimum 500 tasks across 3 projects (scikit-learn, pandas, sympy)
- [ ] Target 1,000 tasks across all 6 projects if feasible
- [ ] Metadata includes: project name, category, difficulty estimate, LOC

### Technical Implementation

#### 5.1.1: Test Harvesting Module

**Input**: Repository URL or local path
**Output**: JSON list of test functions with metadata

```python
# scripts/benchmark/harvest_tests.py

class TestHarvester:
    def extract_tests(self, repo_path: str) -> List[TestFunction]:
        """Extract all test functions from pytest/unittest files."""
        pass

    def parse_test_function(self, ast_node) -> TestFunction:
        """Parse AST node into TestFunction object."""
        pass

    def extract_description(self, func) -> str:
        """Extract natural language description from docstring/comments."""
        pass

    def extract_dependencies(self, func) -> List[str]:
        """Extract imports, fixtures, and auxiliary code."""
        pass
```

**Test Function Schema**:
```json
{
  "id": "sklearn-linear_model-ridge-001",
  "project": "scikit-learn",
  "category": "sklearn.linear_model",
  "subcategory": "ridge",
  "description": "Test Ridge regression with alpha=1.0 on synthetic data",
  "test_code": "def test_ridge_regression(): ...",
  "imports": ["import numpy as np", "from sklearn.linear_model import Ridge"],
  "fixtures": [],
  "auxiliary_code": "X = np.random.randn(100, 5); y = ...",
  "loc": 15,
  "difficulty": "medium"
}
```

#### 5.1.2: Hierarchical Categorization

**Input**: List of test functions
**Output**: Hierarchical taxonomy with category counts

```python
# scripts/benchmark/categorize.py

class Categorizer:
    def build_taxonomy(self, tests: List[TestFunction]) -> Taxonomy:
        """Build hierarchical taxonomy from test categories."""
        pass

    def stratified_sample(self, tests: List[TestFunction], n: int) -> List[TestFunction]:
        """Sample n tests proportionally across categories."""
        pass
```

**Taxonomy Example**:
```
scikit-learn (250 tests)
├── linear_model (60 tests)
│   ├── ridge (12 tests)
│   ├── lasso (10 tests)
│   └── logistic (15 tests)
├── ensemble (45 tests)
│   ├── random_forest (20 tests)
│   └── gradient_boosting (15 tests)
└── ...
```

#### 5.1.3: Filtering Pipeline

**Rules** (from paper):
1. Remove tests with <10 lines of code
2. Remove tests with no assertions (`assert`, `assertEqual`, etc.)
3. Remove tests marked as `@pytest.mark.skip` or `@unittest.skip`
4. Remove trivial tests (e.g., only testing imports, type checks)
5. Remove flaky tests (require network, filesystem, external services)

```python
# scripts/benchmark/filter.py

class TestFilter:
    def is_trivial(self, test: TestFunction) -> bool:
        """Check if test is too simple (e.g., only imports)."""
        return test.loc < 10 or not self.has_assertions(test)

    def is_flaky(self, test: TestFunction) -> bool:
        """Check if test requires external dependencies."""
        flaky_patterns = ['requests.get', 'open(', 'socket.', 'time.sleep']
        return any(p in test.test_code for p in flaky_patterns)
```

#### 5.1.4: Benchmark Package Format

**Output**: JSON dataset + documentation

```bash
benchmarks/
├── repocraft/
│   ├── metadata.json          # Benchmark statistics
│   ├── tasks/
│   │   ├── sklearn-*.json     # 250 tasks
│   │   ├── pandas-*.json      # 200 tasks
│   │   ├── sympy-*.json       # 180 tasks
│   │   ├── statsmodels-*.json # 150 tasks
│   │   ├── requests-*.json    # 120 tasks
│   │   └── django-*.json      # 100 tasks
│   ├── taxonomy.json          # Hierarchical structure
│   └── README.md              # Dataset documentation
```

### Testing Strategy

- **Unit tests**: Test harvesting logic on synthetic test files
- **Integration tests**: Extract tests from small reference repos (10-20 tests)
- **Validation**: Manual review of 50 random tasks for quality
- **Coverage check**: Ensure all 6 projects have >100 tasks each

### Dependencies

- **External**: Access to reference repositories (clone from GitHub)
- **Tools**: `ast` module for Python parsing, `pytest` introspection
- **Phase 4**: None (independent of repo generation)

---

## Epic 5.2: Evaluation Pipeline Implementation

**Goal**: Implement the three-stage evaluation pipeline from the paper: localization, semantic validation, and execution testing.

### User Stories

**As an evaluator**, I want to automatically locate candidate functions in a generated repository so that I can test if required functionality exists.

**As a validator**, I want LLM-based semantic checking so that I can confirm generated functions match task requirements without manual review.

**As a tester**, I want to execute ground-truth tests against generated code so that I can measure functional correctness.

### Acceptance Criteria

- [ ] **Stage 1 (Localization)**: Given a task and generated repo, identify top-k candidate functions
- [ ] **Stage 2 (Semantic Validation)**: LLM majority-vote (2 rounds, 3 voters) confirms function fidelity
- [ ] **Stage 3 (Execution Testing)**: Adapt ground-truth tests and execute against generated code
- [ ] Pipeline produces per-task results: {localized, validated, passed}
- [ ] Aggregated metrics match paper's format (coverage, pass rate, voting rate)
- [ ] Execution isolated in Docker/sandbox to prevent side effects
- [ ] End-to-end pipeline runs in <10 minutes per task (parallelizable)

### Technical Implementation

#### 5.2.1: Stage 1 - Localization

**Goal**: Map task description to candidate functions in generated repository

**Algorithm** (from paper):
1. Embed task description using sentence-transformers
2. Embed all function signatures in generated repo
3. Compute cosine similarity
4. Return top-k candidates (k=5 recommended)

```python
# src/evaluation/localization.py

from sentence_transformers import SentenceTransformer
from typing import List, Tuple

class FunctionLocalizer:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def extract_functions(self, repo_path: str) -> List[FunctionSignature]:
        """Extract all function signatures from generated repo."""
        pass

    def localize(
        self,
        task: Task,
        repo_path: str,
        top_k: int = 5
    ) -> List[Tuple[FunctionSignature, float]]:
        """Return top-k candidate functions with similarity scores."""
        task_embedding = self.model.encode(task.description)
        function_embeddings = self.model.encode([f.signature for f in functions])
        similarities = cosine_similarity([task_embedding], function_embeddings)[0]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [(functions[i], similarities[i]) for i in top_indices]
```

**Function Signature Format**:
```python
class FunctionSignature:
    name: str              # e.g., "ridge_regression"
    module: str            # e.g., "ml_lib.linear_model.ridge"
    signature: str         # e.g., "def ridge_regression(X, y, alpha=1.0)"
    docstring: str         # First line of docstring
    file_path: str         # Absolute path in repo
    start_line: int
    end_line: int
```

#### 5.2.2: Stage 2 - Semantic Validation

**Goal**: LLM-based majority voting to confirm function matches task requirements

**Prompt Template** (from paper's methodology):
```python
VALIDATION_PROMPT = """
You are a code reviewer validating whether a function implements the required functionality.

**Task Requirements**:
{task_description}

**Generated Function**:
```python
{function_code}
```

**Question**: Does this function correctly implement the required functionality?

Answer ONLY with:
- "YES" if the function implements all requirements
- "NO" if the function is missing requirements or has incorrect logic
- "PARTIAL" if the function implements some but not all requirements

Provide a brief 1-sentence justification.

Answer:
"""
```

**Majority Voting Logic**:
```python
# src/evaluation/semantic_validation.py

class SemanticValidator:
    def __init__(self, llm_client, num_voters: int = 3, num_rounds: int = 2):
        self.llm = llm_client
        self.num_voters = num_voters
        self.num_rounds = num_rounds

    def validate_function(
        self,
        task: Task,
        function: FunctionCode
    ) -> ValidationResult:
        """Run majority-vote validation across multiple rounds."""
        votes_round1 = [self._vote(task, function) for _ in range(self.num_voters)]

        if self._has_majority(votes_round1):
            return ValidationResult(
                passed=self._majority_vote(votes_round1) == "YES",
                confidence="high",
                votes=votes_round1
            )

        # Round 2 if no clear majority
        votes_round2 = [self._vote(task, function) for _ in range(self.num_voters)]
        all_votes = votes_round1 + votes_round2

        return ValidationResult(
            passed=self._majority_vote(all_votes) == "YES",
            confidence="medium" if self._has_majority(all_votes) else "low",
            votes=all_votes
        )

    def _vote(self, task: Task, function: FunctionCode) -> str:
        """Single LLM vote: YES/NO/PARTIAL."""
        prompt = VALIDATION_PROMPT.format(
            task_description=task.description,
            function_code=function.code
        )
        response = self.llm.complete(prompt, max_tokens=100)
        return self._parse_vote(response)
```

#### 5.2.3: Stage 3 - Execution Testing

**Goal**: Run ground-truth tests against generated code

**Challenges**:
1. Test adaptation (imports, module names differ from reference)
2. Execution isolation (prevent side effects)
3. Timeout handling (infinite loops)
4. Dependency mismatch (generated code may have different APIs)

```python
# src/evaluation/execution_testing.py

import docker
import tempfile
import shutil
from pathlib import Path

class ExecutionTester:
    def __init__(self, timeout: int = 30):
        self.docker_client = docker.from_env()
        self.timeout = timeout

    def adapt_test(self, task: Task, repo_path: str) -> str:
        """Adapt ground-truth test to use generated repo's imports."""
        # Replace imports: sklearn.linear_model → generated_repo.ml.linear_model
        adapted_imports = self._rewrite_imports(task.imports, repo_path)

        test_code = f"""
{adapted_imports}

{task.auxiliary_code}

{task.test_code}

if __name__ == "__main__":
    {self._extract_test_function_name(task.test_code)}()
    print("TEST_PASSED")
"""
        return test_code

    def execute_test(self, task: Task, repo_path: str) -> ExecutionResult:
        """Run test in isolated Docker container."""
        adapted_test = self.adapt_test(task, repo_path)

        # Create temp directory with repo + test
        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.copytree(repo_path, f"{tmpdir}/repo")
            Path(f"{tmpdir}/test.py").write_text(adapted_test)

            # Run in Docker
            try:
                container = self.docker_client.containers.run(
                    "python:3.11-slim",
                    f"python test.py",
                    volumes={tmpdir: {'bind': '/workspace', 'mode': 'ro'}},
                    working_dir="/workspace",
                    timeout=self.timeout,
                    detach=True
                )

                exit_code = container.wait(timeout=self.timeout)['StatusCode']
                logs = container.logs().decode('utf-8')

                return ExecutionResult(
                    passed="TEST_PASSED" in logs and exit_code == 0,
                    exit_code=exit_code,
                    stdout=logs,
                    error=None if exit_code == 0 else logs
                )

            except docker.errors.ContainerError as e:
                return ExecutionResult(passed=False, error=str(e))
            except TimeoutError:
                return ExecutionResult(passed=False, error="Timeout")
```

#### 5.2.4: Pipeline Orchestration

**End-to-End Flow**:
```python
# src/evaluation/pipeline.py

class EvaluationPipeline:
    def __init__(self, localizer, validator, tester):
        self.localizer = localizer
        self.validator = validator
        self.tester = tester

    def evaluate_task(self, task: Task, repo_path: str) -> TaskResult:
        """Run full 3-stage evaluation on a single task."""

        # Stage 1: Localization
        candidates = self.localizer.localize(task, repo_path, top_k=5)

        if not candidates:
            return TaskResult(
                task_id=task.id,
                localized=False,
                validated=False,
                passed=False,
                stage_failed="localization"
            )

        # Stage 2: Semantic Validation (try top-3 candidates)
        validated_candidate = None
        for candidate, score in candidates[:3]:
            validation = self.validator.validate_function(task, candidate)
            if validation.passed:
                validated_candidate = candidate
                break

        if not validated_candidate:
            return TaskResult(
                task_id=task.id,
                localized=True,
                validated=False,
                passed=False,
                stage_failed="validation"
            )

        # Stage 3: Execution Testing
        execution = self.tester.execute_test(task, repo_path)

        return TaskResult(
            task_id=task.id,
            localized=True,
            validated=True,
            passed=execution.passed,
            stage_failed=None if execution.passed else "execution",
            candidate_function=validated_candidate.name,
            execution_error=execution.error
        )

    def evaluate_repository(
        self,
        tasks: List[Task],
        repo_path: str
    ) -> RepositoryResult:
        """Evaluate all tasks for a repository."""
        results = [self.evaluate_task(task, repo_path) for task in tasks]

        return RepositoryResult(
            project_name=tasks[0].project,
            total_tasks=len(tasks),
            localized=sum(r.localized for r in results),
            validated=sum(r.validated for r in results),
            passed=sum(r.passed for r in results),
            coverage=self._calculate_coverage(tasks, results),
            novelty=self._calculate_novelty(tasks, results),
            task_results=results
        )
```

### Testing Strategy

- **Unit tests**: Mock LLM responses, test voting logic
- **Integration tests**: Run pipeline on 10 synthetic tasks
- **Validation**: Manual review of localization accuracy on 20 tasks
- **Performance**: Measure latency per stage (target <1 min/task for stages 1+2)

### Dependencies

- **Epic 5.1**: Benchmark tasks required for evaluation
- **Phase 4**: Generated repositories to evaluate against
- **External**: Docker for test isolation, sentence-transformers for embeddings

---

## Epic 5.3: End-to-End Benchmark Run

**Goal**: Execute the complete ZeroRepo pipeline on all 6 RepoCraft projects and measure performance against paper's reported metrics.

### User Stories

**As a researcher**, I want to run the full benchmark so that I can compare our implementation to the paper's results.

**As a project manager**, I want automated reports so that I can track progress toward target metrics.

**As an engineer**, I want profiling data so that I can identify bottlenecks for optimization.

### Acceptance Criteria

- [ ] Full pipeline runs on at least 3 projects (scikit-learn, pandas, sympy)
- [ ] All metrics calculated: Coverage, Novelty, Pass Rate, Voting Rate, LOC, Token Usage
- [ ] Results exported in paper's format (tables, charts)
- [ ] Comparison report shows delta from paper's published numbers
- [ ] Profiling data captures: LLM calls, token usage per stage, wall-clock time
- [ ] Reproducible run script with clear logging

### Technical Implementation

#### 5.3.1: Benchmark Runner

**Input**: Project name (e.g., "scikit-learn")
**Output**: Generated repository + evaluation results

```python
# scripts/run_benchmark.py

class BenchmarkRunner:
    def __init__(self, zeropro_pipeline, evaluation_pipeline):
        self.zeropro = zeropro_pipeline
        self.evaluation = evaluation_pipeline

    def run_project(self, project_name: str) -> BenchmarkResult:
        """Run ZeroRepo generation + evaluation for one project."""

        # Step 1: Load benchmark tasks
        tasks = self._load_tasks(project_name)

        # Step 2: Paraphrase project name (paper's methodology)
        paraphrased_name = self._paraphrase_name(project_name)

        # Step 3: Generate repository using ZeroRepo
        logger.info(f"Generating repository for {paraphrased_name}...")
        repo_path = self.zeropro.generate_repository(
            project_description=self._get_project_description(project_name),
            project_name=paraphrased_name
        )

        # Step 4: Evaluate against benchmark
        logger.info(f"Evaluating {len(tasks)} tasks...")
        eval_result = self.evaluation.evaluate_repository(tasks, repo_path)

        # Step 5: Collect profiling data
        profiling = self._collect_profiling_data()

        return BenchmarkResult(
            project=project_name,
            paraphrased_name=paraphrased_name,
            evaluation=eval_result,
            profiling=profiling,
            repo_path=repo_path
        )
```

**Paraphrase Strategy** (from paper):
- scikit-learn → "machine learning toolkit"
- pandas → "data analysis framework"
- sympy → "symbolic math library"
- statsmodels → "statistical modeling package"
- requests → "HTTP client library"
- django → "web application framework"

#### 5.3.2: Metrics Calculation

**Paper's Metrics Implementation**:

```python
# src/evaluation/metrics.py

class MetricsCalculator:
    def calculate_coverage(
        self,
        tasks: List[Task],
        results: List[TaskResult]
    ) -> float:
        """Functionality Coverage: % of categories with ≥1 passed test."""
        categories = set(task.category for task in tasks)
        passed_tasks = [r for r in results if r.passed]
        covered_categories = set(
            tasks[i].category for i, r in enumerate(results) if r.passed
        )
        return len(covered_categories) / len(categories)

    def calculate_novelty(
        self,
        tasks: List[Task],
        results: List[TaskResult]
    ) -> float:
        """Functionality Novelty: % categories outside reference taxonomy."""
        # Extract categories from generated repo
        generated_categories = self._extract_categories_from_repo(results[0].repo_path)
        reference_categories = set(task.category for task in tasks)

        novel_categories = generated_categories - reference_categories
        return len(novel_categories) / len(generated_categories)

    def calculate_pass_rate(self, results: List[TaskResult]) -> float:
        """Pass Rate: fraction of tests passed."""
        return sum(r.passed for r in results) / len(results)

    def calculate_voting_rate(self, results: List[TaskResult]) -> float:
        """Voting Rate: fraction validated by majority-vote."""
        return sum(r.validated for r in results) / len(results)

    def calculate_code_stats(self, repo_path: str) -> CodeStats:
        """Calculate LOC, files, tokens."""
        total_loc = 0
        total_files = 0

        for py_file in Path(repo_path).rglob("*.py"):
            total_files += 1
            total_loc += len(py_file.read_text().splitlines())

        # Estimate tokens (rough: ~4 chars per token)
        total_chars = sum(
            len(f.read_text()) for f in Path(repo_path).rglob("*.py")
        )
        total_tokens = total_chars // 4

        return CodeStats(
            files=total_files,
            loc=total_loc,
            tokens=total_tokens
        )
```

#### 5.3.3: Profiling and Instrumentation

**Track LLM Token Usage**:
```python
# src/evaluation/profiling.py

class ProfilingCollector:
    def __init__(self):
        self.llm_calls = []
        self.stage_timings = {}

    def record_llm_call(
        self,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int
    ):
        """Record an LLM API call."""
        self.llm_calls.append({
            "stage": stage,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "timestamp": time.time()
        })

    def get_stage_summary(self) -> Dict[str, TokenStats]:
        """Aggregate token usage by stage."""
        summary = defaultdict(lambda: {"prompt": 0, "completion": 0, "calls": 0})

        for call in self.llm_calls:
            stage = call["stage"]
            summary[stage]["prompt"] += call["prompt_tokens"]
            summary[stage]["completion"] += call["completion_tokens"]
            summary[stage]["calls"] += 1

        return dict(summary)
```

**Instrumentation Points**:
- Phase 1: Planning (prompt tokens, completion tokens)
- Phase 2: Requirement extraction
- Phase 3: Function generation (per-function tokens)
- Phase 4: Repository synthesis
- Evaluation: Semantic validation (3-6 votes per task)

#### 5.3.4: Report Generation

**Output Format** (matching paper's tables):

```python
# scripts/generate_report.py

class ReportGenerator:
    def generate_comparison_report(
        self,
        results: List[BenchmarkResult]
    ) -> str:
        """Generate markdown report comparing to paper's results."""

        report = f"""
# ZeroRepo Benchmark Results

**Run Date**: {datetime.now().isoformat()}
**Projects**: {len(results)}

## Summary Metrics

| Project | Coverage | Pass Rate | Voting Rate | LOC | Token Usage |
|---------|----------|-----------|-------------|-----|-------------|
"""

        for result in results:
            report += f"| {result.project} | "
            report += f"{result.evaluation.coverage:.1%} | "
            report += f"{result.evaluation.pass_rate:.1%} | "
            report += f"{result.evaluation.voting_rate:.1%} | "
            report += f"{result.profiling.total_loc:,} | "
            report += f"{result.profiling.total_tokens:,} |\n"

        # Add comparison to paper
        report += f"""

## Comparison to Paper (ZeroRepo w/ o3-mini)

| Metric | Our Result | Paper Result | Delta |
|--------|------------|--------------|-------|
| Coverage | {self._avg_coverage(results):.1%} | 81.5% | {self._delta_coverage(results)} |
| Pass Rate | {self._avg_pass_rate(results):.1%} | 69.7% | {self._delta_pass_rate(results)} |
| Voting Rate | {self._avg_voting_rate(results):.1%} | 75.0% | {self._delta_voting_rate(results)} |
| Avg LOC | {self._avg_loc(results):,} | ~24,000 | {self._delta_loc(results)} |

"""
        return report
```

### Testing Strategy

- **Dry run**: Execute on 1 small project (requests) with 50 tasks
- **Full run**: Execute on 3 major projects with full task sets
- **Validation**: Manual review of 10 generated repositories for quality
- **Regression**: Compare results to previous benchmark runs (if any)

### Dependencies

- **Epic 5.1**: Complete benchmark dataset
- **Epic 5.2**: Working evaluation pipeline
- **Phase 1-4**: Complete ZeroRepo implementation

---

## Epic 5.4: Failure Analysis and Prompt Refinement

**Goal**: Systematically analyze failures, categorize root causes, and iteratively refine prompts to improve pass rates.

### User Stories

**As an engineer**, I want to understand why tasks fail so that I can improve the system.

**As a prompt engineer**, I want to A/B test prompt variants so that I can validate improvements empirically.

**As a quality lead**, I want regression tests so that prompt changes don't degrade existing functionality.

### Acceptance Criteria

- [ ] Failure taxonomy with at least 3 categories (planning, generation, execution)
- [ ] Analysis of 100+ failed tasks with categorization
- [ ] At least 5 actionable improvement recommendations
- [ ] A/B testing framework for prompt variants
- [ ] Regression test suite with 50+ test cases
- [ ] Documentation of prompt refinement process and results

### Technical Implementation

#### 5.4.1: Failure Taxonomy

**Categories** (from paper's analysis):

1. **Planning Failures**: Requirements misunderstood, wrong feature decomposition
2. **Generation Failures**: Code generation errors (syntax, logic, incomplete)
3. **Localization Failures**: Correct code generated but not found by embedding search
4. **Validation Failures**: Code is correct but LLM judges incorrectly
5. **Execution Failures**: Code correct semantically but fails ground-truth test

```python
# src/evaluation/failure_analysis.py

class FailureAnalyzer:
    def categorize_failure(self, task: Task, result: TaskResult) -> FailureCategory:
        """Determine root cause of task failure."""

        if not result.localized:
            # Check if function exists with different name
            if self._function_exists_with_different_name(task, result.repo_path):
                return FailureCategory.LOCALIZATION
            else:
                return FailureCategory.PLANNING

        if not result.validated:
            # Check if validation was incorrect (re-run with different LLM)
            if self._revalidate_with_fallback(task, result.candidate_function):
                return FailureCategory.VALIDATION
            else:
                return FailureCategory.GENERATION

        if not result.passed:
            # Execution failure - analyze error message
            if "ImportError" in result.execution_error:
                return FailureCategory.GENERATION  # Missing dependencies
            elif "AssertionError" in result.execution_error:
                return FailureCategory.GENERATION  # Incorrect logic
            elif "TypeError" in result.execution_error:
                return FailureCategory.GENERATION  # API mismatch
            else:
                return FailureCategory.EXECUTION

        return FailureCategory.UNKNOWN

    def analyze_failures(
        self,
        tasks: List[Task],
        results: List[TaskResult]
    ) -> FailureReport:
        """Generate comprehensive failure analysis."""

        failures = [r for r in results if not r.passed]
        categorized = [self.categorize_failure(tasks[i], r)
                       for i, r in enumerate(results) if not r.passed]

        category_counts = Counter(categorized)

        # Sample failures for manual review
        samples_by_category = defaultdict(list)
        for i, category in enumerate(categorized):
            if len(samples_by_category[category]) < 10:
                samples_by_category[category].append(failures[i])

        return FailureReport(
            total_failures=len(failures),
            category_counts=dict(category_counts),
            samples=dict(samples_by_category),
            recommendations=self._generate_recommendations(category_counts)
        )
```

#### 5.4.2: Improvement Recommendations

**Pattern-Based Recommendations**:

```python
def _generate_recommendations(self, category_counts: Counter) -> List[str]:
    """Generate actionable recommendations based on failure patterns."""

    recommendations = []

    # Planning failures > 20% of total
    if category_counts[FailureCategory.PLANNING] > 0.2 * sum(category_counts.values()):
        recommendations.append(
            "HIGH PRIORITY: Planning failures are frequent. "
            "Consider: (1) More detailed requirement extraction prompts, "
            "(2) Multi-round planning with validation, "
            "(3) Better decomposition heuristics."
        )

    # Generation failures > 30% of total
    if category_counts[FailureCategory.GENERATION] > 0.3 * sum(category_counts.values()):
        recommendations.append(
            "MEDIUM PRIORITY: Generation failures indicate prompt quality issues. "
            "Consider: (1) Few-shot examples in generation prompts, "
            "(2) Stronger model for code generation, "
            "(3) Post-generation validation before synthesis."
        )

    # Localization failures > 15% of total
    if category_counts[FailureCategory.LOCALIZATION] > 0.15 * sum(category_counts.values()):
        recommendations.append(
            "MEDIUM PRIORITY: Localization struggles with function naming. "
            "Consider: (1) Standardize function naming conventions, "
            "(2) Use hybrid search (keyword + embedding), "
            "(3) Include docstrings in embedding."
        )

    return recommendations
```

#### 5.4.3: A/B Testing Framework

**Prompt Variant Testing**:

```python
# scripts/ab_test_prompts.py

class PromptABTest:
    def __init__(self, baseline_prompt: str, variant_prompt: str):
        self.baseline = baseline_prompt
        self.variant = variant_prompt

    def run_test(
        self,
        test_cases: List[Task],
        sample_size: int = 50
    ) -> ABTestResult:
        """Run A/B test on a sample of tasks."""

        # Randomly split test cases
        baseline_tasks = random.sample(test_cases, sample_size)
        variant_tasks = random.sample(test_cases, sample_size)

        # Run baseline
        baseline_results = self._run_with_prompt(baseline_tasks, self.baseline)

        # Run variant
        variant_results = self._run_with_prompt(variant_tasks, self.variant)

        # Compare metrics
        baseline_pass_rate = sum(r.passed for r in baseline_results) / len(baseline_results)
        variant_pass_rate = sum(r.passed for r in variant_results) / len(variant_results)

        # Statistical significance test (chi-squared)
        p_value = self._chi_squared_test(baseline_results, variant_results)

        return ABTestResult(
            baseline_pass_rate=baseline_pass_rate,
            variant_pass_rate=variant_pass_rate,
            delta=variant_pass_rate - baseline_pass_rate,
            p_value=p_value,
            significant=p_value < 0.05,
            recommendation="ADOPT VARIANT" if variant_pass_rate > baseline_pass_rate and p_value < 0.05 else "KEEP BASELINE"
        )
```

**Example Prompt Variants**:

| Stage | Baseline | Variant | Hypothesis |
|-------|----------|---------|------------|
| Planning | Zero-shot | Few-shot (3 examples) | Examples improve structure |
| Generation | "Implement X" | "Implement X with error handling and type hints" | More specificity improves quality |
| Synthesis | Sequential integration | Dependency-ordered integration | Order reduces import errors |

#### 5.4.4: Regression Test Suite

**Goal**: Prevent quality degradation during prompt iteration

```python
# tests/regression/test_prompts.py

class PromptRegressionTests:
    @pytest.fixture
    def golden_tasks(self):
        """50 tasks known to pass with current prompts."""
        return load_golden_tasks("tests/regression/golden_tasks.json")

    def test_planning_prompt_regression(self, golden_tasks):
        """Ensure planning prompt changes don't break known-good tasks."""
        planning_tasks = [t for t in golden_tasks if t.stage == "planning"]

        for task in planning_tasks:
            result = run_planning_stage(task)
            assert result.success, f"Regression on task {task.id}"

    def test_generation_prompt_regression(self, golden_tasks):
        """Ensure generation prompt changes maintain quality."""
        generation_tasks = [t for t in golden_tasks if t.stage == "generation"]

        for task in generation_tasks:
            result = run_generation_stage(task)
            assert result.compiles, f"Generated code doesn't compile: {task.id}"
            assert result.has_docstring, f"Missing docstring: {task.id}"
```

**Golden Task Selection**:
- 10 tasks per project (60 total)
- Mix of easy/medium/hard difficulty
- Representative of each functional category
- Known to pass with current implementation

### Testing Strategy

- **Baseline**: Run full benchmark to establish failure distribution
- **Categorization**: Manually validate categorization on 50 failures
- **A/B tests**: Run at least 3 prompt variants with 50 tasks each
- **Regression**: Run regression suite before/after each prompt change

### Dependencies

- **Epic 5.3**: Benchmark run results with failures
- **Epic 5.2**: Evaluation pipeline for re-testing

---

## Epic 5.5: Performance Optimization

**Goal**: Reduce token usage, latency, and cost while maintaining quality metrics.

### User Stories

**As a product manager**, I want to reduce costs so that the system is economically viable at scale.

**As an engineer**, I want to optimize latency so that repositories generate faster.

**As an infrastructure lead**, I want caching strategies so that repeated evaluations are efficient.

### Acceptance Criteria

- [ ] Token usage profiled across all stages
- [ ] Caching implemented for embeddings and LLM responses
- [ ] Batch size optimization for LLM calls
- [ ] Target: <5M tokens per repository generation (vs ~7M baseline)
- [ ] Latency reduction of >30% without quality degradation
- [ ] Performance optimization report with recommendations

### Technical Implementation

#### 5.5.1: Token Usage Profiling

**Breakdown by Stage** (from profiling in Epic 5.3):

```python
# scripts/profile_tokens.py

class TokenProfiler:
    def profile_repository_generation(self, project_name: str) -> TokenProfile:
        """Profile token usage across all stages."""

        profiler = ProfilingCollector()

        # Instrument all LLM calls
        with profiler.track():
            result = run_benchmark(project_name)

        breakdown = {
            "planning": profiler.get_stage_tokens("planning"),
            "requirement_extraction": profiler.get_stage_tokens("requirement_extraction"),
            "function_generation": profiler.get_stage_tokens("function_generation"),
            "repository_synthesis": profiler.get_stage_tokens("repository_synthesis"),
            "evaluation_validation": profiler.get_stage_tokens("semantic_validation")
        }

        return TokenProfile(
            total_tokens=sum(breakdown.values()),
            breakdown=breakdown,
            cost_estimate=self._calculate_cost(breakdown)
        )
```

**Expected Baseline** (from paper):
- Planning: ~500K tokens
- Requirement extraction: ~1M tokens
- Function generation: ~3M tokens (largest)
- Repository synthesis: ~500K tokens
- Evaluation: ~2M tokens (validation votes)
- **Total**: ~7M tokens per repository

#### 5.5.2: Caching Strategies

**Embedding Cache** (for localization):
```python
# src/evaluation/caching.py

import hashlib
import pickle
from pathlib import Path

class EmbeddingCache:
    def __init__(self, cache_dir: str = ".cache/embeddings"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Retrieve cached embedding if available."""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            return pickle.load(cache_file.open("rb"))
        return None

    def set_embedding(self, text: str, embedding: np.ndarray):
        """Cache embedding for future use."""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        pickle.dump(embedding, cache_file.open("wb"))
```

**LLM Response Cache** (for deterministic prompts):
```python
class LLMResponseCache:
    def __init__(self, cache_dir: str = ".cache/llm_responses"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_response(self, prompt: str, model: str) -> Optional[str]:
        """Retrieve cached LLM response."""
        cache_key = hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.txt"

        if cache_file.exists():
            return cache_file.read_text()
        return None

    def set_response(self, prompt: str, model: str, response: str):
        """Cache LLM response."""
        cache_key = hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.txt"
        cache_file.write_text(response)
```

**Cache Invalidation**:
- Embedding cache: Never invalidate (text → embedding is deterministic)
- LLM cache: Invalidate when prompt templates change (track template version)

#### 5.5.3: Batch Optimization

**Current**: Sequential LLM calls for function generation
**Optimized**: Batch multiple functions in single prompt

```python
# src/generation/batch_generation.py

class BatchedFunctionGenerator:
    def __init__(self, max_batch_size: int = 5):
        self.max_batch_size = max_batch_size

    def generate_functions_batched(
        self,
        requirements: List[FunctionRequirement]
    ) -> List[GeneratedFunction]:
        """Generate multiple functions in batched prompts."""

        batches = self._create_batches(requirements, self.max_batch_size)
        results = []

        for batch in batches:
            prompt = self._create_batch_prompt(batch)
            response = self.llm.complete(prompt, max_tokens=4000)
            parsed_functions = self._parse_batch_response(response)
            results.extend(parsed_functions)

        return results

    def _create_batch_prompt(self, requirements: List[FunctionRequirement]) -> str:
        """Create prompt for multiple functions."""
        prompt = "Generate the following Python functions:\n\n"

        for i, req in enumerate(requirements, 1):
            prompt += f"Function {i}: {req.name}\n"
            prompt += f"Requirements: {req.description}\n"
            prompt += f"Signature: {req.signature}\n\n"

        prompt += "Output each function with a separator '---FUNCTION---'\n"
        return prompt
```

**Trade-offs**:
- ✅ Reduces total tokens (shared prompt overhead)
- ✅ Reduces API calls (latency improvement)
- ❌ Larger context window (may hit model limits)
- ❌ Harder to debug individual functions

**Recommendation**: Batch size = 5 (empirically validated in paper)

#### 5.5.4: Unnecessary Re-generation Prevention

**Problem**: Current implementation may regenerate functions multiple times during iteration.

**Solution**: Deduplication + incremental synthesis

```python
# src/synthesis/incremental_synthesis.py

class IncrementalSynthesizer:
    def __init__(self):
        self.generated_functions = {}  # name → code mapping

    def synthesize_with_deduplication(
        self,
        functions: List[GeneratedFunction]
    ) -> str:
        """Only regenerate functions that changed."""

        new_functions = []

        for func in functions:
            if func.name not in self.generated_functions:
                new_functions.append(func)
                self.generated_functions[func.name] = func.code

            elif self._signature_changed(func):
                # Regenerate only if signature changed
                new_functions.append(func)
                self.generated_functions[func.name] = func.code

        # Synthesize only new/changed functions
        return self._synthesize_incremental(new_functions)
```

#### 5.5.5: Model Selection Optimization

**Trade-off**: Cheaper models for simple tasks, expensive models for complex tasks

| Stage | Current Model | Optimized Model | Token Savings |
|-------|--------------|-----------------|---------------|
| Planning | o3-mini | o3-mini | 0% (keep quality) |
| Requirement extraction | o3-mini | GPT-4o-mini | -60% cost |
| Function generation | o3-mini | o3-mini | 0% (critical) |
| Validation voting | GPT-4o | GPT-4o-mini | -60% cost |

**Estimated Savings**: ~40% total cost reduction without quality loss

### Testing Strategy

- **Baseline**: Profile current implementation on 3 projects
- **Optimization**: Implement caching + batching + model selection
- **Comparison**: Re-run profiling, measure token reduction
- **Quality check**: Ensure metrics don't degrade (pass rate ≥ baseline)

### Dependencies

- **Epic 5.3**: Profiling data from benchmark run
- **Epic 5.4**: Ensure optimizations don't break regression tests

---

## Success Metrics

### Primary Metrics (vs Paper's Results)

| Metric | Target | Stretch Goal | Paper Baseline |
|--------|--------|--------------|----------------|
| **Functionality Coverage** | ≥75% | ≥81.5% | 81.5% |
| **Pass Rate** | ≥60% | ≥69.7% | 69.7% |
| **Voting Rate** | ≥70% | ≥75.0% | 75.0% |
| **Lines of Code** | ≥15K | ≥24K | ~24K |

### Secondary Metrics

| Metric | Target |
|--------|--------|
| **Benchmark Construction** | 1,000 tasks across 6 projects |
| **Evaluation Latency** | <10 min per task (parallelized) |
| **Token Usage** | <5M tokens per repository |
| **Cost per Repository** | <$50 (at GPT-4 pricing) |

### Process Metrics

| Metric | Target |
|--------|--------|
| **Failure Categorization** | 100% of failures categorized |
| **Prompt A/B Tests** | ≥3 variants tested |
| **Regression Test Coverage** | 50+ golden tasks |
| **Optimization Impact** | ≥30% latency reduction |

---

## Dependencies

### Internal (ZeroRepo Phases)

- **Phase 1 (RPG-P1-001)**: AIOS design, tool schemas - Required for end-to-end run
- **Phase 2 (RPG-P2-001)**: Planning pipeline - Required for repository generation
- **Phase 3 (RPG-P3-001)**: Generation module - Required for function generation
- **Phase 4 (RPG-P4-001)**: Repository synthesis - Required for final repo output

### External Tools

- **sentence-transformers**: For embedding-based localization
- **Docker**: For isolated test execution
- **pytest**: For ground-truth test adaptation
- **GitHub API**: For downloading reference repositories

### Data

- **Reference Repositories**: scikit-learn, pandas, sympy, statsmodels, requests, django
- **Test Corpora**: Ground-truth test suites from each repository

---

## Risk Assessment

### High Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Reference repo access blocked** | Low | High | Download and cache repos locally |
| **Evaluation pipeline too slow** | Medium | High | Parallelize across tasks, optimize Docker overhead |
| **Pass rate far below paper** | Medium | High | Start with simpler projects, iterate on prompts |

### Medium Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Test adaptation fails frequently** | Medium | Medium | Manual review of adaptations, improve heuristics |
| **LLM validation unreliable** | Medium | Medium | Increase voter count, use stronger models |
| **Token usage exceeds budget** | Medium | Medium | Implement caching early, optimize batch sizes |

### Low Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Benchmark construction incomplete** | Low | Low | Start with 3 projects, expand incrementally |
| **Profiling data noisy** | Low | Low | Run multiple trials, aggregate results |

---

## Timeline Estimate

**Total Duration**: 6-8 weeks (with parallelization)

| Epic | Duration | Dependencies |
|------|----------|--------------|
| **5.1: Benchmark Construction** | 2 weeks | None |
| **5.2: Evaluation Pipeline** | 3 weeks | 5.1 (partial) |
| **5.3: Benchmark Run** | 1 week | 5.1, 5.2, Phase 1-4 |
| **5.4: Failure Analysis** | 2 weeks | 5.3 |
| **5.5: Optimization** | 2 weeks | 5.3 (can overlap with 5.4) |

**Parallel Workstreams**:
- Weeks 1-2: Epic 5.1 (benchmark construction)
- Weeks 3-5: Epic 5.2 (evaluation pipeline) + 5.1 completion
- Week 6: Epic 5.3 (benchmark run)
- Weeks 7-8: Epic 5.4 + 5.5 (analysis and optimization in parallel)

---

## Open Questions

1. **Benchmark Scope**: Start with 3 projects or all 6? (Recommend 3 for MVP)
2. **Model Selection**: Use o3-mini for all stages or optimize per-stage? (Recommend optimization after baseline)
3. **Evaluation Frequency**: Run full benchmark weekly or on-demand? (Recommend weekly for regression tracking)
4. **Ground-Truth Test Licensing**: Are we allowed to use tests from BSD/Apache licensed projects? (Legal review required)
5. **Semantic Validation Cost**: 3-6 LLM calls per task × 1000 tasks = high cost. Acceptable? (Budget approval needed)

---

## Appendix

### A. RepoCraft Task Example

```json
{
  "id": "sklearn-linear_model-ridge-001",
  "project": "scikit-learn",
  "category": "sklearn.linear_model",
  "subcategory": "ridge",
  "description": "Implement Ridge regression with L2 regularization. The model should support alpha parameter for regularization strength, fit method for training, and predict method for inference on new data.",
  "test_code": "def test_ridge_regression():\n    from ml_lib.linear_model import Ridge\n    import numpy as np\n    \n    X = np.random.randn(100, 5)\n    y = X @ np.array([1, 2, 3, 4, 5]) + np.random.randn(100) * 0.1\n    \n    model = Ridge(alpha=1.0)\n    model.fit(X, y)\n    predictions = model.predict(X[:10])\n    \n    assert predictions.shape == (10,)\n    assert np.allclose(predictions, y[:10], atol=1.0)",
  "imports": [
    "import numpy as np"
  ],
  "auxiliary_code": "",
  "loc": 15,
  "difficulty": "medium"
}
```

### B. Evaluation Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Input: Task + Generated Repository                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Localization (Embedding Search)                   │
│  - Embed task description                                   │
│  - Embed all function signatures in repo                    │
│  - Return top-5 candidates by cosine similarity             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        [Candidates Found?] ──NO──> FAIL (Localization)
                 │ YES
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Semantic Validation (LLM Majority Vote)           │
│  - For each candidate (top-3):                              │
│    - Round 1: 3 LLM votes (YES/NO/PARTIAL)                  │
│    - Round 2: 3 more votes if no majority                   │
│  - Accept first candidate with majority YES votes           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
      [Validated Candidate?] ──NO──> FAIL (Validation)
                 │ YES
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: Execution Testing (Docker Sandbox)                │
│  - Adapt ground-truth test (rewrite imports)                │
│  - Execute in isolated Docker container                     │
│  - Check for "TEST_PASSED" output + exit code 0             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        [Test Passed?] ──NO──> FAIL (Execution)
                 │ YES
                 ▼
         ┌───────────────┐
         │  SUCCESS      │
         └───────────────┘
```

### C. Prompt Template Examples

**Localization Not Needed** (uses embeddings)

**Semantic Validation Prompt**:
```
You are a code reviewer validating whether a function implements the required functionality.

**Task Requirements**:
Implement Ridge regression with L2 regularization. The model should support alpha parameter for regularization strength, fit method for training, and predict method for inference on new data.

**Generated Function**:
```python
class Ridge:
    def __init__(self, alpha=1.0):
        self.alpha = alpha
        self.coef_ = None

    def fit(self, X, y):
        """Train the Ridge regression model."""
        import numpy as np
        n_features = X.shape[1]
        identity = np.eye(n_features)
        self.coef_ = np.linalg.solve(
            X.T @ X + self.alpha * identity,
            X.T @ y
        )
        return self

    def predict(self, X):
        """Predict using the trained model."""
        return X @ self.coef_
```

**Question**: Does this function correctly implement the required functionality?

Answer ONLY with:
- "YES" if the function implements all requirements
- "NO" if the function is missing requirements or has incorrect logic
- "PARTIAL" if the function implements some but not all requirements

Provide a brief 1-sentence justification.

Answer:
```

**Expected Response**: "YES. The function implements Ridge regression with alpha regularization, fit method using closed-form solution, and predict method for inference."

### D. References

- **ZeroRepo Paper**: [Arxiv link or internal reference]
- **RepoCraft Benchmark**: [GitHub link if open-sourced]
- **sentence-transformers**: https://www.sbert.net/
- **Docker Python SDK**: https://docker-py.readthedocs.io/

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-07 | Claude Code | Initial draft |

---

**Approval Required From**:
- [ ] Technical Lead (Architecture review)
- [ ] Product Manager (Scope and timeline)
- [ ] Legal (Ground-truth test licensing)
- [ ] Finance (LLM cost budget approval)
