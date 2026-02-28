"""Tests for cobuilder.engine.checkpoint — CheckpointManager + EngineCheckpoint.

Coverage targets from SD-PIPELINE-ENGINE-001 AC-F17:
  - save() writes to .tmp then renames (atomic write path)
  - load_or_create() returns a fresh EngineCheckpoint when no checkpoint exists
  - load_or_create() loads and validates the existing checkpoint (schema version check)
  - load_or_create() raises CheckpointVersionError on schema_version mismatch
  - CheckpointGraphMismatchError when DOT file changed between runs
  - OSError during save() is caught and does NOT propagate (non-fatal)
  - manifest.json is written once on fresh start
  - node_dir() creates per-node artefact directories
"""
from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cobuilder.engine.checkpoint import (
    ENGINE_CHECKPOINT_VERSION,
    CheckpointGraphMismatchError,
    CheckpointManager,
    EngineCheckpoint,
    NodeRecord,
)
from cobuilder.engine.exceptions import CheckpointVersionError


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """Return a fresh run directory inside a pytest tmp directory."""
    d = tmp_path / "test-pipeline-run-20260101T000000Z"
    d.mkdir()
    (d / "nodes").mkdir()
    return d


@pytest.fixture
def manager(run_dir: Path) -> CheckpointManager:
    """Return a CheckpointManager pointed at a fresh run directory."""
    return CheckpointManager(run_dir)


@pytest.fixture
def dot_path() -> str:
    return "/some/pipelines/test-pipeline.dot"


@pytest.fixture
def fresh_checkpoint(run_dir: Path, dot_path: str) -> EngineCheckpoint:
    """Return a freshly created (not yet saved) EngineCheckpoint."""
    now = datetime.now(timezone.utc)
    return EngineCheckpoint(
        pipeline_id="test-pipeline",
        dot_path=dot_path,
        run_dir=str(run_dir),
        started_at=now,
        last_updated_at=now,
    )


# ──────────────────────────────────────────────────────────────────────────────
# NodeRecord
# ──────────────────────────────────────────────────────────────────────────────

class TestNodeRecord:
    def test_basic_construction(self):
        now = datetime.now(timezone.utc)
        record = NodeRecord(
            node_id="start",
            handler_type="start",
            status="skipped",
            started_at=now,
            completed_at=now,
        )
        assert record.node_id == "start"
        assert record.handler_type == "start"
        assert record.status == "skipped"

    def test_defaults(self):
        now = datetime.now(timezone.utc)
        record = NodeRecord(
            node_id="n1",
            handler_type="codergen",
            status="success",
            started_at=now,
            completed_at=now,
        )
        assert record.context_updates == {}
        assert record.preferred_label is None
        assert record.suggested_next is None
        assert record.metadata == {}

    def test_with_all_fields(self):
        now = datetime.now(timezone.utc)
        record = NodeRecord(
            node_id="impl_auth",
            handler_type="codergen",
            status="success",
            context_updates={"auth_result": "jwt"},
            preferred_label="pass",
            suggested_next="validate",
            metadata={"tokens_used": 1234},
            started_at=now,
            completed_at=now,
        )
        assert record.context_updates == {"auth_result": "jwt"}
        assert record.preferred_label == "pass"
        assert record.suggested_next == "validate"
        assert record.metadata["tokens_used"] == 1234


# ──────────────────────────────────────────────────────────────────────────────
# EngineCheckpoint
# ──────────────────────────────────────────────────────────────────────────────

