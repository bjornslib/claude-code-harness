"""DependencyInferrer enricher — infers logical dependencies between pipeline nodes."""
import logging
from .base import BaseEnricher

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a software architect inferring task dependencies.

Current Task: {node_title} (id: {node_id})
Description: {description}

All pipeline nodes (id → title):
{all_nodes}

Repomap dependency relationships:
{repomap_summary}

Based on the task descriptions and module relationships, infer which other tasks
this task logically depends on (must be completed before this one).

Return ONLY a YAML code block:
```yaml
dependencies:
  - depends_on: <node_id>
    reason: <why this dependency exists>
```

Only list real dependencies. If there are none, return an empty list.
"""


class DependencyInferrer(BaseEnricher):
    """Adds `dependencies` key to each node listing logical task dependencies."""

    def enrich_all(self, nodes: list[dict], repomap: dict, sd: str) -> list[dict]:
        """Override to pass all node titles as context to each enrichment call."""
        all_nodes_summary = "\n".join(
            f"  {n.get('id', idx)}: {n.get('title', '')}"
            for idx, n in enumerate(nodes)
        )
        repomap_summary = self._summarize_repomap(repomap)
        return [
            self._enrich_one_with_context(node, repomap_summary, all_nodes_summary)
            for node in nodes
        ]

    def _enrich_one(self, node: dict, repomap: dict, sd: str) -> dict:
        # Called from base class — not used directly (enrich_all overridden)
        return node

    def _enrich_one_with_context(
        self, node: dict, repomap_summary: str, all_nodes_summary: str
    ) -> dict:
        prompt = _PROMPT_TEMPLATE.format(
            node_title=node.get("title", ""),
            node_id=node.get("id", ""),
            description=node.get("description", ""),
            all_nodes=all_nodes_summary,
            repomap_summary=repomap_summary[:1500],
        )
        response = self._call_llm(prompt)
        parsed = self._parse_yaml(response)
        node["dependencies"] = parsed.get("dependencies", [])
        return node

    def _summarize_repomap(self, repomap: dict) -> str:
        """Produce a compact text summary of repomap dependency edges."""
        if not repomap:
            return "(no repomap data)"
        lines = []
        for module, data in repomap.items():
            deps = data.get("dependencies", []) if isinstance(data, dict) else []
            if deps:
                lines.append(f"{module} → {', '.join(deps)}")
        return "\n".join(lines[:50]) if lines else "(no dependency edges)"
