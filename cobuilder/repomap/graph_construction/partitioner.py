"""Module Partitioning Algorithm – LLM-driven feature clustering.

Implements Task 2.3.1 of PRD-RPG-P2-001 (Epic 2.3: Functionality Graph
Construction). Groups selected features into cohesive modules using LLM
analysis, with k-means clustering on embeddings as a fallback.

Partitioning criteria:
- Functional cohesion (features serving similar purposes)
- Data coupling (features sharing data structures)
- Workflow dependencies (features called in sequence)

Performance targets from PRD:
- Target 3-10 modules per graph
- No module has < 2 features or > 15 features
- Cohesion > 0.6 for all modules
- Descriptive module names (not "Module 1")

Example::

    from cobuilder.repomap.graph_construction.partitioner import (
        ModulePartitioner,
        PartitionerConfig,
    )

    partitioner = ModulePartitioner(llm_gateway=gateway)
    result = partitioner.partition(features)

    for module in result.modules:
        print(f"{module.name}: {len(module.feature_ids)} features")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cobuilder.repomap.llm.models import ModelTier
from cobuilder.repomap.ontology.models import FeatureNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class PartitionerConfig(BaseModel):
    """Configuration for the ModulePartitioner.

    Attributes:
        min_modules: Minimum number of modules to create.
        max_modules: Maximum number of modules to create.
        min_features_per_module: Minimum features in a single module.
        max_features_per_module: Maximum features in a single module.
        llm_tier: LLM tier for partitioning.
        enable_llm: Whether to attempt LLM-based partitioning.
        kmeans_n_init: Number of k-means initializations for fallback.
        embedding_dim: Default embedding dimensionality.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    min_modules: int = Field(
        default=3,
        ge=2,
        le=20,
        description="Minimum number of modules",
    )
    max_modules: int = Field(
        default=10,
        ge=2,
        le=50,
        description="Maximum number of modules",
    )
    min_features_per_module: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Minimum features per module",
    )
    max_features_per_module: int = Field(
        default=15,
        ge=2,
        le=100,
        description="Maximum features per module",
    )
    llm_tier: ModelTier = Field(
        default=ModelTier.MEDIUM,
        description="LLM tier for partitioning",
    )
    enable_llm: bool = Field(
        default=True,
        description="Whether to use LLM-based partitioning",
    )
    kmeans_n_init: int = Field(
        default=10,
        ge=1,
        description="Number of k-means random initializations",
    )
    embedding_dim: int = Field(
        default=384,
        ge=1,
        description="Default embedding dimensionality",
    )

    @field_validator("max_modules")
    @classmethod
    def validate_max_modules(cls, v: int, info: Any) -> int:
        """Ensure max_modules >= min_modules."""
        min_mod = info.data.get("min_modules", 3)
        if v < min_mod:
            raise ValueError(
                f"max_modules ({v}) must be >= min_modules ({min_mod})"
            )
        return v


# ---------------------------------------------------------------------------
# Module Specification
# ---------------------------------------------------------------------------


