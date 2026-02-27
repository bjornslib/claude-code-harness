"""Unit tests for zerorepo.cli.app – the main Typer application."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cobuilder.repomap.cli.app import app


runner = CliRunner()


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_version_short_flag(self) -> None:
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "zerorepo" in result.output


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


class TestHelp:
    def test_help_flag(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ZeroRepo" in result.output

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        # Typer's no_args_is_help exits with code 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        assert "Usage" in result.output or "ZeroRepo" in result.output


# ---------------------------------------------------------------------------
# --verbose
# ---------------------------------------------------------------------------


class TestVerbose:
    def test_verbose_flag_accepted(self) -> None:
        """--verbose doesn't crash."""
        result = runner.invoke(app, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_verbose_short_flag(self) -> None:
        result = runner.invoke(app, ["-v", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_config_option_accepted(self, tmp_path) -> None:
        config_file = tmp_path / "test.toml"
        config_file.write_text("")
        result = runner.invoke(app, ["--config", str(config_file), "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# init command via CLI
# ---------------------------------------------------------------------------


class TestInitCommand:
    def test_init_help(self) -> None:
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output.lower() or "Initialise" in result.output

    def test_init_creates_project(self, tmp_path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".zerorepo").is_dir()
        assert (tmp_path / ".zerorepo" / "config.toml").exists()

    def test_init_already_exists_fails(self, tmp_path) -> None:
        (tmp_path / ".zerorepo").mkdir()
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code != 0

    def test_init_nonexistent_path_fails(self) -> None:
        result = runner.invoke(app, ["init", "/nonexistent/xyz123"])
        assert result.exit_code != 0

    def test_init_shows_success_message(self, tmp_path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert "Initialised" in result.output or "zerorepo" in result.output.lower()

    def test_init_warns_no_git(self, tmp_path) -> None:
        """Non-git dir gets a warning."""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        # Should contain a warning about git
        assert "git" in result.output.lower() or "Warning" in result.output

    def test_init_git_repo_no_warning(self, tmp_path) -> None:
        """Git repo doesn't get the non-git warning."""
        import subprocess
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        # Should NOT have the warning
        assert "Warning" not in result.output or "not a git" not in result.output.lower()
