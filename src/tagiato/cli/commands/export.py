"""Příkaz export - export do CSV nebo XMP."""

import csv
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from tagiato.core.config import Config
from tagiato.services.md_parser import MdParser
from tagiato.services.xmp_writer import XmpWriter

console = Console()


def export(
    photos_dir: Path = typer.Argument(
        ...,
        help="Cesta ke složce s fotkami",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Formát exportu (csv/xmp)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Cesta k výstupnímu souboru (jen pro CSV)",
    ),
) -> None:
    """Exportuje data do CSV nebo XMP formátu.

    CSV export vytvoří soubor se všemi metadaty fotek.
    XMP export vytvoří sidecar soubory pro každou fotku.
    """
    config = Config(photos_dir=photos_dir)

    if not config.descriptions_file.exists():
        console.print(f"[red]Chyba:[/red] Soubor {config.descriptions_file} neexistuje")
        console.print("Nejdříve spusťte 'tagiato enrich' pro vygenerování popisků.")
        raise typer.Exit(1)

    parser = MdParser()
    photos = parser.parse(config.descriptions_file)

    if not photos:
        console.print("[yellow]Žádná data k exportu[/yellow]")
        raise typer.Exit(0)

    if format.lower() == "csv":
        _export_csv(photos, photos_dir, output)
    elif format.lower() == "xmp":
        _export_xmp(photos, photos_dir)
    else:
        console.print(f"[red]Neznámý formát:[/red] {format}")
        console.print("Podporované formáty: csv, xmp")
        raise typer.Exit(1)


def _export_csv(photos: list, photos_dir: Path, output: Optional[Path]) -> None:
    """Exportuje do CSV."""
    output_path = output or photos_dir / "photos_export.csv"

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Hlavička
        writer.writerow(["filename", "gps_lat", "gps_lng", "description"])

        # Data
        for photo in photos:
            lat = f"{photo.gps.latitude:.6f}" if photo.gps else ""
            lng = f"{photo.gps.longitude:.6f}" if photo.gps else ""
            writer.writerow([photo.filename, lat, lng, photo.description])

    console.print(f"[green]Hotovo![/green] Exportováno {len(photos)} fotek do {output_path}")


def _export_xmp(photos: list, photos_dir: Path) -> None:
    """Exportuje do XMP sidecar souborů."""
    xmp_writer = XmpWriter()
    exported = 0

    for photo in photos:
        photo_path = photos_dir / photo.filename

        if not photo_path.exists():
            console.print(f"[yellow]Přeskočeno:[/yellow] {photo.filename} (soubor neexistuje)")
            continue

        xmp_writer.write(
            photo_path=photo_path,
            gps=photo.gps,
            description=photo.description if photo.description else None,
        )
        exported += 1

    console.print(f"[green]Hotovo![/green] Vytvořeno {exported} XMP souborů")
