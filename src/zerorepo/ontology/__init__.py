"""ZeroRepo Feature Ontology Service – Data models and backend interface.

This package implements Task 2.1.1 of PRD-RPG-P2-001 (Epic 2.1: Feature
Ontology Service), providing:

- :class:`FeatureNode` -- A node in the feature ontology tree
- :class:`FeaturePath` -- A ranked search result with ordered nodes
- :class:`OntologyStats` -- Aggregate statistics for an ontology backend
- :class:`OntologyBackend` -- Abstract base class for pluggable backends
"""

from zerorepo.ontology.backend import OntologyBackend
from zerorepo.ontology.models import FeatureNode, FeaturePath, OntologyStats

__all__ = [
    "FeatureNode",
    "FeaturePath",
    "OntologyBackend",
    "OntologyStats",
]
