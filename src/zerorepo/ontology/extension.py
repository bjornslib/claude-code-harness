"""Domain Extension API for the Feature Ontology Service.

Implements Task 2.1.5 of PRD-RPG-P2-001: accepts CSV uploads, merges
custom features into the ontology with conflict resolution, and
automatically re-embeds new/updated features.

CSV format expected::

    feature_id,parent_id,name,description,tags,level
    auth,software,Authentication,User auth & identity,"security,identity",1
    auth.jwt,auth,JWT Tokens,JSON Web Tokens for session management,"jwt,tokens",2

Example usage::

    api = OntologyExtensionAPI(store=my_store, embedder=my_embedder)
    result = api.extend_from_csv(Path("custom_features.csv"))
    print(result)  # ExtensionResult(added=95, updated=5, skipped=0, ...)

    # Or extend from FeatureNode list directly
    result = api.extend(nodes, conflict_resolution="override")
"""

from __future__ import annotations

import csv
import io
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zerorepo.ontology.chromadb_store import OntologyChromaStore
from zerorepo.ontology.embeddings import EmbeddingResult, FeatureEmbedder
from zerorepo.ontology.models import FeatureNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CSV column specification (matches PRD output format)
# ---------------------------------------------------------------------------

# Required CSV columns
REQUIRED_COLUMNS = {"feature_id", "name", "level"}

# All recognized columns
ALL_COLUMNS = {"feature_id", "parent_id", "name", "description", "tags", "level"}


class ConflictResolution(str, Enum):
    """Strategy for handling feature ID conflicts during merge.

    OVERRIDE: New features replace existing ones with the same ID.
    SKIP: Existing features are kept; new duplicates are skipped.
    ERROR: Raise an error on any conflict.
    """

    OVERRIDE = "override"
    SKIP = "skip"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class ExtensionResult(BaseModel):
    """Result of an ontology extension operation."""

    model_config = ConfigDict(frozen=True)

    added: int = Field(
        ..., ge=0, description="Number of new features added"
    )
    updated: int = Field(
        ..., ge=0, description="Number of existing features updated (overridden)"
    )
    skipped: int = Field(
        ..., ge=0, description="Number of features skipped (conflicts in skip mode)"
    )
    errors: int = Field(
        ..., ge=0, description="Number of features that failed validation"
    )
    total_processed: int = Field(
        ..., ge=0, description="Total number of features processed from input"
    )
    embedding_result: Optional[EmbeddingResult] = Field(
        default=None,
        description="Result of the re-embedding step (None if embedding skipped)",
    )
    error_details: list[str] = Field(
        default_factory=list,
        description="Human-readable error messages for failed rows",
    )

    @property
    def success_count(self) -> int:
        """Number of features successfully added or updated."""
        return self.added + self.updated

    @property
    def success_rate(self) -> float:
        """Fraction of successfully processed features."""
        if self.total_processed == 0:
            return 1.0
        return self.success_count / self.total_processed

    def __repr__(self) -> str:
        return (
            f"ExtensionResult(added={self.added}, "
            f"updated={self.updated}, "
            f"skipped={self.skipped}, "
            f"errors={self.errors}, "
            f"total={self.total_processed})"
        )


class CSVParseError(Exception):
    """Raised when CSV parsing fails due to format or content errors."""


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def parse_csv_to_nodes(
    csv_content: str,
    source_label: str = "csv-upload",
) -> tuple[list[FeatureNode], list[str]]:
    """Parse CSV content into a list of FeatureNodes.

    Expected CSV columns: feature_id, parent_id, name, description, tags, level

    Args:
        csv_content: Raw CSV string content.
        source_label: Label to add to node metadata for provenance tracking.

    Returns:
        A tuple of (valid_nodes, error_messages).

    Raises:
        CSVParseError: If the CSV has missing required columns or is empty.
    """
    if not csv_content or not csv_content.strip():
        raise CSVParseError("CSV content is empty")

    reader = csv.DictReader(io.StringIO(csv_content))

    if reader.fieldnames is None:
        raise CSVParseError("CSV has no header row")

    # Normalize column names (strip whitespace, lowercase)
    actual_columns = {col.strip().lower() for col in reader.fieldnames}

    # Check required columns
    missing = REQUIRED_COLUMNS - actual_columns
    if missing:
        raise CSVParseError(
            f"CSV is missing required columns: {', '.join(sorted(missing))}. "
            f"Required: {', '.join(sorted(REQUIRED_COLUMNS))}. "
            f"Found: {', '.join(sorted(actual_columns))}"
        )

    nodes: list[FeatureNode] = []
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):  # start=2 (row 1 is header)
        # Normalize keys
        normalized = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

        try:
            node = _parse_row(normalized, source_label)
            nodes.append(node)
        except (ValueError, Exception) as exc:
            errors.append(f"Row {row_num}: {exc}")

    if not nodes and not errors:
        raise CSVParseError("CSV contains no data rows")

    return nodes, errors


