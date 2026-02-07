"""ZeroRepo CLI application entry point.

Built with `Typer <https://typer.tiangolo.com/>`_ and
`Rich <https://rich.readthedocs.io/>`_.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from zerorepo.cli.config import load_config
from zerorepo.cli.errors import error_handler
from zerorepo.cli.init_cmd import run_init
from zerorepo.cli.logging_setup import setup_logging
from zerorepo.cli.ontology import ontology_app
from zerorepo.cli.spec import spec_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="zerorepo",
    help="ZeroRepo – Repository Planning Graph for generating complete software repositories.",
    add_completion=False,
    no_args_is_help=True,
)

_console = Console(stderr=True)

# Register sub-command groups
app.add_typer(ontology_app, name="ontology")
app.add_typer(spec_app, name="spec")


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from zerorepo import __version__

        _console.print(f"zerorepo {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Main callback (global options)
# ---------------------------------------------------------------------------

@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG) output.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration TOML file.",
    ),
) -> None:
    """Global options for ZeroRepo CLI."""
    # Setup logging based on verbosity
    level = "DEBUG" if verbose else "INFO"
    setup_logging(level)

    # Store config path for sub-commands via context
    ctx = typer.Context
    # We use a simple module-level store since Typer callbacks
    # execute before commands
    app._zerorepo_verbose = verbose  # type: ignore[attr-defined]
    app._zerorepo_config_path = config  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------

@app.command()
def init(
    path: Optional[Path] = typer.Argument(
        None,
        help="Target directory to initialise. Defaults to current directory.",
    ),
) -> None:
    """Initialise a new ZeroRepo project.

    Creates the ``.zerorepo/`` directory structure with default configuration.
    """
    with error_handler(_console):
        project_dir = run_init(path)
        _console.print(f"[green]Initialised ZeroRepo project at {project_dir}[/green]")

        # Check if it's a git repo and warn
        from zerorepo.cli.init_cmd import _is_git_repo

        if not _is_git_repo(project_dir):
            _console.print(
                "[yellow]Warning: Not a git repository. "
                "ZeroRepo works best inside a git repo.[/yellow]"
            )


# ---------------------------------------------------------------------------
# Generate command
# ---------------------------------------------------------------------------


@app.command()
def generate(
    spec_file: Path = typer.Argument(
        ..., help="Path to specification file (markdown, text, or JSON)."
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for generated artifacts.",
    ),
    model: str = typer.Option(
        "gpt-5.2",
        "--model",
        "-m",
        help="LLM model to use for enrichment.",
    ),
    skip_enrichment: bool = typer.Option(
        False,
        "--skip-enrichment",
        help="Skip RPG enrichment encoders (produce raw RPGGraph only).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output final RPGGraph as JSON to stdout.",
    ),
) -> None:
    """Generate a Repository Planning Graph from a specification.

    Full pipeline:
    1. Parse spec → RepositorySpec
    2. Build from spec → FunctionalityGraph
    3. Convert → RPGGraph
    4. Enrich with encoders → enriched RPGGraph
    5. Generate report → markdown

    Example::

        zerorepo generate spec.json -o ./output/
        zerorepo generate spec.json --json
        zerorepo generate spec.json --skip-enrichment
    """
    with error_handler(_console):
        import json as json_mod

        from zerorepo.graph_construction.builder import FunctionalityGraphBuilder
        from zerorepo.graph_construction.converter import (
            FunctionalityGraphConverter,
        )
        from zerorepo.rpg_enrichment import (
            BaseClassEncoder,
            DataFlowEncoder,
            FileEncoder,
            FolderEncoder,
            IntraModuleOrderEncoder,
            RPGBuilder,
        )
        from zerorepo.spec_parser.parser import SpecParser

        # ----------------------------------------------------------
        # Stage 1: Parse specification
        # ----------------------------------------------------------
        _console.print(f"[bold]Stage 1:[/bold] Parsing specification from {spec_file}...")
        spec_text = spec_file.read_text(encoding="utf-8")

        from zerorepo.spec_parser.parser import ParserConfig

        parser_config = ParserConfig(model=model)
        parser = SpecParser(config=parser_config)
        spec = parser.parse(spec_text)
        _console.print(
            f"  [dim]Loaded spec: {spec.description[:80]}...[/dim]"
        )

        # ----------------------------------------------------------
        # Stage 2: Build FunctionalityGraph from spec
        # ----------------------------------------------------------
        _console.print("[bold]Stage 2:[/bold] Building FunctionalityGraph from spec...")
        builder = FunctionalityGraphBuilder()
        try:
            func_graph = builder.build_from_spec(spec)
        except ValueError as exc:
            # Graceful fallback: if no epics/components, explain clearly
            raise typer.BadParameter(str(exc))

        _console.print(
            f"  [dim]Built graph: {func_graph.module_count} modules, "
            f"{func_graph.dependency_count} dependencies[/dim]"
        )

        # ----------------------------------------------------------
        # Stage 3: Convert to RPGGraph
        # ----------------------------------------------------------
        _console.print("[bold]Stage 3:[/bold] Converting to RPGGraph...")
        converter = FunctionalityGraphConverter()
        rpg_graph = converter.convert(func_graph, spec=spec)
        _console.print(
            f"  [dim]RPGGraph: {rpg_graph.node_count} nodes, "
            f"{rpg_graph.edge_count} edges[/dim]"
        )

        # ----------------------------------------------------------
        # Stage 4: Enrich with encoders (optional)
        # ----------------------------------------------------------
        if not skip_enrichment:
            _console.print("[bold]Stage 4:[/bold] Enriching RPGGraph with encoders...")

            rpg_builder = RPGBuilder()
            rpg_builder.add_encoder(FolderEncoder())
            rpg_builder.add_encoder(FileEncoder())
            rpg_builder.add_encoder(DataFlowEncoder())
            rpg_builder.add_encoder(IntraModuleOrderEncoder())
            rpg_builder.add_encoder(BaseClassEncoder())

            # InterfaceDesignEncoder requires an LLM gateway
            try:
                from zerorepo.llm.gateway import LLMGateway
                from zerorepo.rpg_enrichment import InterfaceDesignEncoder

                gateway = LLMGateway()
                rpg_builder.add_encoder(
                    InterfaceDesignEncoder(llm_gateway=gateway, model=model)
                )
                logger.info("InterfaceDesignEncoder enabled with model=%s", model)
            except Exception as exc:
                logger.warning(
                    "InterfaceDesignEncoder skipped (LLM unavailable): %s", exc
                )
                _console.print(
                    f"  [yellow]InterfaceDesignEncoder skipped: {exc}[/yellow]"
                )

            rpg_graph = rpg_builder.run(rpg_graph)

            _console.print(
                f"  [dim]Enriched: {rpg_graph.node_count} nodes, "
                f"{rpg_graph.edge_count} edges, "
                f"{len(rpg_builder.steps)} encoder steps[/dim]"
            )

            # Report encoder step summaries
            for step in rpg_builder.steps:
                status = "[green]OK[/green]"
                if step.validation and not step.validation.passed:
                    status = f"[yellow]WARN ({len(step.validation.errors)} errors)[/yellow]"
                _console.print(
                    f"    {step.encoder_name}: {step.duration_ms:.1f}ms {status}"
                )
        else:
            _console.print("[dim]Stage 4: Skipped (--skip-enrichment)[/dim]")

        # ----------------------------------------------------------
        # Stage 5: Output
        # ----------------------------------------------------------
        _console.print("[bold]Stage 5:[/bold] Generating output...")

        if json_output:
            from rich.console import Console as RichConsole

            out_console = RichConsole()
            out_console.print(rpg_graph.to_json(indent=2))

        if output:
            output.mkdir(parents=True, exist_ok=True)

            # Write RepositorySpec JSON
            spec_path = output / "01-spec.json"
            spec_path.write_text(spec.to_json(indent=2), encoding="utf-8")
            _console.print(f"  [green]Saved spec to {spec_path}[/green]")

            # Write FunctionalityGraph JSON
            func_graph_path = output / "03-graph.json"
            func_graph_path.write_text(
                func_graph.to_json(), encoding="utf-8"
            )
            _console.print(
                f"  [green]Saved FunctionalityGraph to {func_graph_path}[/green]"
            )

            # Write RPGGraph JSON
            graph_path = output / "04-rpg.json"
            graph_path.write_text(rpg_graph.to_json(indent=2), encoding="utf-8")
            _console.print(f"  [green]Saved RPGGraph to {graph_path}[/green]")

            # Write summary report (markdown)
            report_path = output / "pipeline-report.md"
            report_content = _build_generate_report(
                spec, func_graph, rpg_graph
            )
            report_path.write_text(report_content, encoding="utf-8")
            _console.print(f"  [green]Saved report to {report_path}[/green]")

        if not json_output and not output:
            _console.print(
                "[yellow]No output specified. Use --output or --json "
                "to save results.[/yellow]"
            )

        _console.print("\n[bold green]Generation complete.[/bold green]")


def _build_generate_report(
    spec: "RepositorySpec",  # noqa: F821
    func_graph: "FunctionalityGraph",  # noqa: F821
    rpg_graph: "RPGGraph",  # noqa: F821
) -> str:
    """Build a markdown summary report of the generation pipeline.

    Args:
        spec: The input RepositorySpec.
        func_graph: The intermediate FunctionalityGraph.
        rpg_graph: The final RPGGraph.

    Returns:
        A markdown report string.
    """
    from zerorepo.models.enums import NodeLevel

    lines = [
        "# ZeroRepo Generation Report",
        "",
        "## Specification",
        "",
        f"- **Description**: {spec.description[:200]}",
    ]

    if spec.core_functionality:
        lines.append(f"- **Core Functionality**: {spec.core_functionality}")

    tech = spec.technical_requirements
    if tech.languages:
        lines.append(f"- **Languages**: {', '.join(tech.languages)}")
    if tech.frameworks:
        lines.append(f"- **Frameworks**: {', '.join(tech.frameworks)}")

    lines.extend([
        "",
        "## Functionality Graph",
        "",
        f"- **Modules**: {func_graph.module_count}",
        f"- **Dependencies**: {func_graph.dependency_count}",
        f"- **Total Features**: {func_graph.feature_count}",
        f"- **Acyclic**: {func_graph.is_acyclic}",
        "",
        "### Modules",
        "",
    ])

    for mod in func_graph.modules:
        lines.append(f"- **{mod.name}** ({mod.feature_count} features): {mod.description[:100]}")

    lines.extend([
        "",
        "## RPG Graph",
        "",
        f"- **Nodes**: {rpg_graph.node_count}",
        f"- **Edges**: {rpg_graph.edge_count}",
        "",
        "### Node Distribution",
        "",
    ])

    # Count nodes by level
    level_counts: dict[str, int] = {}
    for node in rpg_graph.nodes.values():
        level_name = node.level.value
        level_counts[level_name] = level_counts.get(level_name, 0) + 1

    for level_name, count in sorted(level_counts.items()):
        lines.append(f"- **{level_name}**: {count}")

    lines.extend([
        "",
        "---",
        "",
        "*Generated by ZeroRepo*",
        "",
    ])

    return "\n".join(lines)
