"""Test artifact management for graph-guided code generation.

Provides structured storage, retrieval, and lifecycle management of test
artifacts generated during the code generation pipeline. Artifacts include
test code, test results, coverage data, and validation reports.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                              Models                                          #
# --------------------------------------------------------------------------- #


class ArtifactType(str, Enum):
    """Types of test artifacts."""

    TEST_CODE = "test_code"
    TEST_RESULT = "test_result"
    COVERAGE_DATA = "coverage_data"
    VALIDATION_REPORT = "validation_report"
    ERROR_LOG = "error_log"
    REGRESSION_REPORT = "regression_report"


class ArtifactStatus(str, Enum):
    """Lifecycle status of an artifact."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


@dataclass
class TestArtifact:
    """A single test artifact.

    Attributes:
        artifact_id: Unique identifier for this artifact.
        node_id: The UUID of the associated RPG node.
        artifact_type: The type of artifact.
        status: Current lifecycle status.
        content: The artifact content (code, JSON, text).
        metadata: Additional metadata.
        iteration: The generation iteration that produced this artifact.
        created_at: Creation timestamp.
        file_path: Optional file path where artifact is persisted.
    """

    artifact_id: str
    node_id: UUID
    artifact_type: ArtifactType
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    iteration: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    file_path: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this artifact to a dictionary.

        Returns:
            JSON-serializable dictionary.
        """
        return {
            "artifact_id": self.artifact_id,
            "node_id": str(self.node_id),
            "artifact_type": self.artifact_type.value,
            "status": self.status.value,
            "content": self.content,
            "metadata": self.metadata,
            "iteration": self.iteration,
            "created_at": self.created_at.isoformat(),
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestArtifact:
        """Deserialize an artifact from a dictionary.

        Args:
            data: A dictionary previously produced by to_dict().

        Returns:
            A new TestArtifact instance.
        """
        return cls(
            artifact_id=data["artifact_id"],
            node_id=UUID(data["node_id"]),
            artifact_type=ArtifactType(data["artifact_type"]),
            status=ArtifactStatus(data.get("status", "active")),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            iteration=data.get("iteration", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            file_path=data.get("file_path"),
        )


@dataclass
class ArtifactQuery:
    """Query parameters for searching artifacts.

    Attributes:
        node_id: Filter by node UUID.
        artifact_type: Filter by artifact type.
        status: Filter by status.
        iteration: Filter by iteration number.
        min_iteration: Minimum iteration (inclusive).
        max_iteration: Maximum iteration (inclusive).
    """

    node_id: Optional[UUID] = None
    artifact_type: Optional[ArtifactType] = None
    status: Optional[ArtifactStatus] = None
    iteration: Optional[int] = None
    min_iteration: Optional[int] = None
    max_iteration: Optional[int] = None


@dataclass
class ArtifactSummary:
    """Summary statistics for the artifact store.

    Attributes:
        total_artifacts: Total number of artifacts.
        by_type: Count by artifact type.
        by_status: Count by status.
        by_node: Count by node UUID.
        latest_iteration: Highest iteration number.
    """

    total_artifacts: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_node: dict[str, int] = field(default_factory=dict)
    latest_iteration: int = 0


class ArtifactStoreConfig(BaseModel):
    """Configuration for the TestArtifactStore.

    Attributes:
        persist_to_disk: Whether to persist artifacts to disk.
        base_dir: Base directory for artifact storage.
        max_artifacts_per_node: Maximum artifacts to retain per node.
        auto_archive_superseded: Automatically archive superseded artifacts.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    persist_to_disk: bool = Field(
        default=False,
        description="Whether to persist artifacts to disk",
    )
    base_dir: str = Field(
        default="",
        description="Base directory for artifact storage",
    )
    max_artifacts_per_node: int = Field(
        default=50,
        ge=1,
        description="Maximum artifacts per node",
    )
    auto_archive_superseded: bool = Field(
        default=True,
        description="Auto-archive superseded artifacts",
    )


