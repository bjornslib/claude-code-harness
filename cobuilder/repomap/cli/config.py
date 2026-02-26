"""ZeroRepo CLI configuration management.

Loads configuration from TOML files with environment variable overrides
(``ZEROREPO_`` prefix).  Uses :mod:`tomllib` on Python 3.11+.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_DIR = ".zerorepo"
DEFAULT_CONFIG_FILE = "config.toml"

# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------


class ZeroRepoConfig(BaseModel):
    """Application configuration with sensible defaults.

    All fields can be overridden via environment variables with the
    ``ZEROREPO_`` prefix.  For example ``ZEROREPO_LLM_PROVIDER=anthropic``.
    """

    project_dir: Path = Field(default_factory=lambda: Path.cwd())
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    vector_db_path: Path = Field(default_factory=lambda: Path.cwd() / DEFAULT_CONFIG_DIR / "vectordb")
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------


def _apply_env_overrides(data: dict) -> dict:
    """Apply ZEROREPO_ environment variable overrides to *data*."""
    prefix = "ZEROREPO_"
    field_names = set(ZeroRepoConfig.model_fields.keys())
    for key, value in os.environ.items():
        if key.startswith(prefix):
            field = key[len(prefix):].lower()
            if field in field_names:
                data[field] = value
    return data


def load_config(config_path: Path | None = None, project_dir: Path | None = None) -> ZeroRepoConfig:
    """Load configuration from a TOML file with env-var overrides.

    Parameters
    ----------
    config_path:
        Explicit path to a TOML file.  When *None*, looks for
        ``<project_dir>/.zerorepo/config.toml``.
    project_dir:
        Project root directory.  Defaults to :func:`Path.cwd`.

    Returns
    -------
    ZeroRepoConfig
        Parsed and validated configuration.
    """
    project = project_dir or Path.cwd()
    path = config_path or (project / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE)

    data: dict = {}
    if path.exists():
        with open(path, "rb") as fh:
            data = tomllib.load(fh)

    # Flatten nested TOML sections if present
    flat: dict = {}
    for k, v in data.items():
        if isinstance(v, dict):
            flat.update(v)
        else:
            flat[k] = v

    # Always set project_dir from argument / cwd
    flat.setdefault("project_dir", str(project))

    flat = _apply_env_overrides(flat)
    return ZeroRepoConfig(**flat)


def default_config_toml() -> str:
    """Return default configuration as a TOML string."""
    return """\
# ZeroRepo configuration

[general]
llm_provider = "openai"
llm_model = "gpt-4o-mini"
log_level = "INFO"
"""
