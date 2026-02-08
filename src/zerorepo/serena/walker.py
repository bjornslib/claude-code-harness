"""CodebaseWalker -- walk a codebase and produce an RPGGraph baseline.

Uses a :class:`CodebaseAnalyzerProtocol` implementation (e.g.
``FileBasedCodebaseAnalyzer``) to discover packages, modules, and symbols,
then constructs an RPGGraph with the correct MODULE → COMPONENT → FEATURE
node hierarchy and HIERARCHY edges.

Epic 1, Feature 1.2 of PRD-RPG-SERENA-001.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.serena.session import CodebaseAnalyzerProtocol, SymbolEntry

logger = logging.getLogger(__name__)

# Default directories/patterns to exclude
DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    "__pycache__",
    ".git",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
    "*.egg-info",
    "dist",
    "build",
    ".eggs",
]


class CodebaseWalker:
    """Walk a codebase and produce an RPGGraph baseline.

    Uses a :class:`CodebaseAnalyzerProtocol` implementation to discover
    Python packages, modules, and symbols.  Constructs a three-level
    hierarchy: MODULE (packages) → COMPONENT (files) → FEATURE (symbols).

    Args:
        analyzer: An implementation of ``CodebaseAnalyzerProtocol``.
    """

    def __init__(self, analyzer: CodebaseAnalyzerProtocol) -> None:
        self.analyzer = analyzer

    def walk(
        self,
        project_root: Path,
        exclude_patterns: list[str] | None = None,
    ) -> RPGGraph:
        """Walk the codebase and build an RPGGraph with baseline nodes.

        Algorithm:
        1. Activate the analyser for the project root.
        2. Discover Python source directories (skip excluded patterns).
        3. For each package directory → create a MODULE node.
        4. For each ``.py`` file → create a COMPONENT node.
        5. For each class/function in a file → create a FEATURE node.
        6. Create HIERARCHY edges: MODULE → COMPONENT → FEATURE.
        7. Mark all nodes with ``serena_validated: True`` in metadata.
        8. Store metadata: ``baseline_generated_at``, ``project_root``.

        Args:
            project_root: Path to the codebase root directory.
            exclude_patterns: Patterns for directories/files to skip.
                Defaults to :data:`DEFAULT_EXCLUDE_PATTERNS` if not provided.

        Returns:
            A populated RPGGraph containing the baseline.
        """
        excludes = set(exclude_patterns or DEFAULT_EXCLUDE_PATTERNS)

        # Activate the analyser
        result = self.analyzer.activate(project_root)
        if not result.success:
            logger.warning(
                "Analyser activation failed for %s: %s",
                project_root,
                result.details,
            )
            # Return empty graph with error metadata
            graph = RPGGraph()
            graph.metadata["activation_error"] = result.details
            return graph

        graph = RPGGraph()
        graph.metadata["baseline_generated_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        graph.metadata["project_root"] = str(project_root.resolve())

        resolved_root = project_root.resolve()

        # Walk the filesystem to discover Python packages and files
        self._walk_directory(
            graph=graph,
            root=resolved_root,
            current=resolved_root,
            excludes=excludes,
            parent_node_id=None,
        )

        node_count = graph.node_count
        edge_count = graph.edge_count
        logger.info(
            "Baseline graph built: %d nodes, %d edges", node_count, edge_count
        )
        graph.metadata["baseline_stats"] = {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "modules": sum(
                1
                for n in graph.nodes.values()
                if n.level == NodeLevel.MODULE
            ),
            "components": sum(
                1
                for n in graph.nodes.values()
                if n.level == NodeLevel.COMPONENT
            ),
            "features": sum(
                1
                for n in graph.nodes.values()
                if n.level == NodeLevel.FEATURE
            ),
        }

        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk_directory(
        self,
        graph: RPGGraph,
        root: Path,
        current: Path,
        excludes: set[str],
        parent_node_id: Any | None,
    ) -> None:
        """Recursively walk directories, creating MODULE/COMPONENT/FEATURE nodes.

        Args:
            graph: The RPGGraph being constructed.
            root: The project root (for computing relative paths).
            current: The current directory being walked.
            excludes: Set of directory/file name patterns to skip.
            parent_node_id: UUID of the parent MODULE node (or None for root).
        """
        try:
            entries = sorted(os.listdir(current))
        except PermissionError:
            return

        # Check if this directory is a Python package
        is_package = "__init__.py" in entries

        # Determine subdirectories and .py files
        subdirs: list[str] = []
        py_files: list[str] = []

        for entry in entries:
            if self._should_exclude(entry, excludes):
                continue
            full_path = current / entry
            if full_path.is_dir():
                subdirs.append(entry)
            elif entry.endswith(".py") and full_path.is_file():
                py_files.append(entry)

        # If this is a Python package, create a MODULE node for it
        module_node_id = parent_node_id
        if is_package:
            if current == root:
                # The project root itself is a package -- use the dir name
                # as the module name and an empty-string-safe folder_path.
                rel_path = current.name
                module_name = current.name
            else:
                rel_path = str(current.relative_to(root))
                module_name = current.name

            module_node = RPGNode(
                name=module_name,
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=rel_path,
                parent_id=parent_node_id,
                serena_validated=True,
                metadata={"baseline": True, "is_package": True},
            )
            graph.add_node(module_node)
            module_node_id = module_node.id

            # Create HIERARCHY edge from parent to this module
            if parent_node_id is not None:
                edge = RPGEdge(
                    source_id=parent_node_id,
                    target_id=module_node.id,
                    edge_type=EdgeType.HIERARCHY,
                )
                graph.add_edge(edge)

        # Process .py files as COMPONENT nodes
        for py_file in py_files:
            if module_node_id is None and not is_package:
                # Standalone .py file outside a package -- skip
                continue

            full_path = current / py_file

            # Compute relative paths, handling the root-is-a-package case
            if current == root and is_package:
                # Root is itself a package -- use the dir name as prefix
                rel_folder = current.name
                rel_file = f"{current.name}/{py_file}"
            else:
                rel_file = str(full_path.relative_to(root))
                rel_folder = str(current.relative_to(root))

            component_node = RPGNode(
                name=py_file.removesuffix(".py"),
                level=NodeLevel.COMPONENT,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=rel_folder,
                file_path=rel_file,
                parent_id=module_node_id,
                serena_validated=True,
                metadata={"baseline": True},
            )
            graph.add_node(component_node)

            # HIERARCHY edge from MODULE to COMPONENT
            if module_node_id is not None:
                edge = RPGEdge(
                    source_id=module_node_id,
                    target_id=component_node.id,
                    edge_type=EdgeType.HIERARCHY,
                )
                graph.add_edge(edge)

            # Extract symbols from the file
            self._extract_features(
                graph=graph,
                root=root,
                file_path=full_path,
                rel_file=rel_file,
                rel_folder=rel_folder,
                component_node_id=component_node.id,
            )

        # Recurse into subdirectories
        for subdir in subdirs:
            subdir_path = current / subdir
            # Only recurse into Python packages (dirs with __init__.py)
            # or directories that may contain packages
            self._walk_directory(
                graph=graph,
                root=root,
                current=subdir_path,
                excludes=excludes,
                parent_node_id=module_node_id,
            )

    def _extract_features(
        self,
        graph: RPGGraph,
        root: Path,
        file_path: Path,
        rel_file: str,
        rel_folder: str,
        component_node_id: Any,
    ) -> None:
        """Extract class/function symbols from a file and create FEATURE nodes.

        Args:
            graph: The RPGGraph being constructed.
            root: The project root.
            file_path: Absolute path to the Python file.
            rel_file: Relative file path.
            rel_folder: Relative folder path.
            component_node_id: UUID of the parent COMPONENT node.
        """
        symbols = self.analyzer.get_symbols(
            str(file_path.relative_to(root))
        )

        for sym in symbols:
            # Only top-level classes and functions become FEATURE nodes
            # Methods (containing '.') are skipped at the FEATURE level --
            # they're sub-symbols of the class FEATURE
            if "." in sym.name:
                continue

            feature_node = RPGNode(
                name=sym.name,
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=rel_folder,
                file_path=rel_file,
                parent_id=component_node_id,
                serena_validated=True,
                docstring=sym.docstring,
                metadata={
                    "baseline": True,
                    "kind": sym.kind,
                    "line": sym.line,
                    "signature": sym.signature,
                },
            )
            graph.add_node(feature_node)

            # HIERARCHY edge from COMPONENT to FEATURE
            edge = RPGEdge(
                source_id=component_node_id,
                target_id=feature_node.id,
                edge_type=EdgeType.HIERARCHY,
            )
            graph.add_edge(edge)

    @staticmethod
    def _should_exclude(name: str, excludes: set[str]) -> bool:
        """Check if a file/directory name matches any exclude pattern.

        Supports exact matches and simple glob-style ``*`` prefix patterns
        (e.g. ``*.egg-info`` matches ``zerorepo.egg-info``).
        """
        if name.startswith("."):
            return True
        if name in excludes:
            return True
        # Check glob-style patterns like *.egg-info
        for pattern in excludes:
            if pattern.startswith("*") and name.endswith(pattern[1:]):
                return True
        return False
