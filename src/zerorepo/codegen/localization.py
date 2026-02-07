"""Graph-guided localization tools for the code generation pipeline.

Provides fuzzy search over RPG nodes, source code viewing,
dependency exploration, and query tracking for debugging iterations.

Classes:
    RPGFuzzySearch -- Embedding-based search over RPG node descriptions.
    RepositoryCodeView -- Source code reading and AST-based extraction.
    DependencyExplorer -- N-hop neighborhood exploration in the RPG.
    LocalizationTracker -- Query logging with repetition avoidance.
"""

from __future__ import annotations

import ast
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from zerorepo.codegen.localization_models import (
    DependencyMap,
    LocalizationExhaustedError,
    LocalizationResult,
)
from zerorepo.models.enums import TestStatus
from zerorepo.models.graph import RPGGraph
from zerorepo.vectordb.models import SearchResult

logger = logging.getLogger(__name__)


class RPGFuzzySearch:
    """Embedding-based fuzzy search over RPG node descriptions.

    Uses a VectorStore to compute cosine similarity between a text
    query and RPG node descriptions, returning the top-k matches.

    Args:
        graph: The RPGGraph containing nodes to search.
        vector_store: A VectorStore instance for similarity queries.
    """

    def __init__(self, graph: RPGGraph, vector_store: Any) -> None:
        self._graph = graph
        self._vector_store = vector_store

    def search(
        self,
        query: str,
        top_k: int = 5,
        subgraph_id: str | None = None,
    ) -> list[LocalizationResult]:
        """Search for RPG nodes matching a text query.

        Embeds the query and computes cosine similarity against
        RPG node descriptions stored in the vector store.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.
            subgraph_id: Optional subgraph filter (node_id prefix or path).

        Returns:
            List of LocalizationResult ordered by relevance (best first).
        """
        filters: dict[str, Any] | None = None
        if subgraph_id is not None:
            filters = {"path": subgraph_id}

        try:
            search_results: list[SearchResult] = self._vector_store.search(
                query=query,
                top_k=top_k,
                filters=filters,
            )
        except Exception:
            logger.warning("VectorStore search failed for query: %s", query)
            return []

        results: list[LocalizationResult] = []
        for sr in search_results:
            node_id_str = sr.metadata.get("node_id")
            node_id: UUID | None = None
            filepath = ""
            line: int | None = None
            context = sr.document

            if node_id_str:
                try:
                    node_id = UUID(node_id_str)
                    node = self._graph.get_node(node_id)
                    if node:
                        filepath = node.file_path or ""
                        context = node.docstring or node.name
                except (ValueError, KeyError):
                    pass

            results.append(
                LocalizationResult(
                    node_id=node_id,
                    symbol_name=sr.document.split()[0] if sr.document else "",
                    filepath=filepath,
                    line=line,
                    score=max(0.0, min(1.0, sr.score)),
                    source="rpg_fuzzy",
                    context=context,
                )
            )

        return results


