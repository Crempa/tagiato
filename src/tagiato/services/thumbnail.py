"""Generování náhledů fotek."""

from pathlib import Path

from PIL import Image, ExifTags


class ThumbnailGenerator:
    """Generuje náhledy fotek pro Claude."""

    def __init__(self, output_dir: Path, size: int = 1024):
        """
        Args:
            output_dir: Složka pro ukládání náhledů
            size: Kratší strana náhledu v pixelech
        """
        self.output_dir = output_dir
        self.size = size

    def generate(self, photo_path: Path) -> Path:
        """Vygeneruje náhled fotky.

        Args:
            photo_path: Cesta k originální fotce

        Returns:
            Cesta k náhledu
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        thumbnail_path = self.output_dir / f"{photo_path.stem}_thumb.jpg"

        with Image.open(photo_path) as img:
            # Aplikovat EXIF orientaci
            img = self._apply_exif_orientation(img)

            # Vypočítat novou velikost
            width, height = img.size
            if width < height:
                # Výška je delší strana
                new_width = self.size
                new_height = int(height * (self.size / width))
            else:
                # Šířka je delší strana
                new_height = self.size
                new_width = int(width * (self.size / height))

            # Změnit velikost
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Uložit jako JPEG
            img.save(thumbnail_path, "JPEG", quality=85, optimize=True)

        return thumbnail_path

    def _apply_exif_orientation(self, img: Image.Image) -> Image.Image:
        """Aplikuje EXIF orientaci na obrázek."""
        try:
            exif = img._getexif()
            if exif is None:
                return img

            # Najít tag orientace
            orientation_key = None
            for key, value in ExifTags.TAGS.items():
                if value == "Orientation":
                    orientation_key = key
                    break

            if orientation_key is None or orientation_key not in exif:
                return img

            orientation = exif[orientation_key]

            # Aplikovat transformaci podle orientace
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
