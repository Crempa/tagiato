# Tagiato

A tool for automatically adding GPS coordinates and AI-generated descriptions to JPEG photos exported from Luminar.

## Installation

```bash
pipx install tagiato
```

## Usage

```bash
# Start the web interface for a photos directory
tagiato ~/Photos/Trip

# With GPS data from Google Timeline
tagiato ~/Photos/Trip --timeline location-history.json

# With a custom port and without automatically opening the browser
tagiato ~/Photos/Trip --port 3000 --no-browser

# Choose AI provider and model
tagiato ~/Photos/Trip --describe-provider gemini --describe-model flash
```

## Web Interface

After launching, a browser opens with a photo gallery where you can:

- Browse and filter photos
- Generate AI descriptions individually or in batch
- Locate photos using AI (place detection from photo)
- Edit GPS coordinates and descriptions
- Assign GPS from Google Timeline based on timestamps
- Save metadata back to EXIF

## Requirements

- Python 3.10+
- [Claude CLI](https://github.com/anthropics/claude-cli), [Gemini CLI](https://github.com/google-gemini/gemini-cli), or [OpenAI Codex CLI](https://github.com/openai/codex) installed and in PATH
- Google Timeline JSON export (optional, for GPS matching)

## License

MIT
