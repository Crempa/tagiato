"""Příkaz apply - aplikace editovaného descriptions.md do EXIF a XMP."""

from pathlib import Path

import typer
from rich.console import Console

from tagiato.core.config import Config
from tagiato.core.exceptions import TagiatoError, ExifError
from tagiato.services.md_parser import MdParser
from tagiato.services.exif_writer import ExifWriter
from tagiato.services.xmp_writer import XmpWriter

console = Console()


def apply(
    photos_dir: Path = typer.Argument(
        ...,
        help="Cesta ke složce s fotkami",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Aplikuje úpravy z descriptions.md zpět do EXIF a XMP.

    Přečte descriptions.md, extrahuje GPS a popisky, a zapíše je
    do odpovídajících JPEG souborů a XMP sidecar souborů.
    """
    config = Config(photos_dir=photos_dir)

    if not config.descriptions_file.exists():
        console.print(f"[red]Chyba:[/red] Soubor {config.descriptions_file} neexistuje")
        console.print("Nejdříve spusťte 'tagiato enrich' pro vygenerování popisků.")
        raise typer.Exit(1)

    parser = MdParser()
    exif_writer = ExifWriter()
    xmp_writer = XmpWriter()

    try:
        photos = parser.parse(config.descriptions_file)

        if not photos:
            console.print("[yellow]Žádné fotky k aplikování[/yellow]")
            raise typer.Exit(0)

        console.print(f"Načteno {len(photos)} fotek z descriptions.md")

        applied = 0
        errors = 0

        for photo in photos:
            photo_path = photos_dir / photo.filename

            if not photo_path.exists():
                console.print(f"[yellow]Přeskočeno:[/yellow] {photo.filename} (soubor neexistuje)")
                continue

            try:
                # Zápis do EXIF
                exif_writer.write(
                    photo_path=photo_path,
                    gps=photo.gps,
                    description=photo.description if photo.description else None,
                    skip_existing_gps=False,  # Přepsat i existující GPS z MD
                )

                # Zápis do XMP
                xmp_writer.write(
                    photo_path=photo_path,
                    gps=photo.gps,
                    description=photo.description if photo.description else None,
                )

                console.print(f"[green]✓[/green] {photo.filename}")
                applied += 1

            except ExifError as e:
                console.print(f"[red]✗[/red] {photo.filename}: {e}")
                errors += 1

        console.print()
        console.print(f"[green]Hotovo![/green] Aplikováno {applied} fotek, {errors} chyb")

    except TagiatoError as e:
        console.print(f"[red]Chyba:[/red] {e}")
        raise typer.Exit(1)
