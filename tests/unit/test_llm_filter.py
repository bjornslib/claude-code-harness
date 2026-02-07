"""Tests for the LLM Filtering Pipeline (Task 2.2.4).

Tests cover:
- LLMFilterConfig validation and defaults
- FilterDecision model
- FilterResult model and properties
- LLMFilter.filter() with mocked LLM
- Initial filter with batch processing
- Self-check stage with overrides
- Passthrough when no LLM available
- Error handling (LLM failures, malformed responses)
- Edge cases (empty candidates, all pruned, all kept)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from zerorepo.llm.models import ModelTier
from zerorepo.ontology.models import FeatureNode, FeaturePath
from zerorepo.selection.llm_filter import (
    FilterDecision,
    FilterResult,
    LLMFilter,
    LLMFilterConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_path(
    node_id: str, name: str, score: float, desc: str = ""
) -> FeaturePath:
    """Create a test FeaturePath."""
    node = FeatureNode(
        id=node_id,
        name=name,
        level=1,
        description=desc or f"Description of {name}",
    )
    return FeaturePath(nodes=[node], score=score)


@pytest.fixture
def candidates() -> list[FeaturePath]:
    """Sample candidates for filtering."""
    return [
        _make_path("auth", "Authentication", 0.9, "User login and registration"),
        _make_path("api", "REST API", 0.85, "RESTful API endpoints"),
        _make_path("mobile_ui", "Mobile UI", 0.7, "Mobile interface design"),
        _make_path("db", "Database", 0.8, "PostgreSQL data storage"),
    ]


@pytest.fixture
def mock_llm_keep_all() -> MagicMock:
    """Mock LLM that keeps all features."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"
    llm.complete.return_value = json.dumps({
        "decisions": [
            {"feature_id": "auth", "action": "keep", "confidence": 0.95, "reason": "Relevant"},
            {"feature_id": "api", "action": "keep", "confidence": 0.9, "reason": "Relevant"},
            {"feature_id": "mobile_ui", "action": "keep", "confidence": 0.8, "reason": "Relevant"},
            {"feature_id": "db", "action": "keep", "confidence": 0.9, "reason": "Relevant"},
        ]
    })
    return llm


@pytest.fixture
def mock_llm_prune_mobile() -> MagicMock:
    """Mock LLM that prunes mobile UI from backend spec."""
    llm = MagicMock()
    llm.select_model.return_value = "gpt-4o-mini"

    def complete_side_effect(messages, model, tier=None, **kwargs):
        prompt_text = messages[0]["content"]
        if "quality reviewer" in prompt_text.lower():
            # Self-check: confirm the pruning
            return json.dumps({
                "reviews": [
                    {"feature_id": "mobile_ui", "verdict": "correct", "reason": "Backend only"}
                ]
            })
        else:
            # Initial filter
            return json.dumps({
                "decisions": [
                    {"feature_id": "auth", "action": "keep", "confidence": 0.95, "reason": "Auth is needed"},
                    {"feature_id": "api", "action": "keep", "confidence": 0.9, "reason": "REST API core"},
                    {"feature_id": "mobile_ui", "action": "prune", "confidence": 0.85, "reason": "Backend-only spec"},
                    {"feature_id": "db", "action": "keep", "confidence": 0.9, "reason": "Database needed"},
                ]
            })

    llm.complete.side_effect = complete_side_effect
    return llm


# ---------------------------------------------------------------------------
# LLMFilterConfig tests
# ---------------------------------------------------------------------------


class TestLLMFilterConfig:
    """Tests for LLMFilterConfig."""

    def test_defaults(self) -> None:
        cfg = LLMFilterConfig()
        assert cfg.filter_tier == ModelTier.CHEAP
        assert cfg.selfcheck_tier == ModelTier.MEDIUM
        assert cfg.batch_size == 10
        assert cfg.enable_selfcheck is True
        assert cfg.confidence_threshold == 0.7

    def test_custom(self) -> None:
        cfg = LLMFilterConfig(
            filter_tier=ModelTier.STRONG,
            selfcheck_tier=ModelTier.STRONG,
            batch_size=20,
            enable_selfcheck=False,
        )
        assert cfg.batch_size == 20
        assert cfg.enable_selfcheck is False

    def test_invalid_batch_size(self) -> None:
        with pytest.raises(Exception):
            LLMFilterConfig(batch_size=0)


# ---------------------------------------------------------------------------
# FilterDecision tests
# ---------------------------------------------------------------------------


class TestFilterDecision:
    """Tests for FilterDecision model."""

    def test_keep_decision(self) -> None:
        d = FilterDecision(
            feature_id="auth",
            feature_name="Authentication",
            action="keep",
            confidence=0.95,
            reason="Auth is needed",
        )
        assert d.action == "keep"
        assert d.overridden is False

    def test_prune_decision(self) -> None:
        d = FilterDecision(
            feature_id="mobile",
            feature_name="Mobile UI",
            action="prune",
            confidence=0.85,
            reason="Backend-only",
        )
        assert d.action == "prune"

    def test_frozen(self) -> None:
        d = FilterDecision(
            feature_id="x", feature_name="X", action="keep"
        )
        with pytest.raises(Exception):
            d.action = "prune"  # type: ignore


