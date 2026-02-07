"""Localization orchestrator combining Serena and RPG fuzzy search.

Implements a two-stage localization strategy:
1. Try Serena exact lookup first (fast, precise)
2. Fall back to RPG fuzzy search if Serena fails

Classes:
    LocalizationOrchestrator -- Coordinated localization with fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from zerorepo.codegen.localization import (
    LocalizationTracker,
    RPGFuzzySearch,
)
from zerorepo.codegen.localization_models import LocalizationResult
from zerorepo.codegen.serena_editing import SerenaEditor
from zerorepo.models.node import RPGNode

logger = logging.getLogger(__name__)


class LocalizationOrchestrator:
    """Coordinated localization using Serena-first with RPG fallback.

    Strategy: Try Serena exact symbol lookup first (fast, precise),
    then fall back to RPG fuzzy search if Serena is unavailable
    or returns no results.

    All attempts are logged via the LocalizationTracker.

    Args:
        serena_editor: A SerenaEditor for exact symbol lookup.
        fuzzy_search: An RPGFuzzySearch for semantic search.
        tracker: A LocalizationTracker for query logging.
    """

    def __init__(
        self,
        serena_editor: SerenaEditor,
        fuzzy_search: RPGFuzzySearch,
        tracker: LocalizationTracker | None = None,
    ) -> None:
        self._serena = serena_editor
        self._fuzzy = fuzzy_search
        self._tracker = tracker or LocalizationTracker()

    @property
    def tracker(self) -> LocalizationTracker:
        """Return the underlying localization tracker."""
        return self._tracker

    def localize_bug(
        self,
        node: RPGNode,
        error_message: str,
    ) -> LocalizationResult | None:
        """Localize the source of a bug for an RPG node.

        Strategy:
        1. Extract function name from the error traceback.
        2. Try Serena exact lookup first.
        3. Fall back to RPG fuzzy search if Serena fails.
        4. Log all attempts via the tracker.

        Args:
            node: The RPG node that failed tests.
            error_message: The error message or traceback.

        Returns:
            A LocalizationResult if the bug location is found,
            None if all strategies fail.
        """
        # Extract candidate function name from traceback
        func_name = self._extract_function_name(error_message)
        search_query = func_name or node.name

        # Stage 1: Try Serena exact lookup
        if not self._tracker.has_queried(search_query, "serena"):
            result = self._try_serena(search_query, node)
            if result is not None:
                return result

        # Stage 2: Fall back to RPG fuzzy search
        fuzzy_query = f"{node.name} {error_message[:200]}"
        if not self._tracker.has_queried(fuzzy_query, "rpg_fuzzy"):
            result = self._try_fuzzy(fuzzy_query, node)
            if result is not None:
                return result

        return None

    def _try_serena(
        self,
        query: str,
        node: RPGNode,
    ) -> LocalizationResult | None:
        """Attempt exact symbol lookup via Serena.

        Args:
            query: The symbol name to search for.
            node: The RPG node context.

        Returns:
            A LocalizationResult if found, None otherwise.
        """
        symbols = self._serena.find_symbol(query)

        self._tracker.log_query(
            query=query,
            tool="serena",
            results_count=len(symbols),
        )

        if symbols:
            sym = symbols[0]
            return LocalizationResult(
                node_id=node.id,
                symbol_name=sym.name,
                filepath=sym.filepath,
                line=sym.line,
                score=1.0,
                source="serena",
                context=sym.docstring or "",
            )

        return None

    def _try_fuzzy(
        self,
        query: str,
        node: RPGNode,
    ) -> LocalizationResult | None:
        """Attempt semantic search via RPG fuzzy search.

        Args:
            query: The search query text.
            node: The RPG node context.

        Returns:
            The best LocalizationResult if found, None otherwise.
        """
        results = self._fuzzy.search(query, top_k=3)

        self._tracker.log_query(
            query=query,
            tool="rpg_fuzzy",
            results_count=len(results),
        )

        if results:
            best = results[0]
            return best

        return None

    @staticmethod
    def _extract_function_name(error_message: str) -> str | None:
        """Extract a function name from a Python traceback.

        Looks for patterns like 'in function_name' or
        'File "...", line N, in function_name'.

        Args:
            error_message: The error message or traceback text.

        Returns:
            The extracted function name, or None if not found.
        """
        # Match: File "...", line N, in function_name
        match = re.search(
            r'File\s+"[^"]+",\s+line\s+\d+,\s+in\s+(\w+)',
            error_message,
        )
        if match:
            name = match.group(1)
            # Exclude module-level markers
            if name not in ("<module>", "<lambda>"):
                return name

        # Match: in function_name (simpler pattern)
        match = re.search(r"\bin\s+(\w+)\s*$", error_message, re.MULTILINE)
        if match:
            name = match.group(1)
            if name not in ("<module>", "<lambda>"):
                return name

        return None
