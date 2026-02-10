"""Base protocol for seed data generators.

Defines the :class:`SeedGenerator` abstract base class that all ontology
seed data generators must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from zerorepo.ontology.models import FeatureNode


class SeedGenerator(ABC):
    """Abstract base class for ontology seed data generators.

    Each generator produces a list of :class:`FeatureNode` instances
    representing a portion of the feature ontology hierarchy.

    Implementations must ensure:
    - All generated nodes have valid ``parent_id`` references (except roots)
    - Node IDs are globally unique within the generator's output
    - Hierarchical depth is within the target range (4-7 levels)
    """

    @abstractmethod
    def generate(self) -> list[FeatureNode]:
        """Generate seed feature nodes for the ontology.

        Returns:
            List of :class:`FeatureNode` instances forming a valid
            hierarchical tree (roots have ``parent_id=None``).
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this generator (e.g., 'GitHub Topics')."""

    @property
    @abstractmethod
    def source_prefix(self) -> str:
        """Prefix for node IDs from this generator (e.g., 'gh', 'so', 'lib').

        Used to namespace node IDs and avoid collisions between generators.
        """
