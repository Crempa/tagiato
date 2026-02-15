"""Model for a photograph."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from tagiato.models.location import Location, GPSCoordinates


@dataclass
class Photo:
    """Representation of a photograph with metadata."""

    path: Path
    timestamp: Optional[datetime] = None
    original_gps: Optional[GPSCoordinates] = None  # GPS from EXIF (if exists)
    matched_location: Optional[Location] = None  # Location from timeline
    refined_gps: Optional[GPSCoordinates] = None  # Refined GPS from AI
    description: str = ""
    location_name: Optional[str] = None  # Location name from IPTC:Sub-location
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
        """Return the best available GPS coordinates.

        Priority: refined_gps > matched_location > original_gps
        """
        if self.refined_gps:
            return self.refined_gps
        if self.matched_location:
            return self.matched_location.coordinates
        return self.original_gps

    @property
    def place_name(self) -> Optional[str]:
        """Return place name if available."""
        if self.matched_location:
            return self.matched_location.place_name
        return None
