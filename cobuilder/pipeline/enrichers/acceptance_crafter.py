"""AcceptanceCrafter enricher — generates measurable acceptance criteria from task + SD."""
import logging
from .base import BaseEnricher

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a quality engineer writing acceptance criteria for a software task.

Task: {node_title}
Description: {description}

Solution Design Acceptance Section:
{sd_context}

Generate measurable, testable acceptance criteria for this task.
Return ONLY a YAML code block with this structure:
```yaml
acceptance_criteria:
  - id: AC-1
    criterion: <clear, measurable statement>
    testable: true
    evidence_type: unit_test|integration_test|manual_verification|log_output
```
"""


class AcceptanceCrafter(BaseEnricher):
    """Adds `acceptance_criteria` key to each node with a list of structured ACs."""

    def _enrich_one(self, node: dict, repomap: dict, sd: str) -> dict:
        prompt = _PROMPT_TEMPLATE.format(
            node_title=node.get("title", ""),
            description=node.get("description", ""),
            sd_context=sd[:2000],
        )
        response = self._call_llm(prompt)
        parsed = self._parse_yaml(response)
        self._warn_if_empty(parsed, "acceptance_criteria", node.get("title", ""))
        node["acceptance_criteria"] = parsed.get("acceptance_criteria", [])
        return node
