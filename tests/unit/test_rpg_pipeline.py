"""Tests for RPGBuilder pipeline execution and validation aggregation."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from cobuilder.repomap.models.enums import InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.base import RPGEncoder
from cobuilder.repomap.rpg_enrichment.models import EncoderStep, ValidationResult
from cobuilder.repomap.rpg_enrichment.pipeline import RPGBuilder


# ---------------------------------------------------------------------------
# Test encoders
# ---------------------------------------------------------------------------


class MetadataEncoder(RPGEncoder):
    """Sets a unique metadata key on each node."""

    def __init__(self, key: str = "enriched", value: Any = True) -> None:
        self._key = key
        self._value = value

    def encode(self, graph: RPGGraph, spec: Any | None = None, baseline: RPGGraph | None = None) -> RPGGraph:
        for node in graph.nodes.values():
            node.metadata[self._key] = self._value
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        errors = [
            f"Node {nid}: missing {self._key}"
            for nid, node in graph.nodes.items()
            if self._key not in node.metadata
        ]
        return ValidationResult(passed=len(errors) == 0, errors=errors)


class CountingEncoder(RPGEncoder):
    """Tracks how many times encode() is called."""

    def __init__(self) -> None:
        self.call_count = 0

    def encode(self, graph: RPGGraph, spec: Any | None = None, baseline: RPGGraph | None = None) -> RPGGraph:
        self.call_count += 1
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        return ValidationResult(passed=True)


class FailingValidationEncoder(RPGEncoder):
    """Encodes fine but always fails validation."""

    def encode(self, graph: RPGGraph, spec: Any | None = None, baseline: RPGGraph | None = None) -> RPGGraph:
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        return ValidationResult(
            passed=False,
            errors=["validation always fails"],
            warnings=["also a warning"],
        )


class NodeAddingEncoder(RPGEncoder):
    """Adds a new node during encoding (changes node_count)."""

    def encode(self, graph: RPGGraph, spec: Any | None = None, baseline: RPGGraph | None = None) -> RPGGraph:
        new_node = RPGNode(
            name="added_by_encoder",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(new_node)
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        found = any(n.name == "added_by_encoder" for n in graph.nodes.values())
        if not found:
            return ValidationResult(passed=False, errors=["added node missing"])
        return ValidationResult(passed=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph(n_nodes: int = 3) -> RPGGraph:
    """Build a simple graph with MODULE/FUNCTIONALITY nodes."""
    graph = RPGGraph()
    for i in range(n_nodes):
        graph.add_node(
            RPGNode(
                name=f"node_{i}",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
        )
    return graph


# ===========================================================================
# Test: RPGBuilder construction
# ===========================================================================


class TestRPGBuilderConstruction:
    """Tests for creating an RPGBuilder."""

    def test_empty_builder(self) -> None:
        builder = RPGBuilder()
        assert builder.encoders == []
        assert builder.steps == []

    def test_add_encoder_returns_self(self) -> None:
        """add_encoder supports fluent chaining."""
        builder = RPGBuilder()
        result = builder.add_encoder(MetadataEncoder())
        assert result is builder

    def test_add_multiple_encoders(self) -> None:
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder("k1"))
        builder.add_encoder(MetadataEncoder("k2"))
        assert len(builder.encoders) == 2

    def test_add_non_encoder_raises_type_error(self) -> None:
        builder = RPGBuilder()
        with pytest.raises(TypeError, match="Expected RPGEncoder"):
            builder.add_encoder("not an encoder")  # type: ignore[arg-type]

    def test_fluent_chaining(self) -> None:
        """Multiple add_encoder calls can be chained."""
        builder = (
            RPGBuilder()
            .add_encoder(MetadataEncoder("a"))
            .add_encoder(MetadataEncoder("b"))
            .add_encoder(CountingEncoder())
        )
        assert len(builder.encoders) == 3


# ===========================================================================
# Test: Pipeline execution
# ===========================================================================


class TestRPGBuilderRun:
    """Tests for RPGBuilder.run()."""

    def test_run_empty_pipeline(self) -> None:
        """Running an empty pipeline returns the graph unmodified."""
        graph = _make_graph(2)
        builder = RPGBuilder()
        result = builder.run(graph)
        assert result is graph
        assert builder.steps == []

    def test_run_single_encoder(self) -> None:
        """Single encoder modifies the graph."""
        graph = _make_graph(3)
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder("enriched", True))
        result = builder.run(graph)

        assert result is graph
        for node in graph.nodes.values():
            assert node.metadata.get("enriched") is True

    def test_run_multiple_encoders_in_order(self) -> None:
        """Encoders execute in registration order."""
        graph = _make_graph(2)
        enc1 = MetadataEncoder("step", 1)
        enc2 = MetadataEncoder("step", 2)  # overwrites step to 2

        builder = RPGBuilder()
        builder.add_encoder(enc1)
        builder.add_encoder(enc2)
        builder.run(graph)

        # The last encoder wins
        for node in graph.nodes.values():
            assert node.metadata["step"] == 2

    def test_run_records_steps(self) -> None:
        """Each encoder produces an EncoderStep."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder("a"))
        builder.add_encoder(MetadataEncoder("b"))
        builder.run(graph)

        assert len(builder.steps) == 2
        assert builder.steps[0].encoder_name == "MetadataEncoder"
        assert builder.steps[1].encoder_name == "MetadataEncoder"

    def test_steps_have_timing(self) -> None:
        """Steps record positive duration."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder())
        builder.run(graph)

        step = builder.steps[0]
        assert step.duration_ms >= 0
        assert step.started_at is not None
        assert step.finished_at is not None
        assert step.finished_at >= step.started_at

    def test_steps_have_validation(self) -> None:
        """When validate_after_each=True, each step has a validation result."""
        graph = _make_graph(2)
        builder = RPGBuilder(validate_after_each=True)
        builder.add_encoder(MetadataEncoder())
        builder.run(graph)

        step = builder.steps[0]
        assert step.validation is not None
        assert step.validation.passed is True

    def test_steps_no_validation_when_disabled(self) -> None:
        """When validate_after_each=False, steps have no validation."""
        graph = _make_graph(2)
        builder = RPGBuilder(validate_after_each=False)
        builder.add_encoder(MetadataEncoder())
        builder.run(graph)

        step = builder.steps[0]
        assert step.validation is None

    def test_failing_validation_continues_pipeline(self) -> None:
        """A failing validation does not stop the pipeline."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(FailingValidationEncoder())
        builder.add_encoder(MetadataEncoder("after_fail", True))
        builder.run(graph)

        assert len(builder.steps) == 2
        assert builder.steps[0].validation is not None
        assert builder.steps[0].validation.passed is False
        for node in graph.nodes.values():
            assert node.metadata.get("after_fail") is True

    def test_counting_encoder_called_once(self) -> None:
        """Each encoder's encode() is called exactly once per run."""
        graph = _make_graph(1)
        counter = CountingEncoder()
        builder = RPGBuilder()
        builder.add_encoder(counter)
        builder.run(graph)
        assert counter.call_count == 1

    def test_run_clears_previous_steps(self) -> None:
        """Running again resets the steps list."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder())

        builder.run(graph)
        assert len(builder.steps) == 1

        builder.run(graph)
        assert len(builder.steps) == 1  # Reset, not appended

    def test_node_adding_encoder_tracks_modification(self) -> None:
        """Encoder that adds nodes records nodes_modified > 0."""
        graph = _make_graph(2)
        builder = RPGBuilder()
        builder.add_encoder(NodeAddingEncoder())
        builder.run(graph)

        step = builder.steps[0]
        assert step.nodes_modified == 1
        assert graph.node_count == 3


# ===========================================================================
# Test: Validation aggregation
# ===========================================================================


class TestValidateAll:
    """Tests for RPGBuilder.validate_all()."""

    def test_validate_all_passes(self) -> None:
        """All passing encoders yield an aggregated pass."""
        graph = _make_graph(2)
        builder = RPGBuilder()
        enc = MetadataEncoder("enriched")
        builder.add_encoder(enc)
        enc.encode(graph)

        result = builder.validate_all(graph)
        assert result.passed is True
        assert result.errors == []

    def test_validate_all_collects_errors(self) -> None:
        """Errors from multiple encoders are merged."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(FailingValidationEncoder())
        builder.add_encoder(FailingValidationEncoder())

        result = builder.validate_all(graph)
        assert result.passed is False
        assert len(result.errors) == 2

    def test_validate_all_collects_warnings(self) -> None:
        """Warnings from multiple encoders are merged."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(FailingValidationEncoder())

        result = builder.validate_all(graph)
        assert result.passed is False
        assert len(result.warnings) == 1

    def test_validate_all_empty_pipeline(self) -> None:
        """Empty pipeline validates successfully."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        result = builder.validate_all(graph)
        assert result.passed is True

    def test_validate_all_mixed_results(self) -> None:
        """Mix of passing and failing encoders fails overall."""
        graph = _make_graph(1)
        enc_pass = MetadataEncoder("enriched")
        enc_pass.encode(graph)  # pre-encode so validation passes

        builder = RPGBuilder()
        builder.add_encoder(enc_pass)
        builder.add_encoder(FailingValidationEncoder())

        result = builder.validate_all(graph)
        assert result.passed is False
        assert len(result.errors) == 1


