"""Abstract base class for RPG enrichment encoders.

Each encoder is a single enrichment stage that processes an
:class:`~zerorepo.models.graph.RPGGraph` and returns the (potentially
mutated) graph.  Encoders are composed by :class:`RPGBuilder`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.models import ValidationResult


class RPGEncoder(ABC):
    """Abstract base class for a single enrichment encoder stage.

    Subclasses must implement :meth:`encode` and :meth:`validate`.

    Example::

        class TypeInferenceEncoder(RPGEncoder):
            def encode(self, graph: RPGGraph) -> RPGGraph:
                for node in graph.nodes.values():
                    node.metadata["inferred_types"] = infer(node)
                return graph

            def validate(self, graph: RPGGraph) -> ValidationResult:
                errors = []
                for node in graph.nodes.values():
                    if "inferred_types" not in node.metadata:
                        errors.append(f"Node {node.id}: missing inferred_types")
                return ValidationResult(passed=len(errors) == 0, errors=errors)
    """

    @property
    def name(self) -> str:
        """Return the name of this encoder (defaults to class name)."""
        return self.__class__.__name__

    @abstractmethod
    def encode(self, graph: RPGGraph) -> RPGGraph:
        """Run this enrichment stage on *graph*.

        The encoder may mutate the graph in-place (since Pydantic models
        with ``frozen=False`` allow attribute assignment) and must return
        the same graph object.

        Args:
            graph: The RPGGraph to enrich.

        Returns:
            The enriched RPGGraph (same instance, mutated in-place).
        """

    @abstractmethod
    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate that the graph meets this encoder's post-conditions.

        This is called after :meth:`encode` by the pipeline and can also
        be called independently for diagnostic purposes.

        Args:
            graph: The RPGGraph to validate.

        Returns:
            A :class:`ValidationResult` indicating success or failure.
        """
