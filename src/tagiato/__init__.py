"""Tagiato - CLI tool for enriching photos with GPS coordinates and AI descriptions."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("tagiato")
except PackageNotFoundError:
    # Fallback for development without installation
    __version__ = "0.0.0-dev"

__author__ = "Pavel Mica"
