"""Tests for models."""

import pytest
from tagiato.models.location import GPSCoordinates, Location


class TestGPSCoordinates:
    """Tests for GPSCoordinates."""

    def test_from_geo_string_valid(self):
        """Test parsing a valid geo string."""
        coords = GPSCoordinates.from_geo_string("geo:50.042305,15.760400")
        assert coords is not None
        assert coords.latitude == pytest.approx(50.042305)
        assert coords.longitude == pytest.approx(15.760400)

    def test_from_geo_string_invalid(self):
        """Test parsing an invalid geo string."""
        assert GPSCoordinates.from_geo_string("invalid") is None
        assert GPSCoordinates.from_geo_string("") is None
        assert GPSCoordinates.from_geo_string(None) is None

    def test_to_exif_format(self):
        """Test conversion to EXIF format."""
        coords = GPSCoordinates(latitude=50.042305, longitude=15.760400)
        lat_dms, lat_ref, lng_dms, lng_ref = coords.to_exif_format()

        assert lat_ref == "N"
        assert lng_ref == "E"
        assert lat_dms[0] == (50, 1)  # degrees
        assert lng_dms[0] == (15, 1)  # degrees

    def test_to_exif_format_negative(self):
        """Test conversion of negative coordinates."""
        coords = GPSCoordinates(latitude=-33.8688, longitude=-151.2093)
        lat_dms, lat_ref, lng_dms, lng_ref = coords.to_exif_format()

        assert lat_ref == "S"
        assert lng_ref == "W"

    def test_str(self):
        """Test string representation."""
        coords = GPSCoordinates(latitude=50.042305, longitude=15.760400)
        assert str(coords) == "50.042305, 15.760400"

    def test_distance_to_same_point(self):
        """Test distance to the same point."""
        coords = GPSCoordinates(latitude=50.0, longitude=15.0)
        assert coords.distance_to(coords) == pytest.approx(0.0)

    def test_distance_to_known_distance(self):
        """Test distance between Prague and Brno (~185 km)."""
        prague = GPSCoordinates(latitude=50.0755, longitude=14.4378)
        brno = GPSCoordinates(latitude=49.1951, longitude=16.6068)
        distance = prague.distance_to(brno)
        # Prague-Brno is approximately 185 km as the crow flies
        assert 180 < distance < 190

    def test_distance_to_short_distance(self):
        """Test distance within a city (~5 km)."""
        point1 = GPSCoordinates(latitude=50.0755, longitude=14.4378)  # Prague center
        point2 = GPSCoordinates(latitude=50.1000, longitude=14.4500)  # ~3 km north
        distance = point1.distance_to(point2)
        assert 2 < distance < 5


class TestLocation:
    """Tests for Location."""

    def test_location_with_place_name(self):
        """Test location with place name."""
        coords = GPSCoordinates(latitude=50.0, longitude=15.0)
        location = Location(coordinates=coords, place_name="Praha")

        assert location.latitude == 50.0
        assert location.longitude == 15.0
        assert location.place_name == "Praha"
        assert "Praha" in str(location)

    def test_location_confidence(self):
        """Test confidence score."""
        coords = GPSCoordinates(latitude=50.0, longitude=15.0)
        location = Location(coordinates=coords, confidence=0.8)

        assert location.confidence == 0.8
