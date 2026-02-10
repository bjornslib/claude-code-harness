"""Graph Export and Serialization Service.

Implements Task 2.3.6 of PRD-RPG-P2-001 (Epic 2.3: Functionality Graph
Construction). Provides a unified export service for FunctionalityGraph
with multiple output formats and Phase 1 RPGGraph integration.

Supported formats:
- **JSON**: Full metadata with round-trip support
- **GraphML**: For Gephi and other graph visualization tools
- **DOT**: For Graphviz rendering
- **YAML**: Human-readable structured export
- **RPGGraph**: Conversion to Phase 1 RPGGraph model

Example::

    from zerorepo.graph_construction.export import (
        GraphExporter,
        ExportConfig,
        ExportFormat,
    )

    exporter = GraphExporter(config=ExportConfig(include_metrics=True))
    result = exporter.export(graph, ExportFormat.JSON, Path("output.json"))

    # Convert to Phase 1 RPGGraph
    rpg_graph = exporter.to_rpg_graph(graph)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from zerorepo.graph_construction.builder import FunctionalityGraph
from zerorepo.graph_construction.dependencies import DependencyEdge
from zerorepo.graph_construction.partitioner import ModuleSpec
from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Configuration
# ---------------------------------------------------------------------------


class ExportFormat(str, Enum):
    """Supported export formats."""

    JSON = "json"
    GRAPHML = "graphml"
    DOT = "dot"
    YAML = "yaml"
    SUMMARY = "summary"


class ExportConfig(BaseModel):
    """Configuration for graph export.

    Attributes:
        include_metrics: Include quality metrics in export.
        include_rationale: Include rationale text in exports.
        include_metadata: Include graph metadata.
        include_features: Include feature lists in module data.
        pretty_print: Enable pretty formatting.
        indent: Indentation level for JSON/YAML.
        dot_rankdir: DOT graph direction (LR, TB, BT, RL).
        dot_node_shape: DOT node shape.
        dot_node_color: DOT node fill color.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    include_metrics: bool = Field(
        default=True, description="Include metrics in export"
    )
    include_rationale: bool = Field(
        default=True, description="Include rationale text"
    )
    include_metadata: bool = Field(
        default=True, description="Include graph metadata"
    )
    include_features: bool = Field(
        default=True, description="Include feature lists"
    )
    pretty_print: bool = Field(
        default=True, description="Pretty-print output"
    )
    indent: int = Field(default=2, description="Indentation level")
    dot_rankdir: str = Field(
        default="LR", description="DOT graph direction"
    )
    dot_node_shape: str = Field(
        default="box", description="DOT node shape"
    )
    dot_node_color: str = Field(
        default="lightblue", description="DOT node fill color"
    )


# ---------------------------------------------------------------------------
# Export Result
# ---------------------------------------------------------------------------


class ExportResult(BaseModel):
    """Result of an export operation.

    Attributes:
        success: Whether the export succeeded.
        format: The export format used.
        filepath: Path to the exported file (if file-based).
        content: The exported content string.
        size_bytes: Size of the exported content.
        module_count: Number of modules exported.
        dependency_count: Number of dependencies exported.
        error: Error message if export failed.
    """

    model_config = ConfigDict(frozen=True)

    success: bool = Field(description="Whether export succeeded")
    format: ExportFormat = Field(description="Export format used")
    filepath: str = Field(default="", description="Output file path")
    content: str = Field(default="", description="Exported content")
    size_bytes: int = Field(default=0, description="Content size in bytes")
    module_count: int = Field(default=0, description="Modules exported")
    dependency_count: int = Field(
        default=0, description="Dependencies exported"
    )
    error: str = Field(default="", description="Error message")


# ---------------------------------------------------------------------------
# Graph Exporter
# ---------------------------------------------------------------------------


