"""Unit tests for the Ontology Domain Extension API.

Tests cover CSV parsing, conflict resolution, re-embedding, and the
OntologyExtensionAPI as defined in Task 2.1.5 of PRD-RPG-P2-001.

All ChromaDB and embedding calls are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from pydantic import ValidationError

from zerorepo.ontology.chromadb_store import OntologyChromaStore
from zerorepo.ontology.embeddings import EmbeddingResult, FeatureEmbedder
from zerorepo.ontology.extension import (
    ALL_COLUMNS,
    CSVParseError,
    ConflictResolution,
    ExtensionResult,
    OntologyExtensionAPI,
    REQUIRED_COLUMNS,
    parse_csv_file,
    parse_csv_to_nodes,
)
from zerorepo.ontology.models import FeatureNode
from zerorepo.vectordb.exceptions import CollectionError


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

VALID_CSV = """\
feature_id,parent_id,name,description,tags,level
auth,,Authentication,User authentication and identity,"security,identity",0
auth.jwt,auth,JWT Tokens,JSON Web Tokens for session management,"jwt,tokens",1
auth.oauth,auth,OAuth 2.0,OAuth 2.0 protocol support,"oauth,security",1
auth.jwt.validation,auth.jwt,JWT Validation,Token validation and refresh,jwt,2
"""

MINIMAL_CSV = """\
feature_id,name,level
simple,Simple Feature,0
child,Child Feature,1
"""

CSV_WITH_ERRORS = """\
feature_id,parent_id,name,description,tags,level
valid,,Valid Node,A valid node,,0
,missing,Missing ID,Has no feature_id,,1
no_level,,No Level,Missing level column,,
bad_level,,Bad Level,Non-integer level,,abc
"""


def _mock_store() -> MagicMock:
    """Create a mock OntologyChromaStore."""
    store = MagicMock(spec=OntologyChromaStore)
    store.is_initialized = True
    # Default: no existing nodes
    store.get_node.side_effect = KeyError("not found")
    store.add_node.return_value = None
    return store


def _mock_embedder() -> MagicMock:
    """Create a mock FeatureEmbedder."""
    embedder = MagicMock(spec=FeatureEmbedder)
    embedder.embed_nodes.return_value = EmbeddingResult(
        total_nodes=0,
        embedded_count=0,
        failed_count=0,
        skipped_count=0,
        elapsed_seconds=0.1,
        model_name="mock-model",
    )
    return embedder


def _make_node(
    node_id: str = "test",
    name: str = "Test",
    level: int = 0,
    parent_id: str | None = None,
) -> FeatureNode:
    """Create a sample FeatureNode."""
    return FeatureNode(
        id=node_id,
        name=name,
        level=level,
        parent_id=parent_id,
    )


# ---------------------------------------------------------------------------
# CSV Parsing Tests
# ---------------------------------------------------------------------------


class TestParseCSVToNodes:
    """Test CSV string parsing into FeatureNodes."""

    def test_parse_valid_csv(self) -> None:
        """Parse a valid CSV with all columns."""
        nodes, errors = parse_csv_to_nodes(VALID_CSV)
        assert len(nodes) == 4
        assert len(errors) == 0

    def test_parse_node_fields(self) -> None:
        """Parsed nodes have correct fields."""
        nodes, _ = parse_csv_to_nodes(VALID_CSV)
        auth = nodes[0]
        assert auth.id == "auth"
        assert auth.name == "Authentication"
        assert auth.description == "User authentication and identity"
        assert auth.parent_id is None  # Empty string -> None
        assert auth.level == 0
        assert "security" in auth.tags
        assert "identity" in auth.tags

    def test_parse_child_nodes(self) -> None:
        """Child nodes have correct parent_id."""
        nodes, _ = parse_csv_to_nodes(VALID_CSV)
        jwt = nodes[1]
        assert jwt.id == "auth.jwt"
        assert jwt.parent_id == "auth"
        assert jwt.level == 1

    def test_parse_minimal_csv(self) -> None:
        """Parse CSV with only required columns."""
        nodes, errors = parse_csv_to_nodes(MINIMAL_CSV)
        assert len(nodes) == 2
        assert len(errors) == 0
        assert nodes[0].id == "simple"
        assert nodes[0].description is None
        assert nodes[0].tags == []

    def test_parse_empty_csv_raises(self) -> None:
        """Empty CSV content raises CSVParseError."""
        with pytest.raises(CSVParseError, match="empty"):
            parse_csv_to_nodes("")

    def test_parse_whitespace_csv_raises(self) -> None:
        """Whitespace-only CSV raises CSVParseError."""
        with pytest.raises(CSVParseError, match="empty"):
            parse_csv_to_nodes("   \n  ")

    def test_parse_header_only_raises(self) -> None:
        """CSV with only header raises CSVParseError."""
        with pytest.raises(CSVParseError, match="no data rows"):
            parse_csv_to_nodes("feature_id,name,level\n")

    def test_parse_missing_required_column_raises(self) -> None:
        """CSV missing required columns raises CSVParseError."""
        csv = "feature_id,name\ntest,Test\n"
        with pytest.raises(CSVParseError, match="missing required columns.*level"):
            parse_csv_to_nodes(csv)

    def test_parse_with_row_errors(self) -> None:
        """CSV with some invalid rows returns valid nodes + errors."""
        nodes, errors = parse_csv_to_nodes(CSV_WITH_ERRORS)
        assert len(nodes) == 1  # Only "valid" row
        assert len(errors) == 3  # missing_id, no_level, bad_level

    def test_parse_source_label(self) -> None:
        """Source label is added to node metadata."""
        nodes, _ = parse_csv_to_nodes(MINIMAL_CSV, source_label="custom")
        assert nodes[0].metadata.get("source") == "custom"

    def test_parse_tags_parsing(self) -> None:
        """Tags are correctly parsed from comma-separated string."""
        csv = 'feature_id,name,level,tags\ntest,Test,0,"a, b , c"\n'
        nodes, _ = parse_csv_to_nodes(csv)
        assert nodes[0].tags == ["a", "b", "c"]

    def test_parse_empty_tags(self) -> None:
        """Empty tags field produces empty list."""
        csv = "feature_id,name,level,tags\ntest,Test,0,\n"
        nodes, _ = parse_csv_to_nodes(csv)
        assert nodes[0].tags == []

    def test_parse_negative_level_error(self) -> None:
        """Negative level produces an error."""
        csv = "feature_id,name,level\ntest,Test,-1\n"
        nodes, errors = parse_csv_to_nodes(csv)
        assert len(nodes) == 0
        assert len(errors) == 1
        assert "non-negative" in errors[0]

    def test_parse_whitespace_column_names(self) -> None:
        """Column names with whitespace are normalized."""
        csv = " feature_id , name , level \ntest,Test,0\n"
        nodes, errors = parse_csv_to_nodes(csv)
        assert len(nodes) == 1
        assert nodes[0].id == "test"


# ---------------------------------------------------------------------------
# CSV File Parsing Tests
# ---------------------------------------------------------------------------


class TestParseCSVFile:
    """Test CSV file parsing."""

    def test_parse_file(self, tmp_path: Path) -> None:
        """Parse a valid CSV file."""
        csv_file = tmp_path / "features.csv"
        csv_file.write_text(VALID_CSV)
        nodes, errors = parse_csv_file(csv_file)
        assert len(nodes) == 4
        assert len(errors) == 0

    def test_parse_file_source_label(self, tmp_path: Path) -> None:
        """Default source label is the file stem."""
        csv_file = tmp_path / "my_features.csv"
        csv_file.write_text(MINIMAL_CSV)
        nodes, _ = parse_csv_file(csv_file)
        assert nodes[0].metadata.get("source") == "my_features"

    def test_parse_file_custom_label(self, tmp_path: Path) -> None:
        """Custom source label overrides filename."""
        csv_file = tmp_path / "features.csv"
        csv_file.write_text(MINIMAL_CSV)
        nodes, _ = parse_csv_file(csv_file, source_label="custom")
        assert nodes[0].metadata.get("source") == "custom"

    def test_parse_nonexistent_file_raises(self) -> None:
        """Nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            parse_csv_file(Path("/nonexistent/features.csv"))

    def test_parse_directory_raises(self, tmp_path: Path) -> None:
        """Directory path raises CSVParseError."""
        with pytest.raises(CSVParseError, match="not a file"):
            parse_csv_file(tmp_path)