class ModuleSpec(BaseModel):
    """Specification for a single module in the partitioned graph.

    Attributes:
        name: Descriptive module name (e.g., "Evaluation", "Preprocessing").
        description: Functional purpose of the module.
        feature_ids: IDs of features assigned to this module.
        public_interface: Exported functions/classes (feature IDs).
        rationale: Why these features belong together.
        metadata: Additional module-specific data.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Descriptive module name",
    )
    description: str = Field(
        default="",
        description="Functional purpose",
    )
    feature_ids: list[str] = Field(
        ...,
        min_length=1,
        description="IDs of features in this module",
    )
    public_interface: list[str] = Field(
        default_factory=list,
        description="Feature IDs forming the public interface",
    )
    rationale: str = Field(
        default="",
        description="Why these features belong together",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    @property
    def feature_count(self) -> int:
        """Number of features in this module."""
        return len(self.feature_ids)


# ---------------------------------------------------------------------------
# Partition Result
# ---------------------------------------------------------------------------


class PartitionResult(BaseModel):
    """Result of partitioning features into modules.

    Attributes:
        modules: List of module specifications.
        unassigned_feature_ids: Features that couldn't be assigned.
        method: Partitioning method used ("llm" or "kmeans").
        total_features: Total number of input features.
        metadata: Additional result-specific data.
    """

    model_config = ConfigDict(frozen=True)

    modules: list[ModuleSpec] = Field(
        default_factory=list,
        description="Module specifications",
    )
    unassigned_feature_ids: list[str] = Field(
        default_factory=list,
        description="Unassigned feature IDs",
    )
    method: str = Field(
        default="unknown",
        description="Partitioning method used",
    )
    total_features: int = Field(
        default=0,
        ge=0,
        description="Total input features",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    @property
    def module_count(self) -> int:
        """Number of modules created."""
        return len(self.modules)

    @property
    def assigned_feature_count(self) -> int:
        """Number of features assigned to modules."""
        return sum(m.feature_count for m in self.modules)

    @property
    def all_feature_ids(self) -> set[str]:
        """All feature IDs across all modules."""
        ids: set[str] = set()
        for m in self.modules:
            ids.update(m.feature_ids)
        return ids


# ---------------------------------------------------------------------------
# Module Partitioner
# ---------------------------------------------------------------------------


class ModulePartitioner:
    """LLM-driven feature clustering into cohesive modules.

    Groups a set of feature nodes into modules based on functional cohesion,
    data coupling, and workflow dependencies. Uses LLM analysis as the
    primary method with k-means clustering on embeddings as a fallback.

    Args:
        llm_gateway: Optional LLM gateway for LLM-based partitioning.
        config: Optional partitioner configuration.

    Example::

        partitioner = ModulePartitioner(llm_gateway=gateway)
        result = partitioner.partition(features)

        for module in result.modules:
            print(f"{module.name}: {module.feature_count} features")
    """

    def __init__(
        self,
        llm_gateway: Any | None = None,
        config: PartitionerConfig | None = None,
    ) -> None:
        self._llm = llm_gateway
        self._config = config or PartitionerConfig()

    @property
    def config(self) -> PartitionerConfig:
        """Return the partitioner configuration."""
        return self._config

    def partition(
        self,
        features: list[FeatureNode],
        target_modules: int | None = None,
    ) -> PartitionResult:
        """Partition features into cohesive modules.

        Attempts LLM-based partitioning first, falling back to k-means
        clustering on feature embeddings if the LLM is unavailable or fails.

        Args:
            features: List of feature nodes to partition.
            target_modules: Desired number of modules. If None, the LLM
                decides or k-means uses a heuristic.

        Returns:
            A PartitionResult with module specifications.

        Raises:
            ValueError: If features list is empty.
        """
        if not features:
            raise ValueError("Cannot partition an empty list of features")

        # Clamp target_modules to valid range
        if target_modules is not None:
            target_modules = max(
                self._config.min_modules,
                min(target_modules, self._config.max_modules),
            )

        # Build feature map for quick lookup
        feature_map = {f.id: f for f in features}

        # Try LLM-based partitioning first
        if self._config.enable_llm and self._llm is not None:
            try:
                result = self._llm_partition(features, target_modules)
                if result is not None and self._validate_result(
                    result, feature_map
                ):
                    logger.info(
                        "LLM partitioning succeeded: %d modules for %d features",
                        result.module_count,
                        len(features),
                    )
                    return result
                logger.warning(
                    "LLM partitioning returned invalid result, "
                    "falling back to k-means"
                )
            except Exception as e:
                logger.warning(
                    "LLM partitioning failed: %s, falling back to k-means", e
                )

        # Fall back to k-means
        result = self._kmeans_partition(features, target_modules)
        logger.info(
            "K-means partitioning: %d modules for %d features",
            result.module_count,
            len(features),
        )
        return result

    # ------------------------------------------------------------------
    # LLM-based partitioning
    # ------------------------------------------------------------------

    def _llm_partition(
        self,
        features: list[FeatureNode],
        target_modules: int | None,
    ) -> PartitionResult | None:
        """Partition features using LLM analysis.

        Args:
            features: Features to partition.
            target_modules: Desired number of modules.

        Returns:
            A PartitionResult, or None if parsing fails.
        """
        prompt = self._build_partition_prompt(features, target_modules)

        model = self._llm.select_model(tier=self._config.llm_tier)
        response = self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            tier=self._config.llm_tier,
        )

        return self._parse_llm_response(response, features)

    def _build_partition_prompt(
        self,
        features: list[FeatureNode],
        target_modules: int | None,
    ) -> str:
        """Build the LLM prompt for module partitioning.

        Args:
            features: Features to include in the prompt.
            target_modules: Desired number of modules.

        Returns:
            The formatted prompt string.
        """
        feature_lines = []
        for f in features:
            desc = f.description or "No description"
            tags = ", ".join(f.tags) if f.tags else "none"
            feature_lines.append(
                f"- ID: {f.id} | Name: {f.name} | Description: {desc} | Tags: {tags}"
            )

        features_text = "\n".join(feature_lines)

        target_hint = ""
        if target_modules is not None:
            target_hint = f"\nTarget number of modules: {target_modules}"
        else:
            target_hint = (
                f"\nTarget {self._config.min_modules}-{self._config.max_modules} "
                f"modules"
            )

        return f"""You are a software architect partitioning features into cohesive modules.

