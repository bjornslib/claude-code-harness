"""Functionality Graph Builder – construct and export module graphs.

Implements Task 2.3.4 of PRD-RPG-P2-001 (Epic 2.3: Functionality Graph
Construction). Builds a NetworkX graph from modules and dependencies,
with export to JSON, GraphML, and DOT formats.

Integrates:
- ModulePartitioner (Task 2.3.1) for feature → module clustering
- Metrics (Task 2.3.2) for cohesion/coupling/modularity quality checks
- DependencyInference (Task 2.3.3) for module → module dependency edges

Example::

    from zerorepo.graph_construction.builder import (
        FunctionalityGraphBuilder,
        BuilderConfig,
    )

    builder = FunctionalityGraphBuilder(
        llm_gateway=gateway,
    )
    result = builder.build(features)

    # Export
    result.to_json("graph.json")
    result.to_graphml("graph.graphml")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from zerorepo.graph_construction.dependencies import (
    DependencyConfig,
    DependencyEdge,
    DependencyInference,
    DependencyResult,
)
from zerorepo.graph_construction.metrics import (
    MetricsConfig,
    PartitionMetrics,
    compute_all_metrics,
)
from zerorepo.graph_construction.partitioner import (
    ModulePartitioner,
    ModuleSpec,
    PartitionerConfig,
    PartitionResult,
)
from zerorepo.ontology.models import FeatureNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class BuilderConfig(BaseModel):
    """Configuration for the FunctionalityGraphBuilder.

    Attributes:
        partitioner_config: Config for module partitioning.
        dependency_config: Config for dependency inference.
        metrics_config: Config for quality metrics.
        require_acyclic: Whether to require an acyclic graph.
        compute_metrics: Whether to compute quality metrics.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    partitioner_config: PartitionerConfig = Field(
        default_factory=PartitionerConfig,
        description="Partitioner configuration",
    )
    dependency_config: DependencyConfig = Field(
        default_factory=DependencyConfig,
        description="Dependency inference configuration",
    )
    metrics_config: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Metrics configuration",
    )
    require_acyclic: bool = Field(
        default=True,
        description="Require acyclic dependency graph",
    )
    compute_metrics: bool = Field(
        default=True,
        description="Compute quality metrics",
    )


# ---------------------------------------------------------------------------
# Build Result
# ---------------------------------------------------------------------------


