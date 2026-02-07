"""Requirements.txt and requirements-dev.txt generation.

Scans RPG node specifications and generated code to detect
third-party package dependencies and pin appropriate versions.
"""

from __future__ import annotations

import re

from zerorepo.codegen.import_manager import KNOWN_THIRD_PARTY, STDLIB_MODULES
from zerorepo.codegen.models import RequirementEntry
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode


# Standard dev dependencies always included
DEFAULT_DEV_REQUIREMENTS: list[RequirementEntry] = [
    RequirementEntry(
        package_name="pytest",
        version_spec=">=8.0.0,<9.0.0",
        is_dev=True,
        detected_from="default",
    ),
    RequirementEntry(
        package_name="pytest-cov",
        version_spec=">=5.0.0,<6.0.0",
        is_dev=True,
        detected_from="default",
    ),
    RequirementEntry(
        package_name="black",
        version_spec=">=24.0.0,<25.0.0",
        is_dev=True,
        detected_from="default",
    ),
    RequirementEntry(
        package_name="mypy",
        version_spec=">=1.8.0,<2.0.0",
        is_dev=True,
        detected_from="default",
    ),
]


def scan_node_imports(node: RPGNode) -> set[str]:
    """Extract import module names from a node's implementation and docstring.

    Parses import statements from the node's implementation code and
    also looks for library mentions in the docstring.

    Args:
        node: The RPG node to scan.

    Returns:
        A set of top-level module names found.
    """
    modules: set[str] = set()

    # Scan implementation code for import statements
    if node.implementation:
        modules.update(_extract_imports_from_code(node.implementation))

    # Scan test code for additional imports
    if node.test_code:
        modules.update(_extract_imports_from_code(node.test_code))

    # Scan docstring for library mentions
    if node.docstring:
        modules.update(_extract_library_mentions(node.docstring))

    return modules


def _extract_imports_from_code(code: str) -> set[str]:
    """Extract top-level module names from Python import statements.

    Handles both 'import X' and 'from X import Y' patterns.

    Args:
        code: Python source code string.

    Returns:
        A set of top-level module names.
    """
    modules: set[str] = set()

    # Match 'import X' or 'import X as Y'
    for match in re.finditer(r"^import\s+([\w.]+)", code, re.MULTILINE):
        top = match.group(1).split(".")[0]
        modules.add(top)

    # Match 'from X import Y'
    for match in re.finditer(r"^from\s+([\w.]+)\s+import", code, re.MULTILINE):
        top = match.group(1).split(".")[0]
        modules.add(top)

    return modules


def _extract_library_mentions(text: str) -> set[str]:
    """Extract known library names mentioned in text (docstrings, specs).

    Only returns names that are in KNOWN_THIRD_PARTY to avoid false positives.

    Args:
        text: The text to scan.

    Returns:
        A set of known third-party module names mentioned.
    """
    modules: set[str] = set()
    # Look for known library names as whole words
    words = set(re.findall(r"\b(\w+)\b", text.lower()))
    for word in words:
        if word in KNOWN_THIRD_PARTY:
            modules.add(word)
    return modules


def detect_requirements(graph: RPGGraph) -> list[RequirementEntry]:
    """Detect all third-party requirements from the RPG.

    Scans all nodes for import statements and library mentions,
    then maps them to pinned version requirements.

    Args:
        graph: The RPGGraph to scan.

    Returns:
        A deduplicated, sorted list of RequirementEntry objects.
    """
    seen_packages: dict[str, RequirementEntry] = {}

    for node in graph.nodes.values():
        modules = scan_node_imports(node)
        for module_name in modules:
            # Skip stdlib modules
            if module_name in STDLIB_MODULES:
                continue

            # Look up in known third-party mappings
            if module_name in KNOWN_THIRD_PARTY:
                spec = KNOWN_THIRD_PARTY[module_name]
                # Parse "package_name>=x.y.z,<x+1.0.0"
                parts = spec.split(">=", 1)
                pkg_name = parts[0]
                version = ">=" + parts[1] if len(parts) > 1 else ""
                if pkg_name not in seen_packages:
                    seen_packages[pkg_name] = RequirementEntry(
                        package_name=pkg_name,
                        version_spec=version,
                        is_dev=False,
                        detected_from="import_scan",
                    )

    return sorted(seen_packages.values(), key=lambda r: r.package_name.lower())


def render_requirements_txt(requirements: list[RequirementEntry]) -> str:
    """Render requirements.txt content from a list of requirements.

    Only includes non-dev requirements.

    Args:
        requirements: The requirement entries.

    Returns:
        The requirements.txt content string.
    """
    lines = [
        "# Auto-generated requirements - detected from RPG node specifications",
        "#",
    ]
    runtime = [r for r in requirements if not r.is_dev]
    for req in sorted(runtime, key=lambda r: r.package_name.lower()):
        lines.append(req.render())
    lines.append("")  # trailing newline
    return "\n".join(lines)


def render_requirements_dev_txt(
    requirements: list[RequirementEntry],
    dev_requirements: list[RequirementEntry] | None = None,
) -> str:
    """Render requirements-dev.txt content.

    Includes a -r requirements.txt reference, then dev-only packages.

    Args:
        requirements: All requirement entries (dev ones will be filtered).
        dev_requirements: Additional dev requirements (defaults used if None).

    Returns:
        The requirements-dev.txt content string.
    """
    devs = dev_requirements if dev_requirements is not None else DEFAULT_DEV_REQUIREMENTS
    all_dev = list(devs)

    # Also include any explicit dev requirements from the scan
    for req in requirements:
        if req.is_dev and req.package_name not in {d.package_name for d in all_dev}:
            all_dev.append(req)

    lines = [
        "# Auto-generated dev requirements",
        "#",
        "-r requirements.txt",
        "#",
        "# Development & testing tools",
    ]
    for req in sorted(all_dev, key=lambda r: r.package_name.lower()):
        lines.append(req.render())
    lines.append("")
    return "\n".join(lines)