class TestEngineCheckpoint:
    def test_schema_version_default(self):
        now = datetime.now(timezone.utc)
        cp = EngineCheckpoint(
            pipeline_id="test",
            dot_path="/test.dot",
            run_dir="/runs/test",
            started_at=now,
            last_updated_at=now,
        )
        assert cp.schema_version == ENGINE_CHECKPOINT_VERSION

    def test_defaults(self):
        now = datetime.now(timezone.utc)
        cp = EngineCheckpoint(
            pipeline_id="x",
            dot_path="/x.dot",
            run_dir="/runs/x",
            started_at=now,
            last_updated_at=now,
        )
        assert cp.completed_nodes == []
        assert cp.node_records == []
        assert cp.current_node_id is None
        assert cp.last_edge_id is None
        assert cp.context == {}
        assert cp.visit_counts == {}
        assert cp.total_node_executions == 0
        assert cp.total_tokens_used == 0

    def test_json_roundtrip(self, fresh_checkpoint: EngineCheckpoint):
        """EngineCheckpoint must survive JSON serialisation/deserialisation."""
        dumped = fresh_checkpoint.model_dump_json()
        loaded = EngineCheckpoint.model_validate_json(dumped)
        assert loaded.pipeline_id == fresh_checkpoint.pipeline_id
        assert loaded.schema_version == fresh_checkpoint.schema_version
        assert loaded.completed_nodes == []

    def test_json_roundtrip_with_records(self):
        now = datetime.now(timezone.utc)
        record = NodeRecord(
            node_id="start",
            handler_type="start",
            status="skipped",
            started_at=now,
            completed_at=now,
        )
        cp = EngineCheckpoint(
            pipeline_id="pipeline",
            dot_path="/p.dot",
            run_dir="/runs/pipeline",
            started_at=now,
            last_updated_at=now,
            completed_nodes=["start"],
            node_records=[record],
            current_node_id="impl",
            context={"$last_status": "skipped"},
            visit_counts={"start": 1},
            total_node_executions=1,
        )
        loaded = EngineCheckpoint.model_validate_json(cp.model_dump_json())
        assert loaded.completed_nodes == ["start"]
        assert len(loaded.node_records) == 1
        assert loaded.node_records[0].node_id == "start"
        assert loaded.current_node_id == "impl"
        assert loaded.context["$last_status"] == "skipped"
        assert loaded.visit_counts["start"] == 1
        assert loaded.total_node_executions == 1


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointManager — load_or_create (fresh start)
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadOrCreateFresh:
    def test_returns_fresh_checkpoint_when_no_file(
        self, manager: CheckpointManager, dot_path: str
    ):
        cp = manager.load_or_create("test-pipeline", dot_path)
        assert isinstance(cp, EngineCheckpoint)
        assert cp.pipeline_id == "test-pipeline"
        assert cp.dot_path == dot_path
        assert cp.completed_nodes == []
        assert cp.current_node_id is None

    def test_fresh_checkpoint_has_correct_run_dir(
        self, manager: CheckpointManager, run_dir: Path, dot_path: str
    ):
        cp = manager.load_or_create("test-pipeline", dot_path)
        assert cp.run_dir == str(run_dir)

    def test_manifest_written_on_fresh_start(
        self, manager: CheckpointManager, dot_path: str
    ):
        manager.load_or_create("test-pipeline", dot_path)
        manifest_path = manager.run_dir / CheckpointManager.MANIFEST_FILENAME
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["pipeline_id"] == "test-pipeline"
        assert data["dot_path"] == dot_path
        assert data["schema_version"] == ENGINE_CHECKPOINT_VERSION

    def test_manifest_not_overwritten_on_second_call(
        self, manager: CheckpointManager, dot_path: str
    ):
        manager.load_or_create("test-pipeline", dot_path)
        manifest_path = manager.run_dir / CheckpointManager.MANIFEST_FILENAME
        mtime_before = manifest_path.stat().st_mtime

        # Second call (checkpoint still not saved yet so no checkpoint.json)
        manager.load_or_create("test-pipeline", dot_path)
        mtime_after = manifest_path.stat().st_mtime
        assert mtime_before == mtime_after  # manifest was not rewritten


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointManager — save (atomic write)
# ──────────────────────────────────────────────────────────────────────────────

