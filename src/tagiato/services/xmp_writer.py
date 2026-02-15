"""Generating XMP sidecar files."""

from pathlib import Path
from typing import Optional
from datetime import datetime

from tagiato.core.logger import log_call, log_result
from tagiato.models.location import GPSCoordinates


class XmpWriter:
    """Creates XMP sidecar files for photos."""

    XMP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Tagiato">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:exif="http://ns.adobe.com/exif/1.0/"
      xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
      xmlns:Iptc4xmpCore="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/">
{gps_section}
{description_section}
{location_section}
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

    LOCATION_SECTION = """      <Iptc4xmpCore:Location>{location}</Iptc4xmpCore:Location>"""

    def write(
        self,
        photo_path: Path,
        gps: Optional[GPSCoordinates] = None,
        description: Optional[str] = None,
        location_name: Optional[str] = None,
    ) -> Path:
        """Create an XMP sidecar file for a photo.

        Args:
            photo_path: Path to the original photo
            gps: GPS coordinates (optional)
            description: Description (optional)
            location_name: Place name (optional)

        Returns:
            Path to the created XMP file
        """
        log_call(
            "XmpWriter",
            "write",
            file=photo_path.name,
            gps=str(gps) if gps else None,
            description=f"{len(description)} chars" if description else None,
            location_name=location_name,
        )

        xmp_path = photo_path.with_suffix(".xmp")

        # Prepare sections
        gps_section = ""
        if gps:
            gps_section = self.GPS_SECTION.format(
                lat_dms=self._format_gps_for_xmp(gps.latitude, "N", "S"),
                lng_dms=self._format_gps_for_xmp(gps.longitude, "E", "W"),
            )

        description_section = ""
        if description:
            # Escape XML special characters
            escaped_desc = self._escape_xml(description)
            # Headline is a shortened version (first sentence or max 100 characters)
            headline = self._create_headline(description)
            description_section = self.DESCRIPTION_SECTION.format(
                description=escaped_desc,
                headline=self._escape_xml(headline),
            )

        location_section = ""
        if location_name:
            location_section = self.LOCATION_SECTION.format(
                location=self._escape_xml(location_name),
            )

        # Generate XMP
        xmp_content = self.XMP_TEMPLATE.format(
            gps_section=gps_section,
            description_section=description_section,
            location_section=location_section,
        )

        # Save
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(xmp_content)

        log_result("XmpWriter", "write", xmp_path.name)
        return xmp_path

    def _format_gps_for_xmp(self, decimal: float, pos_ref: str, neg_ref: str) -> str:
        """Formats a GPS coordinate into XMP format (DD,MM.MMM[N|S|E|W])."""
        ref = pos_ref if decimal >= 0 else neg_ref
        decimal = abs(decimal)

        degrees = int(decimal)
        minutes = (decimal - degrees) * 60

        return f"{degrees},{minutes:.6f}{ref}"

    def _escape_xml(self, text: str) -> str:
        """Escapes special XML characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _create_headline(self, description: str) -> str:
        """Creates a headline from the description (first sentence or max 100 characters)."""
        # Find the end of the first sentence
        for end_char in [".", "!", "?"]:
            idx = description.find(end_char)
            if idx != -1 and idx < 100:
                return description[: idx + 1]

        # If no sentence end found, truncate to 100 characters
        if len(description) > 100:
            return description[:97] + "..."
        return description
