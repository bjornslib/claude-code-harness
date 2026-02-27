"""Unit tests for the LLM-Generated Ontology Backend.

Tests cover LLMFeatureNodeResponse, LLMOntologyResponse, LLMBackendConfig,
and the LLMOntologyBackend class as defined in Task 2.1.4.

All LLM calls are mocked – no actual API requests are made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from cobuilder.repomap.llm.exceptions import LLMGatewayError
from cobuilder.repomap.llm.gateway import LLMGateway
from cobuilder.repomap.llm.models import GatewayConfig, ModelTier
from cobuilder.repomap.llm.prompt_templates import PromptTemplate
from cobuilder.repomap.ontology.backend import OntologyBackend
from cobuilder.repomap.ontology.llm_backend import (
    LLMBackendConfig,
    LLMFeatureNodeResponse,
    LLMOntologyBackend,
    LLMOntologyResponse,
)
from cobuilder.repomap.ontology.models import FeatureNode, FeaturePath, OntologyStats


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_llm_response_nodes() -> list[dict]:
    """Return a sample list of LLM-generated node dicts."""
    return [
        {
            "id": "auth",
            "name": "Authentication",
            "description": "User authentication and identity management",
            "parent_id": None,
            "level": 0,
            "tags": ["security", "identity"],
        },
        {
            "id": "auth.jwt",
            "name": "JWT Tokens",
            "description": "JSON Web Token based authentication",
            "parent_id": "auth",
            "level": 1,
            "tags": ["jwt", "tokens"],
        },
        {
            "id": "auth.oauth",
            "name": "OAuth 2.0",
            "description": "OAuth 2.0 authorization framework",
            "parent_id": "auth",
            "level": 1,
            "tags": ["oauth", "authorization"],
        },
        {
            "id": "auth.oauth.google",
            "name": "Google OAuth",
            "description": "Google-specific OAuth integration",
            "parent_id": "auth.oauth",
            "level": 2,
            "tags": ["google", "social-login"],
        },
    ]


def _make_llm_response_json(nodes: list[dict] | None = None) -> str:
    """Return a JSON string simulating LLM output."""
    return json.dumps({"nodes": nodes or _make_llm_response_nodes()})


@pytest.fixture()
def mock_gateway() -> MagicMock:
    """Create a mock LLMGateway with complete_json pre-configured."""
    gw = MagicMock(spec=LLMGateway)
    # Default: return a valid LLMOntologyResponse
    gw.complete_json.return_value = LLMOntologyResponse(
        nodes=[
            LLMFeatureNodeResponse(**node)
            for node in _make_llm_response_nodes()
        ]
    )
    return gw


@pytest.fixture()
def mock_prompt_template() -> MagicMock:
    """Create a mock PromptTemplate."""
    pt = MagicMock(spec=PromptTemplate)
    pt.render.return_value = "Mocked prompt for ontology generation"
    return pt


@pytest.fixture()
def backend(
    mock_gateway: MagicMock,
    mock_prompt_template: MagicMock,
) -> LLMOntologyBackend:
    """Create a backend with mocked dependencies."""
    return LLMOntologyBackend(
        gateway=mock_gateway,
        prompt_template=mock_prompt_template,
    )


@pytest.fixture()
def seeded_backend(backend: LLMOntologyBackend) -> LLMOntologyBackend:
    """Create a backend pre-seeded with cached nodes."""
    backend.add_nodes([
        FeatureNode(
            id="auth",
            name="Authentication",
            description="User authentication",
            level=0,
            tags=["security"],
        ),
        FeatureNode(
            id="auth.jwt",
            name="JWT Tokens",
            description="JWT-based auth",
            parent_id="auth",
            level=1,
            tags=["jwt"],
        ),
        FeatureNode(
            id="auth.oauth",
            name="OAuth 2.0",
            description="OAuth integration",
            parent_id="auth",
            level=1,
            tags=["oauth"],
        ),
        FeatureNode(
            id="auth.oauth.google",
            name="Google OAuth",
            description="Google OAuth integration",
            parent_id="auth.oauth",
            level=2,
            tags=["google"],
        ),
    ])
    return backend


# ---------------------------------------------------------------------------
# LLMFeatureNodeResponse Tests
# ---------------------------------------------------------------------------


class TestLLMFeatureNodeResponse:
    """Test the LLM response model for individual nodes."""

    def test_create_valid_node(self) -> None:
        """Create a valid LLM node response."""
        node = LLMFeatureNodeResponse(
            id="ml.transformers",
            name="Transformers",
            description="Attention-based architectures",
            parent_id="ml",
            level=2,
            tags=["nlp", "attention"],
        )
        assert node.id == "ml.transformers"
        assert node.name == "Transformers"
        assert node.level == 2
        assert len(node.tags) == 2

    def test_create_root_node(self) -> None:
        """Create a root node with no parent."""
        node = LLMFeatureNodeResponse(
            id="ml",
            name="Machine Learning",
            level=0,
        )
        assert node.parent_id is None
        assert node.level == 0

    def test_empty_id_rejected(self) -> None:
        """Empty id should be rejected."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            LLMFeatureNodeResponse(id="", name="Test", level=0)

    def test_empty_name_rejected(self) -> None:
        """Empty name should be rejected."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            LLMFeatureNodeResponse(id="test", name="", level=0)

    def test_negative_level_rejected(self) -> None:
        """Negative level should be rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            LLMFeatureNodeResponse(id="test", name="Test", level=-1)

    def test_tags_cleaned(self) -> None:
        """Tags with whitespace and empty entries should be cleaned."""
        node = LLMFeatureNodeResponse(
            id="test",
            name="Test",
            level=0,
            tags=["  valid  ", "", "  ", "also-valid"],
        )
        assert node.tags == ["valid", "also-valid"]

    def test_to_feature_node(self) -> None:
        """Convert to FeatureNode successfully."""
        llm_node = LLMFeatureNodeResponse(
            id="web.react",
            name="React",
            description="React framework",
            parent_id="web",
            level=1,
            tags=["frontend", "react"],
        )
        feature_node = llm_node.to_feature_node()
        assert isinstance(feature_node, FeatureNode)
        assert feature_node.id == "web.react"
        assert feature_node.metadata["source"] == "llm-generated"
        assert feature_node.tags == ["frontend", "react"]

    def test_to_feature_node_minimal(self) -> None:
        """Convert minimal node to FeatureNode."""
        llm_node = LLMFeatureNodeResponse(
            id="root",
            name="Root",
            level=0,
        )
        feature_node = llm_node.to_feature_node()
        assert feature_node.id == "root"
        assert feature_node.parent_id is None
        assert feature_node.description is None


