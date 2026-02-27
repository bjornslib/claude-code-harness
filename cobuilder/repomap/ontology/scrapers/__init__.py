"""Seed data generators for the Feature Ontology Service.

This package implements Task 2.1.2 of PRD-RPG-P2-001 (Epic 2.1), providing
seed data generators that produce hierarchical feature ontology trees:

- :class:`GitHubTopicsGenerator` -- GitHub-style topic hierarchy generator
- :class:`StackOverflowTagsGenerator` -- Stack Overflow tag hierarchy generator
- :class:`LibraryDocsGenerator` -- Library documentation hierarchy generator
- :class:`TaxonomyExpander` -- Combinatorial expansion for 50K+ nodes
- :func:`build_ontology` -- Orchestrates generators, deduplicates, exports CSV
"""

from cobuilder.repomap.ontology.scrapers.build_ontology import (
    OntologyBuilder,
    build_ontology,
)
from cobuilder.repomap.ontology.scrapers.expander import TaxonomyExpander
from cobuilder.repomap.ontology.scrapers.github_topics import GitHubTopicsGenerator
from cobuilder.repomap.ontology.scrapers.library_docs import LibraryDocsGenerator
from cobuilder.repomap.ontology.scrapers.stackoverflow_tags import StackOverflowTagsGenerator

__all__ = [
    "GitHubTopicsGenerator",
    "LibraryDocsGenerator",
    "OntologyBuilder",
    "StackOverflowTagsGenerator",
    "TaxonomyExpander",
    "build_ontology",
]
