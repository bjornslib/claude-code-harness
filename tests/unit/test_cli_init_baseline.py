"""Unit tests for zerorepo init --project-path baseline generation and
zerorepo generate --baseline loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from zerorepo.cli.app import app
from zerorepo.models.enums import NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult
from zerorepo.rpg_enrichment.pipeline import RPGBuilder
from zerorepo.serena.baseline import BaselineManager


runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_simple_graph(n: int = 3) -> RPGGraph:
    """Build a minimal RPGGraph with n MODULE nodes."""
    graph = RPGGraph()
    for i in range(n):
        graph.add_node(
            RPGNode(
                name=f"mod_{i}",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
        )
    return graph


class _SpyEncoder(RPGEncoder):
    """Encoder that records the baseline passed to it."""

    def __init__(self) -> None:
        self.received_baseline: RPGGraph | None = None
        self.called = False

    def encode(
        self,
        graph: RPGGraph,
        spec: Any | None = None,
        baseline: RPGGraph | None = None,
    ) -> RPGGraph:
        self.called = True
        self.received_baseline = baseline
        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        return ValidationResult(passed=True)


# ---------------------------------------------------------------------------
# BaselineManager tests via CLI
# ---------------------------------------------------------------------------


class TestInitProjectPath:
    """Tests for zerorepo init --project-path."""

    def test_init_help_shows_project_path(self) -> None:
        """--project-path is listed in init --help."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "--project-path" in result.output

    def test_init_help_shows_exclude(self) -> None:
        """--exclude is listed in init --help."""
        result = runner.invoke(app, ["init", "--help"])
        assert "--exclude" in result.output


class TestGenerateBaseline:
    """Tests for zerorepo generate --baseline."""

    def test_generate_help_shows_baseline(self) -> None:
        """--baseline is listed in generate --help."""
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--baseline" in result.output

    def test_generate_help_shows_baseline_short_flag(self) -> None:
        """-b is listed as short flag for --baseline."""
        result = runner.invoke(app, ["generate", "--help"])
        assert "-b" in result.output


# ---------------------------------------------------------------------------
# RPGEncoder baseline threading
# ---------------------------------------------------------------------------


class TestRPGEncoderBaselineParam:
    """Tests that RPGEncoder.encode() accepts baseline parameter."""

    def test_encoder_accepts_baseline_none(self) -> None:
        """Calling encode() without baseline works (backward-compatible)."""
        encoder = _SpyEncoder()
        graph = _make_simple_graph(1)
        result = encoder.encode(graph)
        assert result is graph
        assert encoder.called
        assert encoder.received_baseline is None

    def test_encoder_accepts_baseline_graph(self) -> None:
        """Calling encode() with a baseline passes it through."""
        encoder = _SpyEncoder()
        graph = _make_simple_graph(1)
        baseline = _make_simple_graph(2)
        result = encoder.encode(graph, baseline=baseline)
        assert result is graph
        assert encoder.received_baseline is baseline


# ---------------------------------------------------------------------------
# RPGBuilder baseline threading
# ---------------------------------------------------------------------------


class TestRPGBuilderBaseline:
    """Tests that RPGBuilder.run() passes baseline to all encoders."""

    def test_run_without_baseline(self) -> None:
        """run() without baseline keeps it as None for encoders."""
        spy = _SpyEncoder()
        builder = RPGBuilder(validate_after_each=False)
        builder.add_encoder(spy)

        graph = _make_simple_graph(2)
        builder.run(graph)

        assert spy.called
        assert spy.received_baseline is None

    def test_run_with_baseline(self) -> None:
        """run() with baseline passes it to every encoder."""
        spy1 = _SpyEncoder()
        spy2 = _SpyEncoder()
        builder = RPGBuilder(validate_after_each=False)
        builder.add_encoder(spy1)
        builder.add_encoder(spy2)

        graph = _make_simple_graph(2)
        baseline = _make_simple_graph(5)
        builder.run(graph, baseline=baseline)

        assert spy1.received_baseline is baseline
        assert spy2.received_baseline is baseline

    def test_run_with_spec_and_baseline(self) -> None:
        """run() passes both spec and baseline through."""
        spy = _SpyEncoder()
        builder = RPGBuilder(validate_after_each=False)
        builder.add_encoder(spy)

        graph = _make_simple_graph(1)
        baseline = _make_simple_graph(3)
        spec = {"some": "spec"}
        builder.run(graph, spec=spec, baseline=baseline)

        assert spy.called
        assert spy.received_baseline is baseline

    def test_run_without_baseline_produces_identical_output(self) -> None:
        """Pipeline without baseline is identical to current behaviour."""
        spy = _SpyEncoder()
        builder = RPGBuilder(validate_after_each=False)
        builder.add_encoder(spy)

        graph = _make_simple_graph(3)
        result = builder.run(graph)

        assert result is graph
        assert spy.received_baseline is None


# ---------------------------------------------------------------------------
# BaselineManager save/load integration
# ---------------------------------------------------------------------------


class TestBaselineManagerIntegration:
    """Integration test for saving and loading through the full pathway."""

    def test_save_load_roundtrip_via_manager(self, tmp_path: Path) -> None:
        """Save a baseline, load it, pass to pipeline."""
        mgr = BaselineManager()
        baseline_graph = _make_simple_graph(4)
        baseline_path = tmp_path / "baseline.json"
        mgr.save(baseline_graph, output_path=baseline_path, project_root=tmp_path)

        loaded = mgr.load(baseline_path)
        assert loaded.node_count == 4
        assert loaded.metadata["baseline_version"] == "1.0"

        # Now use it as baseline in a pipeline
        spy = _SpyEncoder()
        builder = RPGBuilder(validate_after_each=False)
        builder.add_encoder(spy)

        main_graph = _make_simple_graph(2)
        builder.run(main_graph, baseline=loaded)

        assert spy.received_baseline is loaded
        assert spy.received_baseline.node_count == 4
