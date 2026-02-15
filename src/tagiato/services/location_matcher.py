"""Matching photo time to GPS from timeline."""

import bisect
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from tagiato.core.logger import log_call, log_result, log_info
from tagiato.models.location import Location, GPSCoordinates
from tagiato.models.timeline import TimelinePoint


class LocationMatcher:
    """Matches photo time to the nearest GPS points from timeline with interpolation."""

    def __init__(self, timeline_points: List[TimelinePoint], max_gap_minutes: int = 30):
        """
        Args:
            timeline_points: List of timeline points (must be sorted by time)
            max_gap_minutes: Maximum time difference in minutes
        """
        self.points = timeline_points
        self.max_gap = timedelta(minutes=max_gap_minutes)
        # For binary search we need a list of timestamps
        self._timestamps = [p.timestamp for p in timeline_points]

    def match(self, photo_time: datetime) -> Optional[Location]:
        """Finds and interpolates GPS for the given time.

        Args:
            photo_time: Time the photo was taken

        Returns:
            Location with GPS and confidence, or None if not within tolerance
        """
        log_call("LocationMatcher", "match", photo_time=photo_time.isoformat())

        if not self.points:
            log_info("no timeline points")
            return None

        # Binary search to find the nearest points
        idx = bisect.bisect_left(self._timestamps, photo_time)

        # Get surrounding points
        before, after = self._get_surrounding_points(idx, photo_time)

        if before is None and after is None:
            log_info("no points within tolerance")
            return None

        # If we only have one point
        if before is None:
            result = self._create_location_from_single(after, photo_time)
            log_result("LocationMatcher", "match", f"single point, confidence={result.confidence:.2f}" if result else None)
            return result
        if after is None:
            result = self._create_location_from_single(before, photo_time)
            log_result("LocationMatcher", "match", f"single point, confidence={result.confidence:.2f}" if result else None)
            return result

        # Interpolate between two points
        result = self._interpolate(before, after, photo_time)
        log_result("LocationMatcher", "match", f"interpolated, confidence={result.confidence:.2f}")
        return result

    def _get_surrounding_points(
        self, idx: int, photo_time: datetime
    ) -> Tuple[Optional[TimelinePoint], Optional[TimelinePoint]]:
        """Gets points before and after the given time within tolerance."""
        before = None
        after = None

        # Point before
        if idx > 0:
            candidate = self.points[idx - 1]
            if abs(candidate.timestamp - photo_time) <= self.max_gap:
                before = candidate

        # Point after (or exact match)
        if idx < len(self.points):
            candidate = self.points[idx]
            if abs(candidate.timestamp - photo_time) <= self.max_gap:
                after = candidate

        return before, after

    def _create_location_from_single(
        self, point: TimelinePoint, photo_time: datetime
    ) -> Optional[Location]:
        """Creates a location from a single point with corresponding confidence."""
        time_diff = abs(point.timestamp - photo_time)

        if time_diff > self.max_gap:
            return None

        # Confidence decreases with time distance
        # 1.0 at exact match, 0.3 at tolerance boundary
        confidence = 1.0 - (time_diff / self.max_gap) * 0.7

        return Location(
            coordinates=point.coordinates,
            place_name=point.place_name,
            confidence=confidence,
        )

    def _interpolate(
        self, before: TimelinePoint, after: TimelinePoint, photo_time: datetime
    ) -> Location:
        """Interpolates position between two points."""
        # Time distances
        time_to_before = (photo_time - before.timestamp).total_seconds()
        time_to_after = (after.timestamp - photo_time).total_seconds()
        total_time = time_to_before + time_to_after

        if total_time == 0:
            # Exact match with one point
            return Location(
                coordinates=before.coordinates,
                place_name=before.place_name,
                confidence=1.0,
            )

        # Weight for interpolation (0 = before, 1 = after)
        weight = time_to_before / total_time

        # Interpolated coordinates
        lat = before.latitude + (after.latitude - before.latitude) * weight
        lng = before.longitude + (after.longitude - before.longitude) * weight

        # Confidence - higher if points are close to each other
        # Average distance from both points
        avg_distance = total_time / 2
        max_gap_seconds = self.max_gap.total_seconds()
        confidence = 1.0 - (avg_distance / max_gap_seconds) * 0.7

        # Use place_name from the closer point
        place_name = before.place_name if weight < 0.5 else after.place_name

        return Location(
            coordinates=GPSCoordinates(latitude=lat, longitude=lng),
            place_name=place_name,
            confidence=max(0.3, min(1.0, confidence)),
        )

    def get_timezone_hint(self, photo_time: datetime) -> Optional[str]:
        """Attempts to estimate timezone from the nearest timeline point.

        Returns:
            Timezone string (e.g. "+02:00") or None
        """
        if not self.points:
            return None

        # Find the nearest point
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
