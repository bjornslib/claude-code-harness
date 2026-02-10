"""Dependency Inference – LLM-driven module dependency detection.

Implements Task 2.3.3 of PRD-RPG-P2-001 (Epic 2.3: Functionality Graph
Construction). Infers directed dependencies between modules using LLM
analysis, with embedding-based similarity fallback. Builds a NetworkX
DAG with cycle detection and resolution.

Example::

    from zerorepo.graph_construction.dependencies import (
        DependencyInference,
        DependencyConfig,
    )

    inference = DependencyInference(llm_gateway=gateway)
    result = inference.infer(modules, feature_map)

    for dep in result.dependencies:
        print(f"{dep.source} → {dep.target}: {dep.rationale}")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from zerorepo.graph_construction.partitioner import ModuleSpec
from zerorepo.llm.models import ModelTier
from zerorepo.ontology.models import FeatureNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class DependencyConfig(BaseModel):
    """Configuration for dependency inference.

    Attributes:
        llm_tier: LLM tier for inference.
        enable_llm: Whether to use LLM-based inference.
        enable_cycle_resolution: Whether to automatically resolve cycles.
        max_deps_per_module: Maximum outgoing dependencies per module.
        min_confidence: Minimum confidence for a dependency.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    llm_tier: ModelTier = Field(
        default=ModelTier.MEDIUM,
        description="LLM tier for dependency inference",
    )
    enable_llm: bool = Field(
        default=True,
        description="Whether to use LLM-based inference",
    )
    enable_cycle_resolution: bool = Field(
        default=True,
        description="Automatically resolve cycles",
    )
    max_deps_per_module: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Maximum outgoing deps per module",
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for a dependency",
    )


# ---------------------------------------------------------------------------
# Dependency Edge
# ---------------------------------------------------------------------------


class DependencyEdge(BaseModel):
    """A directed dependency between two modules.

    Attributes:
        source: Name of the dependent module.
        target: Name of the module it depends on.
        dependency_type: Type of dependency (uses, data_flow, workflow).
        weight: Strength of dependency (0.0 to 1.0).
        confidence: Confidence in this dependency (0.0 to 1.0).
        rationale: Why this dependency exists.
    """

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., min_length=1, description="Dependent module")
    target: str = Field(..., min_length=1, description="Module depended on")
    dependency_type: str = Field(
        default="uses",
        description="Type: uses, data_flow, workflow, inheritance",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Dependency strength",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Inference confidence",
    )
    rationale: str = Field(
        default="",
        description="Why this dependency exists",
    )


# ---------------------------------------------------------------------------
# Inference Result
# ---------------------------------------------------------------------------


