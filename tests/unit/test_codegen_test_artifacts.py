"""Unit tests for the codegen test_artifacts module."""

from __future__ import annotations

import json
import os
import tempfile
from uuid import UUID, uuid4

import pytest

from cobuilder.repomap.codegen.test_artifacts import (
    ArtifactQuery,
    ArtifactStatus,
    ArtifactStoreConfig,
    ArtifactSummary,
    ArtifactType,
    TestArtifact,
    TestArtifactStore,
)


# --------------------------------------------------------------------------- #
#                         Test: ArtifactType Enum                              #
# --------------------------------------------------------------------------- #


class TestArtifactType:
    """Test ArtifactType enum values."""

    def test_all_values(self) -> None:
        assert ArtifactType.TEST_CODE == "test_code"
        assert ArtifactType.TEST_RESULT == "test_result"
        assert ArtifactType.COVERAGE_DATA == "coverage_data"
        assert ArtifactType.VALIDATION_REPORT == "validation_report"
        assert ArtifactType.ERROR_LOG == "error_log"
        assert ArtifactType.REGRESSION_REPORT == "regression_report"

    def test_is_string_enum(self) -> None:
        assert isinstance(ArtifactType.TEST_CODE, str)

    def test_from_value(self) -> None:
        assert ArtifactType("test_code") == ArtifactType.TEST_CODE

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            ArtifactType("unknown")


# --------------------------------------------------------------------------- #
#                         Test: ArtifactStatus Enum                            #
# --------------------------------------------------------------------------- #


class TestArtifactStatus:
    """Test ArtifactStatus enum values."""

    def test_all_values(self) -> None:
        assert ArtifactStatus.ACTIVE == "active"
        assert ArtifactStatus.ARCHIVED == "archived"
        assert ArtifactStatus.SUPERSEDED == "superseded"
        assert ArtifactStatus.DELETED == "deleted"


# --------------------------------------------------------------------------- #
#                         Test: TestArtifact                                   #
# --------------------------------------------------------------------------- #


class TestTestArtifact:
    """Test TestArtifact dataclass."""

    def test_creation(self) -> None:
        node_id = uuid4()
        artifact = TestArtifact(
            artifact_id="abc123",
            node_id=node_id,
            artifact_type=ArtifactType.TEST_CODE,
            content="def test_foo(): pass",
        )
        assert artifact.artifact_id == "abc123"
        assert artifact.node_id == node_id
        assert artifact.artifact_type == ArtifactType.TEST_CODE
        assert artifact.status == ArtifactStatus.ACTIVE
        assert artifact.iteration == 0
        assert artifact.file_path is None

    def test_to_dict(self) -> None:
        node_id = uuid4()
        artifact = TestArtifact(
            artifact_id="abc123",
            node_id=node_id,
            artifact_type=ArtifactType.TEST_RESULT,
            content='{"passed": 5}',
            metadata={"source": "pytest"},
            iteration=3,
        )
        data = artifact.to_dict()
        assert data["artifact_id"] == "abc123"
        assert data["node_id"] == str(node_id)
        assert data["artifact_type"] == "test_result"
        assert data["status"] == "active"
        assert data["iteration"] == 3
        assert data["metadata"]["source"] == "pytest"

    def test_from_dict(self) -> None:
        node_id = uuid4()
        data = {
            "artifact_id": "def456",
            "node_id": str(node_id),
            "artifact_type": "coverage_data",
            "status": "archived",
            "content": "coverage text",
            "metadata": {"tool": "coverage.py"},
            "iteration": 5,
            "created_at": "2026-01-15T10:30:00+00:00",
            "file_path": "/tmp/cov.json",
        }
        artifact = TestArtifact.from_dict(data)
        assert artifact.artifact_id == "def456"
        assert artifact.node_id == node_id
        assert artifact.artifact_type == ArtifactType.COVERAGE_DATA
        assert artifact.status == ArtifactStatus.ARCHIVED
        assert artifact.iteration == 5
        assert artifact.file_path == "/tmp/cov.json"

    def test_roundtrip_serialization(self) -> None:
        original = TestArtifact(
            artifact_id="rt001",
            node_id=uuid4(),
            artifact_type=ArtifactType.ERROR_LOG,
            content="Error: something went wrong",
            metadata={"severity": "high"},
            iteration=7,
        )
        data = original.to_dict()
        restored = TestArtifact.from_dict(data)
        assert restored.artifact_id == original.artifact_id
        assert restored.node_id == original.node_id
        assert restored.artifact_type == original.artifact_type
        assert restored.content == original.content
        assert restored.iteration == original.iteration


