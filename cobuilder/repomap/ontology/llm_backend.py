"""LLM-Generated Ontology Backend for the Feature Ontology Service.

Implements an :class:`OntologyBackend` that uses the LLM Gateway to
dynamically generate feature ontology hierarchies from natural language
queries.  This backend is useful when no pre-existing ontology exists
and features must be discovered on-the-fly via LLM reasoning.

This module implements Task 2.1.4 of PRD-RPG-P2-001 (Epic 2.1: Feature
Ontology Service).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cobuilder.repomap.llm.exceptions import LLMGatewayError
from cobuilder.repomap.llm.gateway import LLMGateway
from cobuilder.repomap.llm.models import GatewayConfig, ModelTier
from cobuilder.repomap.llm.prompt_templates import PromptTemplate
from cobuilder.repomap.ontology.backend import OntologyBackend
from cobuilder.repomap.ontology.models import FeatureNode, FeaturePath, OntologyStats

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM Response Models
# ---------------------------------------------------------------------------


class LLMFeatureNodeResponse(BaseModel):
    """A feature node as returned by the LLM.

    Mirrors the :class:`FeatureNode` fields but is designed for parsing
    LLM-generated JSON responses.  Validation is more lenient to handle
    the inherent variability of LLM output.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    id: str = Field(
        ...,
        min_length=1,
        description="Dot-separated hierarchical ID",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human-readable feature name",
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief description of the feature",
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="Parent node ID (null for root nodes)",
    )
    level: int = Field(
        default=0,
        ge=0,
        description="Hierarchical depth (0 = root)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Keyword tags for the feature",
    )

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        """Strip whitespace and remove empty tags from LLM output."""
        return [tag.strip() for tag in v if tag.strip()]

    def to_feature_node(self) -> FeatureNode:
        """Convert to a canonical :class:`FeatureNode`.

        Returns:
            A validated :class:`FeatureNode` instance.

        Raises:
            pydantic.ValidationError: If the conversion produces
                invalid data.
        """
        return FeatureNode(
            id=self.id,
            name=self.name,
            description=self.description,
            parent_id=self.parent_id,
            level=self.level,
            tags=self.tags,
            metadata={"source": "llm-generated"},
        )


