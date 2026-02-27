"""Ontology builder that orchestrates seed generators and exports CSV.

Combines output from all seed generators, deduplicates nodes, validates
the hierarchy (no orphans, correct parent references), and exports to
CSV format.

Implements Task 2.1.2 of PRD-RPG-P2-001.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Optional

from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.ontology.scrapers.base import SeedGenerator
from cobuilder.repomap.ontology.scrapers.expander import TaxonomyExpander
from cobuilder.repomap.ontology.scrapers.github_topics import GitHubTopicsGenerator
from cobuilder.repomap.ontology.scrapers.library_docs import LibraryDocsGenerator
from cobuilder.repomap.ontology.scrapers.stackoverflow_tags import StackOverflowTagsGenerator

logger = logging.getLogger(__name__)

# CSV columns as specified by the PRD
CSV_COLUMNS = ["feature_id", "parent_id", "name", "description", "tags", "level"]


class OntologyBuilder:
    """Orchestrates seed generators, deduplicates, validates, and exports.

    The builder aggregates nodes from all registered generators, checks
    for ID collisions, validates that all parent references resolve, and
    exports the result to CSV.

    Example usage::

        builder = OntologyBuilder()
        builder.add_generator(GitHubTopicsGenerator())
        builder.add_generator(StackOverflowTagsGenerator())
        nodes = builder.build()
        builder.export_csv(Path("ontology.csv"))
    """

    def __init__(self) -> None:
        self._generators: list[SeedGenerator] = []
        self._nodes: list[FeatureNode] = []
        self._node_index: dict[str, FeatureNode] = {}
        self._built = False

    @property
    def generators(self) -> list[SeedGenerator]:
        """Return the list of registered generators."""
        return list(self._generators)

    @property
    def nodes(self) -> list[FeatureNode]:
        """Return the built list of nodes. Must call :meth:`build` first."""
        if not self._built:
            raise RuntimeError(
                "Must call build() before accessing nodes. "
                "No generators have been run yet."
            )
        return list(self._nodes)

    @property
    def node_count(self) -> int:
        """Return the count of built nodes."""
        return len(self._nodes)

    def add_generator(self, generator: SeedGenerator) -> OntologyBuilder:
        """Register a seed generator.

        Args:
            generator: A :class:`SeedGenerator` instance.

        Returns:
            Self for method chaining.

        Raises:
            TypeError: If generator is not a SeedGenerator subclass.
        """
        if not isinstance(generator, SeedGenerator):
            raise TypeError(
                f"Expected SeedGenerator, got {type(generator).__name__}"
            )
        self._generators.append(generator)
        return self

    def build(self) -> list[FeatureNode]:
        """Run all generators, deduplicate, and validate the hierarchy.

        Returns:
            List of all unique :class:`FeatureNode` instances.

        Raises:
            ValueError: If validation fails (orphan nodes, duplicate IDs
                with conflicting data, etc.).
        """
        self._nodes = []
        self._node_index = {}
        duplicates_skipped = 0

        for gen in self._generators:
            logger.info(
                "Running generator '%s' (prefix: %s)",
                gen.name,
                gen.source_prefix,
            )
            gen_nodes = gen.generate()
            logger.info(
                "Generator '%s' produced %d nodes",
                gen.name,
                len(gen_nodes),
            )

            for node in gen_nodes:
                if node.id in self._node_index:
                    duplicates_skipped += 1
                    logger.debug(
                        "Skipping duplicate node ID '%s' from '%s'",
                        node.id,
                        gen.name,
                    )
                    continue
                self._node_index[node.id] = node
                self._nodes.append(node)

        logger.info(
            "Total nodes: %d (skipped %d duplicates)",
            len(self._nodes),
            duplicates_skipped,
        )

        # Validate hierarchy
        self._validate()
        self._built = True
        return list(self._nodes)

    def _validate(self) -> None:
        """Validate the node hierarchy for integrity.

        Checks:
        - All parent_id references point to existing nodes
        - No self-referencing nodes
        - At least one root node exists

        Raises:
            ValueError: If validation fails.
        """
        root_count = 0
        orphans: list[str] = []

        for node in self._nodes:
            if node.parent_id is None:
                root_count += 1
            else:
                if node.parent_id not in self._node_index:
                    orphans.append(
                        f"Node '{node.id}' references non-existent "
                        f"parent '{node.parent_id}'"
                    )
                if node.parent_id == node.id:
                    orphans.append(
                        f"Node '{node.id}' references itself as parent"
                    )

        if orphans:
            raise ValueError(
                f"Hierarchy validation failed with {len(orphans)} "
                f"orphan(s):\n" + "\n".join(orphans[:10])
            )

        if root_count == 0:
            raise ValueError("No root nodes found (all nodes have parents)")

        logger.info(
            "Validation passed: %d root(s), %d total nodes, 0 orphans",
            root_count,
            len(self._nodes),
        )

    def get_depth_stats(self) -> dict[int, int]:
        """Return node count per level.

        Returns:
            Dict mapping level number to count of nodes at that level.
        """
        stats: dict[int, int] = {}
        for node in self._nodes:
            stats[node.level] = stats.get(node.level, 0) + 1
        return dict(sorted(stats.items()))

    def get_max_depth(self) -> int:
        """Return the maximum hierarchical depth across all nodes."""
        if not self._nodes:
            return 0
        return max(node.level for node in self._nodes)

    def get_source_stats(self) -> dict[str, int]:
        """Return node count per source/generator.

        Returns:
            Dict mapping source name to count of nodes from that source.
        """
        stats: dict[str, int] = {}
        for node in self._nodes:
            source = node.metadata.get("source", "unknown")
            stats[source] = stats.get(source, 0) + 1
        return dict(sorted(stats.items()))

    def export_csv(self, output_path: Optional[Path] = None) -> str:
        """Export the ontology to CSV format.

        Columns: ``feature_id,parent_id,name,description,tags,level``

        Args:
            output_path: If provided, writes the CSV to this file path.
                If None, only returns the CSV string.

        Returns:
            The CSV content as a string.

        Raises:
            RuntimeError: If :meth:`build` has not been called yet.
        """
        if not self._built:
            raise RuntimeError("Must call build() before exporting")

        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()

        for node in self._nodes:
            writer.writerow(
                {
                    "feature_id": node.id,
                    "parent_id": node.parent_id or "",
                    "name": node.name,
                    "description": node.description or "",
                    "tags": "|".join(node.tags),
                    "level": node.level,
                }
            )

        csv_content = output.getvalue()

        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(csv_content, encoding="utf-8")
            logger.info("Exported %d nodes to %s", len(self._nodes), output_path)

        return csv_content

    def find_node(self, node_id: str) -> Optional[FeatureNode]:
        """Look up a node by its ID.

        Args:
            node_id: The unique ID to search for.

        Returns:
            The :class:`FeatureNode` if found, else None.
        """
        return self._node_index.get(node_id)

    def get_children(self, node_id: str) -> list[FeatureNode]:
        """Return direct children of a given node.

        Args:
            node_id: The parent node's ID.

        Returns:
            List of child nodes.
        """
        return [n for n in self._nodes if n.parent_id == node_id]

    def get_roots(self) -> list[FeatureNode]:
        """Return all root nodes (nodes with no parent)."""
        return [n for n in self._nodes if n.parent_id is None]


def build_ontology(
    output_path: Optional[Path] = None,
    include_github: bool = True,
    include_stackoverflow: bool = True,
    include_libraries: bool = True,
    include_expander: bool = True,
    target_count: int = 50000,
) -> OntologyBuilder:
    """Convenience function to build the full ontology with all generators.

    Args:
        output_path: Optional CSV file path to export to.
        include_github: Whether to include GitHub Topics generator.
        include_stackoverflow: Whether to include SO Tags generator.
        include_libraries: Whether to include Library Docs generator.
        include_expander: Whether to include the combinatorial expander
            (needed to reach 50K+ target).
        target_count: Target node count for the expander. Only used
            when ``include_expander`` is True.

    Returns:
        The built :class:`OntologyBuilder` instance with all nodes.

    Example::

        builder = build_ontology(Path("output/ontology.csv"))
        print(f"Generated {builder.node_count} nodes")
        print(f"Depth stats: {builder.get_depth_stats()}")
    """
    builder = OntologyBuilder()

    if include_github:
        builder.add_generator(GitHubTopicsGenerator())
    if include_stackoverflow:
        builder.add_generator(StackOverflowTagsGenerator())
    if include_libraries:
        builder.add_generator(LibraryDocsGenerator())
    if include_expander:
        builder.add_generator(TaxonomyExpander(target_count=target_count))

    builder.build()

    if output_path is not None:
        builder.export_csv(output_path)

    return builder
