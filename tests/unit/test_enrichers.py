"""Unit tests for the LLM enrichment pipeline."""
from unittest.mock import patch, MagicMock

import pytest

from cobuilder.pipeline.enrichers import EnrichmentPipeline
from cobuilder.pipeline.enrichers.file_scoper import FileScoper
from cobuilder.pipeline.enrichers.acceptance_crafter import AcceptanceCrafter
from cobuilder.pipeline.enrichers.dependency_inferrer import DependencyInferrer
from cobuilder.pipeline.enrichers.worker_selector import WorkerSelector
from cobuilder.pipeline.enrichers.complexity_sizer import ComplexitySizer


# ---------------------------------------------------------------------------
# FileScoper
# ---------------------------------------------------------------------------

def test_file_scoper_appends_file_scope():
    mock_response = (
        "```yaml\n"
        "file_scope:\n"
        "  modify:\n"
        "    - path: src/auth/routes.py\n"
        "      reason: Add endpoint\n"
        "  create: []\n"
        "  reference_only: []\n"
        "```"
    )
    with patch.object(FileScoper, "_call_llm", return_value=mock_response):
        scoper = FileScoper()
        node = {"title": "Add auth endpoint", "module": "auth"}
        result = scoper._enrich_one(node, {}, "")
    assert "file_scope" in result
    assert result["file_scope"]["modify"][0]["path"] == "src/auth/routes.py"
    assert result["file_scope"]["create"] == []
    assert result["file_scope"]["reference_only"] == []


def test_file_scoper_handles_parse_failure():
    with patch.object(FileScoper, "_call_llm", return_value="invalid yaml!!! no block"):
        scoper = FileScoper()
        node = {"title": "task"}
        result = scoper._enrich_one(node, {}, "")
    assert result["file_scope"] == {"modify": [], "create": [], "reference_only": []}


def test_file_scoper_preserves_other_node_keys():
    mock_response = "```yaml\nfile_scope:\n  modify: []\n  create: []\n  reference_only: []\n```"
    with patch.object(FileScoper, "_call_llm", return_value=mock_response):
        scoper = FileScoper()
        node = {"title": "task", "custom_key": "preserved_value"}
        result = scoper._enrich_one(node, {}, "")
    assert result["custom_key"] == "preserved_value"


# ---------------------------------------------------------------------------
# AcceptanceCrafter
# ---------------------------------------------------------------------------

def test_acceptance_crafter_appends_criteria():
    mock_response = (
        "```yaml\n"
        "acceptance_criteria:\n"
        "  - id: AC-1\n"
        "    criterion: Endpoint returns 200 for valid input\n"
        "    testable: true\n"
        "    evidence_type: integration_test\n"
        "```"
    )
    with patch.object(AcceptanceCrafter, "_call_llm", return_value=mock_response):
        crafter = AcceptanceCrafter()
        node = {"title": "Add endpoint"}
        result = crafter._enrich_one(node, {}, "")
    assert "acceptance_criteria" in result
    assert len(result["acceptance_criteria"]) == 1
    assert result["acceptance_criteria"][0]["id"] == "AC-1"
    assert result["acceptance_criteria"][0]["testable"] is True


def test_acceptance_crafter_returns_empty_list_on_parse_failure():
    with patch.object(AcceptanceCrafter, "_call_llm", return_value="no yaml here"):
        crafter = AcceptanceCrafter()
        node = {"title": "task"}
        result = crafter._enrich_one(node, {}, "")
    assert result["acceptance_criteria"] == []


# ---------------------------------------------------------------------------
# DependencyInferrer
# ---------------------------------------------------------------------------

def test_dependency_inferrer_appends_dependencies():
    mock_response = (
        "```yaml\n"
        "dependencies:\n"
        "  - depends_on: task-001\n"
        "    reason: Requires auth module to exist\n"
        "```"
    )
    with patch.object(DependencyInferrer, "_call_llm", return_value=mock_response):
        inferrer = DependencyInferrer()
        nodes = [
            {"id": "task-001", "title": "Create auth module"},
            {"id": "task-002", "title": "Add auth endpoint"},
        ]
        results = inferrer.enrich_all(nodes, {}, "")
    assert "dependencies" in results[1]
    assert results[1]["dependencies"][0]["depends_on"] == "task-001"