class RepositoryCodeView:
    """Source code reader with AST-based extraction.

    Provides methods to read entire files, extract function/class
    signatures, and retrieve individual function bodies. File contents
    are cached to avoid redundant disk reads.

    Args:
        root_dir: The root directory of the repository.
    """

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._cache: dict[str, str] = {}

    def _resolve_path(self, filepath: str) -> Path:
        """Resolve a relative or absolute filepath against the repo root."""
        p = Path(filepath)
        if p.is_absolute():
            return p
        return self._root / filepath

    def get_file_content(self, filepath: str) -> str:
        """Read the full source code of a file.

        Results are cached for subsequent calls.

        Args:
            filepath: Relative or absolute path to the file.

        Returns:
            The full file content as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if filepath in self._cache:
            return self._cache[filepath]

        resolved = self._resolve_path(filepath)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")

        content = resolved.read_text(encoding="utf-8")
        self._cache[filepath] = content
        return content

    def get_signatures(self, filepath: str) -> list[str]:
        """Extract function and class signatures from a Python file.

        Uses AST parsing to find all top-level and nested function/class
        definitions and return their signatures with type hints.

        Args:
            filepath: Relative or absolute path to the Python file.

        Returns:
            List of signature strings (e.g., 'def foo(x: int) -> str').

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        content = self.get_file_content(filepath)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        signatures: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                sig = self._format_function_signature(node, content)
                signatures.append(sig)
            elif isinstance(node, ast.ClassDef):
                signatures.append(f"class {node.name}")

        return signatures

    @staticmethod
    def _format_function_signature(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
    ) -> str:
        """Format a function AST node into a signature string."""
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        args_parts: list[str] = []

        for arg in node.args.args:
            ann = ""
            if arg.annotation:
                ann = f": {ast.get_source_segment(source, arg.annotation) or '...'}"
            args_parts.append(f"{arg.arg}{ann}")

        args_str = ", ".join(args_parts)
        ret = ""
        if node.returns:
            ret_text = ast.get_source_segment(source, node.returns) or "..."
            ret = f" -> {ret_text}"

        return f"{prefix} {node.name}({args_str}){ret}"

    def get_function_body(self, filepath: str, function_name: str) -> str:
        """Extract the body of a specific function from a Python file.

        Args:
            filepath: Relative or absolute path to the Python file.
            function_name: Name of the function to extract.

        Returns:
            The function body as a string (including def line).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the function is not found.
        """
        content = self.get_file_content(filepath)
        lines = content.splitlines(keepends=True)

        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            raise ValueError(
                f"Cannot parse '{filepath}': {exc}"
            ) from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name == function_name:
                    start = node.lineno - 1  # 0-indexed
                    end = node.end_lineno or (start + 1)
                    return "".join(lines[start:end])

        raise ValueError(
            f"Function '{function_name}' not found in '{filepath}'"
        )

    def clear_cache(self) -> None:
        """Clear the file content cache."""
        self._cache.clear()


