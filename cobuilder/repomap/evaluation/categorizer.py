"""Hierarchical categorization and stratified sampling for benchmark tasks.

Provides two core capabilities:

1. **Taxonomy construction** -- groups :class:`BenchmarkTask` instances by
   their dotted category path and builds a :class:`Taxonomy` tree.
2. **Stratified sampling** -- draws a representative subset of tasks that
   preserves category proportions while guaranteeing at least one task per
   category when possible.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Any

from cobuilder.repomap.evaluation.models import BenchmarkTask, Taxonomy, TaxonomyNode

logger = logging.getLogger(__name__)


class Categorizer:
    """Builds hierarchical taxonomy and performs stratified sampling."""

    # ------------------------------------------------------------------
    # Taxonomy construction
    # ------------------------------------------------------------------

    def build_taxonomy(self, tasks: list[BenchmarkTask]) -> Taxonomy:
        """Build a hierarchical :class:`Taxonomy` from *tasks*.

        Groups tasks by their dotted ``category`` field (e.g.
        ``sklearn.linear_model.ridge``) and builds a tree structure with
        per-node counts.

        Args:
            tasks: Benchmark tasks to categorise.

        Returns:
            A :class:`Taxonomy` instance containing the tree of nodes.
        """
        roots: dict[str, TaxonomyNode] = {}
        categories: set[str] = set()

        for task in tasks:
            parts = task.category.split(".")
            if not parts:
                continue

            categories.add(task.category)

            # Ensure the root node exists.
            root_name = parts[0]
            if root_name not in roots:
                roots[root_name] = TaxonomyNode(name=root_name)

            # Walk the path, creating nodes as needed.
            current = roots[root_name]
            current.count += 1

            for part in parts[1:]:
                if part not in current.children:
                    current.children[part] = TaxonomyNode(name=part)
                current = current.children[part]
                current.count += 1

        return Taxonomy(
            roots=roots,
            total_tasks=len(tasks),
            total_categories=len(categories),
        )

    # ------------------------------------------------------------------
    # Stratified sampling
    # ------------------------------------------------------------------

    def stratified_sample(
        self,
        tasks: list[BenchmarkTask],
        n: int,
        seed: int | None = None,
    ) -> list[BenchmarkTask]:
        """Draw *n* tasks proportionally across categories.

        Each category receives at least one representative (when
        possible).  Remaining slots are distributed proportionally to
        category size using weighted random sampling without replacement.

        Args:
            tasks: The full pool of benchmark tasks.
            n: Desired sample size.
            seed: Optional RNG seed for reproducibility.

        Returns:
            A list of at most *n* :class:`BenchmarkTask` instances.
        """
        if n >= len(tasks):
            return list(tasks)

        rng = random.Random(seed)

        # Group tasks by category.
        by_category: dict[str, list[BenchmarkTask]] = defaultdict(list)
        for task in tasks:
            by_category[task.category].append(task)

        categories = list(by_category.keys())
        num_categories = len(categories)

        if n < num_categories:
            # Not enough slots for every category -- pick *n* random
            # categories and draw one task from each.
            selected_cats = rng.sample(categories, n)
            return [rng.choice(by_category[cat]) for cat in selected_cats]

        # ------------------------------------------------------------------
        # Guarantee at least one task per category.
        # ------------------------------------------------------------------
        sampled: list[BenchmarkTask] = []
        remaining_by_cat: dict[str, list[BenchmarkTask]] = {}

        for cat in categories:
            cat_tasks = by_category[cat]
            chosen = rng.choice(cat_tasks)
            sampled.append(chosen)
            remaining = [t for t in cat_tasks if t.id != chosen.id]
            if remaining:
                remaining_by_cat[cat] = remaining

        # ------------------------------------------------------------------
        # Distribute remaining slots proportionally.
        # ------------------------------------------------------------------
        remaining_n = n - len(sampled)
        if remaining_n > 0 and remaining_by_cat:
            total_remaining = sum(len(v) for v in remaining_by_cat.values())

            all_remaining: list[BenchmarkTask] = []
            weights: list[float] = []
            for cat, cat_tasks in remaining_by_cat.items():
                for task in cat_tasks:
                    all_remaining.append(task)
                    weights.append(len(by_category[cat]) / total_remaining)

            # Weighted sampling without replacement.
            if remaining_n >= len(all_remaining):
                sampled.extend(all_remaining)
            else:
                indices = list(range(len(all_remaining)))
                chosen_indices: list[int] = []
                for _ in range(remaining_n):
                    if not indices:
                        break
                    total_w = sum(weights[i] for i in indices)
                    if total_w == 0:
                        break
                    r = rng.random() * total_w
                    cumsum = 0.0
                    for idx in indices:
                        cumsum += weights[idx]
                        if cumsum >= r:
                            chosen_indices.append(idx)
                            indices.remove(idx)
                            break

                sampled.extend(all_remaining[i] for i in chosen_indices)

        return sampled
