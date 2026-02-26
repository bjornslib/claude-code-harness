"""Implementation code generator for graph-guided code generation.

Generates Python function/class implementations from RPG node specifications
(docstrings, signatures, type hints) using an LLM backend.
"""

from __future__ import annotations

import logging
import textwrap
from typing import Any, Optional

from pydantic import BaseModel, Field

from cobuilder.repomap.models.node import RPGNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_IMPL_SYSTEM_PROMPT = """\
You are a Python implementation expert. Generate clean, production-ready
Python code that satisfies the given specification and passes all provided
tests. Follow PEP 8 style, use type hints, and include inline comments
for complex logic. Output ONLY the implementation code, no markdown fences
or explanations.
"""

_IMPL_USER_TEMPLATE = """\
Generate the implementation for the following Python {interface_type}:

Signature: {signature}

Docstring:
{docstring}

{dependency_context}

{test_context}

Requirements:
- Use type hints on all parameters and return values
- Include inline comments for non-obvious logic
- Handle edge cases (empty inputs, None values, boundary conditions)
- Follow PEP 8 style conventions
- Output ONLY the Python code, no markdown fences
"""

_TEST_GEN_SYSTEM_PROMPT = """\
You are a Python testing expert. Generate comprehensive pytest test cases
from the given function specification. Cover: happy path, edge cases
(empty/None/boundary), and error cases. Output ONLY valid pytest code,
no markdown fences or explanations.
"""

_TEST_GEN_USER_TEMPLATE = """\
Generate pytest test cases for the following Python {interface_type}:

Signature: {signature}

Docstring:
{docstring}

{dependency_context}

Requirements:
- Generate at least 3 test functions
- Cover happy path, edge cases, and error cases
- Use descriptive test names (test_<function>_<scenario>)
- Include appropriate assert statements
- Use pytest.raises for expected exceptions
- Output ONLY valid pytest code, no markdown fences
- Include necessary imports at the top
"""


# ---------------------------------------------------------------------------
# Response model for structured LLM output
# ---------------------------------------------------------------------------


class GeneratedCode(BaseModel):
    """Model for generated code from the LLM.

    Attributes:
        code: The generated Python source code.
        imports: Any additional imports required.
        explanation: Brief explanation of the approach (optional).
    """

    code: str = Field(default="", description="Generated Python source code")
    imports: list[str] = Field(
        default_factory=list,
        description="Additional imports required",
    )
    explanation: str = Field(
        default="",
        description="Brief explanation of the approach",
    )


# ---------------------------------------------------------------------------
# LLM-backed implementation generator
# ---------------------------------------------------------------------------


class LLMImplementationGenerator:
    """Generate implementation code using an LLM backend.

    Uses the LLM gateway to generate Python implementations from RPG node
    specifications (docstrings, signatures, type hints).

    Args:
        llm_gateway: The LLM gateway for making completion requests.
        model: The model identifier to use for generation.
    """

    def __init__(
        self,
        llm_gateway: Any,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._gateway = llm_gateway
        self._model = model

    @property
    def model(self) -> str:
        """The model being used for generation."""
        return self._model

    def generate_implementation(
        self,
        node: RPGNode,
        test_code: str,
        context: dict[str, Any],
    ) -> str:
        """Generate implementation code for an RPG node.

        Constructs a prompt from the node's specification and any
        ancestor context, then calls the LLM to generate code.

        Args:
            node: The RPG node to implement.
            test_code: The pytest test code to satisfy.
            context: Additional context (ancestor implementations, etc.).

        Returns:
            A string of valid Python implementation code.

        Raises:
            ValueError: If the node lacks a signature or docstring.
        """
        if not node.signature:
            raise ValueError(
                f"Node {node.id} ({node.name}) has no signature"
            )

        docstring = node.docstring or "No specification provided."
        interface_type = (
            node.interface_type.value.lower() if node.interface_type else "function"
        )

        # Build dependency context from ancestors
        dep_context = self._build_dependency_context(context)
        test_context = (
            f"Tests to pass:\n{test_code}" if test_code else ""
        )

        prompt = _IMPL_USER_TEMPLATE.format(
            interface_type=interface_type,
            signature=node.signature,
            docstring=docstring,
            dependency_context=dep_context,
            test_context=test_context,
        )

        messages = [
            {"role": "system", "content": _IMPL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        logger.info("Generating implementation for %s (%s)", node.id, node.name)
        response = self._gateway.complete(messages=messages, model=self._model)

        # Strip any markdown fences the LLM might have added
        code = _strip_markdown_fences(response)
        return code

    def generate_tests(
        self,
        node: RPGNode,
        context: dict[str, Any],
    ) -> str:
        """Generate pytest test code for an RPG node.

        Args:
            node: The RPG node to generate tests for.
            context: Additional context (ancestor implementations, etc.).

        Returns:
            A string of valid pytest test code.

        Raises:
            ValueError: If the node lacks a signature.
        """
        if not node.signature:
            raise ValueError(
                f"Node {node.id} ({node.name}) has no signature"
            )

        docstring = node.docstring or "No specification provided."
        interface_type = (
            node.interface_type.value.lower() if node.interface_type else "function"
        )
        dep_context = self._build_dependency_context(context)

        prompt = _TEST_GEN_USER_TEMPLATE.format(
            interface_type=interface_type,
            signature=node.signature,
            docstring=docstring,
            dependency_context=dep_context,
        )

        messages = [
            {"role": "system", "content": _TEST_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        logger.info("Generating tests for %s (%s)", node.id, node.name)
        response = self._gateway.complete(messages=messages, model=self._model)

        code = _strip_markdown_fences(response)
        return code

    @staticmethod
    def _build_dependency_context(context: dict[str, Any]) -> str:
        """Build a dependency context string from ancestor implementations.

        Args:
            context: Context dict that may contain 'ancestor_implementations'.

        Returns:
            A formatted string describing available dependencies, or empty string.
        """
        ancestors = context.get("ancestor_implementations", {})
        if not ancestors:
            return ""

        lines = ["Available dependencies (already implemented):"]
        for name, impl in ancestors.items():
            # Truncate long implementations
            truncated = textwrap.shorten(impl, width=500, placeholder="...")
            lines.append(f"\n{name}:\n{truncated}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from LLM output.

    Handles ```python ... ```, ``` ... ```, and bare code.

    Args:
        text: Raw LLM output that may contain markdown fences.

    Returns:
        Clean Python code without markdown fences.
    """
    stripped = text.strip()

    # Handle ```python\n...\n```
    if stripped.startswith("```python"):
        stripped = stripped[len("```python") :].strip()
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")].strip()
        return stripped

    # Handle ```\n...\n```
    if stripped.startswith("```"):
        stripped = stripped[len("```") :].strip()
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")].strip()
        return stripped

    return stripped