# ===========================================================================
# Test: Logging
# ===========================================================================


class TestRPGBuilderLogging:
    """Tests that the pipeline emits log messages."""

    def test_run_logs_start_and_completion(self, caplog: pytest.LogCaptureFixture) -> None:
        """Pipeline logs start and completion messages."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder())

        with caplog.at_level(logging.INFO, logger="cobuilder.repomap.rpg_enrichment.pipeline"):
            builder.run(graph)

        messages = [r.message for r in caplog.records]
        assert any("Starting RPG enrichment pipeline" in m for m in messages)
        assert any("completed" in m.lower() for m in messages)

    def test_run_logs_per_encoder(self, caplog: pytest.LogCaptureFixture) -> None:
        """Each encoder execution is logged."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(MetadataEncoder())

        with caplog.at_level(logging.INFO, logger="cobuilder.repomap.rpg_enrichment.pipeline"):
            builder.run(graph)

        messages = [r.message for r in caplog.records]
        assert any("Running encoder: MetadataEncoder" in m for m in messages)

    def test_empty_pipeline_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Empty pipeline logs a warning."""
        graph = _make_graph(1)
        builder = RPGBuilder()

        with caplog.at_level(logging.WARNING, logger="cobuilder.repomap.rpg_enrichment.pipeline"):
            builder.run(graph)

        messages = [r.message for r in caplog.records]
        assert any("no encoders" in m.lower() for m in messages)

    def test_failed_validation_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Failed validation during run is logged as a warning."""
        graph = _make_graph(1)
        builder = RPGBuilder()
        builder.add_encoder(FailingValidationEncoder())

        with caplog.at_level(logging.WARNING, logger="cobuilder.repomap.rpg_enrichment.pipeline"):
            builder.run(graph)

        messages = [r.message for r in caplog.records]
        assert any("validation failed" in m.lower() for m in messages)


