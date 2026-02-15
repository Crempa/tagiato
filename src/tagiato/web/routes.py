"""API endpoints for web UI."""

import asyncio
from pathlib import Path
from typing import Optional
import threading

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from tagiato.models.location import GPSCoordinates
from tagiato.services.ai_provider import get_provider, get_available_providers, DESCRIBE_PROMPT_TEMPLATE, LOCATE_PROMPT_TEMPLATE
from tagiato.services.thumbnail import ThumbnailGenerator
from tagiato.services.exif_writer import ExifWriter
from tagiato.core.exceptions import ExifError
from tagiato.web.state import app_state, ProcessingStatus, TaskStatus, log_buffer

import requests

router = APIRouter()


class GPSInput(BaseModel):
    """GPS coordinates input."""
    lat: float
    lng: float


class PhotoUpdate(BaseModel):
    """Update photo data."""
    gps: Optional[GPSInput] = None
    description: Optional[str] = None
    location_name: Optional[str] = None


class BatchRequest(BaseModel):
    """Batch processing request."""
    photos: Optional[list[str]] = None  # None = all photos
    operation: str = "describe"  # "describe" or "locate"


class ProviderSettings(BaseModel):
    """AI provider settings."""
    describe_provider: Optional[str] = None
    describe_model: Optional[str] = None
    locate_provider: Optional[str] = None
    locate_model: Optional[str] = None


class PromptsUpdate(BaseModel):
    """Update prompts for current session."""
    describe_prompt: Optional[str] = None
    locate_prompt: Optional[str] = None


class ContextSettings(BaseModel):
    """Context settings for nearby descriptions."""
    enabled: bool = True
    radius_km: float = 5.0
    max_count: int = 5


class PresetCreate(BaseModel):
    """Create a new preset."""
    key: str
    name: str
    describe_prompt: str
    locate_prompt: str


class PresetRename(BaseModel):
    """Rename preset."""
    name: str


# --- Provider settings endpoints ---

@router.get("/api/settings/providers")
async def get_provider_settings():
    """Get current AI provider settings."""
    return {
        "describe_provider": app_state.describe_provider,
        "describe_model": app_state.describe_model,
        "locate_provider": app_state.locate_provider,
        "locate_model": app_state.locate_model,
        "available_providers": get_available_providers(),
    }


@router.put("/api/settings/providers")
async def update_provider_settings(settings: ProviderSettings):
    """Update AI provider settings."""
    if settings.describe_provider is not None:
        if settings.describe_provider not in ("claude", "gemini", "openai"):
            raise HTTPException(status_code=400, detail="Invalid describe provider")
        app_state.describe_provider = settings.describe_provider

    if settings.describe_model is not None:
        app_state.describe_model = settings.describe_model

    if settings.locate_provider is not None:
        if settings.locate_provider not in ("claude", "gemini", "openai"):
            raise HTTPException(status_code=400, detail="Invalid locate provider")
        app_state.locate_provider = settings.locate_provider

    if settings.locate_model is not None:
        app_state.locate_model = settings.locate_model

    return {
        "success": True,
        "describe_provider": app_state.describe_provider,
        "describe_model": app_state.describe_model,
        "locate_provider": app_state.locate_provider,
        "locate_model": app_state.locate_model,
    }


# --- Photo endpoints ---

@router.get("/api/photos")
async def list_photos(
    filter: str = Query("all", pattern="^(all|with_description|without_description)$"),
    sort: str = Query("date", pattern="^(date|name)$"),
):
    """Get list of all photos."""
    photos = app_state.get_photos_dict()

    # Filter
    if filter == "with_description":
        photos = [p for p in photos if p["description"]]
    elif filter == "without_description":
        photos = [p for p in photos if not p["description"]]

    # Sort
    if sort == "name":
        photos.sort(key=lambda p: p["filename"])
    # date sorting is default from app_state

    return {"photos": photos}


