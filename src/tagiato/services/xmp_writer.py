"""Generování XMP sidecar souborů."""

from pathlib import Path
from typing import Optional
from datetime import datetime

from tagiato.models.location import GPSCoordinates


class XmpWriter:
    """Vytváří XMP sidecar soubory pro fotky."""

    XMP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Tagiato">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:exif="http://ns.adobe.com/exif/1.0/"
      xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">
{gps_section}
{description_section}
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

    GPS_SECTION = """      <exif:GPSLatitude>{lat_dms}</exif:GPSLatitude>
      <exif:GPSLongitude>{lng_dms}</exif:GPSLongitude>"""

    DESCRIPTION_SECTION = """      <dc:description>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">{description}</rdf:li>
        </rdf:Alt>
      </dc:description>
      <photoshop:Headline>{headline}</photoshop:Headline>"""

    def write(
        self,
        photo_path: Path,
        gps: Optional[GPSCoordinates] = None,
        description: Optional[str] = None,
    ) -> Path:
        """Vytvoří XMP sidecar soubor pro fotku.

        Args:
            photo_path: Cesta k originální fotce
            gps: GPS souřadnice (volitelné)
            description: Popisek (volitelné)

        Returns:
            Cesta k vytvořenému XMP souboru
        """
        xmp_path = photo_path.with_suffix(".xmp")

        # Připravit sekce
        gps_section = ""
        if gps:
            gps_section = self.GPS_SECTION.format(
                lat_dms=self._format_gps_for_xmp(gps.latitude, "N", "S"),
                lng_dms=self._format_gps_for_xmp(gps.longitude, "E", "W"),
            )

        description_section = ""
        if description:
            # Escapovat XML speciální znaky
            escaped_desc = self._escape_xml(description)
            # Headline je zkrácená verze (první věta nebo max 100 znaků)
            headline = self._create_headline(description)
            description_section = self.DESCRIPTION_SECTION.format(
                description=escaped_desc,
                headline=self._escape_xml(headline),
            )

        # Vygenerovat XMP
        xmp_content = self.XMP_TEMPLATE.format(
            gps_section=gps_section,
            description_section=description_section,
        )

        # Uložit
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(xmp_content)

        return xmp_path

    def _format_gps_for_xmp(self, decimal: float, pos_ref: str, neg_ref: str) -> str:
        """Formátuje GPS souřadnici do XMP formátu (DD,MM.MMM[N|S|E|W])."""
        ref = pos_ref if decimal >= 0 else neg_ref
        decimal = abs(decimal)

        degrees = int(decimal)
        minutes = (decimal - degrees) * 60

        return f"{degrees},{minutes:.6f}{ref}"

    def _escape_xml(self, text: str) -> str:
        """Escapuje speciální XML znaky."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _create_headline(self, description: str) -> str:
        """Vytvoří headline z popisu (první věta nebo max 100 znaků)."""
        # Najít konec první věty
        for end_char in [".", "!", "?"]:
            idx = description.find(end_char)
            if idx != -1 and idx < 100:
                return description[: idx + 1]

        # Pokud není konec věty, zkrátit na 100 znaků
        if len(description) > 100:
            return description[:97] + "..."
        return description
