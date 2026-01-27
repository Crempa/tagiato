"""Příkaz reset - smazání GPS a popisků z EXIF."""

from pathlib import Path

import typer
from rich.console import Console

from tagiato.services.photo_scanner import PhotoScanner
from tagiato.services.exif_writer import ExifWriter
from tagiato.core.exceptions import TagiatoError

console = Console()


def reset(
    photos_dir: Path = typer.Argument(
        ...,
        help="Cesta ke složce s fotkami",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    gps: bool = typer.Option(
        True,
        "--gps/--no-gps",
        help="Smazat GPS souřadnice",
    ),
    description: bool = typer.Option(
        True,
        "--description/--no-description",
        "-d/-D",
        help="Smazat popisky",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Jen ukázat co by se smazalo, nic neměnit",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Neptat se na potvrzení",
    ),
) -> None:
    """Smaže GPS souřadnice a/nebo popisky z EXIF metadat fotek.

    Příklad použití:
        tagiato reset ~/Photos/Trip              # Smaže GPS i popisky
        tagiato reset ~/Photos/Trip --no-gps    # Smaže jen popisky
        tagiato reset ~/Photos/Trip --no-description  # Smaže jen GPS
        tagiato reset ~/Photos/Trip --dry-run   # Jen ukáže co by se smazalo
    """
    if not gps and not description:
        console.print("[yellow]Není co mazat - zadejte --gps a/nebo --description[/yellow]")
        raise typer.Exit(0)

    try:
        scanner = PhotoScanner()
        exif_writer = ExifWriter()

        photos = scanner.scan(photos_dir)

        if not photos:
            console.print("[yellow]Žádné fotky nenalezeny[/yellow]")
            raise typer.Exit(0)

        what = []
        if gps:
            what.append("GPS")
        if description:
            what.append("popisky")
        what_str = " a ".join(what)

        if dry_run:
            console.print(f"[cyan]Dry run - nalezeno {len(photos)} fotek[/cyan]")
            for photo in photos:
                console.print(f"  {photo.filename}")
            console.print(f"\n[cyan]Bylo by smazáno: {what_str}[/cyan]")
            raise typer.Exit(0)

        if not force:
            console.print(f"[yellow]Chystáte se smazat {what_str} z {len(photos)} fotek.[/yellow]")
            confirm = typer.confirm("Pokračovat?")
            if not confirm:
                console.print("[yellow]Zrušeno[/yellow]")
                raise typer.Exit(0)

        cleared = 0
        errors = 0

        for idx, photo in enumerate(photos, 1):
            console.print(f"[{idx}/{len(photos)}] {photo.filename}...", end=" ")
            try:
                if exif_writer.clear(photo.path, clear_gps=gps, clear_description=description):
                    console.print("[green]OK[/green]")
                    cleared += 1
                else:
                    console.print("[dim]nic ke smazání[/dim]")
            except Exception as e:
                console.print(f"[red]chyba: {e}[/red]")
                errors += 1

        console.print()
        console.print(f"[green]Hotovo![/green] Vyčištěno {cleared} fotek")
        if errors:
            console.print(f"[red]{errors} chyb[/red]")

    except TagiatoError as e:
        console.print(f"[red]Chyba:[/red] {e}")
        raise typer.Exit(1)
