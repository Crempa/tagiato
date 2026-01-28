"""Příkaz serve - spuštění webového UI."""

import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


def serve(
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
    model: str = typer.Option(
        "sonnet",
        "--model",
        "-m",
        help="Model pro Claude (sonnet/opus/haiku)",
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
) -> None:
    """Spustí webové rozhraní pro interaktivní zpracování fotek.

    Umožňuje procházet fotky, přidávat GPS souřadnice a generovat AI popisky
    s plnou kontrolou nad procesem.
    """
    try:
        import uvicorn
        from tagiato.web.app import create_app
        from tagiato.core.logger import set_web_mode
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
    console.print(f"  Model: {model}")
    console.print(f"  Port: {port}")
    console.print()

    # Create FastAPI app
    app = create_app(
        photos_dir=photos_dir,
        timeline_path=timeline,
        model=model,
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
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server ukončen[/yellow]")