# ---------------------------------------------------------------------------
# ConflictResolution Enum Tests
# ---------------------------------------------------------------------------


class TestConflictResolution:
    """Test ConflictResolution enum."""

    def test_values(self) -> None:
        """Enum has expected values."""
        assert ConflictResolution.OVERRIDE.value == "override"
        assert ConflictResolution.SKIP.value == "skip"
        assert ConflictResolution.ERROR.value == "error"

    def test_from_string(self) -> None:
        """Can create from string value."""
        assert ConflictResolution("override") == ConflictResolution.OVERRIDE
        assert ConflictResolution("skip") == ConflictResolution.SKIP
        assert ConflictResolution("error") == ConflictResolution.ERROR


# ---------------------------------------------------------------------------
# ExtensionResult Tests
# ---------------------------------------------------------------------------


class TestExtensionResult:
    """Test ExtensionResult model."""

    def test_create_result(self) -> None:
        """Create a valid result."""
        result = ExtensionResult(
            added=10,
            updated=5,
            skipped=2,
            errors=1,
            total_processed=18,
        )
        assert result.added == 10
        assert result.updated == 5
        assert result.success_count == 15
        assert result.total_processed == 18

    def test_success_rate(self) -> None:
        """Success rate is calculated correctly."""
        result = ExtensionResult(
            added=8,
            updated=2,
            skipped=0,
            errors=0,
            total_processed=10,
        )
        assert result.success_rate == 1.0

    def test_success_rate_with_errors(self) -> None:
        """Success rate with errors."""
        result = ExtensionResult(
            added=6,
            updated=2,
            skipped=1,
            errors=1,
            total_processed=10,
        )
        assert result.success_rate == 0.8

    def test_success_rate_empty(self) -> None:
        """Empty input returns 1.0."""
        result = ExtensionResult(
            added=0,
            updated=0,
            skipped=0,
            errors=0,
            total_processed=0,
        )
        assert result.success_rate == 1.0

    def test_repr(self) -> None:
        """repr is informative."""
        result = ExtensionResult(
            added=10,
            updated=5,
            skipped=2,
            errors=1,
            total_processed=18,
        )
        r = repr(result)
        assert "ExtensionResult" in r
        assert "added=10" in r
        assert "updated=5" in r

    def test_with_error_details(self) -> None:
        """Error details are preserved."""
        result = ExtensionResult(
            added=0,
            updated=0,
            skipped=0,
            errors=2,
            total_processed=2,
            error_details=["Row 2: missing ID", "Row 3: bad level"],
        )
        assert len(result.error_details) == 2

    def test_frozen(self) -> None:
        """ExtensionResult is frozen."""
        result = ExtensionResult(
            added=1, updated=0, skipped=0, errors=0, total_processed=1
        )
        with pytest.raises(ValidationError):
            result.added = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OntologyExtensionAPI Init Tests
