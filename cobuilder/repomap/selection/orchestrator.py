"""Explore-Exploit Orchestrator – main selection loop (Algorithm 2).

Implements Task 2.2.6 of PRD-RPG-P2-001 (Epic 2.2: Explore-Exploit Subtree
Selection). Integrates all five Epic 2.2 components into a single orchestration
loop that alternates between exploitation (vector search), exploration
(coverage-gap queries), diversity sampling, LLM filtering, and convergence
monitoring.

Algorithm 2 (from PRD)::

    1. F = ∅
    2. FOR i = 1 to N:
    3.   // Exploitation
    4.   keywords = LLM_augment(U)
    5.   candidates_exploit = O.search(keywords, top_k=50)
    6.
    7.   // Exploration
    8.   uncovered = O.branches \\ visited_branches
    9.   IF len(uncovered) > 0:
   10.     exploratory_query = LLM_explore(uncovered)
   11.     candidates_explore = O.search(exploratory_query, top_k=20)
   12.   ELSE:
   13.     candidates_explore = ∅
   14.
   15.   // Diversity sampling
   16.   candidates = candidates_exploit ∪ candidates_explore
   17.   f = diversity_sample(candidates, F, θ=0.85)
   18.   IF f is not None:
   19.     F = F ∪ {f}
   20.     visited_branches.add(f.branch)
   21.
   22.   // LLM filtering (every 5 iterations)
   23.   IF i % 5 == 0:
   24.     F = LLM_filter(F, U)
   25.
   26.   // Convergence check
   27.   IF coverage_plateau(F, window=5):
   28.     BREAK
   29.
   30. RETURN F

Example::

    from cobuilder.repomap.selection.orchestrator import (
        ExploreExploitOrchestrator,
        OrchestratorConfig,
    )
    from cobuilder.repomap.ontology.backend import OntologyBackend
    from cobuilder.repomap.llm.gateway import LLMGateway

    store = build_store(...)
    gateway = LLMGateway()

    orch = ExploreExploitOrchestrator(
        store=store,
        llm_gateway=gateway,
    )
    result = orch.run(spec_description="Build a real-time chat app")
    print(f"Selected {result.count} features in {result.iterations_run} iterations")
    print(f"Diversity score: {result.diversity_metrics.silhouette_score:.3f}")
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from cobuilder.repomap.llm.gateway import LLMGateway
from cobuilder.repomap.llm.models import ModelTier
from cobuilder.repomap.ontology.backend import OntologyBackend
from cobuilder.repomap.ontology.models import FeatureNode, FeaturePath
from cobuilder.repomap.selection.convergence import (
    ConvergenceConfig,
    ConvergenceMonitor,
    ConvergenceSummary,
)
from cobuilder.repomap.selection.diversity_sampler import (
    DiversityConfig,
    DiversityMetrics,
    DiversitySampler,
    SamplingResult,
)
from cobuilder.repomap.selection.exploitation import (
    ExploitationConfig,
    ExploitationRetriever,
    RetrievalResult,
)
from cobuilder.repomap.selection.exploration import (
    CoverageTracker,
    ExplorationConfig,
    ExplorationResult,
    ExplorationStrategy,
)
from cobuilder.repomap.selection.llm_filter import (
    FilterResult,
    LLMFilter,
    LLMFilterConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class OrchestratorConfig(BaseModel):
    """Configuration for the ExploreExploitOrchestrator.

    Attributes:
        max_iterations: Maximum number of selection iterations.
        exploit_top_k: Number of results per exploitation query.
        diversity_threshold: Cosine similarity threshold for rejection sampling.
        min_avg_distance: Minimum average pairwise distance for the final
            selection to pass diversity checks.
        features_per_iteration: How many diverse features to select per
            iteration from the merged candidate pool.
        filter_interval: Run LLM filtering every this many iterations.
        enable_exploration: Whether to use exploration phase (coverage-gap
            queries). When False, only exploitation is used.
        enable_filtering: Whether to use LLM filtering at intervals.
        enable_convergence: Whether to enable convergence-based early stopping.
        exploitation_config: Configuration for the exploitation retriever.
        exploration_config: Configuration for the exploration strategy.
        diversity_config: Configuration for the diversity sampler.
        filter_config: Configuration for the LLM filter.
        convergence_config: Configuration for the convergence monitor.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    max_iterations: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum selection iterations (PRD default: 30)",
    )
    exploit_top_k: int = Field(
        default=50,
        ge=5,
        le=200,
        description="Results per exploitation query (PRD default: 50)",
    )
    diversity_threshold: float = Field(
        default=0.85,
        gt=0.0,
        le=1.0,
        description="Cosine similarity threshold for rejection (PRD: 0.85)",
    )
    min_avg_distance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum avg pairwise distance for final selection",
    )
    features_per_iteration: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Features to select per iteration via diversity sampling",
    )
    filter_interval: int = Field(
        default=5,
        ge=1,
        le=30,
        description="LLM filtering every N iterations (PRD default: 5)",
    )
    enable_exploration: bool = Field(
        default=True,
        description="Enable exploration phase for coverage gaps",
    )
    enable_filtering: bool = Field(
        default=True,
        description="Enable LLM filtering at intervals",
    )
    enable_convergence: bool = Field(
        default=True,
        description="Enable convergence-based early stopping",
    )

    # Sub-component configs (optional overrides)
    exploitation_config: ExploitationConfig = Field(
        default_factory=ExploitationConfig,
    )
    exploration_config: ExplorationConfig = Field(
        default_factory=ExplorationConfig,
    )
    diversity_config: DiversityConfig = Field(
        default_factory=lambda: DiversityConfig(
            similarity_threshold=0.85,
            min_avg_distance=0.5,
        ),
    )
    filter_config: LLMFilterConfig = Field(
        default_factory=LLMFilterConfig,
    )
    convergence_config: ConvergenceConfig = Field(
        default_factory=ConvergenceConfig,
    )


