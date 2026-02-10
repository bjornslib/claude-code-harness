"""Tests for Epic 4.7: Workspace Management modules.

Covers BatchedFileWriter, SerenaReindexer, RepositoryStateManager,
ProgressLogger, and GracefulShutdownHandler.
"""

from __future__ import annotations

import os
import signal
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.codegen.file_writer import BatchedFileWriter
from zerorepo.codegen.progress import ProgressLogger
from zerorepo.codegen.reindexer import SerenaReindexer
from zerorepo.codegen.repo_state import RepositoryStateManager
from zerorepo.codegen.signal_handler import GracefulShutdownHandler
from zerorepo.serena.exceptions import MCPError


# =====================================================================
# BatchedFileWriter
# =====================================================================


class TestBatchedFileWriter:
    """Tests for the BatchedFileWriter."""

    def test_queue_write_buffers(self, tmp_path: Path) -> None:
        """Queued writes are buffered until flush."""
        writer = BatchedFileWriter(tmp_path, batch_size=10)
        target = tmp_path / "out.py"
        writer.queue_write(target, "x = 1\n")

        assert writer.pending_count == 1
        assert not target.exists()

    def test_flush_writes_all(self, tmp_path: Path) -> None:
        """Flush writes all queued files and clears the queue."""
        writer = BatchedFileWriter(tmp_path, batch_size=10)
        files = []
        for i in range(3):
            p = tmp_path / f"file_{i}.py"
            writer.queue_write(p, f"# file {i}\n")
            files.append(p)

        written = writer.flush()

        assert len(written) == 3
        assert writer.pending_count == 0
        for p in files:
            assert p.exists()
            assert p.read_text().startswith("# file")

    def test_batched_write_auto_flush(self, tmp_path: Path) -> None:
        """Auto-flush triggers when queue reaches batch_size."""
        writer = BatchedFileWriter(tmp_path, batch_size=5)
        targets = []
        for i in range(5):
            p = tmp_path / f"auto_{i}.py"
            targets.append(p)
            writer.queue_write(p, f"val = {i}\n")

        # After 5th write the queue should have auto-flushed
        assert writer.pending_count == 0
        for p in targets:
            assert p.exists()

    def test_written_files_tracked(self, tmp_path: Path) -> None:
        """All flushed files appear in the written_files list."""
        writer = BatchedFileWriter(tmp_path, batch_size=10)
        p1 = tmp_path / "a.py"
        p2 = tmp_path / "b.py"
        writer.queue_write(p1, "a")
        writer.queue_write(p2, "b")
        writer.flush()

        assert p1 in writer.written_files
        assert p2 in writer.written_files

    def test_atomic_write(self, tmp_path: Path) -> None:
        """Atomic write uses temp-file-then-rename strategy."""
        writer = BatchedFileWriter(tmp_path, batch_size=10)
        target = tmp_path / "module.py"
        content = "def hello(): pass\n"
        writer.queue_write(target, content)
        writer.flush()

        assert target.read_text() == content
        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_write_failure(self, tmp_path: Path) -> None:
        """On write failure, temp file is cleaned up."""
        writer = BatchedFileWriter(tmp_path, batch_size=10)
        target = tmp_path / "fail.py"

        # Patch os.rename to fail, simulating an error after writing
        with patch("zerorepo.codegen.file_writer.os.rename", side_effect=OSError("rename failed")):
            writer.queue_write(target, "content")
            with pytest.raises(OSError, match="rename failed"):
                writer.flush()

        # Target should not exist, temp should be cleaned up
        assert not target.exists()
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Atomic write creates parent directories if needed."""
        writer = BatchedFileWriter(tmp_path, batch_size=10)
        target = tmp_path / "deep" / "nested" / "module.py"
        writer.queue_write(target, "x = 1\n")
        writer.flush()

        assert target.exists()
        assert target.read_text() == "x = 1\n"

    def test_flush_empty_queue(self, tmp_path: Path) -> None:
        """Flushing an empty queue returns an empty list."""
        writer = BatchedFileWriter(tmp_path, batch_size=5)
        result = writer.flush()
        assert result == []


# =====================================================================
# SerenaReindexer
# =====================================================================


class TestSerenaReindexer:
    """Tests for the SerenaReindexer."""

    def _make_mock_client(self) -> MagicMock:
        """Create a mock MCPClient."""
        return MagicMock()

    def test_should_reindex_with_python_files(self, tmp_path: Path) -> None:
        """Returns True when Python files exist in the list."""
        client = self._make_mock_client()
        reindexer = SerenaReindexer(client)

        assert reindexer.should_reindex([
            tmp_path / "a.py",
            tmp_path / "b.txt",
        ])

    def test_reindex_skip_no_changes(self) -> None:
        """Returns False when no Python files are in the list."""
        client = self._make_mock_client()
        reindexer = SerenaReindexer(client)

        assert not reindexer.should_reindex([
            Path("readme.md"),
            Path("data.json"),
        ])

    def test_trigger_reindex_success(self, tmp_path: Path) -> None:
        """Successful re-index returns True."""
        client = self._make_mock_client()
        client.call_tool.return_value = {"status": "ok"}

        reindexer = SerenaReindexer(client)
        result = reindexer.trigger_reindex(tmp_path)

        assert result is True
        client.call_tool.assert_called_once_with(
            "list_dir",
            {"path": str(tmp_path.resolve())},
        )

    def test_trigger_reindex_mcp_error(self, tmp_path: Path) -> None:
        """Returns False when Serena MCP raises an error."""
        client = self._make_mock_client()
        client.call_tool.side_effect = MCPError("Server down")

        reindexer = SerenaReindexer(client)
        result = reindexer.trigger_reindex(tmp_path)

        assert result is False

    def test_reindex_timeout(self, tmp_path: Path) -> None:
        """Returns False when re-index exceeds timeout.

        We simulate this by making call_tool sleep longer than
        the timeout.
        """
        import time as _time

        client = self._make_mock_client()

        def slow_call(*args, **kwargs):
            _time.sleep(0.05)
            return {}

        client.call_tool.side_effect = slow_call

        reindexer = SerenaReindexer(client)
        # Set very tight timeout so the call "exceeds" it
        result = reindexer.trigger_reindex(tmp_path, timeout=0.001)

        assert result is False

    def test_should_reindex_after_trigger(self, tmp_path: Path) -> None:
        """After a successful re-index, should_reindex excludes already-indexed paths."""
        client = self._make_mock_client()
        client.call_tool.return_value = {}
        reindexer = SerenaReindexer(client)

        # Trigger reindex
        reindexer.trigger_reindex(tmp_path)

        # New python files should still need reindexing
        assert reindexer.should_reindex([tmp_path / "new.py"])


# =====================================================================
# RepositoryStateManager
# =====================================================================


class TestRepositoryStateManager:
    """Tests for the RepositoryStateManager."""

    def test_syntax_validation_valid(self, tmp_path: Path) -> None:
        """Valid Python passes syntax check."""
        py_file = tmp_path / "good.py"
        py_file.write_text("def greet(name: str) -> str:\n    return f'Hello {name}'\n")

        assert RepositoryStateManager.validate_syntax(py_file) is True

    def test_syntax_validation_invalid(self, tmp_path: Path) -> None:
        """Invalid Python fails syntax check."""
        py_file = tmp_path / "bad.py"
        py_file.write_text("def broken(\n")

        assert RepositoryStateManager.validate_syntax(py_file) is False

    def test_syntax_validation_nonexistent(self, tmp_path: Path) -> None:
        """Non-existent file returns False."""
        assert RepositoryStateManager.validate_syntax(tmp_path / "nope.py") is False

    def test_validate_all_syntax(self, tmp_path: Path) -> None:
        """Validates all Python files in the workspace."""
        good = tmp_path / "good.py"
        bad = tmp_path / "bad.py"
        good.write_text("x = 1\n")
        bad.write_text("def (:\n")

        mgr = RepositoryStateManager(tmp_path)
        results = mgr.validate_all_syntax()

        assert results[good] is True
        assert results[bad] is False

    def test_file_revert(self, tmp_path: Path) -> None:
        """Revert restores the backed-up version of a file."""
        mgr = RepositoryStateManager(tmp_path)
        target = tmp_path / "module.py"
        target.write_text("original = True\n")

        # Mark dirty (creates backup)
        mgr.mark_dirty(target)

        # Overwrite the file
        target.write_text("modified = True\n")
        assert target.read_text() == "modified = True\n"

        # Revert
        assert mgr.revert_file(target) is True
        assert target.read_text() == "original = True\n"

    def test_revert_no_backup(self, tmp_path: Path) -> None:
        """Revert returns False when no backup exists."""
        mgr = RepositoryStateManager(tmp_path)
        assert mgr.revert_file(tmp_path / "unknown.py") is False

    def test_dirty_file_tracking(self, tmp_path: Path) -> None:
        """Dirty files are tracked and returned sorted."""
        mgr = RepositoryStateManager(tmp_path)
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("a")
        b.write_text("b")

        mgr.mark_dirty(b)
        mgr.mark_dirty(a)

        dirty = mgr.track_dirty_files()
        assert dirty == sorted([a, b])

    def test_gitignore_content(self, tmp_path: Path) -> None:
        """Generated .gitignore contains standard patterns."""
        content = RepositoryStateManager.generate_gitignore()

        assert "__pycache__/" in content
        assert "*.py[cod]" in content
        assert ".pytest_cache/" in content
        assert ".env" in content
        assert "dist/" in content

    def test_validate_all_skips_backups(self, tmp_path: Path) -> None:
        """Validation skips files in the backup directory."""
        mgr = RepositoryStateManager(tmp_path)
        good = tmp_path / "main.py"
        good.write_text("x = 1\n")

        # Create a backup dir with an invalid file
        backup_dir = tmp_path / ".zerorepo_backups"
        backup_dir.mkdir()
        bad_backup = backup_dir / "old.py"
        bad_backup.write_text("def (:\n")

        results = mgr.validate_all_syntax()
        # Only the main file should be validated, not the backup
        assert good in results
        assert bad_backup not in results


# =====================================================================
# ProgressLogger
# =====================================================================


class TestProgressLogger:
    """Tests for the ProgressLogger."""

    def test_eta_before_any_progress(self) -> None:
        """ETA is zero before any nodes are completed."""
        logger = ProgressLogger(total_nodes=50)
        assert logger.eta_seconds == 0.0

    def test_eta_after_all_done(self) -> None:
        """ETA is zero when all nodes are complete."""
        logger = ProgressLogger(total_nodes=10)
        logger.log_progress(10, 100.0)
        assert logger.eta_seconds == 0.0

    def test_progress_logging(self) -> None:
        """ETA calculation is reasonable mid-run."""
        logger = ProgressLogger(total_nodes=100)
        # 50 nodes done in 50 seconds → ~1s per node → 50 remaining → ~50s
        logger.log_progress(50, 50.0)
        eta = logger.eta_seconds
        assert 49.0 <= eta <= 51.0

    def test_node_result_logging(self) -> None:
        """Node results are recorded."""
        logger = ProgressLogger(total_nodes=5)
        logger.log_node_result("node-1", "passed", 1.5)
        logger.log_node_result("node-2", "failed", 3.0)

        assert len(logger._node_log) == 2
        assert logger._node_log[0]["node_id"] == "node-1"
        assert logger._node_log[1]["status"] == "failed"

    def test_zero_total_nodes(self) -> None:
        """Zero total nodes doesn't cause division by zero."""
        logger = ProgressLogger(total_nodes=0)
        logger.log_progress(0, 5.0)
        assert logger.eta_seconds == 0.0

    def test_negative_total_raises(self) -> None:
        """Negative total_nodes raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            ProgressLogger(total_nodes=-1)


# =====================================================================
# GracefulShutdownHandler
# =====================================================================


class TestGracefulShutdownHandler:
    """Tests for the GracefulShutdownHandler."""

    def test_context_manager_installs_handlers(self) -> None:
        """Signal handlers are installed on enter and restored on exit."""
        original_int = signal.getsignal(signal.SIGINT)
        original_term = signal.getsignal(signal.SIGTERM)

        with GracefulShutdownHandler() as handler:
            # While inside, handlers should be our handler
            current_int = signal.getsignal(signal.SIGINT)
            assert current_int is not original_int

        # After exit, handlers should be restored
        assert signal.getsignal(signal.SIGINT) == original_int
        assert signal.getsignal(signal.SIGTERM) == original_term

    def test_shutdown_requested_flag(self) -> None:
        """Sending SIGINT sets the shutdown flag."""
        with GracefulShutdownHandler() as handler:
            assert handler.shutdown_requested is False

            # Simulate SIGINT delivery
            handler._handle_signal(signal.SIGINT, None)

            assert handler.shutdown_requested is True

    def test_graceful_shutdown_writes_checkpoint(self) -> None:
        """Check_shutdown invokes the checkpoint function and raises SystemExit."""
        checkpoint_called = []

        def checkpoint_fn():
            checkpoint_called.append(True)

        with GracefulShutdownHandler(checkpoint_fn=checkpoint_fn) as handler:
            handler._handle_signal(signal.SIGINT, None)

            with pytest.raises(SystemExit):
                handler.check_shutdown()

        assert checkpoint_called == [True]

    def test_check_shutdown_no_signal(self) -> None:
        """Check_shutdown does nothing when no signal received."""
        with GracefulShutdownHandler() as handler:
            # Should not raise
            handler.check_shutdown()

    def test_shutdown_without_checkpoint(self) -> None:
        """Check_shutdown exits cleanly when no checkpoint_fn provided."""
        with GracefulShutdownHandler() as handler:
            handler._handle_signal(signal.SIGTERM, None)

            with pytest.raises(SystemExit):
                handler.check_shutdown()

    def test_handler_does_not_interfere_with_pytest(self) -> None:
        """After context exit, pytest's KeyboardInterrupt handling is intact."""
        original = signal.getsignal(signal.SIGINT)
        with GracefulShutdownHandler():
            pass
        assert signal.getsignal(signal.SIGINT) == original
