"""Unit tests for the codegen integration_generator module."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from cobuilder.repomap.codegen.integration_generator import (
    DependencyEdge,
    IntegrationGenerator,
    IntegrationGeneratorConfig,
    IntegrationTestCase,
    IntegrationTestSuite,
    IntegrationTestType,
    NodeInterface,
    _sanitize,
    build_integration_prompt,
    generate_data_flow_test,
    generate_error_propagation_test,
)


# --------------------------------------------------------------------------- #
#                              Mock LLM                                        #
# --------------------------------------------------------------------------- #


class MockLLM:
    """Mock LLM for testing without API calls."""

    def __init__(self, response: str = "def test_mock(): assert True") -> None:
        self.calls: list[dict] = []
        self._response = response
        self._should_fail = False

    def set_failure(self, should_fail: bool = True) -> None:
        """Configure the mock to raise on next call."""
        self._should_fail = should_fail

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str:
        self.calls.append({"messages": messages, "model": model, **kwargs})
        if self._should_fail:
            raise RuntimeError("LLM API error")
        return self._response


# --------------------------------------------------------------------------- #
#                         Test: IntegrationTestType Enum                       #
# --------------------------------------------------------------------------- #


class TestIntegrationTestType:
    """Test IntegrationTestType enum values."""

    def test_all_values(self) -> None:
        assert IntegrationTestType.DATA_FLOW == "data_flow"
        assert IntegrationTestType.API_CONTRACT == "api_contract"
        assert IntegrationTestType.EVENT_CHAIN == "event_chain"
        assert IntegrationTestType.ERROR_PROPAGATION == "error_propagation"

    def test_is_string_enum(self) -> None:
        assert isinstance(IntegrationTestType.DATA_FLOW, str)

    def test_from_value(self) -> None:
        assert IntegrationTestType("data_flow") == IntegrationTestType.DATA_FLOW

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            IntegrationTestType("unknown")


# --------------------------------------------------------------------------- #
#                         Test: NodeInterface                                  #
# --------------------------------------------------------------------------- #


class TestNodeInterface:
    """Test NodeInterface dataclass."""

    def test_defaults(self) -> None:
        nid = uuid4()
        iface = NodeInterface(node_id=nid)
        assert iface.node_id == nid
        assert iface.node_name == ""
        assert iface.exports == []
        assert iface.imports == []
        assert iface.signature is None
        assert iface.description == ""

    def test_with_data(self) -> None:
        iface = NodeInterface(
            node_id=uuid4(),
            node_name="AuthModule",
            file_path="src/auth.py",
            exports=["login", "logout"],
            imports=["jwt"],
            signature="def login(user, pwd) -> Token",
            description="Handles authentication",
        )
        assert iface.node_name == "AuthModule"
        assert len(iface.exports) == 2
        assert iface.signature is not None


# --------------------------------------------------------------------------- #
#                         Test: DependencyEdge                                 #
# --------------------------------------------------------------------------- #


class TestDependencyEdge:
    """Test DependencyEdge dataclass."""

    def test_defaults(self) -> None:
        s, t = uuid4(), uuid4()
        edge = DependencyEdge(source_id=s, target_id=t)
        assert edge.source_id == s
        assert edge.target_id == t
        assert edge.edge_type == "depends_on"
        assert edge.shared_symbols == []

    def test_with_shared_symbols(self) -> None:
        edge = DependencyEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            shared_symbols=["Token", "UserModel"],
        )
        assert len(edge.shared_symbols) == 2


# --------------------------------------------------------------------------- #
#                         Test: IntegrationTestCase                            #
# --------------------------------------------------------------------------- #


class TestIntegrationTestCase:
    """Test IntegrationTestCase dataclass."""

    def test_creation(self) -> None:
        s, t = uuid4(), uuid4()
        tc = IntegrationTestCase(
            test_name="test_data_flow_auth_to_session",
            test_type=IntegrationTestType.DATA_FLOW,
            source_node_id=s,
            target_node_id=t,
            test_code="def test_data_flow(): pass",
            description="Tests auth to session flow",
            dependencies=[s, t],
        )
        assert tc.test_name == "test_data_flow_auth_to_session"
        assert tc.test_type == IntegrationTestType.DATA_FLOW
        assert len(tc.dependencies) == 2


# --------------------------------------------------------------------------- #
#                         Test: IntegrationTestSuite                           #
# --------------------------------------------------------------------------- #


class TestIntegrationTestSuite:
    """Test IntegrationTestSuite dataclass and render method."""

    def test_defaults(self) -> None:
        suite = IntegrationTestSuite()
        assert suite.test_cases == []
        assert suite.source_file == "test_integration.py"
        assert suite.total_generated == 0

    def test_render_empty(self) -> None:
        suite = IntegrationTestSuite()
        rendered = suite.render()
        assert '"""Generated integration tests."""' in rendered

    def test_render_with_tests(self) -> None:
        suite = IntegrationTestSuite(
            test_cases=[
                IntegrationTestCase(
                    test_name="test_flow",
                    test_type=IntegrationTestType.DATA_FLOW,
                    source_node_id=uuid4(),
                    target_node_id=uuid4(),
                    test_code="def test_flow(): pass",
                    description="A test",
                ),
            ],
            imports_block="import pytest\n",
            setup_code="# setup\n",
            total_generated=1,
        )
        rendered = suite.render()
        assert "import pytest" in rendered
        assert "def test_flow(): pass" in rendered
        assert "# A test" in rendered
        assert "# setup" in rendered

    def test_render_multiple_tests(self) -> None:
        suite = IntegrationTestSuite(
            test_cases=[
                IntegrationTestCase(
                    test_name=f"test_{i}",
                    test_type=IntegrationTestType.DATA_FLOW,
                    source_node_id=uuid4(),
                    target_node_id=uuid4(),
                    test_code=f"def test_{i}(): pass",
                )
                for i in range(3)
            ],
            total_generated=3,
        )
        rendered = suite.render()
        assert "def test_0(): pass" in rendered
        assert "def test_1(): pass" in rendered
        assert "def test_2(): pass" in rendered


# --------------------------------------------------------------------------- #
#                         Test: IntegrationGeneratorConfig                     #
# --------------------------------------------------------------------------- #


class TestIntegrationGeneratorConfig:
    """Test IntegrationGeneratorConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = IntegrationGeneratorConfig()
        assert config.max_tests_per_edge == 3
        assert config.include_error_tests is True
        assert config.include_data_flow is True
        assert config.model_name == "gpt-4o-mini"
        assert config.temperature == 0.3

    def test_custom_values(self) -> None:
        config = IntegrationGeneratorConfig(
            max_tests_per_edge=5,
            include_error_tests=False,
            model_name="claude-3.5-sonnet",
            temperature=0.7,
        )
        assert config.max_tests_per_edge == 5
        assert config.include_error_tests is False

    def test_validation_limits(self) -> None:
        with pytest.raises(Exception):
            IntegrationGeneratorConfig(max_tests_per_edge=0)
        with pytest.raises(Exception):
            IntegrationGeneratorConfig(max_tests_per_edge=15)
        with pytest.raises(Exception):
            IntegrationGeneratorConfig(temperature=-0.1)


