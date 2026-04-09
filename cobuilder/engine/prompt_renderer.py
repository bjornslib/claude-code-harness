"""PromptRenderer — resolves and renders node-level Jinja2 prompt templates.

Resolution order (first non-empty wins):
  1. ``node.prompt_template`` → load ``.cobuilder/prompts/<name>.j2``,
     render with template variables.
  2. ``node.prompt`` → return literal string.
  3. ``""`` (empty fallback).

Template variables available inside ``.j2`` files::

    node.*      — all node attributes (node.id, node.prd_ref, etc.)
    context.*   — pipeline context snapshot (dict-like namespace)
    vars.*      — explicit prompt_vars from node attribute (JSON parsed)
    timestamp   — current UTC ISO-8601 timestamp
    + all node.attrs keys as top-level variables for convenience

Jinja2 is an optional dependency; if it is not installed the renderer
gracefully degrades to returning ``node.prompt`` for every call.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cobuilder.engine.graph import Node

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Root-directory discovery
# ---------------------------------------------------------------------------

def _find_cobuilder_root() -> Path | None:
    """Walk up from this file's location to find the repo root.

    Looks for a directory that contains both ``cobuilder/`` and
    ``.cobuilder/`` as children — that is the cobuilder harness root.

    Returns ``None`` if not found.
    """
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "cobuilder").is_dir() and (parent / ".cobuilder").is_dir():
            return parent
    return None


# ---------------------------------------------------------------------------
# PromptRenderer
# ---------------------------------------------------------------------------

class PromptRenderer:
    """Resolves and renders node-level Jinja2 prompt templates.

    Args:
        prompts_dir: Directory containing ``.j2`` template files.  When
            ``None`` (default) the renderer auto-discovers the cobuilder root
            and uses ``<root>/.cobuilder/prompts/``.

    Usage::

        renderer = PromptRenderer()
        prompt = renderer.render(node, context, run_dir) or f"Execute: {node.id}"
    """

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        if prompts_dir is not None:
            self._prompts_dir: Path | None = Path(prompts_dir)
        else:
            root = _find_cobuilder_root()
            if root is not None:
                self._prompts_dir = root / ".cobuilder" / "prompts"
            else:
                self._prompts_dir = None

        # Lazy-initialised Jinja2 Environment (None when jinja2 is absent)
        self._env: Any = None
        self._jinja2_available: bool | None = None  # None means "not yet checked"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_env(self) -> Any | None:
        """Return the Jinja2 Environment, creating it lazily.

        Returns ``None`` if jinja2 is not importable or if the prompts
        directory does not exist.
        """
        if self._jinja2_available is False:
            return None

        if self._env is not None:
            return self._env

        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore[import]
        except ImportError:
            logger.warning(
                "jinja2 is not installed; PromptRenderer will fall back to node.prompt"
            )
            self._jinja2_available = False
            return None

        if self._prompts_dir is None or not self._prompts_dir.is_dir():
            if self._prompts_dir is not None:
                logger.debug(
                    "Prompts directory not found: %s; PromptRenderer will fall back "
                    "to node.prompt",
                    self._prompts_dir,
                )
            self._jinja2_available = False
            return None

        self._jinja2_available = True
        self._env = Environment(
            loader=FileSystemLoader(str(self._prompts_dir)),
            autoescape=select_autoescape([]),  # Plain text prompts, no HTML escaping
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Register the same slugify filter used by the template instantiator
        import re

        def _slugify(value: str) -> str:
            v = str(value).lower()
            v = re.sub(r"[^a-z0-9]+", "_", v)
            return v.strip("_") or "unnamed"

        self._env.filters["slugify"] = _slugify
        return self._env

    def _build_context(
        self,
        node: "Node",
        pipeline_context: Any | None,
        run_dir: str | Path | None,
    ) -> dict[str, Any]:
        """Build the template variable namespace.

        ``pipeline_context`` may be a plain ``dict`` or a ``PipelineContext``
        instance (which exposes a ``snapshot()`` method returning a dict).
        """
        # Normalise pipeline_context to a plain dict
        if pipeline_context is None:
            ctx_dict: dict[str, Any] = {}
        elif hasattr(pipeline_context, "snapshot"):
            ctx_dict = pipeline_context.snapshot()
        elif isinstance(pipeline_context, dict):
            ctx_dict = pipeline_context
        else:
            ctx_dict = {}

        # Convenience: expose every raw attr key at the top level
        top_level = dict(node.attrs)

        # Structured namespaces override top-level keys with richer objects.
        # Also inject node.id and node.label as top-level variables so templates
        # can use {{ node_id }} and {{ label }} without going through node.*.
        ctx: dict[str, Any] = {
            **top_level,
            "node_id": node.id,
            "label": node.label,
            "node": node,
            "context": ctx_dict,
            "vars": node.prompt_vars,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_dir": str(run_dir) if run_dir else "",
        }
        return ctx

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        node: "Node",
        pipeline_context: dict[str, Any] | None = None,
        run_dir: str | Path | None = None,
    ) -> str:
        """Resolve and render a prompt for *node*.

        Resolution order:
          1. ``node.prompt_template`` → template file rendered with variables.
          2. ``node.prompt`` → returned as-is.
          3. ``""`` (empty string).

        Args:
            node: The pipeline node to render a prompt for.
            pipeline_context: Current pipeline context snapshot (may be None).
            run_dir: Pipeline run directory (used as a template variable).

        Returns:
            Rendered prompt string, or ``""`` if no prompt source is configured.
        """
        template_name = node.prompt_template
        if template_name:
            result = self._render_template(template_name, node, pipeline_context, run_dir)
            if result is not None:
                return result
            # Fall through to node.prompt on template error

        return node.prompt

    def _render_template(
        self,
        template_name: str,
        node: "Node",
        pipeline_context: dict[str, Any] | None,
        run_dir: str | Path | None,
    ) -> str | None:
        """Render *template_name* and return the result.

        Returns ``None`` on any error so the caller can fall back to
        ``node.prompt``.
        """
        env = self._get_env()
        if env is None:
            return None

        # Ensure the template name ends with .j2
        if not template_name.endswith(".j2"):
            template_name = f"{template_name}.j2"

        # Check file exists before asking Jinja2 (friendlier warning message)
        assert self._prompts_dir is not None
        template_path = self._prompts_dir / template_name
        if not template_path.exists():
            logger.warning(
                "Prompt template file not found: %s; falling back to node.prompt "
                "(node_id=%s)",
                template_path,
                node.id,
            )
            return None

        try:
            tmpl = env.get_template(template_name)
            ctx = self._build_context(node, pipeline_context, run_dir)
            return tmpl.render(**ctx)
        except Exception as exc:
            logger.warning(
                "Failed to render prompt template '%s' for node '%s': %s; "
                "falling back to node.prompt",
                template_name,
                node.id,
                exc,
            )
            return None
