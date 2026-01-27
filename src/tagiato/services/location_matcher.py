"""Párování času fotky na GPS z timeline."""

import bisect
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from tagiato.models.location import Location, GPSCoordinates
from tagiato.models.timeline import TimelinePoint


class LocationMatcher:
    """Páruje čas fotky na nejbližší GPS body z timeline s interpolací."""

    def __init__(self, timeline_points: List[TimelinePoint], max_gap_minutes: int = 30):
        """
        Args:
            timeline_points: Seznam bodů z timeline (musí být seřazený podle času)
            max_gap_minutes: Maximální časový rozdíl v minutách
        """
        self.points = timeline_points
        self.max_gap = timedelta(minutes=max_gap_minutes)
        # Pro binary search potřebujeme seznam timestampů
        self._timestamps = [p.timestamp for p in timeline_points]

    def match(self, photo_time: datetime) -> Optional[Location]:
        """Najde a interpoluje GPS pro daný čas.

        Args:
            photo_time: Čas pořízení fotky

        Returns:
            Location s GPS a confidence, nebo None pokud není v toleranci
        """
        if not self.points:
            return None

        # Binary search pro nalezení nejbližších bodů
        idx = bisect.bisect_left(self._timestamps, photo_time)

        # Získat okolní body
        before, after = self._get_surrounding_points(idx, photo_time)

        if before is None and after is None:
            return None

        # Pokud máme jen jeden bod
        if before is None:
            return self._create_location_from_single(after, photo_time)
        if after is None:
            return self._create_location_from_single(before, photo_time)

        # Interpolovat mezi dvěma body
        return self._interpolate(before, after, photo_time)

    def _get_surrounding_points(
        self, idx: int, photo_time: datetime
    ) -> Tuple[Optional[TimelinePoint], Optional[TimelinePoint]]:
        """Získá body před a po daném čase v rámci tolerance."""
        before = None
        after = None

        # Bod před
        if idx > 0:
            candidate = self.points[idx - 1]
            if abs(candidate.timestamp - photo_time) <= self.max_gap:
                before = candidate

        # Bod po (nebo přesná shoda)
        if idx < len(self.points):
            candidate = self.points[idx]
            if abs(candidate.timestamp - photo_time) <= self.max_gap:
                after = candidate

        return before, after

    def _create_location_from_single(
        self, point: TimelinePoint, photo_time: datetime
    ) -> Optional[Location]:
        """Vytvoří lokaci z jednoho bodu s odpovídající confidence."""
        time_diff = abs(point.timestamp - photo_time)

        if time_diff > self.max_gap:
            return None

        # Confidence klesá s časovou vzdáleností
        # 1.0 při přesné shodě, 0.3 na hranici tolerance
        confidence = 1.0 - (time_diff / self.max_gap) * 0.7

        return Location(
            coordinates=point.coordinates,
            place_name=point.place_name,
            confidence=confidence,
        )

    def _interpolate(
        self, before: TimelinePoint, after: TimelinePoint, photo_time: datetime
    ) -> Location:
        """Interpoluje pozici mezi dvěma body."""
        # Časové vzdálenosti
        time_to_before = (photo_time - before.timestamp).total_seconds()
        time_to_after = (after.timestamp - photo_time).total_seconds()
        total_time = time_to_before + time_to_after

        if total_time == 0:
            # Přesná shoda s jedním bodem
            return Location(
                coordinates=before.coordinates,
                place_name=before.place_name,
                confidence=1.0,
            )

        # Váha pro interpolaci (0 = before, 1 = after)
        weight = time_to_before / total_time

        # Interpolované souřadnice
        lat = before.latitude + (after.latitude - before.latitude) * weight
        lng = before.longitude + (after.longitude - before.longitude) * weight

        # Confidence - vyšší pokud jsou body blízko sebe
        # Průměrná vzdálenost od obou bodů
        avg_distance = total_time / 2
        max_gap_seconds = self.max_gap.total_seconds()
        confidence = 1.0 - (avg_distance / max_gap_seconds) * 0.7

        # Použít place_name z bližšího bodu
        place_name = before.place_name if weight < 0.5 else after.place_name

        return Location(
            coordinates=GPSCoordinates(latitude=lat, longitude=lng),
            place_name=place_name,
            confidence=max(0.3, min(1.0, confidence)),
        )

    def get_timezone_hint(self, photo_time: datetime) -> Optional[str]:
        """Pokusí se odhadnout timezone z nejbližšího timeline bodu.

        Returns:
            Timezone string (např. "+02:00") nebo None
        """
        if not self.points:
            return None

        # Najít nejbližší bod
        idx = bisect.bisect_left(self._timestamps, photo_time)

        closest = None
        if idx > 0:
            closest = self.points[idx - 1]
        if idx < len(self.points):
            if closest is None or abs(self.points[idx].timestamp - photo_time) < abs(
                closest.timestamp - photo_time
            ):
                closest = self.points[idx]

        if closest and closest.timestamp.tzinfo:
            offset = closest.timestamp.utcoffset()
            if offset:
                total_seconds = int(offset.total_seconds())
                hours = total_seconds // 3600
                minutes = abs(total_seconds % 3600) // 60
                sign = "+" if total_seconds >= 0 else "-"
                return f"{sign}{abs(hours):02d}:{minutes:02d}"

        return None
