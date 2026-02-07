"""ZeroRepo Feature Ontology Service – Data models and backend interface.

This package implements Epic 2.1 of PRD-RPG-P2-001 (Feature Ontology
Service), providing:

- :class:`FeatureNode` -- A node in the feature ontology tree
- :class:`FeaturePath` -- A ranked search result with ordered nodes
- :class:`OntologyStats` -- Aggregate statistics for an ontology backend
- :class:`OntologyBackend` -- Abstract base class for pluggable backends
- :class:`LLMOntologyBackend` -- LLM-generated ontology backend (Task 2.1.4)
- :class:`LLMBackendConfig` -- Configuration for the LLM backend
- :class:`FeatureEmbedder` -- Batch embedding pipeline (Task 2.1.3)
- :class:`EmbedderConfig` -- Configuration for the embedding pipeline
- :class:`EmbeddingResult` -- Result of a batch embedding operation
- :class:`OntologyChromaStore` -- ChromaDB-backed ontology store (Task 2.1.3)
- :class:`OntologyStoreConfig` -- Configuration for the ChromaDB store
"""

from zerorepo.ontology.backend import OntologyBackend
from zerorepo.ontology.chromadb_store import OntologyChromaStore, OntologyStoreConfig
from zerorepo.ontology.embeddings import (
    EmbedderConfig,
    EmbeddingResult,
    FeatureEmbedder,
)
from zerorepo.ontology.llm_backend import LLMBackendConfig, LLMOntologyBackend
from zerorepo.ontology.models import FeatureNode, FeaturePath, OntologyStats

__all__ = [
    "EmbedderConfig",
    "EmbeddingResult",
    "FeatureEmbedder",
    "FeatureNode",
    "FeaturePath",
    "LLMBackendConfig",
    "LLMOntologyBackend",
    "OntologyBackend",
    "OntologyChromaStore",
    "OntologyStats",
    "OntologyStoreConfig",
]
