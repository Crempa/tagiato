"""Skenování JPEG souborů a čtení EXIF dat."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import piexif

from tagiato.models.photo import Photo
from tagiato.models.location import GPSCoordinates
from tagiato.services.exif_writer import read_location_name


class PhotoScanner:
    """Skenuje složku pro JPEG soubory a čte jejich EXIF data."""

    JPEG_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}

    def scan(self, directory: Path) -> List[Photo]:
        """Naskenuje složku a vrátí seznam fotek s EXIF daty.

        Args:
            directory: Cesta ke složce s fotkami

        Returns:
            Seznam Photo objektů seřazených podle času
        """
        photos = []

        for file_path in directory.iterdir():
            if file_path.suffix in self.JPEG_EXTENSIONS and file_path.is_file():
                photo = self._read_photo(file_path)
                photos.append(photo)

        # Seřadit podle času (fotky bez času na konec)
        photos.sort(key=lambda p: (p.timestamp is None, p.timestamp or datetime.min))
        return photos

    def _read_photo(self, path: Path) -> Photo:
        """Přečte EXIF data z fotky."""
        photo = Photo(path=path)

        try:
            exif_dict = piexif.load(str(path))

            # Přečíst timestamp
            photo.timestamp = self._extract_timestamp(exif_dict)

            # Přečíst GPS pokud existuje
            photo.original_gps = self._extract_gps(exif_dict)

            # Přečíst popisek pokud existuje
            photo.description = self._extract_description(exif_dict)

        except Exception:
            # Pokud EXIF nelze přečíst, pokračujeme bez něj
            pass

        # Přečíst location_name z IPTC (pomocí exiftool)
        photo.location_name = read_location_name(path)

        return photo

    def _extract_timestamp(self, exif_dict: dict) -> Optional[datetime]:
        """Extrahuje timestamp z EXIF dat."""
        # Zkusit DateTimeOriginal
        exif_data = exif_dict.get("Exif", {})
        datetime_original = exif_data.get(piexif.ExifIFD.DateTimeOriginal)

        if datetime_original:
            try:
                # Formát: "2017:04:05 14:32:00"
                dt_str = datetime_original.decode("utf-8") if isinstance(datetime_original, bytes) else datetime_original
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            except (ValueError, AttributeError):
                pass

        # Fallback na DateTime
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
        """Extrahuje GPS souřadnice z EXIF dat."""
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

            # Aplikovat směr
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
        """Převede stupně, minuty, vteřiny na desetinné stupně."""
        # dms je tuple of tuples: ((degrees, 1), (minutes, 1), (seconds, denom))
        degrees = dms[0][0] / dms[0][1]
        minutes = dms[1][0] / dms[1][1]
        seconds = dms[2][0] / dms[2][1]
        return degrees + minutes / 60 + seconds / 3600

    def _extract_description(self, exif_dict: dict) -> str:
        """Extrahuje popisek z EXIF dat."""
        # Zkusit ImageDescription v IFD0
        ifd0_data = exif_dict.get("0th", {})
        description = ifd0_data.get(piexif.ImageIFD.ImageDescription)

        if description:
            try:
                if isinstance(description, bytes):
                    return description.decode("utf-8")
                return str(description)
            except (ValueError, UnicodeDecodeError):
                pass

        return ""
