"""Import management and cross-file reference resolution.

Tracks dependencies from RPG edges, generates PEP 8-compliant import
statements, resolves cross-file references, and detects circular imports.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import PurePosixPath
from uuid import UUID

from zerorepo.codegen.exceptions import CircularImportError, ImportResolutionError
from zerorepo.codegen.models import ImportGroup, ImportStatement
from zerorepo.models.enums import EdgeType
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


# Common Python stdlib module names (top-level)
STDLIB_MODULES: frozenset[str] = frozenset({
    "abc", "argparse", "ast", "asyncio", "base64", "bisect", "calendar",
    "codecs", "collections", "contextlib", "copy", "csv", "dataclasses",
    "datetime", "decimal", "enum", "errno", "fnmatch", "fractions",
    "functools", "glob", "gzip", "hashlib", "heapq", "hmac", "html",
    "http", "importlib", "inspect", "io", "itertools", "json", "logging",
    "math", "mmap", "multiprocessing", "operator", "os", "pathlib",
    "pickle", "platform", "pprint", "queue", "random", "re", "secrets",
    "shlex", "shutil", "signal", "socket", "sqlite3", "statistics",
    "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "timeit", "traceback", "typing", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
})

# Common third-party packages
KNOWN_THIRD_PARTY: dict[str, str] = {
    "numpy": "numpy>=1.24.0,<2.0.0",
    "np": "numpy>=1.24.0,<2.0.0",
    "pandas": "pandas>=2.0.0,<3.0.0",
    "pd": "pandas>=2.0.0,<3.0.0",
    "sklearn": "scikit-learn>=1.3.0,<2.0.0",
    "scipy": "scipy>=1.11.0,<2.0.0",
    "matplotlib": "matplotlib>=3.8.0,<4.0.0",
    "plt": "matplotlib>=3.8.0,<4.0.0",
    "seaborn": "seaborn>=0.13.0,<1.0.0",
    "sns": "seaborn>=0.13.0,<1.0.0",
    "torch": "torch>=2.0.0,<3.0.0",
    "tensorflow": "tensorflow>=2.15.0,<3.0.0",
    "tf": "tensorflow>=2.15.0,<3.0.0",
    "requests": "requests>=2.31.0,<3.0.0",
    "flask": "Flask>=3.0.0,<4.0.0",
    "fastapi": "fastapi>=0.100.0,<1.0.0",
    "pydantic": "pydantic>=2.0.0,<3.0.0",
    "sqlalchemy": "SQLAlchemy>=2.0.0,<3.0.0",
    "click": "click>=8.1.0,<9.0.0",
    "rich": "rich>=13.0.0,<14.0.0",
    "httpx": "httpx>=0.25.0,<1.0.0",
    "aiohttp": "aiohttp>=3.9.0,<4.0.0",
    "celery": "celery>=5.3.0,<6.0.0",
    "redis": "redis>=5.0.0,<6.0.0",
    "boto3": "boto3>=1.34.0,<2.0.0",
    "pillow": "Pillow>=10.0.0,<11.0.0",
    "PIL": "Pillow>=10.0.0,<11.0.0",
    "yaml": "PyYAML>=6.0.0,<7.0.0",
    "toml": "toml>=0.10.0,<1.0.0",
    "tomli": "tomli>=2.0.0,<3.0.0",
    "dotenv": "python-dotenv>=1.0.0,<2.0.0",
}


def classify_import(module_name: str) -> ImportGroup:
    """Classify a module as stdlib, third-party, or local.

    Args:
        module_name: The top-level module name.

    Returns:
        The ImportGroup classification.
    """
    top_level = module_name.split(".")[0]

    if top_level in STDLIB_MODULES:
        return ImportGroup.STDLIB
    if top_level in KNOWN_THIRD_PARTY or top_level in sys.stdlib_module_names:
        return ImportGroup.THIRD_PARTY if top_level in KNOWN_THIRD_PARTY else ImportGroup.STDLIB
    # If it looks like a generated local module (starts with src prefix or project name)
    return ImportGroup.THIRD_PARTY if top_level in KNOWN_THIRD_PARTY else ImportGroup.LOCAL


def _node_to_module_path(node: RPGNode) -> str | None:
    """Convert a node's file_path to a Python module dotted path.

    Example: 'src/data/processors.py' -> 'src.data.processors'

    Args:
        node: The RPG node.

    Returns:
        The dotted module path, or None if node has no file_path.
    """
    if not node.file_path:
        return None
    path = node.file_path.replace("\\", "/")
    if path.endswith(".py"):
        path = path[:-3]
    return path.replace("/", ".")


def resolve_imports_for_file(
    file_path: str,
    file_nodes: list[RPGNode],
    graph: RPGGraph,
) -> list[ImportStatement]:
    """Resolve all imports needed for a given file.

    Examines RPG edges from the nodes in this file to determine which
    external symbols they depend on, and generates appropriate import
    statements grouped by PEP 8 convention.

    Args:
        file_path: The target file path.
        file_nodes: The RPG nodes that belong to this file.
        graph: The full RPG graph for dependency resolution.

    Returns:
        A sorted list of ImportStatement objects.
    """
    imports: dict[str, ImportStatement] = {}
    node_ids_in_file = {n.id for n in file_nodes}

    # Build a reverse map: node_id -> file_path
    node_file_map: dict[UUID, str] = {}
    for node in graph.nodes.values():
        if node.file_path:
            node_file_map[node.id] = node.file_path.replace("\\", "/")

    # Find edges from nodes in this file to nodes in other files
    for edge in graph.edges.values():
        if edge.edge_type not in (EdgeType.DATA_FLOW, EdgeType.INVOCATION):
            continue

        if edge.source_id in node_ids_in_file and edge.target_id not in node_ids_in_file:
            target_node = graph.get_node(edge.target_id)
            if target_node is None or target_node.file_path is None:
                continue

            target_file = target_node.file_path.replace("\\", "/")
            if target_file == file_path:
                continue  # Same file, no import needed

            target_module = _node_to_module_path(target_node)
            if target_module is None:
                continue

            key = f"{target_module}.{target_node.name}"
            if key not in imports:
                group = classify_import(target_module)
                imports[key] = ImportStatement(
                    module_path=target_module,
                    imported_names=[target_node.name],
                    group=group,
                    is_from_import=True,
                )
            else:
                # Add the name if not already present
                if target_node.name not in imports[key].imported_names:
                    imports[key].imported_names.append(target_node.name)

    return _sort_imports(list(imports.values()))


def _sort_imports(imports: list[ImportStatement]) -> list[ImportStatement]:
    """Sort imports by PEP 8 group ordering: stdlib, third-party, local.

    Within each group, sort alphabetically by module path.

    Args:
        imports: The import statements to sort.

    Returns:
        The sorted import statements.
    """
    group_order = {ImportGroup.STDLIB: 0, ImportGroup.THIRD_PARTY: 1, ImportGroup.LOCAL: 2}
    return sorted(
        imports,
        key=lambda i: (group_order.get(i.group, 3), i.module_path),
    )


def render_import_block(imports: list[ImportStatement]) -> str:
    """Render a list of import statements as a PEP 8 compliant block.

    Groups imports with blank lines between stdlib, third-party, and
    local sections.

    Args:
        imports: The sorted import statements.

    Returns:
        The rendered import block string.
    """
    if not imports:
        return ""

    sorted_imports = _sort_imports(imports)
    lines: list[str] = []
    current_group: ImportGroup | None = None

    for imp in sorted_imports:
        if current_group is not None and imp.group != current_group:
            lines.append("")  # Blank line between groups
        current_group = imp.group
        lines.append(imp.render())

    return "\n".join(lines)


def detect_circular_imports(
    file_map: dict[str, list[RPGNode]],
    graph: RPGGraph,
) -> list[list[str]]:
    """Detect circular import dependencies between files.

    Builds a file-level dependency graph from RPG edges and detects
    cycles using DFS.

    Args:
        file_map: Mapping from file paths to RPGNode lists.
        graph: The full RPG graph.

    Returns:
        A list of cycles, where each cycle is a list of file paths.
        Empty list if no circular imports detected.
    """
    # Build file-level adjacency from edges
    file_deps: dict[str, set[str]] = defaultdict(set)
    node_file: dict[UUID, str] = {}

    for path, nodes in file_map.items():
        for node in nodes:
            node_file[node.id] = path

    for edge in graph.edges.values():
        if edge.edge_type not in (EdgeType.DATA_FLOW, EdgeType.INVOCATION):
            continue
        src_file = node_file.get(edge.source_id)
        tgt_file = node_file.get(edge.target_id)
        if src_file and tgt_file and src_file != tgt_file:
            file_deps[src_file].add(tgt_file)

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {f: WHITE for f in file_map}
    parent: dict[str, str | None] = {}
    cycles: list[list[str]] = []

    def _dfs(path: str) -> None:
        color[path] = GRAY
        for dep in sorted(file_deps.get(path, [])):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                # Reconstruct cycle
                cycle = [dep, path]
                current = path
                while current != dep:
                    current = parent.get(current)  # type: ignore[assignment]
                    if current is None or current == dep:
                        break
                    cycle.append(current)
                cycle.reverse()
                cycles.append(cycle)
            elif color[dep] == WHITE:
                parent[dep] = path
                _dfs(dep)
        color[path] = BLACK

    for file_path in sorted(file_map.keys()):
        if color.get(file_path, WHITE) == WHITE:
            parent[file_path] = None
            _dfs(file_path)

    return cycles
