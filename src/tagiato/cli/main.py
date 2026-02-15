"""Hlavní CLI definice pro Tagiato."""

import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from tagiato import __version__

console = Console()


def version_callback(value: bool) -> None:
    if value:
        print(f"tagiato {__version__}")
        raise typer.Exit()


def main(
    photos_dir: Path = typer.Argument(
        ...,
        help="Cesta ke složce s fotkami",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    timeline: Optional[Path] = typer.Option(
        None,
        "--timeline",
        "-t",
        help="Cesta k Google Timeline JSON souboru",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    describe_provider: str = typer.Option(
        "claude",
        "--describe-provider",
        help="Provider pro generování popisků (claude/gemini/openai)",
    ),
    describe_model: str = typer.Option(
        "sonnet",
        "--describe-model",
        help="Model pro popisky (claude: sonnet/opus/haiku, gemini: flash/pro/ultra, openai: o3/o4-mini/gpt-5.2)",
    ),
    locate_provider: str = typer.Option(
        "claude",
        "--locate-provider",
        help="Provider pro lokalizaci (claude/gemini/openai)",
    ),
    locate_model: str = typer.Option(
        "sonnet",
        "--locate-model",
        help="Model pro lokalizaci (claude: sonnet/opus/haiku, gemini: flash/pro/ultra, openai: o3/o4-mini/gpt-5.2)",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port pro webový server",
        min=1024,
        max=65535,
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Neotevírat automaticky prohlížeč",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Zobrazí verzi programu",
    ),
) -> None:
    """Spustí webové rozhraní pro interaktivní zpracování fotek.

    Umožňuje procházet fotky, přidávat GPS souřadnice a generovat AI popisky
    s plnou kontrolou nad procesem.
    """
    try:
        import uvicorn
        from tagiato.web.app import create_app
        from tagiato.core.logger import set_web_mode
        from tagiato.services.exif_writer import is_exiftool_available
    except ImportError as e:
        console.print("[red]Chyba:[/red] Web závislosti nejsou nainstalované.")
        console.print("Nainstalujte je pomocí: pip install tagiato[web]")
        raise typer.Exit(1)

    # Aktivovat web logging
    set_web_mode(True)

    console.print(f"[blue]Tagiato Web UI[/blue]")
    console.print(f"  Složka: {photos_dir}")
    if timeline:
        console.print(f"  Timeline: {timeline}")
    console.print(f"  Popisky: {describe_provider}/{describe_model}")
    console.print(f"  Lokalizace: {locate_provider}/{locate_model}")
    console.print(f"  Port: {port}")

    # Kontrola exiftool
    if not is_exiftool_available():
        console.print()
        console.print("[yellow]⚠ Varování:[/yellow] exiftool není nainstalován")
        console.print("  Zápis názvu lokality (IPTC:Sub-location) nebude dostupný.")
        console.print("  Instalace: brew install exiftool (macOS) nebo apt install libimage-exiftool-perl (Linux)")

    console.print()

    # Create FastAPI app
    fastapi_app = create_app(
        photos_dir=photos_dir,
        timeline_path=timeline,
        describe_provider=describe_provider,
        describe_model=describe_model,
        locate_provider=locate_provider,
        locate_model=locate_model,
    )

    # Open browser
    url = f"http://localhost:{port}"
    if not no_browser:
        console.print(f"[green]Otevírám prohlížeč:[/green] {url}")
        webbrowser.open(url)
    else:
        console.print(f"[green]Aplikace běží na:[/green] {url}")

    console.print()
    console.print("[dim]Ctrl+C pro ukončení[/dim]")
    console.print()

    # Run server
    try:
        uvicorn.run(fastapi_app, host="0.0.0.0", port=port, log_level="warning")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server ukončen[/yellow]")


app = typer.Typer()
app.command()(main)


if __name__ == "__main__":
    app()
