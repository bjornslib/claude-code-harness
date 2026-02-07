"""Ontology data models for the Feature Ontology Service.

Defines Pydantic models for representing feature nodes in a hierarchical
feature ontology, search result paths with scores, and aggregate statistics.

These models support Task 2.1.1 of PRD-RPG-P2-001 (Epic 2.1: Feature
Ontology Service).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class FeatureNode(BaseModel):
    """A node in the feature ontology tree.

    Represents a single feature at any hierarchical level within the
    ontology.  Each node has a unique ``id``, a human-readable ``name``,
    an optional ``description``, and a ``level`` indicating its depth in
    the hierarchy (0 = root domain, higher = more specific).

    Nodes may carry ``tags`` for keyword-based filtering and an optional
    ``embedding`` vector for semantic search.

    Validators enforce:
    - ``level`` must be non-negative
    - ``tags`` entries must be non-empty strings
    - ``embedding`` must have consistent dimensionality (when provided)
    - ``parent_id`` must differ from ``id``
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Unique feature identifier (e.g., 'ml.deep-learning.transformers')",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Human-readable feature name",
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the feature",
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="ID of the parent feature node (None for root nodes)",
    )
    level: int = Field(
        ...,
        ge=0,
        description="Hierarchical depth (0 = root domain, higher = more specific)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Keyword tags for filtering and search augmentation",
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Vector embedding for semantic search (e.g., 1536-dim from text-embedding-3-small)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata for this feature node",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate that all tags are non-empty strings."""
        for i, tag in enumerate(v):
            stripped = tag.strip()
            if not stripped:
                raise ValueError(
                    f"Tag at index {i} is empty or whitespace-only"
                )
            v[i] = stripped
        return v

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        """Validate that embedding is non-empty when provided."""
        if v is not None and len(v) == 0:
            raise ValueError("Embedding must be non-empty when provided")
        return v

    @model_validator(mode="after")
    def validate_node_constraints(self) -> FeatureNode:
        """Validate cross-field constraints.

        - parent_id must differ from id (no self-referencing)
        """
        if self.parent_id is not None and self.parent_id == self.id:
            raise ValueError(
                f"parent_id '{self.parent_id}' must differ from id '{self.id}' "
                f"(no self-referencing)"
            )
        return self

    @property
    def is_root(self) -> bool:
        """Whether this node is a root node (no parent)."""
        return self.parent_id is None

    @property
    def full_path(self) -> str:
        """Return the node's ID as its hierarchical path representation."""
        return self.id

    def embedding_input(self) -> str:
        """Build the text input for embedding generation.

        Follows the PRD specification:
        ``{id} | {description} | {tags}``

        Returns:
            Formatted string for embedding generation.
        """
        parts = [self.id]
        if self.description:
            parts.append(self.description)
        if self.tags:
            parts.append(", ".join(self.tags))
        return " | ".join(parts)

    def __eq__(self, other: object) -> bool:
        """Check equality based on all fields."""
        if not isinstance(other, FeatureNode):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    def __hash__(self) -> int:
        """Hash based on the immutable id field."""
        return hash(self.id)

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"FeatureNode(id='{self.id}', name='{self.name}', "
            f"level={self.level}, tags={self.tags})"
        )


class FeaturePath(BaseModel):
    """A ranked search result representing a path through the ontology.

    Contains an ordered list of :class:`FeatureNode` instances from root
    to leaf, along with a relevance ``score`` from the search engine.

    Validators enforce:
    - ``nodes`` list must be non-empty
    - ``score`` must be between 0.0 and 1.0 (inclusive)
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    nodes: list[FeatureNode] = Field(
        ...,
        min_length=1,
        description="Ordered list of feature nodes from root to leaf",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0 = no match, 1.0 = perfect match)",
    )

    @property
    def leaf(self) -> FeatureNode:
        """Return the leaf (most specific) node in the path."""
        return self.nodes[-1]

    @property
    def root(self) -> FeatureNode:
        """Return the root (most general) node in the path."""
        return self.nodes[0]

    @property
    def depth(self) -> int:
        """Return the depth of this path (number of nodes)."""
        return len(self.nodes)

    @property
    def path_string(self) -> str:
        """Return a human-readable path string.

        Example: ``"Software > Web Development > Frontend > React Hooks"``
        """
        return " > ".join(node.name for node in self.nodes)

    def __eq__(self, other: object) -> bool:
        """Check equality based on all fields."""
        if not isinstance(other, FeaturePath):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"FeaturePath(path='{self.path_string}', "
            f"score={self.score:.3f}, depth={self.depth})"
        )


class OntologyStats(BaseModel):
    """Aggregate statistics for a feature ontology backend.

    Provides summary metrics about the ontology's size, shape, and
    coverage.  Used for health checks and monitoring.

    Validators enforce:
    - All count fields must be non-negative
    - ``max_depth`` must be >= ``total_levels`` when both > 0
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    total_nodes: int = Field(
        ...,
        ge=0,
        description="Total number of feature nodes in the ontology",
    )
    total_levels: int = Field(
        ...,
        ge=0,
        description="Number of distinct hierarchical levels",
    )
    avg_children: float = Field(
        ...,
        ge=0.0,
        description="Average number of children per non-leaf node",
    )
    max_depth: int = Field(
        ...,
        ge=0,
        description="Maximum depth from root to any leaf node",
    )
    root_count: int = Field(
        default=0,
        ge=0,
        description="Number of root nodes (nodes with no parent)",
    )
    leaf_count: int = Field(
        default=0,
        ge=0,
        description="Number of leaf nodes (nodes with no children)",
    )
    nodes_with_embeddings: int = Field(
        default=0,
        ge=0,
        description="Number of nodes that have vector embeddings",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional backend-specific statistics",
    )

    @model_validator(mode="after")
    def validate_stats_constraints(self) -> OntologyStats:
        """Validate cross-field constraints.

        - leaf_count should not exceed total_nodes
        - root_count should not exceed total_nodes
        - nodes_with_embeddings should not exceed total_nodes
        """
        if self.leaf_count > self.total_nodes:
            raise ValueError(
                f"leaf_count ({self.leaf_count}) cannot exceed "
                f"total_nodes ({self.total_nodes})"
            )
        if self.root_count > self.total_nodes:
            raise ValueError(
                f"root_count ({self.root_count}) cannot exceed "
                f"total_nodes ({self.total_nodes})"
            )
        if self.nodes_with_embeddings > self.total_nodes:
            raise ValueError(
                f"nodes_with_embeddings ({self.nodes_with_embeddings}) cannot "
                f"exceed total_nodes ({self.total_nodes})"
            )
        return self

    @property
    def embedding_coverage(self) -> float:
        """Return the fraction of nodes with embeddings (0.0 to 1.0)."""
        if self.total_nodes == 0:
            return 0.0
        return self.nodes_with_embeddings / self.total_nodes

    def __repr__(self) -> str:
        """Return a concise string representation."""
        return (
            f"OntologyStats(total_nodes={self.total_nodes}, "
            f"total_levels={self.total_levels}, "
            f"avg_children={self.avg_children:.1f}, "
            f"max_depth={self.max_depth})"
        )
