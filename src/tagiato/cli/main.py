"""Hlavní CLI definice pro Tagiato."""

import typer

from tagiato import __version__
from tagiato.cli.commands.enrich import enrich
from tagiato.cli.commands.apply import apply
from tagiato.cli.commands.export import export
from tagiato.cli.commands.status import status
from tagiato.cli.commands.reset import reset

app = typer.Typer(
    name="tagiato",
    help="CLI nástroj pro automatické přidání GPS souřadnic a AI-generovaných popisků k JPEG fotografiím.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        print(f"tagiato {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Zobrazí verzi programu",
    ),
) -> None:
    """Tagiato - obohacení fotografií o GPS a AI popisky."""
    pass


# Registrovat příkazy
app.command(name="enrich")(enrich)
app.command(name="apply")(apply)
app.command(name="export")(export)
app.command(name="status")(status)
app.command(name="reset")(reset)


if __name__ == "__main__":
    app()
