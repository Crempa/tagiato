"""Models for location and GPS coordinates."""

import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class GPSCoordinates:
    """GPS coordinates with methods for conversion to EXIF format."""

    latitude: float
    longitude: float

    def to_exif_format(self) -> Tuple[Tuple[Tuple[int, int], ...], str, Tuple[Tuple[int, int], ...], str]:
        """Convert coordinates to EXIF format (degrees, minutes, seconds as rational).

        Returns:
            Tuple containing (lat_dms, lat_ref, lng_dms, lng_ref)
        """
        lat_ref = "N" if self.latitude >= 0 else "S"
        lng_ref = "E" if self.longitude >= 0 else "W"

        lat_dms = self._decimal_to_dms(abs(self.latitude))
        lng_dms = self._decimal_to_dms(abs(self.longitude))

        return lat_dms, lat_ref, lng_dms, lng_ref

    @staticmethod
    def _decimal_to_dms(decimal: float) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """Convert decimal degrees to degrees, minutes, seconds as rational tuple."""
        degrees = int(decimal)
        minutes_decimal = (decimal - degrees) * 60
        minutes = int(minutes_decimal)
        seconds = (minutes_decimal - minutes) * 60
        # Represent as rational numbers (numerator, denominator)
        # Seconds with precision of 4 decimal places
        seconds_rational = (int(seconds * 10000), 10000)
        return ((degrees, 1), (minutes, 1), seconds_rational)

    @classmethod
    def from_geo_string(cls, geo_string: str) -> Optional["GPSCoordinates"]:
        """Parse 'geo:lat,lng' string from Google Timeline.

        Args:
            geo_string: String in format "geo:50.042305,15.760400"

        Returns:
            GPSCoordinates or None if parsing fails
        """
        if not geo_string or not geo_string.startswith("geo:"):
            return None
        try:
            coords = geo_string[4:]  # remove "geo:"
            lat_str, lng_str = coords.split(",")
            return cls(latitude=float(lat_str), longitude=float(lng_str))
        except (ValueError, IndexError):
            return None

    def __str__(self) -> str:
        return f"{self.latitude:.6f}, {self.longitude:.6f}"

    def distance_to(self, other: "GPSCoordinates") -> float:
        """Calculate distance to other coordinates in km (haversine formula).

        Args:
            other: Target GPS coordinates

        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in km

        lat1 = math.radians(self.latitude)
        lat2 = math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlng = math.radians(other.longitude - self.longitude)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


@dataclass
class Location:
    """Location with GPS coordinates and place name."""

    coordinates: GPSCoordinates
    place_name: Optional[str] = None
    confidence: float = 1.0  # 0.0-1.0, how confident we are

    @property
    def latitude(self) -> float:
        return self.coordinates.latitude

    @property
    def longitude(self) -> float:
        return self.coordinates.longitude

    def __str__(self) -> str:
        if self.place_name:
            return f"{self.place_name} ({self.coordinates})"
        return str(self.coordinates)
