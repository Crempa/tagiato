"""Konfigurace pro Tagiato."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Konfigurace pro zpracování fotek."""

    # Cesta ke složce s fotkami
    photos_dir: Path

    # Cesta k timeline JSON (volitelné)
    timeline_path: Optional[Path] = None

    # Maximální časový rozdíl mezi fotkou a GPS bodem (v minutách)
    max_time_gap: int = 30

    # Model pro Claude (sonnet/opus/haiku)
    model: str = "sonnet"

    # Velikost náhledu (kratší strana v px)
    thumbnail_size: int = 1024

    # Verbose mode
    verbose: bool = False

    # Generovat XMP sidecar soubory
    xmp: bool = False

    # Pracovní složka
    @property
    def work_dir(self) -> Path:
        return self.photos_dir / ".tagiato"

    @property
    def thumbnails_dir(self) -> Path:
        return self.work_dir / "thumbnails"

    @property
    def state_file(self) -> Path:
        return self.work_dir / "state.json"

    @property
    def geocode_cache_file(self) -> Path:
        return self.work_dir / "geocode_cache.json"

    @property
    def descriptions_file(self) -> Path:
        return self.photos_dir / "descriptions.md"

    def ensure_dirs(self) -> None:
        """Vytvoří potřebné složky."""
        self.work_dir.mkdir(exist_ok=True)
        self.thumbnails_dir.mkdir(exist_ok=True)