# ---------------------------------------------------------------------------
# Iteration Snapshot
# ---------------------------------------------------------------------------


class IterationSnapshot(BaseModel):
    """A snapshot of a single orchestration iteration.

    Attributes:
        iteration: The iteration number (1-based).
        exploit_count: Number of exploitation candidates retrieved.
        explore_count: Number of exploration candidates retrieved.
        candidates_merged: Total unique candidates after merging.
        selected_count: Number of features selected this iteration.
        total_selected: Cumulative features after this iteration.
        coverage: Coverage ratio at this iteration.
        coverage_delta: Change in coverage from previous iteration.
        duration_ms: Wall-clock time for this iteration in milliseconds.
        filtered: Whether LLM filtering was applied.
        converged: Whether convergence was detected.
    """

    model_config = ConfigDict(frozen=True)

    iteration: int = Field(ge=1)
    exploit_count: int = Field(default=0, ge=0)
    explore_count: int = Field(default=0, ge=0)
    candidates_merged: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    total_selected: int = Field(default=0, ge=0)
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    coverage_delta: float = Field(default=0.0)
    duration_ms: float = Field(default=0.0, ge=0.0)
    filtered: bool = Field(default=False)
    converged: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Orchestration Result
# ---------------------------------------------------------------------------


class OrchestrationResult(BaseModel):
    """Result of the explore-exploit orchestration.

    Attributes:
        selected: Final list of selected diverse FeaturePaths.
        iterations_run: Number of iterations actually executed.
        total_duration_ms: Total wall-clock time in milliseconds.
        convergence_summary: Summary from the convergence monitor.
        diversity_metrics: Final diversity metrics for the selection.
        filter_result: Result from the last LLM filtering pass (if any).
        iteration_history: Per-iteration snapshots.
        stop_reason: Why the orchestration loop stopped.
        metadata: Additional orchestration metadata.
    """

    model_config = ConfigDict(frozen=True)

    selected: list[FeaturePath] = Field(
        default_factory=list,
        description="Final selected feature paths",
    )
    iterations_run: int = Field(
        default=0, ge=0, description="Iterations executed"
    )
    total_duration_ms: float = Field(
        default=0.0, ge=0.0, description="Total duration (ms)"
    )
    convergence_summary: ConvergenceSummary | None = Field(
        default=None, description="Convergence monitoring summary"
    )
    diversity_metrics: DiversityMetrics | None = Field(
        default=None, description="Final diversity metrics"
    )
    filter_result: FilterResult | None = Field(
        default=None, description="Last LLM filter result"
    )
    iteration_history: list[IterationSnapshot] = Field(
        default_factory=list, description="Per-iteration snapshots"
    )
    stop_reason: str = Field(
        default="max_iterations", description="Reason the loop stopped"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extra metadata"
    )

    @property
    def count(self) -> int:
        """Number of selected features."""
        return len(self.selected)

    def to_json(self, indent: int = 2) -> str:
        """Serialize selected features to JSON.

        Returns:
            JSON string with selected feature data.
        """
        features = []
        for path in self.selected:
            features.append({
                "id": path.leaf.id,
                "name": path.leaf.name,
                "level": path.leaf.level,
                "score": path.score,
                "path": [n.name for n in path.nodes],
                "tags": path.leaf.tags,
            })
        return json.dumps(
            {
                "features": features,
                "count": self.count,
                "iterations_run": self.iterations_run,
                "stop_reason": self.stop_reason,
                "diversity_score": (
                    self.diversity_metrics.silhouette_score
                    if self.diversity_metrics
                    else None
                ),
                "final_coverage": (
                    self.convergence_summary.final_coverage
                    if self.convergence_summary
                    else None
                ),
            },
            indent=indent,
        )


