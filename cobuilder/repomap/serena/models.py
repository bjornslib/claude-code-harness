"""Data models for the Serena MCP integration module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolInfo(BaseModel):
    """Information about a symbol discovered via Serena.

    Attributes:
        name: The symbol name (e.g., class or function name).
        kind: The symbol kind (class, function, method, variable).
        filepath: Relative or absolute file path where the symbol is defined.
        line: Line number where the symbol is defined (1-indexed).
        column: Column number where the symbol is defined (0-indexed).
        docstring: The symbol's docstring, if available.
    """

    name: str
    kind: str = Field(
        description="Symbol kind: 'class', 'function', 'method', or 'variable'"
    )
    filepath: str
    line: int = Field(ge=1, description="Line number (1-indexed)")
    column: int = Field(default=0, ge=0, description="Column number (0-indexed)")
    docstring: str | None = None


class PyrightConfig(BaseModel):
    """Pyright configuration for a workspace.

    Attributes:
        include: Glob patterns for files to include in analysis.
        exclude: Glob patterns for files to exclude from analysis.
        type_checking_mode: Pyright type checking strictness level.
        report_missing_imports: Whether to report missing imports.
    """

    include: list[str] = Field(
        default_factory=lambda: ["**/*.py"],
        description="Glob patterns for files to include",
    )
    exclude: list[str] = Field(
        default_factory=lambda: ["**/node_modules", "**/__pycache__"],
        description="Glob patterns for files to exclude",
    )
    type_checking_mode: str = Field(
        default="basic",
        description="Type checking mode: 'off', 'basic', 'standard', 'strict'",
    )
    report_missing_imports: bool = Field(
        default=True,
        description="Whether to report missing imports as errors",
    )
