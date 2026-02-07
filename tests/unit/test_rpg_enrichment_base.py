"""Tests for the RPGEncoder abstract base class and concrete subclass behaviour."""

from __future__ import annotations

from typing import Any

import pytest

from zerorepo.models.enums import InterfaceType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult


# ---------------------------------------------------------------------------
# Test fixtures – concrete encoder stubs
# ---------------------------------------------------------------------------


class StubPassEncoder(RPGEncoder):
    """Concrete encoder that sets metadata on every node and always validates."""

    def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        for node in graph.nodes.values():
            node.metadata["stub_enriched"] = True
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        errors = [
            f"Node {nid}: missing stub_enriched"
            for nid, node in graph.nodes.items()
            if "stub_enriched" not in node.metadata
        ]
        return ValidationResult(passed=len(errors) == 0, errors=errors)


class StubFailEncoder(RPGEncoder):
    """Concrete encoder whose validate always reports errors."""

    def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        return ValidationResult(
            passed=False,
            errors=["always fails"],
            warnings=["consider fixing"],
        )


class StubWarningEncoder(RPGEncoder):
    """Encoder that passes but emits warnings."""

    def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        return ValidationResult(
            passed=True,
            errors=[],
            warnings=["something looks suspicious"],
        )


class NamedEncoder(RPGEncoder):
    """Encoder with a custom name override."""

    @property
    def name(self) -> str:
        return "custom-encoder-v2"

    def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        return ValidationResult(passed=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph(n_nodes: int = 3) -> RPGGraph:
    """Create a simple RPGGraph with *n_nodes* MODULE/FUNCTIONALITY nodes."""
    graph = RPGGraph()
    for i in range(n_nodes):
        node = RPGNode(
            name=f"node_{i}",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        graph.add_node(node)
    return graph


def _make_function_node(name: str = "fn_node") -> RPGNode:
    """Create a FUNCTION_AUGMENTED node with a valid interface + signature."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        signature="def foo() -> None",
    )


# ===========================================================================
# Test: RPGEncoder is abstract and cannot be instantiated
# ===========================================================================


class TestRPGEncoderABC:
    """Tests that RPGEncoder enforces the abstract contract."""

    def test_cannot_instantiate_directly(self) -> None:
        """RPGEncoder itself cannot be instantiated."""
        with pytest.raises(TypeError, match="abstract method"):
            RPGEncoder()  # type: ignore[abstract]

    def test_must_implement_encode(self) -> None:
        """Subclass missing encode() cannot be instantiated."""

        class MissingEncode(RPGEncoder):
            def validate(self, graph: RPGGraph) -> ValidationResult:
                return ValidationResult(passed=True)

        with pytest.raises(TypeError, match="abstract method"):
            MissingEncode()  # type: ignore[abstract]

    def test_must_implement_validate(self) -> None:
        """Subclass missing validate() cannot be instantiated."""

        class MissingValidate(RPGEncoder):
            def encode(self, graph: RPGGraph, spec: Any | None = None) -> RPGGraph:
                return graph

        with pytest.raises(TypeError, match="abstract method"):
            MissingValidate()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        """A fully-implemented subclass can be instantiated."""
        enc = StubPassEncoder()
        assert isinstance(enc, RPGEncoder)


# ===========================================================================
# Test: Default name property
# ===========================================================================


class TestEncoderNameProperty:
    """Tests for the .name property."""

    def test_default_name_is_class_name(self) -> None:
        assert StubPassEncoder().name == "StubPassEncoder"

    def test_custom_name_override(self) -> None:
        assert NamedEncoder().name == "custom-encoder-v2"


# ===========================================================================
# Test: Encode behaviour
# ===========================================================================


class TestEncodeMethod:
    """Tests for encoder.encode() on concrete subclasses."""

    def test_encode_mutates_graph_in_place(self) -> None:
        """StubPassEncoder sets metadata['stub_enriched'] = True on each node."""
        graph = _make_graph(3)
        enc = StubPassEncoder()
        returned = enc.encode(graph)

        assert returned is graph, "encode() should return the same graph object"
        for node in graph.nodes.values():
            assert node.metadata.get("stub_enriched") is True

    def test_encode_on_empty_graph(self) -> None:
        """Encoding an empty graph should succeed without error."""
        graph = RPGGraph()
        enc = StubPassEncoder()
        returned = enc.encode(graph)
        assert returned is graph
        assert graph.node_count == 0

    def test_encode_preserves_existing_metadata(self) -> None:
        """Encoding should add to metadata, not overwrite existing keys."""
        graph = _make_graph(1)
        node = next(iter(graph.nodes.values()))
        node.metadata["pre_existing"] = 42

        StubPassEncoder().encode(graph)

        assert node.metadata["pre_existing"] == 42
        assert node.metadata["stub_enriched"] is True

    def test_encode_with_function_augmented_nodes(self) -> None:
        """Encoder processes FUNCTION_AUGMENTED nodes correctly."""
        graph = RPGGraph()
        fn_node = _make_function_node("test_fn")
        graph.add_node(fn_node)

        StubPassEncoder().encode(graph)
        assert fn_node.metadata.get("stub_enriched") is True

    def test_stub_fail_encoder_does_not_modify(self) -> None:
        """StubFailEncoder.encode() returns graph unmodified."""
        graph = _make_graph(2)
        enc = StubFailEncoder()
        returned = enc.encode(graph)
        assert returned is graph
        for node in graph.nodes.values():
            assert "stub_enriched" not in node.metadata


# ===========================================================================
# Test: Validate behaviour
# ===========================================================================


class TestValidateMethod:
    """Tests for encoder.validate() on concrete subclasses."""

    def test_validate_passes_after_encode(self) -> None:
        """After StubPassEncoder.encode(), validate() should pass."""
        graph = _make_graph(3)
        enc = StubPassEncoder()
        enc.encode(graph)
        result = enc.validate(graph)
        assert result.passed is True
        assert result.errors == []

    def test_validate_fails_before_encode(self) -> None:
        """Before encoding, StubPassEncoder.validate() should fail."""
        graph = _make_graph(2)
        enc = StubPassEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert len(result.errors) == 2

    def test_validate_always_fails_for_fail_encoder(self) -> None:
        """StubFailEncoder.validate() always returns errors."""
        graph = _make_graph(1)
        enc = StubFailEncoder()
        result = enc.validate(graph)
        assert result.passed is False
        assert "always fails" in result.errors
        assert "consider fixing" in result.warnings

    def test_validate_with_warnings(self) -> None:
        """StubWarningEncoder passes but emits warnings."""
        graph = _make_graph(1)
        enc = StubWarningEncoder()
        result = enc.validate(graph)
        assert result.passed is True
        assert result.errors == []
        assert len(result.warnings) == 1

    def test_validate_on_empty_graph(self) -> None:
        """Validating an empty graph should pass (no nodes to fail on)."""
        graph = RPGGraph()
        enc = StubPassEncoder()
        result = enc.validate(graph)
        assert result.passed is True
        assert result.errors == []


# ===========================================================================
# Test: ValidationResult model
# ===========================================================================


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_simple_pass(self) -> None:
        vr = ValidationResult(passed=True)
        assert vr.passed is True
        assert vr.errors == []
        assert vr.warnings == []

    def test_simple_fail(self) -> None:
        vr = ValidationResult(passed=False, errors=["oops"])
        assert vr.passed is False
        assert vr.errors == ["oops"]

    def test_auto_correct_passed_when_errors_present(self) -> None:
        """If errors are provided but passed=True, auto-correct to False."""
        vr = ValidationResult(passed=True, errors=["real error"])
        assert vr.passed is False

    def test_frozen_immutability(self) -> None:
        """ValidationResult is frozen and cannot be mutated."""
        vr = ValidationResult(passed=True)
        with pytest.raises(AttributeError):
            vr.passed = False  # type: ignore[misc]

    def test_warnings_without_errors_pass(self) -> None:
        """Warnings alone do not cause failure."""
        vr = ValidationResult(passed=True, warnings=["watch out"])
        assert vr.passed is True
        assert len(vr.warnings) == 1