# ---------------------------------------------------------------------------


class TestOntologyExtensionAPIInit:
    """Test API initialization."""

    def test_init_with_store(self) -> None:
        """Initialize with store only."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)
        assert api.store is store
        assert api.embedder is None

    def test_init_with_embedder(self) -> None:
        """Initialize with store and embedder."""
        store = _mock_store()
        embedder = _mock_embedder()
        api = OntologyExtensionAPI(store=store, embedder=embedder)
        assert api.store is store
        assert api.embedder is embedder


# ---------------------------------------------------------------------------
# OntologyExtensionAPI.extend Tests
# ---------------------------------------------------------------------------


class TestOntologyExtensionAPIExtend:
    """Test the extend method."""

    def test_extend_empty_list(self) -> None:
        """Extending with empty list returns zero result."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)
        result = api.extend([])
        assert result.total_processed == 0
        assert result.added == 0

    def test_extend_new_nodes(self) -> None:
        """New nodes are added to the store."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)
        nodes = [
            _make_node("a", "A", 0),
            _make_node("b", "B", 1, parent_id="a"),
        ]

        result = api.extend(nodes, embed=False)
        assert result.added == 2
        assert result.updated == 0
        assert result.skipped == 0
        assert store.add_node.call_count == 2

    def test_extend_override_conflict(self) -> None:
        """Override mode replaces existing nodes."""
        store = _mock_store()
        existing = _make_node("a", "Old A", 0)
        store.get_node.side_effect = lambda fid: existing if fid == "a" else (_ for _ in ()).throw(KeyError("not found"))

        api = OntologyExtensionAPI(store=store)
        new_a = _make_node("a", "New A", 0)
        new_b = _make_node("b", "B", 1)

        result = api.extend(
            [new_a, new_b],
            conflict_resolution=ConflictResolution.OVERRIDE,
            embed=False,
        )
        assert result.added == 1  # b is new
        assert result.updated == 1  # a is updated
        assert result.skipped == 0

    def test_extend_skip_conflict(self) -> None:
        """Skip mode keeps existing nodes."""
        store = _mock_store()
        existing = _make_node("a", "Existing A", 0)
        store.get_node.side_effect = lambda fid: existing if fid == "a" else (_ for _ in ()).throw(KeyError("not found"))

        api = OntologyExtensionAPI(store=store)
        new_a = _make_node("a", "New A", 0)
        new_b = _make_node("b", "B", 1)

        result = api.extend(
            [new_a, new_b],
            conflict_resolution=ConflictResolution.SKIP,
            embed=False,
        )
        assert result.added == 1  # b is new
        assert result.updated == 0
        assert result.skipped == 1  # a is skipped

    def test_extend_error_conflict(self) -> None:
        """Error mode raises on conflict."""
        store = _mock_store()
        existing = _make_node("a", "Existing A", 0)
        store.get_node.side_effect = None  # Clear default KeyError
        store.get_node.return_value = existing

        api = OntologyExtensionAPI(store=store)
        new_a = _make_node("a", "New A", 0)

        with pytest.raises(ValueError, match="Conflict.*already exists"):
            api.extend(
                [new_a],
                conflict_resolution=ConflictResolution.ERROR,
                embed=False,
            )

    def test_extend_string_conflict_resolution(self) -> None:
        """String values work for conflict_resolution."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)
        nodes = [_make_node("a", "A", 0)]

        result = api.extend(nodes, conflict_resolution="skip", embed=False)
        assert result.added == 1

    def test_extend_with_embedding(self) -> None:
        """Extend with auto-embedding enabled."""
        store = _mock_store()
        embedder = _mock_embedder()
        embedder.embed_nodes.return_value = EmbeddingResult(
            total_nodes=2,
            embedded_count=2,
            failed_count=0,
            skipped_count=0,
            elapsed_seconds=0.5,
            model_name="mock-model",
        )
        api = OntologyExtensionAPI(store=store, embedder=embedder)
        nodes = [_make_node("a", "A", 0), _make_node("b", "B", 1)]

        result = api.extend(nodes, embed=True)
        assert result.added == 2
        assert result.embedding_result is not None
        assert result.embedding_result.embedded_count == 2
        embedder.embed_nodes.assert_called_once()

    def test_extend_no_embedding_when_disabled(self) -> None:
        """Extend with embed=False skips embedding."""
        store = _mock_store()
        embedder = _mock_embedder()
        api = OntologyExtensionAPI(store=store, embedder=embedder)
        nodes = [_make_node("a", "A", 0)]

        result = api.extend(nodes, embed=False)
        assert result.embedding_result is None
        embedder.embed_nodes.assert_not_called()

    def test_extend_no_embedding_without_embedder(self) -> None:
        """Extend without embedder configured skips embedding."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)
        nodes = [_make_node("a", "A", 0)]

        result = api.extend(nodes, embed=True)
        assert result.embedding_result is None

    def test_extend_store_error_counted(self) -> None:
        """Store errors are counted but don't crash."""
        store = _mock_store()
        store.add_node.side_effect = CollectionError("DB error")
        api = OntologyExtensionAPI(store=store)
        nodes = [_make_node("a", "A", 0)]

        result = api.extend(nodes, embed=False)
        assert result.errors == 1
        assert len(result.error_details) == 1
        assert "DB error" in result.error_details[0]