Features:
{features_text}
{target_hint}

Rules:
- Each module must have a descriptive name (NOT "Module 1", "Module 2", etc.)
- Each module must have a clear functional description
- Minimum {self._config.min_features_per_module} features per module, maximum {self._config.max_features_per_module}
- Group by: functional cohesion, data coupling, workflow dependencies
- Every feature must be assigned to exactly one module
- Identify 1-3 features per module as the public interface

Respond with ONLY a JSON object:
{{
  "modules": [
    {{
      "name": "module name",
      "description": "functional purpose",
      "feature_ids": ["id1", "id2"],
      "public_interface": ["id1"],
      "rationale": "why these features belong together"
    }}
  ]
}}"""

    def _parse_llm_response(
        self,
        response: str,
        features: list[FeatureNode],
    ) -> PartitionResult | None:
        """Parse the LLM's JSON response into a PartitionResult.

        Args:
            response: Raw LLM response string.
            features: Original features for validation.

        Returns:
            A PartitionResult, or None if parsing fails.
        """
        try:
            data = self._extract_json(response)
            if data is None or "modules" not in data:
                return None

            modules: list[ModuleSpec] = []
            feature_ids_all = {f.id for f in features}
            assigned: set[str] = set()

            for m_data in data["modules"]:
                name = m_data.get("name", "")
                if not name:
                    continue

                fids = m_data.get("feature_ids", [])
                # Filter to only valid feature IDs
                valid_fids = [fid for fid in fids if fid in feature_ids_all]
                if not valid_fids:
                    continue

                # Remove duplicates while preserving order
                seen: set[str] = set()
                unique_fids: list[str] = []
                for fid in valid_fids:
                    if fid not in seen and fid not in assigned:
                        seen.add(fid)
                        unique_fids.append(fid)

                if not unique_fids:
                    continue

                assigned.update(unique_fids)

                public = m_data.get("public_interface", [])
                valid_public = [p for p in public if p in seen]

                modules.append(
                    ModuleSpec(
                        name=name,
                        description=m_data.get("description", ""),
                        feature_ids=unique_fids,
                        public_interface=valid_public,
                        rationale=m_data.get("rationale", ""),
                    )
                )

            if not modules:
                return None

            unassigned = list(feature_ids_all - assigned)

            return PartitionResult(
                modules=modules,
                unassigned_feature_ids=unassigned,
                method="llm",
                total_features=len(features),
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse LLM response: %s", e)
            return None

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract JSON from LLM response text.

        Handles:
        - Pure JSON responses
        - JSON wrapped in markdown code blocks
        - JSON embedded in surrounding text

        Args:
            text: Raw LLM response.

        Returns:
            Parsed dict, or None if extraction fails.
        """
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code block
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding embedded JSON object
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
    # K-means fallback
    # ------------------------------------------------------------------

    def _kmeans_partition(
        self,
        features: list[FeatureNode],
        target_modules: int | None,
    ) -> PartitionResult:
        """Partition features using k-means clustering on embeddings.

        Falls back to simple round-robin assignment if no embeddings
        are available.

        Args:
            features: Features to partition.
            target_modules: Desired number of modules.

        Returns:
            A PartitionResult.
        """
        # Determine number of clusters
        n = len(features)
        if target_modules is not None:
            k = min(target_modules, n)
        else:
            # Heuristic: sqrt(n/2), clamped to config range
            k = max(
                self._config.min_modules,
                min(
                    int(np.sqrt(n / 2)) + 1,
                    self._config.max_modules,
                    n,
                ),
            )

        # Ensure k doesn't exceed feature count
        k = min(k, n)

        # Collect embeddings
        embeddings = self._collect_embeddings(features)

        if embeddings is not None:
            labels = self._run_kmeans(embeddings, k)
        else:
            # No embeddings: round-robin assignment
            labels = [i % k for i in range(n)]

        # Build modules from cluster labels
        clusters: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            clusters.setdefault(label, []).append(idx)

        modules = self._build_modules_from_clusters(features, clusters)

        # Enforce size constraints
        modules = self._enforce_size_constraints(modules, features)

        return PartitionResult(
            modules=modules,
            unassigned_feature_ids=[],
            method="kmeans" if embeddings is not None else "round_robin",
            total_features=n,
        )

    def _collect_embeddings(
        self, features: list[FeatureNode]
    ) -> np.ndarray | None:
        """Collect embeddings from feature nodes.

        Args:
            features: Features to extract embeddings from.

        Returns:
            numpy array of shape (n, dim), or None if insufficient embeddings.
        """
        embeddings = []
        for f in features:
            if f.embedding is not None and len(f.embedding) > 0:
                embeddings.append(np.array(f.embedding, dtype=np.float64))

        if len(embeddings) < len(features) * 0.5:
            # Less than 50% have embeddings — not reliable
            return None

        if not embeddings:
            return None

        # Pad missing embeddings with zeros
        dim = embeddings[0].shape[0]
        result = []
        for f in features:
            if f.embedding is not None and len(f.embedding) > 0:
                result.append(np.array(f.embedding[:dim], dtype=np.float64))
            else:
                result.append(np.zeros(dim, dtype=np.float64))

        return np.array(result)

    def _run_kmeans(self, embeddings: np.ndarray, k: int) -> list[int]:
        """Run k-means clustering.

        Args:
            embeddings: Feature embeddings array.
            k: Number of clusters.

        Returns:
            List of cluster labels for each feature.
        """
        from sklearn.cluster import KMeans

        kmeans = KMeans(
            n_clusters=k,
            n_init=self._config.kmeans_n_init,
            random_state=42,
        )
        labels = kmeans.fit_predict(embeddings)
        return labels.tolist()

    def _build_modules_from_clusters(
        self,
        features: list[FeatureNode],
        clusters: dict[int, list[int]],
    ) -> list[ModuleSpec]:
        """Build ModuleSpec objects from cluster assignments.

        Generates descriptive names based on feature tags and names.

        Args:
            features: Original features.
            clusters: Mapping from cluster label to feature indices.

        Returns:
            List of ModuleSpec objects.
        """
        modules: list[ModuleSpec] = []

        for cluster_id in sorted(clusters.keys()):
            indices = clusters[cluster_id]
            cluster_features = [features[i] for i in indices]
            feature_ids = [f.id for f in cluster_features]

            # Generate module name from common tags or feature names
            name = self._generate_module_name(cluster_features, cluster_id)
            description = self._generate_module_description(cluster_features)

            # First feature as public interface
            public = [feature_ids[0]] if feature_ids else []

            modules.append(
                ModuleSpec(
                    name=name,
                    description=description,
                    feature_ids=feature_ids,
                    public_interface=public,
                    rationale=f"Clustered by embedding similarity (cluster {cluster_id})",
                )
            )

        return modules

    @staticmethod
    def _generate_module_name(
        features: list[FeatureNode], cluster_id: int
    ) -> str:
        """Generate a descriptive module name from features.

        Uses the most common tag or shared name prefix as the module name.

        Args:
            features: Features in this module.
            cluster_id: Fallback cluster identifier.

        Returns:
            A descriptive module name.
        """
        # Count tag frequency
        tag_counts: dict[str, int] = {}
        for f in features:
            for tag in f.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        if tag_counts:
            # Use most common tag
            best_tag = max(tag_counts, key=tag_counts.get)  # type: ignore
            return best_tag.replace("_", " ").replace("-", " ").title()

        # Try shared name prefix
        names = [f.name for f in features]
        if len(names) >= 2:
            # Find common prefix words
            first_words = [n.split()[0] if n.split() else "" for n in names]
            if len(set(first_words)) == 1 and first_words[0]:
                return first_words[0].title()

        # Use the first feature's parent path if available
        for f in features:
            if "." in f.id:
                parts = f.id.split(".")
                if len(parts) >= 2:
                    return parts[-2].replace("_", " ").replace("-", " ").title()

        return f"Group {cluster_id + 1}"

    @staticmethod
    def _generate_module_description(features: list[FeatureNode]) -> str:
        """Generate a brief description for a module.

        Args:
            features: Features in this module.

        Returns:
            A descriptive string.
        """
        if len(features) <= 3:
            names = [f.name for f in features]
            return f"Module containing: {', '.join(names)}"

        sample = [f.name for f in features[:3]]
        return (
            f"Module containing {len(features)} features "
            f"including: {', '.join(sample)}"
        )

    def _enforce_size_constraints(
        self,
        modules: list[ModuleSpec],
        features: list[FeatureNode],
    ) -> list[ModuleSpec]:
        """Enforce min/max feature count constraints on modules.

        Merges modules that are too small and splits those that are
        too large.

        Args:
            modules: Initial module list.
            features: All features for reference.

        Returns:
            Adjusted module list.
        """
        if not modules:
            return modules

        min_size = self._config.min_features_per_module
        max_size = self._config.max_features_per_module

        # Build mutable copies
        mutable_modules: list[dict[str, Any]] = []
        for m in modules:
            mutable_modules.append({
                "name": m.name,
                "description": m.description,
                "feature_ids": list(m.feature_ids),
                "public_interface": list(m.public_interface),
                "rationale": m.rationale,
            })

        # Merge modules that are too small
        changed = True
        while changed:
            changed = False
            small = [m for m in mutable_modules if len(m["feature_ids"]) < min_size]
            if not small:
                break

            for s in small:
                if len(mutable_modules) <= self._config.min_modules:
                    break

                # Find smallest non-small module to merge into
                candidates = [
                    m for m in mutable_modules
                    if m is not s
                    and len(m["feature_ids"]) + len(s["feature_ids"]) <= max_size
                ]
                if candidates:
                    target = min(candidates, key=lambda x: len(x["feature_ids"]))
                    target["feature_ids"].extend(s["feature_ids"])
                    target["description"] = self._generate_module_description(
                        [f for f in features if f.id in target["feature_ids"]]
                    )
                    mutable_modules.remove(s)
                    changed = True
                    break

        # Split modules that are too large
        new_modules: list[dict[str, Any]] = []
        for m in mutable_modules:
            if len(m["feature_ids"]) > max_size:
                # Split into chunks
                fids = m["feature_ids"]
                chunk_size = max_size
                for i in range(0, len(fids), chunk_size):
                    chunk = fids[i : i + chunk_size]
                    suffix = f" (Part {i // chunk_size + 1})" if i > 0 else ""
                    new_modules.append({
                        "name": m["name"] + suffix,
                        "description": self._generate_module_description(
                            [f for f in features if f.id in chunk]
                        ),
                        "feature_ids": chunk,
                        "public_interface": [chunk[0]] if chunk else [],
                        "rationale": m["rationale"],
                    })
            else:
                new_modules.append(m)

        # Convert back to ModuleSpec
        result: list[ModuleSpec] = []
        for m in new_modules:
            result.append(
                ModuleSpec(
                    name=m["name"],
                    description=m["description"],
                    feature_ids=m["feature_ids"],
                    public_interface=m["public_interface"],
                    rationale=m["rationale"],
                )
            )

        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_result(
        self,
        result: PartitionResult,
        feature_map: dict[str, FeatureNode],
    ) -> bool:
        """Validate a partition result against constraints.

        Args:
            result: The result to validate.
            feature_map: All features by ID.

        Returns:
            True if the result satisfies all constraints.
        """
        # Must have at least 1 module
        if result.module_count == 0:
            return False

        # Check module count bounds
        if result.module_count < self._config.min_modules:
            logger.debug(
                "Too few modules: %d < %d",
                result.module_count,
                self._config.min_modules,
            )
            return False

        if result.module_count > self._config.max_modules:
            logger.debug(
                "Too many modules: %d > %d",
                result.module_count,
                self._config.max_modules,
            )
            return False

        # Check feature assignment completeness
        all_assigned = result.all_feature_ids
        all_expected = set(feature_map.keys())
        missing = all_expected - all_assigned
        if missing:
            logger.debug(
                "Missing feature assignments: %d features unassigned",
                len(missing),
            )
            # Allow if at least 80% assigned
            if len(missing) > len(all_expected) * 0.2:
                return False

        # Check module sizes
        for m in result.modules:
            if m.feature_count < self._config.min_features_per_module:
                logger.debug(
                    "Module '%s' too small: %d features",
                    m.name,
                    m.feature_count,
                )
                return False
            if m.feature_count > self._config.max_features_per_module:
                logger.debug(
                    "Module '%s' too large: %d features",
                    m.name,
                    m.feature_count,
                )
                return False

        # Check for duplicate assignments
        seen: set[str] = set()
        for m in result.modules:
            for fid in m.feature_ids:
                if fid in seen:
                    logger.debug("Duplicate feature assignment: %s", fid)
                    return False
                seen.add(fid)

        # Check module names are descriptive
        for m in result.modules:
            name_lower = m.name.lower().strip()
            if re.match(r"^module\s*\d+$", name_lower):
                logger.debug("Non-descriptive module name: '%s'", m.name)
                return False

        return True
