"""Pyright configuration management for Serena workspaces.

Generates and writes pyrightconfig.json files for workspace
type checking configuration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from zerorepo.serena.exceptions import SerenaError
from zerorepo.serena.models import PyrightConfig

logger = logging.getLogger(__name__)


class PyrightConfigurator:
    """Manage Pyright configuration for a workspace.

    Generates pyrightconfig.json files with configurable settings
    for Python type checking via Pyright.
    """

    def configure_pyright(
        self,
        workspace_dir: Path,
        config: PyrightConfig | None = None,
    ) -> None:
        """Write pyrightconfig.json to the workspace directory.

        Args:
            workspace_dir: The workspace directory to write the config to.
            config: Pyright configuration. Uses defaults if not provided.

        Raises:
            SerenaError: If the configuration file cannot be written.
        """
        if config is None:
            config = PyrightConfig()

        config_path = workspace_dir / "pyrightconfig.json"
        config_data = {
            "include": config.include,
            "exclude": config.exclude,
            "typeCheckingMode": config.type_checking_mode,
            "reportMissingImports": config.report_missing_imports,
        }

        try:
            config_path.write_text(
                json.dumps(config_data, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise SerenaError(
                f"Failed to write pyrightconfig.json to {workspace_dir}: {exc}"
            ) from exc

        logger.info("Wrote pyrightconfig.json to %s", config_path)
