"""Verbose logger pro Tagiato."""

from typing import Any, Optional
from rich.console import Console

# Globální instance
_console = Console()
_verbose = False
_web_mode = False


def set_verbose(enabled: bool) -> None:
    """Nastaví verbose mode."""
    global _verbose
    _verbose = enabled


def is_verbose() -> bool:
    """Vrátí, zda je verbose mode zapnutý."""
    return _verbose


def set_web_mode(enabled: bool) -> None:
    """Nastaví web mode - loguje do web bufferu."""
    global _web_mode
    _web_mode = enabled


def _web_log(level: str, message: str, data: Optional[dict] = None) -> None:
    """Zaloguje do web bufferu pokud je web mode aktivní."""
    if not _web_mode:
        return
    try:
        from tagiato.web.state import log_buffer
        log_buffer.add(level, message, data)
    except ImportError:
        pass


def log_call(service: str, method: str, **kwargs: Any) -> None:
    """Zaloguje volání služby s parametry.

    Args:
        service: Název služby (např. "Geocoder")
        method: Název metody (např. "geocode")
        **kwargs: Parametry volání
    """
    # Formátovat parametry
    params = []
    for key, value in kwargs.items():
        if value is None:
            continue
        str_value = str(value)
        if len(str_value) > 50:
            str_value = str_value[:47] + "..."
        params.append(f"{key}={str_value}")

    params_str = ", ".join(params) if params else ""
    message = f"→ {service}.{method}({params_str})"

    # Web log - vždy
    _web_log("call", message, {"service": service, "method": method, "params": kwargs})

    # Console log - pouze verbose
    if _verbose:
        _console.print(f"  [dim]{message}[/dim]")


def log_result(service: str, method: str, result: Any) -> None:
    """Zaloguje výsledek volání služby.

    Args:
        service: Název služby
        method: Název metody
        result: Výsledek volání
    """
    str_result = str(result)
    if len(str_result) > 80:
        str_result = str_result[:77] + "..."

    message = f"← {service}.{method} = {str_result}"

    # Web log - vždy
    _web_log("result", message, {"service": service, "method": method, "result": str(result)})

    # Console log - pouze verbose
    if _verbose:
        _console.print(f"  [dim]{message}[/dim]")


def log_info(message: str) -> None:
    """Zaloguje informační zprávu."""
    # Web log - vždy
    _web_log("info", message)

    # Console log - pouze verbose
    if _verbose:
        _console.print(f"  [dim]{message}[/dim]")


def log_warning(message: str) -> None:
    """Zaloguje varovnou zprávu."""
    # Web log - vždy
    _web_log("warning", message)

    # Console log - vždy (varování jsou důležitá)
    _console.print(f"  [yellow]⚠ {message}[/yellow]")


def log_prompt(prompt: str) -> None:
    """Zaloguje celý prompt do web bufferu."""
    _web_log("prompt", "AI Prompt", {"prompt": prompt})


def log_response(response: str) -> None:
    """Zaloguje celou odpověď od AI do web bufferu."""
    _web_log("response", "AI Response", {"response": response})
