"""SerenaSession -- Protocol-based codebase analysis interface.

Defines the ``CodebaseAnalyzerProtocol`` for abstracting codebase analysis,
and provides ``FileBasedCodebaseAnalyzer`` as a standalone implementation
that uses Python's ``ast`` module and ``os.walk`` for symbol extraction
without requiring a running Serena MCP server.

Epic 1, Feature 1.1 of PRD-RPG-SERENA-001.
"""

from __future__ import annotations

import ast
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes for analysis results
# ---------------------------------------------------------------------------


@dataclass
class SymbolEntry:
    """A symbol discovered during codebase analysis.

    Attributes:
        name: Symbol name (class or function/method name).
        kind: Symbol kind -- ``'class'``, ``'function'``, or ``'method'``.
        filepath: Relative file path where the symbol is defined.
        line: Line number (1-indexed).
        signature: Full signature string (e.g. ``def foo(a, b) -> int``).
        docstring: The symbol's docstring, if available.
    """

    name: str
    kind: str
    filepath: str
    line: int = 1
    signature: str | None = None
    docstring: str | None = None


@dataclass
class DirectoryEntry:
    """A directory entry from listing results.

    Attributes:
        name: Name of the file or directory.
        path: Full relative path.
        is_dir: Whether this entry is a directory.
    """

    name: str
    path: str
    is_dir: bool = False


@dataclass
class ActivationResult:
    """Result of activating/connecting to a project.

    Attributes:
        project_root: The resolved project root path.
        success: Whether activation succeeded.
        details: Extra details about the activation.
    """

    project_root: str
    success: bool = True
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CodebaseAnalyzerProtocol(Protocol):
    """Minimal interface for analysing a codebase.

    Implementations can be backed by Serena MCP, Python ``ast``, or mocks.
    All paths used in the protocol are **relative** to the project root.
    """

    def activate(self, project_root: Path) -> ActivationResult:
        """Activate the analyser for a given project root.

        Must be called before any other method.  Subsequent calls may
        re-initialise the analyser for a different project.
        """
        ...

    def list_directory(
        self, path: str, recursive: bool = False
    ) -> list[DirectoryEntry]:
        """List entries in a directory.

        Args:
            path: Relative path within the project (use ``"."`` for root).
            recursive: If ``True``, recurse into subdirectories.

        Returns:
            A list of directory entries.
        """
        ...

    def get_symbols(self, path: str) -> list[SymbolEntry]:
        """Return symbols defined in a single file.

        Args:
            path: Relative file path (e.g. ``"src/foo/bar.py"``).

        Returns:
            List of symbols found in the file.
        """
        ...

    def find_symbol(
        self, name: str, depth: int = 2, include_body: bool = False
    ) -> list[SymbolEntry]:
        """Search for a symbol by name across the project.

        Args:
            name: Symbol name (or dotted path like ``Module.Class``).
            depth: How deep to search within nested scopes.
            include_body: Whether to include the full function/class body.

        Returns:
            List of matching symbols.
        """
        ...

    def find_references(self, symbol: str) -> list[SymbolEntry]:
        """Find references to a symbol across the project.

        Args:
            symbol: The symbol name to search for.

        Returns:
            List of locations where the symbol is referenced.
        """
        ...

    def search_pattern(self, pattern: str) -> list[dict[str, Any]]:
        """Search for a regex pattern across the project.

        Args:
            pattern: A regex pattern string.

        Returns:
            List of match dicts with ``file``, ``line``, ``match`` keys.
        """
        ...


# ---------------------------------------------------------------------------
# File-based implementation (standalone, no Serena required)
# ---------------------------------------------------------------------------


