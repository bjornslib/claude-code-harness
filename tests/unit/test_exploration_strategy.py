"""Tests for the Exploration Strategy (Task 2.2.2).

Tests cover:
- CoverageTracker registration, visiting, and monotonic guarantee
- CoverageTracker gap analysis and per-level stats
- CoverageStats model
- ExplorationConfig validation
- ExplorationStrategy.propose_queries() with LLM and deterministic fallback
- ExplorationStrategy.explore_round() full cycle
- Coverage completion detection
- Error handling and edge cases
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from zerorepo.llm.models import ModelTier
from zerorepo.ontology.models import FeatureNode, FeaturePath
from zerorepo.selection.exploration import (
    CoverageStats,
    CoverageTracker,
    ExplorationConfig,
    ExplorationResult,
    ExplorationStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    node_id: str,
    name: str,
    level: int = 1,
    parent_id: str | None = None,
    tags: list[str] | None = None,
) -> FeatureNode:
    """Create a test FeatureNode."""
    return FeatureNode(
        id=node_id,
        name=name,
        level=level,
        parent_id=parent_id,
        tags=tags or [],
    )


def _make_path(node_id: str, name: str, score: float) -> FeaturePath:
    """Create a single-node FeaturePath."""
    node = _make_node(node_id, name)
    return FeaturePath(nodes=[node], score=score)


@pytest.fixture
def sample_nodes() -> list[FeatureNode]:
    """Create a set of sample ontology nodes."""
    return [
        _make_node("web", "Web Development", level=0),
        _make_node("web.frontend", "Frontend", level=1, parent_id="web"),
        _make_node("web.backend", "Backend", level=1, parent_id="web"),
        _make_node("web.frontend.react", "React", level=2, parent_id="web.frontend", tags=["ui", "spa"]),
        _make_node("web.frontend.vue", "Vue.js", level=2, parent_id="web.frontend", tags=["ui"]),
        _make_node("web.backend.django", "Django", level=2, parent_id="web.backend", tags=["python"]),
        _make_node("web.backend.fastapi", "FastAPI", level=2, parent_id="web.backend", tags=["python", "async"]),
        _make_node("ml", "Machine Learning", level=0),
        _make_node("ml.nlp", "NLP", level=1, parent_id="ml"),
        _make_node("ml.vision", "Computer Vision", level=1, parent_id="ml"),
    ]


@pytest.fixture
def tracker(sample_nodes: list[FeatureNode]) -> CoverageTracker:
    """Create a tracker with sample nodes registered."""
    t = CoverageTracker()
    t.register_nodes(sample_nodes)
    return t


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLMGateway."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"
    llm.complete.return_value = json.dumps({
        "queries": [
            "machine learning NLP",
            "computer vision deep learning",
            "vue.js frontend framework",
        ]
    })
    return llm


@pytest.fixture
def mock_store() -> MagicMock:
    """Create a mock OntologyBackend."""
    store = MagicMock()
    store.search.return_value = [
        _make_path("ml.nlp", "NLP", 0.85),
        _make_path("ml.vision", "Computer Vision", 0.75),
    ]
    return store


# ---------------------------------------------------------------------------
# CoverageTracker tests
# ---------------------------------------------------------------------------


class TestCoverageTracker:
    """Tests for CoverageTracker."""

    def test_empty_tracker(self) -> None:
        t = CoverageTracker()
        assert t.total_nodes == 0
        assert t.visited_count == 0
        assert t.coverage_ratio == 0.0
        assert t.get_unvisited() == []

    def test_register_node(self, tracker: CoverageTracker) -> None:
        assert tracker.total_nodes == 10
        assert tracker.visited_count == 0

    def test_register_empty_id_raises(self) -> None:
        t = CoverageTracker()
        with pytest.raises(ValueError, match="empty"):
            t.register_node("", "Test", level=0)

    def test_register_feature_node(self) -> None:
        t = CoverageTracker()
        node = _make_node("test", "Test Node", level=1)
        t.register_feature_node(node)
        assert t.total_nodes == 1

    def test_mark_visited(self, tracker: CoverageTracker) -> None:
        newly = tracker.mark_visited("web")
        assert newly is True
        assert tracker.is_visited("web")
        assert tracker.visited_count == 1

    def test_mark_visited_idempotent(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")
        newly = tracker.mark_visited("web")
        assert newly is False  # Already visited
        assert tracker.visited_count == 1  # Still 1

    def test_mark_visited_unregistered_raises(
        self, tracker: CoverageTracker
    ) -> None:
        with pytest.raises(KeyError, match="not been registered"):
            tracker.mark_visited("nonexistent")

    def test_monotonic_guarantee(self, tracker: CoverageTracker) -> None:
        """Coverage can only increase."""
        tracker.mark_visited("web")
        assert tracker.coverage_ratio == pytest.approx(0.1)
        tracker.mark_visited("ml")
        assert tracker.coverage_ratio == pytest.approx(0.2)
        # Visiting same node doesn't change ratio
        tracker.mark_visited("web")
        assert tracker.coverage_ratio == pytest.approx(0.2)

    def test_mark_visited_batch(self, tracker: CoverageTracker) -> None:
        count = tracker.mark_visited_batch(
            ["web", "ml", "web.frontend", "unknown_node"]
        )
        assert count == 3  # unknown_node skipped
        assert tracker.visited_count == 3

    def test_mark_paths_visited(self, tracker: CoverageTracker) -> None:
        paths = [
            _make_path("web", "Web Development", 0.9),
            _make_path("ml", "Machine Learning", 0.8),
        ]
        count = tracker.mark_paths_visited(paths)
        assert count == 2
        assert tracker.is_visited("web")
        assert tracker.is_visited("ml")

    def test_mark_paths_visited_auto_register(self) -> None:
        """Unregistered nodes in paths get auto-registered."""
        t = CoverageTracker()
        paths = [_make_path("new_node", "New Node", 0.9)]
        count = t.mark_paths_visited(paths)
        assert count == 1
        assert t.total_nodes == 1
        assert t.is_visited("new_node")

    def test_coverage_ratio(self, tracker: CoverageTracker) -> None:
        for nid in ["web", "ml", "web.frontend", "web.backend", "ml.nlp"]:
            tracker.mark_visited(nid)
        assert tracker.coverage_ratio == pytest.approx(0.5)

    def test_get_unvisited(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")
        tracker.mark_visited("ml")
        unvisited = tracker.get_unvisited()
        assert len(unvisited) == 8
        assert "web" not in unvisited
        assert "ml" not in unvisited

    def test_get_unvisited_at_level(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")
        unvisited_l0 = tracker.get_unvisited_at_level(0)
        assert "web" not in unvisited_l0
        assert "ml" in unvisited_l0

    def test_reset(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")
        tracker.mark_visited("ml")
        assert tracker.visited_count == 2
        tracker.reset()
        assert tracker.visited_count == 0
        assert tracker.total_nodes == 10  # Registrations preserved


# ---------------------------------------------------------------------------
# Coverage gaps tests
# ---------------------------------------------------------------------------


class TestCoverageGaps:
    """Tests for coverage gap analysis."""

    def test_all_unvisited(self, tracker: CoverageTracker) -> None:
        gaps = tracker.get_coverage_gaps()
        assert len(gaps) > 0
        # All nodes are unvisited, so gaps exist
        total_unvisited = sum(g["unvisited_count"] for g in gaps)
        assert total_unvisited == 10

    def test_partial_coverage(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web.frontend.react")
        gaps = tracker.get_coverage_gaps()
        # Should show gaps where coverage < 100%
        for gap in gaps:
            assert gap["unvisited_count"] > 0

    def test_full_coverage_no_gaps(self, tracker: CoverageTracker) -> None:
        # Visit everything
        for nid in [
            "web", "web.frontend", "web.backend",
            "web.frontend.react", "web.frontend.vue",
            "web.backend.django", "web.backend.fastapi",
            "ml", "ml.nlp", "ml.vision",
        ]:
            tracker.mark_visited(nid)
        gaps = tracker.get_coverage_gaps()
        assert len(gaps) == 0

    def test_gaps_sorted_by_size(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")  # Visit just root
        gaps = tracker.get_coverage_gaps()
        # Gaps should be sorted by unvisited_count descending
        counts = [g["unvisited_count"] for g in gaps]
        assert counts == sorted(counts, reverse=True)

    def test_max_gaps_limit(self, tracker: CoverageTracker) -> None:
        gaps = tracker.get_coverage_gaps(max_gaps=2)
        assert len(gaps) <= 2


# ---------------------------------------------------------------------------
# CoverageStats tests
# ---------------------------------------------------------------------------


class TestCoverageStats:
    """Tests for CoverageStats model."""

    def test_stats_empty_tracker(self) -> None:
        t = CoverageTracker()
        stats = t.get_stats()
        assert stats.total_nodes == 0
        assert stats.visited_count == 0
        assert stats.coverage_ratio == 0.0
        assert stats.unvisited_count == 0

    def test_stats_partial(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")
        tracker.mark_visited("ml")
        stats = tracker.get_stats()
        assert stats.total_nodes == 10
        assert stats.visited_count == 2
        assert stats.coverage_ratio == pytest.approx(0.2)
        assert stats.unvisited_count == 8

    def test_stats_level_coverage(self, tracker: CoverageTracker) -> None:
        tracker.mark_visited("web")  # level 0
        tracker.mark_visited("web.frontend")  # level 1
        stats = tracker.get_stats()

        # Level 0: 1 of 2 visited
        assert stats.level_coverage[0] == (1, 2)
        # Level 1: 1 of 4 visited
        assert stats.level_coverage[1] == (1, 4)
        # Level 2: 0 of 4 visited
        assert stats.level_coverage[2] == (0, 4)

    def test_stats_frozen(self, tracker: CoverageTracker) -> None:
        stats = tracker.get_stats()
        with pytest.raises(Exception):
            stats.total_nodes = 999  # type: ignore


# ---------------------------------------------------------------------------
# ExplorationConfig tests
# ---------------------------------------------------------------------------


class TestExplorationConfig:
    """Tests for ExplorationConfig."""

    def test_defaults(self) -> None:
        cfg = ExplorationConfig()
        assert cfg.augmentation_tier == ModelTier.CHEAP
        assert cfg.max_queries_per_round == 5
        assert cfg.min_coverage_for_completion == 0.8
        assert cfg.prefer_underexplored_levels is True
        assert cfg.search_top_k == 10

    def test_custom_values(self) -> None:
        cfg = ExplorationConfig(
            augmentation_tier=ModelTier.MEDIUM,
            max_queries_per_round=10,
            min_coverage_for_completion=0.95,
            prefer_underexplored_levels=False,
        )
        assert cfg.max_queries_per_round == 10
        assert cfg.min_coverage_for_completion == 0.95

    def test_invalid_max_queries(self) -> None:
        with pytest.raises(Exception):
            ExplorationConfig(max_queries_per_round=0)


# ---------------------------------------------------------------------------
# ExplorationStrategy tests
# ---------------------------------------------------------------------------


class TestExplorationStrategy:
    """Tests for ExplorationStrategy."""

    def test_properties(
        self,
        tracker: CoverageTracker,
        mock_store: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        strategy = ExplorationStrategy(
            coverage=tracker,
            store=mock_store,
            llm_gateway=mock_llm,
        )
        assert strategy.coverage is tracker
        assert strategy.config is not None

    def test_is_coverage_complete(self, tracker: CoverageTracker) -> None:
        cfg = ExplorationConfig(min_coverage_for_completion=0.5)
        strategy = ExplorationStrategy(coverage=tracker, config=cfg)

        assert not strategy.is_coverage_complete()

        # Visit half the nodes
        for nid in ["web", "ml", "web.frontend", "web.backend", "ml.nlp"]:
            tracker.mark_visited(nid)

        assert strategy.is_coverage_complete()

    def test_propose_queries_with_llm(
        self,
        tracker: CoverageTracker,
        mock_llm: MagicMock,
    ) -> None:
        strategy = ExplorationStrategy(
            coverage=tracker, llm_gateway=mock_llm
        )
        queries = strategy.propose_queries(n=3)
        assert len(queries) == 3
        mock_llm.complete.assert_called_once()

    def test_propose_queries_deterministic_fallback(
        self, tracker: CoverageTracker
    ) -> None:
        """When no LLM, uses deterministic gap-based queries."""
        strategy = ExplorationStrategy(coverage=tracker, llm_gateway=None)
        queries = strategy.propose_queries(n=3)
        assert len(queries) > 0
        # Queries should contain node names from gaps
        all_names = " ".join(queries)
        # At least some names from our ontology
        assert any(
            name in all_names
            for name in [
                "Web Development", "Frontend", "Backend", "React",
                "Machine Learning", "NLP", "Computer Vision",
            ]
        )

    def test_propose_queries_coverage_complete(
        self, tracker: CoverageTracker
    ) -> None:
        cfg = ExplorationConfig(min_coverage_for_completion=0.0)
        strategy = ExplorationStrategy(coverage=tracker, config=cfg)
        # Coverage is 0% but threshold is 0%, so complete
        queries = strategy.propose_queries()
        assert queries == []

    def test_propose_queries_llm_error_fallback(
        self,
        tracker: CoverageTracker,
        mock_llm: MagicMock,
    ) -> None:
        mock_llm.complete.side_effect = RuntimeError("LLM error")
        strategy = ExplorationStrategy(
            coverage=tracker, llm_gateway=mock_llm
        )
        queries = strategy.propose_queries(n=3)
        # Should fall back to deterministic
        assert len(queries) > 0


# ---------------------------------------------------------------------------
# explore_round tests
# ---------------------------------------------------------------------------


class TestExploreRound:
    """Tests for the full explore_round() cycle."""

    def test_explore_round_basic(
        self,
        tracker: CoverageTracker,
        mock_store: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        strategy = ExplorationStrategy(
            coverage=tracker,
            store=mock_store,
            llm_gateway=mock_llm,
        )
        result = strategy.explore_round()

        assert isinstance(result, ExplorationResult)
        assert len(result.queries) > 0
        assert result.coverage_after >= result.coverage_before
        assert result.newly_visited >= 0

    def test_explore_round_increases_coverage(
        self,
        tracker: CoverageTracker,
        mock_store: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        strategy = ExplorationStrategy(
            coverage=tracker,
            store=mock_store,
            llm_gateway=mock_llm,
        )
        before = tracker.coverage_ratio
        result = strategy.explore_round()
        assert result.coverage_after >= before

    def test_explore_round_already_complete(
        self, tracker: CoverageTracker
    ) -> None:
        cfg = ExplorationConfig(min_coverage_for_completion=0.0)
        strategy = ExplorationStrategy(coverage=tracker, config=cfg)
        result = strategy.explore_round()
        assert result.is_complete is True
        assert result.queries == []

    def test_explore_round_no_store(
        self,
        tracker: CoverageTracker,
        mock_llm: MagicMock,
    ) -> None:
        strategy = ExplorationStrategy(
            coverage=tracker,
            store=None,
            llm_gateway=mock_llm,
        )
        result = strategy.explore_round()
        # Should generate queries but not retrieve paths
        assert result.paths == []

    def test_explore_round_store_error(
        self,
        tracker: CoverageTracker,
        mock_llm: MagicMock,
    ) -> None:
        error_store = MagicMock()
        error_store.search.side_effect = RuntimeError("Store error")

        strategy = ExplorationStrategy(
            coverage=tracker,
            store=error_store,
            llm_gateway=mock_llm,
        )
        # Should not raise
        result = strategy.explore_round()
        assert isinstance(result, ExplorationResult)


# ---------------------------------------------------------------------------
# ExplorationResult tests
# ---------------------------------------------------------------------------


class TestExplorationResult:
    """Tests for ExplorationResult model."""

    def test_empty_result(self) -> None:
        result = ExplorationResult()
        assert result.queries == []
        assert result.paths == []
        assert result.newly_visited == 0
        assert result.is_complete is False

    def test_frozen(self) -> None:
        result = ExplorationResult()
        with pytest.raises(Exception):
            result.newly_visited = 99  # type: ignore

    def test_full_result(self) -> None:
        result = ExplorationResult(
            queries=["test query"],
            paths=[_make_path("a", "A", 0.9)],
            newly_visited=1,
            coverage_before=0.0,
            coverage_after=0.1,
            gaps_analyzed=5,
            is_complete=False,
        )
        assert len(result.queries) == 1
        assert len(result.paths) == 1
        assert result.coverage_after > result.coverage_before


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_package(self) -> None:
        from zerorepo.selection import (
            CoverageStats,
            CoverageTracker,
            ExplorationConfig,
            ExplorationResult,
            ExplorationStrategy,
        )
        assert CoverageTracker is not None
        assert ExplorationStrategy is not None

    def test_import_from_module(self) -> None:
        from zerorepo.selection.exploration import (
            CoverageStats,
            CoverageTracker,
            ExplorationConfig,
            ExplorationResult,
            ExplorationStrategy,
        )
        assert CoverageStats is not None


# ---------------------------------------------------------------------------
# Internal method tests
# ---------------------------------------------------------------------------


class TestInternalMethods:
    """Tests for internal helper methods."""

    def test_format_gaps(
        self,
        tracker: CoverageTracker,
        mock_llm: MagicMock,
    ) -> None:
        strategy = ExplorationStrategy(
            coverage=tracker, llm_gateway=mock_llm
        )
        gaps = tracker.get_coverage_gaps()
        text = strategy._format_gaps(gaps)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_format_visited_summary_empty(
        self, tracker: CoverageTracker
    ) -> None:
        strategy = ExplorationStrategy(coverage=tracker)
        summary = strategy._format_visited_summary()
        assert "no nodes" in summary.lower()

    def test_format_visited_summary_with_visits(
        self, tracker: CoverageTracker
    ) -> None:
        tracker.mark_visited("web")
        tracker.mark_visited("ml")
        strategy = ExplorationStrategy(coverage=tracker)
        summary = strategy._format_visited_summary()
        assert "Web Development" in summary or "Machine Learning" in summary

    def test_parse_queries_valid_json(
        self, tracker: CoverageTracker
    ) -> None:
        strategy = ExplorationStrategy(coverage=tracker)
        text = '{"queries": ["auth", "react"]}'
        result = strategy._parse_queries_response(text, 5)
        assert result == ["auth", "react"]

    def test_parse_queries_json_in_text(
        self, tracker: CoverageTracker
    ) -> None:
        strategy = ExplorationStrategy(coverage=tracker)
        text = 'Here: {"queries": ["a", "b"]}\nDone'
        result = strategy._parse_queries_response(text, 5)
        assert result == ["a", "b"]

    def test_parse_queries_fallback_lines(
        self, tracker: CoverageTracker
    ) -> None:
        strategy = ExplorationStrategy(coverage=tracker)
        text = "- authentication flow\n- websocket messaging"
        result = strategy._parse_queries_response(text, 5)
        assert "authentication flow" in result
        assert "websocket messaging" in result

    def test_generate_queries_deterministic(
        self, tracker: CoverageTracker
    ) -> None:
        strategy = ExplorationStrategy(coverage=tracker)
        gaps = tracker.get_coverage_gaps(max_gaps=5)
        queries = strategy._generate_queries_deterministic(gaps, 3)
        assert len(queries) <= 3
        assert all(isinstance(q, str) for q in queries)
