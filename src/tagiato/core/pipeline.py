"""Hlavní pipeline pro zpracování fotek."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

from tagiato.core.config import Config
from tagiato.models.photo import Photo
from tagiato.models.location import GPSCoordinates
from tagiato.services.photo_scanner import PhotoScanner
from tagiato.services.timeline_loader import TimelineLoader
from tagiato.services.location_matcher import LocationMatcher
from tagiato.services.geocoder import Geocoder
from tagiato.services.thumbnail import ThumbnailGenerator
from tagiato.services.describer import ClaudeDescriber
from tagiato.services.exif_writer import ExifWriter
from tagiato.services.xmp_writer import XmpWriter
from tagiato.state.manager import StateManager


class Pipeline:
    """Orchestruje celý proces zpracování fotek."""

    def __init__(
        self,
        config: Config,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ):
        """
        Args:
            config: Konfigurace
            progress_callback: Callback pro progress (current, total, filename, status)
        """
        self.config = config
        self.progress_callback = progress_callback

        # Inicializovat služby
        self.scanner = PhotoScanner()
        self.timeline_loader = TimelineLoader()
        self.geocoder = Geocoder(cache_file=config.geocode_cache_file)
        self.thumbnail_gen = ThumbnailGenerator(config.thumbnails_dir, config.thumbnail_size)
        self.describer = ClaudeDescriber(model=config.model)
        self.exif_writer = ExifWriter()
        self.xmp_writer = XmpWriter()
        self.state_manager = StateManager(config.state_file)

        # Location matcher se inicializuje později
        self.location_matcher: Optional[LocationMatcher] = None

    def run(self) -> dict:
        """Spustí celou pipeline.

        Returns:
            Statistiky zpracování
        """
        # Inicializace
        self.config.ensure_dirs()
        self.state_manager.load()

        # Skenovat fotky
        photos = self.scanner.scan(self.config.photos_dir)
        self.state_manager.set_total_photos(len(photos))

        # Načíst timeline (pokud je k dispozici)
        if self.config.timeline_path:
            timeline_points = self.timeline_loader.load(self.config.timeline_path)
            self.location_matcher = LocationMatcher(
                timeline_points, self.config.max_time_gap
            )

        # Zpracovat fotky
        processed_photos = []
        for idx, photo in enumerate(photos, 1):
            # Přeskočit již zpracované
            if self.state_manager.is_photo_processed(photo.filename):
                processed_photos.append(photo)
                continue

            self._process_photo(photo, idx, len(photos))
            processed_photos.append(photo)

        # Vygenerovat souhrn a MD
        self._generate_outputs(processed_photos)

        # Dokončit
        self.state_manager.mark_completed()

        return self.state_manager.get_stats()

    def _process_photo(self, photo: Photo, current: int, total: int) -> None:
        """Zpracuje jednu fotku."""
        try:
            # Progress: matching GPS
            self._report_progress(current, total, photo.filename, "Matching GPS...")

            # Match location z timeline
            if photo.timestamp and self.location_matcher and not photo.has_original_gps:
                photo.matched_location = self.location_matcher.match(photo.timestamp)

            # Geocoding
            coords_for_geocoding = photo.final_gps
            if coords_for_geocoding and not photo.place_name:
                self._report_progress(current, total, photo.filename, "Geocoding...")
                place_name = self.geocoder.geocode(coords_for_geocoding)
                if place_name and photo.matched_location:
                    photo.matched_location.place_name = place_name

            # Thumbnail
            self._report_progress(current, total, photo.filename, "Generating thumbnail...")
            photo.thumbnail_path = self.thumbnail_gen.generate(photo.path)

            # Popis od Claude
            self._report_progress(current, total, photo.filename, "Generating description...")
            result = self.describer.describe(
                thumbnail_path=photo.thumbnail_path,
                place_name=photo.place_name,
                coords=photo.final_gps,
                timestamp=photo.timestamp.strftime("%d. %m. %Y %H:%M") if photo.timestamp else None,
            )

            photo.description = result.description
            if result.refined_gps:
                photo.refined_gps = result.refined_gps

            # Zápis EXIF
            self._report_progress(current, total, photo.filename, "Writing EXIF + XMP...")
            final_gps = photo.final_gps

            self.exif_writer.write(
                photo_path=photo.path,
                gps=final_gps if not photo.has_original_gps else None,
                description=photo.description if photo.description else None,
                skip_existing_gps=True,
            )

            # Zápis XMP
            self.xmp_writer.write(
                photo_path=photo.path,
                gps=final_gps,
                description=photo.description if photo.description else None,
            )

            photo.processed = True

            # Uložit stav
            self.state_manager.mark_photo_processed(
                filename=photo.filename,
                has_gps=final_gps is not None,
                has_description=bool(photo.description),
                gps_refined=photo.refined_gps is not None,
            )

            self._report_progress(current, total, photo.filename, "Done")

        except Exception as e:
            photo.error = str(e)
            self.state_manager.mark_photo_processed(
                filename=photo.filename,
                error=str(e),
            )

    def _generate_outputs(self, photos: List[Photo]) -> None:
        """Vygeneruje výstupní soubory."""
        # Seřadit fotky podle data
        photos_with_time = [p for p in photos if p.timestamp]
        photos_with_time.sort(key=lambda p: p.timestamp)

        # Seskupit podle dne
        days = {}
        for photo in photos_with_time:
            day_key = photo.timestamp.strftime("%Y-%m-%d")
            if day_key not in days:
                days[day_key] = []
            days[day_key].append(photo)

        # Získat unikátní místa
        places = []
        for photo in photos_with_time:
            if photo.place_name and photo.place_name not in places:
                places.append(photo.place_name)

        # Vygenerovat souhrn
        summary = ""
        if photos_with_time:
            start_date = photos_with_time[0].timestamp.strftime("%d. %m. %Y")
            end_date = photos_with_time[-1].timestamp.strftime("%d. %m. %Y")

            self._report_progress(
                len(photos), len(photos), "", "Generating trip summary..."
            )
            summary = self.describer.generate_trip_summary(
                photos_info=[p.filename for p in photos_with_time],
                places=places[:10],
                date_range=(start_date, end_date),
            )

        # Zapsat MD
        self._write_descriptions_md(photos, days, places, summary)

    def _write_descriptions_md(
        self,
        photos: List[Photo],
        days: dict,
        places: List[str],
        summary: str,
    ) -> None:
        """Zapíše descriptions.md soubor."""
        lines = []

        # Hlavička
        lines.append("# Popisky fotek")

        if photos:
            photos_with_time = [p for p in photos if p.timestamp]
            if photos_with_time:
                start = min(p.timestamp for p in photos_with_time)
                end = max(p.timestamp for p in photos_with_time)
                lines.append(f"**Období**: {start.strftime('%d. %m.')} - {end.strftime('%d. %m. %Y')}")

        if places:
            lines.append(f"**Místa**: {', '.join(places[:5])}")

        lines.append(f"**Počet fotek**: {len(photos)}")
        lines.append("")

        if summary:
            lines.append(f"AI souhrn: {summary}")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Fotky po dnech
        for day_key in sorted(days.keys()):
            day_photos = days[day_key]
            day_date = datetime.strptime(day_key, "%Y-%m-%d")
            lines.append(f"## {day_date.strftime('%d. %B %Y')}")
            lines.append("")

            for photo in day_photos:
                lines.append(f"### {photo.filename}")

                gps = photo.final_gps
                if gps:
                    lines.append(f"GPS: {gps.latitude:.6f}, {gps.longitude:.6f}")

                lines.append("")

                if photo.description:
                    lines.append(photo.description)
                else:
                    lines.append("(prázdný popisek - AI nerozpoznalo obsah)")

                lines.append("")
                lines.append("---")
                lines.append("")

        # Fotky bez timestampu
        no_time_photos = [p for p in photos if not p.timestamp]
        if no_time_photos:
            lines.append("## Bez data")
            lines.append("")

            for photo in no_time_photos:
                lines.append(f"### {photo.filename}")

                gps = photo.final_gps
                if gps:
                    lines.append(f"GPS: {gps.latitude:.6f}, {gps.longitude:.6f}")

                lines.append("")

                if photo.description:
                    lines.append(photo.description)
                else:
                    lines.append("(prázdný popisek)")

                lines.append("")
                lines.append("---")
                lines.append("")

        # Zapsat soubor
        with open(self.config.descriptions_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _report_progress(
        self, current: int, total: int, filename: str, status: str
    ) -> None:
        """Reportuje progress."""
        if self.progress_callback:
            self.progress_callback(current, total, filename, status)
