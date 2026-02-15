"""Verbose logger for Tagiato."""

from typing import Any, Optional
from rich.console import Console

# Global instance
_console = Console()
_verbose = False
_web_mode = False


def set_verbose(enabled: bool) -> None:
    """Set verbose mode."""
    global _verbose
    _verbose = enabled


def is_verbose() -> bool:
    """Return whether verbose mode is enabled."""
    return _verbose


def set_web_mode(enabled: bool) -> None:
    """Set web mode - logs to web buffer."""
    global _web_mode
    _web_mode = enabled


def _web_log(level: str, message: str, data: Optional[dict] = None) -> None:
    """Log to web buffer if web mode is active."""
    if not _web_mode:
        return
    try:
        from tagiato.web.state import log_buffer
        log_buffer.add(level, message, data)
    except ImportError:
        pass


def log_call(service: str, method: str, **kwargs: Any) -> None:
    """Log a service call with parameters.

    Args:
        service: Service name (e.g. "Geocoder")
        method: Method name (e.g. "geocode")
        **kwargs: Call parameters
    """
    # Format parameters
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

    # Web log - always
    _web_log("call", message, {"service": service, "method": method, "params": kwargs})

    # Console log - verbose only
    if _verbose:
        _console.print(f"  [dim]{message}[/dim]")


def log_result(service: str, method: str, result: Any) -> None:
    """Log a service call result.

    Args:
        service: Service name
        method: Method name
        result: Call result
    """
    str_result = str(result)
    if len(str_result) > 80:
        str_result = str_result[:77] + "..."

    message = f"← {service}.{method} = {str_result}"

    # Web log - always
    _web_log("result", message, {"service": service, "method": method, "result": str(result)})

    # Console log - verbose only
    if _verbose:
        _console.print(f"  [dim]{message}[/dim]")


def log_info(message: str) -> None:
    """Log an informational message."""
    # Web log - always
    _web_log("info", message)

    # Console log - verbose only
    if _verbose:
        _console.print(f"  [dim]{message}[/dim]")


def log_warning(message: str) -> None:
    """Log a warning message."""
    # Web log - always
    _web_log("warning", message)

    # Console log - always (warnings are important)
    _console.print(f"  [yellow]⚠ {message}[/yellow]")


def log_prompt(prompt: str) -> None:
    """Log the full prompt to web buffer."""
    _web_log("prompt", "AI Prompt", {"prompt": prompt})


def log_response(response: str) -> None:
    """Log the full AI response to web buffer."""
    _web_log("response", "AI Response", {"response": response})
