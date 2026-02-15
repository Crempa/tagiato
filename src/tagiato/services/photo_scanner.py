"""Scanning JPEG files and reading EXIF data."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import piexif

from tagiato.models.photo import Photo
from tagiato.models.location import GPSCoordinates
from tagiato.services.exif_writer import read_location_name


class PhotoScanner:
    """Scans a directory for JPEG files and reads their EXIF data."""

    JPEG_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}

    def scan(self, directory: Path) -> List[Photo]:
        """Scan a directory and return a list of photos with EXIF data.

        Args:
            directory: Path to the directory with photos

        Returns:
            List of Photo objects sorted by timestamp
        """
        photos = []

        for file_path in directory.iterdir():
            if file_path.suffix in self.JPEG_EXTENSIONS and file_path.is_file():
                photo = self._read_photo(file_path)
                photos.append(photo)

        # Sort by timestamp (photos without timestamp go to the end)
        photos.sort(key=lambda p: (p.timestamp is None, p.timestamp or datetime.min))
        return photos

    def _read_photo(self, path: Path) -> Photo:
        """Read EXIF data from a photo."""
        photo = Photo(path=path)

        try:
            exif_dict = piexif.load(str(path))

            # Read timestamp
            photo.timestamp = self._extract_timestamp(exif_dict)

            # Read GPS if available
            photo.original_gps = self._extract_gps(exif_dict)

            # Read description if available
            photo.description = self._extract_description(exif_dict)

        except Exception:
            # If EXIF cannot be read, continue without it
            pass

        # Read location_name from IPTC (using exiftool)
        photo.location_name = read_location_name(path)

        return photo

    def _extract_timestamp(self, exif_dict: dict) -> Optional[datetime]:
        """Extract timestamp from EXIF data."""
        # Try DateTimeOriginal
        exif_data = exif_dict.get("Exif", {})
        datetime_original = exif_data.get(piexif.ExifIFD.DateTimeOriginal)

        if datetime_original:
            try:
                # Format: "2017:04:05 14:32:00"
                dt_str = datetime_original.decode("utf-8") if isinstance(datetime_original, bytes) else datetime_original
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            except (ValueError, AttributeError):
                pass

        # Fallback to DateTime
        ifd0_data = exif_dict.get("0th", {})
        date_time = ifd0_data.get(piexif.ImageIFD.DateTime)

        if date_time:
            try:
                dt_str = date_time.decode("utf-8") if isinstance(date_time, bytes) else date_time
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            except (ValueError, AttributeError):
                pass

        return None

    def _extract_gps(self, exif_dict: dict) -> Optional[GPSCoordinates]:
        """Extract GPS coordinates from EXIF data."""
        gps_data = exif_dict.get("GPS", {})

        if not gps_data:
            return None

        lat = gps_data.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps_data.get(piexif.GPSIFD.GPSLatitudeRef)
        lng = gps_data.get(piexif.GPSIFD.GPSLongitude)
        lng_ref = gps_data.get(piexif.GPSIFD.GPSLongitudeRef)

        if not all([lat, lat_ref, lng, lng_ref]):
            return None

        try:
            latitude = self._dms_to_decimal(lat)
            longitude = self._dms_to_decimal(lng)

            # Apply direction
            if isinstance(lat_ref, bytes):
                lat_ref = lat_ref.decode("utf-8")
            if isinstance(lng_ref, bytes):
                lng_ref = lng_ref.decode("utf-8")

            if lat_ref == "S":
                latitude = -latitude
            if lng_ref == "W":
                longitude = -longitude

            return GPSCoordinates(latitude=latitude, longitude=longitude)
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def _dms_to_decimal(dms: tuple) -> float:
        """Convert degrees, minutes, seconds to decimal degrees."""
        # dms is a tuple of tuples: ((degrees, 1), (minutes, 1), (seconds, denom))
        degrees = dms[0][0] / dms[0][1]
        minutes = dms[1][0] / dms[1][1]
        seconds = dms[2][0] / dms[2][1]
        return degrees + minutes / 60 + seconds / 3600

    def _extract_description(self, exif_dict: dict) -> str:
        """Extract description from EXIF data."""
        # Try ImageDescription in IFD0
        ifd0_data = exif_dict.get("0th", {})
        description = ifd0_data.get(piexif.ImageIFD.ImageDescription)

        if description:
            try:
                if isinstance(description, bytes):
                    return description.decode("utf-8")
                return str(description)
            except (ValueError, UnicodeDecodeError):
                pass

        # Fallback: try UserComment in Exif IFD
        exif_data = exif_dict.get("Exif", {})
        user_comment = exif_data.get(piexif.ExifIFD.UserComment)

        if user_comment and isinstance(user_comment, bytes):
            try:
                # UserComment has a special format: 8 bytes encoding + text
                # Supported prefixes: "ASCII\x00\x00\x00", "UNICODE\x00", "JIS\x00\x00\x00\x00\x00"
                if len(user_comment) > 8:
                    encoding_prefix = user_comment[:8]
                    content = user_comment[8:]

                    if encoding_prefix.startswith(b"UNICODE"):
                        # UTF-16 BE encoding
                        return content.decode("utf-16-be").strip("\x00")
                    elif encoding_prefix.startswith(b"ASCII"):
                        return content.decode("ascii", errors="ignore").strip("\x00")
                    else:
                        # Try UTF-8 as fallback
                        return content.decode("utf-8", errors="ignore").strip("\x00")
            except (ValueError, UnicodeDecodeError):
                pass

        return ""
