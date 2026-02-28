"""Tests for JSONLEmitter — JSONL file backend."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cobuilder.engine.events.jsonl_backend import JSONLEmitter
from cobuilder.engine.events.types import EventBuilder, PipelineEvent


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_event(pipeline_id: str = "test-pipe") -> PipelineEvent:
    return EventBuilder.pipeline_started(pipeline_id, "graph.dot", 3)


# ---------------------------------------------------------------------------
# Construction and file creation
# ---------------------------------------------------------------------------

class TestJSONLEmitterConstruction:

    def test_creates_file_on_construction(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        assert os.path.exists(path)
        _run(emitter.aclose())

    def test_creates_parent_directories(self, tmp_path) -> None:
        path = str(tmp_path / "deep" / "nested" / "events.jsonl")
        emitter = JSONLEmitter(path)
        assert os.path.exists(path)
        _run(emitter.aclose())

    def test_path_attribute_stored(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        assert emitter._path == path
        _run(emitter.aclose())


# ---------------------------------------------------------------------------
# Append mode behaviour
# ---------------------------------------------------------------------------

class TestJSONLEmitterAppendMode:

    def test_emit_5_events_produces_5_lines(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        for i in range(5):
            _run(emitter.emit(EventBuilder.pipeline_started(f"p{i}", "g.dot", i)))
        _run(emitter.aclose())
        with open(path, encoding="utf-8") as fh:
            lines = [l for l in fh.readlines() if l.strip()]
        assert len(lines) == 5

    def test_each_line_is_valid_json(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        _run(emitter.emit(_make_event()))
        _run(emitter.aclose())
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    json.loads(line)  # must not raise

    def test_append_mode_preserves_existing_events(self, tmp_path) -> None:
        """Write 2 events, close, open again, write 2 more — expect 4 lines total."""
        path = str(tmp_path / "events.jsonl")

        emitter1 = JSONLEmitter(path)
        for i in range(2):
            _run(emitter1.emit(EventBuilder.pipeline_started(f"p{i}", "g.dot", i)))
        _run(emitter1.aclose())

        emitter2 = JSONLEmitter(path)
        for i in range(2):
            _run(emitter2.emit(EventBuilder.node_started(f"p{i}", f"n{i}", "box", 1)))
        _run(emitter2.aclose())

        with open(path, encoding="utf-8") as fh:
            lines = [l for l in fh.readlines() if l.strip()]
        assert len(lines) == 4

    def test_timestamp_serialised_as_iso_8601_string(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        _run(emitter.emit(_make_event()))
        _run(emitter.aclose())
        with open(path, encoding="utf-8") as fh:
            record = json.loads(fh.read().strip())
        ts = record["timestamp"]
        assert isinstance(ts, str), f"timestamp should be str, got {type(ts)}"
        # Must parse back as ISO-8601
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_flush_after_each_write(self, tmp_path) -> None:
        """File size must grow after each emit() before aclose() is called."""
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        sizes = []
        for i in range(3):
            _run(emitter.emit(EventBuilder.pipeline_started(f"p{i}", "g.dot", i)))
            sizes.append(os.path.getsize(path))
        _run(emitter.aclose())
        # Each emit should have increased the file size
        for a, b in zip(sizes, sizes[1:]):
            assert b > a, f"File size did not increase: {sizes}"


# ---------------------------------------------------------------------------
# aclose() semantics
# ---------------------------------------------------------------------------

class TestJSONLEmitterAclose:

    def test_aclose_closes_file(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        _run(emitter.aclose())
        assert emitter._closed is True

    def test_emit_after_aclose_raises_value_error(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        _run(emitter.aclose())
        with pytest.raises(ValueError, match="closed"):
            _run(emitter.emit(_make_event()))

    def test_aclose_is_idempotent(self, tmp_path) -> None:
        """Calling aclose() twice must not raise."""
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        _run(emitter.aclose())
        _run(emitter.aclose())  # second call must not raise


# ---------------------------------------------------------------------------
# Serialisation correctness
# ---------------------------------------------------------------------------

class TestJSONLEmitterSerialisation:

    def test_event_fields_round_trip(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        evt = EventBuilder.node_completed(
            "my-pipeline", "node_1", "SUCCESS", 250.0, tokens_used=100, span_id="s123"
        )
        _run(emitter.emit(evt))
        _run(emitter.aclose())

        with open(path, encoding="utf-8") as fh:
            record = json.loads(fh.read().strip())

        assert record["type"] == "node.completed"
        assert record["pipeline_id"] == "my-pipeline"
        assert record["node_id"] == "node_1"
        assert record["span_id"] == "s123"
        assert record["data"]["outcome_status"] == "SUCCESS"
        assert record["data"]["tokens_used"] == 100

    def test_lines_are_newline_terminated(self, tmp_path) -> None:
        path = str(tmp_path / "events.jsonl")
        emitter = JSONLEmitter(path)
        for i in range(3):
            _run(emitter.emit(_make_event()))
        _run(emitter.aclose())
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert content.endswith("\n")
        lines = [l for l in content.split("\n") if l.strip()]
        assert len(lines) == 3
