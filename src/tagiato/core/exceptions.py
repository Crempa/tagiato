"""Vlastní výjimky pro Tagiato."""


class TagiatoError(Exception):
    """Základní výjimka pro Tagiato."""

    pass


class ClaudeNotFoundError(TagiatoError):
    """Claude CLI není dostupný."""

    def __init__(self) -> None:
        super().__init__(
            "Claude CLI není nainstalován nebo není v PATH. "
            "Nainstalujte ho pomocí: npm install -g @anthropic-ai/claude-cli"
        )


class TimelineParseError(TagiatoError):
    """Chyba při parsování Timeline JSON."""

    pass


class ExifError(TagiatoError):
    """Chyba při práci s EXIF daty."""

    pass


class GeocodingError(TagiatoError):
    """Chyba při geocodingu."""

    pass