# --------------------------------------------------------------------------- #
#                         Test: Helper Functions                               #
# --------------------------------------------------------------------------- #


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_sanitize_simple(self) -> None:
        assert _sanitize("AuthModule") == "authmodule"

    def test_sanitize_with_spaces(self) -> None:
        assert _sanitize("my module name") == "my_module_name"

    def test_sanitize_with_special_chars(self) -> None:
        assert _sanitize("my-module.v2") == "my_module_v2"

    def test_sanitize_empty(self) -> None:
        assert _sanitize("") == ""

    def test_generate_data_flow_test(self) -> None:
        source = NodeInterface(node_id=uuid4(), node_name="Auth")
        target = NodeInterface(node_id=uuid4(), node_name="Session")
        edge = DependencyEdge(
            source_id=source.node_id,
            target_id=target.node_id,
            shared_symbols=["Token"],
        )
        code = generate_data_flow_test(source, target, edge)
        assert "def test_data_flow_auth_to_session" in code
        assert "Token" in code
        assert "assert" in code

    def test_generate_data_flow_test_no_shared(self) -> None:
        source = NodeInterface(node_id=uuid4(), node_name="A")
        target = NodeInterface(node_id=uuid4(), node_name="B")
        edge = DependencyEdge(source_id=source.node_id, target_id=target.node_id)
        code = generate_data_flow_test(source, target, edge)
        assert "data" in code  # Falls back to 'data' default

    def test_generate_error_propagation_test(self) -> None:
        source = NodeInterface(node_id=uuid4(), node_name="Parser")
        target = NodeInterface(node_id=uuid4(), node_name="Validator")
        edge = DependencyEdge(
            source_id=source.node_id, target_id=target.node_id
        )
        code = generate_error_propagation_test(source, target, edge)
        assert "def test_error_propagation_parser_to_validator" in code
        assert "ValueError" in code

    def test_build_integration_prompt(self) -> None:
        source = NodeInterface(
            node_id=uuid4(),
            node_name="Auth",
            file_path="src/auth.py",
            exports=["login"],
            description="Auth module",
        )
        target = NodeInterface(
            node_id=uuid4(),
            node_name="Session",
            file_path="src/session.py",
            exports=["create_session"],
            description="Session module",
        )
        edge = DependencyEdge(
            source_id=source.node_id,
            target_id=target.node_id,
            shared_symbols=["Token"],
        )
        config = IntegrationGeneratorConfig()
        messages = build_integration_prompt(
            source, target, edge, IntegrationTestType.DATA_FLOW, config
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Auth" in messages[1]["content"]
        assert "Session" in messages[1]["content"]
        assert "Token" in messages[1]["content"]
        assert "data_flow" in messages[1]["content"]


# --------------------------------------------------------------------------- #
#                         Test: IntegrationGenerator                           #
# --------------------------------------------------------------------------- #


class TestIntegrationGenerator:
    """Test IntegrationGenerator orchestration."""

    def setup_method(self) -> None:
        self.source = NodeInterface(
            node_id=uuid4(),
            node_name="AuthModule",
            file_path="src/auth.py",
            exports=["login", "logout"],
        )
        self.target = NodeInterface(
            node_id=uuid4(),
            node_name="SessionManager",
            file_path="src/session.py",
            exports=["create_session"],
        )
        self.edge = DependencyEdge(
            source_id=self.source.node_id,
            target_id=self.target.node_id,
            shared_symbols=["Token"],
        )

    def test_generate_for_edge_template(self) -> None:
        """Test template-based generation (no LLM)."""
        gen = IntegrationGenerator()
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        assert len(cases) == 2  # data_flow + error_propagation
        types = {c.test_type for c in cases}
        assert IntegrationTestType.DATA_FLOW in types
        assert IntegrationTestType.ERROR_PROPAGATION in types

    def test_generate_for_edge_only_data_flow(self) -> None:
        config = IntegrationGeneratorConfig(include_error_tests=False)
        gen = IntegrationGenerator(config=config)
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        assert len(cases) == 1
        assert cases[0].test_type == IntegrationTestType.DATA_FLOW

    def test_generate_for_edge_only_error_tests(self) -> None:
        config = IntegrationGeneratorConfig(include_data_flow=False)
        gen = IntegrationGenerator(config=config)
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        assert len(cases) == 1
        assert cases[0].test_type == IntegrationTestType.ERROR_PROPAGATION

    def test_generate_for_edge_max_tests(self) -> None:
        config = IntegrationGeneratorConfig(max_tests_per_edge=1)
        gen = IntegrationGenerator(config=config)
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        assert len(cases) <= 1

    def test_generate_for_edge_with_llm(self) -> None:
        llm = MockLLM(response="def test_llm_gen(): assert True")
        gen = IntegrationGenerator(llm=llm)
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        assert len(cases) == 2
        # LLM should have been called twice (data_flow + error_propagation)
        assert len(llm.calls) == 2
        assert "def test_llm_gen(): assert True" in cases[0].test_code

    def test_generate_for_edge_llm_fallback(self) -> None:
        """When LLM fails, should fall back to templates."""
        llm = MockLLM()
        llm.set_failure(True)
        gen = IntegrationGenerator(llm=llm)
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        assert len(cases) == 2
        # Despite failure, we still get template-based tests
        assert "def test_data_flow" in cases[0].test_code

    def test_generate_suite_single_edge(self) -> None:
        gen = IntegrationGenerator()
        suite = gen.generate_suite([(self.source, self.target, self.edge)])
        assert isinstance(suite, IntegrationTestSuite)
        assert suite.total_generated == 2
        assert len(suite.test_cases) == 2
        assert "import pytest" in suite.imports_block

    def test_generate_suite_multiple_edges(self) -> None:
        gen = IntegrationGenerator()
        source2 = NodeInterface(
            node_id=uuid4(), node_name="Logger", exports=["log"]
        )
        target2 = NodeInterface(
            node_id=uuid4(), node_name="Audit", exports=["record"]
        )
        edge2 = DependencyEdge(
            source_id=source2.node_id, target_id=target2.node_id
        )
        suite = gen.generate_suite([
            (self.source, self.target, self.edge),
            (source2, target2, edge2),
        ])
        assert suite.total_generated == 4
        assert len(suite.test_cases) == 4

    def test_generate_suite_empty(self) -> None:
        gen = IntegrationGenerator()
        suite = gen.generate_suite([])
        assert suite.total_generated == 0
        assert suite.test_cases == []

    def test_suite_render(self) -> None:
        gen = IntegrationGenerator()
        suite = gen.generate_suite([(self.source, self.target, self.edge)])
        rendered = suite.render()
        assert "def test_data_flow" in rendered
        assert "def test_error_propagation" in rendered

    def test_test_case_dependencies(self) -> None:
        gen = IntegrationGenerator()
        cases = gen.generate_for_edge(self.source, self.target, self.edge)
        for case in cases:
            assert self.source.node_id in case.dependencies
            assert self.target.node_id in case.dependencies

    def test_config_property(self) -> None:
        config = IntegrationGeneratorConfig(max_tests_per_edge=5)
        gen = IntegrationGenerator(config=config)
        assert gen.config is config

    def test_llm_model_passed_correctly(self) -> None:
        llm = MockLLM()
        config = IntegrationGeneratorConfig(model_name="custom-model")
        gen = IntegrationGenerator(config=config, llm=llm)
        gen.generate_for_edge(self.source, self.target, self.edge)
        assert llm.calls[0]["model"] == "custom-model"

    def test_llm_temperature_passed(self) -> None:
        llm = MockLLM()
        config = IntegrationGeneratorConfig(temperature=0.8)
        gen = IntegrationGenerator(config=config, llm=llm)
        gen.generate_for_edge(self.source, self.target, self.edge)
        assert llm.calls[0]["temperature"] == 0.8
