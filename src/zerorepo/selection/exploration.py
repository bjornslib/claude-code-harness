"""Exploration Strategy – coverage tracking and gap-based query generation.

Implements Task 2.2.2 of PRD-RPG-P2-001 (Epic 2.2: Explore-Exploit Subtree
Selection). Tracks visited ontology branches and proposes exploratory queries
for uncovered regions of the feature ontology.

The exploration strategy maintains a *coverage bit vector* keyed by node ID,
and uses an LLM to generate exploratory queries targeting coverage gaps.
Coverage is guaranteed to increase monotonically — once a node is marked
visited, it stays visited.

Key components:

- **CoverageTracker**: Bit-vector coverage tracking with monotonic guarantees
  and per-level statistics.
- **ExplorationStrategy**: Proposes exploratory queries by analysing coverage
  gaps and using LLM to generate targeted search queries.

Example::

    from zerorepo.selection.exploration import (
        CoverageTracker,
        ExplorationConfig,
        ExplorationStrategy,
    )

    tracker = CoverageTracker()
    # Register all known nodes
    tracker.register_nodes(all_feature_nodes)

    strategy = ExplorationStrategy(
        coverage=tracker,
        llm_gateway=gateway,
    )

    # After exploitation, mark visited nodes
    for path in exploitation_result.paths:
        tracker.mark_visited(path.leaf.id)

    # Get exploratory queries for uncovered regions
    queries = strategy.propose_queries(n=5)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from zerorepo.llm.gateway import LLMGateway
from zerorepo.llm.models import ModelTier
from zerorepo.ontology.backend import OntologyBackend
from zerorepo.ontology.models import FeatureNode, FeaturePath

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Coverage Tracker
# ---------------------------------------------------------------------------


class CoverageStats(BaseModel):
    """Coverage statistics snapshot.

    Attributes:
        total_nodes: Total number of registered nodes.
        visited_count: Number of visited nodes.
        coverage_ratio: Fraction of nodes visited (0.0 to 1.0).
        level_coverage: Per-level coverage as {level: (visited, total)}.
        unvisited_count: Number of unvisited nodes.
    """

    model_config = ConfigDict(frozen=True)

    total_nodes: int = Field(ge=0, description="Total registered nodes")
    visited_count: int = Field(ge=0, description="Visited node count")
    coverage_ratio: float = Field(
        ge=0.0, le=1.0, description="Coverage fraction"
    )
    level_coverage: dict[int, tuple[int, int]] = Field(
        default_factory=dict,
        description="Per-level (visited, total) counts",
    )
    unvisited_count: int = Field(ge=0, description="Unvisited node count")


class CoverageTracker:
    """Bit-vector coverage tracker for ontology nodes.

    Tracks which nodes in the feature ontology have been visited (selected)
    by the exploitation or exploration phases. Coverage is **monotonically
    increasing** — once a node is marked visited, it remains visited.

    The tracker stores minimal information per node: ID, name, level, and
    parent_id for gap analysis.

    Example::

        tracker = CoverageTracker()
        tracker.register_node("auth", "Authentication", level=1)
        tracker.mark_visited("auth")
        assert tracker.is_visited("auth")
        assert tracker.coverage_ratio > 0.0
    """

    def __init__(self) -> None:
        self._visited: set[str] = set()
        self._node_info: dict[str, dict[str, Any]] = {}
        # level -> set of node IDs at that level
        self._level_index: dict[int, set[str]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_node(
        self,
        node_id: str,
        name: str,
        level: int,
        parent_id: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Register a node for coverage tracking.

        Args:
            node_id: Unique node identifier.
            name: Human-readable name.
            level: Hierarchical level.
            parent_id: Parent node ID (None for roots).
            tags: Optional tags for the node.

        Raises:
            ValueError: If node_id is empty.
        """
        if not node_id or not node_id.strip():
            raise ValueError("node_id must not be empty")

        self._node_info[node_id] = {
            "name": name,
            "level": level,
            "parent_id": parent_id,
            "tags": tags or [],
        }

        if level not in self._level_index:
            self._level_index[level] = set()
        self._level_index[level].add(node_id)

    def register_feature_node(self, node: FeatureNode) -> None:
        """Register a FeatureNode for coverage tracking.

        Convenience method that extracts fields from a FeatureNode.

        Args:
            node: The FeatureNode to register.
        """
        self.register_node(
            node_id=node.id,
            name=node.name,
            level=node.level,
            parent_id=node.parent_id,
            tags=node.tags,
        )

    def register_nodes(self, nodes: list[FeatureNode]) -> int:
        """Register multiple FeatureNodes.

        Args:
            nodes: List of FeatureNodes to register.

        Returns:
            Number of nodes registered.
        """
        for node in nodes:
            self.register_feature_node(node)
        return len(nodes)

    # ------------------------------------------------------------------
    # Visit tracking (monotonically increasing)
    # ------------------------------------------------------------------

    def mark_visited(self, node_id: str) -> bool:
        """Mark a node as visited.

        Coverage is monotonically increasing — a node that has been visited
        cannot be un-visited.

        Args:
            node_id: The node ID to mark as visited.

        Returns:
            True if the node was newly visited, False if already visited.

        Raises:
            KeyError: If the node_id has not been registered.
        """
        if node_id not in self._node_info:
            raise KeyError(
                f"Node '{node_id}' has not been registered. "
                "Call register_node() first."
            )
        if node_id in self._visited:
            return False
        self._visited.add(node_id)
        return True

    def mark_visited_batch(self, node_ids: list[str]) -> int:
        """Mark multiple nodes as visited.

        Skips unregistered IDs with a warning (does not raise).

        Args:
            node_ids: List of node IDs to mark.

        Returns:
            Number of newly visited nodes.
        """
        newly_visited = 0
        for nid in node_ids:
            if nid not in self._node_info:
                logger.debug("Skipping unregistered node '%s'", nid)
                continue
            if nid not in self._visited:
                self._visited.add(nid)
                newly_visited += 1
        return newly_visited

    def mark_paths_visited(self, paths: list[FeaturePath]) -> int:
        """Mark all leaf nodes from a list of FeaturePaths as visited.

        Registers any unknown nodes encountered in the paths.

        Args:
            paths: List of FeaturePath objects from retrieval.

        Returns:
            Number of newly visited nodes.
        """
        newly = 0
        for path in paths:
            for node in path.nodes:
                if node.id not in self._node_info:
                    self.register_feature_node(node)
                if node.id not in self._visited:
                    self._visited.add(node.id)
                    newly += 1
        return newly

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def is_visited(self, node_id: str) -> bool:
        """Check if a node has been visited."""
        return node_id in self._visited

    @property
    def total_nodes(self) -> int:
        """Total number of registered nodes."""
        return len(self._node_info)

    @property
    def visited_count(self) -> int:
        """Number of visited nodes."""
        return len(self._visited)

    @property
    def coverage_ratio(self) -> float:
        """Fraction of registered nodes that have been visited."""
        if not self._node_info:
            return 0.0
        return len(self._visited) / len(self._node_info)

    def get_unvisited(self) -> list[str]:
        """Return IDs of all unvisited nodes."""
        return [
            nid for nid in self._node_info if nid not in self._visited
        ]

    def get_unvisited_at_level(self, level: int) -> list[str]:
        """Return IDs of unvisited nodes at a specific level."""
        level_nodes = self._level_index.get(level, set())
        return [nid for nid in level_nodes if nid not in self._visited]

    def get_coverage_gaps(self, max_gaps: int = 10) -> list[dict[str, Any]]:
        """Identify coverage gaps for exploration.

        Returns information about unvisited regions, grouped by parent
        nodes that have partial coverage.

        Args:
            max_gaps: Maximum number of gap descriptions to return.

        Returns:
            List of gap dictionaries with fields:
            - parent_id: Parent node ID (or None for root-level gaps)
            - parent_name: Name of the parent node
            - unvisited_children: List of unvisited child node info
            - coverage: Fraction of children visited under this parent
        """
        # Group unvisited by parent_id
        parent_groups: dict[str | None, list[str]] = {}
        for nid in self.get_unvisited():
            info = self._node_info[nid]
            parent = info.get("parent_id")
            if parent not in parent_groups:
                parent_groups[parent] = []
            parent_groups[parent].append(nid)

        gaps: list[dict[str, Any]] = []
        for parent_id, unvisited_ids in parent_groups.items():
            # Count total siblings under this parent
            total_siblings = sum(
                1
                for info in self._node_info.values()
                if info.get("parent_id") == parent_id
            )
            visited_siblings = total_siblings - len(unvisited_ids)

            parent_name = None
            if parent_id and parent_id in self._node_info:
                parent_name = self._node_info[parent_id]["name"]

            children_info = []
            for uid in unvisited_ids[:5]:  # Limit detail per parent
                info = self._node_info[uid]
                children_info.append({
                    "id": uid,
                    "name": info["name"],
                    "level": info["level"],
                    "tags": info.get("tags", []),
                })

            coverage = (
                visited_siblings / total_siblings if total_siblings > 0 else 0.0
            )

            gaps.append({
                "parent_id": parent_id,
                "parent_name": parent_name,
                "unvisited_children": children_info,
                "unvisited_count": len(unvisited_ids),
                "total_siblings": total_siblings,
                "coverage": coverage,
            })

            if len(gaps) >= max_gaps:
                break

        # Sort by most unvisited children (biggest gaps first)
        gaps.sort(key=lambda g: g["unvisited_count"], reverse=True)
        return gaps[:max_gaps]

    def get_stats(self) -> CoverageStats:
        """Compute coverage statistics.

        Returns:
            A CoverageStats snapshot.
        """
        level_cov: dict[int, tuple[int, int]] = {}
        for level, node_ids in self._level_index.items():
            visited = sum(1 for nid in node_ids if nid in self._visited)
            level_cov[level] = (visited, len(node_ids))

        return CoverageStats(
            total_nodes=self.total_nodes,
            visited_count=self.visited_count,
            coverage_ratio=self.coverage_ratio,
            level_coverage=level_cov,
            unvisited_count=self.total_nodes - self.visited_count,
        )

    def reset(self) -> None:
        """Reset all visited state (but keep registrations).

        Note: This breaks the monotonic guarantee. Use only for
        testing or starting a new selection round.
        """
        self._visited.clear()


