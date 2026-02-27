"""Cohesion, Coupling, and Modularity Metrics.

Implements Task 2.3.2 of PRD-RPG-P2-001 (Epic 2.3: Functionality Graph
Construction). Computes software engineering quality metrics for module
partitions:

- **Cohesion**: Average pairwise cosine similarity within each module (target > 0.6)
- **Coupling**: Number of inter-module dependencies per module (target < 3)
- **Modularity (Q-score)**: Newman's modularity metric (target > 0.4)

Example::

    from cobuilder.repomap.graph_construction.metrics import (
        compute_cohesion,
        compute_coupling,
        compute_modularity,
        compute_all_metrics,
    )

    metrics = compute_all_metrics(modules, features, dependencies)
    print(f"Avg cohesion: {metrics.avg_cohesion:.3f}")
    print(f"Q-score: {metrics.modularity_score:.3f}")
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from cobuilder.repomap.graph_construction.partitioner import ModuleSpec
from cobuilder.repomap.ontology.models import FeatureNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class MetricsConfig(BaseModel):
    """Configuration for metrics computation.

    Attributes:
        cohesion_target: Target cohesion threshold.
        coupling_target: Maximum acceptable coupling.
        modularity_target: Target Q-score.
        default_embedding_dim: Fallback embedding dimensionality.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    cohesion_target: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Target intra-module cohesion",
    )
    coupling_target: int = Field(
        default=3,
        ge=0,
        description="Maximum inter-module dependencies per module",
    )
    modularity_target: float = Field(
        default=0.4,
        ge=-1.0,
        le=1.0,
        description="Target Newman's modularity Q-score",
    )
    default_embedding_dim: int = Field(
        default=384,
        ge=1,
        description="Fallback embedding dimensionality",
    )


# ---------------------------------------------------------------------------
# Result Models
# ---------------------------------------------------------------------------


class CohesionResult(BaseModel):
    """Cohesion metrics for a single module.

    Attributes:
        module_name: Name of the module.
        cohesion: Average pairwise cosine similarity.
        min_similarity: Minimum pairwise similarity.
        max_similarity: Maximum pairwise similarity.
        num_features: Number of features in the module.
        num_pairs: Number of feature pairs compared.
        meets_target: Whether cohesion >= target threshold.
    """

    model_config = ConfigDict(frozen=True)

    module_name: str = Field(description="Module name")
    cohesion: float = Field(
        ge=-1.0, le=1.0, description="Average pairwise cosine similarity"
    )
    min_similarity: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Min pairwise similarity"
    )
    max_similarity: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Max pairwise similarity"
    )
    num_features: int = Field(ge=0, description="Features in module")
    num_pairs: int = Field(ge=0, description="Pairs compared")
    meets_target: bool = Field(
        default=False, description="Whether cohesion meets target"
    )


class CouplingResult(BaseModel):
    """Coupling metrics for a single module.

    Attributes:
        module_name: Name of the module.
        outgoing_deps: Number of outgoing dependencies.
        incoming_deps: Number of incoming dependencies.
        total_deps: Total unique dependency count.
        dep_module_names: Names of modules this depends on.
        meets_target: Whether coupling <= target threshold.
    """

    model_config = ConfigDict(frozen=True)

    module_name: str = Field(description="Module name")
    outgoing_deps: int = Field(ge=0, description="Outgoing dependencies")
    incoming_deps: int = Field(ge=0, description="Incoming dependencies")
    total_deps: int = Field(ge=0, description="Total unique dependencies")
    dep_module_names: list[str] = Field(
        default_factory=list, description="Dependent module names"
    )
    meets_target: bool = Field(
        default=False, description="Whether coupling meets target"
    )


class ModularityResult(BaseModel):
    """Newman's modularity Q-score result.

    Attributes:
        q_score: The modularity Q-score (-0.5 to 1.0).
        num_modules: Number of modules.
        num_edges: Number of total edges (dependencies).
        meets_target: Whether Q-score >= target.
    """

    model_config = ConfigDict(frozen=True)

    q_score: float = Field(
        ge=-1.0, le=1.0, description="Newman's modularity Q-score"
    )
    num_modules: int = Field(ge=0, description="Number of modules")
    num_edges: int = Field(ge=0, description="Total edge count")
    meets_target: bool = Field(
        default=False, description="Whether Q-score meets target"
    )


