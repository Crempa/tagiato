"""Zápis GPS a popisků do EXIF metadat."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import piexif

from tagiato.core.exceptions import ExifError
from tagiato.core.logger import log_call, log_info, log_warning
from tagiato.models.location import GPSCoordinates


def is_exiftool_available() -> bool:
    """Zkontroluje, zda je exiftool dostupný v PATH."""
    return shutil.which("exiftool") is not None


def read_location_name(photo_path: Path) -> Optional[str]:
    """Přečte název lokality z IPTC:Sub-location pomocí exiftool.

    Args:
        photo_path: Cesta k JPEG souboru

    Returns:
        Název lokality nebo None pokud není nastaven nebo exiftool není dostupný
    """
    if not is_exiftool_available():
        return None

    try:
        result = subprocess.run(
            ["exiftool", "-s3", "-IPTC:Sub-location", str(photo_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


class ExifWriter:
    """Zapisuje GPS souřadnice a popisky do EXIF metadat JPEG souborů."""

    def write(
        self,
        photo_path: Path,
        gps: Optional[GPSCoordinates] = None,
        description: Optional[str] = None,
        location_name: Optional[str] = None,
        skip_existing_gps: bool = True,
    ) -> None:
        """Zapíše GPS a/nebo popisek do EXIF.

        Args:
            photo_path: Cesta k JPEG souboru
            gps: GPS souřadnice (volitelné)
            description: Popisek fotky (volitelné)
            location_name: Název lokality (volitelné, vyžaduje exiftool)
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
            location_name=location_name,
            skip_existing_gps=skip_existing_gps,
        )

        if gps is None and description is None and location_name is None:
            log_info("nothing to write")
            return

        # Použít exiftool pokud je dostupný
        if is_exiftool_available():
            self._write_with_exiftool(photo_path, gps, description, location_name, skip_existing_gps)
        else:
            # Fallback na piexif (bez location_name)
            self._write_with_piexif(photo_path, gps, description, skip_existing_gps)
            if location_name:
                log_warning("exiftool není dostupný, location_name nebude zapsán")

    def _write_with_exiftool(
        self,
        photo_path: Path,
        gps: Optional[GPSCoordinates],
        description: Optional[str],
        location_name: Optional[str],
        skip_existing_gps: bool,
    ) -> None:
        """Zapíše metadata pomocí exiftool."""
        args = ["exiftool", "-overwrite_original"]

        # GPS
        if gps is not None:
            if skip_existing_gps:
                # Zkontrolovat existující GPS
                check = subprocess.run(
                    ["exiftool", "-s3", "-GPSLatitude", str(photo_path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                has_gps = bool(check.stdout.strip())
                if has_gps:
                    log_info("GPS already exists, skipping")
                else:
                    args.extend([
                        f"-GPSLatitude={abs(gps.latitude)}",
                        f"-GPSLatitudeRef={'N' if gps.latitude >= 0 else 'S'}",
                        f"-GPSLongitude={abs(gps.longitude)}",
                        f"-GPSLongitudeRef={'E' if gps.longitude >= 0 else 'W'}",
                    ])
            else:
                args.extend([
                    f"-GPSLatitude={abs(gps.latitude)}",
                    f"-GPSLatitudeRef={'N' if gps.latitude >= 0 else 'S'}",
                    f"-GPSLongitude={abs(gps.longitude)}",
                    f"-GPSLongitudeRef={'E' if gps.longitude >= 0 else 'W'}",
                ])

        # Description - do ImageDescription i UserComment
        if description is not None:
            args.extend([
                f"-ImageDescription={description}",
                f"-UserComment={description}",
            ])

        # Location name - do IPTC:Sub-location
        if location_name is not None:
            args.append(f"-IPTC:Sub-location={location_name}")

        # Pokud jsou jen základní argumenty, nic nezapisujeme
        if len(args) <= 2:
            log_info("nothing to write with exiftool")
            return

        args.append(str(photo_path))

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise ExifError(f"exiftool selhal: {result.stderr}")
            log_info(f"Metadata zapsána pomocí exiftool")
        except subprocess.TimeoutExpired:
            raise ExifError("exiftool timeout")
        except ExifError:
            raise
        except Exception as e:
            raise ExifError(f"Chyba při zápisu pomocí exiftool: {e}")

    def _write_with_piexif(
        self,
        photo_path: Path,
        gps: Optional[GPSCoordinates],
        description: Optional[str],
        skip_existing_gps: bool,
    ) -> None:
        """Zapíše metadata pomocí piexif (fallback bez location_name)."""
        try:
            # Načíst existující EXIF
            try:
                exif_dict = piexif.load(str(photo_path))
            except Exception:
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
        log_info(f"Writing GPS to EXIF: {gps} -> lat={lat_dms} {lat_ref}, lng={lng_dms} {lng_ref}")

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
        clear_location_name: bool = True,
    ) -> bool:
        """Smaže GPS a/nebo popisek z EXIF.

        Args:
            photo_path: Cesta k JPEG souboru
            clear_gps: Smazat GPS data
            clear_description: Smazat popisek
            clear_location_name: Smazat název lokality (IPTC:Sub-location)

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
            clear_location_name=clear_location_name,
        )

        if not clear_gps and not clear_description and not clear_location_name:
            return False

        # Použít exiftool pokud je dostupný
        if is_exiftool_available():
            return self._clear_with_exiftool(photo_path, clear_gps, clear_description, clear_location_name)
        else:
            return self._clear_with_piexif(photo_path, clear_gps, clear_description)

    def _clear_with_exiftool(
        self,
        photo_path: Path,
        clear_gps: bool,
        clear_description: bool,
        clear_location_name: bool,
    ) -> bool:
        """Smaže metadata pomocí exiftool."""
        args = ["exiftool", "-overwrite_original"]

        if clear_gps:
            args.extend(["-GPSLatitude=", "-GPSLatitudeRef=", "-GPSLongitude=", "-GPSLongitudeRef="])

        if clear_description:
            args.extend(["-ImageDescription=", "-UserComment="])

        if clear_location_name:
            args.append("-IPTC:Sub-location=")

        if len(args) <= 2:
            return False

        args.append(str(photo_path))

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                log_info("Metadata smazána pomocí exiftool")
                return True
            return False
        except Exception as e:
            log_warning(f"Chyba při mazání pomocí exiftool: {e}")
            return False

    def _clear_with_piexif(
        self,
        photo_path: Path,
        clear_gps: bool,
        clear_description: bool,
    ) -> bool:
        """Smaže metadata pomocí piexif (fallback)."""
        try:
            try:
                exif_dict = piexif.load(str(photo_path))
            except Exception:
                log_info("no EXIF to clear")
                return False

            changed = False

            if clear_gps and exif_dict.get("GPS"):
                gps_tags = [
                    piexif.GPSIFD.GPSLatitude,
                    piexif.GPSIFD.GPSLatitudeRef,
                    piexif.GPSIFD.GPSLongitude,
                    piexif.GPSIFD.GPSLongitudeRef,
                    piexif.GPSIFD.GPSAltitude,
                    piexif.GPSIFD.GPSAltitudeRef,
                ]
                for tag in gps_tags:
                    if tag in exif_dict["GPS"]:
                        del exif_dict["GPS"][tag]
                        changed = True

            if clear_description:
                if exif_dict.get("0th") and piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
                    del exif_dict["0th"][piexif.ImageIFD.ImageDescription]
                    changed = True
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