def test_dependency_inferrer_empty_on_parse_failure():
    with patch.object(DependencyInferrer, "_call_llm", return_value="bad output"):
        inferrer = DependencyInferrer()
        nodes = [{"id": "n1", "title": "task"}]
        results = inferrer.enrich_all(nodes, {}, "")
    assert results[0]["dependencies"] == []


def test_dependency_inferrer_passes_all_node_titles_as_context():
    """Ensure enrich_all passes all node titles so LLM has cross-node context."""
    call_args = []

    def capture_llm(self_inner, prompt):
        call_args.append(prompt)
        return "```yaml\ndependencies: []\n```"

    with patch.object(DependencyInferrer, "_call_llm", capture_llm):
        inferrer = DependencyInferrer()
        nodes = [
            {"id": "n1", "title": "Task Alpha"},
            {"id": "n2", "title": "Task Beta"},
        ]
        inferrer.enrich_all(nodes, {}, "")

    # Both node titles must appear in the prompts sent to LLM
    for prompt in call_args:
        assert "Task Alpha" in prompt
        assert "Task Beta" in prompt


# ---------------------------------------------------------------------------
# WorkerSelector
# ---------------------------------------------------------------------------

def test_worker_selector_selects_frontend_expert():
    mock_response = (
        "```yaml\n"
        "worker_type: frontend-dev-expert\n"
        "confidence: 0.95\n"
        "reasoning: Files are React components\n"
        "```"
    )
    with patch.object(WorkerSelector, "_call_llm", return_value=mock_response):
        selector = WorkerSelector()
        node = {
            "title": "Add login form",
            "file_scope": {
                "modify": [{"path": "src/components/Login.tsx", "reason": "add form"}],
                "create": [],
            },
        }
        result = selector._enrich_one(node, {}, "")
    assert result["worker_type"] == "frontend-dev-expert"
    assert result["worker_confidence"] == 0.95


def test_worker_selector_defaults_when_no_file_scope():
    selector = WorkerSelector()
    node = {"title": "task", "file_scope": {"modify": [], "create": []}}
    result = selector._enrich_one(node, {}, "")
    assert result["worker_type"] == "backend-solutions-engineer"


def test_worker_selector_defaults_on_invalid_worker_type():
    mock_response = (
        "```yaml\n"
        "worker_type: unknown-specialist\n"
        "confidence: 0.8\n"
        "reasoning: ?\n"
        "```"
    )
    with patch.object(WorkerSelector, "_call_llm", return_value=mock_response):
        selector = WorkerSelector()
        node = {
            "title": "task",
            "file_scope": {
                "modify": [{"path": "main.py", "reason": "fix"}],
                "create": [],
            },
        }
        result = selector._enrich_one(node, {}, "")
    assert result["worker_type"] == "backend-solutions-engineer"


# ---------------------------------------------------------------------------
# ComplexitySizer
# ---------------------------------------------------------------------------

def test_complexity_sizer_high_complexity():
    mock_response = (
        "```yaml\n"
        "complexity: high\n"
        "estimated_subtasks: 4\n"
        "split_recommendation: true\n"
        "reasoning: Many files and ACs\n"
        "```"
    )
    with patch.object(ComplexitySizer, "_call_llm", return_value=mock_response):
        sizer = ComplexitySizer()
        node = {
            "title": "Refactor everything",
            "file_scope": {
                "modify": [{"path": f"f{i}.py", "reason": "x"} for i in range(8)],
                "create": [],
            },
            "acceptance_criteria": [{"id": f"AC-{i}"} for i in range(9)],
        }
        result = sizer._enrich_one(node, {}, "")
    assert result["complexity"] == "high"
    assert result["estimated_subtasks"] == 4
    assert result["split_recommendation"] is True


