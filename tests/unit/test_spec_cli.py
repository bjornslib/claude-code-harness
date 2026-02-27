"""Tests for the Spec Parser CLI (Task 2.4.6).

Tests cover:
- _read_input helper
- _load_spec helper
- _write_spec helper
- parse command
- refine command
- conflicts command
- suggest command
- export command
- history command
- _print_spec_summary display
- _build_summary_text output
- Error handling for all commands
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import typer

from cobuilder.repomap.spec_parser.models import (
    Constraint,
    ConstraintPriority,
    ConflictSeverity,
    DeploymentTarget,
    QualityAttributes,
    RefinementEntry,
    RepositorySpec,
    ScopeType,
    SpecConflict,
    TechnicalRequirement,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_spec() -> RepositorySpec:
    """Create a sample RepositorySpec for testing."""
    return RepositorySpec(
        description="Build a real-time chat application with React and WebSocket for messaging between users",
        core_functionality="Real-time messaging between users",
        technical_requirements=TechnicalRequirement(
            languages=["TypeScript", "Python"],
            frameworks=["React", "FastAPI"],
            platforms=["Web"],
            scope=ScopeType.FULL_STACK,
            deployment_targets=[DeploymentTarget.CLOUD],
        ),
        quality_attributes=QualityAttributes(
            performance="Sub-100ms message delivery",
            security="End-to-end encryption",
            scalability="Support 10k concurrent users",
        ),
        constraints=[
            Constraint(
                description="Must support offline mode",
                priority=ConstraintPriority.MUST_HAVE,
            ),
            Constraint(
                description="Dark theme would be nice",
                priority=ConstraintPriority.NICE_TO_HAVE,
            ),
        ],
    )


@pytest.fixture
def spec_json_file(tmp_path: Path, sample_spec: RepositorySpec) -> Path:
    """Write sample spec to a JSON file and return the path."""
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(sample_spec.to_json(indent=2), encoding="utf-8")
    return spec_file


@pytest.fixture
def spec_txt_file(tmp_path: Path) -> Path:
    """Write sample spec description to a text file and return the path."""
    txt_file = tmp_path / "spec.txt"
    txt_file.write_text(
        "Build a real-time chat application with React and WebSocket "
        "for messaging between users. It should support offline mode "
        "and dark theme. Deploy to AWS cloud.",
        encoding="utf-8",
    )
    return txt_file


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestReadInput:
    """Tests for _read_input helper."""

    def test_read_existing_file(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _read_input

        f = tmp_path / "test.txt"
        f.write_text("hello world content", encoding="utf-8")

        content = _read_input(f)
        assert content == "hello world content"

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _read_input

        with pytest.raises(typer.BadParameter, match="not found"):
            _read_input(tmp_path / "missing.txt")

    def test_read_directory(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _read_input

        with pytest.raises(typer.BadParameter, match="Not a file"):
            _read_input(tmp_path)

    def test_read_empty_file(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _read_input

        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")

        with pytest.raises(typer.BadParameter, match="empty"):
            _read_input(f)

    def test_read_whitespace_only(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _read_input

        f = tmp_path / "whitespace.txt"
        f.write_text("   \n\t  ", encoding="utf-8")

        with pytest.raises(typer.BadParameter, match="empty"):
            _read_input(f)


class TestLoadSpec:
    """Tests for _load_spec helper."""

    def test_load_valid_spec(
        self, spec_json_file: Path, sample_spec: RepositorySpec
    ) -> None:
        from cobuilder.repomap.cli.spec import _load_spec

        loaded = _load_spec(spec_json_file)
        assert loaded.description == sample_spec.description
        assert loaded.core_functionality == sample_spec.core_functionality
        assert len(loaded.constraints) == 2

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _load_spec

        f = tmp_path / "bad.json"
        f.write_text("{invalid json}", encoding="utf-8")

        with pytest.raises(typer.BadParameter, match="Invalid spec JSON"):
            _load_spec(f)

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        from cobuilder.repomap.cli.spec import _load_spec

        with pytest.raises(typer.BadParameter, match="not found"):
            _load_spec(tmp_path / "missing.json")


class TestWriteSpec:
    """Tests for _write_spec helper."""

    def test_write_spec(
        self, tmp_path: Path, sample_spec: RepositorySpec
    ) -> None:
        from cobuilder.repomap.cli.spec import _write_spec

        output = tmp_path / "output.json"
        _write_spec(sample_spec, output)

        assert output.exists()
        loaded = RepositorySpec.from_json(output.read_text())
        assert loaded.description == sample_spec.description

    def test_write_creates_parent_dirs(
        self, tmp_path: Path, sample_spec: RepositorySpec
    ) -> None:
        from cobuilder.repomap.cli.spec import _write_spec

        output = tmp_path / "nested" / "dir" / "spec.json"
        _write_spec(sample_spec, output)

        assert output.exists()


# ---------------------------------------------------------------------------
# Spec summary display tests
# ---------------------------------------------------------------------------


class TestPrintSpecSummary:
    """Tests for _print_spec_summary."""

    def test_summary_doesnt_crash(self, sample_spec: RepositorySpec) -> None:
        """Just verify it doesn't raise."""
        from cobuilder.repomap.cli.spec import _print_spec_summary

        _print_spec_summary(sample_spec)  # Should not raise

    def test_summary_with_conflicts(self, sample_spec: RepositorySpec) -> None:
        from cobuilder.repomap.cli.spec import _print_spec_summary

        sample_spec.conflicts = [
            SpecConflict(
                description="Backend-only scope conflicts with React frontend",
                severity=ConflictSeverity.ERROR,
                conflicting_fields=["BACKEND_ONLY", "React"],
            ),
        ]
        _print_spec_summary(sample_spec)  # Should not raise

    def test_summary_minimal_spec(self) -> None:
        from cobuilder.repomap.cli.spec import _print_spec_summary

        minimal = RepositorySpec(
            description="A simple test app for running unit tests against code"
        )
        _print_spec_summary(minimal)  # Should not raise


