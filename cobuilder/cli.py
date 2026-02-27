"""CoBuilder CLI — command groups for repomap, pipeline, and agents."""

import typer

from cobuilder.repomap.cli.commands import app as repomap_app

app = typer.Typer(name="cobuilder", help="CoBuilder: unified codebase intelligence")

pipeline_app = typer.Typer(help="Pipeline commands")
agents_app = typer.Typer(help="Agent orchestration commands")

app.add_typer(repomap_app, name="repomap")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(agents_app, name="agents")


@pipeline_app.command("create")
def pipeline_create(
    sd: str = typer.Option(..., "--sd", help="Path to Solution Design file"),
    repo: str = typer.Option(..., "--repo", help="Repository name (registered in .repomap/)"),
    output: str = typer.Option("", "--output", help="Output .dot file path (default: stdout)"),
    prd: str = typer.Option("", "--prd", help="PRD reference (e.g. PRD-COBUILDER-001)"),
    target_dir: str = typer.Option("", "--target-dir", help="Implementation repo root"),
    skip_enrichment: bool = typer.Option(False, "--skip-enrichment", help="Skip LLM enrichment"),
    skip_taskmaster: bool = typer.Option(False, "--skip-taskmaster", help="Skip TaskMaster parse"),
) -> None:
    """Create an Attractor DOT pipeline from a Solution Design + RepoMap baseline."""
    from pathlib import Path
    from cobuilder.pipeline.generate import ensure_baseline, collect_repomap_nodes, filter_nodes_by_sd_relevance, cross_reference_beads, generate_pipeline_dot
    from cobuilder.pipeline.enrichers import EnrichmentPipeline
    from cobuilder.pipeline.taskmaster_bridge import run_taskmaster_parse
    from cobuilder.pipeline.sd_enricher import write_all_enrichments

    project_root = Path(".")
    sd_path = Path(sd)

    # Step 1+2: Ensure baseline, collect nodes
    typer.echo(f"[1/7] Checking RepoMap baseline for '{repo}'...")
    ensure_baseline(repo, project_root)

    typer.echo("[2/7] Collecting RepoMap nodes...")
    nodes = collect_repomap_nodes(repo, project_root)
    typer.echo(f"      Found {len(nodes)} MODIFIED/NEW nodes")

    # Step 2.5: SD relevance filter
    sd_content = sd_path.read_text() if sd_path.exists() else ""
    typer.echo(f"[2.5/7] Filtering nodes by SD relevance ({len(nodes)} candidates)...")
    nodes = filter_nodes_by_sd_relevance(nodes, sd_content)
    typer.echo(f"        Retained {len(nodes)} SD-relevant nodes")

    # Step 3: TaskMaster parse
    taskmaster_tasks = {}
    if not skip_taskmaster:
        typer.echo("[3/7] Running TaskMaster parse...")
        taskmaster_tasks = run_taskmaster_parse(str(sd_path.resolve()), str(project_root.resolve()))
    else:
        typer.echo("[3/7] Skipping TaskMaster parse (--skip-taskmaster)")

    # Step 4: Beads cross-reference
    typer.echo("[4/7] Cross-referencing with beads...")
    nodes = cross_reference_beads(nodes, prd)

    # Step 5: LLM enrichment
    if not skip_enrichment:
        typer.echo("[5/7] Running LLM enrichment pipeline (5 enrichers)...")
        pipeline = EnrichmentPipeline()
        nodes = pipeline.enrich(nodes, {}, sd_content)
    else:
        typer.echo("[5/7] Skipping LLM enrichment (--skip-enrichment)")

    # Step 6: DOT rendering
    typer.echo("[6/7] Rendering DOT pipeline...")
    dot = generate_pipeline_dot(
        prd_ref=prd or f"PRD-{repo.upper()}",
        nodes=nodes,
        solution_design=sd,
        target_dir=target_dir,
    )

    # Step 7: SD v2 enrichment
    typer.echo("[7/7] Writing SD v2 enrichment blocks...")
    count = write_all_enrichments(str(sd_path), nodes, taskmaster_tasks)
    typer.echo(f"      Wrote {count} enrichment blocks to {sd}")

    # Output DOT
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(dot)
        typer.echo(f"Pipeline written to: {output}")
    else:
        typer.echo(dot)