class PartitionMetrics(BaseModel):
    """Aggregate metrics for an entire partition.

    Attributes:
        cohesion_results: Per-module cohesion metrics.
        coupling_results: Per-module coupling metrics.
        modularity: Overall modularity Q-score.
        avg_cohesion: Average cohesion across modules.
        max_coupling: Maximum coupling across modules.
        all_cohesion_met: Whether all modules meet cohesion target.
        all_coupling_met: Whether all modules meet coupling target.
        modularity_met: Whether Q-score meets target.
        overall_quality: Whether all quality targets are met.
    """

    model_config = ConfigDict(frozen=True)

    cohesion_results: list[CohesionResult] = Field(
        default_factory=list, description="Per-module cohesion"
    )
    coupling_results: list[CouplingResult] = Field(
        default_factory=list, description="Per-module coupling"
    )
    modularity: ModularityResult | None = Field(
        default=None, description="Overall modularity"
    )
    avg_cohesion: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Average cohesion"
    )
    max_coupling: int = Field(
        default=0, ge=0, description="Maximum coupling"
    )
    all_cohesion_met: bool = Field(
        default=False, description="All modules meet cohesion target"
    )
    all_coupling_met: bool = Field(
        default=False, description="All modules meet coupling target"
    )
    modularity_met: bool = Field(
        default=False, description="Q-score meets target"
    )

    @property
    def overall_quality(self) -> bool:
        """Whether all quality targets are met."""
        return (
            self.all_cohesion_met
            and self.all_coupling_met
            and self.modularity_met
        )


# ---------------------------------------------------------------------------
# Cohesion computation
# ---------------------------------------------------------------------------


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity in [-1.0, 1.0]. Returns 0.0 for zero vectors.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _get_embedding_vector(
    feature: FeatureNode, dim: int = 384
) -> np.ndarray:
    """Get the embedding vector for a feature.

    Args:
        feature: The feature node.
        dim: Default dimensionality for zero vectors.

    Returns:
        numpy array of the embedding, or zeros if not available.
    """
    if feature.embedding is not None and len(feature.embedding) > 0:
        return np.array(feature.embedding, dtype=np.float64)
    return np.zeros(dim, dtype=np.float64)


def compute_cohesion(
    module: ModuleSpec,
    feature_map: dict[str, FeatureNode],
    config: MetricsConfig | None = None,
) -> CohesionResult:
    """Compute intra-module cohesion as average pairwise cosine similarity.

    Cohesion measures how related the features within a module are to
    each other. Higher cohesion (target > 0.6) indicates a well-defined
    module with tightly related features.

    Args:
        module: The module specification.
        feature_map: All features by ID.
        config: Optional metrics configuration.

    Returns:
        A CohesionResult with the computed metrics.
    """
    cfg = config or MetricsConfig()

    # Get features that exist in the feature map
    features = [
        feature_map[fid]
        for fid in module.feature_ids
        if fid in feature_map
    ]

    n = len(features)
    if n < 2:
        # Single feature or empty → perfect cohesion by default
        return CohesionResult(
            module_name=module.name,
            cohesion=1.0,
            min_similarity=1.0,
            max_similarity=1.0,
            num_features=n,
            num_pairs=0,
            meets_target=True,
        )

    # Determine embedding dimension
    dim = cfg.default_embedding_dim
    for f in features:
        if f.embedding is not None and len(f.embedding) > 0:
            dim = len(f.embedding)
            break

    # Collect embeddings
    embeddings = [_get_embedding_vector(f, dim) for f in features]

    # Compute all pairwise cosine similarities
    similarities: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = _cosine_similarity(embeddings[i], embeddings[j])
            similarities.append(sim)

    if not similarities:
        return CohesionResult(
            module_name=module.name,
            cohesion=0.0,
            num_features=n,
            num_pairs=0,
            meets_target=False,
        )

    avg_sim = float(np.mean(similarities))
    min_sim = float(np.min(similarities))
    max_sim = float(np.max(similarities))

    return CohesionResult(
        module_name=module.name,
        cohesion=avg_sim,
        min_similarity=min_sim,
        max_similarity=max_sim,
        num_features=n,
        num_pairs=len(similarities),
        meets_target=avg_sim >= cfg.cohesion_target,
    )


# ---------------------------------------------------------------------------
# Coupling computation
# ---------------------------------------------------------------------------


