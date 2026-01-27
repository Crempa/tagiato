"""Příkaz enrich - hlavní pipeline pro zpracování fotek."""

from pathlib import Path
from typing import Optional
import time

import typer
from rich.console import Console

from tagiato.core.config import Config
from tagiato.core.pipeline import Pipeline
from tagiato.core.exceptions import TagiatoError

console = Console()


def enrich(
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
    max_time_gap: int = typer.Option(
        30,
        "--max-time-gap",
        "-g",
        help="Maximální časový rozdíl mezi fotkou a GPS bodem (v minutách)",
        min=1,
        max=120,
    ),
    model: str = typer.Option(
        "sonnet",
        "--model",
        "-m",
        help="Model pro Claude (sonnet/opus/haiku)",
    ),
    thumbnail_size: int = typer.Option(
        1024,
        "--thumbnail-size",
        "-s",
        help="Velikost náhledu (kratší strana v px)",
        min=256,
        max=2048,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Podrobný výpis volání nástrojů s parametry",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        "-r",
        help="Resetovat průběh a začít zpracování od začátku",
    ),
    xmp: bool = typer.Option(
        False,
        "--xmp",
        help="Generovat XMP sidecar soubory",
    ),
) -> None:
    """Zpracuje fotky - přidá GPS souřadnice a AI popisky.

    Hlavní příkaz pro celou pipeline: skenování fotek, párování GPS z timeline,
    geocoding, generování popisků od Claude, zápis do EXIF a XMP.
    """
    start_time = time.time()

    # Vytvořit config pro přístup k cestám
    config = Config(
        photos_dir=photos_dir,
        timeline_path=timeline,
        max_time_gap=max_time_gap,
        model=model,
        thumbnail_size=thumbnail_size,
        verbose=verbose,
        xmp=xmp,
    )

    # Reset stavu pokud je požadován
    if reset and config.state_file.exists():
        config.state_file.unlink()
        console.print("[yellow]Stav resetován - začínám od začátku[/yellow]")

    def progress_callback(current: int, total: int, filename: str, status: str) -> None:
        console.print(f"[{current}/{total}] {filename} - {status}")

    try:
        pipeline = Pipeline(config=config, progress_callback=progress_callback)
        stats = pipeline.run()

        # Výsledky
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        console.print()
        console.print(f"[green]Hotovo![/green] Zpracováno {stats['processed']} fotek za {minutes}m {seconds}s")
        console.print(f"  - {stats['with_description']} s popisky")
        console.print(f"  - {stats['without_description']} bez popisku (nerozpoznáno)")
        console.print(f"  - {stats['gps_refined']} GPS upřesněno AI")

        if stats['errors'] > 0:
            console.print(f"  - [red]{stats['errors']} chyb[/red]")

        console.print()
        console.print(f"Výstupy uloženy do: {config.descriptions_file}")

    except TagiatoError as e:
        console.print(f"[red]Chyba:[/red] {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Přerušeno uživatelem[/yellow]")
        raise typer.Exit(130)
