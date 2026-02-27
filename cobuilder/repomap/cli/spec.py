"""CLI commands for the User Specification Parser.

Implements the CLI integration for Task 2.4.6 of PRD-RPG-P2-001.
Provides sub-commands: parse, refine, conflicts, suggest, export.

Example usage::

    zerorepo spec parse spec.txt
    zerorepo spec parse spec.txt --output spec.json
    zerorepo spec refine spec.json --add "Add WebSocket support"
    zerorepo spec conflicts spec.json
    zerorepo spec suggest spec.json
    zerorepo spec export spec.json --format json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cobuilder.repomap.cli.errors import error_handler

logger = logging.getLogger(__name__)

spec_app = typer.Typer(
    name="spec",
    help="User Specification Parser – parse, refine, and validate repository specifications.",
    no_args_is_help=True,
)

_console = Console(stderr=True)
_out_console = Console()  # stdout for data output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_input(input_path: Path) -> str:
    """Read input file content.

    Args:
        input_path: Path to the input file.

    Returns:
        The file content as a string.

    Raises:
        typer.BadParameter: If the file doesn't exist or is empty.
    """
    if not input_path.exists():
        raise typer.BadParameter(f"File not found: {input_path}")
    if not input_path.is_file():
        raise typer.BadParameter(f"Not a file: {input_path}")

    content = input_path.read_text(encoding="utf-8")
    if not content.strip():
        raise typer.BadParameter(f"File is empty: {input_path}")

    return content


def _load_spec(spec_path: Path) -> "RepositorySpec":  # noqa: F821
    """Load a RepositorySpec from a JSON file.

    Args:
        spec_path: Path to the spec JSON file.

    Returns:
        A RepositorySpec instance.

    Raises:
        typer.BadParameter: If the file is invalid.
    """
    from cobuilder.repomap.spec_parser.models import RepositorySpec

    content = _read_input(spec_path)
    try:
        return RepositorySpec.from_json(content)
    except (ValueError, Exception) as exc:
        raise typer.BadParameter(
            f"Invalid spec JSON in {spec_path}: {exc}"
        )


def _write_spec(spec: "RepositorySpec", output_path: Path) -> None:  # noqa: F821
    """Write a RepositorySpec to a JSON file.

    Args:
        spec: The specification to write.
        output_path: File path to write to.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(spec.to_json(indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------


@spec_app.command()
def parse(
    input_file: Path = typer.Argument(
        ..., help="Path to natural language specification file (.txt)."
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON file for the parsed specification.",
    ),
    model: str = typer.Option(
        "gpt-4o-mini",
        "--model",
        "-m",
        help="LLM model to use for parsing.",
    ),
    detect_conflicts: bool = typer.Option(
        True,
        "--conflicts/--no-conflicts",
        help="Run conflict detection after parsing.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output raw JSON to stdout.",
    ),
) -> None:
    """Parse a natural language specification into structured JSON.

    Reads a plain-text description file and uses the LLM to extract
    structured data including languages, frameworks, platforms,
    quality attributes, and constraints.
    """
    with error_handler(_console):
        from cobuilder.repomap.llm.gateway import LLMGateway
        from cobuilder.repomap.spec_parser.conflict_detector import ConflictDetector
        from cobuilder.repomap.spec_parser.parser import ParserConfig, SpecParser

        description = _read_input(input_file)

        _console.print(f"[bold]Parsing specification from {input_file}...[/bold]")

        # Configure and run parser
        config = ParserConfig(model=model)
        gateway = LLMGateway()
        parser = SpecParser(gateway=gateway, config=config)

        spec = parser.parse(description)

        # Optionally detect conflicts
        if detect_conflicts:
            _console.print("[dim]Running conflict detection...[/dim]")
            detector = ConflictDetector()
            conflicts = detector.detect_and_attach(spec)
            if conflicts:
                _console.print(
                    f"[yellow]Found {len(conflicts)} conflict(s)[/yellow]"
                )

        # Output
        if json_output:
            _out_console.print(spec.to_json(indent=2))
        else:
            _print_spec_summary(spec)

        if output:
            _write_spec(spec, output)
            _console.print(f"\n[green]Saved to {output}[/green]")


# ---------------------------------------------------------------------------
# refine
# ---------------------------------------------------------------------------


@spec_app.command()
def refine(
    spec_file: Path = typer.Argument(
        ..., help="Path to existing spec JSON file."
    ),
    add: Optional[str] = typer.Option(
        None,
        "--add",
        "-a",
        help="Add a requirement (natural language).",
    ),
    clarify: Optional[str] = typer.Option(
        None,
        "--clarify",
        "-q",
        help="Clarification question (format: 'question|answer').",
    ),
    context: Optional[str] = typer.Option(
        None,
        "--context",
        "-c",
        help="Additional context for the refinement.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for the refined spec (default: overwrite input).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output refined spec as JSON to stdout.",
    ),
) -> None:
    """Refine an existing specification with additional requirements.

    Supports adding requirements and answering clarification questions.
    Each refinement is recorded in the specification's history.
    """
    with error_handler(_console):
        from cobuilder.repomap.llm.gateway import LLMGateway
        from cobuilder.repomap.spec_parser.refinement import RefinerConfig, SpecRefiner

        if not add and not clarify:
            raise typer.BadParameter(
                "Must specify at least one refinement: --add or --clarify"
            )

        spec = _load_spec(spec_file)
        gateway = LLMGateway()
        refiner = SpecRefiner(gateway=gateway)

        if add:
            _console.print(f"[bold]Adding requirement:[/bold] {add}")
            spec = refiner.add_requirement(spec, add, context=context)
            _console.print("[green]Requirement added.[/green]")

        if clarify:
            parts = clarify.split("|", 1)
            if len(parts) != 2:
                raise typer.BadParameter(
                    "Clarification must be 'question|answer' format"
                )
            question, answer = parts[0].strip(), parts[1].strip()
            _console.print(
                f"[bold]Clarifying:[/bold] {question} -> {answer}"
            )
            spec = refiner.clarify(spec, question, answer, context=context)
            _console.print("[green]Clarification applied.[/green]")

        # Output
        if json_output:
            _out_console.print(spec.to_json(indent=2))
        else:
            _print_spec_summary(spec)

        out_path = output or spec_file
        _write_spec(spec, out_path)
        _console.print(f"\n[green]Saved to {out_path}[/green]")


# ---------------------------------------------------------------------------
# conflicts
# ---------------------------------------------------------------------------


@spec_app.command()
def conflicts(
    spec_file: Path = typer.Argument(
        ..., help="Path to spec JSON file to check for conflicts."
    ),
    attach: bool = typer.Option(
        False,
        "--attach",
        help="Attach detected conflicts to the spec and save.",
    ),
    use_llm: bool = typer.Option(
        True,
        "--llm/--no-llm",
        help="Use LLM for nuanced conflict detection.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output conflicts as JSON.",
    ),
) -> None:
    """Detect conflicting requirements in a specification.

    Checks for rule-based conflicts (e.g., backend-only + React) and
    optionally uses LLM for nuanced detection.
    """
    with error_handler(_console):
        from cobuilder.repomap.spec_parser.conflict_detector import (
            ConflictDetector,
            DetectorConfig,
        )

        spec = _load_spec(spec_file)

        config = DetectorConfig(use_llm=use_llm)
        detector = ConflictDetector(config=config)

        _console.print("[bold]Detecting conflicts...[/bold]")

        if attach:
            detected = detector.detect_and_attach(spec)
            _write_spec(spec, spec_file)
            _console.print(
                f"[green]Attached {len(detected)} conflict(s) to {spec_file}[/green]"
            )
        else:
            detected = detector.detect(spec)

        if json_output:
            output_data = [
                {
                    "description": c.description,
                    "severity": c.severity.value,
                    "conflicting_fields": c.conflicting_fields,
                    "suggestion": c.suggestion,
                }
                for c in detected
            ]
            typer.echo(json.dumps(output_data, indent=2))
            return

        if not detected:
            _console.print("[green]No conflicts detected.[/green]")
            return

        _console.print(
            f"\n[bold]Found {len(detected)} conflict(s):[/bold]\n"
        )

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Severity", width=8)
        table.add_column("Description", min_width=30)
        table.add_column("Items", min_width=20)
        table.add_column("Suggestion", min_width=20)

        for i, conflict in enumerate(detected, start=1):
            severity_style = {
                "ERROR": "bold red",
                "WARNING": "yellow",
                "INFO": "dim",
            }.get(conflict.severity.value, "")

            table.add_row(
                str(i),
                f"[{severity_style}]{conflict.severity.value}[/{severity_style}]",
                conflict.description,
                ", ".join(conflict.conflicting_fields[:3]),
                conflict.suggestion or "-",
            )

        _out_console.print(table)


# ---------------------------------------------------------------------------
# suggest
# ---------------------------------------------------------------------------


@spec_app.command()
def suggest(
    spec_file: Path = typer.Argument(
        ..., help="Path to spec JSON file."
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output suggestions as JSON.",
    ),
) -> None:
    """Get LLM-powered improvement suggestions for a specification."""
    with error_handler(_console):
        from cobuilder.repomap.llm.gateway import LLMGateway
        from cobuilder.repomap.spec_parser.refinement import SpecRefiner

        spec = _load_spec(spec_file)
        gateway = LLMGateway()
        refiner = SpecRefiner(gateway=gateway)

        _console.print("[bold]Generating improvement suggestions...[/bold]")

        response = refiner.suggest_improvements(spec)

        if json_output:
            output_data = [
                {
                    "area": s.area,
                    "suggestion": s.suggestion,
                    "priority": s.priority,
                }
                for s in response.suggestions
            ]
            typer.echo(json.dumps(output_data, indent=2))
            return

        if not response.suggestions:
            _console.print("[green]No improvement suggestions.[/green]")
            return

        _console.print(
            f"\n[bold]{len(response.suggestions)} suggestion(s):[/bold]\n"
        )

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Priority", width=10)
        table.add_column("Area", min_width=15)
        table.add_column("Suggestion", min_width=40)

        for i, suggestion in enumerate(response.suggestions, start=1):
            table.add_row(
                str(i),
                suggestion.priority,
                suggestion.area,
                suggestion.suggestion,
            )

        _out_console.print(table)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@spec_app.command(name="export")
def export_cmd(
    spec_file: Path = typer.Argument(
        ..., help="Path to spec JSON file."
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file path.",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json, summary.",
    ),
) -> None:
    """Export a specification to various formats."""
    with error_handler(_console):
        spec = _load_spec(spec_file)

        if format == "json":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(spec.to_json(indent=2), encoding="utf-8")
            _console.print(f"[green]Exported JSON to {output}[/green]")

        elif format == "summary":
            summary = _build_summary_text(spec)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(summary, encoding="utf-8")
            _console.print(f"[green]Exported summary to {output}[/green]")

        else:
            raise typer.BadParameter(
                f"Unknown format '{format}'. Use: json, summary"
            )


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@spec_app.command()
def history(
    spec_file: Path = typer.Argument(
        ..., help="Path to spec JSON file."
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output history as JSON.",
    ),
) -> None:
    """Show refinement history for a specification."""
    with error_handler(_console):
        spec = _load_spec(spec_file)

        entries = spec.refinement_history

        if json_output:
            output_data = [
                {
                    "action": e.action,
                    "details": e.details,
                    "timestamp": str(e.timestamp),
                }
                for e in entries
            ]
            typer.echo(json.dumps(output_data, indent=2))
            return

        if not entries:
            _console.print("[dim]No refinement history.[/dim]")
            return

        _console.print(
            f"\n[bold]Refinement history ({len(entries)} entries):[/bold]\n"
        )

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Action", width=12)
        table.add_column("Details", min_width=40)
        table.add_column("Timestamp", width=20)

        for i, entry in enumerate(entries, start=1):
            table.add_row(
                str(i),
                entry.action,
                entry.details[:80] + "..." if len(entry.details) > 80 else entry.details,
                str(entry.timestamp)[:19],
            )

        _out_console.print(table)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _print_spec_summary(spec: "RepositorySpec") -> None:  # noqa: F821
    """Print a rich summary of a RepositorySpec."""
    from cobuilder.repomap.spec_parser.models import ConflictSeverity

    _console.print("\n[bold]Specification Summary[/bold]\n")

    # Core
    desc_preview = spec.description[:200]
    if len(spec.description) > 200:
        desc_preview += "..."
    _console.print(f"  [dim]Description:[/dim] {desc_preview}")

    if spec.core_functionality:
        _console.print(f"  [dim]Core:[/dim] {spec.core_functionality}")

    # Technical
    tech = spec.technical_requirements
    if tech.languages:
        _console.print(
            f"  [dim]Languages:[/dim] {', '.join(tech.languages)}"
        )
    if tech.frameworks:
        _console.print(
            f"  [dim]Frameworks:[/dim] {', '.join(tech.frameworks)}"
        )
    if tech.platforms:
        _console.print(
            f"  [dim]Platforms:[/dim] {', '.join(tech.platforms)}"
        )
    if tech.scope:
        _console.print(f"  [dim]Scope:[/dim] {tech.scope.value}")
    if tech.deployment_targets:
        targets = [t.value for t in tech.deployment_targets]
        _console.print(
            f"  [dim]Deploy:[/dim] {', '.join(targets)}"
        )

    # Quality
    qa = spec.quality_attributes
    attrs = []
    if qa.performance:
        attrs.append(f"perf={qa.performance[:30]}")
    if qa.security:
        attrs.append(f"sec={qa.security[:30]}")
    if qa.scalability:
        attrs.append(f"scale={qa.scalability[:30]}")
    if attrs:
        _console.print(f"  [dim]Quality:[/dim] {'; '.join(attrs)}")

    # Constraints
    if spec.constraints:
        _console.print(
            f"  [dim]Constraints:[/dim] {len(spec.constraints)} "
            f"({len(spec.must_have_constraints)} must-have)"
        )

    # Conflicts
    if spec.conflicts:
        error_count = sum(
            1 for c in spec.conflicts
            if c.severity == ConflictSeverity.ERROR
        )
        style = "red" if error_count > 0 else "yellow"
        _console.print(
            f"  [{style}]Conflicts: {len(spec.conflicts)} "
            f"({error_count} errors)[/{style}]"
        )

    # History
    if spec.refinement_history:
        _console.print(
            f"  [dim]Refinements:[/dim] {len(spec.refinement_history)} entries"
        )


def _build_summary_text(spec: "RepositorySpec") -> str:  # noqa: F821
    """Build a plain text summary of a RepositorySpec."""
    lines = [
        f"Repository Specification Summary",
        f"================================",
        f"",
        f"Description: {spec.description}",
        f"",
    ]

    if spec.core_functionality:
        lines.append(f"Core Functionality: {spec.core_functionality}")
        lines.append("")

    tech = spec.technical_requirements
    if tech.languages:
        lines.append(f"Languages: {', '.join(tech.languages)}")
    if tech.frameworks:
        lines.append(f"Frameworks: {', '.join(tech.frameworks)}")
    if tech.platforms:
        lines.append(f"Platforms: {', '.join(tech.platforms)}")
    if tech.scope:
        lines.append(f"Scope: {tech.scope.value}")
    if tech.deployment_targets:
        lines.append(
            f"Deployment: {', '.join(t.value for t in tech.deployment_targets)}"
        )

    lines.append("")

    qa = spec.quality_attributes
    if qa.performance:
        lines.append(f"Performance: {qa.performance}")
    if qa.security:
        lines.append(f"Security: {qa.security}")
    if qa.scalability:
        lines.append(f"Scalability: {qa.scalability}")
    if qa.reliability:
        lines.append(f"Reliability: {qa.reliability}")

    if spec.constraints:
        lines.append("")
        lines.append(f"Constraints ({len(spec.constraints)}):")
        for c in spec.constraints:
            lines.append(f"  [{c.priority.value}] {c.description}")

    if spec.conflicts:
        lines.append("")
        lines.append(f"Conflicts ({len(spec.conflicts)}):")
        for c in spec.conflicts:
            lines.append(f"  [{c.severity.value}] {c.description}")

    lines.append("")
    return "\n".join(lines)
