"""IntraModuleOrderEncoder – computes file_order within each module.

Epic 3.4: Topologically sorts files within each module based on
internal dependency edges, producing an import-safe file_order.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from uuid import UUID

from zerorepo.models.enums import EdgeType, NodeLevel
from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)


class IntraModuleOrderEncoder(RPGEncoder):
    """Compute ``file_order`` for MODULE-level nodes.

    Strategy:
    1. For each MODULE node, collect all distinct ``file_path`` values
       from its HIERARCHY descendants.
    2. Build a file-level dependency graph from DATA_FLOW and INVOCATION
       edges between nodes in different files within the same module.
    3. Topologically sort the file-level graph.
    4. Store the result in ``metadata["file_order"]`` on the module node.

    If a circular dependency is detected, the encoder records the files
    in arbitrary order and adds a warning.
    """

    def encode(self, graph: RPGGraph) -> RPGGraph:
        """Compute file_order for all MODULE nodes."""
        if graph.node_count == 0:
            return graph

        # Build HIERARCHY children map
        children_of: dict[UUID, list[UUID]] = defaultdict(list)
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                children_of[edge.source_id].append(edge.target_id)

        # Map node_id → file_path for file-level dependency building
        node_to_file: dict[UUID, str] = {}
        for nid, node in graph.nodes.items():
            if node.file_path:
                node_to_file[nid] = node.file_path

        # Build file-level dependency edges from DATA_FLOW and INVOCATION
        dep_types = {EdgeType.DATA_FLOW, EdgeType.INVOCATION}
        file_deps: set[tuple[str, str]] = set()
        for edge in graph.edges.values():
            if edge.edge_type not in dep_types:
                continue
            src_file = node_to_file.get(edge.source_id)
            tgt_file = node_to_file.get(edge.target_id)
            if src_file and tgt_file and src_file != tgt_file:
                # source depends on target → target must come first
                file_deps.add((tgt_file, src_file))

        # Process each MODULE node
        for nid, node in graph.nodes.items():
            if node.level != NodeLevel.MODULE:
                continue

            # Collect files in this module
            module_files = self._collect_module_files(nid, children_of, graph)
            if not module_files:
                node.metadata["file_order"] = []
                continue

            # Filter file deps to only those within this module
            module_file_set = set(module_files)
            local_deps = [
                (src, tgt)
                for src, tgt in file_deps
                if src in module_file_set and tgt in module_file_set
            ]

            # Topological sort
            order, has_cycle = self._toposort(module_files, local_deps)

            if has_cycle:
                logger.warning(
                    "Module %s (%s): circular file dependency detected",
                    nid,
                    node.name,
                )
                node.metadata["file_order_circular"] = True

            node.metadata["file_order"] = order
            logger.debug(
                "Module %s (%s): file_order = %s",
                nid,
                node.name,
                order,
            )

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate that MODULE nodes have file_order."""
        errors: list[str] = []
        warnings: list[str] = []

        for nid, node in graph.nodes.items():
            if node.level != NodeLevel.MODULE:
                continue

            file_order = node.metadata.get("file_order")
            if file_order is None:
                errors.append(
                    f"Module {nid} ({node.name}): missing file_order"
                )
            elif node.metadata.get("file_order_circular"):
                warnings.append(
                    f"Module {nid} ({node.name}): circular dependency in file_order"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _collect_module_files(
        module_id: UUID,
        children_of: dict[UUID, list[UUID]],
        graph: RPGGraph,
    ) -> list[str]:
        """Collect all distinct file_path values from a module's descendants."""
        files: list[str] = []
        seen: set[str] = set()
        queue: deque[UUID] = deque([module_id])
        visited: set[UUID] = {module_id}

        while queue:
            current = queue.popleft()
            node = graph.nodes[current]
            if node.file_path and node.file_path not in seen:
                seen.add(node.file_path)
                files.append(node.file_path)
            for child_id in children_of.get(current, []):
                if child_id not in visited:
                    visited.add(child_id)
                    queue.append(child_id)

        return files

    @staticmethod
    def _toposort(
        items: list[str],
        deps: list[tuple[str, str]],
    ) -> tuple[list[str], bool]:
        """Topological sort of string items with (prerequisite, dependent) deps.

        Returns:
            A tuple of (sorted_items, has_cycle).
        """
        in_degree: dict[str, int] = {item: 0 for item in items}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for pre, dep in deps:
            if pre in in_degree and dep in in_degree:
                adjacency[pre].append(dep)
                in_degree[dep] += 1

        queue: deque[str] = deque(
            item for item, deg in in_degree.items() if deg == 0
        )
        result: list[str] = []

        while queue:
            current = queue.popleft()
            result.append(current)
            for neighbor in adjacency.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        has_cycle = len(result) != len(items)
        if has_cycle:
            # Include remaining items in arbitrary order
            remaining = [item for item in items if item not in set(result)]
            result.extend(remaining)

        return result, has_cycle
