"""LLM Filtering Pipeline – prune irrelevant features via LLM review.

Implements Task 2.2.4 of PRD-RPG-P2-001 (Epic 2.2: Explore-Exploit Subtree
Selection). The LLM reviews selected features against the user's specification
and prunes features that are irrelevant to the project scope.

The pipeline operates in two stages:

1. **Initial Filter**: LLM reviews each feature (or batch of features) against
   the user spec and marks each as ``keep`` or ``prune`` with a reason.

2. **Self-Check**: A second LLM call reviews the pruning decisions to catch
   false positives (wrongly pruned relevant features).

Example::

    from cobuilder.repomap.selection.llm_filter import LLMFilter, LLMFilterConfig

    llm_filter = LLMFilter(llm_gateway=gateway)
    result = llm_filter.filter(
        candidates=feature_paths,
        spec_description="Build a REST API backend with FastAPI",
    )
    print(f"Kept {result.kept_count}, pruned {result.pruned_count}")
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from cobuilder.repomap.llm.gateway import LLMGateway
from cobuilder.repomap.llm.models import ModelTier
from cobuilder.repomap.ontology.models import FeaturePath

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class LLMFilterConfig(BaseModel):
    """Configuration for the LLM Filtering Pipeline.

    Attributes:
        filter_tier: LLM tier for initial filtering.
        selfcheck_tier: LLM tier for self-check review.
        batch_size: Number of features to review per LLM call.
        enable_selfcheck: Whether to run the self-check stage.
        confidence_threshold: Minimum confidence for a prune decision
            to be accepted without self-check override.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    filter_tier: ModelTier = Field(
        default=ModelTier.CHEAP,
        description="LLM tier for initial feature filtering",
    )
    selfcheck_tier: ModelTier = Field(
        default=ModelTier.MEDIUM,
        description="LLM tier for self-check review",
    )
    batch_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Features per LLM batch call",
    )
    enable_selfcheck: bool = Field(
        default=True,
        description="Enable self-check review stage",
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Min confidence to accept prune without override",
    )


# ---------------------------------------------------------------------------
# Filter Decision
# ---------------------------------------------------------------------------


class FilterDecision(BaseModel):
    """A single feature filtering decision.

    Attributes:
        feature_id: ID of the feature node.
        feature_name: Name of the feature.
        action: ``"keep"`` or ``"prune"``.
        confidence: LLM's confidence in the decision (0.0 to 1.0).
        reason: Explanation for the decision.
        overridden: Whether the self-check stage overrode this decision.
    """

    model_config = ConfigDict(frozen=True)

    feature_id: str = Field(..., description="Feature node ID")
    feature_name: str = Field(..., description="Feature name")
    action: str = Field(
        ...,
        description="keep or prune",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in decision",
    )
    reason: str = Field(
        default="",
        description="Explanation for the decision",
    )
    overridden: bool = Field(
        default=False,
        description="Whether self-check overrode this decision",
    )


# ---------------------------------------------------------------------------
# Filter Result
# ---------------------------------------------------------------------------


class FilterResult(BaseModel):
    """Result of the LLM filtering pipeline.

    Attributes:
        kept: Feature paths that passed the filter.
        pruned: Feature paths that were filtered out.
        decisions: All filtering decisions with reasons.
        selfcheck_overrides: Number of self-check overrides.
    """

    model_config = ConfigDict(frozen=True)

    kept: list[FeaturePath] = Field(
        default_factory=list,
        description="Features that passed the filter",
    )
    pruned: list[FeaturePath] = Field(
        default_factory=list,
        description="Features that were pruned",
    )
    decisions: list[FilterDecision] = Field(
        default_factory=list,
        description="All filtering decisions",
    )
    selfcheck_overrides: int = Field(
        default=0,
        ge=0,
        description="Number of self-check overrides",
    )

    @property
    def kept_count(self) -> int:
        """Number of kept features."""
        return len(self.kept)

    @property
    def pruned_count(self) -> int:
        """Number of pruned features."""
        return len(self.pruned)

    @property
    def total_count(self) -> int:
        """Total number of features processed."""
        return len(self.kept) + len(self.pruned)


