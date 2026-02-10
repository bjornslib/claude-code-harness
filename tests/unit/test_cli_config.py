"""Unit tests for zerorepo.cli.config."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from zerorepo.cli.config import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    ZeroRepoConfig,
    _apply_env_overrides,
    default_config_toml,
    load_config,
)


# ---------------------------------------------------------------------------
# ZeroRepoConfig model tests
# ---------------------------------------------------------------------------


class TestZeroRepoConfig:
    """Tests for the ZeroRepoConfig pydantic model."""

    def test_defaults(self) -> None:
        cfg = ZeroRepoConfig()
        assert cfg.llm_provider == "openai"
        assert cfg.llm_model == "gpt-4o-mini"
        assert cfg.log_level == "INFO"
        assert cfg.log_file is None
        assert isinstance(cfg.project_dir, Path)
        assert isinstance(cfg.vector_db_path, Path)

    def test_custom_values(self) -> None:
        cfg = ZeroRepoConfig(
            project_dir=Path("/tmp/test"),
            llm_provider="anthropic",
            llm_model="claude-3",
            log_level="DEBUG",
            log_file=Path("/tmp/test.log"),
        )
        assert cfg.llm_provider == "anthropic"
        assert cfg.llm_model == "claude-3"
        assert cfg.log_level == "DEBUG"
        assert cfg.log_file == Path("/tmp/test.log")

    def test_extra_fields_ignored(self) -> None:
        cfg = ZeroRepoConfig(unknown_field="value")
        assert not hasattr(cfg, "unknown_field")

    def test_project_dir_is_path(self) -> None:
        cfg = ZeroRepoConfig(project_dir="/tmp/test")
        assert isinstance(cfg.project_dir, Path)


# ---------------------------------------------------------------------------
# Environment override tests
# ---------------------------------------------------------------------------


class TestEnvOverrides:
    def test_apply_known_field(self) -> None:
        data: dict = {}
        with patch.dict(os.environ, {"ZEROREPO_LLM_PROVIDER": "anthropic"}):
            result = _apply_env_overrides(data)
        assert result["llm_provider"] == "anthropic"

    def test_ignore_unknown_field(self) -> None:
        data: dict = {}
        with patch.dict(os.environ, {"ZEROREPO_UNKNOWN_THING": "val"}):
            result = _apply_env_overrides(data)
        assert "unknown_thing" not in result

    def test_env_overrides_existing(self) -> None:
        data = {"llm_model": "gpt-4"}
        with patch.dict(os.environ, {"ZEROREPO_LLM_MODEL": "gpt-5"}):
            result = _apply_env_overrides(data)
        assert result["llm_model"] == "gpt-5"

    def test_multiple_overrides(self) -> None:
        data: dict = {}
        env = {
            "ZEROREPO_LLM_PROVIDER": "azure",
            "ZEROREPO_LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env):
            result = _apply_env_overrides(data)
        assert result["llm_provider"] == "azure"
        assert result["log_level"] == "DEBUG"


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_no_file(self, tmp_path: Path) -> None:
        """Returns defaults when no config file exists."""
        cfg = load_config(project_dir=tmp_path)
        assert cfg.llm_provider == "openai"
        assert cfg.project_dir == tmp_path

    def test_load_from_toml(self, tmp_path: Path) -> None:
        config_dir = tmp_path / DEFAULT_CONFIG_DIR
        config_dir.mkdir()
        config_file = config_dir / DEFAULT_CONFIG_FILE
        config_file.write_text(
            '[general]\nllm_provider = "anthropic"\nllm_model = "claude-4"\n'
        )
        cfg = load_config(project_dir=tmp_path)
        assert cfg.llm_provider == "anthropic"
        assert cfg.llm_model == "claude-4"

    def test_load_explicit_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "custom.toml"
        config_file.write_text('llm_provider = "custom"\n')
        cfg = load_config(config_path=config_file, project_dir=tmp_path)
        assert cfg.llm_provider == "custom"

    def test_env_override_with_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / DEFAULT_CONFIG_DIR
        config_dir.mkdir()
        config_file = config_dir / DEFAULT_CONFIG_FILE
        config_file.write_text('[general]\nllm_provider = "openai"\n')
        with patch.dict(os.environ, {"ZEROREPO_LLM_PROVIDER": "env-override"}):
            cfg = load_config(project_dir=tmp_path)
        assert cfg.llm_provider == "env-override"

    def test_flat_toml_keys(self, tmp_path: Path) -> None:
        """Top-level keys (no section) also work."""
        config_file = tmp_path / "flat.toml"
        config_file.write_text('log_level = "WARNING"\n')
        cfg = load_config(config_path=config_file, project_dir=tmp_path)
        assert cfg.log_level == "WARNING"


# ---------------------------------------------------------------------------
# default_config_toml
# ---------------------------------------------------------------------------


class TestDefaultConfigToml:
    def test_is_string(self) -> None:
        result = default_config_toml()
        assert isinstance(result, str)

    def test_contains_provider(self) -> None:
        assert "llm_provider" in default_config_toml()

    def test_contains_model(self) -> None:
        assert "llm_model" in default_config_toml()

    def test_valid_toml(self) -> None:
        import tomllib
        data = tomllib.loads(default_config_toml())
        assert "general" in data
