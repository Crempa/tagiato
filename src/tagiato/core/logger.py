"""Verbose logger pro Tagiato."""

from typing import Any, Optional
from rich.console import Console

# Globální instance
_console = Console()
_verbose = False


def set_verbose(enabled: bool) -> None:
    """Nastaví verbose mode."""
    global _verbose
    _verbose = enabled


def is_verbose() -> bool:
    """Vrátí, zda je verbose mode zapnutý."""
    return _verbose


def log_call(service: str, method: str, **kwargs: Any) -> None:
    """Zaloguje volání služby s parametry.

    Args:
        service: Název služby (např. "Geocoder")
        method: Název metody (např. "geocode")
        **kwargs: Parametry volání
    """
    if not _verbose:
        return

    # Formátovat parametry
    params = []
    for key, value in kwargs.items():
        if value is None:
            continue
        # Zkrátit dlouhé hodnoty
        str_value = str(value)
        if len(str_value) > 50:
            str_value = str_value[:47] + "..."
        params.append(f"{key}={str_value}")

    params_str = ", ".join(params) if params else ""
    _console.print(f"  [dim]→ {service}.{method}({params_str})[/dim]")


def log_result(service: str, method: str, result: Any) -> None:
    """Zaloguje výsledek volání služby.

    Args:
        service: Název služby
        method: Název metody
        result: Výsledek volání
    """
    if not _verbose:
        return

    # Zkrátit dlouhé výsledky
    str_result = str(result)
    if len(str_result) > 80:
        str_result = str_result[:77] + "..."

    _console.print(f"  [dim]← {service}.{method} = {str_result}[/dim]")


def log_info(message: str) -> None:
    """Zaloguje informační zprávu v verbose mode."""
    if not _verbose:
        return

    _console.print(f"  [dim]{message}[/dim]")