# ---------------------------------------------------------------------------
# LLM Prompts
# ---------------------------------------------------------------------------


_FILTER_PROMPT = """\
You are a feature relevance evaluator for a software project planner.

Given a project specification and a list of candidate features from a feature \
ontology, evaluate each feature's relevance to the project.

## Project Specification
{spec}

## Candidate Features
{features}

## Instructions

For EACH feature, decide:
- **keep**: The feature is relevant to the project specification
- **prune**: The feature is NOT relevant (e.g., "mobile UI" for a backend-only spec)

Be conservative: when in doubt, keep the feature. Only prune features that are \
clearly irrelevant to the project scope.

Respond with a JSON object:
{{
  "decisions": [
    {{
      "feature_id": "...",
      "action": "keep" or "prune",
      "confidence": 0.0-1.0,
      "reason": "brief explanation"
    }}
  ]
}}
"""


_SELFCHECK_PROMPT = """\
You are a quality reviewer checking feature pruning decisions.

A previous AI reviewed features for relevance to a project and pruned some. \
Review the PRUNED features to catch false positives (features that were \
wrongly removed).

## Project Specification
{spec}

## Pruned Features (to review)
{pruned}

## Original Pruning Reasons
{reasons}

## Instructions

For each pruned feature, decide if the pruning was CORRECT or should be \
OVERRIDDEN (feature should be kept):
- **correct**: The pruning was justified; the feature is truly irrelevant
- **override**: The feature IS actually relevant and should be kept

Only override clear mistakes. The original filter was conservative, so most \
pruning decisions are likely correct.

Respond with a JSON object:
{{
  "reviews": [
    {{
      "feature_id": "...",
      "verdict": "correct" or "override",
      "reason": "brief explanation"
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# LLM Filter
# ---------------------------------------------------------------------------


class LLMFilter:
    """LLM-based feature filtering pipeline.

    Reviews candidate features against the user's specification using
    an LLM, pruning features that are irrelevant to the project scope.
    Optionally runs a self-check stage to catch false positives.

    Args:
        llm_gateway: An LLMGateway instance.
        config: Optional filter configuration.

    Example::

        llm_filter = LLMFilter(llm_gateway=gw)
        result = llm_filter.filter(
            candidates=paths,
            spec_description="Backend REST API with authentication",
        )
    """

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        config: LLMFilterConfig | None = None,
    ) -> None:
        self._llm = llm_gateway
        self._config = config or LLMFilterConfig()

    @property
    def config(self) -> LLMFilterConfig:
        """Return the filter configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter(
        self,
        candidates: list[FeaturePath],
        spec_description: str,
        spec_languages: list[str] | None = None,
        spec_frameworks: list[str] | None = None,
    ) -> FilterResult:
        """Filter candidates for relevance to the specification.

        Args:
            candidates: Feature paths to evaluate.
            spec_description: The user's project description.
            spec_languages: Optional language context.
            spec_frameworks: Optional framework context.

        Returns:
            A FilterResult with kept/pruned features and decisions.

        Raises:
            ValueError: If spec_description is empty.
        """
        if not spec_description or not spec_description.strip():
            raise ValueError("spec_description must not be empty")

        if not candidates:
            return FilterResult()

        # Build spec context
        spec_context = self._build_spec_context(
            spec_description, spec_languages, spec_frameworks
        )

        # If no LLM, keep everything (pass-through)
        if self._llm is None:
            logger.info("No LLM available; keeping all %d candidates", len(candidates))
            decisions = [
                FilterDecision(
                    feature_id=p.leaf.id,
                    feature_name=p.leaf.name,
                    action="keep",
                    confidence=1.0,
                    reason="No LLM available; keeping by default",
                )
                for p in candidates
            ]
            return FilterResult(kept=list(candidates), decisions=decisions)

        # Stage 1: Initial filtering
        decisions = self._initial_filter(candidates, spec_context)

        # Stage 2: Self-check (optional)
        overrides = 0
        if self._config.enable_selfcheck:
            decisions, overrides = self._selfcheck(
                decisions, candidates, spec_context
            )

        # Build result
        kept: list[FeaturePath] = []
        pruned: list[FeaturePath] = []
        path_map = {p.leaf.id: p for p in candidates}

        for d in decisions:
            path = path_map.get(d.feature_id)
            if path is None:
                continue
            if d.action == "keep":
                kept.append(path)
            else:
                pruned.append(path)

        logger.info(
            "LLMFilter: candidates=%d, kept=%d, pruned=%d, overrides=%d",
            len(candidates),
            len(kept),
            len(pruned),
            overrides,
        )

        return FilterResult(
            kept=kept,
            pruned=pruned,
            decisions=decisions,
            selfcheck_overrides=overrides,
        )

    # ------------------------------------------------------------------
    # Internal: Initial filter
    # ------------------------------------------------------------------

    def _initial_filter(
        self,
        candidates: list[FeaturePath],
        spec_context: str,
    ) -> list[FilterDecision]:
        """Run the initial LLM filtering pass.

        Processes candidates in batches.

        Args:
            candidates: Feature paths to evaluate.
            spec_context: Formatted spec description.

        Returns:
            List of FilterDecision objects.
        """
        all_decisions: list[FilterDecision] = []
        batch_size = self._config.batch_size

        for start in range(0, len(candidates), batch_size):
            batch = candidates[start : start + batch_size]
            batch_decisions = self._filter_batch(batch, spec_context)
            all_decisions.extend(batch_decisions)

        return all_decisions

    def _filter_batch(
        self,
        batch: list[FeaturePath],
        spec_context: str,
    ) -> list[FilterDecision]:
        """Filter a single batch of features via LLM.

        Args:
            batch: Feature paths in this batch.
            spec_context: Formatted spec description.

        Returns:
            FilterDecision for each feature in the batch.
        """
        features_text = self._format_features(batch)
        prompt = _FILTER_PROMPT.format(
            spec=spec_context, features=features_text
        )

        try:
            assert self._llm is not None
            model = self._llm.select_model(self._config.filter_tier)
            response = self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                tier=self._config.filter_tier,
            )
            return self._parse_filter_response(response, batch)

        except Exception as exc:
            logger.warning("LLM filter batch failed: %s", exc)
            # On error, keep all features in the batch
            return [
                FilterDecision(
                    feature_id=p.leaf.id,
                    feature_name=p.leaf.name,
                    action="keep",
                    confidence=0.5,
                    reason=f"LLM filter error: {exc}",
                )
                for p in batch
            ]

    def _parse_filter_response(
        self,
        response: str,
        batch: list[FeaturePath],
    ) -> list[FilterDecision]:
        """Parse the LLM filter response into decisions.

        Args:
            response: Raw LLM response.
            batch: The batch of features that were evaluated.

        Returns:
            List of FilterDecision objects.
        """
        feature_map = {p.leaf.id: p for p in batch}
        decisions: list[FilterDecision] = []

        parsed = self._extract_json(response)
        if parsed and "decisions" in parsed:
            for entry in parsed["decisions"]:
                fid = entry.get("feature_id", "")
                if fid not in feature_map:
                    continue

                action = entry.get("action", "keep").lower()
                if action not in ("keep", "prune"):
                    action = "keep"

                decisions.append(
                    FilterDecision(
                        feature_id=fid,
                        feature_name=feature_map[fid].leaf.name,
                        action=action,
                        confidence=min(1.0, max(0.0, entry.get("confidence", 0.8))),
                        reason=entry.get("reason", ""),
                    )
                )
                feature_map.pop(fid)

        # Default: keep any features not mentioned in the response
        for fid, path in feature_map.items():
            decisions.append(
                FilterDecision(
                    feature_id=fid,
                    feature_name=path.leaf.name,
                    action="keep",
                    confidence=0.5,
                    reason="Not mentioned in LLM response; keeping by default",
                )
            )

        return decisions

    # ------------------------------------------------------------------
    # Internal: Self-check
    # ------------------------------------------------------------------

    def _selfcheck(
        self,
        decisions: list[FilterDecision],
        candidates: list[FeaturePath],
        spec_context: str,
    ) -> tuple[list[FilterDecision], int]:
        """Run self-check review on pruned features.

        Args:
            decisions: Initial filter decisions.
            candidates: Original candidate paths.
            spec_context: Formatted spec description.

        Returns:
            Tuple of (updated decisions, number of overrides).
        """
        pruned_decisions = [d for d in decisions if d.action == "prune"]
        if not pruned_decisions:
            return decisions, 0

        path_map = {p.leaf.id: p for p in candidates}
        pruned_features = self._format_features(
            [path_map[d.feature_id] for d in pruned_decisions if d.feature_id in path_map]
        )
        reasons = "\n".join(
            f"- {d.feature_name}: {d.reason}" for d in pruned_decisions
        )

        prompt = _SELFCHECK_PROMPT.format(
            spec=spec_context, pruned=pruned_features, reasons=reasons
        )

        try:
            assert self._llm is not None
            model = self._llm.select_model(self._config.selfcheck_tier)
            response = self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                tier=self._config.selfcheck_tier,
            )
            return self._apply_selfcheck(decisions, response)

        except Exception as exc:
            logger.warning("Self-check failed: %s", exc)
            return decisions, 0

    def _apply_selfcheck(
        self,
        decisions: list[FilterDecision],
        response: str,
    ) -> tuple[list[FilterDecision], int]:
        """Apply self-check overrides to decisions.

        Args:
            decisions: Original decisions.
            response: Self-check LLM response.

        Returns:
            Tuple of (updated decisions, number of overrides).
        """
        parsed = self._extract_json(response)
        if not parsed or "reviews" not in parsed:
            return decisions, 0

        override_ids: set[str] = set()
        for review in parsed["reviews"]:
            if review.get("verdict", "").lower() == "override":
                override_ids.add(review.get("feature_id", ""))

        if not override_ids:
            return decisions, 0

        updated: list[FilterDecision] = []
        overrides = 0

        for d in decisions:
            if d.feature_id in override_ids and d.action == "prune":
                # Override: change to keep
                updated.append(
                    FilterDecision(
                        feature_id=d.feature_id,
                        feature_name=d.feature_name,
                        action="keep",
                        confidence=d.confidence,
                        reason=f"Self-check override: {d.reason}",
                        overridden=True,
                    )
                )
                overrides += 1
            else:
                updated.append(d)

        return updated, overrides

    # ------------------------------------------------------------------
    # Internal: Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_spec_context(
        description: str,
        languages: list[str] | None = None,
        frameworks: list[str] | None = None,
    ) -> str:
        """Build formatted spec context for LLM prompts."""
        parts = [description.strip()]
        if languages:
            parts.append(f"Languages: {', '.join(languages)}")
        if frameworks:
            parts.append(f"Frameworks: {', '.join(frameworks)}")
        return "\n".join(parts)

    @staticmethod
    def _format_features(paths: list[FeaturePath]) -> str:
        """Format feature paths for LLM prompt."""
        lines: list[str] = []
        for p in paths:
            node = p.leaf
            desc = node.description or ""
            tags_str = ", ".join(node.tags) if node.tags else ""
            entry = f"- ID: {node.id} | Name: {node.name}"
            if desc:
                entry += f" | Description: {desc}"
            if tags_str:
                entry += f" | Tags: {tags_str}"
            entry += f" | Score: {p.score:.3f}"
            lines.append(entry)
        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract JSON from LLM response text."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError, TypeError):
            pass

        return None