def compute_coupling(
    module: ModuleSpec,
    all_modules: list[ModuleSpec],
    dependencies: list[tuple[str, str]],
    config: MetricsConfig | None = None,
) -> CouplingResult:
    """Compute inter-module coupling for a single module.

    Coupling measures how many other modules this module depends on or
    is depended upon by. Lower coupling (target < 3) indicates better
    module independence.

    Dependencies are specified as (source_module_name, target_module_name)
    tuples, meaning source depends on target.

    Args:
        module: The module to compute coupling for.
        all_modules: All modules in the partition.
        dependencies: List of (source, target) module dependency pairs.
        config: Optional metrics configuration.

    Returns:
        A CouplingResult with the computed metrics.
    """
    cfg = config or MetricsConfig()

    outgoing: set[str] = set()
    incoming: set[str] = set()

    for src, tgt in dependencies:
        if src == module.name and tgt != module.name:
            outgoing.add(tgt)
        if tgt == module.name and src != module.name:
            incoming.add(src)

    # Total unique modules this module is connected to
    all_deps = outgoing | incoming

    return CouplingResult(
        module_name=module.name,
        outgoing_deps=len(outgoing),
        incoming_deps=len(incoming),
        total_deps=len(all_deps),
        dep_module_names=sorted(all_deps),
        meets_target=len(all_deps) <= cfg.coupling_target,
    )


# ---------------------------------------------------------------------------
# Modularity (Q-score) computation
# ---------------------------------------------------------------------------


def compute_modularity(
    modules: list[ModuleSpec],
    dependencies: list[tuple[str, str]],
    config: MetricsConfig | None = None,
) -> ModularityResult:
    """Compute Newman's modularity Q-score for the partition.

    Newman's modularity Q measures the quality of a network's division
    into modules. It is defined as:

        Q = (1/2m) * sum_ij [ A_ij - (k_i * k_j) / (2m) ] * delta(c_i, c_j)

    where:
    - A_ij is the adjacency matrix
    - k_i is the degree of node i
    - m is the total number of edges
    - delta(c_i, c_j) = 1 if nodes i and j are in the same module

    For module-level computation, we simplify to:

        Q = sum_c [ e_cc - a_c^2 ]

    where:
    - e_cc = fraction of edges within module c
    - a_c = fraction of edge endpoints in module c

    Args:
        modules: All modules in the partition.
        dependencies: List of (source, target) module dependency pairs.
        config: Optional metrics configuration.

    Returns:
        A ModularityResult with the Q-score.
    """
    cfg = config or MetricsConfig()

    if not modules:
        return ModularityResult(
            q_score=0.0,
            num_modules=0,
            num_edges=0,
            meets_target=False,
        )

    # Build module name set
    module_names = {m.name for m in modules}

    # Filter to valid dependencies (between known modules)
    valid_deps = [
        (s, t)
        for s, t in dependencies
        if s in module_names and t in module_names
    ]

    # Total edges (treat as undirected for modularity)
    # Each dependency counts as one edge
    m_total = len(valid_deps)

    if m_total == 0:
        # No edges → each module is isolated → Q = 1 - 1/n (maximum)
        # Actually, with no edges, modularity is undefined or 0
        # Convention: Q = 0 when no edges
        q = 0.0
        if len(modules) > 1:
            # All nodes are isolated in their own community: Q = 0
            q = 0.0
        return ModularityResult(
            q_score=q,
            num_modules=len(modules),
            num_edges=0,
            meets_target=q >= cfg.modularity_target,
        )

    # Count edges within each module and total degree per module
    intra_edges: dict[str, int] = {m.name: 0 for m in modules}
    degree: dict[str, int] = {m.name: 0 for m in modules}

    for src, tgt in valid_deps:
        degree[src] = degree.get(src, 0) + 1
        degree[tgt] = degree.get(tgt, 0) + 1
        if src == tgt:
            # Self-loop (intra-module)
            intra_edges[src] = intra_edges.get(src, 0) + 1

    # Compute Q = sum_c [ e_cc - a_c^2 ]
    # e_cc = fraction of edges with both endpoints in module c
    # a_c = fraction of all edge endpoints that are in module c
    q_score = 0.0
    for mod in modules:
        e_cc = intra_edges.get(mod.name, 0) / m_total
        a_c = degree.get(mod.name, 0) / (2 * m_total)
        q_score += e_cc - a_c * a_c

    # Clamp to valid range
    q_score = max(-1.0, min(1.0, q_score))

    return ModularityResult(
        q_score=q_score,
        num_modules=len(modules),
        num_edges=m_total,
        meets_target=q_score >= cfg.modularity_target,
    )


