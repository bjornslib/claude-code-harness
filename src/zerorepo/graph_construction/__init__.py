"""ZeroRepo Functionality Graph Construction Service.

This package implements Epic 2.3 of PRD-RPG-P2-001 (Functionality Graph
Construction), providing:

- :class:`ModulePartitioner` -- LLM-driven feature clustering into modules (Task 2.3.1)
- :class:`PartitionerConfig` -- Configuration for the module partitioner
- :class:`ModuleSpec` -- Specification for a single module
- :class:`PartitionResult` -- Result of partitioning features into modules
- :func:`compute_cohesion` -- Intra-module cohesion metric (Task 2.3.2)
- :func:`compute_coupling` -- Inter-module coupling metric (Task 2.3.2)
- :func:`compute_modularity` -- Newman's modularity Q-score (Task 2.3.2)
- :func:`compute_all_metrics` -- Aggregate partition quality metrics (Task 2.3.2)
- :class:`MetricsConfig` -- Configuration for metrics computation
- :class:`CohesionResult` -- Per-module cohesion result
- :class:`CouplingResult` -- Per-module coupling result
- :class:`ModularityResult` -- Overall modularity result
- :class:`PartitionMetrics` -- Aggregate metrics result
- :class:`DependencyInference` -- LLM-driven module dependency detection (Task 2.3.3)
- :class:`DependencyConfig` -- Configuration for dependency inference
- :class:`DependencyEdge` -- A directed dependency between modules
- :class:`DependencyResult` -- Result of dependency inference
- :class:`FunctionalityGraphBuilder` -- Full pipeline graph builder (Task 2.3.4)
- :class:`FunctionalityGraph` -- Built graph with export methods
- :class:`BuilderConfig` -- Configuration for the graph builder
- :class:`GraphRefinement` -- Iterative graph refinement engine (Task 2.3.5)
- :class:`RefinementConfig` -- Configuration for the refinement engine
- :class:`RefinementResult` -- Result of a refinement operation
- :class:`RefinementAction` -- A recorded refinement action
- :class:`RefinementHistory` -- History of refinement actions with undo
- :class:`ActionType` -- Enum of refinement action types
- :class:`GraphExporter` -- Unified graph export service (Task 2.3.6)
- :class:`ExportConfig` -- Configuration for graph export
- :class:`ExportFormat` -- Supported export formats enum
- :class:`ExportResult` -- Result of an export operation
"""

from zerorepo.graph_construction.builder import (
    BuilderConfig,
    FunctionalityGraph,
    FunctionalityGraphBuilder,
)
from zerorepo.graph_construction.dependencies import (
    DependencyConfig,
    DependencyEdge,
    DependencyInference,
    DependencyResult,
)
from zerorepo.graph_construction.metrics import (
    CohesionResult,
    CouplingResult,
    MetricsConfig,
    ModularityResult,
    PartitionMetrics,
    compute_all_metrics,
    compute_cohesion,
    compute_coupling,
    compute_feature_modularity,
    compute_modularity,
)
from zerorepo.graph_construction.partitioner import (
    ModulePartitioner,
    ModuleSpec,
    PartitionerConfig,
    PartitionResult,
)
from zerorepo.graph_construction.export import (
    ExportConfig,
    ExportFormat,
    ExportResult,
    GraphExporter,
)
from zerorepo.graph_construction.refinement import (
    ActionType,
    GraphRefinement,
    RefinementAction,
    RefinementConfig,
    RefinementHistory,
    RefinementResult,
)

__all__ = [
    "ActionType",
    "BuilderConfig",
    "CohesionResult",
    "CouplingResult",
    "DependencyConfig",
    "DependencyEdge",
    "DependencyInference",
    "DependencyResult",
    "FunctionalityGraph",
    "FunctionalityGraphBuilder",
    "MetricsConfig",
    "ModularityResult",
    "ModulePartitioner",
    "ModuleSpec",
    "PartitionMetrics",
    "PartitionerConfig",
    "PartitionResult",
    "compute_all_metrics",
    "compute_cohesion",
    "compute_coupling",
    "compute_feature_modularity",
    "compute_modularity",
    "ExportConfig",
    "ExportFormat",
    "ExportResult",
    "GraphExporter",
    "GraphRefinement",
    "RefinementAction",
    "RefinementConfig",
    "RefinementHistory",
    "RefinementResult",
]
