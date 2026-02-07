"""RPGEdge schema for the Repository Planning Graph."""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from zerorepo.models.enums import EdgeType


class RPGEdge(BaseModel):
    """An edge in the Repository Planning Graph.

    Represents a directed relationship between two RPGNode instances.
    Edge types include HIERARCHY, DATA_FLOW, ORDERING, INHERITANCE,
    and INVOCATION.

    Validators enforce:
    - source_id must differ from target_id (no self-loops)
    - data_id, data_type, transformation are only valid for DATA_FLOW edges
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(default_factory=uuid4, description="Unique edge identifier")
    source_id: UUID = Field(
        ...,
        description="UUID of the source node",
    )
    target_id: UUID = Field(
        ...,
        description="UUID of the target node (must differ from source_id)",
    )
    edge_type: EdgeType = Field(
        ...,
        description="Type classification of the edge",
    )
    data_id: Optional[str] = Field(
        default=None,
        description="Identifier for data flowing on this edge (DATA_FLOW only)",
    )
    data_type: Optional[str] = Field(
        default=None,
        description="Type annotation for data (DATA_FLOW only)",
    )
    transformation: Optional[str] = Field(
        default=None,
        description="Description of data transformation (DATA_FLOW only)",
    )
    validated: bool = Field(
        default=False,
        description="Whether this edge has been validated",
    )

    @model_validator(mode="after")
    def validate_edge_constraints(self) -> RPGEdge:
        """Validate edge constraints.

        - source_id must not equal target_id (no self-loops)
        - data_id, data_type, transformation only valid for DATA_FLOW edges
        """
        # No self-loops
        if self.source_id == self.target_id:
            raise ValueError(
                f"Self-loop detected: source_id and target_id are both "
                f"'{self.source_id}'. Edges must connect different nodes."
            )

        # Data fields only valid for DATA_FLOW edges
        data_fields_set = any([
            self.data_id is not None,
            self.data_type is not None,
            self.transformation is not None,
        ])

        if data_fields_set and self.edge_type != EdgeType.DATA_FLOW:
            raise ValueError(
                f"data_id, data_type, and transformation are only valid for "
                f"DATA_FLOW edges, but edge_type is '{self.edge_type.value}'"
            )

        return self

    def __eq__(self, other: object) -> bool:
        """Check equality based on all fields."""
        if not isinstance(other, RPGEdge):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    def __hash__(self) -> int:
        """Hash based on the immutable id field."""
        return hash(self.id)
