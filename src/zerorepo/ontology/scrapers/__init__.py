"""Seed data generators for the Feature Ontology Service.

This package implements Task 2.1.2 of PRD-RPG-P2-001 (Epic 2.1), providing
seed data generators that produce hierarchical feature ontology trees:

- :class:`GitHubTopicsGenerator` -- GitHub-style topic hierarchy generator
- :class:`StackOverflowTagsGenerator` -- Stack Overflow tag hierarchy generator
- :class:`LibraryDocsGenerator` -- Library documentation hierarchy generator
- :func:`build_ontology` -- Orchestrates generators, deduplicates, exports CSV
"""

from zerorepo.ontology.scrapers.build_ontology import (
    OntologyBuilder,
    build_ontology,
)
from zerorepo.ontology.scrapers.github_topics import GitHubTopicsGenerator
from zerorepo.ontology.scrapers.library_docs import LibraryDocsGenerator
from zerorepo.ontology.scrapers.stackoverflow_tags import StackOverflowTagsGenerator

__all__ = [
    "GitHubTopicsGenerator",
    "LibraryDocsGenerator",
    "OntologyBuilder",
    "StackOverflowTagsGenerator",
    "build_ontology",
]
