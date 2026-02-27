"""Custom exceptions for graph operations."""

from __future__ import annotations

from uuid import UUID


class CycleDetectedError(Exception):
    """Raised when a cycle is detected in a graph that should be acyclic.

    Attributes:
        cycle: The list of node UUIDs forming the cycle.
    """

    def __init__(self, cycle: list[UUID], message: str | None = None) -> None:
        self.cycle = cycle
        if message is None:
            ids = " -> ".join(str(uid) for uid in cycle)
            message = f"Cycle detected: {ids}"
        super().__init__(message)
