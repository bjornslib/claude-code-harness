"""Unit tests for ontology data models and backend interface.

Tests cover FeatureNode, FeaturePath, OntologyStats models and
the OntologyBackend abstract interface as defined in Task 2.1.1.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from zerorepo.ontology.backend import OntologyBackend
from zerorepo.ontology.models import FeatureNode, FeaturePath, OntologyStats


# ---------------------------------------------------------------------------
# FeatureNode Tests
# ---------------------------------------------------------------------------


class TestFeatureNodeCreation:
    """Test valid FeatureNode creation."""

    def test_create_root_node(self) -> None:
        """Create a root node with minimal required fields."""
        node = FeatureNode(
            id="software",
            name="Software",
            level=0,
        )
        assert node.id == "software"
        assert node.name == "Software"
        assert node.level == 0
        assert node.parent_id is None
        assert node.description is None
        assert node.tags == []
        assert node.embedding is None
        assert node.metadata == {}

    def test_create_child_node(self) -> None:
        """Create a child node with parent reference."""
        node = FeatureNode(
            id="ml.deep-learning",
            name="Deep Learning",
            description="Neural network-based machine learning",
            parent_id="ml",
            level=2,
            tags=["neural-networks", "deep-learning", "ai"],
        )
        assert node.id == "ml.deep-learning"
        assert node.parent_id == "ml"
        assert node.level == 2
        assert node.description == "Neural network-based machine learning"
        assert len(node.tags) == 3
        assert "deep-learning" in node.tags

    def test_create_node_with_embedding(self) -> None:
        """Create a node with a vector embedding."""
        embedding = [0.1, 0.2, 0.3, -0.4, 0.5]
        node = FeatureNode(
            id="ml.transformers",
            name="Transformers",
            level=3,
            embedding=embedding,
        )
        assert node.embedding is not None
        assert len(node.embedding) == 5
        assert node.embedding[0] == 0.1

    def test_create_node_with_metadata(self) -> None:
        """Create a node with arbitrary metadata."""
        node = FeatureNode(
            id="web.react",
            name="React",
            level=2,
            metadata={"source": "github-topics", "popularity": 95},
        )
        assert node.metadata["source"] == "github-topics"
        assert node.metadata["popularity"] == 95

    def test_create_node_full_fields(self) -> None:
        """Create a node with all fields populated."""
        node = FeatureNode(
            id="ml.deep-learning.transformers.bert",
            name="BERT",
            description="Bidirectional Encoder Representations from Transformers",
            parent_id="ml.deep-learning.transformers",
            level=4,
            tags=["nlp", "bert", "language-model"],
            embedding=[0.1] * 1536,
            metadata={"paper_url": "https://arxiv.org/abs/1810.04805"},
        )
        assert node.id == "ml.deep-learning.transformers.bert"
        assert node.parent_id == "ml.deep-learning.transformers"
        assert node.level == 4
        assert len(node.embedding) == 1536
        assert node.metadata["paper_url"] == "https://arxiv.org/abs/1810.04805"


class TestFeatureNodeValidation:
    """Test FeatureNode validation constraints."""

    def test_empty_id_rejected(self) -> None:
        """An empty id should be rejected."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            FeatureNode(id="", name="Test", level=0)

    def test_empty_name_rejected(self) -> None:
        """An empty name should be rejected."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            FeatureNode(id="test", name="", level=0)

    def test_negative_level_rejected(self) -> None:
        """Negative level should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            FeatureNode(id="test", name="Test", level=-1)

    def test_empty_tag_rejected(self) -> None:
        """An empty tag string should be rejected."""
        with pytest.raises(ValidationError, match="empty or whitespace-only"):
            FeatureNode(
                id="test",
                name="Test",
                level=0,
                tags=["valid", ""],
            )

    def test_whitespace_only_tag_rejected(self) -> None:
        """A whitespace-only tag should be rejected."""
        with pytest.raises(ValidationError, match="empty or whitespace-only"):
            FeatureNode(
                id="test",
                name="Test",
                level=0,
                tags=["valid", "   "],
            )

    def test_empty_embedding_rejected(self) -> None:
        """An empty embedding list should be rejected."""
        with pytest.raises(ValidationError, match="non-empty"):
            FeatureNode(
                id="test",
                name="Test",
                level=0,
                embedding=[],
            )

    def test_self_referencing_parent_rejected(self) -> None:
        """parent_id must differ from id."""
        with pytest.raises(ValidationError, match="must differ from id"):
            FeatureNode(
                id="test",
                name="Test",
                level=0,
                parent_id="test",
            )

    def test_none_embedding_allowed(self) -> None:
        """None embedding should be allowed (no embedding)."""
        node = FeatureNode(id="test", name="Test", level=0, embedding=None)
        assert node.embedding is None

    def test_tags_stripped(self) -> None:
        """Tags with whitespace should be stripped."""
        node = FeatureNode(
            id="test",
            name="Test",
            level=0,
            tags=["  hello  ", "world  "],
        )
        assert node.tags == ["hello", "world"]

    def test_id_max_length(self) -> None:
        """ID exceeding max length should be rejected."""
        with pytest.raises(ValidationError, match="at most 500"):
            FeatureNode(id="x" * 501, name="Test", level=0)

    def test_name_max_length(self) -> None:
        """Name exceeding max length should be rejected."""
        with pytest.raises(ValidationError, match="at most 300"):
            FeatureNode(id="test", name="x" * 301, level=0)