# ---------------------------------------------------------------------------
# Exploration Configuration
# ---------------------------------------------------------------------------


class ExplorationConfig(BaseModel):
    """Configuration for the ExplorationStrategy.

    Attributes:
        augmentation_tier: LLM tier for exploratory query generation.
        max_queries_per_round: Maximum queries to generate per round.
        min_coverage_for_completion: Coverage ratio at which exploration
            is considered complete (no more queries generated).
        prefer_underexplored_levels: Bias towards levels with lower
            coverage when selecting gaps.
        search_top_k: Results to retrieve per exploratory query.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    augmentation_tier: ModelTier = Field(
        default=ModelTier.CHEAP,
        description="LLM tier for exploratory query generation",
    )
    max_queries_per_round: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum exploratory queries per round",
    )
    min_coverage_for_completion: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Coverage threshold for exploration completion",
    )
    prefer_underexplored_levels: bool = Field(
        default=True,
        description="Bias towards levels with lowest coverage",
    )
    search_top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Results per exploratory query",
    )


# ---------------------------------------------------------------------------
# Exploration Result
# ---------------------------------------------------------------------------


class ExplorationResult(BaseModel):
    """Result of an exploration round.

    Attributes:
        queries: Generated exploratory queries.
        paths: Retrieved feature paths from exploratory queries.
        newly_visited: Number of new nodes visited this round.
        coverage_before: Coverage ratio before this round.
        coverage_after: Coverage ratio after this round.
        gaps_analyzed: Number of coverage gaps analyzed.
        is_complete: Whether coverage target has been reached.
    """

    model_config = ConfigDict(frozen=True)

    queries: list[str] = Field(
        default_factory=list,
        description="Generated exploratory queries",
    )
    paths: list[FeaturePath] = Field(
        default_factory=list,
        description="Retrieved feature paths",
    )
    newly_visited: int = Field(
        default=0, ge=0, description="Newly visited nodes"
    )
    coverage_before: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Coverage before round"
    )
    coverage_after: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Coverage after round"
    )
    gaps_analyzed: int = Field(
        default=0, ge=0, description="Gaps analyzed"
    )
    is_complete: bool = Field(
        default=False, description="Whether coverage target reached"
    )


# ---------------------------------------------------------------------------
# Exploration Strategy
# ---------------------------------------------------------------------------


_EXPLORATION_PROMPT = """\
You are a feature ontology exploration assistant. Given information about \
unexplored regions in a software feature ontology, generate {n} search \
queries that would help discover features in those regions.

