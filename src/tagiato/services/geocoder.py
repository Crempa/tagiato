"""Reverse geocoding using the Nominatim API."""

import json
import time
from pathlib import Path
from typing import Optional

import requests

from tagiato.core.logger import log_call, log_result, log_info
from tagiato.models.location import GPSCoordinates


class Geocoder:
    """Reverse geocoding using the OpenStreetMap Nominatim API."""

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
    USER_AGENT = "Tagiato/0.1.0 (https://github.com/pavelmica/tagiato)"
    MIN_REQUEST_INTERVAL = 1.1  # Nominatim requires max 1 request/s

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Args:
            cache_file: Path to the file for caching results
        """
        self.cache_file = cache_file
        self._cache: dict = {}
        self._last_request_time: float = 0
        self._load_cache()

    def _load_cache(self) -> None:
        """Loads cache from file."""
        if self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save_cache(self) -> None:
        """Saves cache to file."""
        if self.cache_file:
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
            except IOError:
                pass

    def _get_cache_key(self, coords: GPSCoordinates) -> str:
        """Creates a cache key (rounded to 4 decimal places)."""
        # Rounding to ~11m precision
        lat = round(coords.latitude, 4)
        lng = round(coords.longitude, 4)
        return f"{lat},{lng}"

    def geocode(self, coords: GPSCoordinates) -> Optional[str]:
        """Gets the place name for the given coordinates.

        Args:
            coords: GPS coordinates

        Returns:
            Place name or None
        """
        log_call("Geocoder", "geocode", lat=coords.latitude, lng=coords.longitude)

        # Try cache
        cache_key = self._get_cache_key(coords)
        if cache_key in self._cache:
            result = self._cache[cache_key]
            log_info(f"cache hit: {result}")
            return result

        # Rate limiting
        self._wait_for_rate_limit()

        try:
            response = requests.get(
                self.NOMINATIM_URL,
                params={
                    "lat": coords.latitude,
                    "lon": coords.longitude,
                    "format": "json",
                    "zoom": 18,  # High precision
                    "addressdetails": 1,
                },
                headers={"User-Agent": self.USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            place_name = self._format_place_name(data)

            # Save to cache
            self._cache[cache_key] = place_name
            self._save_cache()

            log_result("Geocoder", "geocode", place_name)
            return place_name

        except requests.RequestException as e:
            log_info(f"request failed: {e}")
            # On error return None, but don't save to cache
            return None

    def _wait_for_rate_limit(self) -> None:
        """Waits to comply with the rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _format_place_name(self, data: dict) -> Optional[str]:
        """Formats a place name from a Nominatim response."""
        if not data:
            return None

        address = data.get("address", {})

        # Priority address parts
        parts = []

        # Specific place (landmark, building, ...)
        for key in ["tourism", "historic", "building", "amenity"]:
            if key in address:
                parts.append(address[key])
                break

        # Street or neighbourhood
        for key in ["road", "neighbourhood", "suburb"]:
            if key in address:
                parts.append(address[key])
                break

        # City
        for key in ["city", "town", "village", "municipality"]:
            if key in address:
                parts.append(address[key])
                break

        if not parts:
            # Fallback to display_name
            display_name = data.get("display_name", "")
            if display_name:
                # Take the first 2-3 parts
                name_parts = display_name.split(", ")[:3]
                return ", ".join(name_parts)
            return None

        return ", ".join(parts)