# --------------------------------------------------------------------------- #
#                         Test: ArtifactQuery                                  #
# --------------------------------------------------------------------------- #


class TestArtifactQuery:
    """Test ArtifactQuery dataclass."""

    def test_defaults(self) -> None:
        q = ArtifactQuery()
        assert q.node_id is None
        assert q.artifact_type is None
        assert q.status is None
        assert q.iteration is None
        assert q.min_iteration is None
        assert q.max_iteration is None

    def test_with_filters(self) -> None:
        nid = uuid4()
        q = ArtifactQuery(
            node_id=nid,
            artifact_type=ArtifactType.TEST_CODE,
            status=ArtifactStatus.ACTIVE,
            iteration=3,
        )
        assert q.node_id == nid
        assert q.artifact_type == ArtifactType.TEST_CODE


# --------------------------------------------------------------------------- #
#                         Test: ArtifactSummary                                #
# --------------------------------------------------------------------------- #


class TestArtifactSummary:
    """Test ArtifactSummary dataclass."""

    def test_defaults(self) -> None:
        s = ArtifactSummary()
        assert s.total_artifacts == 0
        assert s.by_type == {}
        assert s.by_status == {}
        assert s.latest_iteration == 0


# --------------------------------------------------------------------------- #
#                         Test: ArtifactStoreConfig                            #
# --------------------------------------------------------------------------- #


