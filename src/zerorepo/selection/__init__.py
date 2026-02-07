"""ZeroRepo Explore-Exploit Subtree Selection Service.

This package implements Epic 2.2 of PRD-RPG-P2-001 (Explore-Exploit Subtree
Selection), providing:

- :class:`ExploitationRetriever` -- Vector search with LLM query augmentation (Task 2.2.1)
- :class:`ExploitationConfig` -- Configuration for the exploitation retriever
- :class:`RetrievalResult` -- Ranked retrieval result with augmented queries
- :class:`CoverageTracker` -- Bit-vector coverage tracking (Task 2.2.2)
- :class:`ExplorationStrategy` -- Gap-based exploratory query generation (Task 2.2.2)
- :class:`ExplorationConfig` -- Configuration for the exploration strategy
- :class:`ExplorationResult` -- Result of an exploration round
- :class:`CoverageStats` -- Coverage statistics snapshot
- :class:`DiversitySampler` -- Rejection sampling with cosine similarity (Task 2.2.3)
- :class:`DiversityConfig` -- Configuration for diversity sampling
- :class:`DiversityMetrics` -- Diversity metrics for selected features
- :class:`SamplingResult` -- Result of diversity-aware sampling
- :class:`LLMFilter` -- LLM-based feature relevance filtering (Task 2.2.4)
- :class:`LLMFilterConfig` -- Configuration for LLM filtering
- :class:`FilterResult` -- Result of LLM filtering
- :class:`ConvergenceMonitor` -- Iteration convergence tracking (Task 2.2.5)
- :class:`ConvergenceConfig` -- Configuration for convergence monitoring
- :class:`ConvergenceSnapshot` -- Single iteration convergence snapshot
- :class:`ExploreExploitOrchestrator` -- Main selection loop (Task 2.2.6)
- :class:`OrchestratorConfig` -- Configuration for the orchestrator
- :class:`OrchestrationResult` -- Result of the orchestration loop
- :class:`IterationSnapshot` -- Per-iteration data snapshot
"""

from zerorepo.selection.convergence import (
    ConvergenceConfig,
    ConvergenceMonitor,
    ConvergenceSnapshot,
)
from zerorepo.selection.diversity_sampler import (
    DiversityConfig,
    DiversityMetrics,
    DiversitySampler,
    SamplingResult,
)
from zerorepo.selection.exploitation import (
    ExploitationConfig,
    ExploitationRetriever,
    RetrievalResult,
)
from zerorepo.selection.exploration import (
    CoverageStats,
    CoverageTracker,
    ExplorationConfig,
    ExplorationResult,
    ExplorationStrategy,
)
from zerorepo.selection.llm_filter import (
    FilterResult,
    LLMFilter,
    LLMFilterConfig,
)
from zerorepo.selection.orchestrator import (
    ExploreExploitOrchestrator,
    IterationSnapshot,
    OrchestrationResult,
    OrchestratorConfig,
)

__all__ = [
    "ConvergenceConfig",
    "ConvergenceMonitor",
    "ConvergenceSnapshot",
    "CoverageStats",
    "CoverageTracker",
    "DiversityConfig",
    "DiversityMetrics",
    "DiversitySampler",
    "ExploitationConfig",
    "ExploitationRetriever",
    "ExplorationConfig",
    "ExplorationResult",
    "ExploreExploitOrchestrator",
    "ExplorationStrategy",
    "FilterResult",
    "IterationSnapshot",
    "LLMFilter",
    "LLMFilterConfig",
    "OrchestrationResult",
    "OrchestratorConfig",
    "RetrievalResult",
    "SamplingResult",
]
