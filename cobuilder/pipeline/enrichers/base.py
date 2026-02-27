"""Base enricher class for the LLM enrichment pipeline."""
import re
import logging
import anthropic
import yaml

logger = logging.getLogger(__name__)


class BaseEnricher:
    """Base class for all node enrichers.

    Each enricher makes LLM calls to append structured data to pipeline nodes.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.client = anthropic.Anthropic()

    def enrich_all(self, nodes: list[dict], repomap: dict, sd: str) -> list[dict]:
        """Enrich all nodes in the list."""
        return [self._enrich_one(node, repomap, sd) for node in nodes]

    def _enrich_one(self, node: dict, repomap: dict, sd: str) -> dict:
        """Enrich a single node. Must be overridden by subclasses."""
        raise NotImplementedError

    def _call_llm(self, prompt: str) -> str:
        """Make a single LLM call and return the response text."""
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    def _parse_yaml(self, text: str) -> dict:
        """Extract YAML block from response text. Returns {} on failure."""
        match = re.search(r"```yaml\n(.*?)```", text, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError as e:
                logger.warning("YAML parse failed: %s", e)
        return {}
