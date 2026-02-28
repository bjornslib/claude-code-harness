"""CoBuilder repomap CLI subcommands.

Provides the ``cobuilder repomap`` command group with subcommands:

- ``init``     — Register a repository in .repomap/config.yaml
- ``sync``     — Walk codebase and save baseline + manifest
- ``status``   — Show tracked repos and their sync status
- ``context``  — Print repomap context string for LLM injection
- ``refresh``  — Refresh baseline for specific files/folders only
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

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
    prd: str = typer.Option(
        "", "--prd", help="PRD reference string (used as a keyword for relevance filtering)"
    ),
    prd_keywords: Optional[str] = typer.Option(
        None,
        "--prd-keywords",
        help="Comma-separated keywords for relevance filtering (e.g. 'auth,jwt,login')",
    ),
    sd_files: Optional[str] = typer.Option(
        None,
        "--sd-files",
        help="Comma-separated file paths from the Solution Design for direct matching",
    ),
    format: str = typer.Option(
        "yaml",
        "--format",
        "-f",
        help="Output format: 'yaml' (default) or 'text' (legacy plain text)",
    ),
) -> None:
    """Print the repomap context string suitable for LLM injection.

    In the default YAML format the output includes structured module
    information, dependency graph, and key interfaces filtered by the
    provided PRD keywords and Solution Design file references.
    Use --format=text for the legacy plain-text output.
    """
    from cobuilder.bridge import get_repomap_context

    # Build keyword list: --prd-keywords flag + --prd value (lowercased words)
    keywords: list[str] = []
    if prd_keywords:
        keywords.extend(k.strip() for k in prd_keywords.split(",") if k.strip())
    if prd:
        # Decompose PRD ref into words (e.g. PRD-AUTH-001 → ["auth"])
        keywords.extend(
            w.lower() for w in re.split(r"[^a-zA-Z]+", prd) if w and not w.isdigit()
        )

    sd_refs: list[str] = []
    if sd_files:
        sd_refs = [f.strip() for f in sd_files.split(",") if f.strip()]

    try:
        ctx = get_repomap_context(
            name,
            project_root=Path(project_root),
            max_modules=max_modules,
            prd_keywords=keywords or None,
            sd_file_references=sd_refs or None,
            format=format,
        )
        console.print(ctx)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@app.command("refresh")
def refresh_cmd(
    name: str = typer.Argument(..., help="Repo name registered in .repomap/config.yaml"),
    scope: Optional[List[str]] = typer.Option(
        None,
        "--scope",
        "-s",
        help="File or folder paths to re-scan (repeatable). Relative to repo root.",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        help="Re-scan the entire repository (alias for sync).",
    ),
    project_root: str = typer.Option(
        ".", "--project-root", "-p", help="Root of the project that owns .repomap/"
    ),
) -> None:
    """Refresh the baseline for specific files/folders only.

    Uses scoped_refresh() to re-scan only the paths given via --scope and
    merge them into the existing baseline.  Use --all to re-scan the full
    repository (equivalent to ``cobuilder repomap sync``).

    Examples::

        cobuilder repomap refresh myrepo --scope cobuilder/bridge.py
        cobuilder repomap refresh myrepo --scope src/auth/ --scope src/models.py
        cobuilder repomap refresh myrepo --all
    """
    from cobuilder.bridge import scoped_refresh, sync_baseline

    if all_files:
        console.print(f"Re-scanning full repository [bold]{name}[/bold] …")
        try:
            entry = sync_baseline(name, project_root=Path(project_root))
            console.print(
                f"[green]✓[/green] Synced [bold]{name}[/bold]: "
                f"{entry.get('node_count', 0)} nodes, "
                f"{entry.get('file_count', 0)} files"
            )
        except (KeyError, FileNotFoundError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc
        return

    effective_scope = list(scope) if scope else []
    if not effective_scope:
        console.print(
            "[yellow]Warning:[/yellow] No --scope paths provided. "
            "Use --scope <path> or --all to refresh the full repository."
        )
        raise typer.Exit(1)

    console.print(
        f"Refreshing [bold]{name}[/bold] for {len(effective_scope)} path(s) …"
    )
    try:
        result = scoped_refresh(
            name,
            scope=effective_scope,
            project_root=Path(project_root),
        )
    except (KeyError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if result.get("skipped"):
        console.print(
            f"[yellow]Skipped[/yellow] (debounced within {30}s window): "
            f"{result}"
        )
    else:
        console.print(
            f"[green]✓[/green] Refreshed [bold]{result.get('refreshed_nodes', 0)}[/bold] "
            f"nodes in [bold]{result.get('duration_seconds', 0):.1f}s[/bold]"
        )
        console.print(f"Hash: {result.get('baseline_hash', 'n/a')}")