class DependencyResult(BaseModel):
    """Result of dependency inference.

    Attributes:
        dependencies: Inferred dependency edges.
        graph: NetworkX DiGraph (not serialized in Pydantic).
        is_acyclic: Whether the dependency graph is acyclic.
        cycles_found: Number of cycles found before resolution.
        cycles_resolved: Number of cycles resolved.
        method: Inference method used (llm, embedding, heuristic).
        metadata: Additional result metadata.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    dependencies: list[DependencyEdge] = Field(
        default_factory=list, description="Inferred dependencies"
    )
    is_acyclic: bool = Field(
        default=True, description="Whether graph is acyclic"
    )
    cycles_found: int = Field(
        default=0, ge=0, description="Cycles found before resolution"
    )
    cycles_resolved: int = Field(
        default=0, ge=0, description="Cycles auto-resolved"
    )
    method: str = Field(
        default="unknown", description="Inference method"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @property
    def dependency_count(self) -> int:
        """Number of dependencies."""
        return len(self.dependencies)

    @property
    def as_pairs(self) -> list[tuple[str, str]]:
        """Return dependencies as (source, target) pairs."""
        return [(d.source, d.target) for d in self.dependencies]

    def build_graph(self) -> nx.DiGraph:
        """Build a NetworkX DiGraph from the dependencies.

        Returns:
            A directed graph with module names as nodes and
            dependency metadata on edges.
        """
        g = nx.DiGraph()
        for dep in self.dependencies:
            g.add_edge(
                dep.source,
                dep.target,
                dependency_type=dep.dependency_type,
                weight=dep.weight,
                confidence=dep.confidence,
                rationale=dep.rationale,
            )
        return g


# ---------------------------------------------------------------------------
# Dependency Inference
# ---------------------------------------------------------------------------


class DependencyInference:
    """LLM-driven dependency inference between modules.

    Analyzes module specifications to infer directed dependencies
    (module A depends on module B). Uses LLM analysis as the primary
    method with embedding-based heuristics as fallback.

    Args:
        llm_gateway: Optional LLM gateway.
        config: Optional configuration.

    Example::

        inference = DependencyInference(llm_gateway=gateway)
        result = inference.infer(modules, feature_map)
    """

    def __init__(
        self,
        llm_gateway: Any | None = None,
        config: DependencyConfig | None = None,
    ) -> None:
        self._llm = llm_gateway
        self._config = config or DependencyConfig()

    @property
    def config(self) -> DependencyConfig:
        """Return the inference configuration."""
        return self._config

    def infer(
        self,
        modules: list[ModuleSpec],
        feature_map: dict[str, FeatureNode] | None = None,
    ) -> DependencyResult:
        """Infer dependencies between modules.

        Attempts LLM-based inference first, falling back to heuristic
        methods. Detects and optionally resolves cycles.

        Args:
            modules: Module specifications to analyze.
            feature_map: Optional feature map for embedding-based fallback.

        Returns:
            A DependencyResult with inferred edges.

        Raises:
            ValueError: If modules list is empty.
        """
        if not modules:
            raise ValueError("Cannot infer dependencies for empty modules list")

        if len(modules) == 1:
            # Single module has no dependencies
            return DependencyResult(
                dependencies=[],
                is_acyclic=True,
                method="trivial",
            )

        module_names = {m.name for m in modules}
        deps: list[DependencyEdge] | None = None
        method = "unknown"

        # Try LLM inference
        if self._config.enable_llm and self._llm is not None:
            try:
                deps = self._llm_infer(modules)
                if deps is not None:
                    method = "llm"
            except Exception as e:
                logger.warning("LLM inference failed: %s", e)

        # Fallback to heuristic
        if deps is None:
            deps = self._heuristic_infer(modules, feature_map)
            method = "heuristic"

        # Filter to valid module names and enforce constraints
        deps = self._filter_dependencies(deps, module_names)
        deps = self._enforce_max_deps(deps)

        # Detect and resolve cycles
        cycles_found, cycles_resolved = 0, 0
        is_acyclic = True

        g = self._build_digraph(deps)
        cycles = list(nx.simple_cycles(g))
        cycles_found = len(cycles)

        if cycles_found > 0:
            is_acyclic = False
            if self._config.enable_cycle_resolution:
                deps = self._resolve_cycles(deps, g)
                # Verify resolution
                g_resolved = self._build_digraph(deps)
                remaining = list(nx.simple_cycles(g_resolved))
                cycles_resolved = cycles_found - len(remaining)
                is_acyclic = len(remaining) == 0

        return DependencyResult(
            dependencies=deps,
            is_acyclic=is_acyclic,
            cycles_found=cycles_found,
            cycles_resolved=cycles_resolved,
            method=method,
        )

    # ------------------------------------------------------------------
    # LLM-based inference
    # ------------------------------------------------------------------

    def _llm_infer(
        self, modules: list[ModuleSpec]
    ) -> list[DependencyEdge] | None:
        """Infer dependencies using LLM analysis.

        Args:
            modules: Modules to analyze.

        Returns:
            List of dependency edges, or None if parsing fails.
        """
        prompt = self._build_inference_prompt(modules)

        model = self._llm.select_model(tier=self._config.llm_tier)
        response = self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            tier=self._config.llm_tier,
        )

        return self._parse_llm_response(response, {m.name for m in modules})

    def _build_inference_prompt(self, modules: list[ModuleSpec]) -> str:
        """Build LLM prompt for dependency inference.

        Args:
            modules: Modules to include in the prompt.

        Returns:
            Formatted prompt string.
        """
        module_lines = []
        for m in modules:
            features = ", ".join(m.feature_ids[:10])
            if len(m.feature_ids) > 10:
                features += f"... ({len(m.feature_ids)} total)"
            module_lines.append(
                f"- **{m.name}**: {m.description} "
                f"[Features: {features}]"
            )

        modules_text = "\n".join(module_lines)

        return f"""You are a software architect analyzing module dependencies.

