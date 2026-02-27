"""Deterministic module relevance filter for RepoMap context injection.

Provides :func:`filter_relevant_modules` which selects modules from a
RepoMap baseline that are relevant to a given PRD/Solution Design, using
three purely deterministic strategies (no LLM calls):

1. **Direct match** — module path/name appears in *sd_file_references*.
2. **Dependency match** — module is depended on by a directly matched module
   (via HIERARCHY or INVOCATION edges in the baseline graph).
3. **Keyword match** — module name/path contains any of *prd_keywords*.

Results are deduplicated and sorted: NEW/MODIFIED delta_status nodes first,
then existing nodes, all within each group sorted alphabetically by name.

Also exposes :func:`extract_dependency_graph` which returns a slim
dependency list between a set of named modules (used by
:func:`~cobuilder.bridge.get_repomap_context` to populate the
``dependency_graph`` section of the YAML context).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_baseline(baseline_path: Path) -> dict[str, Any]:
    """Load and parse the baseline JSON file."""
    json_str = baseline_path.read_text(encoding="utf-8")
    return json.loads(json_str)


def _module_name_from_node(node_data: dict[str, Any]) -> str:
    """Derive the module name (top-level folder segment) from a node dict."""
    folder_path: str = node_data.get("folder_path") or ""
    file_path: str = node_data.get("file_path") or ""
    source = folder_path or file_path
    if not source:
        return node_data.get("name") or ""
    return source.split("/")[0]


def _delta_status(node_data: dict[str, Any]) -> str:
    """Extract delta_status from node metadata, defaulting to 'existing'."""
    metadata: dict[str, Any] = node_data.get("metadata") or {}
    return metadata.get("delta_status", "existing")


def _build_module_index(
    data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build a mapping of module_name → aggregated info dict.

    Aggregates all nodes that share the same top-level module folder into
    a single entry containing:
    - ``name``         — module name (top-level folder, e.g. ``"cobuilder"``)
    - ``file_count``   — number of COMPONENT-level nodes in the module
    - ``delta``        — "NEW" or "MODIFIED" if any node has that status,
                         else "existing"
    - ``node_ids``     — list of node UUIDs in this module
    - ``key_interfaces`` — list of interface signature dicts (up to 5)
    - ``summary``      — None (populated by caller if desired)
    """
    modules: dict[str, dict[str, Any]] = {}

    for node_id, node_data in data.get("nodes", {}).items():
        module_name = _module_name_from_node(node_data)
        if not module_name:
            continue

        if module_name not in modules:
            modules[module_name] = {
                "name": module_name,
                "file_count": 0,
                "delta": "existing",
                "node_ids": [],
                "key_interfaces": [],
                "summary": None,
            }

        entry = modules[module_name]
        entry["node_ids"].append(node_id)

        level = node_data.get("level", "")
        if level == "COMPONENT":
            entry["file_count"] += 1

        # Promote delta status: NEW > MODIFIED > existing
        ds = _delta_status(node_data)
        if ds in ("NEW", "MODIFIED"):
            if entry["delta"] not in ("NEW", "MODIFIED"):
                entry["delta"] = ds
            elif ds == "NEW":
                entry["delta"] = "NEW"

        # Collect key_interfaces from FUNCTION_AUGMENTED nodes
        if node_data.get("node_type") == "FUNCTION_AUGMENTED" and node_data.get("signature"):
            if len(entry["key_interfaces"]) < 5:
                entry["key_interfaces"].append(
                    {
                        "signature": node_data["signature"],
                        "file": node_data.get("file_path") or "",
                        "line": None,
                    }
                )

    return modules


def _build_edge_index(
    data: dict[str, Any],
    node_id_to_module: dict[str, str],
) -> dict[str, set[str]]:
    """Build a mapping of module_name → set of modules it depends on.

    Considers HIERARCHY, INVOCATION, and DATA_FLOW edges as dependency edges.
    Edges from a module to itself are ignored.
    """
    deps: dict[str, set[str]] = {}

    dependency_edge_types = {"HIERARCHY", "INVOCATION", "DATA_FLOW"}

    for _edge_id, edge_data in data.get("edges", {}).items():
        etype = edge_data.get("edge_type", "")
        if etype not in dependency_edge_types:
            continue

        src_id = edge_data.get("source_id", "")
        tgt_id = edge_data.get("target_id", "")

        src_module = node_id_to_module.get(src_id, "")
        tgt_module = node_id_to_module.get(tgt_id, "")

        if not src_module or not tgt_module or src_module == tgt_module:
            continue

        deps.setdefault(src_module, set()).add(tgt_module)

    return deps