# ---------------------------------------------------------------------------
# LLMOntologyResponse Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyResponse:
    """Test the top-level LLM response model."""

    def test_create_valid_response(self) -> None:
        """Create a valid response with multiple nodes."""
        response = LLMOntologyResponse(
            nodes=[
                LLMFeatureNodeResponse(id="a", name="A", level=0),
                LLMFeatureNodeResponse(
                    id="a.b", name="B", level=1, parent_id="a"
                ),
            ]
        )
        assert len(response.nodes) == 2

    def test_empty_nodes_rejected(self) -> None:
        """Empty nodes list should be rejected."""
        with pytest.raises(ValidationError, match="at least 1"):
            LLMOntologyResponse(nodes=[])

    def test_parse_from_json(self) -> None:
        """Parse response from JSON string."""
        json_str = _make_llm_response_json()
        response = LLMOntologyResponse.model_validate_json(json_str)
        assert len(response.nodes) == 4
        assert response.nodes[0].id == "auth"
        assert response.nodes[1].parent_id == "auth"


# ---------------------------------------------------------------------------
# LLMBackendConfig Tests
# ---------------------------------------------------------------------------


class TestLLMBackendConfig:
    """Test the LLM backend configuration model."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = LLMBackendConfig()
        assert config.model == "gpt-4o-mini"
        assert config.tier == ModelTier.CHEAP
        assert config.max_nodes == 20
        assert config.cache_enabled is True
        assert config.domain_hint is None
        assert config.template_name == "ontology_generation"

    def test_custom_config(self) -> None:
        """Custom config values are accepted."""
        config = LLMBackendConfig(
            model="gpt-4o",
            tier=ModelTier.STRONG,
            max_nodes=50,
            cache_enabled=False,
            domain_hint="web development",
        )
        assert config.model == "gpt-4o"
        assert config.tier == ModelTier.STRONG
        assert config.max_nodes == 50
        assert config.cache_enabled is False
        assert config.domain_hint == "web development"

    def test_max_nodes_bounds(self) -> None:
        """max_nodes must be between 1 and 100."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            LLMBackendConfig(max_nodes=0)
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            LLMBackendConfig(max_nodes=101)


