"""Main CLI definition for Tagiato."""

import socket
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from tagiato import __version__

console = Console()


def version_callback(value: bool) -> None:
    if value:
        print(f"tagiato {__version__}")
        raise typer.Exit()


def _find_available_port(start_port: int, max_attempts: int = 10) -> Optional[int]:
    """Find an available port starting from start_port, trying up to max_attempts ports."""
    for offset in range(max_attempts):
        candidate = start_port + offset
        if candidate > 65535:
            break
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", candidate))
                return candidate
            except OSError:
                continue
    return None


def main(
    photos_dir: Path = typer.Argument(
        ...,
        help="Path to the photos directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    timeline: Optional[Path] = typer.Option(
        None,
        "--timeline",
        "-t",
        help="Path to Google Timeline JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    describe_provider: str = typer.Option(
        "claude",
        "--describe-provider",
        help="Provider for generating descriptions (claude/gemini/openai)",
    ),
    describe_model: str = typer.Option(
        "sonnet",
        "--describe-model",
        help="Model for descriptions (claude: sonnet/opus/haiku, gemini: flash/pro/ultra, openai: o3/o4-mini/gpt-5.2)",
    ),
    locate_provider: str = typer.Option(
        "claude",
        "--locate-provider",
        help="Provider for localization (claude/gemini/openai)",
    ),
    locate_model: str = typer.Option(
        "sonnet",
        "--locate-model",
        help="Model for localization (claude: sonnet/opus/haiku, gemini: flash/pro/ultra, openai: o3/o4-mini/gpt-5.2)",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port for the web server",
        min=1024,
        max=65535,
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Do not automatically open the browser",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show program version",
    ),
) -> None:
    """Start the web interface for interactive photo processing.

    Allows browsing photos, adding GPS coordinates, and generating AI descriptions
    with full control over the process.
    """
    try:
        import uvicorn
        from tagiato.web.app import create_app
        from tagiato.core.logger import set_web_mode
        from tagiato.services.exif_writer import is_exiftool_available
    except ImportError as e:
        console.print("[red]Error:[/red] Web dependencies are not installed.")
        console.print("Install them using: pip install tagiato[web]")
        raise typer.Exit(1)

    # Activate web logging
    set_web_mode(True)

    console.print(f"[blue]Tagiato Web UI[/blue]")
    console.print(f"  Directory: {photos_dir}")
    if timeline:
        console.print(f"  Timeline: {timeline}")
    console.print(f"  Descriptions: {describe_provider}/{describe_model}")
    console.print(f"  Localization: {locate_provider}/{locate_model}")
    console.print(f"  Port: {port}")

    # Check exiftool
    if not is_exiftool_available():
        console.print()
        console.print("[yellow]⚠ Warning:[/yellow] exiftool is not installed")
        console.print("  Writing location name (IPTC:Sub-location) will not be available.")
        console.print("  Install: brew install exiftool (macOS) or apt install libimage-exiftool-perl (Linux)")

    console.print()

    # Create FastAPI app
    fastapi_app = create_app(
        photos_dir=photos_dir,
        timeline_path=timeline,
        describe_provider=describe_provider,
        describe_model=describe_model,
        locate_provider=locate_provider,
        locate_model=locate_model,
    )

    # Find available port (try up to 10 ports starting from the requested one)
    actual_port = _find_available_port(port)
    if actual_port is None:
        console.print(f"[red]Error:[/red] Could not find an available port (tried {port}–{port + 9})")
        raise typer.Exit(1)

    if actual_port != port:
        console.print(f"[yellow]Port {port} is occupied, using {actual_port}[/yellow]")

    # Open browser
    url = f"http://localhost:{actual_port}"
    if not no_browser:
        console.print(f"[green]Opening browser:[/green] {url}")
        webbrowser.open(url)
    else:
        console.print(f"[green]Application running at:[/green] {url}")

    console.print()
    console.print("[dim]Ctrl+C to exit[/dim]")
    console.print()

    # Run server
    try:
        uvicorn.run(fastapi_app, host="0.0.0.0", port=actual_port, log_level="warning")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")


app = typer.Typer()
app.command()(main)


if __name__ == "__main__":
    app()
