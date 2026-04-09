"""Tests for cobuilder.engine.prompt_renderer.PromptRenderer (Epic 2).

All tests are self-contained: they create temporary directories / template
files rather than depending on files that may or may not exist on disk.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from cobuilder.engine.graph import Node
from cobuilder.engine.prompt_renderer import PromptRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_node(
    node_id: str = "test_node",
    shape: str = "box",
    label: str = "",
    **attrs,
) -> Node:
    """Construct a minimal Node for testing."""
    return Node(
        id=node_id,
        shape=shape,
        label=label or node_id,
        attrs={"shape": shape, **attrs},
    )


def renderer_with_dir(tmp_path: Path) -> PromptRenderer:
    """Return a PromptRenderer pointed at *tmp_path* as the prompts directory."""
    return PromptRenderer(prompts_dir=tmp_path)


# ---------------------------------------------------------------------------
# 2.6 — Basic rendering tests
# ---------------------------------------------------------------------------

class TestRenderWithTemplate:
    """test_render_with_template — template file exists → rendered output."""

    def test_renders_simple_template(self, tmp_path: Path) -> None:
        (tmp_path / "hello.j2").write_text("Hello, {{ node_id }}!")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(node_id="my_node", prompt_template="hello")
        result = renderer.render(node)
        assert result == "Hello, my_node!"

    def test_renders_template_with_j2_suffix(self, tmp_path: Path) -> None:
        """prompt_template value may already end in .j2 — should not double-add."""
        (tmp_path / "task.j2").write_text("Task: {{ node_id }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(node_id="impl", prompt_template="task.j2")
        result = renderer.render(node)
        assert result == "Task: impl"


class TestRenderFallbackToPrompt:
    """test_render_fallback_to_prompt — no template set → literal node.prompt."""

    def test_returns_node_prompt_when_no_template(self, tmp_path: Path) -> None:
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt="Do the thing")
        result = renderer.render(node)
        assert result == "Do the thing"

    def test_returns_empty_when_neither_set(self, tmp_path: Path) -> None:
        renderer = renderer_with_dir(tmp_path)
        node = make_node()  # no prompt, no prompt_template
        result = renderer.render(node)
        assert result == ""


class TestRenderFallbackToEmpty:
    """test_render_fallback_to_empty — neither template nor prompt → empty string."""

    def test_empty_string_fallback(self, tmp_path: Path) -> None:
        renderer = renderer_with_dir(tmp_path)
        node = make_node(node_id="bare")
        assert renderer.render(node) == ""

    def test_missing_prompts_dir_falls_back_to_prompt(self, tmp_path: Path) -> None:
        missing_dir = tmp_path / "nonexistent"
        renderer = PromptRenderer(prompts_dir=missing_dir)
        node = make_node(prompt="Fallback prompt", prompt_template="something")
        result = renderer.render(node)
        assert result == "Fallback prompt"


class TestTemplateVariables:
    """test_template_variables — node attrs, context, vars all accessible."""

    def test_node_attrs_accessible(self, tmp_path: Path) -> None:
        (tmp_path / "attrs.j2").write_text("{{ node_id }}-{{ prd_ref }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(node_id="n1", prd_ref="PRD-TEST-001", prompt_template="attrs")
        assert renderer.render(node) == "n1-PRD-TEST-001"

    def test_node_object_accessible(self, tmp_path: Path) -> None:
        (tmp_path / "node_obj.j2").write_text("{{ node.id }}/{{ node.shape }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(node_id="n2", shape="box", prompt_template="node_obj")
        assert renderer.render(node) == "n2/box"

    def test_context_dict_accessible(self, tmp_path: Path) -> None:
        (tmp_path / "ctx.j2").write_text("{{ context.my_key }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt_template="ctx")
        result = renderer.render(node, pipeline_context={"my_key": "hello"})
        assert result == "hello"

    def test_pipeline_context_object_snapshot(self, tmp_path: Path) -> None:
        """PipelineContext objects are snapshotted via .snapshot()."""
        (tmp_path / "ctx2.j2").write_text("{{ context.val }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt_template="ctx2")

        class FakeContext:
            def snapshot(self):
                return {"val": "from_snapshot"}

        result = renderer.render(node, pipeline_context=FakeContext())
        assert result == "from_snapshot"

    def test_vars_namespace(self, tmp_path: Path) -> None:
        (tmp_path / "vars_tmpl.j2").write_text("{{ vars.greeting }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(
            prompt_template="vars_tmpl",
            prompt_vars=json.dumps({"greeting": "hi"}),
        )
        result = renderer.render(node)
        assert result == "hi"

    def test_timestamp_available(self, tmp_path: Path) -> None:
        (tmp_path / "ts.j2").write_text("ts={{ timestamp[:4] }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt_template="ts")
        result = renderer.render(node)
        # Should start with "ts=20" (year 2xxx)
        assert result.startswith("ts=20")

    def test_run_dir_available(self, tmp_path: Path) -> None:
        (tmp_path / "rd.j2").write_text("run={{ run_dir }}")
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt_template="rd")
        result = renderer.render(node, run_dir="/some/dir")
        assert result == "run=/some/dir"


# ---------------------------------------------------------------------------
# Node property tests
# ---------------------------------------------------------------------------

class TestNodeProperties:
    """Verify the new Node property accessors added in 2.3."""

    def test_prompt_template_default_empty(self) -> None:
        node = make_node()
        assert node.prompt_template == ""

    def test_prompt_template_set(self) -> None:
        node = make_node(prompt_template="research")
        assert node.prompt_template == "research"

    def test_prompt_vars_default_empty_dict(self) -> None:
        node = make_node()
        assert node.prompt_vars == {}

    def test_prompt_vars_valid_json(self) -> None:
        node = make_node(prompt_vars='{"key": "value", "num": 42}')
        assert node.prompt_vars == {"key": "value", "num": 42}

    def test_prompt_vars_invalid_json_returns_empty(self) -> None:
        node = make_node(prompt_vars="not-json{{{")
        assert node.prompt_vars == {}

    def test_prompt_vars_empty_string_returns_empty(self) -> None:
        node = make_node(prompt_vars="")
        # "{}" is the default so empty string gets parsed as empty dict
        node2 = Node(id="x", shape="box", label="x", attrs={"prompt_vars": ""})
        assert node2.prompt_vars == {}  # empty string → JSONDecodeError → {}


class TestPromptVarsJsonParse:
    """test_prompt_vars_json_parse — valid JSON → dict; invalid JSON → empty dict."""

    def test_valid_json_dict(self) -> None:
        node = make_node(prompt_vars='{"a": 1}')
        assert node.prompt_vars == {"a": 1}

    def test_invalid_json(self) -> None:
        node = make_node(prompt_vars="oops")
        assert node.prompt_vars == {}

    def test_json_array_not_dict(self) -> None:
        """JSON arrays are valid JSON but the property should still return them."""
        node = make_node(prompt_vars='["a","b"]')
        # json.loads returns a list; that's fine — property just returns it
        assert node.prompt_vars == ["a", "b"]


# ---------------------------------------------------------------------------
# Missing template file graceful fallback
# ---------------------------------------------------------------------------

class TestMissingTemplateFile:
    """test_missing_template_file — warns, falls back to node.prompt."""

    def test_falls_back_to_node_prompt(self, tmp_path: Path) -> None:
        renderer = renderer_with_dir(tmp_path)  # dir exists but template does not
        node = make_node(prompt_template="nonexistent", prompt="fallback!")
        result = renderer.render(node)
        assert result == "fallback!"

    def test_falls_back_to_empty_when_no_prompt(self, tmp_path: Path) -> None:
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt_template="nonexistent")
        result = renderer.render(node)
        assert result == ""

    def test_emits_warning(self, tmp_path: Path, caplog) -> None:
        import logging
        renderer = renderer_with_dir(tmp_path)
        node = make_node(prompt_template="nonexistent")
        with caplog.at_level(logging.WARNING, logger="cobuilder.engine.prompt_renderer"):
            renderer.render(node)
        assert any("not found" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Validation rule integration
# ---------------------------------------------------------------------------

class TestValidationAcceptsPromptTemplate:
    """test_validation_accepts_prompt_template — Rule 13 passes with only prompt_template."""

    def test_rule13_accepts_prompt_template(self) -> None:
        from cobuilder.engine.graph import Graph
        from cobuilder.engine.validation.rules import LlmNodesHavePrompts

        # Node with prompt_template but no prompt and no label
        node = Node(
            id="impl",
            shape="box",
            label="",
            attrs={"shape": "box", "prompt_template": "research"},
        )
        graph = Graph(
            name="test",
            nodes={"impl": node},
            edges=[],
        )
        rule = LlmNodesHavePrompts()
        violations = rule.check(graph)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_rule13_warns_when_all_missing(self) -> None:
        from cobuilder.engine.graph import Graph
        from cobuilder.engine.validation.rules import LlmNodesHavePrompts

        node = Node(
            id="impl",
            shape="box",
            label="",
            attrs={"shape": "box"},  # no prompt, no prompt_template, no label
        )
        graph = Graph(name="test", nodes={"impl": node}, edges=[])
        rule = LlmNodesHavePrompts()
        violations = rule.check(graph)
        assert len(violations) == 1
        assert "prompt_template" in violations[0].message


class TestPromptTemplateExistsRule:
    """Tests for the PromptTemplateExists advanced validation rule."""

    def test_no_violation_when_template_exists(self, tmp_path: Path, monkeypatch) -> None:
        from cobuilder.engine.graph import Graph
        from cobuilder.engine.validation.advanced_rules import PromptTemplateExists

        (tmp_path / "research.j2").write_text("template content")

        monkeypatch.setattr(
            PromptTemplateExists,
            "_find_prompts_dir",
            staticmethod(lambda: tmp_path),
        )

        node = Node(
            id="research_node",
            shape="tab",
            label="Research",
            attrs={"shape": "tab", "prompt_template": "research"},
        )
        graph = Graph(name="test", nodes={"research_node": node}, edges=[])
        rule = PromptTemplateExists()
        violations = rule.check(graph)
        assert violations == []

    def test_warns_when_template_file_missing(self, tmp_path: Path, monkeypatch) -> None:
        from cobuilder.engine.graph import Graph
        from cobuilder.engine.validation.advanced_rules import PromptTemplateExists

        monkeypatch.setattr(
            PromptTemplateExists,
            "_find_prompts_dir",
            staticmethod(lambda: tmp_path),
        )

        node = Node(
            id="n",
            shape="box",
            label="N",
            attrs={"shape": "box", "prompt_template": "missing_template"},
        )
        graph = Graph(name="test", nodes={"n": node}, edges=[])
        rule = PromptTemplateExists()
        violations = rule.check(graph)
        assert len(violations) == 1
        assert "missing_template.j2" in violations[0].message

    def test_no_violation_for_nodes_without_template(self, tmp_path: Path, monkeypatch) -> None:
        from cobuilder.engine.graph import Graph
        from cobuilder.engine.validation.advanced_rules import PromptTemplateExists

        monkeypatch.setattr(
            PromptTemplateExists,
            "_find_prompts_dir",
            staticmethod(lambda: tmp_path),
        )

        node = Node(
            id="plain",
            shape="box",
            label="Plain",
            attrs={"shape": "box", "prompt": "Do work"},
        )
        graph = Graph(name="test", nodes={"plain": node}, edges=[])
        rule = PromptTemplateExists()
        violations = rule.check(graph)
        assert violations == []