class FileBasedCodebaseAnalyzer:
    """Codebase analyser that uses Python ``ast`` and ``os.walk``.

    This is the default analyser used when Serena MCP is not available.
    It only handles Python (``.py``) files.

    Implements :class:`CodebaseAnalyzerProtocol`.
    """

    def __init__(self) -> None:
        self._project_root: Path | None = None

    # -- Protocol methods ---------------------------------------------------

    def activate(self, project_root: Path) -> ActivationResult:
        """Set the project root for subsequent operations."""
        resolved = project_root.resolve()
        if not resolved.is_dir():
            return ActivationResult(
                project_root=str(resolved),
                success=False,
                details={"error": f"Not a directory: {resolved}"},
            )
        self._project_root = resolved
        logger.info("FileBasedCodebaseAnalyzer activated: %s", resolved)
        return ActivationResult(
            project_root=str(resolved),
            success=True,
            details={"files_detected": True},
        )

    def list_directory(
        self, path: str, recursive: bool = False
    ) -> list[DirectoryEntry]:
        """List directory entries using ``os.listdir`` / ``os.walk``."""
        self._ensure_activated()
        assert self._project_root is not None

        target = self._project_root / path
        if not target.is_dir():
            return []

        entries: list[DirectoryEntry] = []
        if recursive:
            for root, dirs, files in os.walk(target):
                # Skip hidden / cache dirs
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".") and d != "__pycache__"
                ]
                rel_root = Path(root).relative_to(self._project_root)
                for d in sorted(dirs):
                    entries.append(
                        DirectoryEntry(
                            name=d,
                            path=str(rel_root / d),
                            is_dir=True,
                        )
                    )
                for f in sorted(files):
                    entries.append(
                        DirectoryEntry(
                            name=f,
                            path=str(rel_root / f),
                            is_dir=False,
                        )
                    )
        else:
            try:
                items = sorted(os.listdir(target))
            except PermissionError:
                return []
            rel_target = target.relative_to(self._project_root)
            for item in items:
                if item.startswith(".") or item == "__pycache__":
                    continue
                full = target / item
                entries.append(
                    DirectoryEntry(
                        name=item,
                        path=str(rel_target / item),
                        is_dir=full.is_dir(),
                    )
                )
        return entries

    def get_symbols(self, path: str) -> list[SymbolEntry]:
        """Parse a Python file and return top-level class/function symbols."""
        self._ensure_activated()
        assert self._project_root is not None

        full_path = self._project_root / path
        if not full_path.is_file() or not full_path.suffix == ".py":
            return []

        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(full_path))
        except (SyntaxError, UnicodeDecodeError):
            logger.debug("Could not parse %s", path)
            return []

        return self._extract_symbols(tree, path)

    def find_symbol(
        self, name: str, depth: int = 2, include_body: bool = False
    ) -> list[SymbolEntry]:
        """Search for a named symbol across all Python files."""
        self._ensure_activated()
        assert self._project_root is not None

        results: list[SymbolEntry] = []
        for root, dirs, files in os.walk(self._project_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d != "__pycache__"
            ]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                full = Path(root) / fname
                rel = str(full.relative_to(self._project_root))
                try:
                    source = full.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(full))
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for sym in self._extract_symbols(tree, rel):
                    if sym.name == name or name in sym.name:
                        results.append(sym)
        return results

    def find_references(self, symbol: str) -> list[SymbolEntry]:
        """Find references to a symbol using simple text search in AST names."""
        self._ensure_activated()
        assert self._project_root is not None

        results: list[SymbolEntry] = []
        for root, dirs, files in os.walk(self._project_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d != "__pycache__"
            ]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                full = Path(root) / fname
                rel = str(full.relative_to(self._project_root))
                try:
                    source = full.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(full))
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Name) and node.id == symbol:
                        results.append(
                            SymbolEntry(
                                name=symbol,
                                kind="reference",
                                filepath=rel,
                                line=getattr(node, "lineno", 1),
                            )
                        )
                    elif (
                        isinstance(node, ast.Attribute) and node.attr == symbol
                    ):
                        results.append(
                            SymbolEntry(
                                name=symbol,
                                kind="reference",
                                filepath=rel,
                                line=getattr(node, "lineno", 1),
                            )
                        )
        return results

    def search_pattern(self, pattern: str) -> list[dict[str, Any]]:
        """Search for a text pattern across all Python files.

        NOTE: This is a basic ``str.find`` search, not full regex.
        """
        self._ensure_activated()
        assert self._project_root is not None

        import re

        try:
            compiled = re.compile(pattern)
        except re.error:
            return []

        results: list[dict[str, Any]] = []
        for root, dirs, files in os.walk(self._project_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d != "__pycache__"
            ]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                full = Path(root) / fname
                rel = str(full.relative_to(self._project_root))
                try:
                    lines = full.read_text(encoding="utf-8").splitlines()
                except (UnicodeDecodeError, PermissionError):
                    continue
                for i, line in enumerate(lines, start=1):
                    m = compiled.search(line)
                    if m:
                        results.append(
                            {"file": rel, "line": i, "match": m.group()}
                        )
        return results

    # -- Internal helpers ---------------------------------------------------

    def _ensure_activated(self) -> None:
        """Raise if ``activate()`` has not been called."""
        if self._project_root is None:
            raise RuntimeError(
                "FileBasedCodebaseAnalyzer not activated. "
                "Call activate(project_root) first."
            )

    @staticmethod
    def _extract_symbols(tree: ast.Module, filepath: str) -> list[SymbolEntry]:
        """Extract top-level classes and functions from an AST.

        For classes, also extracts methods (one level deep).
        """
        symbols: list[SymbolEntry] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                sig = f"class {node.name}"
                # Add base classes if any
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.dump(base))
                if bases:
                    sig += f"({', '.join(bases)})"
                sig += ":"

                symbols.append(
                    SymbolEntry(
                        name=node.name,
                        kind="class",
                        filepath=filepath,
                        line=node.lineno,
                        signature=sig,
                        docstring=ast.get_docstring(node),
                    )
                )

                # Extract methods from the class
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_sig = _build_function_signature(child)
                        symbols.append(
                            SymbolEntry(
                                name=f"{node.name}.{child.name}",
                                kind="method",
                                filepath=filepath,
                                line=child.lineno,
                                signature=method_sig,
                                docstring=ast.get_docstring(child),
                            )
                        )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = _build_function_signature(node)
                symbols.append(
                    SymbolEntry(
                        name=node.name,
                        kind="function",
                        filepath=filepath,
                        line=node.lineno,
                        signature=sig,
                        docstring=ast.get_docstring(node),
                    )
                )

        return symbols


