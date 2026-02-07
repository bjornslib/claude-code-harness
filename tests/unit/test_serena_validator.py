"""Unit tests for SerenaValidator (Epic 3.7).

All tests mock the Serena MCP client so no real server is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.rpg_enrichment.serena_validator import (
    SerenaValidator,
    _compute_recommendation,
    _empty_report,
)
from zerorepo.rpg_enrichment.models import ValidationResult


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _mock_serena(
    files: list[str] | None = None,
    symbols: dict[str, list[str]] | None = None,
) -> MagicMock:
    """Create a mock Serena client using the call_tool API.

    Args:
        files: List of actual file paths returned by get_symbols_overview.
        symbols: Mapping of file_path -> list of symbol names.
    """
    mock = MagicMock()
    _files = files or []
    _symbols = symbols or {}

    def _call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "get_symbols_overview":
            fp = arguments.get("file_path")
            if fp:
                # Per-file symbol query
                return {"symbols": _symbols.get(fp, [])}
            # Project-wide query
            return {"files": _files}
        elif tool_name == "activate_project":
            return {"status": "ok"}
        return {}

    mock.call_tool.side_effect = _call_tool
    return mock


def _make_feature(
    name: str,
    file_path: str,
    folder_path: str = "src/",
    signature: str | None = None,
) -> RPGNode:
    """Create a FEATURE node."""
    kwargs: dict[str, Any] = {
        "name": name,
        "level": NodeLevel.FEATURE,
        "node_type": NodeType.FUNCTIONALITY,
        "folder_path": folder_path,
        "file_path": file_path,
    }
    if signature:
        kwargs["node_type"] = NodeType.FUNCTION_AUGMENTED
        kwargs["interface_type"] = InterfaceType.FUNCTION
        kwargs["signature"] = signature
    return RPGNode(**kwargs)


def _make_graph_with_files(file_paths: list[str]) -> RPGGraph:
    """Create a graph with one FEATURE node per file_path."""
    graph = RPGGraph()
    for i, fp in enumerate(file_paths):
        folder = "/".join(fp.split("/")[:-1]) + "/"
        node = _make_feature(f"feature_{i}", fp, folder_path=folder)
        graph.add_node(node)
    return graph


# ===========================================================================
# Test 1: No Serena client -> SKIPPED report
# ===========================================================================


class TestNoSerenaClient:
    def test_no_client_produces_skipped_report(self) -> None:
        validator = SerenaValidator(serena_client=None)
        graph = _make_graph_with_files(["src/main.py"])

        validator.encode(graph)

        report = graph.metadata.get("validation_report")
        assert report is not None
        assert report["recommendation"] == "SKIPPED"
        assert report["drift_percentage"] == 0.0
        assert report["missing_files"] == []
        assert report["extra_files"] == []


# ===========================================================================
# Test 2: Empty graph -> SKIPPED report
# ===========================================================================


class TestEmptyGraph:
    def test_empty_graph_produces_skipped_report(self) -> None:
        mock = _mock_serena(files=["src/main.py"])
        validator = SerenaValidator(serena_client=mock)
        graph = RPGGraph()

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert report["recommendation"] == "SKIPPED"


# ===========================================================================
# Test 3: Perfect match -> PROCEED
# ===========================================================================


class TestPerfectMatch:
    def test_all_files_match_produces_proceed(self) -> None:
        planned_files = ["src/main.py", "src/utils.py"]
        mock = _mock_serena(files=planned_files)
        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(planned_files)

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert report["recommendation"] == "PROCEED"
        assert report["drift_percentage"] == 0.0
        assert report["missing_files"] == []
        assert report["extra_files"] == []


# ===========================================================================
# Test 4: Missing files -> drift detected
# ===========================================================================


class TestMissingFiles:
    def test_missing_files_in_report(self) -> None:
        planned = ["src/main.py", "src/utils.py", "src/config.py"]
        actual = ["src/main.py"]  # 2 missing
        mock = _mock_serena(files=actual)
        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(planned)

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert "src/utils.py" in report["missing_files"]
        assert "src/config.py" in report["missing_files"]
        assert report["drift_percentage"] > 0


# ===========================================================================
# Test 5: Extra files -> drift detected
# ===========================================================================


class TestExtraFiles:
    def test_extra_files_in_report(self) -> None:
        planned = ["src/main.py"]
        actual = ["src/main.py", "src/extra.py", "src/bonus.py"]
        mock = _mock_serena(files=actual)
        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(planned)

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert "src/extra.py" in report["extra_files"]
        assert "src/bonus.py" in report["extra_files"]


# ===========================================================================
# Test 6: serena_validated flag set on matching nodes
# ===========================================================================


class TestSerenaValidatedFlag:
    def test_matching_nodes_get_validated_flag(self) -> None:
        planned = ["src/main.py", "src/missing.py"]
        actual = ["src/main.py"]
        mock = _mock_serena(files=actual)
        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(planned)

        validator.encode(graph)

        for node in graph.nodes.values():
            if node.file_path == "src/main.py":
                assert node.serena_validated is True
            elif node.file_path == "src/missing.py":
                # Not validated — remains at default False
                assert node.serena_validated is False


# ===========================================================================
# Test 7: High drift -> MANUAL_RECONCILIATION
# ===========================================================================


class TestHighDrift:
    def test_high_drift_recommends_manual_reconciliation(self) -> None:
        # 1 planned file, but 10 extra -> > 15% drift
        planned = ["src/a.py"]
        actual = [
            "src/a.py",
            "src/b.py",
            "src/c.py",
            "src/d.py",
            "src/e.py",
            "src/f.py",
            "src/g.py",
            "src/h.py",
            "src/i.py",
            "src/j.py",
        ]
        mock = _mock_serena(files=actual)
        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(planned)

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert report["recommendation"] == "MANUAL_RECONCILIATION"
        assert report["drift_percentage"] > 15.0


# ===========================================================================
# Test 8: Serena error -> SKIPPED (graceful degradation)
# ===========================================================================


class TestSerenaError:
    def test_serena_error_does_not_raise(self) -> None:
        """When Serena connection fails, encode() does not propagate the error."""
        mock = MagicMock()
        mock.call_tool.side_effect = RuntimeError("Connection refused")

        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(["src/main.py"])

        # Should NOT raise
        validator.encode(graph)

        report = graph.metadata["validation_report"]
        # _get_actual_files catches the error and returns [], producing a
        # drift report with all planned files as missing
        assert "recommendation" in report
        assert report["missing_files"] == ["src/main.py"]

    def test_serena_error_still_produces_report(self) -> None:
        """Even with Serena errors, a valid drift report is generated."""
        mock = MagicMock()
        mock.call_tool.side_effect = ConnectionError("Serena offline")

        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(["src/main.py", "src/utils.py"])

        validator.encode(graph)

        report = graph.metadata["validation_report"]
        # Required keys are present
        assert "missing_files" in report
        assert "extra_files" in report
        assert "signature_mismatches" in report
        assert "drift_percentage" in report
        assert "recommendation" in report


# ===========================================================================
# Test 9: Validate method checks report structure
# ===========================================================================


class TestValidateMethod:
    def test_validate_passes_after_encode(self) -> None:
        mock = _mock_serena(files=["src/main.py"])
        validator = SerenaValidator(serena_client=mock)
        graph = _make_graph_with_files(["src/main.py"])

        validator.encode(graph)
        result = validator.validate(graph)

        assert result.passed is True

    def test_validate_fails_without_report(self) -> None:
        validator = SerenaValidator(serena_client=None)
        graph = RPGGraph()  # No encode() called

        result = validator.validate(graph)

        assert result.passed is False
        assert any("Missing validation_report" in e for e in result.errors)

    def test_validate_warns_on_high_drift(self) -> None:
        """High drift should produce a warning."""
        validator = SerenaValidator(serena_client=None)
        graph = RPGGraph()
        graph.metadata["validation_report"] = {
            "missing_files": ["a.py", "b.py"],
            "extra_files": [],
            "signature_mismatches": [],
            "drift_percentage": 20.0,
            "recommendation": "MANUAL_RECONCILIATION",
        }

        result = validator.validate(graph)
        assert result.passed is True
        assert any("High drift" in w for w in result.warnings)


# ===========================================================================
# Test 10: Helper functions
# ===========================================================================


class TestHelpers:
    def test_empty_report_defaults(self) -> None:
        report = _empty_report()
        assert report["recommendation"] == "SKIPPED"
        assert report["drift_percentage"] == 0.0

    def test_compute_recommendation_proceed(self) -> None:
        assert _compute_recommendation(3.0) == "PROCEED"

    def test_compute_recommendation_caution(self) -> None:
        assert _compute_recommendation(10.0) == "PROCEED_WITH_CAUTION"

    def test_compute_recommendation_manual(self) -> None:
        assert _compute_recommendation(20.0) == "MANUAL_RECONCILIATION"

    def test_compute_recommendation_boundary_5(self) -> None:
        assert _compute_recommendation(5.0) == "PROCEED_WITH_CAUTION"

    def test_compute_recommendation_boundary_15(self) -> None:
        assert _compute_recommendation(15.0) == "MANUAL_RECONCILIATION"


# ===========================================================================
# Test 11: Project path activation
# ===========================================================================


class TestProjectActivation:
    def test_activate_project_called_when_path_provided(self) -> None:
        mock = _mock_serena(files=["src/main.py"])
        validator = SerenaValidator(
            serena_client=mock,
            project_path="/my/project",
        )
        graph = _make_graph_with_files(["src/main.py"])

        validator.encode(graph)

        # Check activate_project was called via call_tool
        calls = [
            c for c in mock.call_tool.call_args_list
            if c[0][0] == "activate_project"
        ]
        assert len(calls) == 1
        assert calls[0][0][1] == {"project_path": "/my/project"}


# ===========================================================================
# Test 12: Encoder name property
# ===========================================================================


class TestEncoderName:
    def test_name_is_class_name(self) -> None:
        validator = SerenaValidator()
        assert validator.name == "SerenaValidator"


# ===========================================================================
# Test 13: Signature mismatches
# ===========================================================================


class TestSignatureMismatches:
    def test_mismatched_symbols_detected(self) -> None:
        graph = RPGGraph()
        node = RPGNode(
            name="login_handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.FUNCTION,
            signature="def login_handler(user: str) -> bool:",
            folder_path="src/auth/",
            file_path="src/auth/login.py",
        )
        graph.add_node(node)

        mock = _mock_serena(
            files=["src/auth/login.py"],
            symbols={"src/auth/login.py": ["handle_login", "validate_creds"]},
        )
        validator = SerenaValidator(serena_client=mock)
        validator.encode(graph)

        report = graph.metadata["validation_report"]
        # login_handler is not in the actual symbols
        assert len(report["signature_mismatches"]) >= 1
        mm = report["signature_mismatches"][0]
        assert mm["file_path"] == "src/auth/login.py"
        assert mm["node_name"] == "login_handler"

    def test_matching_symbols_no_mismatch(self) -> None:
        graph = RPGGraph()
        node = RPGNode(
            name="login_handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.FUNCTION,
            signature="def login_handler(user: str) -> bool:",
            folder_path="src/auth/",
            file_path="src/auth/login.py",
        )
        graph.add_node(node)

        mock = _mock_serena(
            files=["src/auth/login.py"],
            symbols={"src/auth/login.py": ["login_handler", "validate_creds"]},
        )
        validator = SerenaValidator(serena_client=mock)
        validator.encode(graph)

        report = graph.metadata["validation_report"]
        assert len(report["signature_mismatches"]) == 0
