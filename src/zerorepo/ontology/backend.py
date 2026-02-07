"""Abstract backend interface for the Feature Ontology Service.

Defines the ``OntologyBackend`` abstract base class that all ontology
backend implementations must satisfy.  This enables pluggable backends
(GitHub Topics, LLM-generated, custom Elasticsearch, etc.) as required
by FR-2.1.1 of PRD-RPG-P2-001.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from zerorepo.ontology.models import FeatureNode, FeaturePath, OntologyStats


class OntologyBackend(ABC):
    """Abstract base class for feature ontology backends.

    All ontology backends must implement these four core methods:

    - :meth:`search` -- Semantic search for feature paths
    - :meth:`get_node` -- Retrieve a single feature node by ID
    - :meth:`get_children` -- List child nodes of a given feature
    - :meth:`get_statistics` -- Aggregate ontology statistics

    Example usage::

        class MyBackend(OntologyBackend):
            def search(self, query, top_k=10):
                ...
            def get_node(self, feature_id):
                ...
            def get_children(self, feature_id):
                ...
            def get_statistics(self):
                ...

        backend = MyBackend()
        results = backend.search("authentication", top_k=5)
    """

    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> list[FeaturePath]:
        """Search the ontology for features matching a query.

        Performs semantic search using vector embeddings and/or keyword
        matching to find the most relevant feature paths.

        Args:
            query: Natural language search query
                (e.g., ``"user authentication"``).
            top_k: Maximum number of results to return.
                Must be positive.  Defaults to 10.

        Returns:
            Ordered list of :class:`FeaturePath` results, sorted by
            descending relevance score.  May contain fewer than
            ``top_k`` entries if the ontology has fewer matches.

        Raises:
            ValueError: If ``query`` is empty or ``top_k`` is not positive.
        """

    @abstractmethod
    def get_node(self, feature_id: str) -> FeatureNode:
        """Retrieve a single feature node by its unique identifier.

        Args:
            feature_id: The unique ID of the feature node
                (e.g., ``"ml.deep-learning.transformers"``).

        Returns:
            The :class:`FeatureNode` with the given ID.

        Raises:
            KeyError: If no node with the given ``feature_id`` exists.
            ValueError: If ``feature_id`` is empty.
        """

    @abstractmethod
    def get_children(self, feature_id: str) -> list[FeatureNode]:
        """List the direct children of a feature node.

        Args:
            feature_id: The unique ID of the parent feature node.

        Returns:
            List of :class:`FeatureNode` instances that are direct
            children of the specified node.  Returns an empty list if
            the node has no children (i.e., is a leaf node).

        Raises:
            KeyError: If no node with the given ``feature_id`` exists.
            ValueError: If ``feature_id`` is empty.
        """

    @abstractmethod
    def get_statistics(self) -> OntologyStats:
        """Compute and return aggregate ontology statistics.

        Returns:
            An :class:`OntologyStats` instance with summary metrics
            about the ontology's size, shape, and coverage.
        """
