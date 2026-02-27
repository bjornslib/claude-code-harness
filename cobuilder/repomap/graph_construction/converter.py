"""FunctionalityGraph → RPGGraph converter.

Converts the module-level FunctionalityGraph produced by
:class:`FunctionalityGraphBuilder` into the richer RPGGraph schema
expected by the RPG enrichment pipeline (Epics 3.x).

Mapping strategy:

- Each :class:`ModuleSpec` → :class:`RPGNode` at ``NodeLevel.MODULE``
- Each ``feature_id`` within a module → :class:`RPGNode` at
  ``NodeLevel.FEATURE`` (or ``COMPONENT`` when aggregated)
- Parent-child MODULE→FEATURE links → :class:`RPGEdge` with
  ``EdgeType.HIERARCHY``
- Each :class:`DependencyEdge` → :class:`RPGEdge` with
  ``EdgeType.DATA_FLOW``

Example::

    from cobuilder.repomap.graph_construction.converter import (
        FunctionalityGraphConverter,
    )

    converter = FunctionalityGraphConverter()
    rpg_graph = converter.convert(functionality_graph)
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from cobuilder.repomap.graph_construction.builder import FunctionalityGraph
from cobuilder.repomap.graph_construction.dependencies import DependencyEdge
from cobuilder.repomap.graph_construction.partitioner import ModuleSpec
from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import DeltaStatus, EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode

logger = logging.getLogger(__name__)


class FunctionalityGraphConverter:
    """Convert a :class:`FunctionalityGraph` into an :class:`RPGGraph`.

    Creates RPGNode objects at MODULE and FEATURE levels with HIERARCHY
    edges between them.  Module-to-module dependencies from the
    FunctionalityGraph are mapped to DATA_FLOW edges in the RPGGraph.

    Example::

        converter = FunctionalityGraphConverter()
        rpg = converter.convert(func_graph)
    """

    def convert(
        self,
        func_graph: FunctionalityGraph,
        spec: Any = None,
        baseline: RPGGraph | None = None,
    ) -> RPGGraph:
        """Convert a FunctionalityGraph to an RPGGraph.

        When a ``spec`` with components is provided, an intermediate
        COMPONENT level is inserted between MODULE and FEATURE nodes,
        producing a three-level hierarchy: MODULE → COMPONENT → FEATURE.
        Without components the converter falls back to MODULE → FEATURE.

        When the spec contains ``data_flows`` with feature-level source/
        target names, the converter creates DATA_FLOW edges between the
        corresponding FEATURE nodes in addition to the module-level edges.

        When a ``baseline`` RPGGraph is provided, nodes are tagged with
        ``delta_status`` metadata (``DeltaStatus.NEW``, ``EXISTING``,
        or ``MODIFIED``). Existing nodes preserve their baseline data
        (signatures, file_paths, docstrings). Without a baseline, no
        delta_status metadata is set and behaviour is identical to before.

        Args:
            func_graph: The FunctionalityGraph to convert.
            spec: Optional RepositorySpec with ``components`` for
                three-level hierarchy.
            baseline: Optional baseline RPGGraph for delta-aware
                graph construction.

        Returns:
            A new :class:`RPGGraph` populated with nodes and edges.
        """
        rpg = RPGGraph(metadata={"source": "functionality_graph_converter"})

        if baseline is not None:
            rpg.metadata["has_baseline"] = True

        # Track module-name → module-node-UUID for dependency edge mapping
        module_name_to_id: dict[str, UUID] = {}
        # Track feature-id → feature-node-UUID for feature-level edges
        feature_id_to_uuid: dict[str, UUID] = {}

        # Collect spec components for COMPONENT-level node creation
        spec_components: list[Any] = []
        if spec is not None:
            spec_components = getattr(spec, "components", None) or []

        # ----------------------------------------------------------
        # Phase 1: Create MODULE nodes and their child nodes
        # ----------------------------------------------------------
        for module in func_graph.modules:
            module_node = self._create_module_node(module)
            rpg.add_node(module_node)
            module_name_to_id[module.name] = module_node.id

            # Delta tagging for MODULE nodes
            if baseline is not None:
                bl_node = self._find_matching_baseline_node(
                    module.name, baseline, level=NodeLevel.MODULE
                )
                self._tag_delta_status(module_node, bl_node)

            logger.debug(
                "Created MODULE node '%s' (id=%s) with %d features",
                module.name,
                module_node.id,
                module.feature_count,
            )

            if spec_components:
                # --- Three-level hierarchy: MODULE → COMPONENT → FEATURE ---
                # Match components to this module by scanning component
                # suggested_module or by checking if the component name
                # appears in the module's epic description / feature IDs.
                matched_components = self._match_components_to_module(
                    module, spec_components
                )

                if matched_components:
                    # Track which features are claimed by components
                    claimed_features: set[str] = set()

                    for comp in matched_components:
                        comp_name = getattr(comp, "name", str(comp))
                        comp_desc = getattr(comp, "description", "") or ""
                        comp_type = getattr(comp, "component_type", None)
                        comp_techs = getattr(comp, "technologies", []) or []

                        component_node = self._create_component_node(
                            name=comp_name,
                            description=comp_desc,
                            parent_id=module_node.id,
                            module_name=module.name,
                            component_type=comp_type,
                            technologies=comp_techs,
                        )
                        rpg.add_node(component_node)

                        # Delta tagging for COMPONENT nodes - prefer LLM classification
                        if baseline is not None:
                            self._tag_delta_status_from_llm(
                                component_node, comp, baseline
                            )

                        # HIERARCHY edge: MODULE → COMPONENT
                        hierarchy_edge = RPGEdge(
                            source_id=module_node.id,
                            target_id=component_node.id,
                            edge_type=EdgeType.HIERARCHY,
                        )
                        rpg.add_edge(hierarchy_edge)

                        # Assign features to this component – use name
                        # similarity or distribute evenly
                        comp_features = self._assign_features_to_component(
                            comp_name, module.feature_ids, claimed_features
                        )
                        claimed_features.update(comp_features)

                        for feature_id in comp_features:
                            feature_node = self._create_feature_node(
                                feature_id=feature_id,
                                parent_id=component_node.id,
                                module_name=module.name,
                            )
                            rpg.add_node(feature_node)
                            feature_id_to_uuid[feature_id] = feature_node.id

                            # Delta tagging for FEATURE nodes
                            if baseline is not None:
                                bl_feat = self._find_matching_baseline_node(
                                    feature_node.name, baseline,
                                    level=NodeLevel.FEATURE,
                                )
                                self._tag_delta_status(feature_node, bl_feat)

                            # HIERARCHY edge: COMPONENT → FEATURE
                            feat_edge = RPGEdge(
                                source_id=component_node.id,
                                target_id=feature_node.id,
                                edge_type=EdgeType.HIERARCHY,
                            )
                            rpg.add_edge(feat_edge)

                    # Handle unclaimed features – attach directly to module
                    unclaimed = [
                        fid for fid in module.feature_ids
                        if fid not in claimed_features
                    ]
                    for feature_id in unclaimed:
                        feature_node = self._create_feature_node(
                            feature_id=feature_id,
                            parent_id=module_node.id,
                            module_name=module.name,
                        )
                        rpg.add_node(feature_node)
                        feature_id_to_uuid[feature_id] = feature_node.id

                        # Delta tagging for unclaimed FEATURE nodes
                        if baseline is not None:
                            bl_feat = self._find_matching_baseline_node(
                                feature_node.name, baseline,
                                level=NodeLevel.FEATURE,
                            )
                            self._tag_delta_status(feature_node, bl_feat)

                        hierarchy_edge = RPGEdge(
                            source_id=module_node.id,
                            target_id=feature_node.id,
                            edge_type=EdgeType.HIERARCHY,
                        )
                        rpg.add_edge(hierarchy_edge)
                else:
                    # No components matched this module – flat hierarchy
                    self._add_flat_features(
                        rpg, module, module_node, feature_id_to_uuid,
                        baseline=baseline,
                    )
            else:
                # --- Two-level hierarchy: MODULE → FEATURE ---
                self._add_flat_features(
                    rpg, module, module_node, feature_id_to_uuid,
                    baseline=baseline,
                )

        # ----------------------------------------------------------
        # Phase 2: Convert module dependencies to DATA_FLOW edges
        # ----------------------------------------------------------
        for dep in func_graph.dependencies:
            source_id = module_name_to_id.get(dep.source)
            target_id = module_name_to_id.get(dep.target)

            if source_id is None or target_id is None:
                logger.warning(
                    "Skipping dependency %s → %s: module node not found",
                    dep.source,
                    dep.target,
                )
                continue

            data_flow_edge = self._create_data_flow_edge(
                source_id=source_id,
                target_id=target_id,
                dep=dep,
            )
            rpg.add_edge(data_flow_edge)

        # ----------------------------------------------------------
        # Phase 3: Create feature-level DATA_FLOW edges from spec
        # ----------------------------------------------------------
        if spec is not None:
            spec_data_flows = getattr(spec, "data_flows", None) or []
            for flow in spec_data_flows:
                source_name = str(getattr(flow, "source", "") or "")
                target_name = str(getattr(flow, "target", "") or "")

                src_uuid = feature_id_to_uuid.get(source_name)
                tgt_uuid = feature_id_to_uuid.get(target_name)

                if src_uuid and tgt_uuid and src_uuid != tgt_uuid:
                    flow_desc = str(getattr(flow, "description", "") or "")
                    flow_protocol = getattr(flow, "protocol", None)
                    feature_flow_edge = RPGEdge(
                        source_id=src_uuid,
                        target_id=tgt_uuid,
                        edge_type=EdgeType.DATA_FLOW,
                        data_type=str(flow_protocol) if flow_protocol else "data_flow",
                        transformation=flow_desc or None,
                    )
                    rpg.add_edge(feature_flow_edge)

        logger.info(
            "Converted FunctionalityGraph → RPGGraph: "
            "%d nodes, %d edges",
            rpg.node_count,
            rpg.edge_count,
        )

        return rpg

    # ------------------------------------------------------------------
    # Component matching helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_components_to_module(
        module: ModuleSpec, components: list[Any]
    ) -> list[Any]:
        """Find components that belong to a given module.

        Matches by ``suggested_module`` attribute, or by checking whether
        the component name (lowered) appears in the module name, description,
        or feature IDs.

        Args:
            module: The module to match against.
            components: All spec components.

        Returns:
            Components that belong to this module.
        """
        matched: list[Any] = []
        module_lower = module.name.lower()
        module_desc_lower = (module.description or "").lower()
        feature_ids_lower = " ".join(module.feature_ids).lower()

        for comp in components:
            # Check suggested_module first
            suggested = getattr(comp, "suggested_module", None)
            if suggested and str(suggested).lower() == module_lower:
                matched.append(comp)
                continue

            # Fuzzy match: component name in module context
            comp_name = (getattr(comp, "name", "") or "").lower()
            if comp_name and (
                comp_name in module_lower
                or comp_name in module_desc_lower
                or comp_name in feature_ids_lower
                or module_lower in comp_name
            ):
                matched.append(comp)

        return matched

    @staticmethod
    def _assign_features_to_component(
        comp_name: str,
        feature_ids: list[str],
        already_claimed: set[str],
    ) -> list[str]:
        """Assign feature IDs to a component based on name similarity.

        Features whose ID contains part of the component name (or vice
        versa) are assigned.  If no matches are found, falls back to
        assigning the first unclaimed feature.

        Args:
            comp_name: Component name.
            feature_ids: All feature IDs in the module.
            already_claimed: Features already claimed by other components.

        Returns:
            List of feature IDs assigned to this component.
        """
        available = [fid for fid in feature_ids if fid not in already_claimed]
        if not available:
            return []

        comp_lower = comp_name.lower().replace(" ", "_").replace("-", "_")
        matched = []

        for fid in available:
            fid_lower = fid.lower()
            if comp_lower in fid_lower or fid_lower in comp_lower:
                matched.append(fid)

        # If no match found, assign one unclaimed feature
        if not matched and available:
            matched.append(available[0])

        return matched

    @staticmethod
    def _add_flat_features(
        rpg: RPGGraph,
        module: ModuleSpec,
        module_node: RPGNode,
        feature_id_to_uuid: dict[str, UUID],
        baseline: RPGGraph | None = None,
    ) -> None:
        """Add FEATURE nodes as direct children of a MODULE node.

        Args:
            rpg: The RPGGraph being built.
            module: The module specification.
            module_node: The module RPGNode.
            feature_id_to_uuid: Mapping to populate.
            baseline: Optional baseline RPGGraph for delta tagging.
        """
        for feature_id in module.feature_ids:
            feature_node = FunctionalityGraphConverter._create_feature_node(
                feature_id=feature_id,
                parent_id=module_node.id,
                module_name=module.name,
            )
            rpg.add_node(feature_node)
            feature_id_to_uuid[feature_id] = feature_node.id

            # Delta tagging for flat FEATURE nodes
            if baseline is not None:
                bl_feat = FunctionalityGraphConverter._find_matching_baseline_node(
                    feature_node.name, baseline, level=NodeLevel.FEATURE,
                )
                FunctionalityGraphConverter._tag_delta_status(feature_node, bl_feat)

            hierarchy_edge = RPGEdge(
                source_id=module_node.id,
                target_id=feature_node.id,
                edge_type=EdgeType.HIERARCHY,
            )
            rpg.add_edge(hierarchy_edge)

    # ------------------------------------------------------------------
    # Node factories
    # ------------------------------------------------------------------

    @staticmethod
    def _create_module_node(module: ModuleSpec) -> RPGNode:
        """Create an RPGNode at MODULE level from a ModuleSpec.

        Args:
            module: The module specification.

        Returns:
            A new RPGNode representing the module.
        """
        return RPGNode(
            name=module.name,
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            docstring=module.description,
            metadata={
                "feature_count": module.feature_count,
                "feature_ids": list(module.feature_ids),
                "public_interface": list(module.public_interface),
                "rationale": module.rationale,
                "source": "functionality_graph",
            },
        )

    @staticmethod
    def _create_feature_node(
        feature_id: str,
        parent_id: UUID,
        module_name: str,
    ) -> RPGNode:
        """Create an RPGNode at FEATURE level for a feature ID.

        Args:
            feature_id: The feature identifier string.
            parent_id: UUID of the parent node (module or component).
            module_name: Name of the parent module (for metadata).

        Returns:
            A new RPGNode representing the feature.
        """
        # Derive a human-readable name from the feature ID
        name = feature_id.replace("_", " ").replace("-", " ").strip()
        if not name:
            name = f"feature-{feature_id}"

        return RPGNode(
            name=name,
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            parent_id=parent_id,
            metadata={
                "feature_id": feature_id,
                "module_name": module_name,
                "source": "functionality_graph",
            },
        )

    @staticmethod
    def _create_component_node(
        name: str,
        description: str,
        parent_id: UUID,
        module_name: str,
        component_type: str | None = None,
        technologies: list[str] | None = None,
    ) -> RPGNode:
        """Create an RPGNode at COMPONENT level.

        Args:
            name: Component name.
            description: Component description.
            parent_id: UUID of the parent module node.
            module_name: Name of the parent module (for metadata).
            component_type: Optional type classification.
            technologies: Optional list of technologies.

        Returns:
            A new RPGNode representing the component.
        """
        return RPGNode(
            name=name,
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FUNCTIONALITY,
            parent_id=parent_id,
            docstring=description,
            metadata={
                "module_name": module_name,
                "component_type": component_type,
                "technologies": technologies or [],
                "source": "functionality_graph",
            },
        )

    # ------------------------------------------------------------------
    # Edge factories
    # ------------------------------------------------------------------

    @staticmethod
    def _create_data_flow_edge(
        source_id: UUID,
        target_id: UUID,
        dep: DependencyEdge,
    ) -> RPGEdge:
        """Create a DATA_FLOW RPGEdge from a DependencyEdge.

        Args:
            source_id: UUID of the source module node.
            target_id: UUID of the target module node.
            dep: The original dependency edge with metadata.

        Returns:
            A new RPGEdge of type DATA_FLOW.
        """
        return RPGEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=EdgeType.DATA_FLOW,
            data_type=dep.dependency_type,
            transformation=dep.rationale or None,
        )

    # ------------------------------------------------------------------
    # Baseline / delta helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_matching_baseline_node(
        name: str,
        baseline: RPGGraph,
        level: NodeLevel | None = None,
    ) -> RPGNode | None:
        """Find a node in the baseline that matches by name.

        Uses exact match first, then normalized (case-insensitive,
        underscore-normalized) match. When ``level`` is provided,
        only nodes at that level are considered.

        Args:
            name: The name to search for.
            baseline: The baseline RPGGraph to search.
            level: Optional level filter.

        Returns:
            The matching RPGNode, or None if no match found.
        """
        # Exact name match
        for node in baseline.nodes.values():
            if level is not None and node.level != level:
                continue
            if node.name == name:
                return node

        # Normalized name match
        normalized = name.lower().replace(" ", "_").replace("-", "_")
        for node in baseline.nodes.values():
            if level is not None and node.level != level:
                continue
            node_normalized = node.name.lower().replace(" ", "_").replace("-", "_")
            if node_normalized == normalized:
                return node

        return None

    @staticmethod
    def _tag_delta_status(
        node: RPGNode,
        baseline_node: RPGNode | None,
    ) -> None:
        """Tag a node with delta_status metadata.

        If a matching baseline node is found, the node is tagged as
        EXISTING and enriched with baseline data. Otherwise it is tagged
        as NEW.

        Args:
            node: The newly created node to tag.
            baseline_node: The matching baseline node, or None.
        """
        if baseline_node is None:
            node.metadata["delta_status"] = DeltaStatus.NEW.value
            return

        # Existing node – preserve baseline data
        node.metadata["delta_status"] = DeltaStatus.EXISTING.value
        node.metadata["baseline_node_id"] = str(baseline_node.id)

        # Copy enrichment data from baseline
        if baseline_node.folder_path and not node.folder_path:
            node.folder_path = baseline_node.folder_path
        if baseline_node.file_path and not node.file_path:
            node.file_path = baseline_node.file_path
        if baseline_node.signature and not node.signature:
            node.signature = baseline_node.signature
        if baseline_node.docstring and not node.docstring:
            node.docstring = baseline_node.docstring
        if baseline_node.interface_type and not node.interface_type:
            node.interface_type = baseline_node.interface_type
        if baseline_node.node_type != NodeType.FUNCTIONALITY:
            # Preserve enriched node_type from baseline
            node.node_type = baseline_node.node_type

    @staticmethod
    def _tag_delta_status_from_llm(
        node: RPGNode,
        component: Any,
        baseline: RPGGraph | None,
    ) -> None:
        """Tag node with delta_status using LLM classification when available.

        Prefers LLM-provided delta classification over name-based matching.
        Falls back to the existing ``_find_matching_baseline_node()`` +
        ``_tag_delta_status()`` behaviour when the component carries no
        LLM classification fields.

        Priority:
            1. If component has ``delta_status`` set (from LLM), use it directly
            2. Look up baseline node by ``baseline_match_name`` for enrichment
            3. Fall back to existing ``_find_matching_baseline_node()`` behaviour

        Args:
            node: The newly created RPGNode to tag.
            component: A spec Component (or any object with optional
                ``delta_status``, ``baseline_match_name``, ``change_summary``
                attributes).
            baseline: Optional baseline RPGGraph for enrichment lookups.
        """
        delta_status = getattr(component, "delta_status", None)
        baseline_match = getattr(component, "baseline_match_name", None)
        change_summary = getattr(component, "change_summary", None)

        if delta_status is not None:
            # LLM provided classification – use it
            node.metadata["delta_status"] = (
                delta_status.value
                if hasattr(delta_status, "value")
                else str(delta_status)
            )
            node.metadata["delta_source"] = "llm"

            if baseline_match and baseline is not None:
                node.metadata["baseline_match_name"] = baseline_match
                # Try to find the baseline node for data enrichment
                bl_node = (
                    FunctionalityGraphConverter._find_matching_baseline_node(
                        baseline_match, baseline, level=node.level
                    )
                )
                if bl_node:
                    node.metadata["baseline_node_id"] = str(bl_node.id)
                    # Copy enrichment data from baseline
                    if bl_node.folder_path and not node.folder_path:
                        node.folder_path = bl_node.folder_path
                    if bl_node.file_path and not node.file_path:
                        node.file_path = bl_node.file_path
                    if bl_node.signature and not node.signature:
                        node.signature = bl_node.signature
                    if bl_node.docstring and not node.docstring:
                        node.docstring = bl_node.docstring
                    if bl_node.interface_type and not node.interface_type:
                        node.interface_type = bl_node.interface_type
                    if bl_node.node_type != NodeType.FUNCTIONALITY:
                        node.node_type = bl_node.node_type

            if change_summary:
                node.metadata["change_summary"] = change_summary
            return

        # Fall back to existing name-matching behavior
        if baseline is not None:
            bl_node = (
                FunctionalityGraphConverter._find_matching_baseline_node(
                    node.name, baseline, level=node.level
                )
            )
            FunctionalityGraphConverter._tag_delta_status(node, bl_node)
