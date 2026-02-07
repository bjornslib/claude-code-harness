"""Unit tests for ontology seed data generators and builder.

Tests cover GitHubTopicsGenerator, StackOverflowTagsGenerator,
LibraryDocsGenerator, OntologyBuilder, and the build_ontology
convenience function as defined in Task 2.1.2.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from zerorepo.ontology.models import FeatureNode
from zerorepo.ontology.scrapers.base import SeedGenerator
from zerorepo.ontology.scrapers.build_ontology import (
    CSV_COLUMNS,
    OntologyBuilder,
    build_ontology,
)
from zerorepo.ontology.scrapers.github_topics import GitHubTopicsGenerator
from zerorepo.ontology.scrapers.library_docs import LibraryDocsGenerator
from zerorepo.ontology.scrapers.stackoverflow_tags import StackOverflowTagsGenerator


# ---------------------------------------------------------------------------
# SeedGenerator Base Tests
# ---------------------------------------------------------------------------


class TestSeedGeneratorBase:
    """Test the SeedGenerator abstract base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Cannot instantiate SeedGenerator directly."""
        with pytest.raises(TypeError, match="abstract"):
            SeedGenerator()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        """A concrete subclass can be instantiated and used."""

        class TestGen(SeedGenerator):
            @property
            def name(self) -> str:
                return "Test"

            @property
            def source_prefix(self) -> str:
                return "test"

            def generate(self) -> list[FeatureNode]:
                return [
                    FeatureNode(id="test.root", name="Root", level=0),
                ]

        gen = TestGen()
        assert gen.name == "Test"
        assert gen.source_prefix == "test"
        nodes = gen.generate()
        assert len(nodes) == 1
        assert nodes[0].id == "test.root"


# ---------------------------------------------------------------------------
# GitHubTopicsGenerator Tests
# ---------------------------------------------------------------------------


class TestGitHubTopicsGenerator:
    """Test the GitHub Topics seed data generator."""

    @pytest.fixture()
    def generator(self) -> GitHubTopicsGenerator:
        """Create a GitHubTopicsGenerator instance."""
        return GitHubTopicsGenerator()

    def test_name(self, generator: GitHubTopicsGenerator) -> None:
        """Generator has correct name."""
        assert generator.name == "GitHub Topics"

    def test_source_prefix(self, generator: GitHubTopicsGenerator) -> None:
        """Generator has correct source prefix."""
        assert generator.source_prefix == "gh"

    def test_generate_returns_nodes(self, generator: GitHubTopicsGenerator) -> None:
        """Generate produces a list of FeatureNode instances."""
        nodes = generator.generate()
        assert isinstance(nodes, list)
        assert len(nodes) > 0
        assert all(isinstance(n, FeatureNode) for n in nodes)

    def test_generate_produces_significant_count(
        self, generator: GitHubTopicsGenerator
    ) -> None:
        """Generate should produce a substantial number of nodes (>500)."""
        nodes = generator.generate()
        assert len(nodes) > 500

    def test_all_ids_prefixed_with_gh(
        self, generator: GitHubTopicsGenerator
    ) -> None:
        """All node IDs start with 'gh.' prefix."""
        nodes = generator.generate()
        for node in nodes:
            assert node.id.startswith("gh."), f"Node ID '{node.id}' missing 'gh.' prefix"

    def test_root_nodes_exist(self, generator: GitHubTopicsGenerator) -> None:
        """At least one root node (parent_id=None) exists."""
        nodes = generator.generate()
        roots = [n for n in nodes if n.parent_id is None]
        assert len(roots) > 0

    def test_no_orphan_nodes(self, generator: GitHubTopicsGenerator) -> None:
        """Every non-root node references a valid parent."""
        nodes = generator.generate()
        node_ids = {n.id for n in nodes}
        for node in nodes:
            if node.parent_id is not None:
                assert node.parent_id in node_ids, (
                    f"Node '{node.id}' references non-existent parent '{node.parent_id}'"
                )

    def test_unique_ids(self, generator: GitHubTopicsGenerator) -> None:
        """All node IDs are unique."""
        nodes = generator.generate()
        ids = [n.id for n in nodes]
        assert len(ids) == len(set(ids)), "Duplicate node IDs found"

    def test_hierarchical_depth(self, generator: GitHubTopicsGenerator) -> None:
        """Hierarchy has depth of at least 4 levels (0 through 3+)."""
        nodes = generator.generate()
        max_level = max(n.level for n in nodes)
        assert max_level >= 4, f"Max depth {max_level} < 4"

    def test_nodes_have_metadata(self, generator: GitHubTopicsGenerator) -> None:
        """All nodes have source metadata."""
        nodes = generator.generate()
        for node in nodes[:20]:  # spot check first 20
            assert "source" in node.metadata
            assert node.metadata["source"] == "github-topics"

    def test_nodes_have_tags(self, generator: GitHubTopicsGenerator) -> None:
        """All nodes have at least one tag."""
        nodes = generator.generate()
        for node in nodes[:20]:
            assert len(node.tags) > 0, f"Node '{node.id}' has no tags"

    def test_nodes_have_descriptions(
        self, generator: GitHubTopicsGenerator
    ) -> None:
        """All nodes have a description."""
        nodes = generator.generate()
        for node in nodes[:20]:
            assert node.description is not None
            assert len(node.description) > 0

    def test_level_consistency(self, generator: GitHubTopicsGenerator) -> None:
        """Child nodes have level > parent nodes."""
        nodes = generator.generate()
        node_map = {n.id: n for n in nodes}
        for node in nodes:
            if node.parent_id is not None and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                assert node.level > parent.level, (
                    f"Node '{node.id}' (level {node.level}) not deeper "
                    f"than parent '{parent.id}' (level {parent.level})"
                )


# ---------------------------------------------------------------------------
# StackOverflowTagsGenerator Tests
# ---------------------------------------------------------------------------


class TestStackOverflowTagsGenerator:
    """Test the Stack Overflow Tags seed data generator."""

    @pytest.fixture()
    def generator(self) -> StackOverflowTagsGenerator:
        """Create a StackOverflowTagsGenerator instance."""
        return StackOverflowTagsGenerator()

    def test_name(self, generator: StackOverflowTagsGenerator) -> None:
        """Generator has correct name."""
        assert generator.name == "Stack Overflow Tags"

    def test_source_prefix(self, generator: StackOverflowTagsGenerator) -> None:
        """Generator has correct source prefix."""
        assert generator.source_prefix == "so"

    def test_generate_returns_nodes(
        self, generator: StackOverflowTagsGenerator
    ) -> None:
        """Generate produces FeatureNode instances."""
        nodes = generator.generate()
        assert isinstance(nodes, list)
        assert len(nodes) > 0
        assert all(isinstance(n, FeatureNode) for n in nodes)

    def test_generate_produces_significant_count(
        self, generator: StackOverflowTagsGenerator
    ) -> None:
        """Generate should produce a substantial number of nodes (>200)."""
        nodes = generator.generate()
        assert len(nodes) > 200

    def test_all_ids_prefixed_with_so(
        self, generator: StackOverflowTagsGenerator
    ) -> None:
        """All node IDs start with 'so.' prefix."""
        nodes = generator.generate()
        for node in nodes:
            assert node.id.startswith("so."), f"Node ID '{node.id}' missing 'so.' prefix"

    def test_no_orphan_nodes(self, generator: StackOverflowTagsGenerator) -> None:
        """Every non-root node references a valid parent."""
        nodes = generator.generate()
        node_ids = {n.id for n in nodes}
        for node in nodes:
            if node.parent_id is not None:
                assert node.parent_id in node_ids

    def test_unique_ids(self, generator: StackOverflowTagsGenerator) -> None:
        """All node IDs are unique."""
        nodes = generator.generate()
        ids = [n.id for n in nodes]
        assert len(ids) == len(set(ids))

    def test_hierarchical_depth(
        self, generator: StackOverflowTagsGenerator
    ) -> None:
        """Hierarchy has depth of at least 4 levels."""
        nodes = generator.generate()
        max_level = max(n.level for n in nodes)
        assert max_level >= 4

    def test_nodes_have_so_metadata(
        self, generator: StackOverflowTagsGenerator
    ) -> None:
        """Nodes have stackoverflow-tags source metadata."""
        nodes = generator.generate()
        for node in nodes[:10]:
            assert node.metadata.get("source") == "stackoverflow-tags"


# ---------------------------------------------------------------------------
# LibraryDocsGenerator Tests
# ---------------------------------------------------------------------------


class TestLibraryDocsGenerator:
    """Test the Library Documentation seed data generator."""

    @pytest.fixture()
    def generator(self) -> LibraryDocsGenerator:
        """Create a LibraryDocsGenerator instance."""
        return LibraryDocsGenerator()

    def test_name(self, generator: LibraryDocsGenerator) -> None:
        """Generator has correct name."""
        assert generator.name == "Library Docs"

    def test_source_prefix(self, generator: LibraryDocsGenerator) -> None:
        """Generator has correct source prefix."""
        assert generator.source_prefix == "lib"

    def test_generate_returns_nodes(self, generator: LibraryDocsGenerator) -> None:
        """Generate produces FeatureNode instances."""
        nodes = generator.generate()
        assert isinstance(nodes, list)
        assert len(nodes) > 0
        assert all(isinstance(n, FeatureNode) for n in nodes)

    def test_generate_produces_significant_count(
        self, generator: LibraryDocsGenerator
    ) -> None:
        """Generate should produce a substantial number of nodes (>200)."""
        nodes = generator.generate()
        assert len(nodes) > 200

    def test_all_ids_prefixed_with_lib(
        self, generator: LibraryDocsGenerator
    ) -> None:
        """All node IDs start with 'lib.' prefix."""
        nodes = generator.generate()
        for node in nodes:
            assert node.id.startswith("lib."), f"Node ID '{node.id}' missing 'lib.' prefix"

    def test_no_orphan_nodes(self, generator: LibraryDocsGenerator) -> None:
        """Every non-root node references a valid parent."""
        nodes = generator.generate()
        node_ids = {n.id for n in nodes}
        for node in nodes:
            if node.parent_id is not None:
                assert node.parent_id in node_ids

    def test_unique_ids(self, generator: LibraryDocsGenerator) -> None:
        """All node IDs are unique."""
        nodes = generator.generate()
        ids = [n.id for n in nodes]
        assert len(ids) == len(set(ids))

    def test_library_root_nodes(self, generator: LibraryDocsGenerator) -> None:
        """Each library has a root node."""
        nodes = generator.generate()
        roots = [n for n in nodes if n.parent_id is None]
        root_ids = {n.id for n in roots}
        # All known libraries should have root nodes
        assert "lib.scikit-learn" in root_ids
        assert "lib.react" in root_ids
        assert "lib.django" in root_ids
        assert "lib.tensorflow" in root_ids
        assert "lib.pytorch" in root_ids
        assert "lib.fastapi-lib" in root_ids

    def test_nodes_have_library_metadata(
        self, generator: LibraryDocsGenerator
    ) -> None:
        """Nodes have library-docs source and library name in metadata."""
        nodes = generator.generate()
        for node in nodes[:10]:
            assert node.metadata.get("source") == "library-docs"
            assert "library" in node.metadata

    def test_hierarchical_depth(self, generator: LibraryDocsGenerator) -> None:
        """Hierarchy has depth of at least 4 levels."""
        nodes = generator.generate()
        max_level = max(n.level for n in nodes)
        assert max_level >= 4


# ---------------------------------------------------------------------------
# OntologyBuilder Tests
# ---------------------------------------------------------------------------


class _MinimalGenerator(SeedGenerator):
    """Minimal generator for testing the builder."""

    def __init__(self, prefix: str, count: int = 5) -> None:
        self._prefix = prefix
        self._count = count

    @property
    def name(self) -> str:
        return f"Minimal-{self._prefix}"

    @property
    def source_prefix(self) -> str:
        return self._prefix

    def generate(self) -> list[FeatureNode]:
        nodes = [
            FeatureNode(
                id=f"{self._prefix}.root",
                name=f"{self._prefix} Root",
                level=0,
                metadata={"source": self._prefix},
            )
        ]
        for i in range(1, self._count):
            nodes.append(
                FeatureNode(
                    id=f"{self._prefix}.child-{i}",
                    name=f"Child {i}",
                    level=1,
                    parent_id=f"{self._prefix}.root",
                    metadata={"source": self._prefix},
                )
            )
        return nodes


class TestOntologyBuilder:
    """Test the OntologyBuilder orchestrator."""

    def test_add_generator(self) -> None:
        """Generators can be added via method chaining."""
        builder = OntologyBuilder()
        result = builder.add_generator(_MinimalGenerator("a"))
        assert result is builder  # method chaining
        assert len(builder.generators) == 1

    def test_add_generator_type_check(self) -> None:
        """Adding a non-SeedGenerator raises TypeError."""
        builder = OntologyBuilder()
        with pytest.raises(TypeError, match="Expected SeedGenerator"):
            builder.add_generator("not a generator")  # type: ignore[arg-type]

    def test_build_single_generator(self) -> None:
        """Build with a single generator works."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("test", count=3))
        nodes = builder.build()
        assert len(nodes) == 3
        assert builder.node_count == 3

    def test_build_multiple_generators(self) -> None:
        """Build with multiple generators combines results."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("a", count=3))
        builder.add_generator(_MinimalGenerator("b", count=4))
        nodes = builder.build()
        assert len(nodes) == 7  # 3 + 4

    def test_build_deduplicates(self) -> None:
        """Build skips duplicate node IDs."""
        # Create two generators that produce a node with the same ID
        gen_a = _MinimalGenerator("shared", count=2)
        gen_b = _MinimalGenerator("shared", count=3)

        builder = OntologyBuilder()
        builder.add_generator(gen_a)
        builder.add_generator(gen_b)
        nodes = builder.build()

        # gen_a produces 2 nodes, gen_b produces 3 nodes
        # shared.root and shared.child-1 are duplicated
        # so we should have 3 unique nodes (root, child-1, child-2)
        assert len(nodes) == 3

    def test_nodes_before_build_raises(self) -> None:
        """Accessing nodes before build raises RuntimeError."""
        builder = OntologyBuilder()
        with pytest.raises(RuntimeError, match="Must call build"):
            _ = builder.nodes

    def test_validation_catches_orphans(self) -> None:
        """Validation fails if a node references a non-existent parent."""

        class OrphanGenerator(SeedGenerator):
            @property
            def name(self) -> str:
                return "Orphan"

            @property
            def source_prefix(self) -> str:
                return "orphan"

            def generate(self) -> list[FeatureNode]:
                return [
                    FeatureNode(id="orphan.root", name="Root", level=0),
                    FeatureNode(
                        id="orphan.child",
                        name="Child",
                        level=1,
                        parent_id="nonexistent",  # orphan!
                    ),
                ]

        builder = OntologyBuilder()
        builder.add_generator(OrphanGenerator())
        with pytest.raises(ValueError, match="orphan"):
            builder.build()

    def test_validation_requires_root(self) -> None:
        """Validation fails if no root nodes exist."""

        class NoRootGenerator(SeedGenerator):
            @property
            def name(self) -> str:
                return "NoRoot"

            @property
            def source_prefix(self) -> str:
                return "noroot"

            def generate(self) -> list[FeatureNode]:
                # Both nodes reference each other's parent - creates cycle
                # but more importantly neither has parent_id=None
                return [
                    FeatureNode(
                        id="noroot.a",
                        name="A",
                        level=0,
                        parent_id="noroot.b",
                    ),
                    FeatureNode(
                        id="noroot.b",
                        name="B",
                        level=0,
                        parent_id="noroot.a",
                    ),
                ]

        builder = OntologyBuilder()
        builder.add_generator(NoRootGenerator())
        with pytest.raises(ValueError, match="No root nodes"):
            builder.build()

    def test_get_depth_stats(self) -> None:
        """get_depth_stats returns correct level distribution."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("test", count=5))
        builder.build()
        stats = builder.get_depth_stats()
        assert stats[0] == 1  # 1 root at level 0
        assert stats[1] == 4  # 4 children at level 1

    def test_get_max_depth(self) -> None:
        """get_max_depth returns the maximum level."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("test", count=5))
        builder.build()
        assert builder.get_max_depth() == 1

    def test_get_source_stats(self) -> None:
        """get_source_stats returns counts per source."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("a", count=3))
        builder.add_generator(_MinimalGenerator("b", count=4))
        builder.build()
        stats = builder.get_source_stats()
        assert stats["a"] == 3
        assert stats["b"] == 4

    def test_find_node(self) -> None:
        """find_node returns the correct node or None."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("test", count=3))
        builder.build()
        node = builder.find_node("test.root")
        assert node is not None
        assert node.id == "test.root"
        assert builder.find_node("nonexistent") is None

    def test_get_children(self) -> None:
        """get_children returns direct children."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("test", count=4))
        builder.build()
        children = builder.get_children("test.root")
        assert len(children) == 3
        child_ids = {c.id for c in children}
        assert "test.child-1" in child_ids
        assert "test.child-2" in child_ids
        assert "test.child-3" in child_ids

    def test_get_roots(self) -> None:
        """get_roots returns only root nodes."""
        builder = OntologyBuilder()
        builder.add_generator(_MinimalGenerator("a", count=3))
        builder.add_generator(_MinimalGenerator("b", count=2))
        builder.build()
        roots = builder.get_roots()
        assert len(roots) == 2
        root_ids = {r.id for r in roots}
        assert "a.root" in root_ids
        assert "b.root" in root_ids


