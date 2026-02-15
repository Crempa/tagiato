"""Services for Tagiato."""

from tagiato.services.photo_scanner import PhotoScanner
from tagiato.services.geocoder import Geocoder
from tagiato.services.thumbnail import ThumbnailGenerator
from tagiato.services.exif_writer import ExifWriter, is_exiftool_available, read_location_name
from tagiato.services.xmp_writer import XmpWriter

__all__ = [
    "PhotoScanner",
    "Geocoder",
    "ThumbnailGenerator",
    "ExifWriter",
    "is_exiftool_available",
    "read_location_name",
    "XmpWriter",
]