class TestArtifactStoreConfig:
    """Test ArtifactStoreConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = ArtifactStoreConfig()
        assert config.persist_to_disk is False
        assert config.base_dir == ""
        assert config.max_artifacts_per_node == 50
        assert config.auto_archive_superseded is True

    def test_custom_values(self) -> None:
        config = ArtifactStoreConfig(
            persist_to_disk=True,
            base_dir="/tmp/artifacts",
            max_artifacts_per_node=10,
            auto_archive_superseded=False,
        )
        assert config.persist_to_disk is True
        assert config.base_dir == "/tmp/artifacts"

    def test_validation(self) -> None:
        with pytest.raises(Exception):
            ArtifactStoreConfig(max_artifacts_per_node=0)


# --------------------------------------------------------------------------- #
#                         Test: TestArtifactStore                              #
# --------------------------------------------------------------------------- #


class TestTestArtifactStore:
    """Test TestArtifactStore CRUD and query operations."""

    def setup_method(self) -> None:
        self.store = TestArtifactStore()
        self.node_id = uuid4()

    def test_store_artifact(self) -> None:
        artifact = self.store.store(
            self.node_id,
            ArtifactType.TEST_CODE,
            "def test_foo(): pass",
        )
        assert artifact.artifact_id is not None
        assert artifact.node_id == self.node_id
        assert artifact.artifact_type == ArtifactType.TEST_CODE
        assert artifact.status == ArtifactStatus.ACTIVE

    def test_get_artifact(self) -> None:
        artifact = self.store.store(
            self.node_id,
            ArtifactType.TEST_CODE,
            "code",
        )
        retrieved = self.store.get(artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.artifact_id == artifact.artifact_id

    def test_get_nonexistent(self) -> None:
        assert self.store.get("nonexistent") is None

    def test_store_with_metadata(self) -> None:
        artifact = self.store.store(
            self.node_id,
            ArtifactType.TEST_RESULT,
            '{"passed": 5}',
            iteration=3,
            metadata={"runner": "pytest"},
        )
        assert artifact.iteration == 3
        assert artifact.metadata["runner"] == "pytest"

    def test_auto_archive_superseded(self) -> None:
        a1 = self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "v1"
        )
        a2 = self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "v2"
        )
        # a1 should be superseded
        assert self.store.get(a1.artifact_id).status == ArtifactStatus.SUPERSEDED
        assert self.store.get(a2.artifact_id).status == ArtifactStatus.ACTIVE

    def test_no_auto_archive_when_disabled(self) -> None:
        config = ArtifactStoreConfig(auto_archive_superseded=False)
        store = TestArtifactStore(config=config)
        a1 = store.store(self.node_id, ArtifactType.TEST_CODE, "v1")
        a2 = store.store(self.node_id, ArtifactType.TEST_CODE, "v2")
        assert store.get(a1.artifact_id).status == ArtifactStatus.ACTIVE
        assert store.get(a2.artifact_id).status == ArtifactStatus.ACTIVE

    def test_query_by_node(self) -> None:
        n1, n2 = uuid4(), uuid4()
        self.store.store(n1, ArtifactType.TEST_CODE, "code1")
        self.store.store(n2, ArtifactType.TEST_CODE, "code2")
        results = self.store.query(ArtifactQuery(node_id=n1))
        assert len(results) == 1
        assert results[0].node_id == n1

    def test_query_by_type(self) -> None:
        self.store.store(self.node_id, ArtifactType.TEST_CODE, "code")
        self.store.store(self.node_id, ArtifactType.ERROR_LOG, "error")
        results = self.store.query(
            ArtifactQuery(artifact_type=ArtifactType.ERROR_LOG)
        )
        assert len(results) == 1
        assert results[0].artifact_type == ArtifactType.ERROR_LOG

    def test_query_by_status(self) -> None:
        a1 = self.store.store(self.node_id, ArtifactType.TEST_CODE, "v1")
        self.store.store(self.node_id, ArtifactType.TEST_CODE, "v2")
        # a1 should be superseded
        results = self.store.query(
            ArtifactQuery(status=ArtifactStatus.SUPERSEDED)
        )
        assert len(results) == 1
        assert results[0].artifact_id == a1.artifact_id

    def test_query_by_iteration(self) -> None:
        self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "v1", iteration=1
        )
        self.store.store(
            self.node_id, ArtifactType.ERROR_LOG, "err", iteration=2
        )
        results = self.store.query(ArtifactQuery(iteration=2))
        assert len(results) == 1
        assert results[0].iteration == 2

    def test_query_by_iteration_range(self) -> None:
        config = ArtifactStoreConfig(auto_archive_superseded=False)
        store = TestArtifactStore(config=config)
        store.store(self.node_id, ArtifactType.TEST_CODE, "v1", iteration=1)
        store.store(self.node_id, ArtifactType.TEST_CODE, "v2", iteration=3)
        store.store(self.node_id, ArtifactType.TEST_CODE, "v3", iteration=5)
        results = store.query(
            ArtifactQuery(min_iteration=2, max_iteration=4)
        )
        assert len(results) == 1
        assert results[0].iteration == 3

    def test_query_combined_filters(self) -> None:
        n1, n2 = uuid4(), uuid4()
        config = ArtifactStoreConfig(auto_archive_superseded=False)
        store = TestArtifactStore(config=config)
        store.store(n1, ArtifactType.TEST_CODE, "c1", iteration=1)
        store.store(n1, ArtifactType.ERROR_LOG, "e1", iteration=1)
        store.store(n2, ArtifactType.TEST_CODE, "c2", iteration=1)
        results = store.query(
            ArtifactQuery(
                node_id=n1,
                artifact_type=ArtifactType.TEST_CODE,
            )
        )
        assert len(results) == 1
        assert results[0].node_id == n1

    def test_query_empty_results(self) -> None:
        results = self.store.query(ArtifactQuery(node_id=uuid4()))
        assert results == []

    def test_get_latest(self) -> None:
        self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "v1", iteration=1
        )
        a2 = self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "v2", iteration=2
        )
        latest = self.store.get_latest(self.node_id, ArtifactType.TEST_CODE)
        assert latest is not None
        assert latest.artifact_id == a2.artifact_id
        assert latest.content == "v2"

    def test_get_latest_nonexistent(self) -> None:
        result = self.store.get_latest(uuid4(), ArtifactType.TEST_CODE)
        assert result is None

    def test_archive(self) -> None:
        artifact = self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "code"
        )
        assert self.store.archive(artifact.artifact_id) is True
        assert (
            self.store.get(artifact.artifact_id).status == ArtifactStatus.ARCHIVED
        )

    def test_archive_nonexistent(self) -> None:
        assert self.store.archive("nonexistent") is False

    def test_delete(self) -> None:
        artifact = self.store.store(
            self.node_id, ArtifactType.TEST_CODE, "code"
        )
        assert self.store.delete(artifact.artifact_id) is True
        assert (
            self.store.get(artifact.artifact_id).status == ArtifactStatus.DELETED
        )

    def test_delete_nonexistent(self) -> None:
        assert self.store.delete("nonexistent") is False

    def test_purge_deleted(self) -> None:
        a1 = self.store.store(self.node_id, ArtifactType.TEST_CODE, "c1")
        a2 = self.store.store(self.node_id, ArtifactType.ERROR_LOG, "e1")
        self.store.delete(a1.artifact_id)
        purged = self.store.purge_deleted()
        assert purged == 1
        assert self.store.get(a1.artifact_id) is None
        assert self.store.get(a2.artifact_id) is not None

    def test_purge_nothing(self) -> None:
        self.store.store(self.node_id, ArtifactType.TEST_CODE, "code")
        assert self.store.purge_deleted() == 0

    def test_get_summary(self) -> None:
        n1, n2 = uuid4(), uuid4()
        config = ArtifactStoreConfig(auto_archive_superseded=False)
        store = TestArtifactStore(config=config)
        store.store(n1, ArtifactType.TEST_CODE, "c", iteration=1)
        store.store(n1, ArtifactType.ERROR_LOG, "e", iteration=2)
        store.store(n2, ArtifactType.TEST_CODE, "c", iteration=3)

        summary = store.get_summary()
        assert summary.total_artifacts == 3
        assert summary.by_type["test_code"] == 2
        assert summary.by_type["error_log"] == 1
        assert summary.by_status["active"] == 3
        assert summary.latest_iteration == 3
        assert str(n1) in summary.by_node
        assert summary.by_node[str(n1)] == 2

    def test_get_summary_empty(self) -> None:
        summary = self.store.get_summary()
        assert summary.total_artifacts == 0
        assert summary.latest_iteration == 0

    def test_config_property(self) -> None:
        config = ArtifactStoreConfig(max_artifacts_per_node=10)
        store = TestArtifactStore(config=config)
        assert store.config is config

    def test_enforce_max_artifacts(self) -> None:
        config = ArtifactStoreConfig(
            max_artifacts_per_node=3,
            auto_archive_superseded=False,
        )
        store = TestArtifactStore(config=config)
        # Store 5 artifacts of different types for the same node
        ids = []
        for i in range(5):
            # Use different types to avoid superseding
            types = [
                ArtifactType.TEST_CODE,
                ArtifactType.TEST_RESULT,
                ArtifactType.ERROR_LOG,
                ArtifactType.COVERAGE_DATA,
                ArtifactType.VALIDATION_REPORT,
            ]
            a = store.store(self.node_id, types[i], f"content_{i}", iteration=i)
            ids.append(a.artifact_id)

        # Only 3 should remain active
        active = store.query(
            ArtifactQuery(node_id=self.node_id, status=ArtifactStatus.ACTIVE)
        )
        assert len(active) == 3


# --------------------------------------------------------------------------- #
#                         Test: Disk Persistence                               #
# --------------------------------------------------------------------------- #


class TestArtifactStorePersistence:
    """Test save/load to disk functionality."""

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TestArtifactStore()
            node_id = uuid4()
            store.store(
                node_id,
                ArtifactType.TEST_CODE,
                "def test_foo(): pass",
                iteration=1,
                metadata={"source": "gen"},
            )
            store.store(
                node_id,
                ArtifactType.ERROR_LOG,
                "some error",
                iteration=2,
            )

            path = os.path.join(tmpdir, "artifacts.json")
            saved_path = store.save_to_disk(path)
            assert os.path.exists(saved_path)

            # Load into a new store
            loaded = TestArtifactStore.load_from_disk(saved_path)
            summary = loaded.get_summary()
            assert summary.total_artifacts == 2

    def test_save_creates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "deep", "nested")
            path = os.path.join(nested, "artifacts.json")
            store = TestArtifactStore()
            store.store(uuid4(), ArtifactType.TEST_CODE, "code")
            store.save_to_disk(path)
            assert os.path.exists(path)

    def test_load_nonexistent_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            TestArtifactStore.load_from_disk("/nonexistent/path.json")

    def test_save_to_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ArtifactStoreConfig(base_dir=tmpdir)
            store = TestArtifactStore(config=config)
            store.store(uuid4(), ArtifactType.TEST_CODE, "code")
            path = store.save_to_disk()
            assert os.path.exists(path)
            assert tmpdir in path

    def test_roundtrip_with_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TestArtifactStore(
                ArtifactStoreConfig(auto_archive_superseded=False)
            )
            node_id = uuid4()
            a1 = store.store(
                node_id,
                ArtifactType.REGRESSION_REPORT,
                '{"regressions": []}',
                iteration=5,
                metadata={"critical": False},
            )
            store.archive(a1.artifact_id)

            path = os.path.join(tmpdir, "arts.json")
            store.save_to_disk(path)

            loaded = TestArtifactStore.load_from_disk(path)
            restored = loaded.get(a1.artifact_id)
            assert restored is not None
            assert restored.artifact_type == ArtifactType.REGRESSION_REPORT
            assert restored.status == ArtifactStatus.ARCHIVED
            assert restored.iteration == 5
            assert restored.metadata["critical"] is False
