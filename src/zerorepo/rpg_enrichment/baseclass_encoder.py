"""BaseClassEncoder – identifies shared patterns and creates abstract base classes.

Epic 3.5: Detects similar leaf features, extracts abstract base classes,
and links derived features via inheritance.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any
from uuid import UUID

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)

# Minimum number of similar features to justify a base class.
_MIN_FEATURES_FOR_ABSTRACTION = 3


def _extract_common_suffix(names: list[str]) -> str | None:
    """Extract a common suffix from a list of names.

    Example: ['linear_regression', 'ridge_regression', 'lasso_regression']
    → 'regression'

    Args:
        names: List of feature names.

    Returns:
        The common suffix or None if no shared suffix exists.
    """
    if len(names) < 2:
        return None

    # Split each name into parts
    parts_list = [name.lower().replace("-", "_").split("_") for name in names]
    if not all(parts_list):
        return None

    # Compare from the end
    min_len = min(len(p) for p in parts_list)
    common_parts: list[str] = []

    for i in range(1, min_len + 1):
        suffixes = {tuple(p[-i:]) for p in parts_list}
        if len(suffixes) == 1:
            common_parts = list(suffixes.pop())
        else:
            break

    return "_".join(common_parts) if common_parts else None


def _generate_base_class_name(common_suffix: str) -> str:
    """Generate a PascalCase base class name from a common suffix.

    Example: 'regression' → 'BaseRegression'
    """
    parts = common_suffix.split("_")
    pascal = "".join(p.capitalize() for p in parts if p)
    return f"Base{pascal}"


class BaseClassEncoder(RPGEncoder):
    """Detect shared patterns across leaf features and create abstract base classes.

    Strategy:
    1. For each MODULE, collect leaf features.
    2. Group features by naming pattern (common suffix).
    3. If a group has ``>= min_features_for_abstraction`` members,
       create an abstract base class node.
    4. Add INHERITANCE edges from derived features to the base class.
    5. Record ``inherits_from``, ``is_abstract``, ``abstract_methods`` metadata.

    Metadata set:
    - ``metadata["is_abstract"]`` = True on base class nodes
    - ``metadata["abstract_methods"]`` = list of method names
    - ``metadata["inherits_from"]`` = base class node UUID on derived nodes
    """

    def __init__(
        self,
        min_features_for_abstraction: int = _MIN_FEATURES_FOR_ABSTRACTION,
    ) -> None:
        self._min_features = min_features_for_abstraction

    def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        """Detect patterns and create base class nodes."""
        if graph.node_count == 0:
            return graph

        # Build HIERARCHY children map
        children_of: dict[UUID, list[UUID]] = defaultdict(list)
        parent_of: dict[UUID, UUID] = {}
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.HIERARCHY:
                children_of[edge.source_id].append(edge.target_id)
                parent_of[edge.target_id] = edge.source_id

        # Find leaf nodes (no HIERARCHY children)
        leaf_ids = [
            nid for nid in graph.nodes if nid not in children_of
        ]

        # Group leaves by module
        module_leaves: dict[UUID | None, list[UUID]] = defaultdict(list)
        for lid in leaf_ids:
            # Walk up to find module
            current = lid
            module_id = None
            while current in parent_of:
                current = parent_of[current]
                if graph.nodes[current].level == NodeLevel.MODULE:
                    module_id = current
                    break
            module_leaves[module_id].append(lid)

        # For each module, detect patterns
        for module_id, leaves in module_leaves.items():
            if len(leaves) < self._min_features:
                continue

            leaf_names = {lid: graph.nodes[lid].name for lid in leaves}
            groups = self._group_by_suffix(leaf_names)

            for suffix, group_ids in groups.items():
                if len(group_ids) < self._min_features:
                    continue

                base_class_name = _generate_base_class_name(suffix)
                self._create_base_class(
                    graph,
                    base_class_name=base_class_name,
                    derived_ids=group_ids,
                    module_id=module_id,
                    common_suffix=suffix,
                )

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate base class creation and inheritance links."""
        errors: list[str] = []
        warnings: list[str] = []

        # Find base class nodes
        base_classes = [
            (nid, node)
            for nid, node in graph.nodes.items()
            if node.metadata.get("is_abstract") is True
        ]

        for bc_id, bc_node in base_classes:
            # Check abstract_methods is set
            methods = bc_node.metadata.get("abstract_methods", [])
            if not methods:
                warnings.append(
                    f"Base class {bc_id} ({bc_node.name}): no abstract_methods defined"
                )

            # Check that at least one derived node references this base
            has_derived = any(
                node.metadata.get("inherits_from") == bc_id
                for node in graph.nodes.values()
            )
            if not has_derived:
                warnings.append(
                    f"Base class {bc_id} ({bc_node.name}): no derived nodes found"
                )

        # Check derived nodes point to valid base classes
        for nid, node in graph.nodes.items():
            base_id = node.metadata.get("inherits_from")
            if base_id is not None and base_id not in graph.nodes:
                errors.append(
                    f"Node {nid} ({node.name}): inherits_from {base_id} "
                    f"not found in graph"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _group_by_suffix(
        leaf_names: dict[UUID, str],
    ) -> dict[str, list[UUID]]:
        """Group leaf node IDs by their common name suffix."""
        # Try all pairs to find common suffixes
        suffixes: dict[str, set[UUID]] = defaultdict(set)

        ids = list(leaf_names.keys())
        names = list(leaf_names.values())

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                suffix = _extract_common_suffix([names[i], names[j]])
                if suffix:
                    suffixes[suffix].add(ids[i])
                    suffixes[suffix].add(ids[j])

        # Convert to sorted lists
        return {
            suffix: sorted(id_set, key=lambda x: leaf_names.get(x, ""))
            for suffix, id_set in suffixes.items()
        }

    def _create_base_class(
        self,
        graph: RPGGraph,
        base_class_name: str,
        derived_ids: list[UUID],
        module_id: UUID | None,
        common_suffix: str,
    ) -> UUID:
        """Create an abstract base class node and link derived features."""
        # Determine folder_path from module or first derived node
        folder_path = ""
        if module_id and module_id in graph.nodes:
            folder_path = graph.nodes[module_id].folder_path or ""
        elif derived_ids:
            first = graph.nodes.get(derived_ids[0])
            if first and first.folder_path:
                folder_path = first.folder_path

        # Create the base class node
        base_node = RPGNode(
            name=base_class_name,
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.CLASS,
            signature=f"class {base_class_name}(ABC):",
            folder_path=folder_path,
            file_path=f"{folder_path}base.py" if folder_path else "base.py",
            metadata={
                "is_abstract": True,
                "abstract_methods": self._infer_abstract_methods(
                    graph, derived_ids
                ),
                "derived_count": len(derived_ids),
                "common_suffix": common_suffix,
            },
        )
        graph.add_node(base_node)

        # Link to module via HIERARCHY if module exists
        if module_id and module_id in graph.nodes:
            graph.add_edge(
                RPGEdge(
                    source_id=module_id,
                    target_id=base_node.id,
                    edge_type=EdgeType.HIERARCHY,
                )
            )

        # Link derived features
        for derived_id in derived_ids:
            derived_node = graph.nodes.get(derived_id)
            if derived_node:
                derived_node.metadata["inherits_from"] = base_node.id
                # Add INHERITANCE edge
                graph.add_edge(
                    RPGEdge(
                        source_id=base_node.id,
                        target_id=derived_id,
                        edge_type=EdgeType.INHERITANCE,
                    )
                )

        logger.info(
            "Created base class %s with %d derived features",
            base_class_name,
            len(derived_ids),
        )

        return base_node.id

    @staticmethod
    def _infer_abstract_methods(
        graph: RPGGraph,
        derived_ids: list[UUID],
    ) -> list[str]:
        """Infer abstract methods from common patterns in derived feature names.

        Heuristic: look for common verbs/action words across derived features.
        Default to standard patterns like 'execute', 'process', 'run'.
        """
        common_words: defaultdict[str, int] = defaultdict(int)

        for did in derived_ids:
            node = graph.nodes.get(did)
            if not node:
                continue
            # Extract action words from name
            words = node.name.lower().replace("-", "_").split("_")
            for word in words:
                if len(word) > 2:  # Skip short words
                    common_words[word] += 1

        # Find words common to most derived features
        threshold = max(2, len(derived_ids) // 2)
        common = [
            word
            for word, count in sorted(
                common_words.items(), key=lambda x: -x[1]
            )
            if count >= threshold
        ]

        if not common:
            # Default abstract methods
            return ["execute", "validate"]

        # Use common words as method names
        methods = []
        for word in common[:3]:  # Max 3 abstract methods
            if word not in ("base", "abstract"):
                methods.append(word)

        return methods or ["execute", "validate"]
