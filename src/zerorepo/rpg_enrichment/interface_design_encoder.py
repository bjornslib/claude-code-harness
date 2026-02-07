"""InterfaceDesignEncoder -- generates signatures, docstrings, and interface types.

Epic 3.6: For each FEATURE-level node, determines whether it should be a
standalone function or a class method, generates a typed Python signature
and Google-style docstring via the LLM gateway, and adds INVOCATION edges
between features that reference each other within the same file.
"""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from typing import Any, Protocol
from uuid import UUID

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import EdgeType, InterfaceType, NodeLevel, NodeType
from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)

# Minimum number of interdependent features in the same file to form a class.
_MIN_CLASS_GROUP_SIZE = 2


# ---------------------------------------------------------------------------
# LLM Gateway protocol (duck-typed so tests can inject a mock)
# ---------------------------------------------------------------------------


class LLMGatewayProtocol(Protocol):
    """Minimal interface expected from an LLM gateway."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_signature_syntax(signature: str) -> bool:
    """Check that *signature* is syntactically valid Python.

    Appends ``pass`` to the signature so ``ast.parse`` can treat it as a
    complete function definition.

    Args:
        signature: A ``def ...`` or ``class ...`` line.

    Returns:
        True if the signature can be parsed, False otherwise.
    """
    try:
        ast.parse(f"{signature}\n    pass")
        return True
    except SyntaxError:
        return False


def _safe_function_name(name: str) -> str:
    """Convert a feature name to a valid Python identifier.

    Args:
        name: Raw feature name.

    Returns:
        A lower-case, underscore-delimited Python identifier.
    """
    result = name.lower().strip().replace(" ", "_").replace("-", "_")
    result = "".join(c for c in result if c.isalnum() or c == "_")
    result = result.strip("_") or "unnamed"
    if result[0].isdigit():
        result = f"fn_{result}"
    return result


def _safe_class_name(name: str) -> str:
    """Convert a name to PascalCase suitable for a Python class.

    Args:
        name: Raw name.

    Returns:
        A PascalCase Python identifier.
    """
    parts = name.replace("-", " ").replace("_", " ").split()
    pascal = "".join(p.capitalize() for p in parts if p)
    if not pascal or pascal[0].isdigit():
        pascal = f"Cls{pascal}"
    return pascal


# ---------------------------------------------------------------------------
# InterfaceDesignEncoder
# ---------------------------------------------------------------------------


class InterfaceDesignEncoder(RPGEncoder):
    """Assign interface_type, signature, and docstring to FEATURE nodes.

    Strategy:
    1. Group FEATURE-level nodes by ``file_path``.
    2. Within each file, identify independent vs. interdependent features.
       - Independent (no same-file DATA_FLOW / INVOCATION deps) ->
         ``interface_type = FUNCTION``.
       - Interdependent (>= ``_MIN_CLASS_GROUP_SIZE`` features sharing
         same-file deps) -> grouped into a class.  The class node itself
         gets ``InterfaceType.CLASS``; its members get ``InterfaceType.METHOD``.
    3. For each node, generate a typed Python signature via the LLM gateway
       using the ``signature_generation`` template.
    4. Generate a Google-style docstring via the ``docstring_generation``
       template.
    5. Set ``node_type = NodeType.FUNCTION_AUGMENTED``.
    6. Validate signatures with ``ast.parse``.
    7. Add ``INVOCATION`` edges between features that reference each other
       within the same file.

    Args:
        llm_gateway: An object implementing :class:`LLMGatewayProtocol`.
        model: Model identifier forwarded to ``llm_gateway.complete()``.
    """

    def __init__(
        self,
        llm_gateway: LLMGatewayProtocol,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._llm = llm_gateway
        self._model = model

    # ------------------------------------------------------------------
    # RPGEncoder interface
    # ------------------------------------------------------------------

    def encode(self, graph: RPGGraph) -> RPGGraph:
        """Enrich FEATURE nodes with signatures, docstrings, and interface types."""
        if graph.node_count == 0:
            return graph

        # Collect FEATURE-level nodes grouped by file_path
        file_features: dict[str, list[UUID]] = defaultdict(list)
        for nid, node in graph.nodes.items():
            if node.level == NodeLevel.FEATURE and node.file_path:
                file_features[node.file_path].append(nid)

        # Build same-file dependency map from existing DATA_FLOW / INVOCATION edges
        same_file_deps = self._build_same_file_deps(graph)

        # Process each file group
        for file_path, feature_ids in file_features.items():
            self._process_file_group(
                graph, file_path, feature_ids, same_file_deps
            )

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate that FEATURE nodes have valid signatures and interface types."""
        errors: list[str] = []
        warnings: list[str] = []

        for nid, node in graph.nodes.items():
            if node.level != NodeLevel.FEATURE:
                continue
            if node.file_path is None:
                # Features without file_path are structural; skip them.
                continue

            # Must have interface_type
            if node.interface_type is None:
                errors.append(
                    f"Feature {nid} ({node.name}): missing interface_type"
                )

            # Must have node_type == FUNCTION_AUGMENTED
            if node.node_type != NodeType.FUNCTION_AUGMENTED:
                warnings.append(
                    f"Feature {nid} ({node.name}): node_type is "
                    f"{node.node_type.value}, expected FUNCTION_AUGMENTED"
                )

            # Signature must exist and be valid
            if node.signature is None:
                errors.append(
                    f"Feature {nid} ({node.name}): missing signature"
                )
            elif not _validate_signature_syntax(node.signature):
                errors.append(
                    f"Feature {nid} ({node.name}): invalid signature syntax: "
                    f"{node.signature!r}"
                )

            # Docstring should exist
            if node.docstring is None:
                warnings.append(
                    f"Feature {nid} ({node.name}): missing docstring"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_same_file_deps(
        self, graph: RPGGraph
    ) -> dict[UUID, set[UUID]]:
        """Build a mapping of node -> set of same-file dependencies.

        Only considers DATA_FLOW and INVOCATION edges where both endpoints
        share the same ``file_path``.
        """
        dep_types = {EdgeType.DATA_FLOW, EdgeType.INVOCATION}
        deps: dict[UUID, set[UUID]] = defaultdict(set)

        for edge in graph.edges.values():
            if edge.edge_type not in dep_types:
                continue
            src = graph.nodes.get(edge.source_id)
            tgt = graph.nodes.get(edge.target_id)
            if (
                src
                and tgt
                and src.file_path
                and src.file_path == tgt.file_path
            ):
                deps[edge.source_id].add(edge.target_id)
                deps[edge.target_id].add(edge.source_id)

        return deps

    def _process_file_group(
        self,
        graph: RPGGraph,
        file_path: str,
        feature_ids: list[UUID],
        same_file_deps: dict[UUID, set[UUID]],
    ) -> None:
        """Process all features within a single file."""
        file_id_set = set(feature_ids)

        # Partition into independent and interdependent groups
        interdependent_ids: set[UUID] = set()
        for fid in feature_ids:
            local_deps = same_file_deps.get(fid, set()) & file_id_set
            if local_deps:
                interdependent_ids.add(fid)
                interdependent_ids.update(local_deps)

        independent_ids = [
            fid for fid in feature_ids if fid not in interdependent_ids
        ]

        # --- Independent features → FUNCTION ---
        for fid in independent_ids:
            node = graph.nodes[fid]
            func_name = _safe_function_name(node.name)
            self._enrich_node(
                node,
                interface_type=InterfaceType.FUNCTION,
                func_name=func_name,
            )

        # --- Interdependent features → CLASS + METHOD ---
        if len(interdependent_ids) >= _MIN_CLASS_GROUP_SIZE:
            self._process_class_group(
                graph, file_path, sorted(interdependent_ids), same_file_deps
            )
        else:
            # Fewer than threshold → treat as individual functions
            for fid in interdependent_ids:
                node = graph.nodes[fid]
                func_name = _safe_function_name(node.name)
                self._enrich_node(
                    node,
                    interface_type=InterfaceType.FUNCTION,
                    func_name=func_name,
                )

    def _process_class_group(
        self,
        graph: RPGGraph,
        file_path: str,
        member_ids: list[UUID],
        same_file_deps: dict[UUID, set[UUID]],
    ) -> None:
        """Create a class grouping for interdependent features.

        Sets up the first node (alphabetically by name) as the CLASS node
        and the rest as METHOD nodes.  Also adds INVOCATION edges between
        members that reference each other.
        """
        # Sort by name for determinism
        member_ids_sorted = sorted(
            member_ids, key=lambda mid: graph.nodes[mid].name
        )

        # Pick a class name from the file_path stem
        stem = file_path.rsplit("/", 1)[-1].removesuffix(".py")
        class_name = _safe_class_name(stem)

        # Enrich each member as METHOD
        for mid in member_ids_sorted:
            node = graph.nodes[mid]
            method_name = _safe_function_name(node.name)
            self._enrich_node(
                node,
                interface_type=InterfaceType.METHOD,
                func_name=method_name,
                class_name=class_name,
            )

        # Add INVOCATION edges between members that reference each other
        file_id_set = set(member_ids_sorted)
        added_pairs: set[tuple[UUID, UUID]] = set()

        # Collect existing INVOCATION edge pairs so we don't duplicate
        existing_inv: set[tuple[UUID, UUID]] = set()
        for edge in graph.edges.values():
            if edge.edge_type == EdgeType.INVOCATION:
                existing_inv.add((edge.source_id, edge.target_id))

        for mid in member_ids_sorted:
            local_deps = same_file_deps.get(mid, set()) & file_id_set
            for dep_id in local_deps:
                pair = (mid, dep_id)
                if (
                    pair not in added_pairs
                    and pair not in existing_inv
                    and mid != dep_id
                ):
                    graph.add_edge(
                        RPGEdge(
                            source_id=mid,
                            target_id=dep_id,
                            edge_type=EdgeType.INVOCATION,
                        )
                    )
                    added_pairs.add(pair)

    def _enrich_node(
        self,
        node: Any,  # RPGNode – avoid circular import typing
        *,
        interface_type: InterfaceType,
        func_name: str,
        class_name: str | None = None,
    ) -> None:
        """Set interface_type, signature, docstring, and node_type on a node."""
        # Generate signature
        signature = self._generate_signature(
            func_name=func_name,
            description=node.name,
            class_name=class_name,
        )

        # Validate and fall back if invalid
        if not _validate_signature_syntax(signature):
            logger.warning(
                "LLM-generated signature for %s is invalid; using fallback",
                node.name,
            )
            if interface_type == InterfaceType.METHOD:
                signature = f"def {func_name}(self) -> None:"
            else:
                signature = f"def {func_name}() -> None:"

        # Generate docstring
        docstring = self._generate_docstring(
            func_name=func_name,
            signature=signature,
        )

        # Update the node fields.
        # Note: Pydantic validators require interface_type and signature to
        # be set together for FUNCTION_AUGMENTED node_type.  We set signature
        # first, then interface_type, then node_type.
        node.signature = signature
        node.interface_type = interface_type
        node.node_type = NodeType.FUNCTION_AUGMENTED
        node.docstring = docstring

        node.metadata["llm_signature_generated"] = True

    def _generate_signature(
        self,
        func_name: str,
        description: str,
        class_name: str | None = None,
    ) -> str:
        """Call the LLM to generate a typed Python function signature.

        Args:
            func_name: The function/method name.
            description: Description of what the function does.
            class_name: If this is a method, the enclosing class name.

        Returns:
            A ``def ...`` signature line.
        """
        prompt = (
            f"Generate a Python function signature for a function named "
            f"'{func_name}' that {description}."
        )
        if class_name:
            prompt += f" This is a method of class '{class_name}'."
        prompt += (
            " Return ONLY the def line with type hints, ending with a colon. "
            "Example: def process(self, data: list[str]) -> dict[str, int]:"
        )

        try:
            raw = self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
            )
            # Clean up: take the first line that starts with 'def '
            for line in raw.strip().splitlines():
                stripped = line.strip()
                if stripped.startswith("def "):
                    return stripped
            # If LLM didn't return a proper def line, use the raw output
            return raw.strip()
        except Exception:
            logger.exception(
                "LLM signature generation failed for %s", func_name
            )
            if class_name:
                return f"def {func_name}(self) -> None:"
            return f"def {func_name}() -> None:"

    def _generate_docstring(
        self,
        func_name: str,
        signature: str,
    ) -> str:
        """Call the LLM to generate a Google-style docstring.

        Args:
            func_name: The function name.
            signature: The generated function signature.

        Returns:
            A Google-style docstring (without triple quotes).
        """
        prompt = (
            f"Generate a Google-style docstring for the following Python function.\n\n"
            f"Signature: {signature}\n\n"
            f"Return ONLY the docstring content (without triple quotes)."
        )

        try:
            raw = self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
            )
            return raw.strip()
        except Exception:
            logger.exception(
                "LLM docstring generation failed for %s", func_name
            )
            return f"{func_name}: auto-generated docstring."
