"""Pydantic data models for the ZeroRepo evaluation and benchmarking pipeline.

Defines the core data structures for:
- Benchmark tasks from the RepoCraft benchmark suite
- Function signatures extracted from generated repositories
- Evaluation results (localization, validation, execution)
- Aggregated repository-level and benchmark-level results
- Profiling and token usage statistics
- Taxonomy structures for task categorisation
- Failure analysis and A/B testing models
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DifficultyLevel(str, Enum):
    """Difficulty classification for benchmark tasks."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class VoteResult(str, Enum):
    """Possible outcomes of a single LLM validation vote."""

    YES = "YES"
    NO = "NO"
    PARTIAL = "PARTIAL"


class StageFailed(str, Enum):
    """Pipeline stage at which a task failed."""

    LOCALIZATION = "localization"
    VALIDATION = "validation"
    EXECUTION = "execution"


class FailureCategory(str, Enum):
    """High-level category for failure analysis."""

    PLANNING = "planning"
    GENERATION = "generation"
    LOCALIZATION = "localization"
    VALIDATION = "validation"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Benchmark Task Models
# ---------------------------------------------------------------------------


class BenchmarkTask(BaseModel):
    """A single evaluation task from the RepoCraft benchmark.

    Each task maps a natural-language description to a ground-truth test
    function that can be used to validate a generated repository.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: str = Field(
        ...,
        min_length=1,
        description="Unique task ID e.g. sklearn-linear_model-ridge-001",
    )
    project: str = Field(
        ...,
        min_length=1,
        description="Source project name e.g. scikit-learn",
    )
    category: str = Field(
        ...,
        min_length=1,
        description="Module category e.g. sklearn.linear_model",
    )
    subcategory: str = Field(
        default="",
        description="Subcategory e.g. ridge",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Natural language task description",
    )
    test_code: str = Field(
        ...,
        min_length=1,
        description="Ground-truth test function code",
    )
    imports: list[str] = Field(
        default_factory=list,
        description="Required import statements",
    )
    fixtures: list[str] = Field(
        default_factory=list,
        description="Test fixtures needed",
    )
    auxiliary_code: str = Field(
        default="",
        description="Helper code for test execution",
    )
    loc: int = Field(
        default=0,
        ge=0,
        description="Lines of code in test",
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM,
        description="Difficulty classification for the task",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata for this task",
    )


# ---------------------------------------------------------------------------
# Function Signature Models
# ---------------------------------------------------------------------------


class FunctionSignature(BaseModel):
    """A function extracted from a generated repository.

    Used during the localisation stage to match benchmark tasks
    to candidate functions in the generated codebase.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    name: str = Field(
        ...,
        min_length=1,
        description="Function name",
    )
    module: str = Field(
        ...,
        min_length=1,
        description="Dotted module path e.g. ml_lib.linear_model.ridge",
    )
    signature: str = Field(
        ...,
        min_length=1,
        description="Full function signature e.g. def ridge_regression(X, y, alpha=1.0)",
    )
    docstring: str = Field(
        default="",
        description="Function docstring",
    )
    file_path: str = Field(
        ...,
        min_length=1,
        description="File path relative to repo root",
    )
    start_line: int = Field(
        default=0,
        ge=0,
        description="Start line number of the function",
    )
    end_line: int = Field(
        default=0,
        ge=0,
        description="End line number of the function",
    )
    body: str = Field(
        default="",
        description="Full function body source code",
    )


# ---------------------------------------------------------------------------
# Evaluation Result Models
# ---------------------------------------------------------------------------


class Vote(BaseModel):
    """A single LLM validation vote.

    During semantic validation, multiple LLM calls vote on whether a
    candidate function satisfies the benchmark task requirements.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    result: VoteResult = Field(
        ...,
        description="Vote outcome",
    )
    justification: str = Field(
        default="",
        description="Reasoning behind the vote",
    )
    model: str = Field(
        default="",
        description="LLM model used for this vote",
    )
    round_num: int = Field(
        default=1,
        ge=1,
        description="Voting round number",
    )


class ValidationResult(BaseModel):
    """Result from the semantic validation stage.

    Aggregates multiple LLM votes to determine whether a candidate
    function semantically matches the benchmark task.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    passed: bool = Field(
        ...,
        description="Whether semantic validation passed",
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level: high, medium, or low",
    )
    votes: list[Vote] = Field(
        default_factory=list,
        description="Individual LLM votes",
    )
    candidate_function: Optional[str] = Field(
        default=None,
        description="Name of the candidate function evaluated",
    )


