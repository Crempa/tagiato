"""Reverse geocoding pomocí Nominatim API."""

import json
import time
from pathlib import Path
from typing import Optional

import requests

from tagiato.core.logger import log_call, log_result, log_info
from tagiato.models.location import GPSCoordinates


class Geocoder:
    """Reverse geocoding pomocí OpenStreetMap Nominatim API."""

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
    USER_AGENT = "Tagiato/0.1.0 (https://github.com/pavelmica/tagiato)"
    MIN_REQUEST_INTERVAL = 1.1  # Nominatim vyžaduje max 1 request/s

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Args:
            cache_file: Cesta k souboru pro cache výsledků
        """
        self.cache_file = cache_file
        self._cache: dict = {}
        self._last_request_time: float = 0
        self._load_cache()

    def _load_cache(self) -> None:
        """Načte cache ze souboru."""
        if self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save_cache(self) -> None:
        """Uloží cache do souboru."""
        if self.cache_file:
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
            except IOError:
                pass

    def _get_cache_key(self, coords: GPSCoordinates) -> str:
        """Vytvoří klíč pro cache (zaokrouhleno na 4 desetinná místa)."""
        # Zaokrouhlení na ~11m přesnost
        lat = round(coords.latitude, 4)
        lng = round(coords.longitude, 4)
        return f"{lat},{lng}"

    def geocode(self, coords: GPSCoordinates) -> Optional[str]:
        """Získá název místa pro dané souřadnice.

        Args:
            coords: GPS souřadnice

        Returns:
            Název místa nebo None
        """
        log_call("Geocoder", "geocode", lat=coords.latitude, lng=coords.longitude)

        # Zkusit cache
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
                    "zoom": 18,  # Vysoká přesnost
                    "addressdetails": 1,
                },
                headers={"User-Agent": self.USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            place_name = self._format_place_name(data)

            # Uložit do cache
            self._cache[cache_key] = place_name
            self._save_cache()

            log_result("Geocoder", "geocode", place_name)
            return place_name

        except requests.RequestException as e:
            log_info(f"request failed: {e}")
            # Při chybě vrátit None, ale neuložit do cache
            return None

    def _wait_for_rate_limit(self) -> None:
        """Počká na dodržení rate limitu."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _format_place_name(self, data: dict) -> Optional[str]:
        """Formátuje název místa z Nominatim odpovědi."""
        if not data:
            return None

        address = data.get("address", {})

        # Prioritní části adresy
        parts = []

        # Specifické místo (památka, budova, ...)
        for key in ["tourism", "historic", "building", "amenity"]:
            if key in address:
                parts.append(address[key])
                break

        # Ulice nebo čtvrť
        for key in ["road", "neighbourhood", "suburb"]:
            if key in address:
                parts.append(address[key])
                break

        # Město
        for key in ["city", "town", "village", "municipality"]:
            if key in address:
                parts.append(address[key])
                break

        if not parts:
            # Fallback na display_name
            display_name = data.get("display_name", "")
            if display_name:
                # Vzít první 2-3 části
                name_parts = display_name.split(", ")[:3]
                return ", ".join(name_parts)
            return None

        return ", ".join(parts)
