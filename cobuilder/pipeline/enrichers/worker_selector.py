"""WorkerSelector enricher — determines the best worker type for each task node."""
import logging
from .base import BaseEnricher

logger = logging.getLogger(__name__)

_VALID_WORKER_TYPES = {
    "frontend-dev-expert",
    "backend-solutions-engineer",
    "tdd-test-engineer",
    "solution-architect",
}
_DEFAULT_WORKER = "backend-solutions-engineer"

_PROMPT_TEMPLATE = """\
You are assigning the right specialist worker to a software task.

Task: {node_title}
Description: {description}

Files to modify: {modify_files}
Files to create: {create_files}

Available worker types:
- frontend-dev-expert: React, Next.js, TypeScript, CSS, UI components, Zustand
- backend-solutions-engineer: Python, FastAPI, PydanticAI, databases, APIs, LLM pipelines
- tdd-test-engineer: Writing tests, pytest, Jest, test infrastructure, CI
- solution-architect: System design, architecture documents, cross-cutting decisions

Based on the file types and task description, select the best worker.

Return ONLY a YAML code block:
```yaml
worker_type: <one of the four valid types>
confidence: <0.0 to 1.0>
reasoning: <brief explanation>
```
"""


class WorkerSelector(BaseEnricher):
    """Adds `worker_type`, `worker_confidence`, and `worker_reasoning` keys to each node."""

    def _enrich_one(self, node: dict, repomap: dict, sd: str) -> dict:
        file_scope = node.get("file_scope", {})
        modify_files = [
            f.get("path", "") for f in file_scope.get("modify", [])
        ]
        create_files = [
            f.get("path", "") for f in file_scope.get("create", [])
        ]

        if not modify_files and not create_files:
            node["worker_type"] = _DEFAULT_WORKER
            node["worker_confidence"] = 0.5
            node["worker_reasoning"] = "No file scope available; defaulting to backend engineer."
            return node

        prompt = _PROMPT_TEMPLATE.format(
            node_title=node.get("title", ""),
            description=node.get("description", ""),
            modify_files=", ".join(modify_files) or "(none)",
            create_files=", ".join(create_files) or "(none)",
        )
        response = self._call_llm(prompt)
        parsed = self._parse_yaml(response)
        self._warn_if_empty(parsed, "worker_type", node.get("title", ""))

        worker_type = parsed.get("worker_type", _DEFAULT_WORKER)
        if worker_type not in _VALID_WORKER_TYPES:
            logger.warning(
                "Invalid worker_type '%s' from LLM; defaulting to %s",
                worker_type,
                _DEFAULT_WORKER,
            )
            worker_type = _DEFAULT_WORKER

        node["worker_type"] = worker_type
        node["worker_confidence"] = float(parsed.get("confidence", 0.7))
        node["worker_reasoning"] = parsed.get("reasoning", "")
        return node
