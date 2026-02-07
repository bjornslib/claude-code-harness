"""ZeroRepo evaluation and benchmarking pipeline.

Provides the data models, metrics computation, and orchestration for
evaluating generated repositories against the RepoCraft benchmark suite.
"""

from zerorepo.evaluation.caching import (
    BatchedFunctionGenerator,
    EmbeddingCache,
    LLMResponseCache,
)
from zerorepo.evaluation.categorizer import Categorizer
from zerorepo.evaluation.execution_testing import ExecutionTester, SandboxProtocol
from zerorepo.evaluation.failure_analysis import FailureAnalyzer, PromptABTest
from zerorepo.evaluation.localization import FunctionLocalizer
from zerorepo.evaluation.metrics import MetricsCalculator
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
from zerorepo.evaluation.pipeline import EvaluationPipeline
from zerorepo.evaluation.profiling import ProfilingCollector
from zerorepo.evaluation.report import ReportGenerator
from zerorepo.evaluation.semantic_validation import LLMClient, SemanticValidator
from zerorepo.evaluation.test_filter import TestFilter

__all__ = [
    "ABTestResult",
    "BatchedFunctionGenerator",
    "BenchmarkResult",
    "BenchmarkTask",
    "Categorizer",
    "CodeStats",
    "DifficultyLevel",
    "EmbeddingCache",
    "EvaluationPipeline",
    "ExecutionResult",
    "ExecutionTester",
    "FailureAnalyzer",
    "FailureCategory",
    "FailureReport",
    "FunctionLocalizer",
    "FunctionSignature",
    "LLMClient",
    "LLMResponseCache",
    "MetricsCalculator",
    "ProfilingCollector",
    "ProfilingData",
    "PromptABTest",
    "ReportGenerator",
    "RepositoryResult",
    "SandboxProtocol",
    "SemanticValidator",
    "StageFailed",
    "TaskResult",
    "Taxonomy",
    "TaxonomyNode",
    "TestFilter",
    "TokenStats",
    "ValidationResult",
    "Vote",
    "VoteResult",
]
