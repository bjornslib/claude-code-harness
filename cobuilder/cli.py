"""CoBuilder CLI — command groups for repomap, pipeline, and agents."""

import typer

app = typer.Typer(name="cobuilder", help="CoBuilder: unified codebase intelligence")

repomap_app = typer.Typer(help="RepoMap commands")
pipeline_app = typer.Typer(help="Pipeline commands")
agents_app = typer.Typer(help="Agent orchestration commands")

app.add_typer(repomap_app, name="repomap")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(agents_app, name="agents")
