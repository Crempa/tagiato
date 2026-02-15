"""Configuration for Tagiato."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Configuration for photo processing."""

    # Path to the photos directory
    photos_dir: Path

    # Path to timeline JSON (optional)
    timeline_path: Optional[Path] = None

    # Maximum time difference between photo and GPS point (in minutes)
    max_time_gap: int = 30

    # Model for Claude (sonnet/opus/haiku)
    model: str = "sonnet"

    # Thumbnail size (shorter side in px)
    thumbnail_size: int = 1024

    # Verbose mode
    verbose: bool = False

    # Generate XMP sidecar files
    xmp: bool = False

    # Working directory
    @property
    def work_dir(self) -> Path:
        return self.photos_dir / ".tagiato"

    @property
    def thumbnails_dir(self) -> Path:
        return self.work_dir / "thumbnails"

    @property
    def state_file(self) -> Path:
        return self.work_dir / "state.json"

    @property
    def geocode_cache_file(self) -> Path:
        return self.work_dir / "geocode_cache.json"

    @property
    def descriptions_file(self) -> Path:
        return self.photos_dir / "descriptions.md"

    def ensure_dirs(self) -> None:
        """Creates necessary directories."""
        self.work_dir.mkdir(exist_ok=True)
        self.thumbnails_dir.mkdir(exist_ok=True)
