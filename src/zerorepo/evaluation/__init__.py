"""ZeroRepo evaluation and benchmarking pipeline.

Provides the data models, metrics computation, and orchestration for
evaluating generated repositories against the RepoCraft benchmark suite.
"""

from zerorepo.evaluation.models import (
    ABTestResult,
    BenchmarkResult,
    BenchmarkTask,
    CodeStats,
    DifficultyLevel,
    ExecutionResult,
    FailureCategory,
    FailureReport,
    FunctionSignature,
    ProfilingData,
    RepositoryResult,
    StageFailed,
    TaskResult,
    Taxonomy,
    TaxonomyNode,
    TokenStats,
    ValidationResult,
    Vote,
    VoteResult,
)

__all__ = [
    "ABTestResult",
    "BenchmarkResult",
    "BenchmarkTask",
    "CodeStats",
    "DifficultyLevel",
    "ExecutionResult",
    "FailureCategory",
    "FailureReport",
    "FunctionSignature",
    "ProfilingData",
    "RepositoryResult",
    "StageFailed",
    "TaskResult",
    "Taxonomy",
    "TaxonomyNode",
    "TokenStats",
    "ValidationResult",
    "Vote",
    "VoteResult",
]
