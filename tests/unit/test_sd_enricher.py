"""Tests for cobuilder.pipeline.sd_enricher."""

import pytest

from cobuilder.pipeline.sd_enricher import write_all_enrichments, write_enrichment_block


def test_write_enrichment_block_appends(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text(
        "# Title\n\n## F2.1: Auto-Init Logic\n\nSome content.\n\n## F2.2: Other\n\nOther content.\n"
    )

    node = {
        "node_id": "impl_autoinit",
        "worker_type": "backend-solutions-engineer",
        "delta_status": "MODIFIED",
        "file_scope": {
            "modify": [{"path": "cobuilder/bridge.py", "reason": "add auto-init"}],
            "create": [],
            "reference_only": [],
        },
        "acceptance_criteria": [],
    }

    result = write_enrichment_block(str(sd), "F2.1", node, bead_id="bd-123")
    assert result is True
    content = sd.read_text()
    assert "## CoBuilder Enrichment — F2.1" in content
    assert "bd-123" in content
    assert "cobuilder/bridge.py" in content
    # Verify F2.2 section still intact
    assert "## F2.2: Other" in content


def test_write_enrichment_block_replaces_existing(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text(
        "# Title\n\n## F2.1: Feature\n\nContent.\n\n"
        "## CoBuilder Enrichment — F2.1: Feature\n"
        "<!-- Auto-generated -->\n\n"
        "```yaml\npipeline_node: old\n```\n\n"
        "## F2.2: Other\n"
    )

    node = {"node_id": "impl_new", "worker_type": "backend-solutions-engineer", "delta_status": "NEW"}
    write_enrichment_block(str(sd), "F2.1", node)
    content = sd.read_text()

    # Should only have one enrichment block
    assert content.count("## CoBuilder Enrichment — F2.1") == 1
    assert "impl_new" in content
    assert "pipeline_node: old" not in content


def test_write_enrichment_block_feature_not_found(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text("# Title\n\n## F2.1: Feature\n\nContent.\n")

    node = {"node_id": "impl_x"}
    result = write_enrichment_block(str(sd), "F2.99", node)
    assert result is False


def test_write_enrichment_block_file_not_found(tmp_path):
    node = {"node_id": "impl_x"}
    result = write_enrichment_block(str(tmp_path / "nonexistent.md"), "F2.1", node)
    assert result is False


def test_write_enrichment_block_create_files(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text("# Title\n\n## F2.3: New Feature\n\nDesc.\n")

    node = {
        "node_id": "impl_new_feat",
        "worker_type": "backend-solutions-engineer",
        "delta_status": "NEW",
        "file_scope": {
            "modify": [],
            "create": [{"path": "cobuilder/new_module.py", "reason": "new module"}],
            "reference_only": ["cobuilder/models.py"],
        },
        "acceptance_criteria": [
            {"criterion": "Module is importable"},
            "Returns correct data",
        ],
    }

    result = write_enrichment_block(str(sd), "F2.3", node, bead_id="bd-456")
    assert result is True
    content = sd.read_text()
    assert "cobuilder/new_module.py" in content
    assert "cobuilder/models.py" in content
    assert "Module is importable" in content
    assert "Returns correct data" in content


def test_write_enrichment_block_with_taskmaster_tasks(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text("## F2.1: Feature\n\nContent.\n")

    node = {"node_id": "impl_x", "worker_type": "backend-solutions-engineer", "delta_status": "MODIFIED"}
    tm_tasks = [{"id": 5, "title": "Implement auth endpoint"}, {"id": 6, "title": "Add tests"}]

    result = write_enrichment_block(str(sd), "F2.1", node, taskmaster_tasks=tm_tasks)
    assert result is True
    content = sd.read_text()
    assert "id: 5" in content
    assert "Implement auth endpoint" in content


def test_write_enrichment_block_preserves_subsequent_content(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text(
        "# Title\n\n"
        "## F2.1: Feature One\n\nContent one.\n\n"
        "## F2.2: Feature Two\n\nContent two.\n\n"
        "## F2.3: Feature Three\n\nContent three.\n"
    )

    node = {"node_id": "impl_one", "worker_type": "backend-solutions-engineer", "delta_status": "NEW"}
    write_enrichment_block(str(sd), "F2.1", node)
    content = sd.read_text()

    assert "## F2.2: Feature Two" in content
    assert "Content two." in content
    assert "## F2.3: Feature Three" in content
    assert "Content three." in content


def test_write_all_enrichments(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text(
        "# Doc\n\n## F2.1: First\n\nContent.\n\n## F2.2: Second\n\nContent.\n\n## F2.99: Not in nodes\n\nContent.\n"
    )

    nodes = [
        {"feature_id": "F2.1", "node_id": "impl_first", "bead_id": "bd-1", "title": "First feature"},
        {"feature_id": "F2.2", "node_id": "impl_second", "bead_id": "bd-2", "title": "Second feature"},
    ]

    count = write_all_enrichments(str(sd), nodes)
    assert count == 2
    content = sd.read_text()
    assert "## CoBuilder Enrichment — F2.1" in content
    assert "## CoBuilder Enrichment — F2.2" in content
    assert "## F2.99: Not in nodes" in content


def test_write_all_enrichments_skips_missing_feature_id(tmp_path):
    sd = tmp_path / "test.md"
    sd.write_text("# Doc\n\n## F2.1: Feature\n\nContent.\n")

    nodes = [
        {"node_id": "impl_no_feature"},  # no feature_id
        {"feature_id": "F2.1", "node_id": "impl_feat"},
    ]

    count = write_all_enrichments(str(sd), nodes)
    assert count == 1