def test_complexity_sizer_defaults_on_invalid_complexity():
    mock_response = (
        "```yaml\n"
        "complexity: extreme\n"
        "estimated_subtasks: 2\n"
        "split_recommendation: false\n"
        "reasoning: ok\n"
        "```"
    )
    with patch.object(ComplexitySizer, "_call_llm", return_value=mock_response):
        sizer = ComplexitySizer()
        node = {"title": "task", "file_scope": {"modify": [], "create": []}, "acceptance_criteria": []}
        result = sizer._enrich_one(node, {}, "")
    assert result["complexity"] == "medium"


# ---------------------------------------------------------------------------
# EnrichmentPipeline (integration / chain test)
# ---------------------------------------------------------------------------

def test_enrichment_pipeline_chains_all_enrichers():
    file_scope_yaml = (
        "```yaml\n"
        "file_scope:\n"
        "  modify: []\n"
        "  create: []\n"
        "  reference_only: []\n"
        "```"
    )
    ac_yaml = "```yaml\nacceptance_criteria: []\n```"
    deps_yaml = "```yaml\ndependencies: []\n```"
    worker_yaml = (
        "```yaml\n"
        "worker_type: backend-solutions-engineer\n"
        "confidence: 0.8\n"
        "reasoning: default\n"
        "```"
    )
    complexity_yaml = (
        "```yaml\n"
        "complexity: low\n"
        "estimated_subtasks: 1\n"
        "split_recommendation: false\n"
        "reasoning: small task\n"
        "```"
    )

    with (
        patch.object(FileScoper, "_call_llm", return_value=file_scope_yaml),
        patch.object(AcceptanceCrafter, "_call_llm", return_value=ac_yaml),
        patch.object(DependencyInferrer, "_call_llm", return_value=deps_yaml),
        patch.object(WorkerSelector, "_call_llm", return_value=worker_yaml),
        patch.object(ComplexitySizer, "_call_llm", return_value=complexity_yaml),
    ):
        pipeline = EnrichmentPipeline()
        nodes = [{"title": "test task", "id": "n1"}]
        result = pipeline.enrich(nodes, {}, "sample sd text")

    assert len(result) == 1
    node = result[0]
    assert "file_scope" in node
    assert "acceptance_criteria" in node
    assert "dependencies" in node
    assert "worker_type" in node
    assert "complexity" in node
    assert node["complexity"] == "low"
    assert node["worker_type"] == "backend-solutions-engineer"


def test_enrichment_pipeline_enriches_multiple_nodes():
    yaml_block = "```yaml\nfile_scope:\n  modify: []\n  create: []\n  reference_only: []\n```"
    ac_yaml = "```yaml\nacceptance_criteria: []\n```"
    deps_yaml = "```yaml\ndependencies: []\n```"
    worker_yaml = "```yaml\nworker_type: backend-solutions-engineer\nconfidence: 0.7\nreasoning: x\n```"
    complexity_yaml = "```yaml\ncomplexity: low\nestimated_subtasks: 1\nsplit_recommendation: false\nreasoning: ok\n```"

    with (
        patch.object(FileScoper, "_call_llm", return_value=yaml_block),
        patch.object(AcceptanceCrafter, "_call_llm", return_value=ac_yaml),
        patch.object(DependencyInferrer, "_call_llm", return_value=deps_yaml),
        patch.object(WorkerSelector, "_call_llm", return_value=worker_yaml),
        patch.object(ComplexitySizer, "_call_llm", return_value=complexity_yaml),
    ):
        pipeline = EnrichmentPipeline()
        nodes = [
            {"title": "Task A", "id": "n1"},
            {"title": "Task B", "id": "n2"},
            {"title": "Task C", "id": "n3"},
        ]
        result = pipeline.enrich(nodes, {}, "")

    assert len(result) == 3
    for node in result:
        assert "file_scope" in node
        assert "acceptance_criteria" in node
        assert "dependencies" in node
        assert "worker_type" in node
        assert "complexity" in node