def _sort_key(module_entry: dict[str, Any]) -> tuple[int, str]:
    """Sort key: NEW (0) < MODIFIED (1) < existing (2), then alpha by name."""
    delta = module_entry.get("delta", "existing")
    order = {"NEW": 0, "MODIFIED": 1}.get(delta, 2)
    return (order, module_entry.get("name", ""))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def filter_relevant_modules(
    baseline_path: Path,
    prd_keywords: list[str],
    sd_file_references: list[str],
    max_results: int = 15,
) -> list[dict]:
    """Filter RepoMap modules relevant to a PRD/SD — deterministic, no LLM.

    Three-strategy approach applied in order; results are merged and
    deduplicated before final sorting:

    1. **Direct match**: module path/name appears in *sd_file_references*
       (case-insensitive substring check).
    2. **Dependency match**: module is depended on by a directly matched
       module (via HIERARCHY / INVOCATION / DATA_FLOW edges).
    3. **Keyword match**: module name contains any of *prd_keywords*
       (case-insensitive word-boundary match).

    Final list is sorted: NEW/MODIFIED first, then existing; alphabetical
    within each group.  Capped at *max_results*.

    Args:
        baseline_path: Path to ``.repomap/baselines/{repo}/baseline.json``.
        prd_keywords: Lowercase keywords from the PRD title/description.
        sd_file_references: File paths mentioned in the Solution Design.
        max_results: Maximum number of modules to return.

    Returns:
        List of module dicts with keys:
        ``name``, ``delta``, ``files``, ``summary``, ``key_interfaces``.
    """
    baseline_path = Path(baseline_path)
    data = _load_baseline(baseline_path)

    modules = _build_module_index(data)

    # Build node → module reverse map for edge traversal
    node_id_to_module: dict[str, str] = {}
    for name, entry in modules.items():
        for nid in entry["node_ids"]:
            node_id_to_module[nid] = name

    # Strategy 1 — Direct match via sd_file_references
    sd_refs_lower = [ref.lower() for ref in (sd_file_references or [])]
    direct_matches: set[str] = set()
    for mod_name in modules:
        mod_lower = mod_name.lower()
        if any(mod_lower in ref or ref.startswith(mod_lower + "/") for ref in sd_refs_lower):
            direct_matches.add(mod_name)
        elif any(mod_lower in ref for ref in sd_refs_lower):
            direct_matches.add(mod_name)

    # Strategy 2 — Dependency expansion from direct matches
    edge_deps = _build_edge_index(data, node_id_to_module)
    dependency_matches: set[str] = set()
    for direct_mod in direct_matches:
        for dep_mod in edge_deps.get(direct_mod, set()):
            if dep_mod not in direct_matches:
                dependency_matches.add(dep_mod)

    # Strategy 3 — Keyword match
    keyword_matches: set[str] = set()
    if prd_keywords:
        for mod_name in modules:
            mod_lower = mod_name.lower()
            for kw in prd_keywords:
                if re.search(r"\b" + re.escape(kw.lower()) + r"\b", mod_lower):
                    keyword_matches.add(mod_name)
                    break

    # Merge all matches (deduplicated by set union)
    all_matches = direct_matches | dependency_matches | keyword_matches

    # Build result list
    result: list[dict] = []
    for mod_name in all_matches:
        entry = modules[mod_name]
        result.append(
            {
                "name": entry["name"],
                "delta": entry["delta"],
                "files": entry["file_count"],
                "summary": None,
                "key_interfaces": entry["key_interfaces"],
            }
        )

    # Sort: NEW/MODIFIED first, then alphabetical; cap at max_results
    result.sort(key=_sort_key)
    return result[:max_results]


def extract_dependency_graph(
    baseline_path: Path,
    module_names: list[str],
) -> list[dict]:
    """Extract dependency edges between a set of named modules.

    Reads the baseline graph and returns edges where both source and target
    modules appear in *module_names*.  Only HIERARCHY, INVOCATION, and
    DATA_FLOW edge types are included.

    Args:
        baseline_path: Path to ``.repomap/baselines/{repo}/baseline.json``.
        module_names: List of module names to include (e.g. top-level folders).

    Returns:
        List of dicts with keys: ``from``, ``to``, ``type``, ``description``.
        Deduplicated by (from, to, type) triple.
    """
    baseline_path = Path(baseline_path)
    data = _load_baseline(baseline_path)

    modules = _build_module_index(data)

    node_id_to_module: dict[str, str] = {}
    for name, entry in modules.items():
        for nid in entry["node_ids"]:
            node_id_to_module[nid] = name

    module_set = set(module_names)
    dependency_edge_types = {"HIERARCHY", "INVOCATION", "DATA_FLOW"}

    # Collect unique (from, to, type) triples
    seen: set[tuple[str, str, str]] = set()
    result: list[dict] = []

    for _edge_id, edge_data in data.get("edges", {}).items():
        etype = edge_data.get("edge_type", "")
        if etype not in dependency_edge_types:
            continue

        src_module = node_id_to_module.get(edge_data.get("source_id", ""), "")
        tgt_module = node_id_to_module.get(edge_data.get("target_id", ""), "")

        if not src_module or not tgt_module or src_module == tgt_module:
            continue
        if src_module not in module_set or tgt_module not in module_set:
            continue

        key = (src_module, tgt_module, etype)
        if key in seen:
            continue
        seen.add(key)

        description = edge_data.get("transformation") or edge_data.get("data_type") or ""
        result.append(
            {
                "from": src_module,
                "to": tgt_module,
                "type": "depends",
                "description": description,
            }
        )

    return result