class LLMOntologyResponse(BaseModel):
    """Top-level response model for LLM-generated ontology.

    The LLM is expected to return a JSON object with a ``nodes`` list
    conforming to this schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    nodes: list[LLMFeatureNodeResponse] = Field(
        ...,
        min_length=1,
        description="List of feature nodes in the ontology",
    )


# ---------------------------------------------------------------------------
# LLM Backend Configuration
# ---------------------------------------------------------------------------


class LLMBackendConfig(BaseModel):
    """Configuration for the LLM Ontology Backend."""

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use for ontology generation",
    )
    tier: ModelTier = Field(
        default=ModelTier.CHEAP,
        description="Model tier for cost tracking",
    )
    max_nodes: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of nodes per generation request",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Whether to cache generated ontology nodes",
    )
    domain_hint: Optional[str] = Field(
        default=None,
        description="Optional domain hint to guide ontology generation",
    )
    template_name: str = Field(
        default="ontology_generation",
        description="Name of the Jinja2 prompt template (without .jinja2)",
    )


# ---------------------------------------------------------------------------
# LLM Ontology Backend
# ---------------------------------------------------------------------------


class LLMOntologyBackend(OntologyBackend):
    """Ontology backend that generates features using an LLM.

    Uses the :class:`LLMGateway` to dynamically generate feature ontology
    hierarchies from natural language queries.  Generated nodes are cached
    in memory so subsequent lookups and child queries are efficient.

    Example::

        gateway = LLMGateway()
        backend = LLMOntologyBackend(gateway=gateway)
        results = backend.search("user authentication", top_k=5)

    The backend maintains an internal node cache.  Nodes generated via
    :meth:`search` are stored and available through :meth:`get_node`
    and :meth:`get_children` without additional LLM calls.
    """

    def __init__(
        self,
        gateway: LLMGateway,
        config: LLMBackendConfig | None = None,
        prompt_template: PromptTemplate | None = None,
    ) -> None:
        """Initialise the LLM-generated ontology backend.

        Args:
            gateway: An initialised :class:`LLMGateway` for making
                LLM completion requests.
            config: Optional backend configuration.  Defaults to
                sensible defaults.
            prompt_template: Optional :class:`PromptTemplate` instance.
                Defaults to the built-in template directory.
        """
        self._gateway = gateway
        self._config = config or LLMBackendConfig()
        self._prompt_template = prompt_template or PromptTemplate()
        self._nodes: dict[str, FeatureNode] = {}
        self._generation_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def gateway(self) -> LLMGateway:
        """Access the underlying LLM Gateway."""
        return self._gateway

    @property
    def config(self) -> LLMBackendConfig:
        """Access the backend configuration."""
        return self._config

    @property
    def node_cache(self) -> dict[str, FeatureNode]:
        """Access the internal node cache (read-only view)."""
        return dict(self._nodes)

    @property
    def generation_count(self) -> int:
        """Number of LLM generation requests made."""
        return self._generation_count

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def add_node(self, node: FeatureNode) -> None:
        """Add a node directly to the internal cache.

        Useful for pre-seeding the ontology with known nodes.

        Args:
            node: A :class:`FeatureNode` to add to the cache.
        """
        self._nodes[node.id] = node

    def add_nodes(self, nodes: list[FeatureNode]) -> None:
        """Add multiple nodes to the internal cache.

        Args:
            nodes: List of :class:`FeatureNode` instances.
        """
        for node in nodes:
            self._nodes[node.id] = node

    def clear_cache(self) -> None:
        """Clear all cached nodes."""
        self._nodes.clear()

    # ------------------------------------------------------------------
    # OntologyBackend interface implementation
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
        """Search for features by generating ontology nodes via LLM.

        Generates a feature ontology from the query using the LLM, caches
        the resulting nodes, and returns ranked :class:`FeaturePath` results.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            Ordered list of :class:`FeaturePath` results.

        Raises:
            ValueError: If ``query`` is empty or ``top_k`` is not positive.
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        # Build the prompt
        existing_nodes_context = []
        if self._config.cache_enabled and self._nodes:
            existing_nodes_context = [
                {"id": n.id, "name": n.name, "description": n.description}
                for n in list(self._nodes.values())[:50]  # Limit context size
            ]

        prompt = self._prompt_template.render(
            self._config.template_name,
            query=query.strip(),
            domain_hint=self._config.domain_hint,
            existing_nodes=existing_nodes_context if existing_nodes_context else None,
            max_nodes=min(self._config.max_nodes, top_k * 3),
        )

        # Call the LLM
        try:
            response = self._gateway.complete_json(
                messages=[{"role": "user", "content": prompt}],
                model=self._config.model,
                response_schema=LLMOntologyResponse,
                tier=self._config.tier,
            )
            self._generation_count += 1
        except LLMGatewayError:
            logger.exception("LLM generation failed for query: %s", query)
            raise

        # Convert response nodes to FeatureNodes and cache them
        generated_nodes = self._ingest_response(response)

        # Build FeaturePaths from generated nodes
        paths = self._build_paths(generated_nodes, top_k)

        return paths

    def get_node(self, feature_id: str) -> FeatureNode:
        """Retrieve a cached feature node by ID.

        Args:
            feature_id: The unique ID of the feature node.

        Returns:
            The :class:`FeatureNode` with the given ID.

        Raises:
            KeyError: If no node with the given ID exists in the cache.
            ValueError: If ``feature_id`` is empty.
        """
        if not feature_id or not feature_id.strip():
            raise ValueError("feature_id must not be empty")

        feature_id = feature_id.strip()
        if feature_id not in self._nodes:
            raise KeyError(f"Node '{feature_id}' not found")

        return self._nodes[feature_id]

    def get_children(self, feature_id: str) -> list[FeatureNode]:
        """List children of a cached feature node.

        Args:
            feature_id: The unique ID of the parent feature node.

        Returns:
            List of :class:`FeatureNode` children.

        Raises:
            KeyError: If no node with the given ID exists in the cache.
            ValueError: If ``feature_id`` is empty.
        """
        if not feature_id or not feature_id.strip():
            raise ValueError("feature_id must not be empty")

        feature_id = feature_id.strip()
        if feature_id not in self._nodes:
            raise KeyError(f"Node '{feature_id}' not found")

        return [
            node
            for node in self._nodes.values()
            if node.parent_id == feature_id
        ]

    def get_statistics(self) -> OntologyStats:
        """Compute statistics for the cached ontology.

        Returns:
            An :class:`OntologyStats` instance with summary metrics.
        """
        total = len(self._nodes)

        if total == 0:
            return OntologyStats(
                total_nodes=0,
                total_levels=0,
                avg_children=0.0,
                max_depth=0,
                root_count=0,
                leaf_count=0,
                nodes_with_embeddings=0,
                metadata={
                    "backend": "llm-generated",
                    "generation_count": self._generation_count,
                },
            )

        # Compute statistics
        levels = {node.level for node in self._nodes.values()}
        root_count = sum(
            1 for node in self._nodes.values() if node.is_root
        )
        parent_ids = {
            node.parent_id
            for node in self._nodes.values()
            if node.parent_id is not None
        }
        leaf_ids = set(self._nodes.keys()) - parent_ids
        leaf_count = len(leaf_ids)
        nodes_with_embeddings = sum(
            1 for node in self._nodes.values() if node.embedding is not None
        )

        # Average children per non-leaf node
        non_leaf_count = total - leaf_count
        if non_leaf_count > 0:
            total_children = sum(
                1
                for node in self._nodes.values()
                if node.parent_id is not None
            )
            avg_children = total_children / non_leaf_count
        else:
            avg_children = 0.0

        max_depth = max(node.level for node in self._nodes.values())

        return OntologyStats(
            total_nodes=total,
            total_levels=len(levels),
            avg_children=avg_children,
            max_depth=max_depth,
            root_count=root_count,
            leaf_count=leaf_count,
            nodes_with_embeddings=nodes_with_embeddings,
            metadata={
                "backend": "llm-generated",
                "generation_count": self._generation_count,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest_response(
        self,
        response: LLMOntologyResponse,
    ) -> list[FeatureNode]:
        """Convert LLM response nodes into FeatureNodes and cache them.

        Handles validation errors gracefully – nodes that fail validation
        are logged and skipped rather than raising.

        Args:
            response: The parsed LLM response.

        Returns:
            List of successfully converted :class:`FeatureNode` instances.
        """
        nodes: list[FeatureNode] = []

        for llm_node in response.nodes:
            try:
                feature_node = llm_node.to_feature_node()
                self._nodes[feature_node.id] = feature_node
                nodes.append(feature_node)
            except Exception:
                logger.warning(
                    "Skipping invalid LLM-generated node: id=%s, name=%s",
                    llm_node.id,
                    llm_node.name,
                    exc_info=True,
                )

        return nodes

    def _build_paths(
        self,
        nodes: list[FeatureNode],
        top_k: int,
    ) -> list[FeaturePath]:
        """Build :class:`FeaturePath` instances from generated nodes.

        For each leaf node, traces the path back to a root node through
        the cache.  Non-leaf nodes are also included if they have no
        traceable parent path (orphan nodes).

        Scores are assigned based on the node's position in the generated
        list (earlier = higher relevance, as LLMs tend to put most relevant
        items first).

        Args:
            nodes: Newly generated :class:`FeatureNode` instances.
            top_k: Maximum number of paths to return.

        Returns:
            Sorted list of :class:`FeaturePath` results.
        """
        if not nodes:
            return []

        paths: list[FeaturePath] = []

        for i, node in enumerate(nodes):
            # Trace the path from this node to root
            path_nodes = self._trace_path(node)

            # Score: decay from 1.0 based on position in result list
            score = max(0.01, 1.0 - (i * 0.8 / max(len(nodes) - 1, 1)))

            try:
                feature_path = FeaturePath(
                    nodes=path_nodes,
                    score=round(score, 4),
                )
                paths.append(feature_path)
            except Exception:
                logger.warning(
                    "Skipping invalid path for node: %s",
                    node.id,
                    exc_info=True,
                )

        # Sort by score descending and limit to top_k
        paths.sort(key=lambda p: p.score, reverse=True)
        return paths[:top_k]

    def _trace_path(self, node: FeatureNode) -> list[FeatureNode]:
        """Trace the full path from root to the given node.

        Walks up through ``parent_id`` references in the cache until
        a root node (or a missing parent) is reached, then returns
        the path in root-to-leaf order.

        Includes cycle detection to handle malformed ontologies.

        Args:
            node: The starting (leaf-most) node.

        Returns:
            Ordered list of nodes from root to the given node.
        """
        path: list[FeatureNode] = [node]
        visited: set[str] = {node.id}
        current = node

        while current.parent_id is not None:
            if current.parent_id in visited:
                # Cycle detected – stop tracing
                logger.warning(
                    "Cycle detected in ontology at node %s -> %s",
                    current.id,
                    current.parent_id,
                )
                break

            parent = self._nodes.get(current.parent_id)
            if parent is None:
                # Parent not in cache – stop tracing
                break

            visited.add(parent.id)
            path.append(parent)
            current = parent

        # Reverse to get root-to-leaf order
        path.reverse()
        return path