# ===========================================================================
# Test: EncoderStep model
# ===========================================================================


class TestEncoderStep:
    """Tests for the EncoderStep dataclass."""

    def test_basic_creation(self) -> None:
        step = EncoderStep(encoder_name="TestEncoder")
        assert step.encoder_name == "TestEncoder"
        assert step.finished_at is None
        assert step.duration_ms == 0.0
        assert step.nodes_modified == 0
        assert step.validation is None

    def test_with_finish(self) -> None:
        """with_finish creates a new step with completion data."""
        from datetime import datetime, timezone

        step = EncoderStep(encoder_name="Test")
        finished = datetime.now(timezone.utc)
        vr = ValidationResult(passed=True)
        completed = step.with_finish(
            finished_at=finished,
            duration_ms=42.5,
            nodes_modified=3,
            validation=vr,
        )

        assert completed.encoder_name == "Test"
        assert completed.finished_at == finished
        assert completed.duration_ms == 42.5
        assert completed.nodes_modified == 3
        assert completed.validation is vr
        # Original unchanged
        assert step.finished_at is None

    def test_frozen(self) -> None:
        """EncoderStep is frozen."""
        step = EncoderStep(encoder_name="Test")
        with pytest.raises(AttributeError):
            step.encoder_name = "changed"  # type: ignore[misc]

    def test_metadata_field(self) -> None:
        step = EncoderStep(encoder_name="Test", metadata={"key": "value"})
        assert step.metadata == {"key": "value"}
