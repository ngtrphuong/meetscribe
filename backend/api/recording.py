"""Recording control REST API endpoints.

POST /api/recording/start   → start a new recording session
POST /api/recording/stop    → stop current recording and trigger POST processing
POST /api/recording/pause   → pause current recording
POST /api/recording/resume  → resume a paused recording

All endpoints delegate to MeetingOrchestrator which owns the session state.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class StartRequest(BaseModel):
    title: Optional[str] = Field(None, description="Meeting title (auto-generated if omitted)")
    system_device_id: Optional[int] = Field(None, description="System audio loopback device ID")
    mic_device_id: Optional[int] = Field(None, description="Microphone device ID")
    language: str = Field("vi", description="Primary language hint: vi, en, or auto")
    hotwords: list[str] = Field(default_factory=list, description="Domain hotwords for ASR boosting")
    consent_recording: bool = Field(False, description="Consent to save audio file (Decree 356)")
    consent_voiceprint: bool = Field(False, description="Consent to extract voiceprints (Decree 356)")
    template_name: str = Field("general_vi", description="Summary template name")
    llm_provider: str = Field("ollama", description="LLM provider: ollama, claude, openai, gemini")
    silence_timeout: int = Field(300, description="Auto-stop after N seconds of silence (0=disabled)")


class StopRequest(BaseModel):
    meeting_id: str


class PauseRequest(BaseModel):
    meeting_id: str


class ResumeRequest(BaseModel):
    meeting_id: str


@router.post("/start")
async def start_recording(req: StartRequest):
    """Start a new recording session.

    Creates a meeting in the database, opens audio streams, and begins
    LIVE transcription. Returns the meeting_id for all subsequent calls.
    """
    from backend.pipeline.orchestrator import get_orchestrator

    orch = get_orchestrator()

    try:
        meeting_id = await orch.start_meeting(
            title=req.title,
            system_device_id=req.system_device_id,
            mic_device_id=req.mic_device_id,
            language=req.language,
            hotwords=req.hotwords,
            consent_recording=req.consent_recording,
            consent_voiceprint=req.consent_voiceprint,
            template_name=req.template_name,
            llm_provider=req.llm_provider,
            silence_timeout=req.silence_timeout,
        )
        return {
            "meeting_id": meeting_id,
            "status": "recording",
            "message": "Recording started",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/stop")
async def stop_recording(req: StopRequest):
    """Stop a recording session and trigger POST processing.

    The pipeline will:
    1. Stop audio capture
    2. Run VibeVoice POST transcription (high-accuracy)
    3. Run LLM summarization
    4. Notify clients via WebSocket ("complete")
    """
    from backend.pipeline.orchestrator import get_orchestrator

    orch = get_orchestrator()

    if not orch.is_meeting_active(req.meeting_id):
        raise HTTPException(status_code=404, detail="Meeting not found or not active")

    try:
        await orch.stop_meeting(req.meeting_id)
        return {
            "meeting_id": req.meeting_id,
            "status": "processing",
            "message": "Recording stopped — POST processing started",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/pause")
async def pause_recording(req: PauseRequest):
    """Pause audio capture (buffer is retained)."""
    from backend.pipeline.orchestrator import get_orchestrator

    orch = get_orchestrator()

    if not orch.is_meeting_active(req.meeting_id):
        raise HTTPException(status_code=404, detail="Meeting not found or not active")

    try:
        await orch.pause_meeting(req.meeting_id)
        return {"meeting_id": req.meeting_id, "status": "paused"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resume")
async def resume_recording(req: ResumeRequest):
    """Resume a paused recording."""
    from backend.pipeline.orchestrator import get_orchestrator

    orch = get_orchestrator()

    try:
        await orch.resume_meeting(req.meeting_id)
        return {"meeting_id": req.meeting_id, "status": "recording"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status/{meeting_id}")
async def recording_status(meeting_id: str):
    """Get current state of a recording session."""
    from backend.pipeline.orchestrator import get_orchestrator

    orch = get_orchestrator()
    state = orch.get_meeting_state(meeting_id)

    if state is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return {"meeting_id": meeting_id, "status": state}
