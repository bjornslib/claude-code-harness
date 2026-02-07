"""Unit tests for RPGNode schema."""

import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from zerorepo.models.enums import (
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from zerorepo.models.node import RPGNode


class TestRPGNodeCreation:
    """Test valid RPGNode creation for each level/type combination."""

    def test_create_module_functionality(self) -> None:
        """Create a MODULE/FUNCTIONALITY node with minimal fields."""
        node = RPGNode(
            name="authentication",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert node.name == "authentication"
        assert node.level == NodeLevel.MODULE
        assert node.node_type == NodeType.FUNCTIONALITY
        assert isinstance(node.id, UUID)
        assert node.parent_id is None
        assert node.test_status == TestStatus.PENDING
        assert node.serena_validated is False
        assert node.actual_dependencies == []
        assert node.metadata == {}

    def test_create_component_folder_augmented(self) -> None:
        """Create a COMPONENT/FOLDER_AUGMENTED node."""
        parent_id = uuid4()
        node = RPGNode(
            name="user_management",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FOLDER_AUGMENTED,
            parent_id=parent_id,
            folder_path="src/auth/users",
        )
        assert node.level == NodeLevel.COMPONENT
        assert node.node_type == NodeType.FOLDER_AUGMENTED
        assert node.parent_id == parent_id
        assert node.folder_path == "src/auth/users"

    def test_create_feature_file_augmented(self) -> None:
        """Create a FEATURE/FILE_AUGMENTED node."""
        node = RPGNode(
            name="login_handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/login.py",
        )
        assert node.level == NodeLevel.FEATURE
        assert node.node_type == NodeType.FILE_AUGMENTED
        assert node.file_path == "src/auth/login.py"

    def test_create_feature_function_augmented(self) -> None:
        """Create a FEATURE/FUNCTION_AUGMENTED node - requires interface_type and signature."""
        node = RPGNode(
            name="hash_password",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/utils.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def hash_password(password: str) -> str",
            docstring="Hash a password using bcrypt",
        )
        assert node.node_type == NodeType.FUNCTION_AUGMENTED
        assert node.interface_type == InterfaceType.FUNCTION
        assert node.signature == "def hash_password(password: str) -> str"

    def test_create_function_augmented_class(self) -> None:
        """Create a FUNCTION_AUGMENTED node with CLASS interface_type."""
        node = RPGNode(
            name="UserService",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.CLASS,
            signature="class UserService",
            folder_path="src/auth",
            file_path="src/auth/service.py",
        )
        assert node.interface_type == InterfaceType.CLASS

    def test_create_function_augmented_method(self) -> None:
        """Create a FUNCTION_AUGMENTED node with METHOD interface_type."""
        node = RPGNode(
            name="authenticate",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            interface_type=InterfaceType.METHOD,
            signature="def authenticate(self, username: str, password: str) -> bool",
            folder_path="src/auth",
            file_path="src/auth/service.py",
        )
        assert node.interface_type == InterfaceType.METHOD

    def test_create_with_all_fields(self) -> None:
        """Create a node with every field populated."""
        parent_id = uuid4()
        dep_id = uuid4()
        node = RPGNode(
            name="process_payment",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            parent_id=parent_id,
            folder_path="src/payment",
            file_path="src/payment/processor.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def process_payment(amount: float) -> bool",
            docstring="Process a payment transaction",
            implementation="def process_payment(amount: float) -> bool:\n    return True",
            test_code="def test_process_payment():\n    assert process_payment(10.0)",
            test_status=TestStatus.PASSED,
            serena_validated=True,
            actual_dependencies=[dep_id],
            metadata={"complexity": "medium", "priority": 1},
        )
        assert node.parent_id == parent_id
        assert node.implementation is not None
        assert node.test_status == TestStatus.PASSED
        assert node.serena_validated is True
        assert len(node.actual_dependencies) == 1
        assert node.metadata["complexity"] == "medium"

    @pytest.mark.parametrize("level", list(NodeLevel))
    def test_create_all_levels(self, level: NodeLevel) -> None:
        """Test creation with each NodeLevel value."""
        kwargs: dict = {
            "name": f"test_{level.value.lower()}",
            "level": level,
            "node_type": NodeType.FUNCTIONALITY,
        }
        node = RPGNode(**kwargs)
        assert node.level == level

    @pytest.mark.parametrize(
        "node_type",
        [NodeType.FUNCTIONALITY, NodeType.FOLDER_AUGMENTED, NodeType.FILE_AUGMENTED],
    )
    def test_create_non_function_augmented_types(self, node_type: NodeType) -> None:
        """Test creation with non-FUNCTION_AUGMENTED types (no interface_type needed)."""
        node = RPGNode(
            name=f"test_{node_type.value.lower()}",
            level=NodeLevel.MODULE,
            node_type=node_type,
        )
        assert node.node_type == node_type
        assert node.interface_type is None


class TestRPGNodeUUIDUniqueness:
    """Test UUID auto-generation and uniqueness."""

    def test_auto_generated_uuid(self) -> None:
        """ID is auto-generated when not provided."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert isinstance(node.id, UUID)

    def test_uuid_uniqueness(self) -> None:
        """Multiple nodes get unique IDs."""
        nodes = [
            RPGNode(
                name=f"node_{i}",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
            for i in range(100)
        ]
        ids = {node.id for node in nodes}
        assert len(ids) == 100

    def test_explicit_uuid(self) -> None:
        """Explicit UUID can be set."""
        custom_id = uuid4()
        node = RPGNode(
            id=custom_id,
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert node.id == custom_id


class TestRPGNodeValidationErrors:
    """Test validation errors for invalid field combinations."""

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValidationError."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            RPGNode(
                name="",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )

    def test_whitespace_only_name_raises(self) -> None:
        """Whitespace-only name raises ValidationError (after strip)."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            RPGNode(
                name="   ",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )

    def test_name_too_long_raises(self) -> None:
        """Name exceeding 200 chars raises ValidationError."""
        with pytest.raises(ValidationError, match="String should have at most 200 characters"):
            RPGNode(
                name="x" * 201,
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )

    def test_name_max_length_ok(self) -> None:
        """Name at exactly 200 chars succeeds."""
        node = RPGNode(
            name="x" * 200,
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert len(node.name) == 200

    def test_invalid_level_raises(self) -> None:
        """Invalid level value raises ValidationError."""
        with pytest.raises(ValidationError):
            RPGNode(
                name="test",
                level="INVALID",  # type: ignore[arg-type]
                node_type=NodeType.FUNCTIONALITY,
            )

    def test_invalid_node_type_raises(self) -> None:
        """Invalid node_type value raises ValidationError."""
        with pytest.raises(ValidationError):
            RPGNode(
                name="test",
                level=NodeLevel.MODULE,
                node_type="INVALID",  # type: ignore[arg-type]
                )

    def test_function_augmented_without_interface_type_raises(self) -> None:
        """FUNCTION_AUGMENTED node without interface_type raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="interface_type is required when node_type is FUNCTION_AUGMENTED",
        ):
            RPGNode(
                name="test_func",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
            )

    def test_interface_type_without_signature_raises(self) -> None:
        """Setting interface_type without signature raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="signature is required when interface_type is set",
        ):
            RPGNode(
                name="test_func",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                interface_type=InterfaceType.FUNCTION,
            )

    def test_implementation_without_file_path_raises(self) -> None:
        """Setting implementation without file_path raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="implementation cannot be set without file_path",
        ):
            RPGNode(
                name="test_func",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                interface_type=InterfaceType.FUNCTION,
                signature="def test() -> None",
                implementation="def test() -> None:\n    pass",
            )

    def test_file_path_not_under_folder_path_raises(self) -> None:
        """file_path not starting with folder_path raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="file_path.*must start with folder_path",
        ):
            RPGNode(
                name="test",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FILE_AUGMENTED,
                folder_path="src/auth",
                file_path="src/payment/handler.py",
            )

    def test_absolute_folder_path_raises(self) -> None:
        """Absolute folder_path raises ValidationError."""
        with pytest.raises(ValidationError, match="Path must be relative"):
            RPGNode(
                name="test",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path="/absolute/path",
            )

    def test_absolute_file_path_raises(self) -> None:
        """Absolute file_path raises ValidationError."""
        with pytest.raises(ValidationError, match="Path must be relative"):
            RPGNode(
                name="test",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FILE_AUGMENTED,
                folder_path="src",
                file_path="/absolute/file.py",
            )


