"""Functional tests for RPGNode schema.

These tests simulate real-world usage patterns for the RPGNode model,
exercising creation, validation, and serialization in realistic scenarios.
"""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cobuilder.repomap.models.enums import (
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from cobuilder.repomap.models.node import RPGNode


pytestmark = pytest.mark.functional


class TestModuleNodeCreation:
    """Functional: Create MODULE nodes as top-level containers."""

    def test_create_module_no_parent(self) -> None:
        """Create MODULE node - assert level, no parent."""
        module = RPGNode(
            name="authentication",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="src/auth",
            docstring="Authentication module handling login and registration",
        )
        assert module.level == NodeLevel.MODULE
        assert module.parent_id is None
        assert module.folder_path == "src/auth"
        assert module.docstring is not None

    def test_create_multiple_independent_modules(self) -> None:
        """Create multiple independent MODULE nodes."""
        modules = [
            RPGNode(
                name=name,
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=f"src/{name}",
            )
            for name in ["auth", "payment", "analytics", "notifications"]
        ]
        assert len(modules) == 4
        assert all(m.level == NodeLevel.MODULE for m in modules)
        assert len({m.id for m in modules}) == 4  # All unique IDs


class TestFeatureNodeWithParent:
    """Functional: Create FEATURE nodes with parent relationships."""

    def test_create_feature_with_parent(self) -> None:
        """Create FEATURE node with parent → assert parent_id set."""
        module = RPGNode(
            name="auth",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        feature = RPGNode(
            name="login",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            parent_id=module.id,
            folder_path="src/auth",
            file_path="src/auth/login.py",
        )
        assert feature.parent_id == module.id
        assert feature.level == NodeLevel.FEATURE

    def test_create_component_hierarchy(self) -> None:
        """Build a MODULE → COMPONENT → FEATURE hierarchy."""
        module = RPGNode(
            name="payment",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="src/payment",
        )
        component = RPGNode(
            name="stripe_integration",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FOLDER_AUGMENTED,
            parent_id=module.id,
            folder_path="src/payment/stripe",
        )
        feature = RPGNode(
            name="process_charge",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            parent_id=component.id,
            folder_path="src/payment/stripe",
            file_path="src/payment/stripe/charges.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def process_charge(amount: float, currency: str) -> bool",
        )

        assert module.parent_id is None
        assert component.parent_id == module.id
        assert feature.parent_id == component.id


class TestFunctionAugmentedNode:
    """Functional: Create FUNCTION_AUGMENTED nodes with required fields."""

    def test_function_augmented_requires_interface_type_and_signature(self) -> None:
        """Create FUNCTION_AUGMENTED node → require interface_type, signature."""
        node = RPGNode(
            name="hash_password",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/utils.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def hash_password(password: str, salt: Optional[str] = None) -> str",
            docstring="Hash a password using bcrypt with optional custom salt",
        )
        assert node.interface_type == InterfaceType.FUNCTION
        assert node.signature is not None
        assert "hash_password" in node.signature

    def test_function_augmented_with_implementation(self) -> None:
        """FUNCTION_AUGMENTED with full implementation code."""
        impl = (
            "import bcrypt\n\n"
            "def hash_password(password: str, salt: Optional[str] = None) -> str:\n"
            "    if salt is None:\n"
            "        salt = bcrypt.gensalt()\n"
            "    return bcrypt.hashpw(password.encode(), salt).decode()\n"
        )
        test = (
            "def test_hash_password():\n"
            "    hashed = hash_password('secret')\n"
            "    assert hashed != 'secret'\n"
            "    assert len(hashed) > 0\n"
        )
        node = RPGNode(
            name="hash_password",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/utils.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def hash_password(password: str, salt: Optional[str] = None) -> str",
            docstring="Hash a password using bcrypt",
            implementation=impl,
            test_code=test,
            test_status=TestStatus.PASSED,
            serena_validated=True,
        )
        assert node.implementation is not None
        assert "bcrypt" in node.implementation
        assert node.test_status == TestStatus.PASSED
        assert node.serena_validated is True


class TestInvalidFilePath:
    """Functional: Validate file_path/folder_path constraints."""

    def test_invalid_file_path_not_under_folder(self) -> None:
        """Attempt invalid file_path (not under folder_path) → ValidationError."""
        with pytest.raises(ValidationError, match="file_path.*must start with folder_path"):
            RPGNode(
                name="misplaced_handler",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FILE_AUGMENTED,
                folder_path="src/auth",
                file_path="src/payment/handler.py",
            )

    def test_file_path_matching_folder_succeeds(self) -> None:
        """file_path exactly matching folder_path prefix succeeds."""
        node = RPGNode(
            name="handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/handler.py",
        )
        assert node.file_path.startswith(node.folder_path)

    def test_deeply_nested_file_path(self) -> None:
        """file_path deeply nested under folder_path succeeds."""
        node = RPGNode(
            name="deep_handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src",
            file_path="src/auth/handlers/v2/login/handler.py",
        )
        assert node.file_path.startswith(node.folder_path)


class TestRealisticGraphScenario:
    """Functional: Build a realistic small RPG scenario."""

    def test_build_auth_module_tree(self) -> None:
        """Build a realistic authentication module tree with 10+ nodes."""
        # Module
        auth_module = RPGNode(
            name="authentication",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="src/auth",
            docstring="Authentication and authorization module",
        )

        # Components
        user_mgmt = RPGNode(
            name="user_management",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FOLDER_AUGMENTED,
            parent_id=auth_module.id,
            folder_path="src/auth/users",
        )
        session_mgmt = RPGNode(
            name="session_management",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FOLDER_AUGMENTED,
            parent_id=auth_module.id,
            folder_path="src/auth/sessions",
        )

        # Features under user_management
        features = [
            RPGNode(
                name="create_user",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                parent_id=user_mgmt.id,
                folder_path="src/auth/users",
                file_path="src/auth/users/crud.py",
                interface_type=InterfaceType.FUNCTION,
                signature="def create_user(username: str, email: str, password: str) -> User",
            ),
            RPGNode(
                name="authenticate_user",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                parent_id=user_mgmt.id,
                folder_path="src/auth/users",
                file_path="src/auth/users/auth.py",
                interface_type=InterfaceType.FUNCTION,
                signature="def authenticate_user(username: str, password: str) -> Optional[User]",
            ),
            RPGNode(
                name="UserService",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                parent_id=user_mgmt.id,
                folder_path="src/auth/users",
                file_path="src/auth/users/service.py",
                interface_type=InterfaceType.CLASS,
                signature="class UserService",
            ),
        ]

        # Features under session_management
        session_features = [
            RPGNode(
                name="create_session",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                parent_id=session_mgmt.id,
                folder_path="src/auth/sessions",
                file_path="src/auth/sessions/manager.py",
                interface_type=InterfaceType.FUNCTION,
                signature="def create_session(user_id: UUID) -> Session",
            ),
            RPGNode(
                name="validate_session",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                parent_id=session_mgmt.id,
                folder_path="src/auth/sessions",
                file_path="src/auth/sessions/manager.py",
                interface_type=InterfaceType.FUNCTION,
                signature="def validate_session(token: str) -> bool",
            ),
        ]

        all_nodes = [auth_module, user_mgmt, session_mgmt] + features + session_features

        # Verify all unique IDs
        ids = {n.id for n in all_nodes}
        assert len(ids) == len(all_nodes)

        # Verify hierarchy
        assert auth_module.parent_id is None
        assert user_mgmt.parent_id == auth_module.id
        assert session_mgmt.parent_id == auth_module.id
        assert all(f.parent_id == user_mgmt.id for f in features)
        assert all(f.parent_id == session_mgmt.id for f in session_features)

        # All function augmented have interface_type and signature
        function_nodes = [n for n in all_nodes if n.node_type == NodeType.FUNCTION_AUGMENTED]
        assert len(function_nodes) == 5
        assert all(n.interface_type is not None for n in function_nodes)
        assert all(n.signature is not None for n in function_nodes)

    def test_serialize_deserialize_full_tree(self) -> None:
        """Build tree, serialize all nodes, deserialize, verify equality."""
        nodes = []
        parent = RPGNode(
            name="root_module",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="src",
            metadata={"created_by": "test"},
        )
        nodes.append(parent)

        for i in range(5):
            comp = RPGNode(
                name=f"component_{i}",
                level=NodeLevel.COMPONENT,
                node_type=NodeType.FOLDER_AUGMENTED,
                parent_id=parent.id,
                folder_path=f"src/comp_{i}",
            )
            nodes.append(comp)

            for j in range(3):
                feat = RPGNode(
                    name=f"feature_{i}_{j}",
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTION_AUGMENTED,
                    parent_id=comp.id,
                    folder_path=f"src/comp_{i}",
                    file_path=f"src/comp_{i}/feat_{j}.py",
                    interface_type=InterfaceType.FUNCTION,
                    signature=f"def feature_{i}_{j}() -> None",
                    test_status=TestStatus.PENDING,
                )
                nodes.append(feat)

        # 1 module + 5 components + 15 features = 21 nodes
        assert len(nodes) == 21

        # Serialize each node to JSON and deserialize
        for node in nodes:
            json_str = node.model_dump_json()
            restored = RPGNode.model_validate_json(json_str)
            assert node == restored, f"Round-trip failed for node '{node.name}'"

    def test_batch_json_serialize_deserialize(self) -> None:
        """Serialize list of nodes as JSON array, deserialize, verify."""
        nodes = [
            RPGNode(
                name=f"node_{i}",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                metadata={"index": i},
            )
            for i in range(50)
        ]

        # Serialize as JSON array
        json_str = json.dumps([n.model_dump(mode="json") for n in nodes])
        data = json.loads(json_str)
        restored = [RPGNode.model_validate(item) for item in data]

        assert len(restored) == 50
        for orig, rest in zip(nodes, restored):
            assert orig == rest


class TestNodeStatusWorkflow:
    """Functional: Simulate a node going through its lifecycle."""

    def test_node_lifecycle(self) -> None:
        """Node starts PENDING, gets implementation, passes tests, gets validated."""
        node = RPGNode(
            name="process_order",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/orders",
            file_path="src/orders/processor.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def process_order(order_id: UUID) -> OrderResult",
        )

        # Initial state
        assert node.test_status == TestStatus.PENDING
        assert node.serena_validated is False
        assert node.implementation is None

        # Add implementation
        node.implementation = "def process_order(order_id: UUID) -> OrderResult:\n    return OrderResult(success=True)"
        assert node.implementation is not None

        # Add test
        node.test_code = "def test_process_order():\n    result = process_order(uuid4())\n    assert result.success"

        # Tests pass
        node.test_status = TestStatus.PASSED
        assert node.test_status == TestStatus.PASSED

        # Serena validates
        node.serena_validated = True
        assert node.serena_validated is True

        # Add actual dependencies
        dep = uuid4()
        node.actual_dependencies = [dep]
        assert len(node.actual_dependencies) == 1

    def test_node_test_failure_and_recovery(self) -> None:
        """Node fails tests, gets fixed, passes."""
        node = RPGNode(
            name="validate_input",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/utils",
            file_path="src/utils/validators.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def validate_input(data: dict) -> bool",
        )

        # Tests fail
        node.test_status = TestStatus.FAILED
        assert node.test_status == TestStatus.FAILED

        # Fix and re-run
        node.test_status = TestStatus.PASSED
        assert node.test_status == TestStatus.PASSED
