"""CoBuilder repomap CLI subcommands.

Provides the ``cobuilder repomap`` command group with subcommands:

- ``init``     — Register a repository in .repomap/config.yaml
- ``sync``     — Walk codebase and save baseline + manifest
- ``status``   — Show tracked repos and their sync status
- ``context``  — Print repomap context string for LLM injection
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(help="CoBuilder RepoMap — codebase indexing and context commands")


@app.command("init")
def init_cmd(
    name: str = typer.Argument(..., help="Short identifier for the repository"),
    target_dir: str = typer.Option(
        ..., "--target-dir", "-t", help="Absolute path to the repository root"
    ),
    project_root: str = typer.Option(
        ".", "--project-root", "-p", help="Root of the project that owns .repomap/"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Update an existing entry instead of raising"
    ),
) -> None:
    """Register a repository in .repomap/config.yaml (no scanning)."""
    from cobuilder.bridge import init_repo

    try:
        entry = init_repo(
            name,
            target_dir=Path(target_dir),
            project_root=Path(project_root),
            force=force,
        )
        console.print(
            f"[green]✓[/green] Registered [bold]{name}[/bold] → {entry['path']}"
        )
        console.print(
            "Run [bold]cobuilder repomap sync[/bold] to create the first baseline."
        )
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@app.command("sync")
def sync_cmd(
    name: str = typer.Argument(..., help="Repository name (must be registered)"),
    project_root: str = typer.Option(
        ".", "--project-root", "-p", help="Root of the project that owns .repomap/"
    ),
) -> None:
    """Walk the registered repository and save a new baseline."""
    from cobuilder.bridge import sync_baseline

    console.print(f"Syncing [bold]{name}[/bold] …")
    try:
        entry = sync_baseline(name, project_root=Path(project_root))
        console.print(
            f"[green]✓[/green] Synced [bold]{name}[/bold]: "
            f"{entry.get('node_count', 0)} nodes, "
            f"{entry.get('file_count', 0)} files"
        )
        console.print(f"Hash: {entry.get('baseline_hash', 'n/a')}")
    except (KeyError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@app.command("status")
def status_cmd(
    project_root: str = typer.Option(
        ".", "--project-root", "-p", help="Root of the project that owns .repomap/"
    ),
    name: Optional[str] = typer.Argument(
        None, help="Repository name (omit to show all)"
    ),
) -> None:
    """Show tracked repos and their sync status."""
    import yaml  # noqa: PLC0415

    repomap_dir = Path(project_root) / ".repomap"
    config_path = repomap_dir / "config.yaml"

    if not config_path.exists():
        console.print(
            "[yellow]No .repomap/config.yaml found.[/yellow] "
            "Run [bold]cobuilder repomap init[/bold] to register a repo."
        )
        return

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    repos = config.get("repos", [])
    if not repos:
        console.print("No repositories registered yet.")
        return

    if name:
        repos = [r for r in repos if r.get("name") == name]
        if not repos:
            console.print(f"[red]No repository named '{name}' found.[/red]")
            raise typer.Exit(1)

    table = Table(title="CoBuilder RepoMap — Tracked Repositories")
    table.add_column("Name", style="bold cyan")
    table.add_column("Path")
    table.add_column("Nodes", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Last Synced")
    table.add_column("Hash")

    for repo in repos:
        last_synced = repo.get("last_synced") or "[dim]never[/dim]"
        baseline_hash = repo.get("baseline_hash") or "[dim]n/a[/dim]"
        table.add_row(
            repo.get("name", "?"),
            repo.get("path", "?"),
            str(repo.get("node_count", 0)),
            str(repo.get("file_count", 0)),
            last_synced,
            baseline_hash,
        )

    console.print(table)


@app.command("context")
def context_cmd(
    name: str = typer.Argument(..., help="Repository name"),
    project_root: str = typer.Option(
        ".", "--project-root", "-p", help="Root of the project that owns .repomap/"
    ),
    max_modules: int = typer.Option(
        10, "--max-modules", "-m", help="Maximum number of top modules to list"
    ),
) -> None:
    """Print the repomap context string suitable for LLM injection."""
    from cobuilder.bridge import get_repomap_context

    try:
        ctx = get_repomap_context(
            name,
            project_root=Path(project_root),
            max_modules=max_modules,
        )
        console.print(ctx)
    except (KeyError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
