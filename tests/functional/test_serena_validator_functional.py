"""Functional tests for SerenaValidator (Epic 3.7).

These tests exercise the validator in realistic multi-node graph scenarios,
verifying end-to-end drift detection and RPGBuilder pipeline integration.
All tests mock the Serena MCP client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.rpg_enrichment.pipeline import RPGBuilder
from cobuilder.repomap.rpg_enrichment.serena_validator import SerenaValidator


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_serena(
    files: list[str] | None = None,
    symbols: dict[str, list[str]] | None = None,
) -> MagicMock:
    """Create a mock Serena client using the call_tool API."""
    mock = MagicMock()
    _files = files or []
    _symbols = symbols or {}

    def _call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "get_symbols_overview":
            fp = arguments.get("file_path")
            if fp:
                return {"symbols": _symbols.get(fp, [])}
            return {"files": _files}
        elif tool_name == "activate_project":
            return {"status": "ok"}
        return {}

    mock.call_tool.side_effect = _call_tool
    return mock


def _build_realistic_graph() -> RPGGraph:
    """Build a realistic RPG graph with multiple modules and features.

    Structure:
        auth/ (MODULE)
        |- auth/login.py    (FEATURE: Login Handler)
        |- auth/register.py (FEATURE: Registration)
        |- auth/token.py    (FEATURE: Token Manager)

        data/ (MODULE)
        |- data/loader.py   (FEATURE: Data Loader)
        |- data/parser.py   (FEATURE: Data Parser)

        api/ (MODULE)
        |- api/routes.py    (FEATURE: Route Definitions)
    """
    graph = RPGGraph()

    # --- AUTH module ---
    auth_mod = RPGNode(
        name="auth",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="auth/",
    )
    graph.add_node(auth_mod)

    login = RPGNode(
        name="Login Handler",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        signature="def login(username: str, password: str) -> bool:",
        folder_path="auth/",
        file_path="auth/login.py",
    )
    register = RPGNode(
        name="Registration",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="auth/",
        file_path="auth/register.py",
    )
    token = RPGNode(
        name="Token Manager",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=InterfaceType.FUNCTION,
        signature="def create_token(user_id: int) -> str:",
        folder_path="auth/",
        file_path="auth/token.py",
    )
    for n in [login, register, token]:
        graph.add_node(n)
        graph.add_edge(RPGEdge(
            source_id=auth_mod.id, target_id=n.id, edge_type=EdgeType.HIERARCHY
        ))

    # --- DATA module ---
    data_mod = RPGNode(
        name="data",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="data/",
    )
    graph.add_node(data_mod)

    loader = RPGNode(
        name="Data Loader",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="data/",
        file_path="data/loader.py",
    )
    parser = RPGNode(
        name="Data Parser",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="data/",
        file_path="data/parser.py",
    )
    for n in [loader, parser]:
        graph.add_node(n)
        graph.add_edge(RPGEdge(
            source_id=data_mod.id, target_id=n.id, edge_type=EdgeType.HIERARCHY
        ))

    # --- API module ---
    api_mod = RPGNode(
        name="api",
        level=NodeLevel.MODULE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="api/",
    )
    graph.add_node(api_mod)

    routes = RPGNode(
        name="Route Definitions",
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTIONALITY,
        folder_path="api/",
        file_path="api/routes.py",
    )
    graph.add_node(routes)
    graph.add_edge(RPGEdge(
        source_id=api_mod.id, target_id=routes.id, edge_type=EdgeType.HIERARCHY
    ))

    return graph


# ===========================================================================
# Functional Tests
# ===========================================================================


class TestSerenaValidatorFunctional:
    """End-to-end functional tests for SerenaValidator."""

    def test_perfect_match_realistic_graph(self) -> None:
        """All planned files match actual -> PROCEED with 0% drift."""
        actual_files = [
            "auth/login.py",
            "auth/register.py",
            "auth/token.py",
            "data/loader.py",
            "data/parser.py",
            "api/routes.py",
        ]
        mock = _mock_serena(files=actual_files)
        validator = SerenaValidator(serena_client=mock)
        graph = _build_realistic_graph()

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert report["recommendation"] == "PROCEED"
        assert report["drift_percentage"] == 0.0
        assert report["missing_files"] == []
        assert report["extra_files"] == []

    def test_partial_implementation_detected(self) -> None:
        """Only some planned files exist -> missing files detected."""
        actual_files = [
            "auth/login.py",
            "auth/register.py",
            # auth/token.py, data/*, api/* missing
        ]
        mock = _mock_serena(files=actual_files)
        validator = SerenaValidator(serena_client=mock)
        graph = _build_realistic_graph()

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert len(report["missing_files"]) == 4
        assert "auth/token.py" in report["missing_files"]
        assert "data/loader.py" in report["missing_files"]
        assert report["drift_percentage"] > 15.0
        assert report["recommendation"] == "MANUAL_RECONCILIATION"

    def test_extra_unplanned_files_detected(self) -> None:
        """Actual code has files not in the RPG plan."""
        actual_files = [
            "auth/login.py",
            "auth/register.py",
            "auth/token.py",
            "data/loader.py",
            "data/parser.py",
            "api/routes.py",
            # Extra unplanned files
            "auth/middleware.py",
            "data/cache.py",
        ]
        mock = _mock_serena(files=actual_files)
        validator = SerenaValidator(serena_client=mock)
        graph = _build_realistic_graph()

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert "auth/middleware.py" in report["extra_files"]
        assert "data/cache.py" in report["extra_files"]
        assert report["drift_percentage"] > 0

    def test_serena_validated_flag_on_matching_nodes(self) -> None:
        """Nodes whose file_path matches actual code get serena_validated=True."""
        actual_files = ["auth/login.py", "data/loader.py"]
        mock = _mock_serena(files=actual_files)
        validator = SerenaValidator(serena_client=mock)
        graph = _build_realistic_graph()

        validator.encode(graph)

        validated_nodes = [
            n for n in graph.nodes.values() if n.serena_validated is True
        ]
        validated_files = {n.file_path for n in validated_nodes}
        assert "auth/login.py" in validated_files
        assert "data/loader.py" in validated_files

    def test_pipeline_integration(self) -> None:
        """SerenaValidator works correctly in an RPGBuilder pipeline."""
        actual_files = [
            "auth/login.py",
            "auth/register.py",
            "auth/token.py",
            "data/loader.py",
            "data/parser.py",
            "api/routes.py",
        ]
        mock = _mock_serena(files=actual_files)
        validator = SerenaValidator(serena_client=mock)
        builder = RPGBuilder(validate_after_each=True)
        builder.add_encoder(validator)

        graph = _build_realistic_graph()
        result = builder.run(graph)

        assert result is graph
        assert len(builder.steps) == 1
        step = builder.steps[0]
        assert step.encoder_name == "SerenaValidator"
        assert step.validation is not None
        assert step.validation.passed is True

    def test_graceful_degradation_in_pipeline(self) -> None:
        """When Serena errors on get_symbols_overview, _get_actual_files
        returns [] and the validator proceeds with all files as missing.
        The pipeline still completes without raising."""
        mock = MagicMock()
        mock.call_tool.side_effect = ConnectionError("Server down")

        validator = SerenaValidator(serena_client=mock)
        builder = RPGBuilder(validate_after_each=True)
        builder.add_encoder(validator)

        graph = _build_realistic_graph()
        result = builder.run(graph)

        # Pipeline completes without error
        report = result.metadata["validation_report"]
        assert "recommendation" in report
        # Since _get_actual_files catches the exception and returns [],
        # all planned files will be missing -> high drift
        assert report["drift_percentage"] > 0

    def test_no_client_graceful_degradation(self) -> None:
        """No client provided -> SKIPPED with no errors."""
        validator = SerenaValidator(serena_client=None)
        graph = _build_realistic_graph()

        validator.encode(graph)
        result = validator.validate(graph)

        report = graph.metadata["validation_report"]
        assert report["recommendation"] == "SKIPPED"
        assert result.passed is True

    def test_signature_mismatch_detection(self) -> None:
        """Planned signatures not found in actual code are flagged."""
        actual_files = [
            "auth/login.py",
            "auth/register.py",
            "auth/token.py",
            "data/loader.py",
            "data/parser.py",
            "api/routes.py",
        ]
        mock = _mock_serena(
            files=actual_files,
            symbols={
                "auth/login.py": ["authenticate", "check_password"],
                "auth/token.py": ["generate_jwt", "verify_jwt"],
            },
        )
        validator = SerenaValidator(serena_client=mock)
        graph = _build_realistic_graph()

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        # login() and create_token() are not in actual symbols
        assert len(report["signature_mismatches"]) >= 1

    def test_drift_percentage_computation(self) -> None:
        """Verify drift percentage is correctly computed as a 0-100 value."""
        # 6 planned, 2 actual that match, 4 missing, 3 extra
        actual_files = [
            "auth/login.py",
            "auth/register.py",
            "unexpected/a.py",
            "unexpected/b.py",
            "unexpected/c.py",
        ]
        mock = _mock_serena(files=actual_files)
        validator = SerenaValidator(serena_client=mock)
        graph = _build_realistic_graph()

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        # Total universe = 6 planned + 3 extra (that aren't in planned) = 9
        # Drift items = 4 missing + 3 extra = 7
        # drift_pct = 7/9 * 100 = ~77.78%
        assert report["drift_percentage"] > 50.0
        assert report["drift_percentage"] <= 100.0
        assert report["recommendation"] == "MANUAL_RECONCILIATION"
