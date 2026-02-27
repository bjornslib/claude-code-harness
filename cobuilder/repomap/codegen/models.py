"""Pydantic models for the repository assembly pipeline.

Provides structured models for file structure plans, import statements,
requirements entries, coverage reports, and generated repository metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from cobuilder.repomap.codegen.state import GenerationStatus


class ImportGroup(str, Enum):
    """PEP 8 import grouping categories."""

    STDLIB = "stdlib"
    THIRD_PARTY = "third_party"
    LOCAL = "local"


class ImportStatement(BaseModel):
    """A single import statement for a Python module.

    Attributes:
        module_path: The dotted module path (e.g. 'os.path').
        imported_names: Specific names imported (e.g. ['join', 'exists']).
            Empty list means import the whole module.
        alias: Optional alias (as X).
        group: PEP 8 import group classification.
        is_from_import: Whether this is a 'from X import Y' style.
    """

    module_path: str = Field(..., min_length=1, description="Dotted module path")
    imported_names: list[str] = Field(
        default_factory=list,
        description="Names imported from the module",
    )
    alias: Optional[str] = Field(
        default=None,
        description="Optional import alias",
    )
    group: ImportGroup = Field(
        default=ImportGroup.LOCAL,
        description="PEP 8 import group",
    )
    is_from_import: bool = Field(
        default=True,
        description="Whether this is a 'from X import Y' style import",
    )

    def render(self) -> str:
        """Render this import statement as a Python import line."""
        if self.is_from_import and self.imported_names:
            names = ", ".join(sorted(self.imported_names))
            line = f"from {self.module_path} import {names}"
        else:
            line = f"import {self.module_path}"
        if self.alias:
            line += f" as {self.alias}"
        return line


class FileEntry(BaseModel):
    """A planned file in the generated repository.

    Attributes:
        path: Relative file path from the repository root.
        content: The file content to write.
        is_package_init: Whether this is a __init__.py file.
        source_node_ids: RPG node UUIDs that contribute to this file.
    """

    path: str = Field(..., min_length=1, description="Relative file path")
    content: str = Field(default="", description="File content")
    is_package_init: bool = Field(
        default=False,
        description="Whether this is a __init__.py file",
    )
    source_node_ids: list[UUID] = Field(
        default_factory=list,
        description="RPG node UUIDs contributing to this file",
    )

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, v: str) -> str:
        """Ensure path is relative (no leading slash)."""
        if v.startswith("/"):
            raise ValueError("File path must be relative (no leading '/')")
        return v.replace("\\", "/")


class DirectoryEntry(BaseModel):
    """A planned directory in the generated repository.

    Attributes:
        path: Relative directory path from the repository root.
        needs_init: Whether an __init__.py should be generated.
    """

    path: str = Field(..., min_length=1, description="Relative directory path")
    needs_init: bool = Field(
        default=True,
        description="Whether to generate __init__.py",
    )

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, v: str) -> str:
        """Ensure path is relative (no leading slash)."""
        if v.startswith("/"):
            raise ValueError("Directory path must be relative (no leading '/')")
        return v.replace("\\", "/").rstrip("/")


class RequirementEntry(BaseModel):
    """A single entry in requirements.txt.

    Attributes:
        package_name: The PyPI package name.
        version_spec: Version specifier (e.g. '>=1.24.0,<2.0.0').
        is_dev: Whether this is a dev-only dependency.
        detected_from: How this requirement was detected.
    """

    package_name: str = Field(..., min_length=1, description="PyPI package name")
    version_spec: str = Field(default="", description="Version specifier")
    is_dev: bool = Field(default=False, description="Dev-only dependency")
    detected_from: str = Field(
        default="import_scan",
        description="Detection method: 'import_scan', 'rpg_spec', or 'manual'",
    )

    def render(self) -> str:
        """Render as a requirements.txt line."""
        if self.version_spec:
            return f"{self.package_name}{self.version_spec}"
        return self.package_name


class NodeCoverageEntry(BaseModel):
    """Coverage information for a single RPG node.

    Attributes:
        node_id: The UUID of the RPG node.
        node_name: Human-readable node name.
        status: Generation status.
        retry_count: Number of debug retries.
        failure_reason: Reason for failure (if any).
        subgraph_id: The subgraph this node belongs to.
    """

    node_id: UUID = Field(..., description="RPG node UUID")
    node_name: str = Field(default="", description="Human-readable name")
    status: GenerationStatus = Field(
        default=GenerationStatus.PENDING,
        description="Node generation status",
    )
    retry_count: int = Field(default=0, ge=0, description="Number of debug retries")
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for failure",
    )
    subgraph_id: Optional[str] = Field(
        default=None,
        description="Subgraph this node belongs to",
    )


class SubgraphCoverage(BaseModel):
    """Coverage breakdown for a single subgraph.

    Attributes:
        subgraph_id: Identifier for the subgraph.
        total: Total number of nodes.
        passed: Number of passed nodes.
        failed: Number of failed nodes.
        skipped: Number of skipped nodes.
    """

    subgraph_id: str = Field(..., description="Subgraph identifier")
    total: int = Field(default=0, ge=0, description="Total nodes")
    passed: int = Field(default=0, ge=0, description="Passed nodes")
    failed: int = Field(default=0, ge=0, description="Failed nodes")
    skipped: int = Field(default=0, ge=0, description="Skipped nodes")

    @property
    def pass_rate(self) -> float:
        """Compute the pass rate as a percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100.0


