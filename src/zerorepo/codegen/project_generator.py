"""pyproject.toml and setup.py generation for the generated repository.

Extracts project metadata from RPG and NL spec to generate
PEP 621-compliant pyproject.toml (preferred) or legacy setup.py.
"""

from __future__ import annotations

from typing import Any

from zerorepo.codegen.models import RequirementEntry
from zerorepo.models.graph import RPGGraph


def extract_project_metadata(graph: RPGGraph) -> dict[str, Any]:
    """Extract project metadata from the RPG graph metadata.

    Looks for standard metadata keys in the RPG metadata dict.
    Falls back to sensible defaults for missing fields.

    Args:
        graph: The RPGGraph with metadata.

    Returns:
        A dict with project metadata keys:
        name, description, version, author, license, python_requires,
        entry_points.
    """
    meta = graph.metadata

    return {
        "name": meta.get("project_name", "generated-project"),
        "description": meta.get(
            "project_description", "Auto-generated Python project from RPG specification"
        ),
        "version": meta.get("version", "0.1.0"),
        "author": meta.get("author", "ZeroRepo Code Generator"),
        "license": meta.get("license", "MIT"),
        "python_requires": meta.get("python_requires", ">=3.11"),
        "entry_points": meta.get("entry_points", {}),
    }


def render_pyproject_toml(
    metadata: dict[str, Any],
    requirements: list[RequirementEntry],
) -> str:
    """Render a pyproject.toml file from metadata and requirements.

    Uses hatchling as the build backend and includes PEP 621
    compliant project metadata.

    Args:
        metadata: Project metadata dict from extract_project_metadata.
        requirements: Runtime requirements (non-dev).

    Returns:
        The pyproject.toml content string.
    """
    name = metadata.get("name", "generated-project")
    description = metadata.get("description", "")
    version = metadata.get("version", "0.1.0")
    author = metadata.get("author", "ZeroRepo")
    license_name = metadata.get("license", "MIT")
    python_requires = metadata.get("python_requires", ">=3.11")

    runtime_reqs = [r for r in requirements if not r.is_dev]
    dev_reqs = [r for r in requirements if r.is_dev]

    lines: list[str] = [
        "[build-system]",
        'requires = ["hatchling"]',
        'build-backend = "hatchling.build"',
        "",
        "[project]",
        f'name = "{name}"',
        f'version = "{version}"',
        f'description = "{description}"',
        f'requires-python = "{python_requires}"',
    ]

    # License
    lines.append(f'license = "{license_name}"')

    # Authors
    lines.append(f'authors = [{{name = "{author}"}}]')

    # Dependencies
    if runtime_reqs:
        lines.append("dependencies = [")
        for req in sorted(runtime_reqs, key=lambda r: r.package_name.lower()):
            lines.append(f'    "{req.render()}",')
        lines.append("]")
    else:
        lines.append("dependencies = []")

    # Dev dependencies
    lines.append("")
    lines.append("[project.optional-dependencies]")
    dev_lines = ['    "pytest>=8.0.0,<9.0.0"', '    "pytest-cov>=5.0.0,<6.0.0"']
    for req in sorted(dev_reqs, key=lambda r: r.package_name.lower()):
        dev_lines.append(f'    "{req.render()}"')
    lines.append("dev = [")
    lines.extend(f"{line}," for line in dev_lines)
    lines.append("]")

    # Entry points
    entry_points = metadata.get("entry_points", {})
    if entry_points:
        lines.append("")
        lines.append("[project.scripts]")
        for name_ep, path_ep in sorted(entry_points.items()):
            lines.append(f'{name_ep} = "{path_ep}"')

    # Build configuration
    lines.append("")
    lines.append("[tool.pytest.ini_options]")
    lines.append('testpaths = ["tests"]')
    lines.append("")
    lines.append("[tool.hatch.build.targets.wheel]")
    lines.append('packages = ["src"]')
    lines.append("")

    return "\n".join(lines)


def render_setup_py(
    metadata: dict[str, Any],
    requirements: list[RequirementEntry],
) -> str:
    """Render a legacy setup.py as fallback.

    Used when pyproject.toml is not suitable or when explicitly requested.

    Args:
        metadata: Project metadata dict.
        requirements: Runtime requirements.

    Returns:
        The setup.py content string.
    """
    name = metadata.get("name", "generated-project")
    description = metadata.get("description", "")
    version = metadata.get("version", "0.1.0")
    author = metadata.get("author", "ZeroRepo")
    python_requires = metadata.get("python_requires", ">=3.11")

    runtime_reqs = [r for r in requirements if not r.is_dev]
    req_strings = [f'        "{r.render()}"' for r in sorted(
        runtime_reqs, key=lambda r: r.package_name.lower()
    )]

    lines = [
        '"""Setup configuration for the generated project."""',
        "",
        "from setuptools import find_packages, setup",
        "",
        "",
        "setup(",
        f'    name="{name}",',
        f'    version="{version}",',
        f'    description="{description}",',
        f'    author="{author}",',
        f'    python_requires="{python_requires}",',
        '    packages=find_packages(where="src"),',
        '    package_dir={"": "src"},',
        "    install_requires=[",
    ]
    lines.extend(f"{r}," for r in req_strings)
    lines.append("    ],")
    lines.append(")")
    lines.append("")

    return "\n".join(lines)
