"""FolderEncoder – assigns folder_path to module and descendant nodes.

Epic 3.1: Maps functional subgraphs (modules) to directory namespaces
with consistent inheritance down the HIERARCHY tree.
"""

from __future__ import annotations

import keyword
import logging
import re
from collections import deque
from typing import Any
from uuid import UUID

from zerorepo.models.enums import EdgeType, NodeLevel
from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)

# Maximum files per folder before recommending a submodule split.
_MAX_FILES_PER_FOLDER = 15


def _to_package_name(name: str) -> str:
    """Convert a human-readable name to a valid Python package name.

    Rules:
    - Lowercase
    - Replace spaces/hyphens/dots with underscores
    - Strip non-alphanumeric/underscore characters
    - Prefix with underscore if starts with a digit
    - Avoid Python keywords by appending ``_pkg``

    Args:
        name: The human-readable name.

    Returns:
        A valid Python identifier suitable for a package directory.
    """
    result = name.lower().strip()
    result = re.sub(r"[\s\-\.]+", "_", result)
    result = re.sub(r"[^a-z0-9_]", "", result)
    # Remove leading underscores, then re-add one if starts with digit
    result = result.lstrip("_") or "unnamed"
    if result[0].isdigit():
        result = f"_{result}"
    if keyword.iskeyword(result):
        result = f"{result}_pkg"
    return result


class FolderEncoder(RPGEncoder):
    """Assign ``folder_path`` to every node via HIERARCHY-based namespace inheritance.

    Strategy:
    1. Find root nodes (no incoming HIERARCHY edges).
    2. Assign ``folder_path = ""`` to roots (project root).
    3. BFS down HIERARCHY edges, propagating
       ``parent.folder_path + _to_package_name(child.name) + "/"``.
    4. Warn if any module folder exceeds ``max_files_per_folder`` estimated files.

    Metadata set per node:
    - ``folder_path`` (on the node itself, not in metadata dict)
    - ``metadata["estimated_files"]`` on MODULE-level nodes
    - ``metadata["folder_oversized"]`` if estimated files > max
    """

    def __init__(self, max_files_per_folder: int = _MAX_FILES_PER_FOLDER) -> None:
        self._max_files = max_files_per_folder

    def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        """Assign folder_path to all nodes via HIERARCHY BFS."""
        if graph.node_count == 0:
            return graph

        # Build parent→children adjacency from HIERARCHY edges
        children_of: dict[UUID, list[UUID]] = {}
        has_parent: set[UUID] = set()
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                children_of.setdefault(edge.source_id, []).append(edge.target_id)
                has_parent.add(edge.target_id)

        # Root nodes = nodes with no incoming HIERARCHY edge
        roots = [nid for nid in graph.nodes if nid not in has_parent]

        if not roots:
            # All nodes have parents — likely the graph has no HIERARCHY edges.
            # Fall back: treat all MODULE-level nodes as roots.
            roots = [
                nid
                for nid, node in graph.nodes.items()
                if node.level == NodeLevel.MODULE
            ]
        if not roots:
            # Last resort: treat all nodes as roots
            roots = list(graph.nodes.keys())

        # BFS to propagate folder_path
        visited: set[UUID] = set()
        queue: deque[UUID] = deque()

        for root_id in roots:
            node = graph.nodes[root_id]
            # Roots get empty folder_path (project root)
            if node.folder_path is None:
                node.folder_path = ""
            visited.add(root_id)
            queue.append(root_id)

        while queue:
            parent_id = queue.popleft()
            parent_node = graph.nodes[parent_id]
            parent_path = parent_node.folder_path or ""

            for child_id in children_of.get(parent_id, []):
                if child_id in visited:
                    continue
                visited.add(child_id)

                child_node = graph.nodes[child_id]
                pkg_name = _to_package_name(child_node.name)
                child_node.folder_path = f"{parent_path}{pkg_name}/"

                # For FILE_AUGMENTED or FUNCTION_AUGMENTED leaf nodes that also
                # have a file_path, ensure file_path is under the folder
                if child_node.file_path and not child_node.file_path.startswith(
                    child_node.folder_path
                ):
                    child_node.file_path = f"{child_node.folder_path}{child_node.file_path.rsplit('/', 1)[-1]}"

                queue.append(child_id)

        # Handle unvisited nodes (disconnected from HIERARCHY)
        for nid, node in graph.nodes.items():
            if nid not in visited and node.folder_path is None:
                node.folder_path = ""
                logger.debug(
                    "Node %s (%s) has no HIERARCHY parent, assigned root folder",
                    nid,
                    node.name,
                )

        # Estimate files per MODULE folder and flag oversized
        self._estimate_folder_sizes(graph, children_of)

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate that all nodes have valid folder_path assignments."""
        errors: list[str] = []
        warnings: list[str] = []

        for nid, node in graph.nodes.items():
            if node.folder_path is None:
                errors.append(f"Node {nid} ({node.name}): missing folder_path")
                continue

            # Validate folder name components are valid identifiers
            parts = [p for p in node.folder_path.split("/") if p]
            for part in parts:
                if not part.isidentifier():
                    errors.append(
                        f"Node {nid} ({node.name}): folder component '{part}' "
                        f"is not a valid Python identifier"
                    )

            # Check for oversized folders
            if node.metadata.get("folder_oversized"):
                warnings.append(
                    f"Node {nid} ({node.name}): folder has "
                    f"{node.metadata.get('estimated_files', '?')} estimated files "
                    f"(max {self._max_files}), consider submodule split"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _estimate_folder_sizes(
        self,
        graph: RPGGraph,
        children_of: dict[UUID, list[UUID]],
    ) -> None:
        """Estimate file count per MODULE folder and flag oversized ones."""
        for nid, node in graph.nodes.items():
            if node.level != NodeLevel.MODULE:
                continue

            # Count leaf descendants (heuristic: leaf_count / 3 files)
            leaf_count = self._count_leaves(nid, children_of, graph)
            estimated_files = max(1, leaf_count // 3)
            node.metadata["estimated_files"] = estimated_files

            if estimated_files > self._max_files:
                node.metadata["folder_oversized"] = True
                logger.warning(
                    "Module %s (%s): estimated %d files exceeds max %d",
                    nid,
                    node.name,
                    estimated_files,
                    self._max_files,
                )

    @staticmethod
    def _count_leaves(
        node_id: UUID,
        children_of: dict[UUID, list[UUID]],
        graph: RPGGraph,
    ) -> int:
        """Count leaf descendants of a node (nodes with no children in HIERARCHY)."""
        count = 0
        queue: deque[UUID] = deque([node_id])
        visited: set[UUID] = {node_id}

        while queue:
            current = queue.popleft()
            kids = children_of.get(current, [])
            if not kids and current != node_id:
                count += 1
            for kid in kids:
                if kid not in visited:
                    visited.add(kid)
                    queue.append(kid)

        return count