# ---------------------------------------------------------------------------
# OntologyExtensionAPI.extend_from_csv_string Tests
# ---------------------------------------------------------------------------


class TestOntologyExtensionAPIFromCSVString:
    """Test CSV string extension."""

    def test_extend_from_csv_string(self) -> None:
        """Extend from valid CSV string."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        result = api.extend_from_csv_string(VALID_CSV, embed=False)
        assert result.added == 4
        assert result.errors == 0

    def test_extend_from_csv_string_with_errors(self) -> None:
        """CSV parse errors are included in result."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        result = api.extend_from_csv_string(CSV_WITH_ERRORS, embed=False)
        assert result.added == 1  # Only "valid" row
        assert result.errors == 3  # 3 parse errors
        assert len(result.error_details) == 3

    def test_extend_from_invalid_csv_raises(self) -> None:
        """Invalid CSV raises CSVParseError."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        with pytest.raises(CSVParseError, match="empty"):
            api.extend_from_csv_string("")

    def test_extend_from_csv_string_source_label(self) -> None:
        """Source label is passed through."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        result = api.extend_from_csv_string(
            MINIMAL_CSV, embed=False, source_label="test-upload"
        )
        assert result.added == 2


# ---------------------------------------------------------------------------
# OntologyExtensionAPI.extend_from_csv Tests
# ---------------------------------------------------------------------------