# --------------------------------------------------------------------------- #
#                           Test Artifact Store                                #
# --------------------------------------------------------------------------- #


class TestArtifactStore:
    """Manages the lifecycle of test artifacts.

    Provides CRUD operations, querying, and persistence for test artifacts
    generated during the code generation pipeline.

    Args:
        config: Store configuration.
    """

    def __init__(self, config: ArtifactStoreConfig | None = None) -> None:
        self._config = config or ArtifactStoreConfig()
        # artifact_id -> TestArtifact
        self._store: dict[str, TestArtifact] = {}

    @property
    def config(self) -> ArtifactStoreConfig:
        """The store configuration."""
        return self._config

    def store(
        self,
        node_id: UUID,
        artifact_type: ArtifactType,
        content: str,
        *,
        iteration: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> TestArtifact:
        """Store a new artifact.

        If auto_archive_superseded is enabled, previous artifacts of the
        same type and node will be marked as SUPERSEDED.

        Args:
            node_id: The UUID of the associated node.
            artifact_type: The type of artifact.
            content: The artifact content.
            iteration: The generation iteration.
            metadata: Optional metadata dict.

        Returns:
            The created TestArtifact.
        """
        artifact_id = str(uuid4())[:8]

        # Auto-archive previous artifacts of same type/node
        if self._config.auto_archive_superseded:
            for existing in self._store.values():
                if (
                    existing.node_id == node_id
                    and existing.artifact_type == artifact_type
                    and existing.status == ArtifactStatus.ACTIVE
                ):
                    existing.status = ArtifactStatus.SUPERSEDED
                    logger.debug(
                        "Superseded artifact %s for node %s",
                        existing.artifact_id,
                        node_id,
                    )

        artifact = TestArtifact(
            artifact_id=artifact_id,
            node_id=node_id,
            artifact_type=artifact_type,
            content=content,
            metadata=metadata or {},
            iteration=iteration,
        )

        self._store[artifact_id] = artifact
        logger.debug(
            "Stored artifact %s (type=%s) for node %s",
            artifact_id,
            artifact_type.value,
            node_id,
        )

        # Enforce max artifacts per node
        self._enforce_limits(node_id)

        return artifact

    def get(self, artifact_id: str) -> Optional[TestArtifact]:
        """Retrieve an artifact by ID.

        Args:
            artifact_id: The unique artifact identifier.

        Returns:
            The TestArtifact, or None if not found.
        """
        return self._store.get(artifact_id)

    def query(self, q: ArtifactQuery) -> list[TestArtifact]:
        """Query artifacts matching the given criteria.

        All query parameters are optional; results must match ALL provided
        parameters (AND logic).

        Args:
            q: The query parameters.

        Returns:
            List of matching artifacts, sorted by creation time (newest first).
        """
        results: list[TestArtifact] = []

        for artifact in self._store.values():
            if q.node_id is not None and artifact.node_id != q.node_id:
                continue
            if (
                q.artifact_type is not None
                and artifact.artifact_type != q.artifact_type
            ):
                continue
            if q.status is not None and artifact.status != q.status:
                continue
            if q.iteration is not None and artifact.iteration != q.iteration:
                continue
            if (
                q.min_iteration is not None
                and artifact.iteration < q.min_iteration
            ):
                continue
            if (
                q.max_iteration is not None
                and artifact.iteration > q.max_iteration
            ):
                continue
            results.append(artifact)

        # Sort by creation time, newest first
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results

    def get_latest(
        self,
        node_id: UUID,
        artifact_type: ArtifactType,
    ) -> Optional[TestArtifact]:
        """Get the latest active artifact for a node and type.

        Args:
            node_id: The UUID of the node.
            artifact_type: The type of artifact.

        Returns:
            The latest active artifact, or None if none exists.
        """
        results = self.query(
            ArtifactQuery(
                node_id=node_id,
                artifact_type=artifact_type,
                status=ArtifactStatus.ACTIVE,
            )
        )
        return results[0] if results else None

    def archive(self, artifact_id: str) -> bool:
        """Archive an artifact.

        Args:
            artifact_id: The artifact to archive.

        Returns:
            True if archived, False if not found.
        """
        artifact = self._store.get(artifact_id)
        if artifact is None:
            return False
        artifact.status = ArtifactStatus.ARCHIVED
        return True

    def delete(self, artifact_id: str) -> bool:
        """Soft-delete an artifact (marks as DELETED, doesn't remove).

        Args:
            artifact_id: The artifact to delete.

        Returns:
            True if deleted, False if not found.
        """
        artifact = self._store.get(artifact_id)
        if artifact is None:
            return False
        artifact.status = ArtifactStatus.DELETED
        return True

    def purge_deleted(self) -> int:
        """Remove all artifacts marked as DELETED from storage.

        Returns:
            Number of artifacts purged.
        """
        to_purge = [
            aid
            for aid, a in self._store.items()
            if a.status == ArtifactStatus.DELETED
        ]
        for aid in to_purge:
            del self._store[aid]
        return len(to_purge)

    def get_summary(self) -> ArtifactSummary:
        """Generate a summary of the artifact store.

        Returns:
            An ArtifactSummary with statistics.
        """
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_node: dict[str, int] = {}
        latest_iter = 0

        for artifact in self._store.values():
            t = artifact.artifact_type.value
            by_type[t] = by_type.get(t, 0) + 1

            s = artifact.status.value
            by_status[s] = by_status.get(s, 0) + 1

            n = str(artifact.node_id)
            by_node[n] = by_node.get(n, 0) + 1

            if artifact.iteration > latest_iter:
                latest_iter = artifact.iteration

        return ArtifactSummary(
            total_artifacts=len(self._store),
            by_type=by_type,
            by_status=by_status,
            by_node=by_node,
            latest_iteration=latest_iter,
        )

    def save_to_disk(self, path: str | None = None) -> str:
        """Persist all artifacts to a JSON file.

        Args:
            path: Optional output path. Defaults to config base_dir.

        Returns:
            The path the artifacts were saved to.
        """
        target = path or os.path.join(
            self._config.base_dir or tempfile.gettempdir(),
            "test_artifacts.json",
        )
        dir_name = os.path.dirname(os.path.abspath(target))
        os.makedirs(dir_name, exist_ok=True)

        data = {
            "artifacts": [a.to_dict() for a in self._store.values()],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, target)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        logger.info("Saved %d artifacts to %s", len(self._store), target)
        return target

    @classmethod
    def load_from_disk(
        cls,
        path: str,
        config: ArtifactStoreConfig | None = None,
    ) -> TestArtifactStore:
        """Load artifacts from a JSON file.

        Args:
            path: The path to the JSON file.
            config: Optional store configuration.

        Returns:
            A new TestArtifactStore populated with the loaded artifacts.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        with open(path) as f:
            data = json.load(f)

        store = cls(config=config)
        for artifact_data in data.get("artifacts", []):
            artifact = TestArtifact.from_dict(artifact_data)
            store._store[artifact.artifact_id] = artifact

        logger.info("Loaded %d artifacts from %s", len(store._store), path)
        return store

    def _enforce_limits(self, node_id: UUID) -> None:
        """Enforce max artifacts per node by archiving oldest.

        Args:
            node_id: The node to enforce limits for.
        """
        node_artifacts = [
            a for a in self._store.values()
            if a.node_id == node_id and a.status == ArtifactStatus.ACTIVE
        ]

        if len(node_artifacts) <= self._config.max_artifacts_per_node:
            return

        # Sort by creation time, oldest first
        node_artifacts.sort(key=lambda a: a.created_at)
        excess = len(node_artifacts) - self._config.max_artifacts_per_node

        for i in range(excess):
            node_artifacts[i].status = ArtifactStatus.ARCHIVED
            logger.debug(
                "Auto-archived artifact %s (limit enforcement)",
                node_artifacts[i].artifact_id,
            )
