"""Unit tests for RPGEdge schema."""

import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType


class TestRPGEdgeCreation:
    """Test valid RPGEdge creation for each edge_type."""

    def test_create_hierarchy_edge(self) -> None:
        """Create a HIERARCHY edge between two nodes."""
        source = uuid4()
        target = uuid4()
        edge = RPGEdge(
            source_id=source,
            target_id=target,
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge.source_id == source
        assert edge.target_id == target
        assert edge.edge_type == EdgeType.HIERARCHY
        assert isinstance(edge.id, UUID)
        assert edge.data_id is None
        assert edge.data_type is None
        assert edge.transformation is None
        assert edge.validated is False

    def test_create_data_flow_edge(self) -> None:
        """Create a DATA_FLOW edge with data fields."""
        source = uuid4()
        target = uuid4()
        edge = RPGEdge(
            source_id=source,
            target_id=target,
            edge_type=EdgeType.DATA_FLOW,
            data_id="user_token",
            data_type="str",
            transformation="JWT encoding",
        )
        assert edge.edge_type == EdgeType.DATA_FLOW
        assert edge.data_id == "user_token"
        assert edge.data_type == "str"
        assert edge.transformation == "JWT encoding"

    def test_create_ordering_edge(self) -> None:
        """Create an ORDERING edge."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.ORDERING,
        )
        assert edge.edge_type == EdgeType.ORDERING

    def test_create_inheritance_edge(self) -> None:
        """Create an INHERITANCE edge."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.INHERITANCE,
        )
        assert edge.edge_type == EdgeType.INHERITANCE

    def test_create_invocation_edge(self) -> None:
        """Create an INVOCATION edge."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.INVOCATION,
        )
        assert edge.edge_type == EdgeType.INVOCATION

    @pytest.mark.parametrize("edge_type", list(EdgeType))
    def test_create_all_edge_types(self, edge_type: EdgeType) -> None:
        """Test creation with each EdgeType value."""
        kwargs: dict = {
            "source_id": uuid4(),
            "target_id": uuid4(),
            "edge_type": edge_type,
        }
        if edge_type == EdgeType.DATA_FLOW:
            kwargs["data_id"] = "test_data"
            kwargs["data_type"] = "str"
        edge = RPGEdge(**kwargs)
        assert edge.edge_type == edge_type

    def test_create_data_flow_with_partial_data_fields(self) -> None:
        """DATA_FLOW edge with only data_id (no data_type or transformation) succeeds."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
            data_id="user_id",
        )
        assert edge.data_id == "user_id"
        assert edge.data_type is None
        assert edge.transformation is None

    def test_create_data_flow_without_data_fields(self) -> None:
        """DATA_FLOW edge without any data fields succeeds."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
        )
        assert edge.edge_type == EdgeType.DATA_FLOW
        assert edge.data_id is None

    def test_create_with_validated_true(self) -> None:
        """Create edge with validated=True."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
            validated=True,
        )
        assert edge.validated is True

    def test_auto_generated_uuid(self) -> None:
        """ID is auto-generated when not provided."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        assert isinstance(edge.id, UUID)

    def test_uuid_uniqueness(self) -> None:
        """Multiple edges get unique IDs."""
        edges = [
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=EdgeType.HIERARCHY,
            )
            for _ in range(100)
        ]
        ids = {edge.id for edge in edges}
        assert len(ids) == 100

    def test_explicit_uuid(self) -> None:
        """Explicit UUID can be set."""
        custom_id = uuid4()
        edge = RPGEdge(
            id=custom_id,
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge.id == custom_id


class TestRPGEdgeSelfLoopPrevention:
    """Test self-loop prevention (source_id == target_id)."""

    def test_self_loop_raises(self) -> None:
        """Same source_id and target_id raises ValidationError."""
        same_id = uuid4()
        with pytest.raises(ValidationError, match="Self-loop detected"):
            RPGEdge(
                source_id=same_id,
                target_id=same_id,
                edge_type=EdgeType.HIERARCHY,
            )

    def test_self_loop_raises_for_all_edge_types(self) -> None:
        """Self-loop raises for every edge type."""
        same_id = uuid4()
        for edge_type in EdgeType:
            with pytest.raises(ValidationError, match="Self-loop detected"):
                RPGEdge(
                    source_id=same_id,
                    target_id=same_id,
                    edge_type=edge_type,
                )


class TestRPGEdgeDataFieldConstraints:
    """Test data field constraints (only valid for DATA_FLOW)."""

    def test_hierarchy_with_data_id_raises(self) -> None:
        """HIERARCHY edge with data_id raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="data_id.*only valid for DATA_FLOW",
        ):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=EdgeType.HIERARCHY,
                data_id="some_data",
            )

    def test_ordering_with_data_type_raises(self) -> None:
        """ORDERING edge with data_type raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="only valid for DATA_FLOW",
        ):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=EdgeType.ORDERING,
                data_type="int",
            )

    def test_inheritance_with_transformation_raises(self) -> None:
        """INHERITANCE edge with transformation raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="only valid for DATA_FLOW",
        ):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=EdgeType.INHERITANCE,
                transformation="some transform",
            )

    def test_invocation_with_data_id_raises(self) -> None:
        """INVOCATION edge with data_id raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="only valid for DATA_FLOW",
        ):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=EdgeType.INVOCATION,
                data_id="call_result",
            )

    @pytest.mark.parametrize(
        "edge_type",
        [EdgeType.HIERARCHY, EdgeType.ORDERING, EdgeType.INHERITANCE, EdgeType.INVOCATION],
    )
    def test_non_data_flow_with_all_data_fields_raises(self, edge_type: EdgeType) -> None:
        """Non-DATA_FLOW edges with all data fields raise ValidationError."""
        with pytest.raises(ValidationError, match="only valid for DATA_FLOW"):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=edge_type,
                data_id="data",
                data_type="str",
                transformation="transform",
            )


class TestRPGEdgeSerialization:
    """Test JSON serialization round-trip."""

    def test_json_round_trip_minimal(self) -> None:
        """Minimal edge survives JSON round-trip."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        json_str = edge.model_dump_json()
        restored = RPGEdge.model_validate_json(json_str)
        assert edge == restored

    def test_json_round_trip_data_flow(self) -> None:
        """DATA_FLOW edge with all data fields survives round-trip."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
            data_id="hashed_password",
            data_type="str",
            transformation="bcrypt hash",
            validated=True,
        )
        json_str = edge.model_dump_json()
        restored = RPGEdge.model_validate_json(json_str)
        assert edge == restored

    def test_json_dict_round_trip(self) -> None:
        """Edge survives model_dump -> model_validate round-trip."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.INVOCATION,
        )
        data = edge.model_dump()
        restored = RPGEdge.model_validate(data)
        assert edge == restored

    def test_json_string_parsing(self) -> None:
        """Parse edge from raw JSON string."""
        edge_id = uuid4()
        source_id = uuid4()
        target_id = uuid4()
        json_str = json.dumps({
            "id": str(edge_id),
            "source_id": str(source_id),
            "target_id": str(target_id),
            "edge_type": "HIERARCHY",
            "data_id": None,
            "data_type": None,
            "transformation": None,
            "validated": False,
        })
        edge = RPGEdge.model_validate_json(json_str)
        assert edge.id == edge_id
        assert edge.source_id == source_id
        assert edge.target_id == target_id

    def test_serialized_json_valid(self) -> None:
        """Serialized output is valid JSON."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
            data_id="test",
        )
        json_str = edge.model_dump_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "source_id" in parsed
        assert "edge_type" in parsed

    def test_serialization_preserves_uuid_format(self) -> None:
        """UUIDs are serialized as strings."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        data = edge.model_dump(mode="json")
        assert isinstance(data["id"], str)
        assert isinstance(data["source_id"], str)
        assert isinstance(data["target_id"], str)
        # Verify they can be parsed back
        UUID(data["id"])
        UUID(data["source_id"])
        UUID(data["target_id"])

    def test_serialization_preserves_enum_values(self) -> None:
        """Enums are serialized as their string values."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
        )
        data = edge.model_dump(mode="json")
        assert data["edge_type"] == "DATA_FLOW"

    @pytest.mark.parametrize("edge_type", list(EdgeType))
    def test_json_round_trip_all_edge_types(self, edge_type: EdgeType) -> None:
        """All edge types survive JSON round-trip."""
        kwargs: dict = {
            "source_id": uuid4(),
            "target_id": uuid4(),
            "edge_type": edge_type,
        }
        if edge_type == EdgeType.DATA_FLOW:
            kwargs["data_id"] = "test"
            kwargs["data_type"] = "str"
            kwargs["transformation"] = "identity"
        edge = RPGEdge(**kwargs)
        json_str = edge.model_dump_json()
        restored = RPGEdge.model_validate_json(json_str)
        assert edge == restored


class TestRPGEdgeEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_assignment(self) -> None:
        """Validate assignment is enforced for mutable fields."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        edge.validated = True
        assert edge.validated is True

    def test_invalid_edge_type_raises(self) -> None:
        """Invalid edge_type raises ValidationError."""
        with pytest.raises(ValidationError):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type="INVALID",  # type: ignore[arg-type]
            )

    def test_missing_source_id_raises(self) -> None:
        """Missing source_id raises ValidationError."""
        with pytest.raises(ValidationError):
            RPGEdge(
                target_id=uuid4(),
                edge_type=EdgeType.HIERARCHY,
            )  # type: ignore[call-arg]

    def test_missing_target_id_raises(self) -> None:
        """Missing target_id raises ValidationError."""
        with pytest.raises(ValidationError):
            RPGEdge(
                source_id=uuid4(),
                edge_type=EdgeType.HIERARCHY,
            )  # type: ignore[call-arg]

    def test_missing_edge_type_raises(self) -> None:
        """Missing edge_type raises ValidationError."""
        with pytest.raises(ValidationError):
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
            )  # type: ignore[call-arg]

    def test_equality_different_ids(self) -> None:
        """Edges with different IDs are not equal."""
        source = uuid4()
        target = uuid4()
        edge1 = RPGEdge(
            source_id=source,
            target_id=target,
            edge_type=EdgeType.HIERARCHY,
        )
        edge2 = RPGEdge(
            source_id=source,
            target_id=target,
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge1 != edge2  # Different auto-generated IDs

    def test_equality_same_fields(self) -> None:
        """Edges with identical fields (including ID) are equal."""
        edge_id = uuid4()
        source = uuid4()
        target = uuid4()
        edge1 = RPGEdge(
            id=edge_id,
            source_id=source,
            target_id=target,
            edge_type=EdgeType.HIERARCHY,
        )
        edge2 = RPGEdge(
            id=edge_id,
            source_id=source,
            target_id=target,
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge1 == edge2

    def test_not_equal_to_non_edge(self) -> None:
        """Edge is not equal to non-RPGEdge object."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge != "not an edge"
        assert edge != 42
        assert edge != None  # noqa: E711

    def test_hash_based_on_id(self) -> None:
        """Hash is based on the edge ID."""
        edge_id = uuid4()
        edge = RPGEdge(
            id=edge_id,
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.HIERARCHY,
        )
        assert hash(edge) == hash(edge_id)

    def test_data_flow_edge_full_data(self) -> None:
        """DATA_FLOW edge with all data fields set."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
            data_id="user_data",
            data_type="Dict[str, Any]",
            transformation="serialize to JSON, encrypt, base64 encode",
            validated=True,
        )
        assert edge.data_id == "user_data"
        assert edge.data_type == "Dict[str, Any]"
        assert "encrypt" in edge.transformation