# ---------------------------------------------------------------------------
# LLMOntologyBackend Construction Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendConstruction:
    """Test backend construction and properties."""

    def test_create_with_defaults(self, mock_gateway: MagicMock) -> None:
        """Create backend with default config."""
        backend = LLMOntologyBackend(gateway=mock_gateway)
        assert backend.gateway is mock_gateway
        assert isinstance(backend.config, LLMBackendConfig)
        assert backend.generation_count == 0
        assert backend.node_cache == {}

    def test_create_with_custom_config(
        self, mock_gateway: MagicMock
    ) -> None:
        """Create backend with custom config."""
        config = LLMBackendConfig(model="gpt-4o", max_nodes=50)
        backend = LLMOntologyBackend(
            gateway=mock_gateway, config=config
        )
        assert backend.config.model == "gpt-4o"
        assert backend.config.max_nodes == 50

    def test_create_with_custom_prompt_template(
        self,
        mock_gateway: MagicMock,
        mock_prompt_template: MagicMock,
    ) -> None:
        """Create backend with custom prompt template."""
        backend = LLMOntologyBackend(
            gateway=mock_gateway,
            prompt_template=mock_prompt_template,
        )
        # prompt_template is used internally; just verify no error
        assert backend.generation_count == 0


# ---------------------------------------------------------------------------
# LLMOntologyBackend Cache Management Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendCache:
    """Test node cache management methods."""

    def test_add_node(self, backend: LLMOntologyBackend) -> None:
        """Add a single node to the cache."""
        node = FeatureNode(id="test", name="Test", level=0)
        backend.add_node(node)
        assert "test" in backend.node_cache
        assert backend.node_cache["test"] == node

    def test_add_nodes(self, backend: LLMOntologyBackend) -> None:
        """Add multiple nodes to the cache."""
        nodes = [
            FeatureNode(id="a", name="A", level=0),
            FeatureNode(id="b", name="B", level=0),
        ]
        backend.add_nodes(nodes)
        assert len(backend.node_cache) == 2
        assert "a" in backend.node_cache
        assert "b" in backend.node_cache

    def test_clear_cache(self, seeded_backend: LLMOntologyBackend) -> None:
        """Clear all cached nodes."""
        assert len(seeded_backend.node_cache) == 4
        seeded_backend.clear_cache()
        assert len(seeded_backend.node_cache) == 0

    def test_add_node_overwrites_existing(
        self, backend: LLMOntologyBackend
    ) -> None:
        """Adding a node with an existing ID overwrites it."""
        node1 = FeatureNode(id="test", name="Original", level=0)
        node2 = FeatureNode(id="test", name="Updated", level=0)
        backend.add_node(node1)
        backend.add_node(node2)
        assert backend.node_cache["test"].name == "Updated"

    def test_node_cache_is_copy(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """node_cache returns a copy, not the internal dict."""
        cache = seeded_backend.node_cache
        cache["injected"] = FeatureNode(id="injected", name="Bad", level=0)
        assert "injected" not in seeded_backend.node_cache


# ---------------------------------------------------------------------------
# LLMOntologyBackend.search() Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendSearch:
    """Test the search method with mocked LLM calls."""

    def test_search_returns_feature_paths(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() returns a list of FeaturePaths."""
        results = backend.search("authentication", top_k=5)
        assert isinstance(results, list)
        assert all(isinstance(r, FeaturePath) for r in results)
        assert len(results) > 0

    def test_search_increments_generation_count(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() increments the generation counter."""
        assert backend.generation_count == 0
        backend.search("authentication")
        assert backend.generation_count == 1
        backend.search("database")
        assert backend.generation_count == 2

    def test_search_caches_generated_nodes(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() caches generated nodes for later retrieval."""
        assert len(backend.node_cache) == 0
        backend.search("authentication")
        assert len(backend.node_cache) == 4  # 4 nodes in mock response

    def test_search_empty_query_raises(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() with empty query raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            backend.search("")

    def test_search_whitespace_query_raises(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() with whitespace-only query raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            backend.search("   ")

    def test_search_zero_top_k_raises(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() with non-positive top_k raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            backend.search("test", top_k=0)

    def test_search_negative_top_k_raises(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() with negative top_k raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            backend.search("test", top_k=-1)

    def test_search_respects_top_k(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() returns at most top_k results."""
        results = backend.search("authentication", top_k=2)
        assert len(results) <= 2

    def test_search_results_sorted_by_score(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() results are sorted by score descending."""
        results = backend.search("authentication", top_k=10)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_search_results_have_valid_scores(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() result scores are between 0.0 and 1.0."""
        results = backend.search("authentication", top_k=10)
        for result in results:
            assert 0.0 <= result.score <= 1.0

    def test_search_calls_llm_gateway(
        self,
        backend: LLMOntologyBackend,
        mock_gateway: MagicMock,
    ) -> None:
        """search() calls the LLM gateway's complete_json."""
        backend.search("authentication")
        mock_gateway.complete_json.assert_called_once()
        call_args = mock_gateway.complete_json.call_args
        assert call_args.kwargs["model"] == "gpt-4o-mini"
        assert call_args.kwargs["response_schema"] is LLMOntologyResponse

    def test_search_uses_prompt_template(
        self,
        backend: LLMOntologyBackend,
        mock_prompt_template: MagicMock,
    ) -> None:
        """search() renders the prompt template with correct args."""
        backend.search("authentication", top_k=5)
        mock_prompt_template.render.assert_called_once()
        call_args = mock_prompt_template.render.call_args
        assert call_args.args[0] == "ontology_generation"
        assert call_args.kwargs["query"] == "authentication"

    def test_search_llm_error_propagates(
        self,
        backend: LLMOntologyBackend,
        mock_gateway: MagicMock,
    ) -> None:
        """search() propagates LLM gateway errors."""
        mock_gateway.complete_json.side_effect = LLMGatewayError(
            "API error"
        )
        with pytest.raises(LLMGatewayError, match="API error"):
            backend.search("authentication")

    def test_search_with_domain_hint(
        self,
        mock_gateway: MagicMock,
        mock_prompt_template: MagicMock,
    ) -> None:
        """search() passes domain_hint to the prompt template."""
        config = LLMBackendConfig(domain_hint="web development")
        backend = LLMOntologyBackend(
            gateway=mock_gateway,
            config=config,
            prompt_template=mock_prompt_template,
        )
        backend.search("react hooks")
        call_args = mock_prompt_template.render.call_args
        assert call_args.kwargs["domain_hint"] == "web development"

    def test_search_with_existing_cache_sends_context(
        self,
        seeded_backend: LLMOntologyBackend,
        mock_prompt_template: MagicMock,
    ) -> None:
        """search() sends existing cached nodes as context."""
        seeded_backend.search("authentication patterns")
        call_args = mock_prompt_template.render.call_args
        existing = call_args.kwargs["existing_nodes"]
        assert existing is not None
        assert len(existing) > 0

    def test_search_paths_trace_to_root(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() paths trace from root to leaf."""
        results = backend.search("authentication")
        # At least one path should have multiple nodes (root -> child)
        multi_node_paths = [r for r in results if r.depth > 1]
        assert len(multi_node_paths) > 0
        for path in multi_node_paths:
            # First node should be root (or parent not in cache)
            assert path.root.is_root or path.root.parent_id not in backend.node_cache


# ---------------------------------------------------------------------------
# LLMOntologyBackend.get_node() Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendGetNode:
    """Test the get_node method."""

    def test_get_existing_node(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_node() returns a cached node."""
        node = seeded_backend.get_node("auth")
        assert isinstance(node, FeatureNode)
        assert node.id == "auth"
        assert node.name == "Authentication"

    def test_get_child_node(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_node() returns a child node."""
        node = seeded_backend.get_node("auth.jwt")
        assert node.id == "auth.jwt"
        assert node.parent_id == "auth"

    def test_get_nonexistent_node_raises(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_node() raises KeyError for missing node."""
        with pytest.raises(KeyError, match="not found"):
            seeded_backend.get_node("nonexistent")

    def test_get_node_empty_id_raises(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_node() with empty id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            seeded_backend.get_node("")

    def test_get_node_whitespace_id_raises(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_node() with whitespace-only id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            seeded_backend.get_node("   ")


# ---------------------------------------------------------------------------
# LLMOntologyBackend.get_children() Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendGetChildren:
    """Test the get_children method."""

    def test_get_children_returns_children(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() returns direct children."""
        children = seeded_backend.get_children("auth")
        assert len(children) == 2
        child_ids = {c.id for c in children}
        assert child_ids == {"auth.jwt", "auth.oauth"}

    def test_get_children_leaf_returns_empty(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() on a leaf node returns empty list."""
        children = seeded_backend.get_children("auth.jwt")
        assert children == []

    def test_get_children_nested(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() returns correct children for nested nodes."""
        children = seeded_backend.get_children("auth.oauth")
        assert len(children) == 1
        assert children[0].id == "auth.oauth.google"

    def test_get_children_nonexistent_raises(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() raises KeyError for missing parent."""
        with pytest.raises(KeyError, match="not found"):
            seeded_backend.get_children("nonexistent")

    def test_get_children_empty_id_raises(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() with empty id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            seeded_backend.get_children("")

    def test_get_children_whitespace_id_raises(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() with whitespace-only id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            seeded_backend.get_children("   ")


# ---------------------------------------------------------------------------
# LLMOntologyBackend.get_statistics() Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendGetStatistics:
    """Test the get_statistics method."""

    def test_empty_ontology_stats(
        self, backend: LLMOntologyBackend
    ) -> None:
        """Empty backend returns zero stats."""
        stats = backend.get_statistics()
        assert isinstance(stats, OntologyStats)
        assert stats.total_nodes == 0
        assert stats.total_levels == 0
        assert stats.avg_children == 0.0
        assert stats.max_depth == 0
        assert stats.root_count == 0
        assert stats.leaf_count == 0
        assert stats.nodes_with_embeddings == 0
        assert stats.metadata["backend"] == "llm-generated"
        assert stats.metadata["generation_count"] == 0

    def test_seeded_ontology_stats(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Seeded backend returns correct stats."""
        stats = seeded_backend.get_statistics()
        assert stats.total_nodes == 4
        assert stats.root_count == 1  # only "auth" is root
        assert stats.total_levels == 3  # levels 0, 1, 2
        assert stats.max_depth == 2
        assert stats.metadata["backend"] == "llm-generated"

    def test_stats_leaf_count(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Leaf count is computed correctly."""
        stats = seeded_backend.get_statistics()
        # auth.jwt and auth.oauth.google are leaves
        # auth has children (auth.jwt, auth.oauth)
        # auth.oauth has children (auth.oauth.google)
        assert stats.leaf_count == 2  # auth.jwt and auth.oauth.google

    def test_stats_avg_children(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Average children is computed correctly."""
        stats = seeded_backend.get_statistics()
        # Non-leaf nodes: auth (2 children), auth.oauth (1 child)
        # Total children = 3 (auth.jwt, auth.oauth, auth.oauth.google)
        # avg_children = 3 / 2 = 1.5
        assert stats.avg_children == 1.5

    def test_stats_embedding_coverage(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Embedding coverage is correct (no embeddings in seeded data)."""
        stats = seeded_backend.get_statistics()
        assert stats.nodes_with_embeddings == 0
        assert stats.embedding_coverage == 0.0

    def test_stats_with_embeddings(
        self, backend: LLMOntologyBackend
    ) -> None:
        """Stats track nodes with embeddings."""
        backend.add_node(
            FeatureNode(
                id="test",
                name="Test",
                level=0,
                embedding=[0.1, 0.2, 0.3],
            )
        )
        stats = backend.get_statistics()
        assert stats.nodes_with_embeddings == 1
        assert stats.embedding_coverage == 1.0

    def test_stats_generation_count(
        self, backend: LLMOntologyBackend
    ) -> None:
        """Stats include generation count."""
        backend.search("test query")
        stats = backend.get_statistics()
        assert stats.metadata["generation_count"] == 1


# ---------------------------------------------------------------------------
# LLMOntologyBackend Path Tracing Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendPathTracing:
    """Test the internal path tracing logic."""

    def test_trace_root_node(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Tracing a root node returns a single-node path."""
        root = seeded_backend.get_node("auth")
        path = seeded_backend._trace_path(root)
        assert len(path) == 1
        assert path[0].id == "auth"

    def test_trace_child_node(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Tracing a child node returns root -> child path."""
        child = seeded_backend.get_node("auth.jwt")
        path = seeded_backend._trace_path(child)
        assert len(path) == 2
        assert path[0].id == "auth"
        assert path[1].id == "auth.jwt"

    def test_trace_deep_node(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """Tracing a deep node returns full root -> ... -> leaf path."""
        deep = seeded_backend.get_node("auth.oauth.google")
        path = seeded_backend._trace_path(deep)
        assert len(path) == 3
        assert path[0].id == "auth"
        assert path[1].id == "auth.oauth"
        assert path[2].id == "auth.oauth.google"

    def test_trace_orphan_node(
        self, backend: LLMOntologyBackend
    ) -> None:
        """Tracing an orphan (parent not in cache) stops at the orphan."""
        orphan = FeatureNode(
            id="orphan.child",
            name="Orphan Child",
            level=1,
            parent_id="missing.parent",
        )
        backend.add_node(orphan)
        path = backend._trace_path(orphan)
        assert len(path) == 1
        assert path[0].id == "orphan.child"

    def test_trace_cycle_detection(
        self, backend: LLMOntologyBackend
    ) -> None:
        """Tracing detects and handles cycles gracefully."""
        # Create a cycle: a -> b -> a
        node_a = FeatureNode(
            id="cycle.a",
            name="A",
            level=0,
            parent_id="cycle.b",
        )
        node_b = FeatureNode(
            id="cycle.b",
            name="B",
            level=1,
            parent_id="cycle.a",
        )
        backend.add_node(node_a)
        backend.add_node(node_b)

        # Should not infinite loop – cycle detection kicks in
        path = backend._trace_path(node_a)
        assert len(path) <= 3  # At most: a -> b -> (cycle detected)


# ---------------------------------------------------------------------------
# LLMOntologyBackend Invalid Response Handling
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendInvalidResponses:
    """Test graceful handling of invalid LLM responses."""

    def test_response_with_self_referencing_node(
        self,
        mock_gateway: MagicMock,
        mock_prompt_template: MagicMock,
    ) -> None:
        """Nodes with self-referencing parent_id are skipped."""
        mock_gateway.complete_json.return_value = LLMOntologyResponse(
            nodes=[
                LLMFeatureNodeResponse(
                    id="root", name="Root", level=0
                ),
                LLMFeatureNodeResponse(
                    id="self-ref",
                    name="Self Ref",
                    level=1,
                    parent_id="self-ref",  # Self-referencing!
                ),
            ]
        )
        backend = LLMOntologyBackend(
            gateway=mock_gateway,
            prompt_template=mock_prompt_template,
        )
        results = backend.search("test")
        # The self-referencing node should be skipped
        assert "root" in backend.node_cache
        assert "self-ref" not in backend.node_cache

    def test_response_with_mixed_valid_invalid(
        self,
        mock_gateway: MagicMock,
        mock_prompt_template: MagicMock,
    ) -> None:
        """Valid nodes are cached even if some nodes fail validation."""
        mock_gateway.complete_json.return_value = LLMOntologyResponse(
            nodes=[
                LLMFeatureNodeResponse(
                    id="valid", name="Valid", level=0
                ),
                LLMFeatureNodeResponse(
                    id="also-valid",
                    name="Also Valid",
                    level=1,
                    parent_id="valid",
                ),
            ]
        )
        backend = LLMOntologyBackend(
            gateway=mock_gateway,
            prompt_template=mock_prompt_template,
        )
        results = backend.search("test")
        assert "valid" in backend.node_cache
        assert "also-valid" in backend.node_cache


# ---------------------------------------------------------------------------
# LLMOntologyBackend OntologyBackend Conformance Tests
# ---------------------------------------------------------------------------


class TestLLMOntologyBackendConformance:
    """Verify that LLMOntologyBackend fully conforms to OntologyBackend."""

    def test_is_subclass_of_ontology_backend(self) -> None:
        """LLMOntologyBackend is a subclass of OntologyBackend."""
        assert issubclass(LLMOntologyBackend, OntologyBackend)

    def test_can_be_instantiated(
        self, mock_gateway: MagicMock
    ) -> None:
        """LLMOntologyBackend can be instantiated (all abstract methods implemented)."""
        backend = LLMOntologyBackend(gateway=mock_gateway)
        assert isinstance(backend, OntologyBackend)

    def test_search_signature_matches(
        self, backend: LLMOntologyBackend
    ) -> None:
        """search() accepts the same signature as the base class."""
        results = backend.search("test query", top_k=3)
        assert isinstance(results, list)

    def test_get_node_signature_matches(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_node() accepts the same signature as the base class."""
        node = seeded_backend.get_node("auth")
        assert isinstance(node, FeatureNode)

    def test_get_children_signature_matches(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_children() accepts the same signature as the base class."""
        children = seeded_backend.get_children("auth")
        assert isinstance(children, list)

    def test_get_statistics_signature_matches(
        self, seeded_backend: LLMOntologyBackend
    ) -> None:
        """get_statistics() accepts the same signature as the base class."""
        stats = seeded_backend.get_statistics()
        assert isinstance(stats, OntologyStats)


# ---------------------------------------------------------------------------
# Package Import Tests
# ---------------------------------------------------------------------------


class TestLLMBackendPackageImports:
    """Test that the LLM backend is importable from the ontology package."""

    def test_import_from_package(self) -> None:
        """LLM backend classes are importable from cobuilder.repomap.ontology."""
        from cobuilder.repomap.ontology import LLMBackendConfig, LLMOntologyBackend

        assert LLMOntologyBackend is not None
        assert LLMBackendConfig is not None

    def test_import_from_module(self) -> None:
        """LLM backend classes are importable from the module."""
        from cobuilder.repomap.ontology.llm_backend import (
            LLMBackendConfig,
            LLMFeatureNodeResponse,
            LLMOntologyBackend,
            LLMOntologyResponse,
        )

        assert LLMOntologyBackend is not None
        assert LLMBackendConfig is not None
        assert LLMFeatureNodeResponse is not None
        assert LLMOntologyResponse is not None