class TestFeatureNodeProperties:
    """Test FeatureNode computed properties and methods."""

    def test_is_root_true(self) -> None:
        """Root nodes have no parent."""
        node = FeatureNode(id="root", name="Root", level=0)
        assert node.is_root is True

    def test_is_root_false(self) -> None:
        """Child nodes are not root."""
        node = FeatureNode(
            id="child", name="Child", level=1, parent_id="root"
        )
        assert node.is_root is False

    def test_full_path(self) -> None:
        """full_path returns the node's id."""
        node = FeatureNode(
            id="ml.deep-learning.transformers",
            name="Transformers",
            level=3,
        )
        assert node.full_path == "ml.deep-learning.transformers"

    def test_embedding_input_minimal(self) -> None:
        """embedding_input with only id."""
        node = FeatureNode(id="ml.transformers", name="Transformers", level=3)
        assert node.embedding_input() == "ml.transformers"

    def test_embedding_input_with_description(self) -> None:
        """embedding_input with id and description."""
        node = FeatureNode(
            id="ml.transformers",
            name="Transformers",
            level=3,
            description="Attention-based architectures",
        )
        assert (
            node.embedding_input()
            == "ml.transformers | Attention-based architectures"
        )

    def test_embedding_input_with_tags(self) -> None:
        """embedding_input with id and tags."""
        node = FeatureNode(
            id="ml.transformers",
            name="Transformers",
            level=3,
            tags=["nlp", "attention"],
        )
        assert node.embedding_input() == "ml.transformers | nlp, attention"

    def test_embedding_input_full(self) -> None:
        """embedding_input with id, description, and tags (PRD format)."""
        node = FeatureNode(
            id="ml.transformers",
            name="Transformers",
            level=3,
            description="Attention-based architectures",
            tags=["nlp", "attention"],
        )
        expected = "ml.transformers | Attention-based architectures | nlp, attention"
        assert node.embedding_input() == expected

    def test_repr(self) -> None:
        """repr should be concise and informative."""
        node = FeatureNode(
            id="ml.bert",
            name="BERT",
            level=4,
            tags=["nlp"],
        )
        r = repr(node)
        assert "FeatureNode" in r
        assert "ml.bert" in r
        assert "BERT" in r
        assert "level=4" in r

    def test_equality(self) -> None:
        """Nodes with same data should be equal."""
        node1 = FeatureNode(id="a", name="A", level=0)
        node2 = FeatureNode(id="a", name="A", level=0)
        assert node1 == node2

    def test_inequality(self) -> None:
        """Nodes with different data should not be equal."""
        node1 = FeatureNode(id="a", name="A", level=0)
        node2 = FeatureNode(id="b", name="B", level=0)
        assert node1 != node2

    def test_hash(self) -> None:
        """Nodes should be hashable by id."""
        node1 = FeatureNode(id="a", name="A", level=0)
        node2 = FeatureNode(id="a", name="A modified", level=1)
        assert hash(node1) == hash(node2)  # same id = same hash

    def test_hash_in_set(self) -> None:
        """Nodes should be usable in sets."""
        node1 = FeatureNode(id="a", name="A", level=0)
        node2 = FeatureNode(id="b", name="B", level=0)
        s = {node1, node2}
        assert len(s) == 2

    def test_equality_not_implemented(self) -> None:
        """Comparing with non-FeatureNode returns NotImplemented."""
        node = FeatureNode(id="a", name="A", level=0)
        assert node != "not a node"


