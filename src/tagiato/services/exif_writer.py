"""Zápis GPS a popisků do EXIF metadat."""

from pathlib import Path
from typing import Optional

import piexif

from tagiato.core.exceptions import ExifError
from tagiato.core.logger import log_call, log_info
from tagiato.models.location import GPSCoordinates


class ExifWriter:
    """Zapisuje GPS souřadnice a popisky do EXIF metadat JPEG souborů."""

    def write(
        self,
        photo_path: Path,
        gps: Optional[GPSCoordinates] = None,
        description: Optional[str] = None,
        skip_existing_gps: bool = True,
    ) -> None:
        """Zapíše GPS a/nebo popisek do EXIF.

        Args:
            photo_path: Cesta k JPEG souboru
            gps: GPS souřadnice (volitelné)
            description: Popisek fotky (volitelné)
            skip_existing_gps: Přeskočit zápis GPS pokud už existuje

        Raises:
            ExifError: Pokud zápis selže
        """
        log_call(
            "ExifWriter",
            "write",
            file=photo_path.name,
            gps=str(gps) if gps else None,
            description=f"{len(description)} chars" if description else None,
            skip_existing_gps=skip_existing_gps,
        )

        if gps is None and description is None:
            log_info("nothing to write")
            return

        try:
            # Načíst existující EXIF
            try:
                exif_dict = piexif.load(str(photo_path))
            except Exception:
                # Pokud EXIF neexistuje, vytvořit prázdný
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

            # Zapsat GPS
            if gps is not None:
                has_existing_gps = self._has_gps(exif_dict)
                if not (skip_existing_gps and has_existing_gps):
                    self._write_gps(exif_dict, gps)

            # Zapsat popisek
            if description is not None:
                self._write_description(exif_dict, description)

            # Uložit změny
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(photo_path))

        except Exception as e:
            raise ExifError(f"Chyba při zápisu EXIF do {photo_path}: {e}")

    def _has_gps(self, exif_dict: dict) -> bool:
        """Zkontroluje, zda EXIF obsahuje GPS data."""
        gps_data = exif_dict.get("GPS", {})
        return bool(
            gps_data.get(piexif.GPSIFD.GPSLatitude)
            and gps_data.get(piexif.GPSIFD.GPSLongitude)
        )

    def _write_gps(self, exif_dict: dict, gps: GPSCoordinates) -> None:
        """Zapíše GPS souřadnice do EXIF dict."""
        lat_dms, lat_ref, lng_dms, lng_ref = gps.to_exif_format()

        exif_dict["GPS"] = {
            piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
            piexif.GPSIFD.GPSLatitude: lat_dms,
            piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode("utf-8"),
            piexif.GPSIFD.GPSLongitude: lng_dms,
            piexif.GPSIFD.GPSLongitudeRef: lng_ref.encode("utf-8"),
        }

    def _write_description(self, exif_dict: dict, description: str) -> None:
        """Zapíše popisek do EXIF dict."""
        # ImageDescription v IFD0
        if "0th" not in exif_dict:
            exif_dict["0th"] = {}

        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8")

        # Také zapsat do UserComment v Exif IFD pro lepší kompatibilitu
        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}

        # UserComment má speciální formát: 8 bajtů encoding + text
        # Použijeme Unicode (UTF-8)
        user_comment = b"UNICODE\x00" + description.encode("utf-16-be")
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
