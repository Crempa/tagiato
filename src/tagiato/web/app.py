"""FastAPI aplikace pro web UI."""

import re
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tagiato.models.photo import Photo
from tagiato.models.location import Location
from tagiato.services.photo_scanner import PhotoScanner
from tagiato.services.timeline_loader import TimelineLoader
from tagiato.services.location_matcher import LocationMatcher
from tagiato.services.thumbnail import ThumbnailGenerator
from tagiato.web.state import app_state, PhotoState, ProcessingStatus
from tagiato.web.routes import router


def _read_location_from_xmp(xmp_path: Path) -> Optional[str]:
    """Přečte location_name z XMP sidecar souboru.

    Args:
        xmp_path: Cesta k XMP souboru

    Returns:
        Název místa nebo None
    """
    if not xmp_path.exists():
        return None

    try:
        content = xmp_path.read_text(encoding="utf-8")
        # Hledáme tag <Iptc4xmpCore:Location>...</Iptc4xmpCore:Location>
        match = re.search(r"<Iptc4xmpCore:Location>([^<]+)</Iptc4xmpCore:Location>", content)
        if match:
            # Unescape XML entities
            location = match.group(1)
            location = location.replace("&amp;", "&")
            location = location.replace("&lt;", "<")
            location = location.replace("&gt;", ">")
            location = location.replace("&quot;", '"')
            location = location.replace("&apos;", "'")
            return location.strip() if location.strip() else None
    except (IOError, UnicodeDecodeError):
        pass

    return None


def create_app(
    photos_dir: Path,
    timeline_path: Optional[Path] = None,
    describe_provider: str = "claude",
    describe_model: str = "sonnet",
    locate_provider: str = "claude",
    locate_model: str = "sonnet",
) -> FastAPI:
    """Create and configure FastAPI app."""

    app = FastAPI(
        title="Tagiato",
        description="Web UI pro zpracování fotek",
    )

    # Setup paths
    work_dir = photos_dir / ".tagiato"
    work_dir.mkdir(exist_ok=True)
    thumbnails_dir = work_dir / "thumbnails"
    thumbnails_dir.mkdir(exist_ok=True)

    # Store config in app state
    app_state.photos_dir = photos_dir
    app_state.thumbnails_dir = thumbnails_dir
    app_state.tagiato_dir = work_dir

    # Provider settings
    app_state.describe_provider = describe_provider
    app_state.describe_model = describe_model
    app_state.locate_provider = locate_provider
    app_state.locate_model = locate_model

    # Load prompt presets
    app_state.load_presets()

    # Templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Load photos
    _load_photos(photos_dir, timeline_path, thumbnails_dir)

    # Include API routes
    app.include_router(router)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Main page."""
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "folder_name": photos_dir.name,
                "photos_count": len(app_state.photos),
                "describe_provider": app_state.describe_provider,
                "describe_model": app_state.describe_model,
                "locate_provider": app_state.locate_provider,
                "locate_model": app_state.locate_model,
            }
        )

    return app


def _load_photos(
    photos_dir: Path,
    timeline_path: Optional[Path],
    thumbnails_dir: Path,
) -> None:
    """Load photos and match GPS from timeline."""

    # Scan photos
    scanner = PhotoScanner()
    photos: List[Photo] = scanner.scan(photos_dir)

    # Load timeline if provided
    matcher: Optional[LocationMatcher] = None
    if timeline_path:
        loader = TimelineLoader()
        timeline_points = loader.load(timeline_path)
        if timeline_points:
            matcher = LocationMatcher(timeline_points)

    # Thumbnail generator
    thumbnail_gen = ThumbnailGenerator(thumbnails_dir)

    # Process each photo
    for photo in photos:
        # Create state
        state = PhotoState(
            filename=photo.filename,
            path=photo.path,
            timestamp=photo.timestamp,
        )

        # GPS from EXIF
        if photo.original_gps:
            state.gps = photo.original_gps
            state.gps_source = "exif"
            state.has_exif_gps = True

        # GPS from timeline (only if no EXIF GPS)
        elif matcher and photo.timestamp:
            location: Optional[Location] = matcher.match(photo.timestamp)
            if location:
                state.gps = location.coordinates
                state.gps_source = "timeline"
                state.place_name = location.place_name

        # Read description from EXIF
        if photo.description:
            state.description = photo.description
            state.has_exif_description = True
            state.ai_status = ProcessingStatus.DONE

        # Read location_name - first from IPTC in JPEG (via exiftool), then XMP sidecar as fallback
        if photo.location_name:
            state.location_name = photo.location_name
        else:
            xmp_path = photo.path.with_suffix(".xmp")
            location_name = _read_location_from_xmp(xmp_path)
            if location_name:
                state.location_name = location_name

        # Generate thumbnail path (generate on-demand)
        thumb_path = thumbnails_dir / f"{photo.path.stem}_thumb.jpg"
        if thumb_path.exists():
            state.thumbnail_path = thumb_path

        # Store in app state
        app_state.photos[photo.filename] = state
        app_state.photos_order.append(photo.filename)