class TestFeatureNodeSerialization:
    """Test FeatureNode JSON serialization/deserialization."""

    def test_round_trip_json(self) -> None:
        """Serialize and deserialize a FeatureNode."""
        node = FeatureNode(
            id="ml.bert",
            name="BERT",
            description="Bidirectional encoder",
            parent_id="ml.transformers",
            level=4,
            tags=["nlp", "bert"],
            embedding=[0.1, 0.2, 0.3],
            metadata={"source": "github"},
        )
        json_str = node.model_dump_json()
        restored = FeatureNode.model_validate_json(json_str)
        assert restored == node

    def test_model_dump(self) -> None:
        """model_dump produces correct dict."""
        node = FeatureNode(id="test", name="Test", level=0)
        d = node.model_dump()
        assert d["id"] == "test"
        assert d["name"] == "Test"
        assert d["level"] == 0
        assert d["parent_id"] is None
        assert d["tags"] == []


# ---------------------------------------------------------------------------
# FeaturePath Tests
# ---------------------------------------------------------------------------


class TestFeaturePathCreation:
    """Test valid FeaturePath creation."""

    def test_create_single_node_path(self) -> None:
        """Create a path with a single node."""
        node = FeatureNode(id="root", name="Root", level=0)
        path = FeaturePath(nodes=[node], score=0.95)
        assert len(path.nodes) == 1
        assert path.score == 0.95

    def test_create_multi_node_path(self) -> None:
        """Create a path from root to leaf."""
        root = FeatureNode(id="software", name="Software", level=0)
        mid = FeatureNode(
            id="web", name="Web Development", level=1, parent_id="software"
        )
        leaf = FeatureNode(
            id="react", name="React Hooks", level=2, parent_id="web"
        )
        path = FeaturePath(nodes=[root, mid, leaf], score=0.87)
        assert len(path.nodes) == 3
        assert path.score == 0.87


class TestFeaturePathValidation:
    """Test FeaturePath validation constraints."""

    def test_empty_nodes_rejected(self) -> None:
        """Empty nodes list should be rejected."""
        with pytest.raises(ValidationError, match="at least 1"):
            FeaturePath(nodes=[], score=0.5)

    def test_score_below_zero_rejected(self) -> None:
        """Score below 0.0 should be rejected."""
        node = FeatureNode(id="test", name="Test", level=0)
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            FeaturePath(nodes=[node], score=-0.1)

    def test_score_above_one_rejected(self) -> None:
        """Score above 1.0 should be rejected."""
        node = FeatureNode(id="test", name="Test", level=0)
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            FeaturePath(nodes=[node], score=1.1)

    def test_score_boundary_zero(self) -> None:
        """Score of exactly 0.0 should be accepted."""
        node = FeatureNode(id="test", name="Test", level=0)
        path = FeaturePath(nodes=[node], score=0.0)
        assert path.score == 0.0

    def test_score_boundary_one(self) -> None:
        """Score of exactly 1.0 should be accepted."""
        node = FeatureNode(id="test", name="Test", level=0)
        path = FeaturePath(nodes=[node], score=1.0)
        assert path.score == 1.0