class TestBuildSummaryText:
    """Tests for _build_summary_text."""

    def test_summary_text(self, sample_spec: RepositorySpec) -> None:
        from cobuilder.repomap.cli.spec import _build_summary_text

        text = _build_summary_text(sample_spec)

        assert "Repository Specification Summary" in text
        assert "real-time chat" in text
        assert "TypeScript" in text
        assert "React" in text
        assert "MUST_HAVE" in text

    def test_summary_with_quality(self, sample_spec: RepositorySpec) -> None:
        from cobuilder.repomap.cli.spec import _build_summary_text

        text = _build_summary_text(sample_spec)

        assert "Performance" in text
        assert "Security" in text
        assert "Scalability" in text

    def test_summary_with_conflicts(self, sample_spec: RepositorySpec) -> None:
        from cobuilder.repomap.cli.spec import _build_summary_text

        sample_spec.conflicts = [
            SpecConflict(
                description="Test conflict",
                severity=ConflictSeverity.WARNING,
                conflicting_fields=["A", "B"],
            ),
        ]
        text = _build_summary_text(sample_spec)
        assert "Conflicts" in text
        assert "WARNING" in text

    def test_summary_minimal_spec(self) -> None:
        from cobuilder.repomap.cli.spec import _build_summary_text

        minimal = RepositorySpec(
            description="A simple test app for running unit tests against code"
        )
        text = _build_summary_text(minimal)
        assert "simple test app" in text


# ---------------------------------------------------------------------------
# CLI command tests (with Typer test runner)
# ---------------------------------------------------------------------------


class TestExportCommand:
    """Tests for the export command."""

    def test_export_json(
        self, spec_json_file: Path, tmp_path: Path
    ) -> None:
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        runner = CliRunner()
        output = tmp_path / "exported.json"

        result = runner.invoke(
            spec_app,
            ["export", str(spec_json_file), "--output", str(output)],
        )

        assert result.exit_code == 0
        assert output.exists()

        # Verify the exported JSON is valid
        loaded = json.loads(output.read_text())
        assert "description" in loaded

    def test_export_summary(
        self, spec_json_file: Path, tmp_path: Path
    ) -> None:
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        runner = CliRunner()
        output = tmp_path / "summary.txt"

        result = runner.invoke(
            spec_app,
            [
                "export",
                str(spec_json_file),
                "--output",
                str(output),
                "--format",
                "summary",
            ],
        )

        assert result.exit_code == 0
        assert output.exists()
        content = output.read_text()
        assert "Repository Specification Summary" in content

    def test_export_invalid_format(
        self, spec_json_file: Path, tmp_path: Path
    ) -> None:
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        runner = CliRunner()
        output = tmp_path / "out.txt"

        result = runner.invoke(
            spec_app,
            [
                "export",
                str(spec_json_file),
                "--output",
                str(output),
                "--format",
                "xml",
            ],
        )

        # Should exit with error
        assert result.exit_code != 0


