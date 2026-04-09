"""Tests for cobuilder.engine.handlers.planner (Epic 3).

All SDK calls are mocked — no real LLM calls are made.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cobuilder.engine.graph import Node
from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.handlers.planner import (
    PlannerHandler,
    _FALLBACK_TOOL_SETS,
    _infer_tool_set,
    _load_tool_sets,
)
from cobuilder.engine.outcome import OutcomeStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_node(
    node_id: str = "test_node",
    shape: str = "box",
    label: str = "",
    **attrs: Any,
) -> Node:
    """Construct a minimal Node for testing."""
    return Node(
        id=node_id,
        shape=shape,
        label=label or node_id,
        attrs={"shape": shape, **attrs},
    )


def make_request(node: Node, run_dir: str = "") -> HandlerRequest:
    """Construct a minimal HandlerRequest wrapping *node*."""
    ctx = MagicMock()
    ctx.snapshot.return_value = {}
    return HandlerRequest(
        node=node,
        context=ctx,
        run_dir=run_dir,
        pipeline_id="test-pipeline",
    )


async def _make_async_gen(*messages: Any):
    """Async generator yielding *messages* one by one (for SDK mock)."""
    for m in messages:
        yield m


# ---------------------------------------------------------------------------
# Handler protocol compliance
# ---------------------------------------------------------------------------

class TestPlannerHandlerProtocol:
    def test_satisfies_handler_protocol(self) -> None:
        assert isinstance(PlannerHandler(), Handler)


# ---------------------------------------------------------------------------
# Tool set resolution
# ---------------------------------------------------------------------------

class TestPlannerResearchDispatch:
    """test_planner_research_dispatch — explicit tool_set='research' resolves correctly."""

    def test_resolves_research_tools(self, tmp_path: Path) -> None:
        tool_sets = _load_tool_sets(tmp_path / "nonexistent.yaml")  # will use fallback
        assert "mcp__context7__query-docs" in tool_sets["research"]
        assert "mcp__perplexity__perplexity_research" in tool_sets["research"]
        assert "Bash" in tool_sets["research"]

    @pytest.mark.asyncio
    async def test_dispatch_uses_research_tools(self, tmp_path: Path) -> None:
        node = make_node("my_research", shape="box", tool_set="research")
        request = make_request(node, run_dir=str(tmp_path))

        handler = PlannerHandler()
        # Reset class-level cache to force fresh load using fallback
        PlannerHandler._tool_sets = None

        captured_options: list[Any] = []

        async def fake_query(prompt: str, options: Any = None):
            captured_options.append(options)
            return
            yield  # make it an async generator

        with patch("claude_code_sdk.query", new=fake_query):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS
        assert captured_options
        used_tools = captured_options[0].allowed_tools
        assert "mcp__context7__query-docs" in used_tools
        assert "mcp__perplexity__perplexity_research" in used_tools


class TestPlannerRefineDispatch:
    """test_planner_refine_dispatch — tool_set='refine' restricts to no web research."""

    def test_refine_excludes_web_research(self, tmp_path: Path) -> None:
        tool_sets = _load_tool_sets(tmp_path / "nonexistent.yaml")
        refine_tools = tool_sets["refine"]
        # Should NOT have open-web research
        assert "mcp__perplexity__perplexity_research" not in refine_tools
        assert "mcp__context7__query-docs" not in refine_tools
        # Should still have memory and editing
        assert "Read" in refine_tools
        assert "Edit" in refine_tools
        assert "mcp__hindsight__retain" in refine_tools

    @pytest.mark.asyncio
    async def test_dispatch_uses_refine_tools(self, tmp_path: Path) -> None:
        node = make_node("my_refine", shape="note", tool_set="refine")
        request = make_request(node, run_dir=str(tmp_path))

        handler = PlannerHandler()
        PlannerHandler._tool_sets = None

        captured_options: list[Any] = []

        async def fake_query(prompt: str, options: Any = None):
            captured_options.append(options)
            return
            yield

        with patch("claude_code_sdk.query", new=fake_query):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS
        used_tools = captured_options[0].allowed_tools
        assert "mcp__perplexity__perplexity_research" not in used_tools
        assert "Edit" in used_tools


class TestPlannerCustomToolSet:
    """test_planner_custom_tool_set — tool_set='plan' resolves plan-specific tools."""

    def test_plan_tools_are_read_only(self, tmp_path: Path) -> None:
        tool_sets = _load_tool_sets(tmp_path / "nonexistent.yaml")
        plan_tools = tool_sets["plan"]
        assert "Read" in plan_tools
        assert "Glob" in plan_tools
        assert "Grep" in plan_tools
        # plan is read-only — no edit/write
        assert "Edit" not in plan_tools
        assert "Write" not in plan_tools
        assert "Bash" not in plan_tools


# ---------------------------------------------------------------------------
# Tool set inference from shape
# ---------------------------------------------------------------------------

class TestInferToolSet:
    """test_planner_infer_tool_set_tab and test_planner_infer_tool_set_note."""

    def test_tab_shape_infers_research(self) -> None:
        node = make_node("n1", shape="tab")
        assert _infer_tool_set(node) == "research"

    def test_note_shape_infers_refine(self) -> None:
        node = make_node("n2", shape="note")
        assert _infer_tool_set(node) == "refine"

    def test_box_shape_infers_full(self) -> None:
        node = make_node("n3", shape="box")
        assert _infer_tool_set(node) == "full"

    def test_unknown_shape_infers_full(self) -> None:
        node = make_node("n4", shape="hexagon")
        assert _infer_tool_set(node) == "full"

    @pytest.mark.asyncio
    async def test_tab_node_without_explicit_tool_set_uses_research(self, tmp_path: Path) -> None:
        """Tab node without explicit tool_set → infers 'research' tools."""
        node = make_node("research_node", shape="tab")  # no tool_set attr
        request = make_request(node, run_dir=str(tmp_path))

        handler = PlannerHandler()
        PlannerHandler._tool_sets = None

        captured_options: list[Any] = []

        async def fake_query(prompt: str, options: Any = None):
            captured_options.append(options)
            return
            yield

        with patch("claude_code_sdk.query", new=fake_query):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS
        used_tools = captured_options[0].allowed_tools
        assert "mcp__context7__query-docs" in used_tools

    @pytest.mark.asyncio
    async def test_note_node_without_explicit_tool_set_uses_refine(self, tmp_path: Path) -> None:
        """Note node without explicit tool_set → infers 'refine' tools."""
        node = make_node("refine_node", shape="note")  # no tool_set attr
        request = make_request(node, run_dir=str(tmp_path))

        handler = PlannerHandler()
        PlannerHandler._tool_sets = None

        captured_options: list[Any] = []

        async def fake_query(prompt: str, options: Any = None):
            captured_options.append(options)
            return
            yield

        with patch("claude_code_sdk.query", new=fake_query):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS
        used_tools = captured_options[0].allowed_tools
        assert "mcp__perplexity__perplexity_research" not in used_tools
        assert "Edit" in used_tools


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

class TestToolSetsLoadedFromYaml:
    """test_tool_sets_loaded_from_yaml — .cobuilder/tool-sets.yaml parsed correctly."""

    def test_loads_custom_yaml(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            custom_set:
              description: "test set"
              tools:
                - Read
                - Grep
                - mcp__custom__tool
        """)
        yaml_file = tmp_path / "tool-sets.yaml"
        yaml_file.write_text(yaml_content)

        result = _load_tool_sets(yaml_file)

        assert "custom_set" in result
        assert result["custom_set"] == ["Read", "Grep", "mcp__custom__tool"]

    def test_real_yaml_has_four_named_sets(self) -> None:
        """The actual .cobuilder/tool-sets.yaml has the required four named sets."""
        # Load without explicit path — discovers via _find_cobuilder_root()
        tool_sets = _load_tool_sets()
        assert "research" in tool_sets
        assert "refine" in tool_sets
        assert "plan" in tool_sets
        assert "full" in tool_sets

    def test_yaml_research_set_matches_run_research_tools(self) -> None:
        """YAML research set contains same tools as legacy run_research.py."""
        tool_sets = _load_tool_sets()
        research_tools = set(tool_sets["research"])
        required = {
            "mcp__context7__resolve-library-id",
            "mcp__context7__query-docs",
            "mcp__perplexity__perplexity_ask",
            "mcp__perplexity__perplexity_research",
            "mcp__hindsight__reflect",
            "mcp__hindsight__retain",
            "mcp__hindsight__recall",
            "mcp__serena__find_symbol",
            "mcp__serena__find_file",
        }
        assert required.issubset(research_tools), (
            f"Missing tools in research set: {required - research_tools}"
        )


