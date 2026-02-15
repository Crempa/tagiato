"""Generating photo thumbnails."""

import warnings
from pathlib import Path

from PIL import Image, ExifTags


class ThumbnailGenerator:
    """Generates photo thumbnails for Claude."""

    def __init__(self, output_dir: Path, size: int = 1024):
        """
        Args:
            output_dir: Directory for storing thumbnails
            size: Shorter side of the thumbnail in pixels
        """
        self.output_dir = output_dir
        self.size = size

    def generate(self, photo_path: Path) -> Path:
        """Generates a photo thumbnail.

        Args:
            photo_path: Path to the original photo

        Returns:
            Path to the thumbnail
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        thumbnail_path = self.output_dir / f"{photo_path.stem}_thumb.jpg"

        # Suppress warnings about corrupt EXIF data
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Corrupt EXIF data")
            img = Image.open(photo_path)

        with img:
            # Apply EXIF orientation
            img = self._apply_exif_orientation(img)

            # Calculate new size
            width, height = img.size
            if width < height:
                # Height is the longer side
                new_width = self.size
                new_height = int(height * (self.size / width))
            else:
                # Width is the longer side
                new_height = self.size
                new_width = int(width * (self.size / height))

            # Resize
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save as JPEG
            img.save(thumbnail_path, "JPEG", quality=85, optimize=True)

        return thumbnail_path

    def _apply_exif_orientation(self, img: Image.Image) -> Image.Image:
        """Applies EXIF orientation to the image."""
        try:
            exif = img._getexif()
            if exif is None:
                return img

            # Find the orientation tag
            orientation_key = None
            for key, value in ExifTags.TAGS.items():
                if value == "Orientation":
                    orientation_key = key
                    break

            if orientation_key is None or orientation_key not in exif:
                return img

            orientation = exif[orientation_key]

            # Apply transformation based on orientation
            if orientation == 2:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                img = img.rotate(180)
            elif orientation == 4:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(270)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 7:
                img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(90)
            elif orientation == 8:
                img = img.rotate(90, expand=True)

        except (AttributeError, KeyError, IndexError):
            pass

        return img