Modules:
{modules_text}

For each module, determine which other modules it depends on (uses/requires).
A depends on B means: A's features need B's features to work properly.

Rules:
- Only include genuine dependencies (not every module depends on every other)
- Dependencies should be directed: A → B means "A uses B"
- Avoid circular dependencies (A → B → A)
- Each dependency should have a clear rationale
- Assign confidence (0.0-1.0) and type (uses, data_flow, workflow)

Respond with ONLY a JSON object:
{{
  "dependencies": [
    {{
      "source": "ModuleName",
      "target": "DependencyModule",
      "dependency_type": "uses",
      "weight": 0.8,
      "confidence": 0.9,
      "rationale": "why this dependency exists"
    }}
  ]
}}"""

    def _parse_llm_response(
        self,
        response: str,
        module_names: set[str],
    ) -> list[DependencyEdge] | None:
        """Parse LLM response into dependency edges.

        Args:
            response: Raw LLM response.
            module_names: Valid module names.

        Returns:
            List of edges, or None if parsing fails.
        """
        try:
            data = self._extract_json(response)
            if data is None or "dependencies" not in data:
                return None

            edges: list[DependencyEdge] = []
            for d in data["dependencies"]:
                source = d.get("source", "")
                target = d.get("target", "")

                if source not in module_names or target not in module_names:
                    continue
                if source == target:
                    continue

                confidence = float(d.get("confidence", 1.0))
                if confidence < self._config.min_confidence:
                    continue

                edges.append(
                    DependencyEdge(
                        source=source,
                        target=target,
                        dependency_type=d.get("dependency_type", "uses"),
                        weight=min(1.0, max(0.0, float(d.get("weight", 1.0)))),
                        confidence=min(1.0, max(0.0, confidence)),
                        rationale=d.get("rationale", ""),
                    )
                )

            return edges if edges else None

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to parse dependency response: %s", e)
            return None

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract JSON from LLM response text.

        Args:
            text: Raw LLM response.

        Returns:
            Parsed dict, or None.
        """
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Code block
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Embedded JSON
        brace_start = text.find("{")
        if brace_start >= 0:
            brace_count = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return json.loads(text[brace_start : i + 1])
                        except json.JSONDecodeError:
                            break

        return None

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _heuristic_infer(
        self,
        modules: list[ModuleSpec],
        feature_map: dict[str, FeatureNode] | None,
    ) -> list[DependencyEdge]:
        """Infer dependencies using name-based heuristics.

        Looks for common patterns:
        - Modules with "API" depend on "Auth" and "DB" modules
        - "Testing" modules depend on modules they test
        - Modules sharing tag prefixes may be related

        Args:
            modules: Modules to analyze.
            feature_map: Optional feature map.

        Returns:
            List of heuristic dependency edges.
        """
        edges: list[DependencyEdge] = []
        module_names = {m.name for m in modules}
        module_by_name = {m.name: m for m in modules}

        # Heuristic: modules sharing features with similar tags
        if feature_map:
            tag_modules: dict[str, list[str]] = {}
            for mod in modules:
                for fid in mod.feature_ids:
                    feat = feature_map.get(fid)
                    if feat:
                        for tag in feat.tags:
                            tag_modules.setdefault(tag, []).append(mod.name)

            # If features in module A share tags with features in module B,
            # and A has fewer features, A might depend on B
            for tag, mod_names in tag_modules.items():
                unique_mods = list(set(mod_names))
                if len(unique_mods) == 2:
                    m1, m2 = unique_mods
                    c1 = module_by_name[m1].feature_count
                    c2 = module_by_name[m2].feature_count
                    # Smaller depends on larger (heuristic)
                    if c1 < c2:
                        edges.append(
                            DependencyEdge(
                                source=m1,
                                target=m2,
                                dependency_type="uses",
                                weight=0.5,
                                confidence=0.5,
                                rationale=f"Shared tag: {tag}",
                            )
                        )
                    elif c2 < c1:
                        edges.append(
                            DependencyEdge(
                                source=m2,
                                target=m1,
                                dependency_type="uses",
                                weight=0.5,
                                confidence=0.5,
                                rationale=f"Shared tag: {tag}",
                            )
                        )

        # De-duplicate edges
        seen: set[tuple[str, str]] = set()
        unique_edges: list[DependencyEdge] = []
        for e in edges:
            key = (e.source, e.target)
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        return unique_edges

    # ------------------------------------------------------------------
    # Graph utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _build_digraph(deps: list[DependencyEdge]) -> nx.DiGraph:
        """Build a NetworkX DiGraph from dependency edges.

        Args:
            deps: Dependency edges.

        Returns:
            NetworkX DiGraph.
        """
        g = nx.DiGraph()
        for dep in deps:
            g.add_edge(dep.source, dep.target)
        return g

    def _filter_dependencies(
        self,
        deps: list[DependencyEdge],
        module_names: set[str],
    ) -> list[DependencyEdge]:
        """Filter dependencies to valid module names and remove self-loops.

        Args:
            deps: Raw dependencies.
            module_names: Valid module names.

        Returns:
            Filtered dependencies.
        """
        return [
            d
            for d in deps
            if d.source in module_names
            and d.target in module_names
            and d.source != d.target
            and d.confidence >= self._config.min_confidence
        ]

    def _enforce_max_deps(
        self, deps: list[DependencyEdge]
    ) -> list[DependencyEdge]:
        """Enforce maximum dependencies per module.

        Keeps the highest-weight dependencies.

        Args:
            deps: Dependencies to trim.

        Returns:
            Trimmed dependencies.
        """
        max_deps = self._config.max_deps_per_module

        # Group by source
        by_source: dict[str, list[DependencyEdge]] = {}
        for d in deps:
            by_source.setdefault(d.source, []).append(d)

        result: list[DependencyEdge] = []
        for source, source_deps in by_source.items():
            if len(source_deps) <= max_deps:
                result.extend(source_deps)
            else:
                # Keep top-N by weight * confidence
                sorted_deps = sorted(
                    source_deps,
                    key=lambda d: d.weight * d.confidence,
                    reverse=True,
                )
                result.extend(sorted_deps[:max_deps])

        return result

    def _resolve_cycles(
        self,
        deps: list[DependencyEdge],
        g: nx.DiGraph,
    ) -> list[DependencyEdge]:
        """Resolve cycles by removing the weakest edge in each cycle.

        Iteratively finds cycles and removes the edge with the lowest
        weight * confidence product.

        Args:
            deps: Current dependencies.
            g: NetworkX graph.

        Returns:
            Dependencies with cycles resolved.
        """
        removed: set[tuple[str, str]] = set()
        max_iterations = len(deps) * 2  # Safety limit

        for _ in range(max_iterations):
            cycles = list(nx.simple_cycles(g))
            if not cycles:
                break

            cycle = cycles[0]
            # Find the weakest edge in this cycle
            cycle_edges = []
            for i in range(len(cycle)):
                src = cycle[i]
                tgt = cycle[(i + 1) % len(cycle)]
                cycle_edges.append((src, tgt))

            # Find matching deps and their weights
            weakest_edge = None
            weakest_score = float("inf")
            for src, tgt in cycle_edges:
                for d in deps:
                    if d.source == src and d.target == tgt:
                        score = d.weight * d.confidence
                        if score < weakest_score:
                            weakest_score = score
                            weakest_edge = (src, tgt)

            if weakest_edge:
                removed.add(weakest_edge)
                g.remove_edge(weakest_edge[0], weakest_edge[1])
                logger.info(
                    "Resolved cycle by removing %s → %s (score=%.3f)",
                    weakest_edge[0],
                    weakest_edge[1],
                    weakest_score,
                )
            else:
                # Shouldn't happen, but break to prevent infinite loop
                break

        # Rebuild deps list without removed edges
        return [
            d
            for d in deps
            if (d.source, d.target) not in removed
        ]