class TestOntologyExtensionAPIFromCSVFile:
    """Test CSV file extension."""

    def test_extend_from_csv_file(self, tmp_path: Path) -> None:
        """Extend from valid CSV file."""
        csv_file = tmp_path / "features.csv"
        csv_file.write_text(VALID_CSV)

        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        result = api.extend_from_csv(csv_file, embed=False)
        assert result.added == 4
        assert result.errors == 0

    def test_extend_from_csv_file_with_errors(self, tmp_path: Path) -> None:
        """CSV file with errors reports them."""
        csv_file = tmp_path / "features.csv"
        csv_file.write_text(CSV_WITH_ERRORS)

        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        result = api.extend_from_csv(csv_file, embed=False)
        assert result.added == 1
        assert result.errors == 3

    def test_extend_from_nonexistent_file(self) -> None:
        """Nonexistent file raises FileNotFoundError."""
        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        with pytest.raises(FileNotFoundError):
            api.extend_from_csv(Path("/nonexistent.csv"), embed=False)

    def test_extend_from_csv_override(self, tmp_path: Path) -> None:
        """Override conflict resolution in CSV file extension."""
        csv_file = tmp_path / "features.csv"
        csv_file.write_text(MINIMAL_CSV)

        store = _mock_store()
        existing = _make_node("simple", "Existing Simple", 0)
        store.get_node.side_effect = lambda fid: existing if fid == "simple" else (_ for _ in ()).throw(KeyError("not found"))

        api = OntologyExtensionAPI(store=store)
        result = api.extend_from_csv(
            csv_file,
            conflict_resolution="override",
            embed=False,
        )
        assert result.updated == 1  # simple overridden
        assert result.added == 1  # child added


# ---------------------------------------------------------------------------
# Integration-style tests (full pipeline)
# ---------------------------------------------------------------------------


class TestExtensionPipeline:
    """Test the complete extension pipeline."""

    def test_full_pipeline_100_features(self) -> None:
        """Test extending with 100 features (acceptance criteria)."""
        # Build CSV with 100 features
        lines = ["feature_id,parent_id,name,description,tags,level"]
        lines.append("root,,Root,Root node,,0")
        for i in range(99):
            lines.append(
                f"feat.{i},root,Feature {i},Description {i},"
                f'"tag-{i},common",1'
            )
        csv_content = "\n".join(lines) + "\n"

        store = _mock_store()
        api = OntologyExtensionAPI(store=store)

        result = api.extend_from_csv_string(csv_content, embed=False)
        assert result.added == 100
        assert result.errors == 0
        assert result.total_processed == 100
        assert store.add_node.call_count == 100

    def test_override_preserves_new_description(self) -> None:
        """Override test: new description takes precedence (acceptance criteria)."""
        store = _mock_store()
        old_node = FeatureNode(
            id="auth",
            name="Authentication",
            description="Old description",
            level=0,
        )
        store.get_node.side_effect = None  # Clear default KeyError
        store.get_node.return_value = old_node

        api = OntologyExtensionAPI(store=store)
        new_node = FeatureNode(
            id="auth",
            name="Authentication v2",
            description="New description",
            level=0,
        )

        result = api.extend(
            [new_node],
            conflict_resolution="override",
            embed=False,
        )

        assert result.updated == 1
        # Verify add_node was called with the NEW node
        store.add_node.assert_called_once_with(new_node)
        call_args = store.add_node.call_args[0][0]
        assert call_args.description == "New description"
        assert call_args.name == "Authentication v2"


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Test that extension classes are importable."""

    def test_import_from_package(self) -> None:
        """Main symbols importable from zerorepo.ontology."""
        from zerorepo.ontology import (
            ConflictResolution,
            ExtensionResult,
            OntologyExtensionAPI,
        )

        assert ConflictResolution is not None
        assert ExtensionResult is not None
        assert OntologyExtensionAPI is not None

    def test_import_from_module(self) -> None:
        """All symbols importable from zerorepo.ontology.extension."""
        from zerorepo.ontology.extension import (
            ALL_COLUMNS,
            CSVParseError,
            ConflictResolution,
            ExtensionResult,
            OntologyExtensionAPI,
            REQUIRED_COLUMNS,
            parse_csv_file,
            parse_csv_to_nodes,
        )

        assert ALL_COLUMNS is not None
        assert CSVParseError is not None
        assert REQUIRED_COLUMNS is not None
        assert parse_csv_to_nodes is not None
        assert parse_csv_file is not None