def parse_csv_file(
    file_path: Path,
    encoding: str = "utf-8",
    source_label: str | None = None,
) -> tuple[list[FeatureNode], list[str]]:
    """Parse a CSV file into FeatureNodes.

    Args:
        file_path: Path to the CSV file.
        encoding: File encoding. Defaults to UTF-8.
        source_label: Provenance label. Defaults to filename.

    Returns:
        A tuple of (valid_nodes, error_messages).

    Raises:
        FileNotFoundError: If the file doesn't exist.
        CSVParseError: If the CSV format is invalid.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    if not file_path.is_file():
        raise CSVParseError(f"Path is not a file: {file_path}")

    label = source_label or file_path.stem
    content = file_path.read_text(encoding=encoding)
    return parse_csv_to_nodes(content, source_label=label)


def _parse_row(row: dict[str, str], source_label: str) -> FeatureNode:
    """Parse a single CSV row into a FeatureNode.

    Args:
        row: Normalized row dict (lowercase keys, stripped values).
        source_label: Provenance label for metadata.

    Returns:
        A validated FeatureNode.

    Raises:
        ValueError: If the row has invalid data.
    """
    feature_id = row.get("feature_id", "").strip()
    if not feature_id:
        raise ValueError("feature_id is required and cannot be empty")

    name = row.get("name", "").strip()
    if not name:
        raise ValueError(f"name is required for feature '{feature_id}'")

    # Parse level
    level_str = row.get("level", "").strip()
    if not level_str:
        raise ValueError(f"level is required for feature '{feature_id}'")
    try:
        level = int(level_str)
    except ValueError:
        raise ValueError(
            f"level must be an integer for feature '{feature_id}', got '{level_str}'"
        )
    if level < 0:
        raise ValueError(
            f"level must be non-negative for feature '{feature_id}', got {level}"
        )

    # Optional fields
    parent_id = row.get("parent_id", "").strip() or None
    description = row.get("description", "").strip() or None

    # Parse tags (comma-separated)
    tags_str = row.get("tags", "").strip()
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    return FeatureNode(
        id=feature_id,
        name=name,
        description=description,
        parent_id=parent_id,
        level=level,
        tags=tags,
        metadata={"source": source_label},
    )


# ---------------------------------------------------------------------------
# Extension API
# ---------------------------------------------------------------------------


class OntologyExtensionAPI:
    """API for extending the feature ontology with custom features.

    Provides CSV upload, merge with conflict resolution, and automatic
    re-embedding of new/updated features.

    Example::

        api = OntologyExtensionAPI(store=store, embedder=embedder)

        # From CSV file
        result = api.extend_from_csv(Path("features.csv"))

        # From CSV string
        result = api.extend_from_csv_string(csv_content)

        # From FeatureNode list
        result = api.extend(nodes, conflict_resolution="override")
    """

    def __init__(
        self,
        store: OntologyChromaStore,
        embedder: FeatureEmbedder | None = None,
    ) -> None:
        """Initialize the extension API.

        Args:
            store: The OntologyChromaStore to extend.
            embedder: Optional FeatureEmbedder for automatic re-embedding.
                If not provided, embedding is skipped.
        """
        self._store = store
        self._embedder = embedder

    @property
    def store(self) -> OntologyChromaStore:
        """Return the underlying store."""
        return self._store

    @property
    def embedder(self) -> FeatureEmbedder | None:
        """Return the embedder, if configured."""
        return self._embedder

    def extend(
        self,
        nodes: list[FeatureNode],
        conflict_resolution: ConflictResolution | str = ConflictResolution.OVERRIDE,
        embed: bool = True,
    ) -> ExtensionResult:
        """Extend the ontology with a list of FeatureNodes.

        Args:
            nodes: List of FeatureNodes to merge into the ontology.
            conflict_resolution: How to handle ID conflicts.
                - "override": Replace existing nodes (default).
                - "skip": Keep existing nodes, skip new duplicates.
                - "error": Raise on any conflict.
            embed: If True and an embedder is configured, automatically
                embed new/updated nodes. Defaults to True.

        Returns:
            An :class:`ExtensionResult` summarising the operation.

        Raises:
            ValueError: If conflict_resolution is "error" and conflicts exist.
        """
        if isinstance(conflict_resolution, str):
            conflict_resolution = ConflictResolution(conflict_resolution)

        added = 0
        updated = 0
        skipped = 0
        errors = 0
        error_details: list[str] = []
        nodes_to_embed: list[FeatureNode] = []

        for node in nodes:
            try:
                existing = self._get_existing_node(node.id)

                if existing is not None:
                    # Conflict: node already exists
                    if conflict_resolution == ConflictResolution.OVERRIDE:
                        self._store.add_node(node)
                        nodes_to_embed.append(node)
                        updated += 1
                        logger.debug(
                            "Override: updated node '%s' (%s -> %s)",
                            node.id,
                            existing.name,
                            node.name,
                        )
                    elif conflict_resolution == ConflictResolution.SKIP:
                        skipped += 1
                        logger.debug(
                            "Skip: kept existing node '%s'", node.id
                        )
                    elif conflict_resolution == ConflictResolution.ERROR:
                        raise ValueError(
                            f"Conflict: feature '{node.id}' already exists "
                            f"and conflict_resolution is 'error'"
                        )
                else:
                    # New node
                    self._store.add_node(node)
                    nodes_to_embed.append(node)
                    added += 1

            except ValueError:
                raise  # Re-raise conflict errors in ERROR mode
            except Exception as exc:
                errors += 1
                error_details.append(f"Node '{node.id}': {exc}")
                logger.warning("Failed to add node '%s': %s", node.id, exc)

        # Re-embed new/updated nodes
        embedding_result = None
        if embed and self._embedder is not None and nodes_to_embed:
            embedding_result = self._embedder.embed_nodes(
                nodes_to_embed, overwrite=True
            )
            # Update embeddings in store
            for node in nodes_to_embed:
                if node.embedding is not None:
                    try:
                        self._store.add_node(node)
                    except Exception as exc:
                        logger.warning(
                            "Failed to update embedding for '%s': %s",
                            node.id,
                            exc,
                        )

        result = ExtensionResult(
            added=added,
            updated=updated,
            skipped=skipped,
            errors=errors,
            total_processed=len(nodes),
            embedding_result=embedding_result,
            error_details=error_details,
        )

        logger.info(
            "Extension complete: %d added, %d updated, %d skipped, %d errors",
            added,
            updated,
            skipped,
            errors,
        )

        return result

    def extend_from_csv(
        self,
        file_path: Path,
        conflict_resolution: ConflictResolution | str = ConflictResolution.OVERRIDE,
        embed: bool = True,
        encoding: str = "utf-8",
    ) -> ExtensionResult:
        """Extend the ontology from a CSV file.

        Args:
            file_path: Path to the CSV file.
            conflict_resolution: How to handle ID conflicts.
            embed: Whether to auto-embed new features.
            encoding: File encoding. Defaults to UTF-8.

        Returns:
            An :class:`ExtensionResult` summarising the operation.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            CSVParseError: If the CSV format is invalid.
        """
        nodes, parse_errors = parse_csv_file(
            file_path, encoding=encoding, source_label=file_path.stem
        )

        result = self.extend(
            nodes,
            conflict_resolution=conflict_resolution,
            embed=embed,
        )

        # Merge parse errors into result
        if parse_errors:
            all_errors = list(result.error_details) + parse_errors
            result = ExtensionResult(
                added=result.added,
                updated=result.updated,
                skipped=result.skipped,
                errors=result.errors + len(parse_errors),
                total_processed=result.total_processed + len(parse_errors),
                embedding_result=result.embedding_result,
                error_details=all_errors,
            )

        return result

    def extend_from_csv_string(
        self,
        csv_content: str,
        conflict_resolution: ConflictResolution | str = ConflictResolution.OVERRIDE,
        embed: bool = True,
        source_label: str = "csv-upload",
    ) -> ExtensionResult:
        """Extend the ontology from a CSV string.

        Args:
            csv_content: Raw CSV content as a string.
            conflict_resolution: How to handle ID conflicts.
            embed: Whether to auto-embed new features.
            source_label: Provenance label for tracking.

        Returns:
            An :class:`ExtensionResult` summarising the operation.

        Raises:
            CSVParseError: If the CSV format is invalid.
        """
        nodes, parse_errors = parse_csv_to_nodes(
            csv_content, source_label=source_label
        )

        result = self.extend(
            nodes,
            conflict_resolution=conflict_resolution,
            embed=embed,
        )

        # Merge parse errors
        if parse_errors:
            all_errors = list(result.error_details) + parse_errors
            result = ExtensionResult(
                added=result.added,
                updated=result.updated,
                skipped=result.skipped,
                errors=result.errors + len(parse_errors),
                total_processed=result.total_processed + len(parse_errors),
                embedding_result=result.embedding_result,
                error_details=all_errors,
            )

        return result

    def _get_existing_node(self, feature_id: str) -> FeatureNode | None:
        """Check if a node with the given ID already exists.

        Args:
            feature_id: The feature ID to check.

        Returns:
            The existing FeatureNode, or None if not found.
        """
        try:
            return self._store.get_node(feature_id)
        except (KeyError, Exception):
            return None
