"""SerenaValidator -- compares RPG planned structure against actual code via Serena.

Epic 3.7: Compares the planned RPG file/interface structure against
existing code symbols obtained via the Serena MCP client, reporting drift
between plan and reality.  If no Serena client is provided or Serena errors
out, the validator gracefully degrades to a SKIPPED report.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from zerorepo.models.enums import NodeLevel
from zerorepo.models.graph import RPGGraph
from zerorepo.rpg_enrichment.base import RPGEncoder
from zerorepo.rpg_enrichment.models import ValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serena client protocol (duck-typed for testability)
# ---------------------------------------------------------------------------


class SerenaClientProtocol(Protocol):
    """Minimal interface expected from a Serena MCP client.

    Matches the ``call_tool`` API of :class:`zerorepo.serena.client.MCPClient`.
    """

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Drift thresholds (as percentages, 0-100)
# ---------------------------------------------------------------------------

_LOW_DRIFT_THRESHOLD = 5.0  # percent
_HIGH_DRIFT_THRESHOLD = 15.0  # percent


# ---------------------------------------------------------------------------
# Drift report helpers
# ---------------------------------------------------------------------------


def _empty_report(recommendation: str = "SKIPPED") -> dict[str, Any]:
    """Return an empty validation report.

    Args:
        recommendation: The recommendation string (default ``'SKIPPED'``).

    Returns:
        A drift report dictionary with zeroed-out fields.
    """
    return {
        "missing_files": [],
        "extra_files": [],
        "signature_mismatches": [],
        "drift_percentage": 0.0,
        "recommendation": recommendation,
    }


def _compute_recommendation(drift_pct: float) -> str:
    """Determine the recommendation based on drift percentage.

    Args:
        drift_pct: Drift percentage (0-100).

    Returns:
        One of ``'PROCEED'``, ``'PROCEED_WITH_CAUTION'``, or
        ``'MANUAL_RECONCILIATION'``.
    """
    if drift_pct < _LOW_DRIFT_THRESHOLD:
        return "PROCEED"
    elif drift_pct < _HIGH_DRIFT_THRESHOLD:
        return "PROCEED_WITH_CAUTION"
    else:
        return "MANUAL_RECONCILIATION"


# ---------------------------------------------------------------------------
# SerenaValidator
# ---------------------------------------------------------------------------


class SerenaValidator(RPGEncoder):
    """Compare RPG planned file structure against actual code via Serena MCP.

    Strategy:
    1. Collect all distinct ``file_path`` values from the RPG graph.
    2. If a Serena client is available, call ``get_symbols_overview`` to
       retrieve actual file/symbol information from the codebase.
    3. Compare planned vs. actual files:
       - ``missing_files``: in RPG but not in actual code.
       - ``extra_files``: in actual code but not in RPG.
       - ``signature_mismatches``: planned vs. actual signature differences.
    4. Compute ``drift_percentage`` (0-100) and produce a recommendation:
       - ``< 5%`` drift -> ``PROCEED``
       - ``5-15%`` drift -> ``PROCEED_WITH_CAUTION``
       - ``> 15%`` drift -> ``MANUAL_RECONCILIATION``
    5. Set ``serena_validated = True`` on nodes whose ``file_path`` exists
       in the actual codebase.
    6. Store the drift report in ``graph.metadata['validation_report']``.

    Graceful degradation: if no Serena client is provided or Serena errors
    out, produce an empty report with ``recommendation = 'SKIPPED'``.

    Args:
        serena_client: Optional Serena MCP client (must implement ``call_tool``).
        project_path: Optional path to activate in Serena.
    """

    def __init__(
        self,
        serena_client: Optional[SerenaClientProtocol] = None,
        project_path: str | None = None,
    ) -> None:
        self._client = serena_client
        self._project_path = project_path

    # ------------------------------------------------------------------
    # RPGEncoder interface
    # ------------------------------------------------------------------

    def encode(self, graph: RPGGraph, spec: Any | None = None, baseline: RPGGraph | None = None) -> RPGGraph:
        """Run Serena validation and store drift report in graph metadata."""
        if graph.node_count == 0:
            graph.metadata["validation_report"] = _empty_report("SKIPPED")
            return graph

        if self._client is None:
            logger.info("No Serena client provided; skipping validation.")
            graph.metadata["validation_report"] = _empty_report("SKIPPED")
            return graph

        try:
            report = self._run_validation(graph)
            graph.metadata["validation_report"] = report
        except Exception:
            logger.exception("Serena validation failed; using SKIPPED report.")
            graph.metadata["validation_report"] = _empty_report("SKIPPED")

        return graph

    def validate(self, graph: RPGGraph) -> ValidationResult:
        """Validate that the drift report exists and is well-formed."""
        errors: list[str] = []
        warnings: list[str] = []

        report = graph.metadata.get("validation_report")
        if report is None:
            errors.append("Missing validation_report in graph metadata")
            return ValidationResult(passed=False, errors=errors)

        # Check required keys
        required_keys = {
            "missing_files",
            "extra_files",
            "signature_mismatches",
            "drift_percentage",
            "recommendation",
        }
        missing_keys = required_keys - set(report.keys())
        if missing_keys:
            errors.append(
                f"validation_report missing keys: {sorted(missing_keys)}"
            )

        # Check recommendation is valid
        valid_recommendations = {
            "PROCEED",
            "PROCEED_WITH_CAUTION",
            "MANUAL_RECONCILIATION",
            "SKIPPED",
        }
        rec = report.get("recommendation")
        if rec not in valid_recommendations:
            errors.append(
                f"Invalid recommendation: {rec!r}. "
                f"Expected one of {sorted(valid_recommendations)}"
            )

        # Warnings for high drift
        drift = report.get("drift_percentage", 0.0)
        if drift >= _HIGH_DRIFT_THRESHOLD:
            warnings.append(
                f"High drift detected: {drift:.1f}% -- manual reconciliation recommended"
            )
        elif drift >= _LOW_DRIFT_THRESHOLD:
            warnings.append(
                f"Moderate drift detected: {drift:.1f}% -- proceed with caution"
            )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_validation(self, graph: RPGGraph) -> dict[str, Any]:
        """Execute the full Serena validation workflow.

        Args:
            graph: The RPG graph to validate.

        Returns:
            A drift report dictionary.
        """
        assert self._client is not None

        # 1. Activate project if path is specified
        if self._project_path:
            try:
                self._client.call_tool(
                    "activate_project",
                    {"project_path": self._project_path},
                )
            except Exception:
                logger.warning("Failed to activate project in Serena")

        # 2. Get actual files from Serena
        actual_files = self._get_actual_files()

        # 3. Collect planned file_paths from RPG
        planned_files = self._collect_planned_files(graph)

        # 4. Compute drift
        planned_set = set(planned_files)
        actual_set = set(actual_files)

        missing_files = sorted(planned_set - actual_set)
        extra_files = sorted(actual_set - planned_set)

        # 5. Signature mismatches (compare where both exist)
        signature_mismatches = self._check_signature_mismatches(
            graph, actual_set
        )

        # 6. Compute drift percentage (0-100)
        total_files = len(planned_set | actual_set)
        if total_files == 0:
            drift_pct = 0.0
        else:
            drift_items = len(missing_files) + len(extra_files) + len(signature_mismatches)
            drift_pct = (drift_items / total_files) * 100.0

        recommendation = _compute_recommendation(drift_pct)

        # 7. Mark validated nodes
        for nid, node in graph.nodes.items():
            if node.file_path and node.file_path in actual_set:
                node.serena_validated = True

        return {
            "missing_files": missing_files,
            "extra_files": extra_files,
            "signature_mismatches": signature_mismatches,
            "drift_percentage": round(drift_pct, 2),
            "recommendation": recommendation,
        }

    def _get_actual_files(self) -> list[str]:
        """Query Serena for actual files in the project.

        Returns:
            A list of file paths present in the actual codebase.
        """
        assert self._client is not None

        try:
            result = self._client.call_tool(
                "get_symbols_overview",
                {"include_files": True},
            )
        except Exception:
            logger.exception("Serena get_symbols_overview failed")
            return []

        # Extract file paths from the Serena response.
        # The response format varies; handle common patterns.
        files: list[str] = []
        if isinstance(result, dict):
            raw_files = result.get("files", result.get("symbols", []))
            if isinstance(raw_files, list):
                for item in raw_files:
                    if isinstance(item, str):
                        files.append(item)
                    elif isinstance(item, dict):
                        fp = item.get("file_path", item.get("path", ""))
                        if fp:
                            files.append(fp)

        return files

    @staticmethod
    def _collect_planned_files(graph: RPGGraph) -> list[str]:
        """Collect all distinct file_path values from RPG nodes.

        Args:
            graph: The RPG graph.

        Returns:
            Sorted list of unique planned file paths.
        """
        file_paths: set[str] = set()
        for node in graph.nodes.values():
            if node.file_path:
                file_paths.add(node.file_path)
        return sorted(file_paths)

    def _check_signature_mismatches(
        self,
        graph: RPGGraph,
        actual_files: set[str],
    ) -> list[dict[str, Any]]:
        """Compare planned signatures against actual code structure.

        For files that exist both in the RPG plan and in the actual code,
        this queries Serena for the file's symbols and checks whether
        planned function/class names appear.

        Returns:
            List of mismatch dictionaries.
        """
        if not self._client:
            return []

        mismatches: list[dict[str, Any]] = []

        # Group nodes by file for efficiency
        file_nodes: dict[str, list[Any]] = {}
        for node in graph.nodes.values():
            if (
                node.file_path
                and node.file_path in actual_files
                and node.signature
            ):
                file_nodes.setdefault(node.file_path, []).append(node)

        for file_path, nodes in file_nodes.items():
            try:
                symbols_result = self._client.call_tool(
                    "get_symbols_overview",
                    {"file_path": file_path},
                )
            except Exception:
                logger.debug(
                    "Could not get symbols for %s; skipping mismatch check",
                    file_path,
                )
                continue

            # Extract actual symbol names
            actual_symbols: set[str] = set()
            if isinstance(symbols_result, dict):
                for sym in symbols_result.get("symbols", []):
                    if isinstance(sym, dict):
                        actual_symbols.add(sym.get("name", ""))
                    elif isinstance(sym, str):
                        actual_symbols.add(sym)

            for node in nodes:
                func_name = self._extract_name_from_signature(node.signature)
                if func_name and actual_symbols and func_name not in actual_symbols:
                    mismatches.append({
                        "file_path": file_path,
                        "node_name": node.name,
                        "planned_signature": node.signature,
                        "actual_signature": None,
                    })

        return mismatches

    @staticmethod
    def _extract_name_from_signature(signature: str) -> str | None:
        """Extract the function/class name from a signature string.

        Args:
            signature: A ``def ...`` or ``class ...`` line.

        Returns:
            The extracted name, or None if unparseable.
        """
        sig = signature.strip()
        if sig.startswith("def "):
            paren_idx = sig.find("(")
            if paren_idx > 4:
                return sig[4:paren_idx].strip()
        elif sig.startswith("class "):
            # Find end at ( or :
            paren_idx = sig.find("(")
            colon_idx = sig.find(":")
            candidates = [p for p in [paren_idx, colon_idx] if p > 6]
            if candidates:
                end = min(candidates)
                return sig[6:end].strip()
        return None
