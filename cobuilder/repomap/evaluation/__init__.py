"""ZeroRepo evaluation and benchmarking pipeline.

Provides the data models, metrics computation, and orchestration for
evaluating generated repositories against the RepoCraft benchmark suite.
"""

from cobuilder.repomap.evaluation.caching import (
    BatchedFunctionGenerator,
    EmbeddingCache,
    LLMResponseCache,
)
from cobuilder.repomap.evaluation.categorizer import Categorizer
from cobuilder.repomap.evaluation.execution_testing import ExecutionTester, SandboxProtocol
from cobuilder.repomap.evaluation.failure_analysis import FailureAnalyzer, PromptABTest
from cobuilder.repomap.evaluation.localization import FunctionLocalizer
from cobuilder.repomap.evaluation.metrics import MetricsCalculator
from cobuilder.repomap.evaluation.models import (
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
from cobuilder.repomap.evaluation.pipeline import EvaluationPipeline
from cobuilder.repomap.evaluation.profiling import ProfilingCollector
from cobuilder.repomap.evaluation.report import ReportGenerator
from cobuilder.repomap.evaluation.semantic_validation import LLMClient, SemanticValidator
from cobuilder.repomap.evaluation.test_filter import TestFilter

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