# ---------------------------------------------------------------------------
# Feature-level modularity (using feature dependencies)
# ---------------------------------------------------------------------------


def compute_feature_modularity(
    modules: list[ModuleSpec],
    feature_dependencies: list[tuple[str, str]],
    config: MetricsConfig | None = None,
) -> ModularityResult:
    """Compute Newman's modularity using feature-level dependencies.

    This provides a more granular modularity measure by looking at
    which features depend on features in other modules.

    Args:
        modules: All modules in the partition.
        feature_dependencies: List of (source_feature_id, target_feature_id) pairs.
        config: Optional metrics configuration.

    Returns:
        A ModularityResult with the Q-score.
    """
    cfg = config or MetricsConfig()

    if not modules or not feature_dependencies:
        return ModularityResult(
            q_score=0.0,
            num_modules=len(modules),
            num_edges=len(feature_dependencies),
            meets_target=False,
        )

    # Build feature-to-module mapping
    feature_to_module: dict[str, str] = {}
    for mod in modules:
        for fid in mod.feature_ids:
            feature_to_module[fid] = mod.name

    # Convert feature deps to module deps (count intra vs inter)
    m_total = len(feature_dependencies)
    module_names = {m.name for m in modules}

    intra_count: dict[str, int] = {name: 0 for name in module_names}
    degree: dict[str, int] = {name: 0 for name in module_names}

    for src_feat, tgt_feat in feature_dependencies:
        src_mod = feature_to_module.get(src_feat)
        tgt_mod = feature_to_module.get(tgt_feat)

        if src_mod is None or tgt_mod is None:
            continue

        degree[src_mod] = degree.get(src_mod, 0) + 1
        degree[tgt_mod] = degree.get(tgt_mod, 0) + 1

        if src_mod == tgt_mod:
            intra_count[src_mod] = intra_count.get(src_mod, 0) + 1

    if m_total == 0:
        return ModularityResult(
            q_score=0.0,
            num_modules=len(modules),
            num_edges=0,
            meets_target=False,
        )

    # Q = sum_c [ e_cc - a_c^2 ]
    q_score = 0.0
    for name in module_names:
        e_cc = intra_count.get(name, 0) / m_total
        a_c = degree.get(name, 0) / (2 * m_total)
        q_score += e_cc - a_c * a_c

    q_score = max(-1.0, min(1.0, q_score))

    return ModularityResult(
        q_score=q_score,
        num_modules=len(modules),
        num_edges=m_total,
        meets_target=q_score >= cfg.modularity_target,
    )


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def compute_all_metrics(
    modules: list[ModuleSpec],
    feature_map: dict[str, FeatureNode],
    dependencies: list[tuple[str, str]] | None = None,
    config: MetricsConfig | None = None,
) -> PartitionMetrics:
    """Compute all partition quality metrics.

    Computes cohesion for each module, coupling based on dependencies,
    and overall modularity Q-score.

    Args:
        modules: All modules in the partition.
        feature_map: All features by ID.
        dependencies: Module-level dependency pairs (source, target).
            If None, coupling and modularity use empty dependency list.
        config: Optional metrics configuration.

    Returns:
        A PartitionMetrics with all computed metrics.
    """
    cfg = config or MetricsConfig()
    deps = dependencies or []

    # Compute cohesion for each module
    cohesion_results = [
        compute_cohesion(mod, feature_map, cfg) for mod in modules
    ]

    # Compute coupling for each module
    coupling_results = [
        compute_coupling(mod, modules, deps, cfg) for mod in modules
    ]

    # Compute modularity
    modularity = compute_modularity(modules, deps, cfg)

    # Aggregate
    avg_cohesion = 0.0
    if cohesion_results:
        avg_cohesion = float(np.mean([c.cohesion for c in cohesion_results]))

    max_coupling = 0
    if coupling_results:
        max_coupling = max(c.total_deps for c in coupling_results)

    all_cohesion_met = all(c.meets_target for c in cohesion_results)
    all_coupling_met = all(c.meets_target for c in coupling_results)

    return PartitionMetrics(
        cohesion_results=cohesion_results,
        coupling_results=coupling_results,
        modularity=modularity,
        avg_cohesion=avg_cohesion,
        max_coupling=max_coupling,
        all_cohesion_met=all_cohesion_met,
        all_coupling_met=all_coupling_met,
        modularity_met=modularity.meets_target if modularity else False,
    )