class TestSaveAtomic:
    def test_checkpoint_json_created_after_save(
        self, manager: CheckpointManager, fresh_checkpoint: EngineCheckpoint
    ):
        assert not manager.checkpoint_path.exists()
        manager.save(fresh_checkpoint)
        assert manager.checkpoint_path.exists()

    def test_tmp_file_absent_after_save(
        self, manager: CheckpointManager, fresh_checkpoint: EngineCheckpoint
    ):
        manager.save(fresh_checkpoint)
        assert not manager._tmp_path.exists()

    def test_saved_content_is_valid_json(
        self, manager: CheckpointManager, fresh_checkpoint: EngineCheckpoint
    ):
        manager.save(fresh_checkpoint)
        data = json.loads(manager.checkpoint_path.read_text())
        assert data["pipeline_id"] == fresh_checkpoint.pipeline_id
        assert data["schema_version"] == ENGINE_CHECKPOINT_VERSION

    def test_last_updated_at_refreshed_on_save(
        self, manager: CheckpointManager, fresh_checkpoint: EngineCheckpoint
    ):
        original_ts = fresh_checkpoint.last_updated_at
        manager.save(fresh_checkpoint)
        data = json.loads(manager.checkpoint_path.read_text())
        saved_ts = datetime.fromisoformat(data["last_updated_at"])
        # The saved timestamp should be >= original (refreshed at write time)
        assert saved_ts >= original_ts

    def test_save_overwrites_previous_checkpoint(
        self, manager: CheckpointManager, run_dir: Path, dot_path: str
    ):
        now = datetime.now(timezone.utc)
        cp1 = EngineCheckpoint(
            pipeline_id="pipeline",
            dot_path=dot_path,
            run_dir=str(run_dir),
            started_at=now,
            last_updated_at=now,
            completed_nodes=["start"],
            current_node_id="impl",
        )
        manager.save(cp1)

        cp2 = EngineCheckpoint(
            pipeline_id="pipeline",
            dot_path=dot_path,
            run_dir=str(run_dir),
            started_at=now,
            last_updated_at=now,
            completed_nodes=["start", "impl"],
            current_node_id="exit",
        )
        manager.save(cp2)

        loaded = EngineCheckpoint.model_validate_json(
            manager.checkpoint_path.read_text()
        )
        assert loaded.completed_nodes == ["start", "impl"]
        assert loaded.current_node_id == "exit"

    def test_save_nonfatal_on_oserror(
        self, tmp_path: Path, fresh_checkpoint: EngineCheckpoint
    ):
        """OSError during save must NOT propagate — logged instead."""
        # Create a manager pointing to a non-writable directory
        locked_dir = tmp_path / "locked"
        locked_dir.mkdir()

        # Make directory read-only (skip on Windows where chmod is limited)
        if sys.platform != "win32":
            os.chmod(locked_dir, stat.S_IRUSR | stat.S_IXUSR)
            try:
                m = CheckpointManager(locked_dir)
                # Should not raise even though write will fail
                m.save(fresh_checkpoint)
                # Checkpoint file should NOT exist (write failed)
                assert not (locked_dir / CheckpointManager.CHECKPOINT_FILENAME).exists()
            finally:
                os.chmod(locked_dir, stat.S_IRWXU)

    def test_save_creates_run_dir_if_missing(
        self, tmp_path: Path, dot_path: str
    ):
        """save() creates run_dir if it doesn't exist yet."""
        missing_dir = tmp_path / "pipeline-run-20260101T000000Z"
        assert not missing_dir.exists()
        m = CheckpointManager(missing_dir)
        now = datetime.now(timezone.utc)
        cp = EngineCheckpoint(
            pipeline_id="pipeline",
            dot_path=dot_path,
            run_dir=str(missing_dir),
            started_at=now,
            last_updated_at=now,
        )
        m.save(cp)
        assert m.checkpoint_path.exists()


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointManager — load_or_create (resume)
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadOrCreateResume:
    def _save_checkpoint(
        self,
        manager: CheckpointManager,
        dot_path: str,
        completed_nodes: list[str],
        current_node_id: str | None = None,
    ) -> EngineCheckpoint:
        now = datetime.now(timezone.utc)
        cp = EngineCheckpoint(
            pipeline_id="test-pipeline",
            dot_path=dot_path,
            run_dir=str(manager.run_dir),
            started_at=now,
            last_updated_at=now,
            completed_nodes=completed_nodes,
            current_node_id=current_node_id,
        )
        manager.save(cp)
        return cp

    def test_loads_existing_checkpoint(
        self, manager: CheckpointManager, dot_path: str
    ):
        self._save_checkpoint(manager, dot_path, ["start"], "impl")
        loaded = manager.load_or_create("test-pipeline", dot_path)
        assert loaded.completed_nodes == ["start"]
        assert loaded.current_node_id == "impl"

    def test_loaded_pipeline_id_matches(
        self, manager: CheckpointManager, dot_path: str
    ):
        self._save_checkpoint(manager, dot_path, ["start"])
        loaded = manager.load_or_create("test-pipeline", dot_path)
        assert loaded.pipeline_id == "test-pipeline"

    def test_schema_version_mismatch_raises(
        self, manager: CheckpointManager, dot_path: str
    ):
        """CheckpointVersionError raised when schema_version does not match."""
        # Manually write a checkpoint with a different schema version
        cp_data = {
            "schema_version": "0.9.0",  # different from ENGINE_CHECKPOINT_VERSION
            "pipeline_id": "test-pipeline",
            "dot_path": dot_path,
            "run_dir": str(manager.run_dir),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "completed_nodes": [],
            "node_records": [],
            "current_node_id": None,
            "last_edge_id": None,
            "context": {},
            "visit_counts": {},
            "total_node_executions": 0,
            "total_tokens_used": 0,
        }
        manager.checkpoint_path.write_text(json.dumps(cp_data))

        with pytest.raises(CheckpointVersionError) as exc_info:
            manager.load_or_create("test-pipeline", dot_path)

        assert "0.9.0" in str(exc_info.value)
        assert ENGINE_CHECKPOINT_VERSION in str(exc_info.value)

    def test_graph_mismatch_raises_when_node_missing(
        self, manager: CheckpointManager, dot_path: str
    ):
        """CheckpointGraphMismatchError when completed node absent from graph."""
        self._save_checkpoint(manager, dot_path, ["start", "old_node"], "impl")

        current_graph_nodes = ["start", "impl", "finalize"]  # 'old_node' removed
        with pytest.raises(CheckpointGraphMismatchError) as exc_info:
            manager.load_or_create(
                "test-pipeline", dot_path, graph_node_ids=current_graph_nodes
            )

        err = exc_info.value
        assert "old_node" in err.missing_nodes
        assert "old_node" in str(err)

    def test_no_graph_mismatch_when_graph_grows(
        self, manager: CheckpointManager, dot_path: str
    ):
        """Adding new nodes to the graph is safe — only removed nodes are an issue."""
        self._save_checkpoint(manager, dot_path, ["start"], "impl")
        # Graph now has extra nodes — that's fine
        graph_nodes = ["start", "impl", "finalize", "new_extra_node"]
        loaded = manager.load_or_create(
            "test-pipeline", dot_path, graph_node_ids=graph_nodes
        )
        assert loaded.completed_nodes == ["start"]

    def test_no_graph_check_when_graph_node_ids_none(
        self, manager: CheckpointManager, dot_path: str
    ):
        """When graph_node_ids is None, graph mismatch check is skipped."""
        self._save_checkpoint(manager, dot_path, ["start", "deleted_node"])
        # Should not raise even though 'deleted_node' is in completed_nodes
        loaded = manager.load_or_create("test-pipeline", dot_path, graph_node_ids=None)
        assert "deleted_node" in loaded.completed_nodes


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointManager — create_run_dir
# ──────────────────────────────────────────────────────────────────────────────