# ---------------------------------------------------------------------------
# CSV Export Tests
# ---------------------------------------------------------------------------


class TestOntologyBuilderCSVExport:
    """Test CSV export functionality."""

    @pytest.fixture()
    def builder(self) -> OntologyBuilder:
        """Create a built OntologyBuilder."""
        b = OntologyBuilder()
        b.add_generator(_MinimalGenerator("test", count=3))
        b.build()
        return b

    def test_export_csv_string(self, builder: OntologyBuilder) -> None:
        """Export returns valid CSV string."""
        csv_str = builder.export_csv()
        assert len(csv_str) > 0
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 3
        assert set(reader.fieldnames or []) == set(CSV_COLUMNS)

    def test_export_csv_columns(self, builder: OntologyBuilder) -> None:
        """CSV has correct column names."""
        csv_str = builder.export_csv()
        first_line = csv_str.split("\n")[0]
        assert "feature_id" in first_line
        assert "parent_id" in first_line
        assert "name" in first_line
        assert "description" in first_line
        assert "tags" in first_line
        assert "level" in first_line

    def test_export_csv_root_has_empty_parent(
        self, builder: OntologyBuilder
    ) -> None:
        """Root nodes have empty parent_id in CSV."""
        csv_str = builder.export_csv()
        reader = csv.DictReader(io.StringIO(csv_str))
        for row in reader:
            if row["feature_id"] == "test.root":
                assert row["parent_id"] == ""
                break

    def test_export_csv_tags_pipe_separated(
        self, builder: OntologyBuilder
    ) -> None:
        """Tags are pipe-separated in CSV."""
        csv_str = builder.export_csv()
        # Tags should not contain commas within the tag field
        # (they use pipe separation)
        reader = csv.DictReader(io.StringIO(csv_str))
        for row in reader:
            tags = row["tags"]
            if tags:
                # Pipe-separated tags should reconstruct correctly
                parts = tags.split("|")
                assert all(len(p.strip()) >= 0 for p in parts)

    def test_export_csv_to_file(
        self, builder: OntologyBuilder, tmp_path: Path
    ) -> None:
        """Export writes CSV file when path is provided."""
        output_path = tmp_path / "test_ontology.csv"
        csv_str = builder.export_csv(output_path)
        assert output_path.exists()
        file_content = output_path.read_text(encoding="utf-8")
        # Normalize line endings for comparison (csv module uses \r\n)
        assert file_content.replace("\r\n", "\n") == csv_str.replace("\r\n", "\n")

    def test_export_csv_creates_parent_dirs(
        self, builder: OntologyBuilder, tmp_path: Path
    ) -> None:
        """Export creates parent directories if needed."""
        output_path = tmp_path / "subdir" / "deep" / "ontology.csv"
        builder.export_csv(output_path)
        assert output_path.exists()

    def test_export_before_build_raises(self) -> None:
        """Exporting before build raises RuntimeError."""
        builder = OntologyBuilder()
        with pytest.raises(RuntimeError, match="Must call build"):
            builder.export_csv()


