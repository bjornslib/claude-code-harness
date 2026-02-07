"""Functional tests for RPGEdge schema.

These tests simulate real-world usage patterns for the RPGEdge model,
exercising creation and validation in realistic graph scenarios.
"""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.node import RPGNode


pytestmark = pytest.mark.functional


class TestHierarchyEdges:
    """Functional: Create HIERARCHY edges between nodes at different levels."""

    def test_hierarchy_edge_module_to_component(self) -> None:
        """Create HIERARCHY edge between MODULE and COMPONENT → assert edge_type."""
        module = RPGNode(
            name="auth",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
        )
        component = RPGNode(
            name="user_mgmt",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FOLDER_AUGMENTED,
            parent_id=module.id,
        )
        edge = RPGEdge(
            source_id=module.id,
            target_id=component.id,
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge.edge_type == EdgeType.HIERARCHY
        assert edge.source_id == module.id
        assert edge.target_id == component.id
        assert edge.data_id is None

    def test_hierarchy_edge_component_to_feature(self) -> None:
        """Create HIERARCHY edge between COMPONENT and FEATURE."""
        component_id = uuid4()
        feature = RPGNode(
            name="login_handler",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FILE_AUGMENTED,
            parent_id=component_id,
            folder_path="src/auth",
            file_path="src/auth/login.py",
        )
        edge = RPGEdge(
            source_id=component_id,
            target_id=feature.id,
            edge_type=EdgeType.HIERARCHY,
        )
        assert edge.edge_type == EdgeType.HIERARCHY


class TestDataFlowEdges:
    """Functional: Create DATA_FLOW edges with transformation metadata."""

    def test_data_flow_edge_with_transformation(self) -> None:
        """Create DATA_FLOW edge with transformation → assert all data fields set."""
        source_id = uuid4()
        target_id = uuid4()
        edge = RPGEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=EdgeType.DATA_FLOW,
            data_id="hashed_password",
            data_type="str",
            transformation="bcrypt hash with salt",
        )
        assert edge.data_id == "hashed_password"
        assert edge.data_type == "str"
        assert edge.transformation == "bcrypt hash with salt"
        assert edge.edge_type == EdgeType.DATA_FLOW

    def test_data_flow_pipeline(self) -> None:
        """Build a data flow pipeline: input → process → output."""
        input_node = uuid4()
        process_node = uuid4()
        output_node = uuid4()

        edge1 = RPGEdge(
            source_id=input_node,
            target_id=process_node,
            edge_type=EdgeType.DATA_FLOW,
            data_id="raw_data",
            data_type="Dict[str, Any]",
            transformation="validate and normalize",
        )
        edge2 = RPGEdge(
            source_id=process_node,
            target_id=output_node,
            edge_type=EdgeType.DATA_FLOW,
            data_id="processed_data",
            data_type="ProcessedResult",
            transformation="aggregate and format",
        )

        assert edge1.target_id == edge2.source_id
        assert edge1.data_id != edge2.data_id


class TestSelfLoopPrevention:
    """Functional: Attempt self-loop edges."""

    def test_self_loop_raises_validation_error(self) -> None:
        """Attempt self-loop edge → ValidationError."""
        node = RPGNode(
            name="self_referencing",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
        )
        with pytest.raises(ValidationError, match="Self-loop detected"):
            RPGEdge(
                source_id=node.id,
                target_id=node.id,
                edge_type=EdgeType.HIERARCHY,
            )


class TestInvocationEdge:
    """Functional: Create INVOCATION edges with no data fields."""

    def test_invocation_edge_no_data_fields(self) -> None:
        """Create INVOCATION edge → assert no data fields."""
        caller = RPGNode(
            name="authenticate",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/auth.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def authenticate(user: str, pwd: str) -> bool",
        )
        callee = RPGNode(
            name="hash_password",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTION_AUGMENTED,
            folder_path="src/auth",
            file_path="src/auth/utils.py",
            interface_type=InterfaceType.FUNCTION,
            signature="def hash_password(pwd: str) -> str",
        )
        edge = RPGEdge(
            source_id=caller.id,
            target_id=callee.id,
            edge_type=EdgeType.INVOCATION,
        )
        assert edge.edge_type == EdgeType.INVOCATION
        assert edge.data_id is None
        assert edge.data_type is None
        assert edge.transformation is None


