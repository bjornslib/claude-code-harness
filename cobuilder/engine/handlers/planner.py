"""PlannerHandler — unified handler for planning-type nodes (research, refine, plan).

Replaces the previous pattern where tab/note shapes were CodergenHandler aliases.
Configurable via DOT node attributes:
    tool_set        — named set from .cobuilder/tool-sets.yaml
    prompt_template — Jinja2 template name (rendered via PromptRenderer)
    prompt          — literal prompt fallback
    system_prompt   — custom system prompt
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback tool sets (used when YAML is missing)
# ---------------------------------------------------------------------------

_FALLBACK_TOOL_SETS: dict[str, list[str]] = {
    "research": [
        "Bash", "Read", "Edit", "Write", "ToolSearch", "LSP",
        "mcp__context7__resolve-library-id",
        "mcp__context7__query-docs",
        "mcp__perplexity__perplexity_ask",
        "mcp__perplexity__perplexity_reason",
        "mcp__perplexity__perplexity_research",
        "mcp__hindsight__reflect",
        "mcp__hindsight__retain",
        "mcp__hindsight__recall",
        "mcp__serena__activate_project",
        "mcp__serena__check_onboarding_performed",
        "mcp__serena__find_symbol",
        "mcp__serena__search_for_pattern",
        "mcp__serena__get_symbols_overview",
        "mcp__serena__find_referencing_symbols",
        "mcp__serena__find_file",
    ],
    "refine": [
        "Read", "Edit", "Write", "ToolSearch", "LSP",
        "mcp__hindsight__reflect",
        "mcp__hindsight__retain",
        "mcp__hindsight__recall",
        "mcp__perplexity__perplexity_reason",
        "mcp__serena__activate_project",
        "mcp__serena__check_onboarding_performed",
        "mcp__serena__find_symbol",
        "mcp__serena__search_for_pattern",
        "mcp__serena__get_symbols_overview",
        "mcp__serena__find_referencing_symbols",
        "mcp__serena__find_file",
    ],
    "plan": [
        "Read", "ToolSearch", "LSP", "Glob", "Grep",
        "mcp__hindsight__reflect",
        "mcp__hindsight__recall",
        "mcp__perplexity__perplexity_ask",
    ],
    "full": [
        "Bash", "Read", "Edit", "Write", "ToolSearch", "LSP", "Glob", "Grep",
    ],
}


# ---------------------------------------------------------------------------
# Tool set loading
# ---------------------------------------------------------------------------

def _find_cobuilder_root() -> Path | None:
    """Walk up from this file's location to find the repo root.

    Looks for a directory that contains both ``cobuilder/`` and
    ``.cobuilder/`` as children — that is the cobuilder harness root.
    """
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "cobuilder").is_dir() and (parent / ".cobuilder").is_dir():
            return parent
    return None


def _load_tool_sets(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load named tool sets from a YAML file.

    Resolution:
    1. Explicit ``path`` argument (if provided)
    2. ``.cobuilder/tool-sets.yaml`` discovered by traversing up from __file__
    3. Hardcoded fallback dict (``_FALLBACK_TOOL_SETS``)
    4. Empty dict (if yaml is not importable and fallback unreachable)

    Args:
        path: Optional explicit path to the tool-sets YAML file.

    Returns:
        dict mapping set name → list of tool strings.
    """
    yaml_path: Path | None = None

    if path is not None:
        yaml_path = Path(path)
    else:
        root = _find_cobuilder_root()
        if root is not None:
            candidate = root / ".cobuilder" / "tool-sets.yaml"
            if candidate.exists():
                yaml_path = candidate

    if yaml_path is None or not yaml_path.exists():
        logger.debug(
            "tool-sets.yaml not found (path=%s); using hardcoded fallback tool sets",
            yaml_path,
        )
        return dict(_FALLBACK_TOOL_SETS)

    try:
        import yaml  # type: ignore[import]
    except ImportError:
        logger.warning(
            "PyYAML not installed; cannot load tool-sets.yaml — using hardcoded fallback"
        )
        return dict(_FALLBACK_TOOL_SETS)

    try:
        with open(yaml_path) as f:
            raw: Any = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to read tool-sets.yaml at %s: %s; using fallback", yaml_path, exc)
        return dict(_FALLBACK_TOOL_SETS)

    if not isinstance(raw, dict):
        logger.warning(
            "tool-sets.yaml at %s has unexpected top-level type %s; using fallback",
            yaml_path,
            type(raw).__name__,
        )
        return dict(_FALLBACK_TOOL_SETS)

    result: dict[str, list[str]] = {}
    for name, entry in raw.items():
        if isinstance(entry, dict) and "tools" in entry:
            tools = entry["tools"]
            if isinstance(tools, list):
                result[str(name)] = [str(t) for t in tools]
            else:
                logger.warning("tool-sets.yaml: tools for '%s' is not a list; skipping", name)
        else:
            logger.warning("tool-sets.yaml: entry '%s' is missing 'tools' key; skipping", name)

    return result


