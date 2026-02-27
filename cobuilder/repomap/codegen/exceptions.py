"""Custom exceptions for the code generation assembly pipeline."""

from __future__ import annotations


class AssemblyError(Exception):
    """Base exception for all repository assembly errors."""

    pass


class FileStructureError(AssemblyError):
    """Raised when file structure creation fails.

    Examples: conflicting paths, invalid directory names,
    permission errors during directory creation.
    """

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"File structure error at '{path}': {reason}")


class ImportResolutionError(AssemblyError):
    """Raised when an import cannot be resolved.

    Includes both the source module requesting the import
    and the target symbol that could not be resolved.
    """

    def __init__(self, source_module: str, target_symbol: str, reason: str) -> None:
        self.source_module = source_module
        self.target_symbol = target_symbol
        self.reason = reason
        super().__init__(
            f"Cannot resolve import of '{target_symbol}' "
            f"in '{source_module}': {reason}"
        )


class CircularImportError(AssemblyError):
    """Raised when a circular import dependency is detected.

    Attributes:
        cycle: The list of module paths forming the cycle.
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        super().__init__(f"Circular import detected: {cycle_str}")


class MetadataExtractionError(AssemblyError):
    """Raised when metadata cannot be extracted for project configuration."""

    pass
