"""In-memory stav fotek pro web UI."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import threading
import queue
import json

from tagiato.models.location import GPSCoordinates


class LogBuffer:
    """Thread-safe log buffer pro web UI."""

    MAX_ENTRIES = 1000

    def __init__(self):
        self.entries: List[dict] = []
        self.lock = threading.Lock()
        self.subscribers: List[queue.Queue] = []

    def add(self, level: str, message: str, data: Optional[dict] = None):
        """Přidá log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }

        with self.lock:
            self.entries.append(entry)
            # Omezit velikost bufferu
            if len(self.entries) > self.MAX_ENTRIES:
                self.entries = self.entries[-self.MAX_ENTRIES:]

            # Notifikovat subscribery
            for q in self.subscribers:
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    pass

    def get_all(self) -> List[dict]:
        """Vrátí všechny log entries."""
        with self.lock:
            return list(self.entries)

    def clear(self):
        """Vymaže log buffer."""
        with self.lock:
            self.entries.clear()

    def subscribe(self) -> queue.Queue:
        """Vytvoří nový subscriber queue pro SSE."""
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        """Odstraní subscriber queue."""
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


# Global log buffer
log_buffer = LogBuffer()


class ProcessingStatus(str, Enum):
    """Stav zpracování fotky."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class PhotoState:
    """Stav jedné fotky v UI."""

    filename: str
    path: Path
    timestamp: Optional[datetime] = None

    # GPS data
    gps: Optional[GPSCoordinates] = None
    gps_source: str = ""  # "exif", "timeline", "manual"

    # Place name from timeline (optional context for AI)
    place_name: Optional[str] = None

    # AI description
    description: str = ""

    # Thumbnail
    thumbnail_path: Optional[Path] = None

    # Processing status
    ai_status: ProcessingStatus = ProcessingStatus.PENDING
    locate_status: ProcessingStatus = ProcessingStatus.PENDING

    # Error messages
    ai_error: Optional[str] = None
    locate_error: Optional[str] = None

    # AI location result
    locate_confidence: str = ""  # "high", "medium", "low"
    location_name: str = ""  # Name of located place (from AI locate or XMP)

    # Flags
    has_exif_gps: bool = False
    has_exif_description: bool = False
    ai_empty_response: bool = False  # AI returned empty description

    # Dirty flag - unsaved changes
    is_dirty: bool = False

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "filename": self.filename,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "gps": {
                "lat": self.gps.latitude,
                "lng": self.gps.longitude,
            } if self.gps else None,
            "gps_source": self.gps_source,
            "place_name": self.place_name,
            "description": self.description,
            "has_thumbnail": self.thumbnail_path is not None,
            "ai_status": self.ai_status.value,
            "ai_error": self.ai_error,
            "locate_status": self.locate_status.value,
            "locate_error": self.locate_error,
            "locate_confidence": self.locate_confidence,
            "location_name": self.location_name,
            "has_exif_gps": self.has_exif_gps,
            "has_exif_description": self.has_exif_description,
            "ai_empty_response": self.ai_empty_response,
            "is_dirty": self.is_dirty,
        }


@dataclass
class BatchState:
    """Stav dávkového zpracování."""

    is_running: bool = False
    should_stop: bool = False
    current_photo: Optional[str] = None
    queue: List[str] = field(default_factory=list)
    completed: List[str] = field(default_factory=list)
    operation: str = "describe"  # "describe" or "locate"

    def to_dict(self) -> dict:
        return {
            "is_running": self.is_running,
            "current_photo": self.current_photo,
            "queue_count": len(self.queue),
            "completed_count": len(self.completed),
            "queue": self.queue[:10],  # First 10 for preview
            "operation": self.operation,
        }


class AppState:
    """Globální stav aplikace."""

    def __init__(self):
        self.photos: Dict[str, PhotoState] = {}
        self.photos_order: List[str] = []  # Ordered by timestamp
        self.batch: BatchState = BatchState()
        self.lock = threading.Lock()

        # Config
        self.photos_dir: Optional[Path] = None
        self.thumbnails_dir: Optional[Path] = None
        self.tagiato_dir: Optional[Path] = None  # .tagiato working directory

        # AI provider settings
        self.describe_provider: str = "claude"  # "claude" or "gemini"
        self.describe_model: str = "sonnet"
        self.locate_provider: str = "claude"  # "claude" or "gemini"
        self.locate_model: str = "sonnet"

        # Custom AI prompts (None = use default)
        self.describe_prompt: Optional[str] = None
        self.locate_prompt: Optional[str] = None

        # Prompt presets
        self.active_preset: Optional[str] = None  # key of active preset
        self.presets: Dict[str, dict] = {}  # loaded presets

    def get_photo(self, filename: str) -> Optional[PhotoState]:
        """Get photo by filename."""
        with self.lock:
            return self.photos.get(filename)

    def update_photo(self, filename: str, **kwargs) -> Optional[PhotoState]:
        """Update photo state."""
        with self.lock:
            if filename not in self.photos:
                return None
            photo = self.photos[filename]
            for key, value in kwargs.items():
                if hasattr(photo, key):
                    setattr(photo, key, value)
            return photo

    def get_all_photos(self) -> List[PhotoState]:
        """Get all photos in order."""
        with self.lock:
            return [self.photos[name] for name in self.photos_order if name in self.photos]

    def get_photos_dict(self) -> List[dict]:
        """Get all photos as dicts for JSON response."""
        return [p.to_dict() for p in self.get_all_photos()]

    def load_presets(self) -> None:
        """Načte presety z prompts.json a aktivuje poslední."""
        if not self.tagiato_dir:
            return

        prompts_file = self.tagiato_dir / "prompts.json"
        if not prompts_file.exists():
            return

        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.presets = data.get("presets", {})
            last_active = data.get("last_active")

            # Activate last used preset if exists
            if last_active and last_active in self.presets:
                self._activate_preset_internal(last_active)

        except (json.JSONDecodeError, IOError):
            pass

    def save_presets(self) -> None:
        """Uloží presety do prompts.json."""
        if not self.tagiato_dir:
            return

        prompts_file = self.tagiato_dir / "prompts.json"
        data = {
            "last_active": self.active_preset,
            "presets": self.presets,
        }

        try:
            with open(prompts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def _activate_preset_internal(self, key: str) -> bool:
        """Aktivuje preset bez ukládání."""
        if key not in self.presets:
            return False

        preset = self.presets[key]
        self.describe_prompt = preset.get("describe_prompt")
        self.locate_prompt = preset.get("locate_prompt")
        self.active_preset = key
        return True

    def activate_preset(self, key: str) -> bool:
        """Aktivuje preset a uloží jako poslední použitý."""
        if not self._activate_preset_internal(key):
            return False
        self.save_presets()
        return True

    def create_preset(self, key: str, name: str, describe_prompt: str, locate_prompt: str) -> None:
        """Vytvoří nový preset a aktivuje ho."""
        self.presets[key] = {
            "name": name,
            "describe_prompt": describe_prompt,
            "locate_prompt": locate_prompt,
        }
        self.describe_prompt = describe_prompt
        self.locate_prompt = locate_prompt
        self.active_preset = key
        self.save_presets()

    def delete_preset(self, key: str) -> bool:
        """Smaže preset."""
        if key not in self.presets:
            return False

        del self.presets[key]

        # If deleted preset was active, reset prompts
        if self.active_preset == key:
            self.active_preset = None
            self.describe_prompt = None
            self.locate_prompt = None

        self.save_presets()
        return True

    def get_prompts_state(self) -> dict:
        """Vrátí aktuální stav promptů pro API."""
        return {
            "describe_prompt": self.describe_prompt,
            "locate_prompt": self.locate_prompt,
            "active_preset": self.active_preset,
            "active_preset_name": self.presets[self.active_preset]["name"] if self.active_preset and self.active_preset in self.presets else None,
        }


# Global app state
app_state = AppState()
