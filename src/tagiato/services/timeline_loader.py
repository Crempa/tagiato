"""Načítání a parsování Google Timeline JSON."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from tagiato.core.exceptions import TimelineParseError
from tagiato.models.location import GPSCoordinates
from tagiato.models.timeline import TimelinePoint


class TimelineLoader:
    """Načítá a parsuje Google Timeline JSON (on-device export formát)."""

    def load(self, path: Path) -> List[TimelinePoint]:
        """Načte timeline JSON a vrátí seznam bodů seřazených podle času.

        Args:
            path: Cesta k JSON souboru

        Returns:
            Seznam TimelinePoint seřazených podle času

        Raises:
            TimelineParseError: Pokud nelze načíst nebo parsovat soubor
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise TimelineParseError(f"Neplatný JSON formát: {e}")
        except FileNotFoundError:
            raise TimelineParseError(f"Soubor nenalezen: {path}")
        except Exception as e:
            raise TimelineParseError(f"Chyba při čtení souboru: {e}")

        points = []

        # On-device export je pole záznamů
        if not isinstance(data, list):
            raise TimelineParseError("Očekáván seznam záznamů v timeline JSON")

        for record in data:
            extracted = self._extract_points_from_record(record)
            points.extend(extracted)

        # Seřadit podle času
        points.sort()

        return points

    def _extract_points_from_record(self, record: dict) -> List[TimelinePoint]:
        """Extrahuje body z jednoho záznamu (visit nebo activity)."""
        points = []

        # Zpracovat "visit" záznamy
        if "visit" in record:
            visit = record["visit"]
            point = self._extract_visit_point(visit)
            if point:
                points.append(point)

        # Zpracovat "activity" záznamy
        if "activity" in record:
            activity = record["activity"]
            start_point, end_point = self._extract_activity_points(activity)
            if start_point:
                points.append(start_point)
            if end_point:
                points.append(end_point)

        return points

    def _extract_visit_point(self, visit: dict) -> Optional[TimelinePoint]:
        """Extrahuje bod z visit záznamu."""
        top_candidate = visit.get("topCandidate", {})
        place_location = top_candidate.get("placeLocation")

        if not place_location:
            return None

        coords = GPSCoordinates.from_geo_string(place_location)
        if not coords:
            return None

        # Získat timestamp - použít startTime
        timestamp = self._parse_timestamp(visit.get("startTime"))
        if not timestamp:
            return None

        place_name = top_candidate.get("semanticType") or top_candidate.get("placeId")

        return TimelinePoint(
            timestamp=timestamp,
            coordinates=coords,
            place_name=place_name,
            activity_type="visit",
        )

    def _extract_activity_points(self, activity: dict) -> tuple:
        """Extrahuje start a end body z activity záznamu."""
        start_point = None
        end_point = None

        # Start pozice
        start_location = activity.get("start")
        if start_location:
            coords = GPSCoordinates.from_geo_string(start_location)
            timestamp = self._parse_timestamp(activity.get("startTime"))
            if coords and timestamp:
                start_point = TimelinePoint(
                    timestamp=timestamp,
                    coordinates=coords,
                    activity_type="activity",
                )

        # End pozice
        end_location = activity.get("end")
        if end_location:
            coords = GPSCoordinates.from_geo_string(end_location)
            timestamp = self._parse_timestamp(activity.get("endTime"))
            if coords and timestamp:
                end_point = TimelinePoint(
                    timestamp=timestamp,
                    coordinates=coords,
                    activity_type="activity",
                )

        return start_point, end_point

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parsuje ISO 8601 timestamp s timezone."""
        if not timestamp_str:
            return None

        try:
            # Python 3.11+ podporuje fromisoformat s timezone
            # Pro starší verze musíme upravit formát
            # Formát: "2017-04-05T16:44:08.421+02:00"

            # Pokusit se přímo parsovat
            try:
                return datetime.fromisoformat(timestamp_str)
            except ValueError:
                pass

            # Fallback - odstranit milisekundy a timezone offset pro starší Python
            # Toto není ideální, ale funguje pro základní použití
            if "." in timestamp_str:
                # Odstranit milisekundy
                base, rest = timestamp_str.split(".")
                # Najít timezone offset
                if "+" in rest:
                    tz_part = rest.split("+")[1]
                    timestamp_str = base + "+" + tz_part
                elif "-" in rest[1:]:  # Přeskočit první znak (může být číslo)
                    idx = rest.rfind("-")
                    tz_part = rest[idx + 1 :]
                    timestamp_str = base + "-" + tz_part

            return datetime.fromisoformat(timestamp_str)

        except (ValueError, AttributeError):
            return None
