"""Unit tests for zerorepo.cli.init_cmd."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerorepo.cli.config import DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_FILE
from zerorepo.cli.errors import CLIError
from zerorepo.cli.init_cmd import (
    _create_project_structure,
    _is_git_repo,
    _write_default_config,
    run_init,
)


# ---------------------------------------------------------------------------
# _is_git_repo tests
# ---------------------------------------------------------------------------


class TestIsGitRepo:
    def test_real_git_repo(self, tmp_path: Path) -> None:
        """A directory with `git init` should be detected."""
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        assert _is_git_repo(tmp_path) is True

    def test_non_git_dir(self, tmp_path: Path) -> None:
        assert _is_git_repo(tmp_path) is False

    def test_git_not_found(self, tmp_path: Path) -> None:
        """Handles missing git binary gracefully."""
        with patch("zerorepo.cli.init_cmd.subprocess.run", side_effect=FileNotFoundError):
            assert _is_git_repo(tmp_path) is False


# ---------------------------------------------------------------------------
# _create_project_structure tests
# ---------------------------------------------------------------------------


class TestCreateProjectStructure:
    def test_creates_dirs(self, tmp_path: Path) -> None:
        created = _create_project_structure(tmp_path)
        assert (tmp_path / DEFAULT_CONFIG_DIR).is_dir()
        assert (tmp_path / DEFAULT_CONFIG_DIR / "graphs").is_dir()
        assert (tmp_path / DEFAULT_CONFIG_DIR / "sandbox").is_dir()
        assert len(created) == 3

    def test_idempotent(self, tmp_path: Path) -> None:
        """Second call creates nothing new."""
        _create_project_structure(tmp_path)
        created = _create_project_structure(tmp_path)
        assert len(created) == 0


# ---------------------------------------------------------------------------
# _write_default_config tests
# ---------------------------------------------------------------------------


class TestWriteDefaultConfig:
    def test_writes_config(self, tmp_path: Path) -> None:
        (tmp_path / DEFAULT_CONFIG_DIR).mkdir()
        path = _write_default_config(tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "llm_provider" in content

    def test_raises_if_exists(self, tmp_path: Path) -> None:
        config_dir = tmp_path / DEFAULT_CONFIG_DIR
        config_dir.mkdir()
        config_file = config_dir / DEFAULT_CONFIG_FILE
        config_file.write_text("existing")
        with pytest.raises(CLIError, match="already exists"):
            _write_default_config(tmp_path)


# ---------------------------------------------------------------------------
# run_init tests
# ---------------------------------------------------------------------------


class TestRunInit:
    def test_creates_structure(self, tmp_path: Path) -> None:
        result = run_init(tmp_path)
        assert result == tmp_path
        assert (tmp_path / DEFAULT_CONFIG_DIR).is_dir()
        assert (tmp_path / DEFAULT_CONFIG_DIR / "graphs").is_dir()
        assert (tmp_path / DEFAULT_CONFIG_DIR / "sandbox").is_dir()
        assert (tmp_path / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE).exists()

    def test_raises_on_nonexistent_dir(self) -> None:
        with pytest.raises(CLIError, match="does not exist"):
            run_init(Path("/nonexistent/path/abc123"))

    def test_raises_on_file_not_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "afile"
        f.write_text("hi")
        with pytest.raises(CLIError, match="Not a directory"):
            run_init(f)

    def test_raises_if_already_initialised(self, tmp_path: Path) -> None:
        (tmp_path / DEFAULT_CONFIG_DIR).mkdir()
        with pytest.raises(CLIError, match="Already initialised"):
            run_init(tmp_path)

    def test_default_path_is_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_init(None)
        assert result == tmp_path
        assert (tmp_path / DEFAULT_CONFIG_DIR).is_dir()

    def test_config_toml_is_valid(self, tmp_path: Path) -> None:
        run_init(tmp_path)
        import tomllib
        config_file = tmp_path / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
        with open(config_file, "rb") as fh:
            data = tomllib.load(fh)
        assert "general" in data
