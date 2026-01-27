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

    def clear(
        self,
        photo_path: Path,
        clear_gps: bool = True,
        clear_description: bool = True,
    ) -> bool:
        """Smaže GPS a/nebo popisek z EXIF.

        Args:
            photo_path: Cesta k JPEG souboru
            clear_gps: Smazat GPS data
            clear_description: Smazat popisek

        Returns:
            True pokud bylo něco smazáno

        Raises:
            ExifError: Pokud operace selže
        """
        log_call(
            "ExifWriter",
            "clear",
            file=photo_path.name,
            clear_gps=clear_gps,
            clear_description=clear_description,
        )

        if not clear_gps and not clear_description:
            return False

        try:
            # Načíst existující EXIF
            try:
                exif_dict = piexif.load(str(photo_path))
            except Exception:
                log_info("no EXIF to clear")
                return False

            changed = False

            # Smazat GPS
            if clear_gps and exif_dict.get("GPS"):
                gps_tags_to_remove = [
                    piexif.GPSIFD.GPSLatitude,
                    piexif.GPSIFD.GPSLatitudeRef,
                    piexif.GPSIFD.GPSLongitude,
                    piexif.GPSIFD.GPSLongitudeRef,
                    piexif.GPSIFD.GPSAltitude,
                    piexif.GPSIFD.GPSAltitudeRef,
                ]
                for tag in gps_tags_to_remove:
                    if tag in exif_dict["GPS"]:
                        del exif_dict["GPS"][tag]
                        changed = True

            # Smazat popisek
            if clear_description:
                # ImageDescription v IFD0
                if exif_dict.get("0th") and piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
                    del exif_dict["0th"][piexif.ImageIFD.ImageDescription]
                    changed = True

                # UserComment v Exif IFD
                if exif_dict.get("Exif") and piexif.ExifIFD.UserComment in exif_dict["Exif"]:
                    del exif_dict["Exif"][piexif.ExifIFD.UserComment]
                    changed = True

            if changed:
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(photo_path))
                log_info("EXIF cleared")

            return changed

        except Exception as e:
            raise ExifError(f"Chyba při mazání EXIF z {photo_path}: {e}")