class FunctionalityGraph(BaseModel):
    """A functionality graph with modules and dependencies.

    Wraps a NetworkX DiGraph with structured metadata and export methods.

    Attributes:
        modules: Module specifications.
        dependencies: Dependency edges.
        partition_result: Full partition result.
        dependency_result: Full dependency result.
        metrics: Quality metrics (if computed).
        is_acyclic: Whether the graph is acyclic.
        metadata: Additional graph metadata.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    modules: list[ModuleSpec] = Field(
        default_factory=list, description="Module specs"
    )
    dependencies: list[DependencyEdge] = Field(
        default_factory=list, description="Dependency edges"
    )
    partition_result: PartitionResult | None = Field(
        default=None, description="Full partition result"
    )
    dependency_result: DependencyResult | None = Field(
        default=None, description="Full dependency result"
    )
    metrics: PartitionMetrics | None = Field(
        default=None, description="Quality metrics"
    )
    is_acyclic: bool = Field(
        default=True, description="Is the graph acyclic"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Graph metadata"
    )

    @property
    def module_count(self) -> int:
        """Number of modules."""
        return len(self.modules)

    @property
    def dependency_count(self) -> int:
        """Number of dependencies."""
        return len(self.dependencies)

    @property
    def feature_count(self) -> int:
        """Total features across all modules."""
        return sum(m.feature_count for m in self.modules)

    def build_networkx_graph(self) -> nx.DiGraph:
        """Build a NetworkX DiGraph from this functionality graph.

        Nodes represent modules with their full metadata.
        Edges represent dependencies with type, weight, and rationale.

        Returns:
            A NetworkX DiGraph.
        """
        g = nx.DiGraph()

        # Add module nodes
        for mod in self.modules:
            g.add_node(
                mod.name,
                description=mod.description,
                features=mod.feature_ids,
                public_interface=mod.public_interface,
                feature_count=mod.feature_count,
                rationale=mod.rationale,
            )

        # Add dependency edges
        for dep in self.dependencies:
            g.add_edge(
                dep.source,
                dep.target,
                dependency_type=dep.dependency_type,
                weight=dep.weight,
                confidence=dep.confidence,
                rationale=dep.rationale,
            )

        return g

    def to_json(self, filepath: str | Path | None = None) -> str:
        """Export the graph to JSON format.

        Preserves all module and dependency metadata.

        Args:
            filepath: Optional path to write JSON file.

        Returns:
            JSON string representation.
        """
        data = {
            "modules": [
                {
                    "name": m.name,
                    "description": m.description,
                    "feature_ids": m.feature_ids,
                    "public_interface": m.public_interface,
                    "feature_count": m.feature_count,
                    "rationale": m.rationale,
                }
                for m in self.modules
            ],
            "dependencies": [
                {
                    "source": d.source,
                    "target": d.target,
                    "dependency_type": d.dependency_type,
                    "weight": d.weight,
                    "confidence": d.confidence,
                    "rationale": d.rationale,
                }
                for d in self.dependencies
            ],
            "metadata": {
                "module_count": self.module_count,
                "dependency_count": self.dependency_count,
                "feature_count": self.feature_count,
                "is_acyclic": self.is_acyclic,
                **self.metadata,
            },
        }

        if self.metrics:
            data["metrics"] = {
                "avg_cohesion": self.metrics.avg_cohesion,
                "max_coupling": self.metrics.max_coupling,
                "all_cohesion_met": self.metrics.all_cohesion_met,
                "all_coupling_met": self.metrics.all_coupling_met,
                "modularity_met": self.metrics.modularity_met,
                "overall_quality": self.metrics.overall_quality,
            }
            if self.metrics.modularity:
                data["metrics"]["q_score"] = self.metrics.modularity.q_score

        json_str = json.dumps(data, indent=2, default=str)

        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str, encoding="utf-8")
            logger.info("Exported graph to JSON: %s", path)

        return json_str

    def to_graphml(self, filepath: str | Path) -> None:
        """Export the graph to GraphML format.

        GraphML is supported by Gephi and other graph visualization tools.

        Args:
            filepath: Path to write GraphML file.
        """
        g = self.build_networkx_graph()

        # Convert list attributes to strings for GraphML compatibility
        for node in g.nodes:
            attrs = g.nodes[node]
            if "features" in attrs:
                attrs["features"] = ", ".join(attrs["features"])
            if "public_interface" in attrs:
                attrs["public_interface"] = ", ".join(attrs["public_interface"])

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        nx.write_graphml(g, str(path))
        logger.info("Exported graph to GraphML: %s", path)

    def to_dot(self, filepath: str | Path | None = None) -> str:
        """Export the graph to DOT format.

        DOT format is used by Graphviz for visualization.

        Args:
            filepath: Optional path to write DOT file.

        Returns:
            DOT format string.
        """
        lines = ["digraph FunctionalityGraph {"]
        lines.append('    rankdir=LR;')
        lines.append('    node [shape=box, style=filled, fillcolor=lightblue];')
        lines.append("")

        # Add nodes
        for mod in self.modules:
            label = f"{mod.name}\\n({mod.feature_count} features)"
            lines.append(
                f'    "{mod.name}" [label="{label}", '
                f'tooltip="{mod.description}"];'
            )

        lines.append("")

        # Add edges
        for dep in self.dependencies:
            label = dep.dependency_type
            lines.append(
                f'    "{dep.source}" -> "{dep.target}" '
                f'[label="{label}", weight={dep.weight}];'
            )

        lines.append("}")

        dot_str = "\n".join(lines)

        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dot_str, encoding="utf-8")
            logger.info("Exported graph to DOT: %s", path)

        return dot_str

    @classmethod
    def from_json(cls, json_str: str) -> FunctionalityGraph:
        """Load a FunctionalityGraph from a JSON string.

        Args:
            json_str: JSON string from to_json().

        Returns:
            A new FunctionalityGraph.
        """
        data = json.loads(json_str)

        modules = [
            ModuleSpec(
                name=m["name"],
                description=m.get("description", ""),
                feature_ids=m["feature_ids"],
                public_interface=m.get("public_interface", []),
                rationale=m.get("rationale", ""),
            )
            for m in data.get("modules", [])
        ]

        dependencies = [
            DependencyEdge(
                source=d["source"],
                target=d["target"],
                dependency_type=d.get("dependency_type", "uses"),
                weight=d.get("weight", 1.0),
                confidence=d.get("confidence", 1.0),
                rationale=d.get("rationale", ""),
            )
            for d in data.get("dependencies", [])
        ]

        metadata = data.get("metadata", {})
        is_acyclic = metadata.pop("is_acyclic", True)

        return cls(
            modules=modules,
            dependencies=dependencies,
            is_acyclic=is_acyclic,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Functionality Graph Builder
# ---------------------------------------------------------------------------


class FunctionalityGraphBuilder:
    """Builds functionality graphs from features.

    Orchestrates the full pipeline:
    1. Partition features into modules (Task 2.3.1)
    2. Infer dependencies between modules (Task 2.3.3)
    3. Compute quality metrics (Task 2.3.2)
    4. Package into a FunctionalityGraph

    Args:
        llm_gateway: Optional LLM gateway for LLM-based operations.
        config: Optional builder configuration.

    Example::

        builder = FunctionalityGraphBuilder(llm_gateway=gateway)
        graph = builder.build(features)
        graph.to_json("output.json")
    """

    def __init__(
        self,
        llm_gateway: Any | None = None,
        config: BuilderConfig | None = None,
    ) -> None:
        self._llm = llm_gateway
        self._config = config or BuilderConfig()

        self._partitioner = ModulePartitioner(
            llm_gateway=self._llm,
            config=self._config.partitioner_config,
        )
        self._dep_inference = DependencyInference(
            llm_gateway=self._llm,
            config=self._config.dependency_config,
        )

    @property
    def config(self) -> BuilderConfig:
        """Return the builder configuration."""
        return self._config

    def build(
        self,
        features: list[FeatureNode],
        target_modules: int | None = None,
    ) -> FunctionalityGraph:
        """Build a functionality graph from features.

        Full pipeline: partition → infer dependencies → compute metrics.

        Args:
            features: Features to build the graph from.
            target_modules: Optional target number of modules.

        Returns:
            A FunctionalityGraph with modules, dependencies, and metrics.

        Raises:
            ValueError: If features list is empty.
        """
        if not features:
            raise ValueError("Cannot build graph from empty features list")

        feature_map = {f.id: f for f in features}

        # Step 1: Partition features into modules
        logger.info("Partitioning %d features into modules...", len(features))
        partition_result = self._partitioner.partition(
            features, target_modules=target_modules
        )
        logger.info(
            "Partitioned into %d modules using %s",
            partition_result.module_count,
            partition_result.method,
        )

        # Step 2: Infer dependencies
        logger.info("Inferring module dependencies...")
        dep_result = self._dep_inference.infer(
            partition_result.modules, feature_map
        )
        logger.info(
            "Inferred %d dependencies (%s), acyclic=%s",
            dep_result.dependency_count,
            dep_result.method,
            dep_result.is_acyclic,
        )

        # Step 3: Compute quality metrics
        metrics = None
        if self._config.compute_metrics:
            logger.info("Computing quality metrics...")
            metrics = compute_all_metrics(
                modules=partition_result.modules,
                feature_map=feature_map,
                dependencies=dep_result.as_pairs,
                config=self._config.metrics_config,
            )
            logger.info(
                "Metrics: avg_cohesion=%.3f, max_coupling=%d, Q=%.3f",
                metrics.avg_cohesion,
                metrics.max_coupling,
                metrics.modularity.q_score if metrics.modularity else 0.0,
            )

        return FunctionalityGraph(
            modules=partition_result.modules,
            dependencies=dep_result.dependencies,
            partition_result=partition_result,
            dependency_result=dep_result,
            metrics=metrics,
            is_acyclic=dep_result.is_acyclic,
            metadata={
                "total_features": len(features),
                "partition_method": partition_result.method,
                "dependency_method": dep_result.method,
            },
        )

    def build_from_spec(
        self,
        spec: Any,
    ) -> FunctionalityGraph:
        """Build a functionality graph from a RepositorySpec.

        Creates ModuleSpec objects from the spec's epics (if available),
        with components becoming features within modules.  Spec data_flows
        are mapped to DependencyEdge objects.

        This method is designed to work with the extended RepositorySpec
        that includes ``epics``, ``components``, ``data_flows``, and
        ``file_recommendations`` fields.  It degrades gracefully when
        those fields are absent (e.g. with the base RepositorySpec).

        Args:
            spec: A RepositorySpec instance (possibly with extended fields
                added by the spec-to-graph bridge).

        Returns:
            A FunctionalityGraph built from the specification.

        Raises:
            ValueError: If no modules can be derived from the spec.
        """
        # Extract epics – each becomes a module
        epics = getattr(spec, "epics", None) or []
        components = getattr(spec, "components", None) or []
        data_flows = getattr(spec, "data_flows", None) or []

        modules: list[ModuleSpec] = []

        if epics:
            for epic in epics:
                # Each epic becomes a module.  Components within the
                # epic become its feature_ids.
                epic_name = getattr(epic, "name", None) or getattr(epic, "title", str(epic))
                epic_desc = getattr(epic, "description", "") or ""
                epic_id = getattr(epic, "id", epic_name)

                # Gather feature IDs: look for sub-components or use the
                # epic's own ID as a single feature.
                epic_components = getattr(epic, "components", None) or []
                feature_ids: list[str] = []
                for comp in epic_components:
                    comp_id = getattr(comp, "id", None) or getattr(comp, "name", str(comp))
                    feature_ids.append(str(comp_id))

                if not feature_ids:
                    # Use the epic's ID itself as a feature placeholder
                    feature_ids = [str(epic_id)]

                modules.append(
                    ModuleSpec(
                        name=str(epic_name),
                        description=str(epic_desc),
                        feature_ids=feature_ids,
                        public_interface=feature_ids[:1],
                        rationale=f"Derived from spec epic: {epic_name}",
                    )
                )
        elif components:
            # Fallback: group all components into a single module
            feature_ids = []
            for comp in components:
                comp_id = getattr(comp, "id", None) or getattr(comp, "name", str(comp))
                feature_ids.append(str(comp_id))

            if feature_ids:
                core_func = getattr(spec, "core_functionality", None) or "Main"
                modules.append(
                    ModuleSpec(
                        name=str(core_func)[:200],
                        description=getattr(spec, "description", "")[:500] or "",
                        feature_ids=feature_ids,
                        public_interface=feature_ids[:1],
                        rationale="Derived from spec components",
                    )
                )

        if not modules:
            raise ValueError(
                "Cannot build graph from spec: no epics or components found. "
                "Ensure the RepositorySpec has been extended with epic/component fields."
            )

        logger.info(
            "Built %d module(s) from spec with %d total features",
            len(modules),
            sum(m.feature_count for m in modules),
        )

        # Build dependencies from data_flows
        dep_edges: list[DependencyEdge] = []
        module_names = {m.name for m in modules}

        for flow in data_flows:
            source_name = getattr(flow, "source", None) or ""
            target_name = getattr(flow, "target", None) or ""
            flow_type = getattr(flow, "type", "data_flow") or "data_flow"
            flow_desc = getattr(flow, "description", "") or ""

            if str(source_name) in module_names and str(target_name) in module_names:
                if str(source_name) != str(target_name):
                    dep_edges.append(
                        DependencyEdge(
                            source=str(source_name),
                            target=str(target_name),
                            dependency_type=str(flow_type),
                            weight=0.8,
                            confidence=0.9,
                            rationale=str(flow_desc),
                        )
                    )

        return FunctionalityGraph(
            modules=modules,
            dependencies=dep_edges,
            is_acyclic=True,
            metadata={
                "source": "repository_spec",
                "spec_id": str(getattr(spec, "id", "unknown")),
                "total_modules": len(modules),
                "total_dependencies": len(dep_edges),
            },
        )

    def build_from_modules(
        self,
        modules: list[ModuleSpec],
        feature_map: dict[str, FeatureNode] | None = None,
    ) -> FunctionalityGraph:
        """Build a functionality graph from pre-defined modules.

        Skips the partitioning step and goes straight to dependency
        inference and metrics.

        Args:
            modules: Pre-defined module specifications.
            feature_map: Optional feature map for metrics.

        Returns:
            A FunctionalityGraph.
        """
        if not modules:
            raise ValueError("Cannot build graph from empty modules list")

        fmap = feature_map or {}

        # Infer dependencies
        dep_result = self._dep_inference.infer(modules, fmap)

        # Compute metrics
        metrics = None
        if self._config.compute_metrics and fmap:
            dep_pairs = dep_result.as_pairs
            metrics = compute_all_metrics(
                modules=modules,
                feature_map=fmap,
                dependencies=dep_pairs,
                config=self._config.metrics_config,
            )

        return FunctionalityGraph(
            modules=modules,
            dependencies=dep_result.dependencies,
            dependency_result=dep_result,
            metrics=metrics,
            is_acyclic=dep_result.is_acyclic,
            metadata={
                "dependency_method": dep_result.method,
            },
        )
