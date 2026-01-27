"""Model pro fotografii."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from tagiato.models.location import Location, GPSCoordinates


@dataclass
class Photo:
    """Reprezentace fotografie s metadaty."""

    path: Path
    timestamp: Optional[datetime] = None
    original_gps: Optional[GPSCoordinates] = None  # GPS z EXIF (pokud existuje)
    matched_location: Optional[Location] = None  # Lokace z timeline
    refined_gps: Optional[GPSCoordinates] = None  # Upřesněné GPS od AI
    description: str = ""
    thumbnail_path: Optional[Path] = None
    processed: bool = False
    error: Optional[str] = None

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def has_original_gps(self) -> bool:
        return self.original_gps is not None

    @property
    def final_gps(self) -> Optional[GPSCoordinates]:
        """Vrátí nejlepší dostupné GPS souřadnice.

        Priorita: refined_gps > matched_location > original_gps
        """
        if self.refined_gps:
            return self.refined_gps
        if self.matched_location:
            return self.matched_location.coordinates
        return self.original_gps

    @property
    def place_name(self) -> Optional[str]:
        """Vrátí název místa pokud je dostupný."""
        if self.matched_location:
            return self.matched_location.place_name
        return None
