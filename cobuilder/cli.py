"""CoBuilder CLI — command groups for repomap, pipeline, and agents."""

import typer

from cobuilder.repomap.cli.commands import app as repomap_app

app = typer.Typer(name="cobuilder", help="CoBuilder: unified codebase intelligence")

pipeline_app = typer.Typer(help="Pipeline commands")
agents_app = typer.Typer(help="Agent orchestration commands")

app.add_typer(repomap_app, name="repomap")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(agents_app, name="agents")