# ---------------------------------------------------------------------------
# AST helper
# ---------------------------------------------------------------------------


def _build_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    """Build a human-readable signature from an AST function node.

    Produces e.g. ``"def foo(self, x: int, y: str = 'default') -> bool"``.
    """
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args_parts: list[str] = []

    for arg in node.args.args:
        part = arg.arg
        if arg.annotation:
            try:
                part += f": {ast.unparse(arg.annotation)}"
            except Exception:
                pass
        args_parts.append(part)

    # Defaults are right-aligned to the args list
    n_defaults = len(node.args.defaults)
    if n_defaults:
        offset = len(node.args.args) - n_defaults
        for i, default in enumerate(node.args.defaults):
            try:
                args_parts[offset + i] += f" = {ast.unparse(default)}"
            except Exception:
                args_parts[offset + i] += " = ..."

    # *args
    if node.args.vararg:
        part = f"*{node.args.vararg.arg}"
        if node.args.vararg.annotation:
            try:
                part += f": {ast.unparse(node.args.vararg.annotation)}"
            except Exception:
                pass
        args_parts.append(part)

    # **kwargs
    if node.args.kwarg:
        part = f"**{node.args.kwarg.arg}"
        if node.args.kwarg.annotation:
            try:
                part += f": {ast.unparse(node.args.kwarg.annotation)}"
            except Exception:
                pass
        args_parts.append(part)

    sig = f"{prefix} {node.name}({', '.join(args_parts)})"

    if node.returns:
        try:
            sig += f" -> {ast.unparse(node.returns)}"
        except Exception:
            pass

    return sig
