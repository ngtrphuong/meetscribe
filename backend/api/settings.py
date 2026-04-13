"""Settings API — read and update runtime configuration.

GET /api/settings    → current settings
PUT /api/settings    → update settings

File: backend/api/settings.py
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.config import settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    asr_live_engine: Optional[str] = None
    asr_post_engine: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    default_language: Optional[str] = None
    vibevoice_quantization: Optional[str] = None
    ollama_base_url: Optional[str] = None
    silence_timeout: Optional[int] = None


@router.get("")
async def get_settings():
    """Return current application settings (non-sensitive fields only)."""
    return {
        "asr_live_engine": settings.asr_live_engine,
        "asr_post_engine": settings.asr_post_engine,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "default_language": settings.default_language,
        "vibevoice_quantization": settings.vibevoice_quantization,
        "ollama_base_url": settings.ollama_base_url,
        "env": settings.env,
        "data_dir": str(settings.data_dir),
        "models_dir": str(settings.models_dir),
        "audio_devices": await _list_devices(),
    }


@router.put("")
async def update_settings(update: SettingsUpdate):
    """Update runtime settings.

    Note: These updates are ephemeral (in-memory). For persistent changes,
    update the .env file and restart the server.
    """
    changed = {}
    for field, value in update.model_dump(exclude_none=True).items():
        if hasattr(settings, field):
            object.__setattr__(settings, field, value)
            changed[field] = value

    return {"updated": changed, "message": "Settings updated (restart to persist)"}


@router.get("/templates")
async def list_templates():
    """List available LLM summary templates."""
    from backend.llm.summarizer import MeetingSummarizer
    summarizer = MeetingSummarizer()
    return {"templates": summarizer.list_templates()}


@router.get("/audio/devices")
async def list_audio_devices():
    """List available audio input/output devices."""
    return {"devices": await _list_devices()}


async def _list_devices() -> list[dict]:
    try:
        from backend.audio.capture import list_audio_devices_async
        return await list_audio_devices_async()
    except Exception:
        return []
