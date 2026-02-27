"""ComplexitySizer enricher — assesses task complexity and recommends splitting."""
import logging
from .base import BaseEnricher

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a software engineering lead assessing task complexity.

Task: {node_title}
Description: {description}

Files to modify: {modify_count}
Files to create: {create_count}
Number of acceptance criteria: {ac_count}

Assess the complexity of this task and whether it should be split into subtasks.

Guidelines:
- low: 1-2 files, 1-3 ACs, straightforward implementation
- medium: 3-5 files, 4-6 ACs, some coordination needed
- high: 6+ files, 7+ ACs, multiple systems involved, split recommended

Return ONLY a YAML code block:
```yaml
complexity: low|medium|high
estimated_subtasks: <integer, 1 if no split needed>
split_recommendation: true|false
reasoning: <brief explanation>
```
"""


class ComplexitySizer(BaseEnricher):
    """Adds `complexity`, `estimated_subtasks`, `split_recommendation`, and `sizing_reasoning` keys."""

    def _enrich_one(self, node: dict, repomap: dict, sd: str) -> dict:
        file_scope = node.get("file_scope", {})
        modify_count = len(file_scope.get("modify", []))
        create_count = len(file_scope.get("create", []))
        ac_count = len(node.get("acceptance_criteria", []))

        prompt = _PROMPT_TEMPLATE.format(
            node_title=node.get("title", ""),
            description=node.get("description", ""),
            modify_count=modify_count,
            create_count=create_count,
            ac_count=ac_count,
        )
        response = self._call_llm(prompt)
        parsed = self._parse_yaml(response)

        complexity = parsed.get("complexity", "medium")
        if complexity not in {"low", "medium", "high"}:
            complexity = "medium"

        node["complexity"] = complexity
        node["estimated_subtasks"] = int(parsed.get("estimated_subtasks", 1))
        node["split_recommendation"] = bool(parsed.get("split_recommendation", False))
        node["sizing_reasoning"] = parsed.get("reasoning", "")
        return node
