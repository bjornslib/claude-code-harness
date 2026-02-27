"""Generate __init__.py files with __all__ exports for Python packages.

Analyzes RPG nodes grouped by file to determine which symbols should
be exported from each package's __init__.py.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from cobuilder.repomap.codegen.models import FileEntry
from cobuilder.repomap.models.enums import InterfaceType
from cobuilder.repomap.models.node import RPGNode


def generate_init_content(
    package_path: str,
    file_map: dict[str, list[RPGNode]],
) -> str:
    """Generate the content for a __init__.py in a given package.

    Scans all files under the package directory, extracts public
    symbol names from RPG nodes, and generates import statements
    plus an __all__ export list.

    Args:
        package_path: The package directory path (e.g. 'src/data').
        file_map: Mapping from file paths to RPGNode lists.

    Returns:
        The generated __init__.py content string.
    """
    imports: list[str] = []
    all_names: list[str] = []

    # Find all files directly under this package
    package_prefix = package_path.rstrip("/") + "/"
    child_files: list[str] = sorted(
        path
        for path in file_map
        if path.startswith(package_prefix)
        and "/" not in path[len(package_prefix):]
        and path.endswith(".py")
        and not path.endswith("__init__.py")
    )

    for file_path in child_files:
        nodes = file_map.get(file_path, [])
        if not nodes:
            continue

        # Derive module name from file path
        module_name = PurePosixPath(file_path).stem

        # Collect exportable names
        exportable: list[str] = []
        for node in nodes:
            if node.name and not node.name.startswith("_"):
                exportable.append(node.name)

        if exportable:
            names_str = ", ".join(sorted(exportable))
            imports.append(f"from .{module_name} import {names_str}")
            all_names.extend(sorted(exportable))

    # Build the file content
    lines: list[str] = []
    docstring = _generate_package_docstring(package_path)
    lines.append(f'"""{docstring}"""')
    lines.append("")

    if imports:
        for imp in imports:
            lines.append(imp)
        lines.append("")
        all_items = ", ".join(f'"{name}"' for name in sorted(set(all_names)))
        lines.append(f"__all__ = [{all_items}]")
    else:
        lines.append("# No public exports yet.")

    lines.append("")  # trailing newline
    return "\n".join(lines)


def _generate_package_docstring(package_path: str) -> str:
    """Generate a brief docstring for a package from its path.

    Args:
        package_path: The package directory path.

    Returns:
        A one-line docstring string.
    """
    parts = PurePosixPath(package_path).parts
    # Use the last directory component as the description
    package_name = parts[-1] if parts else "package"
    return f"{package_name.replace('_', ' ').title()} package."


def collect_init_files(
    directories: list[str],
    file_map: dict[str, list[RPGNode]],
) -> list[FileEntry]:
    """Generate FileEntry objects for all __init__.py files needed.

    Args:
        directories: List of directory paths that need __init__.py.
        file_map: Mapping from file paths to RPGNode lists.

    Returns:
        A list of FileEntry objects for __init__.py files.
    """
    entries: list[FileEntry] = []
    for dir_path in sorted(directories):
        init_path = f"{dir_path.rstrip('/')}/__init__.py"
        content = generate_init_content(dir_path, file_map)
        entries.append(
            FileEntry(
                path=init_path,
                content=content,
                is_package_init=True,
            )
        )
    return entries