class TestFeaturePathProperties:
    """Test FeaturePath computed properties."""

    def _make_path(self) -> FeaturePath:
        """Create a sample 3-node path."""
        root = FeatureNode(id="a", name="A", level=0)
        mid = FeatureNode(id="b", name="B", level=1, parent_id="a")
        leaf = FeatureNode(id="c", name="C", level=2, parent_id="b")
        return FeaturePath(nodes=[root, mid, leaf], score=0.75)

    def test_leaf(self) -> None:
        """leaf returns the last node."""
        path = self._make_path()
        assert path.leaf.id == "c"

    def test_root(self) -> None:
        """root returns the first node."""
        path = self._make_path()
        assert path.root.id == "a"

    def test_depth(self) -> None:
        """depth returns node count."""
        path = self._make_path()
        assert path.depth == 3

    def test_path_string(self) -> None:
        """path_string returns human-readable path."""
        path = self._make_path()
        assert path.path_string == "A > B > C"

    def test_repr(self) -> None:
        """repr should be concise."""
        path = self._make_path()
        r = repr(path)
        assert "FeaturePath" in r
        assert "A > B > C" in r
        assert "0.750" in r

    def test_equality(self) -> None:
        """Paths with same data should be equal."""
        node = FeatureNode(id="a", name="A", level=0)
        p1 = FeaturePath(nodes=[node], score=0.5)
        p2 = FeaturePath(nodes=[node], score=0.5)
        assert p1 == p2

    def test_inequality(self) -> None:
        """Paths with different scores should not be equal."""
        node = FeatureNode(id="a", name="A", level=0)
        p1 = FeaturePath(nodes=[node], score=0.5)
        p2 = FeaturePath(nodes=[node], score=0.6)
        assert p1 != p2

    def test_equality_not_implemented(self) -> None:
        """Comparing with non-FeaturePath returns NotImplemented."""
        node = FeatureNode(id="a", name="A", level=0)
        path = FeaturePath(nodes=[node], score=0.5)
        assert path != "not a path"


class TestFeaturePathSerialization:
    """Test FeaturePath JSON serialization."""

    def test_round_trip_json(self) -> None:
        """Serialize and deserialize a FeaturePath."""
        node = FeatureNode(id="a", name="A", level=0, tags=["x"])
        path = FeaturePath(nodes=[node], score=0.88)
        json_str = path.model_dump_json()
        restored = FeaturePath.model_validate_json(json_str)
        assert restored == path


# ---------------------------------------------------------------------------
# OntologyStats Tests
# ---------------------------------------------------------------------------


class TestOntologyStatsCreation:
    """Test valid OntologyStats creation."""

    def test_create_minimal(self) -> None:
        """Create stats with required fields only."""
        stats = OntologyStats(
            total_nodes=1000,
            total_levels=5,
            avg_children=3.5,
            max_depth=7,
        )
        assert stats.total_nodes == 1000
        assert stats.total_levels == 5
        assert stats.avg_children == 3.5
        assert stats.max_depth == 7
        assert stats.root_count == 0
        assert stats.leaf_count == 0
        assert stats.nodes_with_embeddings == 0
        assert stats.metadata == {}

    def test_create_full(self) -> None:
        """Create stats with all fields."""
        stats = OntologyStats(
            total_nodes=50000,
            total_levels=7,
            avg_children=8.2,
            max_depth=7,
            root_count=10,
            leaf_count=35000,
            nodes_with_embeddings=48000,
            metadata={"backend": "github-topics", "last_updated": "2026-02-07"},
        )
        assert stats.total_nodes == 50000
        assert stats.root_count == 10
        assert stats.leaf_count == 35000
        assert stats.nodes_with_embeddings == 48000
        assert stats.metadata["backend"] == "github-topics"

    def test_empty_ontology(self) -> None:
        """Create stats for an empty ontology."""
        stats = OntologyStats(
            total_nodes=0,
            total_levels=0,
            avg_children=0.0,
            max_depth=0,
        )
        assert stats.total_nodes == 0
        assert stats.embedding_coverage == 0.0


