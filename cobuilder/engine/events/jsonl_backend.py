"""JSONL backend — appends every PipelineEvent as a JSON line to a local file.

The file is opened in append mode on construction so that events from a
resumed pipeline run accumulate rather than overwriting prior events.
Each ``emit()`` call serialises the event to JSON, writes a newline-terminated
line, and flushes immediately to ensure durability on process crash.

After ``aclose()`` is called, subsequent ``emit()`` calls raise ``ValueError``
to surface programming errors — the emitter should always be used inside a
``try/finally: await emitter.aclose()`` block.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
from typing import IO

from cobuilder.engine.events.types import PipelineEvent

logger = logging.getLogger(__name__)


class JSONLEmitter:
    """Appends pipeline events as newline-delimited JSON to ``{run_dir}/pipeline-events.jsonl``.

    File is opened in append mode on construction.  Each ``emit()`` call
    writes exactly one JSON line and flushes the buffer.  ``aclose()`` closes
    the file handle; subsequent ``emit()`` calls raise ``ValueError``.
    """

    def __init__(self, path: str) -> None:
        """Open the JSONL file in append mode.

        Args:
            path: Absolute path to the JSONL file.  The parent directory must
                  already exist (or will be created here for convenience).
        """
        self._path = path
        self._closed = False
        self._failed = False  # Set on first write error; subsequent writes are no-ops

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        try:
            self._file: IO[str] = open(path, "a", encoding="utf-8")  # noqa: WPS515
        except OSError as exc:
            logger.warning("JSONLEmitter: cannot open %s: %s", path, exc)
            self._failed = True
            self._file = None  # type: ignore[assignment]

    async def emit(self, event: PipelineEvent) -> None:
        """Serialise ``event`` to a JSON line and flush.

        Raises:
            ValueError: If ``aclose()`` has already been called.
        """
        if self._closed:
            raise ValueError("JSONLEmitter: emitter is closed")
        if self._failed or self._file is None:
            return

        try:
            record = dataclasses.asdict(event)
            # Replace datetime with ISO-8601 string for JSON compatibility
            record["timestamp"] = event.timestamp.isoformat()
            line = json.dumps(record, ensure_ascii=False)
            self._file.write(line + "\n")
            self._file.flush()
        except OSError as exc:
            if not self._failed:
                logger.warning("JSONLEmitter: write failure on %s: %s", self._path, exc)
                self._failed = True

    async def aclose(self) -> None:
        """Close the file handle.  Idempotent — safe to call multiple times."""
        if self._closed:
            return
        self._closed = True
        if self._file is not None:
            try:
                self._file.close()
            except OSError as exc:
                logger.warning("JSONLEmitter: error closing %s: %s", self._path, exc)
