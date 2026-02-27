"""ZeroRepo ``init`` command.

Creates the ``.zerorepo/`` project structure in the target directory and
writes a default configuration file.  Optionally walks a codebase to
produce a baseline RPGGraph via ``--project-path``.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

from cobuilder.repomap.cli.config import DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_FILE, default_config_toml
from cobuilder.repomap.cli.errors import CLIError

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_git_repo(path: Path) -> bool:
    """Return True if *path* is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _create_project_structure(project_dir: Path) -> list[Path]:
    """Create the .zerorepo directory tree, returning paths created."""
    base = project_dir / DEFAULT_CONFIG_DIR
    dirs = [
        base,
        base / "graphs",
        base / "sandbox",
    ]
    created: list[Path] = []
    for d in dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(d)
    return created


def _write_default_config(project_dir: Path) -> Path:
    """Write the default config.toml, returning the path."""
    config_path = project_dir / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
    if config_path.exists():
        raise CLIError(
            f"Configuration already exists: {config_path}\n"
            "Use --force to overwrite (not yet implemented)."
        )
    config_path.write_text(default_config_toml())
    return config_path


# ---------------------------------------------------------------------------
# Command implementation (called from app.py)
# ---------------------------------------------------------------------------


def run_init(
    path: Optional[Path] = None,
    *,
    console: "typer.Context | None" = None,
) -> Path:
    """Execute the init command logic.

    Parameters
    ----------
    path:
        Target directory.  Defaults to current working directory.

    Returns
    -------
    Path
        The project directory that was initialised.
    """
    project_dir = (path or Path.cwd()).resolve()

    if not project_dir.exists():
        raise CLIError(f"Directory does not exist: {project_dir}")

    if not project_dir.is_dir():
        raise CLIError(f"Not a directory: {project_dir}")

    # Check for existing .zerorepo
    zerorepo_dir = project_dir / DEFAULT_CONFIG_DIR
    if zerorepo_dir.exists():
        raise CLIError(
            f"Already initialised: {zerorepo_dir} exists.\n"
            "Remove it first or use a different directory."
        )

    # Warn if not a git repo
    is_git = _is_git_repo(project_dir)

    # Create structure
    _create_project_structure(project_dir)

    # Write default config
    config_path = _write_default_config(project_dir)

    return project_dir


# ---------------------------------------------------------------------------
# Baseline generation (called from app.py when --project-path is set)
# ---------------------------------------------------------------------------


def run_baseline_generation(
    *,
    project_dir: Path,
    project_path: Path,
    output_path: Path | None = None,
    exclude_patterns: list[str] | None = None,
    console: "Console | None" = None,
) -> Path:
    """Walk a codebase and generate a baseline RPGGraph.

    Parameters
    ----------
    project_dir:
        The initialised project directory (contains ``.zerorepo/``).
    project_path:
        Path to the codebase to analyse.
    output_path:
        Where to write the baseline JSON.  Defaults to
        ``project_dir / .zerorepo / baseline.json``.
    exclude_patterns:
        Optional list of directory name patterns to skip during walk.
    console:
        Optional Rich console for status output.

    Returns
    -------
    Path
        The path to the generated baseline file.
    """
    from cobuilder.repomap.serena.baseline import BaselineManager
    from cobuilder.repomap.serena.session import FileBasedCodebaseAnalyzer
    from cobuilder.repomap.serena.walker import CodebaseWalker

    project_path = project_path.resolve()
    if not project_path.exists():
        raise CLIError(f"Project path does not exist: {project_path}")
    if not project_path.is_dir():
        raise CLIError(f"Project path is not a directory: {project_path}")

    if console:
        console.print(
            f"[bold]Baseline:[/bold] Analysing codebase at {project_path}..."
        )

    # Walk the codebase
    analyzer = FileBasedCodebaseAnalyzer()
    walker = CodebaseWalker(analyzer=analyzer)
    graph = walker.walk(project_path, exclude_patterns=exclude_patterns)

    if console:
        console.print(
            f"  [dim]Discovered {graph.node_count} nodes, "
            f"{graph.edge_count} edges[/dim]"
        )

    # Save baseline
    manager = BaselineManager()
    baseline_path = output_path or BaselineManager.default_path(project_dir)
    saved = manager.save(graph, output_path=baseline_path, project_root=project_path)

    if console:
        console.print(f"  [green]Saved baseline to {saved}[/green]")

    return saved