class TestOntologyStatsValidation:
    """Test OntologyStats validation constraints."""

    def test_negative_total_nodes_rejected(self) -> None:
        """Negative total_nodes should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            OntologyStats(
                total_nodes=-1,
                total_levels=0,
                avg_children=0.0,
                max_depth=0,
            )

    def test_negative_total_levels_rejected(self) -> None:
        """Negative total_levels should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            OntologyStats(
                total_nodes=0,
                total_levels=-1,
                avg_children=0.0,
                max_depth=0,
            )

    def test_negative_avg_children_rejected(self) -> None:
        """Negative avg_children should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            OntologyStats(
                total_nodes=0,
                total_levels=0,
                avg_children=-1.0,
                max_depth=0,
            )

    def test_negative_max_depth_rejected(self) -> None:
        """Negative max_depth should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            OntologyStats(
                total_nodes=0,
                total_levels=0,
                avg_children=0.0,
                max_depth=-1,
            )

    def test_leaf_count_exceeds_total_rejected(self) -> None:
        """leaf_count exceeding total_nodes should be rejected."""
        with pytest.raises(ValidationError, match="leaf_count.*cannot exceed"):
            OntologyStats(
                total_nodes=10,
                total_levels=3,
                avg_children=2.0,
                max_depth=3,
                leaf_count=11,
            )

    def test_root_count_exceeds_total_rejected(self) -> None:
        """root_count exceeding total_nodes should be rejected."""
        with pytest.raises(ValidationError, match="root_count.*cannot exceed"):
            OntologyStats(
                total_nodes=10,
                total_levels=3,
                avg_children=2.0,
                max_depth=3,
                root_count=11,
            )

    def test_embeddings_count_exceeds_total_rejected(self) -> None:
        """nodes_with_embeddings exceeding total_nodes should be rejected."""
        with pytest.raises(
            ValidationError, match="nodes_with_embeddings.*cannot exceed"
        ):
            OntologyStats(
                total_nodes=10,
                total_levels=3,
                avg_children=2.0,
                max_depth=3,
                nodes_with_embeddings=11,
            )


class TestOntologyStatsProperties:
    """Test OntologyStats computed properties."""

    def test_embedding_coverage_full(self) -> None:
        """100% embedding coverage."""
        stats = OntologyStats(
            total_nodes=100,
            total_levels=3,
            avg_children=3.0,
            max_depth=3,
            nodes_with_embeddings=100,
        )
        assert stats.embedding_coverage == 1.0

    def test_embedding_coverage_partial(self) -> None:
        """Partial embedding coverage."""
        stats = OntologyStats(
            total_nodes=100,
            total_levels=3,
            avg_children=3.0,
            max_depth=3,
            nodes_with_embeddings=75,
        )
        assert stats.embedding_coverage == 0.75

    def test_embedding_coverage_none(self) -> None:
        """No embeddings."""
        stats = OntologyStats(
            total_nodes=100,
            total_levels=3,
            avg_children=3.0,
            max_depth=3,
            nodes_with_embeddings=0,
        )
        assert stats.embedding_coverage == 0.0

    def test_embedding_coverage_empty_ontology(self) -> None:
        """Empty ontology returns 0.0 coverage without division error."""
        stats = OntologyStats(
            total_nodes=0,
            total_levels=0,
            avg_children=0.0,
            max_depth=0,
        )
        assert stats.embedding_coverage == 0.0

    def test_repr(self) -> None:
        """repr should be concise."""
        stats = OntologyStats(
            total_nodes=1000,
            total_levels=5,
            avg_children=3.5,
            max_depth=7,
        )
        r = repr(stats)
        assert "OntologyStats" in r
        assert "1000" in r
        assert "5" in r


class TestOntologyStatsSerialization:
    """Test OntologyStats JSON serialization."""

    def test_round_trip_json(self) -> None:
        """Serialize and deserialize OntologyStats."""
        stats = OntologyStats(
            total_nodes=50000,
            total_levels=7,
            avg_children=8.2,
            max_depth=7,
            root_count=10,
            leaf_count=35000,
            nodes_with_embeddings=48000,
        )
        json_str = stats.model_dump_json()
        restored = OntologyStats.model_validate_json(json_str)
        assert restored.total_nodes == stats.total_nodes
        assert restored.leaf_count == stats.leaf_count
        assert restored.nodes_with_embeddings == stats.nodes_with_embeddings


