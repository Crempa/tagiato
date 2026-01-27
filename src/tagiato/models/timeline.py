"""Model pro body z Google Timeline."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from tagiato.models.location import GPSCoordinates


@dataclass
class TimelinePoint:
    """Bod z Google Timeline s časem a GPS."""

    timestamp: datetime
    coordinates: GPSCoordinates
    place_name: Optional[str] = None
    activity_type: Optional[str] = None  # "visit" nebo "activity"

    @property
    def latitude(self) -> float:
        return self.coordinates.latitude

    @property
    def longitude(self) -> float:
        return self.coordinates.longitude

    def __lt__(self, other: "TimelinePoint") -> bool:
        """Pro řazení podle času."""
        return self.timestamp < other.timestamp