# ---------------------------------------------------------------------------
# FilterResult tests
# ---------------------------------------------------------------------------


class TestFilterResult:
    """Tests for FilterResult model."""

    def test_empty(self) -> None:
        r = FilterResult()
        assert r.kept_count == 0
        assert r.pruned_count == 0
        assert r.total_count == 0

    def test_properties(self) -> None:
        r = FilterResult(
            kept=[_make_path("a", "A", 0.9)],
            pruned=[_make_path("b", "B", 0.8)],
            selfcheck_overrides=1,
        )
        assert r.kept_count == 1
        assert r.pruned_count == 1
        assert r.total_count == 2

    def test_frozen(self) -> None:
        r = FilterResult()
        with pytest.raises(Exception):
            r.selfcheck_overrides = 5  # type: ignore


# ---------------------------------------------------------------------------
# LLMFilter tests
# ---------------------------------------------------------------------------


class TestLLMFilter:
    """Tests for LLMFilter."""

    def test_properties(self) -> None:
        cfg = LLMFilterConfig(batch_size=5)
        f = LLMFilter(config=cfg)
        assert f.config.batch_size == 5

    def test_empty_spec_raises(self) -> None:
        f = LLMFilter()
        with pytest.raises(ValueError, match="empty"):
            f.filter([], spec_description="")

    def test_empty_candidates(self) -> None:
        f = LLMFilter()
        result = f.filter([], spec_description="Backend API")
        assert result.kept_count == 0
        assert result.pruned_count == 0

    def test_no_llm_passthrough(
        self, candidates: list[FeaturePath]
    ) -> None:
        """Without LLM, all features are kept."""
        f = LLMFilter(llm_gateway=None)
        result = f.filter(candidates, spec_description="Backend API")
        assert result.kept_count == len(candidates)
        assert result.pruned_count == 0

    def test_filter_keeps_all(
        self,
        candidates: list[FeaturePath],
        mock_llm_keep_all: MagicMock,
    ) -> None:
        cfg = LLMFilterConfig(enable_selfcheck=False)
        f = LLMFilter(llm_gateway=mock_llm_keep_all, config=cfg)
        result = f.filter(candidates, spec_description="Full stack app")
        assert result.kept_count == 4
        assert result.pruned_count == 0

    def test_filter_prunes_mobile(
        self,
        candidates: list[FeaturePath],
        mock_llm_prune_mobile: MagicMock,
    ) -> None:
        f = LLMFilter(llm_gateway=mock_llm_prune_mobile)
        result = f.filter(candidates, spec_description="Backend REST API with FastAPI")

        assert result.kept_count == 3
        assert result.pruned_count == 1

        pruned_ids = [p.leaf.id for p in result.pruned]
        assert "mobile_ui" in pruned_ids

        kept_ids = [p.leaf.id for p in result.kept]
        assert "auth" in kept_ids
        assert "api" in kept_ids
        assert "db" in kept_ids

    def test_filter_with_languages_and_frameworks(
        self,
        candidates: list[FeaturePath],
        mock_llm_keep_all: MagicMock,
    ) -> None:
        cfg = LLMFilterConfig(enable_selfcheck=False)
        f = LLMFilter(llm_gateway=mock_llm_keep_all, config=cfg)
        result = f.filter(
            candidates,
            spec_description="Backend API",
            spec_languages=["Python"],
            spec_frameworks=["FastAPI"],
        )
        assert result.kept_count == 4


# ---------------------------------------------------------------------------
# Self-check tests
# ---------------------------------------------------------------------------


