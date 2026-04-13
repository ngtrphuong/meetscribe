"""Meetings REST API endpoints.

GET    /api/meetings                  → paginated meeting list
GET    /api/meetings/{id}             → meeting detail + summary + actions
GET    /api/meetings/{id}/transcript  → full transcript segments
GET    /api/meetings/{id}/actions     → action items
POST   /api/meetings/{id}/summarize   → re-run LLM summarization
POST   /api/meetings/{id}/reprocess   → re-run VibeVoice POST transcription
DELETE /api/meetings/{id}/purge       → Decree 356 full purge

File: backend/api/meetings.py
"""

from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel

router = APIRouter()


class SummarizeRequest(BaseModel):
    template: str = "general_vi"
    llm_provider: str = "ollama"


@router.get("")
async def list_meetings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    language: Optional[str] = Query(None, description="vi or en"),
    status: Optional[str] = Query(None),
):
    from backend.storage.repository import list_meetings as db_list
    meetings = await db_list(page=page, per_page=per_page, language=language, status=status)
    return {"meetings": [m.model_dump() for m in meetings], "page": page, "per_page": per_page}


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str):
    from backend.storage.repository import get_meeting_detail
    detail = await get_meeting_detail(meeting_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return detail.model_dump()


@router.get("/{meeting_id}/transcript")
async def get_transcript(meeting_id: str):
    from backend.storage.repository import get_transcript, get_meeting
    meeting = await get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    segments = await get_transcript(meeting_id)
    return {"meeting_id": meeting_id, "segments": [s.model_dump() for s in segments]}


@router.get("/{meeting_id}/actions")
async def get_actions(meeting_id: str):
    from backend.storage.repository import list_action_items, get_meeting
    meeting = await get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    items = await list_action_items(meeting_id)
    return {"meeting_id": meeting_id, "action_items": [i.model_dump() for i in items]}


@router.post("/{meeting_id}/summarize")
async def summarize_meeting(meeting_id: str, req: SummarizeRequest):
    """Re-run LLM summarization with a (possibly different) template/provider."""
    from backend.storage.repository import get_transcript, get_meeting, save_summary
    from backend.llm.summarizer import MeetingSummarizer
    from backend.asr.base import TranscriptSegment
    from backend.config import settings

    meeting = await get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    segments_db = await get_transcript(meeting_id)
    if not segments_db:
        raise HTTPException(status_code=400, detail="No transcript segments found")

    asr_segments = [
        TranscriptSegment(
            text=s.text,
            start_time=s.start_time,
            end_time=s.end_time,
            confidence=s.confidence or 0.9,
            language=s.language or "vi",
            speaker=s.speaker_label,
            source=s.source,
        )
        for s in segments_db
    ]

    summarizer = MeetingSummarizer()
    summary_text = await summarizer.summarize(
        segments=asr_segments,
        template_name=req.template,
        provider_name=req.llm_provider,
        meeting_title=meeting.title,
        started_at=meeting.started_at,
        duration_seconds=meeting.duration_seconds or 0,
    )

    summary = await save_summary(
        meeting_id=meeting_id,
        content=summary_text,
        template_name=req.template,
        llm_provider=req.llm_provider,
        llm_model=settings.llm_model,
    )

    return summary.model_dump()


@router.post("/{meeting_id}/reprocess")
async def reprocess_meeting(meeting_id: str):
    """Re-run VibeVoice POST transcription on stored audio."""
    from backend.storage.repository import get_meeting

    meeting = await get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not meeting.audio_retained or not meeting.audio_file_path:
        raise HTTPException(
            status_code=400,
            detail="No audio file available. Audio must be retained (consent_recording=True).",
        )

    # Run POST ASR in background
    import asyncio
    asyncio.create_task(_reprocess_background(meeting_id, meeting.audio_file_path))

    return {"meeting_id": meeting_id, "status": "reprocessing"}


@router.delete("/{meeting_id}/purge")
async def purge_meeting(meeting_id: str):
    """Full data purge (Decree 356 data subject right)."""
    from backend.compliance.data_purge import purge_meeting as do_purge

    result = await do_purge(meeting_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"meeting_id": meeting_id, "purged": result}


@router.post("/import")
async def import_audio(
    file: UploadFile = File(..., description="Audio/video file to transcribe"),
    title: Optional[str] = Form(None, description="Meeting title (auto-generated if omitted)"),
    language: str = Form("vi", description="Primary language: vi, en, auto"),
    template: str = Form("general_vi", description="Summary template name"),
    llm_provider: str = Form("ollama", description="LLM provider: ollama, claude"),
    asr_engine: str = Form("vibevoice", description="ASR engine: vibevoice, faster-whisper, phowhisper, parakeet-vi"),
    consent_recording: bool = Form(False, description="Retain original audio file"),
):
    """Import an audio/video file, transcribe it, and generate a summary.

    Supported formats: WAV, MP3, M4A, OGG, FLAC, AAC, MP4, WEBM, MKV, AVI, MOV, TS

    Returns the meeting_id immediately; transcription runs in the background.
    Poll GET /api/meetings/{id} for status transitions:
      processing → complete (or error)
    """
    from backend.audio.file_import import import_audio_file, SUPPORTED_EXTENSIONS
    from backend.storage.repository import create_meeting, update_meeting
    import asyncio, tempfile, pathlib

    suffix = pathlib.Path(file.filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Save uploaded file to a temp location
    tmp_src = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await file.read()
        tmp_src.write(content)
        tmp_src.flush()
        src_path = tmp_src.name
    finally:
        tmp_src.close()

    # Create meeting record
    meeting_title = title or f"Import: {file.filename or 'audio'}"
    meeting = await create_meeting(
        title=meeting_title,
        language=language if language != "auto" else "vi",
        asr_post_engine=asr_engine,
        llm_provider=llm_provider,
        template_name=template,
        consent_recording=consent_recording,
        consent_voiceprint=False,
    )
    meeting_id = meeting.id
    # Immediately mark as processing (create_meeting sets status='recording')
    await update_meeting(meeting_id, status="processing")

    # Run import + transcription in background
    asyncio.create_task(
        _import_background(meeting_id, src_path, language, template, llm_provider, asr_engine),
        name=f"import-{meeting_id}",
    )

    return {
        "meeting_id": meeting_id,
        "status": "processing",
        "message": f"File '{file.filename}' received — transcription started",
    }


async def _import_background(
    meeting_id: str,
    src_path: str,
    language: str,
    template_name: str,
    llm_provider: str,
    asr_engine: str = "vibevoice",
) -> None:
    """Convert → POST ASR → LLM summarization → mark complete."""
    import os
    from backend.api.websocket import manager
    from backend.audio.file_import import import_audio_file, get_audio_duration
    from backend.storage.repository import (
        insert_segments_bulk, save_summary, update_meeting,
    )
    from backend.storage.models import TranscriptSegmentDB
    from backend.asr.engine_factory import ASREngineFactory
    from backend.asr.base import TranscriptSegment
    from backend.llm.summarizer import MeetingSummarizer
    from backend.storage.repository import get_meeting
    from backend.config import settings

    await manager.send_status(meeting_id, "processing", "Converting audio…")

    try:
        # Step 1: Convert to 16kHz mono WAV
        wav_path = await import_audio_file(src_path)
        duration = get_audio_duration(wav_path)

        # Step 2: POST ASR (with fallback chain)
        await manager.send_status(meeting_id, "processing", "Transcribing audio…")
        engine_order = [asr_engine]
        if asr_engine not in ("faster-whisper", "phowhisper"):
            engine_order += ["faster-whisper"]  # fallback

        segments = []
        used_engine = None
        for eng_name in engine_order:
            try:
                engine = ASREngineFactory.create(eng_name)
                init_kwargs = {"quantization": settings.vibevoice_quantization} if eng_name == "vibevoice" else {}
                await engine.initialize(init_kwargs)
                segments = await engine.transcribe_file(wav_path)
                await engine.shutdown()
                used_engine = eng_name
                break
            except Exception as eng_err:
                import structlog as _sl
                _sl.get_logger(__name__).warning("ASR engine failed, trying fallback", engine=eng_name, error=str(eng_err))
                try:
                    await engine.shutdown()
                except Exception:
                    pass

        if not used_engine:
            raise RuntimeError("All ASR engines failed — no segments produced")

        db_segs = [
            TranscriptSegmentDB(
                meeting_id=meeting_id,
                text=s.text,
                start_time=s.start_time,
                end_time=s.end_time,
                confidence=s.confidence,
                language=s.language,
                speaker_label=s.speaker,
                source="post",
            )
            for s in segments if s.text.strip()
        ]
        await insert_segments_bulk(db_segs)

        # Step 3: LLM summarization
        meeting = await get_meeting(meeting_id)
        if db_segs and meeting:
            await manager.send_status(meeting_id, "processing", "Generating summary…")
            asr_segments = [
                TranscriptSegment(
                    text=s.text, start_time=s.start_time, end_time=s.end_time,
                    confidence=s.confidence or 0.9, language=s.language or "vi",
                    speaker=s.speaker_label, source="post",
                )
                for s in db_segs
            ]
            summarizer = MeetingSummarizer()
            summary_text = await summarizer.summarize(
                segments=asr_segments,
                template_name=template_name,
                provider_name=llm_provider,
                meeting_title=meeting.title,
                started_at=meeting.started_at,
                duration_seconds=duration,
            )
            await save_summary(
                meeting_id=meeting_id,
                content=summary_text,
                template_name=template_name,
                llm_provider=llm_provider,
                llm_model=settings.llm_model,
            )

        # Step 4: Mark complete
        await update_meeting(
            meeting_id,
            status="complete",
            ended_at=datetime.datetime.now(datetime.UTC).isoformat(),
            duration_seconds=int(duration),
        )
        await manager.send_status(meeting_id, "complete", "Transcription complete")

    except Exception as exc:
        import structlog as _sl
        _sl.get_logger(__name__).error("Import background failed", meeting_id=meeting_id, error=str(exc))
        await update_meeting(meeting_id, status="error")
        await manager.send_status(meeting_id, "error", str(exc))
    finally:
        # Cleanup temp files
        for path in [src_path]:
            try:
                os.unlink(path)
            except OSError:
                pass


async def _reprocess_background(meeting_id: str, audio_path: str) -> None:
    from backend.api.websocket import manager
    from backend.storage.repository import (
        delete_segments_by_source, insert_segments_bulk, update_meeting
    )
    from backend.storage.models import TranscriptSegmentDB
    from backend.asr.engine_factory import ASREngineFactory
    from backend.config import settings

    await manager.send_status(meeting_id, "processing", "Re-running POST transcription…")

    try:
        engine = ASREngineFactory.create(settings.asr_post_engine)
        await engine.initialize({"quantization": settings.vibevoice_quantization})
        segments = await engine.transcribe_file(audio_path)
        await engine.shutdown()

        db_segs = [
            TranscriptSegmentDB(
                meeting_id=meeting_id,
                text=s.text,
                start_time=s.start_time,
                end_time=s.end_time,
                confidence=s.confidence,
                language=s.language,
                speaker_label=s.speaker,
                source="post",
            )
            for s in segments if s.text.strip()
        ]

        await delete_segments_by_source(meeting_id, "post")
        await insert_segments_bulk(db_segs)
        await update_meeting(meeting_id, status="complete")
        await manager.send_status(meeting_id, "complete", "Reprocessing complete")

    except Exception as exc:
        await manager.send_status(meeting_id, "error", str(exc))
