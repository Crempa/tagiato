"""In-memory photo state for web UI."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import threading
import queue
import json
import uuid

from tagiato.models.location import GPSCoordinates


class TaskStatus(str, Enum):
    """AI task status."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class AITask:
    """AI task for asynchronous processing."""
    task_id: str
    filename: str
    operation: str  # "describe" or "locate"
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "filename": self.filename,
            "operation": self.operation,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


class LogBuffer:
    """Thread-safe log buffer for web UI."""

    MAX_ENTRIES = 1000

    def __init__(self):
        self.entries: List[dict] = []
        self.lock = threading.Lock()
        self.subscribers: List[queue.Queue] = []

    def add(self, level: str, message: str, data: Optional[dict] = None):
        """Add a log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }

        with self.lock:
            self.entries.append(entry)
            # Limit buffer size
            if len(self.entries) > self.MAX_ENTRIES:
                self.entries = self.entries[-self.MAX_ENTRIES:]

            # Notify subscribers
            for q in self.subscribers:
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    pass

    def get_all(self) -> List[dict]:
        """Return all log entries."""
        with self.lock:
            return list(self.entries)

    def clear(self):
        """Clear the log buffer."""
        with self.lock:
            self.entries.clear()

    def subscribe(self) -> queue.Queue:
        """Create a new subscriber queue for SSE."""
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        """Remove a subscriber queue."""
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


# Global log buffer
log_buffer = LogBuffer()


class ProcessingStatus(str, Enum):
    """Photo processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class PhotoState:
    """State of a single photo in the UI."""

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
    """Batch processing state."""

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
    """Global application state."""

    def __init__(self):
        self.photos: Dict[str, PhotoState] = {}
        self.photos_order: List[str] = []  # Ordered by timestamp
        self.batch: BatchState = BatchState()
        self.lock = threading.Lock()

        # AI tasks for async processing
        self.ai_tasks: Dict[str, AITask] = {}
        self.ai_tasks_lock = threading.Lock()

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

        # Context settings for nearby descriptions
        self.context_enabled: bool = True
        self.context_radius_km: float = 5.0
        self.context_max_count: int = 5

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

    def create_task(self, filename: str, operation: str) -> AITask:
        """Create a new AI task."""
        task_id = str(uuid.uuid4())
        task = AITask(
            task_id=task_id,
            filename=filename,
            operation=operation,
            status=TaskStatus.PENDING,
        )
        with self.ai_tasks_lock:
            self.ai_tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[AITask]:
        """Return AI task by ID."""
        with self.ai_tasks_lock:
            return self.ai_tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs) -> Optional[AITask]:
        """Update AI task."""
        with self.ai_tasks_lock:
            task = self.ai_tasks.get(task_id)
            if not task:
                return None
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            return task

    def cleanup_old_tasks(self, max_age_seconds: int = 3600) -> None:
        """Remove old completed tasks."""
        with self.ai_tasks_lock:
            to_remove = []
            for task_id, task in self.ai_tasks.items():
                if task.status in (TaskStatus.DONE, TaskStatus.ERROR):
                    to_remove.append(task_id)
            # Keep only last 100 completed tasks
            if len(to_remove) > 100:
                for task_id in to_remove[:-100]:
                    del self.ai_tasks[task_id]

    def get_photos_dict(self) -> List[dict]:
        """Get all photos as dicts for JSON response."""
        return [p.to_dict() for p in self.get_all_photos()]

    def load_presets(self) -> None:
        """Load presets from prompts.json and activate the last one."""
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
        """Save presets to prompts.json."""
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
        """Activate preset without saving."""
        if key not in self.presets:
            return False

        preset = self.presets[key]
        self.describe_prompt = preset.get("describe_prompt")
        self.locate_prompt = preset.get("locate_prompt")
        self.active_preset = key
        return True

    def activate_preset(self, key: str) -> bool:
        """Activate preset and save as last used."""
        if not self._activate_preset_internal(key):
            return False
        self.save_presets()
        return True

    def create_preset(self, key: str, name: str, describe_prompt: str, locate_prompt: str) -> None:
        """Create a new preset and activate it."""
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
        """Delete a preset."""
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
        """Return current prompts state for API."""
        return {
            "describe_prompt": self.describe_prompt,
            "locate_prompt": self.locate_prompt,
            "active_preset": self.active_preset,
            "active_preset_name": self.presets[self.active_preset]["name"] if self.active_preset and self.active_preset in self.presets else None,
        }

    def _estimate_gps_from_time(self, photo: PhotoState) -> Optional[GPSCoordinates]:
        """Estimate GPS from temporally close photos (within 30 minutes).

        Args:
            photo: Photo without GPS

        Returns:
            GPS from the nearest temporally close photo, or None
        """
        if not photo.timestamp:
            return None

        MAX_TIME_GAP = 30 * 60  # 30 minutes in seconds
        closest_time_diff = float("inf")
        closest_gps = None

        for other in self.get_all_photos():
            if not other.gps or not other.timestamp:
                continue
            if other.filename == photo.filename:
                continue

            time_diff = abs((photo.timestamp - other.timestamp).total_seconds())
            if time_diff <= MAX_TIME_GAP and time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_gps = other.gps

        return closest_gps

    def get_nearby_descriptions(self, filename: str) -> List[tuple]:
        """Return descriptions from photos within radius.

        Args:
            filename: Name of photo for which we are looking for context

        Returns:
            List of tuples (filename, description, distance_km) sorted by distance
        """
        if not self.context_enabled:
            return []

        photo = self.get_photo(filename)
        if not photo:
            return []

        # Get GPS (own or estimated from time)
        target_gps = photo.gps or self._estimate_gps_from_time(photo)
        if not target_gps:
            return []

        nearby = []
        for other in self.get_all_photos():
            if other.filename == filename or not other.description:
                continue

            other_gps = other.gps or self._estimate_gps_from_time(other)
            if not other_gps:
                continue

            distance = target_gps.distance_to(other_gps)
            if distance <= self.context_radius_km:
                nearby.append((other.filename, other.description, distance))

        # Sort by distance, take max_count
        nearby.sort(key=lambda x: x[2])
        return nearby[: self.context_max_count]

    def load_settings(self) -> None:
        """Load settings from .tagiato/settings.json."""
        if not self.tagiato_dir:
            return

        settings_file = self.tagiato_dir / "settings.json"
        if not settings_file.exists():
            return

        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.context_enabled = data.get("context_enabled", True)
            self.context_radius_km = data.get("context_radius_km", 5.0)
            self.context_max_count = data.get("context_max_count", 5)

        except (json.JSONDecodeError, IOError):
            pass

    def save_settings(self) -> None:
        """Save settings to .tagiato/settings.json."""
        if not self.tagiato_dir:
            return

        settings_file = self.tagiato_dir / "settings.json"
        data = {
            "context_enabled": self.context_enabled,
            "context_radius_km": self.context_radius_km,
            "context_max_count": self.context_max_count,
        }

        try:
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass


# Global app state
app_state = AppState()