# ---------------------------------------------------------------------------
# OntologyBackend Interface Tests
# ---------------------------------------------------------------------------


class _MockOntologyBackend(OntologyBackend):
    """Concrete implementation of OntologyBackend for testing."""

    def __init__(self) -> None:
        self._nodes: dict[str, FeatureNode] = {}

    def add(self, node: FeatureNode) -> None:
        """Add a node to the mock backend."""
        self._nodes[node.id] = node

    def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
        """Return mock search results."""
        if not query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        results = []
        for node in list(self._nodes.values())[:top_k]:
            results.append(FeaturePath(nodes=[node], score=0.5))
        return results

    def get_node(self, feature_id: str) -> FeatureNode:
        """Return a node by id."""
        if not feature_id:
            raise ValueError("feature_id must not be empty")
        if feature_id not in self._nodes:
            raise KeyError(f"Node '{feature_id}' not found")
        return self._nodes[feature_id]

    def get_children(self, feature_id: str) -> list[FeatureNode]:
        """Return children of a node."""
        if not feature_id:
            raise ValueError("feature_id must not be empty")
        if feature_id not in self._nodes:
            raise KeyError(f"Node '{feature_id}' not found")
        return [
            n
            for n in self._nodes.values()
            if n.parent_id == feature_id
        ]

    def get_statistics(self) -> OntologyStats:
        """Return mock statistics."""
        total = len(self._nodes)
        roots = sum(1 for n in self._nodes.values() if n.is_root)
        leaves_set = set(self._nodes.keys()) - {
            n.parent_id
            for n in self._nodes.values()
            if n.parent_id is not None
        }
        return OntologyStats(
            total_nodes=total,
            total_levels=max((n.level for n in self._nodes.values()), default=0) + 1 if total > 0 else 0,
            avg_children=total / max(roots, 1) if total > 0 else 0.0,
            max_depth=max((n.level for n in self._nodes.values()), default=0),
            root_count=roots,
            leaf_count=len(leaves_set),
        )


class TestOntologyBackendInterface:
    """Test the OntologyBackend abstract interface via mock implementation."""

    @pytest.fixture()
    def backend(self) -> _MockOntologyBackend:
        """Create a mock backend with sample data."""
        b = _MockOntologyBackend()
        b.add(FeatureNode(id="ml", name="Machine Learning", level=0))
        b.add(
            FeatureNode(
                id="ml.dl",
                name="Deep Learning",
                level=1,
                parent_id="ml",
            )
        )
        b.add(
            FeatureNode(
                id="ml.dl.transformers",
                name="Transformers",
                level=2,
                parent_id="ml.dl",
            )
        )
        b.add(
            FeatureNode(
                id="ml.dl.cnn",
                name="CNN",
                level=2,
                parent_id="ml.dl",
            )
        )
        return b

    def test_cannot_instantiate_abstract(self) -> None:
        """Cannot instantiate OntologyBackend directly."""
        with pytest.raises(TypeError, match="abstract"):
            OntologyBackend()  # type: ignore[abstract]

    def test_search_returns_results(self, backend: _MockOntologyBackend) -> None:
        """Search returns FeaturePath results."""
        results = backend.search("learning", top_k=2)
        assert len(results) == 2
        assert all(isinstance(r, FeaturePath) for r in results)
        assert all(0.0 <= r.score <= 1.0 for r in results)

    def test_search_empty_query_raises(self, backend: _MockOntologyBackend) -> None:
        """Search with empty query raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            backend.search("")

    def test_search_zero_top_k_raises(self, backend: _MockOntologyBackend) -> None:
        """Search with non-positive top_k raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            backend.search("test", top_k=0)

    def test_get_node_found(self, backend: _MockOntologyBackend) -> None:
        """get_node returns existing node."""
        node = backend.get_node("ml.dl")
        assert isinstance(node, FeatureNode)
        assert node.id == "ml.dl"
        assert node.name == "Deep Learning"

    def test_get_node_not_found(self, backend: _MockOntologyBackend) -> None:
        """get_node raises KeyError for missing node."""
        with pytest.raises(KeyError, match="not found"):
            backend.get_node("nonexistent")

    def test_get_node_empty_id_raises(self, backend: _MockOntologyBackend) -> None:
        """get_node with empty id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            backend.get_node("")

    def test_get_children_returns_children(
        self, backend: _MockOntologyBackend
    ) -> None:
        """get_children returns direct children."""
        children = backend.get_children("ml.dl")
        assert len(children) == 2
        child_ids = {c.id for c in children}
        assert child_ids == {"ml.dl.transformers", "ml.dl.cnn"}

    def test_get_children_leaf_returns_empty(
        self, backend: _MockOntologyBackend
    ) -> None:
        """get_children on a leaf returns empty list."""
        children = backend.get_children("ml.dl.transformers")
        assert children == []

    def test_get_children_not_found(self, backend: _MockOntologyBackend) -> None:
        """get_children raises KeyError for missing node."""
        with pytest.raises(KeyError, match="not found"):
            backend.get_children("nonexistent")

    def test_get_children_empty_id_raises(
        self, backend: _MockOntologyBackend
    ) -> None:
        """get_children with empty id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            backend.get_children("")

    def test_get_statistics(self, backend: _MockOntologyBackend) -> None:
        """get_statistics returns valid OntologyStats."""
        stats = backend.get_statistics()
        assert isinstance(stats, OntologyStats)
        assert stats.total_nodes == 4
        assert stats.root_count == 1
        assert stats.total_levels > 0
        assert stats.max_depth >= 0


