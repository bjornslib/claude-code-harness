"""Functional / integration tests for graph_ops module.

These tests build realistic graph structures resembling actual software
projects and test graph operations end-to-end.
"""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from zerorepo.models.enums import (
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
    TestStatus,
)
from zerorepo.models.edge import RPGEdge
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode

from zerorepo.graph_ops import (
    CycleDetectedError,
    topological_sort,
    detect_cycles,
    extract_subgraph_by_module,
    extract_subgraph_by_level,
    extract_subgraph_by_type,
    get_ancestors,
    get_descendants,
    get_direct_dependencies,
    filter_by_level,
    filter_by_status,
    filter_by_validation,
    filter_nodes,
    diff_dependencies,
    serialize_graph,
    deserialize_graph,
)


# --------------------------------------------------------------------------- #
#                          Realistic Graph Builder                             #
# --------------------------------------------------------------------------- #


def _build_realistic_project() -> tuple[RPGGraph, dict[str, UUID]]:
    """Build a realistic software project graph.

    Structure:
        auth_module (MODULE)
          ├── auth_service (COMPONENT)
          │     ├── login_func (FEATURE, FUNCTION_AUGMENTED)
          │     └── logout_func (FEATURE, FUNCTION_AUGMENTED)
          └── token_mgr (COMPONENT)
                └── validate_token (FEATURE, FUNCTION_AUGMENTED)

        api_module (MODULE)
          └── routes (COMPONENT)
                └── user_route (FEATURE, FUNCTION_AUGMENTED)

    Dependencies:
        login_func --DATA_FLOW--> validate_token
        user_route --INVOCATION--> login_func
        user_route --DATA_FLOW--> validate_token
    """
    ids: dict[str, UUID] = {}
    graph = RPGGraph(metadata={"project": "realistic-app", "version": "1.0"})

    def add_node(
        key: str,
        name: str,
        level: NodeLevel,
        node_type: NodeType = NodeType.FUNCTIONALITY,
        parent_key: str | None = None,
        test_status: TestStatus = TestStatus.PENDING,
        validated: bool = False,
        interface_type: InterfaceType | None = None,
        signature: str | None = None,
        folder_path: str | None = None,
        file_path: str | None = None,
    ) -> None:
        uid = uuid4()
        ids[key] = uid
        kwargs: dict = dict(
            id=uid,
            name=name,
            level=level,
            node_type=node_type,
            test_status=test_status,
            serena_validated=validated,
        )
        if parent_key:
            kwargs["parent_id"] = ids[parent_key]
        if interface_type:
            kwargs["interface_type"] = interface_type
        if signature:
            kwargs["signature"] = signature
        if folder_path:
            kwargs["folder_path"] = folder_path
        if file_path:
            kwargs["file_path"] = file_path
        graph.add_node(RPGNode(**kwargs))

    # Auth module
    add_node(
        "auth_mod",
        "auth",
        NodeLevel.MODULE,
        folder_path="src/auth",
    )
    add_node(
        "auth_svc",
        "auth_service",
        NodeLevel.COMPONENT,
        parent_key="auth_mod",
        test_status=TestStatus.PASSED,
        validated=True,
        folder_path="src/auth/service",
    )
    add_node(
        "login",
        "login",
        NodeLevel.FEATURE,
        NodeType.FUNCTION_AUGMENTED,
        parent_key="auth_svc",
        test_status=TestStatus.PASSED,
        validated=True,
        interface_type=InterfaceType.FUNCTION,
        signature="def login(username: str, password: str) -> Token",
        folder_path="src/auth/service",
        file_path="src/auth/service/login.py",
    )
    add_node(
        "logout",
        "logout",
        NodeLevel.FEATURE,
        NodeType.FUNCTION_AUGMENTED,
        parent_key="auth_svc",
        test_status=TestStatus.FAILED,
        validated=False,
        interface_type=InterfaceType.FUNCTION,
        signature="def logout(token: Token) -> bool",
        folder_path="src/auth/service",
        file_path="src/auth/service/logout.py",
    )
    add_node(
        "token_mgr",
        "token_manager",
        NodeLevel.COMPONENT,
        parent_key="auth_mod",
        test_status=TestStatus.PASSED,
        validated=True,
        folder_path="src/auth/tokens",
    )
    add_node(
        "validate",
        "validate_token",
        NodeLevel.FEATURE,
        NodeType.FUNCTION_AUGMENTED,
        parent_key="token_mgr",
        test_status=TestStatus.PASSED,
        validated=True,
        interface_type=InterfaceType.FUNCTION,
        signature="def validate_token(token: str) -> bool",
        folder_path="src/auth/tokens",
        file_path="src/auth/tokens/validate.py",
    )

    # API module
    add_node(
        "api_mod",
        "api",
        NodeLevel.MODULE,
        folder_path="src/api",
    )
    add_node(
        "routes",
        "routes",
        NodeLevel.COMPONENT,
        parent_key="api_mod",
        folder_path="src/api/routes",
    )
    add_node(
        "user_route",
        "user_route",
        NodeLevel.FEATURE,
        NodeType.FUNCTION_AUGMENTED,
        parent_key="routes",
        interface_type=InterfaceType.FUNCTION,
        signature="def user_route(request: Request) -> Response",
        folder_path="src/api/routes",
        file_path="src/api/routes/user.py",
    )

    # HIERARCHY edges
    for parent, child in [
        ("auth_mod", "auth_svc"),
        ("auth_mod", "token_mgr"),
        ("auth_svc", "login"),
        ("auth_svc", "logout"),
        ("token_mgr", "validate"),
        ("api_mod", "routes"),
        ("routes", "user_route"),
    ]:
        graph.add_edge(
            RPGEdge(
                source_id=ids[parent],
                target_id=ids[child],
                edge_type=EdgeType.HIERARCHY,
            )
        )

    # DATA_FLOW edges
    graph.add_edge(
        RPGEdge(
            source_id=ids["login"],
            target_id=ids["validate"],
            edge_type=EdgeType.DATA_FLOW,
            data_id="token_str",
            data_type="str",
        )
    )
    graph.add_edge(
        RPGEdge(
            source_id=ids["user_route"],
            target_id=ids["validate"],
            edge_type=EdgeType.DATA_FLOW,
            data_id="auth_token",
            data_type="str",
        )
    )

    # INVOCATION edge
    graph.add_edge(
        RPGEdge(
            source_id=ids["user_route"],
            target_id=ids["login"],
            edge_type=EdgeType.INVOCATION,
        )
    )

    return graph, ids