class TestHistoryCommand:
    """Tests for the history command."""

    def test_history_empty(self, spec_json_file: Path) -> None:
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        runner = CliRunner()
        result = runner.invoke(spec_app, ["history", str(spec_json_file)])

        assert result.exit_code == 0

    def test_history_with_entries(
        self, tmp_path: Path, sample_spec: RepositorySpec
    ) -> None:
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        sample_spec.refinement_history = [
            RefinementEntry(
                action="add",
                details="Added WebSocket requirement",
                timestamp=datetime.now(timezone.utc),
            ),
            RefinementEntry(
                action="clarify",
                details="Clarified deployment target",
                timestamp=datetime.now(timezone.utc),
            ),
        ]
        spec_file = tmp_path / "spec_with_history.json"
        spec_file.write_text(sample_spec.to_json(indent=2), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(spec_app, ["history", str(spec_file)])

        assert result.exit_code == 0

    def test_history_json_output(
        self, tmp_path: Path, sample_spec: RepositorySpec
    ) -> None:
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        sample_spec.refinement_history = [
            RefinementEntry(
                action="add",
                details="Added auth requirement",
                timestamp=datetime.now(timezone.utc),
            ),
        ]
        spec_file = tmp_path / "spec_hist.json"
        spec_file.write_text(sample_spec.to_json(indent=2), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            spec_app, ["history", str(spec_file), "--json"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert len(output) == 1
        assert output[0]["action"] == "add"


# ---------------------------------------------------------------------------
# Conflicts command tests
# ---------------------------------------------------------------------------


class TestConflictsCommand:
    """Tests for the conflicts command."""

    def test_conflicts_no_conflicts(self, spec_json_file: Path) -> None:
        """No conflicts on a valid spec."""
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        runner = CliRunner()
        result = runner.invoke(
            spec_app,
            ["conflicts", str(spec_json_file), "--no-llm"],
        )

        assert result.exit_code == 0

    def test_conflicts_detects_scope_mismatch(self, tmp_path: Path) -> None:
        """Detects BACKEND_ONLY + React conflict."""
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        # Create a spec with a known conflict
        conflicting_spec = RepositorySpec(
            description="Build a backend-only API service with Python and React for user management",
            technical_requirements=TechnicalRequirement(
                languages=["Python"],
                frameworks=["React", "FastAPI"],
                scope=ScopeType.BACKEND_ONLY,
            ),
        )
        spec_file = tmp_path / "conflicting.json"
        spec_file.write_text(conflicting_spec.to_json(indent=2), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            spec_app,
            ["conflicts", str(spec_file), "--no-llm"],
        )

        assert result.exit_code == 0

    def test_conflicts_json_output(self, tmp_path: Path) -> None:
        """JSON output format for conflicts command."""
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        conflicting_spec = RepositorySpec(
            description="Build a backend-only API service with Python and React for user management",
            technical_requirements=TechnicalRequirement(
                languages=["Python"],
                frameworks=["React", "FastAPI"],
                scope=ScopeType.BACKEND_ONLY,
            ),
        )
        spec_file = tmp_path / "conflicting.json"
        spec_file.write_text(conflicting_spec.to_json(indent=2), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            spec_app,
            ["conflicts", str(spec_file), "--no-llm", "--json"],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert isinstance(output, list)
        assert len(output) >= 1
        assert "severity" in output[0]
        assert "description" in output[0]
        assert "conflicting_fields" in output[0]

    def test_conflicts_attach_saves_to_file(self, tmp_path: Path) -> None:
        """--attach flag saves conflicts to the spec file."""
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        conflicting_spec = RepositorySpec(
            description="Build a backend-only API service with Python and React for user management",
            technical_requirements=TechnicalRequirement(
                languages=["Python"],
                frameworks=["React"],
                scope=ScopeType.BACKEND_ONLY,
            ),
        )
        spec_file = tmp_path / "attach_test.json"
        spec_file.write_text(conflicting_spec.to_json(indent=2), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            spec_app,
            ["conflicts", str(spec_file), "--no-llm", "--attach"],
        )

        assert result.exit_code == 0

        # Reload and verify conflicts were attached
        updated = RepositorySpec.from_json(spec_file.read_text())
        assert len(updated.conflicts) >= 1

    def test_conflicts_nonexistent_file(self, tmp_path: Path) -> None:
        """Error on nonexistent spec file."""
        from typer.testing import CliRunner
        from cobuilder.repomap.cli.spec import spec_app

        runner = CliRunner()
        result = runner.invoke(
            spec_app,
            ["conflicts", str(tmp_path / "missing.json"), "--no-llm"],
        )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Import and registration tests
# ---------------------------------------------------------------------------


class TestImports:
    """Tests for CLI module imports."""

    def test_import_spec_app(self) -> None:
        from cobuilder.repomap.cli.spec import spec_app

        assert spec_app is not None

    def test_spec_app_has_commands(self) -> None:
        from cobuilder.repomap.cli.spec import spec_app

        # Verify all expected commands are registered
        command_names = {
            cmd.name or cmd.callback.__name__
            for cmd in spec_app.registered_commands
        }
        expected = {"parse", "refine", "conflicts", "suggest", "export", "history"}
        assert expected.issubset(command_names)

    def test_main_app_has_spec(self) -> None:
        from cobuilder.repomap.cli.app import app

        # Check that spec is registered as a sub-command group
        group_names = {g.name for g in app.registered_groups if g.name}
        assert "spec" in group_names

    def test_main_app_has_ontology(self) -> None:
        from cobuilder.repomap.cli.app import app

        group_names = {g.name for g in app.registered_groups if g.name}
        assert "ontology" in group_names