class DependencyExplorer:
    """N-hop dependency neighbourhood explorer for RPG graphs.

    Traverses incoming and outgoing edges around a center node
    to build a DependencyMap showing the local neighbourhood.

    Args:
        graph: The RPGGraph to explore.
    """

    def __init__(self, graph: RPGGraph) -> None:
        self._graph = graph

    def explore(
        self,
        node_id: UUID,
        hops: int = 2,
    ) -> DependencyMap:
        """Explore the N-hop neighbourhood of a node.

        Shows both incoming (dependents) and outgoing (dependencies)
        edges, highlighting failed nodes.

        Args:
            node_id: The center node UUID.
            hops: Number of hops to explore (default: 2).

        Returns:
            A DependencyMap containing the neighbourhood.

        Raises:
            ValueError: If node_id is not found in the graph.
        """
        if node_id not in self._graph.nodes:
            raise ValueError(f"Node '{node_id}' not found in graph")

        incoming = self._collect_incoming(node_id, hops)
        outgoing = self._collect_outgoing(node_id, hops)

        return DependencyMap(
            center_node_id=node_id,
            incoming=incoming,
            outgoing=outgoing,
            hops=hops,
        )

    def _collect_incoming(
        self, node_id: UUID, hops: int
    ) -> list[tuple[UUID, str]]:
        """Collect incoming edges up to N hops."""
        result: list[tuple[UUID, str]] = []
        visited: set[UUID] = {node_id}
        queue: deque[tuple[UUID, int]] = deque([(node_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= hops:
                continue

            for edge in self._graph.edges.values():
                if edge.target_id == current and edge.source_id not in visited:
                    visited.add(edge.source_id)
                    edge_label = edge.edge_type.value
                    node = self._graph.get_node(edge.source_id)
                    if node and node.test_status == TestStatus.FAILED:
                        edge_label = f"{edge_label}[FAILED]"
                    result.append((edge.source_id, edge_label))
                    queue.append((edge.source_id, depth + 1))

        return result

    def _collect_outgoing(
        self, node_id: UUID, hops: int
    ) -> list[tuple[UUID, str]]:
        """Collect outgoing edges up to N hops."""
        result: list[tuple[UUID, str]] = []
        visited: set[UUID] = {node_id}
        queue: deque[tuple[UUID, int]] = deque([(node_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= hops:
                continue

            for edge in self._graph.edges.values():
                if edge.source_id == current and edge.target_id not in visited:
                    visited.add(edge.target_id)
                    edge_label = edge.edge_type.value
                    node = self._graph.get_node(edge.target_id)
                    if node and node.test_status == TestStatus.FAILED:
                        edge_label = f"{edge_label}[FAILED]"
                    result.append((edge.target_id, edge_label))
                    queue.append((edge.target_id, depth + 1))

        return result

    def as_ascii_tree(
        self,
        dep_map: DependencyMap,
    ) -> str:
        """Render a DependencyMap as an ASCII tree string.

        Args:
            dep_map: The DependencyMap to render.

        Returns:
            An ASCII tree representation.
        """
        lines: list[str] = []
        center_node = self._graph.get_node(dep_map.center_node_id)
        center_name = center_node.name if center_node else str(dep_map.center_node_id)
        lines.append(f"[{center_name}]")

        if dep_map.incoming:
            lines.append("  Incoming:")
            for nid, etype in dep_map.incoming:
                node = self._graph.get_node(nid)
                name = node.name if node else str(nid)
                lines.append(f"    <- {name} ({etype})")

        if dep_map.outgoing:
            lines.append("  Outgoing:")
            for nid, etype in dep_map.outgoing:
                node = self._graph.get_node(nid)
                name = node.name if node else str(nid)
                lines.append(f"    -> {name} ({etype})")

        return "\n".join(lines)


class LocalizationTracker:
    """Query logger with repetition avoidance for debugging iterations.

    Tracks each localization query (text, tool, results) and enforces
    a maximum number of attempts per debugging iteration. Provides
    search history to avoid re-running identical queries.

    Args:
        max_attempts: Maximum queries per debugging iteration (default: 20).
    """

    def __init__(self, max_attempts: int = 20) -> None:
        self._max_attempts = max_attempts
        self._history: list[dict[str, Any]] = []

    @property
    def attempt_count(self) -> int:
        """Return the number of attempts so far."""
        return len(self._history)

    @property
    def max_attempts(self) -> int:
        """Return the maximum number of allowed attempts."""
        return self._max_attempts

    @property
    def history(self) -> list[dict[str, Any]]:
        """Return the full query history."""
        return list(self._history)

    def log_query(
        self,
        query: str,
        tool: str,
        results_count: int,
        results: list[Any] | None = None,
    ) -> None:
        """Log a localization query.

        Args:
            query: The query text.
            tool: The tool used (e.g., 'serena', 'rpg_fuzzy').
            results_count: Number of results found.
            results: Optional list of result details.

        Raises:
            LocalizationExhaustedError: If the attempt limit is exceeded.
        """
        if len(self._history) >= self._max_attempts:
            raise LocalizationExhaustedError(self._max_attempts)

        self._history.append({
            "query": query,
            "tool": tool,
            "results_count": results_count,
            "results": results or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def has_queried(self, query: str, tool: str) -> bool:
        """Check if an identical query has already been run.

        Args:
            query: The query text.
            tool: The tool name.

        Returns:
            True if this exact (query, tool) combination was already logged.
        """
        return any(
            entry["query"] == query and entry["tool"] == tool
            for entry in self._history
        )

    def get_previous_queries(self) -> list[str]:
        """Return all previously executed query strings.

        Returns:
            List of unique query strings from the history.
        """
        seen: set[str] = set()
        queries: list[str] = []
        for entry in self._history:
            q = entry["query"]
            if q not in seen:
                seen.add(q)
                queries.append(q)
        return queries

    def reset(self) -> None:
        """Clear the query history and reset the attempt counter."""
        self._history.clear()
