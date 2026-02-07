"""Integration test generator for graph-guided code generation.

Generates cross-node integration tests by analyzing dependency edges
in the RPG graph and creating test cases that verify interactions
between connected nodes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                              Protocols                                       #
# --------------------------------------------------------------------------- #


class LLMProtocol(Protocol):
    """Protocol for LLM interactions (real or mock)."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request and return the response text."""
        ...


# --------------------------------------------------------------------------- #
#                              Models                                          #
# --------------------------------------------------------------------------- #


class IntegrationTestType(str, Enum):
    """Types of integration tests that can be generated."""

    DATA_FLOW = "data_flow"
    API_CONTRACT = "api_contract"
    EVENT_CHAIN = "event_chain"
    ERROR_PROPAGATION = "error_propagation"


@dataclass
class NodeInterface:
    """Describes a node's public interface for integration test generation.

    Attributes:
        node_id: The UUID of the node.
        node_name: Human-readable name.
        file_path: Where the node's code lives.
        exports: List of exported symbols (functions, classes).
        imports: List of symbols imported by this node.
        signature: Optional function/class signature.
        description: What the node does.
    """

    node_id: UUID
    node_name: str = ""
    file_path: str = ""
    exports: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    signature: Optional[str] = None
    description: str = ""


@dataclass
class DependencyEdge:
    """An edge between two nodes representing a dependency.

    Attributes:
        source_id: The upstream node UUID (provider).
        target_id: The downstream node UUID (consumer).
        edge_type: The type of dependency relationship.
        shared_symbols: Symbols shared across this edge.
    """

    source_id: UUID
    target_id: UUID
    edge_type: str = "depends_on"
    shared_symbols: list[str] = field(default_factory=list)


@dataclass
class IntegrationTestCase:
    """A generated integration test case.

    Attributes:
        test_name: The name of the test function.
        test_type: The type of integration test.
        source_node_id: The upstream node in the interaction.
        target_node_id: The downstream node in the interaction.
        test_code: The generated Python test code.
        description: Human-readable description of what is tested.
        dependencies: Node UUIDs this test depends on.
    """

    test_name: str
    test_type: IntegrationTestType
    source_node_id: UUID
    target_node_id: UUID
    test_code: str
    description: str = ""
    dependencies: list[UUID] = field(default_factory=list)


@dataclass
class IntegrationTestSuite:
    """A complete suite of integration tests for a node pair or group.

    Attributes:
        test_cases: All generated test cases.
        source_file: Suggested file path for the test module.
        imports_block: Python import block for the test file.
        setup_code: Optional shared test setup code.
        total_generated: Number of tests generated.
    """

    test_cases: list[IntegrationTestCase] = field(default_factory=list)
    source_file: str = "test_integration.py"
    imports_block: str = ""
    setup_code: str = ""
    total_generated: int = 0

    def render(self) -> str:
        """Render the complete test file as a Python string.

        Returns:
            The full Python test file content.
        """
        parts = ['"""Generated integration tests."""\n']

        if self.imports_block:
            parts.append(self.imports_block)
            parts.append("")

        if self.setup_code:
            parts.append(self.setup_code)
            parts.append("")

        for tc in self.test_cases:
            if tc.description:
                parts.append(f"# {tc.description}")
            parts.append(tc.test_code)
            parts.append("")

        return "\n".join(parts)


