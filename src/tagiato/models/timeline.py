"""Model for points from Google Timeline."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from tagiato.models.location import GPSCoordinates


@dataclass
class TimelinePoint:
    """Point from Google Timeline with time and GPS."""

    timestamp: datetime
    coordinates: GPSCoordinates
    place_name: Optional[str] = None
    activity_type: Optional[str] = None  # "visit" or "activity"

    @property
    def latitude(self) -> float:
        return self.coordinates.latitude

    @property
    def longitude(self) -> float:
        return self.coordinates.longitude

    def __lt__(self, other: "TimelinePoint") -> bool:
        """For sorting by time."""
        return self.timestamp < other.timestamp