class TestRPGNodePathValidation:
    """Test path validation between folder_path and file_path."""

    def test_file_under_folder_succeeds(self) -> None:
        """file_path starting with folder_path succeeds."""
        node = RPGNode(
            name="handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/handler.py",
        )
        assert node.file_path == "src/auth/handler.py"

    def test_file_in_subfolder_succeeds(self) -> None:
        """file_path in a subfolder of folder_path succeeds."""
        node = RPGNode(
            name="handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/handlers/login.py",
        )
        assert node.file_path == "src/auth/handlers/login.py"

    def test_file_path_without_folder_path_succeeds(self) -> None:
        """file_path without folder_path succeeds (no constraint to check)."""
        node = RPGNode(
            name="handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            file_path="src/auth/handler.py",
        )
        assert node.file_path == "src/auth/handler.py"
        assert node.folder_path is None

    def test_folder_path_without_file_path_succeeds(self) -> None:
        """folder_path without file_path succeeds."""
        node = RPGNode(
            name="auth",
            level=NodeLevel.MODULE,
            node_type=NodeType.FOLDER_AUGMENTED,
            folder_path="src/auth",
        )
        assert node.folder_path == "src/auth"
        assert node.file_path is None

    def test_backslash_path_normalized(self) -> None:
        """Windows-style backslash paths are normalized to forward slashes."""
        node = RPGNode(
            name="handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            folder_path="src\\auth",
            file_path="src\\auth\\handler.py",
        )
        assert node.folder_path == "src/auth"
        assert node.file_path == "src/auth/handler.py"