class CoverageReport(BaseModel):
    """Full coverage report for the code generation run.

    Attributes:
        timestamp: When the report was generated.
        total_nodes: Total RPG nodes planned.
        passed_nodes: Nodes that passed.
        failed_nodes: Nodes that failed.
        skipped_nodes: Nodes that were skipped.
        node_details: Per-node coverage entries.
        subgraph_breakdown: Coverage per subgraph.
        generation_time_seconds: Wall time for generation.
        metadata: Additional metadata (model used, phase versions, etc).
    """

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Report generation timestamp",
    )
    total_nodes: int = Field(default=0, ge=0, description="Total planned nodes")
    passed_nodes: int = Field(default=0, ge=0, description="Passed nodes")
    failed_nodes: int = Field(default=0, ge=0, description="Failed nodes")
    skipped_nodes: int = Field(default=0, ge=0, description="Skipped nodes")
    node_details: list[NodeCoverageEntry] = Field(
        default_factory=list,
        description="Per-node coverage details",
    )
    subgraph_breakdown: list[SubgraphCoverage] = Field(
        default_factory=list,
        description="Per-subgraph breakdown",
    )
    generation_time_seconds: Optional[float] = Field(
        default=None,
        description="Wall time for generation in seconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    @property
    def pass_rate(self) -> float:
        """Compute the overall pass rate as a percentage."""
        if self.total_nodes == 0:
            return 0.0
        return (self.passed_nodes / self.total_nodes) * 100.0


class RepositoryManifest(BaseModel):
    """Complete manifest of a generated repository.

    Tracks all files, directories, and metadata about the generated
    repository for inspection and validation.

    Attributes:
        project_name: Name of the generated project.
        project_description: One-line project description.
        files: All planned files.
        directories: All planned directories.
        requirements: Detected requirements.
        coverage: Generation coverage report.
        rpg_metadata: Metadata from the source RPG.
    """

    project_name: str = Field(default="generated_repo", description="Project name")
    project_description: str = Field(
        default="",
        description="One-line project description",
    )
    files: list[FileEntry] = Field(
        default_factory=list,
        description="All files in the repository",
    )
    directories: list[DirectoryEntry] = Field(
        default_factory=list,
        description="All directories in the repository",
    )
    requirements: list[RequirementEntry] = Field(
        default_factory=list,
        description="Detected requirements",
    )
    coverage: Optional[CoverageReport] = Field(
        default=None,
        description="Generation coverage report",
    )
    rpg_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata from the source RPG",
    )
