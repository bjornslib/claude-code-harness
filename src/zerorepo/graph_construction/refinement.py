"""Iterative Refinement for Functionality Graphs.

Implements Task 2.3.5 of PRD-RPG-P2-001 (Epic 2.3: Functionality Graph
Construction). Provides user-driven graph refinement operations with
LLM-powered quality suggestions.

Operations:
- ``move_feature``: Move a feature from one module to another
- ``merge_modules``: Combine two modules into one
- ``split_module``: Split a module into sub-modules via clustering

Each operation:
1. Validates the request
2. Applies the structural change
3. Re-computes quality metrics (cohesion/coupling)
4. Optionally asks LLM for improvement suggestions
5. Records the action in refinement history

Example::

    from zerorepo.graph_construction.refinement import (
        GraphRefinement,
        RefinementConfig,
    )

    refiner = GraphRefinement(
        graph=functionality_graph,
        llm_gateway=gateway,
    )
    result = refiner.move_feature("feat_x", "ModuleA", "ModuleB")
    print(result.suggestion)  # LLM suggestion
    print(result.metrics_after)  # Updated metrics

    # Undo last action
    refiner.undo()
"""

from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from zerorepo.graph_construction.dependencies import (
    DependencyEdge,
    DependencyInference,
    DependencyResult,
)
from zerorepo.graph_construction.metrics import (
    MetricsConfig,
    PartitionMetrics,
    compute_all_metrics,
    compute_cohesion,
)
from zerorepo.graph_construction.partitioner import (
    ModulePartitioner,
    ModuleSpec,
    PartitionerConfig,
)
from zerorepo.llm.models import ModelTier
from zerorepo.ontology.models import FeatureNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Configuration
# ---------------------------------------------------------------------------


class ActionType(str, Enum):
    """Types of refinement actions."""

    MOVE_FEATURE = "move_feature"
    MERGE_MODULES = "merge_modules"
    SPLIT_MODULE = "split_module"