class TestSelfCheck:
    """Tests for the self-check stage."""

    def test_selfcheck_confirms_pruning(
        self,
        candidates: list[FeaturePath],
        mock_llm_prune_mobile: MagicMock,
    ) -> None:
        f = LLMFilter(llm_gateway=mock_llm_prune_mobile)
        result = f.filter(candidates, spec_description="Backend API")
        # Self-check confirms the pruning (verdict: correct)
        assert result.selfcheck_overrides == 0
        assert result.pruned_count == 1

    def test_selfcheck_override(
        self, candidates: list[FeaturePath]
    ) -> None:
        """Self-check overrides a wrongly pruned feature."""
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"

        call_count = {"n": 0}

        def complete_side_effect(messages, model, tier=None, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Initial filter: prune auth (wrongly)
                return json.dumps({
                    "decisions": [
                        {"feature_id": "auth", "action": "prune", "confidence": 0.6, "reason": "Not needed?"},
                        {"feature_id": "api", "action": "keep", "confidence": 0.9, "reason": "Core"},
                        {"feature_id": "mobile_ui", "action": "prune", "confidence": 0.85, "reason": "Backend only"},
                        {"feature_id": "db", "action": "keep", "confidence": 0.9, "reason": "Needed"},
                    ]
                })
            else:
                # Self-check: override auth pruning
                return json.dumps({
                    "reviews": [
                        {"feature_id": "auth", "verdict": "override", "reason": "Auth IS needed for API"},
                        {"feature_id": "mobile_ui", "verdict": "correct", "reason": "Really not needed"},
                    ]
                })

        llm.complete.side_effect = complete_side_effect

        f = LLMFilter(llm_gateway=llm)
        result = f.filter(candidates, spec_description="Backend API with auth")

        assert result.selfcheck_overrides == 1
        kept_ids = {p.leaf.id for p in result.kept}
        assert "auth" in kept_ids  # Override restored it

    def test_selfcheck_disabled(
        self,
        candidates: list[FeaturePath],
        mock_llm_prune_mobile: MagicMock,
    ) -> None:
        cfg = LLMFilterConfig(enable_selfcheck=False)
        f = LLMFilter(llm_gateway=mock_llm_prune_mobile, config=cfg)
        result = f.filter(candidates, spec_description="Backend API")
        # LLM should only be called once (no self-check)
        assert mock_llm_prune_mobile.complete.call_count == 1


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling."""

    def test_llm_error_keeps_all(
        self, candidates: list[FeaturePath]
    ) -> None:
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.side_effect = RuntimeError("LLM down")

        f = LLMFilter(llm_gateway=llm)
        result = f.filter(candidates, spec_description="Backend API")
        # On error, keeps all
        assert result.kept_count == len(candidates)

    def test_malformed_response(
        self, candidates: list[FeaturePath]
    ) -> None:
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"
        llm.complete.return_value = "This is not JSON at all"

        cfg = LLMFilterConfig(enable_selfcheck=False)
        f = LLMFilter(llm_gateway=llm, config=cfg)
        result = f.filter(candidates, spec_description="Backend API")
        # Should keep all (not mentioned in response)
        assert result.kept_count == len(candidates)

    def test_selfcheck_error_preserves_original(
        self, candidates: list[FeaturePath]
    ) -> None:
        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"

        call_count = {"n": 0}
        def complete_effect(messages, model, tier=None, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return json.dumps({
                    "decisions": [
                        {"feature_id": "auth", "action": "keep", "confidence": 0.9, "reason": "OK"},
                        {"feature_id": "api", "action": "keep", "confidence": 0.9, "reason": "OK"},
                        {"feature_id": "mobile_ui", "action": "prune", "confidence": 0.8, "reason": "Nope"},
                        {"feature_id": "db", "action": "keep", "confidence": 0.9, "reason": "OK"},
                    ]
                })
            else:
                raise RuntimeError("Self-check failed")

        llm.complete.side_effect = complete_effect

        f = LLMFilter(llm_gateway=llm)
        result = f.filter(candidates, spec_description="Backend API")
        # Self-check error preserves original decisions
        assert result.pruned_count == 1
        assert result.selfcheck_overrides == 0


# ---------------------------------------------------------------------------
# Batch processing tests
# ---------------------------------------------------------------------------


class TestBatchProcessing:
    """Tests for batch processing."""

    def test_single_batch(
        self,
        candidates: list[FeaturePath],
        mock_llm_keep_all: MagicMock,
    ) -> None:
        cfg = LLMFilterConfig(batch_size=10, enable_selfcheck=False)
        f = LLMFilter(llm_gateway=mock_llm_keep_all, config=cfg)
        result = f.filter(candidates, spec_description="App")
        # 4 candidates < batch_size, so 1 call
        assert mock_llm_keep_all.complete.call_count == 1

    def test_multiple_batches(self) -> None:
        """Large candidate set processed in batches."""
        candidates = [
            _make_path(f"f{i}", f"Feature {i}", 0.9) for i in range(15)
        ]

        llm = MagicMock()
        llm.select_model.return_value = "gpt-4o-mini"

        def complete_effect(messages, model, tier=None, **kwargs):
            # Keep all
            return json.dumps({"decisions": []})

        llm.complete.side_effect = complete_effect

        cfg = LLMFilterConfig(batch_size=5, enable_selfcheck=False)
        f = LLMFilter(llm_gateway=llm, config=cfg)
        result = f.filter(candidates, spec_description="App")
        # 15 features / 5 per batch = 3 calls
        assert llm.complete.call_count == 3
        # All kept (not mentioned = keep)
        assert result.kept_count == 15


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for module imports."""

    def test_import_from_module(self) -> None:
        from zerorepo.selection.llm_filter import (
            FilterDecision,
            FilterResult,
            LLMFilter,
            LLMFilterConfig,
        )
        assert LLMFilter is not None