class TestOntologyBackendSubclassPartial:
    """Test that partially implementing OntologyBackend fails correctly."""

    def test_missing_search(self) -> None:
        """Subclass missing search() cannot be instantiated."""

        class Incomplete(OntologyBackend):
            def get_node(self, feature_id: str) -> FeatureNode:
                ...

            def get_children(self, feature_id: str) -> list[FeatureNode]:
                ...

            def get_statistics(self) -> OntologyStats:
                ...

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()  # type: ignore[abstract]

    def test_missing_get_node(self) -> None:
        """Subclass missing get_node() cannot be instantiated."""

        class Incomplete(OntologyBackend):
            def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
                ...

            def get_children(self, feature_id: str) -> list[FeatureNode]:
                ...

            def get_statistics(self) -> OntologyStats:
                ...

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()  # type: ignore[abstract]

    def test_missing_get_children(self) -> None:
        """Subclass missing get_children() cannot be instantiated."""

        class Incomplete(OntologyBackend):
            def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
                ...

            def get_node(self, feature_id: str) -> FeatureNode:
                ...

            def get_statistics(self) -> OntologyStats:
                ...

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()  # type: ignore[abstract]

    def test_missing_get_statistics(self) -> None:
        """Subclass missing get_statistics() cannot be instantiated."""

        class Incomplete(OntologyBackend):
            def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
                ...

            def get_node(self, feature_id: str) -> FeatureNode:
                ...

            def get_children(self, feature_id: str) -> list[FeatureNode]:
                ...

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Test that the ontology package exports all expected symbols."""

    def test_import_from_package(self) -> None:
        """All public symbols are importable from zerorepo.ontology."""
        from zerorepo.ontology import (
            FeatureNode,
            FeaturePath,
            OntologyBackend,
            OntologyStats,
        )

        assert FeatureNode is not None
        assert FeaturePath is not None
        assert OntologyBackend is not None
        assert OntologyStats is not None

    def test_import_from_models(self) -> None:
        """Models are importable from zerorepo.ontology.models."""
        from zerorepo.ontology.models import (
            FeatureNode,
            FeaturePath,
            OntologyStats,
        )

        assert FeatureNode is not None
        assert FeaturePath is not None
        assert OntologyStats is not None

    def test_import_from_backend(self) -> None:
        """Backend is importable from zerorepo.ontology.backend."""
        from zerorepo.ontology.backend import OntologyBackend

        assert OntologyBackend is not None
