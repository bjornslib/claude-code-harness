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

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.enums import EdgeType, NodeLevel, NodeType
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode
from cobuilder.repomap.serena.session import CodebaseAnalyzerProtocol, SymbolEntry

logger = logging.getLogger(__name__)

# File extensions treated as TypeScript/JavaScript source files
TS_EXTENSIONS: frozenset[str] = frozenset([".ts", ".tsx", ".js", ".jsx"])

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
    ".next",
    ".nuxt",
    "out",
    ".turbo",
    ".swc",
    "trees",
    "worktrees",
]


class CodebaseWalker:
    """Walk a codebase and produce an RPGGraph baseline.

    Uses a :class:`CodebaseAnalyzerProtocol` implementation to discover
    packages, modules, and symbols.  Constructs a three-level hierarchy:
    MODULE (packages/directories) → COMPONENT (files) → FEATURE (symbols).

    Supported file types:
    - **Python** (``.py``): full symbol extraction via the analyser.
    - **TypeScript/React** (``.ts``, ``.tsx``): component nodes created;
      symbol extraction is a no-op with ``FileBasedCodebaseAnalyzer`` (which
      only parses Python AST) but will work transparently with a Serena-backed
      analyser that understands TypeScript.
    - **JavaScript** (``.js``, ``.jsx``): treated the same as TypeScript.

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
        2. Discover source directories (skip excluded patterns).
        3. For each Python package or TS/JS directory → create a MODULE node.
        4. For each ``.py`` / ``.ts`` / ``.tsx`` / ``.js`` / ``.jsx`` file
           → create a COMPONENT node.
        5. For each class/function in a ``.py`` file → create a FEATURE node.
           (Symbol extraction is a no-op for TS/JS with the default analyser.)
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

        Supports Python packages (``.py`` files in directories with
        ``__init__.py``) and TypeScript/JavaScript source files (``.ts``,
        ``.tsx``, ``.js``, ``.jsx``).  A directory becomes a MODULE node if it
        is a Python package **or** if it directly contains TS/JS source files.

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

        # Determine subdirectories, .py files, and TypeScript/JS files
        subdirs: list[str] = []
        py_files: list[str] = []
        ts_files: list[str] = []

        for entry in entries:
            if self._should_exclude(entry, excludes):
                continue
            full_path = current / entry
            if full_path.is_dir():
                subdirs.append(entry)
            elif full_path.is_file():
                if entry.endswith(".py"):
                    py_files.append(entry)
                elif Path(entry).suffix in TS_EXTENSIONS:
                    ts_files.append(entry)

        # A TypeScript directory is any non-excluded directory with TS/JS files
        is_ts_dir = bool(ts_files)

        # Create a MODULE node for Python packages OR TypeScript directories
        module_node_id = parent_node_id
        if is_package or is_ts_dir:
            if current == root:
                # The project root itself is a module -- use the dir name
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
                metadata={
                    "baseline": True,
                    "is_package": is_package,
                    "is_ts_dir": is_ts_dir,
                },
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

            # Compute relative paths, handling the root-is-a-module case
            if current == root:
                # Root directory — use the dir name as prefix so that
                # file_path always starts with folder_path.
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

        # Process TypeScript/JavaScript files as COMPONENT nodes
        for ts_file in ts_files:
            if module_node_id is None:
                # No module context (shouldn't happen if is_ts_dir is True)
                continue

            full_path = current / ts_file

            # Compute relative paths, handling the root case
            if current == root:
                rel_folder = current.name
                rel_file = f"{current.name}/{ts_file}"
            else:
                rel_file = str(full_path.relative_to(root))
                rel_folder = str(current.relative_to(root))

            # Use the stem (e.g. "App" from "App.tsx", "index" from "index.ts")
            component_name = Path(ts_file).stem

            component_node = RPGNode(
                name=component_name,
                level=NodeLevel.COMPONENT,
                node_type=NodeType.FUNCTIONALITY,
                folder_path=rel_folder,
                file_path=rel_file,
                parent_id=module_node_id,
                serena_validated=True,
                metadata={"baseline": True, "language": "typescript"},
            )
            graph.add_node(component_node)

            # HIERARCHY edge from MODULE to COMPONENT
            edge = RPGEdge(
                source_id=module_node_id,
                target_id=component_node.id,
                edge_type=EdgeType.HIERARCHY,
            )
            graph.add_edge(edge)

            # Attempt feature extraction; gracefully returns [] for non-.py files
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

    def walk_paths(
        self,
        paths: list[str | Path],
        project_root: Path,
        exclude_patterns: list[str] | None = None,
    ) -> RPGGraph:
        """Walk only the specified file/directory paths and return an RPGGraph.

        Produces the same node structure as walk() but restricted to the
        given paths. File paths are processed directly; directory paths
        are walked recursively.

        Args:
            paths: List of relative or absolute file/directory paths to scan.
            project_root: The project root for computing relative node IDs.
            exclude_patterns: Optional patterns to exclude (same as walk()).

        Returns:
            RPGGraph containing nodes for the scoped paths only.
        """
        excludes = set(exclude_patterns or DEFAULT_EXCLUDE_PATTERNS)

        # Activate the analyser for the project root
        result = self.analyzer.activate(project_root)
        if not result.success:
            logger.warning(
                "Analyser activation failed for %s: %s",
                project_root,
                result.details,
            )
            graph = RPGGraph()
            graph.metadata["activation_error"] = result.details
            return graph

        graph = RPGGraph()
        graph.metadata["baseline_generated_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        graph.metadata["project_root"] = str(project_root.resolve())

        resolved_root = project_root.resolve()

        _SCOPED_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
            [".py", ".ts", ".tsx", ".js", ".jsx"]
        )

        for raw_path in paths:
            p = Path(raw_path)
            # Resolve to absolute path
            if not p.is_absolute():
                p = (resolved_root / p).resolve()
            else:
                p = p.resolve()

            if not p.exists():
                logger.warning("walk_paths: path does not exist, skipping: %s", p)
                continue

            if p.is_dir():
                # Recursively walk the directory with the existing helper
                self._walk_directory(
                    graph=graph,
                    root=resolved_root,
                    current=p,
                    excludes=excludes,
                    parent_node_id=None,
                )
            elif p.is_file():
                suffix = p.suffix
                if suffix not in _SCOPED_SOURCE_EXTENSIONS:
                    logger.debug(
                        "walk_paths: skipping non-source file: %s", p
                    )
                    continue

                # Determine relative paths using the same logic as _walk_directory
                parent_dir = p.parent
                if parent_dir == resolved_root:
                    rel_folder = resolved_root.name
                    rel_file = f"{resolved_root.name}/{p.name}"
                else:
                    try:
                        rel_file = str(p.relative_to(resolved_root))
                        rel_folder = str(parent_dir.relative_to(resolved_root))
                    except ValueError:
                        # Path is outside project_root — use the filename only
                        logger.warning(
                            "walk_paths: file outside project_root, using name only: %s",
                            p,
                        )
                        rel_file = p.name
                        rel_folder = ""

                if suffix == ".py":
                    # Need a module node for the parent directory to satisfy
                    # the COMPONENT parent_id requirement. We look for an
                    # existing MODULE node with matching folder_path, or create
                    # a synthetic one if needed.
                    existing_module: RPGNode | None = None
                    for node in graph.nodes.values():
                        from cobuilder.repomap.models.enums import NodeLevel as _NL
                        if (
                            node.level == _NL.MODULE
                            and node.folder_path == rel_folder
                        ):
                            existing_module = node
                            break

                    if existing_module is None:
                        # Create a minimal MODULE node for this directory
                        dir_name = parent_dir.name if rel_folder else resolved_root.name
                        from cobuilder.repomap.models.enums import NodeLevel as _NL2
                        from cobuilder.repomap.models.enums import NodeType as _NT2
                        module_node = RPGNode(
                            name=dir_name,
                            level=_NL2.MODULE,
                            node_type=_NT2.FUNCTIONALITY,
                            folder_path=rel_folder,
                            parent_id=None,
                            serena_validated=True,
                            metadata={
                                "baseline": True,
                                "is_package": (parent_dir / "__init__.py").exists(),
                                "is_ts_dir": False,
                                "scoped_synthetic": True,
                            },
                        )
                        graph.add_node(module_node)
                        module_node_id: Any = module_node.id
                    else:
                        module_node_id = existing_module.id

                    component_node = RPGNode(
                        name=p.stem,
                        level=NodeLevel.COMPONENT,
                        node_type=NodeType.FUNCTIONALITY,
                        folder_path=rel_folder,
                        file_path=rel_file,
                        parent_id=module_node_id,
                        serena_validated=True,
                        metadata={"baseline": True},
                    )
                    graph.add_node(component_node)

                    if module_node_id is not None:
                        edge = RPGEdge(
                            source_id=module_node_id,
                            target_id=component_node.id,
                            edge_type=EdgeType.HIERARCHY,
                        )
                        graph.add_edge(edge)

                    # Extract features
                    self._extract_features(
                        graph=graph,
                        root=resolved_root,
                        file_path=p,
                        rel_file=rel_file,
                        rel_folder=rel_folder,
                        component_node_id=component_node.id,
                    )

                elif suffix in TS_EXTENSIONS:
                    # TypeScript/JS file — create MODULE + COMPONENT, no features
                    existing_module_ts: RPGNode | None = None
                    for node in graph.nodes.values():
                        from cobuilder.repomap.models.enums import NodeLevel as _NL3
                        if (
                            node.level == _NL3.MODULE
                            and node.folder_path == rel_folder
                        ):
                            existing_module_ts = node
                            break

                    if existing_module_ts is None:
                        dir_name_ts = parent_dir.name if rel_folder else resolved_root.name
                        from cobuilder.repomap.models.enums import NodeLevel as _NL4
                        from cobuilder.repomap.models.enums import NodeType as _NT4
                        module_node_ts = RPGNode(
                            name=dir_name_ts,
                            level=_NL4.MODULE,
                            node_type=_NT4.FUNCTIONALITY,
                            folder_path=rel_folder,
                            parent_id=None,
                            serena_validated=True,
                            metadata={
                                "baseline": True,
                                "is_package": False,
                                "is_ts_dir": True,
                                "scoped_synthetic": True,
                            },
                        )
                        graph.add_node(module_node_ts)
                        module_node_ts_id: Any = module_node_ts.id
                    else:
                        module_node_ts_id = existing_module_ts.id

                    component_node_ts = RPGNode(
                        name=Path(p.name).stem,
                        level=NodeLevel.COMPONENT,
                        node_type=NodeType.FUNCTIONALITY,
                        folder_path=rel_folder,
                        file_path=rel_file,
                        parent_id=module_node_ts_id,
                        serena_validated=True,
                        metadata={"baseline": True, "language": "typescript"},
                    )
                    graph.add_node(component_node_ts)

                    edge_ts = RPGEdge(
                        source_id=module_node_ts_id,
                        target_id=component_node_ts.id,
                        edge_type=EdgeType.HIERARCHY,
                    )
                    graph.add_edge(edge_ts)

                    # Attempt feature extraction (no-op for TS with FileBasedAnalyzer)
                    self._extract_features(
                        graph=graph,
                        root=resolved_root,
                        file_path=p,
                        rel_file=rel_file,
                        rel_folder=rel_folder,
                        component_node_id=component_node_ts.id,
                    )

        logger.info(
            "Scoped walk complete: %d nodes, %d edges (from %d paths)",
            graph.node_count,
            graph.edge_count,
            len(paths),
        )
        return graph

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