def _infer_tool_set(node: Any) -> str:
    """Infer the tool set name from the node's shape when not explicitly set.

    - shape=tab  → "research"
    - shape=note → "refine"
    - anything else → "full"
    """
    shape = getattr(node, "shape", "")
    if shape == "tab":
        return "research"
    if shape == "note":
        return "refine"
    return "full"


# ---------------------------------------------------------------------------
# PlannerHandler
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM_PROMPT = (
    "You are a planning/research agent. Follow the prompt instructions carefully "
    "and report your findings."
)


class PlannerHandler:
    """Unified handler for planning-type nodes: research (tab), refine (note), plan.

    Tool set and prompt are configurable via DOT node attributes:

    ``tool_set``
        Named tool set from ``.cobuilder/tool-sets.yaml``.  When absent the
        handler infers the set from the node shape (tab→research, note→refine,
        other→full).

    ``prompt_template`` / ``prompt``
        Prompt resolution is delegated to ``PromptRenderer`` (Epic 2).

    ``system_prompt``
        Custom system prompt string.  Falls back to a generic default.

    Implementation writes evidence JSON to
    ``{run_dir}/nodes/{node_id}/evidence.json`` after SDK execution.
    """

    # Cache tool sets at class level to avoid repeated YAML loads
    _tool_sets: dict[str, list[str]] | None = None

    def _get_tool_sets(self) -> dict[str, list[str]]:
        if PlannerHandler._tool_sets is None:
            PlannerHandler._tool_sets = _load_tool_sets()
        return PlannerHandler._tool_sets

    def _resolve_tools(self, node: Any) -> list[str]:
        """Resolve the list of allowed tools for *node*."""
        tool_sets = self._get_tool_sets()
        set_name: str = node.attrs.get("tool_set", "") or _infer_tool_set(node)
        tools = tool_sets.get(set_name)
        if tools is None:
            logger.warning(
                "Unknown tool_set '%s' for node '%s'; falling back to 'full'",
                set_name,
                node.id,
            )
            tools = tool_sets.get("full", [])
        return tools

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Execute a planning node via the Claude Code SDK.

        Falls back gracefully when ``claude_code_sdk`` is not importable.
        """
        node = request.node

        try:
            import claude_code_sdk  # type: ignore[import-untyped]
            from claude_code_sdk import ClaudeCodeOptions
        except ImportError:
            logger.warning(
                "claude_code_sdk not importable; PlannerHandler cannot execute node '%s'",
                node.id,
            )
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={f"${node.id}.status": "failed"},
                metadata={
                    "dispatch_strategy": "planner-sdk",
                    "error": "claude_code_sdk not installed",
                },
            )

        from cobuilder.engine.prompt_renderer import PromptRenderer
        renderer = PromptRenderer()
        prompt = renderer.render(node, request.context, request.run_dir) or f"Execute task: {node.id}"

        tools = self._resolve_tools(node)
        system_prompt = node.attrs.get("system_prompt", "") or _DEFAULT_SYSTEM_PROMPT

        options = ClaudeCodeOptions(
            allowed_tools=tools,
            system_prompt=system_prompt,
        )

        try:
            messages = []
            async for message in claude_code_sdk.query(prompt=prompt, options=options):
                messages.append(message)

            # Write evidence JSON
            if request.run_dir:
                evidence_dir = os.path.join(request.run_dir, "nodes", node.id)
                os.makedirs(evidence_dir, exist_ok=True)
                evidence_path = os.path.join(evidence_dir, "evidence.json")
                evidence = {
                    "node_id": node.id,
                    "tool_set": node.attrs.get("tool_set", "") or _infer_tool_set(node),
                    "tools_used": tools,
                    "message_count": len(messages),
                    "status": "success",
                }
                try:
                    with open(evidence_path, "w") as f:
                        json.dump(evidence, f, indent=2)
                except OSError as exc:
                    logger.warning("Could not write evidence file for node '%s': %s", node.id, exc)

            return Outcome(
                status=OutcomeStatus.SUCCESS,
                context_updates={f"${node.id}.status": "success"},
                metadata={
                    "dispatch_strategy": "planner-sdk",
                    "tool_set": node.attrs.get("tool_set", "") or _infer_tool_set(node),
                },
                raw_messages=messages,
            )
        except Exception as exc:
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={f"${node.id}.status": "failed"},
                metadata={
                    "dispatch_strategy": "planner-sdk",
                    "error": str(exc),
                },
            )


assert isinstance(PlannerHandler(), Handler)
