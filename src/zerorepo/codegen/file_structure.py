"""File structure generation from RPG node paths.

Creates directory hierarchy from RPG node file_path attributes,
ensuring proper Python package structure with __init__.py files.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath
from uuid import UUID

from zerorepo.codegen.exceptions import FileStructureError
from zerorepo.codegen.models import DirectoryEntry, FileEntry
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


def extract_directories(graph: RPGGraph) -> list[DirectoryEntry]:
    """Extract unique directories from RPG node file_paths.

    Scans all nodes with a file_path attribute and collects all
    intermediate directories. Each directory under src/ is marked
    as needing an __init__.py. The root directories (src/, tests/,
    docs/) are always included.

    Args:
        graph: The RPGGraph containing nodes with file_path attributes.

    Returns:
        A sorted list of DirectoryEntry objects (parents before children).
    """
    dirs: dict[str, DirectoryEntry] = {}

    # Always include standard directories
    for standard_dir in ("src", "tests", "docs"):
        dirs[standard_dir] = DirectoryEntry(
            path=standard_dir,
            needs_init=(standard_dir == "src"),
        )

    for node in graph.nodes.values():
        if node.file_path:
            # Get all parent directories of the file path
            parts = PurePosixPath(node.file_path).parts
            for i in range(1, len(parts)):
                dir_path = str(PurePosixPath(*parts[:i]))
                needs_init = dir_path.startswith("src")
                if dir_path not in dirs:
                    dirs[dir_path] = DirectoryEntry(
                        path=dir_path,
                        needs_init=needs_init,
                    )

    # Sort by path length (parents first) then alphabetically
    return sorted(dirs.values(), key=lambda d: (d.path.count("/"), d.path))


def extract_file_entries(graph: RPGGraph) -> list[FileEntry]:
    """Extract unique file entries from RPG nodes.

    Groups nodes by their file_path so that multiple nodes targeting
    the same file are merged into a single FileEntry with all
    contributing node IDs.

    Args:
        graph: The RPGGraph containing nodes with file_path attributes.

    Returns:
        A list of FileEntry objects sorted by path.
    """
    files: dict[str, FileEntry] = {}

    for node in graph.nodes.values():
        if not node.file_path:
            continue

        path = node.file_path.replace("\\", "/")
        if path in files:
            files[path].source_node_ids.append(node.id)
        else:
            files[path] = FileEntry(
                path=path,
                source_node_ids=[node.id],
            )

    return sorted(files.values(), key=lambda f: f.path)


def build_file_map(graph: RPGGraph) -> dict[str, list[RPGNode]]:
    """Build a mapping from file paths to the nodes that belong to each file.

    This is used by downstream generators (import manager, init generator)
    to know which functions/classes belong to which file.

    Args:
        graph: The RPGGraph to process.

    Returns:
        A dict mapping relative file path to the list of RPGNode objects
        that should be generated into that file.
    """
    file_map: dict[str, list[RPGNode]] = {}
    for node in graph.nodes.values():
        if node.file_path:
            path = node.file_path.replace("\\", "/")
            file_map.setdefault(path, []).append(node)

    # Sort nodes within each file by name for deterministic output
    for path in file_map:
        file_map[path].sort(key=lambda n: n.name)

    return file_map


def validate_file_structure(
    directories: list[DirectoryEntry],
    files: list[FileEntry],
) -> list[str]:
    """Validate a planned file structure for consistency.

    Checks:
    - All file parent directories exist in the directory list
    - No duplicate file paths
    - No path conflicts (file path is also a directory path)

    Args:
        directories: Planned directories.
        files: Planned files.

    Returns:
        A list of warning messages (empty if valid).
    """
    warnings: list[str] = []
    dir_paths = {d.path for d in directories}
    file_paths: set[str] = set()

    for f in files:
        # Check for duplicate file paths
        if f.path in file_paths:
            warnings.append(f"Duplicate file path: {f.path}")
        file_paths.add(f.path)

        # Check parent directory exists
        parent = str(PurePosixPath(f.path).parent)
        if parent != "." and parent not in dir_paths:
            warnings.append(
                f"File '{f.path}' parent directory '{parent}' not in directory list"
            )

        # Check path conflict
        if f.path in dir_paths:
            warnings.append(
                f"Path conflict: '{f.path}' is both a file and a directory"
            )

    return warnings


def create_directory_structure(
    base_path: str,
    directories: list[DirectoryEntry],
) -> list[str]:
    """Create directories on disk.

    Args:
        base_path: The root directory for the generated repository.
        directories: The directories to create.

    Returns:
        A list of created directory paths (absolute).

    Raises:
        FileStructureError: If a directory cannot be created.
    """
    created: list[str] = []
    for entry in directories:
        full_path = os.path.join(base_path, entry.path)
        try:
            os.makedirs(full_path, exist_ok=True)
            created.append(full_path)
        except OSError as e:
            raise FileStructureError(entry.path, str(e)) from e
    return created