class TestCreateRunDir:
    def test_creates_directory(self, tmp_path: Path):
        pipelines_dir = tmp_path / "pipelines"
        m = CheckpointManager.create_run_dir(pipelines_dir, "my-pipeline", "20260101T000000Z")
        assert m.run_dir.exists()
        assert m.run_dir.name == "my-pipeline-run-20260101T000000Z"

    def test_nodes_subdir_created(self, tmp_path: Path):
        pipelines_dir = tmp_path / "pipelines"
        m = CheckpointManager.create_run_dir(pipelines_dir, "pipe", "20260101T000000Z")
        assert (m.run_dir / "nodes").exists()

    def test_timestamp_defaults_to_now(self, tmp_path: Path):
        pipelines_dir = tmp_path / "pipelines"
        m = CheckpointManager.create_run_dir(pipelines_dir, "pipe")
        # Just verify the directory was created with some timestamp suffix
        assert m.run_dir.exists()
        assert m.run_dir.name.startswith("pipe-run-")


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointManager — convenience methods
# ──────────────────────────────────────────────────────────────────────────────

class TestConvenienceMethods:
    def test_exists_false_before_save(self, manager: CheckpointManager):
        assert not manager.exists()

    def test_exists_true_after_save(
        self, manager: CheckpointManager, fresh_checkpoint: EngineCheckpoint
    ):
        manager.save(fresh_checkpoint)
        assert manager.exists()

    def test_node_dir_creates_directory(self, manager: CheckpointManager):
        d = manager.node_dir("impl_auth")
        assert d.exists()
        assert d.parent == manager.run_dir / "nodes"
        assert d.name == "impl_auth"

    def test_node_dir_idempotent(self, manager: CheckpointManager):
        d1 = manager.node_dir("n1")
        d2 = manager.node_dir("n1")
        assert d1 == d2


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointGraphMismatchError
# ──────────────────────────────────────────────────────────────────────────────

class TestCheckpointGraphMismatchError:
    def test_attributes(self):
        err = CheckpointGraphMismatchError(
            checkpoint_path="/runs/cp.json",
            missing_nodes=["old_a", "old_b"],
            extra_nodes=[],
        )
        assert err.checkpoint_path == "/runs/cp.json"
        assert "old_a" in err.missing_nodes
        assert "old_b" in err.missing_nodes
        assert "old_a" in str(err)

    def test_is_exception(self):
        err = CheckpointGraphMismatchError(
            checkpoint_path="/runs/cp.json",
            missing_nodes=["n1"],
            extra_nodes=[],
        )
        assert isinstance(err, Exception)


# ──────────────────────────────────────────────────────────────────────────────
# ENGINE_CHECKPOINT_VERSION constant
# ──────────────────────────────────────────────────────────────────────────────

class TestVersionConstant:
    def test_version_is_string(self):
        assert isinstance(ENGINE_CHECKPOINT_VERSION, str)

    def test_version_format(self):
        """Must be semver-like: X.Y.Z."""
        parts = ENGINE_CHECKPOINT_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_default_schema_version_matches_constant(self):
        now = datetime.now(timezone.utc)
        cp = EngineCheckpoint(
            pipeline_id="x",
            dot_path="/x.dot",
            run_dir="/runs/x",
            started_at=now,
            last_updated_at=now,
        )
        assert cp.schema_version == ENGINE_CHECKPOINT_VERSION