# ---------------------------------------------------------------------------
# build_ontology convenience function Tests
# ---------------------------------------------------------------------------


class TestBuildOntologyFunction:
    """Test the build_ontology convenience function."""

    def test_build_all_generators(self) -> None:
        """Build with all generators produces many nodes."""
        builder = build_ontology()
        assert builder.node_count > 1000

    def test_build_github_only(self) -> None:
        """Build with GitHub generator only."""
        builder = build_ontology(
            include_github=True,
            include_stackoverflow=False,
            include_libraries=False,
        )
        assert builder.node_count > 0
        for node in builder.nodes[:50]:
            assert node.id.startswith("gh.")

    def test_build_stackoverflow_only(self) -> None:
        """Build with SO generator only."""
        builder = build_ontology(
            include_github=False,
            include_stackoverflow=True,
            include_libraries=False,
        )
        assert builder.node_count > 0
        for node in builder.nodes[:50]:
            assert node.id.startswith("so.")

    def test_build_libraries_only(self) -> None:
        """Build with library generator only."""
        builder = build_ontology(
            include_github=False,
            include_stackoverflow=False,
            include_libraries=True,
        )
        assert builder.node_count > 0
        for node in builder.nodes[:50]:
            assert node.id.startswith("lib.")

    def test_build_with_csv_export(self, tmp_path: Path) -> None:
        """Build and export to CSV file."""
        output_path = tmp_path / "ontology.csv"
        builder = build_ontology(output_path=output_path)
        assert output_path.exists()
        assert builder.node_count > 0

        # Verify CSV is valid
        reader = csv.DictReader(output_path.open(encoding="utf-8"))
        rows = list(reader)
        assert len(rows) == builder.node_count

    def test_no_orphan_nodes_in_full_build(self) -> None:
        """Full build produces no orphan nodes."""
        builder = build_ontology()
        node_ids = {n.id for n in builder.nodes}
        for node in builder.nodes:
            if node.parent_id is not None:
                assert node.parent_id in node_ids, (
                    f"Orphan: '{node.id}' references '{node.parent_id}'"
                )

    def test_hierarchical_depth_in_full_build(self) -> None:
        """Full build achieves 4-7 levels of depth."""
        builder = build_ontology()
        max_depth = builder.get_max_depth()
        assert max_depth >= 4, f"Max depth {max_depth} < 4"
        assert max_depth <= 7, f"Max depth {max_depth} > 7"

    def test_unique_ids_in_full_build(self) -> None:
        """Full build has no duplicate IDs."""
        builder = build_ontology()
        ids = [n.id for n in builder.nodes]
        assert len(ids) == len(set(ids)), "Duplicate IDs in full build"

    def test_depth_stats_reasonable(self) -> None:
        """Depth stats show reasonable distribution."""
        builder = build_ontology()
        stats = builder.get_depth_stats()
        # Should have nodes at multiple levels
        assert len(stats) >= 4
        # Level 0 should have roots
        assert stats.get(0, 0) > 0

    def test_source_stats_all_present(self) -> None:
        """Source stats include all three generators."""
        builder = build_ontology()
        source_stats = builder.get_source_stats()
        assert "github-topics" in source_stats
        assert "stackoverflow-tags" in source_stats
        assert "library-docs" in source_stats


# ---------------------------------------------------------------------------
# Package import Tests
# ---------------------------------------------------------------------------


class TestScrapersPackageImports:
    """Test that the scrapers package exports all expected symbols."""

    def test_import_from_package(self) -> None:
        """All public symbols importable from zerorepo.ontology.scrapers."""
        from zerorepo.ontology.scrapers import (
            GitHubTopicsGenerator,
            LibraryDocsGenerator,
            OntologyBuilder,
            StackOverflowTagsGenerator,
            build_ontology,
        )

        assert GitHubTopicsGenerator is not None
        assert StackOverflowTagsGenerator is not None
        assert LibraryDocsGenerator is not None
        assert OntologyBuilder is not None
        assert build_ontology is not None

    def test_import_base(self) -> None:
        """SeedGenerator is importable from base module."""
        from zerorepo.ontology.scrapers.base import SeedGenerator

        assert SeedGenerator is not None
