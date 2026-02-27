"""RPGNode schema for the Repository Planning Graph."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from cobuilder.repomap.models.enums import InterfaceType, NodeLevel, NodeType, TestStatus


class RPGNode(BaseModel):
    """A node in the Repository Planning Graph.

    Represents a unit of planning/implementation at one of three hierarchical
    levels (MODULE, COMPONENT, FEATURE) with one of four type classifications
    (FUNCTIONALITY, FOLDER_AUGMENTED, FILE_AUGMENTED, FUNCTION_AUGMENTED).

    Validators enforce consistency constraints:
    - file_path must be a child of folder_path when both are present
    - signature is required when interface_type is set
    - implementation cannot be set without file_path
    - interface_type is required when node_type is FUNCTION_AUGMENTED
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(default_factory=uuid4, description="Unique node identifier")
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable node name",
    )
    level: NodeLevel = Field(..., description="Hierarchical level of the node")
    node_type: NodeType = Field(..., description="Type classification of the node")
    parent_id: Optional[UUID] = Field(
        default=None,
        description="UUID of the parent node in the hierarchy",
    )
    folder_path: Optional[str] = Field(
        default=None,
        description="Relative folder path for this node",
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Relative file path for this node",
    )
    interface_type: Optional[InterfaceType] = Field(
        default=None,
        description="Interface type (required for FUNCTION_AUGMENTED nodes)",
    )
    signature: Optional[str] = Field(
        default=None,
        description="Python function/method signature",
    )
    docstring: Optional[str] = Field(
        default=None,
        description="Documentation string",
    )
    implementation: Optional[str] = Field(
        default=None,
        description="Python implementation code",
    )
    test_code: Optional[str] = Field(
        default=None,
        description="Pytest test code for this node",
    )
    test_status: TestStatus = Field(
        default=TestStatus.PENDING,
        description="Current test execution status",
    )
    serena_validated: bool = Field(
        default=False,
        description="Whether Serena has validated this node",
    )
    actual_dependencies: list[UUID] = Field(
        default_factory=list,
        description="UUIDs of actual runtime dependencies (populated by Serena)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata for this node",
    )

    @field_validator("folder_path", "file_path")
    @classmethod
    def validate_path_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate that paths are relative (no leading slash) and well-formed."""
        if v is None:
            return v
        if v.startswith("/"):
            raise ValueError("Path must be relative (no leading '/')")
        # Normalize path separators
        return v.replace("\\", "/")

    @model_validator(mode="after")
    def validate_field_constraints(self) -> RPGNode:
        """Validate cross-field constraints.

        - file_path must be a child of folder_path when both present
        - signature is required when interface_type is set
        - implementation cannot be set without file_path
        - interface_type is required when node_type is FUNCTION_AUGMENTED
        """
        # file_path must be child of folder_path when both present
        if self.file_path is not None and self.folder_path is not None:
            if not self.file_path.startswith(self.folder_path):
                raise ValueError(
                    f"file_path '{self.file_path}' must start with "
                    f"folder_path '{self.folder_path}'"
                )

        # signature required when interface_type is set
        if self.interface_type is not None and self.signature is None:
            raise ValueError(
                "signature is required when interface_type is set"
            )

        # implementation cannot be set without file_path
        if self.implementation is not None and self.file_path is None:
            raise ValueError(
                "implementation cannot be set without file_path"
            )

        # interface_type required when node_type is FUNCTION_AUGMENTED
        if (
            self.node_type == NodeType.FUNCTION_AUGMENTED
            and self.interface_type is None
        ):
            raise ValueError(
                "interface_type is required when node_type is FUNCTION_AUGMENTED"
            )

        return self

    def __eq__(self, other: object) -> bool:
        """Check equality based on all fields."""
        if not isinstance(other, RPGNode):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    def __hash__(self) -> int:
        """Hash based on the immutable id field."""
        return hash(self.id)