class TestToolSetsMissingYamlFallback:
    """test_tool_sets_missing_yaml_fallback — missing YAML → hardcoded fallback used."""

    def test_nonexistent_path_returns_fallback(self, tmp_path: Path) -> None:
        result = _load_tool_sets(tmp_path / "does_not_exist.yaml")
        # Should return something equivalent to the fallback
        assert "research" in result
        assert "refine" in result
        assert "plan" in result
        assert "full" in result
        # Values should match fallback
        assert result["research"] == _FALLBACK_TOOL_SETS["research"]

    def test_fallback_has_mcp_tools_in_research(self) -> None:
        fallback = dict(_FALLBACK_TOOL_SETS)
        assert "mcp__context7__query-docs" in fallback["research"]
        assert "mcp__perplexity__perplexity_research" in fallback["research"]

    def test_invalid_yaml_returns_fallback(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "tool-sets.yaml"
        bad_yaml.write_text("!!: [invalid: yaml: {{{")

        result = _load_tool_sets(bad_yaml)
        # Should fall back gracefully
        assert "research" in result or result == {}  # Either fallback or empty is ok

    def test_yaml_with_no_tools_key_skips_entry(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            good_set:
              description: "has tools"
              tools:
                - Read
            bad_set:
              description: "no tools key"
        """)
        yaml_file = tmp_path / "tool-sets.yaml"
        yaml_file.write_text(yaml_content)

        result = _load_tool_sets(yaml_file)
        assert "good_set" in result
        assert result["good_set"] == ["Read"]
        assert "bad_set" not in result


# ---------------------------------------------------------------------------
# Evidence file writing
# ---------------------------------------------------------------------------

class TestEvidenceFileWriting:
    @pytest.mark.asyncio
    async def test_writes_evidence_json(self, tmp_path: Path) -> None:
        node = make_node("ev_node", shape="tab", tool_set="research")
        request = make_request(node, run_dir=str(tmp_path))

        handler = PlannerHandler()
        PlannerHandler._tool_sets = None

        async def fake_query(prompt: str, options: Any = None):
            return
            yield

        with patch("claude_code_sdk.query", new=fake_query):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS

        evidence_path = tmp_path / "nodes" / "ev_node" / "evidence.json"
        assert evidence_path.exists(), f"Evidence file not found at {evidence_path}"

        data = json.loads(evidence_path.read_text())
        assert data["node_id"] == "ev_node"
        assert data["status"] == "success"
        assert "tools_used" in data


# ---------------------------------------------------------------------------
# Schema: acceptance-test-writer as worker_type
# ---------------------------------------------------------------------------

class TestATWriterAsWorkerType:
    """test_at_writer_as_worker_type — codergen node with worker_type='acceptance-test-writer' is valid."""

    def test_at_writer_in_valid_worker_types(self) -> None:
        from cobuilder.engine.schema import VALID_WORKER_TYPES
        assert "acceptance-test-writer" in VALID_WORKER_TYPES

    def test_at_writer_not_in_valid_handlers(self) -> None:
        from cobuilder.engine.schema import VALID_HANDLERS
        assert "acceptance-test-writer" not in VALID_HANDLERS

    def test_codergen_node_with_at_writer_worker_type(self) -> None:
        """A box (codergen) node with worker_type='acceptance-test-writer' should be valid."""
        from cobuilder.engine.schema import VALID_WORKER_TYPES
        node = make_node(
            "write_tests",
            shape="box",
            handler="codergen",
            worker_type="acceptance-test-writer",
            bead_id="AT-001",
            sd_path="docs/sds/example.md",
        )
        assert node.worker_type == "acceptance-test-writer"
        assert node.worker_type in VALID_WORKER_TYPES


# ---------------------------------------------------------------------------
# Registry: tab and note shapes use PlannerHandler
# ---------------------------------------------------------------------------

class TestRegistryUsagesPlannerHandler:
    def test_tab_shape_dispatches_to_planner(self) -> None:
        from cobuilder.engine.handlers.registry import HandlerRegistry
        registry = HandlerRegistry.default()
        node = make_node("n", shape="tab")
        handler = registry.dispatch(node)
        assert isinstance(handler, PlannerHandler)

    def test_note_shape_dispatches_to_planner(self) -> None:
        from cobuilder.engine.handlers.registry import HandlerRegistry
        registry = HandlerRegistry.default()
        node = make_node("n", shape="note")
        handler = registry.dispatch(node)
        assert isinstance(handler, PlannerHandler)