class ExecutionResult(BaseModel):
    """Result from the test execution stage.

    Captures the outcome of running a benchmark test against a
    candidate function inside the sandbox.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    passed: bool = Field(
        ...,
        description="Whether the test execution passed",
    )
    exit_code: int = Field(
        default=-1,
        description="Process exit code (0 = success)",
    )
    stdout: str = Field(
        default="",
        description="Standard output captured from execution",
    )
    stderr: str = Field(
        default="",
        description="Standard error captured from execution",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed",
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Execution duration in milliseconds",
    )


class TaskResult(BaseModel):
    """Result for a single evaluation task through the pipeline.

    Tracks progression through the three pipeline stages:
    localisation -> semantic validation -> test execution.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    task_id: str = Field(
        ...,
        min_length=1,
        description="Benchmark task identifier",
    )
    localized: bool = Field(
        default=False,
        description="Whether a candidate function was found",
    )
    validated: bool = Field(
        default=False,
        description="Whether semantic validation passed",
    )
    passed: bool = Field(
        default=False,
        description="Whether test execution passed",
    )
    stage_failed: Optional[StageFailed] = Field(
        default=None,
        description="Pipeline stage where failure occurred",
    )
    candidate_function: Optional[str] = Field(
        default=None,
        description="Name of the matched candidate function",
    )
    candidate_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Similarity score of the candidate match",
    )
    validation_result: Optional[ValidationResult] = Field(
        default=None,
        description="Detailed semantic validation result",
    )
    execution_result: Optional[ExecutionResult] = Field(
        default=None,
        description="Detailed test execution result",
    )
    execution_error: Optional[str] = Field(
        default=None,
        description="Error message if execution stage errored",
    )


# ---------------------------------------------------------------------------
# Repository-Level Result Models
# ---------------------------------------------------------------------------


