"""Prompt template management using Jinja2 for the LLM Gateway."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from zerorepo.llm.exceptions import TemplateError

# Default template directory is the ``templates/`` sub-package shipped with
# this module.
_DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"


class PromptTemplate:
    """Render prompt templates stored as Jinja2 files.

    The class lazily loads templates from a configurable directory, defaulting
    to the built-in ``templates/`` directory shipped with the ``zerorepo.llm``
    package.

    Example::

        pt = PromptTemplate()
        prompt = pt.render("feature_extraction", spec_text="Build a login page")
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialise the Jinja2 environment.

        Args:
            template_dir: Directory containing ``*.jinja2`` template files.
                Defaults to the built-in ``templates/`` directory.
        """
        self._template_dir = template_dir or _DEFAULT_TEMPLATE_DIR
        if not self._template_dir.is_dir():
            raise TemplateError(
                f"Template directory does not exist: {self._template_dir}"
            )
        self._env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **variables: Any) -> str:
        """Render a template with the given variables.

        Args:
            template_name: Name of the template **without** the ``.jinja2``
                extension (e.g. ``"feature_extraction"``).
            **variables: Template variables passed to Jinja2.

        Returns:
            The rendered prompt string.

        Raises:
            TemplateError: If the template cannot be found or a required
                variable is missing.
        """
        full_name = f"{template_name}.jinja2"
        try:
            template = self._env.get_template(full_name)
        except TemplateNotFound:
            raise TemplateError(
                f"Template '{full_name}' not found in {self._template_dir}"
            ) from None

        try:
            return template.render(**variables)
        except Exception as exc:
            raise TemplateError(
                f"Error rendering template '{full_name}': {exc}"
            ) from exc

    def list_templates(self) -> list[str]:
        """Return the names (without ``.jinja2``) of all available templates."""
        return [
            t.removesuffix(".jinja2")
            for t in self._env.list_templates()
            if t.endswith(".jinja2")
        ]