class GraphExporter:
    """Unified export service for FunctionalityGraph.

    Supports multiple output formats and provides conversion to the
    Phase 1 RPGGraph model for integration.

    Args:
        config: Optional export configuration.

    Example::

        exporter = GraphExporter()
        result = exporter.export(graph, ExportFormat.JSON)
        print(result.content)
    """

    def __init__(self, config: ExportConfig | None = None) -> None:
        self._config = config or ExportConfig()

    @property
    def config(self) -> ExportConfig:
        """Return the export configuration."""
        return self._config

    def export(
        self,
        graph: FunctionalityGraph,
        fmt: ExportFormat,
        filepath: str | Path | None = None,
    ) -> ExportResult:
        """Export a FunctionalityGraph in the specified format.

        Args:
            graph: The graph to export.
            fmt: Target export format.
            filepath: Optional path to write the file.

        Returns:
            ExportResult with content and metadata.
        """
        try:
            if fmt == ExportFormat.JSON:
                content = self._export_json(graph)
            elif fmt == ExportFormat.GRAPHML:
                content = self._export_graphml(graph, filepath)
            elif fmt == ExportFormat.DOT:
                content = self._export_dot(graph)
            elif fmt == ExportFormat.YAML:
                content = self._export_yaml(graph)
            elif fmt == ExportFormat.SUMMARY:
                content = self._export_summary(graph)
            else:
                return ExportResult(
                    success=False,
                    format=fmt,
                    error=f"Unsupported format: {fmt}",
                )

            # Write to file if path provided
            out_path = ""
            if filepath and fmt != ExportFormat.GRAPHML:
                path = Path(filepath)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                out_path = str(path)
                logger.info("Exported graph to %s: %s", fmt.value, path)

            return ExportResult(
                success=True,
                format=fmt,
                filepath=out_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                module_count=graph.module_count,
                dependency_count=graph.dependency_count,
            )

        except Exception as e:
            logger.error("Export failed (%s): %s", fmt.value, e)
            return ExportResult(
                success=False,
                format=fmt,
                error=str(e),
            )

    def export_all(
        self,
        graph: FunctionalityGraph,
        output_dir: str | Path,
        base_name: str = "graph",
    ) -> dict[ExportFormat, ExportResult]:
        """Export a graph in all supported file formats.

        Args:
            graph: The graph to export.
            output_dir: Directory for output files.
            base_name: Base filename (without extension).

        Returns:
            Dict mapping format to ExportResult.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        results: dict[ExportFormat, ExportResult] = {}
        format_ext = {
            ExportFormat.JSON: ".json",
            ExportFormat.GRAPHML: ".graphml",
            ExportFormat.DOT: ".dot",
            ExportFormat.YAML: ".yaml",
            ExportFormat.SUMMARY: ".txt",
        }

        for fmt, ext in format_ext.items():
            filepath = out / f"{base_name}{ext}"
            results[fmt] = self.export(graph, fmt, filepath)

        return results

    # -------------------------------------------------------------------
    # Format-specific exporters
    # -------------------------------------------------------------------

    def _export_json(self, graph: FunctionalityGraph) -> str:
        """Export to JSON format."""
        data: dict[str, Any] = {
            "version": "2.3",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        # Modules
        modules_data = []
        for m in graph.modules:
            mod: dict[str, Any] = {
                "name": m.name,
                "description": m.description,
                "feature_count": m.feature_count,
            }
            if self._config.include_features:
                mod["feature_ids"] = list(m.feature_ids)
                mod["public_interface"] = list(m.public_interface)
            if self._config.include_rationale:
                mod["rationale"] = m.rationale
            modules_data.append(mod)
        data["modules"] = modules_data

        # Dependencies
        deps_data = []
        for d in graph.dependencies:
            dep: dict[str, Any] = {
                "source": d.source,
                "target": d.target,
                "dependency_type": d.dependency_type,
                "weight": d.weight,
                "confidence": d.confidence,
            }
            if self._config.include_rationale:
                dep["rationale"] = d.rationale
            deps_data.append(dep)
        data["dependencies"] = deps_data

        # Metadata
        if self._config.include_metadata:
            data["metadata"] = {
                "module_count": graph.module_count,
                "dependency_count": graph.dependency_count,
                "feature_count": graph.feature_count,
                "is_acyclic": graph.is_acyclic,
                **graph.metadata,
            }

        # Metrics
        if self._config.include_metrics and graph.metrics:
            data["metrics"] = {
                "avg_cohesion": graph.metrics.avg_cohesion,
                "max_coupling": graph.metrics.max_coupling,
                "all_cohesion_met": graph.metrics.all_cohesion_met,
                "all_coupling_met": graph.metrics.all_coupling_met,
                "modularity_met": graph.metrics.modularity_met,
                "overall_quality": graph.metrics.overall_quality,
            }
            if graph.metrics.modularity:
                data["metrics"]["q_score"] = graph.metrics.modularity.q_score

        indent = self._config.indent if self._config.pretty_print else None
        return json.dumps(data, indent=indent, default=str)

    def _export_graphml(
        self,
        graph: FunctionalityGraph,
        filepath: str | Path | None = None,
    ) -> str:
        """Export to GraphML format."""
        nx_graph = graph.build_networkx_graph()

        # Convert list attributes to strings for GraphML
        for node in nx_graph.nodes:
            attrs = nx_graph.nodes[node]
            for key, val in list(attrs.items()):
                if isinstance(val, list):
                    attrs[key] = ", ".join(str(v) for v in val)
                elif not isinstance(val, (str, int, float, bool)):
                    attrs[key] = str(val)

        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            nx.write_graphml(nx_graph, str(path))
            logger.info("Exported graph to GraphML: %s", path)

        # Also return as string via temporary generation
        from io import BytesIO

        buf = BytesIO()
        nx.write_graphml(nx_graph, buf)
        return buf.getvalue().decode("utf-8")

    def _export_dot(self, graph: FunctionalityGraph) -> str:
        """Export to DOT format."""
        cfg = self._config
        lines = ["digraph FunctionalityGraph {"]
        lines.append(f"    rankdir={cfg.dot_rankdir};")
        lines.append(
            f"    node [shape={cfg.dot_node_shape}, style=filled, "
            f"fillcolor={cfg.dot_node_color}];"
        )
        lines.append("")

        # Nodes
        for mod in graph.modules:
            label = f"{mod.name}\\n({mod.feature_count} features)"
            tooltip = mod.description.replace('"', '\\"')
            lines.append(
                f'    "{mod.name}" [label="{label}", '
                f'tooltip="{tooltip}"];'
            )

        lines.append("")

        # Edges
        for dep in graph.dependencies:
            label = dep.dependency_type
            attrs = f'label="{label}", weight={dep.weight}'
            if self._config.include_rationale and dep.rationale:
                tooltip = dep.rationale.replace('"', '\\"')
                attrs += f', tooltip="{tooltip}"'
            lines.append(
                f'    "{dep.source}" -> "{dep.target}" [{attrs}];'
            )

        lines.append("}")
        return "\n".join(lines)

    def _export_yaml(self, graph: FunctionalityGraph) -> str:
        """Export to YAML format (manual generation, no PyYAML dependency)."""
        lines: list[str] = []
        lines.append("# Functionality Graph Export")
        lines.append(f"# Exported: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")
        lines.append("modules:")

        for m in graph.modules:
            lines.append(f"  - name: {m.name}")
            lines.append(f"    description: \"{m.description}\"")
            lines.append(f"    feature_count: {m.feature_count}")
            if self._config.include_features and m.feature_ids:
                lines.append("    feature_ids:")
                for fid in m.feature_ids:
                    lines.append(f"      - {fid}")
            if self._config.include_rationale and m.rationale:
                lines.append(f"    rationale: \"{m.rationale}\"")
            lines.append("")

        lines.append("dependencies:")
        for d in graph.dependencies:
            lines.append(f"  - source: {d.source}")
            lines.append(f"    target: {d.target}")
            lines.append(f"    type: {d.dependency_type}")
            lines.append(f"    weight: {d.weight}")
            if self._config.include_rationale and d.rationale:
                lines.append(f"    rationale: \"{d.rationale}\"")
            lines.append("")

        if self._config.include_metadata:
            lines.append("metadata:")
            lines.append(f"  module_count: {graph.module_count}")
            lines.append(f"  dependency_count: {graph.dependency_count}")
            lines.append(f"  feature_count: {graph.feature_count}")
            lines.append(f"  is_acyclic: {str(graph.is_acyclic).lower()}")
            lines.append("")

        if self._config.include_metrics and graph.metrics:
            lines.append("metrics:")
            lines.append(f"  avg_cohesion: {graph.metrics.avg_cohesion:.4f}")
            lines.append(f"  max_coupling: {graph.metrics.max_coupling}")
            lines.append(f"  overall_quality: {graph.metrics.overall_quality}")
            if graph.metrics.modularity:
                lines.append(
                    f"  q_score: {graph.metrics.modularity.q_score:.4f}"
                )

        return "\n".join(lines)

    def _export_summary(self, graph: FunctionalityGraph) -> str:
        """Export a human-readable text summary."""
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("FUNCTIONALITY GRAPH SUMMARY")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Modules: {graph.module_count}")
        lines.append(f"Dependencies: {graph.dependency_count}")
        lines.append(f"Total Features: {graph.feature_count}")
        lines.append(f"Acyclic: {graph.is_acyclic}")
        lines.append("")

        lines.append("-" * 40)
        lines.append("MODULES")
        lines.append("-" * 40)
        for m in graph.modules:
            lines.append(f"\n  [{m.name}] ({m.feature_count} features)")
            lines.append(f"  Description: {m.description}")
            if m.feature_ids:
                features_str = ", ".join(m.feature_ids[:10])
                if m.feature_count > 10:
                    features_str += f", ... (+{m.feature_count - 10} more)"
                lines.append(f"  Features: {features_str}")
            if m.public_interface:
                lines.append(
                    f"  Public Interface: {', '.join(m.public_interface)}"
                )

        lines.append("")
        lines.append("-" * 40)
        lines.append("DEPENDENCIES")
        lines.append("-" * 40)
        for d in graph.dependencies:
            lines.append(
                f"\n  {d.source} --[{d.dependency_type}]--> {d.target} "
                f"(weight={d.weight:.2f})"
            )
            if d.rationale:
                lines.append(f"  Rationale: {d.rationale}")

        if graph.metrics:
            lines.append("")
            lines.append("-" * 40)
            lines.append("QUALITY METRICS")
            lines.append("-" * 40)
            lines.append(
                f"  Average Cohesion: {graph.metrics.avg_cohesion:.4f}"
            )
            lines.append(f"  Max Coupling: {graph.metrics.max_coupling}")
            lines.append(
                f"  Overall Quality: {graph.metrics.overall_quality}"
            )
            if graph.metrics.modularity:
                lines.append(
                    f"  Modularity Q-score: "
                    f"{graph.metrics.modularity.q_score:.4f}"
                )

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Phase 1 RPGGraph conversion
    # -------------------------------------------------------------------

    def to_rpg_graph(
        self,
        graph: FunctionalityGraph,
        project_name: str = "zerorepo",
    ) -> RPGGraph:
        """Convert a FunctionalityGraph to a Phase 1 RPGGraph.

        Maps:
        - Each ModuleSpec → an RPGNode (NodeLevel.MODULE)
        - Each feature_id → an RPGNode (NodeLevel.FEATURE) + HIERARCHY edge
        - Each DependencyEdge → an RPGEdge (EdgeType.DATA_FLOW or INVOCATION)

        Args:
            graph: The FunctionalityGraph to convert.
            project_name: Project name for metadata.

        Returns:
            A populated RPGGraph.
        """
        rpg = RPGGraph(
            metadata={
                "project": project_name,
                "source": "FunctionalityGraph",
                "module_count": graph.module_count,
                "feature_count": graph.feature_count,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Track module name → node UUID mapping
        module_node_ids: dict[str, Any] = {}

        # Create module nodes
        for mod in graph.modules:
            node = RPGNode(
                name=mod.name,
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=mod.name.lower().replace(" ", "_"),
                metadata={
                    "description": mod.description,
                    "feature_count": mod.feature_count,
                    "rationale": mod.rationale,
                    "public_interface": list(mod.public_interface),
                },
            )
            rpg.add_node(node)
            module_node_ids[mod.name] = node.id

            # Create feature nodes under this module
            for fid in mod.feature_ids:
                feat_node = RPGNode(
                    name=fid,
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTIONALITY,
                    parent_id=node.id,
                    folder_path=f"{mod.name.lower().replace(' ', '_')}/{fid}",
                    metadata={
                        "module": mod.name,
                        "is_public": fid in mod.public_interface,
                    },
                )
                rpg.add_node(feat_node)

                # HIERARCHY edge from module to feature
                hier_edge = RPGEdge(
                    source_id=node.id,
                    target_id=feat_node.id,
                    edge_type=EdgeType.HIERARCHY,
                )
                rpg.add_edge(hier_edge)

        # Create dependency edges
        for dep in graph.dependencies:
            source_id = module_node_ids.get(dep.source)
            target_id = module_node_ids.get(dep.target)
            if source_id and target_id:
                edge_type = (
                    EdgeType.DATA_FLOW
                    if dep.dependency_type == "data_flow"
                    else EdgeType.INVOCATION
                )
                rpg_edge = RPGEdge(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=edge_type,
                    validated=True,
                )
                rpg.add_edge(rpg_edge)

        logger.info(
            "Converted FunctionalityGraph to RPGGraph: "
            "%d nodes, %d edges",
            rpg.node_count,
            rpg.edge_count,
        )

        return rpg

    # -------------------------------------------------------------------
    # Loading (round-trip)
    # -------------------------------------------------------------------

    @staticmethod
    def from_json(
        json_str: str | None = None,
        filepath: str | Path | None = None,
    ) -> FunctionalityGraph:
        """Load a FunctionalityGraph from JSON.

        Args:
            json_str: JSON string to parse.
            filepath: Path to JSON file to read.

        Returns:
            A FunctionalityGraph instance.

        Raises:
            ValueError: If neither json_str nor filepath provided.
        """
        if json_str is None and filepath is None:
            raise ValueError(
                "Must provide either json_str or filepath"
            )

        if filepath is not None:
            path = Path(filepath)
            json_str = path.read_text(encoding="utf-8")

        assert json_str is not None
        data = json.loads(json_str)

        # Handle both the exporter format and the builder format
        modules_data = data.get("modules", [])
        modules = [
            ModuleSpec(
                name=m["name"],
                description=m.get("description", ""),
                feature_ids=m.get("feature_ids", []),
                public_interface=m.get("public_interface", []),
                rationale=m.get("rationale", ""),
            )
            for m in modules_data
        ]

        deps_data = data.get("dependencies", [])
        dependencies = [
            DependencyEdge(
                source=d["source"],
                target=d["target"],
                dependency_type=d.get("dependency_type", "uses"),
                weight=d.get("weight", 1.0),
                confidence=d.get("confidence", 1.0),
                rationale=d.get("rationale", ""),
            )
            for d in deps_data
        ]

        metadata = data.get("metadata", {})
        is_acyclic = metadata.pop("is_acyclic", True)

        return FunctionalityGraph(
            modules=modules,
            dependencies=dependencies,
            is_acyclic=is_acyclic,
            metadata=metadata,
        )