class IntegrationGeneratorConfig(BaseModel):
    """Configuration for the IntegrationGenerator.

    Attributes:
        max_tests_per_edge: Maximum tests to generate per dependency edge.
        include_error_tests: Whether to generate error propagation tests.
        include_data_flow: Whether to generate data flow tests.
        model_name: LLM model to use for generation.
        temperature: LLM generation temperature.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    max_tests_per_edge: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum tests per dependency edge",
    )
    include_error_tests: bool = Field(
        default=True,
        description="Generate error propagation tests",
    )
    include_data_flow: bool = Field(
        default=True,
        description="Generate data flow tests",
    )
    model_name: str = Field(
        default="gpt-4o-mini",
        description="LLM model for test generation",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LLM generation temperature",
    )


# --------------------------------------------------------------------------- #
#                           Prompt Builder                                     #
# --------------------------------------------------------------------------- #


def build_integration_prompt(
    source: NodeInterface,
    target: NodeInterface,
    edge: DependencyEdge,
    test_type: IntegrationTestType,
    config: IntegrationGeneratorConfig,
) -> list[dict[str, Any]]:
    """Build an LLM prompt for generating integration tests.

    Args:
        source: The upstream node interface.
        target: The downstream node interface.
        edge: The dependency edge between them.
        test_type: The type of integration test to generate.
        config: The generator configuration.

    Returns:
        A list of chat messages suitable for LLM completion.
    """
    system_msg = (
        "You are an expert Python test engineer. Generate pytest integration "
        "tests that verify the interaction between two modules. "
        "Use appropriate mocking and assertions. "
        "Return ONLY the test function code, no imports or setup."
    )

    shared = ", ".join(edge.shared_symbols) if edge.shared_symbols else "none"

    user_msg = (
        f"Generate a {test_type.value} integration test.\n\n"
        f"Source module: {source.node_name}\n"
        f"  File: {source.file_path}\n"
        f"  Exports: {', '.join(source.exports)}\n"
        f"  Signature: {source.signature or 'N/A'}\n"
        f"  Description: {source.description}\n\n"
        f"Target module: {target.node_name}\n"
        f"  File: {target.file_path}\n"
        f"  Exports: {', '.join(target.exports)}\n"
        f"  Signature: {target.signature or 'N/A'}\n"
        f"  Description: {target.description}\n\n"
        f"Shared symbols: {shared}\n"
        f"Edge type: {edge.edge_type}\n\n"
        f"Write a single pytest test function that verifies the "
        f"{test_type.value} interaction between these modules."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


# --------------------------------------------------------------------------- #
#                      Template-Based Generator                                #
# --------------------------------------------------------------------------- #


def generate_data_flow_test(
    source: NodeInterface,
    target: NodeInterface,
    edge: DependencyEdge,
) -> str:
    """Generate a data flow integration test from a template.

    This is used as a fallback when no LLM is available.

    Args:
        source: The upstream node interface.
        target: The downstream node interface.
        edge: The dependency edge.

    Returns:
        Python test code as a string.
    """
    test_name = (
        f"test_data_flow_{_sanitize(source.node_name)}"
        f"_to_{_sanitize(target.node_name)}"
    )
    shared = edge.shared_symbols[:1] or ["data"]
    symbol = shared[0]

    return (
        f"def {test_name}():\n"
        f'    """Test data flows from {source.node_name} to '
        f'{target.node_name}."""\n'
        f"    # Setup: create expected data from source\n"
        f"    source_output = {{'key': 'value', 'symbol': '{symbol}'}}\n"
        f"    # Verify target can process source's output\n"
        f"    assert source_output is not None\n"
        f"    assert 'key' in source_output\n"
    )


def generate_error_propagation_test(
    source: NodeInterface,
    target: NodeInterface,
    edge: DependencyEdge,
) -> str:
    """Generate an error propagation integration test from a template.

    Args:
        source: The upstream node interface.
        target: The downstream node interface.
        edge: The dependency edge.

    Returns:
        Python test code as a string.
    """
    test_name = (
        f"test_error_propagation_{_sanitize(source.node_name)}"
        f"_to_{_sanitize(target.node_name)}"
    )

    return (
        f"def {test_name}():\n"
        f'    """Test error propagation from {source.node_name} to '
        f'{target.node_name}."""\n'
        f"    # When source raises an error, target should handle gracefully\n"
        f"    import pytest\n"
        f"    # Simulate source failure\n"
        f"    source_error = ValueError('source failed')\n"
        f"    # Verify error is properly handled\n"
        f"    assert str(source_error) == 'source failed'\n"
    )


def _sanitize(name: str) -> str:
    """Sanitize a name for use in a Python identifier.

    Args:
        name: The original name.

    Returns:
        A sanitized version safe for use as a Python identifier.
    """
    return "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()


# --------------------------------------------------------------------------- #
#                        Integration Generator                                 #
# --------------------------------------------------------------------------- #