## Coverage Gaps

The following areas of the ontology have NOT been explored yet:

{gaps}

## Already Explored

These areas have already been covered:
{visited_summary}

## Instructions

Generate {n} diverse search queries that target the unexplored regions. Each \
query should:
- Focus on a different unexplored area
- Use specific technical terms relevant to that area
- Be concise (2-6 words)
- Avoid terms already well-covered by visited nodes

Respond with a JSON object: {{"queries": ["query1", "query2", ...]}}
"""


class ExplorationStrategy:
    """Coverage-based exploration strategy for ontology feature discovery.

    Analyses coverage gaps in the feature ontology and uses an LLM to
    generate targeted search queries for uncovered regions. Works in
    tandem with the :class:`CoverageTracker` to ensure monotonically
    increasing coverage.

    Args:
        coverage: A CoverageTracker instance (may be shared with exploitation).
        store: An OntologyBackend for executing exploratory searches.
        llm_gateway: An LLMGateway for generating exploratory queries.
        config: Optional exploration configuration.

    Example::

        strategy = ExplorationStrategy(
            coverage=tracker,
            store=store,
            llm_gateway=gateway,
        )
        result = strategy.explore_round()
    """

    def __init__(
        self,
        coverage: CoverageTracker,
        store: OntologyBackend | None = None,
        llm_gateway: LLMGateway | None = None,
        config: ExplorationConfig | None = None,
    ) -> None:
        self._coverage = coverage
        self._store = store
        self._llm = llm_gateway
        self._config = config or ExplorationConfig()

    @property
    def coverage(self) -> CoverageTracker:
        """Return the coverage tracker."""
        return self._coverage

    @property
    def config(self) -> ExplorationConfig:
        """Return the exploration configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_coverage_complete(self) -> bool:
        """Check if coverage has reached the target threshold."""
        return (
            self._coverage.coverage_ratio
            >= self._config.min_coverage_for_completion
        )

    def propose_queries(self, n: int | None = None) -> list[str]:
        """Propose exploratory queries based on coverage gaps.

        Analyses the coverage tracker's gaps and generates targeted
        queries via LLM (or a deterministic fallback if no LLM).

        Args:
            n: Number of queries to generate. Defaults to config value.

        Returns:
            List of exploratory query strings.
        """
        if self.is_coverage_complete():
            logger.info("Coverage complete (%.1f%%), no queries needed",
                       self._coverage.coverage_ratio * 100)
            return []

        n = n or self._config.max_queries_per_round
        gaps = self._coverage.get_coverage_gaps(max_gaps=n * 2)

        if not gaps:
            return []

        # Try LLM-based generation
        if self._llm is not None:
            queries = self._generate_queries_llm(gaps, n)
            if queries:
                return queries

        # Fallback: deterministic gap-based queries
        return self._generate_queries_deterministic(gaps, n)

    def explore_round(self) -> ExplorationResult:
        """Execute one full exploration round.

        1. Checks if coverage is already complete.
        2. Generates exploratory queries.
        3. Searches the store with each query.
        4. Marks retrieved nodes as visited.
        5. Returns the round results.

        Returns:
            An ExplorationResult with the round's findings.
        """
        coverage_before = self._coverage.coverage_ratio

        if self.is_coverage_complete():
            return ExplorationResult(
                coverage_before=coverage_before,
                coverage_after=coverage_before,
                is_complete=True,
            )

        # Generate queries
        queries = self.propose_queries()
        gaps_analyzed = len(
            self._coverage.get_coverage_gaps(
                max_gaps=self._config.max_queries_per_round * 2
            )
        )

        if not queries:
            return ExplorationResult(
                coverage_before=coverage_before,
                coverage_after=coverage_before,
                gaps_analyzed=gaps_analyzed,
                is_complete=self.is_coverage_complete(),
            )

        # Search with each query
        all_paths: list[FeaturePath] = []
        if self._store is not None:
            for q in queries:
                try:
                    paths = self._store.search(
                        query=q,
                        top_k=self._config.search_top_k,
                    )
                    all_paths.extend(paths)
                except Exception as exc:
                    logger.warning(
                        "Exploration search failed for %r: %s", q[:40], exc
                    )

        # Mark visited
        newly_visited = self._coverage.mark_paths_visited(all_paths)
        coverage_after = self._coverage.coverage_ratio

        logger.info(
            "Exploration round: queries=%d, paths=%d, new_visited=%d, "
            "coverage=%.1f%% -> %.1f%%",
            len(queries),
            len(all_paths),
            newly_visited,
            coverage_before * 100,
            coverage_after * 100,
        )

        return ExplorationResult(
            queries=queries,
            paths=all_paths,
            newly_visited=newly_visited,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            gaps_analyzed=gaps_analyzed,
            is_complete=self.is_coverage_complete(),
        )

    # ------------------------------------------------------------------
    # Internal: LLM-based query generation
    # ------------------------------------------------------------------

    def _generate_queries_llm(
        self,
        gaps: list[dict[str, Any]],
        n: int,
    ) -> list[str]:
        """Generate exploratory queries using the LLM.

        Args:
            gaps: Coverage gap descriptions from CoverageTracker.
            n: Number of queries to generate.

        Returns:
            List of query strings (may be empty on failure).
        """
        if self._llm is None:
            return []

        gaps_text = self._format_gaps(gaps)
        visited_summary = self._format_visited_summary()

        prompt = _EXPLORATION_PROMPT.format(
            n=n,
            gaps=gaps_text,
            visited_summary=visited_summary,
        )

        try:
            model = self._llm.select_model(self._config.augmentation_tier)
            response = self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                tier=self._config.augmentation_tier,
            )
            return self._parse_queries_response(response, n)

        except Exception as exc:
            logger.warning(
                "LLM exploration query generation failed: %s", exc
            )
            return []

    def _format_gaps(self, gaps: list[dict[str, Any]]) -> str:
        """Format coverage gaps for the LLM prompt."""
        lines: list[str] = []
        for gap in gaps:
            parent_name = gap.get("parent_name") or "(root level)"
            coverage_pct = gap["coverage"] * 100
            children = gap.get("unvisited_children", [])
            child_names = ", ".join(
                c.get("name", c.get("id", "?")) for c in children[:5]
            )
            lines.append(
                f"- Under '{parent_name}' ({coverage_pct:.0f}% covered): "
                f"{gap['unvisited_count']} unexplored — e.g., {child_names}"
            )
        return "\n".join(lines) if lines else "(no gaps identified)"

    def _format_visited_summary(self) -> str:
        """Format a summary of visited nodes for the LLM prompt."""
        visited_ids = list(self._coverage._visited)[:20]
        if not visited_ids:
            return "(no nodes visited yet)"

        names: list[str] = []
        for nid in visited_ids:
            info = self._coverage._node_info.get(nid, {})
            name = info.get("name", nid)
            names.append(name)

        summary = ", ".join(names)
        if len(self._coverage._visited) > 20:
            summary += f" ... and {len(self._coverage._visited) - 20} more"
        return summary

    def _parse_queries_response(
        self, response: str, max_n: int
    ) -> list[str]:
        """Parse the LLM response into a list of queries."""
        # Try JSON first
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "queries" in data:
                queries = data["queries"]
                if isinstance(queries, list):
                    cleaned = [
                        str(q).strip()
                        for q in queries
                        if isinstance(q, str) and q.strip()
                    ]
                    return cleaned[:max_n]
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: extract JSON from text
        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            data = json.loads(response[start:end])
            if isinstance(data, dict) and "queries" in data:
                queries = data["queries"]
                if isinstance(queries, list):
                    cleaned = [
                        str(q).strip()
                        for q in queries
                        if isinstance(q, str) and q.strip()
                    ]
                    return cleaned[:max_n]
        except (ValueError, json.JSONDecodeError, TypeError):
            pass

        # Last resort: split by lines
        lines = [
            line.strip().lstrip("- ").lstrip("* ").strip('"').strip("'")
            for line in response.strip().split("\n")
            if line.strip()
        ]
        cleaned = [line for line in lines if 2 <= len(line) <= 200]
        return cleaned[:max_n]

    # ------------------------------------------------------------------
    # Internal: Deterministic fallback
    # ------------------------------------------------------------------

    def _generate_queries_deterministic(
        self,
        gaps: list[dict[str, Any]],
        n: int,
    ) -> list[str]:
        """Generate queries from gap data without LLM.

        Uses node names and tags from the largest coverage gaps.

        Args:
            gaps: Coverage gap descriptions.
            n: Number of queries to generate.

        Returns:
            List of query strings.
        """
        queries: list[str] = []

        for gap in gaps:
            if len(queries) >= n:
                break

            children = gap.get("unvisited_children", [])
            for child in children:
                if len(queries) >= n:
                    break

                name = child.get("name", "")
                tags = child.get("tags", [])

                if tags:
                    query = f"{name} {' '.join(tags[:2])}"
                else:
                    query = name

                if query.strip():
                    queries.append(query.strip())

        return queries[:n]
