"""Tagiato - CLI nástroj pro obohacení fotografií GPS souřadnicemi a AI popisky."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("tagiato")
except PackageNotFoundError:
    # Fallback for development without installation
    __version__ = "0.0.0-dev"

__author__ = "Pavel Mica"