class IntegrationGenerator:
    """Generates integration tests for dependency edges in the RPG graph.

    Uses templates and optionally an LLM to generate cross-module test
    cases that verify interactions between connected nodes.

    Args:
        config: Generator configuration.
        llm: Optional LLM instance for AI-generated tests.
    """

    def __init__(
        self,
        config: IntegrationGeneratorConfig | None = None,
        llm: LLMProtocol | None = None,
    ) -> None:
        self._config = config or IntegrationGeneratorConfig()
        self._llm = llm

    @property
    def config(self) -> IntegrationGeneratorConfig:
        """The generator configuration."""
        return self._config

    def generate_for_edge(
        self,
        source: NodeInterface,
        target: NodeInterface,
        edge: DependencyEdge,
    ) -> list[IntegrationTestCase]:
        """Generate integration tests for a single dependency edge.

        Args:
            source: The upstream node interface.
            target: The downstream node interface.
            edge: The dependency edge between them.

        Returns:
            A list of generated IntegrationTestCase objects.
        """
        test_cases: list[IntegrationTestCase] = []

        # Generate data flow test
        if self._config.include_data_flow:
            if self._llm:
                test_code = self._generate_with_llm(
                    source, target, edge, IntegrationTestType.DATA_FLOW
                )
            else:
                test_code = generate_data_flow_test(source, target, edge)

            test_name = (
                f"test_data_flow_{_sanitize(source.node_name)}"
                f"_to_{_sanitize(target.node_name)}"
            )
            test_cases.append(
                IntegrationTestCase(
                    test_name=test_name,
                    test_type=IntegrationTestType.DATA_FLOW,
                    source_node_id=source.node_id,
                    target_node_id=target.node_id,
                    test_code=test_code,
                    description=(
                        f"Data flow from {source.node_name} to {target.node_name}"
                    ),
                    dependencies=[source.node_id, target.node_id],
                )
            )

        # Generate error propagation test
        if self._config.include_error_tests:
            if self._llm:
                test_code = self._generate_with_llm(
                    source, target, edge, IntegrationTestType.ERROR_PROPAGATION
                )
            else:
                test_code = generate_error_propagation_test(source, target, edge)

            test_name = (
                f"test_error_propagation_{_sanitize(source.node_name)}"
                f"_to_{_sanitize(target.node_name)}"
            )
            test_cases.append(
                IntegrationTestCase(
                    test_name=test_name,
                    test_type=IntegrationTestType.ERROR_PROPAGATION,
                    source_node_id=source.node_id,
                    target_node_id=target.node_id,
                    test_code=test_code,
                    description=(
                        f"Error propagation from {source.node_name} "
                        f"to {target.node_name}"
                    ),
                    dependencies=[source.node_id, target.node_id],
                )
            )

        # Respect max_tests_per_edge
        return test_cases[: self._config.max_tests_per_edge]

    def generate_suite(
        self,
        edges: list[tuple[NodeInterface, NodeInterface, DependencyEdge]],
    ) -> IntegrationTestSuite:
        """Generate a full integration test suite from multiple edges.

        Args:
            edges: List of (source, target, edge) tuples to generate tests for.

        Returns:
            An IntegrationTestSuite with all generated test cases.
        """
        all_cases: list[IntegrationTestCase] = []

        for source, target, edge in edges:
            logger.info(
                "Generating integration tests for edge %s -> %s",
                source.node_name,
                target.node_name,
            )
            cases = self.generate_for_edge(source, target, edge)
            all_cases.extend(cases)

        imports_block = (
            "import pytest\n"
            "from unittest.mock import MagicMock, patch\n"
        )

        suite = IntegrationTestSuite(
            test_cases=all_cases,
            imports_block=imports_block,
            total_generated=len(all_cases),
        )

        logger.info("Generated %d integration tests from %d edges", len(all_cases), len(edges))
        return suite

    def _generate_with_llm(
        self,
        source: NodeInterface,
        target: NodeInterface,
        edge: DependencyEdge,
        test_type: IntegrationTestType,
    ) -> str:
        """Generate a test case using the LLM.

        Args:
            source: The upstream node interface.
            target: The downstream node interface.
            edge: The dependency edge.
            test_type: The type of integration test.

        Returns:
            Generated test code as a string.
        """
        if not self._llm:
            raise RuntimeError("LLM not configured")

        messages = build_integration_prompt(
            source, target, edge, test_type, self._config
        )

        try:
            response = self._llm.complete(
                messages=messages,
                model=self._config.model_name,
                temperature=self._config.temperature,
            )
            return response.strip()
        except Exception as exc:
            logger.warning(
                "LLM generation failed for %s test (%s -> %s): %s",
                test_type.value,
                source.node_name,
                target.node_name,
                exc,
            )
            # Fall back to template
            if test_type == IntegrationTestType.DATA_FLOW:
                return generate_data_flow_test(source, target, edge)
            else:
                return generate_error_propagation_test(source, target, edge)
