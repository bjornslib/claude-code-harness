"""CLI commands for the Ontology Service.

Implements the CLI integration for Task 2.1.6 of PRD-RPG-P2-001.
Provides sub-commands: build, search, stats, extend, export.

Example usage::

    zerorepo ontology build
    zerorepo ontology search "authentication"
    zerorepo ontology stats
    zerorepo ontology extend --csv features.csv
    zerorepo ontology export --output ontology.csv
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from zerorepo.cli.errors import error_handler

logger = logging.getLogger(__name__)

ontology_app = typer.Typer(
    name="ontology",
    help="Feature Ontology Service – build, search, extend, and export the feature ontology.",
    no_args_is_help=True,
)

_console = Console(stderr=True)
_out_console = Console()  # stdout for data output


def _get_service(project_dir: Path) -> "OntologyService":  # noqa: F821
    """Lazy-import and create the OntologyService to avoid circular imports.

    Args:
        project_dir: Project root directory.

    Returns:
        A configured OntologyService instance.
    """
    from zerorepo.ontology.service import OntologyService

    return OntologyService.create(project_dir=project_dir)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


@ontology_app.command()
def build(
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-p",
        help="Project root directory.",
    ),
    no_github: bool = typer.Option(
        False,
        "--no-github",
        help="Exclude GitHub Topics generator.",
    ),
    no_stackoverflow: bool = typer.Option(
        False,
        "--no-stackoverflow",
        help="Exclude StackOverflow Tags generator.",
    ),
    no_libraries: bool = typer.Option(
        False,
        "--no-libraries",
        help="Exclude Library Docs generator.",
    ),
    no_expander: bool = typer.Option(
        False,
        "--no-expander",
        help="Exclude combinatorial taxonomy expander.",
    ),
    target_count: int = typer.Option(
        50000,
        "--target-count",
        "-t",
        help="Target node count for the taxonomy expander.",
    ),
    output_csv: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Export ontology to CSV file after building.",
    ),
) -> None:
    """Build the feature ontology from seed generators.

    Runs configured seed generators (GitHub Topics, StackOverflow Tags,
    Library Docs, Taxonomy Expander), embeds nodes, and stores them
    in ChromaDB.
    """
    with error_handler(_console):
        service = _get_service(project_dir.resolve())

        _console.print("[bold]Building feature ontology...[/bold]")

        result = service.build(
            include_github=not no_github,
            include_stackoverflow=not no_stackoverflow,
            include_libraries=not no_libraries,
            include_expander=not no_expander,
            target_count=target_count,
        )

        _console.print(f"[green]Build complete![/green]")
        _console.print(f"  Total nodes: {result.total_nodes}")
        _console.print(f"  Stored: {result.stored_count}")
        _console.print(f"  Max depth: {result.max_depth}")

        if result.embedding_result:
            _console.print(
                f"  Embedded: {result.embedding_result.embedded_count} "
                f"({result.embedding_result.elapsed_seconds:.1f}s)"
            )

        if result.source_stats:
            _console.print("\n[bold]Source breakdown:[/bold]")
            for source, count in sorted(
                result.source_stats.items(), key=lambda x: -x[1]
            ):
                _console.print(f"  {source}: {count}")

        if output_csv:
            csv_content = service.export_csv(output_csv)
            _console.print(
                f"\n[green]Exported to {output_csv}[/green]"
            )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@ontology_app.command()
def search(
    query: str = typer.Argument(
        ..., help="Natural language search query."
    ),
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-p",
        help="Project root directory.",
    ),
    top_k: int = typer.Option(
        10,
        "--top-k",
        "-k",
        help="Maximum number of results.",
    ),
    level: Optional[int] = typer.Option(
        None,
        "--level",
        "-l",
        help="Filter by hierarchical level.",
    ),
    parent_id: Optional[str] = typer.Option(
        None,
        "--parent",
        help="Filter by parent node ID.",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        help="Filter by tags (comma-separated).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output results as JSON.",
    ),
) -> None:
    """Search the feature ontology for matching features.

    Returns ranked results with relevance scores.
    """
    with error_handler(_console):
        service = _get_service(project_dir.resolve())

        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()]
            if tags
            else None
        )

        result = service.search(
            query=query,
            top_k=top_k,
            level=level,
            parent_id=parent_id,
            tags=tag_list,
        )

        if json_output:
            output_data = {
                "query": result.query,
                "total_results": result.total_results,
                "results": [
                    {
                        "path": path.path_string,
                        "score": path.score,
                        "leaf_id": path.leaf.id,
                        "leaf_name": path.leaf.name,
                        "leaf_description": path.leaf.description,
                        "depth": path.depth,
                    }
                    for path in result.paths
                ],
            }
            _out_console.print(json.dumps(output_data, indent=2))
            return

        if result.total_results == 0:
            _console.print(f"[yellow]No results found for '{query}'[/yellow]")
            return

        _console.print(
            f"\n[bold]Search results for '{query}' "
            f"({result.total_results} results):[/bold]\n"
        )

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Score", width=6)
        table.add_column("Feature", min_width=20)
        table.add_column("Path", min_width=30)
        table.add_column("Level", width=5)

        for i, path in enumerate(result.paths, start=1):
            score_str = f"{path.score:.3f}"
            table.add_row(
                str(i),
                score_str,
                path.leaf.name,
                path.path_string,
                str(path.leaf.level),
            )

        _out_console.print(table)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


@ontology_app.command()
def stats(
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-p",
        help="Project root directory.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output statistics as JSON.",
    ),
) -> None:
    """Display ontology statistics."""
    with error_handler(_console):
        service = _get_service(project_dir.resolve())
        ontology_stats = service.stats()

        if json_output:
            _out_console.print(
                json.dumps(ontology_stats.model_dump(), indent=2)
            )
            return

        _console.print("\n[bold]Ontology Statistics[/bold]\n")
        _console.print(f"  Total nodes:      {ontology_stats.total_nodes}")
        _console.print(f"  Total levels:     {ontology_stats.total_levels}")
        _console.print(f"  Max depth:        {ontology_stats.max_depth}")
        _console.print(f"  Root nodes:       {ontology_stats.root_count}")
        _console.print(f"  Leaf nodes:       {ontology_stats.leaf_count}")
        _console.print(f"  Avg children:     {ontology_stats.avg_children:.1f}")
        _console.print(
            f"  With embeddings:  {ontology_stats.nodes_with_embeddings} "
            f"({ontology_stats.embedding_coverage:.1%})"
        )


# ---------------------------------------------------------------------------
# extend
# ---------------------------------------------------------------------------


@ontology_app.command()
def extend(
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-p",
        help="Project root directory.",
    ),
    csv_file: Path = typer.Option(
        ...,
        "--csv",
        "-f",
        help="Path to CSV file with custom features.",
    ),
    conflict_resolution: str = typer.Option(
        "override",
        "--conflict",
        "-c",
        help="Conflict resolution: override, skip, error.",
    ),
    no_embed: bool = typer.Option(
        False,
        "--no-embed",
        help="Skip automatic embedding of new features.",
    ),
) -> None:
    """Extend the ontology with custom features from CSV.

    CSV format: feature_id,parent_id,name,description,tags,level
    """
    with error_handler(_console):
        service = _get_service(project_dir.resolve())

        _console.print(
            f"[bold]Extending ontology from {csv_file}...[/bold]"
        )

        result = service.extend(
            csv_path=csv_file,
            conflict_resolution=conflict_resolution,
            embed=not no_embed,
        )

        _console.print(f"[green]Extension complete![/green]")
        _console.print(f"  Added:   {result.added}")
        _console.print(f"  Updated: {result.updated}")
        _console.print(f"  Skipped: {result.skipped}")
        _console.print(f"  Errors:  {result.errors}")

        if result.error_details:
            _console.print("\n[yellow]Errors:[/yellow]")
            for error in result.error_details[:10]:
                _console.print(f"  - {error}")
            if len(result.error_details) > 10:
                _console.print(
                    f"  ... and {len(result.error_details) - 10} more"
                )


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@ontology_app.command(name="export")
def export_cmd(
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        "-p",
        help="Project root directory.",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output CSV file path.",
    ),
) -> None:
    """Export the ontology to CSV format."""
    with error_handler(_console):
        service = _get_service(project_dir.resolve())

        csv_content = service.export_csv(output)
        line_count = csv_content.count("\n")

        _console.print(
            f"[green]Exported ontology to {output} ({line_count} rows)[/green]"
        )
