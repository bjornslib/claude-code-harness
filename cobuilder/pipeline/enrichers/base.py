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

    def _parse_yaml(self, text: str, *, _retries: int = 2) -> dict:
        """Extract YAML block from response text with retry on parse failure.

        If the YAML block cannot be parsed, sends the raw response back to the
        LLM with the parse error and asks for a corrected version.  Retries up
        to *_retries* times before returning ``{}``.
        """
        match = re.search(r"```yaml\n(.*?)```", text, re.DOTALL)
        if not match:
            return {}

        raw_yaml = match.group(1)
        try:
            return yaml.safe_load(raw_yaml) or {}
        except yaml.YAMLError as e:
            logger.warning("YAML parse failed: %s", e)

        # Retry: ask the LLM to fix the YAML
        for attempt in range(1, _retries + 1):
            logger.info("Retrying YAML parse (attempt %d/%d)", attempt, _retries)
            fix_prompt = (
                "The following YAML block failed to parse:\n\n"
                f"```yaml\n{raw_yaml}```\n\n"
                f"Parse error: {e}\n\n"
                "Please return ONLY the corrected YAML inside a ```yaml``` "
                "code fence.  Make sure all string values containing colons "
                "are quoted."
            )
            try:
                fixed_text = self._call_llm(fix_prompt)
                fixed_match = re.search(r"```yaml\n(.*?)```", fixed_text, re.DOTALL)
                if fixed_match:
                    result = yaml.safe_load(fixed_match.group(1))
                    if result:
                        logger.info("YAML fix succeeded on attempt %d", attempt)
                        return result
            except (yaml.YAMLError, Exception) as retry_err:
                logger.warning("YAML fix attempt %d failed: %s", attempt, retry_err)

        logger.error("YAML parse failed after %d retries, returning empty dict", _retries)
        return {}
