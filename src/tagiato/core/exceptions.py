"""Custom exceptions for Tagiato."""


class TagiatoError(Exception):
    """Base exception for Tagiato."""

    pass


class ClaudeNotFoundError(TagiatoError):
    """Claude CLI is not available."""

    def __init__(self) -> None:
        super().__init__(
            "Claude CLI is not installed or not in PATH. "
            "Install it using: npm install -g @anthropic-ai/claude-cli"
        )


class TimelineParseError(TagiatoError):
    """Error parsing Timeline JSON."""

    pass


class ExifError(TagiatoError):
    """Error working with EXIF data."""

    pass


class GeocodingError(TagiatoError):
    """Error during geocoding."""

    pass