# ---------------------------------------------------------------------------
# Explore-Exploit Orchestrator
# ---------------------------------------------------------------------------


class ExploreExploitOrchestrator:
    """Main orchestration loop for explore-exploit subtree selection.

    Integrates exploitation retrieval, exploration strategy, diversity
    sampling, LLM filtering, and convergence monitoring into a unified
    iterative selection pipeline (Algorithm 2 from PRD-RPG-P2-001).

    Args:
        store: An initialized OntologyBackend.
        llm_gateway: An LLMGateway for augmented queries and filtering.
        config: Optional orchestrator configuration.

    Example::

        orch = ExploreExploitOrchestrator(
            store=chroma_store,
            llm_gateway=gateway,
        )
        result = orch.run(
            spec_description="Build a real-time chat app with React",
            spec_languages=["TypeScript", "Python"],
        )
        # Export as JSON
        with open("features.json", "w") as f:
            f.write(result.to_json())
    """

    def __init__(
        self,
        store: OntologyBackend,
        llm_gateway: LLMGateway | None = None,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self._store = store
        self._llm = llm_gateway
        self._config = config or OrchestratorConfig()

        # Build sub-components
        self._retriever = ExploitationRetriever(
            store=store,
            llm_gateway=llm_gateway,
            config=self._config.exploitation_config,
        )
        self._coverage = CoverageTracker()
        self._explorer = ExplorationStrategy(
            coverage=self._coverage,
            store=store,
            llm_gateway=llm_gateway,
            config=self._config.exploration_config,
        )
        self._sampler = DiversitySampler(
            config=DiversityConfig(
                similarity_threshold=self._config.diversity_threshold,
                min_avg_distance=self._config.min_avg_distance,
            ),
        )
        self._filter = LLMFilter(
            llm_gateway=llm_gateway,
            config=self._config.filter_config,
        )
        self._monitor = ConvergenceMonitor(
            config=self._config.convergence_config,
        )

    @property
    def store(self) -> OntologyBackend:
        """Return the ontology backend."""
        return self._store

    @property
    def config(self) -> OrchestratorConfig:
        """Return the orchestrator configuration."""
        return self._config

    @property
    def coverage(self) -> CoverageTracker:
        """Return the coverage tracker."""
        return self._coverage

    @property
    def monitor(self) -> ConvergenceMonitor:
        """Return the convergence monitor."""
        return self._monitor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        spec_description: str,
        spec_languages: list[str] | None = None,
        spec_frameworks: list[str] | None = None,
    ) -> OrchestrationResult:
        """Execute the explore-exploit selection loop.

        Implements Algorithm 2 from the PRD. Iterates through exploitation,
        exploration, diversity sampling, periodic LLM filtering, and
        convergence checks.

        Args:
            spec_description: Natural language project specification.
            spec_languages: Optional target programming languages.
            spec_frameworks: Optional framework preferences.

        Returns:
            An OrchestrationResult with selected features and metadata.

        Raises:
            ValueError: If spec_description is empty.
        """
        if not spec_description or not spec_description.strip():
            raise ValueError("spec_description must not be empty")

        spec_description = spec_description.strip()
        start_time = time.monotonic()

        # Initialize state
        selected: list[FeaturePath] = []
        selected_ids: set[str] = set()
        iteration_history: list[IterationSnapshot] = []
        last_filter_result: FilterResult | None = None
        stop_reason = "max_iterations"

        # Seed coverage tracker from store statistics
        self._seed_coverage_tracker()

        logger.info(
            "ExploreExploitOrchestrator: starting with max_iterations=%d, "
            "spec=%r",
            self._config.max_iterations,
            spec_description[:80],
        )

        for i in range(1, self._config.max_iterations + 1):
            iter_start = time.monotonic()

            # Phase 1: Exploitation
            exploit_paths = self._exploitation_phase(
                spec_description=spec_description,
                spec_languages=spec_languages,
                spec_frameworks=spec_frameworks,
            )

            # Phase 2: Exploration (if enabled)
            explore_paths: list[FeaturePath] = []
            if self._config.enable_exploration:
                explore_paths = self._exploration_phase()

            # Merge candidates (de-duplicate by leaf ID)
            merged = self._merge_candidates(
                exploit_paths, explore_paths, selected_ids
            )

            # Phase 3: Diversity sampling from merged candidates
            newly_selected = self._diversity_phase(
                candidates=merged,
                already_selected=selected,
                n=self._config.features_per_iteration,
            )

            # Add newly selected to cumulative set
            for path in newly_selected:
                if path.leaf.id not in selected_ids:
                    selected.append(path)
                    selected_ids.add(path.leaf.id)
                    # Mark visited in coverage tracker
                    self._coverage.mark_paths_visited([path])

            # Phase 4: LLM filtering (every filter_interval iterations)
            filtered_this_iter = False
            if (
                self._config.enable_filtering
                and i % self._config.filter_interval == 0
                and selected
            ):
                selected, selected_ids, last_filter_result = (
                    self._filtering_phase(
                        selected=selected,
                        spec_description=spec_description,
                        spec_languages=spec_languages,
                        spec_frameworks=spec_frameworks,
                    )
                )
                filtered_this_iter = True

            # Phase 5: Convergence check
            coverage_ratio = self._coverage.coverage_ratio
            self._monitor.record(
                iteration=i,
                coverage=min(coverage_ratio, 1.0),
                newly_selected=len(newly_selected),
            )

            iter_duration = (time.monotonic() - iter_start) * 1000
            converged = self._monitor.should_stop if self._config.enable_convergence else False

            snapshot = IterationSnapshot(
                iteration=i,
                exploit_count=len(exploit_paths),
                explore_count=len(explore_paths),
                candidates_merged=len(merged),
                selected_count=len(newly_selected),
                total_selected=len(selected),
                coverage=min(coverage_ratio, 1.0),
                coverage_delta=self._monitor._history[-1].coverage_delta if self._monitor._history else 0.0,
                duration_ms=iter_duration,
                filtered=filtered_this_iter,
                converged=converged,
            )
            iteration_history.append(snapshot)

            logger.info(
                "Iteration %d: exploit=%d, explore=%d, merged=%d, "
                "selected=%d, total=%d, coverage=%.3f, dur=%.0fms",
                i,
                len(exploit_paths),
                len(explore_paths),
                len(merged),
                len(newly_selected),
                len(selected),
                coverage_ratio,
                iter_duration,
            )

            # Check convergence for early stopping
            if self._config.enable_convergence and self._monitor.should_stop:
                if self._monitor.has_converged:
                    stop_reason = "converged"
                elif self._monitor.has_plateaued:
                    stop_reason = "plateau"
                else:
                    stop_reason = "max_iterations"
                logger.info(
                    "Early stopping at iteration %d: %s", i, stop_reason
                )
                break

        # Compute final diversity metrics
        embeddings = [
            path.leaf.embedding or [0.0] * 384
            for path in selected
        ]
        final_diversity = self._sampler.compute_metrics(
            embeddings, num_rejected=0
        )

        total_duration = (time.monotonic() - start_time) * 1000

        result = OrchestrationResult(
            selected=selected,
            iterations_run=len(iteration_history),
            total_duration_ms=total_duration,
            convergence_summary=self._monitor.get_summary(),
            diversity_metrics=final_diversity,
            filter_result=last_filter_result,
            iteration_history=iteration_history,
            stop_reason=stop_reason,
            metadata={
                "spec_description": spec_description[:200],
                "spec_languages": spec_languages,
                "spec_frameworks": spec_frameworks,
                "config": {
                    "max_iterations": self._config.max_iterations,
                    "exploit_top_k": self._config.exploit_top_k,
                    "diversity_threshold": self._config.diversity_threshold,
                    "features_per_iteration": self._config.features_per_iteration,
                    "filter_interval": self._config.filter_interval,
                },
            },
        )

        logger.info(
            "ExploreExploitOrchestrator: completed in %.0fms, "
            "iterations=%d, selected=%d, stop=%s, diversity=%.3f",
            total_duration,
            result.iterations_run,
            result.count,
            stop_reason,
            final_diversity.silhouette_score,
        )

        return result

    # ------------------------------------------------------------------
    # Internal phases
    # ------------------------------------------------------------------

    def _seed_coverage_tracker(self) -> None:
        """Seed the coverage tracker with ontology statistics.

        Attempts to register top-level categories from the store's
        statistics so the coverage tracker has nodes to track against.
        Falls back gracefully if the store doesn't provide stats.
        """
        try:
            stats = self._store.get_statistics()
            if hasattr(stats, "total_features") and stats.total_features > 0:
                logger.debug(
                    "Ontology stats: %d features, %d categories",
                    stats.total_features,
                    getattr(stats, "total_categories", 0),
                )
        except Exception as exc:
            logger.debug("Could not seed coverage tracker: %s", exc)

    def _exploitation_phase(
        self,
        spec_description: str,
        spec_languages: list[str] | None = None,
        spec_frameworks: list[str] | None = None,
    ) -> list[FeaturePath]:
        """Execute the exploitation phase: vector search with LLM augmentation.

        Args:
            spec_description: Project specification.
            spec_languages: Optional languages.
            spec_frameworks: Optional frameworks.

        Returns:
            List of retrieved FeaturePaths.
        """
        try:
            result = self._retriever.retrieve_for_spec(
                description=spec_description,
                languages=spec_languages,
                frameworks=spec_frameworks,
                top_k=self._config.exploit_top_k,
            )
            # Register nodes in coverage tracker
            for path in result.paths:
                self._coverage.mark_paths_visited(result.paths)
            return result.paths
        except Exception as exc:
            logger.warning("Exploitation phase failed: %s", exc)
            return []

    def _exploration_phase(self) -> list[FeaturePath]:
        """Execute the exploration phase: coverage-gap targeted queries.

        Returns:
            List of exploration-discovered FeaturePaths.
        """
        try:
            result = self._explorer.explore_round()
            return result.new_paths if hasattr(result, "new_paths") else []
        except Exception as exc:
            logger.warning("Exploration phase failed: %s", exc)
            return []

    def _merge_candidates(
        self,
        exploit_paths: list[FeaturePath],
        explore_paths: list[FeaturePath],
        already_selected_ids: set[str],
    ) -> list[FeaturePath]:
        """Merge and de-duplicate candidates from exploitation and exploration.

        Removes features already in the selected set. Keeps the
        highest-scoring version when duplicates appear.

        Args:
            exploit_paths: Paths from exploitation.
            explore_paths: Paths from exploration.
            already_selected_ids: IDs of already-selected features.

        Returns:
            De-duplicated list of candidate FeaturePaths.
        """
        best: dict[str, FeaturePath] = {}

        for path in exploit_paths + explore_paths:
            leaf_id = path.leaf.id
            if leaf_id in already_selected_ids:
                continue
            if leaf_id not in best or path.score > best[leaf_id].score:
                best[leaf_id] = path

        # Sort by score descending
        return sorted(best.values(), key=lambda p: p.score, reverse=True)

    def _diversity_phase(
        self,
        candidates: list[FeaturePath],
        already_selected: list[FeaturePath],
        n: int,
    ) -> list[FeaturePath]:
        """Select diverse features from candidates.

        Uses the DiversitySampler to reject candidates too similar to
        what's already been selected.

        Args:
            candidates: New candidate FeaturePaths.
            already_selected: Previously selected FeaturePaths.
            n: Maximum number of features to select this iteration.

        Returns:
            List of newly selected diverse FeaturePaths.
        """
        if not candidates:
            return []

        # Build combined candidates: already_selected + new candidates.
        # The sampler processes in order, so we put new candidates after
        # the "already selected" seed. We need to sample only from the
        # new candidates though.
        #
        # Strategy: sample from new candidates only, checking against
        # embeddings of already_selected features.
        threshold = self._config.diversity_threshold
        selected_embeddings = [
            path.leaf.embedding or [0.0] * 384
            for path in already_selected
        ]

        newly_selected: list[FeaturePath] = []
        for path in candidates:
            if len(newly_selected) >= n:
                break

            embedding = path.leaf.embedding or [0.0] * 384
            if self._sampler._is_diverse(
                embedding, selected_embeddings, threshold
            ):
                newly_selected.append(path)
                selected_embeddings.append(embedding)

        return newly_selected

    def _filtering_phase(
        self,
        selected: list[FeaturePath],
        spec_description: str,
        spec_languages: list[str] | None = None,
        spec_frameworks: list[str] | None = None,
    ) -> tuple[list[FeaturePath], set[str], FilterResult]:
        """Execute the LLM filtering phase.

        Filters the current selection for relevance. Pruned features are
        removed from the selected set.

        Args:
            selected: Currently selected FeaturePaths.
            spec_description: Project specification.
            spec_languages: Optional languages.
            spec_frameworks: Optional frameworks.

        Returns:
            Tuple of (filtered_selected, updated_ids, filter_result).
        """
        try:
            result = self._filter.filter(
                candidates=selected,
                spec_description=spec_description,
                spec_languages=spec_languages,
                spec_frameworks=spec_frameworks,
            )

            # Rebuild selected list from kept features
            kept_ids = {p.leaf.id for p in result.kept}
            filtered_selected = [p for p in selected if p.leaf.id in kept_ids]
            filtered_ids = {p.leaf.id for p in filtered_selected}

            pruned_count = len(selected) - len(filtered_selected)
            if pruned_count > 0:
                logger.info(
                    "LLM filter pruned %d features, keeping %d",
                    pruned_count,
                    len(filtered_selected),
                )

            return filtered_selected, filtered_ids, result

        except Exception as exc:
            logger.warning("LLM filtering failed, keeping all: %s", exc)
            return selected, {p.leaf.id for p in selected}, FilterResult()
