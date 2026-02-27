"""DataFlowEncoder – encodes typed inter-module data flow edges.

Epic 3.3: Builds a typed DAG of data flows between modules,
adding DATA_FLOW edges with input/output schema metadata.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, NodeLevel
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.rpg_enrichment.base import RPGEncoder
from cobuilder.repomap.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)

# Common type mapping for heuristic inference
_TYPE_HINTS: dict[str, str] = {
    "data": "pd.DataFrame",
    "dataset": "pd.DataFrame",
    "dataframe": "pd.DataFrame",
    "array": "np.ndarray",
    "matrix": "np.ndarray",
    "tensor": "np.ndarray",
    "vector": "np.ndarray",
    "text": "str",
    "string": "str",
    "path": "Path",
    "file": "Path",
    "config": "dict[str, Any]",
    "configuration": "dict[str, Any]",
    "settings": "dict[str, Any]",
    "model": "BaseModel",
    "result": "dict[str, Any]",
    "results": "list[dict[str, Any]]",
    "score": "float",
    "scores": "list[float]",
    "metric": "float",
    "metrics": "dict[str, float]",
    "predictions": "np.ndarray",
    "labels": "np.ndarray",
    "features": "np.ndarray",
    "weights": "np.ndarray",
    "parameters": "dict[str, Any]",
    "index": "int",
    "count": "int",
    "flag": "bool",
    "image": "np.ndarray",
    "images": "list[np.ndarray]",
    "list": "list[Any]",
    "mapping": "dict[str, Any]",
}


def _infer_type_from_name(name: str) -> str:
    """Infer a Python type annotation from a feature/module name.

    Uses keyword matching against common ML/data science naming patterns.
    Falls back to ``Any`` if no match is found.

    Args:
        name: The name to infer a type from.

    Returns:
        A Python type annotation string.
    """
    lower = name.lower()
    for keyword, type_hint in _TYPE_HINTS.items():
        if keyword in lower:
            return type_hint
    return "Any"


class DataFlowEncoder(RPGEncoder):
    """Encode inter-module data flow edges with typed schemas.

    Strategy:
    1. Identify existing DATA_FLOW edges between nodes in different modules.
    2. For edges without ``data_type``, infer type from node names.
    3. Record ``input_schema`` and ``output_schema`` in node metadata.
    4. Validate that the inter-module data flow DAG is acyclic.

    If no existing DATA_FLOW edges exist between modules, the encoder
    creates new ones based on HIERARCHY structure and node dependencies.

    Metadata set:
    - ``metadata["input_schema"]`` on target nodes of DATA_FLOW edges
    - ``metadata["output_schema"]`` on source nodes of DATA_FLOW edges
    - ``metadata["flow_validated"]`` on DATA_FLOW edges (via edge validated field)
    """

    def encode(self, graph: RPGGraph, spec: Any | None = None, baseline: RPGGraph | None = None) -> RPGGraph:
        """Encode data flow types on inter-module edges.

        When a ``baseline`` is provided, existing DATA_FLOW edges from the
        baseline are used to supplement the current graph's edges. This
        preserves real dependency relationships with accurate type
        annotations from previously analysed code.
        """
        if graph.node_count == 0:
            return graph

        # --- Merge baseline DATA_FLOW edges into the current graph ---
        if baseline:
            self._merge_baseline_edges(graph, baseline)

        # Map each node to its module (MODULE-level ancestor)
        node_to_module = self._build_module_map(graph)

        # Process existing DATA_FLOW edges
        for edge in list(graph.edges.values()):
            if edge.edge_type != EdgeType.DATA_FLOW:
                continue

            src_mod = node_to_module.get(edge.source_id)
            tgt_mod = node_to_module.get(edge.target_id)

            # Only annotate inter-module edges
            if src_mod == tgt_mod and src_mod is not None:
                continue

            # Infer data_type if not already set
            if edge.data_type is None:
                src_node = graph.nodes.get(edge.source_id)
                tgt_node = graph.nodes.get(edge.target_id)
                if src_node:
                    inferred = _infer_type_from_name(src_node.name)
                    edge.data_type = inferred
                    edge.data_id = edge.data_id or src_node.name

            # Set schemas on connected nodes
            self._annotate_schemas(graph, edge)
            edge.validated = True

        # Check for module pairs that have dependencies but no DATA_FLOW edges
        self._create_missing_flows(graph, node_to_module)

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate data flow edges have typed schemas and DAG is acyclic."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check DATA_FLOW edges have data_type
        for eid, edge in graph.edges.items():
            if edge.edge_type != EdgeType.DATA_FLOW:
                continue
            if edge.data_type is None:
                warnings.append(
                    f"DATA_FLOW edge {eid}: missing data_type annotation"
                )

        # Check for cycles in DATA_FLOW edges between modules
        node_to_module = self._build_module_map(graph)
        module_graph: dict[UUID, set[UUID]] = defaultdict(set)

        for edge in graph.edges.values():
            if edge.edge_type != EdgeType.DATA_FLOW:
                continue
            src_mod = node_to_module.get(edge.source_id)
            tgt_mod = node_to_module.get(edge.target_id)
            if src_mod and tgt_mod and src_mod != tgt_mod:
                module_graph[src_mod].add(tgt_mod)

        # Simple cycle detection via DFS
        if self._has_cycle(module_graph):
            errors.append(
                "Inter-module DATA_FLOW graph contains a cycle"
            )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _merge_baseline_edges(graph: RPGGraph, baseline: RPGGraph) -> None:
        """Merge DATA_FLOW edges from the baseline into the current graph.

        For each baseline DATA_FLOW edge, finds matching source/target nodes
        in the current graph by name. If both endpoints exist and no
        equivalent edge already exists, creates a new DATA_FLOW edge with
        the baseline's type annotations.

        Also updates existing edges with baseline type information when
        matching edges are found but have inferior type annotations (e.g.
        ``Any`` replaced by a real Pydantic model name).

        Args:
            graph: The current RPGGraph to enrich.
            baseline: The baseline RPGGraph with real dependency data.
        """
        # Build name→node lookup for current graph
        name_to_node: dict[str, Any] = {}
        for node in graph.nodes.values():
            name_to_node[node.name.lower()] = node

        # Build existing DATA_FLOW edge set by (source_name, target_name)
        existing_flows: set[tuple[str, str]] = set()
        edge_by_names: dict[tuple[str, str], RPGEdge] = {}
        for edge in graph.edges.values():
            if edge.edge_type != EdgeType.DATA_FLOW:
                continue
            src = graph.nodes.get(edge.source_id)
            tgt = graph.nodes.get(edge.target_id)
            if src and tgt:
                key = (src.name.lower(), tgt.name.lower())
                existing_flows.add(key)
                edge_by_names[key] = edge

        # Process baseline DATA_FLOW edges
        for b_edge in baseline.edges.values():
            if b_edge.edge_type != EdgeType.DATA_FLOW:
                continue

            b_src = baseline.nodes.get(b_edge.source_id)
            b_tgt = baseline.nodes.get(b_edge.target_id)
            if not b_src or not b_tgt:
                continue

            src_key = b_src.name.lower()
            tgt_key = b_tgt.name.lower()
            current_src = name_to_node.get(src_key)
            current_tgt = name_to_node.get(tgt_key)

            if not current_src or not current_tgt:
                continue
            if current_src.id == current_tgt.id:
                continue

            key = (src_key, tgt_key)

            if key in existing_flows:
                # Upgrade type annotation if baseline has better info
                existing_edge = edge_by_names.get(key)
                if (
                    existing_edge
                    and b_edge.data_type
                    and (
                        existing_edge.data_type is None
                        or existing_edge.data_type == "Any"
                    )
                ):
                    existing_edge.data_type = b_edge.data_type
                    existing_edge.data_id = b_edge.data_id or existing_edge.data_id
                    if current_src:
                        current_src.metadata["baseline_dataflow_upgraded"] = True
            else:
                # Create new DATA_FLOW edge from baseline
                new_edge = RPGEdge(
                    source_id=current_src.id,
                    target_id=current_tgt.id,
                    edge_type=EdgeType.DATA_FLOW,
                    data_id=b_edge.data_id,
                    data_type=b_edge.data_type,
                    validated=True,
                )
                graph.add_edge(new_edge)
                existing_flows.add(key)
                edge_by_names[key] = new_edge

                # Mark nodes as having baseline-derived edges
                current_src.metadata["baseline_dataflow_source"] = True
                current_tgt.metadata["baseline_dataflow_target"] = True

                logger.info(
                    "Merged baseline DATA_FLOW: %s → %s (type: %s)",
                    b_src.name, b_tgt.name, b_edge.data_type,
                )

    @staticmethod
    def _build_module_map(graph: RPGGraph) -> dict[UUID, UUID]:
        """Map each node to its nearest MODULE ancestor via HIERARCHY edges."""
        # Build parent map
        parent_of: dict[UUID, UUID] = {}
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                parent_of[edge.target_id] = edge.source_id

        node_to_module: dict[UUID, UUID] = {}
        for nid, node in graph.nodes.items():
            if node.level == NodeLevel.MODULE:
                node_to_module[nid] = nid
            else:
                # Walk up to find MODULE ancestor
                current = nid
                while current in parent_of:
                    current = parent_of[current]
                    if graph.nodes[current].level == NodeLevel.MODULE:
                        node_to_module[nid] = current
                        break

        return node_to_module

    @staticmethod
    def _annotate_schemas(graph: RPGGraph, edge: RPGEdge) -> None:
        """Set input/output schema metadata on nodes connected by a DATA_FLOW edge."""
        src_node = graph.nodes.get(edge.source_id)
        tgt_node = graph.nodes.get(edge.target_id)

        if src_node and edge.data_type:
            output_schema = src_node.metadata.get("output_schema", {})
            output_schema[edge.data_id or "output"] = edge.data_type
            src_node.metadata["output_schema"] = output_schema

        if tgt_node and edge.data_type:
            input_schema = tgt_node.metadata.get("input_schema", {})
            input_schema[edge.data_id or "input"] = edge.data_type
            tgt_node.metadata["input_schema"] = input_schema

    def _create_missing_flows(
        self, graph: RPGGraph, node_to_module: dict[UUID, UUID]
    ) -> None:
        """Create DATA_FLOW edges for module pairs connected by other edge types."""
        # Find module pairs connected by INVOCATION or ORDERING edges
        existing_flows: set[tuple[UUID, UUID]] = set()
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.DATA_FLOW:
                src_mod = node_to_module.get(edge.source_id)
                tgt_mod = node_to_module.get(edge.target_id)
                if src_mod and tgt_mod:
                    existing_flows.add((src_mod, tgt_mod))

        for edge in list(graph.edges.values()):
            if edge.edge_type not in (EdgeType.INVOCATION, EdgeType.ORDERING):
                continue
            src_mod = node_to_module.get(edge.source_id)
            tgt_mod = node_to_module.get(edge.target_id)
            if (
                src_mod
                and tgt_mod
                and src_mod != tgt_mod
                and (src_mod, tgt_mod) not in existing_flows
            ):
                # Create a DATA_FLOW edge between the modules
                src_node = graph.nodes[edge.source_id]
                tgt_node = graph.nodes[edge.target_id]
                inferred_type = _infer_type_from_name(src_node.name)

                new_edge = RPGEdge(
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    edge_type=EdgeType.DATA_FLOW,
                    data_id=src_node.name,
                    data_type=inferred_type,
                )
                graph.add_edge(new_edge)
                self._annotate_schemas(graph, new_edge)
                existing_flows.add((src_mod, tgt_mod))

                logger.info(
                    "Created DATA_FLOW edge: %s → %s (type: %s)",
                    src_node.name,
                    tgt_node.name,
                    inferred_type,
                )

    @staticmethod
    def _has_cycle(adjacency: dict[UUID, set[UUID]]) -> bool:
        """Check if a directed graph has a cycle using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[UUID, int] = {}

        # Collect all nodes
        all_nodes: set[UUID] = set(adjacency.keys())
        for targets in adjacency.values():
            all_nodes.update(targets)

        for node in all_nodes:
            color[node] = WHITE

        def _dfs(n: UUID) -> bool:
            color[n] = GRAY
            for neighbor in adjacency.get(n, set()):
                if color.get(neighbor) == GRAY:
                    return True
                if color.get(neighbor) == WHITE and _dfs(neighbor):
                    return True
            color[n] = BLACK
            return False

        for node in all_nodes:
            if color[node] == WHITE and _dfs(node):
                return True
        return False