@router.get("/api/photos/{filename}/thumbnail")
async def get_thumbnail(filename: str):
    """Get thumbnail image for photo."""
    photo = app_state.get_photo(filename)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    if not photo.thumbnail_path or not photo.thumbnail_path.exists():
        # Generate thumbnail on-the-fly
        if app_state.thumbnails_dir and photo.path.exists():
            generator = ThumbnailGenerator(app_state.thumbnails_dir)
            try:
                photo.thumbnail_path = generator.generate(photo.path)
                app_state.update_photo(filename, thumbnail_path=photo.thumbnail_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {e}")

    if photo.thumbnail_path and photo.thumbnail_path.exists():
        return FileResponse(
            photo.thumbnail_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )

    raise HTTPException(status_code=404, detail="Thumbnail not available")


async def _run_describe_task(task_id: str, filename: str, user_hint: str):
    """Background worker for generating description."""
    photo = app_state.get_photo(filename)
    if not photo:
        app_state.update_task(task_id, status=TaskStatus.ERROR, error="Photo not found")
        return

    app_state.update_task(task_id, status=TaskStatus.RUNNING)
    app_state.update_photo(filename, ai_status=ProcessingStatus.PROCESSING)

    try:
        # Ensure thumbnail exists
        if not photo.thumbnail_path or not photo.thumbnail_path.exists():
            if app_state.thumbnails_dir:
                generator = ThumbnailGenerator(app_state.thumbnails_dir)
                photo.thumbnail_path = generator.generate(photo.path)

        if not photo.thumbnail_path:
            raise Exception("Cannot generate thumbnail")

        provider = get_provider(app_state.describe_provider, app_state.describe_model)

        # Get nearby descriptions context
        nearby = app_state.get_nearby_descriptions(filename)
        nearby_descriptions = [desc for _, desc, _ in nearby]

        # Include own description if exists (for regeneration)
        if photo.description:
            nearby_descriptions.insert(0, photo.description)

        # Log used context
        if nearby_descriptions:
            if photo.description:
                context_info = f"own description + " if nearby else "own description"
                if nearby:
                    context_info += ", ".join(f"{fn} ({d:.1f}km)" for fn, _, d in nearby)
            else:
                context_info = ", ".join(f"{fn} ({d:.1f}km)" for fn, _, d in nearby)
            log_buffer.add("info", f"Nearby context: {context_info}")

        # Run blocking AI call in thread pool
        result = await asyncio.to_thread(
            provider.describe,
            thumbnail_path=photo.thumbnail_path,
            place_name=None,
            coords=photo.gps,
            timestamp=photo.timestamp.isoformat() if photo.timestamp else None,
            custom_prompt=app_state.describe_prompt,
            location_name=photo.location_name or None,
            user_hint=user_hint,
            nearby_descriptions=nearby_descriptions if nearby_descriptions else None,
        )

        if result.description:
            app_state.update_photo(
                filename,
                description=result.description,
                ai_status=ProcessingStatus.DONE,
                ai_error=None,
                ai_empty_response=False,
                is_dirty=True,
            )
            app_state.update_task(
                task_id,
                status=TaskStatus.DONE,
                result={"success": True, "description": result.description}
            )
        else:
            app_state.update_photo(
                filename,
                ai_status=ProcessingStatus.DONE,
                ai_empty_response=True,
            )
            app_state.update_task(
                task_id,
                status=TaskStatus.DONE,
                result={"success": True, "description": "", "empty": True}
            )

    except Exception as e:
        app_state.update_photo(
            filename,
            ai_status=ProcessingStatus.ERROR,
            ai_error=str(e),
        )
        app_state.update_task(task_id, status=TaskStatus.ERROR, error=str(e))


@router.post("/api/photos/{filename}/generate")
async def generate_description(filename: str, request: Request):
    """Generate AI description for a photo (async)."""
    photo = app_state.get_photo(filename)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Parse optional user_hint from request body
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    user_hint = body.get("user_hint", "")

    # Create task and start background processing
    task = app_state.create_task(filename, "describe")
    asyncio.create_task(_run_describe_task(task.task_id, filename, user_hint))

    return {"task_id": task.task_id, "status": "started"}


async def _run_locate_task(task_id: str, filename: str, user_hint: str):
    """Background worker for localization."""
    photo = app_state.get_photo(filename)
    if not photo:
        app_state.update_task(task_id, status=TaskStatus.ERROR, error="Photo not found")
        return

    app_state.update_task(task_id, status=TaskStatus.RUNNING)
    app_state.update_photo(filename, locate_status=ProcessingStatus.PROCESSING)

    try:
        # Ensure thumbnail exists
        if not photo.thumbnail_path or not photo.thumbnail_path.exists():
            if app_state.thumbnails_dir:
                generator = ThumbnailGenerator(app_state.thumbnails_dir)
                photo.thumbnail_path = generator.generate(photo.path)

        if not photo.thumbnail_path:
            raise Exception("Cannot generate thumbnail")

        provider = get_provider(app_state.locate_provider, app_state.locate_model)

        # Run blocking AI call in thread pool
        result = await asyncio.to_thread(
            provider.locate,
            thumbnail_path=photo.thumbnail_path,
            timestamp=photo.timestamp.isoformat() if photo.timestamp else None,
            custom_prompt=app_state.locate_prompt,
            user_hint=user_hint,
        )

        if result.gps:
            app_state.update_photo(
                filename,
                gps=result.gps,
                gps_source="ai",
                locate_status=ProcessingStatus.DONE,
                locate_error=None,
                locate_confidence=result.confidence,
                location_name=result.location_name,
                is_dirty=True,
            )
            app_state.update_task(
                task_id,
                status=TaskStatus.DONE,
                result={
                    "success": True,
                    "gps": {"lat": result.gps.latitude, "lng": result.gps.longitude},
                    "confidence": result.confidence,
                    "location_name": result.location_name,
                    "reasoning": result.reasoning,
                }
            )
        else:
            # Even without GPS we may have location_name
            app_state.update_photo(
                filename,
                locate_status=ProcessingStatus.DONE,
                locate_confidence=result.confidence,
                location_name=result.location_name,
            )
            app_state.update_task(
                task_id,
                status=TaskStatus.DONE,
                result={
                    "success": True,
                    "gps": None,
                    "confidence": result.confidence,
                    "location_name": result.location_name,
                    "reasoning": result.reasoning,
                }
            )

    except Exception as e:
        app_state.update_photo(
            filename,
            locate_status=ProcessingStatus.ERROR,
            locate_error=str(e),
        )
        app_state.update_task(task_id, status=TaskStatus.ERROR, error=str(e))


@router.post("/api/photos/{filename}/locate")
async def locate_photo(filename: str, request: Request):
    """Use AI to determine precise GPS location of a photo (async)."""
    photo = app_state.get_photo(filename)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Parse optional user_hint from request body
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    user_hint = body.get("user_hint", "")

    # Create task and start background processing
    task = app_state.create_task(filename, "locate")
    asyncio.create_task(_run_locate_task(task.task_id, filename, user_hint))

    return {"task_id": task.task_id, "status": "started"}


@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of an AI task."""
    task = app_state.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.post("/api/photos/{filename}/prompt-preview")
async def get_prompt_preview(filename: str, request: Request):
    """Get the actual prompt that would be sent to AI (with all placeholders filled)."""
    photo = app_state.get_photo(filename)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    prompt_type = body.get("type", "describe")  # "describe" or "locate"
    user_hint = body.get("user_hint", "")
    include_image = body.get("include_image", True)  # Default to include image

    # Build image line based on include_image flag
    if include_image:
        thumbnail_path = str(photo.thumbnail_path.absolute()) if photo.thumbnail_path else "[thumbnail not available]"
        image_line = f"- Analyze this image: {thumbnail_path}\n"
    else:
        image_line = ""

    # Build context for describe prompt
    if prompt_type == "describe":
        context_lines = []
        if photo.gps:
            context_lines.append(f"- GPS: {photo.gps.latitude:.6f}, {photo.gps.longitude:.6f}")
        if photo.location_name:
            context_lines.append(f"- Located place: {photo.location_name}")
        if photo.timestamp:
            context_lines.append(f"- Date: {photo.timestamp.strftime('%d. %m. %Y %H:%M')}")

        user_hint_line = f"- User adds: {user_hint}" if user_hint.strip() else ""

        # Get nearby descriptions context for preview
        nearby = app_state.get_nearby_descriptions(filename)
        nearby_descriptions = [desc for _, desc, _ in nearby]

        # Include own description if exists (for regeneration)
        if photo.description:
            nearby_descriptions.insert(0, photo.description)

        if nearby_descriptions:
            descriptions_text = "\n".join(f"- {desc}" for desc in nearby_descriptions)
            nearby_line = f"""EXISTING DESCRIPTIONS FROM NEARBY:
{descriptions_text}

IMPORTANT: NEVER repeat information from the descriptions above!
Choose a DIFFERENT interesting fact about the given place.
"""
        else:
            nearby_line = ""

        template = app_state.describe_prompt or DESCRIBE_PROMPT_TEMPLATE

        prompt = template.format(
            image_line=image_line,
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
            nearby_descriptions_line=nearby_line,
        )
    else:
        # Locate prompt
        user_hint_line = f"- User adds: {user_hint}" if user_hint.strip() else ""

        template = app_state.locate_prompt or LOCATE_PROMPT_TEMPLATE

        prompt = template.format(
            image_line=image_line,
            timestamp=photo.timestamp.strftime("%d. %m. %Y %H:%M") if photo.timestamp else "unknown",
            user_hint_line=user_hint_line,
        )

    return {"prompt": prompt, "type": prompt_type}


@router.put("/api/photos/{filename}")
async def update_photo(filename: str, data: PhotoUpdate):
    """Update photo data and save to EXIF."""
    photo = app_state.get_photo(filename)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Update GPS if provided
    if data.gps:
        new_gps = GPSCoordinates(latitude=data.gps.lat, longitude=data.gps.lng)
        app_state.update_photo(filename, gps=new_gps, gps_source="manual", is_dirty=True)

    # Update description if provided
    if data.description is not None:
        app_state.update_photo(filename, description=data.description, is_dirty=True)

    # Update location_name if provided
    if data.location_name is not None:
        app_state.update_photo(filename, location_name=data.location_name, is_dirty=True)

    # Get updated photo
    photo = app_state.get_photo(filename)

    # Write to EXIF
    try:
        exif_writer = ExifWriter()
        exif_writer.write(
            photo_path=photo.path,
            gps=photo.gps,
            description=photo.description if photo.description else None,
            location_name=photo.location_name if photo.location_name else None,
            skip_existing_gps=False,  # Always overwrite in serve mode
        )

        app_state.update_photo(filename, is_dirty=False)
        return {"success": True, "message": "Saved to EXIF"}

    except ExifError as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Batch processing endpoints ---

def _run_batch_processing():
    """Background worker for batch processing."""
    while True:
        with app_state.lock:
            if app_state.batch.should_stop or not app_state.batch.queue:
                app_state.batch.is_running = False
                app_state.batch.should_stop = False
                app_state.batch.current_photo = None
                return

            filename = app_state.batch.queue.pop(0)
            app_state.batch.current_photo = filename
            operation = app_state.batch.operation

        photo = app_state.get_photo(filename)
        if not photo:
            continue

        # Check for stop signal
        if app_state.batch.should_stop:
            continue

        try:
            # Ensure thumbnail
            if not photo.thumbnail_path or not photo.thumbnail_path.exists():
                if app_state.thumbnails_dir:
                    generator = ThumbnailGenerator(app_state.thumbnails_dir)
                    photo.thumbnail_path = generator.generate(photo.path)
                    app_state.update_photo(filename, thumbnail_path=photo.thumbnail_path)

            if photo.thumbnail_path:
                if operation == "locate":
                    # Batch locate
                    provider = get_provider(app_state.locate_provider, app_state.locate_model)
                    app_state.update_photo(filename, locate_status=ProcessingStatus.PROCESSING)
                    result = provider.locate(
                        thumbnail_path=photo.thumbnail_path,
                        timestamp=photo.timestamp.isoformat() if photo.timestamp else None,
                        custom_prompt=app_state.locate_prompt,
                    )

                    if result.gps:
                        app_state.update_photo(
                            filename,
                            gps=result.gps,
                            gps_source="ai",
                            locate_status=ProcessingStatus.DONE,
                            locate_confidence=result.confidence,
                            location_name=result.location_name,
                            is_dirty=True,
                        )
                    else:
                        # Even without GPS we may have location_name
                        app_state.update_photo(
                            filename,
                            locate_status=ProcessingStatus.DONE,
                            locate_confidence=result.confidence,
                            location_name=result.location_name,
                        )

                else:
                    # Batch describe (default)
                    if not photo.description and photo.ai_status != ProcessingStatus.DONE:
                        provider = get_provider(app_state.describe_provider, app_state.describe_model)
                        app_state.update_photo(filename, ai_status=ProcessingStatus.PROCESSING)

                        # Get nearby descriptions context (updated for each photo in batch)
                        nearby = app_state.get_nearby_descriptions(filename)
                        nearby_descriptions = [desc for _, desc, _ in nearby]

                        # Include own description if exists (for regeneration)
                        if photo.description:
                            nearby_descriptions.insert(0, photo.description)

                        # Log used context
                        if nearby_descriptions:
                            if photo.description:
                                context_info = f"own description"
                                if nearby:
                                    context_info += " + " + ", ".join(f"{fn} ({d:.1f}km)" for fn, _, d in nearby)
                            else:
                                context_info = ", ".join(f"{fn} ({d:.1f}km)" for fn, _, d in nearby)
                            log_buffer.add("info", f"[{filename}] Nearby context: {context_info}")

                        result = provider.describe(
                            thumbnail_path=photo.thumbnail_path,
                            place_name=None,
                            coords=photo.gps,
                            timestamp=photo.timestamp.isoformat() if photo.timestamp else None,
                            custom_prompt=app_state.describe_prompt,
                            location_name=photo.location_name or None,
                            nearby_descriptions=nearby_descriptions if nearby_descriptions else None,
                        )

                        if result.description:
                            app_state.update_photo(
                                filename,
                                description=result.description,
                                ai_status=ProcessingStatus.DONE,
                                is_dirty=True,
                            )
                        else:
                            app_state.update_photo(
                                filename,
                                ai_status=ProcessingStatus.DONE,
                                ai_empty_response=True,
                            )

        except Exception as e:
            if operation == "locate":
                app_state.update_photo(
                    filename,
                    locate_status=ProcessingStatus.ERROR,
                    locate_error=str(e),
                )
            else:
                app_state.update_photo(
                    filename,
                    ai_status=ProcessingStatus.ERROR,
                    ai_error=str(e),
                )

        with app_state.lock:
            app_state.batch.completed.append(filename)


@router.post("/api/batch/start")
async def start_batch(request: BatchRequest):
    """Start batch processing."""
    if request.operation not in ("describe", "locate"):
        raise HTTPException(status_code=400, detail="Invalid operation")

    with app_state.lock:
        if app_state.batch.is_running:
            raise HTTPException(status_code=400, detail="Batch processing already running")

        # Determine which photos to process
        if request.photos:
            queue = [p for p in request.photos if p in app_state.photos]
        else:
            queue = list(app_state.photos_order)

        if not queue:
            raise HTTPException(status_code=400, detail="No photos to process")

        app_state.batch.queue = queue
        app_state.batch.completed = []
        app_state.batch.is_running = True
        app_state.batch.should_stop = False
        app_state.batch.operation = request.operation

    # Start background thread
    thread = threading.Thread(target=_run_batch_processing, daemon=True)
    thread.start()

    return {"success": True, "queue_count": len(queue), "operation": request.operation}


@router.post("/api/batch/stop")
async def stop_batch():
    """Stop batch processing after current photo."""
    with app_state.lock:
        if not app_state.batch.is_running:
            return {"success": True, "message": "Not running"}

        app_state.batch.should_stop = True
        return {"success": True, "message": "Stopping after current photo"}


@router.get("/api/batch/status")
async def batch_status():
    """Get batch processing status."""
    return app_state.batch.to_dict()


# --- Save all endpoint ---

@router.post("/api/photos/save-all")
async def save_all_photos(request: BatchRequest):
    """Save all (or selected) photos to EXIF."""
    # Determine which photos to save
    if request.photos:
        filenames = [p for p in request.photos if p in app_state.photos]
    else:
        filenames = list(app_state.photos_order)

    if not filenames:
        raise HTTPException(status_code=400, detail="No photos to save")

    writer = ExifWriter()
    saved = 0
    errors = []

    for filename in filenames:
        photo = app_state.get_photo(filename)
        if not photo:
            continue

        # Skip if nothing to save
        if not photo.gps and not photo.description:
            continue

        try:
            writer.write(
                photo_path=photo.path,
                gps=photo.gps,
                description=photo.description if photo.description else None,
                skip_existing_gps=False,
            )
            app_state.update_photo(filename, is_dirty=False)
            saved += 1
        except ExifError as e:
            errors.append(f"{filename}: {str(e)}")

    return {
        "success": True,
        "saved": saved,
        "total": len(filenames),
        "errors": errors if errors else None,
    }


# --- Geocode search proxy ---

# --- Prompts settings endpoints ---

@router.get("/api/settings/prompts")
async def get_prompts_settings():
    """Get current prompts settings."""
    return {
        "describe_prompt": app_state.describe_prompt,
        "locate_prompt": app_state.locate_prompt,
        "active_preset": app_state.active_preset,
        "active_preset_name": app_state.presets[app_state.active_preset]["name"] if app_state.active_preset and app_state.active_preset in app_state.presets else None,
        "default_describe_prompt": DESCRIBE_PROMPT_TEMPLATE,
        "default_locate_prompt": LOCATE_PROMPT_TEMPLATE,
    }


@router.put("/api/settings/prompts")
async def update_prompts_settings(prompts: PromptsUpdate):
    """Update prompts for current session (without saving to preset)."""
    if prompts.describe_prompt is not None:
        app_state.describe_prompt = prompts.describe_prompt if prompts.describe_prompt else None
    if prompts.locate_prompt is not None:
        app_state.locate_prompt = prompts.locate_prompt if prompts.locate_prompt else None

    return {
        "success": True,
        "describe_prompt": app_state.describe_prompt,
        "locate_prompt": app_state.locate_prompt,
    }


@router.get("/api/settings/presets")
async def get_presets():
    """Get all presets."""
    return {
        "presets": app_state.presets,
        "active_preset": app_state.active_preset,
    }


@router.post("/api/settings/presets")
async def create_preset(preset: PresetCreate):
    """Create a new preset and activate it."""
    if not preset.key or not preset.name:
        raise HTTPException(status_code=400, detail="Key and name are required")

    app_state.create_preset(
        key=preset.key,
        name=preset.name,
        describe_prompt=preset.describe_prompt,
        locate_prompt=preset.locate_prompt,
    )

    return {
        "success": True,
        "key": preset.key,
        "active_preset": app_state.active_preset,
    }


@router.put("/api/settings/presets/{key}")
async def rename_preset(key: str, data: PresetRename):
    """Rename a preset."""
    if key not in app_state.presets:
        raise HTTPException(status_code=404, detail="Preset not found")

    app_state.presets[key]["name"] = data.name
    app_state.save_presets()

    return {"success": True}


@router.delete("/api/settings/presets/{key}")
async def delete_preset(key: str):
    """Delete a preset."""
    if not app_state.delete_preset(key):
        raise HTTPException(status_code=404, detail="Preset not found")

    return {
        "success": True,
        "active_preset": app_state.active_preset,
    }


@router.post("/api/settings/presets/{key}/activate")
async def activate_preset(key: str):
    """Activate a preset."""
    if not app_state.activate_preset(key):
        raise HTTPException(status_code=404, detail="Preset not found")

    return {
        "success": True,
        "describe_prompt": app_state.describe_prompt,
        "locate_prompt": app_state.locate_prompt,
    }


# --- Context settings endpoints ---

@router.get("/api/settings/context")
async def get_context_settings():
    """Get context settings for nearby descriptions."""
    return {
        "enabled": app_state.context_enabled,
        "radius_km": app_state.context_radius_km,
        "max_count": app_state.context_max_count,
    }


@router.put("/api/settings/context")
async def update_context_settings(data: ContextSettings):
    """Update context settings for nearby descriptions."""
    # Validate radius
    if data.radius_km < 0.5 or data.radius_km > 20:
        raise HTTPException(status_code=400, detail="Radius must be between 0.5 and 20 km")

    # Validate max_count
    if data.max_count < 1 or data.max_count > 10:
        raise HTTPException(status_code=400, detail="Max count must be between 1 and 10")

    app_state.context_enabled = data.enabled
    app_state.context_radius_km = data.radius_km
    app_state.context_max_count = data.max_count
    app_state.save_settings()

    return {
        "success": True,
        "enabled": app_state.context_enabled,
        "radius_km": app_state.context_radius_km,
        "max_count": app_state.context_max_count,
    }


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Tagiato/0.1.0 (https://github.com/pavelmica/tagiato)"


@router.get("/api/geocode/search")
async def geocode_search(q: str = Query(..., min_length=2)):
    """Nominatim search autocomplete proxy."""
    try:
        response = requests.get(
            NOMINATIM_SEARCH_URL,
            params={
                "q": q,
                "format": "json",
                "addressdetails": 1,
                "limit": 5,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()

        results = []
        for item in response.json():
            results.append({
                "display_name": item.get("display_name", ""),
                "lat": float(item.get("lat", 0)),
                "lng": float(item.get("lon", 0)),
            })

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Logs endpoints ---

import json

@router.get("/api/logs")
async def get_logs():
    """Get all log entries."""
    return {"logs": log_buffer.get_all()}


@router.delete("/api/logs")
async def clear_logs():
    """Clear log buffer."""
    log_buffer.clear()
    return {"success": True}


@router.get("/api/logs/stream")
async def stream_logs():
    """SSE stream of log entries."""
    async def event_generator():
        q = log_buffer.subscribe()
        try:
            # First send existing logs
            for entry in log_buffer.get_all():
                yield f"data: {json.dumps(entry)}\n\n"

            # Then stream new ones
            while True:
                try:
                    # Wait for new log entry (with timeout for keep-alive)
                    entry = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=30)
                    )
                    yield f"data: {json.dumps(entry)}\n\n"
                except Exception:
                    # Timeout - send keep-alive
                    yield ": keep-alive\n\n"
        finally:
            log_buffer.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
