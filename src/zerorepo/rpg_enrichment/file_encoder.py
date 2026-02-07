"""FileEncoder – assigns file_path to leaf nodes within their folder namespace.

Epic 3.2: Clusters semantically related leaf features into files,
balancing cohesion with file size constraints.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from uuid import UUID

from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)

# Default max estimated lines-of-code per file.
_MAX_LOC_PER_FILE = 500
# Default complexity-to-LOC multiplier.
_COMPLEXITY_LOC_RATIO = 30


def _to_file_name(name: str) -> str:
    """Convert a feature name to a Python module file name.

    Args:
        name: The feature or cluster name.

    Returns:
        A valid Python file name (e.g. ``"data_loaders.py"``).
    """
    result = name.lower().strip()
    result = re.sub(r"[\s\-\.]+", "_", result)
    result = re.sub(r"[^a-z0-9_]", "", result)
    result = result.strip("_") or "module"
    if result[0].isdigit():
        result = f"_{result}"
    if not result.endswith(".py"):
        result = f"{result}.py"
    return result


class FileEncoder(RPGEncoder):
    """Assign ``file_path`` to leaf nodes by grouping them within folders.

    Strategy:
    1. For each folder namespace (unique ``folder_path``), collect leaf nodes.
    2. Group leaves by their parent node (a simple cohesion heuristic:
       siblings under the same COMPONENT parent likely belong together).
    3. If a group's estimated LOC exceeds ``max_loc_per_file``, split it.
    4. Assign ``file_path = folder_path + file_name`` to each leaf.

    Metadata set per node:
    - ``metadata["estimated_loc"]`` per leaf
    - ``metadata["file_group"]`` cluster label for the leaf
    """

    def __init__(
        self,
        max_loc_per_file: int = _MAX_LOC_PER_FILE,
        complexity_loc_ratio: int = _COMPLEXITY_LOC_RATIO,
    ) -> None:
        self._max_loc = max_loc_per_file
        self._loc_ratio = complexity_loc_ratio

    def encode(self, graph: RPGGraph) -> RPGGraph:
        """Assign file_path to all leaf nodes."""
        if graph.node_count == 0:
            return graph

        # Build parent mapping from HIERARCHY edges
        parent_of: dict[UUID, UUID] = {}
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                parent_of[edge.target_id] = edge.source_id

        # Collect leaf nodes (FEATURE level or nodes with no HIERARCHY children)
        children_of: dict[UUID, list[UUID]] = defaultdict(list)
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                children_of[edge.source_id].append(edge.target_id)

        leaf_ids = [
            nid
            for nid in graph.nodes
            if nid not in children_of or len(children_of[nid]) == 0
        ]

        # Group leaves by folder_path
        folder_groups: dict[str, list[UUID]] = defaultdict(list)
        for lid in leaf_ids:
            node = graph.nodes[lid]
            folder = node.folder_path or ""
            folder_groups[folder].append(lid)

        # For each folder, sub-group by parent and assign files
        for folder, node_ids in folder_groups.items():
            self._assign_files_in_folder(graph, folder, node_ids, parent_of)

        # Ensure non-leaf nodes that should have file_path also get one
        # (e.g., COMPONENT nodes that represent a single class)
        for nid, node in graph.nodes.items():
            if node.file_path is None and node.level == NodeLevel.FEATURE:
                # FEATURE nodes without file_path: skip (they're structural)
                pass

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate file assignments for leaf nodes."""
        errors: list[str] = []
        warnings: list[str] = []

        # Build children map for leaf detection
        children_of: set[UUID] = set()
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                children_of.add(edge.source_id)

        leaf_ids = [nid for nid in graph.nodes if nid not in children_of]

        for lid in leaf_ids:
            node = graph.nodes[lid]
            if node.file_path is None:
                errors.append(
                    f"Leaf node {lid} ({node.name}): missing file_path"
                )
            elif node.folder_path and not node.file_path.startswith(node.folder_path):
                errors.append(
                    f"Leaf node {lid} ({node.name}): file_path '{node.file_path}' "
                    f"not under folder_path '{node.folder_path}'"
                )

            estimated_loc = node.metadata.get("estimated_loc", 0)
            if estimated_loc > self._max_loc:
                warnings.append(
                    f"Leaf node {lid} ({node.name}): estimated {estimated_loc} LOC "
                    f"exceeds {self._max_loc}"
                )

        # Check file-level size estimates
        file_loc: dict[str, int] = defaultdict(int)
        for lid in leaf_ids:
            node = graph.nodes[lid]
            if node.file_path:
                file_loc[node.file_path] += node.metadata.get("estimated_loc", 0)

        for fpath, total_loc in file_loc.items():
            if total_loc > self._max_loc:
                warnings.append(
                    f"File '{fpath}' estimated at {total_loc} LOC "
                    f"(max {self._max_loc})"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _assign_files_in_folder(
        self,
        graph: RPGGraph,
        folder: str,
        node_ids: list[UUID],
        parent_of: dict[UUID, UUID],
    ) -> None:
        """Group nodes in a folder and assign file paths."""
        # Group by parent (siblings → same file)
        parent_groups: dict[UUID | None, list[UUID]] = defaultdict(list)
        for nid in node_ids:
            parent_id = parent_of.get(nid)
            parent_groups[parent_id].append(nid)

        # Track used file names to avoid collisions
        used_names: set[str] = set()

        for parent_id, group_nids in parent_groups.items():
            # Estimate LOC for group
            total_loc = 0
            for nid in group_nids:
                node = graph.nodes[nid]
                est = node.metadata.get("complexity_estimate", 3) * self._loc_ratio
                node.metadata["estimated_loc"] = est
                total_loc += est

            # If group exceeds max LOC, split into sub-groups
            if total_loc > self._max_loc and len(group_nids) > 1:
                sub_groups = self._split_group(graph, group_nids)
            else:
                sub_groups = [group_nids]

            for sub_group in sub_groups:
                # File name from the first node's name or parent name
                if parent_id and parent_id in graph.nodes:
                    base_name = graph.nodes[parent_id].name
                else:
                    base_name = graph.nodes[sub_group[0]].name

                file_name = _to_file_name(base_name)

                # Deduplicate file names
                if file_name in used_names:
                    idx = 2
                    while f"{file_name[:-3]}_{idx}.py" in used_names:
                        idx += 1
                    file_name = f"{file_name[:-3]}_{idx}.py"
                used_names.add(file_name)

                file_path = f"{folder}{file_name}"

                for nid in sub_group:
                    node = graph.nodes[nid]
                    node.file_path = file_path
                    node.metadata["file_group"] = file_name

                logger.debug(
                    "Assigned %d nodes to %s",
                    len(sub_group),
                    file_path,
                )

    @staticmethod
    def _split_group(
        graph: RPGGraph,
        node_ids: list[UUID],
    ) -> list[list[UUID]]:
        """Split an oversized group roughly in half."""
        mid = len(node_ids) // 2
        return [node_ids[:mid], node_ids[mid:]]
