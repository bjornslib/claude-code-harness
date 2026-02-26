"""Unit tests for PromptTemplate (Jinja2-based prompt management)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cobuilder.repomap.llm.exceptions import TemplateError
from cobuilder.repomap.llm.prompt_templates import PromptTemplate


# Path to the built-in templates shipped with zerorepo.llm
_BUILTIN_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "zerorepo" / "llm" / "templates"


class TestPromptTemplateInit:
    """Tests for PromptTemplate initialisation."""

    def test_default_template_dir(self) -> None:
        """Default constructor uses the built-in templates directory."""
        pt = PromptTemplate()
        # Should not raise and should find at least one template
        assert len(pt.list_templates()) > 0

    def test_custom_template_dir(self, tmp_path: Path) -> None:
        """Constructor accepts a custom template directory."""
        (tmp_path / "hello.jinja2").write_text("Hello {{ name }}!")
        pt = PromptTemplate(template_dir=tmp_path)
        assert "hello" in pt.list_templates()

    def test_nonexistent_dir_raises_template_error(self, tmp_path: Path) -> None:
        """Passing a nonexistent directory raises TemplateError."""
        bad_dir = tmp_path / "does_not_exist"
        with pytest.raises(TemplateError, match="does not exist"):
            PromptTemplate(template_dir=bad_dir)


class TestPromptTemplateRender:
    """Tests for the render method."""

    def test_render_feature_extraction(self) -> None:
        """Render the built-in feature_extraction template."""
        pt = PromptTemplate()
        result = pt.render("feature_extraction", spec_text="Build a login page")
        assert "Build a login page" in result
        assert "feature" in result.lower()

    def test_render_function_generation_minimal(self) -> None:
        """Render function_generation with required variables only."""
        pt = PromptTemplate()
        result = pt.render(
            "function_generation",
            signature="def add(a: int, b: int) -> int",
            docstring="Add two integers.",
        )
        assert "def add(a: int, b: int) -> int" in result
        assert "Add two integers." in result

    def test_render_function_generation_with_optionals(self) -> None:
        """Render function_generation with optional dependencies and context."""
        pt = PromptTemplate()
        result = pt.render(
            "function_generation",
            signature="def process(data: list) -> dict",
            docstring="Process data.",
            dependencies=["numpy", "pandas"],
            context="Part of the data pipeline",
        )
        assert "numpy" in result
        assert "pandas" in result
        assert "Part of the data pipeline" in result

    def test_render_module_planning(self) -> None:
        """Render the module_planning template."""
        pt = PromptTemplate()
        result = pt.render(
            "module_planning",
            project_name="ZeroRepo",
            features=[
                {"name": "Auth", "description": "User authentication"},
                {"name": "API", "description": "REST API layer"},
            ],
        )
        assert "ZeroRepo" in result
        assert "Auth" in result
        assert "API" in result

    def test_render_missing_template_raises(self) -> None:
        """Rendering a template that doesn't exist raises TemplateError."""
        pt = PromptTemplate()
        with pytest.raises(TemplateError, match="not found"):
            pt.render("nonexistent_template", foo="bar")

    def test_render_missing_variable_raises(self) -> None:
        """Missing required variable raises TemplateError (StrictUndefined)."""
        pt = PromptTemplate()
        # feature_extraction requires spec_text
        with pytest.raises(TemplateError, match="Error rendering"):
            pt.render("feature_extraction")  # missing spec_text

    def test_render_custom_template(self, tmp_path: Path) -> None:
        """Render a custom template from a custom directory."""
        (tmp_path / "greet.jinja2").write_text("Hello, {{ name }}! You are {{ role }}.")
        pt = PromptTemplate(template_dir=tmp_path)
        result = pt.render("greet", name="Alice", role="developer")
        assert result == "Hello, Alice! You are developer."

    def test_render_returns_string(self) -> None:
        """Render always returns a string."""
        pt = PromptTemplate()
        result = pt.render("feature_extraction", spec_text="test")
        assert isinstance(result, str)

    def test_render_preserves_multiline(self) -> None:
        """Rendered output preserves multiline content."""
        pt = PromptTemplate()
        spec = "Line 1\nLine 2\nLine 3"
        result = pt.render("feature_extraction", spec_text=spec)
        assert "Line 1\nLine 2\nLine 3" in result


class TestPromptTemplateListTemplates:
    """Tests for the list_templates method."""

    def test_builtin_templates_listed(self) -> None:
        """Built-in templates include the known set."""
        pt = PromptTemplate()
        templates = pt.list_templates()
        assert "feature_extraction" in templates
        assert "function_generation" in templates
        assert "module_planning" in templates

    def test_returns_names_without_extension(self) -> None:
        """Template names don't include .jinja2 extension."""
        pt = PromptTemplate()
        for name in pt.list_templates():
            assert not name.endswith(".jinja2")

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        """Empty template directory returns empty list."""
        pt = PromptTemplate(template_dir=tmp_path)
        assert pt.list_templates() == []

    def test_non_jinja2_files_excluded(self, tmp_path: Path) -> None:
        """Non-.jinja2 files are not listed."""
        (tmp_path / "readme.txt").write_text("not a template")
        (tmp_path / "config.json").write_text("{}")
        (tmp_path / "real.jinja2").write_text("{{ x }}")
        pt = PromptTemplate(template_dir=tmp_path)
        templates = pt.list_templates()
        assert templates == ["real"]

    def test_multiple_custom_templates(self, tmp_path: Path) -> None:
        """Multiple jinja2 files are all listed."""
        for name in ["alpha", "beta", "gamma"]:
            (tmp_path / f"{name}.jinja2").write_text(f"Template {name}")
        pt = PromptTemplate(template_dir=tmp_path)
        templates = sorted(pt.list_templates())
        assert templates == ["alpha", "beta", "gamma"]
