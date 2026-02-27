"""ZeroRepo LLM Gateway – unified multi-provider LLM interface.

This package implements Epic 1.3 of PRD-RPG-P1-001, providing:

- :class:`LLMGateway` – Multi-provider completion via LiteLLM
- :class:`ModelTier` – Tiered model selection (CHEAP / MEDIUM / STRONG)
- :class:`TokenTracker` – Token usage tracking with cost estimation
- :class:`PromptTemplate` – Jinja2-based prompt template management
"""

from cobuilder.repomap.llm.exceptions import (
    ConfigurationError,
    LLMGatewayError,
    RetryExhaustedError,
    TemplateError,
)
from cobuilder.repomap.llm.gateway import LLMGateway
from cobuilder.repomap.llm.models import (
    GatewayConfig,
    LLMLogEntry,
    ModelTier,
)
from cobuilder.repomap.llm.prompt_templates import PromptTemplate
from cobuilder.repomap.llm.token_tracker import TokenTracker

__all__ = [
    "ConfigurationError",
    "GatewayConfig",
    "LLMGateway",
    "LLMGatewayError",
    "LLMLogEntry",
    "ModelTier",
    "PromptTemplate",
    "RetryExhaustedError",
    "TemplateError",
    "TokenTracker",
]