class RepositoryResult(BaseModel):
    """Aggregated result for all tasks against a single generated repository.

    Provides summary statistics (pass rate, coverage, novelty) as well
    as individual per-task results.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    project_name: str = Field(
        ...,
        min_length=1,
        description="Name of the evaluated project",
    )
    total_tasks: int = Field(
        ...,
        ge=0,
        description="Total number of benchmark tasks evaluated",
    )
    localized: int = Field(
        default=0,
        ge=0,
        description="Number of tasks that found a candidate function",
    )
    validated: int = Field(
        default=0,
        ge=0,
        description="Number of tasks that passed semantic validation",
    )
    passed: int = Field(
        default=0,
        ge=0,
        description="Number of tasks that passed test execution",
    )
    coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of categories with at least one passed test",
    )
    novelty: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of categories outside the reference taxonomy",
    )
    task_results: list[TaskResult] = Field(
        default_factory=list,
        description="Per-task evaluation results",
    )

    @property
    def pass_rate(self) -> float:
        """Fraction of tasks that passed test execution."""
        return self.passed / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def voting_rate(self) -> float:
        """Fraction of tasks that passed semantic validation."""
        return self.validated / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def localization_rate(self) -> float:
        """Fraction of tasks that found a candidate function."""
        return self.localized / self.total_tasks if self.total_tasks > 0 else 0.0


# ---------------------------------------------------------------------------
# Profiling and Statistics Models
# ---------------------------------------------------------------------------


class CodeStats(BaseModel):
    """Statistics about generated code."""

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    files: int = Field(
        default=0,
        ge=0,
        description="Number of source files",
    )
    loc: int = Field(
        default=0,
        ge=0,
        description="Total lines of code",
    )
    estimated_tokens: int = Field(
        default=0,
        ge=0,
        description="Estimated token count",
    )


class TokenStats(BaseModel):
    """Token usage statistics for a pipeline stage."""

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Number of prompt tokens consumed",
    )
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Number of completion tokens generated",
    )
    total_calls: int = Field(
        default=0,
        ge=0,
        description="Number of LLM API calls made",
    )

    @property
    def total_tokens(self) -> int:
        """Total tokens (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens


class ProfilingData(BaseModel):
    """Profiling data for a benchmark run.

    Tracks token usage per stage, wall-clock timings, and
    derived cost estimates.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    stage_tokens: dict[str, TokenStats] = Field(
        default_factory=dict,
        description="Token usage keyed by pipeline stage name",
    )
    stage_timings: dict[str, float] = Field(
        default_factory=dict,
        description="Wall-clock seconds keyed by pipeline stage name",
    )
    total_duration_s: float = Field(
        default=0.0,
        ge=0.0,
        description="Total benchmark duration in seconds",
    )

    @property
    def total_tokens(self) -> int:
        """Sum of all tokens across all stages."""
        return sum(s.total_tokens for s in self.stage_tokens.values())

    @property
    def total_cost_usd(self) -> float:
        """Rough cost estimate at $10 per million tokens."""
        return self.total_tokens * 10 / 1_000_000


# ---------------------------------------------------------------------------
# Benchmark Result Models
# ---------------------------------------------------------------------------


class BenchmarkResult(BaseModel):
    """Complete result for one project's benchmark run.

    Combines the evaluation result with profiling data and
    metadata about the generated repository.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    project: str = Field(
        ...,
        min_length=1,
        description="Source project name",
    )
    paraphrased_name: str = Field(
        default="",
        description="Paraphrased project name used during generation",
    )
    evaluation: RepositoryResult = Field(
        ...,
        description="Evaluation results for this project",
    )
    profiling: ProfilingData = Field(
        default_factory=ProfilingData,
        description="Profiling and cost data for the run",
    )
    repo_path: str = Field(
        default="",
        description="Path to the generated repository on disk",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the benchmark was run",
    )


# ---------------------------------------------------------------------------
# Taxonomy Models
# ---------------------------------------------------------------------------


class TaxonomyNode(BaseModel):
    """A node in the hierarchical taxonomy tree.

    The taxonomy organises benchmark tasks by project, module,
    and subcategory.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    name: str = Field(
        ...,
        min_length=1,
        description="Taxonomy node name",
    )
    count: int = Field(
        default=0,
        ge=0,
        description="Number of tasks at this level",
    )
    children: dict[str, TaxonomyNode] = Field(
        default_factory=dict,
        description="Child nodes keyed by name",
    )


class Taxonomy(BaseModel):
    """Hierarchical taxonomy of benchmark tasks.

    Provides a tree structure for navigating benchmark tasks
    by project and category.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    roots: dict[str, TaxonomyNode] = Field(
        default_factory=dict,
        description="Root taxonomy nodes keyed by project name",
    )
    total_tasks: int = Field(
        default=0,
        ge=0,
        description="Total number of tasks in the taxonomy",
    )
    total_categories: int = Field(
        default=0,
        ge=0,
        description="Total number of unique categories",
    )


# ---------------------------------------------------------------------------
# Failure Analysis Models
# ---------------------------------------------------------------------------


class FailureReport(BaseModel):
    """Comprehensive failure analysis report.

    Categorises failures, provides representative samples,
    and generates actionable recommendations.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    total_failures: int = Field(
        ...,
        ge=0,
        description="Total number of failures analysed",
    )
    category_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Failure count per category",
    )
    samples: dict[str, list[TaskResult]] = Field(
        default_factory=dict,
        description="Representative failure samples per category",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations based on failure patterns",
    )


# ---------------------------------------------------------------------------
# A/B Testing Models
# ---------------------------------------------------------------------------


class ABTestResult(BaseModel):
    """Result of a prompt A/B test.

    Compares a baseline prompt against a variant and reports
    statistical significance.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    baseline_pass_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pass rate using the baseline prompt",
    )
    variant_pass_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pass rate using the variant prompt",
    )
    delta: float = Field(
        default=0.0,
        description="Difference (variant - baseline)",
    )
    p_value: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Statistical p-value for the difference",
    )
    significant: bool = Field(
        default=False,
        description="Whether the difference is statistically significant",
    )
    sample_size: int = Field(
        default=0,
        ge=0,
        description="Number of tasks in each group",
    )
    recommendation: str = Field(
        default="KEEP BASELINE",
        description="Recommendation based on the test outcome",
    )
