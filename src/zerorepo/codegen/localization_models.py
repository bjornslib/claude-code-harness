"""Data models for the localization and Serena editing modules.

Provides Pydantic models for localization results, dependency maps,
and custom exceptions used across the code generation pipeline.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LocalizationResult(BaseModel):
    """A single result from a localization search.

    Attributes:
        node_id: The UUID of the matched RPG node, if identified.
        symbol_name: The name of the symbol found.
        filepath: The file path where the symbol is located.
        line: The line number of the symbol (1-indexed).
        score: Confidence score between 0.0 and 1.0.
        source: The tool that produced this result ('serena', 'rpg_fuzzy', 'ast').
        context: Surrounding code or description for context.
    """

    node_id: Optional[UUID] = Field(
        default=None,
        description="UUID of the matched RPG node",
    )
    symbol_name: str = Field(
        ...,
        description="Name of the located symbol",
    )
    filepath: str = Field(
        ...,
        description="File path where the symbol is located",
    )
    line: Optional[int] = Field(
        default=None,
        ge=1,
        description="Line number (1-indexed)",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    source: str = Field(
        ...,
        description="Tool that produced this result: 'serena', 'rpg_fuzzy', or 'ast'",
    )
    context: str = Field(
        default="",
        description="Surrounding code or description for context",
    )


class DependencyMap(BaseModel):
    """N-hop dependency neighborhood around a center node.

    Attributes:
        center_node_id: The UUID of the center node.
        incoming: List of (node_id, edge_type) tuples for incoming edges.
        outgoing: List of (node_id, edge_type) tuples for outgoing edges.
        hops: Number of hops explored from the center.
    """

    center_node_id: UUID = Field(
        ...,
        description="UUID of the center node",
    )
    incoming: list[tuple[UUID, str]] = Field(
        default_factory=list,
        description="Incoming edges as (node_id, edge_type) tuples",
    )
    outgoing: list[tuple[UUID, str]] = Field(
        default_factory=list,
        description="Outgoing edges as (node_id, edge_type) tuples",
    )
    hops: int = Field(
        ...,
        ge=0,
        description="Number of hops explored from the center",
    )


class LocalizationExhaustedError(Exception):
    """Raised when the localization tracker exceeds its query limit.

    This signals that the debugging iteration has exhausted its
    budget for localization queries without resolving the issue.
    """

    def __init__(self, limit: int, message: str | None = None) -> None:
        self.limit = limit
        detail = message or f"Localization exhausted after {limit} attempts"
        super().__init__(detail)
