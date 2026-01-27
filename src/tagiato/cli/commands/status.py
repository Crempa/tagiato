"""Příkaz status - kontrola stavu zpracování."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from tagiato.core.config import Config
from tagiato.state.manager import StateManager
from tagiato.services.photo_scanner import PhotoScanner

console = Console()


def status(
    photos_dir: Path = typer.Argument(
        ...,
        help="Cesta ke složce s fotkami",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Zobrazí stav zpracování složky s fotkami."""
    config = Config(photos_dir=photos_dir)

    # Zkontrolovat existenci pracovní složky
    if not config.work_dir.exists():
        console.print(f"[yellow]Složka nebyla dosud zpracována[/yellow]")
        console.print(f"Spusťte 'tagiato enrich {photos_dir}' pro zahájení zpracování.")
        return

    # Načíst stav
    state_manager = StateManager(config.state_file)
    state_manager.load()
    stats = state_manager.get_stats()

    if not stats:
        console.print("[yellow]Žádná data o stavu[/yellow]")
        return

    # Spočítat aktuální fotky
    scanner = PhotoScanner()
    current_photos = scanner.scan(photos_dir)
    current_count = len(current_photos)

    # Zobrazit stav
    table = Table(title=f"Stav zpracování: {photos_dir.name}")

    table.add_column("Metrika", style="cyan")
    table.add_column("Hodnota", style="green")

    table.add_row("Fotek ve složce", str(current_count))
    table.add_row("Zpracováno", f"{stats['processed']}/{stats['total']}")
    table.add_row("S popiskem", str(stats['with_description']))
    table.add_row("Bez popisku", str(stats['without_description']))
    table.add_row("S GPS", str(stats['with_gps']))
    table.add_row("GPS upřesněno AI", str(stats['gps_refined']))

    if stats['errors'] > 0:
        table.add_row("Chyby", f"[red]{stats['errors']}[/red]")

    table.add_row("Zahájeno", stats['started_at'][:19] if stats['started_at'] else "-")

    if stats['completed_at']:
        table.add_row("Dokončeno", stats['completed_at'][:19])
        table.add_row("Stav", "[green]Dokončeno[/green]")
    else:
        table.add_row("Stav", "[yellow]Nedokončeno[/yellow]")

    console.print(table)

    # Kontrola nových fotek
    if current_count > stats['total']:
        new_count = current_count - stats['total']
        console.print()
        console.print(f"[yellow]Nalezeno {new_count} nových fotek od posledního zpracování[/yellow]")
        console.print(f"Spusťte 'tagiato enrich {photos_dir}' pro jejich zpracování.")

    # Kontrola descriptions.md
    if config.descriptions_file.exists():
        console.print()
        console.print(f"Soubor s popisky: {config.descriptions_file}")