class TestRPGNodeSerialization:
    """Test JSON serialization round-trip without loss."""

    def test_json_round_trip_minimal(self) -> None:
        """Minimal node survives JSON round-trip."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        json_str = node.model_dump_json()
        restored = RPGNode.model_validate_json(json_str)
        assert node == restored

    def test_json_round_trip_full(self) -> None:
        """Fully populated node survives JSON round-trip."""
        dep_id = uuid4()
        node = RPGNode(
            name="hash_password",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            parent_id=uuid4(),
            folder_path="src/auth",
            file_path="src/auth/utils.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def hash_password(password: str) -> str",
            docstring="Hash a password",
            implementation="def hash_password(password: str) -> str:\n    return 'hashed'",
            test_code="def test_hash():\n    assert hash_password('x')",
            test_status=TestStatus.PASSED,
            serena_validated=True,
            actual_dependencies=[dep_id],
            metadata={"complexity": "low", "nested": {"key": "value"}},
        )
        json_str = node.model_dump_json()
        restored = RPGNode.model_validate_json(json_str)
        assert node == restored

    def test_json_dict_round_trip(self) -> None:
        """Node survives model_dump -> model_validate round-trip."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            metadata={"key": "value"},
        )
        data = node.model_dump()
        restored = RPGNode.model_validate(data)
        assert node == restored

    def test_json_string_parsing(self) -> None:
        """Parse node from raw JSON string."""
        node_id = uuid4()
        json_str = json.dumps({
            "id": str(node_id),
            "name": "test_from_json",
            "level": "MODULE",
            "node_type": "FUNCTIONALITY",
            "parent_id": None,
            "folder_path": None,
            "file_path": None,
            "interface_type": None,
            "signature": None,
            "docstring": None,
            "implementation": None,
            "test_code": None,
            "test_status": "PENDING",
            "serena_validated": False,
            "actual_dependencies": [],
            "metadata": {},
        })
        node = RPGNode.model_validate_json(json_str)
        assert node.id == node_id
        assert node.name == "test_from_json"

    def test_serialized_json_valid(self) -> None:
        """Serialized output is valid JSON."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        json_str = node.model_dump_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "level" in parsed

    def test_serialization_preserves_uuid_format(self) -> None:
        """UUIDs are serialized as strings."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        data = node.model_dump(mode="json")
        assert isinstance(data["id"], str)
        # Verify it can be parsed back to UUID
        UUID(data["id"])

    def test_serialization_preserves_enum_values(self) -> None:
        """Enums are serialized as their string values."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            test_status=TestStatus.FAILED,
        )
        data = node.model_dump(mode="json")
        assert data["level"] == "MODULE"
        assert data["node_type"] == "FUNCTIONALITY"
        assert data["test_status"] == "FAILED"


class TestRPGNodeEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_metadata_with_complex_types(self) -> None:
        """Metadata can contain nested complex structures."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            metadata={
                "list": [1, 2, 3],
                "nested": {"a": {"b": "c"}},
                "number": 42,
                "float": 3.14,
                "bool": True,
                "null": None,
            },
        )
        assert node.metadata["list"] == [1, 2, 3]
        assert node.metadata["nested"]["a"]["b"] == "c"

    def test_multiple_actual_dependencies(self) -> None:
        """Node can have multiple actual dependencies."""
        deps = [uuid4() for _ in range(5)]
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            actual_dependencies=deps,
        )
        assert len(node.actual_dependencies) == 5
        assert all(isinstance(d, UUID) for d in node.actual_dependencies)

    def test_name_with_special_characters(self) -> None:
        """Name can contain special characters."""
        node = RPGNode(
            name="auth_handler-v2.1 (deprecated)",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert node.name == "auth_handler-v2.1 (deprecated)"

    def test_name_stripped(self) -> None:
        """Leading/trailing whitespace stripped from name."""
        node = RPGNode(
            name="  test_name  ",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert node.name == "test_name"

    def test_validate_assignment(self) -> None:
        """Validate assignment is enforced for mutable fields."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        # Valid reassignment
        node.test_status = TestStatus.PASSED
        assert node.test_status == TestStatus.PASSED

        # Invalid reassignment triggers validation
        with pytest.raises(ValidationError):
            node.level = "INVALID"  # type: ignore[assignment]

    def test_test_status_defaults_to_pending(self) -> None:
        """Default test_status is PENDING."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        assert node.test_status == TestStatus.PENDING

    @pytest.mark.parametrize("status", list(TestStatus))
    def test_all_test_status_values(self, status: TestStatus) -> None:
        """All TestStatus values are valid."""
        node = RPGNode(
            name="test",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            test_status=status,
        )
        assert node.test_status == status