# =========================================================================== #
#                     Functional Test: Full Workflow                            #
# =========================================================================== #


@pytest.mark.functional
class TestRealisticGraphWorkflow:
    """End-to-end tests simulating a real workflow on a realistic graph."""

    @pytest.fixture
    def project(self) -> tuple[RPGGraph, dict[str, UUID]]:
        return _build_realistic_project()

    def test_topological_sort_respects_hierarchy(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        order = topological_sort(graph)
        # Modules before their components
        assert order.index(ids["auth_mod"]) < order.index(ids["auth_svc"])
        assert order.index(ids["auth_mod"]) < order.index(ids["token_mgr"])
        assert order.index(ids["api_mod"]) < order.index(ids["routes"])
        # Components before their features
        assert order.index(ids["auth_svc"]) < order.index(ids["login"])
        assert order.index(ids["token_mgr"]) < order.index(ids["validate"])
        # DATA_FLOW: login before validate
        assert order.index(ids["login"]) < order.index(ids["validate"])

    def test_no_cycles_in_project(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, _ = project
        assert detect_cycles(graph) == []

    def test_extract_auth_module(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        auth_sub = extract_subgraph_by_module(graph, ids["auth_mod"])
        auth_names = {n.name for n in auth_sub.nodes.values()}
        assert auth_names == {
            "auth",
            "auth_service",
            "login",
            "logout",
            "token_manager",
            "validate_token",
        }
        # Should NOT include api module nodes
        assert ids["api_mod"] not in auth_sub.nodes
        assert ids["user_route"] not in auth_sub.nodes

    def test_extract_api_module(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        api_sub = extract_subgraph_by_module(graph, ids["api_mod"])
        api_names = {n.name for n in api_sub.nodes.values()}
        assert api_names == {"api", "routes", "user_route"}

    def test_extract_features_only(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        feature_sub = extract_subgraph_by_level(graph, NodeLevel.FEATURE)
        feature_names = {n.name for n in feature_sub.nodes.values()}
        assert feature_names == {
            "login",
            "logout",
            "validate_token",
            "user_route",
        }
        # Edges between features should be preserved
        assert feature_sub.edge_count >= 2  # At least DATA_FLOW + INVOCATION

    def test_extract_function_augmented(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, _ = project
        fn_sub = extract_subgraph_by_type(graph, NodeType.FUNCTION_AUGMENTED)
        for node in fn_sub.nodes.values():
            assert node.node_type == NodeType.FUNCTION_AUGMENTED
            assert node.interface_type is not None

    def test_ancestors_of_validate_token(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        # HIERARCHY ancestors of validate_token
        ancestors = get_ancestors(
            graph, ids["validate"], [EdgeType.HIERARCHY]
        )
        assert ancestors == {ids["auth_mod"], ids["token_mgr"]}

    def test_descendants_of_auth_module(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        desc = get_descendants(
            graph, ids["auth_mod"], [EdgeType.HIERARCHY]
        )
        expected = {
            ids["auth_svc"],
            ids["token_mgr"],
            ids["login"],
            ids["logout"],
            ids["validate"],
        }
        assert desc == expected

    def test_direct_deps_of_user_route(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        deps = get_direct_dependencies(graph, ids["user_route"])
        assert set(deps) == {ids["validate"], ids["login"]}

    def test_filter_passed_tests(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, _ = project
        passed = filter_by_status(graph, TestStatus.PASSED)
        passed_names = {n.name for n in passed}
        assert "login" in passed_names
        assert "validate_token" in passed_names
        assert "auth_service" in passed_names
        assert "logout" not in passed_names  # FAILED

    def test_filter_failed_tests(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, _ = project
        failed = filter_by_status(graph, TestStatus.FAILED)
        assert len(failed) == 1
        assert failed[0].name == "logout"

    def test_filter_validated_nodes(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, _ = project
        validated = filter_by_validation(graph, True)
        validated_names = {n.name for n in validated}
        assert "login" in validated_names
        assert "validate_token" in validated_names
        assert "logout" not in validated_names

    def test_filter_unvalidated_nodes(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, _ = project
        unvalidated = filter_by_validation(graph, False)
        unvalidated_names = {n.name for n in unvalidated}
        assert "logout" in unvalidated_names
        # Nodes with default pending status and validated=False
        assert "auth" in unvalidated_names

    def test_diff_with_actual_dependencies(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        graph, ids = project
        # Simulate: user_route has actual_dependencies set to validate only
        user_node = graph.nodes[ids["user_route"]]
        user_node.actual_dependencies = [ids["validate"]]

        result = diff_dependencies(user_node, graph)
        # planned: validate + login
        assert set(result["planned"]) == {ids["validate"], ids["login"]}
        # actual: validate only
        assert result["actual"] == [ids["validate"]]
        # missing: login
        assert set(result["missing"]) == {ids["login"]}
        assert result["extra"] == []

    def test_serialize_deserialize_full_project(
        self, project: tuple[RPGGraph, dict[str, UUID]], tmp_path
    ) -> None:
        graph, ids = project
        path = tmp_path / "project.json"
        serialize_graph(graph, path)
        loaded = deserialize_graph(path)

        assert loaded.node_count == graph.node_count
        assert loaded.edge_count == graph.edge_count
        assert loaded.metadata == graph.metadata

        # Verify specific node survived round-trip
        login_node = loaded.nodes[ids["login"]]
        assert login_node.name == "login"
        assert login_node.level == NodeLevel.FEATURE
        assert login_node.interface_type == InterfaceType.FUNCTION
        assert login_node.test_status == TestStatus.PASSED

    def test_combined_workflow_find_untested_features(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        """Realistic workflow: find features that aren't passing tests."""
        graph, _ = project
        features = filter_by_level(graph, NodeLevel.FEATURE)
        not_passing = [
            f for f in features if f.test_status != TestStatus.PASSED
        ]
        not_passing_names = {n.name for n in not_passing}
        assert "logout" in not_passing_names
        assert "user_route" in not_passing_names  # PENDING

    def test_combined_workflow_impact_analysis(
        self, project: tuple[RPGGraph, dict[str, UUID]]
    ) -> None:
        """What depends (transitively) on validate_token via DATA_FLOW?"""
        graph, ids = project
        # Find everything that depends on validate_token
        # = ancestors of validate_token via DATA_FLOW
        dependents = get_ancestors(
            graph, ids["validate"], [EdgeType.DATA_FLOW]
        )
        dependent_names = {graph.nodes[d].name for d in dependents}
        assert "login" in dependent_names
        assert "user_route" in dependent_names


@pytest.mark.functional
class TestEdgeCases:
    """Edge case and boundary condition tests."""

    def test_large_graph_topological_sort(self) -> None:
        """Test topological sort on a larger graph (100 nodes linear chain)."""
        graph = RPGGraph()
        ids = [uuid4() for _ in range(100)]
        for i, uid in enumerate(ids):
            graph.add_node(
                RPGNode(
                    id=uid,
                    name=f"node_{i}",
                    level=NodeLevel.COMPONENT,
                    node_type=NodeType.FUNCTIONALITY,
                )
            )
        for i in range(99):
            graph.add_edge(
                RPGEdge(
                    source_id=ids[i],
                    target_id=ids[i + 1],
                    edge_type=EdgeType.HIERARCHY,
                )
            )

        result = topological_sort(graph)
        assert len(result) == 100
        # Verify strict ordering
        for i in range(99):
            assert result.index(ids[i]) < result.index(ids[i + 1])

    def test_wide_graph_topological_sort(self) -> None:
        """Test with a wide graph (1 root, 50 children)."""
        graph = RPGGraph()
        root = uuid4()
        graph.add_node(
            RPGNode(
                id=root,
                name="root",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
        )
        children = []
        for i in range(50):
            child = uuid4()
            children.append(child)
            graph.add_node(
                RPGNode(
                    id=child,
                    name=f"child_{i}",
                    level=NodeLevel.COMPONENT,
                    node_type=NodeType.FUNCTIONALITY,
                )
            )
            graph.add_edge(
                RPGEdge(
                    source_id=root,
                    target_id=child,
                    edge_type=EdgeType.HIERARCHY,
                )
            )

        result = topological_sort(graph)
        assert result[0] == root
        assert set(result[1:]) == set(children)

    def test_serialize_deserialize_round_trip_equality(self, tmp_path) -> None:
        """Verify that serialize -> deserialize -> serialize produces identical JSON."""
        graph, _ = _build_realistic_project()
        path1 = tmp_path / "first.json"
        path2 = tmp_path / "second.json"

        serialize_graph(graph, path1)
        loaded = deserialize_graph(path1)
        serialize_graph(loaded, path2)

        json1 = path1.read_text()
        json2 = path2.read_text()
        assert json1 == json2

    def test_subgraph_preserves_invocation_edges(self) -> None:
        """Extracting by level preserves INVOCATION edges between nodes."""
        graph = RPGGraph()
        f1, f2 = uuid4(), uuid4()
        graph.add_node(
            RPGNode(
                id=f1,
                name="caller",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                interface_type=InterfaceType.FUNCTION,
                signature="def caller() -> None",
            )
        )
        graph.add_node(
            RPGNode(
                id=f2,
                name="callee",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                interface_type=InterfaceType.FUNCTION,
                signature="def callee() -> None",
            )
        )
        graph.add_edge(
            RPGEdge(
                source_id=f1,
                target_id=f2,
                edge_type=EdgeType.INVOCATION,
            )
        )

        sub = extract_subgraph_by_level(graph, NodeLevel.FEATURE)
        assert sub.edge_count == 1
        edge = list(sub.edges.values())[0]
        assert edge.edge_type == EdgeType.INVOCATION

    def test_transitive_closure_through_mixed_edges(self) -> None:
        """Ancestors/descendants through mixed HIERARCHY + DATA_FLOW."""
        graph = RPGGraph()
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
        for uid, name in [(a, "A"), (b, "B"), (c, "C"), (d, "D")]:
            graph.add_node(
                RPGNode(
                    id=uid,
                    name=name,
                    level=NodeLevel.COMPONENT,
                    node_type=NodeType.FUNCTIONALITY,
                )
            )
        # A --HIERARCHY--> B --DATA_FLOW--> C --HIERARCHY--> D
        graph.add_edge(
            RPGEdge(
                source_id=a, target_id=b, edge_type=EdgeType.HIERARCHY
            )
        )
        graph.add_edge(
            RPGEdge(
                source_id=b, target_id=c, edge_type=EdgeType.DATA_FLOW
            )
        )
        graph.add_edge(
            RPGEdge(
                source_id=c, target_id=d, edge_type=EdgeType.HIERARCHY
            )
        )

        desc = get_descendants(
            graph, a, [EdgeType.HIERARCHY, EdgeType.DATA_FLOW]
        )
        assert desc == {b, c, d}

        ancestors = get_ancestors(
            graph, d, [EdgeType.HIERARCHY, EdgeType.DATA_FLOW]
        )
        assert ancestors == {a, b, c}
