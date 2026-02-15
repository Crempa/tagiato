"""Loading and parsing Google Timeline JSON."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from tagiato.core.exceptions import TimelineParseError
from tagiato.core.logger import log_call, log_result
from tagiato.models.location import GPSCoordinates
from tagiato.models.timeline import TimelinePoint


class TimelineLoader:
    """Loads and parses Google Timeline JSON (on-device export format)."""

    def load(self, path: Path) -> List[TimelinePoint]:
        """Loads timeline JSON and returns a list of points sorted by time.

        Args:
            path: Path to the JSON file

        Returns:
            List of TimelinePoint sorted by time

        Raises:
            TimelineParseError: If the file cannot be loaded or parsed
        """
        log_call("TimelineLoader", "load", path=str(path))

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise TimelineParseError(f"Invalid JSON format: {e}")
        except FileNotFoundError:
            raise TimelineParseError(f"File not found: {path}")
        except Exception as e:
            raise TimelineParseError(f"Error reading file: {e}")

        points = []

        # On-device export is an array of records
        if not isinstance(data, list):
            raise TimelineParseError("Expected a list of records in timeline JSON")

        for record in data:
            extracted = self._extract_points_from_record(record)
            points.extend(extracted)

        # Sort by time
        points.sort()

        log_result("TimelineLoader", "load", f"{len(points)} points")
        return points

    def _extract_points_from_record(self, record: dict) -> List[TimelinePoint]:
        """Extracts points from a single record (visit or activity)."""
        points = []

        # Process "visit" records
        if "visit" in record:
            visit = record["visit"]
            point = self._extract_visit_point(visit)
            if point:
                points.append(point)

        # Process "activity" records
        if "activity" in record:
            activity = record["activity"]
            start_point, end_point = self._extract_activity_points(activity)
            if start_point:
                points.append(start_point)
            if end_point:
                points.append(end_point)

        return points

    def _extract_visit_point(self, visit: dict) -> Optional[TimelinePoint]:
        """Extracts a point from a visit record."""
        top_candidate = visit.get("topCandidate", {})
        place_location = top_candidate.get("placeLocation")

        if not place_location:
            return None

        coords = GPSCoordinates.from_geo_string(place_location)
        if not coords:
            return None

        # Get timestamp - use startTime
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
        """Extracts start and end points from an activity record."""
        start_point = None
        end_point = None

        # Start position
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

        # End position
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
        """Parses an ISO 8601 timestamp with timezone."""
        if not timestamp_str:
            return None

        try:
            # Python 3.11+ supports fromisoformat with timezone
            # For older versions we need to adjust the format
            # Format: "2017-04-05T16:44:08.421+02:00"

            # Try to parse directly
            try:
                return datetime.fromisoformat(timestamp_str)
            except ValueError:
                pass

            # Fallback - remove milliseconds and timezone offset for older Python
            # This is not ideal, but works for basic usage
            if "." in timestamp_str:
                # Remove milliseconds
                base, rest = timestamp_str.split(".")
                # Find timezone offset
                if "+" in rest:
                    tz_part = rest.split("+")[1]
                    timestamp_str = base + "+" + tz_part
                elif "-" in rest[1:]:  # Skip the first character (could be a digit)
                    idx = rest.rfind("-")
                    tz_part = rest[idx + 1 :]
                    timestamp_str = base + "-" + tz_part

            return datetime.fromisoformat(timestamp_str)

        except (ValueError, AttributeError):
            return None
