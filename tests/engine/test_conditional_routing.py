"""Tests for Epic 1: Structured Tool Output + N-Way Conditional Routing.

Covers:
- ToolHandler JSON stdout parsing (parse_json_output=true/false)
- DiamondNWayBranching validation rule (accepts N-way, rejects missing conditions)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from cobuilder.engine.graph import Edge, Graph, Node
from cobuilder.engine.handlers.tool import ToolHandler
from cobuilder.engine.outcome import OutcomeStatus
from cobuilder.engine.validation import Severity
from cobuilder.engine.validation.advanced_rules import DiamondNWayBranching
from tests.engine.validation.conftest import make_edge, make_graph, make_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_node(node_id: str, command: str = "echo hi", **attrs) -> Node:
    """Create a parallelogram (tool) node."""
    return Node(
        id=node_id,
        shape="parallelogram",
        label=node_id,
        attrs={"shape": "parallelogram", "tool_command": command, **attrs},
    )


def _make_handler_request(node: Node, run_dir: str = "/tmp"):
    """Create a minimal HandlerRequest for the given node."""
    from cobuilder.engine.context import PipelineContext
    from cobuilder.engine.handlers.base import HandlerRequest

    ctx = PipelineContext({})
    return HandlerRequest(node=node, context=ctx, run_dir=run_dir)


def _fake_subprocess_result(stdout: str, stderr: str = "", returncode: int = 0):
    """Return a mock CompletedProcess-like object."""
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


# ---------------------------------------------------------------------------
# 1.1 — ToolHandler JSON output parsing
# ---------------------------------------------------------------------------

class TestToolJsonParse:

    def test_tool_json_parse_success(self):
        """JSON stdout with parse_json_output=true → individual keys stored in context."""
        payload = {"status": "ok", "count": 42, "message": "done"}
        node = _make_tool_node("check_node", command="my-tool", parse_json_output="true")
        request = _make_handler_request(node)

        with patch("subprocess.run", return_value=_fake_subprocess_result(json.dumps(payload))):
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        # Raw stdout is always stored
        assert outcome.context_updates["$check_node.stdout"] == json.dumps(payload)
        # Individual keys extracted
        assert outcome.context_updates["$check_node.status"] == "ok"
        assert outcome.context_updates["$check_node.count"] == 42
        assert outcome.context_updates["$check_node.message"] == "done"

    def test_tool_json_parse_disabled(self):
        """parse_json_output=false (default) → no individual key extraction."""
        payload = {"status": "ok", "count": 42}
        node = _make_tool_node("check_node", command="my-tool")
        request = _make_handler_request(node)

        with patch("subprocess.run", return_value=_fake_subprocess_result(json.dumps(payload))):
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        assert outcome.context_updates["$check_node.stdout"] == json.dumps(payload)
        # Individual keys must NOT be present when parse_json_output is false
        assert "$check_node.status" not in outcome.context_updates
        assert "$check_node.count" not in outcome.context_updates

    def test_tool_json_parse_invalid(self):
        """Non-JSON stdout with parse_json_output=true → graceful fallback, raw stdout stored."""
        raw_output = "not json at all"
        node = _make_tool_node("check_node", command="my-tool", parse_json_output="true")
        request = _make_handler_request(node)

        with patch("subprocess.run", return_value=_fake_subprocess_result(raw_output)):
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        # Raw stdout still stored
        assert outcome.context_updates["$check_node.stdout"] == raw_output
        # No extra keys from attempted JSON parse
        extra_keys = [k for k in outcome.context_updates if k not in (
            "$check_node.exit_code", "$check_node.stdout", "$check_node.stderr"
        )]
        assert extra_keys == []

    def test_tool_json_parse_nested(self):
        """Nested JSON values stored as-is under the top-level key."""
        payload = {"result": {"code": 0, "data": [1, 2, 3]}, "ok": True}
        node = _make_tool_node("check_node", command="my-tool", parse_json_output="true")
        request = _make_handler_request(node)

        with patch("subprocess.run", return_value=_fake_subprocess_result(json.dumps(payload))):
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        # Top-level keys extracted; nested dict stored as-is (not further flattened)
        assert outcome.context_updates["$check_node.result"] == {"code": 0, "data": [1, 2, 3]}
        assert outcome.context_updates["$check_node.ok"] is True

    def test_tool_json_parse_json_array_not_extracted(self):
        """JSON array stdout with parse_json_output=true → raw stdout only (not a dict)."""
        payload = [1, 2, 3]
        node = _make_tool_node("check_node", command="my-tool", parse_json_output="true")
        request = _make_handler_request(node)

        with patch("subprocess.run", return_value=_fake_subprocess_result(json.dumps(payload))):
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        assert outcome.context_updates["$check_node.stdout"] == json.dumps(payload)
        # No extra keys — array is not key-extractable
        extra_keys = [k for k in outcome.context_updates if k not in (
            "$check_node.exit_code", "$check_node.stdout", "$check_node.stderr"
        )]
        assert extra_keys == []


# ---------------------------------------------------------------------------
# 1.3 — DiamondNWayBranching validation rule
# ---------------------------------------------------------------------------

class TestDiamondNWayValidation:

    def _make_diamond_graph(self, conditions: list[str | None]) -> Graph:
        """Build a graph with a single diamond node and N outgoing edges.

        Args:
            conditions: List of condition strings for each outgoing edge.
                        Use None to omit the condition (empty string).
        """
        start = make_node("start", shape="Mdiamond")
        diamond = make_node("branch", shape="diamond")
        exits = [make_node(f"exit_{i}", shape="Msquare") for i in range(len(conditions))]

        edges = [make_edge("start", "branch")]
        for i, cond in enumerate(conditions):
            edges.append(make_edge("branch", f"exit_{i}", condition=cond or ""))

        return make_graph(
            nodes=[start, diamond] + exits,
            edges=edges,
        )

    def test_diamond_nway_validation_accepts_two_conditions(self):
        """Validator accepts diamond with exactly 2 conditioned edges (classic pass/fail)."""
        graph = self._make_diamond_graph(["pass", "fail"])
        violations = DiamondNWayBranching().check(graph)
        # Only the warning about missing catch-all — no errors
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert errors == []

    def test_diamond_nway_validation_accepts_three_conditions(self):
        """Validator accepts diamond with 3+ conditioned edges."""
        graph = self._make_diamond_graph(["pass", "fail", "partial"])
        violations = DiamondNWayBranching().check(graph)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert errors == []

    def test_diamond_nway_validation_accepts_with_catchall(self):
        """Validator accepts and emits no warning when catch-all condition=true is present."""
        graph = self._make_diamond_graph(["pass", "fail", "true"])
        violations = DiamondNWayBranching().check(graph)
        assert violations == []

    def test_diamond_validation_rejects_missing_condition(self):
        """Validator rejects a diamond edge with no condition attribute."""
        graph = self._make_diamond_graph(["pass", None])  # second edge has no condition
        violations = DiamondNWayBranching().check(graph)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert errors[0].rule_id == "DiamondNWayBranching"
        assert "condition" in errors[0].message.lower()
        assert errors[0].edge_src == "branch"
        assert errors[0].edge_dst == "exit_1"

    def test_diamond_validation_rejects_too_few_edges(self):
        """Validator rejects diamond with fewer than 2 outgoing edges."""
        start = make_node("start", shape="Mdiamond")
        diamond = make_node("branch", shape="diamond")
        exit_ = make_node("done", shape="Msquare")
        graph = make_graph(
            nodes=[start, diamond, exit_],
            edges=[
                make_edge("start", "branch"),
                make_edge("branch", "done", condition="pass"),
            ],
        )
        violations = DiamondNWayBranching().check(graph)
        errors = [v for v in violations if v.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].rule_id == "DiamondNWayBranching"
        assert errors[0].node_id == "branch"

    def test_diamond_validation_warns_no_catchall(self):
        """Validator emits WARNING when no catch-all condition=true edge is present."""
        graph = self._make_diamond_graph(["pass", "fail"])
        violations = DiamondNWayBranching().check(graph)
        warnings = [v for v in violations if v.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert warnings[0].rule_id == "DiamondNWayBranching"
        assert "catch-all" in warnings[0].message.lower() or "true" in warnings[0].message.lower()

    def test_non_diamond_nodes_not_checked(self):
        """Non-diamond shapes (box, hexagon, etc.) are not subject to this rule."""
        start = make_node("start", shape="Mdiamond")
        box = make_node("work", shape="box")
        exit_ = make_node("done", shape="Msquare")
        graph = make_graph(
            nodes=[start, box, exit_],
            edges=[make_edge("start", "work"), make_edge("work", "done")],
        )
        violations = DiamondNWayBranching().check(graph)
        assert violations == []


# ---------------------------------------------------------------------------
# 1.5 — ToolHandler working_dir attribute
# ---------------------------------------------------------------------------

class TestToolWorkingDir:

    def test_tool_working_dir_default_uses_run_dir(self):
        """Default (no working_dir attr) → cwd is request.run_dir."""
        node = _make_tool_node("check_node", command="echo hi")
        request = _make_handler_request(node, run_dir="/my/run/dir")

        with patch("subprocess.run", return_value=_fake_subprocess_result("ok")) as mock_run:
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        # subprocess.run should have been called with cwd=/my/run/dir
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("cwd") == "/my/run/dir"

    def test_tool_working_dir_explicit_run_dir(self):
        """working_dir='run_dir' explicitly → same as default, uses request.run_dir."""
        node = _make_tool_node("check_node", command="echo hi", working_dir="run_dir")
        request = _make_handler_request(node, run_dir="/my/run/dir")

        with patch("subprocess.run", return_value=_fake_subprocess_result("ok")) as mock_run:
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("cwd") == "/my/run/dir"

    def test_tool_working_dir_target_dir_from_graph(self):
        """working_dir='target_dir' with $graph in context → uses graph target_dir."""
        from cobuilder.engine.context import PipelineContext
        from cobuilder.engine.handlers.base import HandlerRequest
        from cobuilder.engine.graph import Graph

        node = _make_tool_node("deploy", command="make deploy", working_dir="target_dir")

        # Create a mock graph with target_dir in attrs
        graph = Graph(name="test", attrs={"target_dir": "/impl/repo"})
        ctx = PipelineContext({"$graph": graph})
        request = HandlerRequest(node=node, context=ctx, run_dir="/my/run/dir")

        with patch("subprocess.run", return_value=_fake_subprocess_result("deployed")) as mock_run:
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("cwd") == "/impl/repo"

    def test_tool_working_dir_target_dir_from_context_key(self):
        """working_dir='target_dir' with $target_dir in context (no $graph) → uses context key."""
        from cobuilder.engine.context import PipelineContext
        from cobuilder.engine.handlers.base import HandlerRequest

        node = _make_tool_node("deploy", command="make deploy", working_dir="target_dir")

        ctx = PipelineContext({"$target_dir": "/fallback/repo"})
        request = HandlerRequest(node=node, context=ctx, run_dir="/my/run/dir")

        with patch("subprocess.run", return_value=_fake_subprocess_result("deployed")) as mock_run:
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("cwd") == "/fallback/repo"

    def test_tool_working_dir_target_dir_fallback_to_run_dir(self):
        """working_dir='target_dir' but no target_dir anywhere → falls back to run_dir with warning."""
        node = _make_tool_node("deploy", command="make deploy", working_dir="target_dir")
        request = _make_handler_request(node, run_dir="/my/run/dir")

        with patch("subprocess.run", return_value=_fake_subprocess_result("ok")) as mock_run:
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        mock_run.assert_called_once()
        # Falls back to run_dir when target_dir is not available
        assert mock_run.call_args.kwargs.get("cwd") == "/my/run/dir"

    def test_tool_working_dir_invalid_value_defaults_to_run_dir(self):
        """Invalid working_dir value → Node property normalizes to 'run_dir'."""
        node = _make_tool_node("check_node", command="echo hi", working_dir="bogus")
        assert node.working_dir == "run_dir"  # Node property normalizes
        request = _make_handler_request(node, run_dir="/my/run/dir")

        with patch("subprocess.run", return_value=_fake_subprocess_result("ok")) as mock_run:
            import asyncio
            outcome = asyncio.get_event_loop().run_until_complete(
                ToolHandler().execute(request)
            )

        assert outcome.status == OutcomeStatus.SUCCESS
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("cwd") == "/my/run/dir"
