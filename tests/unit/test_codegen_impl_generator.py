"""Unit tests for the implementation code generator."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from zerorepo.codegen.impl_generator import (
    GeneratedCode,
    LLMImplementationGenerator,
    _strip_markdown_fences,
)
from zerorepo.models.enums import InterfaceType, NodeLevel, NodeType
from zerorepo.models.node import RPGNode


# --------------------------------------------------------------------------- #
#                              Helpers / Fixtures                              #
# --------------------------------------------------------------------------- #


def _make_func_node(
    *,
    name: str = "calculate_mean",
    docstring: str = "Calculate the mean of a list of numbers.",
    signature: str = "def calculate_mean(numbers: list[float]) -> float",
    interface_type: InterfaceType = InterfaceType.FUNCTION,
) -> RPGNode:
    """Create a FUNCTION_AUGMENTED node for testing."""
    return RPGNode(
        name=name,
        level=NodeLevel.FEATURE,
        node_type=NodeType.FUNCTION_AUGMENTED,
        interface_type=interface_type,
        folder_path="src",
        file_path="src/module.py",
        signature=signature,
        docstring=docstring,
    )


def _make_mock_gateway(response: str = "def calculate_mean(numbers): return sum(numbers) / len(numbers)") -> MagicMock:
    """Create a mock LLM gateway that returns a fixed response."""
    gateway = MagicMock()
    gateway.complete.return_value = response
    return gateway


# --------------------------------------------------------------------------- #
#                              Tests: _strip_markdown_fences                   #
# --------------------------------------------------------------------------- #


class TestStripMarkdownFences:
    """Tests for the markdown fence stripping utility."""

    def test_no_fences(self):
        code = "def foo(): return 42"
        assert _strip_markdown_fences(code) == code

    def test_python_fences(self):
        text = "```python\ndef foo(): return 42\n```"
        assert _strip_markdown_fences(text) == "def foo(): return 42"

    def test_plain_fences(self):
        text = "```\ndef foo(): return 42\n```"
        assert _strip_markdown_fences(text) == "def foo(): return 42"

    def test_fences_with_whitespace(self):
        text = "\n\n```python\ndef foo(): return 42\n```\n\n"
        assert _strip_markdown_fences(text) == "def foo(): return 42"

    def test_no_closing_fence(self):
        text = "```python\ndef foo(): return 42"
        assert _strip_markdown_fences(text) == "def foo(): return 42"


# --------------------------------------------------------------------------- #
#                              Tests: GeneratedCode model                      #
# --------------------------------------------------------------------------- #


class TestGeneratedCode:
    """Tests for the GeneratedCode Pydantic model."""

    def test_defaults(self):
        gc = GeneratedCode()
        assert gc.code == ""
        assert gc.imports == []
        assert gc.explanation == ""

    def test_with_values(self):
        gc = GeneratedCode(
            code="def foo(): pass",
            imports=["import os"],
            explanation="Simple function",
        )
        assert gc.code == "def foo(): pass"
        assert gc.imports == ["import os"]
        assert gc.explanation == "Simple function"


# --------------------------------------------------------------------------- #
#                              Tests: LLMImplementationGenerator               #
# --------------------------------------------------------------------------- #


class TestLLMImplementationGenerator:
    """Tests for the LLM-backed implementation generator."""

    def test_generate_implementation_from_spec(self):
        """Simple mean function generates runnable Python with type hints."""
        response = "def calculate_mean(numbers: list[float]) -> float:\n    return sum(numbers) / len(numbers)"
        gateway = _make_mock_gateway(response)
        gen = LLMImplementationGenerator(gateway, model="gpt-4o-mini")

        node = _make_func_node()
        result = gen.generate_implementation(node, "def test_it(): assert True", {})

        assert "calculate_mean" in result
        assert "return" in result
        gateway.complete.assert_called_once()

        # Verify prompt structure
        call_args = gateway.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_generate_implementation_no_signature_raises(self):
        """Node without signature raises ValueError."""
        gateway = _make_mock_gateway()
        gen = LLMImplementationGenerator(gateway)

        # Use FUNCTIONALITY node_type which doesn't require interface_type/signature
        node = RPGNode(
            name="no_sig",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )

        with pytest.raises(ValueError, match="has no signature"):
            gen.generate_implementation(node, "", {})

    def test_generate_implementation_strips_fences(self):
        """Markdown fences are stripped from LLM output."""
        response = "```python\ndef foo(): return 42\n```"
        gateway = _make_mock_gateway(response)
        gen = LLMImplementationGenerator(gateway)

        node = _make_func_node()
        result = gen.generate_implementation(node, "", {})

        assert not result.startswith("```")
        assert "def foo()" in result

    def test_generate_implementation_with_context(self):
        """Ancestor implementations are included in the prompt."""
        gateway = _make_mock_gateway("def calculate_mean(numbers): pass")
        gen = LLMImplementationGenerator(gateway)

        node = _make_func_node()
        context = {
            "ancestor_implementations": {
                "helper_func": "def helper_func(): return 42",
            }
        }

        gen.generate_implementation(node, "", context)

        call_args = gateway.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        user_msg = messages[1]["content"]
        assert "helper_func" in user_msg
        assert "Available dependencies" in user_msg

    def test_generate_tests(self):
        """Generate test code from a node specification."""
        response = (
            "import pytest\n\n"
            "def test_calculate_mean_happy():\n"
            "    assert calculate_mean([1, 2, 3]) == 2.0\n\n"
            "def test_calculate_mean_single():\n"
            "    assert calculate_mean([5]) == 5.0\n\n"
            "def test_calculate_mean_empty():\n"
            "    with pytest.raises(ZeroDivisionError):\n"
            "        calculate_mean([])\n"
        )
        gateway = _make_mock_gateway(response)
        gen = LLMImplementationGenerator(gateway)

        node = _make_func_node()
        result = gen.generate_tests(node, {})

        assert "test_calculate_mean" in result
        assert "assert" in result
        gateway.complete.assert_called_once()

    def test_generate_tests_no_signature_raises(self):
        """Node without signature raises ValueError for test generation."""
        gateway = _make_mock_gateway()
        gen = LLMImplementationGenerator(gateway)

        # Use FUNCTIONALITY node_type which doesn't require interface_type/signature
        node = RPGNode(
            name="no_sig",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )

        with pytest.raises(ValueError, match="has no signature"):
            gen.generate_tests(node, {})

    def test_model_property(self):
        """Model property returns configured model."""
        gateway = _make_mock_gateway()
        gen = LLMImplementationGenerator(gateway, model="claude-3-haiku-20240307")
        assert gen.model == "claude-3-haiku-20240307"

    def test_class_interface_type(self):
        """CLASS interface type is handled in the prompt."""
        gateway = _make_mock_gateway("class MyClass:\n    pass")
        gen = LLMImplementationGenerator(gateway)

        node = _make_func_node(
            name="MyClass",
            interface_type=InterfaceType.CLASS,
            signature="class MyClass",
        )
        gen.generate_implementation(node, "", {})

        call_args = gateway.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        user_msg = messages[1]["content"]
        assert "class" in user_msg.lower()

    def test_build_dependency_context_empty(self):
        """Empty context produces empty dependency string."""
        result = LLMImplementationGenerator._build_dependency_context({})
        assert result == ""

    def test_build_dependency_context_with_ancestors(self):
        """Context with ancestor implementations produces formatted string."""
        context = {
            "ancestor_implementations": {
                "helper": "def helper(): return 42",
            }
        }
        result = LLMImplementationGenerator._build_dependency_context(context)
        assert "Available dependencies" in result
        assert "helper" in result

    def test_no_docstring_uses_default(self):
        """Node without docstring uses default placeholder."""
        gateway = _make_mock_gateway("def foo(): pass")
        gen = LLMImplementationGenerator(gateway)

        node = _make_func_node(docstring=None)
        gen.generate_implementation(node, "", {})

        call_args = gateway.complete.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        user_msg = messages[1]["content"]
        assert "No specification provided" in user_msg
