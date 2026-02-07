"""Batched file writer with atomic write support.

Provides buffered file writing with configurable batch sizes and atomic
write operations using temp-file-then-rename to ensure data integrity
during code generation.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class BatchedFileWriter:
    """Buffer and batch-write generated code files atomically.

    Files are queued in memory and flushed to disk either manually or
    when the queue reaches the configured batch size. Each write is
    atomic: content is written to a temporary file first, then renamed
    to the target path.

    Args:
        workspace_dir: Root directory for all file writes.
        batch_size: Number of queued files before auto-flush triggers.
    """

    def __init__(self, workspace_dir: Path, batch_size: int = 5) -> None:
        self._workspace_dir = workspace_dir
        self._batch_size = batch_size
        self._queue: list[tuple[Path, str]] = []
        self._written_files: list[Path] = []

    @property
    def pending_count(self) -> int:
        """Return the number of buffered writes awaiting flush."""
        return len(self._queue)

    @property
    def written_files(self) -> list[Path]:
        """Return all files written during this session."""
        return list(self._written_files)

    def queue_write(self, filepath: Path, content: str) -> None:
        """Buffer a file write for later flushing.

        If the queue reaches ``batch_size`` after this addition the
        queue is automatically flushed.

        Args:
            filepath: Target file path (relative or absolute).
            content: File content to write.
        """
        self._queue.append((filepath, content))
        self.auto_flush_check()

    def auto_flush_check(self) -> None:
        """Flush the queue if it has reached the batch size."""
        if len(self._queue) >= self._batch_size:
            self.flush()

    def flush(self) -> list[Path]:
        """Write all buffered files to disk atomically.

        Returns:
            List of file paths that were written.
        """
        written: list[Path] = []
        for filepath, content in self._queue:
            self._atomic_write(filepath, content)
            self._written_files.append(filepath)
            written.append(filepath)
            logger.info("Wrote file: %s", filepath)

        self._queue.clear()
        return written

    @staticmethod
    def _atomic_write(filepath: Path, content: str) -> None:
        """Write content to *filepath* atomically via temp-file rename.

        The parent directory is created if it does not exist. A
        temporary file is written first; only after the full write
        succeeds is it renamed to the target path. On failure the
        temporary file is cleaned up.

        Args:
            filepath: Destination file path.
            content: Content to write.

        Raises:
            OSError: If the write or rename operation fails.
        """
        dir_path = filepath.parent
        dir_path.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(content)
            os.rename(tmp_path, str(filepath))
        except BaseException:
            # Clean up temp file on any error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
