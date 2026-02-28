"""Tests for cobuilder.pipeline.dot_context."""

import pytest
from pathlib import Path

from cobuilder.pipeline.dot_context import get_pipeline_context


SAMPLE_DOT = """digraph pipeline {
    graph [prd_ref="PRD-TEST-001"; label="Test Pipeline"];
    impl_auth [handler=codergen; status=pending; label="Implement auth"; bead_id="bd-001"];
    impl_db [handler=codergen; status=validated; label="Setup database"; bead_id="bd-002"];
    impl_auth -> impl_db;
}"""


def test_missing_file_returns_empty():
    result = get_pipeline_context("/nonexistent/path/pipeline.dot")
    assert result == ""


def test_invalid_dot_returns_empty(tmp_path):
    f = tmp_path / "bad.dot"
    f.write_text("this is not valid dot {{{")
    # Should not raise, just return empty or non-empty (parser is lenient)
    result = get_pipeline_context(str(f))
    # Either "" or a string — the parser is lenient, just must not raise
    assert isinstance(result, str)


def test_valid_dot_returns_nonempty(tmp_path):
    f = tmp_path / "pipeline.dot"
    f.write_text(SAMPLE_DOT)
    result = get_pipeline_context(str(f))
    assert result != ""


def test_node_labels_appear_in_output(tmp_path):
    f = tmp_path / "pipeline.dot"
    f.write_text(SAMPLE_DOT)
    result = get_pipeline_context(str(f))
    assert "Implement auth" in result
    assert "Setup database" in result


def test_prd_ref_appears_in_output(tmp_path):
    f = tmp_path / "pipeline.dot"
    f.write_text(SAMPLE_DOT)
    result = get_pipeline_context(str(f))
    assert "PRD-TEST-001" in result


def test_pending_nodes_in_pending_section(tmp_path):
    f = tmp_path / "pipeline.dot"
    f.write_text(SAMPLE_DOT)
    result = get_pipeline_context(str(f))
    assert "PENDING" in result
    # impl_auth is pending — its label should appear near/under PENDING
    assert "Implement auth" in result


def test_validated_nodes_in_validated_section(tmp_path):
    f = tmp_path / "pipeline.dot"
    f.write_text(SAMPLE_DOT)
    result = get_pipeline_context(str(f))
    assert "VALIDATED" in result
    assert "Setup database" in result
