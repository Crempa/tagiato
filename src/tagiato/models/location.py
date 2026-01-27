"""Modely pro lokaci a GPS souřadnice."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class GPSCoordinates:
    """GPS souřadnice s metodami pro konverzi do EXIF formátu."""

    latitude: float
    longitude: float

    def to_exif_format(self) -> Tuple[Tuple[Tuple[int, int], ...], str, Tuple[Tuple[int, int], ...], str]:
        """Převede souřadnice do EXIF formátu (degrees, minutes, seconds jako rational).

        Returns:
            Tuple obsahující (lat_dms, lat_ref, lng_dms, lng_ref)
        """
        lat_ref = "N" if self.latitude >= 0 else "S"
        lng_ref = "E" if self.longitude >= 0 else "W"

        lat_dms = self._decimal_to_dms(abs(self.latitude))
        lng_dms = self._decimal_to_dms(abs(self.longitude))

        return lat_dms, lat_ref, lng_dms, lng_ref

    @staticmethod
    def _decimal_to_dms(decimal: float) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """Převede desetinné stupně na stupně, minuty, vteřiny jako rational tuple."""
        degrees = int(decimal)
        minutes_decimal = (decimal - degrees) * 60
        minutes = int(minutes_decimal)
        seconds = (minutes_decimal - minutes) * 60
        # Reprezentujeme jako rational čísla (čitatel, jmenovatel)
        # Vteřiny s přesností na 4 desetinná místa
        seconds_rational = (int(seconds * 10000), 10000)
        return ((degrees, 1), (minutes, 1), seconds_rational)

    @classmethod
    def from_geo_string(cls, geo_string: str) -> Optional["GPSCoordinates"]:
        """Parsuje 'geo:lat,lng' string z Google Timeline.

        Args:
            geo_string: String ve formátu "geo:50.042305,15.760400"

        Returns:
            GPSCoordinates nebo None pokud parsing selže
        """
        if not geo_string or not geo_string.startswith("geo:"):
            return None
        try:
            coords = geo_string[4:]  # odstranit "geo:"
            lat_str, lng_str = coords.split(",")
            return cls(latitude=float(lat_str), longitude=float(lng_str))
        except (ValueError, IndexError):
            return None

    def __str__(self) -> str:
        return f"{self.latitude:.6f}, {self.longitude:.6f}"


@dataclass
class Location:
    """Lokace s GPS souřadnicemi a názvem místa."""

    coordinates: GPSCoordinates
    place_name: Optional[str] = None
    confidence: float = 1.0  # 0.0-1.0, jak moc jsme si jisti

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
