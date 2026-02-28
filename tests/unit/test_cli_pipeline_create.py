"""Tests for cobuilder pipeline create CLI command."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cobuilder.cli import app

runner = CliRunner()


def test_pipeline_create_calls_all_steps(tmp_path):
    """Verify all 7 steps are called in order."""
    sd_file = tmp_path / "test.md"
    sd_file.write_text("# SD\n\n## F2.1: Test\n\nContent.\n")

    with patch("cobuilder.pipeline.generate.ensure_baseline") as mock_eb, \
         patch("cobuilder.pipeline.generate.collect_repomap_nodes", return_value=[{"node_id": "n1", "title": "Node 1"}]) as mock_crn, \
         patch("cobuilder.pipeline.taskmaster_bridge.run_taskmaster_parse", return_value={}) as mock_tm, \
         patch("cobuilder.pipeline.generate.cross_reference_beads", side_effect=lambda n, p: n) as mock_crb, \
         patch("cobuilder.pipeline.enrichers.EnrichmentPipeline") as mock_ep, \
         patch("cobuilder.pipeline.generate.generate_pipeline_dot", return_value="digraph {}") as mock_dot, \
         patch("cobuilder.pipeline.sd_enricher.write_all_enrichments", return_value=0) as mock_wae:

        mock_ep.return_value.enrich.return_value = [{"node_id": "n1", "title": "Node 1"}]

        result = runner.invoke(app, [
            "pipeline", "create",
            "--sd", str(sd_file),
            "--repo", "testrepo",
            "--prd", "PRD-TEST-001",
        ])

    assert result.exit_code == 0, result.output
    mock_eb.assert_called_once()
    mock_crn.assert_called_once()
    mock_tm.assert_called_once()
    mock_crb.assert_called_once()
    mock_ep.return_value.enrich.assert_called_once()
    mock_dot.assert_called_once()
    mock_wae.assert_called_once()


def test_pipeline_create_skip_enrichment(tmp_path):
    """--skip-enrichment prevents EnrichmentPipeline from being instantiated."""
    sd_file = tmp_path / "test.md"
    sd_file.write_text("# SD\n")

    with patch("cobuilder.pipeline.generate.ensure_baseline"), \
         patch("cobuilder.pipeline.generate.collect_repomap_nodes", return_value=[]), \
         patch("cobuilder.pipeline.taskmaster_bridge.run_taskmaster_parse", return_value={}), \
         patch("cobuilder.pipeline.generate.cross_reference_beads", side_effect=lambda n, p: n), \
         patch("cobuilder.pipeline.enrichers.EnrichmentPipeline") as mock_ep, \
         patch("cobuilder.pipeline.generate.generate_pipeline_dot", return_value="digraph {}"), \
         patch("cobuilder.pipeline.sd_enricher.write_all_enrichments", return_value=0):

        result = runner.invoke(app, [
            "pipeline", "create",
            "--sd", str(sd_file),
            "--repo", "testrepo",
            "--skip-enrichment",
        ])

    assert result.exit_code == 0
    mock_ep.assert_not_called()


def test_pipeline_create_skip_taskmaster(tmp_path):
    """--skip-taskmaster prevents run_taskmaster_parse from being called."""
    sd_file = tmp_path / "test.md"
    sd_file.write_text("# SD\n")

    with patch("cobuilder.pipeline.generate.ensure_baseline"), \
         patch("cobuilder.pipeline.generate.collect_repomap_nodes", return_value=[]), \
         patch("cobuilder.pipeline.taskmaster_bridge.run_taskmaster_parse") as mock_tm, \
         patch("cobuilder.pipeline.generate.cross_reference_beads", side_effect=lambda n, p: n), \
         patch("cobuilder.pipeline.enrichers.EnrichmentPipeline") as mock_ep, \
         patch("cobuilder.pipeline.generate.generate_pipeline_dot", return_value="digraph {}"), \
         patch("cobuilder.pipeline.sd_enricher.write_all_enrichments", return_value=0):

        mock_ep.return_value.enrich.return_value = []
        result = runner.invoke(app, [
            "pipeline", "create",
            "--sd", str(sd_file),
            "--repo", "testrepo",
            "--skip-taskmaster",
        ])

    assert result.exit_code == 0
    mock_tm.assert_not_called()


def test_pipeline_create_writes_output_file(tmp_path):
    """--output writes DOT content to the specified file."""
    sd_file = tmp_path / "test.md"
    sd_file.write_text("# SD\n")
    output_file = tmp_path / "out.dot"

    with patch("cobuilder.pipeline.generate.ensure_baseline"), \
         patch("cobuilder.pipeline.generate.collect_repomap_nodes", return_value=[]), \
         patch("cobuilder.pipeline.taskmaster_bridge.run_taskmaster_parse", return_value={}), \
         patch("cobuilder.pipeline.generate.cross_reference_beads", side_effect=lambda n, p: n), \
         patch("cobuilder.pipeline.enrichers.EnrichmentPipeline") as mock_ep, \
         patch("cobuilder.pipeline.generate.generate_pipeline_dot", return_value="digraph { }"), \
         patch("cobuilder.pipeline.sd_enricher.write_all_enrichments", return_value=0):

        mock_ep.return_value.enrich.return_value = []
        result = runner.invoke(app, [
            "pipeline", "create",
            "--sd", str(sd_file),
            "--repo", "testrepo",
            "--output", str(output_file),
        ])

    assert result.exit_code == 0
    assert output_file.exists()
    assert "digraph" in output_file.read_text()
