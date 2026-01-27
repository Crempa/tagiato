"""Parsování editovaného descriptions.md souboru."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from tagiato.models.location import GPSCoordinates


@dataclass
class ParsedPhoto:
    """Parsovaná fotka z MD souboru."""

    filename: str
    gps: Optional[GPSCoordinates] = None
    description: str = ""


class MdParser:
    """Parsuje descriptions.md a extrahuje úpravy."""

    # Regex pro parsování
    PHOTO_HEADER_RE = re.compile(r"^###?\s+(.+\.jpe?g)\s*$", re.IGNORECASE)
    GPS_RE = re.compile(r"^GPS:\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$")
    SEPARATOR_RE = re.compile(r"^-{3,}\s*$")

    def parse(self, md_path: Path) -> List[ParsedPhoto]:
        """Parsuje MD soubor a vrátí seznam fotek s úpravami.

        Args:
            md_path: Cesta k descriptions.md

        Returns:
            Seznam ParsedPhoto
        """
        if not md_path.exists():
            return []

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        return self._parse_content(content)

    def _parse_content(self, content: str) -> List[ParsedPhoto]:
        """Parsuje obsah MD souboru."""
        photos = []
        lines = content.split("\n")

        current_photo: Optional[ParsedPhoto] = None
        description_lines: List[str] = []
        in_header = True  # Na začátku souboru je hlavička

        for line in lines:
            # Separator mezi fotkami
            if self.SEPARATOR_RE.match(line):
                # Uložit předchozí fotku
                if current_photo:
                    current_photo.description = self._clean_description(description_lines)
                    photos.append(current_photo)
                    current_photo = None
                    description_lines = []
                in_header = False
                continue

            # Hlavička fotky
            header_match = self.PHOTO_HEADER_RE.match(line)
            if header_match:
                # Uložit předchozí fotku
                if current_photo:
                    current_photo.description = self._clean_description(description_lines)
                    photos.append(current_photo)
                    description_lines = []

                current_photo = ParsedPhoto(filename=header_match.group(1))
                in_header = False
                continue

            # Přeskočit hlavičku souboru
            if in_header:
                continue

            # GPS řádek
            if current_photo:
                gps_match = self.GPS_RE.match(line)
                if gps_match:
                    try:
                        lat = float(gps_match.group(1))
                        lng = float(gps_match.group(2))
                        current_photo.gps = GPSCoordinates(latitude=lat, longitude=lng)
                    except ValueError:
                        pass
                    continue

                # Popisek - přidat řádek
                # Přeskočit prázdné řádky na začátku popisu
                if line.strip() or description_lines:
                    description_lines.append(line)

        # Uložit poslední fotku
        if current_photo:
            current_photo.description = self._clean_description(description_lines)
            photos.append(current_photo)

        return photos

    def _clean_description(self, lines: List[str]) -> str:
        """Očistí a spojí řádky popisu."""
        # Odstranit prázdné řádky na začátku a konci
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        # Spojit a odstranit poznámky v závorkách na začátku
        text = "\n".join(lines).strip()

        # Odstranit "(prázdný popisek...)" nebo podobné
        if text.startswith("(") and "popisek" in text.lower():
            return ""

        return text