class TestRealisticGraphEdges:
    """Functional: Build realistic graph with mixed edge types."""

    def test_build_complete_graph_edges(self) -> None:
        """Build a graph with 3 modules, 5 components, 10 hierarchy edges."""
        # Create nodes
        modules = [
            RPGNode(
                name=f"module_{i}",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
            for i in range(3)
        ]

        components: list[RPGNode] = []
        hierarchy_edges: list[RPGEdge] = []

        # Module 0 gets 2 components, module 1 gets 2, module 2 gets 1
        comp_counts = [2, 2, 1]
        for mod_idx, count in enumerate(comp_counts):
            for comp_idx in range(count):
                comp = RPGNode(
                    name=f"component_{mod_idx}_{comp_idx}",
                    level=NodeLevel.COMPONENT,
                    node_type=NodeType.FOLDER_AUGMENTED,
                    parent_id=modules[mod_idx].id,
                )
                components.append(comp)
                edge = RPGEdge(
                    source_id=modules[mod_idx].id,
                    target_id=comp.id,
                    edge_type=EdgeType.HIERARCHY,
                )
                hierarchy_edges.append(edge)

        # 5 components total
        assert len(components) == 5
        assert len(hierarchy_edges) == 5

        # Add features under each component (2 features each = 10 features)
        features: list[RPGNode] = []
        for comp in components:
            for feat_idx in range(2):
                feat = RPGNode(
                    name=f"feature_{comp.name}_{feat_idx}",
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTION_AUGMENTED,
                    parent_id=comp.id,
                    folder_path="src",
                    file_path=f"src/feat_{feat_idx}.py",
                    interface_type=InterfaceType.FUNCTION,
                    signature=f"def func_{feat_idx}() -> None",
                )
                features.append(feat)
                edge = RPGEdge(
                    source_id=comp.id,
                    target_id=feat.id,
                    edge_type=EdgeType.HIERARCHY,
                )
                hierarchy_edges.append(edge)

        # 10 features + 5 component edges + 10 feature edges = 15 hierarchy edges
        assert len(features) == 10
        assert len(hierarchy_edges) == 15

        # All edges connect different nodes
        for e in hierarchy_edges:
            assert e.source_id != e.target_id

    def test_mixed_edge_types_serialization(self) -> None:
        """Create edges of all types, serialize, deserialize."""
        node_ids = [uuid4() for _ in range(6)]

        edges = [
            RPGEdge(
                source_id=node_ids[0],
                target_id=node_ids[1],
                edge_type=EdgeType.HIERARCHY,
            ),
            RPGEdge(
                source_id=node_ids[1],
                target_id=node_ids[2],
                edge_type=EdgeType.DATA_FLOW,
                data_id="result",
                data_type="int",
                transformation="compute",
            ),
            RPGEdge(
                source_id=node_ids[2],
                target_id=node_ids[3],
                edge_type=EdgeType.ORDERING,
            ),
            RPGEdge(
                source_id=node_ids[3],
                target_id=node_ids[4],
                edge_type=EdgeType.INHERITANCE,
            ),
            RPGEdge(
                source_id=node_ids[4],
                target_id=node_ids[5],
                edge_type=EdgeType.INVOCATION,
            ),
        ]

        # Serialize all as JSON
        json_str = json.dumps([e.model_dump(mode="json") for e in edges])
        data = json.loads(json_str)
        restored = [RPGEdge.model_validate(item) for item in data]

        assert len(restored) == 5
        for orig, rest in zip(edges, restored):
            assert orig == rest

        # Verify edge types preserved
        assert restored[0].edge_type == EdgeType.HIERARCHY
        assert restored[1].edge_type == EdgeType.DATA_FLOW
        assert restored[1].data_id == "result"
        assert restored[2].edge_type == EdgeType.ORDERING
        assert restored[3].edge_type == EdgeType.INHERITANCE
        assert restored[4].edge_type == EdgeType.INVOCATION


class TestEdgeValidationScenarios:
    """Functional: Validation scenarios for edges in realistic contexts."""

    def test_data_flow_with_complex_types(self) -> None:
        """DATA_FLOW edge with complex type annotations."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
            data_id="user_profiles",
            data_type="List[Dict[str, Union[str, int, None]]]",
            transformation="filter by active status, sort by created_at, paginate",
        )
        assert "Union" in edge.data_type
        assert "paginate" in edge.transformation

    def test_batch_edge_creation(self) -> None:
        """Create 100 edges efficiently."""
        edges = [
            RPGEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                edge_type=EdgeType.HIERARCHY,
            )
            for _ in range(100)
        ]
        assert len(edges) == 100
        assert len({e.id for e in edges}) == 100  # All unique IDs

    def test_validated_edge_workflow(self) -> None:
        """Edge starts unvalidated, then gets validated."""
        edge = RPGEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            edge_type=EdgeType.DATA_FLOW,
            data_id="token",
            data_type="str",
        )
        assert edge.validated is False

        # Validate the edge
        edge.validated = True
        assert edge.validated is True

        # Serialize and verify
        json_str = edge.model_dump_json()
        restored = RPGEdge.model_validate_json(json_str)
        assert restored.validated is True
