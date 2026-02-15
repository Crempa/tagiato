# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install globally via pipx
make install

# Set up development environment (creates .venv)
make dev

# Run tests (requires make dev first)
make test

# Run specific test file
. .venv/bin/activate && pytest tests/test_models.py -v

# Clean build artifacts
make clean
```

## Architecture Overview

Tagiato is a web-based tool for enriching JPEG photos with GPS coordinates and AI-generated descriptions. It is launched via `tagiato <photos_dir>` which starts a FastAPI web server.

### Core Components

**CLI Entry Point** (`cli/main.py`) - Typer-based launcher that starts the web server with configurable options (provider, model, port, timeline).

**Web Interface** (`web/`) - FastAPI application:
- `app.py` - App factory, creates FastAPI app with configuration
- `routes.py` - All API endpoints (photo management, AI operations, batch processing, settings)
- `state.py` - In-memory state management for the web session

**AI Provider Abstraction** (`services/ai_provider.py`) - Supports three providers:
- Claude: `claude --dangerously-skip-permissions --model X --print`
- Gemini: `gemini --yolo --model X --output-format text`
- OpenAI: `codex exec --model X --image Y --full-auto`

Each provider can be configured separately for describe vs locate operations.

### Data Flow

```
Photo Directory
     ↓
PhotoScanner (EXIF extraction)
     ↓
TimelineLoader + LocationMatcher (GPS from timeline)
     ↓
ThumbnailGenerator (resize for AI)
     ↓
AIProvider.describe() → JSON {description, refined_gps}
     ↓
ExifWriter / XmpWriter (persist to files)
```

### State Management

- Working directory: `.tagiato/` inside photos folder
- State file: `.tagiato/state.json` - tracks processed photos for resumability
- Geocode cache: `.tagiato/geocode_cache.json` - avoids repeated API calls

### GPS Priority Order

1. `refined_gps` - AI-detected landmark coordinates
2. `matched_location` - Timeline GPS matched by timestamp
3. `original_gps` - Original EXIF GPS from camera

### Web Interface

`tagiato <photos_dir>` starts FastAPI server with:
- Photo gallery with thumbnails
- Per-photo AI describe/locate buttons
- Batch processing with progress tracking
- Provider/model settings modal
- Real-time log panel via SSE

## Key Patterns

- **Prompt templates** in `ai_provider.py` expect JSON response with optional markdown code blocks
- **JSON parsing** handles ````json` blocks, raw JSON, or JSON embedded in text
- **Subprocess timeouts** of 120s for all AI CLI calls

## Development Guidelines

- **Versioning**: Update `VERSION` file with each change following SemVer:
  - MAJOR: breaking changes (incompatible API changes)
  - MINOR: new functionality (backwards compatible)
  - PATCH: bug fixes, minor adjustments
- **Commits**: Never create git commits - the user handles this themselves
