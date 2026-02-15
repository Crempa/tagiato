"""Processing state management for resumability."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PhotoState:
    """Processing state of a single photo."""

    filename: str
    processed: bool = False
    has_gps: bool = False
    has_description: bool = False
    gps_refined: bool = False
    error: Optional[str] = None
    processed_at: Optional[str] = None


@dataclass
class ProcessingState:
    """Overall processing state."""

    started_at: str = ""
    completed_at: Optional[str] = None
    total_photos: int = 0
    processed_photos: int = 0
    photos: Dict[str, PhotoState] = field(default_factory=dict)


class StateManager:
    """Manages processing state for resumability."""

    def __init__(self, state_file: Path):
        """
        Args:
            state_file: Path to the state file
        """
        self.state_file = state_file
        self._state: Optional[ProcessingState] = None

    def load(self) -> ProcessingState:
        """Load state from file or create a new one."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Reconstruct PhotoState objects
                photos = {}
                for filename, photo_data in data.get("photos", {}).items():
                    photos[filename] = PhotoState(**photo_data)

                self._state = ProcessingState(
                    started_at=data.get("started_at", ""),
                    completed_at=data.get("completed_at"),
                    total_photos=data.get("total_photos", 0),
                    processed_photos=data.get("processed_photos", 0),
                    photos=photos,
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                self._state = self._create_new_state()
        else:
            self._state = self._create_new_state()

        return self._state

    def _create_new_state(self) -> ProcessingState:
        """Create a new state."""
        return ProcessingState(started_at=datetime.now().isoformat())

    def save(self) -> None:
        """Save state to file."""
        if self._state is None:
            return

        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Serialize to JSON
        data = {
            "started_at": self._state.started_at,
            "completed_at": self._state.completed_at,
            "total_photos": self._state.total_photos,
            "processed_photos": self._state.processed_photos,
            "photos": {
                filename: asdict(photo) for filename, photo in self._state.photos.items()
            },
        }

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_photo_processed(self, filename: str) -> bool:
        """Check whether the photo has already been processed."""
        if self._state is None:
            return False
        photo_state = self._state.photos.get(filename)
        return photo_state is not None and photo_state.processed

    def mark_photo_processed(
        self,
        filename: str,
        has_gps: bool = False,
        has_description: bool = False,
        gps_refined: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Mark a photo as processed."""
        if self._state is None:
            self._state = self._create_new_state()

        self._state.photos[filename] = PhotoState(
            filename=filename,
            processed=True,
            has_gps=has_gps,
            has_description=has_description,
            gps_refined=gps_refined,
            error=error,
            processed_at=datetime.now().isoformat(),
        )
        self._state.processed_photos = sum(
            1 for p in self._state.photos.values() if p.processed
        )
        self.save()

    def set_total_photos(self, count: int) -> None:
        """Set the total number of photos."""
        if self._state is None:
            self._state = self._create_new_state()
        self._state.total_photos = count
        self.save()

    def mark_completed(self) -> None:
        """Mark processing as completed."""
        if self._state is None:
            return
        self._state.completed_at = datetime.now().isoformat()
        self.save()

    def get_stats(self) -> dict:
        """Return processing statistics."""
        if self._state is None:
            return {}

        with_description = sum(1 for p in self._state.photos.values() if p.has_description)
        with_gps = sum(1 for p in self._state.photos.values() if p.has_gps)
        gps_refined = sum(1 for p in self._state.photos.values() if p.gps_refined)
        errors = sum(1 for p in self._state.photos.values() if p.error)

        return {
            "total": self._state.total_photos,
            "processed": self._state.processed_photos,
            "with_description": with_description,
            "without_description": self._state.processed_photos - with_description,
            "with_gps": with_gps,
            "gps_refined": gps_refined,
            "errors": errors,
            "started_at": self._state.started_at,
            "completed_at": self._state.completed_at,
        }
