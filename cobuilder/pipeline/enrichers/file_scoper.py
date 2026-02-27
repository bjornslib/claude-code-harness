"""FileScoper enricher — identifies files that need modification for a task."""
import logging
from .base import BaseEnricher

logger = logging.getLogger(__name__)

_DEFAULT_FILE_SCOPE = {"modify": [], "create": [], "reference_only": []}

_PROMPT_TEMPLATE = """\
You are analyzing a software task to identify which files need modification.

Task: {node_title}
Description: {description}
Module: {module}
Interfaces: {interfaces}

SD Context:
{sd_context}

Return ONLY a YAML code block with this structure:
```yaml
file_scope:
  modify:
    - path: <relative_file_path>
      reason: <why this file changes>
  create:
    - path: <relative_file_path>
      reason: <why this file is new>
  reference_only:
    - <relative_file_path>
```
"""


class FileScoper(BaseEnricher):
    """Adds `file_scope` key to each node identifying files to modify/create/reference."""

    def _enrich_one(self, node: dict, repomap: dict, sd: str) -> dict:
        prompt = _PROMPT_TEMPLATE.format(
            node_title=node.get("title", ""),
            description=node.get("description", ""),
            module=node.get("module", ""),
            interfaces=node.get("interfaces", ""),
            sd_context=sd[:2000],
        )
        response = self._call_llm(prompt)
        parsed = self._parse_yaml(response)
        self._warn_if_empty(parsed, "file_scope", node.get("title", ""))
        node["file_scope"] = parsed.get("file_scope", _DEFAULT_FILE_SCOPE.copy())
        return node