class RefinementConfig(BaseModel):
    """Configuration for the graph refinement engine.

    Attributes:
        enable_llm_suggestions: Whether to ask LLM for suggestions.
        llm_tier: LLM tier for suggestion generation.
        recompute_metrics: Whether to recompute metrics after each edit.
        min_module_size: Minimum features per module (warn if below).
        max_history_size: Maximum refinement history entries.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    enable_llm_suggestions: bool = Field(
        default=True, description="Enable LLM suggestions after edits"
    )
    llm_tier: ModelTier = Field(
        default=ModelTier.MEDIUM,
        description="LLM tier for suggestions",
    )
    recompute_metrics: bool = Field(
        default=True,
        description="Recompute metrics after each edit",
    )
    metrics_config: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Metrics configuration",
    )
    min_module_size: int = Field(
        default=1,
        description="Minimum features per module",
    )
    max_history_size: int = Field(
        default=100,
        description="Maximum refinement history entries",
    )


# ---------------------------------------------------------------------------
# Action and Result Models
# ---------------------------------------------------------------------------


class RefinementAction(BaseModel):
    """A single refinement action with before/after state.

    Attributes:
        action_type: Type of the action.
        params: Action parameters.
        timestamp: When the action was performed.
        modules_before: Snapshot of modules before the action.
        dependencies_before: Snapshot of dependencies before the action.
        metrics_before: Metrics before the action.
        metrics_after: Metrics after the action.
        suggestion: LLM suggestion (if any).
    """

    model_config = ConfigDict(frozen=True)

    action_type: ActionType = Field(description="Type of refinement action")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Action parameters"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp",
    )
    modules_before: list[ModuleSpec] = Field(
        default_factory=list, description="Modules before edit"
    )
    dependencies_before: list[DependencyEdge] = Field(
        default_factory=list, description="Dependencies before edit"
    )
    metrics_before: PartitionMetrics | None = Field(
        default=None, description="Metrics before edit"
    )
    metrics_after: PartitionMetrics | None = Field(
        default=None, description="Metrics after edit"
    )
    suggestion: str = Field(
        default="", description="LLM suggestion"
    )


class RefinementResult(BaseModel):
    """Result of a refinement operation.

    Attributes:
        success: Whether the operation succeeded.
        action: The recorded action.
        modules: Updated module list.
        metrics_before: Metrics before the edit.
        metrics_after: Metrics after the edit.
        suggestion: LLM suggestion for further improvements.
        warnings: Any warnings generated.
    """

    model_config = ConfigDict(frozen=True)

    success: bool = Field(description="Whether the operation succeeded")
    action: RefinementAction | None = Field(
        default=None, description="The recorded action"
    )
    modules: list[ModuleSpec] = Field(
        default_factory=list, description="Updated modules"
    )
    metrics_before: PartitionMetrics | None = Field(
        default=None, description="Metrics before edit"
    )
    metrics_after: PartitionMetrics | None = Field(
        default=None, description="Metrics after edit"
    )
    suggestion: str = Field(
        default="", description="LLM suggestion"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings"
    )
    error: str = Field(default="", description="Error message if failed")


class RefinementHistory(BaseModel):
    """History of refinement actions with undo support.

    Attributes:
        actions: Ordered list of refinement actions.
        max_size: Maximum number of actions to retain.
    """

    model_config = ConfigDict(frozen=False)

    actions: list[RefinementAction] = Field(
        default_factory=list, description="Refinement actions"
    )
    max_size: int = Field(default=100, description="Max history size")

    @property
    def action_count(self) -> int:
        """Number of actions in history."""
        return len(self.actions)

    @property
    def can_undo(self) -> bool:
        """Whether there are actions to undo."""
        return len(self.actions) > 0

    @property
    def last_action(self) -> RefinementAction | None:
        """The most recent action."""
        return self.actions[-1] if self.actions else None

    def add(self, action: RefinementAction) -> None:
        """Add an action to history, trimming if needed."""
        self.actions.append(action)
        if len(self.actions) > self.max_size:
            self.actions = self.actions[-self.max_size :]

    def pop(self) -> RefinementAction | None:
        """Remove and return the last action."""
        return self.actions.pop() if self.actions else None

    def to_summary(self) -> list[dict[str, Any]]:
        """Return a summary of all actions."""
        return [
            {
                "action": a.action_type.value,
                "params": a.params,
                "timestamp": a.timestamp,
                "has_suggestion": bool(a.suggestion),
            }
            for a in self.actions
        ]


# ---------------------------------------------------------------------------
# Graph Refinement Engine
# ---------------------------------------------------------------------------


class GraphRefinement:
    """Iterative refinement engine for functionality graphs.

    Manages a mutable working copy of modules and dependencies, applies
    user edits, re-evaluates quality metrics, and provides LLM-powered
    improvement suggestions.

    Args:
        modules: Initial module specifications.
        dependencies: Initial dependency edges.
        feature_map: Feature ID → FeatureNode mapping.
        llm_gateway: Optional LLM gateway for suggestions.
        config: Optional refinement configuration.

    Example::

        refiner = GraphRefinement(
            modules=graph.modules,
            dependencies=graph.dependencies,
            feature_map=features,
            llm_gateway=gateway,
        )
        result = refiner.move_feature("auth.jwt", "Auth", "Security")
        if result.suggestion:
            print(result.suggestion)
    """

    def __init__(
        self,
        modules: list[ModuleSpec],
        dependencies: list[DependencyEdge] | None = None,
        feature_map: dict[str, FeatureNode] | None = None,
        llm_gateway: Any | None = None,
        config: RefinementConfig | None = None,
    ) -> None:
        self._config = config or RefinementConfig()
        self._llm = llm_gateway
        self._feature_map = feature_map or {}

        # Mutable working copies
        self._modules: list[ModuleSpec] = list(modules)
        self._dependencies: list[DependencyEdge] = list(dependencies or [])

        self._history = RefinementHistory(
            max_size=self._config.max_history_size
        )

    @property
    def modules(self) -> list[ModuleSpec]:
        """Current module list (read-only copy)."""
        return list(self._modules)

    @property
    def dependencies(self) -> list[DependencyEdge]:
        """Current dependency list (read-only copy)."""
        return list(self._dependencies)

    @property
    def history(self) -> RefinementHistory:
        """Refinement history."""
        return self._history

    @property
    def module_names(self) -> set[str]:
        """Set of current module names."""
        return {m.name for m in self._modules}

    def _get_module(self, name: str) -> ModuleSpec | None:
        """Find a module by name."""
        for m in self._modules:
            if m.name == name:
                return m
        return None

    def _find_feature_module(self, feature_id: str) -> str | None:
        """Find which module contains a feature."""
        for m in self._modules:
            if feature_id in m.feature_ids:
                return m.name
        return None

    def _compute_current_metrics(self) -> PartitionMetrics | None:
        """Compute metrics for the current state."""
        if not self._config.recompute_metrics:
            return None
        dep_pairs = [(d.source, d.target) for d in self._dependencies]
        return compute_all_metrics(
            modules=self._modules,
            feature_map=self._feature_map,
            dependencies=dep_pairs,
            config=self._config.metrics_config,
        )

    def _get_llm_suggestion(
        self,
        action_type: ActionType,
        params: dict[str, Any],
        metrics_before: PartitionMetrics | None,
        metrics_after: PartitionMetrics | None,
    ) -> str:
        """Get LLM suggestion after an edit."""
        if not self._config.enable_llm_suggestions or not self._llm:
            return ""

        try:
            model = self._llm.select_model(self._config.llm_tier)
            prompt = self._build_suggestion_prompt(
                action_type, params, metrics_before, metrics_after
            )
            response = self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                tier=self._config.llm_tier,
            )
            return response.strip()
        except Exception as e:
            logger.warning("LLM suggestion failed: %s", e)
            return ""

    def _build_suggestion_prompt(
        self,
        action_type: ActionType,
        params: dict[str, Any],
        metrics_before: PartitionMetrics | None,
        metrics_after: PartitionMetrics | None,
    ) -> str:
        """Build the LLM prompt for post-edit suggestions."""
        module_summary = []
        for m in self._modules:
            module_summary.append(
                f"  - {m.name}: {m.feature_count} features "
                f"({', '.join(m.feature_ids[:5])}{'...' if m.feature_count > 5 else ''})"
            )

        prompt_parts = [
            "You are a software architecture advisor.",
            f"\nAction performed: {action_type.value}",
            f"Parameters: {json.dumps(params)}",
            "\nCurrent modules:",
            *module_summary,
        ]

        if metrics_before:
            prompt_parts.append(
                f"\nMetrics BEFORE: avg_cohesion={metrics_before.avg_cohesion:.3f}, "
                f"max_coupling={metrics_before.max_coupling}"
            )
        if metrics_after:
            prompt_parts.append(
                f"Metrics AFTER: avg_cohesion={metrics_after.avg_cohesion:.3f}, "
                f"max_coupling={metrics_after.max_coupling}"
            )

        prompt_parts.append(
            "\nBased on this change, provide a brief suggestion (1-2 sentences) "
            "on how to improve module quality. Focus on cohesion and coupling."
        )

        return "\n".join(prompt_parts)

    def _snapshot_modules(self) -> list[ModuleSpec]:
        """Take a snapshot of current modules."""
        return list(self._modules)

    def _snapshot_dependencies(self) -> list[DependencyEdge]:
        """Take a snapshot of current dependencies."""
        return list(self._dependencies)

    def _replace_module(self, old_name: str, new_module: ModuleSpec) -> None:
        """Replace a module by name."""
        for i, m in enumerate(self._modules):
            if m.name == old_name:
                self._modules[i] = new_module
                return

    def _remove_module(self, name: str) -> None:
        """Remove a module by name."""
        self._modules = [m for m in self._modules if m.name != name]

    def _update_dependencies_for_rename(
        self, old_name: str, new_name: str
    ) -> None:
        """Update dependencies when a module is renamed."""
        updated = []
        for d in self._dependencies:
            source = new_name if d.source == old_name else d.source
            target = new_name if d.target == old_name else d.target
            if source != d.source or target != d.target:
                updated.append(
                    DependencyEdge(
                        source=source,
                        target=target,
                        dependency_type=d.dependency_type,
                        weight=d.weight,
                        confidence=d.confidence,
                        rationale=d.rationale,
                    )
                )
            else:
                updated.append(d)
        self._dependencies = updated

    def _remove_dependencies_for_module(self, name: str) -> None:
        """Remove all dependencies involving a module."""
        self._dependencies = [
            d
            for d in self._dependencies
            if d.source != name and d.target != name
        ]

    # -------------------------------------------------------------------
    # Public Operations
    # -------------------------------------------------------------------

    def move_feature(
        self,
        feature_id: str,
        from_module: str,
        to_module: str,
    ) -> RefinementResult:
        """Move a feature from one module to another.

        Args:
            feature_id: ID of the feature to move.
            from_module: Source module name.
            to_module: Destination module name.

        Returns:
            RefinementResult with updated state and suggestions.
        """
        params = {
            "feature_id": feature_id,
            "from_module": from_module,
            "to_module": to_module,
        }

        # Validate
        src = self._get_module(from_module)
        dst = self._get_module(to_module)

        if src is None:
            return RefinementResult(
                success=False,
                error=f"Source module '{from_module}' not found",
            )
        if dst is None:
            return RefinementResult(
                success=False,
                error=f"Destination module '{to_module}' not found",
            )
        if from_module == to_module:
            return RefinementResult(
                success=False,
                error="Source and destination modules are the same",
            )
        if feature_id not in src.feature_ids:
            return RefinementResult(
                success=False,
                error=f"Feature '{feature_id}' not in module '{from_module}'",
            )

        # Snapshot state
        modules_before = self._snapshot_modules()
        deps_before = self._snapshot_dependencies()
        metrics_before = self._compute_current_metrics()

        # Apply edit
        warnings: list[str] = []
        new_src_features = [f for f in src.feature_ids if f != feature_id]
        new_dst_features = list(dst.feature_ids) + [feature_id]

        new_src = ModuleSpec(
            name=src.name,
            description=src.description,
            feature_ids=new_src_features,
            public_interface=[
                p for p in src.public_interface if p != feature_id
            ],
            rationale=src.rationale,
            metadata=src.metadata,
        )
        new_dst = ModuleSpec(
            name=dst.name,
            description=dst.description,
            feature_ids=new_dst_features,
            public_interface=dst.public_interface,
            rationale=dst.rationale,
            metadata=dst.metadata,
        )

        self._replace_module(from_module, new_src)
        self._replace_module(to_module, new_dst)

        if len(new_src_features) < self._config.min_module_size:
            warnings.append(
                f"Module '{from_module}' now has {len(new_src_features)} features "
                f"(below minimum of {self._config.min_module_size})"
            )

        # Recompute metrics
        metrics_after = self._compute_current_metrics()

        # Get LLM suggestion
        suggestion = self._get_llm_suggestion(
            ActionType.MOVE_FEATURE, params, metrics_before, metrics_after
        )

        # Record action
        action = RefinementAction(
            action_type=ActionType.MOVE_FEATURE,
            params=params,
            modules_before=modules_before,
            dependencies_before=deps_before,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            suggestion=suggestion,
        )
        self._history.add(action)

        logger.info(
            "Moved feature '%s' from '%s' to '%s'",
            feature_id, from_module, to_module,
        )

        return RefinementResult(
            success=True,
            action=action,
            modules=self.modules,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            suggestion=suggestion,
            warnings=warnings,
        )

    def merge_modules(
        self,
        module_a: str,
        module_b: str,
        merged_name: str | None = None,
    ) -> RefinementResult:
        """Merge two modules into one.

        Args:
            module_a: First module name.
            module_b: Second module name.
            merged_name: Optional name for the merged module.

        Returns:
            RefinementResult with updated state.
        """
        params = {
            "module_a": module_a,
            "module_b": module_b,
            "merged_name": merged_name,
        }

        # Validate
        mod_a = self._get_module(module_a)
        mod_b = self._get_module(module_b)

        if mod_a is None:
            return RefinementResult(
                success=False,
                error=f"Module '{module_a}' not found",
            )
        if mod_b is None:
            return RefinementResult(
                success=False,
                error=f"Module '{module_b}' not found",
            )
        if module_a == module_b:
            return RefinementResult(
                success=False,
                error="Cannot merge a module with itself",
            )

        # Snapshot
        modules_before = self._snapshot_modules()
        deps_before = self._snapshot_dependencies()
        metrics_before = self._compute_current_metrics()

        # Build merged module
        name = merged_name or f"{module_a}+{module_b}"
        merged_features = list(mod_a.feature_ids) + list(mod_b.feature_ids)
        merged_public = list(mod_a.public_interface) + list(
            mod_b.public_interface
        )
        merged_desc = (
            f"Merged from {module_a} and {module_b}. "
            f"{mod_a.description} {mod_b.description}"
        ).strip()

        merged = ModuleSpec(
            name=name,
            description=merged_desc,
            feature_ids=merged_features,
            public_interface=merged_public,
            rationale=f"Merged {module_a} + {module_b}",
        )

        # Remove old modules and add merged
        self._remove_module(module_a)
        self._remove_module(module_b)
        self._modules.append(merged)

        # Update dependencies: redirect both old names to the merged name
        # and remove self-loops
        updated_deps: list[DependencyEdge] = []
        for d in self._dependencies:
            source = name if d.source in (module_a, module_b) else d.source
            target = name if d.target in (module_a, module_b) else d.target
            if source == target:
                continue  # Remove self-loop
            updated_deps.append(
                DependencyEdge(
                    source=source,
                    target=target,
                    dependency_type=d.dependency_type,
                    weight=d.weight,
                    confidence=d.confidence,
                    rationale=d.rationale,
                )
            )
        # Deduplicate (same source-target pairs)
        seen: set[tuple[str, str]] = set()
        deduped: list[DependencyEdge] = []
        for d in updated_deps:
            key = (d.source, d.target)
            if key not in seen:
                seen.add(key)
                deduped.append(d)
        self._dependencies = deduped

        # Recompute metrics
        metrics_after = self._compute_current_metrics()

        # LLM suggestion
        suggestion = self._get_llm_suggestion(
            ActionType.MERGE_MODULES, params, metrics_before, metrics_after
        )

        # Record
        action = RefinementAction(
            action_type=ActionType.MERGE_MODULES,
            params=params,
            modules_before=modules_before,
            dependencies_before=deps_before,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            suggestion=suggestion,
        )
        self._history.add(action)

        logger.info(
            "Merged modules '%s' and '%s' into '%s'",
            module_a, module_b, name,
        )

        return RefinementResult(
            success=True,
            action=action,
            modules=self.modules,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            suggestion=suggestion,
        )

    def split_module(
        self,
        module_name: str,
        num_parts: int = 2,
    ) -> RefinementResult:
        """Split a module into sub-modules using clustering.

        Uses embedding-based k-means if features have embeddings,
        otherwise splits by feature order.

        Args:
            module_name: Name of the module to split.
            num_parts: Number of parts to split into.

        Returns:
            RefinementResult with updated state.
        """
        params = {
            "module_name": module_name,
            "num_parts": num_parts,
        }

        # Validate
        mod = self._get_module(module_name)
        if mod is None:
            return RefinementResult(
                success=False,
                error=f"Module '{module_name}' not found",
            )
        if num_parts < 2:
            return RefinementResult(
                success=False,
                error="num_parts must be at least 2",
            )
        if mod.feature_count < num_parts:
            return RefinementResult(
                success=False,
                error=(
                    f"Module '{module_name}' has {mod.feature_count} features, "
                    f"cannot split into {num_parts} parts"
                ),
            )

        # Snapshot
        modules_before = self._snapshot_modules()
        deps_before = self._snapshot_dependencies()
        metrics_before = self._compute_current_metrics()

        # Perform split
        sub_modules = self._cluster_split(mod, num_parts)

        # Replace original with sub-modules
        self._remove_module(module_name)
        self._modules.extend(sub_modules)

        # Update dependencies: redirect old module name to all sub-modules
        # or just the first one (simplest approach)
        new_names = [s.name for s in sub_modules]
        updated_deps: list[DependencyEdge] = []
        for d in self._dependencies:
            if d.source == module_name:
                # Fan out: first sub-module inherits outgoing deps
                updated_deps.append(
                    DependencyEdge(
                        source=new_names[0],
                        target=d.target,
                        dependency_type=d.dependency_type,
                        weight=d.weight,
                        confidence=d.confidence,
                        rationale=d.rationale,
                    )
                )
            elif d.target == module_name:
                # Fan in: all sub-modules receive incoming deps
                for nm in new_names:
                    updated_deps.append(
                        DependencyEdge(
                            source=d.source,
                            target=nm,
                            dependency_type=d.dependency_type,
                            weight=d.weight,
                            confidence=d.confidence,
                            rationale=d.rationale,
                        )
                    )
            else:
                updated_deps.append(d)

        # Deduplicate and remove self-loops
        seen: set[tuple[str, str]] = set()
        deduped: list[DependencyEdge] = []
        for d in updated_deps:
            key = (d.source, d.target)
            if key not in seen and d.source != d.target:
                seen.add(key)
                deduped.append(d)
        self._dependencies = deduped

        # Recompute metrics
        metrics_after = self._compute_current_metrics()

        # LLM suggestion
        suggestion = self._get_llm_suggestion(
            ActionType.SPLIT_MODULE, params, metrics_before, metrics_after
        )

        # Record
        action = RefinementAction(
            action_type=ActionType.SPLIT_MODULE,
            params=params,
            modules_before=modules_before,
            dependencies_before=deps_before,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            suggestion=suggestion,
        )
        self._history.add(action)

        logger.info(
            "Split module '%s' into %d parts: %s",
            module_name, num_parts, new_names,
        )

        return RefinementResult(
            success=True,
            action=action,
            modules=self.modules,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            suggestion=suggestion,
        )

    def _cluster_split(
        self, module: ModuleSpec, num_parts: int
    ) -> list[ModuleSpec]:
        """Split a module using clustering on feature embeddings.

        Falls back to round-robin if embeddings are not available.
        """
        features = module.feature_ids

        # Try embedding-based clustering
        embeddings = []
        for fid in features:
            feat = self._feature_map.get(fid)
            if feat and feat.embedding:
                embeddings.append(np.array(feat.embedding, dtype=np.float64))

        if len(embeddings) >= num_parts and len(embeddings) == len(features):
            return self._kmeans_split(module, num_parts, embeddings)

        # Fallback: round-robin split
        return self._roundrobin_split(module, num_parts)

    def _kmeans_split(
        self,
        module: ModuleSpec,
        num_parts: int,
        embeddings: list[np.ndarray],
    ) -> list[ModuleSpec]:
        """Split using k-means clustering on embeddings."""
        from sklearn.cluster import KMeans

        X = np.vstack(embeddings)
        kmeans = KMeans(n_clusters=num_parts, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        clusters: dict[int, list[str]] = {}
        for i, fid in enumerate(module.feature_ids):
            cluster = int(labels[i])
            clusters.setdefault(cluster, []).append(fid)

        sub_modules: list[ModuleSpec] = []
        for idx in sorted(clusters.keys()):
            fids = clusters[idx]
            sub_name = f"{module.name}_part{idx + 1}"
            sub_modules.append(
                ModuleSpec(
                    name=sub_name,
                    description=f"Split from {module.name} (part {idx + 1})",
                    feature_ids=fids,
                    rationale=f"Cluster-based split from {module.name}",
                )
            )

        return sub_modules

    def _roundrobin_split(
        self, module: ModuleSpec, num_parts: int
    ) -> list[ModuleSpec]:
        """Split using round-robin assignment."""
        buckets: list[list[str]] = [[] for _ in range(num_parts)]
        for i, fid in enumerate(module.feature_ids):
            buckets[i % num_parts].append(fid)

        sub_modules: list[ModuleSpec] = []
        for idx, fids in enumerate(buckets):
            if fids:  # Skip empty buckets
                sub_name = f"{module.name}_part{idx + 1}"
                sub_modules.append(
                    ModuleSpec(
                        name=sub_name,
                        description=f"Split from {module.name} (part {idx + 1})",
                        feature_ids=fids,
                        rationale=f"Round-robin split from {module.name}",
                    )
                )

        return sub_modules

    # -------------------------------------------------------------------
    # Undo
    # -------------------------------------------------------------------

    def undo(self) -> RefinementResult:
        """Undo the last refinement action.

        Restores modules and dependencies to their pre-action state.

        Returns:
            RefinementResult indicating success.
        """
        if not self._history.can_undo:
            return RefinementResult(
                success=False,
                error="No actions to undo",
            )

        action = self._history.pop()
        if action is None:
            return RefinementResult(
                success=False,
                error="No actions to undo",
            )

        # Restore state
        self._modules = list(action.modules_before)
        self._dependencies = list(action.dependencies_before)

        logger.info("Undid action: %s", action.action_type.value)

        return RefinementResult(
            success=True,
            action=action,
            modules=self.modules,
            metrics_before=action.metrics_after,
            metrics_after=action.metrics_before,
        )

    # -------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------

    def get_metrics(self) -> PartitionMetrics | None:
        """Compute and return current metrics."""
        return self._compute_current_metrics()

    def get_module_features(self, module_name: str) -> list[str]:
        """Get feature IDs in a module."""
        mod = self._get_module(module_name)
        return list(mod.feature_ids) if mod else []

    def get_history_summary(self) -> list[dict[str, Any]]:
        """Get a summary of all refinement actions."""
        return self._history.to_summary()
