import typer

from .assemble_fragments import main as assemble_fragments
from .extract_patches import main as extract_patches
from .summarise_changes import main as summarise_changes
from .summarise_fragments import main as summarise_fragments

app = typer.Typer(help="vigilia - tools for reviewing code changes")


app.command(name="extract-patches")(extract_patches)
app.command(name="assemble-fragments")(assemble_fragments)
app.command(name="summarise-fragments")(summarise_fragments)
app.command(name="summarise-changes")(summarise_changes)


def main() -> None:
    app()
